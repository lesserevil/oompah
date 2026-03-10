"""FastAPI server with htmx kanban dashboard, JSON REST API, and WebSocket push."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse

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
    BUILTIN_FOCI, DEFAULT_FOCUS, Focus, FocusSuggestion,
    load_foci, load_suggestions, save_foci, score_focus,
    update_suggestion_status,
)
from oompah.cache import TTLCache
from oompah.error_watcher import ErrorWatcher, ProjectLogWatcherManager
from oompah.projects import ProjectError, ProjectStore
from oompah.providers import ProviderStore

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

# Global provider store
_provider_store = ProviderStore()

# Global reference to orchestrator, set during startup
_orchestrator: Orchestrator | None = None

# Error watcher — created when orchestrator is set
_error_watcher: ErrorWatcher | None = None

# Project log watcher manager — watches log files for all projects
_log_watcher_manager: ProjectLogWatcherManager | None = None

# Connected WebSocket clients
_ws_clients: set[WebSocket] = set()


def set_orchestrator(orch: Orchestrator) -> None:
    global _orchestrator, _error_watcher, _log_watcher_manager
    _orchestrator = orch
    # Full observer: state + issues refresh (for dispatch, close, state changes)
    orch._observers.append(_on_orchestrator_change)
    # State-only observer: state broadcast without issues re-fetch (for agent activity)
    orch._state_only_observers.append(_on_state_only_change)
    orch._activity_observers.append(_on_agent_activity)
    # Error watcher: creates beads for backend/frontend errors
    _error_watcher = ErrorWatcher(orch.tracker)
    _error_watcher.install_log_handler("oompah")

    # Project log watcher manager: watches log files for projects that set log_path.
    # Each project gets its own ErrorWatcher backed by the project's tracker so
    # error beads are created in the correct project.
    def _make_error_watcher(project_id: str) -> ErrorWatcher:
        tracker = orch._tracker_for_project(project_id)
        return ErrorWatcher(tracker, project_id=project_id)

    _log_watcher_manager = ProjectLogWatcherManager(_make_error_watcher)
    _log_watcher_manager.sync_watchers(orch.project_store.list_all())


def _get_orchestrator() -> Orchestrator:
    if _orchestrator is None:
        raise RuntimeError("Orchestrator not initialized")
    return _orchestrator


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
            loop.create_task(_broadcast({
                "type": "activity",
                "identifier": identifier,
                "entry": entry.to_dict() if hasattr(entry, 'to_dict') else str(entry),
            }))
    except RuntimeError:
        pass


def _fetch_and_serialize_issues(orch) -> dict[str, list]:
    """Fetch all issues and serialize — runs in thread pool to avoid blocking."""
    all_issues = _fetch_all_issues(orch, None)

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
            parents[issue.id] = {"deferred": 0, "open": 0, "in_progress": 0, "closed": 0}
    for issue in all_issues:
        if issue.parent_id and issue.parent_id in parents:
            child_state = issue.state.strip().lower()
            if child_state in parents[issue.parent_id]:
                parents[issue.parent_id][child_state] += 1

    result: dict[str, list] = {}
    for issue in all_issues:
        if "archive:yes" in issue.labels:
            continue
        state = issue.state.strip().lower()
        if state not in result:
            result[state] = []
        entry = {
            "id": issue.id,
            "identifier": issue.identifier,
            "title": issue.title,
            "description": issue.description,
            "priority": issue.priority,
            "state": issue.state,
            "labels": issue.labels,
            "issue_type": issue.issue_type,
            "parent_id": issue.parent_id,
            "project_id": issue.project_id,
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
        await ws.send_text(json.dumps(
            {"type": "state", "data": orch.get_snapshot()}, default=str))
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
                    await ws.send_text(json.dumps(
                        {"type": "state", "data": orch.get_snapshot()}, default=str))
                    await broadcast_issues()
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        _ws_clients.discard(ws)
        logger.info("WebSocket client disconnected (%d remaining)", len(_ws_clients))


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
        t_fetch = time.monotonic()
        fetch_ms = (t_fetch - t_start) * 1000
        if fetch_ms > 1000:
            logger.warning("Issues API slow: fetch=%.0fms issues=%d",
                           fetch_ms, len(all_issues))

        # Build a map for epic child counts
        epics: dict[str, dict] = {}
        parent_ids: set[str] = set()
        for issue in all_issues:
            if issue.parent_id:
                parent_ids.add(issue.parent_id)
        for issue in all_issues:
            if issue.id in parent_ids or issue.issue_type == "epic":
                epics[issue.id] = {"deferred": 0, "open": 0, "in_progress": 0, "closed": 0}

        # Count children per parent per state
        for issue in all_issues:
            if issue.parent_id and issue.parent_id in epics:
                child_state = issue.state.strip().lower()
                if child_state in epics[issue.parent_id]:
                    epics[issue.parent_id][child_state] += 1

        result: dict[str, list] = {}
        for issue in all_issues:
            # Hide archived issues
            if "archive:yes" in issue.labels:
                continue
            state = issue.state.strip().lower()
            if state not in result:
                result[state] = []
            entry = {
                "id": issue.id,
                "identifier": issue.identifier,
                "title": issue.title,
                "description": issue.description,
                "priority": issue.priority,
                "state": issue.state,
                "labels": issue.labels,
                "issue_type": issue.issue_type,
                "parent_id": issue.parent_id,
                "project_id": issue.project_id,
            }
            if issue.id in epics:
                entry["children_counts"] = epics[issue.id]
            result[state].append(entry)
        # Sort each column by priority
        for state in result:
            result[state].sort(key=lambda i: i["priority"] if i["priority"] is not None else 999)
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


@app.post("/api/v1/issues")
async def api_create_issue(request: Request):
    """Create a new issue."""
    try:
        orch = _get_orchestrator()
        body = await request.json()

        title = body.get("title", "").strip()
        if not title:
            return JSONResponse(
                {"error": {"code": "validation", "message": "Title is required"}},
                status_code=400,
            )

        project_id = body.get("project_id")
        tracker = _get_tracker(orch, project_id)

        issue_type = body.get("type", "task")
        issue = tracker.create_issue(
            title=title,
            issue_type=issue_type,
            description=body.get("description"),
            priority=body.get("priority"),
            initial_status=body.get("status"),
        )
        issue.project_id = project_id

        # Auto-add 'draft' label to new epics so they appear in the kanban
        if issue_type == "epic":
            tracker.add_label(issue.identifier, "draft")

        # Link to parent epic if specified
        parent_id = body.get("parent_id")
        if parent_id:
            tracker.add_parent_child(issue.id, parent_id)

        _api_cache.invalidate("issues:all")
        await broadcast_issues()
        return JSONResponse({
            "ok": True,
            "issue": {
                "id": issue.id,
                "identifier": issue.identifier,
                "title": issue.title,
                "state": issue.state,
            },
        }, status_code=201)
    except Exception as exc:
        logger.error("Create issue API error: %s", exc)
        return JSONResponse(
            {"error": {"code": "create_failed", "message": str(exc)}},
            status_code=500,
        )


@app.patch("/api/v1/issues/{identifier}")
async def api_update_issue(identifier: str, request: Request):
    """Update an issue's state, priority, or title."""
    try:
        orch = _get_orchestrator()
        body = await request.json()
        project_id = body.get("project_id") or request.query_params.get("project_id")
        tracker = _get_tracker(orch, project_id)

        new_status = body.get("status")
        new_priority = body.get("priority")
        new_title = body.get("title")
        new_description = body.get("description")

        if new_status == "closed":
            tracker.close_issue(identifier)
        elif new_status is not None:
            tracker.update_issue(identifier, status=new_status)

        if new_priority is not None:
            tracker.update_issue(identifier, priority=str(new_priority))

        if new_title is not None:
            tracker.update_issue(identifier, title=new_title)

        if new_description is not None:
            tracker.update_issue(identifier, description=new_description)

        # Terminate agent whenever issue is moved away from in_progress
        if new_status is not None:
            terminal = {s.strip().lower() for s in orch.config.tracker_terminal_states}
            status_norm = new_status.strip().lower()
            if status_norm != "in_progress":
                for issue_id, entry in list(orch.state.running.items()):
                    if entry.identifier == identifier:
                        logger.info("Terminating agent for %s (moved to %s via UI)", identifier, new_status)
                        await orch._terminate_running(issue_id, cleanup_workspace=(status_norm in terminal))
                        break

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
        body = await request.json()
        label = body.get("label", "").strip()
        if not label:
            return JSONResponse(
                {"error": {"code": "validation", "message": "label is required"}},
                status_code=400,
            )
        project_id = body.get("project_id")
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
        project_id = request.query_params.get("project_id")
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
    """Return comments for an issue."""
    try:
        orch = _get_orchestrator()
        project_id = request.query_params.get("project_id")
        cache_key = f"comments:{project_id}:{identifier}"
        cached = _api_cache.get(cache_key)
        if cached is not None:
            return JSONResponse(cached)
        tracker = _get_tracker(orch, project_id)
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
        body = await request.json()
        text = body.get("text", "").strip()
        if not text:
            return JSONResponse(
                {"error": {"code": "validation", "message": "Comment text is required"}},
                status_code=400,
            )
        author = body.get("author", "user")
        project_id = body.get("project_id")
        tracker = _get_tracker(orch, project_id)
        result = tracker.add_comment(identifier, text, author=author)

        # When a human (non-oompah) answers a question, remove the
        # asking_question label so the orchestrator picks it back up.
        if author != "oompah":
            try:
                issue = tracker.fetch_issue_detail(identifier)
                if issue and "asking_question" in issue.labels:
                    tracker.remove_label(identifier, "asking_question")
                    logger.info(
                        "Removed asking_question label from %s after user comment",
                        identifier,
                    )
            except Exception as exc:
                logger.debug(
                    "Failed to check/remove asking_question label on %s: %s",
                    identifier, exc,
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
    """Return full issue detail for the slide-out panel."""
    try:
        orch = _get_orchestrator()
        project_id = request.query_params.get("project_id")
        cache_key = f"detail:{project_id}:{identifier}"
        cached = _api_cache.get(cache_key)
        if cached is not None:
            return JSONResponse(cached)
        tracker = _get_tracker(orch, project_id)
        issue = tracker.fetch_issue_detail(identifier)
        if issue is None:
            return JSONResponse(
                {"error": {"code": "issue_not_found", "message": f"Issue {identifier} not found"}},
                status_code=404,
            )
        result = {
            "id": issue.id,
            "identifier": issue.identifier,
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
                    "title": c.title,
                    "state": c.state,
                    "priority": c.priority,
                    "issue_type": c.issue_type,
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
                return JSONResponse({
                    "identifier": identifier,
                    "profile": entry.agent_profile_name,
                    "started_at": entry.started_at.isoformat(),
                    "activity": [a.to_dict() for a in entry.activity_log],
                })
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
        return JSONResponse({
            "ok": True,
            "draining": running_count,
            "drain_timeout_s": drain_timeout,
        })
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
            return JSONResponse({"error": f"Issue {identifier} not found or not dispatchable"}, status_code=404)
        await orch._dispatch(issue, attempt=None)
        return JSONResponse({"ok": True, "dispatched": identifier})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/v1/providers")
async def api_list_providers():
    """List all configured model providers."""
    providers = _provider_store.list_all()
    return JSONResponse([p.to_safe_dict() for p in providers])


@app.post("/api/v1/providers")
async def api_create_provider(request: Request):
    """Create a new model provider."""
    try:
        body = await request.json()
        name = body.get("name", "").strip()
        base_url = body.get("base_url", "").strip()
        if not name or not base_url:
            return JSONResponse(
                {"error": {"code": "validation", "message": "Name and base_url are required"}},
                status_code=400,
            )
        provider = _provider_store.create(
            name=name,
            base_url=base_url,
            api_key=body.get("api_key", ""),
            models=body.get("models", []),
            default_model=body.get("default_model"),
            provider_type=body.get("provider_type", "openai"),
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
    """Update a model provider."""
    try:
        body = await request.json()
        fields = {}
        for key in ("name", "base_url", "api_key", "models", "default_model", "provider_type", "model_roles", "model_costs"):
            if key in body:
                fields[key] = body[key]
        provider = _provider_store.update(provider_id, **fields)
        if not provider:
            return JSONResponse(
                {"error": {"code": "not_found", "message": f"Provider {provider_id} not found"}},
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
        {"error": {"code": "not_found", "message": f"Provider {provider_id} not found"}},
        status_code=404,
    )


@app.post("/api/v1/providers/fetch-models")
async def api_fetch_models(req: Request):
    """Proxy to fetch models from a provider's /models endpoint."""
    import asyncio, urllib.request, ssl
    data = await req.json()
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


# --- Project API ---


@app.get("/api/v1/projects")
async def api_list_projects():
    """List all configured projects."""
    orch = _get_orchestrator()
    return JSONResponse([p.to_dict() for p in orch.project_store.list_all()])


@app.post("/api/v1/projects")
async def api_create_project(request: Request):
    """Register a new project (git repo with beads)."""
    try:
        orch = _get_orchestrator()
        body = await request.json()
        repo_url = body.get("repo_url", "").strip()
        if not repo_url:
            return JSONResponse(
                {"error": {"code": "validation", "message": "repo_url is required"}},
                status_code=400,
            )
        name = body.get("name", "").strip() or None  # None = auto from URL
        branch = body.get("branch", "main").strip()
        git_user_name = body.get("git_user_name", "").strip() or None
        git_user_email = body.get("git_user_email", "").strip() or None
        project = orch.project_store.create(
            repo_url=repo_url, name=name, branch=branch,
            git_user_name=git_user_name, git_user_email=git_user_email,
        )
        # Sync log watchers in case the new project has a log_path
        if _log_watcher_manager:
            _log_watcher_manager.sync_watchers(orch.project_store.list_all())
        return JSONResponse(project.to_dict(), status_code=201)
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
            {"error": {"code": "not_found", "message": f"Project {project_id} not found"}},
            status_code=404,
        )
    return JSONResponse(project.to_dict())


@app.patch("/api/v1/projects/{project_id}")
async def api_update_project(project_id: str, request: Request):
    """Update a project's mutable fields."""
    try:
        orch = _get_orchestrator()
        body = await request.json()
        fields = {}
        for key in ("name", "repo_url", "branch", "git_user_name", "git_user_email", "log_path", "webhook_secret"):
            if key in body:
                fields[key] = body[key]
        if "yolo" in body:
            fields["yolo"] = bool(body["yolo"])
        project = orch.project_store.update(project_id, **fields)
        if not project:
            return JSONResponse(
                {"error": {"code": "not_found", "message": f"Project {project_id} not found"}},
                status_code=404,
            )
        # Sync log watchers when project settings change (log_path may have been added/changed/removed)
        if _log_watcher_manager:
            _log_watcher_manager.sync_watchers(orch.project_store.list_all())
        return JSONResponse(project.to_dict())
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
        body = await request.json()
        new_focus = Focus.from_dict(body)
        if not new_focus.name:
            return JSONResponse(
                {"error": {"code": "validation", "message": "name is required"}},
                status_code=400,
            )
        # Load existing user foci, replace if same name exists
        foci = load_foci()
        user_foci = [f for f in foci if f.name not in {b.name for b in BUILTIN_FOCI} or f.name == new_focus.name]
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
            {"error": {"code": "not_found", "message": f"Focus '{name}' not found in user foci"}},
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
            {"error": {"code": "not_found", "message": f"Focus '{name}' not found in user foci"}},
            status_code=404,
        )
    save_foci(new_list)
    return JSONResponse({"deleted": name})


@app.patch("/api/v1/foci/{name}")
async def api_update_focus(name: str, request: Request):
    """Update a focus (status, fields). For builtins, creates a user override."""
    import os, json as _json
    user_path = ".oompah/foci.json"
    body = await request.json()
    new_status = body.get("status")
    if new_status and new_status not in ("active", "inactive", "proposed"):
        return JSONResponse(
            {"error": {"code": "validation", "message": "status must be active, inactive, or proposed"}},
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
    body = await request.json()
    status = body.get("status", "")
    if status not in ("accepted", "dismissed"):
        return JSONResponse(
            {"error": {"code": "validation", "message": "status must be 'accepted' or 'dismissed'"}},
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
        return JSONResponse({
            "budget": snapshot["budget"],
            "cost_by_profile": snapshot["cost_by_profile"],
            "agent_profiles": snapshot["agent_profiles"],
        })
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
        reviews = get_all_open_reviews(projects)
        # Enrich reviews with agent status
        active_branches = {
            entry.issue.identifier
            for entry in orch.state.running.values()
            if entry.issue
        }
        for item in reviews:
            r = item.get("review", {})
            item["agent_active"] = r.get("source_branch", "") in active_branches
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
    original bead (by matching the review source branch to bead identifiers),
    posts a comment about the conflict, and reopens the bead so the
    agent can resolve it on its own branch.
    """
    try:
        orch = _get_orchestrator()
        project = orch.project_store.get(project_id)
        if not project:
            return JSONResponse(
                {"error": {"code": "not_found", "message": f"Project {project_id} not found"}},
                status_code=404,
            )
        provider = detect_provider(project.repo_url)
        if not provider:
            return JSONResponse(
                {"error": {"code": "unsupported", "message": "No SCM provider detected for this project"}},
                status_code=400,
            )
        slug = extract_repo_slug(project.repo_url)
        success, message = provider.rebase_review(slug, review_id)

        notified_issue = None
        if not success and "conflict" in message.lower():
            # Try to find and notify the original bead
            notified_issue = _notify_conflict_on_bead(
                orch, project_id, provider, slug, review_id,
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
    """Move a bead back to 'open' so its agent retries (e.g. after CI failure).

    Matches the review source branch to a bead identifier, moves it to open,
    and adds a comment instructing the agent to fix CI failures.
    """
    try:
        orch = _get_orchestrator()
        project = orch.project_store.get(project_id)
        if not project:
            return JSONResponse(
                {"error": {"code": "not_found", "message": f"Project {project_id} not found"}},
                status_code=404,
            )
        provider = detect_provider(project.repo_url)
        if not provider:
            return JSONResponse(
                {"error": {"code": "unsupported", "message": "No SCM provider detected"}},
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
            # No existing bead — create one for this external review
            matched = tracker.create_issue(
                title=f"Fix CI: {review.title or branch}",
                issue_type="bug",
                description=(
                    f"Auto-created bead for external review #{review_id} "
                    f"(branch: {branch}).\n\n"
                    f"URL: {review.url or 'N/A'}"
                ),
                priority=0,
                initial_status="open",
            )
            logger.info("Created bead %s for external review #%s (branch %s)",
                         matched.identifier, review_id, branch)
        else:
            tracker.update_issue(matched.identifier, status="open", priority="0")
        tracker.add_label(matched.identifier, "ci-fix")
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
    orch, project_id: str, provider, slug: str, review_id: str,
) -> str | None:
    """Find the bead that owns a review's source branch, comment, and reopen.

    Returns the bead identifier if found and notified, else None.
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

        # The branch name is the sanitized bead identifier.
        # Look up the bead by trying the branch name as an identifier.
        tracker = orch._tracker_for_project(project_id)
        issue = tracker.fetch_issue_detail(source_branch)
        if not issue:
            # No existing bead — create one for this external review
            review_title = review.title or source_branch
            issue = tracker.create_issue(
                title=f"Resolve conflicts: {review_title}",
                issue_type="bug",
                description=(
                    f"Auto-created bead for external review #{review_id} "
                    f"(branch: {source_branch}) which has merge conflicts.\n\n"
                    f"URL: {review.url or 'N/A'}"
                ),
                priority=0,
                initial_status="open",
            )
            logger.info("Created bead %s for external review #%s conflict (branch %s)",
                         issue.identifier, review_id, source_branch)

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

        # Add merge-conflict label so the focus system picks the right role
        try:
            tracker.update_issue(issue.identifier, **{"add-label": "merge-conflict"})
        except Exception as label_exc:
            logger.warning("Failed to add merge-conflict label to %s: %s",
                         issue.identifier, label_exc)

        # Reopen the bead if it's in a terminal state
        state_lower = issue.state.strip().lower()
        if state_lower in [s.lower() for s in orch.config.tracker_terminal_states]:
            tracker.reopen_issue(issue.identifier)
            tracker.update_issue(issue.identifier, priority="0")
            logger.info(
                "Reopened bead %s as P0 for merge conflict resolution (review #%s)",
                issue.identifier, review_id,
            )
        else:
            logger.info(
                "Commented on bead %s about merge conflict (review #%s), already in state '%s'",
                issue.identifier, review_id, issue.state,
            )

        return issue.identifier

    except Exception as exc:
        logger.warning("Failed to notify bead about conflict for review #%s: %s", review_id, exc)
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


@app.post("/api/v1/errors")
async def api_report_error(request: Request):
    """Accept error reports from the frontend and create beads."""
    if not _error_watcher:
        return JSONResponse(
            {"error": {"code": "unavailable", "message": "Error watcher not initialized"}},
            status_code=503,
        )
    body = await request.json()
    message = body.get("message", "").strip()
    if not message:
        return JSONResponse(
            {"error": {"code": "bad_request", "message": "message is required"}},
            status_code=400,
        )
    source = body.get("source", "frontend")
    detail = body.get("detail")
    priority = body.get("priority", 3)
    identifier = _error_watcher.report_error(
        source=source,
        message=message,
        detail=detail,
        priority=priority,
    )
    return JSONResponse({
        "created": identifier is not None,
        "identifier": identifier,
        "deduplicated": identifier is None,
    })


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
    orch.request_refresh()


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
            return JSONResponse({"ok": True, "action": "ignored", "event_type": event_type})

        # Find matching project
        orch = _get_orchestrator()
        projects = orch.project_store.list_all()
        project = match_project_by_repo(projects, event.repo_slug, "github")

        # Validate signature if project has a webhook_secret
        if project and project.webhook_secret:
            if not validate_github_signature(body_bytes, signature, project.webhook_secret):
                logger.warning(
                    "GitHub webhook signature validation failed for %s (delivery=%s)",
                    event.repo_slug, delivery_id,
                )
                return JSONResponse(
                    {"error": "Invalid signature"},
                    status_code=401,
                )

        _handle_webhook_event(event, project)
        return JSONResponse({
            "ok": True,
            "action": "processed",
            "event_type": event_type,
            "delivery_id": delivery_id,
            "review_id": event.review_id,
            "pr_action": event.action,
        })

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
            return JSONResponse({"ok": True, "action": "ignored", "event_type": event_type})

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
        return JSONResponse({
            "ok": True,
            "action": "processed",
            "event_type": event_type,
            "review_id": event.review_id,
            "mr_action": event.action,
        })

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

    html = f"""
    <div class="stats">
      <div class="stat-card">
        <div class="label">Running</div>
        <div class="value running">{counts['running']}</div>
      </div>
      <div class="stat-card">
        <div class="label">Retrying</div>
        <div class="value retrying">{counts['retrying']}</div>
      </div>
      <div class="stat-card">
        <div class="label">Total Tokens</div>
        <div class="value tokens">{fmt_tokens(totals['total_tokens'])}</div>
      </div>
      <div class="stat-card">
        <div class="label">Runtime</div>
        <div class="value">{fmt_duration(totals['seconds_running'])}</div>
      </div>
    </div>
    """

    html += '<h2>Running Sessions</h2>'
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
              <td class="mono">{_esc(row['issue_identifier'])}</td>
              <td><span class="badge badge-running">{_esc(row['state'])}</span></td>
              <td>{row['turn_count']}</td>
              <td class="mono">{_esc(row.get('last_event') or '-')}</td>
              <td class="truncate">{_esc(row.get('last_message') or '-')}</td>
              <td class="mono">{fmt_time(row.get('started_at'))}</td>
              <td class="mono">{fmt_tokens(tokens.get('total_tokens', 0))}</td>
            </tr>
            """
        html += "</tbody></table>"
    else:
        html += '<p class="empty">No running sessions</p>'

    html += '<h2>Retry Queue</h2>'
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
              <td class="mono">{_esc(row['issue_identifier'])}</td>
              <td>{row['attempt']}</td>
              <td class="mono">{fmt_time(row.get('due_at'))}</td>
              <td class="truncate"><span class="badge badge-error">{_esc(row.get('error') or '-')}</span></td>
            </tr>
            """
        html += "</tbody></table>"
    else:
        html += '<p class="empty">No pending retries</p>'

    html += f'<p class="updated">Last updated: {fmt_time(snapshot.get("generated_at"))}</p>'
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
