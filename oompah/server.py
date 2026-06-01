"""FastAPI server with htmx kanban dashboard, JSON REST API, and WebSocket push."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from fastapi import FastAPI, File, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, Response

from oompah.events import EventType
from oompah.scm import detect_provider, extract_repo_slug, get_all_open_reviews
from oompah.webhooks import (
    WebhookEvent,
    match_project_by_repo,
    parse_github_webhook,
    parse_gitlab_webhook,
    validate_github_signature,
    validate_gitlab_token,
)
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
from oompah.issue_enhancer import (
    EnhancementResult,
    IssueEnhancerError,
    enhance_issue,
    has_quality_source,
)
from oompah.models import AgentProfile
from oompah.projects import ProjectError, ProjectStore
from oompah.providers import ProviderStore
from oompah.roles import RoleError, RoleStore
from oompah.statuses import (
    ARCHIVED,
    CANONICAL_STATUSES,
    IN_PROGRESS,
    MERGED,
    NEEDS_ANSWER,
    NEEDS_CI_FIX,
    NEEDS_REBASE,
    OPEN,
    canonicalize_status,
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


app = FastAPI(title="oompah", version="0.1.0")

# Serve static assets (favicon, etc.) from oompah/static/
from fastapi.staticfiles import StaticFiles

_STATIC_DIR = Path(__file__).resolve().parent / "static"
if _STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/favicon.ico")
@app.get("/favicon.svg")
async def favicon():
    """Serve the SVG favicon at both /favicon.ico and /favicon.svg.

    Browsers request /favicon.ico by default; modern browsers will accept
    an SVG response there as long as the Content-Type is correct.
    """
    fav = _STATIC_DIR / "favicon.svg"
    if not fav.is_file():
        return Response(status_code=404)
    return Response(
        content=fav.read_bytes(),
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

_BACKLOG_TASK_IDENTIFIER_RE = re.compile(r"^TASK-(.+)$", re.IGNORECASE)


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
    return {
        "project_name": project_name,
        "display_identifier": _display_identifier(issue.identifier, project_name),
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
    # Error watcher: creates beads for backend/frontend errors
    _error_watcher = ErrorWatcher(orch.tracker)
    _error_watcher.install_log_handler("oompah")
    # Register so the orchestrator can ask it to auto-close transient
    # error beads when an issue's retry path succeeds (oompah-zlz_2-0nc).
    orch.register_error_watcher(_error_watcher, project_id=None)

    # Project log watcher manager: watches log files for projects that set log_path.
    # Each project gets its own ErrorWatcher backed by the project's tracker so
    # error beads are created in the correct project.
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

# Shared response cache for API endpoints
_api_cache = TTLCache()


def _state_key(state: str | None) -> str:
    return canonicalize_status(state).strip().lower().replace("-", "_").replace(" ", "_")


def _dashboard_state(state: str | None) -> str:
    """Map tracker-native states onto dashboard column keys."""
    return _state_key(state)


_DASHBOARD_STATE_KEYS = tuple(_dashboard_state(status) for status in CANONICAL_STATUSES)


def _empty_state_counts() -> dict[str, int]:
    return {key: 0 for key in _DASHBOARD_STATE_KEYS}


def _issue_dashboard_state(issue) -> str:
    if "archive:yes" in (issue.labels or []):
        return _dashboard_state(ARCHIVED)
    return _dashboard_state(issue.state)


def _on_state_only_change(snapshot: dict) -> None:
    """Called on agent activity — broadcast state only, no issues re-fetch."""
    import time

    global _last_state_broadcast
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
    # we can flag in-flight beads. Mirrors api_issues; both paths read
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
            **_issue_display_fields(issue, project_names),
        }
        if issue.id in parents:
            entry["children_counts"] = parents[issue.id]
        result[state].append(entry)
    return result


async def _do_broadcast_issues() -> None:
    """Actually fetch and broadcast issues to all WS clients."""
    global _last_issues_broadcast, _issues_broadcast_pending
    _issues_broadcast_pending = False
    try:
        orch = _get_orchestrator()
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            _api_thread_pool, _fetch_and_serialize_issues, orch
        )
        _last_issues_broadcast = time.monotonic() * 1000
        _api_cache.set("issues:all", result, ttl_ms=5000)
        if _ws_clients:
            await _broadcast({"type": "issues", "data": result})
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
        # Send initial issues (fetch in thread to avoid blocking)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            _api_thread_pool, _fetch_and_serialize_issues, orch
        )
        await ws.send_text(json.dumps({"type": "issues", "data": result}, default=str))

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
    """Return current system state snapshot."""
    try:
        orch = _get_orchestrator()
        return JSONResponse(orch.get_snapshot())
    except Exception as exc:
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
    try:
        t_start = time.monotonic()
        orch = _get_orchestrator()
        filter_project = request.query_params.get("project_id")

        # Serve from cache if fresh and no project filter
        if not filter_project:
            cached = _api_cache.get("issues:all")
            if cached is not None:
                return JSONResponse(cached)

        # Fetch issues from all projects (in dedicated pool to avoid tick contention)
        loop = asyncio.get_event_loop()
        all_issues = await loop.run_in_executor(
            _api_thread_pool, _fetch_all_issues, orch, filter_project
        )
        project_names = _project_names_by_id(orch)
        t_fetch = time.monotonic()
        fetch_ms = (t_fetch - t_start) * 1000
        if fetch_ms > 1000:
            logger.warning(
                "Issues API slow: fetch=%.0fms issues=%d", fetch_ms, len(all_issues)
            )

        # Build a map for epic child counts
        epics: dict[str, dict] = {}
        parent_ids: set[str] = set()
        for issue in all_issues:
            if issue.parent_id:
                parent_ids.add(issue.parent_id)
        for issue in all_issues:
            if issue.id in parent_ids or issue.issue_type == "epic":
                epics[issue.id] = _empty_state_counts()

        # Count children per parent per state
        for issue in all_issues:
            if issue.parent_id and issue.parent_id in epics:
                child_state = _issue_dashboard_state(issue)
                if child_state in epics[issue.parent_id]:
                    epics[issue.parent_id][child_state] += 1

        # Build a quick set of branch names with open (unmerged) reviews
        # so we can flag issues whose work is still in flight on a PR.
        # Falls back to empty set if the orchestrator hasn't done its
        # first review_check tick yet.
        unmerged_branches: set[str] = set(
            getattr(orch, "_unmerged_review_branches", set()) or set()
        )

        result: dict[str, list] = {}
        for issue in all_issues:
            state = _issue_dashboard_state(issue)
            if state not in result:
                result[state] = []
            # has_open_review: True when this issue's branch is among the
            # source branches of currently-open (unmerged) PRs across the
            # project's tracked forge reviews. The dashboard's "show
            # in-flight only" filter uses this to hide closed beads whose
            # work has fully landed (no PR open) while keeping closed
            # beads whose PR is still in queue/CI.
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
                **_issue_display_fields(issue, project_names),
            }
            if issue.id in epics:
                entry["children_counts"] = epics[issue.id]
            result[state].append(entry)
        # Sort each column by priority
        for state in result:
            result[state].sort(
                key=lambda i: i["priority"] if i["priority"] is not None else 999
            )
        if not filter_project:
            _api_cache.set("issues:all", result, ttl_ms=5000)
        return JSONResponse(result)
    except Exception as exc:
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
        tracker = _get_tracker(orch, project_id)

        # Optional enhancement pass (oompah-zlz_2-u8pz).
        enhance_mode = (request.query_params.get("enhance") or "").strip().lower()
        description = body.get("description")
        if enhance_mode in ("true", "apply"):
            try:
                enhancement = _run_issue_enhancement(
                    orch=orch,
                    project_id=project_id,
                    title=title,
                    description=description,
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
        issue = tracker.create_issue(
            title=title,
            issue_type=issue_type,
            description=description,
            priority=body.get("priority"),
            initial_status=body.get("status"),
            parent=parent_id,
        )
        issue.project_id = project_id

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
        has = has_quality_source(repo_path)
        # The kind reported here matches load_quality_source's tag so
        # the dashboard can surface AGENTS.md vs WORKFLOW.md hints.
        kind = ""
        if has:
            from oompah.issue_enhancer import load_quality_source

            kind, _ = load_quality_source(repo_path)
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
    either go through the child-issue flow or be done directly in Backlog.md
    when intentionally bypassing any backend hooks.
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
        if not project_id:
            return JSONResponse(
                {"error": {"code": "validation", "message": "project_id is required"}},
                status_code=400,
            )
        tracker = _get_tracker(orch, project_id)

        new_status = body.get("status")
        new_priority = body.get("priority")
        new_title = body.get("title")
        new_description = body.get("description")

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
            if new_status is not None:
                update_fields["status"] = new_status
            if new_priority is not None:
                update_fields["priority"] = str(new_priority)
            if new_title is not None:
                update_fields["title"] = new_title
            if new_description is not None:
                update_fields["description"] = new_description
            if update_fields:
                tracker.update_issue(identifier, **update_fields)

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
                # scheduled timer doesn't re-dispatch a closed bead later.
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
        project_id = body.get("project_id") or request.query_params.get("project_id")
        tracker = _get_tracker(orch, project_id)
        tracker.add_label(identifier, label)
        _api_cache.invalidate("issues:all")
        _api_cache.invalidate_prefix(f"detail:{project_id}:{identifier}")
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
        project_id = body.get("project_id") or request.query_params.get("project_id")
        tracker = _get_tracker(orch, project_id)
        tracker.remove_label(identifier, label)
        _api_cache.invalidate("issues:all")
        _api_cache.invalidate_prefix(f"detail:{project_id}:{identifier}")
        await broadcast_issues()
        return JSONResponse({"ok": True})
    except Exception as exc:
        logger.error("Remove label API error: %s", exc)
        return JSONResponse(
            {"error": {"code": "label_failed", "message": str(exc)}},
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
        project_id = body.get("project_id") or request.query_params.get("project_id")
        tracker = _get_tracker(orch, project_id)
        result = tracker.add_comment(identifier, text, author=author)

        # When a human (non-oompah) answers a question, move the task
        # back to Open so the orchestrator picks it up.
        if author != "oompah":
            try:
                issue = tracker.fetch_issue_detail(identifier)
                if issue and (
                    canonicalize_status(issue.state) == NEEDS_ANSWER
                    or "asking_question" in issue.labels
                ):
                    tracker.update_issue(identifier, status=OPEN)
                    if "asking_question" in issue.labels:
                        tracker.remove_label(identifier, "asking_question")
                    logger.info(
                        "Moved %s from Needs Answer to Open after user comment",
                        identifier,
                    )
                    # Trigger dispatch so the orchestrator re-dispatches promptly
                    orch = _get_orchestrator()
                    if orch:
                        orch.request_refresh()
            except Exception as exc:
                logger.debug(
                    "Failed to check/remove asking_question label on %s: %s",
                    identifier,
                    exc,
                )

        _api_cache.invalidate(f"comments:{project_id}:{identifier}")
        _api_cache.invalidate_prefix(f"detail:{project_id}:{identifier}")
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
        cache_key = f"detail:{project_id}:{identifier}"
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
        # Use the resolved project_id (may differ from query param if it was None)
        project_id = resolved_project_id
        project_names = _project_names_by_id(orch)
        project_name = project_names.get(project_id or "")
        result = {
            "id": issue.id,
            "identifier": issue.identifier,
            "display_identifier": _display_identifier(issue.identifier, project_name),
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
        }
        if issue.issue_type in ("epic", "feature"):
            children = tracker.fetch_children(issue.id)
            result["children"] = [
                {
                    "id": c.id,
                    "identifier": c.identifier,
                    "display_identifier": _display_identifier(
                        c.identifier,
                        project_names.get(c.project_id or "") or project_name,
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
                        "started_at": entry.started_at.isoformat(),
                        "activity": [a.to_dict() for a in entry.activity_log],
                    }
                )
        return JSONResponse({"identifier": identifier, "activity": []})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/v1/orchestrator/pause")
async def api_orchestrator_pause():
    """Pause the orchestrator (stop dispatching new agents)."""
    try:
        orch = _get_orchestrator()
        orch.pause()
        return JSONResponse({"ok": True, "paused": True})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/v1/orchestrator/resume")
async def api_orchestrator_resume():
    """Resume the orchestrator."""
    try:
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
    """Manually dispatch a specific issue to an agent."""
    try:
        orch = _get_orchestrator()
        candidates = orch._fetch_all_candidates()
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
    that need ProviderStore / ACP-mode awareness — see bead
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

    Validation layers (see bead oompah-zlz_2-rls):

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
    """
    status, message = _resolve_role_status(role, provider_store)
    out: dict = {"role": role_name, "status": status}
    if message is not None:
        out["message"] = message
    if role is not None:
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

    Body shape::

        {
          "fast":     {"provider_id": "prov-X", "model": "..."},
          "standard": {"provider_id": "prov-X", "model": "..."},
          "deep":     {"provider_id": "prov-Y", "model": "..."},
          "default":  {"provider_id": "prov-Z", "model": "..."}
        }

    All four standard roles are required for v1 (extensible role names
    are out of scope for the epic). Each row is validated against
    ProviderStore: provider_id must exist, and model must be in the
    provider's catalog (ACP-mode providers with empty catalogs accept
    any model name).

    Unlike the pre-xau7 role-matrix endpoint, profiles named after the
    role are NOT required to exist — RoleStore is independent of
    AgentProfileStore.

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

    # Phase 1: shape validation. ``model`` may be empty when the
    # provider is ACP-mode with no catalog (Claude SDK et al. — the SDK
    # picks the model from the operator's subscription); the phase-2
    # check below enforces that case.
    errors: list[str] = []
    parsed: dict[str, tuple[str, str]] = {}
    for role in ROLE_MATRIX_KEYS:
        if role not in body:
            errors.append(f"missing role {role!r}")
            continue
        row = body[role]
        if not isinstance(row, dict):
            errors.append(f"role {role!r}: row must be a JSON object")
            continue
        pid = row.get("provider_id")
        model = row.get("model") or ""
        if not isinstance(pid, str) or not pid:
            errors.append(f"role {role!r}: provider_id is required")
            continue
        if not isinstance(model, str):
            errors.append(f"role {role!r}: model must be a string")
            continue
        parsed[role] = (pid, model)
    if errors:
        return JSONResponse(
            {"error": {"code": "validation", "message": "; ".join(errors)}},
            status_code=400,
        )

    # Phase 2: cross-store validation. ACP-mode providers with an empty
    # catalog let model stay empty (SDK-managed); everyone else requires
    # a non-empty model that's in the provider's catalog.
    for role, (pid, model) in parsed.items():
        provider = _provider_store.get(pid)
        if provider is None:
            errors.append(f"role {role!r}: provider_id {pid!r} not found")
            continue
        catalog = list(provider.models or [])
        is_acp_sdk_managed = provider.mode == "acp" and not catalog
        if not model and not is_acp_sdk_managed:
            errors.append(f"role {role!r}: model is required")
            continue
        if catalog and model and model not in catalog:
            errors.append(
                f"role {role!r}: model {model!r} not in provider "
                f"{provider.name!r}'s catalog (have: "
                f"{', '.join(catalog)})"
            )
    if errors:
        return JSONResponse(
            {"error": {"code": "validation", "message": "; ".join(errors)}},
            status_code=400,
        )

    # Phase 3: snapshot + apply + rollback-on-failure.
    snapshot = _role_store.snapshot()
    try:
        for role, (pid, model) in parsed.items():
            _role_store.set(role, pid, model)
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
    """Register a new project (git repo with Backlog.md tasks)."""
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
        project = orch.project_store.create(
            repo_url=repo_url,
            name=name,
            branch=branch,
            branches=branches,
            default_branch=default_branch,
            git_user_name=git_user_name,
            git_user_email=git_user_email,
            access_token=access_token,
        )
        # Sync log watchers in case the new project has a log_path
        if _log_watcher_manager:
            _log_watcher_manager.sync_watchers(orch.project_store.list_all())
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
    foci = load_foci()
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
        # Load existing user foci, replace if same name exists
        foci = load_foci()
        user_foci = [
            f
            for f in foci
            if f.name not in {b.name for b in BUILTIN_FOCI} or f.name == new_focus.name
        ]
        # Actually, just load the user file directly
        import os, json as _json

        user_path = ".oompah/foci.json"
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
    if not os.path.exists(user_path):
        return JSONResponse(
            {
                "error": {
                    "code": "not_found",
                    "message": f"Focus '{name}' not found in user foci",
                }
            },
            status_code=404,
        )
    try:
        with open(user_path, "r") as fp:
            existing = [Focus.from_dict(d) for d in _json.load(fp)]
    except Exception:
        existing = []
    new_list = [f for f in existing if f.name != name]
    if len(new_list) == len(existing):
        return JSONResponse(
            {
                "error": {
                    "code": "not_found",
                    "message": f"Focus '{name}' not found in user foci",
                }
            },
            status_code=404,
        )
    save_foci(new_list)
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

    # Load user foci
    existing: list[Focus] = []
    if os.path.exists(user_path):
        try:
            with open(user_path, "r") as fp:
                existing = [Focus.from_dict(d) for d in _json.load(fp)]
        except Exception:
            pass

    # Find in user foci first
    found = None
    for f in existing:
        if f.name == name:
            found = f
            break

    if not found:
        # Check builtins — create a user override
        for b in BUILTIN_FOCI:
            if b.name == name:
                found = Focus.from_dict(b.to_dict())
                existing.append(found)
                break

    if not found:
        return JSONResponse(
            {"error": {"code": "not_found", "message": f"Focus '{name}' not found"}},
            status_code=404,
        )

    # Apply updates
    for key in ("status", "role", "description"):
        if key in body:
            setattr(found, key, body[key])
    for key in ("must_do", "must_not_do", "keywords", "issue_types", "labels"):
        if key in body:
            setattr(found, key, body[key])
    if "priority" in body:
        try:
            found.priority = int(body["priority"])
        except (ValueError, TypeError):
            pass
    # Optional model overrides — empty string clears the override.
    for key in ("model_role", "model", "provider_id"):
        if key in body:
            v = body[key]
            if v is None or (isinstance(v, str) and not v.strip()):
                setattr(found, key, None)
            else:
                setattr(found, key, str(v).strip())
    if "allow_image_output" in body:
        found.allow_image_output = bool(body["allow_image_output"])

    save_foci(existing, user_path)
    return JSONResponse(found.to_dict())


@app.get("/api/v1/foci/suggestions")
async def api_list_focus_suggestions():
    """List focus suggestions generated by the analyzer."""
    suggestions = load_suggestions()
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
    if update_suggestion_status(name, status):
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
        cached = _api_cache.get("reviews:all")
        if cached is not None:
            return JSONResponse(cached)
        orch = _get_orchestrator()
        projects = orch.project_store.list_all()
        # Index projects by id for fast lookup in the loop below.
        _project_by_id = {p.id: p for p in projects}
        reviews = get_all_open_reviews(projects)
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
            notified_issue = _notify_conflict_on_bead(
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


def _notify_conflict_on_bead(
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
    """List the attachments recorded on an issue (rich records from beads
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
    import tempfile

    contents = await file.read()
    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=ext,
        dir=tempfile.gettempdir(),
    ) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        store = AttachmentStore(project.repo_path)
        try:
            rec = store.add(identifier, tmp_path, mime_type=mime, added_by="user")
        except AttachmentTooLarge as exc:
            return JSONResponse(
                {"error": {"code": "payload_too_large", "message": str(exc)}},
                status_code=413,
            )
        except AttachmentMimeRejected as exc:
            return JSONResponse(
                {"error": {"code": "unsupported_media_type", "message": str(exc)}},
                status_code=415,
            )

        # Update beads metadata: append the new record to the existing list.
        existing = []
        try:
            existing = list(tracker.fetch_attachments(identifier) or [])
        except Exception:
            pass
        merged = existing + [rec.to_dict()]
        tracker.set_attachments(identifier, merged, project_root=project.repo_path)

        # Commit the file so it travels with the repo.
        try:
            store.commit(
                [rec.path],
                f"Add attachment {os.path.basename(rec.path)} for {identifier}",
            )
        except Exception as exc:
            logger.warning("attachment commit failed for %s: %s", identifier, exc)

        return JSONResponse(rec.to_dict(), status_code=201)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


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
    try:
        with open(abs_path, "rb") as f:
            data = f.read()
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
    """Accept error reports from the frontend and create beads."""
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

    # Invalidate caches and trigger a refresh cycle
    _api_cache.invalidate("reviews:all")
    _api_cache.invalidate("issues:all")
    if event.merged:
        orch.invalidate_merged_branches()
    orch.request_refresh()

    # If the webhook signals that the project's tracked branch advanced
    # (push to that branch, or PR merged into it), pull the latest source
    # and beads state. Without this, new commits — including beads
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
    # destroyed + merged=True), label the corresponding bead as merged and
    # trigger a source sync.  This is the queue-mode equivalent of the
    # direct-merge path that fires on PR closed+merged webhooks.
    if event.event_type == "merge_group" and event.merged and project:
        threading.Thread(
            target=_label_bead_merged_from_merge_group,
            args=(orch, event, project),
            name=f"merge-group-label-{project.name}",
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


def _label_bead_merged_from_merge_group(orch, event, project) -> None:
    """Label the bead as merged when a merge_group destroyed event signals success.

    The merge_group ``head_ref`` is ``gh-readonly-queue/<base>/<pr-identifier>``
    where ``<pr-identifier>`` encodes the source branch name.  We parse out
    the branch name and match it to a closed bead so it gets the ``merged``
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
    # prefix used to identify the bead.
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
        # The bead identifier follows "pr-<N>-" prefix.
        tail = parts[3]
        dash_parts = tail.split("-", 2)
        if len(dash_parts) >= 3:
            branch_name = dash_parts[2]
        else:
            branch_name = tail

    try:
        tracker = orch._tracker_for_project(project.id)
        issue = tracker.fetch_issue_detail(branch_name)
        if issue is None:
            logger.debug(
                "merge_group: no bead found for branch %r (head_ref=%r)",
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
            "merge_group: failed to label bead for head_ref %r: %s",
            head_ref,
            exc,
        )


def _sync_project_after_webhook(
    orch,
    project_id: str,
    project_name: str,
) -> None:
    """Pull source + validate Backlog.md config for one project after a webhook.

    Best-effort: any failure is logged but does not raise. The next
    service restart's startup sync remains the safety net.
    """
    try:
        status = orch.project_store.sync_project_sources(project_id)
        logger.info(
            "Webhook sync %s: git=%s backlog=%s",
            project_name,
            status.get("git", "?"),
            status.get("backlog", "?"),
        )
    except Exception as exc:
        logger.warning("Webhook sync failed for %s: %s", project_name, exc)


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


# --- Kanban Dashboard ---


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve the kanban dashboard."""
    return _load_template("dashboard.html")


@app.get("/providers", response_class=HTMLResponse)
async def providers_page():
    """Serve the providers management page."""
    return _load_template("providers.html")


@app.get("/projects-manage", response_class=HTMLResponse)
async def projects_page():
    """Serve the projects management page."""
    return _load_template("projects.html")


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
    return _load_template("foci.html")


@app.get("/reviews", response_class=HTMLResponse)
async def reviews_page():
    """Serve the reviews (review) listing page."""
    return _load_template("reviews.html")


def _esc(s: str) -> str:
    """Basic HTML escaping."""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
