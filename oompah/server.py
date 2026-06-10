"""FastAPI server with htmx kanban dashboard, JSON REST API, and WebSocket push."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import re
import signal
import threading
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from fastapi import FastAPI, File, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, Response

from oompah.events import EventType
from oompah.scm import (
    ReviewRequest,
    detect_provider,
    extract_repo_slug,
)
from oompah.webhooks import (
    WebhookEvent,
    match_project_by_repo,
    parse_github_webhook,
    parse_gitlab_webhook,
    validate_github_signature,
    validate_gitlab_token,
)
from oompah.backlog_webhooks import validate_backlog_webhook_signature
from oompah.focus import (
    BUILTIN_FOCI,
    DEFAULT_FOCUS,
    Focus,
    FocusSuggestion,
    load_foci,
    load_suggestions,
    save_foci,
    score_focus,
    update_suggestion_status,
)
from oompah.agent_profile_store import (
    AgentProfileError,
    AgentProfileStore,
    DEFAULT_AGENT_PROFILES_PATH,
)
from oompah.cache import TTLCache
from oompah.error_watcher import ErrorWatcher, ProjectLogWatcherManager
from oompah.ipc import OrchestratorIPC, get_ipc
from oompah.issue_enhancer import (
    EnhancementResult,
    IssueEnhancerError,
    enhance_issue,
    has_quality_source,
)
from oompah.models import AgentProfile
from oompah.projects import ProjectError, ProjectStore
from oompah.providers import ProviderStore
from oompah.roles import Candidate, RoleError, RoleStore, VALID_STRATEGIES, DEFAULT_STRATEGY
from oompah.statuses import (
    ARCHIVED,
    CANONICAL_STATUSES,
    IN_PROGRESS,
    IN_REVIEW,
    MERGED,
    NEEDS_ANSWER,
    NEEDS_CI_FIX,
    NEEDS_HUMAN,
    NEEDS_REBASE,
    OPEN,
    canonicalize_status,
    epic_rollup_state,
)
from oompah.agent_profile_store import (
    AgentProfileStore,
    AgentProfileStoreError,
)

if TYPE_CHECKING:
    from oompah.orchestrator import Orchestrator

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_template_cache: dict[str, str] = {}


def _load_template(name: str) -> str:
    """Load an HTML template, cached in memory after first read."""
    cached = _template_cache.get(name)
    if cached is not None:
        return cached
    content = (_TEMPLATES_DIR / name).read_text()
    _template_cache[name] = content
    return content


_NO_CACHE_HEADERS: dict[str, str] = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}


def _html_response(name: str) -> HTMLResponse:
    """Return an HTMLResponse for *name* with cache-busting headers.

    HTML pages are never cached by the browser so that after a server
    auto-update + restart users immediately receive the latest template
    rather than a browser-cached stale copy that may be missing recently
    added JavaScript functions (e.g. toggleHideMerged).
    """
    return HTMLResponse(content=_load_template(name), headers=_NO_CACHE_HEADERS)


# ---------------------------------------------------------------------------
# ASGI lifespan — Granian path
# ---------------------------------------------------------------------------
# When Granian is the HTTP server it owns the process; the orchestrator and
# all long-lived services are started *inside* the ASGI lifespan so they
# share the worker's event loop (required for the WebSocket _broadcast path).
#
# Guard: the lifespan only activates when ``OOMPAH_EMBED_ORCHESTRATOR=1`` is
# set by ``__main__._run_granian()``.  For the uvicorn path and tests the
# lifespan is a no-op (just ``yield``).
#
# Error handling: ``setup_services()`` raises ``StartupError`` instead of
# calling ``sys.exit(1)``.  If we let any exception (including SystemExit)
# escape the lifespan coroutine, Python's asyncio machinery stores it in the
# task and later emits "Task exception was never retrieved", and Granian may
# respawn the worker.  Instead we catch ``StartupError`` here, log it, and
# call ``os._exit(1)`` which terminates the process immediately without
# unwinding the Python stack — the exception never escapes the task.

_GRANIAN_RESTART_SENTINEL = ".oompah-granian-restart"


@contextlib.asynccontextmanager
async def _lifespan(app: "FastAPI"):  # noqa: F821 – forward ref ok
    """ASGI lifespan context manager.

    No-op (uvicorn / tests): ``OOMPAH_EMBED_ORCHESTRATOR`` not set → yield.

    Granian path: ``OOMPAH_EMBED_ORCHESTRATOR=1`` → run ``setup_services()``,
    start the orchestrator and supporting tasks, ``yield``, then tear down on
    shutdown.

    On :class:`~oompah.bootstrap.StartupError` (validation failure): log the
    error and call ``os._exit(1)`` so the exception never escapes the
    coroutine (avoids "Task exception was never retrieved" and Granian worker
    respawn loops).
    """
    embed = os.environ.get("OOMPAH_EMBED_ORCHESTRATOR")
    if not embed:
        # No-op path: uvicorn runs the orchestrator outside the lifespan.
        yield
        return

    # -----------------------------------------------------------------
    # Granian path: set up and run all services inside the worker loop.
    # -----------------------------------------------------------------
    import asyncio as _asyncio

    from oompah.bootstrap import Services, StartupError, setup_services
    from oompah.config import ServiceConfig, WorkflowError, load_workflow
    from watchfiles import awatch

    workflow_path = (
        os.environ.get("OOMPAH_WORKFLOW_PATH")
        or os.environ.get("OOMPAH_GRANIAN_WORKFLOW")
        or "./WORKFLOW.md"
    )
    cli_port_s = os.environ.get("OOMPAH_SERVER_PORT_OVERRIDE")
    cli_port: int | None = int(cli_port_s) if cli_port_s else None
    start_paused = os.environ.get("OOMPAH_START_PAUSED") == "1"

    try:
        services: Services = await setup_services(
            workflow_path, cli_port=cli_port, start_paused=start_paused,
        )
    except StartupError as exc:
        # Clean abort: log, then terminate the process without letting the
        # exception escape this coroutine (avoids asyncio task-exception
        # noise and Granian worker respawn).
        logger.critical(
            "Startup validation failed — aborting (no worker respawn): %s",
            exc,
        )
        # Signal the Granian supervisor to stop before we exit the worker.
        try:
            os.kill(os.getppid(), signal.SIGTERM)
        except ProcessLookupError:
            pass
        os._exit(1)  # noqa: SLF001 — intentional hard exit

    # Wire the orchestrator into the server's global so request handlers
    # can reach it.
    set_orchestrator(services.orchestrator)

    # Wire forwarder health alerts into the orchestrator.
    def _on_forwarder_status(status: dict) -> None:
        orch = services.orchestrator
        orch._alerts = [
            a for a in orch._alerts if a.get("source") != "webhook_forwarder"
        ]
        if not status.get("available"):
            detail = status.get("detail") or "gh-webhook extension unavailable"
            orch._alerts.append({
                "level": "warning",
                "source": "webhook_forwarder",
                "message": (
                    f"Webhooks degraded: {detail}. "
                    "Install with `make install-gh-extensions`. "
                    "Falling back to periodic full-sync (slower)."
                ),
            })

    services.webhook_forwarder._status_callback = _on_forwarder_status
    await services.webhook_forwarder.start()

    # Workflow file watcher task.
    async def _watch_workflow() -> None:
        try:
            async for _changes in awatch(workflow_path):
                logger.info("Workflow file changed, reloading")
                try:
                    from oompah.config import (
                        ServiceConfig,
                        WorkflowError,
                        load_workflow,
                        validate_dispatch_config,
                    )

                    new_wf = load_workflow(workflow_path)
                    new_config = ServiceConfig.from_workflow(new_wf)
                    errs = validate_dispatch_config(new_config)
                    if errs:
                        logger.error(
                            "Invalid workflow reload: %s", "; ".join(errs),
                        )
                        continue
                    services.orchestrator.reload_config(
                        new_config, new_wf.prompt_template,
                    )
                except WorkflowError as exc:
                    logger.error("Workflow reload failed: %s", exc)
        except _asyncio.CancelledError:
            pass

    async def _supervise() -> None:
        try:
            while True:
                await _asyncio.sleep(0.5)
                if services.orchestrator.wants_restart:
                    logger.info(
                        "Orchestrator wants restart; signalling Granian supervisor"
                    )
                    Path(_GRANIAN_RESTART_SENTINEL).touch()
                    os.kill(os.getppid(), signal.SIGTERM)
                    return
        except _asyncio.CancelledError:
            pass

    watch_task = _asyncio.create_task(_watch_workflow())
    orch_task = _asyncio.create_task(services.orchestrator.run())
    supervise_task = _asyncio.create_task(_supervise())

    try:
        yield  # --- app is running ---
    finally:
        # Shutdown: stop all background tasks.
        await services.orchestrator.stop()
        await services.webhook_forwarder.stop()
        supervise_task.cancel()
        watch_task.cancel()
        orch_task.cancel()
        try:
            await _asyncio.wait_for(orch_task, timeout=5.0)
        except (_asyncio.CancelledError, _asyncio.TimeoutError):
            pass


app = FastAPI(title="oompah", version="0.1.0", lifespan=_lifespan)

# Serve static assets (favicon, etc.) from oompah/static/
from fastapi.staticfiles import StaticFiles

_STATIC_DIR = Path(__file__).resolve().parent / "static"
if _STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

# Favicon bytes cached at module load time to avoid a synchronous disk read
# on every request (hot path — browsers hit /favicon.ico on every page load).
_FAVICON_PATH = _STATIC_DIR / "favicon.svg"
_FAVICON_CACHE: bytes | None = _FAVICON_PATH.read_bytes() if _FAVICON_PATH.is_file() else None


@app.get("/favicon.ico")
@app.get("/favicon.svg")
async def favicon():
    """Serve the SVG favicon at both /favicon.ico and /favicon.svg.

    Browsers request /favicon.ico by default; modern browsers will accept
    an SVG response there as long as the Content-Type is correct.

    The favicon bytes are loaded once at module import time and cached in
    ``_FAVICON_CACHE`` so that no synchronous disk I/O occurs on the event
    loop during request handling.
    """
    if _FAVICON_CACHE is None:
        return Response(status_code=404)
    return Response(
        content=_FAVICON_CACHE,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=86400"},
    )


# Global provider store
_provider_store = ProviderStore()

# Global role store. Wired to the same instance the orchestrator uses
# via set_orchestrator(); empty here so server-side imports don't crash.
# See epic oompah-zlz_2-xau7 for the decoupling rationale.
_role_store: RoleStore = RoleStore(provider_store=_provider_store)

# Global agent profile store. Lazily seeded from WORKFLOW.md by
# ServiceConfig.from_workflow on first boot; thereafter the JSON file
# is the source of truth and is the path API writes go through. A
# fresh empty store is created here so server-side imports don't
# crash; the orchestrator wires its real store into both itself and
# this server module via :func:`set_orchestrator` at startup, which
# also registers the reload callback that fires on every write through
# /api/v1/agent-profiles (oompah-zlz_2-mif).
_agent_profile_store = AgentProfileStore()

# Global reference to orchestrator, set during startup
_orchestrator: Orchestrator | None = None

# IPC layer for multi-process mode (TASK-469.5.1).
# Populated from OOMPAH_IPC_DB_PATH if set; None in single-process mode.
# In API-only mode (no orchestrator), this is used to read state/issues
# from the SQLite cache written by the scheduler process and to enqueue
# commands for the scheduler.
_ipc: OrchestratorIPC | None = get_ipc()

# Error watcher — created when orchestrator is set
_error_watcher: ErrorWatcher | None = None

# Project log watcher manager — watches log files for all projects
_log_watcher_manager: ProjectLogWatcherManager | None = None

# Connected WebSocket clients
_ws_clients: set[WebSocket] = set()

# Per-project ACP console manager (oompah-zlz_2-ebwe). Constructed in
# set_orchestrator() once the project/provider/role stores are wired,
# then accessed by the WS handler and the GET /api/v1/console endpoints.
_console_manager: Any = None

_BACKLOG_TASK_IDENTIFIER_RE = re.compile(r"^TASK-(\d+(?:\.\d+)*)$", re.IGNORECASE)


def _project_names_by_id(orch) -> dict[str, str]:
    """Return known project display names keyed by project id."""
    try:
        projects = orch.project_store.list_all()
    except Exception:
        return {}

    names: dict[str, str] = {}
    for project in projects:
        project_id = getattr(project, "id", None)
        project_name = getattr(project, "name", None)
        if isinstance(project_id, str) and isinstance(project_name, str):
            if project_id and project_name:
                names[project_id] = project_name
    return names


def _display_identifier(identifier: str, project_name: str | None) -> str:
    """Format Backlog task ids for display without changing their real id."""
    if not project_name:
        return identifier
    match = _BACKLOG_TASK_IDENTIFIER_RE.match(identifier)
    if not match:
        return identifier
    return f"{project_name}-{match.group(1)}"


def _issue_display_fields(
    issue,
    project_names: dict[str, str],
) -> dict[str, str | None]:
    project_name = project_names.get(issue.project_id or "")
    # Prefer the tracker's own display_identifier when set (e.g. GitHub issues
    # use a short form like "tasks#1234"). Fall back to the Backlog-specific
    # formatter so existing TASK-NNN identifiers still appear as
    # "ProjectName-NNN" in the dashboard.
    di = getattr(issue, "display_identifier", None) or _display_identifier(
        issue.identifier, project_name
    )
    return {
        "project_name": project_name,
        "display_identifier": di,
    }


def set_orchestrator(orch: Orchestrator) -> None:
    global _orchestrator, _error_watcher, _log_watcher_manager
    global _agent_profile_store, _role_store, _provider_store
    _orchestrator = orch
    # Share the orchestrator's profile store so /api/v1/agent-profiles
    # writes go to the same in-memory state the dispatch loop reads.
    _agent_profile_store = orch.agent_profile_store
    # Same for the role store (epic xau7).
    _role_store = orch.role_store
    # Keep _provider_store in sync so Phase-2 validation in api_put_roles
    # and Phase-3 _role_store.set() use the same store instance.
    _provider_store = orch.provider_store
    # Full observer: state + issues refresh (for dispatch, close, state changes)
    orch._observers.append(_on_orchestrator_change)
    # State-only observer: state broadcast without issues re-fetch (for agent activity)
    orch._state_only_observers.append(_on_state_only_change)
    orch._activity_observers.append(_on_agent_activity)

    # Wire AgentProfileStore -> Orchestrator partial reload (oompah-zlz_2-mif).
    # Every successful create/update/delete on the store fires this callback,
    # which queues the new profile list onto the orchestrator. The swap is
    # applied at the start of the next _tick() — a quiescent point — so the
    # current tick (if any) sees a single consistent profile list end-to-end.
    def _on_profiles_changed(profiles, source: str) -> None:
        try:
            orch.replace_agent_profiles(profiles, source=f"api:{source}")
        except Exception as exc:  # noqa: BLE001 — callback must never break a write
            logger.error(
                "Failed to schedule agent profile reload (source=%s): %s",
                source,
                exc,
            )

    _agent_profile_store.set_reload_callback(_on_profiles_changed)
    # Error watcher: creates tasks for backend/frontend errors
    _error_watcher = ErrorWatcher(orch.tracker)
    _error_watcher.install_log_handler("oompah")
    # Register so the orchestrator can ask it to auto-close transient
    # error tasks when an issue's retry path succeeds (oompah-zlz_2-0nc).
    orch.register_error_watcher(_error_watcher, project_id=None)

    # Project log watcher manager: watches log files for projects that set log_path.
    # Each project gets its own ErrorWatcher backed by the project's tracker so
    # error tasks are created in the correct project.
    def _make_error_watcher(project_id: str) -> ErrorWatcher:
        tracker = orch._tracker_for_project(project_id)
        watcher = ErrorWatcher(tracker, project_id=project_id)
        # Same auto-close hook as the global watcher above, scoped per project.
        orch.register_error_watcher(watcher, project_id=project_id)
        return watcher

    _log_watcher_manager = ProjectLogWatcherManager(_make_error_watcher)
    _log_watcher_manager.sync_watchers(orch.project_store.list_all())

    # Per-project ACP console manager (oompah-zlz_2-ebwe + oompah-zlz_2-g73s).
    # Wires the new modular console layer:
    #   * ``oompah.console_store.ConsoleStore`` for on-disk JSONL transcripts +
    #     meta sidecar (replaces the legacy per-project store).
    #   * ``oompah.console.ConsoleSessionManager`` for the in-memory
    #     ConsoleSession registry (replaces ``oompah.console_legacy``).
    #   * The on_event_factory hook fans every persisted event over the
    #     existing WS pool as ``{type:"console_event", project_id, event}``.
    #   * The workspace_resolver supplies each ConsoleSession with the
    #     project's repo_path so SDK tools execute in the right tree.
    global _console_manager
    from oompah.console import ConsoleSessionManager
    from oompah.console_format import ConsoleEvent
    from oompah.console_store import ConsoleStore, DEFAULT_CONSOLE_ROOT

    console_store = ConsoleStore(root=DEFAULT_CONSOLE_ROOT)

    def _resolve_console_workspace(project_id: str) -> str | None:
        try:
            project = orch.project_store.get(project_id)
        except Exception:
            return None
        if project is None:
            return None
        return project.repo_path or None

    def _make_console_event_callback(
        project_id: str,
    ) -> Callable[["ConsoleEvent"], None]:
        """Per-session factory: returns the ``on_event`` callable the
        ConsoleSession invokes for every persisted event.

        The callable schedules ``_broadcast`` onto whatever asyncio
        loop is currently running. ``_broadcast`` is a no-op when
        there are no clients, so this is safe to call from any
        thread that has a running loop (the runner task itself, or
        an executor-thread call into the session). Falls back to
        silent skip when no loop is available (synchronous unit
        tests).
        """

        def _on_event(event: "ConsoleEvent") -> None:
            if not _ws_clients:
                return
            try:
                payload = event.to_dict()
            except Exception as exc:
                logger.debug(
                    "console on_event: failed to serialize event for %s: %s",
                    project_id,
                    exc,
                )
                return
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                return
            if not loop.is_running():
                return
            try:
                loop.create_task(
                    _broadcast(
                        {
                            "type": "console_event",
                            "project_id": project_id,
                            "event": payload,
                        }
                    )
                )
            except RuntimeError:
                # Loop closed underneath us — give up quietly.
                return

        return _on_event

    _console_manager = ConsoleSessionManager(
        store=console_store,
        provider_store=orch.provider_store,
        role_store=orch.role_store,
        on_event_factory=_make_console_event_callback,
        workspace_resolver=_resolve_console_workspace,
    )


def _get_orchestrator() -> Orchestrator:
    if _orchestrator is None:
        raise RuntimeError("Orchestrator not initialized")
    return _orchestrator


def _set_agent_profile_store(store: AgentProfileStore) -> None:
    """Test-only: replace the global agent profile store.

    Not part of the public API. Used by integration tests that need the
    store to point at a tmp_path so test runs don't collide with each
    other or with the dev environment's .oompah/agent_profiles.json.
    """
    global _agent_profile_store
    _agent_profile_store = store


def _get_agent_profile_store() -> AgentProfileStore:
    """Return the process-wide agent profile store (for tests/inspection)."""
    return _agent_profile_store


_last_state_broadcast = 0.0
_last_issues_broadcast = 0.0
_ISSUES_THROTTLE_MS = 3000  # Don't fetch/broadcast issues more than every 3s
# Dedicated thread pool for API requests so they don't compete with tick threads
from concurrent.futures import ThreadPoolExecutor

_api_thread_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="api")
_issues_broadcast_pending = False
_STATE_THROTTLE_MS = 500  # Don't broadcast state more than every 500ms
_ISSUES_SNAPSHOT_STALE_MS = 5000
_issues_snapshot_lock = threading.Lock()
_issues_snapshot: dict[str, Any] = {
    "data": None,
    "orch_id": None,
    "created_at_monotonic": 0.0,
    "created_at_wall": None,
    "duration_ms": None,
    "issue_count": 0,
    "error": None,
}
_issues_refresh_task: asyncio.Task | None = None
_api_metrics_lock = threading.Lock()
_api_metrics: dict[str, dict[str, Any]] = {}

# ---------------------------------------------------------------------------
# State snapshot cache for combined-mode API responsiveness
# ---------------------------------------------------------------------------
# In combined (single-process) mode the /api/v1/state endpoint previously
# called orch.get_snapshot() on every request, which rebuilds state from
# scratch and can block behind GIL contention from heavy maintenance work
# (YAML parsing, archive scans).  Instead we cache the last snapshot emitted
# by the orchestrator's observer callbacks and serve it without recomputing.
# Cache TTL is generous (30 s) — observers fire on every tick / agent event,
# so in practice the snapshot is always fresher than this limit.
_STATE_SNAPSHOT_MAX_AGE_S = 30.0
_state_snapshot_lock = threading.Lock()
_state_snapshot: dict[str, Any] | None = None
_state_snapshot_at: float = 0.0  # monotonic seconds


def _update_state_snapshot(snapshot: dict[str, Any]) -> None:
    """Store a fresh snapshot from an orchestrator observer callback."""
    global _state_snapshot, _state_snapshot_at
    with _state_snapshot_lock:
        _state_snapshot = snapshot
        _state_snapshot_at = time.monotonic()


def _read_state_snapshot() -> dict[str, Any] | None:
    """Return the cached snapshot if it is fresh enough, else None."""
    with _state_snapshot_lock:
        if _state_snapshot is None:
            return None
        age = time.monotonic() - _state_snapshot_at
        if age > _STATE_SNAPSHOT_MAX_AGE_S:
            return None
        return dict(_state_snapshot)


# Shared response cache for API endpoints
_api_cache = TTLCache()


def _state_key(state: str | None) -> str:
    return canonicalize_status(state).strip().lower().replace("-", "_").replace(" ", "_")


def _dashboard_state(state: str | None) -> str:
    """Map tracker-native states onto canonical dashboard statuses."""
    return canonicalize_status(state)


_DASHBOARD_STATE_KEYS = tuple(_dashboard_state(status) for status in CANONICAL_STATUSES)


def _empty_state_counts() -> dict[str, int]:
    return {key: 0 for key in _DASHBOARD_STATE_KEYS}


def _empty_issue_board() -> dict[str, list]:
    return {key: [] for key in _DASHBOARD_STATE_KEYS}


def _record_api_latency(endpoint: str, duration_ms: float, *, ok: bool = True) -> None:
    with _api_metrics_lock:
        stats = _api_metrics.setdefault(
            endpoint,
            {
                "count": 0,
                "error_count": 0,
                "slow_count": 0,
                "last_ms": 0.0,
                "max_ms": 0.0,
                "total_ms": 0.0,
            },
        )
        stats["count"] += 1
        if not ok:
            stats["error_count"] += 1
        if duration_ms > 1000:
            stats["slow_count"] += 1
        stats["last_ms"] = round(duration_ms, 3)
        stats["max_ms"] = round(max(float(stats["max_ms"]), duration_ms), 3)
        stats["total_ms"] += duration_ms
        stats["avg_ms"] = round(stats["total_ms"] / stats["count"], 3)


def _api_metrics_snapshot() -> dict[str, dict[str, Any]]:
    with _api_metrics_lock:
        return {
            endpoint: {
                key: value
                for key, value in stats.items()
                if key != "total_ms"
            }
            for endpoint, stats in _api_metrics.items()
        }


def _issue_dashboard_state(issue) -> str:
    if "archive:yes" in (issue.labels or []):
        return _dashboard_state(ARCHIVED)
    return _dashboard_state(issue.state)


def _issue_count_from_board(board: dict[str, Any]) -> int:
    return sum(len(v) for v in board.values() if isinstance(v, list))


def _copy_issue_board(
    board: dict[str, Any], filter_project: str | None = None
) -> dict[str, list]:
    copied: dict[str, list] = {}
    for state in _DASHBOARD_STATE_KEYS:
        issues = board.get(state, [])
        if not isinstance(issues, list):
            issues = []
        if filter_project:
            issues = [i for i in issues if i.get("project_id") == filter_project]
        copied[state] = list(issues)
    for state, issues in board.items():
        if state in copied or not isinstance(issues, list):
            continue
        if filter_project:
            issues = [i for i in issues if i.get("project_id") == filter_project]
        copied[state] = list(issues)
    return copied


def _snapshot_refreshing_locked() -> bool:
    return _issues_refresh_task is not None and not _issues_refresh_task.done()


def _issues_snapshot_payload(
    *,
    filter_project: str | None = None,
    allow_empty: bool = False,
    orch: "Orchestrator | None" = None,
    include_meta: bool = False,
) -> dict[str, Any] | None:
    with _issues_snapshot_lock:
        data = _issues_snapshot.get("data")
        snapshot_orch_id = _issues_snapshot.get("orch_id")
        if (
            data is not None
            and orch is not None
            and snapshot_orch_id is not None
            and snapshot_orch_id != id(orch)
        ):
            data = None
        if data is None and not allow_empty:
            return None
        nowm = time.monotonic()
        created = float(_issues_snapshot.get("created_at_monotonic") or 0.0)
        age_ms = (nowm - created) * 1000 if created else None
        payload = _copy_issue_board(data or _empty_issue_board(), filter_project)
        if include_meta:
            payload["_meta"] = {
                "snapshot_age_ms": round(age_ms, 0) if age_ms is not None else None,
                "snapshot_created_at": _issues_snapshot.get("created_at_wall"),
                "refreshing": _snapshot_refreshing_locked(),
                "last_refresh_ms": _issues_snapshot.get("duration_ms"),
                "issue_count": _issue_count_from_board(data or {}),
                "error": _issues_snapshot.get("error"),
                "stale": (
                    age_ms is None or age_ms >= _ISSUES_SNAPSHOT_STALE_MS
                ),
            }
        return payload


def _issues_snapshot_headers(orch: "Orchestrator | None" = None) -> dict[str, str]:
    payload = _issues_snapshot_payload(
        allow_empty=True, orch=orch, include_meta=True
    )
    meta = (payload or {}).get("_meta", {})
    headers: dict[str, str] = {}
    if meta.get("snapshot_age_ms") is not None:
        headers["X-Oompah-Issues-Snapshot-Age-Ms"] = str(meta["snapshot_age_ms"])
    if meta.get("snapshot_created_at") is not None:
        headers["X-Oompah-Issues-Snapshot-Created-At"] = str(
            meta["snapshot_created_at"]
        )
    headers["X-Oompah-Issues-Refreshing"] = "true" if meta.get("refreshing") else "false"
    headers["X-Oompah-Issues-Stale"] = "true" if meta.get("stale") else "false"
    if meta.get("last_refresh_ms") is not None:
        headers["X-Oompah-Issues-Refresh-Ms"] = str(meta["last_refresh_ms"])
    headers["X-Oompah-Issues-Count"] = str(meta.get("issue_count", 0))
    return headers


def _set_issues_snapshot(
    data: dict[str, list],
    *,
    duration_ms: float,
    error: str | None = None,
    orch_id: int | None = None,
) -> None:
    with _issues_snapshot_lock:
        _issues_snapshot["data"] = data
        _issues_snapshot["orch_id"] = orch_id
        _issues_snapshot["created_at_monotonic"] = time.monotonic()
        _issues_snapshot["created_at_wall"] = datetime.now(timezone.utc).isoformat()
        _issues_snapshot["duration_ms"] = round(duration_ms, 3)
        _issues_snapshot["issue_count"] = _issue_count_from_board(data)
        _issues_snapshot["error"] = error
    _api_cache.set("issues:all", data, ttl_ms=60_000)


async def _ensure_issues_snapshot_refresh(
    orch: "Orchestrator",
    *,
    force: bool = False,
    broadcast: bool = False,
) -> None:
    """Start one background board refresh if the snapshot is absent/stale.

    The request path never waits for the refresh. This keeps the dashboard
    responsive even when the Backlog corpus takes tens of seconds to parse.
    """
    global _issues_refresh_task
    with _issues_snapshot_lock:
        existing = _issues_refresh_task
        if existing is not None and not existing.done():
            return
        created = float(_issues_snapshot.get("created_at_monotonic") or 0.0)
        snapshot_orch_id = _issues_snapshot.get("orch_id")
        if snapshot_orch_id is not None and snapshot_orch_id != id(orch):
            created = 0.0
        age_ms = (time.monotonic() - created) * 1000 if created else None
        if (
            not force
            and created
            and age_ms is not None
            and age_ms < _ISSUES_SNAPSHOT_STALE_MS
        ):
            return

        async def _runner() -> None:
            global _issues_refresh_task
            start = time.monotonic()
            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    _api_thread_pool, _fetch_and_serialize_issues, orch
                )
                duration_ms = (time.monotonic() - start) * 1000
                _set_issues_snapshot(result, duration_ms=duration_ms, orch_id=id(orch))
                if duration_ms > 1000:
                    logger.warning(
                        "Issues snapshot refresh slow: refresh=%.0fms issues=%d",
                        duration_ms,
                        _issue_count_from_board(result),
                    )
                if broadcast and _ws_clients:
                    payload = _issues_snapshot_payload(allow_empty=True, orch=orch)
                    await _broadcast({"type": "issues", "data": payload})
            except Exception as exc:
                duration_ms = (time.monotonic() - start) * 1000
                logger.debug("issues snapshot refresh failed: %s", exc)
                with _issues_snapshot_lock:
                    _issues_snapshot["error"] = str(exc)
                    _issues_snapshot["duration_ms"] = round(duration_ms, 3)
                if broadcast and _ws_clients:
                    payload = _issues_snapshot_payload(allow_empty=True, orch=orch)
                    await _broadcast({"type": "issues", "data": payload})
            finally:
                with _issues_snapshot_lock:
                    _issues_refresh_task = None

        _issues_refresh_task = asyncio.create_task(
            _runner(), name="issues-snapshot-refresh"
        )


async def _wait_for_issues_snapshot_refresh(timeout_ms: int = 250) -> None:
    with _issues_snapshot_lock:
        task = _issues_refresh_task
    if task is None or task.done():
        return
    try:
        await asyncio.wait_for(asyncio.shield(task), timeout=timeout_ms / 1000.0)
    except asyncio.TimeoutError:
        return


# Workflow rank for each canonical status (Backlog < Open < In Progress <
# ... < Done < Merged < Archived). Used to pick the "more advanced" status.
_STATUS_RANK = {s: i for i, s in enumerate(CANONICAL_STATUSES)}


def _status_rank(status: str) -> int:
    """Position of *status* in the canonical workflow order, or -1 if unknown."""
    return _STATUS_RANK.get(canonicalize_status(status), -1)


def _effective_display_status(orch, issue) -> str:
    """Status to display for *issue*, reconciling the default branch with the
    epic branch for shared-epic children.

    A shared-epic child records agent progress on the epic branch, while the
    operator's manual moves land on the default branch; neither is strictly
    authoritative until the epic merges. We show whichever is **further along
    the workflow**:

    * epic branch ahead (e.g. agent marked it Done/Merged) → show that, so the
      board doesn't keep a finished child in Open/In-Progress; and
    * default branch ahead (e.g. operator moved Backlog→Open before the epic
      branch caught up) → show that, so manual moves aren't reverted.

    Ties keep the default-branch value. Returns ``issue.state`` unchanged for
    non-shared / non-child issues, or on any lookup failure (display must
    never break the board).
    """
    parent_id = getattr(issue, "parent_id", None)
    project_id = getattr(issue, "project_id", None)
    identifier = getattr(issue, "identifier", None)
    if not (parent_id and project_id and identifier):
        return issue.state
    try:
        if orch._project_epic_strategy(project_id) != "shared":
            return issue.state
        epic_status = orch.project_store.read_task_status_in_epic_worktree(
            project_id, parent_id, identifier
        )
    except Exception:  # noqa: BLE001 — display path; fall back to default branch
        return issue.state
    if not epic_status:
        return issue.state
    if _status_rank(epic_status) > _status_rank(issue.state):
        return epic_status
    return issue.state


def _manual_needs_human_comment(
    identifier: str,
    issue,
    explicit_comment: object | None = None,
) -> str:
    text = str(explicit_comment or "").strip()
    if text:
        return text
    title = getattr(issue, "title", None) or identifier
    return (
        "Moved to Needs Human from the dashboard/API. "
        f"Human action required: inspect {identifier} ({title}), add the "
        "specific decision, missing information, or manual fix needed, then "
        "move the task back to Open when it is ready for agents again."
    )


def _mark_tracker_needs_human(
    tracker,
    identifier: str,
    comment: str,
    *,
    author: str = "oompah",
) -> None:
    if hasattr(tracker, "mark_needs_human"):
        tracker.mark_needs_human(identifier, comment, author=author)
        return
    tracker.update_issue(identifier, status=NEEDS_HUMAN)
    tracker.add_comment(identifier, comment, author=author)


def _fetch_open_reviews_for_api(
    projects: list[Any],
) -> tuple[list[dict[str, Any]], dict[str, list[ReviewRequest]], set[str]]:
    """Fetch reviews for the Reviews page and preserve typed cache data."""
    results: list[dict[str, Any]] = []
    reviews_by_project: dict[str, list[ReviewRequest]] = {}
    successful_project_ids: set[str] = set()

    for project in projects:
        project_id = str(project.id)
        provider = detect_provider(
            project.repo_url, access_token=getattr(project, "access_token", None),
        )
        if not provider:
            logger.debug("No SCM provider detected for %s", project.repo_url)
            reviews_by_project[project_id] = []
            successful_project_ids.add(project_id)
            continue

        slug = extract_repo_slug(project.repo_url)
        try:
            reviews = provider.list_open_reviews(slug)
        except Exception as exc:
            logger.warning("Failed to fetch reviews for %s: %s", project.name, exc)
            continue

        reviews_by_project[project_id] = reviews
        successful_project_ids.add(project_id)

        project_yolo = bool(getattr(project, "yolo", False))
        for review in reviews:
            results.append({
                "project_id": project.id,
                "project_name": project.name,
                "project_yolo": project_yolo,
                "provider": provider.provider_name(),
                "review": review.to_dict(),
            })

    return results, reviews_by_project, successful_project_ids


def _sync_orchestrator_review_cache(
    orch: "Orchestrator",
    reviews_by_project: dict[str, list[ReviewRequest]],
    successful_project_ids: set[str],
) -> None:
    """Keep dashboard review summary aligned with /api/v1/reviews.

    The dashboard badge reads ``orch._reviews_cache`` while the Reviews page
    fetches this endpoint directly. When the endpoint has fresher forge data,
    sync successfully fetched project entries so the badge and board agree
    without clearing dispatch gates for projects whose fetch failed.
    """
    old_summary = None
    if callable(getattr(orch, "_reviews_summary", None)):
        try:
            old_summary = orch._reviews_summary()
        except Exception:
            old_summary = None

    cache: dict[str, list[ReviewRequest]] = {
        str(project_id): list(reviews)
        for project_id, reviews in (getattr(orch, "_reviews_cache", {}) or {}).items()
    }
    for project_id in successful_project_ids:
        cache[project_id] = list(reviews_by_project.get(project_id, []))

    orch._reviews_cache = cache
    orch._unmerged_review_branches = {
        r.source_branch
        for reviews in cache.values()
        for r in reviews
        if r.source_branch
    }

    if not callable(getattr(orch, "_reviews_summary", None)):
        return

    try:
        new_summary = orch._reviews_summary()
    except Exception:
        return
    if new_summary == old_summary:
        return

    try:
        orch._last_emitted_reviews_summary = dict(new_summary)
    except Exception:
        pass
    notify = getattr(orch, "_notify_state_only", None)
    if callable(notify):
        notify()


def _on_state_only_change(snapshot: dict) -> None:
    """Called on agent activity — broadcast state only, no issues re-fetch."""
    import time

    global _last_state_broadcast
    # Always cache the snapshot so api_state() can serve it without recomputing.
    _update_state_snapshot(snapshot)
    if not _ws_clients:
        return
    now = time.monotonic() * 1000
    if now - _last_state_broadcast < _STATE_THROTTLE_MS:
        return
    _last_state_broadcast = now
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_broadcast({"type": "state", "data": snapshot}))
    except RuntimeError:
        pass


def _on_orchestrator_change(snapshot: dict) -> None:
    """Called on state changes (dispatch, close, etc.). Broadcasts state + issues."""
    import time

    global _last_state_broadcast
    # Always cache the snapshot so api_state() can serve it without recomputing.
    _update_state_snapshot(snapshot)
    _api_cache.invalidate("issues:all")
    if not _ws_clients:
        return
    now = time.monotonic() * 1000
    if now - _last_state_broadcast < _STATE_THROTTLE_MS:
        return
    _last_state_broadcast = now
    # Schedule broadcast in the running event loop
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_broadcast({"type": "state", "data": snapshot}))
            loop.create_task(_throttled_broadcast_issues())
    except RuntimeError:
        pass


def _on_agent_activity(identifier: str, entry) -> None:
    """Called by orchestrator on each agent activity entry. Push to WS clients."""
    if not _ws_clients:
        return
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(
                _broadcast(
                    {
                        "type": "activity",
                        "identifier": identifier,
                        "entry": entry.to_dict()
                        if hasattr(entry, "to_dict")
                        else str(entry),
                    }
                )
            )
    except RuntimeError:
        pass


def _fetch_and_serialize_issues(orch) -> dict[str, list]:
    """Fetch all issues and serialize — runs in thread pool to avoid blocking.

    Mirrors the entry shape produced by ``api_issues`` (the GET endpoint)
    so the WebSocket push path and the initial-load fetch path produce
    interchangeable payloads. If you add a field to one, add it here too.
    """
    all_issues = _fetch_all_issues(orch, None)
    project_names = _project_names_by_id(orch)

    # Build a map for parent child counts — any issue that has children gets counts
    # First pass: find all parent_ids referenced by children
    parent_ids: set[str] = set()
    for issue in all_issues:
        if issue.parent_id:
            parent_ids.add(issue.parent_id)
    # Also include explicit epics even if they have no children yet
    parents: dict[str, dict] = {}
    for issue in all_issues:
        if issue.id in parent_ids or issue.issue_type == "epic":
            parents[issue.id] = _empty_state_counts()
    for issue in all_issues:
        if issue.parent_id and issue.parent_id in parents:
            child_state = _issue_dashboard_state(issue)
            if child_state in parents[issue.parent_id]:
                parents[issue.parent_id][child_state] += 1

    # Snapshot of source-branches with currently-open (unmerged) PRs so
    # we can flag in-flight tasks. Mirrors api_issues; both paths read
    # from the orchestrator's _unmerged_review_branches cache populated
    # in _handle_review_check.
    unmerged_branches: set[str] = set(
        getattr(orch, "_unmerged_review_branches", set()) or set()
    )

    result: dict[str, list] = {}
    for issue in all_issues:
        state = _issue_dashboard_state(issue)
        if state not in result:
            result[state] = []
        branch = issue.branch_name or issue.identifier
        has_open_review = branch in unmerged_branches if branch else False
        tracker_state = issue.state
        entry = {
            "id": issue.id,
            "identifier": issue.identifier,
            "title": issue.title,
            "description": issue.description,
            "priority": issue.priority,
            "state": state,
            "tracker_state": tracker_state,
            "labels": issue.labels,
            "issue_type": issue.issue_type,
            "parent_id": issue.parent_id,
            "project_id": issue.project_id,
            "branch_name": issue.branch_name,
            "has_open_review": has_open_review,
            "attachments": list(getattr(issue, "attachments", []) or []),
            # Tracker identity fields — populated for GitHub-backed issues;
            # None/False for legacy Backlog-backed issues (backward compat).
            "tracker_kind": getattr(issue, "tracker_kind", None),
            "tracker_owner": getattr(issue, "tracker_owner", None),
            "tracker_repo": getattr(issue, "tracker_repo", None),
            "issue_number": getattr(issue, "issue_number", None),
            "url": getattr(issue, "url", None) or getattr(issue, "provider_url", None),
            "managed_repo": getattr(issue, "managed_repo", None),
            "target_branch": getattr(issue, "target_branch", None),
            "work_branch": getattr(issue, "work_branch", None),
            "is_legacy": bool(getattr(issue, "is_legacy", False)),
            **_issue_display_fields(issue, project_names),
        }
        if issue.id in parents:
            entry["children_counts"] = parents[issue.id]
        result[state].append(entry)
    for state in result:
        result[state].sort(
            key=lambda i: i["priority"] if i["priority"] is not None else 999
        )
    return result


async def _do_broadcast_issues() -> None:
    """Broadcast the current board snapshot and refresh it in the background."""
    global _last_issues_broadcast, _issues_broadcast_pending
    _issues_broadcast_pending = False
    try:
        orch = _get_orchestrator()
        _last_issues_broadcast = time.monotonic() * 1000
        payload = _issues_snapshot_payload(allow_empty=False, orch=orch)
        if payload is not None and _ws_clients:
            await _broadcast({"type": "issues", "data": payload})
        await _ensure_issues_snapshot_refresh(orch, force=True, broadcast=True)
    except Exception as exc:
        logger.debug("broadcast_issues failed: %s", exc)


async def broadcast_issues() -> None:
    """Immediately fetch and broadcast issues (used for UI-driven actions)."""
    await _do_broadcast_issues()


async def _throttled_broadcast_issues() -> None:
    """Throttled issue broadcast — debounces rapid background orchestrator calls."""
    global _issues_broadcast_pending
    if not _ws_clients:
        return
    now = time.monotonic() * 1000
    elapsed = now - _last_issues_broadcast
    if elapsed >= _ISSUES_THROTTLE_MS:
        await _do_broadcast_issues()
    elif not _issues_broadcast_pending:
        _issues_broadcast_pending = True
        delay = (_ISSUES_THROTTLE_MS - elapsed) / 1000
        asyncio.get_event_loop().call_later(
            delay, lambda: asyncio.ensure_future(_do_broadcast_issues())
        )


async def _broadcast(msg: dict) -> None:
    """Send a JSON message to all connected WebSocket clients."""
    if not _ws_clients:
        return
    text = json.dumps(msg, default=str)
    try:
        clients = list(_ws_clients)
    except RuntimeError:
        return  # set changed during snapshot, skip this broadcast
    dead: list[WebSocket] = []
    for ws in clients:
        try:
            await ws.send_text(text)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _ws_clients.discard(ws)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """WebSocket endpoint for real-time UI updates."""
    await ws.accept()
    _ws_clients.add(ws)
    logger.info("WebSocket client connected (%d total)", len(_ws_clients))
    try:
        # Send initial state + issues immediately
        orch = _get_orchestrator()
        await ws.send_text(
            json.dumps({"type": "state", "data": orch.get_snapshot()}, default=str)
        )
        payload = _issues_snapshot_payload(allow_empty=True, orch=orch)
        await ws.send_text(
            json.dumps({"type": "issues", "data": payload}, default=str)
        )
        await _ensure_issues_snapshot_refresh(orch, broadcast=True)

        # Keep connection alive, handle client messages
        while True:
            data = await ws.receive_text()
            # Client can send "ping" to keep alive or "refresh" to request data
            try:
                msg = json.loads(data)
                if msg.get("action") == "refresh":
                    await ws.send_text(
                        json.dumps(
                            {"type": "state", "data": orch.get_snapshot()}, default=str
                        )
                    )
                    await broadcast_issues()
                elif msg.get("type") == "console_input":
                    # Per-project ACP console (oompah-zlz_2-ebwe).
                    # Operator typed something in the dashboard's console
                    # panel; route it to the project's ConsoleSession,
                    # which serializes inputs server-side.
                    await _handle_console_input(ws, msg)
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        _ws_clients.discard(ws)
        logger.info("WebSocket client disconnected (%d remaining)", len(_ws_clients))


# ----------------------------------------------------------------------
# Per-project ACP console (oompah-zlz_2-ebwe)
# ----------------------------------------------------------------------


async def _handle_console_input(ws: WebSocket, msg: dict) -> None:
    """Handle a {type:"console_input", project_id, text, attachments?} WS msg.

    Routes the operator input into the project's ConsoleSession via
    ``ConsoleSessionManager.get(project_id).send(text, attachments)``.
    The session's on_event callback (wired at construction in
    :func:`set_orchestrator`) broadcasts every persisted event to all
    WS clients as ``{type:"console_event", project_id, event}``; the
    client filters by project_id.

    Unknown / not-yet-registered projects return an inline error
    ``console_event`` so the originating tab surfaces the failure.
    Validation errors (missing project_id / empty text) silently no-op
    — the UI shouldn't be sending these but if it does, dropping is
    safer than crashing.
    """
    project_id = str(msg.get("project_id") or "")
    text = str(msg.get("text") or "")
    if not project_id or not text.strip():
        return
    if _console_manager is None:
        await ws.send_text(
            json.dumps(
                {
                    "type": "console_event",
                    "project_id": project_id,
                    "event": {
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "kind": "error",
                        "is_error": True,
                        "text": "console manager not initialized",
                    },
                }
            )
        )
        return
    # Reject unknown project_id before touching the manager so we
    # don't spawn an orphan session.
    try:
        orch = _get_orchestrator()
        project = orch.project_store.get(project_id)
    except Exception:
        project = None
    if project is None:
        await ws.send_text(
            json.dumps(
                {
                    "type": "console_event",
                    "project_id": project_id,
                    "event": {
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "kind": "error",
                        "is_error": True,
                        "text": f"unknown project_id {project_id!r}",
                    },
                }
            )
        )
        return
    attachments_raw = msg.get("attachments") or []
    attachments = [str(a) for a in attachments_raw if a]
    try:
        session = _console_manager.get(project_id)
    except Exception as exc:
        await ws.send_text(
            json.dumps(
                {
                    "type": "console_event",
                    "project_id": project_id,
                    "event": {
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "kind": "error",
                        "is_error": True,
                        "text": str(exc),
                    },
                }
            )
        )
        return
    # session.send() awaits the turn to completion. The serial queue
    # inside the session guarantees concurrent operator inputs from
    # multiple WS clients run one at a time.
    try:
        await session.send(text, attachments=attachments or None)
    except Exception as exc:
        # The session already records an internal ``error`` event on
        # most failure paths; only emit an out-of-band one here when
        # send itself raised (closed session, etc.).
        await ws.send_text(
            json.dumps(
                {
                    "type": "console_event",
                    "project_id": project_id,
                    "event": {
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "kind": "error",
                        "is_error": True,
                        "text": f"console send failed: {exc}",
                    },
                }
            )
        )


# Hard cap on transcript pagination to keep responses bounded.
_CONSOLE_TRANSCRIPT_MAX_LIMIT = 1000
_CONSOLE_TRANSCRIPT_DEFAULT_LIMIT = 200


def _coerce_transcript_limit(raw: int | str | None) -> int:
    """Validate + cap the ?limit query param."""
    if raw is None:
        return _CONSOLE_TRANSCRIPT_DEFAULT_LIMIT
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return _CONSOLE_TRANSCRIPT_DEFAULT_LIMIT
    if value < 0:
        return _CONSOLE_TRANSCRIPT_DEFAULT_LIMIT
    return max(1, min(_CONSOLE_TRANSCRIPT_MAX_LIMIT, value))


@app.get("/api/v1/console/{project_id}/transcript")
async def api_console_transcript(
    project_id: str,
    since: str | None = None,
    limit: int | None = None,
):
    """Return the project's console transcript.

    Query params:

    * ``since`` — when set, return only events with ``ts > since``
      (ISO-8601 string compare; matches the format the store uses).
    * ``limit`` — max events to return (default 200, capped at 1000).

    Response shape:

        {"events": [...], "meta": {...}}

    ``meta`` is the contents of the on-disk meta sidecar (typically
    ``{"backend": "...", "model_role": "...", "switched_at": "..."}``)
    so the UI can render the current backend without a second round-
    trip. Missing / empty meta returns ``{}``.

    Unknown project_id returns 404.
    """
    if _console_manager is None:
        return JSONResponse(
            {
                "error": {
                    "code": "not_ready",
                    "message": "console manager not initialized",
                }
            },
            status_code=503,
        )
    orch = _get_orchestrator()
    try:
        project = orch.project_store.get(project_id)
    except Exception:
        project = None
    if project is None:
        return JSONResponse(
            {
                "error": {
                    "code": "no_project",
                    "message": f"Unknown project_id {project_id!r}",
                }
            },
            status_code=404,
        )
    capped_limit = _coerce_transcript_limit(limit)
    since_ts: str | None = None
    if since is not None:
        # Defensive: empty string == treat as None. Non-strings can't
        # arrive here through FastAPI, but coerce anyway.
        ss = str(since).strip()
        if ss:
            since_ts = ss
    store = _console_manager.store
    try:
        events = store.read_all(project_id, since_ts=since_ts, limit=capped_limit)
    except Exception as exc:
        logger.warning("Console transcript read failed for %s: %s", project_id, exc)
        events = []
    try:
        meta = store.load_meta(project_id)
    except Exception:
        meta = {}
    return JSONResponse(
        {
            "project_id": project_id,
            "events": events,
            "meta": meta,
            "limit": capped_limit,
            "since": since_ts,
        }
    )


@app.post("/api/v1/console/{project_id}/backend")
async def api_console_backend(project_id: str, request: Request):
    """Swap the console's active backend / model role for ``project_id``.

    Body (JSON): ``{"backend": "claude" | "codex", "model_role": "default"}``.

    Returns:

    * ``200`` ``{"backend": "..."}`` on success.
    * ``400`` on missing / unknown backend.
    * ``404`` on unknown project_id.
    * ``409`` ``{"error": "turn in flight"}`` if a turn is currently
      running on the session.
    * ``503`` if the console manager hasn't been wired yet.

    The new backend is persisted to the meta sidecar so service
    restarts pick it up.
    """
    if _console_manager is None:
        return JSONResponse(
            {
                "error": {
                    "code": "not_ready",
                    "message": "console manager not initialized",
                }
            },
            status_code=503,
        )
    orch = _get_orchestrator()
    try:
        project = orch.project_store.get(project_id)
    except Exception:
        project = None
    if project is None:
        return JSONResponse(
            {
                "error": {
                    "code": "no_project",
                    "message": f"Unknown project_id {project_id!r}",
                }
            },
            status_code=404,
        )
    try:
        body = await request.json()
    except Exception:
        body = None
    if not isinstance(body, dict):
        return JSONResponse(
            {
                "error": {
                    "code": "bad_request",
                    "message": "request body must be a JSON object",
                }
            },
            status_code=400,
        )
    backend = body.get("backend")
    if not isinstance(backend, str) or not backend.strip():
        return JSONResponse(
            {
                "error": {
                    "code": "bad_request",
                    "message": "missing 'backend' string field",
                }
            },
            status_code=400,
        )
    backend = backend.strip()
    model_role_raw = body.get("model_role", "default")
    model_role = (
        model_role_raw.strip()
        if isinstance(model_role_raw, str) and model_role_raw.strip()
        else "default"
    )
    try:
        session = _console_manager.get(project_id)
    except Exception as exc:
        return JSONResponse(
            {"error": {"code": "session_error", "message": str(exc)}},
            status_code=500,
        )
    try:
        await session.switch_backend(backend, model_role=model_role)
    except ValueError as exc:
        # Unknown backend → translator missing.
        return JSONResponse(
            {"error": {"code": "unknown_backend", "message": str(exc)}},
            status_code=400,
        )
    except RuntimeError as exc:
        # Turn in flight (per ConsoleSession.switch_backend contract).
        return JSONResponse(
            {"error": {"code": "turn_in_flight", "message": "turn in flight"}},
            status_code=409,
        )
    meta = session.get_meta()
    return JSONResponse(
        {
            "backend": meta.get("backend"),
            "model_role": meta.get("model_role"),
        }
    )


@app.delete("/api/v1/console/{project_id}")
async def api_console_delete(project_id: str):
    """Clear the project's console session — in-memory + on-disk.

    Idempotent: missing projects return 404, but missing sessions /
    missing transcript files are silently OK and return 200.

    Hard-resets even when a turn is "in flight" — the runner task is
    shut down, then the disk transcript is removed. The next operator
    input reconstructs a fresh session.
    """
    if _console_manager is None:
        return JSONResponse(
            {
                "error": {
                    "code": "not_ready",
                    "message": "console manager not initialized",
                }
            },
            status_code=503,
        )
    orch = _get_orchestrator()
    try:
        project = orch.project_store.get(project_id)
    except Exception:
        project = None
    if project is None:
        return JSONResponse(
            {
                "error": {
                    "code": "no_project",
                    "message": f"Unknown project_id {project_id!r}",
                }
            },
            status_code=404,
        )
    # Drop the in-memory session first (forces shutdown of its runner
    # task so a mid-turn delete still completes). Errors are absorbed
    # — manager.remove is already best-effort.
    try:
        await _console_manager.remove(project_id)
    except Exception as exc:
        logger.warning(
            "Console DELETE: manager.remove raised for %s: %s", project_id, exc
        )
    # Then clear on-disk transcript + meta. ConsoleStore.clear is
    # idempotent (missing files are ignored).
    try:
        _console_manager.store.clear(project_id)
    except Exception as exc:
        logger.warning("Console DELETE: store.clear raised for %s: %s", project_id, exc)
    return JSONResponse({"ok": True})


# --- JSON REST API ---


@app.get("/api/v1/state")
async def api_state():
    """Return current system state snapshot.

    Read paths (fastest-first):

    1. **API-only mode** (``_orchestrator is None``, IPC set): reads the
       pre-computed snapshot from the SQLite IPC cache written by the
       scheduler process.  Never touches the tracker, YAML parsing, or
       GIL-heavy scheduler code.

    2. **Combined mode — cached snapshot**: returns the snapshot that was
       stored by the last orchestrator observer callback
       (``_on_orchestrator_change`` / ``_on_state_only_change``).  This
       avoids rebuilding state during a tick / maintenance burst.

    3. **Combined mode — live fallback**: calls ``orch.get_snapshot()``
       directly when no cached snapshot is available yet (e.g. on first
       request before the first tick completes).
    """
    t_start = time.monotonic()
    try:
        # API-only mode: read state from the IPC SQLite cache.
        if _orchestrator is None and _ipc is not None:
            snapshot, _ = _ipc.read_state()
            if snapshot is None:
                return JSONResponse(
                    {"error": {"code": "unavailable", "message": "State snapshot not yet available from scheduler"}},
                    status_code=503,
                )
            duration_ms = (time.monotonic() - t_start) * 1000
            _record_api_latency("/api/v1/state", duration_ms)
            snapshot["api_metrics"] = _api_metrics_snapshot()
            return JSONResponse(snapshot)

        # Combined mode: prefer the cached snapshot to avoid recomputing
        # during maintenance / tick bursts.
        orch = _get_orchestrator()
        snapshot = _read_state_snapshot()
        if snapshot is None:
            # No cached snapshot yet — fall back to live computation.
            snapshot = orch.get_snapshot()
        duration_ms = (time.monotonic() - t_start) * 1000
        _record_api_latency("/api/v1/state", duration_ms)
        snapshot["api_metrics"] = _api_metrics_snapshot()
        return JSONResponse(snapshot)
    except Exception as exc:
        _record_api_latency(
            "/api/v1/state", (time.monotonic() - t_start) * 1000, ok=False
        )
        logger.error("State API error: %s", exc)
        return JSONResponse(
            {"error": {"code": "unavailable", "message": str(exc)}},
            status_code=503,
        )


@app.get("/api/v1/issues")
async def api_issues(request: Request):
    """Return all issues grouped by state for the kanban board.

    Query params:
        project_id - filter to a single project (optional)
    """
    t_start = time.monotonic()
    try:
        orch = _get_orchestrator()
        filter_project = request.query_params.get("project_id")
        await _ensure_issues_snapshot_refresh(orch, broadcast=bool(_ws_clients))
        payload = _issues_snapshot_payload(
            filter_project=filter_project, allow_empty=False, orch=orch
        )
        if payload is None:
            await _wait_for_issues_snapshot_refresh()
            payload = _issues_snapshot_payload(
                filter_project=filter_project, allow_empty=False, orch=orch
            )
        if payload is None:
            payload = _issues_snapshot_payload(
                filter_project=filter_project, allow_empty=True, orch=orch
            )
        duration_ms = (time.monotonic() - t_start) * 1000
        _record_api_latency("/api/v1/issues", duration_ms)
        return JSONResponse(payload, headers=_issues_snapshot_headers(orch))
    except Exception as exc:
        _record_api_latency(
            "/api/v1/issues", (time.monotonic() - t_start) * 1000, ok=False
        )
        logger.error("Issues API error: %s", exc)
        return JSONResponse(
            {"error": {"code": "unavailable", "message": str(exc)}},
            status_code=503,
        )


def _get_tracker(orch, project_id: str | None = None):
    """Get the appropriate tracker for a project_id."""
    if not project_id:
        raise ValueError("project_id is required")
    return orch._tracker_for_project(project_id)


def _find_tracker_for_issue(orch, identifier: str, project_id: str | None = None):
    """Get a tracker for an issue, searching all projects if project_id is missing.

    Returns (tracker, project_id, issue) tuple. If the issue cannot be found in
    any project, returns (None, None, None).

    Used by read-only endpoints (issue detail, comments, attachments) where the
    UI may not know which project an issue belongs to. Mutating endpoints
    should still require project_id explicitly via _get_tracker().
    """
    # Fast path: explicit project_id wins
    if project_id:
        try:
            tracker = orch._tracker_for_project(project_id)
        except Exception:
            return None, None, None
        try:
            issue = tracker.fetch_issue_detail(identifier)
        except Exception:
            issue = None
        return tracker, project_id, issue

    # Slow path: search all known projects for the issue
    projects = orch.project_store.list_all()
    if not projects:
        # Legacy mode — single tracker
        try:
            issue = orch.tracker.fetch_issue_detail(identifier)
        except Exception:
            issue = None
        return orch.tracker, None, issue

    for project in projects:
        try:
            tracker = orch._tracker_for_project(project.id)
            issue = tracker.fetch_issue_detail(identifier)
        except Exception:
            continue
        if issue is not None:
            return tracker, project.id, issue

    return None, None, None


def _resolve_identifier(
    identifier: str,
    body: dict | None = None,
    query_params=None,
) -> str:
    """Resolve the canonical issue identifier for a request.

    For GitHub-backed issues whose identifiers contain slashes (e.g.
    ``owner/repo#123``), HTTP servers normalise ``%2F`` to ``/`` before
    routing, so the raw identifier cannot be embedded in a path segment.
    Callers can pass the identifier in the request body (``issue_key``) or
    as a ``?issue_key=`` query parameter instead.  This function prefers
    those over the path-captured value.

    Falls back to URL-decoding the path parameter so that any
    percent-encoded but slash-free characters (e.g. ``%23`` for ``#``) are
    handled correctly.
    """
    if body:
        key = body.get("issue_key")
        if key and str(key).strip():
            return str(key).strip()
    if query_params:
        key = query_params.get("issue_key")
        if key and str(key).strip():
            return str(key).strip()
    return urllib.parse.unquote(identifier)


def _managed_repo_slug(repo_url: str) -> str | None:
    """Extract ``owner/repo`` from a GitHub/GitLab remote URL.

    Handles both https (``https://github.com/owner/repo``) and ssh
    (``git@github.com:owner/repo``) URL forms.  Returns ``None`` when the
    URL cannot be parsed.
    """
    url = (repo_url or "").strip().rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    # https://host/owner/repo or http://host/owner/subgroup/repo
    m = re.match(r"https?://[^/]+/(.+)", url)
    if m:
        parts = m.group(1).split("/")
        if len(parts) >= 2:
            return "/".join(parts[:2])
    # git@host:owner/repo or git@host:owner/subgroup/repo
    m = re.match(r"[^@]+@[^:]+:(.+)", url)
    if m:
        parts = m.group(1).split("/")
        if len(parts) >= 2:
            return "/".join(parts[:2])
    return None


def _get_tracker_for_managed_repo(orch, managed_repo: str):
    """Find the tracker and project_id for a given managed-repo slug.

    Args:
        orch: Orchestrator instance.
        managed_repo: ``owner/repo`` of the managed code repository as
            registered in the project store (matched against the project's
            ``repo_url``).

    Returns:
        ``(tracker, project_id)`` tuple.

    Raises:
        ValueError: No project matched the given ``managed_repo``.
    """
    projects = orch.project_store.list_all()
    for project in projects:
        slug = _managed_repo_slug(getattr(project, "repo_url", "") or "")
        if slug and slug.lower() == managed_repo.lower():
            return orch._tracker_for_project(project.id), project.id
    raise ValueError(f"No project found for managed_repo: {managed_repo!r}")


def _fetch_all_issues(orch, filter_project: str | None = None):
    """Fetch issues from all projects or a specific one (parallel)."""
    from concurrent.futures import ThreadPoolExecutor
    from oompah.tracker import TrackerError

    projects = orch.project_store.list_all()
    if not projects:
        # No projects configured — legacy mode
        return orch.tracker.fetch_all_issues()

    targets = [p for p in projects if not filter_project or p.id == filter_project]
    if not targets:
        return []

    def _fetch_for_project(project):
        try:
            tracker = orch._tracker_for_project(project.id)
            issues = tracker.fetch_all_issues()
            for issue in issues:
                issue.project_id = project.id
                # Display-only: reflect the epic-branch status for shared-
                # epic children (their default-branch copy lags until the
                # epic lands), so the board shows Done/Merged in the right
                # column instead of a stale Open/In-Progress. See
                # _effective_display_status.
                issue.state = _effective_display_status(orch, issue)
            # Roll each epic up to a state derived from its children's
            # (now-enriched) states, so the board shows the epic in the
            # column that matches its children — Done (ready to merge) when
            # all children are done, In Progress while any are active, etc.
            # See epic_rollup_state. Same-project list, so ids are unique.
            child_states: dict[str, list[str]] = {}
            for issue in issues:
                if issue.parent_id:
                    child_states.setdefault(issue.parent_id, []).append(issue.state)
            for issue in issues:
                if (issue.issue_type or "").strip().lower() == "epic":
                    rolled = epic_rollup_state(child_states.get(issue.id, []))
                    if rolled:
                        issue.state = rolled
            return issues
        except (TrackerError, ProjectError) as exc:
            logger.error("Fetch issues failed for project %s: %s", project.name, exc)
            return []

    all_issues = []
    with ThreadPoolExecutor(max_workers=min(len(targets), 4)) as pool:
        for issues in pool.map(_fetch_for_project, targets):
            all_issues.extend(issues)
    return all_issues


def _verify_epic_state_after_update(
    tracker,
    identifier: str,
    expected_status: str,
) -> bool:
    """Verify that an Epic issue's state is at the expected value after update.

    Used by :func:`api_update_issue` to detect when the tracker backend
    post-update epic-state hook has reverted a manual state transition.
    Returns ``True`` when the issue's state matches expected_status,
    ``False`` when the backend has already reverted it.

    This is a synchronous function (runs in the API worker thread pool from
    the async API handler).
    """
    try:
        issue = tracker.fetch_issue_detail(identifier)
        if issue is None:
            return True  # can no longer verify — treat as settled
        actual = (issue.state or "").strip().lower()
        expected = expected_status.strip().lower()
        return actual == expected
    except Exception:  # noqa: BLE001 — verification failures are best-effort
        return True


@app.post("/api/v1/issues")
async def api_create_issue(request: Request):
    """Create a new issue.

    Supports an optional ``?enhance=`` query parameter to run a one-shot
    LLM enhancement of the operator's title/description against the
    target project's AGENTS.md (with a fallback to WORKFLOW.md's
    ``Issue Quality`` block). See oompah-zlz_2-u8pz for the design.

    Values for ``enhance``:

    * ``true`` — Return ``{original, enhanced, missing_fields,
      suggested_changes, diff}`` with ``ok=true`` and HTTP 200; nothing
      is written.
    * ``apply`` — Run the enhancement, then write the enhanced version
      via :meth:`tracker.create_issue`. Falls back to the original
      input on enhancement error so the operator's intent is never
      lost.
    * absent / anything else — Verbatim write (back-compat default).
    """
    try:
        orch = _get_orchestrator()
        try:
            body = await request.json()
        except (json.JSONDecodeError, ValueError) as exc:
            return JSONResponse(
                {
                    "error": {
                        "code": "validation",
                        "message": f"Invalid JSON: {exc}",
                    }
                },
                status_code=400,
            )
        if not isinstance(body, dict):
            return JSONResponse(
                {
                    "error": {
                        "code": "validation",
                        "message": "request body must be a JSON object",
                    }
                },
                status_code=400,
            )

        title = body.get("title", "").strip()
        if not title:
            return JSONResponse(
                {"error": {"code": "validation", "message": "Title is required"}},
                status_code=400,
            )

        project_id = body.get("project_id")
        # Optional tracker-identity / branch metadata.  Extract early so
        # managed_repo can be used as an alternative to project_id for tracker
        # resolution when project_id is absent.
        managed_repo = (body.get("managed_repo") or "").strip() or None
        target_branch = (body.get("target_branch") or "").strip() or None
        work_branch = (body.get("work_branch") or "").strip() or None

        # Basic format validation: managed_repo must be "owner/repo" when given.
        if managed_repo and "/" not in managed_repo:
            return JSONResponse(
                {
                    "error": {
                        "code": "validation",
                        "message": "managed_repo must be in 'owner/repo' format",
                    }
                },
                status_code=400,
            )

        # Resolve tracker: project_id wins; fall back to managed_repo lookup;
        # error if neither is given (GitHub-backed tasks require an explicit
        # project target so the adapter knows where to create the issue).
        if project_id:
            tracker = _get_tracker(orch, project_id)
        elif managed_repo:
            try:
                tracker, project_id = _get_tracker_for_managed_repo(
                    orch, managed_repo
                )
            except ValueError as exc:
                return JSONResponse(
                    {
                        "error": {
                            "code": "not_found",
                            "message": str(exc),
                        }
                    },
                    status_code=404,
                )
        else:
            return JSONResponse(
                {
                    "error": {
                        "code": "validation",
                        "message": "project_id or managed_repo is required",
                    }
                },
                status_code=400,
            )

        # Optional enhancement pass (oompah-zlz_2-u8pz).
        enhance_mode = (request.query_params.get("enhance") or "").strip().lower()
        description = body.get("description")
        if enhance_mode in ("true", "apply"):
            try:
                enhancement = await asyncio.to_thread(
                    lambda: _run_issue_enhancement(
                        orch=orch,
                        project_id=project_id,
                        title=title,
                        description=description,
                    )
                )
            except IssueEnhancerError as exc:
                # Preview-mode failures surface to the dashboard so the
                # operator can fall back to a verbatim save. Apply-mode
                # failures fall through to verbatim creation so the
                # operator's input is never lost on transient LLM
                # outages.
                if enhance_mode == "true":
                    return JSONResponse(
                        {"error": {"code": "enhance_failed", "message": str(exc)}},
                        status_code=502,
                    )
                logger.warning(
                    "issue_enhancer: apply-mode failed for project=%s, "
                    "writing verbatim: %s",
                    project_id,
                    exc,
                )
                enhancement = None
            if enhance_mode == "true":
                # Preview-only — do not write anything.
                return JSONResponse(
                    {
                        "ok": True,
                        "mode": "enhance_preview",
                        **enhancement.to_dict(),
                    },
                    status_code=200,
                )
            # Apply mode: swap in the enhanced fields before write.
            if enhancement is not None:
                title = enhancement.enhanced_title or title
                description = enhancement.enhanced_description

        issue_type = body.get("type", "task")
        parent_id = body.get("parent_id") or None
        # Optional focus/routing labels for GitHub-backed projects (e.g.
        # "needs:frontend", "area:api").  Accepted as a JSON list of strings or
        # as a single comma-separated string for convenience.
        raw_labels = body.get("labels")
        if isinstance(raw_labels, list):
            initial_labels: list[str] | None = [
                l.strip() for l in raw_labels if isinstance(l, str) and l.strip()
            ] or None
        elif isinstance(raw_labels, str) and raw_labels.strip():
            initial_labels = [
                l.strip() for l in raw_labels.split(",") if l.strip()
            ] or None
        else:
            initial_labels = None

        # Preserve source-task identity across tracker backends (TASK-460.3 AC#2).
        # When source_task_id is provided (e.g. via `oompah task create --source`),
        # prepend a "Triggered by: <id>" header to the description so the follow-up
        # is traceable back to its origin in every tracker backend.
        source_task_id = (body.get("source_task_id") or "").strip() or None
        if source_task_id:
            source_header = f"Triggered by: {source_task_id}"
            if description:
                description = f"{source_header}\n\n{description}"
            else:
                description = source_header

        issue = tracker.create_issue(
            title=title,
            issue_type=issue_type,
            description=description,
            priority=body.get("priority"),
            initial_status=body.get("status"),
            labels=initial_labels,
            parent=parent_id,
        )
        issue.project_id = project_id
        # Persist tracker-identity fields onto the returned issue so the
        # response carries the full schema even when the tracker adapter
        # doesn't set them during creation.
        if managed_repo:
            issue.managed_repo = managed_repo
        if target_branch:
            issue.target_branch = target_branch
        if work_branch:
            issue.work_branch = work_branch

        # Auto-add 'draft' label to new epics so they appear in the kanban
        if issue_type == "epic":
            tracker.add_label(issue.identifier, "draft")

        _api_cache.invalidate("issues:all")
        await broadcast_issues()
        return JSONResponse(
            {
                "ok": True,
                "issue": {
                    "id": issue.id,
                    "identifier": issue.identifier,
                    "title": issue.title,
                    "state": issue.state,
                    "tracker_kind": getattr(issue, "tracker_kind", None),
                    "tracker_owner": getattr(issue, "tracker_owner", None),
                    "tracker_repo": getattr(issue, "tracker_repo", None),
                    "issue_number": getattr(issue, "issue_number", None),
                    "url": (
                        getattr(issue, "url", None)
                        or getattr(issue, "provider_url", None)
                    ),
                    "managed_repo": getattr(issue, "managed_repo", None),
                    "target_branch": getattr(issue, "target_branch", None),
                    "work_branch": getattr(issue, "work_branch", None),
                    "is_legacy": bool(getattr(issue, "is_legacy", False)),
                },
            },
            status_code=201,
        )
    except Exception as exc:
        logger.error("Create issue API error: %s", exc)
        return JSONResponse(
            {"error": {"code": "create_failed", "message": str(exc)}},
            status_code=500,
        )


def _run_issue_enhancement(
    *,
    orch,
    project_id: str | None,
    title: str,
    description: str | None,
) -> EnhancementResult:
    """Resolve the project workspace + 'default' role and run the enhancer.

    Pulled out of :func:`api_create_issue` so tests can patch the
    resolution path independently of the FastAPI request lifecycle.

    Raises :class:`IssueEnhancerError` on any failure that should
    surface to the operator.
    """
    if not project_id:
        raise IssueEnhancerError("project_id is required for enhancement")
    project = orch.project_store.get(project_id)
    if project is None:
        raise IssueEnhancerError(f"project not found: {project_id}")
    repo_path = getattr(project, "repo_path", None)
    # Resolve the LLM provider+model via RoleStore('default'), then
    # fall back to provider_store.get_default() so single-provider
    # installations work out of the box. The model resolution mirrors
    # completion_verifier.run_stage2_sync.
    provider, model = orch._resolve_role("default")
    if provider is None:
        provider = orch.provider_store.get_default()
        if provider is not None:
            model = (getattr(provider, "model_roles", None) or {}).get(
                "default"
            ) or getattr(provider, "default_model", None)
            if not model:
                models = getattr(provider, "models", None) or []
                if models:
                    model = models[0]
    return enhance_issue(
        title=title,
        description=description,
        repo_path=repo_path,
        provider=provider,
        model=model,
    )


@app.get("/api/v1/projects/{project_id}/issue-quality-source")
async def api_issue_quality_source(project_id: str):
    """Report whether the project has a quality source the enhancer can use.

    Used by the dashboard's create-issue dialog to show or hide the
    Enhance button. Returns ``{"has_source": bool, "kind": str}`` where
    ``kind`` is one of ``""``, ``"agents_md"``, or
    ``"workflow_quality"``.
    """
    try:
        orch = _get_orchestrator()
        project = orch.project_store.get(project_id)
        if project is None:
            return JSONResponse(
                {"error": {"code": "not_found", "message": "project not found"}},
                status_code=404,
            )
        repo_path = getattr(project, "repo_path", None)

        def _check_quality_source() -> tuple[bool, str]:
            """Check quality source availability. File I/O — runs in thread."""
            _has = has_quality_source(repo_path)
            _kind = ""
            if _has:
                from oompah.issue_enhancer import load_quality_source as _load_qs

                _kind, _ = _load_qs(repo_path)
            return _has, _kind

        has, kind = await asyncio.to_thread(_check_quality_source)
        return JSONResponse({"has_source": has, "kind": kind})
    except Exception as exc:
        logger.error("issue-quality-source API error: %s", exc)
        return JSONResponse(
            {"error": {"code": "lookup_failed", "message": str(exc)}},
            status_code=500,
        )


@app.patch("/api/v1/issues/{identifier}")
async def api_update_issue(identifier: str, request: Request):
    """Update an issue's state, priority, or title.

    Epic issues have special semantics around state: the tracker backend may
    re-evaluate the epic's effective state from children's states after
    a manual update and overwrite the just-written value. We detect
    this by re-reading the issue state after the write and returning a
    clear 409 rejection when a manual state on an epic is immediately
    reverted by the backend.

    This lets the operator understand that epic state is derived
    (controlled by children's states) and that manual transitions must
    either go through the child-issue flow or be done directly via the
    tracker backend when intentionally bypassing any backend hooks.
    """
    try:
        orch = _get_orchestrator()
        try:
            body = await request.json()
        except (json.JSONDecodeError, ValueError) as exc:
            return JSONResponse(
                {
                    "error": {
                        "code": "validation",
                        "message": f"Invalid JSON: {exc}",
                    }
                },
                status_code=400,
            )
        if not isinstance(body, dict):
            return JSONResponse(
                {
                    "error": {
                        "code": "validation",
                        "message": "request body must be a JSON object",
                    }
                },
                status_code=400,
            )
        project_id = body.get("project_id") or request.query_params.get("project_id")

        # Resolve canonical identifier: support issue_key for GitHub identifiers
        # with slashes that cannot survive in URL path segments.
        resolved_identifier = _resolve_identifier(identifier, body, request.query_params)

        # Resolve tracker: project_id wins; then managed_repo; then search by
        # identifier so GitHub-backed clients don't need to know the internal
        # project_id when the identifier is unambiguous.
        managed_repo_req = (body.get("managed_repo") or "").strip() or None
        if project_id:
            tracker = _get_tracker(orch, project_id)
        elif managed_repo_req:
            if "/" not in managed_repo_req:
                return JSONResponse(
                    {
                        "error": {
                            "code": "validation",
                            "message": "managed_repo must be in 'owner/repo' format",
                        }
                    },
                    status_code=400,
                )
            try:
                tracker, project_id = _get_tracker_for_managed_repo(
                    orch, managed_repo_req
                )
            except ValueError as exc:
                return JSONResponse(
                    {"error": {"code": "not_found", "message": str(exc)}},
                    status_code=404,
                )
        else:
            tracker, project_id, _ = _find_tracker_for_issue(
                orch, resolved_identifier, project_id
            )
            if tracker is None:
                return JSONResponse(
                    {
                        "error": {
                            "code": "issue_not_found",
                            "message": f"Issue {resolved_identifier!r} not found in any project",
                        }
                    },
                    status_code=404,
                )

        # Re-map identifier to the resolved value for all downstream calls.
        identifier = resolved_identifier

        new_status = body.get("status")
        new_priority = body.get("priority")
        new_title = body.get("title")
        new_description = body.get("description")
        needs_human_comment = body.get("needs_human_comment", body.get("comment"))

        # Optional tracker-identity / branch fields accepted for update.
        # These are persisted to the tracker adapter when supported; validated
        # here so clients get a clear 400 for bad values regardless of backend.
        new_managed_repo = (body.get("managed_repo") or "").strip() or None
        new_target_branch = (body.get("target_branch") or "").strip() or None
        new_work_branch = (body.get("work_branch") or "").strip() or None
        if new_managed_repo and "/" not in new_managed_repo:
            return JSONResponse(
                {
                    "error": {
                        "code": "validation",
                        "message": "managed_repo must be in 'owner/repo' format",
                    }
                },
                status_code=400,
            )

        # Determine issue type for Epic-specific state handling.
        # We need this before the update so we know whether to apply
        # post-update verification.
        existing_issue = tracker.fetch_issue_detail(identifier)
        is_epic = (
            existing_issue is not None
            and (existing_issue.issue_type or "").strip().lower() == "epic"
        )

        if new_status is not None and str(new_status).strip().lower() == "closed":
            # Legacy close alias; apply other fields first if any.
            update_fields: dict[str, str] = {}
            if new_priority is not None:
                update_fields["priority"] = str(new_priority)
            if new_title is not None:
                update_fields["title"] = new_title
            if new_description is not None:
                update_fields["description"] = new_description
            if update_fields:
                tracker.update_issue(identifier, **update_fields)
            tracker.close_issue(identifier)
        else:
            update_fields = {}
            needs_human_status: str | None = None
            if new_status is not None:
                if canonicalize_status(new_status) == NEEDS_HUMAN:
                    needs_human_status = str(new_status)
                else:
                    update_fields["status"] = new_status
            if new_priority is not None:
                update_fields["priority"] = str(new_priority)
            if new_title is not None:
                update_fields["title"] = new_title
            if new_description is not None:
                update_fields["description"] = new_description
            # Tracker-identity metadata updates passed through when given.
            if new_managed_repo is not None:
                update_fields["managed_repo"] = new_managed_repo
            if new_target_branch is not None:
                update_fields["target_branch"] = new_target_branch
            if new_work_branch is not None:
                update_fields["work_branch"] = new_work_branch
            if update_fields:
                tracker.update_issue(identifier, **update_fields)
            if needs_human_status is not None:
                _mark_tracker_needs_human(
                    tracker,
                    identifier,
                    _manual_needs_human_comment(
                        identifier,
                        existing_issue,
                        needs_human_comment,
                    ),
                )

        # --- Epic state verification (oompah-zlz_2-sytm) ---
        # For Epic issues the tracker backend may have a post-update hook that
        # reverts a manual state transition to the state computed from
        # children's states. We re-read the issue state immediately after
        # the write and, if it has already been reverted, retry up to
        # 2 more times with a small delay to let the hook settle.
        # If the state still reverts we return 409 so the operator knows
        # the backend overrode their intent rather than silently failing.
        #
        # Only applies to non-terminal transitions: the backend hook overwrites
        # the user's intended "active" state (open/in_progress) for epics
        # but does not block terminal transitions (close/archive).
        if new_status is not None and is_epic:
            terminal = {
                _state_key(s)
                for s in getattr(orch.config, "tracker_terminal_states", ["Done"])
            }
            if _state_key(new_status) not in terminal:
                for attempt in range(3):
                    await asyncio.sleep(0.3)
                    loop = asyncio.get_event_loop()
                    verified = await loop.run_in_executor(
                        _api_thread_pool,
                        _verify_epic_state_after_update,
                        tracker,
                        identifier,
                        new_status,
                    )
                    if verified:
                        break
                else:
                    # All attempts failed: the backend reverted or ignored the update.
                    _api_cache.invalidate("issues:all")
                    _api_cache.invalidate_prefix(f"detail:{project_id}:{identifier}")
                    await broadcast_issues()
                    return JSONResponse(
                        {
                            "error": {
                                "code": "epic_state_reverted",
                                "message": (
                                    f"Epic {identifier} state could not be changed "
                                    f"to {new_status!r}: the tracker backend reverted the "
                                    f"update. Epic state is derived from children's "
                                    f"states; to change the epic state, first "
                                    f"resolve or update the child issues."
                                ),
                            }
                        },
                        status_code=409,
                    )

        # Terminate agent whenever issue is moved away from in_progress
        if new_status is not None:
            terminal = {_state_key(s) for s in orch.config.tracker_terminal_states}
            status_norm = _state_key(new_status)
            if status_norm != "in_progress":
                for issue_id, entry in list(orch.state.running.items()):
                    if entry.identifier == identifier:
                        logger.info(
                            "Terminating agent for %s (moved to %s via UI)",
                            identifier,
                            new_status,
                        )
                        await orch._terminate_running(
                            issue_id, cleanup_workspace=(status_norm in terminal)
                        )
                        break

                # Also cancel any *pending retry* for this identifier so a
                # scheduled timer doesn't re-dispatch a closed task later.
                # Without this, a worker that failed pre-close leaves a
                # retry timer behind that fires after the close and
                # silently re-opens the issue (oompah-zlz_2-4jq case).
                for retry_iid, retry in list(orch.state.retry_attempts.items()):
                    if retry.identifier == identifier:
                        if retry.timer_handle and not retry.timer_handle.cancelled():
                            retry.timer_handle.cancel()
                        orch.state.retry_attempts.pop(retry_iid, None)
                        orch.state.claimed.discard(retry_iid)
                        if status_norm in terminal:
                            orch.state.completed.add(retry_iid)
                        logger.info(
                            "Cancelled pending retry for %s (moved to %s via UI)",
                            identifier,
                            new_status,
                        )

        _api_cache.invalidate("issues:all")
        _api_cache.invalidate_prefix(f"detail:{project_id}:{identifier}")
        await broadcast_issues()
        return JSONResponse({"ok": True})
    except Exception as exc:
        logger.error("Update issue API error: %s", exc)
        return JSONResponse(
            {"error": {"code": "update_failed", "message": str(exc)}},
            status_code=500,
        )


@app.post("/api/v1/issues/{identifier}/labels")
async def api_add_label(identifier: str, request: Request):
    """Add a label to an issue."""
    try:
        orch = _get_orchestrator()
        try:
            body = await request.json()
        except (json.JSONDecodeError, ValueError) as exc:
            return JSONResponse(
                {
                    "error": {
                        "code": "validation",
                        "message": f"Invalid JSON: {exc}",
                    }
                },
                status_code=400,
            )
        if not isinstance(body, dict):
            return JSONResponse(
                {
                    "error": {
                        "code": "validation",
                        "message": "request body must be a JSON object",
                    }
                },
                status_code=400,
            )
        label = body.get("label", "").strip()
        if not label:
            return JSONResponse(
                {"error": {"code": "validation", "message": "label is required"}},
                status_code=400,
            )
        # Resolve identifier: issue_key body field overrides path param to
        # support GitHub identifiers with slashes.
        resolved_identifier = _resolve_identifier(identifier, body, request.query_params)
        project_id = body.get("project_id") or request.query_params.get("project_id")
        managed_repo_req = (body.get("managed_repo") or "").strip() or None
        if project_id:
            tracker = _get_tracker(orch, project_id)
        elif managed_repo_req:
            try:
                tracker, project_id = _get_tracker_for_managed_repo(
                    orch, managed_repo_req
                )
            except ValueError as exc:
                return JSONResponse(
                    {"error": {"code": "not_found", "message": str(exc)}},
                    status_code=404,
                )
        else:
            tracker, project_id, _ = _find_tracker_for_issue(
                orch, resolved_identifier
            )
            if tracker is None:
                return JSONResponse(
                    {
                        "error": {
                            "code": "issue_not_found",
                            "message": f"Issue {resolved_identifier!r} not found",
                        }
                    },
                    status_code=404,
                )
        tracker.add_label(resolved_identifier, label)
        _api_cache.invalidate("issues:all")
        _api_cache.invalidate_prefix(f"detail:{project_id}:{resolved_identifier}")
        await broadcast_issues()
        return JSONResponse({"ok": True}, status_code=201)
    except Exception as exc:
        logger.error("Add label API error: %s", exc)
        return JSONResponse(
            {"error": {"code": "label_failed", "message": str(exc)}},
            status_code=500,
        )


@app.delete("/api/v1/issues/{identifier}/labels/{label}")
async def api_remove_label(identifier: str, label: str, request: Request):
    """Remove a label from an issue."""
    try:
        orch = _get_orchestrator()
        # Read project_id from request body (for consistency with POST /labels)
        # Fall back to query params for backward compatibility
        body = {}
        try:
            body = await request.json()
        except Exception:
            pass
        # Resolve identifier: issue_key query or body param overrides path param
        # to support GitHub identifiers with slashes.
        resolved_identifier = _resolve_identifier(identifier, body, request.query_params)
        # URL-decode the label in case it contains percent-encoded characters.
        decoded_label = urllib.parse.unquote(label)
        project_id = body.get("project_id") or request.query_params.get("project_id")
        managed_repo_req = (body.get("managed_repo") or "").strip() or None
        if project_id:
            tracker = _get_tracker(orch, project_id)
        elif managed_repo_req:
            try:
                tracker, project_id = _get_tracker_for_managed_repo(
                    orch, managed_repo_req
                )
            except ValueError as exc:
                return JSONResponse(
                    {"error": {"code": "not_found", "message": str(exc)}},
                    status_code=404,
                )
        else:
            tracker, project_id, _ = _find_tracker_for_issue(
                orch, resolved_identifier
            )
            if tracker is None:
                return JSONResponse(
                    {
                        "error": {
                            "code": "issue_not_found",
                            "message": f"Issue {resolved_identifier!r} not found",
                        }
                    },
                    status_code=404,
                )
        tracker.remove_label(resolved_identifier, decoded_label)
        _api_cache.invalidate("issues:all")
        _api_cache.invalidate_prefix(f"detail:{project_id}:{resolved_identifier}")
        await broadcast_issues()
        return JSONResponse({"ok": True})
    except Exception as exc:
        logger.error("Remove label API error: %s", exc)
        return JSONResponse(
            {"error": {"code": "label_failed", "message": str(exc)}},
            status_code=500,
        )


@app.post("/api/v1/issues/{identifier}/dependencies")
async def api_add_dependency(identifier: str, request: Request):
    """Record that *identifier* depends on (is blocked by) another issue.

    Request body (JSON):
        depends_on  – identifier of the blocker task (required)
        issue_key   – full identifier when the path param is URL-encoded
        project_id  – optional; used to resolve the tracker directly
        managed_repo – optional; ``owner/repo`` alternative to project_id
    """
    try:
        orch = _get_orchestrator()
        try:
            body = await request.json()
        except (json.JSONDecodeError, ValueError) as exc:
            return JSONResponse(
                {
                    "error": {
                        "code": "validation",
                        "message": f"Invalid JSON: {exc}",
                    }
                },
                status_code=400,
            )
        if not isinstance(body, dict):
            return JSONResponse(
                {
                    "error": {
                        "code": "validation",
                        "message": "request body must be a JSON object",
                    }
                },
                status_code=400,
            )

        depends_on = (body.get("depends_on") or "").strip()
        if not depends_on:
            return JSONResponse(
                {
                    "error": {
                        "code": "validation",
                        "message": "depends_on is required",
                    }
                },
                status_code=400,
            )

        resolved_identifier = _resolve_identifier(identifier, body, request.query_params)
        project_id = body.get("project_id") or request.query_params.get("project_id")
        managed_repo_req = (body.get("managed_repo") or "").strip() or None

        if project_id:
            tracker = _get_tracker(orch, project_id)
        elif managed_repo_req:
            if "/" not in managed_repo_req:
                return JSONResponse(
                    {
                        "error": {
                            "code": "validation",
                            "message": "managed_repo must be in 'owner/repo' format",
                        }
                    },
                    status_code=400,
                )
            try:
                tracker, project_id = _get_tracker_for_managed_repo(
                    orch, managed_repo_req
                )
            except ValueError as exc:
                return JSONResponse(
                    {"error": {"code": "not_found", "message": str(exc)}},
                    status_code=404,
                )
        else:
            tracker, project_id, _ = _find_tracker_for_issue(
                orch, resolved_identifier
            )
            if tracker is None:
                return JSONResponse(
                    {
                        "error": {
                            "code": "issue_not_found",
                            "message": f"Issue {resolved_identifier!r} not found",
                        }
                    },
                    status_code=404,
                )

        tracker.add_dependency(resolved_identifier, depends_on)
        _api_cache.invalidate("issues:all")
        _api_cache.invalidate_prefix(f"detail:{project_id}:{resolved_identifier}")
        await broadcast_issues()
        return JSONResponse({"ok": True}, status_code=201)
    except Exception as exc:
        logger.error("Add dependency API error: %s", exc)
        return JSONResponse(
            {"error": {"code": "dependency_failed", "message": str(exc)}},
            status_code=500,
        )


@app.get("/api/v1/issues/{identifier}/comments")
async def api_get_comments(identifier: str, request: Request):
    """Return comments for an issue.

    project_id is OPTIONAL. When omitted, this endpoint searches every known
    project for an issue with the given identifier (read-only fan-out).
    """
    try:
        orch = _get_orchestrator()
        project_id = request.query_params.get("project_id")
        cache_key = f"comments:{project_id}:{identifier}"
        cached = _api_cache.get(cache_key)
        if cached is not None:
            return JSONResponse(cached)
        tracker, resolved_project_id, issue = _find_tracker_for_issue(
            orch, identifier, project_id
        )
        if tracker is None or issue is None:
            return JSONResponse(
                {
                    "error": {
                        "code": "issue_not_found",
                        "message": f"Issue {identifier} not found",
                    }
                },
                status_code=404,
            )
        comments = tracker.fetch_comments(identifier)
        _api_cache.set(cache_key, comments, ttl_ms=3000)
        return JSONResponse(comments)
    except Exception as exc:
        logger.error("Comments API error: %s", exc)
        return JSONResponse(
            {"error": {"code": "unavailable", "message": str(exc)}},
            status_code=503,
        )


@app.post("/api/v1/issues/{identifier}/comments")
async def api_add_comment(identifier: str, request: Request):
    """Add a comment to an issue.

    When a non-agent user posts a comment on an issue with the
    'asking_question' label, the label is automatically removed so
    the orchestrator can re-dispatch an agent to continue work.
    """
    try:
        orch = _get_orchestrator()
        try:
            body = await request.json()
        except (json.JSONDecodeError, ValueError) as exc:
            return JSONResponse(
                {
                    "error": {
                        "code": "validation",
                        "message": f"Invalid JSON: {exc}",
                    }
                },
                status_code=400,
            )
        if not isinstance(body, dict):
            return JSONResponse(
                {
                    "error": {
                        "code": "validation",
                        "message": "request body must be a JSON object",
                    }
                },
                status_code=400,
            )
        text = body.get("text", "").strip()
        if not text:
            return JSONResponse(
                {
                    "error": {
                        "code": "validation",
                        "message": "Comment text is required",
                    }
                },
                status_code=400,
            )
        author = body.get("author", "user")
        # Resolve identifier: issue_key body field overrides path param to
        # support GitHub identifiers with slashes.
        resolved_identifier = _resolve_identifier(identifier, body, request.query_params)
        project_id = body.get("project_id") or request.query_params.get("project_id")
        managed_repo_req = (body.get("managed_repo") or "").strip() or None
        if project_id:
            tracker = _get_tracker(orch, project_id)
        elif managed_repo_req:
            try:
                tracker, project_id = _get_tracker_for_managed_repo(
                    orch, managed_repo_req
                )
            except ValueError as exc:
                return JSONResponse(
                    {"error": {"code": "not_found", "message": str(exc)}},
                    status_code=404,
                )
        else:
            tracker, project_id, _ = _find_tracker_for_issue(
                orch, resolved_identifier
            )
            if tracker is None:
                return JSONResponse(
                    {
                        "error": {
                            "code": "issue_not_found",
                            "message": f"Issue {resolved_identifier!r} not found",
                        }
                    },
                    status_code=404,
                )
        result = tracker.add_comment(resolved_identifier, text, author=author)

        # When a human (non-oompah) answers a question, move the task
        # back to Open so the orchestrator picks it up.
        if author != "oompah":
            try:
                issue = tracker.fetch_issue_detail(resolved_identifier)
                if issue and (
                    canonicalize_status(issue.state) == NEEDS_ANSWER
                    or "asking_question" in issue.labels
                ):
                    tracker.update_issue(resolved_identifier, status=OPEN)
                    if "asking_question" in issue.labels:
                        tracker.remove_label(resolved_identifier, "asking_question")
                    logger.info(
                        "Moved %s from Needs Answer to Open after user comment",
                        resolved_identifier,
                    )
                    # Trigger dispatch so the orchestrator re-dispatches promptly
                    orch = _get_orchestrator()
                    if orch:
                        orch.request_refresh()
            except Exception as exc:
                logger.debug(
                    "Failed to check/remove asking_question label on %s: %s",
                    resolved_identifier,
                    exc,
                )

        _api_cache.invalidate(f"comments:{project_id}:{resolved_identifier}")
        _api_cache.invalidate_prefix(f"detail:{project_id}:{resolved_identifier}")
        _api_cache.invalidate("issues:all")
        await broadcast_issues()
        return JSONResponse(result, status_code=201)
    except Exception as exc:
        logger.error("Add comment API error: %s", exc)
        return JSONResponse(
            {"error": {"code": "comment_failed", "message": str(exc)}},
            status_code=500,
        )


@app.get("/api/v1/issues/{identifier}/detail")
async def api_issue_full_detail(identifier: str, request: Request):
    """Return full issue detail for the slide-out panel.

    project_id is OPTIONAL. When omitted, this endpoint searches every known
    project for an issue with the given identifier. The slide-out panel may
    not know which project an issue belongs to (e.g. when opened from a
    cross-project listing).
    """
    try:
        orch = _get_orchestrator()
        project_id = request.query_params.get("project_id")
        # Resolve identifier: issue_key query param overrides path param to
        # support GitHub identifiers with slashes.
        resolved_identifier = _resolve_identifier(identifier, None, request.query_params)
        cache_key = f"detail:{project_id}:{resolved_identifier}"
        cached = _api_cache.get(cache_key)
        if cached is not None:
            return JSONResponse(cached)
        tracker, resolved_project_id, issue = _find_tracker_for_issue(
            orch, resolved_identifier, project_id
        )
        if tracker is None or issue is None:
            return JSONResponse(
                {
                    "error": {
                        "code": "issue_not_found",
                        "message": f"Issue {resolved_identifier} not found",
                    }
                },
                status_code=404,
            )
        # Use the resolved project_id (may differ from query param if it was None)
        project_id = resolved_project_id
        project_names = _project_names_by_id(orch)
        project_name = project_names.get(project_id or "")
        # Prefer the tracker's own display_identifier when set (GitHub issues);
        # fall back to the Backlog-specific formatter for legacy issues.
        display_id = getattr(issue, "display_identifier", None) or _display_identifier(
            issue.identifier, project_name
        )
        result = {
            "id": issue.id,
            "identifier": issue.identifier,
            "display_identifier": display_id,
            "project_name": project_name,
            "title": issue.title,
            "description": issue.description,
            "priority": issue.priority,
            "state": issue.state,
            "issue_type": issue.issue_type,
            "parent_id": issue.parent_id,
            "project_id": project_id,
            "labels": issue.labels,
            "created_at": issue.created_at.isoformat() if issue.created_at else None,
            "updated_at": issue.updated_at.isoformat() if issue.updated_at else None,
            # Tracker identity fields — present for GitHub-backed issues;
            # null/false for legacy Backlog-backed issues (backward compat).
            "tracker_kind": getattr(issue, "tracker_kind", None),
            "tracker_owner": getattr(issue, "tracker_owner", None),
            "tracker_repo": getattr(issue, "tracker_repo", None),
            "issue_number": getattr(issue, "issue_number", None),
            "url": getattr(issue, "url", None) or getattr(issue, "provider_url", None),
            "managed_repo": getattr(issue, "managed_repo", None),
            "target_branch": getattr(issue, "target_branch", None),
            "work_branch": getattr(issue, "work_branch", None),
            "is_legacy": bool(getattr(issue, "is_legacy", False)),
        }
        if issue.issue_type in ("epic", "feature"):
            children = tracker.fetch_children(issue.id)
            result["children"] = [
                {
                    "id": c.id,
                    "identifier": c.identifier,
                    "display_identifier": (
                        getattr(c, "display_identifier", None)
                        or _display_identifier(
                            c.identifier,
                            project_names.get(c.project_id or "") or project_name,
                        )
                    ),
                    "project_name": (
                        project_names.get(c.project_id or "") or project_name
                    ),
                    "title": c.title,
                    "state": c.state,
                    "priority": c.priority,
                    "issue_type": c.issue_type,
                    "project_id": c.project_id or project_id,
                }
                for c in children
            ]
        # Always include comments
        result["comments"] = tracker.fetch_comments(issue.identifier)
        _api_cache.set(cache_key, result, ttl_ms=3000)
        return JSONResponse(result)
    except Exception as exc:
        logger.error("Issue detail API error: %s", exc)
        return JSONResponse(
            {"error": {"code": "unavailable", "message": str(exc)}},
            status_code=503,
        )


@app.get("/api/v1/issues/{identifier}/release-picks")
async def api_get_release_picks(identifier: str, request: Request):
    """Return normalised release-pick metadata for a task.

    Reads ``oompah.backports`` and ``oompah.backport_of`` frontmatter from
    the task identified by *identifier* and returns a dict with:

    * ``identifier`` — the task identifier.
    * ``backports`` — list of backport entries, each with ``branch``,
      ``status``, ``task_id``, ``pr_url``, ``pr_id`` (derived),
      ``is_valid``, and ``validation_error``.
    * ``backport_of`` — ``{source, status}`` when this task is a child
      backport task, otherwise ``null``.

    When *project_id* is supplied as a query parameter the target branches
    in ``backports`` are validated against the project's configured patterns.
    """
    try:
        from oompah.release_pick_api import get_release_pick_detail

        orch = _get_orchestrator()
        project_id = request.query_params.get("project_id")
        tracker, resolved_project_id, issue = _find_tracker_for_issue(
            orch, identifier, project_id
        )
        if tracker is None or issue is None:
            return JSONResponse(
                {
                    "error": {
                        "code": "issue_not_found",
                        "message": f"Issue {identifier} not found",
                    }
                },
                status_code=404,
            )
        project = None
        if resolved_project_id:
            try:
                project = orch.project_store.get(resolved_project_id)
            except Exception:
                project = None
        result = get_release_pick_detail(tracker, issue.identifier, project=project)
        return JSONResponse(result)
    except Exception as exc:
        logger.error("Release picks GET API error for %s: %s", identifier, exc)
        return JSONResponse(
            {"error": {"code": "unavailable", "message": str(exc)}},
            status_code=503,
        )


@app.patch("/api/v1/issues/{identifier}/release-picks")
async def api_update_release_picks(identifier: str, request: Request):
    """Update release-pick metadata for a task.

    Accepts a JSON body with one of two update modes:

    **Single-entry update** (``branch`` key at root level)::

        {
            "project_id": "my-project",
            "branch": "release/1.0",
            "status": "pr_open",
            "task_id": "TASK-123.1",
            "pr_url": "https://github.com/org/repo/pull/42"
        }

    **Bulk update** (``backports`` list at root level)::

        {
            "project_id": "my-project",
            "backports": [
                {"branch": "release/1.0", "status": "pr_open", "task_id": "TASK-123.1"},
                {"branch": "release/2.0", "status": "waiting"}
            ]
        }

    ``project_id`` is **required** for write operations so the server can
    look up the correct project tracker and validate target branches.

    Returns the updated release-pick detail (same shape as GET).
    """
    try:
        from oompah.release_pick_api import (
            get_release_pick_detail,
            update_release_pick_entry,
            update_release_picks_bulk,
        )

        # Parse and validate body before touching the orchestrator so that
        # basic input errors return 400 without requiring a running server.
        try:
            body = await request.json()
        except (json.JSONDecodeError, ValueError) as exc:
            return JSONResponse(
                {"error": {"code": "validation", "message": f"Invalid JSON: {exc}"}},
                status_code=400,
            )
        if not isinstance(body, dict):
            return JSONResponse(
                {
                    "error": {
                        "code": "validation",
                        "message": "Request body must be a JSON object",
                    }
                },
                status_code=400,
            )

        project_id = body.get("project_id") or request.query_params.get("project_id")
        if not project_id:
            return JSONResponse(
                {
                    "error": {
                        "code": "validation",
                        "message": "project_id is required for release-pick updates",
                    }
                },
                status_code=400,
            )

        orch = _get_orchestrator()
        try:
            tracker = _get_tracker(orch, project_id)
        except Exception as exc:
            return JSONResponse(
                {"error": {"code": "project_not_found", "message": str(exc)}},
                status_code=404,
            )

        project = None
        try:
            project = orch.project_store.get(project_id)
        except Exception:
            project = None

        # Determine update mode: bulk (backports list) or single-entry
        backports_list = body.get("backports")
        if backports_list is not None:
            # Bulk mode
            if not isinstance(backports_list, list):
                return JSONResponse(
                    {
                        "error": {
                            "code": "validation",
                            "message": "'backports' must be a list of objects",
                        }
                    },
                    status_code=400,
                )
            try:
                result = update_release_picks_bulk(
                    tracker,
                    identifier,
                    backports=backports_list,
                    project=project,
                )
            except ValueError as exc:
                return JSONResponse(
                    {"error": {"code": "validation", "message": str(exc)}},
                    status_code=400,
                )
        else:
            # Single-entry mode — "branch" is required
            branch = body.get("branch")
            if not branch:
                return JSONResponse(
                    {
                        "error": {
                            "code": "validation",
                            "message": (
                                "Either 'branch' (single-entry mode) or "
                                "'backports' (bulk mode) is required"
                            ),
                        }
                    },
                    status_code=400,
                )
            try:
                result = update_release_pick_entry(
                    tracker,
                    identifier,
                    branch=branch,
                    status=body.get("status"),
                    task_id=body.get("task_id"),
                    pr_url=body.get("pr_url"),
                    project=project,
                )
            except ValueError as exc:
                return JSONResponse(
                    {"error": {"code": "validation", "message": str(exc)}},
                    status_code=400,
                )

        # Invalidate any cached detail for this issue
        _api_cache.invalidate_prefix(f"detail:{project_id}:{identifier}")
        return JSONResponse(result)
    except Exception as exc:
        logger.error("Release picks PATCH API error for %s: %s", identifier, exc)
        return JSONResponse(
            {"error": {"code": "unavailable", "message": str(exc)}},
            status_code=503,
        )


@app.get("/api/v1/issues/{identifier}/release-picks/matrix")
async def api_get_epic_release_picks_matrix(identifier: str, request: Request):
    """Return the child-by-target-branch release-pick matrix for an epic.

    Fetches all child tasks of the epic identified by *identifier*, reads
    their ``oompah.backports`` metadata, and returns a matrix where each row
    is a child task and each column is a unique target branch.

    Response shape::

        {
            "epic_identifier": "TASK-456",
            "branches": ["release/1.0", "release/2.0"],
            "rows": [
                {
                    "identifier": "TASK-456.1",
                    "title": "...",
                    "state": "done",
                    "entries": {
                        "release/1.0": { <normalised entry> },
                        "release/2.0": null
                    }
                }
            ]
        }

    Optional query parameter: ``project_id`` — when supplied, target branches
    are validated against the project's configured patterns.
    """
    try:
        from oompah.release_pick_api import get_epic_release_pick_matrix

        orch = _get_orchestrator()
        project_id = request.query_params.get("project_id")
        tracker, resolved_project_id, issue = _find_tracker_for_issue(
            orch, identifier, project_id
        )
        if tracker is None:
            return JSONResponse(
                {
                    "error": {
                        "code": "issue_not_found",
                        "message": f"Issue {identifier} not found",
                    }
                },
                status_code=404,
            )
        project = None
        if resolved_project_id:
            try:
                project = orch.project_store.get(resolved_project_id)
            except Exception:
                project = None
        result = get_epic_release_pick_matrix(tracker, identifier, project=project)
        return JSONResponse(result)
    except Exception as exc:
        logger.error(
            "Release picks matrix GET API error for %s: %s", identifier, exc
        )
        return JSONResponse(
            {"error": {"code": "unavailable", "message": str(exc)}},
            status_code=503,
        )


@app.post("/api/v1/issues/{identifier}/release-picks/apply-all")
async def api_apply_release_picks_to_all_children(identifier: str, request: Request):
    """Apply a set of release-pick branches to all children of an epic.

    Accepts a JSON body::

        {
            "project_id": "my-project",
            "branches": ["release/1.0", "release/2.0"],
            "skip_children": ["TASK-456.3"]
        }

    * ``project_id`` — **required**.  Used to locate the tracker and
      validate branch names.
    * ``branches`` — **required**.  List of target branch names to apply to
      every child.
    * ``skip_children`` — optional list of child identifiers that should
      receive a ``skipped`` entry instead of ``waiting``.

    Returns the updated epic release-pick matrix (same shape as
    ``GET /api/v1/issues/{identifier}/release-picks/matrix``).
    """
    try:
        from oompah.release_pick_api import apply_release_picks_to_all_children

        try:
            body = await request.json()
        except (json.JSONDecodeError, ValueError) as exc:
            return JSONResponse(
                {"error": {"code": "validation", "message": f"Invalid JSON: {exc}"}},
                status_code=400,
            )
        if not isinstance(body, dict):
            return JSONResponse(
                {
                    "error": {
                        "code": "validation",
                        "message": "Request body must be a JSON object",
                    }
                },
                status_code=400,
            )

        project_id = body.get("project_id") or request.query_params.get("project_id")
        if not project_id:
            return JSONResponse(
                {
                    "error": {
                        "code": "validation",
                        "message": "project_id is required for release-pick apply-all",
                    }
                },
                status_code=400,
            )

        branches = body.get("branches")
        if not branches or not isinstance(branches, list):
            return JSONResponse(
                {
                    "error": {
                        "code": "validation",
                        "message": "'branches' must be a non-empty list of branch names",
                    }
                },
                status_code=400,
            )

        orch = _get_orchestrator()
        try:
            tracker = _get_tracker(orch, project_id)
        except Exception as exc:
            return JSONResponse(
                {"error": {"code": "project_not_found", "message": str(exc)}},
                status_code=404,
            )

        project = None
        try:
            project = orch.project_store.get(project_id)
        except Exception:
            project = None

        skip_children = body.get("skip_children") or []
        if not isinstance(skip_children, list):
            return JSONResponse(
                {
                    "error": {
                        "code": "validation",
                        "message": "'skip_children' must be a list of identifiers",
                    }
                },
                status_code=400,
            )

        try:
            result = apply_release_picks_to_all_children(
                tracker,
                identifier,
                branches=branches,
                skip_children=skip_children,
                project=project,
            )
        except ValueError as exc:
            return JSONResponse(
                {"error": {"code": "validation", "message": str(exc)}},
                status_code=400,
            )

        return JSONResponse(result)
    except Exception as exc:
        logger.error(
            "Release picks apply-all POST API error for %s: %s", identifier, exc
        )
        return JSONResponse(
            {"error": {"code": "unavailable", "message": str(exc)}},
            status_code=503,
        )


@app.get("/api/v1/agents/{identifier}/activity")
async def api_agent_activity(identifier: str):
    """Return the activity log for a running agent."""
    try:
        orch = _get_orchestrator()
        for entry in orch.state.running.values():
            if entry.identifier == identifier:
                return JSONResponse(
                    {
                        "identifier": identifier,
                        "profile": entry.agent_profile_name,
                        "provider_name": entry.provider_name,
                        "model_name": entry.model_name,
                        "started_at": entry.started_at.isoformat(),
                        "activity": [a.to_dict() for a in entry.activity_log],
                    }
                )
        return JSONResponse({"identifier": identifier, "activity": []})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/v1/orchestrator/pause")
async def api_orchestrator_pause():
    """Pause the orchestrator (stop dispatching new agents).

    In multi-process / API-only mode enqueues a 'pause' command in the
    IPC SQLite queue so the scheduler process picks it up on the next tick.
    """
    try:
        if _orchestrator is None and _ipc is not None:
            cmd_id = _ipc.enqueue_command("pause")
            return JSONResponse({"ok": True, "paused": True, "ipc_command_id": cmd_id})
        orch = _get_orchestrator()
        orch.pause()
        return JSONResponse({"ok": True, "paused": True})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/v1/orchestrator/resume")
async def api_orchestrator_resume():
    """Resume the orchestrator.

    In multi-process / API-only mode enqueues an 'unpause' command in
    the IPC SQLite queue.
    """
    try:
        if _orchestrator is None and _ipc is not None:
            cmd_id = _ipc.enqueue_command("unpause")
            return JSONResponse({"ok": True, "paused": False, "ipc_command_id": cmd_id})
        orch = _get_orchestrator()
        orch.unpause()
        return JSONResponse({"ok": True, "paused": False})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/v1/orchestrator/restart")
async def api_orchestrator_restart(request: Request):
    """Graceful restart: drain running agents, then restart the process."""
    try:
        orch = _get_orchestrator()
        body = {}
        try:
            body = await request.json()
        except Exception:
            pass
        drain_timeout = body.get("drain_timeout_s", 60)
        running_count = len(orch.state.running)
        asyncio.create_task(orch.graceful_restart(drain_timeout_s=drain_timeout))
        return JSONResponse(
            {
                "ok": True,
                "draining": running_count,
                "drain_timeout_s": drain_timeout,
            }
        )
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/v1/orchestrator/dispatch/{identifier}")
async def api_orchestrator_dispatch(identifier: str):
    """Manually dispatch a specific issue to an agent.

    In multi-process / API-only mode enqueues a 'dispatch_issue' command in
    the IPC SQLite queue so the scheduler process picks it up on the next tick.
    """
    try:
        if _orchestrator is None and _ipc is not None:
            cmd_id = _ipc.enqueue_command("dispatch_issue", {"identifier": identifier})
            return JSONResponse({"ok": True, "dispatched": identifier, "ipc_command_id": cmd_id})
        orch = _get_orchestrator()
        # _fetch_all_candidates() uses asyncio.run() internally; calling it
        # directly from an async route raises "asyncio.run() cannot be called
        # from a running event loop".  Run it in a thread pool so it gets its
        # own event loop, matching how the tick loop handles it (TASK-495).
        candidates = await asyncio.to_thread(orch._fetch_all_candidates)
        issue = next((i for i in candidates if i.identifier == identifier), None)
        if not issue:
            return JSONResponse(
                {"error": f"Issue {identifier} not found or not dispatchable"},
                status_code=404,
            )
        await orch._dispatch(issue, attempt=None)
        return JSONResponse({"ok": True, "dispatched": identifier})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/v1/providers")
async def api_list_providers():
    """List all configured model providers."""
    providers = _provider_store.list_all()
    return JSONResponse([p.to_safe_dict() for p in providers])


@app.get("/api/v1/acp-backends")
async def api_list_acp_backends():
    """List registered ACP backends.

    Surfaces the registry from ``oompah/acp_backends/registry.py`` so
    the provider edit dialog can populate its Backend dropdown without
    hardcoding the backend names. ``default`` is the back-compat
    default applied when a provider has no backend field set on disk.

    Each entry in ``descriptors`` carries the metadata the dashboard
    needs to render the Fetch Models button correctly
    (oompah-zlz_2-zvm0 §3):

    * ``has_catalog`` — True iff the backend implements ``fetch_models()``.
      When False, the dashboard disables the button with a tooltip.
    * ``supports_model_selection`` — mirrors ``has_catalog`` today;
      separate field reserved for future backends that support a
      catalog but only at session-creation time.
    * ``fetch_note`` — short human-readable string the dashboard
      surfaces alongside the disabled state (e.g. for Claude:
      "Claude SDK manages model selection via subscription.").
    * ``label`` — backend display name for the dropdown.
    """
    from oompah.acp_backends import BACKENDS

    descriptors: dict[str, dict[str, Any]] = {}
    for name, cls in BACKENDS.items():
        # Sniff fetch_models() at class- or instance-level. The default
        # ClaudeAcpBackend has none; future Codex backend may add one.
        has_catalog = callable(getattr(cls, "fetch_models", None))
        # Per-backend note: ClaudeAcpBackend's subscription path is the
        # one well-known case; everything else gets a generic note that
        # the dashboard can override via the disabled-tooltip text.
        if name == "claude":
            fetch_note = "Claude SDK manages model selection via subscription."
        elif not has_catalog:
            fetch_note = (
                f"Backend {name!r} does not expose a model catalog — "
                f"enter model names manually if needed."
            )
        else:
            fetch_note = ""
        descriptors[name] = {
            "label": getattr(cls, "label", None) or name,
            "has_catalog": has_catalog,
            "supports_model_selection": has_catalog,
            "fetch_note": fetch_note,
        }
    return JSONResponse(
        {
            "backends": sorted(BACKENDS.keys()),
            "default": "claude",
            "descriptors": descriptors,
        }
    )


@app.post("/api/v1/providers")
async def api_create_provider(request: Request):
    """Create a new model provider.

    Validation rules:
      - ``name`` is always required.
      - ``mode`` must be one of {"api", "acp"} (defaults to "api").
      - When mode == "api": ``base_url`` is required (legacy behavior;
        the OpenAI-compatible client cannot operate without it).
      - When mode == "acp": ``base_url`` and ``api_key`` are optional —
        the Claude Agent SDK manages the connection and bills against
        the operator's claude subscription.
    """
    try:
        try:
            body = await request.json()
        except (json.JSONDecodeError, ValueError) as exc:
            return JSONResponse(
                {
                    "error": {
                        "code": "validation",
                        "message": f"Invalid JSON: {exc}",
                    }
                },
                status_code=400,
            )
        if not isinstance(body, dict):
            return JSONResponse(
                {
                    "error": {
                        "code": "validation",
                        "message": "request body must be a JSON object",
                    }
                },
                status_code=400,
            )
        name = body.get("name", "").strip()
        raw_mode = str(body.get("mode", "api") or "api").lower()
        mode = raw_mode if raw_mode in ("api", "acp") else "api"
        base_url = body.get("base_url", "").strip()
        if not name:
            return JSONResponse(
                {"error": {"code": "validation", "message": "Name is required"}},
                status_code=400,
            )
        # ACP providers don't need a base_url — the Claude Agent SDK
        # manages the connection. API providers still need one or the
        # OpenAI-compatible client can't dispatch a single call.
        if mode == "api" and not base_url:
            return JSONResponse(
                {
                    "error": {
                        "code": "validation",
                        "message": "base_url is required for api-mode providers",
                    }
                },
                status_code=400,
            )
        provider = _provider_store.create(
            name=name,
            base_url=base_url,
            api_key=body.get("api_key", ""),
            models=body.get("models", []),
            default_model=body.get("default_model"),
            provider_type=body.get("provider_type", "openai"),
            # ACP backend selector (used only when an agent profile
            # with mode=acp routes through this provider). None means
            # "default to claude" — preserves back-compat for providers
            # created before the field existed.
            backend=body.get("backend"),
            mode=mode,
            acp_permission_mode=body.get("acp_permission_mode"),
            acp_subscription_only=bool(body.get("acp_subscription_only", False)),
            # ACP billing model (oompah-zlz_2-ag7h). "subscription"
            # (default) bypasses the budget gate; "per_token"
            # participates in it. Ignored for non-acp modes.
            billing_model=body.get("billing_model", "subscription"),
        )
        return JSONResponse(provider.to_safe_dict(), status_code=201)
    except Exception as exc:
        logger.error("Create provider error: %s", exc)
        return JSONResponse(
            {"error": {"code": "create_failed", "message": str(exc)}},
            status_code=500,
        )


@app.patch("/api/v1/providers/{provider_id}")
async def api_update_provider(provider_id: str, request: Request):
    """Update a model provider.

    Accepts partial updates. ACP-aware validation rules:
      - When the request flips ``mode`` to "api" and the (resulting)
        provider has no ``base_url``, the request is rejected.
      - Switching to ``mode == "acp"`` is always allowed; base_url and
        api_key remain stored but unused.
    """
    try:
        try:
            body = await request.json()
        except (json.JSONDecodeError, ValueError) as exc:
            return JSONResponse(
                {
                    "error": {
                        "code": "validation",
                        "message": f"Invalid JSON: {exc}",
                    }
                },
                status_code=400,
            )
        if not isinstance(body, dict):
            return JSONResponse(
                {
                    "error": {
                        "code": "validation",
                        "message": "request body must be a JSON object",
                    }
                },
                status_code=400,
            )
        fields = {}
        for key in (
            "name",
            "base_url",
            "api_key",
            "models",
            "default_model",
            "provider_type",
            "model_roles",
            "model_costs",
            "model_capabilities",
            "mode",
            "acp_permission_mode",
            "acp_subscription_only",
            "backend",
            "billing_model",
        ):
            if key in body:
                fields[key] = body[key]
        # Normalize backend: "" → None so the default-to-claude
        # resolution at validate time keeps working.
        if fields.get("backend") == "":
            fields["backend"] = None
        # Normalize the mode field early so the validation below sees
        # the value the store will end up writing.
        if "mode" in fields:
            m = str(fields["mode"] or "api").lower()
            fields["mode"] = m if m in ("api", "acp") else "api"
        # Normalize billing_model: drop unknown values back to
        # "subscription" so a typo or stale client doesn't silently
        # start metering against the budget. Mirrors the from_dict
        # safety net in oompah/models.py.
        if "billing_model" in fields:
            val = fields["billing_model"]
            if not isinstance(val, str) or val.lower() not in (
                "subscription",
                "per_token",
            ):
                fields["billing_model"] = "subscription"
            else:
                fields["billing_model"] = val.lower()
        # Determine the effective post-update mode + base_url to enforce
        # the api-mode base_url requirement (regression preserved).
        existing = _provider_store.get(provider_id)
        if existing is None:
            return JSONResponse(
                {
                    "error": {
                        "code": "not_found",
                        "message": f"Provider {provider_id} not found",
                    }
                },
                status_code=404,
            )
        effective_mode = fields.get("mode", existing.mode)
        effective_base_url = fields.get("base_url", existing.base_url)
        if effective_mode == "api" and not (effective_base_url or "").strip():
            return JSONResponse(
                {
                    "error": {
                        "code": "validation",
                        "message": "base_url is required for api-mode providers",
                    }
                },
                status_code=400,
            )
        provider = _provider_store.update(provider_id, **fields)
        if not provider:
            return JSONResponse(
                {
                    "error": {
                        "code": "not_found",
                        "message": f"Provider {provider_id} not found",
                    }
                },
                status_code=404,
            )
        return JSONResponse(provider.to_safe_dict())
    except Exception as exc:
        logger.error("Update provider error: %s", exc)
        return JSONResponse(
            {"error": {"code": "update_failed", "message": str(exc)}},
            status_code=500,
        )


@app.delete("/api/v1/providers/{provider_id}")
async def api_delete_provider(provider_id: str):
    """Delete a model provider."""
    if _provider_store.delete(provider_id):
        return JSONResponse({"ok": True})
    return JSONResponse(
        {
            "error": {
                "code": "not_found",
                "message": f"Provider {provider_id} not found",
            }
        },
        status_code=404,
    )


# ----------------------------------------------------------------------
# Provider health-check endpoint (TASK-407.3)
#
# POST /api/v1/providers/{provider_id}/test
#
# Sends a tiny prompt to the provider and returns a structured result
# with success/failure, model used, latency, response text, and a
# normalized error reason. Does NOT create tasks, mutate config, or
# update role round-robin state.
# ----------------------------------------------------------------------


@app.post("/api/v1/providers/{provider_id}/test")
async def api_test_provider(provider_id: str):
    """Manually test a configured provider by sending a tiny probe prompt.

    Returns 200 with a structured result body regardless of whether the
    probe succeeded (the ``success`` field distinguishes the two cases).
    Returns 404 only when the provider_id is not in the store at all.
    """
    from oompah.provider_health import run_acp_health_check, run_health_check

    provider = _provider_store.get(provider_id)
    if provider is None:
        return JSONResponse(
            {
                "error": {
                    "code": "not_found",
                    "message": f"Provider {provider_id} not found",
                }
            },
            status_code=404,
        )

    try:
        if provider.mode == "acp":
            # ACP providers are session-based (Claude Agent SDK / OpenAI
            # Agents SDK / opencode CLI, per provider.backend) and must be
            # probed by running a live turn — there is no synchronous HTTP
            # path. run_acp_health_check is async, so await it directly
            # rather than offloading to a thread.
            result = await run_acp_health_check(provider)
        else:
            result = await asyncio.to_thread(run_health_check, provider)
    except Exception as exc:
        logger.error("Provider health-check error for %s: %s", provider_id, exc)
        return JSONResponse(
            {
                "provider_id": provider_id,
                "provider_name": provider.name,
                "model": "",
                "success": False,
                "latency_ms": 0.0,
                "error_reason": "unknown_error",
                "error_detail": str(exc)[:300],
            }
        )

    return JSONResponse(result.to_dict())


# ----------------------------------------------------------------------
# Agent profiles CRUD (oompah-zlz_2-xaj + oompah-zlz_2-mif)
#
# Backed by AgentProfileStore at .oompah/agent_profiles.json.
# WORKFLOW.md remains a fallback / migration source only — once a profile
# JSON file exists, WORKFLOW.md edits are ignored on reload.
#
# Validation rules (POST/PATCH):
#   - name: non-empty, unique across the store.
#   - mode: one of {auto, api, cli, acp}; falls through AgentProfileStore
#           validator which uses VALID_MODES.
#   - api / auto modes: provider_id required.
#   - acp mode:        provider_id NOT required.
#
# Live-reload: a successful POST/PATCH/DELETE goes through the store's
# reload callback (registered in :func:`set_orchestrator`) which calls
# ``Orchestrator.replace_agent_profiles``. That queues a partial config
# swap applied at the next ``_tick()`` quiescent point — no WORKFLOW.md
# round-trip. See oompah-zlz_2-mif.
# ----------------------------------------------------------------------


def _validate_profile_payload_acp_aware(
    body: dict,
    *,
    existing_profile=None,
) -> tuple[dict, list[str]]:
    """Cross-store validation hook for /api/v1/agent-profiles writes.

    Layered ON TOP of AgentProfileStore's own per-record validation
    (which only enforces invariants visible to the store: name, mode
    enum, provider_id presence for api/auto). This adds the checks
    that need ProviderStore / ACP-mode awareness — see task
    oompah-zlz_2-rls:

    * mode=api: provider_id must EXIST in ProviderStore (not just be
      non-empty).
    * mode=acp: provider_id is ignored at dispatch — warn if the
      operator submits one.
    * model_role: when set AND the resolved provider has a
      model_roles map, the role must exist as a key (otherwise
      dispatch will fail at resolve time with a confusing "role
      not defined" error).

    Returns (cleaned_body, warnings). Raises ValueError on hard
    failures with a human-readable message.

    ``existing_profile`` is the current store record for PATCH calls
    (None for POST), so partial bodies validate against the merged
    shape — e.g. PATCH ``{"mode": "acp"}`` on a profile that already
    has a provider_id triggers the warning.
    """
    out = dict(body)
    warnings: list[str] = []

    # Resolve effective mode / provider_id / model_role across the
    # body and the existing record so partial PATCHes validate
    # correctly.
    def _eff(key, default=None):
        if key in body:
            return body[key]
        if existing_profile is not None:
            return getattr(existing_profile, key, default)
        return default

    mode = (_eff("mode", "auto") or "auto").strip().lower()
    provider_id = _eff("provider_id")
    model_role = _eff("model_role")

    if mode == "acp":
        if provider_id:
            warnings.append(
                "mode=acp ignores provider_id — calls bill against the "
                "operator's claude subscription, not a provider. "
                "The saved value will be retained but not used at dispatch."
            )
    elif mode == "api":
        if not provider_id:
            raise ValueError("mode=api requires provider_id")
        if _provider_store.get(provider_id) is None:
            raise ValueError(
                f"provider_id {provider_id!r} does not exist in ProviderStore"
            )
    elif mode == "auto":
        # auto can fall back to the lone default provider, so an
        # empty provider_id is OK; but if one is supplied it must
        # exist.
        if provider_id and _provider_store.get(provider_id) is None:
            raise ValueError(
                f"provider_id {provider_id!r} does not exist in ProviderStore"
            )

    # model_role check: resolve against the provider's model_roles
    # map. Only applies when a provider can be resolved (mode in
    # auto/api with a provider_id).
    if model_role and mode in ("auto", "api") and provider_id:
        prov = _provider_store.get(provider_id)
        if prov is not None and prov.model_roles:
            if model_role not in prov.model_roles:
                roles = sorted(prov.model_roles.keys())
                raise ValueError(
                    f"model_role {model_role!r} not defined in provider "
                    f"{prov.name!r}. Configured roles: "
                    f"{', '.join(roles) if roles else '(none)'}"
                )

    return out, warnings


@app.get("/api/v1/agent-profiles")
async def api_list_agent_profiles():
    """List all configured agent profiles from the JSON store."""
    profiles = _agent_profile_store.list_all()
    return JSONResponse([p.to_dict() for p in profiles])


@app.post("/api/v1/agent-profiles")
async def api_create_agent_profile(request: Request):
    """Create a new agent profile.

    Body: full AgentProfile JSON (see AgentProfile.to_dict). Required:
    name, command (defaults if absent), mode. provider_id required when
    mode in {auto, api}.

    Validation layers (see task oompah-zlz_2-rls):

    * Cross-store: mode=api requires an EXISTING provider_id;
      mode=acp warns if provider_id is set; model_role must exist
      in the provider's model_roles map when the map is non-empty.
    * Per-record: name uniqueness, mode enum, etc. (AgentProfileStore).

    Live-reload (oompah-zlz_2-mif): a successful create fires the store's
    reload callback, which queues a partial orchestrator config swap that
    applies at the start of the next ``_tick()``. No WORKFLOW.md edit
    required; in-flight running agents keep their existing profile.
    """
    try:
        body = await request.json()
    except Exception as exc:  # noqa: BLE001 — malformed JSON body
        return JSONResponse(
            {"error": {"code": "validation", "message": f"Invalid JSON: {exc}"}},
            status_code=400,
        )
    try:
        if not isinstance(body, dict):
            return JSONResponse(
                {
                    "error": {
                        "code": "validation",
                        "message": "Request body must be a JSON object",
                    }
                },
                status_code=400,
            )
        try:
            body, warnings = _validate_profile_payload_acp_aware(body)
        except ValueError as exc:
            return JSONResponse(
                {"error": {"code": "validation", "message": str(exc)}},
                status_code=400,
            )
        try:
            profile = _agent_profile_store.create(body)
        except AgentProfileError as exc:
            return JSONResponse(
                {"error": {"code": "validation", "message": str(exc)}},
                status_code=400,
            )
        out = profile.to_dict()
        if warnings:
            out["warnings"] = warnings
        return JSONResponse(out, status_code=201)
    except Exception as exc:
        logger.error("Create agent profile error: %s", exc)
        return JSONResponse(
            {"error": {"code": "create_failed", "message": str(exc)}},
            status_code=500,
        )


@app.patch("/api/v1/agent-profiles/{name}")
async def api_update_agent_profile(name: str, request: Request):
    """Patch an existing agent profile by name.

    Body: partial dict of fields to update. Validates the resulting
    profile (uniqueness if renamed; mode/provider_id consistency).
    Cross-store validation: same rules as POST (see
    ``_validate_profile_payload_acp_aware``).

    Live-reload (oompah-zlz_2-mif): a successful update fires the store's
    reload callback, queuing a partial orchestrator config swap that
    applies at the next ``_tick()`` quiescent point.
    """
    try:
        body = await request.json()
    except Exception as exc:  # noqa: BLE001 — malformed JSON body
        return JSONResponse(
            {"error": {"code": "validation", "message": f"Invalid JSON: {exc}"}},
            status_code=400,
        )
    try:
        if not isinstance(body, dict):
            return JSONResponse(
                {
                    "error": {
                        "code": "validation",
                        "message": "Request body must be a JSON object",
                    }
                },
                status_code=400,
            )
        existing = _agent_profile_store.get(name)
        if existing is None:
            return JSONResponse(
                {
                    "error": {
                        "code": "not_found",
                        "message": f"Agent profile {name!r} not found",
                    }
                },
                status_code=404,
            )
        try:
            body, warnings = _validate_profile_payload_acp_aware(
                body,
                existing_profile=existing,
            )
        except ValueError as exc:
            return JSONResponse(
                {"error": {"code": "validation", "message": str(exc)}},
                status_code=400,
            )
        try:
            profile = _agent_profile_store.update(name, **body)
        except AgentProfileError as exc:
            return JSONResponse(
                {"error": {"code": "validation", "message": str(exc)}},
                status_code=400,
            )
        if profile is None:
            return JSONResponse(
                {
                    "error": {
                        "code": "not_found",
                        "message": f"Agent profile {name!r} not found",
                    }
                },
                status_code=404,
            )
        out = profile.to_dict()
        if warnings:
            out["warnings"] = warnings
        return JSONResponse(out)
    except Exception as exc:
        logger.error("Update agent profile error: %s", exc)
        return JSONResponse(
            {"error": {"code": "update_failed", "message": str(exc)}},
            status_code=500,
        )


@app.delete("/api/v1/agent-profiles/{name}")
async def api_delete_agent_profile(name: str):
    """Delete an agent profile by name.

    Live-reload (oompah-zlz_2-mif): a successful delete fires the store's
    reload callback, queuing a partial orchestrator config swap that
    applies at the next ``_tick()`` quiescent point.
    """
    if _agent_profile_store.delete(name):
        return JSONResponse({"ok": True})
    return JSONResponse(
        {
            "error": {
                "code": "not_found",
                "message": f"Agent profile {name!r} not found",
            }
        },
        status_code=404,
    )


# ----------------------------------------------------------------------
# Role-assignment matrix (oompah-zlz_2-6xc)
#
# A four-row matrix mapping the standard role names (fast/standard/deep/
# default) to (provider, model) pairs in one operation. Each row updates
# the profile of the same name in the AgentProfileStore. Profiles not
# in the matrix (e.g. specialty profiles like merge_conflict) are
# untouched.
#
# Atomicity: all four rows are validated up front. If any single row
# fails (provider unknown, model not in provider's catalog, profile
# missing from the store), the request is rejected with 400 BEFORE any
# profile is mutated. On the unlikely path where validation passes but
# a write fails mid-flight, every previously-mutated profile is
# rolled back to its pre-call snapshot so partial writes are never
# observable.
# ----------------------------------------------------------------------

ROLE_MATRIX_KEYS: tuple[str, ...] = ("fast", "standard", "deep", "default")


def _reload_orchestrator_config_after_profile_change() -> None:
    """Trigger an orchestrator reload so updated profiles take effect.

    Best-effort: when the orchestrator is not yet wired (early boot,
    test contexts), this is a no-op. When a workflow reload itself
    fails, we log a warning but keep the JSON store change persisted —
    the operator can recover by fixing WORKFLOW.md or rolling back.
    """
    if _orchestrator is None:
        return
    try:
        from oompah.config import (
            ServiceConfig,
            WorkflowError,
            load_workflow,
            validate_dispatch_config,
        )

        wf = load_workflow(_orchestrator.workflow_path)
        new_config = ServiceConfig.from_workflow(wf)
        errs = validate_dispatch_config(new_config)
        if errs:
            logger.warning(
                "agent profile reload: workflow validation failed: %s",
                "; ".join(errs),
            )
            return
        _orchestrator.reload_config(new_config, wf.prompt_template)
    except WorkflowError as exc:
        logger.warning("agent profile reload: workflow load failed: %s", exc)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("agent profile reload failed: %s", exc)


def _resolve_candidate_status(
    candidate,  # type: oompah.roles.Candidate
    provider_store: ProviderStore,
) -> tuple[str, str | None]:
    """Compute the (status, message) tuple for a single candidate.

    Used by the new multi-candidate serializer to report per-candidate
    health in GET /api/v1/roles responses.

    Status values match those of :func:`_resolve_role_status`:
    ``"resolved"``, ``"missing_provider"``, ``"missing_model"``,
    ``"empty_catalog"``.
    """
    if not getattr(candidate, "provider_id", None):
        return ("missing_provider", "no provider_id")
    provider = provider_store.get(candidate.provider_id)
    if provider is None:
        return ("missing_provider", f"provider {candidate.provider_id!r} not found")
    catalog = list(provider.models or [])
    is_acp_sdk_managed = getattr(provider, "mode", "api") == "acp" and not catalog
    if is_acp_sdk_managed:
        return ("resolved", None)
    if not catalog:
        return ("empty_catalog", f"provider {provider.name!r} has no models listed")
    if not candidate.model:
        return ("missing_model", f"no model assigned for provider {provider.name!r}")
    if candidate.model not in catalog:
        return (
            "missing_model",
            f"model {candidate.model!r} not in provider {provider.name!r}'s catalog",
        )
    return ("resolved", None)


def _resolve_role_status(
    role,  # type: oompah.roles.Role | None
    provider_store: ProviderStore,
) -> tuple[str, str | None]:
    """Compute the (status, message) tuple for one role-matrix row.

    Operates on a RoleStore Role record (epic oompah-zlz_2-xau7).
    Empty roles report ``unassigned`` rather than the old
    ``missing_profile`` since roles no longer need a same-named profile.

    ``status`` is one of:
      - ``"resolved"`` — role's provider exists and model is in catalog
        (or provider is ACP-mode with an SDK-managed empty catalog).
      - ``"unassigned"`` — no entry in RoleStore for this slot yet.
      - ``"missing_provider"`` — role points at a provider_id that no
        longer exists in ProviderStore.
      - ``"missing_model"`` — provider has a non-empty catalog but the
        role's model is not in it.
      - ``"empty_catalog"`` — non-ACP provider has zero models. The
        operator needs to populate the catalog before this resolves.
    """
    if role is None:
        return ("unassigned", "no provider/model assigned to this role")
    provider = provider_store.get(role.provider_id)
    if provider is None:
        return ("missing_provider", f"provider {role.provider_id!r} not found")
    catalog = list(provider.models or [])
    is_acp_sdk_managed = getattr(provider, "mode", "api") == "acp" and not catalog
    if is_acp_sdk_managed:
        # Empty model is fine — the SDK picks. Non-empty model is also
        # fine, since the catalog isn't authoritative for ACP backends.
        return ("resolved", None)
    if not catalog:
        return ("empty_catalog", f"provider {provider.name!r} has no models listed")
    if not role.model:
        return ("missing_model", f"no model assigned for provider {provider.name!r}")
    if role.model not in catalog:
        return (
            "missing_model",
            f"model {role.model!r} not in provider {provider.name!r}'s catalog",
        )
    return ("resolved", None)


def _resolve_role_matrix_status(
    profile: AgentProfile | None,
    provider_store: ProviderStore,
) -> tuple[str, str | None]:
    """Legacy profile-based status resolver.

    Kept temporarily for back-compat with test fixtures and any callers
    that haven't migrated to ``_resolve_role_status``. New code should
    consult RoleStore directly via the new resolver above.
    """
    if profile is None:
        return ("missing_profile", "no profile of this name exists")
    pid = profile.provider_id
    if not pid:
        return ("missing_provider", "no provider_id set on the profile")
    provider = provider_store.get(pid)
    if provider is None:
        return ("missing_provider", f"provider {pid!r} not found")
    catalog = list(provider.models or [])
    if not catalog:
        return ("empty_catalog", f"provider {provider.name!r} has no models listed")
    chosen = profile.model
    if not chosen:
        if profile.model_role and provider.model_roles.get(profile.model_role):
            chosen = provider.model_roles[profile.model_role]
        else:
            chosen = provider.default_model or catalog[0]
    if chosen not in catalog:
        return (
            "missing_model",
            f"model {chosen!r} not in provider {provider.name!r}'s catalog",
        )
    return ("resolved", None)


def _serialize_role_row(
    role_name: str,
    role,  # type: oompah.roles.Role | None
    provider_store: ProviderStore,
) -> dict:
    """Serialize one role-matrix row for the API response.

    Sourced from RoleStore (epic xau7). Empty roles return a row with
    status=unassigned and no provider/model fields populated.

    New fields (TASK-407.2):
      - ``strategy``: the role's selection strategy ("priority", "round_robin").
      - ``candidates``: ordered list of per-candidate dicts, each with
        ``provider_id``, ``model``, ``status``, and optional
        ``provider_name``/``provider_mode``.

    Backward-compat fields (first-candidate projection):
      - ``provider_id``, ``model``, ``provider_mode``, ``provider_name``
        continue to mirror the first candidate so existing UI / tests
        keep working without modification.
    """
    status, message = _resolve_role_status(role, provider_store)
    out: dict = {"role": role_name, "status": status}
    if message is not None:
        out["message"] = message
    if role is not None:
        # New fields: strategy + per-candidate list.
        out["strategy"] = role.strategy
        candidates_out: list[dict] = []
        for c in role.candidates:
            c_status, _ = _resolve_candidate_status(c, provider_store)
            cand_out: dict = {
                "provider_id": c.provider_id,
                "model": c.model,
                "status": c_status,
            }
            prov = provider_store.get(c.provider_id)
            if prov is not None:
                cand_out["provider_name"] = prov.name
                cand_out["provider_mode"] = prov.mode
            candidates_out.append(cand_out)
        out["candidates"] = candidates_out
        # Backward-compat: mirror the first candidate at the row level.
        out["provider_id"] = role.provider_id
        out["model"] = role.model
        provider = provider_store.get(role.provider_id)
        if provider is not None:
            out["provider_mode"] = provider.mode
            out["provider_name"] = provider.name
    return out


def _serialize_role_matrix_row(
    role: str,
    profile: AgentProfile | None,
    provider_store: ProviderStore,
) -> dict:
    """Legacy profile-based row serializer.

    Kept for back-compat with existing tests; new code should call
    ``_serialize_role_row`` against a RoleStore entry instead.
    """
    status, message = _resolve_role_matrix_status(profile, provider_store)
    out: dict = {"role": role, "status": status}
    if message is not None:
        out["message"] = message
    if profile is not None:
        out["profile_name"] = profile.name
        out["provider_id"] = profile.provider_id
        out["model"] = profile.model
        out["model_role"] = profile.model_role
    if profile is not None and profile.provider_id:
        provider = provider_store.get(profile.provider_id)
        if provider is not None:
            out["provider_mode"] = provider.mode
            out["provider_name"] = provider.name
    return out


@app.get("/api/v1/roles")
async def api_get_roles():
    """Return the current role assignments from RoleStore.

    Returns ``{"rows": [...]}`` in the same shape as the legacy
    role-matrix endpoint. Roles without an entry in RoleStore show up
    with ``status=unassigned``. See epic oompah-zlz_2-xau7.
    """
    rows = [
        _serialize_role_row(role_name, _role_store.get(role_name), _provider_store)
        for role_name in ROLE_MATRIX_KEYS
    ]
    return JSONResponse({"rows": rows})


@app.put("/api/v1/roles")
async def api_put_roles(request: Request):
    """Atomically update the role assignments in RoleStore.

    Supports two body shapes per role:

    **New format** (strategy + candidates list, TASK-407.2)::

        {
          "fast": {
            "strategy": "priority",
            "candidates": [
              {"provider_id": "prov-X", "model": "..."},
              {"provider_id": "prov-Y", "model": "..."}
            ]
          },
          ...
        }

    **Legacy format** (backward compat — single provider/model)::

        {
          "fast":     {"provider_id": "prov-X", "model": "..."},
          "standard": {"provider_id": "prov-X", "model": "..."},
          "deep":     {"provider_id": "prov-Y", "model": "..."},
          "default":  {"provider_id": "prov-Z", "model": "..."}
        }

    Legacy rows are promoted internally to a single-candidate priority
    role so both formats pass through the same validation + storage path.

    All four standard roles are required for v1. Each candidate is
    validated against ProviderStore: provider_id must exist and model
    must be in the provider's catalog (ACP-mode providers with empty
    catalogs accept any model name).

    If any validation fails the entire request is rejected with 400
    and no role is touched. Mid-apply failures roll back to the
    pre-call snapshot via ``RoleStore.snapshot()`` / ``restore()``.
    """
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError) as exc:
        return JSONResponse(
            {"error": {"code": "validation", "message": f"invalid JSON: {exc}"}},
            status_code=400,
        )
    if not isinstance(body, dict):
        return JSONResponse(
            {
                "error": {
                    "code": "validation",
                    "message": "request body must be a JSON object",
                }
            },
            status_code=400,
        )

    # Phase 1: shape validation.
    # Normalize both old (provider_id/model) and new (strategy/candidates)
    # formats into a common dict:  role_name -> (strategy, [Candidate, ...])
    errors: list[str] = []
    # Maps role_name -> (strategy, list-of-Candidate)
    parsed: dict[str, tuple[str, list[Candidate]]] = {}
    for role in ROLE_MATRIX_KEYS:
        if role not in body:
            errors.append(f"missing role {role!r}")
            continue
        row = body[role]
        if not isinstance(row, dict):
            errors.append(f"role {role!r}: row must be a JSON object")
            continue

        if "candidates" in row:
            # --- New format: strategy + candidates list ---
            strategy = row.get("strategy") or DEFAULT_STRATEGY
            if not isinstance(strategy, str):
                errors.append(
                    f"role {role!r}: strategy must be a string"
                )
                continue
            if strategy not in VALID_STRATEGIES:
                errors.append(
                    f"role {role!r}: strategy {strategy!r} is not valid; "
                    f"must be one of: {', '.join(sorted(VALID_STRATEGIES))}"
                )
                continue
            candidates_raw = row.get("candidates")
            if not isinstance(candidates_raw, list) or not candidates_raw:
                errors.append(f"role {role!r}: candidates must be a non-empty list")
                continue
            candidates: list[Candidate] = []
            row_ok = True
            for idx, c in enumerate(candidates_raw):
                if not isinstance(c, dict):
                    errors.append(
                        f"role {role!r}: candidate[{idx}] must be a JSON object"
                    )
                    row_ok = False
                    break
                pid = c.get("provider_id")
                model = c.get("model") or ""
                if not isinstance(pid, str) or not pid:
                    errors.append(
                        f"role {role!r}: candidate[{idx}].provider_id is required"
                    )
                    row_ok = False
                    break
                if not isinstance(model, str):
                    errors.append(
                        f"role {role!r}: candidate[{idx}].model must be a string"
                    )
                    row_ok = False
                    break
                candidates.append(Candidate(provider_id=pid, model=model))
            if not row_ok:
                continue
            parsed[role] = (strategy, candidates)
        else:
            # --- Legacy format: single provider_id + model ---
            pid = row.get("provider_id")
            model = row.get("model") or ""
            if not isinstance(pid, str) or not pid:
                errors.append(f"role {role!r}: provider_id is required")
                continue
            if not isinstance(model, str):
                errors.append(f"role {role!r}: model must be a string")
                continue
            parsed[role] = (DEFAULT_STRATEGY, [Candidate(provider_id=pid, model=model)])

    if errors:
        return JSONResponse(
            {"error": {"code": "validation", "message": "; ".join(errors)}},
            status_code=400,
        )

    # Phase 2: cross-store validation.
    # Delegate each candidate to RoleStore._validate() by calling
    # set_candidates() in a dry-run fashion (we use _provider_store
    # directly to keep the same validation logic).
    for role, (strategy, candidates) in parsed.items():
        seen_pairs: set[tuple[str, str]] = set()
        for idx, cand in enumerate(candidates):
            pair = (cand.provider_id, cand.model)
            if pair in seen_pairs:
                errors.append(
                    f"role {role!r}: duplicate candidate at index {idx}"
                )
                break
            seen_pairs.add(pair)
            provider = _provider_store.get(cand.provider_id)
            if provider is None:
                errors.append(
                    f"role {role!r}: provider_id {cand.provider_id!r} not found"
                )
                break
            catalog = list(provider.models or [])
            is_acp_sdk_managed = provider.mode == "acp" and not catalog
            if not cand.model and not is_acp_sdk_managed:
                errors.append(f"role {role!r}: model is required")
                break
            if catalog and cand.model and cand.model not in catalog:
                errors.append(
                    f"role {role!r}: model {cand.model!r} not in provider "
                    f"{provider.name!r}'s catalog (have: "
                    f"{', '.join(catalog)})"
                )
                break

    if errors:
        return JSONResponse(
            {"error": {"code": "validation", "message": "; ".join(errors)}},
            status_code=400,
        )

    # Phase 3: snapshot + apply + rollback-on-failure.
    snapshot = _role_store.snapshot()
    try:
        for role, (strategy, candidates) in parsed.items():
            _role_store.set_candidates(role, strategy, candidates)
    except (RoleError, Exception) as exc:  # noqa: BLE001 — any error → roll back
        try:
            _role_store.restore(snapshot)
        except Exception as rollback_exc:  # noqa: BLE001
            logger.error("role-store rollback failed: %s", rollback_exc)
        logger.error("role update failed: %s", exc)
        return JSONResponse(
            {
                "error": {
                    "code": "update_failed",
                    "message": f"role update failed: {exc}",
                }
            },
            status_code=500,
        )

    rows = [
        _serialize_role_row(role_name, _role_store.get(role_name), _provider_store)
        for role_name in ROLE_MATRIX_KEYS
    ]
    return JSONResponse({"rows": rows})


@app.get("/api/v1/agent-profiles/role-matrix")
async def api_get_role_matrix():
    """Legacy alias for ``GET /api/v1/roles``.

    Pre-xau7 UIs called this endpoint; preserved for one release so
    in-flight dashboards keep working. New code should call
    ``/api/v1/roles`` directly.
    """
    return await api_get_roles()


@app.put("/api/v1/agent-profiles/role-matrix")
async def api_put_role_matrix(request: Request):
    """Legacy alias for ``PUT /api/v1/roles``.

    See ``api_put_roles`` for the body shape and semantics. Unlike the
    pre-xau7 implementation, this no longer mutates AgentProfile
    records — the assignments live in RoleStore.
    """
    return await api_put_roles(request)


@app.post("/api/v1/providers/fetch-models")
async def api_fetch_models(req: Request):
    """Fetch the model catalog for a provider.

    Branches on ``mode`` (oompah-zlz_2-zvm0 §3):

    * ``mode == "acp"`` — dispatch to the selected ACP backend. If the
      backend exposes a ``fetch_models()`` hook, call it. Otherwise
      return an empty list plus a human-readable note ("Claude SDK
      manages model selection via subscription.") so the dashboard
      can surface it inline instead of failing with a 404 from a
      meaningless HTTP probe.
    * ``mode == "api"`` — the historical OpenAI-compatible
      ``<base_url>/models`` path. Unchanged.
    """
    import asyncio, urllib.request, ssl

    try:
        data = await req.json()
    except (json.JSONDecodeError, ValueError) as exc:
        return JSONResponse(
            {
                "error": {
                    "code": "validation",
                    "message": f"Invalid JSON: {exc}",
                }
            },
            status_code=400,
        )
    if not isinstance(data, dict):
        return JSONResponse(
            {
                "error": {
                    "code": "validation",
                    "message": "request body must be a JSON object",
                }
            },
            status_code=400,
        )
    raw_mode = str(data.get("mode") or "").lower()
    backend_name = (data.get("backend") or "claude").strip() or "claude"

    # ACP-aware branch: dispatch through the registered backend.
    if raw_mode == "acp":
        try:
            from oompah.acp_backends import BACKENDS, get_backend

            backend_cls = get_backend(backend_name)
            if backend_cls is None:
                return JSONResponse(
                    {
                        "models": [],
                        "note": (
                            f"Unknown ACP backend: {backend_name!r}. "
                            f"Registered backends: {sorted(BACKENDS)}."
                        ),
                        "supports_model_selection": False,
                    },
                    status_code=200,
                )
            backend = backend_cls()
            # Honour an optional fetch_models() hook on the backend.
            # Today's ClaudeAcpBackend has none — the SDK manages
            # selection via subscription, so we return the canonical
            # subscription-managed note.
            fetch_hook = getattr(backend, "fetch_models", None)
            if callable(fetch_hook):
                try:
                    models = await asyncio.to_thread(fetch_hook)
                    if not isinstance(models, list):
                        models = []
                    return JSONResponse(
                        {
                            "models": sorted(str(m) for m in models),
                            "supports_model_selection": True,
                        }
                    )
                except Exception as exc:
                    return JSONResponse(
                        {"models": [], "error": str(exc)},
                        status_code=502,
                    )
            # No catalog hook — Claude SDK et al. The dashboard
            # disables the Fetch Models button and surfaces this note.
            note = "Claude SDK manages model selection via subscription."
            if backend_name != "claude":
                note = f"Backend {backend_name!r} does not expose a model catalog."
            return JSONResponse(
                {
                    "models": [],
                    "note": note,
                    "supports_model_selection": False,
                }
            )
        except Exception as exc:
            return JSONResponse(
                {"models": [], "error": f"ACP fetch failed: {exc}"},
                status_code=502,
            )

    # OpenAI-compatible path (legacy behaviour).
    base_url = (data.get("base_url") or "").rstrip("/")
    api_key = data.get("api_key", "")
    provider_id = data.get("provider_id", "")
    if not api_key and provider_id:
        existing = _provider_store.get(provider_id)
        if existing:
            api_key = existing.api_key or ""
    if not base_url:
        return JSONResponse({"error": "base_url required"}, status_code=400)

    def _fetch():
        url = f"{base_url}/models"
        rq = urllib.request.Request(url)
        rq.add_header("User-Agent", "oompah/0.1")
        if api_key:
            rq.add_header("Authorization", f"Bearer {api_key}")
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(rq, timeout=10, context=ctx) as resp:
            return json.loads(resp.read().decode())

    try:
        body = await asyncio.to_thread(_fetch)
        models = []
        if isinstance(body, dict) and "data" in body:
            models = sorted([m["id"] for m in body["data"] if "id" in m])
        elif isinstance(body, list):
            models = sorted([m["id"] if isinstance(m, dict) else str(m) for m in body])
        return JSONResponse({"models": models})
    except Exception as e:
        return JSONResponse({"error": str(e), "models": []}, status_code=502)


# Cache of OpenRouter's model catalog (id → context_length). Refreshed
# at most once per process; the catalog is several hundred entries and
# rarely changes within a single oompah session.
_openrouter_context_cache: dict[str, int] | None = None


def _fetch_openrouter_contexts() -> dict[str, int]:
    """Fetch and cache OpenRouter's model catalog as {model_id: context_length}.

    Used as the fallback path for context-size auto-population when a
    provider's /v1/models response doesn't expose max_model_len. Returns
    an empty dict on error (caller treats as "no fallback available").
    """
    global _openrouter_context_cache
    if _openrouter_context_cache is not None:
        return _openrouter_context_cache
    import urllib.request, ssl

    try:
        rq = urllib.request.Request("https://openrouter.ai/api/v1/models")
        rq.add_header("User-Agent", "oompah/0.1")
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(rq, timeout=10, context=ctx) as resp:
            body = json.loads(resp.read().decode())
        out: dict[str, int] = {}
        for m in body.get("data") or []:
            mid = m.get("id")
            ctx_len = m.get("context_length")
            if mid and isinstance(ctx_len, int) and ctx_len > 0:
                out[mid] = ctx_len
        _openrouter_context_cache = out
        return out
    except Exception:
        _openrouter_context_cache = {}
        return {}


def _normalize_model_for_openrouter(model_id: str) -> list[str]:
    """Return candidate keys to look up in OpenRouter's catalog.

    Provider-specific model names sometimes differ from OpenRouter's
    `vendor/model` namespace. Try a few normalizations: exact id,
    bare model name (last path segment), and the bare name with common
    vendor prefixes.
    """
    candidates = [model_id]
    # Strip vendor prefix variants: "azure/anthropic/claude-sonnet-4-6" → also try "anthropic/claude-sonnet-4-6"
    parts = model_id.split("/")
    if len(parts) >= 2:
        candidates.append("/".join(parts[-2:]))
    if len(parts) >= 1:
        candidates.append(parts[-1])
    # de-dup, preserve order
    seen: set[str] = set()
    out: list[str] = []
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _bare_model_key(name: str) -> str:
    """Reduce a model id (full or bare) to a comparable key.

    Strips vendor path prefix, lowercases, and normalizes dash/dot
    variations in version numbers (``claude-sonnet-4-6`` →
    ``claude.sonnet.4.6``). Used for fuzzy matching against
    OpenRouter's catalog where the bare-name conventions diverge from
    the upstream provider's (e.g., we use ``claude-sonnet-4-6``,
    OpenRouter has ``anthropic/claude-sonnet-4.6``).
    """
    bare = name.split("/")[-1]
    # Drop trailing :free or similar tags
    bare = bare.split(":")[0]
    return bare.replace("-", ".").lower()


def _lookup_openrouter(model_id: str, openrouter: dict[str, int]) -> int | None:
    """Best-effort match of a provider's model_id against OpenRouter's catalog.

    Two passes:
      1. Exact-key match against any path-stripped variant of model_id.
      2. Fuzzy match: scan the catalog for any entry whose bare-name
         (vendor stripped, dash↔dot normalized, lower-cased) equals
         the target's bare-name. First match wins.

    Returns the catalog entry's context_length, or None if no match.
    """
    # Pass 1: exact-key candidates
    for key in _normalize_model_for_openrouter(model_id):
        if key in openrouter:
            return openrouter[key]
    # Pass 2: fuzzy bare-name match
    target = _bare_model_key(model_id)
    for or_id, ctx in openrouter.items():
        if _bare_model_key(or_id) == target:
            return ctx
    return None


@app.post("/api/v1/providers/{provider_id}/auto-populate-contexts")
async def api_auto_populate_contexts(provider_id: str):
    """Auto-populate `model_contexts` for a provider.

    Strategy per model:
      1. Fetch the provider's own /v1/models endpoint and look for
         `max_model_len` (vLLM-served openai-compatible endpoints
         include this field per model entry).
      2. On miss, fall back to OpenRouter's /api/v1/models catalog
         (https://openrouter.ai/api/v1/models) and match by
         normalized id.

    Existing entries in `model_contexts` are preserved; this endpoint
    only fills in missing entries (won't overwrite operator-set values).

    Returns a summary including which models were resolved by each path
    and which couldn't be resolved at all (operator must set those by
    hand).
    """
    import asyncio, urllib.request, ssl

    provider = _provider_store.get(provider_id)
    if not provider:
        return JSONResponse(
            {
                "error": {
                    "code": "not_found",
                    "message": f"Provider {provider_id} not found",
                }
            },
            status_code=404,
        )

    base_url = (provider.base_url or "").rstrip("/")
    api_key = provider.api_key or ""

    # Step 1: pull /v1/models with full record (not just IDs) so we can read max_model_len
    upstream_error: str | None = None

    def _fetch_models() -> list[dict]:
        nonlocal upstream_error
        if not base_url:
            upstream_error = "no base_url on provider"
            return []
        url = f"{base_url}/models"
        rq = urllib.request.Request(url)
        rq.add_header("User-Agent", "oompah/0.1")
        if api_key:
            rq.add_header("Authorization", f"Bearer {api_key}")
        ctx = ssl.create_default_context()
        try:
            with urllib.request.urlopen(rq, timeout=10, context=ctx) as resp:
                body = json.loads(resp.read().decode())
        except Exception as exc:
            upstream_error = f"{type(exc).__name__}: {exc}"
            logger.warning("auto-populate: upstream fetch %s failed: %s", url, exc)
            return []
        if isinstance(body, dict) and isinstance(body.get("data"), list):
            return [m for m in body["data"] if isinstance(m, dict)]
        if isinstance(body, list):
            return [m for m in body if isinstance(m, dict)]
        return []

    upstream_models = await asyncio.to_thread(_fetch_models)
    upstream_by_id = {m.get("id"): m for m in upstream_models if m.get("id")}
    logger.info(
        "auto-populate %s: upstream fetched %d model(s); error=%s",
        provider_id,
        len(upstream_models),
        upstream_error,
    )

    openrouter = await asyncio.to_thread(_fetch_openrouter_contexts)

    resolved_via_upstream: list[str] = []
    resolved_via_openrouter: list[str] = []
    unresolved: list[str] = []
    preserved: list[str] = []

    new_contexts: dict[str, int] = dict(provider.model_contexts or {})

    for model_id in provider.models or []:
        if model_id in new_contexts and new_contexts[model_id] > 0:
            preserved.append(model_id)
            continue

        # Step 1: upstream max_model_len
        m = upstream_by_id.get(model_id) or {}
        upstream_ctx = m.get("max_model_len")
        if isinstance(upstream_ctx, int) and upstream_ctx > 0:
            new_contexts[model_id] = upstream_ctx
            resolved_via_upstream.append(model_id)
            continue

        # Step 2: openrouter (exact + fuzzy bare-name match)
        found = _lookup_openrouter(model_id, openrouter)
        if found:
            new_contexts[model_id] = found
            resolved_via_openrouter.append(model_id)
            continue

        unresolved.append(model_id)

    # Persist
    if new_contexts != (provider.model_contexts or {}):
        _provider_store.update(provider_id, model_contexts=new_contexts)

    return JSONResponse(
        {
            "ok": True,
            "provider_id": provider_id,
            "model_contexts": new_contexts,
            "resolved_via_upstream": resolved_via_upstream,
            "resolved_via_openrouter": resolved_via_openrouter,
            "unresolved": unresolved,
            "preserved": preserved,
            "diagnostics": {
                "upstream_models_fetched": len(upstream_models),
                "upstream_error": upstream_error,
                "openrouter_catalog_size": len(openrouter),
            },
        }
    )


# --- Project API ---


@app.get("/api/v1/projects")
async def api_list_projects():
    """List all configured projects."""
    orch = _get_orchestrator()
    return JSONResponse([p.to_safe_dict() for p in orch.project_store.list_all()])


@app.post("/api/v1/projects")
async def api_create_project(request: Request):
    """Register a new project (git repo with tracker-managed tasks)."""
    try:
        orch = _get_orchestrator()
        try:
            body = await request.json()
        except (json.JSONDecodeError, ValueError) as exc:
            return JSONResponse(
                {
                    "error": {
                        "code": "validation",
                        "message": f"Invalid JSON: {exc}",
                    }
                },
                status_code=400,
            )
        if not isinstance(body, dict):
            return JSONResponse(
                {
                    "error": {
                        "code": "validation",
                        "message": "request body must be a JSON object",
                    }
                },
                status_code=400,
            )
        repo_url = body.get("repo_url", "").strip()
        if not repo_url:
            return JSONResponse(
                {"error": {"code": "validation", "message": "repo_url is required"}},
                status_code=400,
            )
        name = body.get("name", "").strip() or None  # None = auto from URL
        branch = body.get("branch", "main").strip()
        branches = body.get("branches")
        default_branch = body.get("default_branch", "").strip() or None
        git_user_name = body.get("git_user_name", "").strip() or None
        git_user_email = body.get("git_user_email", "").strip() or None
        access_token = (body.get("access_token") or "").strip() or None
        # Per-project tracker configuration
        tracker_kind = (body.get("tracker_kind") or "").strip() or None
        tracker_owner = (body.get("tracker_owner") or "").strip() or None
        tracker_repo = (body.get("tracker_repo") or "").strip() or None
        github_project_node_id = (body.get("github_project_node_id") or "").strip() or None
        legacy_backlog_enabled = bool(body.get("legacy_backlog_enabled", False))
        legacy_backlog_dispatch = bool(body.get("legacy_backlog_dispatch", False))
        project = orch.project_store.create(
            repo_url=repo_url,
            name=name,
            branch=branch,
            branches=branches,
            default_branch=default_branch,
            git_user_name=git_user_name,
            git_user_email=git_user_email,
            access_token=access_token,
            tracker_kind=tracker_kind,
            tracker_owner=tracker_owner,
            tracker_repo=tracker_repo,
            github_project_node_id=github_project_node_id,
            legacy_backlog_enabled=legacy_backlog_enabled,
            legacy_backlog_dispatch=legacy_backlog_dispatch,
        )
        # Sync log watchers in case the new project has a log_path
        if _log_watcher_manager:
            _log_watcher_manager.sync_watchers(orch.project_store.list_all())
        # Install Backlog webhook hook for the new project (best-effort).
        _install_backlog_hook_for_project(project)
        return JSONResponse(project.to_safe_dict(), status_code=201)
    except ProjectError as exc:
        return JSONResponse(
            {"error": {"code": "validation", "message": str(exc)}},
            status_code=400,
        )
    except Exception as exc:
        logger.error("Create project error: %s", exc)
        return JSONResponse(
            {"error": {"code": "create_failed", "message": str(exc)}},
            status_code=500,
        )


@app.get("/api/v1/projects/{project_id}")
async def api_get_project(project_id: str):
    """Return a single project by ID."""
    orch = _get_orchestrator()
    project = orch.project_store.get(project_id)
    if not project:
        return JSONResponse(
            {
                "error": {
                    "code": "not_found",
                    "message": f"Project {project_id} not found",
                }
            },
            status_code=404,
        )
    return JSONResponse(project.to_safe_dict())


@app.patch("/api/v1/projects/{project_id}")
async def api_update_project(project_id: str, request: Request):
    """Update a project's mutable fields."""
    try:
        orch = _get_orchestrator()
        try:
            body = await request.json()
        except (json.JSONDecodeError, ValueError) as exc:
            return JSONResponse(
                {
                    "error": {
                        "code": "validation",
                        "message": f"Invalid JSON: {exc}",
                    }
                },
                status_code=400,
            )
        if not isinstance(body, dict):
            return JSONResponse(
                {
                    "error": {
                        "code": "validation",
                        "message": "request body must be a JSON object",
                    }
                },
                status_code=400,
            )
        fields = {}
        for key in (
            "name",
            "repo_url",
            "branch",
            "branches",
            "default_branch",
            "git_user_name",
            "git_user_email",
            "log_path",
            "webhook_secret",
            "access_token",
        ):
            if key in body:
                fields[key] = body[key]
        if "yolo" in body:
            fields["yolo"] = bool(body["yolo"])
        if "max_in_flight_prs" in body:
            raw = body["max_in_flight_prs"]
            try:
                val = int(raw)
            except (TypeError, ValueError):
                return JSONResponse(
                    {
                        "error": {
                            "code": "validation",
                            "message": "max_in_flight_prs must be a positive integer",
                        }
                    },
                    status_code=400,
                )
            if val < 1:
                return JSONResponse(
                    {
                        "error": {
                            "code": "validation",
                            "message": "max_in_flight_prs must be >= 1",
                        }
                    },
                    status_code=400,
                )
            fields["max_in_flight_prs"] = val
        if "merge_queue_enabled" in body:
            fields["merge_queue_enabled"] = bool(body["merge_queue_enabled"])
        if "paused" in body:
            fields["paused"] = bool(body["paused"])
        # test_command / test_command_full: accept string or null. ProjectStore
        # normalizes whitespace and treats empty strings as None.
        for key in ("test_command", "test_command_full"):
            if key in body:
                val = body[key]
                if val is not None and not isinstance(val, str):
                    return JSONResponse(
                        {
                            "error": {
                                "code": "validation",
                                "message": f"{key} must be a string or null",
                            }
                        },
                        status_code=400,
                    )
                fields[key] = val
        if "test_skip_paths" in body:
            val = body["test_skip_paths"]
            if val is None:
                fields["test_skip_paths"] = []
            elif isinstance(val, list) and all(isinstance(x, str) for x in val):
                fields["test_skip_paths"] = val
            else:
                return JSONResponse(
                    {
                        "error": {
                            "code": "validation",
                            "message": "test_skip_paths must be a list of strings or null",
                        }
                    },
                    status_code=400,
                )
        if "epic_strategy" in body:
            val = body["epic_strategy"]
            if val is None:
                fields["epic_strategy"] = "flat"
            elif isinstance(val, str) and val.strip().lower() in (
                "flat",
                "stacked",
                "shared",
            ):
                fields["epic_strategy"] = val.strip().lower()
            else:
                return JSONResponse(
                    {
                        "error": {
                            "code": "validation",
                            "message": "epic_strategy must be one of: flat, stacked, shared",
                        }
                    },
                    status_code=400,
                )
        if "require_epic_for_tasks" in body:
            val = body["require_epic_for_tasks"]
            if isinstance(val, bool):
                fields["require_epic_for_tasks"] = val
            else:
                return JSONResponse(
                    {
                        "error": {
                            "code": "validation",
                            "message": "require_epic_for_tasks must be a boolean",
                        }
                    },
                    status_code=400,
                )
        if "provider_whitelist" in body:
            val = body["provider_whitelist"]
            if val is None:
                fields["provider_whitelist"] = []
            elif isinstance(val, list) and all(isinstance(x, str) for x in val):
                fields["provider_whitelist"] = val
            else:
                return JSONResponse(
                    {
                        "error": {
                            "code": "validation",
                            "message": "provider_whitelist must be a list of strings or null",
                        }
                    },
                    status_code=400,
                )
        # Per-project tracker configuration (TASK-459.3)
        for key in ("tracker_kind", "tracker_owner", "tracker_repo", "github_project_node_id"):
            if key in body:
                val = body[key]
                if val is not None and not isinstance(val, str):
                    return JSONResponse(
                        {
                            "error": {
                                "code": "validation",
                                "message": f"{key} must be a string or null",
                            }
                        },
                        status_code=400,
                    )
                fields[key] = val
        for key in ("legacy_backlog_enabled", "legacy_backlog_dispatch"):
            if key in body:
                fields[key] = bool(body[key])
        if "tracker_cutover_at" in body:
            val = body["tracker_cutover_at"]
            if val is None:
                fields["tracker_cutover_at"] = None
            elif isinstance(val, str):
                fields["tracker_cutover_at"] = val  # ProjectStore.update() parses it
            else:
                return JSONResponse(
                    {
                        "error": {
                            "code": "validation",
                            "message": "tracker_cutover_at must be an ISO 8601 datetime string or null",
                        }
                    },
                    status_code=400,
                )
        project = orch.project_store.update(project_id, **fields)
        if not project:
            return JSONResponse(
                {
                    "error": {
                        "code": "not_found",
                        "message": f"Project {project_id} not found",
                    }
                },
                status_code=404,
            )
        # Sync log watchers when project settings change (log_path may have been added/changed/removed)
        if _log_watcher_manager:
            _log_watcher_manager.sync_watchers(orch.project_store.list_all())
        # Re-install Backlog webhook hook in case webhook_secret or URL changed.
        _install_backlog_hook_for_project(project)
        return JSONResponse(project.to_safe_dict())
    except ProjectError as exc:
        return JSONResponse(
            {"error": {"code": "validation", "message": str(exc)}},
            status_code=400,
        )
    except Exception as exc:
        logger.error("Update project error: %s", exc)
        return JSONResponse(
            {"error": {"code": "update_failed", "message": str(exc)}},
            status_code=500,
        )


@app.delete("/api/v1/projects/{project_id}")
async def api_delete_project(project_id: str):
    """Delete a project."""
    orch = _get_orchestrator()
    if orch.project_store.delete(project_id):
        # Stop any log file watcher for this project
        if _log_watcher_manager:
            _log_watcher_manager.sync_watchers(orch.project_store.list_all())
        return JSONResponse({"ok": True})
    return JSONResponse(
        {"error": {"code": "not_found", "message": f"Project {project_id} not found"}},
        status_code=404,
    )


@app.post("/api/v1/projects/{project_id}/pause")
async def api_project_pause(project_id: str):
    """Pause dispatch for a single project.

    Mirrors /api/v1/orchestrator/pause but scoped to one project.
    The orchestrator's _should_dispatch will reject every issue in
    this project with reason "project_paused" until /resume is called.
    Composes with the global pause: a request is dispatchable only
    if neither the global nor the project's pause is set.
    """
    try:
        orch = _get_orchestrator()
        project = orch.project_store.update(project_id, paused=True)
        if not project:
            return JSONResponse(
                {
                    "error": {
                        "code": "not_found",
                        "message": f"Project {project_id} not found",
                    }
                },
                status_code=404,
            )
        return JSONResponse({"ok": True, "id": project_id, "paused": True})
    except ProjectError as exc:
        return JSONResponse(
            {"error": {"code": "validation", "message": str(exc)}},
            status_code=400,
        )
    except Exception as exc:
        logger.error("Project pause error: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/v1/projects/{project_id}/resume")
async def api_project_resume(project_id: str):
    """Resume dispatch for a single project (clear the per-project pause)."""
    try:
        orch = _get_orchestrator()
        project = orch.project_store.update(project_id, paused=False)
        if not project:
            return JSONResponse(
                {
                    "error": {
                        "code": "not_found",
                        "message": f"Project {project_id} not found",
                    }
                },
                status_code=404,
            )
        return JSONResponse({"ok": True, "id": project_id, "paused": False})
    except ProjectError as exc:
        return JSONResponse(
            {"error": {"code": "validation", "message": str(exc)}},
            status_code=400,
        )
    except Exception as exc:
        logger.error("Project resume error: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/v1/projects/{project_id}/worktrees")
async def api_list_worktrees(project_id: str):
    """List active worktrees for a project."""
    try:
        orch = _get_orchestrator()
        paths = orch.project_store.list_worktrees(project_id)
        return JSONResponse({"project_id": project_id, "worktrees": paths})
    except ProjectError as exc:
        return JSONResponse(
            {"error": {"code": "not_found", "message": str(exc)}},
            status_code=404,
        )


@app.get("/api/v1/foci")
async def api_list_foci():
    """List all foci (user + builtins)."""
    foci = await asyncio.to_thread(load_foci)
    return JSONResponse([f.to_dict() for f in foci])


@app.post("/api/v1/foci")
async def api_create_focus(request: Request):
    """Add or update a user focus."""
    try:
        try:
            body = await request.json()
        except (json.JSONDecodeError, ValueError) as exc:
            return JSONResponse(
                {
                    "error": {
                        "code": "validation",
                        "message": f"Invalid JSON: {exc}",
                    }
                },
                status_code=400,
            )
        if not isinstance(body, dict):
            return JSONResponse(
                {
                    "error": {
                        "code": "validation",
                        "message": "request body must be a JSON object",
                    }
                },
                status_code=400,
            )
        new_focus = Focus.from_dict(body)
        if not new_focus.name:
            return JSONResponse(
                {"error": {"code": "validation", "message": "name is required"}},
                status_code=400,
            )
        import os, json as _json

        user_path = ".oompah/foci.json"

        def _save_focus() -> None:
            """Load user foci, replace if same name exists, then save. Runs in thread."""
            existing_user: list[Focus] = []
            if os.path.exists(user_path):
                try:
                    with open(user_path, "r") as fp:
                        existing_user = [Focus.from_dict(d) for d in _json.load(fp)]
                except Exception:
                    pass
            existing_user = [f for f in existing_user if f.name != new_focus.name]
            existing_user.append(new_focus)
            save_foci(existing_user)

        await asyncio.to_thread(_save_focus)
        return JSONResponse(new_focus.to_dict(), status_code=201)
    except Exception as exc:
        logger.error("Create focus error: %s", exc)
        return JSONResponse(
            {"error": {"code": "create_failed", "message": str(exc)}},
            status_code=500,
        )


@app.delete("/api/v1/foci/{name}")
async def api_delete_focus(name: str):
    """Delete a user focus by name. Cannot delete builtins."""
    import os, json as _json

    user_path = ".oompah/foci.json"

    def _delete_focus() -> bool:
        """Load user foci, remove by name, save. Returns True if found. Runs in thread."""
        if not os.path.exists(user_path):
            return False
        try:
            with open(user_path, "r") as fp:
                existing = [Focus.from_dict(d) for d in _json.load(fp)]
        except Exception:
            existing = []
        new_list = [f for f in existing if f.name != name]
        if len(new_list) == len(existing):
            return False
        save_foci(new_list)
        return True

    found = await asyncio.to_thread(_delete_focus)
    if not found:
        return JSONResponse(
            {
                "error": {
                    "code": "not_found",
                    "message": f"Focus '{name}' not found in user foci",
                }
            },
            status_code=404,
        )
    return JSONResponse({"deleted": name})


@app.patch("/api/v1/foci/{name}")
async def api_update_focus(name: str, request: Request):
    """Update a focus (status, fields). For builtins, creates a user override."""
    import os, json as _json

    user_path = ".oompah/foci.json"
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError) as exc:
        return JSONResponse(
            {
                "error": {
                    "code": "validation",
                    "message": f"Invalid JSON: {exc}",
                }
            },
            status_code=400,
        )
    new_status = body.get("status")
    if not isinstance(body, dict):
        return JSONResponse(
            {
                "error": {
                    "code": "validation",
                    "message": "request body must be a JSON object",
                }
            },
            status_code=400,
        )
    if new_status and new_status not in ("active", "inactive", "proposed"):
        return JSONResponse(
            {
                "error": {
                    "code": "validation",
                    "message": "status must be active, inactive, or proposed",
                }
            },
            status_code=400,
        )

    def _load_update_save() -> Focus | None:
        """Load foci, apply updates, save. Returns updated Focus or None. Runs in thread."""
        # Load user foci
        existing: list[Focus] = []
        if os.path.exists(user_path):
            try:
                with open(user_path, "r") as fp:
                    existing = [Focus.from_dict(d) for d in _json.load(fp)]
            except Exception:
                pass

        # Find in user foci first
        _found: Focus | None = None
        for f in existing:
            if f.name == name:
                _found = f
                break

        if not _found:
            # Check builtins — create a user override
            for b in BUILTIN_FOCI:
                if b.name == name:
                    _found = Focus.from_dict(b.to_dict())
                    existing.append(_found)
                    break

        if not _found:
            return None

        # Apply updates
        for key in ("status", "role", "description"):
            if key in body:
                setattr(_found, key, body[key])
        for key in ("must_do", "must_not_do", "keywords", "issue_types", "labels"):
            if key in body:
                setattr(_found, key, body[key])
        if "priority" in body:
            try:
                _found.priority = int(body["priority"])
            except (ValueError, TypeError):
                pass
        # Optional model overrides — empty string clears the override.
        for key in ("model_role", "model", "provider_id"):
            if key in body:
                v = body[key]
                if v is None or (isinstance(v, str) and not v.strip()):
                    setattr(_found, key, None)
                else:
                    setattr(_found, key, str(v).strip())
        if "allow_image_output" in body:
            _found.allow_image_output = bool(body["allow_image_output"])

        save_foci(existing, user_path)
        return _found

    found = await asyncio.to_thread(_load_update_save)
    if found is None:
        return JSONResponse(
            {"error": {"code": "not_found", "message": f"Focus '{name}' not found"}},
            status_code=404,
        )
    return JSONResponse(found.to_dict())


@app.get("/api/v1/foci/suggestions")
async def api_list_focus_suggestions():
    """List focus suggestions generated by the analyzer."""
    suggestions = await asyncio.to_thread(load_suggestions)
    return JSONResponse([s.to_dict() for s in suggestions])


@app.patch("/api/v1/foci/suggestions/{name}")
async def api_update_focus_suggestion(name: str, request: Request):
    """Update a suggestion's status (accepted, dismissed)."""
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError) as exc:
        return JSONResponse(
            {
                "error": {
                    "code": "validation",
                    "message": f"Invalid JSON: {exc}",
                }
            },
            status_code=400,
        )
    if not isinstance(body, dict):
        return JSONResponse(
            {
                "error": {
                    "code": "validation",
                    "message": "request body must be a JSON object",
                }
            },
            status_code=400,
        )
    status = body.get("status", "")
    if status not in ("accepted", "dismissed"):
        return JSONResponse(
            {
                "error": {
                    "code": "validation",
                    "message": "status must be 'accepted' or 'dismissed'",
                }
            },
            status_code=400,
        )
    found = await asyncio.to_thread(update_suggestion_status, name, status)
    if found:
        return JSONResponse({"name": name, "status": status})
    return JSONResponse(
        {"error": {"code": "not_found", "message": f"Suggestion '{name}' not found"}},
        status_code=404,
    )


@app.get("/api/v1/budget")
async def api_budget():
    """Return current budget and cost tracking info."""
    try:
        orch = _get_orchestrator()
        snapshot = orch.get_snapshot()
        return JSONResponse(
            {
                "budget": snapshot["budget"],
                "cost_by_profile": snapshot["cost_by_profile"],
                "agent_profiles": snapshot["agent_profiles"],
                # "json" (default) means the dashboard's Agent Profiles
                # section can add/edit/delete via /api/v1/agent-profiles.
                # "workflow" means OOMPAH_AGENT_PROFILES_SOURCE=workflow
                # is set and the UI should be read-only. See
                # docs/agent-profiles.md.
                "agent_profiles_source": snapshot.get(
                    "agent_profiles_source",
                    "json",
                ),
            }
        )
    except Exception as exc:
        logger.error("Budget API error: %s", exc)
        return JSONResponse(
            {"error": {"code": "unavailable", "message": str(exc)}},
            status_code=503,
        )


@app.get("/api/v1/reviews")
async def api_list_reviews():
    """List all open reviews across all projects."""
    try:
        orch = _get_orchestrator()
        projects = orch.project_store.list_all()
        cached = _api_cache.get("reviews:all")
        if cached is not None:
            return JSONResponse(cached)
        # Index projects by id for fast lookup in the loop below.
        _project_by_id = {p.id: p for p in projects}
        reviews, reviews_by_project, successful_project_ids = _fetch_open_reviews_for_api(
            projects
        )
        # Enrich reviews with agent status
        active_branches = {
            entry.issue.identifier
            for entry in orch.state.running.values()
            if entry.issue
        }
        # oompah-zlz_2-btf.2: surface YOLO repo-config errors on each PR
        # so the dashboard / per-PR detail can show why YOLO can't merge.
        repo_config_errors = getattr(orch, "_yolo_repo_config_errors", {}) or {}
        # oompah-zlz_2-rxwe.2: surface churn-magnet flag on PRs so the
        # dashboard can render high-risk warnings. The flag is populated
        # by the orchestrator during YOLO review sync; we also re-check
        # here for non-YOLO projects or reviews that haven't been synced
        # yet this tick.
        try:
            from oompah.churn_magnet import get_store as _get_churn_store
            _cm_store = _get_churn_store()
        except Exception:
            _cm_store = None
        for item in reviews:
            r = item.get("review", {})
            item["agent_active"] = r.get("source_branch", "") in active_branches
            err = repo_config_errors.get(
                (item.get("project_id", ""), str(r.get("id", "")))
            )
            if err:
                item["repo_config_error"] = err.get("msg", "")
                item["repo_config_error_fingerprint"] = err.get("fingerprint", "")
            # Propagate churn_magnet flag from the review object to the
            # top-level item so the dashboard can access it easily.
            if r.get("churn_magnet"):
                item["churn_magnet"] = True
                item["churn_magnet_files"] = r.get("churn_magnet_files", [])
            elif _cm_store is not None:
                # For reviews not yet checked by YOLO (non-YOLO projects
                # or first tick), do the check here.
                pid = item.get("project_id")
                if pid:
                    try:
                        top_files = set(
                            fp for fp, _ in _cm_store.get_top_files(pid)
                        )
                        if top_files and r.get("files"):
                            overlap = set(r["files"]) & top_files
                            if overlap:
                                item["churn_magnet"] = True
                                item["churn_magnet_files"] = sorted(overlap)
                    except Exception:
                        pass
            # Surface gate config for each PR (oompah-zlz_2-rxwe.3).
            # Build a quick project lookup so we don't call list_all() again.
            pid = item.get("project_id", "")
            proj = _project_by_id.get(pid) if _project_by_id else None
            if proj:
                item["churn_magnet_gate_enabled"] = bool(
                    getattr(proj, "churn_magnet_gate_enabled", False)
                )
                item["churn_magnet_top_n"] = max(
                    1, int(getattr(proj, "churn_magnet_top_n", 10))
                )
                # gate_blocked: true when the gate would fire for this PR.
                # Combines project-level gate-on switch + PR-level flags.
                if (
                    item.get("churn_magnet_gate_enabled")
                    and item.get("churn_magnet")
                    and r.get("needs_rebase", False)
                ):
                    item["gate_blocked"] = True
        _sync_orchestrator_review_cache(
            orch, reviews_by_project, successful_project_ids
        )
        _api_cache.set("reviews:all", reviews, ttl_ms=10000)
        return JSONResponse(reviews)
    except Exception as exc:
        logger.error("Reviews API error: %s", exc)
        return JSONResponse(
            {"error": {"code": "fetch_failed", "message": str(exc)}},
            status_code=500,
        )


@app.post("/api/v1/reviews/{project_id}/{review_id}/rebase")
async def api_rebase_review(project_id: str, review_id: str):
    """Trigger a rebase for a review.

    If the rebase fails due to merge conflicts, automatically finds the
    original task (by matching the review source branch to task identifiers),
    posts a comment about the conflict, and reopens the task so the
    agent can resolve it on its own branch.
    """
    try:
        orch = _get_orchestrator()
        project = orch.project_store.get(project_id)
        if not project:
            return JSONResponse(
                {
                    "error": {
                        "code": "not_found",
                        "message": f"Project {project_id} not found",
                    }
                },
                status_code=404,
            )
        provider = detect_provider(project.repo_url, access_token=project.access_token)
        if not provider:
            return JSONResponse(
                {
                    "error": {
                        "code": "unsupported",
                        "message": "No SCM provider detected for this project",
                    }
                },
                status_code=400,
            )
        slug = extract_repo_slug(project.repo_url)
        success, message = provider.rebase_review(slug, review_id)

        notified_issue = None
        if not success and "conflict" in message.lower():
            # Try to find and notify the original task
            notified_issue = _notify_conflict_on_task(
                orch,
                project_id,
                provider,
                slug,
                review_id,
            )

        status_code = 200 if success else 409
        _api_cache.invalidate("reviews:all")
        resp = {"success": success, "message": message}
        if notified_issue:
            resp["notified_issue"] = notified_issue
        return JSONResponse(resp, status_code=status_code)
    except Exception as exc:
        logger.error("Rebase API error: %s", exc)
        return JSONResponse(
            {"error": {"code": "rebase_failed", "message": str(exc)}},
            status_code=500,
        )


@app.post("/api/v1/reviews/{project_id}/{review_id}/retry")
async def api_retry_review(project_id: str, review_id: str):
    """Move a task to the CI-fix status so its agent retries.

    Matches the review source branch to a task identifier, marks it Needs CI Fix,
    and adds a comment instructing the agent to fix CI failures.
    """
    try:
        orch = _get_orchestrator()
        project = orch.project_store.get(project_id)
        if not project:
            return JSONResponse(
                {
                    "error": {
                        "code": "not_found",
                        "message": f"Project {project_id} not found",
                    }
                },
                status_code=404,
            )
        provider = detect_provider(project.repo_url, access_token=project.access_token)
        if not provider:
            return JSONResponse(
                {
                    "error": {
                        "code": "unsupported",
                        "message": "No SCM provider detected",
                    }
                },
                status_code=400,
            )
        slug = extract_repo_slug(project.repo_url)
        review = provider.get_review(slug, review_id)
        if not review:
            return JSONResponse(
                {"error": {"code": "not_found", "message": "Review not found"}},
                status_code=404,
            )
        branch = review.source_branch
        tracker = orch._tracker_for_project(project_id)
        all_issues = tracker.fetch_all_issues()
        matched = None
        for issue in all_issues:
            if issue.identifier == branch or issue.id == branch:
                matched = issue
                break
        if not matched:
            # No existing task — create one for this external review
            matched = tracker.create_issue(
                title=f"Fix CI: {review.title or branch}",
                issue_type="bug",
                description=(
                    f"Auto-created task for external review #{review_id} "
                    f"(branch: {branch}).\n\n"
                    f"URL: {review.url or 'N/A'}"
                ),
                priority=0,
                initial_status=NEEDS_CI_FIX,
            )
            logger.info(
                "Created task %s for external review #%s (branch %s)",
                matched.identifier,
                review_id,
                branch,
            )
        else:
            tracker.update_issue(
                matched.identifier,
                status=NEEDS_CI_FIX,
                priority="0",
                **{"add-label": "ci-fix"},
            )
        tracker.add_comment(
            matched.identifier,
            f"CI tests failed on review #{review_id}. "
            "Your ONLY task is to fix the failing CI tests so this review can merge. "
            "Do NOT rewrite or rework the feature — the feature code is done. "
            "IMPORTANT: File paths in CI logs are not trustworthy — "
            "do NOT use them. Run tests locally to get accurate paths. "
            "Steps: 1) rebase your branch onto main, 2) run the tests locally, "
            "3) fix any test failures using local paths, 4) push. Nothing else.",
            author="oompah",
        )
        _api_cache.invalidate("issues:all")
        _api_cache.invalidate("reviews:all")
        await broadcast_issues()
        return JSONResponse({"success": True, "identifier": matched.identifier})
    except Exception as exc:
        logger.error("Retry review API error: %s", exc)
        return JSONResponse(
            {"error": {"code": "retry_failed", "message": str(exc)}},
            status_code=500,
        )


def _notify_conflict_on_task(
    orch,
    project_id: str,
    provider,
    slug: str,
    review_id: str,
) -> str | None:
    """Find the task that owns a review's source branch, comment, and reopen.

    Returns the task identifier if found and notified, else None.
    """
    try:
        # Get the review details to find the source branch
        review = provider.get_review(slug, review_id)
        if not review:
            logger.warning("Could not fetch review %s to find source branch", review_id)
            return None

        source_branch = review.source_branch
        target_branch = review.target_branch
        if not source_branch:
            return None

        # The branch name is the sanitized task identifier.
        # Look up the task by trying the branch name as an identifier.
        tracker = orch._tracker_for_project(project_id)
        issue = tracker.fetch_issue_detail(source_branch)
        if not issue:
            # No existing task — create one for this external review
            review_title = review.title or source_branch
            issue = tracker.create_issue(
                title=f"Resolve conflicts: {review_title}",
                issue_type="bug",
                description=(
                    f"Auto-created task for external review #{review_id} "
                    f"(branch: {source_branch}) which has merge conflicts.\n\n"
                    f"URL: {review.url or 'N/A'}"
                ),
                priority=0,
                initial_status=NEEDS_REBASE,
            )
            logger.info(
                "Created task %s for external review #%s conflict (branch %s)",
                issue.identifier,
                review_id,
                source_branch,
            )

        # Post a comment about the conflict
        comment_text = (
            f"Merge conflict detected: review #{review_id} cannot be automatically rebased "
            f"onto {target_branch}.\n\n"
            f"Please resolve the conflicts on this branch ({source_branch}):\n"
            f"1. Run: git fetch origin && git rebase origin/{target_branch}\n"
            f"2. Resolve all conflicts, keeping the intent of both sides\n"
            f"3. Run tests to verify nothing is broken\n"
            f"4. Force-push: git push --force-with-lease\n"
            f"5. Verify the review is clean and CI passes"
        )
        tracker.add_comment(issue.identifier, comment_text, author="oompah")

        # Mark the task if it's in a terminal state, and add label atomically
        state_lower = issue.state.strip().lower()
        if state_lower in [s.lower() for s in orch.config.tracker_terminal_states]:
            tracker.update_issue(
                issue.identifier,
                status=NEEDS_REBASE,
                priority="0",
                **{"add-label": "merge-conflict"},
            )
            logger.info(
                "Reopened task %s as P0 for merge conflict resolution (review #%s)",
                issue.identifier,
                review_id,
            )
        else:
            try:
                tracker.update_issue(
                    issue.identifier,
                    status=NEEDS_REBASE,
                    **{"add-label": "merge-conflict"},
                )
            except Exception as label_exc:
                logger.warning(
                    "Failed to add merge-conflict label to %s: %s",
                    issue.identifier,
                    label_exc,
                )
            logger.info(
                "Commented on task %s about merge conflict (review #%s), already in state '%s'",
                issue.identifier,
                review_id,
                issue.state,
            )

        return issue.identifier

    except Exception as exc:
        logger.warning(
            "Failed to notify task about conflict for review #%s: %s", review_id, exc
        )
        return None


@app.get("/api/v1/{issue_identifier}")
async def api_issue_detail(issue_identifier: str):
    """Return issue-specific runtime details."""
    try:
        orch = _get_orchestrator()
        detail = orch.get_issue_detail(issue_identifier)
        if detail is None:
            return JSONResponse(
                {
                    "error": {
                        "code": "issue_not_found",
                        "message": f"Issue {issue_identifier} not found in current state",
                    }
                },
                status_code=404,
            )
        return JSONResponse(detail)
    except Exception as exc:
        logger.error("Issue detail API error: %s", exc)
        return JSONResponse(
            {"error": {"code": "unavailable", "message": str(exc)}},
            status_code=503,
        )


@app.post("/api/v1/refresh")
async def api_refresh():
    """Queue an immediate poll+reconciliation cycle."""
    try:
        orch = _get_orchestrator()
        orch.request_refresh()
        return JSONResponse(
            {
                "queued": True,
                "coalesced": False,
                "requested_at": datetime.now(timezone.utc).isoformat(),
                "operations": ["poll", "reconcile"],
            },
            status_code=202,
        )
    except Exception as exc:
        logger.error("Refresh API error: %s", exc)
        return JSONResponse(
            {"error": {"code": "unavailable", "message": str(exc)}},
            status_code=503,
        )


# ---------------------------------------------------------------------------
# Multimodal attachments (Phase 4)
# ---------------------------------------------------------------------------

_ATTACHMENT_MIME_BY_EXT = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".pdf": "application/pdf",
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".mp4": "video/mp4",
}

_SVG_SCRIPT_RE = re.compile(
    rb"<script\b[^>]*>.*?</script\s*>", re.IGNORECASE | re.DOTALL
)
_SVG_EVENT_ATTR_RE = re.compile(rb'\son\w+\s*=\s*"[^"]*"', re.IGNORECASE)


def _sanitize_svg(data: bytes) -> bytes:
    """Strip <script> blocks and on*= event handlers from SVG bytes.

    Best-effort; for richer hardening swap in a real SVG sanitizer."""
    out = _SVG_SCRIPT_RE.sub(b"", data)
    out = _SVG_EVENT_ATTR_RE.sub(b"", out)
    return out


def _resolve_attachment_path(orch, rel: str) -> tuple[str | None, str | None]:
    """Resolve a repo-relative attachment path to ``(project_id, abs_path)``.

    Refuses anything that isn't under some known project's
    ``.oompah/attachments/`` tree. Returns ``(None, None)`` on traversal,
    unknown project, or missing file.
    """
    if not rel or os.path.isabs(rel) or ".." in rel.split("/"):
        return None, None
    if not rel.startswith(".oompah/attachments/"):
        return None, None
    for project in orch.project_store.list_all():
        repo_path = getattr(project, "repo_path", None)
        if not repo_path:
            continue
        candidate = os.path.realpath(os.path.join(repo_path, rel))
        attach_root = os.path.realpath(
            os.path.join(repo_path, ".oompah", "attachments")
        )
        if candidate.startswith(attach_root + os.sep) and os.path.isfile(candidate):
            return project.id, candidate
    return None, None


@app.get("/api/v1/issues/{identifier}/attachments")
async def api_list_attachments(identifier: str):
    """List the attachments recorded on an issue (rich records from tasks
    metadata; the on-disk sidecar is not consulted here)."""
    try:
        orch = _get_orchestrator()
    except Exception as exc:
        return JSONResponse(
            {"error": {"code": "unavailable", "message": str(exc)}}, status_code=503
        )
    tracker, _project_id, _issue = _find_tracker_for_issue(orch, identifier)
    if tracker is None:
        return JSONResponse(
            {
                "error": {
                    "code": "not_found",
                    "message": f"Issue {identifier} not found",
                }
            },
            status_code=404,
        )
    try:
        records = tracker.fetch_attachments(identifier)
    except Exception as exc:
        return JSONResponse(
            {"error": {"code": "tracker_error", "message": str(exc)}}, status_code=500
        )
    return JSONResponse(records)


@app.post("/api/v1/issues/{identifier}/attachments")
async def api_upload_attachment(identifier: str, file: UploadFile = File(...)):
    """Upload an attachment to an issue. Multipart form: ``file=<binary>``."""
    try:
        orch = _get_orchestrator()
    except Exception as exc:
        return JSONResponse(
            {"error": {"code": "unavailable", "message": str(exc)}}, status_code=503
        )

    tracker, project_id, _issue = _find_tracker_for_issue(orch, identifier)
    if tracker is None:
        return JSONResponse(
            {
                "error": {
                    "code": "not_found",
                    "message": f"Issue {identifier} not found",
                }
            },
            status_code=404,
        )
    if not project_id:
        return JSONResponse(
            {
                "error": {
                    "code": "no_project",
                    "message": "Attachments require a project-backed issue",
                }
            },
            status_code=400,
        )
    project = orch.project_store.get(project_id)
    if not project or not project.repo_path:
        return JSONResponse(
            {"error": {"code": "no_repo", "message": "Project has no repo_path"}},
            status_code=500,
        )

    # Validate mime up-front from the file's name (uploads usually have
    # accurate content_type but the AttachmentStore re-validates from the
    # extension as the canonical source of truth).
    from oompah.attachments import (
        ALLOWED_MIME_TYPES,
        AttachmentStore,
        AttachmentMimeRejected,
        AttachmentTooLarge,
    )

    ext = os.path.splitext(file.filename or "")[1].lower()
    mime = _ATTACHMENT_MIME_BY_EXT.get(ext) or file.content_type or ""
    if mime not in ALLOWED_MIME_TYPES:
        return JSONResponse(
            {
                "error": {
                    "code": "unsupported_media_type",
                    "message": f"mime {mime!r} not allowed",
                }
            },
            status_code=415,
        )

    # Stage to a temp file then hand to AttachmentStore.add.
    # All blocking I/O (write, file-copy, git commit) runs in a thread to
    # avoid stalling the shared event loop.
    import tempfile

    contents = await file.read()

    def _upload_sync() -> tuple[dict | None, tuple[str, str, int] | None]:
        """Write, store, and commit. Returns (record_dict, None) on success or
        (None, (error_code, message, http_status)) on known errors."""
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=ext,
            dir=tempfile.gettempdir(),
        ) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name

        try:
            _store = AttachmentStore(project.repo_path)
            try:
                _rec = _store.add(identifier, tmp_path, mime_type=mime, added_by="user")
            except AttachmentTooLarge as _exc:
                return None, ("payload_too_large", str(_exc), 413)
            except AttachmentMimeRejected as _exc:
                return None, ("unsupported_media_type", str(_exc), 415)

            # Update task metadata: append the new record to the existing list.
            _existing: list = []
            try:
                _existing = list(tracker.fetch_attachments(identifier) or [])
            except Exception:
                pass
            _merged = _existing + [_rec.to_dict()]
            tracker.set_attachments(
                identifier, _merged, project_root=project.repo_path
            )

            # Commit the file so it travels with the repo.
            try:
                _store.commit(
                    [_rec.path],
                    f"Add attachment {os.path.basename(_rec.path)} for {identifier}",
                )
            except Exception as _exc:
                logger.warning(
                    "attachment commit failed for %s: %s", identifier, _exc
                )

            return _rec.to_dict(), None
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    rec_dict, upload_error = await asyncio.to_thread(_upload_sync)
    if upload_error is not None:
        err_code, err_msg, err_status = upload_error
        return JSONResponse(
            {"error": {"code": err_code, "message": err_msg}},
            status_code=err_status,
        )
    return JSONResponse(rec_dict, status_code=201)


@app.get("/api/v1/attachments/{path:path}")
async def api_serve_attachment(path: str):
    """Stream an attachment by its repo-relative path. Path-validated to
    a known project's ``.oompah/attachments/`` tree; SVGs are sanitized
    before return."""
    try:
        orch = _get_orchestrator()
    except Exception:
        return JSONResponse({"error": {"code": "unavailable"}}, status_code=503)
    project_id, abs_path = _resolve_attachment_path(orch, path)
    if not abs_path:
        return JSONResponse(
            {"error": {"code": "not_found", "message": "attachment not found"}},
            status_code=404,
        )
    ext = os.path.splitext(abs_path)[1].lower()
    mime = _ATTACHMENT_MIME_BY_EXT.get(ext, "application/octet-stream")

    def _read_attachment() -> bytes:
        """Read attachment file. Runs in thread to avoid blocking the event loop."""
        with open(abs_path, "rb") as f:
            return f.read()

    try:
        data = await asyncio.to_thread(_read_attachment)
    except OSError:
        return JSONResponse({"error": {"code": "io_error"}}, status_code=500)
    if mime == "image/svg+xml":
        data = _sanitize_svg(data)
    return Response(content=data, media_type=mime)


@app.delete("/api/v1/attachments/{path:path}")
async def api_delete_attachment(path: str, request: Request):
    """Remove an attachment from its issue. Generated attachments require
    ``?force=generated`` to confirm."""
    try:
        orch = _get_orchestrator()
    except Exception as exc:
        return JSONResponse(
            {"error": {"code": "unavailable", "message": str(exc)}}, status_code=503
        )

    project_id, abs_path = _resolve_attachment_path(orch, path)
    if not project_id:
        return JSONResponse(
            {"error": {"code": "not_found", "message": "attachment not found"}},
            status_code=404,
        )
    project = orch.project_store.get(project_id)
    if not project or not project.repo_path:
        return JSONResponse({"error": {"code": "no_repo"}}, status_code=500)

    # Identifier from path: .oompah/attachments/<id>/...
    parts = path.split("/")
    if len(parts) < 4:
        return JSONResponse({"error": {"code": "bad_path"}}, status_code=400)
    identifier = parts[2]

    # Find the metadata record so we can check generated + emit the right
    # response.
    tracker = orch._tracker_for_project(project_id)
    try:
        records = list(tracker.fetch_attachments(identifier) or [])
    except Exception:
        records = []
    target = next((r for r in records if r.get("path") == path), None)
    if target is None:
        return JSONResponse(
            {"error": {"code": "not_found", "message": "attachment not on issue"}},
            status_code=404,
        )
    if target.get("generated") and request.query_params.get("force") != "generated":
        return JSONResponse(
            {
                "error": {
                    "code": "confirm_generated",
                    "message": "Generated attachments require ?force=generated",
                }
            },
            status_code=409,
        )

    from oompah.attachments import AttachmentStore

    store = AttachmentStore(project.repo_path)
    try:
        store.remove(path)
    except Exception as exc:
        logger.warning("attachment remove failed: %s", exc)

    remaining = [r for r in records if r.get("path") != path]
    tracker.set_attachments(identifier, remaining, project_root=project.repo_path)
    try:
        store.commit([path], f"Remove attachment {os.path.basename(path)}")
    except Exception as exc:
        logger.warning("attachment delete commit failed: %s", exc)

    return JSONResponse({"deleted": path})


@app.post("/api/v1/errors")
async def api_report_error(request: Request):
    """Accept error reports from the frontend and create tasks."""
    if not _error_watcher:
        return JSONResponse(
            {
                "error": {
                    "code": "unavailable",
                    "message": "Error watcher not initialized",
                }
            },
            status_code=503,
        )
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError) as exc:
        return JSONResponse(
            {
                "error": {
                    "code": "validation",
                    "message": f"Invalid JSON: {exc}",
                }
            },
            status_code=400,
        )
    message = body.get("message", "").strip()
    if not message:
        return JSONResponse(
            {"error": {"code": "bad_request", "message": "message is required"}},
            status_code=400,
        )
    source = body.get("source", "frontend")
    detail = body.get("detail")
    priority = body.get("priority", 3)
    error_class = body.get("error_class") or None
    identifier = _error_watcher.report_error(
        source=source,
        message=message,
        detail=detail,
        priority=priority,
        error_class=error_class,
    )
    return JSONResponse(
        {
            "created": identifier is not None,
            "identifier": identifier,
            "deduplicated": identifier is None,
        }
    )


# --- Forge Webhook Receivers ---


def _handle_webhook_event(event: WebhookEvent, project) -> None:
    """Process a validated webhook event: emit on EventBus and trigger refresh.

    Args:
        event: The parsed webhook event.
        project: The matched Project object (may be None for unmatched repos).
    """
    orch = _get_orchestrator()

    payload = {
        "provider": event.provider,
        "event_type": event.event_type,
        "action": event.action,
        "repo_slug": event.repo_slug,
        "review_id": event.review_id,
        "source_branch": event.source_branch,
        "target_branch": event.target_branch,
        "author": event.author,
        "title": event.title,
        "merged": event.merged,
    }
    # Include extended fields only when non-empty to keep payloads compact.
    if event.issue_number:
        payload["issue_number"] = event.issue_number
    if event.comment_id:
        payload["comment_id"] = event.comment_id
    if event.label_name:
        payload["label_name"] = event.label_name
    if event.project_item_id:
        payload["project_item_id"] = event.project_item_id
    if event.project_field_name:
        payload["project_field_name"] = event.project_field_name
    if event.project_field_value:
        payload["project_field_value"] = event.project_field_value
    if project:
        payload["project_id"] = project.id
        payload["project_name"] = project.name
        # Record the timestamp of this webhook delivery on the project so
        # callers can track the last-seen delivery time per-project.
        now = datetime.now(timezone.utc)
        orch.project_store.update(
            project.id,
            last_webhook_received_at=now,
        )

    orch.event_bus.emit(EventType.FORGE_WEBHOOK_RECEIVED, payload)
    logger.info(
        "Forge webhook: %s %s/%s #%s (action=%s, merged=%s, project=%s)",
        event.provider,
        event.repo_slug,
        event.event_type,
        event.review_id,
        event.action,
        event.merged,
        project.name if project else "unmatched",
    )

    # ---------------------------------------------------------------------------
    # Cache invalidation — targeted per event type (AC#1 + AC#2)
    # ---------------------------------------------------------------------------
    # Invalidate only the caches that the current event can affect, so that
    # unrelated cached entries are not evicted unnecessarily.

    _project_id = project.id if project else None

    if event.event_type in ("pull_request", "merge_group", "Merge Request Hook"):
        # PR / MR / merge-queue events affect the review board and may close issues.
        _api_cache.invalidate("reviews:all")
        _api_cache.invalidate("issues:all")
    elif event.event_type == "issues":
        # Issue state or metadata changed; drop the per-issue detail as well.
        _api_cache.invalidate("issues:all")
        if _project_id and event.issue_number:
            _api_cache.invalidate_prefix(f"detail:{_project_id}:{event.issue_number}")
    elif event.event_type == "issue_comment":
        # A comment was created, edited, or deleted on an issue.
        _api_cache.invalidate("issues:all")
        if _project_id and event.issue_number:
            _api_cache.invalidate(f"comments:{_project_id}:{event.issue_number}")
            _api_cache.invalidate_prefix(f"detail:{_project_id}:{event.issue_number}")
    elif event.event_type == "projects_v2_item":
        # A GitHub Projects v2 item field changed (e.g. Oompah Status).
        # We cannot cheaply map project_item_id → issue_number here, so we
        # drop the full issue-list cache and let the next fetch rebuild it.
        _api_cache.invalidate("issues:all")
    # label events (repository-level label definitions) and push events do
    # not directly change cached task data; push state is refreshed via the
    # source-sync thread when the tracked branch advances.

    if event.merged:
        orch.invalidate_merged_branches()

    # Invalidate the tracker's in-memory read cache (ETag-based) for events
    # that may update the branch-to-issue mapping.  For GitHubIssueTracker
    # this clears the ETag store so the next fetch re-validates against the
    # live API, rebuilding the branch-to-issue index.  Best-effort: any
    # failure is swallowed so it never blocks the webhook response path.
    if project and event.event_type in ("issues", "pull_request", "Merge Request Hook", "push"):
        try:
            tracker = orch._tracker_for_project(project.id)
            inval = getattr(tracker, "invalidate_read_cache", None)
            if callable(inval):
                inval()
        except Exception:  # pragma: no cover — defensive, never block webhook
            pass

    # Request an orchestrator refresh cycle only for events that can affect
    # dispatch, status, comments, or review reconciliation.  This prevents
    # webhook storms (e.g. many repository-level label-created events or
    # pushes to non-tracked branches) from triggering unnecessary
    # orchestrator wakeups.
    if _webhook_should_request_refresh(event, project):
        orch.request_refresh()

    # If the webhook signals that the project's tracked branch advanced
    # (push to that branch, or PR merged into it), pull the latest source
    # and tasks state. Without this, new commits — including tasks
    # un-defers and direct chore pushes — only land on the local clone at
    # the next service restart. Sync runs in a background thread so the
    # webhook response stays fast.
    if project and _webhook_advanced_tracked_branch(event, project):
        threading.Thread(
            target=_sync_project_after_webhook,
            args=(orch, project.id, project.name),
            name=f"webhook-sync-{project.name}",
            daemon=True,
        ).start()

    # When GitHub's merge queue successfully dequeues a PR (merge_group
    # destroyed + merged=True), label the corresponding task as merged and
    # trigger a source sync.  This is the queue-mode equivalent of the
    # direct-merge path that fires on PR closed+merged webhooks.
    if event.event_type == "merge_group" and event.merged and project:
        threading.Thread(
            target=_label_task_merged_from_merge_group,
            args=(orch, event, project),
            name=f"merge-group-label-{project.name}",
            daemon=True,
        ).start()

    # When a PR/MR is opened or reopened, mark the task In Review immediately
    # rather than waiting for the next polling cycle.
    if (
        event.event_type in ("pull_request", "Merge Request Hook")
        and event.action in ("opened", "reopened")
        and project
    ):
        threading.Thread(
            target=_mark_task_in_review_from_webhook,
            args=(orch, event, project),
            name=f"webhook-in-review-{project.name}",
            daemon=True,
        ).start()

    # When a PR/MR is closed with merge (direct merge, not merge_group),
    # mark the task Merged immediately without waiting for the sweep.
    if (
        event.event_type in ("pull_request", "Merge Request Hook")
        and event.action == "closed"
        and event.merged
        and project
    ):
        threading.Thread(
            target=_label_task_merged_from_pr,
            args=(orch, event, project),
            name=f"webhook-merged-{project.name}",
            daemon=True,
        ).start()


def _webhook_advanced_tracked_branch(event, project) -> bool:
    """True when the webhook indicates any of the project's tracked branches advanced on origin.

    Three cases:
      * ``push`` events on any tracked branch (target_branch matches a branch pattern).
      * ``pull_request`` events with ``merged=True`` whose base branch is
        a tracked branch.
      * ``merge_group`` events with ``merged=True`` (queue dequeued
        successfully), whose target_branch is a tracked branch.
    """
    if event.event_type == "push":
        return project.matches_branch(event.target_branch)
    if event.event_type == "pull_request" and event.merged:
        return project.matches_branch(event.target_branch)
    if event.event_type == "merge_group" and event.merged:
        return project.matches_branch(event.target_branch)
    return False


# Actions on ``issues`` events that change a task's dispatch eligibility or
# lifecycle state.
_DISPATCH_AFFECTING_ISSUE_ACTIONS: frozenset[str] = frozenset(
    {
        "opened",
        "closed",
        "reopened",
        "labeled",
        "unlabeled",
        "assigned",
        "unassigned",
        "transferred",
        "deleted",
    }
)

# ``projects_v2_item`` actions that may update Oompah Status or dispatch fields.
_DISPATCH_AFFECTING_PROJECTS_ACTIONS: frozenset[str] = frozenset(
    {"created", "edited", "deleted"}
)


def _webhook_should_request_refresh(event: "WebhookEvent", project) -> bool:
    """Return ``True`` when the event can affect dispatch, status, comments, or review reconciliation.

    Events that cannot change any task-relevant state — for example
    repository-level label definitions being created or edited, or push
    events to branches that are not tracked by any project — do not
    warrant waking the orchestrator dispatch loop.

    Args:
        event: The parsed webhook event.
        project: The matched :class:`~oompah.models.Project` (may be ``None``
            for unmatched repos).

    Returns:
        ``True`` if the event warrants an orchestrator refresh; ``False``
        otherwise.
    """
    # Review- and merge-queue events always warrant a refresh (GitHub and GitLab).
    if event.event_type in ("pull_request", "merge_group", "Merge Request Hook"):
        return True
    # Comment events may contain orchestrator directives or status updates
    # that agents post as structured comments.
    if event.event_type == "issue_comment":
        return True
    # Issue events warrant a refresh only for actions that change dispatch
    # eligibility: opened/closed/reopened change the task life-cycle;
    # labeled/unlabeled and assigned/unassigned may gate routing;
    # transferred/deleted remove the task from consideration.
    if event.event_type == "issues" and event.action in _DISPATCH_AFFECTING_ISSUE_ACTIONS:
        return True
    # Project-field events may update the Oompah Status field which drives
    # task dispatch.  Restrict to the actions that actually change item state.
    if event.event_type == "projects_v2_item" and event.action in _DISPATCH_AFFECTING_PROJECTS_ACTIONS:
        return True
    # A push to one of the project's tracked branches means new commits landed
    # and the orchestrator should scan for newly-deferred or un-deferred tasks.
    if event.event_type == "push" and project and _webhook_advanced_tracked_branch(event, project):
        return True
    # All other events are not dispatch-relevant:
    # - repository-level label changes (label created/edited/deleted)
    # - push to non-tracked branches
    # - unrecognised projects_v2_item actions (e.g. reordered, archived)
    # - issues with non-status actions (e.g. locked, unlocked, pinned)
    return False


def _label_task_merged_from_merge_group(orch, event, project) -> None:
    """Label the task as merged when a merge_group destroyed event signals success.

    The merge_group ``head_ref`` is ``gh-readonly-queue/<base>/<pr-identifier>``
    where ``<pr-identifier>`` encodes the source branch name.  We parse out
    the branch name and match it to a closed task so it gets the ``merged``
    label — the same outcome as today's direct-merge path.

    This runs in a background thread (called from _handle_webhook_event).
    """
    if not project:
        return
    head_ref = (event.source_branch or "").strip()
    if not head_ref:
        return

    # The head_ref looks like:
    #   gh-readonly-queue/main/pr-123-<branch-name>
    # We extract everything after the third "/" segment as the branch name
    # prefix used to identify the task.
    parts = head_ref.split("/", 3)
    if len(parts) < 4:
        # Fallback: use the whole head_ref, which likely won't match but
        # log a debug so operators can diagnose.
        branch_name = head_ref
        logger.debug(
            "merge_group head_ref %r does not match expected pattern "
            "gh-readonly-queue/<base>/<branch>; trying as-is",
            head_ref,
        )
    else:
        # parts[3] is something like "pr-42-oompah-zlz_2-xyz"
        # The task identifier follows "pr-<N>-" prefix.
        tail = parts[3]
        dash_parts = tail.split("-", 2)
        if len(dash_parts) >= 3:
            branch_name = dash_parts[2]
        else:
            branch_name = tail

    try:
        tracker = orch._tracker_for_project(project.id)
        # Use _resolve_task_for_branch so GitHub-backed tasks (whose
        # branch names are generated slugs) are found via the per-project
        # branch index, and legacy Backlog tasks (branch==identifier) are
        # found via the direct fetch_issue_detail fallback.
        issue = orch._resolve_task_for_branch(
            tracker, branch_name, project_id=project.id
        )
        if issue is None:
            logger.debug(
                "merge_group: no task found for branch %r (head_ref=%r)",
                branch_name,
                head_ref,
            )
            return
        if canonicalize_status(issue.state) != MERGED:
            tracker.update_issue(issue.identifier, status=MERGED)
            logger.info(
                "merge_group: marked %s as Merged (head_ref=%r)",
                issue.identifier,
                head_ref,
            )
    except Exception as exc:
        logger.warning(
            "merge_group: failed to label task for head_ref %r: %s",
            head_ref,
            exc,
        )


def _mark_task_in_review_from_webhook(orch, event, project) -> None:
    """Mark a task ``In Review`` when a PR/MR is opened or reopened.

    Looks up the task whose branch matches the PR's source branch and
    advances it to ``In Review``.  Also writes review metadata
    (review URL, review number, work branch) so the task record carries
    a stable PR link.

    Runs in a background thread (called from :func:`_handle_webhook_event`).
    """
    if not project:
        return
    source_branch = (event.source_branch or "").strip()
    if not source_branch:
        return
    try:
        tracker = orch._tracker_for_project(project.id)
        # Use _resolve_task_for_branch so GitHub-backed tasks (whose
        # branch names are generated slugs) are found via the per-project
        # branch index, and legacy Backlog tasks (branch==identifier) are
        # found via the direct fetch_issue_detail fallback.
        issue = orch._resolve_task_for_branch(
            tracker, source_branch, project_id=project.id
        )
        if issue is None:
            logger.debug(
                "webhook In Review: no task found for branch %r (project=%s)",
                source_branch,
                project.name,
            )
            return
        current_status = canonicalize_status(issue.state)
        if current_status == IN_REVIEW:
            # Already In Review; still refresh metadata in case this is a
            # reopened PR that now carries different review metadata.
            pass
        elif current_status in (MERGED, "Archived"):
            logger.debug(
                "webhook In Review: skipping %s (already %s)",
                issue.identifier,
                current_status,
            )
            return
        else:
            tracker.update_issue(issue.identifier, status=IN_REVIEW)
            logger.info(
                "webhook: marked %s as In Review (PR #%s opened/reopened, branch=%s)",
                issue.identifier,
                event.review_id,
                source_branch,
            )
        # Write review metadata so the task record has a stable PR link
        review_url = None
        # GitHub PR URL can be reconstructed from repo slug + PR number
        if event.review_id and event.repo_slug:
            provider_base = (
                "https://gitlab.com"
                if event.provider == "gitlab"
                else "https://github.com"
            )
            pr_path = (
                "merge_requests" if event.provider == "gitlab" else "pull"
            )
            review_url = (
                f"{provider_base}/{event.repo_slug}/{pr_path}/{event.review_id}"
            )
        for key, value in [
            ("oompah.review_url", review_url),
            ("oompah.review_number", event.review_id or None),
            ("oompah.work_branch", source_branch),
            ("oompah.target_branch", event.target_branch or None),
        ]:
            if not value:
                continue
            try:
                tracker.set_metadata_field(issue.identifier, key, value)
            except Exception as exc:  # noqa: BLE001 - best effort
                logger.debug(
                    "webhook In Review: failed to write metadata %s for %s: %s",
                    key,
                    issue.identifier,
                    exc,
                )
    except Exception as exc:
        logger.warning(
            "webhook: failed to mark In Review for branch %r (project=%s): %s",
            source_branch,
            project.name if project else "?",
            exc,
        )


def _label_task_merged_from_pr(orch, event, project) -> None:
    """Mark a task ``Merged`` when a pull request is closed with merge.

    This handles direct PR merges (``pull_request`` closed + merged=True).
    The merge_group path (queue-mode merges) is handled separately by
    :func:`_label_task_merged_from_merge_group`.

    Runs in a background thread (called from :func:`_handle_webhook_event`).
    """
    if not project:
        return
    source_branch = (event.source_branch or "").strip()
    if not source_branch:
        return
    try:
        tracker = orch._tracker_for_project(project.id)
        # Use _resolve_task_for_branch so GitHub-backed tasks (whose
        # branch names are generated slugs) are found via the per-project
        # branch index, and legacy Backlog tasks (branch==identifier) are
        # found via the direct fetch_issue_detail fallback.
        issue = orch._resolve_task_for_branch(
            tracker, source_branch, project_id=project.id
        )
        if issue is None:
            logger.debug(
                "webhook Merged: no task found for branch %r (project=%s)",
                source_branch,
                project.name,
            )
            return
        if canonicalize_status(issue.state) != MERGED:
            tracker.update_issue(issue.identifier, status=MERGED)
            logger.info(
                "webhook: marked %s as Merged (PR #%s closed+merged, branch=%s)",
                issue.identifier,
                event.review_id,
                source_branch,
            )
        else:
            logger.debug(
                "webhook Merged: %s already Merged; skipping",
                issue.identifier,
            )
    except Exception as exc:
        logger.warning(
            "webhook: failed to mark Merged for branch %r (project=%s): %s",
            source_branch,
            project.name if project else "?",
            exc,
        )


def _sync_project_after_webhook(
    orch,
    project_id: str,
    project_name: str,
) -> None:
    """Pull source + validate tracker config for one project after a webhook.

    Best-effort: any failure is logged but does not raise. The next
    service restart's startup sync remains the safety net.
    """
    try:
        status = orch.project_store.sync_project_sources(project_id)
        logger.info(
            "Webhook sync %s: git=%s backlog=%s conflicts=%s",
            project_name,
            status.get("git", "?"),
            status.get("backlog", "?"),
            status.get("conflicts", "?"),
        )
        # Refresh conflict alerts after each project sync so the dashboard
        # immediately reflects resolved or new conflicts.
        if hasattr(orch, "_refresh_backlog_conflict_alerts"):
            orch._refresh_backlog_conflict_alerts()
    except Exception as exc:
        logger.warning("Webhook sync failed for %s: %s", project_name, exc)


def _install_backlog_hook_for_project(project) -> None:
    """Install or update the Backlog webhook hook for one project.

    GitHub-backed projects (``tracker_kind == "github_issues"``) are skipped
    — they use GitHub webhooks for task-change notifications and do not need
    Backlog post-commit hooks.

    Best-effort: any failure is logged at DEBUG level so project
    create/update operations are never blocked by hook installation
    errors.
    """
    # GitHub-backed projects must not install Backlog hooks (TASK-463.4).
    tracker_kind = getattr(project, "tracker_kind", None)
    if tracker_kind == "github_issues":
        logger.debug(
            "_install_backlog_hook_for_project: skipping GitHub-backed project %s",
            getattr(project, "id", "?"),
        )
        return

    try:
        from oompah.backlog_webhooks import install_backlog_webhook_hook

        port = int(os.environ.get("OOMPAH_SERVER_PORT", "8080"))
        server_base_url = (
            os.environ.get("OOMPAH_SERVER_URL")
            or f"http://localhost:{port}"
        )
        webhook_url = server_base_url.rstrip("/") + "/api/v1/webhooks/backlog"
        secret = getattr(project, "webhook_secret", None) or ""
        repo_path = getattr(project, "repo_path", None) or ""

        install_backlog_webhook_hook(
            repo_path=repo_path,
            webhook_url=webhook_url,
            project_id=project.id,
            secret=secret,
        )
    except Exception as exc:
        logger.debug(
            "_install_backlog_hook_for_project: failed for %s: %s",
            getattr(project, "id", "?"),
            exc,
        )


@app.post("/api/v1/webhooks/github")
async def api_webhook_github(request: Request):
    """Receive GitHub webhook events (push, pull_request, etc.).

    Validates the ``X-Hub-Signature-256`` HMAC signature against the
    project's ``webhook_secret``. If no secret is configured on any
    matching project, the webhook is accepted without validation (to
    support initial setup).
    """
    try:
        body_bytes = await request.body()

        event_type = request.headers.get("X-GitHub-Event", "")
        signature = request.headers.get("X-Hub-Signature-256", "")
        delivery_id = request.headers.get("X-GitHub-Delivery", "")

        if not event_type:
            return JSONResponse(
                {"error": "Missing X-GitHub-Event header"},
                status_code=400,
            )

        try:
            payload = json.loads(body_bytes)
        except (json.JSONDecodeError, ValueError):
            return JSONResponse(
                {"error": "Invalid JSON payload"},
                status_code=400,
            )

        # Parse the webhook
        event = parse_github_webhook(event_type, payload)
        if event is None:
            # Non-PR event — acknowledge but don't process
            return JSONResponse(
                {"ok": True, "action": "ignored", "event_type": event_type}
            )

        # Find matching project
        orch = _get_orchestrator()
        projects = orch.project_store.list_all()
        project = match_project_by_repo(projects, event.repo_slug, "github")

        # Validate signature if project has a webhook_secret
        if project and project.webhook_secret:
            if not validate_github_signature(
                body_bytes, signature, project.webhook_secret
            ):
                logger.warning(
                    "GitHub webhook signature validation failed for %s (delivery=%s)",
                    event.repo_slug,
                    delivery_id,
                )
                return JSONResponse(
                    {"error": "Invalid signature"},
                    status_code=401,
                )

        _handle_webhook_event(event, project)
        return JSONResponse(
            {
                "ok": True,
                "action": "processed",
                "event_type": event_type,
                "delivery_id": delivery_id,
                "review_id": event.review_id,
                "pr_action": event.action,
            }
        )

    except Exception as exc:
        logger.error("GitHub webhook error: %s", exc, exc_info=True)
        return JSONResponse(
            {"error": {"code": "webhook_error", "message": str(exc)}},
            status_code=500,
        )


@app.post("/api/v1/webhooks/gitlab")
async def api_webhook_gitlab(request: Request):
    """Receive GitLab webhook events (Merge Request Hook, etc.).

    Validates the ``X-Gitlab-Token`` header against the project's
    ``webhook_secret``. If no secret is configured on any matching
    project, the webhook is accepted without validation.
    """
    try:
        body_bytes = await request.body()

        event_type = request.headers.get("X-Gitlab-Event", "")
        token = request.headers.get("X-Gitlab-Token", "")

        if not event_type:
            return JSONResponse(
                {"error": "Missing X-Gitlab-Event header"},
                status_code=400,
            )

        try:
            payload = json.loads(body_bytes)
        except (json.JSONDecodeError, ValueError):
            return JSONResponse(
                {"error": "Invalid JSON payload"},
                status_code=400,
            )

        # Parse the webhook
        event = parse_gitlab_webhook(event_type, payload)
        if event is None:
            return JSONResponse(
                {"ok": True, "action": "ignored", "event_type": event_type}
            )

        # Find matching project
        orch = _get_orchestrator()
        projects = orch.project_store.list_all()
        project = match_project_by_repo(projects, event.repo_slug, "gitlab")

        # Validate token if project has a webhook_secret
        if project and project.webhook_secret:
            if not validate_gitlab_token(token, project.webhook_secret):
                logger.warning(
                    "GitLab webhook token validation failed for %s",
                    event.repo_slug,
                )
                return JSONResponse(
                    {"error": "Invalid token"},
                    status_code=401,
                )

        _handle_webhook_event(event, project)
        return JSONResponse(
            {
                "ok": True,
                "action": "processed",
                "event_type": event_type,
                "review_id": event.review_id,
                "mr_action": event.action,
            }
        )

    except Exception as exc:
        logger.error("GitLab webhook error: %s", exc, exc_info=True)
        return JSONResponse(
            {"error": {"code": "webhook_error", "message": str(exc)}},
            status_code=500,
        )


@app.post("/api/v1/webhooks/backlog")
async def api_webhook_backlog(request: Request):
    """Receive Backlog.md task-change webhook notifications.

    This endpoint is called by the ``post-commit`` git hook installed
    in each managed project repo whenever a commit touches backlog task
    files.  The hook signs the payload with HMAC-SHA256 and sends the
    signature in ``X-Oompah-Signature: sha256=<hex>``.

    Validation:
    - If the project has a ``webhook_secret`` configured and the request
      carries a signature header, the signature is validated.
    - If the project has no secret (or the request carries no signature),
      the webhook is accepted without authentication (to support initial
      setup and repos with no secret).

    On receipt:
    - Invalidates the issue list cache for the project.
    - Triggers a ``git pull`` / Backlog sync in a background thread.
    - Calls ``orchestrator.request_refresh()`` so the dashboard updates.

    Returns:
        200 OK on success, 400 on bad JSON / missing fields,
        401 on signature mismatch.
    """
    try:
        body_bytes = await request.body()

        # Require a non-empty body.
        if not body_bytes:
            return JSONResponse(
                {"error": "Empty request body"},
                status_code=400,
            )

        try:
            payload = json.loads(body_bytes)
        except (json.JSONDecodeError, ValueError):
            return JSONResponse(
                {"error": "Invalid JSON payload"},
                status_code=400,
            )

        if not isinstance(payload, dict):
            return JSONResponse(
                {"error": "Payload must be a JSON object"},
                status_code=400,
            )

        project_id = payload.get("project_id", "")
        event = payload.get("event", "")
        files_changed = payload.get("files", [])

        # Look up the project.
        orch = _get_orchestrator()
        project = orch.project_store.get(project_id) if project_id else None

        # GitHub-backed projects must not process Backlog webhook receipts
        # (TASK-463.4).  If a stale hook fires for a project that has since
        # been migrated to GitHub Issues, acknowledge the request but take no
        # action so the transition is safe and idempotent.
        if project and getattr(project, "tracker_kind", None) == "github_issues":
            logger.info(
                "Backlog webhook ignored for GitHub-backed project %s "
                "(tracker_kind=github_issues); returning ok with no-op action",
                project_id,
            )
            return JSONResponse(
                {
                    "ok": True,
                    "action": "ignored",
                    "reason": "github_issues tracker",
                    "project_id": project_id,
                }
            )

        # Validate HMAC signature if the project has a secret configured.
        signature = request.headers.get("X-Oompah-Signature", "")
        if project and project.webhook_secret:
            if signature:
                if not validate_backlog_webhook_signature(
                    body_bytes, signature, project.webhook_secret
                ):
                    logger.warning(
                        "Backlog webhook signature validation failed for project %s",
                        project_id,
                    )
                    return JSONResponse(
                        {"error": "Invalid signature"},
                        status_code=401,
                    )
            # If the project has a secret but no signature was sent, accept
            # the request anyway (hook may not have a secret configured yet).

        logger.info(
            "Backlog webhook: project=%s event=%s files=%s",
            project_id or "(unmatched)",
            event,
            len(files_changed) if isinstance(files_changed, list) else "?",
        )

        # Invalidate caches so the next dashboard fetch is fresh.
        _api_cache.invalidate("issues:all")
        if project_id:
            _api_cache.invalidate_prefix(f"detail:{project_id}:")

        # Request an orchestrator refresh so the dashboard updates promptly.
        orch.request_refresh()

        # Trigger a git pull + Backlog config sync in a background thread.
        if project:
            threading.Thread(
                target=_sync_project_after_webhook,
                args=(orch, project.id, project.name),
                name=f"backlog-webhook-sync-{project.name}",
                daemon=True,
            ).start()

        return JSONResponse(
            {
                "ok": True,
                "action": "processed",
                "project_id": project_id,
                "event": event,
                "files_changed": len(files_changed) if isinstance(files_changed, list) else 0,
            }
        )

    except Exception as exc:
        logger.error("Backlog webhook error: %s", exc, exc_info=True)
        return JSONResponse(
            {"error": {"code": "webhook_error", "message": str(exc)}},
            status_code=500,
        )


# --- Kanban Dashboard ---


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve the kanban dashboard."""
    return _html_response("dashboard.html")


@app.get("/providers", response_class=HTMLResponse)
async def providers_page():
    """Serve the providers management page."""
    return _html_response("providers.html")


@app.get("/projects-manage", response_class=HTMLResponse)
async def projects_page():
    """Serve the projects management page."""
    return _html_response("projects.html")


# Keep the old dashboard content endpoint for backward compat
@app.get("/dashboard/content", response_class=HTMLResponse)
async def dashboard_content():
    """Return the htmx partial for the status view (legacy)."""
    try:
        orch = _get_orchestrator()
        snapshot = orch.get_snapshot()
    except Exception as exc:
        return HTMLResponse(f'<p class="empty">Error: {exc}</p>')

    counts = snapshot["counts"]
    totals = snapshot["agent_totals"]
    running = snapshot["running"]
    retrying = snapshot["retrying"]
    project_names = {
        p.get("id"): p.get("name")
        for p in snapshot.get("projects", [])
        if isinstance(p, dict) and p.get("id") and p.get("name")
    }

    def fmt_tokens(n: int) -> str:
        if n >= 1_000_000:
            return f"{n / 1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n / 1_000:.1f}K"
        return str(n)

    def fmt_duration(seconds: float) -> str:
        if seconds < 60:
            return f"{seconds:.0f}s"
        if seconds < 3600:
            return f"{seconds / 60:.1f}m"
        return f"{seconds / 3600:.1f}h"

    def fmt_time(iso: str | None) -> str:
        if not iso:
            return "-"
        try:
            dt = datetime.fromisoformat(iso)
            return dt.strftime("%H:%M:%S")
        except (ValueError, TypeError):
            return "-"

    def display_issue_identifier(row: dict[str, Any]) -> str:
        return _display_identifier(
            row["issue_identifier"],
            project_names.get(row.get("project_id")),
        )

    html = f"""
    <div class="stats">
      <div class="stat-card">
        <div class="label">Running</div>
        <div class="value running">{counts["running"]}</div>
      </div>
      <div class="stat-card">
        <div class="label">Retrying</div>
        <div class="value retrying">{counts["retrying"]}</div>
      </div>
      <div class="stat-card">
        <div class="label">Total Tokens</div>
        <div class="value tokens">{fmt_tokens(totals["total_tokens"])}</div>
      </div>
      <div class="stat-card">
        <div class="label">Runtime</div>
        <div class="value">{fmt_duration(totals["seconds_running"])}</div>
      </div>
    </div>
    """

    html += "<h2>Running Sessions</h2>"
    if running:
        html += """
        <table>
          <thead><tr>
            <th>Issue</th><th>State</th><th>Turns</th><th>Last Event</th>
            <th>Last Message</th><th>Started</th><th>Tokens</th>
          </tr></thead>
          <tbody>
        """
        for row in running:
            tokens = row.get("tokens", {})
            html += f"""
            <tr>
              <td class="mono">{_esc(display_issue_identifier(row))}</td>
              <td><span class="badge badge-running">{_esc(row["state"])}</span></td>
              <td>{row["turn_count"]}</td>
              <td class="mono">{_esc(row.get("last_event") or "-")}</td>
              <td class="truncate">{_esc(row.get("last_message") or "-")}</td>
              <td class="mono">{fmt_time(row.get("started_at"))}</td>
              <td class="mono">{fmt_tokens(tokens.get("total_tokens", 0))}</td>
            </tr>
            """
        html += "</tbody></table>"
    else:
        html += '<p class="empty">No running sessions</p>'

    html += "<h2>Retry Queue</h2>"
    if retrying:
        html += """
        <table>
          <thead><tr>
            <th>Issue</th><th>Attempt</th><th>Due At</th><th>Error</th>
          </tr></thead>
          <tbody>
        """
        for row in retrying:
            html += f"""
            <tr>
              <td class="mono">{_esc(row["issue_identifier"])}</td>
              <td>{row["attempt"]}</td>
              <td class="mono">{fmt_time(row.get("due_at"))}</td>
              <td class="truncate"><span class="badge badge-error">{_esc(row.get("error") or "-")}</span></td>
            </tr>
            """
        html += "</tbody></table>"
    else:
        html += '<p class="empty">No pending retries</p>'

    html += (
        f'<p class="updated">Last updated: {fmt_time(snapshot.get("generated_at"))}</p>'
    )
    return HTMLResponse(html)


@app.get("/foci", response_class=HTMLResponse)
async def foci_page():
    """Serve the foci management page."""
    return _html_response("foci.html")


@app.get("/reviews", response_class=HTMLResponse)
async def reviews_page():
    """Serve the reviews (review) listing page."""
    return _html_response("reviews.html")


def _esc(s: str) -> str:
    """Basic HTML escaping."""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
