<<<<<<< HEAD
"""FastAPI server with htmx kanban dashboard, JSON REST API, and WebSocket push."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse

from oompah.scm import detect_provider, extract_repo_slug, get_all_open_reviews
from oompah.focus import (
    BUILTIN_FOCI, DEFAULT_FOCUS, Focus, FocusSuggestion,
    load_foci, load_suggestions, save_foci, score_focus,
    update_suggestion_status,
)
from oompah.projects import ProjectError, ProjectStore
from oompah.providers import ProviderStore

if TYPE_CHECKING:
    from oompah.orchestrator import Orchestrator

logger = logging.getLogger(__name__)

app = FastAPI(title="oompah", version="0.1.0")

# Global provider store
_provider_store = ProviderStore()

# Global reference to orchestrator, set during startup
_orchestrator: Orchestrator | None = None

# Connected WebSocket clients
_ws_clients: set[WebSocket] = set()


def set_orchestrator(orch: Orchestrator) -> None:
    global _orchestrator
    _orchestrator = orch
    # Register as observer so we push on every state change
    orch._observers.append(_on_orchestrator_change)
    orch._activity_observers.append(_on_agent_activity)


def _get_orchestrator() -> Orchestrator:
    if _orchestrator is None:
        raise RuntimeError("Orchestrator not initialized")
    return _orchestrator


_last_state_broadcast = 0.0
_last_issues_broadcast = 0.0
_ISSUES_THROTTLE_MS = 3000  # Don't fetch/broadcast issues more than every 3s
_issues_broadcast_pending = False
_STATE_THROTTLE_MS = 500  # Don't broadcast state more than every 500ms

def _on_orchestrator_change(snapshot: dict) -> None:
    """Called by the orchestrator whenever state changes. Enqueue WS broadcast."""
    import time
    global _last_state_broadcast
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
    result: dict[str, list] = {}
    for issue in all_issues:
        if "archive:yes" in issue.labels:
            continue
        state = issue.state.strip().lower()
        if state not in result:
            result[state] = []
        result[state].append({
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
        })
    return result


async def _do_broadcast_issues() -> None:
    """Actually fetch and broadcast issues to all WS clients."""
    global _last_issues_broadcast, _issues_broadcast_pending
    _issues_broadcast_pending = False
    if not _ws_clients:
        return
    try:
        orch = _get_orchestrator()
        result = await asyncio.to_thread(_fetch_and_serialize_issues, orch)
        _last_issues_broadcast = time.monotonic() * 1000
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
        result = await asyncio.to_thread(_fetch_and_serialize_issues, orch)
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
        orch = _get_orchestrator()
        filter_project = request.query_params.get("project_id")

        # Fetch issues from all projects (in thread to avoid blocking)
        all_issues = await asyncio.to_thread(_fetch_all_issues, orch, filter_project)

        # Build a map for epic child counts
        epics: dict[str, dict] = {}
        for issue in all_issues:
            if issue.issue_type == "epic":
                epics[issue.id] = {"deferred": 0, "open": 0, "in_progress": 0, "closed": 0}

        # Count children per epic per state
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
            if issue.issue_type == "epic" and issue.id in epics:
                entry["children_counts"] = epics[issue.id]
            result[state].append(entry)
        # Sort each column by priority
        for state in result:
            result[state].sort(key=lambda i: i["priority"] if i["priority"] is not None else 999)
        return JSONResponse(result)
    except Exception as exc:
        logger.error("Issues API error: %s", exc)
        return JSONResponse(
            {"error": {"code": "unavailable", "message": str(exc)}},
            status_code=503,
        )


def _get_tracker(orch, project_id: str | None = None):
    """Get the appropriate tracker for a project_id, falling back to legacy."""
    if project_id:
        return orch._tracker_for_project(project_id)
    return orch.tracker


def _fetch_all_issues(orch, filter_project: str | None = None):
    """Fetch issues from all projects or a specific one."""
    from oompah.tracker import TrackerError

    projects = orch.project_store.list_all()
    if not projects:
        # No projects configured — legacy mode
        return orch.tracker.fetch_all_issues()

    all_issues = []
    for project in projects:
        if filter_project and project.id != filter_project:
            continue
        try:
            tracker = orch._tracker_for_project(project.id)
            issues = tracker.fetch_all_issues()
            for issue in issues:
                issue.project_id = project.id
            all_issues.extend(issues)
        except (TrackerError, ProjectError) as exc:
            logger.error("Fetch issues failed for project %s: %s", project.name, exc)
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

        issue = tracker.create_issue(
            title=title,
            issue_type=body.get("type", "task"),
            description=body.get("description"),
            priority=body.get("priority"),
            initial_status=body.get("status"),
        )
        issue.project_id = project_id

        # Link to parent epic if specified
        parent_id = body.get("parent_id")
        if parent_id:
            tracker.add_parent_child(issue.id, parent_id)

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

        # Immediately terminate agent if issue moved to terminal or non-active state
        if new_status is not None:
            terminal = {s.strip().lower() for s in orch.config.tracker_terminal_states}
            active = {s.strip().lower() for s in orch.config.tracker_active_states}
            status_norm = new_status.strip().lower()
            if status_norm in terminal or status_norm not in active:
                # Find running entry by identifier and terminate
                for issue_id, entry in list(orch.state.running.items()):
                    if entry.identifier == identifier:
                        logger.info("Terminating agent for %s (moved to %s via UI)", identifier, new_status)
                        await orch._terminate_running(issue_id, cleanup_workspace=(status_norm in terminal))
                        break

        await broadcast_issues()
        return JSONResponse({"ok": True})
    except Exception as exc:
        logger.error("Update issue API error: %s", exc)
        return JSONResponse(
            {"error": {"code": "update_failed", "message": str(exc)}},
            status_code=500,
        )


@app.get("/api/v1/issues/{identifier}/comments")
async def api_get_comments(identifier: str, request: Request):
    """Return comments for an issue."""
    try:
        orch = _get_orchestrator()
        project_id = request.query_params.get("project_id")
        tracker = _get_tracker(orch, project_id)
        comments = tracker.fetch_comments(identifier)
        return JSONResponse(comments)
    except Exception as exc:
        logger.error("Comments API error: %s", exc)
        return JSONResponse(
            {"error": {"code": "unavailable", "message": str(exc)}},
            status_code=503,
        )


@app.post("/api/v1/issues/{identifier}/comments")
async def api_add_comment(identifier: str, request: Request):
    """Add a comment to an issue."""
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
            "project_id": issue.project_id,
            "labels": issue.labels,
            "created_at": issue.created_at.isoformat() if issue.created_at else None,
            "updated_at": issue.updated_at.isoformat() if issue.updated_at else None,
        }
        if issue.issue_type == "epic":
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


@app.patch("/api/v1/projects/{project_id}")
async def api_update_project(project_id: str, request: Request):
    """Update a project."""
    try:
        orch = _get_orchestrator()
        body = await request.json()
        fields = {}
        for key in ("name", "repo_path", "branch", "git_user_name", "git_user_email"):
            if key in body:
                fields[key] = body[key]
        project = orch.project_store.update(project_id, **fields)
        if not project:
            return JSONResponse(
                {"error": {"code": "not_found", "message": f"Project {project_id} not found"}},
                status_code=404,
            )
        return JSONResponse(project.to_dict())
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
    """List all open PRs/MRs across all projects."""
    try:
        orch = _get_orchestrator()
        projects = orch.project_store.list_all()
        reviews = get_all_open_reviews(projects)
        return JSONResponse(reviews)
    except Exception as exc:
        logger.error("Reviews API error: %s", exc)
        return JSONResponse(
            {"error": {"code": "fetch_failed", "message": str(exc)}},
            status_code=500,
        )


@app.post("/api/v1/reviews/{project_id}/{review_id}/rebase")
async def api_rebase_review(project_id: str, review_id: str):
    """Trigger a rebase for a PR/MR.

    If the rebase fails due to merge conflicts, automatically finds the
    original bead (by matching the PR source branch to bead identifiers),
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

    Matches the PR/MR source branch to a bead identifier, moves it to open,
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
            return JSONResponse(
                {"success": False, "message": f"No bead found matching branch '{branch}'"},
                status_code=404,
            )
        tracker.update_issue(matched.identifier, status="open", priority="0")
        tracker.add_comment(
            matched.identifier,
            f"CI tests failed on PR/MR #{review_id}. Please rebase onto main, "
            "fix the failing tests, and push so CI passes and the PR can merge cleanly.",
            author="oompah",
        )
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
    """Find the bead that owns a PR's source branch, comment, and reopen.

    Returns the bead identifier if found and notified, else None.
    """
    try:
        # Get the PR/MR details to find the source branch
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
            logger.info(
                "No bead found matching branch '%s' for PR #%s",
                source_branch, review_id,
            )
            return None

        # Post a comment about the conflict
        comment_text = (
            f"Merge conflict detected: PR/MR #{review_id} cannot be automatically rebased "
            f"onto {target_branch}.\n\n"
            f"Please resolve the conflicts on this branch ({source_branch}):\n"
            f"1. Run: git fetch origin && git rebase origin/{target_branch}\n"
            f"2. Resolve all conflicts, keeping the intent of both sides\n"
            f"3. Run tests to verify nothing is broken\n"
            f"4. Force-push: git push --force-with-lease\n"
            f"5. Verify the PR/MR is clean and CI passes"
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
            logger.info(
                "Reopened bead %s for merge conflict resolution (PR #%s)",
                issue.identifier, review_id,
            )
        else:
            logger.info(
                "Commented on bead %s about merge conflict (PR #%s), already in state '%s'",
                issue.identifier, review_id, issue.state,
            )

        return issue.identifier

    except Exception as exc:
        logger.warning("Failed to notify bead about conflict for PR #%s: %s", review_id, exc)
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


# --- Kanban Dashboard ---


DASHBOARD_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>oompah</title>
  <style>
    :root {
      --bg: #0d1117;
      --surface: #161b22;
      --surface-hover: #1c2129;
      --border: #30363d;
      --text: #e6edf3;
      --text-muted: #7d8590;
      --accent: #58a6ff;
      --green: #3fb950;
      --yellow: #d29922;
      --red: #f85149;
      --orange: #d18616;
      --purple: #bc8cff;
    }
    html { font-size: 125%; }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      height: 100vh;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }
    .toolbar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 0.75rem 1.5rem;
      border-bottom: 1px solid var(--border);
      flex-shrink: 0;
    }
    .toolbar h1 {
      font-size: 1.25rem;
      color: var(--accent);
      font-weight: 700;
    }
    .toolbar .status {
      font-size: 0.75rem;
      color: var(--text-muted);
    }
    button {
      background: var(--surface);
      color: var(--accent);
      border: 1px solid var(--border);
      padding: 0.3rem 0.75rem;
      border-radius: 6px;
      cursor: pointer;
      font-size: 0.75rem;
      font-weight: 600;
    }
    button:hover { background: rgba(88, 166, 255, 0.1); }
    button.active {
      background: rgba(88, 166, 255, 0.15);
      border-color: var(--accent);
    }

    .view-toggle {
      display: flex;
      border: 1px solid var(--border);
      border-radius: 6px;
      overflow: hidden;
    }
    .view-toggle button {
      border: none;
      border-radius: 0;
      padding: 0.3rem 0.6rem;
    }
    .view-toggle button + button {
      border-left: 1px solid var(--border);
    }

    .main-area {
      display: flex;
      flex: 1;
      overflow: hidden;
    }

    .board {
      display: flex;
      gap: 1rem;
      padding: 1rem 1.5rem;
      flex: 1;
      overflow-x: auto;
      overflow-y: hidden;
      align-items: flex-start;
    }

    /* Swimlane view */
    .board.swimlane-view {
      flex-direction: column;
      align-items: stretch;
      overflow-y: auto;
      overflow-x: hidden;
      gap: 0;
      padding: 1rem calc(1.5rem - 1px);
    }
    .swimlane {
      border: 1px solid var(--border);
      border-radius: 10px;
      margin: 0 0 0.75rem 0;
      background: var(--surface);
    }
    .swimlane-header {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      padding: 0.6rem 1rem;
      cursor: pointer;
      user-select: none;
      border-bottom: 1px solid var(--border);
    }
    .swimlane.collapsed .swimlane-header {
      border-bottom: none;
    }
    .swimlane-toggle {
      font-size: 0.7rem;
      color: var(--text-muted);
      transition: transform 0.15s;
    }
    .swimlane.collapsed .swimlane-toggle {
      transform: rotate(-90deg);
    }
    .swimlane-title {
      font-size: 0.85rem;
      font-weight: 600;
      color: var(--text);
      flex: 1;
    }
    .swimlane-counts {
      font-family: 'SF Mono', 'Fira Code', monospace;
      font-size: 0.7rem;
      color: var(--text-muted);
    }
    .swimlane-actions button {
      font-size: 0.65rem;
      padding: 0.15rem 0.5rem;
    }
    .swimlane-columns {
      display: flex;
      gap: 1rem;
      padding: 0.5rem 0;
      overflow-x: auto;
    }
    .swimlane.collapsed .swimlane-columns {
      display: none;
    }
    .swimlane-columns .column {
      background: transparent;
      border: none;
      border-radius: 0;
      max-height: none;
    }

    .column {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 10px;
      min-width: 280px;
      flex: 1;
      display: flex;
      flex-direction: column;
      max-height: calc(100vh - 80px);
    }
    .column-header {
      padding: 0.75rem 1rem;
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-shrink: 0;
      cursor: grab;
    }
    .column-header:active { cursor: grabbing; }
    .column-header.col-drag-over {
      background: rgba(88, 166, 255, 0.15);
      border-bottom-color: var(--blue);
    }
    .column-header .col-grip {
      color: var(--text-muted);
      opacity: 0.4;
      font-size: 0.7rem;
      margin-right: 0.4rem;
      user-select: none;
    }
    .column-header:hover .col-grip { opacity: 0.8; }
    .column-header .col-title {
      font-size: 0.8rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-muted);
    }
    .column-header .col-count {
      font-size: 0.7rem;
      background: var(--border);
      color: var(--text-muted);
      padding: 0.1rem 0.5rem;
      border-radius: 10px;
      font-weight: 600;
    }
    .column-body {
      padding: 0.5rem;
      overflow-y: auto;
      flex: 1;
      min-height: 60px;
    }
    .column-body.drag-over {
      background: rgba(88, 166, 255, 0.05);
      outline: 2px dashed var(--accent);
      outline-offset: -4px;
      border-radius: 0 0 10px 10px;
    }

    .card {
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 0.6rem 0.75rem;
      margin-bottom: 0.5rem;
      cursor: grab;
      transition: border-color 0.15s, box-shadow 0.15s;
      position: relative;
    }
    .card:hover {
      border-color: var(--accent);
    }
    .card.dragging {
      opacity: 0.4;
    }
    .card-id {
      font-family: 'SF Mono', 'Fira Code', monospace;
      font-size: 0.7rem;
      color: var(--text-muted);
      margin-bottom: 0.25rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 0.4rem;
    }
    .card-id-left {
      display: flex;
      align-items: center;
      gap: 0.4rem;
    }
    .card-title {
      font-size: 0.85rem;
      font-weight: 500;
      line-height: 1.3;
      cursor: text;
      padding: 2px 4px;
      margin: -2px -4px;
      border-radius: 4px;
      border: 1px solid transparent;
      outline: none;
      min-height: 1.3em;
    }
    .card-title:hover { border-color: var(--border); }
    .card-title:focus {
      border-color: var(--accent);
      background: var(--surface);
      cursor: text;
    }
    .card-desc {
      font-size: 0.75rem;
      color: var(--text-muted);
      margin-top: 0.3rem;
      line-height: 1.3;
      cursor: text;
      padding: 2px 4px;
      margin-left: -4px;
      margin-right: -4px;
      border-radius: 4px;
      border: 1px solid transparent;
      outline: none;
      max-height: 3.9em;
      overflow: hidden;
    }
    .card-desc:hover { border-color: var(--border); }
    .card-desc:focus {
      border-color: var(--accent);
      background: var(--surface);
      cursor: text;
      max-height: none;
    }
    .card-desc:empty::before {
      content: "Add description...";
      color: var(--border);
      font-style: italic;
    }

    .priority-badge {
      font-size: 0.65rem;
      font-weight: 700;
      padding: 0.1rem 0.35rem;
      border-radius: 4px;
      font-family: 'SF Mono', 'Fira Code', monospace;
    }
    .p0 { background: rgba(248, 81, 73, 0.2); color: var(--red); }
    .p1 { background: rgba(209, 134, 22, 0.2); color: var(--orange); }
    .p2 { background: rgba(210, 153, 34, 0.2); color: var(--yellow); }
    .p3 { background: rgba(88, 166, 255, 0.15); color: var(--accent); }
    .p4 { background: rgba(125, 133, 144, 0.15); color: var(--text-muted); }

    /* Epic badge on child cards */
    .epic-badge {
      font-size: 0.6rem;
      font-weight: 600;
      padding: 0.1rem 0.35rem;
      border-radius: 4px;
      background: rgba(188, 140, 255, 0.15);
      color: var(--purple);
      cursor: pointer;
      position: relative;
      font-family: 'SF Mono', 'Fira Code', monospace;
    }

    /* Epic tooltip */
    .epic-tooltip {
      display: none;
      position: absolute;
      top: 100%;
      left: 0;
      margin-top: 4px;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 0.6rem 0.75rem;
      width: 240px;
      z-index: 50;
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
    }
    .epic-badge:hover .epic-tooltip {
      display: block;
    }
    .epic-tooltip-title {
      font-size: 0.8rem;
      font-weight: 600;
      color: var(--text);
      margin-bottom: 0.25rem;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    }
    .epic-tooltip-desc {
      font-size: 0.7rem;
      color: var(--text-muted);
      margin-bottom: 0.4rem;
      line-height: 1.3;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    }
    .epic-tooltip-link {
      font-size: 0.7rem;
      color: var(--accent);
      cursor: pointer;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    }
    .epic-tooltip-link:hover { text-decoration: underline; }

    .drop-indicator {
      height: 3px;
      background: var(--accent);
      border-radius: 2px;
      margin: 2px 0;
      display: none;
    }
    .drop-indicator.visible {
      display: block;
    }

    /* Detail slide-out panel */
    .detail-panel {
      width: 0;
      overflow: hidden;
      border-left: 1px solid var(--border);
      background: var(--surface);
      transition: width 0.2s ease;
      flex-shrink: 0;
      display: flex;
      flex-direction: column;
    }
    .detail-panel.open {
      width: 400px;
    }
    .detail-panel-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 0.75rem 1rem;
      border-bottom: 1px solid var(--border);
      flex-shrink: 0;
    }
    .detail-panel-header h3 {
      font-size: 0.85rem;
      color: var(--text-muted);
      font-weight: 600;
    }
    .detail-panel-close {
      background: none;
      border: none;
      color: var(--text-muted);
      font-size: 1.1rem;
      cursor: pointer;
      padding: 0.2rem 0.4rem;
    }
    .detail-panel-close:hover { color: var(--text); background: none; }
    .detail-panel-body {
      flex: 1;
      overflow-y: auto;
      padding: 1rem;
    }
    .detail-field {
      margin-bottom: 1rem;
    }
    .detail-field-label {
      font-size: 0.7rem;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 0.25rem;
    }
    .detail-field-value {
      font-size: 0.85rem;
      color: var(--text);
      line-height: 1.4;
    }
    .detail-editable {
      font-size: 0.85rem;
      color: var(--text);
      line-height: 1.4;
      cursor: text;
      padding: 2px 4px;
      margin: -2px -4px;
      border-radius: 4px;
      border: 1px solid transparent;
      outline: none;
      min-height: 1.3em;
      white-space: pre-wrap;
      word-break: break-word;
    }
    .detail-editable:hover { border-color: var(--border); }
    .detail-editable:focus {
      border-color: var(--accent);
      background: var(--bg);
      cursor: text;
    }
    .detail-editable:empty::before {
      content: attr(data-placeholder);
      color: var(--border);
      font-style: italic;
    }
    .detail-children-list {
      list-style: none;
    }
    .detail-children-list li {
      padding: 0.35rem 0.5rem;
      border-radius: 4px;
      font-size: 0.8rem;
      margin-bottom: 0.25rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      cursor: pointer;
    }
    .detail-children-list li:hover {
      background: var(--bg);
    }
    .detail-child-state {
      font-size: 0.65rem;
      padding: 0.1rem 0.35rem;
      border-radius: 4px;
      background: var(--border);
      color: var(--text-muted);
      font-family: 'SF Mono', 'Fira Code', monospace;
    }

    /* Comments */
    .comments-list {
      max-height: 300px;
      overflow-y: auto;
      margin-bottom: 0.5rem;
    }
    .comment {
      padding: 0.4rem 0;
      border-bottom: 1px solid rgba(48, 54, 61, 0.5);
    }
    .comment:last-child { border-bottom: none; }
    .comment-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 0.15rem;
    }
    .comment-author {
      font-size: 0.7rem;
      font-weight: 600;
      color: var(--accent);
    }
    .comment-time {
      font-size: 0.6rem;
      color: var(--text-muted);
      font-family: 'SF Mono', 'Fira Code', monospace;
    }
    .comment-text {
      font-size: 0.75rem;
      color: var(--text);
      line-height: 1.4;
      white-space: pre-wrap;
    }
    .comment-input {
      width: 100%;
      background: var(--bg);
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 0.4rem 0.5rem;
      font-size: 0.75rem;
      font-family: inherit;
      outline: none;
      resize: vertical;
      min-height: 50px;
    }
    .comment-input:focus { border-color: var(--accent); }

    /* Agent status bar */
    .agent-bar {
      display: flex;
      align-items: center;
      gap: 1rem;
      padding: 0.4rem 1.5rem;
      border-bottom: 1px solid var(--border);
      background: var(--surface);
      font-size: 0.72rem;
      flex-shrink: 0;
    }
    .agent-bar .agent-stat {
      color: var(--text-muted);
    }
    .agent-bar .agent-stat strong {
      color: var(--text);
    }
    .agent-bar .paused-badge {
      background: rgba(210, 153, 34, 0.2);
      color: var(--yellow);
      padding: 0.1rem 0.4rem;
      border-radius: 4px;
      font-weight: 600;
    }
    .running-agents {
      display: flex;
      gap: 0.4rem;
      flex-wrap: wrap;
    }
    .running-agent-chip {
      display: inline-flex;
      align-items: center;
      gap: 0.25rem;
      background: rgba(63, 185, 80, 0.1);
      border: 1px solid rgba(63, 185, 80, 0.3);
      border-radius: 4px;
      padding: 0.1rem 0.4rem;
      font-size: 0.65rem;
      color: var(--green);
      font-family: 'SF Mono', 'Fira Code', monospace;
      cursor: pointer;
    }
    .running-agent-chip:hover {
      background: rgba(63, 185, 80, 0.2);
    }
    .running-agent-chip .dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: var(--green);
      animation: pulse 1.5s ease-in-out infinite;
    }
    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.3; }
    }
    @keyframes spin {
      to { transform: rotate(360deg); }
    }
    .btn-paused {
      color: var(--yellow) !important;
      border-color: var(--yellow) !important;
    }

    /* Activity panel */
    .activity-overlay {
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.6);
      z-index: 200;
      justify-content: center;
      align-items: center;
    }
    .activity-overlay.open { display: flex; }
    .activity-panel {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      width: 700px;
      max-width: 90vw;
      max-height: 80vh;
      display: flex;
      flex-direction: column;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
    }
    .activity-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 1rem 1.25rem;
      border-bottom: 1px solid var(--border);
    }
    .activity-header h3 {
      font-size: 0.9rem;
      color: var(--accent);
    }
    .activity-body {
      flex: 1;
      overflow-y: auto;
      padding: 0.75rem 1.25rem;
      font-size: 0.75rem;
      font-family: 'SF Mono', 'Fira Code', monospace;
    }
    .activity-entry {
      padding: 0.3rem 0;
      border-bottom: 1px solid rgba(48, 54, 61, 0.5);
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
      align-items: flex-start;
      cursor: pointer;
    }
    .activity-entry:hover { background: rgba(48, 54, 61, 0.3); }
    .activity-entry:last-child { border-bottom: none; }
    .activity-turn {
      color: var(--text-muted);
      min-width: 2rem;
      text-align: right;
      flex-shrink: 0;
    }
    .activity-kind {
      min-width: 5rem;
      flex-shrink: 0;
      font-weight: 600;
    }
    .activity-kind.thinking { color: var(--purple); }
    .activity-kind.tool_call { color: var(--yellow); }
    .activity-kind.tool_result { color: var(--text-muted); }
    .activity-kind.message { color: var(--green); }
    .activity-kind.error { color: var(--red); }
    .activity-summary {
      color: var(--text);
      word-break: break-word;
      white-space: pre-wrap;
    }
    .activity-detail {
      display: none;
      width: 100%;
      padding: 0.5rem 0.75rem;
      margin-top: 0.25rem;
      background: rgba(0, 0, 0, 0.3);
      border-radius: 4px;
      font-size: 0.75rem;
      color: var(--text-muted);
      white-space: pre-wrap;
      word-break: break-word;
      max-height: 300px;
      overflow-y: auto;
    }
    .activity-entry.expanded .activity-detail { display: block; }

    /* Create dialog */
    .dialog-overlay {
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.6);
      z-index: 100;
      justify-content: center;
      align-items: center;
    }
    .dialog-overlay.open {
      display: flex;
    }
    .dialog {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1.5rem;
      width: 460px;
      max-width: 90vw;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
    }
    .dialog h2 {
      font-size: 1rem;
      margin-bottom: 1rem;
      color: var(--text);
    }
    .dialog label {
      display: block;
      font-size: 0.75rem;
      color: var(--text-muted);
      margin-bottom: 0.25rem;
      margin-top: 0.75rem;
    }
    .dialog label:first-of-type { margin-top: 0; }
    .dialog input, .dialog select, .dialog textarea {
      width: 100%;
      background: var(--bg);
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 0.5rem 0.6rem;
      font-size: 0.85rem;
      font-family: inherit;
      outline: none;
    }
    .dialog input:focus, .dialog select:focus, .dialog textarea:focus {
      border-color: var(--accent);
    }
    .dialog textarea {
      resize: vertical;
      min-height: 80px;
    }
    .dialog-actions {
      display: flex;
      justify-content: flex-end;
      gap: 0.5rem;
      margin-top: 1.25rem;
    }
    .dialog-actions button {
      padding: 0.4rem 1rem;
      font-size: 0.8rem;
    }
    .dialog-actions .btn-primary {
      background: var(--accent);
      color: var(--bg);
      border-color: var(--accent);
    }
    .dialog-actions .btn-primary:hover {
      background: #79bbff;
    }
    .dialog-actions .btn-primary:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
  </style>
</head>
<body>
  <div class="toolbar">
    <h1>oompah</h1>
    <div style="display: flex; align-items: center; gap: 1rem;">
      <span class="status" id="status-text">Loading...</span>
      <div class="view-toggle">
        <button id="btn-flat" class="active" onclick="setViewMode('flat')">Flat</button>
        <button id="btn-swimlane" onclick="setViewMode('swimlane')">Swimlanes</button>
      </div>
      <select id="project-filter" onchange="refreshBoard()" style="padding:4px 8px;border-radius:4px;border:1px solid var(--border);background:var(--card-bg);color:var(--text);">
        <option value="">All Projects</option>
      </select>
      <button onclick="openCreateDialog()">+ Create</button>
      <button onclick="window.location='/projects-manage'">Projects</button>
      <button onclick="window.location='/providers'">Providers</button>
      <button onclick="window.location='/foci'">Foci</button>
      <button onclick="window.location='/reviews'">Reviews</button>
      <button id="btn-pause" onclick="togglePause()">Pause</button>
      <button onclick="refreshBoard()">Refresh</button>
    </div>
  </div>
  <div class="agent-bar" id="agent-bar">
    <span class="agent-stat">Agents: <strong id="agent-count">0</strong></span>
    <span class="agent-stat">Tokens: <strong id="agent-tokens">0</strong></span>
    <span class="agent-stat">Cost: <strong id="agent-cost">$0.00</strong></span>
    <span class="agent-stat">Budget: <strong id="agent-budget">-</strong></span>
    <span class="agent-stat" id="reviews-stat" style="display:none;cursor:pointer;" onclick="window.location='/reviews'">
      <strong id="reviews-count" style="color:var(--blue,#58a6ff);">0</strong> <span class="reviews-label">reviews waiting</span>
    </span>
    <span class="agent-stat" id="proposed-foci-stat" style="display:none;cursor:pointer;" onclick="window.location='/foci'">
      <strong id="proposed-foci-count" style="color:var(--yellow,#e2b340);">0</strong> proposed foci
    </span>
    <div class="running-agents" id="running-agents"></div>
  </div>
  <div class="main-area">
    <div class="board" id="board">
      <div id="board-spinner" style="display:flex;align-items:center;justify-content:center;width:100%;padding:3rem;color:var(--text-muted);font-size:0.9rem;gap:0.75rem;">
        <svg width="20" height="20" viewBox="0 0 24 24" style="animation:spin 1s linear infinite;">
          <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" fill="none" stroke-dasharray="31.4 31.4" stroke-linecap="round"/>
        </svg>
        Loading issues...
      </div>
    </div>
    <div class="detail-panel" id="detail-panel">
      <div class="detail-panel-header">
        <h3 id="detail-panel-title">Details</h3>
        <button class="detail-panel-close" onclick="closeDetailPanel()">&times;</button>
      </div>
      <div class="detail-panel-body" id="detail-panel-body"></div>
    </div>
  </div>

<script>
const COLUMNS = ['deferred', 'open', 'in_progress', 'closed'];
const COLUMN_LABELS = {deferred: 'Backlog', open: 'Open', in_progress: 'In Progress', closed: 'Closed'};

let boardData = {};
let allIssuesFlat = [];
let dragState = null;
let columnDragState = null;  // {sourceState, epicId (or null for flat)}
let viewMode = 'flat';
let collapsedSwimlanes = {};
let orchPaused = false;
let lastRunningAgents = [];
let currentProjects = [];

// --- Edit-state tracking ---
// Bug fix: Track when user is inline-editing a card field so that incoming
// WebSocket updates do not destroy their in-progress edits by rebuilding the DOM.
let editingState = null;      // {identifier, field} or null
let _pendingBoardData = null; // queued board data to render after editing ends
let _editingDetailPanel = false; // true if user is typing in comment textarea

// --- WebSocket connection ---
let ws = null;
let wsReconnectTimer = null;

function connectWebSocket() {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(proto + '//' + location.host + '/ws');

  ws.onopen = () => {
    document.getElementById('status-text').textContent = 'Connected';
    if (wsReconnectTimer) { clearTimeout(wsReconnectTimer); wsReconnectTimer = null; }
  };

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      if (msg.type === 'state') {
        handleStateUpdate(msg.data);
      } else if (msg.type === 'issues') {
        renderBoard(filterByProject(msg.data));
        refreshOpenDetailPanel();
      } else if (msg.type === 'activity') {
        handleActivityPush(msg.identifier, msg.entry);
        if (_openDetailIdentifier && msg.identifier === _openDetailIdentifier) {
          refreshOpenDetailPanel();
        }
      }
    } catch (e) { /* ignore parse errors */ }
  };

  ws.onclose = () => {
    document.getElementById('status-text').textContent = 'Reconnecting...';
    ws = null;
    wsReconnectTimer = setTimeout(connectWebSocket, 2000);
  };

  ws.onerror = () => {
    if (ws) ws.close();
  };
}

function handleStateUpdate(state) {
  // Update pause state
  orchPaused = state.paused || false;
  const pauseBtn = document.getElementById('btn-pause');
  if (orchPaused) {
    pauseBtn.textContent = 'Resume';
    pauseBtn.classList.add('btn-paused');
  } else {
    pauseBtn.textContent = 'Pause';
    pauseBtn.classList.remove('btn-paused');
  }

  // Update agent stats
  document.getElementById('agent-count').textContent = state.counts.running;
  const totals = state.agent_totals || {};
  document.getElementById('agent-tokens').textContent = (totals.total_tokens || 0).toLocaleString();
  document.getElementById('agent-cost').textContent = '$' + (totals.estimated_cost || 0).toFixed(2);
  const budget = state.budget || {};
  if (budget.limit > 0) {
    document.getElementById('agent-budget').textContent =
      '$' + (budget.spent || 0).toFixed(2) + ' / $' + budget.limit.toFixed(2);
  }

  // Check for proposed foci and pending reviews
  fetchProposedFociCount();
  fetchReviewsCount();

  // Render running agent chips
  const container = document.getElementById('running-agents');
  const running = state.running || [];
  lastRunningAgents = running;
  if (running.length === 0) {
    container.innerHTML = orchPaused ? '<span class="paused-badge">PAUSED</span>' : '';
  } else {
    container.innerHTML = running.map(r => {
      const id = esc(r.issue_identifier);
      return '<span class="running-agent-chip" onclick="openActivityPanel(&quot;' + id + '&quot;)">' +
        '<span class="dot"></span>' +
        id +
        (r.agent_profile ? ' (' + esc(r.agent_profile) + ')' : '') +
      '</span>';
    }).join('');
    if (orchPaused) {
      container.innerHTML += ' <span class="paused-badge">PAUSED</span>';
    }
  }

  // Update project filter dropdown
  const projects = state.projects || [];
  currentProjects = projects;
  const sel = document.getElementById('project-filter');
  if (sel && projects.length > 0) {
    const curVal = sel.value;
    sel.innerHTML = '<option value="">All Projects</option>' +
      projects.map(p => '<option value="' + esc(p.id) + '"' +
        (p.id === curVal ? ' selected' : '') + '>' + esc(p.name) + '</option>').join('');
    sel.style.display = '';
  } else if (sel && projects.length === 0) {
    sel.style.display = 'none';
  }

  // Update activity panel if open
  const activityOverlay = document.getElementById('activity-overlay');
  if (activityOverlay && activityOverlay.classList.contains('open')) {
    const activeId = document.getElementById('activity-title').dataset.identifier;
    const agent = running.find(r => r.issue_identifier === activeId);
    if (agent && agent.focus_role) {
      // Update title with latest focus info
      let title = 'Agent: ' + activeId;
      const parts = [];
      if (agent.focus_role) parts.push(agent.focus_role);
      if (agent.agent_profile) parts.push(agent.agent_profile);
      if (parts.length > 0) title += ' — ' + parts.join(' · ');
      document.getElementById('activity-title').textContent = title;
    }
  }
}

// --- Orchestrator state (legacy fallback, replaced by WebSocket) ---
async function fetchOrchestratorState() {
  try {
    const res = await fetch('/api/v1/state');
    if (!res.ok) return;
    const state = await res.json();
    handleStateUpdate(state);
  } catch (e) { /* ignore */ }
}

async function togglePause() {
  const endpoint = orchPaused ? '/api/v1/orchestrator/resume' : '/api/v1/orchestrator/pause';
  await fetch(endpoint, {method: 'POST'});
  await fetchOrchestratorState();
}

async function fetchReviewsCount() {
  try {
    const res = await fetch('/api/v1/reviews');
    if (!res.ok) return;
    const reviews = await res.json();
    const el = document.getElementById('reviews-stat');
    const countEl = document.getElementById('reviews-count');
    const conflicts = reviews.filter(r => r.review && r.review.has_conflicts).length;
    if (conflicts > 0) {
      countEl.textContent = conflicts;
      countEl.style.color = 'var(--red, #f85149)';
      el.querySelector('.reviews-label').textContent = 'conflicts need resolution';
      el.style.display = '';
    } else if (reviews.length > 0) {
      countEl.textContent = reviews.length;
      countEl.style.color = 'var(--blue, #58a6ff)';
      el.querySelector('.reviews-label').textContent = 'reviews waiting';
      el.style.display = '';
    } else {
      el.style.display = 'none';
    }
  } catch(e) {}
}

async function fetchProposedFociCount() {
  try {
    const res = await fetch('/api/v1/foci');
    if (!res.ok) return;
    const foci = await res.json();
    const proposed = foci.filter(f => f.status === 'proposed');
    const el = document.getElementById('proposed-foci-stat');
    const countEl = document.getElementById('proposed-foci-count');
    if (proposed.length > 0) {
      countEl.textContent = proposed.length;
      el.style.display = '';
    } else {
      el.style.display = 'none';
    }
  } catch(e) {}
}

function filterByProject(data) {
  const sel = document.getElementById('project-filter');
  const pid = sel ? sel.value : '';
  if (!pid) return data;
  const filtered = {};
  for (const [state, issues] of Object.entries(data)) {
    const matching = issues.filter(i => i.project_id === pid);
    if (matching.length > 0) filtered[state] = matching;
  }
  return filtered;
}

async function fetchIssues() {
  const filter = document.getElementById('project-filter');
  const pid = filter ? filter.value : '';
  const url = pid ? '/api/v1/issues?project_id=' + encodeURIComponent(pid) : '/api/v1/issues';
  const res = await fetch(url);
  if (!res.ok) return null;
  return await res.json();
}

function moveIssueInBoard(identifier, newState) {
  // Move an issue between columns in the local boardData
  if (!boardData) return;
  for (const [state, issues] of Object.entries(boardData)) {
    const idx = issues.findIndex(i => i.identifier === identifier);
    if (idx !== -1) {
      const [issue] = issues.splice(idx, 1);
      issue.state = newState;
      if (!boardData[newState]) boardData[newState] = [];
      boardData[newState].push(issue);
      return;
    }
  }
}

async function updateIssue(identifier, fields) {
  const res = await fetch(`/api/v1/issues/${identifier}`, {
    method: 'PATCH',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(fields),
  });
  return res.ok;
}

function setViewMode(mode) {
  viewMode = mode;
  document.getElementById('btn-flat').classList.toggle('active', mode === 'flat');
  document.getElementById('btn-swimlane').classList.toggle('active', mode === 'swimlane');
  renderBoard(boardData);
}

// Build flat list of all issues from grouped data
function flattenIssues(data) {
  const all = [];
  for (const state of Object.keys(data)) {
    for (const issue of data[state]) {
      all.push(issue);
    }
  }
  return all;
}

// Get epic info by ID from flat list
function getEpicById(epicId) {
  return allIssuesFlat.find(i => i.id === epicId && i.issue_type === 'epic');
}

function renderBoard(data) {
  // Bug fix: If the user is currently editing a card field, defer the
  // full DOM rebuild. Store the latest data and render it once the
  // user finishes editing (on blur).
  if (editingState) {
    _pendingBoardData = data;
    // Still update the in-memory data so other lookups stay current
    boardData = data;
    allIssuesFlat = flattenIssues(data);
    return;
  }

  boardData = data;
  allIssuesFlat = flattenIssues(data);
  _pendingBoardData = null;
  const board = document.getElementById('board');
  board.innerHTML = '';

  if (viewMode === 'swimlane') {
    board.className = 'board swimlane-view';
    renderSwimlaneView(board, data);
  } else {
    board.className = 'board';
    renderFlatView(board, data);
  }

  document.getElementById('status-text').textContent =
    `Updated ${new Date().toLocaleTimeString()}`;
}

function renderFlatView(board, data) {
  for (const col of COLUMNS) {
    const allInCol = data[col] || [];
    // Filter out epics in flat view
    const issues = allInCol.filter(i => i.issue_type !== 'epic');
    const column = document.createElement('div');
    column.className = 'column';
    column.dataset.state = col;

    column.innerHTML = `
      <div class="column-header" draggable="true">
        <span><span class="col-grip">&#8942;&#8942;</span><span class="col-title">${COLUMN_LABELS[col]}</span></span>
        <span class="col-count">${issues.length}</span>
      </div>
      <div class="column-body" data-state="${col}"></div>
    `;

    const header = column.querySelector('.column-header');
    setupColumnDrag(header, col, null);
    const body = column.querySelector('.column-body');
    setupDropZone(body);

    for (let i = 0; i < issues.length; i++) {
      const indicator = document.createElement('div');
      indicator.className = 'drop-indicator';
      indicator.dataset.position = String(i);
      body.appendChild(indicator);
      body.appendChild(createCard(issues[i]));
    }
    const lastIndicator = document.createElement('div');
    lastIndicator.className = 'drop-indicator';
    lastIndicator.dataset.position = String(issues.length);
    body.appendChild(lastIndicator);

    board.appendChild(column);
  }
}

function renderSwimlaneView(board, data) {
  // Collect epics and group children
  const epics = allIssuesFlat.filter(i => i.issue_type === 'epic');
  const epicIds = new Set(epics.map(e => e.id));
  const orphans = allIssuesFlat.filter(i => i.issue_type !== 'epic' && (!i.parent_id || !epicIds.has(i.parent_id)));

  // Render each epic as a swimlane
  for (const epic of epics) {
    const children = allIssuesFlat.filter(i => i.parent_id === epic.id && i.issue_type !== 'epic');
    const counts = epic.children_counts || {deferred: 0, open: 0, in_progress: 0, closed: 0};
    const isCollapsed = collapsedSwimlanes[epic.id] || false;

    const lane = document.createElement('div');
    lane.className = 'swimlane' + (isCollapsed ? ' collapsed' : '');
    lane.dataset.epicId = epic.id;

    const countsStr = `${counts.deferred} / ${counts.open} / ${counts.in_progress} / ${counts.closed}`;

    lane.innerHTML = `
      <div class="swimlane-header" onclick="toggleSwimlane('${esc(epic.id)}')">
        <span class="swimlane-toggle">&#9660;</span>
        <span class="swimlane-title">${esc(epic.title)}</span>
        <span class="swimlane-counts" title="Backlog / Open / In Progress / Closed">${countsStr}</span>
        <span class="swimlane-actions">
          <button onclick="event.stopPropagation(); openCreateDialogForEpic('${esc(epic.id)}')">+ Child</button>
          <button onclick="event.stopPropagation(); openDetailPanel('${esc(epic.identifier)}')">Details</button>
        </span>
      </div>
      <div class="swimlane-columns"></div>
    `;

    const cols = lane.querySelector('.swimlane-columns');
    for (const col of COLUMNS) {
      const colIssues = children.filter(c => c.state.trim().toLowerCase() === col);
      const sc = document.createElement('div');
      sc.className = 'column';
      sc.innerHTML = `
        <div class="column-header" draggable="true">
          <span><span class="col-grip">&#8942;&#8942;</span><span class="col-title">${COLUMN_LABELS[col]}</span></span>
          <span class="col-count">${colIssues.length}</span>
        </div>
        <div class="column-body" data-state="${col}"></div>
      `;
      const scHeader = sc.querySelector('.column-header');
      setupColumnDrag(scHeader, col, epic.id);
      const scBody = sc.querySelector('.column-body');
      setupDropZone(scBody);
      for (const issue of colIssues) {
        scBody.appendChild(createCard(issue));
      }
      cols.appendChild(sc);
    }

    board.appendChild(lane);
  }

  // Orphan swimlane (items not belonging to any epic)
  if (orphans.length > 0) {
    const lane = document.createElement('div');
    const isCollapsed = collapsedSwimlanes['_orphans'] || false;
    lane.className = 'swimlane' + (isCollapsed ? ' collapsed' : '');

    lane.innerHTML = `
      <div class="swimlane-header" onclick="toggleSwimlane('_orphans')">
        <span class="swimlane-toggle">&#9660;</span>
        <span class="swimlane-title" style="color: var(--text-muted);">Unassigned</span>
        <span class="swimlane-counts">${orphans.length} items</span>
      </div>
      <div class="swimlane-columns"></div>
    `;

    const cols = lane.querySelector('.swimlane-columns');
    for (const col of COLUMNS) {
      const colIssues = orphans.filter(o => o.state.trim().toLowerCase() === col);
      const sc = document.createElement('div');
      sc.className = 'column';
      sc.innerHTML = `
        <div class="column-header" draggable="true">
          <span><span class="col-grip">&#8942;&#8942;</span><span class="col-title">${COLUMN_LABELS[col]}</span></span>
          <span class="col-count">${colIssues.length}</span>
        </div>
        <div class="column-body" data-state="${col}"></div>
      `;
      const scHeader = sc.querySelector('.column-header');
      setupColumnDrag(scHeader, col, '_orphans');
      const scBody = sc.querySelector('.column-body');
      setupDropZone(scBody);
      for (const issue of colIssues) {
        scBody.appendChild(createCard(issue));
      }
      cols.appendChild(sc);
    }

    board.appendChild(lane);
  }
}

function toggleSwimlane(id) {
  collapsedSwimlanes[id] = !collapsedSwimlanes[id];
  renderBoard(boardData);
}

function createCard(issue) {
  const card = document.createElement('div');
  card.className = 'card';
  card.draggable = true;
  card.dataset.id = issue.identifier;
  card.dataset.priority = issue.priority ?? 4;
  card.dataset.projectId = issue.project_id || '';

  const pClass = `p${issue.priority ?? 4}`;

  // Build epic badge HTML if this issue has a parent
  let epicBadgeHtml = '';
  if (issue.parent_id) {
    const epic = getEpicById(issue.parent_id);
    if (epic) {
      epicBadgeHtml = `
        <span class="epic-badge" onclick="event.stopPropagation()">
          ${esc(epic.identifier)}
          <span class="epic-tooltip">
            <div class="epic-tooltip-title">${esc(epic.title)}</div>
            <div class="epic-tooltip-desc">${esc(epic.description || 'No description')}</div>
            <span class="epic-tooltip-link" onclick="event.stopPropagation(); openDetailPanel('${esc(epic.identifier)}')">Details &rarr;</span>
          </span>
        </span>
      `;
    }
  }

  card.innerHTML = `
    <div class="card-id">
      <span class="card-id-left">
        <span>${esc(issue.identifier)}</span>
        ${epicBadgeHtml}
      </span>
      <span class="priority-badge ${pClass}">P${issue.priority ?? 4}</span>
    </div>
    <div class="card-title" contenteditable="true" spellcheck="false"
         data-field="title" data-id="${esc(issue.identifier)}">${esc(issue.title)}</div>
    <div class="card-desc" contenteditable="true" spellcheck="false"
         data-field="description" data-id="${esc(issue.identifier)}">${esc(issue.description || '')}</div>
  `;

  // Click card ID to open detail panel
  card.querySelector('.card-id-left > span:first-child').style.cursor = 'pointer';
  card.querySelector('.card-id-left > span:first-child').addEventListener('click', (e) => {
    e.stopPropagation();
    openDetailPanel(issue.identifier);
  });

  // Drag handlers
  card.addEventListener('dragstart', e => {
    dragState = {
      identifier: issue.identifier,
      sourceState: issue.state.trim().toLowerCase(),
      priority: issue.priority,
      projectId: issue.project_id,
    };
    card.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', issue.identifier);
  });
  card.addEventListener('dragend', () => {
    card.classList.remove('dragging');
    clearAllIndicators();
    dragState = null;
  });

  // Inline editing
  const titleEl = card.querySelector('.card-title');
  const descEl = card.querySelector('.card-desc');
  for (const el of [titleEl, descEl]) {
    el.addEventListener('mousedown', e => {
      if (document.activeElement === el) e.stopPropagation();
    });
    el.addEventListener('focus', () => {
      card.draggable = false;
      // Bug fix: Track that this field is being edited so renderBoard()
      // defers DOM rebuilds until the user finishes.
      editingState = { identifier: el.dataset.id, field: el.dataset.field };
    });
    el.addEventListener('blur', async () => {
      card.draggable = true;
      const field = el.dataset.field;
      const id = el.dataset.id;
      const newValue = el.textContent.trim();
      const pid = card.dataset.projectId;
      // Bug fix: Clear editing state *before* the async save so that
      // any queued board data can be rendered.
      editingState = null;
      await updateIssue(id, {[field]: newValue, project_id: pid});
      // Flush any board data that arrived while we were editing.
      if (_pendingBoardData) {
        const pending = _pendingBoardData;
        _pendingBoardData = null;
        renderBoard(pending);
      }
    });
    el.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); el.blur(); }
      if (e.key === 'Escape') el.blur();
    });
  }

  return card;
}

function setupColumnDrag(header, sourceState, epicId) {
  header.addEventListener('dragstart', e => {
    // Don't interfere with card drags — cards set dragState
    columnDragState = { sourceState, epicId };
    dragState = null;
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', 'column:' + sourceState);
    header.style.opacity = '0.5';
  });
  header.addEventListener('dragend', () => {
    header.style.opacity = '';
    columnDragState = null;
    document.querySelectorAll('.column-header.col-drag-over').forEach(
      el => el.classList.remove('col-drag-over')
    );
  });

  // Column headers are also drop targets for other column drags
  header.addEventListener('dragover', e => {
    if (!columnDragState) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    header.classList.add('col-drag-over');
  });
  header.addEventListener('dragleave', () => {
    header.classList.remove('col-drag-over');
  });
  header.addEventListener('drop', async e => {
    e.preventDefault();
    header.classList.remove('col-drag-over');
    if (!columnDragState) return;

    const targetState = sourceState;  // this header's state
    const src = columnDragState;
    columnDragState = null;
    if (targetState === src.sourceState) return;

    // Determine which column header's epicId to use for scoping
    // In swimlane view, only move items within the source epic
    // Both source and target should be in the same swimlane context
    const scopeEpicId = src.epicId;

    // Collect cards to move from the source column
    const cardsToMove = getCardsInColumn(src.sourceState, scopeEpicId);
    if (cardsToMove.length === 0) return;

    // Confirm with user
    const label = COLUMN_LABELS[src.sourceState] || src.sourceState;
    const targetLabel = COLUMN_LABELS[targetState] || targetState;
    const scope = scopeEpicId ? (scopeEpicId === '_orphans' ? 'Unassigned' : 'this swimlane') : 'all visible';
    if (!confirm(`Move ${cardsToMove.length} item(s) from ${label} → ${targetLabel} (${scope})?`)) return;

    // Optimistic update
    for (const issue of cardsToMove) {
      moveIssueInBoard(issue.identifier, targetState);
    }
    renderBoard(boardData);

    // Fire API calls
    for (const issue of cardsToMove) {
      updateIssue(issue.identifier, {status: targetState, project_id: issue.project_id || ''});
    }
  });
}

function getCardsInColumn(state, epicId) {
  // Get visible cards in a column, scoped by epicId (swimlane) or project filter (flat)
  const issues = (boardData[state] || []).filter(i => i.issue_type !== 'epic');
  if (epicId === null) {
    // Flat view — all visible (already filtered by project)
    return issues;
  } else if (epicId === '_orphans') {
    // Orphan swimlane — items with no parent or parent not an epic
    const epicIds = new Set(allIssuesFlat.filter(i => i.issue_type === 'epic').map(e => e.id));
    return issues.filter(i => !i.parent_id || !epicIds.has(i.parent_id));
  } else {
    // Specific epic swimlane
    return issues.filter(i => i.parent_id === epicId);
  }
}

function setupDropZone(body) {
  body.addEventListener('dragover', e => {
    if (columnDragState) return;  // column drags handled by column headers
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    body.classList.add('drag-over');
    const indicators = body.querySelectorAll('.drop-indicator');
    let closest = null;
    let closestDist = Infinity;
    for (const ind of indicators) {
      const rect = ind.getBoundingClientRect();
      const dist = Math.abs(e.clientY - (rect.top + rect.height / 2));
      if (dist < closestDist) { closestDist = dist; closest = ind; }
    }
    clearAllIndicators();
    body.classList.add('drag-over');
    if (closest) closest.classList.add('visible');
  });

  body.addEventListener('dragleave', e => {
    if (!body.contains(e.relatedTarget)) {
      body.classList.remove('drag-over');
      clearAllIndicators();
    }
  });

  body.addEventListener('drop', async e => {
    e.preventDefault();
    body.classList.remove('drag-over');
    clearAllIndicators();
    if (!dragState) return;

    const targetState = body.dataset.state;
    const identifier = dragState.identifier;
    if (targetState === dragState.sourceState) return;

    // Optimistic update: move card in boardData immediately
    moveIssueInBoard(identifier, targetState);
    renderBoard(boardData);

    // Fire API call in background — WebSocket will confirm or correct
    updateIssue(identifier, {status: targetState, project_id: dragState.projectId});
  });
}

function clearAllIndicators() {
  document.querySelectorAll('.drop-indicator').forEach(el => el.classList.remove('visible'));
  document.querySelectorAll('.column-body').forEach(el => el.classList.remove('drag-over'));
}

function esc(s) {
  if (!s) return '';
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

async function refreshBoard() {
  if (ws && ws.readyState === WebSocket.OPEN) {
    // Ask server to push fresh data via WebSocket
    ws.send(JSON.stringify({action: 'refresh'}));
    return;
  }
  // Fallback to REST
  document.getElementById('status-text').textContent = 'Refreshing...';
  const data = await fetchIssues();
  if (data) renderBoard(data);
  fetchOrchestratorState();
}

// --- Agent activity panel ---
let activityPollTimer = null;

async function openActivityPanel(identifier) {
  const agent = lastRunningAgents.find(r => r.issue_identifier === identifier);
  let title = 'Agent: ' + identifier;
  if (agent) {
    const parts = [];
    if (agent.focus_role) parts.push(agent.focus_role);
    if (agent.agent_profile) parts.push(agent.agent_profile);
    if (parts.length > 0) title += ' — ' + parts.join(' · ');
  }
  const titleEl = document.getElementById('activity-title');
  titleEl.textContent = title;
  titleEl.dataset.identifier = identifier;
  document.getElementById('activity-overlay').classList.add('open');
  await refreshActivity(identifier);
  // Only poll if WebSocket is not connected
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    activityPollTimer = setInterval(() => refreshActivity(identifier), 2000);
  }
}

function closeActivityPanel() {
  const el = document.getElementById('activity-overlay');
  if (el) el.classList.remove('open');
  if (activityPollTimer) { clearInterval(activityPollTimer); activityPollTimer = null; }
}

function renderActivityEntry(a) {
  const hasDetail = a.detail && a.detail.trim().length > 0;
  const div = document.createElement('div');
  div.className = 'activity-entry';
  if (hasDetail) {
    div.style.cursor = 'pointer';
    div.addEventListener('click', () => div.classList.toggle('expanded'));
  }
  div.innerHTML =
    '<span class="activity-turn">' + esc(String(a.turn || '')) + '</span>' +
    '<span class="activity-kind ' + esc(a.kind || '') + '">' + esc(a.kind || '') + '</span>' +
    '<span class="activity-summary">' + esc(a.summary || '') +
      (hasDetail ? ' <span style="color:var(--text-muted);font-size:0.7rem;">&#9660;</span>' : '') +
    '</span>' +
    (hasDetail ? '<div class="activity-detail">' + esc(a.detail) + '</div>' : '');
  return div;
}

function handleActivityPush(identifier, entry) {
  // Only update if the activity panel is open for this agent
  const overlay = document.getElementById('activity-overlay');
  if (!overlay || !overlay.classList.contains('open')) return;
  const titleEl = document.getElementById('activity-title');
  if (titleEl.dataset.identifier !== identifier) return;
  const body = document.getElementById('activity-body');
  body.appendChild(renderActivityEntry(entry));
  body.scrollTop = body.scrollHeight;
}

async function refreshActivity(identifier) {
  try {
    const res = await fetch('/api/v1/agents/' + encodeURIComponent(identifier) + '/activity');
    const data = await res.json();
    const body = document.getElementById('activity-body');
    const entries = data.activity || [];
    if (entries.length === 0) {
      body.innerHTML = '<div style="color:var(--text-muted);text-align:center;padding:2rem;">No activity yet...</div>';
      return;
    }
    body.innerHTML = '';
    for (const a of entries) {
      body.appendChild(renderActivityEntry(a));
    }
    body.scrollTop = body.scrollHeight;
  } catch(e) {}
}

// --- Detail panel ---
let _openDetailIdentifier = null;
let _detailRefreshTimer = null;

function refreshOpenDetailPanel() {
  if (!_openDetailIdentifier) return;
  if (!document.getElementById('detail-panel').classList.contains('open')) return;
  // Do not overwrite while user is editing title, description, or comment.
  const focused = document.activeElement;
  if (focused && focused.classList.contains('detail-editable')) return;
  const commentInput = document.getElementById('comment-input');
  if (commentInput && document.activeElement === commentInput) return;
  // Debounce: wait 500ms to batch rapid updates
  if (_detailRefreshTimer) clearTimeout(_detailRefreshTimer);
  _detailRefreshTimer = setTimeout(() => {
    _detailRefreshTimer = null;
    // Re-check: user may have started editing during the debounce window
    const stillFocused = document.activeElement;
    if (stillFocused && stillFocused.classList.contains('detail-editable')) return;
    const ci = document.getElementById('comment-input');
    if (ci && document.activeElement === ci) return;
    if (_openDetailIdentifier) openDetailPanel(_openDetailIdentifier);
  }, 500);
}

async function openDetailPanel(identifier) {
  _openDetailIdentifier = identifier;
  const panel = document.getElementById('detail-panel');
  const body = document.getElementById('detail-panel-body');
  const isRefresh = panel.classList.contains('open');
  if (!isRefresh) {
    body.innerHTML = '<div style="color:var(--text-muted);font-size:0.8rem;">Loading...</div>';
  }
  panel.classList.add('open');

  const issue = allIssuesFlat.find(i => i.identifier === identifier);
  const pidParam = issue && issue.project_id ? `?project_id=${encodeURIComponent(issue.project_id)}` : '';
  const res = await fetch(`/api/v1/issues/${encodeURIComponent(identifier)}/detail${pidParam}`);
  if (!res.ok) {
    body.innerHTML = '<div style="color:var(--red);font-size:0.8rem;">Failed to load</div>';
    return;
  }
  const detail = await res.json();
  document.getElementById('detail-panel-title').textContent = detail.identifier;
  body.dataset.projectId = detail.project_id || '';

  const pClass = `p${detail.priority ?? 4}`;
  let html = `
    <div class="detail-field">
      <div class="detail-field-label">Title</div>
      <div class="detail-editable" contenteditable="true" spellcheck="false"
           id="detail-title-edit" data-field="title" data-placeholder="No title"
           data-id="${esc(detail.identifier)}">${esc(detail.title)}</div>
    </div>
    <div class="detail-field">
      <div class="detail-field-label">Type</div>
      <div class="detail-field-value">${esc(detail.issue_type)}</div>
    </div>
    <div class="detail-field">
      <div class="detail-field-label">State</div>
      <div class="detail-field-value">${esc(detail.state)}</div>
    </div>
    <div class="detail-field">
      <div class="detail-field-label">Priority</div>
      <div class="detail-field-value"><span class="priority-badge ${pClass}">P${detail.priority ?? 4}</span></div>
    </div>
    <div class="detail-field">
      <div class="detail-field-label">Description</div>
      <div class="detail-editable" contenteditable="true" spellcheck="false"
           id="detail-desc-edit" data-field="description" data-placeholder="No description"
           data-id="${esc(detail.identifier)}">${esc(detail.description || '')}</div>
    </div>
  `;

  if (detail.parent_id) {
    const epic = getEpicById(detail.parent_id);
    if (epic) {
      html += `
        <div class="detail-field">
          <div class="detail-field-label">Parent Epic</div>
          <div class="detail-field-value">
            <span class="epic-badge" style="cursor:pointer" onclick="openDetailPanel('${esc(epic.identifier)}')">${esc(epic.identifier)}</span>
            ${esc(epic.title)}
          </div>
        </div>
      `;
    }
  }

  if (detail.created_at) {
    html += `
      <div class="detail-field">
        <div class="detail-field-label">Created</div>
        <div class="detail-field-value">${new Date(detail.created_at).toLocaleString()}</div>
      </div>
    `;
  }

  if (detail.children && detail.children.length > 0) {
    html += `
      <div class="detail-field">
        <div class="detail-field-label">Children (${detail.children.length})</div>
        <ul class="detail-children-list">
          ${detail.children.map(c => `
            <li onclick="openDetailPanel('${esc(c.identifier)}')">
              <span>${esc(c.identifier)} ${esc(c.title)}</span>
              <span class="detail-child-state">${esc(c.state)}</span>
            </li>
          `).join('')}
        </ul>
      </div>
    `;

    html += `
      <button onclick="openCreateDialogForEpic('${esc(detail.id)}')" style="margin-top:0.5rem;width:100%;">+ Create Child</button>
    `;
  } else if (detail.issue_type === 'epic') {
    html += `
      <div class="detail-field">
        <div class="detail-field-label">Children</div>
        <div class="detail-field-value" style="color:var(--text-muted)">No children yet</div>
      </div>
      <button onclick="openCreateDialogForEpic('${esc(detail.id)}')" style="margin-top:0.5rem;width:100%;">+ Create Child</button>
    `;
  }

  // Comments section
  const comments = detail.comments || [];
  html += `
    <div class="detail-field" style="margin-top:1rem; border-top:1px solid var(--border); padding-top:1rem;">
      <div class="detail-field-label">Comments (${comments.length})</div>
      <div class="comments-list" id="comments-list">
        ${comments.length === 0 ? '<div style="color:var(--text-muted);font-size:0.75rem;padding:0.3rem 0;">No comments yet</div>' : ''}
        ${comments.map(c => `
          <div class="comment">
            <div class="comment-header">
              <span class="comment-author">${esc(c.author || 'unknown')}</span>
              <span class="comment-time">${c.created_at ? new Date(c.created_at).toLocaleString() : ''}</span>
            </div>
            <div class="comment-text">${esc(c.text)}</div>
          </div>
        `).join('')}
      </div>
      <div class="comment-input-area">
        <textarea id="comment-input" class="comment-input" placeholder="Add a comment..." rows="2"></textarea>
        <button onclick="submitComment('${esc(detail.identifier)}')" style="margin-top:0.3rem;width:100%;">Post Comment</button>
      </div>
    </div>
  `;

  // Preserve in-progress comment text across refreshes
  const prevInput = document.getElementById('comment-input');
  const prevText = prevInput ? prevInput.value : '';

  body.innerHTML = html;

  // Wire up editable title and description fields
  for (const el of body.querySelectorAll('.detail-editable')) {
    el.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey && el.id === 'detail-title-edit') {
        // Single-line feel for title: Enter saves
        e.preventDefault();
        el.blur();
      }
      if (e.key === 'Escape') el.blur();
    });
    el.addEventListener('blur', async () => {
      const field = el.dataset.field;
      const id = el.dataset.id;
      const newValue = el.textContent.trim();
      const pid = document.getElementById('detail-panel-body').dataset.projectId;
      await updateIssue(id, {[field]: newValue, project_id: pid});
    });
  }

  // Restore comment draft and scroll to bottom
  if (prevText) {
    const newInput = document.getElementById('comment-input');
    if (newInput) newInput.value = prevText;
  }
  const commentsList = document.getElementById('comments-list');
  if (commentsList) commentsList.scrollTop = commentsList.scrollHeight;
}

async function submitComment(identifier) {
  const input = document.getElementById('comment-input');
  const text = input.value.trim();
  if (!text) return;
  input.value = '';
  await fetch(`/api/v1/issues/${encodeURIComponent(identifier)}/comments`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({text, author: 'user', project_id: document.getElementById('detail-panel-body').dataset.projectId}),
  });
  // Reload detail panel to show new comment
  openDetailPanel(identifier);
}

function closeDetailPanel() {
  _openDetailIdentifier = null;
  document.getElementById('detail-panel').classList.remove('open');
}

// --- Create dialog ---
let createParentId = null;

function populateProjectSelect(selectedId) {
  const row = document.getElementById('create-project-row');
  const sel = document.getElementById('create-project-select');
  if (!row || !sel) return;
  if (currentProjects.length === 0) {
    row.style.display = 'none';
    return;
  }
  row.style.display = '';
  sel.innerHTML = currentProjects.map(p =>
    '<option value="' + esc(p.id) + '"' + (p.id === selectedId ? ' selected' : '') + '>' + esc(p.name) + '</option>'
  ).join('');
}

function openCreateDialog() {
  createParentId = null;
  document.getElementById('create-dialog-title').textContent = 'Create Issue';
  document.getElementById('create-dialog').classList.add('open');
  document.getElementById('create-title').value = '';
  document.getElementById('create-desc').value = '';
  document.getElementById('create-type').value = 'task';
  document.getElementById('create-priority').value = '2';
  // Show all types when creating standalone
  const typeSelect = document.getElementById('create-type');
  typeSelect.querySelector('option[value="epic"]').style.display = '';
  // Pre-select the currently filtered project (if any)
  const filterSel = document.getElementById('project-filter');
  const defaultProjectId = filterSel ? filterSel.value : '';
  populateProjectSelect(defaultProjectId);
  setTimeout(() => document.getElementById('create-title').focus(), 50);
}

function openCreateDialogForEpic(epicId) {
  createParentId = epicId;
  const epic = allIssuesFlat.find(i => i.id === epicId);
  document.getElementById('create-dialog-title').textContent =
    epic ? `Create Child of ${epic.identifier}` : 'Create Child';
  document.getElementById('create-dialog').classList.add('open');
  document.getElementById('create-title').value = '';
  document.getElementById('create-desc').value = '';
  document.getElementById('create-type').value = 'task';
  document.getElementById('create-priority').value = '2';
  // Hide epic type when creating children
  const typeSelect = document.getElementById('create-type');
  typeSelect.querySelector('option[value="epic"]').style.display = 'none';
  // Pre-select the epic's project
  const epicProjectId = epic && epic.project_id ? epic.project_id : '';
  populateProjectSelect(epicProjectId);
  setTimeout(() => document.getElementById('create-title').focus(), 50);
}

function closeCreateDialog() {
  document.getElementById('create-dialog').classList.remove('open');
  createParentId = null;
}

async function submitCreateDialog() {
  const title = document.getElementById('create-title').value.trim();
  if (!title) return;

  const btn = document.getElementById('create-submit');
  btn.disabled = true;
  btn.textContent = 'Creating...';

  try {
    const body = {
      title,
      type: document.getElementById('create-type').value,
      description: document.getElementById('create-desc').value.trim() || undefined,
      priority: parseInt(document.getElementById('create-priority').value, 10),
    };
    if (createParentId) {
      body.parent_id = createParentId;
    }
    // Use project from dialog selector if available
    const projectSel = document.getElementById('create-project-select');
    if (projectSel && projectSel.value) {
      body.project_id = projectSel.value;
    }
    // Fallback: if no project selector (single-project mode), use the parent epic's project
    if (!body.project_id && createParentId) {
      const epic = allIssuesFlat.find(i => i.id === createParentId);
      if (epic && epic.project_id) body.project_id = epic.project_id;
    }
    // Last resort: selected project filter
    if (!body.project_id) {
      const sel = document.getElementById('project-filter');
      if (sel && sel.value) body.project_id = sel.value;
    }
    const res = await fetch('/api/v1/issues', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    });
    if (res.ok) {
      closeCreateDialog();
      await refreshBoard();
      // Re-open detail panel if we were creating a child
      if (createParentId) {
        const epic = allIssuesFlat.find(i => i.id === createParentId);
        if (epic) openDetailPanel(epic.identifier);
      }
    }
  } finally {
    btn.disabled = false;
    btn.textContent = 'Create';
  }
}

// Close on Escape
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    closeCreateDialog();
    closeDetailPanel();
    closeActivityPanel();
  }
});

// Initial load via WebSocket (falls back to REST if WS fails)
connectWebSocket();
</script>

<div class="dialog-overlay" id="create-dialog" onclick="if(event.target===this)closeCreateDialog()">
  <div class="dialog">
    <h2 id="create-dialog-title">Create Issue</h2>
    <div id="create-project-row" style="display:none;">
      <label for="create-project-select">Project</label>
      <select id="create-project-select"></select>
    </div>
    <label for="create-type">Type</label>
    <select id="create-type">
      <option value="task">Task</option>
      <option value="bug">Bug</option>
      <option value="feature">Feature</option>
      <option value="epic">Epic</option>
      <option value="chore">Chore</option>
    </select>
    <label for="create-title">Summary</label>
    <input type="text" id="create-title" placeholder="Brief issue summary"
           onkeydown="if(event.key==='Enter')submitCreateDialog()">
    <label for="create-priority">Priority</label>
    <select id="create-priority">
      <option value="0">P0 &mdash; Critical</option>
      <option value="1">P1 &mdash; High</option>
      <option value="2" selected>P2 &mdash; Medium</option>
      <option value="3">P3 &mdash; Low</option>
      <option value="4">P4 &mdash; Backlog</option>
    </select>
    <label for="create-desc">Description</label>
    <textarea id="create-desc" placeholder="Optional details..."></textarea>
    <div class="dialog-actions">
      <button onclick="closeCreateDialog()">Cancel</button>
      <button class="btn-primary" id="create-submit" onclick="submitCreateDialog()">Create</button>
    </div>
  </div>
</div>

<div class="activity-overlay" id="activity-overlay" onclick="if(event.target===this)closeActivityPanel()">
  <div class="activity-panel">
    <div class="activity-header">
      <h3 id="activity-title">Agent Activity</h3>
      <button onclick="closeActivityPanel()">&times;</button>
    </div>
    <div class="activity-body" id="activity-body">
      <div style="color: var(--text-muted); text-align: center; padding: 2rem;">Loading...</div>
    </div>
  </div>
</div>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve the kanban dashboard."""
    return DASHBOARD_HTML


PROVIDERS_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>oompah - Providers</title>
  <style>
    :root {
      --bg: #0d1117;
      --surface: #161b22;
      --border: #30363d;
      --text: #e6edf3;
      --text-muted: #7d8590;
      --accent: #58a6ff;
      --green: #3fb950;
      --red: #f85149;
    }
    html { font-size: 125%; }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
    }
    .toolbar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 0.75rem 1.5rem;
      border-bottom: 1px solid var(--border);
    }
    .toolbar h1 {
      font-size: 1.25rem;
      color: var(--accent);
      font-weight: 700;
    }
    .toolbar h1 a { color: var(--accent); text-decoration: none; }
    .toolbar h1 span { color: var(--text-muted); font-weight: 400; }
    button {
      background: var(--surface);
      color: var(--accent);
      border: 1px solid var(--border);
      padding: 0.3rem 0.75rem;
      border-radius: 6px;
      cursor: pointer;
      font-size: 0.75rem;
      font-weight: 600;
    }
    button:hover { background: rgba(88, 166, 255, 0.1); }
    .btn-primary {
      background: var(--accent);
      color: var(--bg);
      border-color: var(--accent);
    }
    .btn-primary:hover { background: #79bbff; }
    .btn-danger {
      color: var(--red);
      border-color: rgba(248, 81, 73, 0.3);
    }
    .btn-danger:hover { background: rgba(248, 81, 73, 0.1); }

    .content {
      max-width: 900px;
      margin: 2rem auto;
      padding: 0 1.5rem;
    }
    .content h2 {
      font-size: 1.1rem;
      margin-bottom: 1rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .provider-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 1rem 1.25rem;
      margin-bottom: 0.75rem;
    }
    .provider-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 0.5rem;
    }
    .provider-name {
      font-size: 1rem;
      font-weight: 600;
    }
    .provider-type {
      font-size: 0.7rem;
      padding: 0.1rem 0.4rem;
      border-radius: 4px;
      background: rgba(88, 166, 255, 0.15);
      color: var(--accent);
      font-family: 'SF Mono', 'Fira Code', monospace;
    }
    .provider-detail {
      font-size: 0.8rem;
      color: var(--text-muted);
      margin-bottom: 0.25rem;
    }
    .provider-detail code {
      color: var(--text);
      font-family: 'SF Mono', 'Fira Code', monospace;
      font-size: 0.75rem;
    }
    .provider-models {
      display: flex;
      flex-wrap: wrap;
      gap: 0.3rem;
      margin-top: 0.4rem;
    }
    .model-tag {
      font-size: 0.65rem;
      padding: 0.15rem 0.4rem;
      border-radius: 4px;
      background: var(--bg);
      border: 1px solid var(--border);
      color: var(--text-muted);
      font-family: 'SF Mono', 'Fira Code', monospace;
    }
    .model-tag.default {
      border-color: var(--green);
      color: var(--green);
    }

    /* Tag input for models */
    .tag-input-wrap {
      display: flex;
      flex-wrap: wrap;
      gap: 0.3rem;
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 0.35rem 0.5rem;
      min-height: 38px;
      max-height: 30vh;
      overflow-y: auto;
      cursor: text;
    }
    .tag-input-wrap:focus-within { border-color: var(--accent); }
    .tag-input-wrap .tag {
      display: flex;
      align-items: center;
      gap: 0.2rem;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 4px;
      padding: 0.15rem 0.4rem;
      font-size: 0.75rem;
      font-family: 'SF Mono', 'Fira Code', monospace;
      color: var(--text);
    }
    .tag-input-wrap .tag .tag-remove {
      cursor: pointer;
      color: var(--text-muted);
      font-size: 0.85rem;
      line-height: 1;
      margin-left: 0.15rem;
    }
    .tag-input-wrap .tag .tag-remove:hover { color: var(--red); }
    .tag-input-wrap input {
      border: none;
      background: none;
      outline: none;
      color: var(--text);
      font-size: 0.8rem;
      flex: 1;
      min-width: 100px;
      padding: 0.15rem 0;
    }
    .provider-actions {
      display: flex;
      gap: 0.4rem;
      margin-top: 0.6rem;
    }
    .empty-state {
      text-align: center;
      padding: 3rem 1rem;
      color: var(--text-muted);
      font-size: 0.9rem;
    }

    /* Form dialog */
    .dialog-overlay {
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.6);
      z-index: 100;
      justify-content: center;
      align-items: flex-start;
      overflow-y: auto;
      padding: 2rem 1rem;
    }
    .dialog-overlay.open { display: flex; }
    .dialog {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1.5rem;
      width: 520px;
      max-width: 90vw;
      max-height: none;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
      margin: auto;
    }
    .dialog h2 {
      font-size: 1rem;
      margin-bottom: 1rem;
      color: var(--text);
    }
    .dialog label {
      display: block;
      font-size: 0.75rem;
      color: var(--text-muted);
      margin-bottom: 0.25rem;
      margin-top: 0.75rem;
    }
    .dialog label:first-of-type { margin-top: 0; }
    .dialog input, .dialog select, .dialog textarea {
      width: 100%;
      background: var(--bg);
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 0.5rem 0.6rem;
      font-size: 0.85rem;
      font-family: inherit;
      outline: none;
    }
    .dialog input:focus, .dialog select:focus { border-color: var(--accent); }
    .dialog .hint {
      font-size: 0.7rem;
      color: var(--text-muted);
      margin-top: 0.2rem;
    }
    .dialog-actions {
      display: flex;
      justify-content: flex-end;
      gap: 0.5rem;
      margin-top: 1.25rem;
    }
    .dialog-actions button {
      padding: 0.4rem 1rem;
      font-size: 0.8rem;
    }
  </style>
</head>
<body>
  <div class="toolbar">
    <h1><a href="/">oompah</a> <span>/ providers</span></h1>
    <div style="display: flex; gap: 0.5rem;">
      <button onclick="window.location='/'">Back to Board</button>
    </div>
  </div>
  <div class="content">
    <h2>
      Model Providers
      <button class="btn-primary" onclick="openProviderDialog()">+ Add Provider</button>
    </h2>
    <div id="providers-list"></div>
  </div>

<script>
let providers = [];
let editingId = null;

async function loadProviders() {
  const res = await fetch('/api/v1/providers');
  if (!res.ok) return;
  providers = await res.json();
  renderProviders();
}

function renderProviders() {
  const container = document.getElementById('providers-list');
  if (providers.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        No providers configured yet.<br>
        Add an OpenAI-compatible API endpoint to get started.
      </div>
    `;
    return;
  }

  container.innerHTML = providers.map(p => `
    <div class="provider-card">
      <div class="provider-header">
        <span class="provider-name">${esc(p.name)}</span>
        <span class="provider-type">${esc(p.provider_type)}</span>
      </div>
      <div class="provider-detail">URL: <code>${esc(p.base_url)}</code></div>
      <div class="provider-detail">API Key: <code>${esc(p.api_key_masked || 'not set')}</code></div>
      ${p.models && p.models.length > 0 ? `
        <div class="provider-models">
          ${p.models.map(m => `
            <span class="model-tag ${m === p.default_model ? 'default' : ''}">${esc(m)}${m === p.default_model ? ' *' : ''}</span>
          `).join('')}
        </div>
      ` : '<div class="provider-detail" style="margin-top:0.3rem;">No models configured</div>'}
      <div class="provider-actions">
        <button onclick="editProvider('${esc(p.id)}')">Edit</button>
        <button class="btn-danger" onclick="deleteProvider('${esc(p.id)}', '${esc(p.name)}')">Delete</button>
      </div>
    </div>
  `).join('');
}

let dialogModels = [];

function openProviderDialog(provider) {
  editingId = provider ? provider.id : null;
  document.getElementById('dialog-title').textContent = provider ? 'Edit Provider' : 'Add Provider';
  document.getElementById('prov-name').value = provider ? provider.name : '';
  document.getElementById('prov-type').value = provider ? provider.provider_type : 'openai';
  document.getElementById('prov-url').value = provider ? provider.base_url : '';
  document.getElementById('prov-key').value = '';
  document.getElementById('prov-key').placeholder = provider ? 'Leave blank to keep current key' : 'sk-...';
  dialogModels = provider && provider.models ? [...provider.models] : [];
  renderModelTags();
  syncDefaultModelSelect(provider ? (provider.default_model || '') : '');
  document.getElementById('prov-models-input').value = '';
  document.getElementById('provider-dialog').classList.add('open');
  setTimeout(() => document.getElementById('prov-name').focus(), 50);
}

function addModel(name) {
  name = name.trim();
  if (!name || dialogModels.includes(name)) return;
  dialogModels.push(name);
  renderModelTags();
  const sel = document.getElementById('prov-default-model');
  syncDefaultModelSelect(sel.value);
}

function removeModel(name) {
  dialogModels = dialogModels.filter(m => m !== name);
  renderModelTags();
  const sel = document.getElementById('prov-default-model');
  syncDefaultModelSelect(sel.value === name ? '' : sel.value);
}

function renderModelTags() {
  const wrap = document.getElementById('prov-models-wrap');
  const input = document.getElementById('prov-models-input');
  wrap.querySelectorAll('.tag').forEach(t => t.remove());
  dialogModels.forEach(m => {
    const tag = document.createElement('span');
    tag.className = 'tag';
    tag.textContent = m;
    const rm = document.createElement('span');
    rm.className = 'tag-remove';
    rm.textContent = '\u00d7';
    rm.addEventListener('click', () => removeModel(m));
    tag.appendChild(rm);
    wrap.insertBefore(tag, input);
  });
}

function syncDefaultModelSelect(currentVal) {
  const sel = document.getElementById('prov-default-model');
  sel.innerHTML = '<option value="">— none —</option>';
  dialogModels.forEach(m => {
    const opt = document.createElement('option');
    opt.value = m;
    opt.textContent = m;
    sel.appendChild(opt);
  });
  if (currentVal && dialogModels.includes(currentVal)) {
    sel.value = currentVal;
  }
}

async function fetchModelsFromProvider() {
  const base_url = document.getElementById('prov-url').value.trim();
  const api_key = document.getElementById('prov-key').value.trim();
  if (!base_url) { alert('Enter a Base URL first.'); return; }
  const btn = document.getElementById('fetch-models-btn');
  btn.textContent = 'Fetching...';
  btn.disabled = true;
  try {
    const res = await fetch('/api/v1/providers/fetch-models', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({base_url, api_key, provider_id: editingId || undefined}),
    });
    const data = await res.json();
    if (data.models && data.models.length > 0) {
      const prevDefault = document.getElementById('prov-default-model').value;
      data.models.forEach(m => addModel(m));
      syncDefaultModelSelect(prevDefault);
    } else {
      alert(data.error ? 'Error: ' + data.error : 'No models found at this endpoint.');
    }
  } catch (e) {
    alert('Failed to fetch models: ' + e.message);
  } finally {
    btn.textContent = 'Fetch Models';
    btn.disabled = false;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('prov-models-input').addEventListener('keydown', e => {
    const input = e.target;
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      addModel(input.value.replace(',', ''));
      input.value = '';
    }
    if (e.key === 'Backspace' && !input.value && dialogModels.length) {
      removeModel(dialogModels[dialogModels.length - 1]);
    }
  });

  document.getElementById('prov-models-input').addEventListener('blur', e => {
    const val = e.target.value.trim();
    if (val) {
      addModel(val);
      e.target.value = '';
    }
  });

  loadProviders();
});

function closeProviderDialog() {
  document.getElementById('provider-dialog').classList.remove('open');
  editingId = null;
}

function editProvider(id) {
  const p = providers.find(x => x.id === id);
  if (p) openProviderDialog(p);
}

async function deleteProvider(id, name) {
  if (!confirm(`Delete provider "${name}"?`)) return;
  await fetch(`/api/v1/providers/${id}`, {method: 'DELETE'});
  await loadProviders();
}

async function submitProvider() {
  const name = document.getElementById('prov-name').value.trim();
  const base_url = document.getElementById('prov-url').value.trim();
  if (!name || !base_url) return;

  const body = {
    name,
    base_url,
    provider_type: document.getElementById('prov-type').value,
    models: [...dialogModels],
    default_model: document.getElementById('prov-default-model').value.trim() || undefined,
  };

  const apiKey = document.getElementById('prov-key').value.trim();
  if (apiKey) body.api_key = apiKey;

  if (editingId) {
    await fetch(`/api/v1/providers/${editingId}`, {
      method: 'PATCH',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    });
  } else {
    body.api_key = apiKey;
    await fetch('/api/v1/providers', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    });
  }

  closeProviderDialog();
  await loadProviders();
}

function esc(s) {
  if (!s) return '';
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeProviderDialog();
});

</script>

<div class="dialog-overlay" id="provider-dialog" onclick="if(event.target===this)closeProviderDialog()">
  <div class="dialog">
    <h2 id="dialog-title">Add Provider</h2>
    <label for="prov-name">Name</label>
    <input type="text" id="prov-name" placeholder="e.g., OpenAI, Anthropic, Ollama">
    <label for="prov-type">Provider Type</label>
    <select id="prov-type">
      <option value="openai">OpenAI Compatible</option>
      <option value="anthropic">Anthropic</option>
      <option value="custom">Custom</option>
    </select>
    <label for="prov-url">Base URL</label>
    <input type="text" id="prov-url" placeholder="https://api.openai.com/v1">
    <div class="hint">The API base URL. For local models, use http://localhost:PORT/v1</div>
    <label for="prov-key">API Key</label>
    <input type="password" id="prov-key" placeholder="sk-...">
    <label style="display:flex;justify-content:space-between;align-items:center;">
      Models
      <button type="button" id="fetch-models-btn" onclick="fetchModelsFromProvider()" style="font-size:0.65rem;padding:0.15rem 0.5rem;">Fetch Models</button>
    </label>
    <div class="tag-input-wrap" id="prov-models-wrap" onclick="document.getElementById('prov-models-input').focus()">
      <input type="text" id="prov-models-input" placeholder="Type model name and press Enter">
    </div>
    <div class="hint">Press Enter or comma to add a model, or click Fetch Models to auto-discover</div>
    <label for="prov-default-model">Default Model</label>
    <select id="prov-default-model">
      <option value="">— none —</option>
    </select>
    <div class="hint">Model to use when no specific model is requested</div>
    <div class="dialog-actions">
      <button onclick="closeProviderDialog()">Cancel</button>
      <button class="btn-primary" onclick="submitProvider()">Save</button>
    </div>
  </div>
</div>
</body>
</html>
"""


@app.get("/providers", response_class=HTMLResponse)
async def providers_page():
    """Serve the providers management page."""
    return PROVIDERS_HTML


PROJECTS_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>oompah - Projects</title>
  <style>
    :root {
      --bg: #0d1117; --surface: #161b22; --border: #30363d;
      --text: #e6edf3; --text-muted: #7d8590; --accent: #58a6ff;
      --green: #3fb950; --red: #f85149;
    }
    html { font-size: 125%; }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }
    .toolbar { display: flex; justify-content: space-between; align-items: center; padding: 0.75rem 1.5rem; border-bottom: 1px solid var(--border); }
    .toolbar h1 { font-size: 1.25rem; color: var(--accent); font-weight: 700; }
    .toolbar h1 a { color: var(--accent); text-decoration: none; }
    .toolbar h1 span { color: var(--text-muted); font-weight: 400; }
    button { background: var(--surface); color: var(--accent); border: 1px solid var(--border); padding: 0.3rem 0.75rem; border-radius: 6px; cursor: pointer; font-size: 0.75rem; font-weight: 600; }
    button:hover { background: rgba(88, 166, 255, 0.1); }
    .btn-primary { background: var(--accent); color: var(--bg); border-color: var(--accent); }
    .btn-primary:hover { background: #79bbff; }
    .btn-danger { color: var(--red); border-color: rgba(248, 81, 73, 0.3); }
    .btn-danger:hover { background: rgba(248, 81, 73, 0.1); }
    .content { max-width: 900px; margin: 2rem auto; padding: 0 1.5rem; }
    .content h2 { font-size: 1.1rem; margin-bottom: 1rem; display: flex; justify-content: space-between; align-items: center; }
    .project-card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 1rem 1.25rem; margin-bottom: 0.75rem; }
    .project-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; }
    .project-name { font-size: 1rem; font-weight: 600; }
    .project-id { font-size: 0.7rem; color: var(--text-muted); font-family: 'SF Mono', 'Fira Code', monospace; }
    .field-row { display: flex; gap: 0.5rem; align-items: center; margin-top: 0.35rem; font-size: 0.8rem; color: var(--text-muted); }
    .field-label { font-weight: 600; min-width: 80px; }
    .field-value { font-family: 'SF Mono', 'Fira Code', monospace; font-size: 0.75rem; word-break: break-all; }
    .form-group { margin-bottom: 0.75rem; }
    .form-group label { display: block; font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.25rem; }
    .form-group input { width: 100%; padding: 0.4rem 0.6rem; border-radius: 6px; border: 1px solid var(--border); background: var(--bg); color: var(--text); font-size: 0.85rem; }
    .form-card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 1.25rem; margin-bottom: 1rem; display: none; }
    .form-actions { display: flex; gap: 0.5rem; justify-content: flex-end; margin-top: 0.75rem; }
    .empty-state { text-align: center; padding: 3rem; color: var(--text-muted); }
    .worktree-list { font-size: 0.75rem; color: var(--text-muted); font-family: monospace; margin-top: 0.5rem; }
  </style>
</head>
<body>
  <div class="toolbar">
    <h1><a href="/">oompah</a> <span>/ Projects</span></h1>
    <div style="display:flex;gap:0.5rem;">
      <button onclick="window.location='/'">Dashboard</button>
      <button onclick="window.location='/providers'">Providers</button>
    </div>
  </div>

  <div class="content">
    <h2>Projects <button class="btn-primary" onclick="toggleAddForm()">+ Add Project</button></h2>

    <div class="form-card" id="add-form">
      <div class="form-group">
        <label>Git Repository URL</label>
        <input type="text" id="add-repo" placeholder="https://github.com/org/repo.git">
      </div>
      <div class="form-group">
        <label>Name (optional &mdash; defaults to repo name)</label>
        <input type="text" id="add-name" placeholder="">
      </div>
      <div class="form-group">
        <label>Branch</label>
        <input type="text" id="add-branch" placeholder="main" value="main">
      </div>
      <div class="form-group">
        <label>Git User Name (defaults to global git config)</label>
        <input type="text" id="add-git-user-name" placeholder="">
      </div>
      <div class="form-group">
        <label>Git User Email (defaults to global git config)</label>
        <input type="text" id="add-git-user-email" placeholder="">
      </div>
      <div id="add-error" style="color:var(--red);font-size:0.8rem;margin-bottom:0.5rem;display:none;"></div>
      <div class="form-actions">
        <button onclick="toggleAddForm()">Cancel</button>
        <button class="btn-primary" onclick="addProject()">Add Project</button>
      </div>
    </div>

    <div id="project-list"></div>
  </div>

<script>
async function loadProjects() {
  const res = await fetch('/api/v1/projects');
  const projects = await res.json();
  const container = document.getElementById('project-list');
  if (projects.length === 0) {
    container.innerHTML = '<div class="empty-state">No projects configured.<br>Add a git repo with beads to get started.</div>';
    return;
  }
  container.innerHTML = projects.map(p => `
    <div class="project-card" id="card-${esc(p.id)}">
      <div class="project-header">
        <span class="project-name">${esc(p.name)}</span>
        <span class="project-id">${esc(p.id)}</span>
      </div>
      <div class="field-row">
        <span class="field-label">Repo:</span>
        <span class="field-value">${esc(p.repo_url)}</span>
      </div>
      <div class="field-row">
        <span class="field-label">Local:</span>
        <span class="field-value">${esc(p.repo_path)}</span>
      </div>
      <div class="field-row">
        <span class="field-label">Branch:</span>
        <span class="field-value">${esc(p.branch)}</span>
      </div>
      ${p.git_user_name ? `<div class="field-row">
        <span class="field-label">Git User:</span>
        <span class="field-value">${esc(p.git_user_name)} &lt;${esc(p.git_user_email || '')}&gt;</span>
      </div>` : ''}
      <div class="field-row" style="margin-top:0.75rem;">
        <button onclick="showWorktrees('${esc(p.id)}')">Worktrees</button>
        <button class="btn-danger" onclick="deleteProject('${esc(p.id)}', '${esc(p.name)}')">Delete</button>
      </div>
      <div class="worktree-list" id="wt-${esc(p.id)}" style="display:none;"></div>
    </div>
  `).join('');
}

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function toggleAddForm() {
  const f = document.getElementById('add-form');
  f.style.display = f.style.display === 'none' ? 'block' : 'none';
  document.getElementById('add-error').style.display = 'none';
}

async function addProject() {
  const repo = document.getElementById('add-repo').value.trim();
  const name = document.getElementById('add-name').value.trim() || undefined;
  const branch = document.getElementById('add-branch').value.trim() || 'main';
  const gitUserName = document.getElementById('add-git-user-name').value.trim() || undefined;
  const gitUserEmail = document.getElementById('add-git-user-email').value.trim() || undefined;
  const errEl = document.getElementById('add-error');
  if (!repo) {
    errEl.textContent = 'Repository URL is required';
    errEl.style.display = 'block';
    return;
  }
  const res = await fetch('/api/v1/projects', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({repo_url: repo, name, branch, git_user_name: gitUserName, git_user_email: gitUserEmail}),
  });
  if (res.ok) {
    toggleAddForm();
    document.getElementById('add-name').value = '';
    document.getElementById('add-repo').value = '';
    document.getElementById('add-branch').value = 'main';
    document.getElementById('add-git-user-name').value = '';
    document.getElementById('add-git-user-email').value = '';
    loadProjects();
  } else {
    const data = await res.json();
    errEl.textContent = (data.error && data.error.message) || 'Failed to add project';
    errEl.style.display = 'block';
  }
}

async function deleteProject(id, name) {
  if (!confirm('Delete project "' + name + '"? This does not delete the repo.')) return;
  await fetch('/api/v1/projects/' + id, {method: 'DELETE'});
  loadProjects();
}

async function showWorktrees(id) {
  const el = document.getElementById('wt-' + id);
  if (el.style.display !== 'none') { el.style.display = 'none'; return; }
  const res = await fetch('/api/v1/projects/' + id + '/worktrees');
  const data = await res.json();
  const wts = data.worktrees || [];
  el.innerHTML = wts.length > 0
    ? '<strong>Active worktrees:</strong><br>' + wts.map(w => esc(w)).join('<br>')
    : '<em>No active worktrees</em>';
  el.style.display = 'block';
}

loadProjects();
</script>
</body>
</html>
"""


@app.get("/projects-manage", response_class=HTMLResponse)
async def projects_page():
    """Serve the projects management page."""
    return PROJECTS_HTML


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


FOCI_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>oompah - Foci</title>
  <style>
    :root {
      --bg: #0d1117; --surface: #161b22; --border: #30363d;
      --text: #e6edf3; --text-muted: #7d8590; --accent: #58a6ff;
      --green: #3fb950; --red: #f85149; --yellow: #e2b340;
    }
    html { font-size: 125%; }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }
    .toolbar { display: flex; justify-content: space-between; align-items: center; padding: 0.75rem 1.5rem; border-bottom: 1px solid var(--border); }
    .toolbar h1 { font-size: 1.25rem; color: var(--accent); font-weight: 700; }
    .toolbar h1 a { color: var(--accent); text-decoration: none; }
    .toolbar h1 span { color: var(--text-muted); font-weight: 400; }
    button { background: var(--surface); color: var(--accent); border: 1px solid var(--border); padding: 0.3rem 0.75rem; border-radius: 6px; cursor: pointer; font-size: 0.75rem; font-weight: 600; }
    button:hover { background: rgba(88, 166, 255, 0.1); }
    .btn-primary { background: var(--accent); color: var(--bg); border-color: var(--accent); }
    .btn-primary:hover { background: #79bbff; }
    .btn-danger { color: var(--red); border-color: rgba(248, 81, 73, 0.3); }
    .btn-danger:hover { background: rgba(248, 81, 73, 0.1); }
    .btn-sm { font-size: 0.7rem; padding: 0.2rem 0.5rem; }
    .content { max-width: 900px; margin: 1.5rem auto; padding: 0 1.5rem; }
    .section-title { font-size: 1rem; font-weight: 600; margin-bottom: 0.75rem; color: var(--text); }
    .focus-card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 1rem; margin-bottom: 0.75rem; }
    .focus-card.proposed { border-color: var(--yellow); }
    .focus-card.inactive { opacity: 0.6; }
    .focus-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; }
    .focus-name { font-weight: 700; font-size: 0.95rem; }
    .focus-role { color: var(--text-muted); font-size: 0.8rem; }
    .badge { display: inline-block; font-size: 0.65rem; font-weight: 700; padding: 0.15rem 0.5rem; border-radius: 10px; text-transform: uppercase; margin-left: 0.5rem; }
    .badge-active { background: rgba(63, 185, 80, 0.15); color: var(--green); }
    .badge-inactive { background: rgba(125, 133, 144, 0.15); color: var(--text-muted); }
    .badge-proposed { background: rgba(226, 179, 64, 0.15); color: var(--yellow); }
    .focus-desc { font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.5rem; line-height: 1.4; }
    .focus-keywords { font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.5rem; }
    .focus-keywords span { display: inline-block; background: rgba(88, 166, 255, 0.1); color: var(--accent); padding: 0.1rem 0.4rem; border-radius: 4px; margin: 0.1rem 0.15rem; font-size: 0.7rem; }
    .focus-rules { font-size: 0.75rem; margin-bottom: 0.5rem; }
    .focus-rules strong { color: var(--text); }
    .focus-rules ul { margin: 0.2rem 0 0 1.2rem; color: var(--text-muted); }
    .focus-rules li { margin-bottom: 0.15rem; }
    .focus-actions { display: flex; gap: 0.5rem; margin-top: 0.5rem; }
    .empty-state { text-align: center; padding: 3rem; color: var(--text-muted); }
    .suggestion-reason { font-size: 0.75rem; color: var(--yellow); margin-bottom: 0.5rem; font-style: italic; }
    .edit-form { margin-top: 0.75rem; border-top: 1px solid var(--border); padding-top: 0.75rem; }
    .edit-form .form-row { margin-bottom: 0.5rem; }
    .edit-form label { display: block; font-size: 0.7rem; color: var(--text-muted); margin-bottom: 0.15rem; font-weight: 600; }
    .edit-form input, .edit-form textarea { width: 100%; padding: 0.35rem 0.5rem; border-radius: 5px; border: 1px solid var(--border); background: var(--bg); color: var(--text); font-size: 0.8rem; font-family: inherit; }
    .edit-form textarea { resize: vertical; min-height: 3rem; }
    .edit-form .help { font-size: 0.65rem; color: var(--text-muted); margin-top: 0.1rem; }
    .edit-form .form-actions { display: flex; gap: 0.5rem; margin-top: 0.75rem; }
  </style>
</head>
<body>
  <div class="toolbar">
    <h1><a href="/">oompah</a> <span>/ Foci</span></h1>
    <div>
      <button onclick="window.location='/'">Dashboard</button>
    </div>
  </div>

  <div class="content">
    <div id="proposed-section"></div>
    <div id="active-section"></div>
    <div id="inactive-section"></div>
  </div>

<script>
let _fociData = [];

function esc(s) {
  if (!s) return '';
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function escAttr(s) {
  if (!s) return '';
  return s.replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

async function loadFoci() {
  const res = await fetch('/api/v1/foci');
  _fociData = await res.json();

  const proposed = _fociData.filter(f => f.status === 'proposed');
  const active = _fociData.filter(f => f.status === 'active');
  const inactive = _fociData.filter(f => f.status === 'inactive');

  renderSection('proposed-section', 'Proposed Foci', proposed, 'proposed');
  renderSection('active-section', 'Active Foci', active, 'active');
  renderSection('inactive-section', 'Inactive Foci', inactive, 'inactive');
}

function renderSection(containerId, title, foci, sectionType) {
  const el = document.getElementById(containerId);
  if (foci.length === 0 && sectionType !== 'active') {
    el.innerHTML = '';
    return;
  }
  let html = '<h2 class="section-title">' + esc(title) + ' (' + foci.length + ')</h2>';
  if (foci.length === 0) {
    html += '<div class="empty-state">No ' + sectionType + ' foci.</div>';
  } else {
    html += foci.map(f => renderFocusCard(f)).join('');
  }
  el.innerHTML = html;
}

function renderFocusCard(f) {
  const badgeClass = 'badge-' + f.status;
  let statusActions = '';

  if (f.status === 'proposed') {
    statusActions = `
      <button class="btn-primary btn-sm" onclick="setFocusStatus('${escAttr(f.name)}', 'active')">Activate</button>
      <button class="btn-sm" onclick="setFocusStatus('${escAttr(f.name)}', 'inactive')">Dismiss</button>
    `;
  } else if (f.status === 'active') {
    statusActions = `<button class="btn-sm" onclick="setFocusStatus('${escAttr(f.name)}', 'inactive')">Deactivate</button>`;
  } else {
    statusActions = `<button class="btn-primary btn-sm" onclick="setFocusStatus('${escAttr(f.name)}', 'active')">Activate</button>`;
  }

  let keywords = '';
  if (f.keywords && f.keywords.length > 0) {
    keywords = '<div class="focus-keywords">Keywords: ' +
      f.keywords.map(k => '<span>' + esc(k) + '</span>').join('') + '</div>';
  }

  let issueTypes = '';
  if (f.issue_types && f.issue_types.length > 0) {
    issueTypes = '<div class="focus-keywords">Issue types: ' +
      f.issue_types.map(t => '<span>' + esc(t) + '</span>').join('') + '</div>';
  }

  let labels = '';
  if (f.labels && f.labels.length > 0) {
    labels = '<div class="focus-keywords">Labels: ' +
      f.labels.map(l => '<span>' + esc(l) + '</span>').join('') + '</div>';
  }

  let mustDo = '';
  if (f.must_do && f.must_do.length > 0) {
    mustDo = '<div class="focus-rules"><strong>Must do:</strong><ul>' +
      f.must_do.map(m => '<li>' + esc(m) + '</li>').join('') + '</ul></div>';
  }

  let mustNotDo = '';
  if (f.must_not_do && f.must_not_do.length > 0) {
    mustNotDo = '<div class="focus-rules"><strong>Must NOT do:</strong><ul>' +
      f.must_not_do.map(m => '<li>' + esc(m) + '</li>').join('') + '</ul></div>';
  }

  const cardId = 'focus-' + f.name.replace(/[^a-zA-Z0-9]/g, '_');

  return `
    <div class="focus-card ${f.status}" id="${cardId}">
      <div class="focus-header">
        <div>
          <span class="focus-name">${esc(f.name)}</span>
          <span class="badge ${badgeClass}">${esc(f.status)}</span>
        </div>
        <span class="focus-role">${esc(f.role)}</span>
      </div>
      <div class="focus-desc">${esc(f.description)}</div>
      ${keywords}
      ${issueTypes}
      ${labels}
      ${mustDo}
      ${mustNotDo}
      <div class="focus-actions">
        ${statusActions}
        <button class="btn-sm" onclick="toggleEdit('${escAttr(f.name)}')">Edit</button>
        <button class="btn-danger btn-sm" onclick="deleteFocus('${escAttr(f.name)}')">Delete</button>
      </div>
      <div id="edit-${cardId}" style="display:none;"></div>
    </div>
  `;
}

function toggleEdit(name) {
  const f = _fociData.find(x => x.name === name);
  if (!f) return;
  const cardId = 'focus-' + name.replace(/[^a-zA-Z0-9]/g, '_');
  const editEl = document.getElementById('edit-' + cardId);
  if (!editEl) return;

  if (editEl.style.display !== 'none') {
    editEl.style.display = 'none';
    editEl.innerHTML = '';
    return;
  }

  editEl.style.display = 'block';
  editEl.innerHTML = renderEditForm(f);
}

function renderEditForm(f) {
  const n = escAttr(f.name);
  return `
    <div class="edit-form">
      <div class="form-row">
        <label>Role</label>
        <input type="text" id="ef-role-${n}" value="${escAttr(f.role)}">
      </div>
      <div class="form-row">
        <label>Description</label>
        <textarea id="ef-desc-${n}" rows="3">${esc(f.description)}</textarea>
      </div>
      <div class="form-row">
        <label>Keywords</label>
        <input type="text" id="ef-kw-${n}" value="${escAttr((f.keywords || []).join(', '))}">
        <div class="help">Comma-separated</div>
      </div>
      <div class="form-row">
        <label>Issue Types</label>
        <input type="text" id="ef-types-${n}" value="${escAttr((f.issue_types || []).join(', '))}">
        <div class="help">Comma-separated (e.g. bug, task, feature)</div>
      </div>
      <div class="form-row">
        <label>Labels</label>
        <input type="text" id="ef-labels-${n}" value="${escAttr((f.labels || []).join(', '))}">
        <div class="help">Comma-separated</div>
      </div>
      <div class="form-row">
        <label>Priority (tiebreaker, higher = preferred)</label>
        <input type="number" id="ef-pri-${n}" value="${f.priority || 0}" style="width:5rem;">
      </div>
      <div class="form-row">
        <label>Must Do (one per line)</label>
        <textarea id="ef-must-${n}" rows="3">${esc((f.must_do || []).join('\\n'))}</textarea>
      </div>
      <div class="form-row">
        <label>Must NOT Do (one per line)</label>
        <textarea id="ef-mustnot-${n}" rows="3">${esc((f.must_not_do || []).join('\\n'))}</textarea>
      </div>
      <div class="form-actions">
        <button class="btn-primary btn-sm" onclick="saveEdit('${n}')">Save</button>
        <button class="btn-sm" onclick="toggleEdit('${n}')">Cancel</button>
      </div>
    </div>
  `;
}

function splitCSV(s) {
  return s.split(',').map(x => x.trim()).filter(x => x);
}

function splitLines(s) {
  return s.split('\\n').map(x => x.trim()).filter(x => x);
}

async function saveEdit(name) {
  const n = name;
  const body = {
    role: document.getElementById('ef-role-' + n).value,
    description: document.getElementById('ef-desc-' + n).value,
    keywords: splitCSV(document.getElementById('ef-kw-' + n).value),
    issue_types: splitCSV(document.getElementById('ef-types-' + n).value),
    labels: splitCSV(document.getElementById('ef-labels-' + n).value),
    priority: parseInt(document.getElementById('ef-pri-' + n).value) || 0,
    must_do: splitLines(document.getElementById('ef-must-' + n).value),
    must_not_do: splitLines(document.getElementById('ef-mustnot-' + n).value),
  };
  const res = await fetch('/api/v1/foci/' + encodeURIComponent(name), {
    method: 'PATCH',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body),
  });
  if (res.ok) {
    loadFoci();
  } else {
    const err = await res.json();
    alert('Save failed: ' + ((err.error && err.error.message) || 'unknown error'));
  }
}

async function setFocusStatus(name, status) {
  await fetch('/api/v1/foci/' + encodeURIComponent(name), {
    method: 'PATCH',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({status}),
  });
  loadFoci();
}

async function deleteFocus(name) {
  if (!confirm('Delete focus "' + name + '"? This cannot be undone.')) return;
  const res = await fetch('/api/v1/foci/' + encodeURIComponent(name), {
    method: 'DELETE',
  });
  if (res.ok) {
    loadFoci();
  } else {
    const err = await res.json();
    alert('Delete failed: ' + ((err.error && err.error.message) || 'unknown error'));
  }
}

loadFoci();
</script>
</body>
</html>
"""


@app.get("/foci", response_class=HTMLResponse)
async def foci_page():
    """Serve the foci management page."""
    return FOCI_HTML


REVIEWS_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>oompah - Reviews</title>
  <style>
    :root {
      --bg: #0d1117; --surface: #161b22; --border: #30363d;
      --text: #e6edf3; --text-muted: #7d8590; --accent: #58a6ff;
      --green: #3fb950; --red: #f85149; --yellow: #e2b340; --purple: #bc8cff;
    }
    html { font-size: 125%; }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }
    .toolbar { display: flex; justify-content: space-between; align-items: center; padding: 0.75rem 1.5rem; border-bottom: 1px solid var(--border); }
    .toolbar h1 { font-size: 1.25rem; color: var(--accent); font-weight: 700; }
    .toolbar h1 a { color: var(--accent); text-decoration: none; }
    .toolbar h1 span { color: var(--text-muted); font-weight: 400; }
    button { background: var(--surface); color: var(--accent); border: 1px solid var(--border); padding: 0.3rem 0.75rem; border-radius: 6px; cursor: pointer; font-size: 0.75rem; font-weight: 600; }
    button:hover { background: rgba(88, 166, 255, 0.1); }
    .content { max-width: 1000px; margin: 1.5rem auto; padding: 0 1.5rem; }
    .summary-bar { display: flex; gap: 1.5rem; margin-bottom: 1.5rem; font-size: 0.85rem; color: var(--text-muted); }
    .summary-bar strong { color: var(--text); }
    .project-section { margin-bottom: 2rem; }
    .project-header { font-size: 0.95rem; font-weight: 700; margin-bottom: 0.75rem; display: flex; align-items: center; gap: 0.5rem; }
    .provider-badge { font-size: 0.6rem; font-weight: 700; padding: 0.15rem 0.45rem; border-radius: 10px; text-transform: uppercase; }
    .provider-github { background: rgba(88, 166, 255, 0.15); color: var(--accent); }
    .provider-gitlab { background: rgba(226, 131, 64, 0.15); color: #e8833f; }
    .review-card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 0.85rem 1rem; margin-bottom: 0.5rem; }
    .review-card:hover { border-color: var(--accent); }
    .review-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.35rem; }
    .review-title { font-weight: 600; font-size: 0.9rem; }
    .review-title a { color: var(--text); text-decoration: none; }
    .review-title a:hover { color: var(--accent); text-decoration: underline; }
    .review-id { color: var(--text-muted); font-size: 0.75rem; font-weight: 400; }
    .review-meta { display: flex; gap: 1rem; font-size: 0.75rem; color: var(--text-muted); flex-wrap: wrap; align-items: center; }
    .review-desc { font-size: 0.8rem; color: var(--text-muted); margin-top: 0.4rem; line-height: 1.4; max-height: 3.6em; overflow: hidden; }
    .draft-badge { background: rgba(125, 133, 144, 0.2); color: var(--text-muted); font-size: 0.65rem; padding: 0.1rem 0.4rem; border-radius: 8px; font-weight: 600; }
    .ci-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 0.2rem; vertical-align: middle; }
    .ci-passed { background: var(--green); }
    .ci-failed { background: var(--red); }
    .ci-pending { background: var(--yellow); }
    .branch-info { font-family: 'SFMono-Regular', Consolas, monospace; font-size: 0.7rem; background: rgba(88, 166, 255, 0.08); padding: 0.1rem 0.35rem; border-radius: 4px; }
    .label-tag { display: inline-block; font-size: 0.65rem; padding: 0.1rem 0.35rem; border-radius: 4px; background: rgba(188, 140, 255, 0.15); color: var(--purple); margin-left: 0.25rem; }
    .diff-stat { font-family: 'SFMono-Regular', Consolas, monospace; font-size: 0.7rem; }
    .diff-add { color: var(--green); }
    .diff-del { color: var(--red); }
    .review-card.needs-rebase { border-color: var(--yellow); }
    .review-card.has-conflicts { border-color: var(--red); }
    .rebase-badge { display: inline-block; font-size: 0.65rem; font-weight: 700; padding: 0.1rem 0.4rem; border-radius: 8px; background: rgba(226, 179, 64, 0.15); color: var(--yellow); text-transform: uppercase; }
    .conflict-badge { display: inline-block; font-size: 0.65rem; font-weight: 700; padding: 0.1rem 0.4rem; border-radius: 8px; background: rgba(248, 81, 73, 0.15); color: var(--red); text-transform: uppercase; }
    .btn-rebase { background: rgba(226, 179, 64, 0.15); color: var(--yellow); border-color: rgba(226, 179, 64, 0.3); font-size: 0.65rem; padding: 0.15rem 0.5rem; vertical-align: middle; }
    .btn-rebase:hover { background: rgba(226, 179, 64, 0.25); }
    .btn-rebase:disabled { opacity: 0.5; cursor: not-allowed; }
    .btn-rebase.success { background: rgba(63, 185, 80, 0.15); color: var(--green); border-color: rgba(63, 185, 80, 0.3); }
    .btn-rebase.failed { background: rgba(248, 81, 73, 0.15); color: var(--red); border-color: rgba(248, 81, 73, 0.3); }
    .btn-resolve { background: rgba(248, 81, 73, 0.15); color: var(--red); border-color: rgba(248, 81, 73, 0.3); font-size: 0.65rem; padding: 0.15rem 0.5rem; vertical-align: middle; }
    .btn-resolve:hover { background: rgba(248, 81, 73, 0.25); }
    .btn-resolve:disabled { opacity: 0.5; cursor: not-allowed; }
    .btn-resolve.success { background: rgba(63, 185, 80, 0.15); color: var(--green); border-color: rgba(63, 185, 80, 0.3); }
    .btn-retry { background: rgba(248, 81, 73, 0.15); color: var(--red); border-color: rgba(248, 81, 73, 0.3); font-size: 0.65rem; padding: 0.15rem 0.5rem; vertical-align: middle; }
    .btn-retry:hover { background: rgba(248, 81, 73, 0.25); }
    .btn-retry:disabled { opacity: 0.5; cursor: not-allowed; }
    .btn-retry.success { background: rgba(63, 185, 80, 0.15); color: var(--green); border-color: rgba(63, 185, 80, 0.3); }
    .empty-state { text-align: center; padding: 3rem; color: var(--text-muted); }
    .loading { text-align: center; padding: 3rem; color: var(--text-muted); }
    .error-msg { text-align: center; padding: 2rem; color: var(--red); }
  </style>
</head>
<body>
  <div class="toolbar">
    <h1><a href="/">oompah</a> <span>/ Reviews</span></h1>
    <div>
      <button onclick="loadReviews()">Refresh</button>
      <button onclick="window.location='/'">Dashboard</button>
    </div>
  </div>

  <div class="content">
    <div class="summary-bar" id="summary-bar"></div>
    <div id="reviews-container"><div class="loading">Loading reviews...</div></div>
  </div>

<script>
function esc(s) {
  if (!s) return '';
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function timeAgo(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  const now = new Date();
  const diffMs = now - d;
  const mins = Math.floor(diffMs / 60000);
  if (mins < 60) return mins + 'm ago';
  const hours = Math.floor(mins / 60);
  if (hours < 24) return hours + 'h ago';
  const days = Math.floor(hours / 24);
  return days + 'd ago';
}

async function loadReviews() {
  const container = document.getElementById('reviews-container');
  container.innerHTML = '<div class="loading">Loading reviews...</div>';

  try {
    const res = await fetch('/api/v1/reviews');
    if (!res.ok) {
      const err = await res.json();
      container.innerHTML = '<div class="error-msg">Failed to load reviews: ' +
        esc((err.error && err.error.message) || 'unknown error') + '</div>';
      return;
    }
    const data = await res.json();
    renderReviews(data);
  } catch(e) {
    container.innerHTML = '<div class="error-msg">Failed to load reviews: ' + esc(e.message) + '</div>';
  }
}

function renderReviews(data) {
  const container = document.getElementById('reviews-container');
  const summaryBar = document.getElementById('summary-bar');

  if (data.length === 0) {
    container.innerHTML = '<div class="empty-state">No open pull requests or merge requests.</div>';
    summaryBar.innerHTML = '';
    return;
  }

  // Group by project
  const byProject = {};
  for (const item of data) {
    const key = item.project_name;
    if (!byProject[key]) byProject[key] = { provider: item.provider, project_id: item.project_id, reviews: [] };
    byProject[key].reviews.push(item.review);
  }

  // Summary
  const totalReviews = data.length;
  const drafts = data.filter(d => d.review.draft).length;
  const conflicts = data.filter(d => d.review.has_conflicts).length;
  const projectCount = Object.keys(byProject).length;
  let summaryHtml = '<span>Open: <strong>' + totalReviews + '</strong></span>';
  if (conflicts > 0) summaryHtml += '<span style="color:var(--red);">Conflicts: <strong>' + conflicts + '</strong></span>';
  if (drafts > 0) summaryHtml += '<span>Drafts: <strong>' + drafts + '</strong></span>';
  summaryHtml += '<span>Projects: <strong>' + projectCount + '</strong></span>';
  summaryBar.innerHTML = summaryHtml;

  // Render by project
  let html = '';
  for (const [projectName, group] of Object.entries(byProject)) {
    const providerClass = 'provider-' + group.provider;
    const providerLabel = group.provider === 'github' ? 'GitHub' : 'GitLab';
    const reviewLabel = group.provider === 'github' ? 'PRs' : 'MRs';

    html += '<div class="project-section">';
    html += '<div class="project-header">' + esc(projectName) +
      ' <span class="provider-badge ' + providerClass + '">' + providerLabel + '</span>' +
      ' <span style="color:var(--text-muted);font-size:0.8rem;font-weight:400;">' +
      group.reviews.length + ' open ' + reviewLabel + '</span></div>';

    for (const r of group.reviews) {
      html += renderReviewCard(r, group.provider, group.project_id);
    }
    html += '</div>';
  }

  container.innerHTML = html;
}

function renderReviewCard(r, provider, projectId) {
  const idPrefix = provider === 'github' ? '#' : '!';

  let ciHtml = '';
  if (r.ci_status) {
    ciHtml = '<span><span class="ci-dot ci-' + r.ci_status + '"></span>' + r.ci_status + '</span>';
    if (r.ci_status === 'failed') {
      ciHtml += ' <button class="btn-retry" onclick="retryReview(\\'' + esc(projectId) + '\\', \\'' + esc(r.id) + '\\', this)">Retry</button>';
    }
  }

  let draftHtml = r.draft ? ' <span class="draft-badge">Draft</span>' : '';

  let rebaseHtml = '';
  if (r.has_conflicts) {
    rebaseHtml = ' <span class="conflict-badge">Merge Conflicts</span>' +
      ' <button class="btn-resolve" ' +
      'onclick="resolveConflicts(\\'' + esc(projectId) + '\\', \\'' + esc(r.id) + '\\', this)">Resolve Conflicts</button>';
  } else if (r.needs_rebase) {
    rebaseHtml = ' <span class="rebase-badge">Needs Rebase</span>' +
      ' <button class="btn-rebase" ' +
      'onclick="triggerRebase(\\'' + esc(projectId) + '\\', \\'' + esc(r.id) + '\\', this)">Rebase</button>';
  }

  let labelsHtml = '';
  if (r.labels && r.labels.length > 0) {
    labelsHtml = r.labels.map(l => '<span class="label-tag">' + esc(l) + '</span>').join('');
  }

  let diffHtml = '';
  if (r.additions > 0 || r.deletions > 0) {
    diffHtml = '<span class="diff-stat"><span class="diff-add">+' + r.additions + '</span> ' +
      '<span class="diff-del">-' + r.deletions + '</span></span>';
  }

  let descHtml = '';
  if (r.description) {
    descHtml = '<div class="review-desc">' + esc(r.description) + '</div>';
  }

  let reviewersHtml = '';
  if (r.reviewers && r.reviewers.length > 0) {
    reviewersHtml = '<span>Reviewers: ' + r.reviewers.map(v => esc(v)).join(', ') + '</span>';
  }

  return `
    <div class="review-card ${r.has_conflicts ? 'has-conflicts' : r.needs_rebase ? 'needs-rebase' : ''}">
      <div class="review-header">
        <div class="review-title">
          <a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.title)}</a>
          ${draftHtml}${rebaseHtml}${labelsHtml}
          <span class="review-id">${idPrefix}${esc(r.id)}</span>
        </div>
        ${diffHtml}
      </div>
      <div class="review-meta">
        <span>${esc(r.author)}</span>
        <span class="branch-info">${esc(r.source_branch)} &rarr; ${esc(r.target_branch)}</span>
        ${ciHtml}
        <span>${timeAgo(r.created_at)}</span>
        ${reviewersHtml}
      </div>
      ${descHtml}
    </div>
  `;
}

async function triggerRebase(projectId, reviewId, btn) {
  btn.disabled = true;
  btn.textContent = 'Rebasing...';
  try {
    const res = await fetch('/api/v1/reviews/' + encodeURIComponent(projectId) + '/' + encodeURIComponent(reviewId) + '/rebase', {
      method: 'POST',
    });
    const data = await res.json();
    if (data.success) {
      btn.textContent = 'Done';
      btn.className = 'btn-rebase success';
      setTimeout(() => loadReviews(), 2000);
    } else {
      btn.className = 'btn-rebase failed';
      btn.disabled = false;
      const msg = (data.message || '').toLowerCase();
      if (msg.includes('conflict') && data.notified_issue) {
        btn.textContent = 'Conflicts — notified ' + data.notified_issue;
        btn.className = 'btn-rebase success';
        btn.disabled = true;
      } else if (msg.includes('conflict')) {
        btn.textContent = 'Conflicts — no matching bead found';
      } else {
        btn.textContent = 'Failed';
      }
    }
  } catch(e) {
    btn.textContent = 'Error';
    btn.className = 'btn-rebase failed';
    btn.disabled = false;
  }
}

async function resolveConflicts(projectId, reviewId, btn) {
  btn.disabled = true;
  btn.textContent = 'Notifying agent...';
  try {
    const res = await fetch('/api/v1/reviews/' + encodeURIComponent(projectId) + '/' + encodeURIComponent(reviewId) + '/rebase', {
      method: 'POST',
    });
    const data = await res.json();
    if (data.notified_issue) {
      btn.textContent = 'Agent notified (' + data.notified_issue + ')';
      btn.className = 'btn-resolve success';
    } else if (data.success) {
      btn.textContent = 'Rebased';
      btn.className = 'btn-resolve success';
      setTimeout(() => loadReviews(), 2000);
    } else {
      btn.textContent = 'No matching bead found';
      btn.className = 'btn-resolve';
      btn.disabled = false;
    }
  } catch(e) {
    btn.textContent = 'Error';
    btn.className = 'btn-resolve';
    btn.disabled = false;
  }
}

async function retryReview(projectId, reviewId, btn) {
  btn.disabled = true;
  btn.textContent = 'Reopening...';
  try {
    const res = await fetch('/api/v1/reviews/' + encodeURIComponent(projectId) + '/' + encodeURIComponent(reviewId) + '/retry', {
      method: 'POST',
    });
    const data = await res.json();
    if (data.success) {
      btn.textContent = 'Reopened ' + (data.identifier || '');
      btn.className = 'btn-retry success';
      setTimeout(() => loadReviews(), 2000);
    } else {
      btn.textContent = data.message || 'No bead found';
      btn.disabled = false;
    }
  } catch(e) {
    btn.textContent = 'Error';
    btn.disabled = false;
  }
}

loadReviews();
</script>
</body>
</html>
"""


@app.get("/reviews", response_class=HTMLResponse)
async def reviews_page():
    """Serve the reviews (PR/MR) listing page."""
    return REVIEWS_HTML


def _esc(s: str) -> str:
    """Basic HTML escaping."""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
=======
/*very long string containing HTML, CSS, and Python code*/
>>>>>>> fa688de (umpah-b6d: Fix swimlane column width)
