"""FastAPI server with htmx kanban dashboard and JSON REST API."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

if TYPE_CHECKING:
    from umpah.orchestrator import Orchestrator

logger = logging.getLogger(__name__)

app = FastAPI(title="umpah", version="0.1.0")

# Global reference to orchestrator, set during startup
_orchestrator: Orchestrator | None = None


def set_orchestrator(orch: Orchestrator) -> None:
    global _orchestrator
    _orchestrator = orch


def _get_orchestrator() -> Orchestrator:
    if _orchestrator is None:
        raise RuntimeError("Orchestrator not initialized")
    return _orchestrator


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
async def api_issues():
    """Return all issues grouped by state for the kanban board."""
    try:
        orch = _get_orchestrator()
        issues = orch.tracker.fetch_all_issues_enriched()

        # Build a map for epic child counts
        epics: dict[str, dict] = {}
        for issue in issues:
            if issue.issue_type == "epic":
                epics[issue.id] = {"deferred": 0, "open": 0, "in_progress": 0, "closed": 0}

        # Count children per epic per state
        for issue in issues:
            if issue.parent_id and issue.parent_id in epics:
                child_state = issue.state.strip().lower()
                if child_state in epics[issue.parent_id]:
                    epics[issue.parent_id][child_state] += 1

        result: dict[str, list] = {}
        for issue in issues:
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

        issue = orch.tracker.create_issue(
            title=title,
            issue_type=body.get("type", "task"),
            description=body.get("description"),
            priority=body.get("priority"),
        )

        # Link to parent epic if specified
        parent_id = body.get("parent_id")
        if parent_id:
            orch.tracker.add_parent_child(issue.id, parent_id)

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

        new_status = body.get("status")
        new_priority = body.get("priority")
        new_title = body.get("title")
        new_description = body.get("description")

        if new_status == "closed":
            orch.tracker.close_issue(identifier)
        elif new_status is not None:
            # Check if currently closed — need to reopen
            orch.tracker.update_issue(identifier, status=new_status)

        if new_priority is not None:
            orch.tracker.update_issue(identifier, priority=str(new_priority))

        if new_title is not None:
            orch.tracker.update_issue(identifier, title=new_title)

        if new_description is not None:
            orch.tracker.update_issue(identifier, description=new_description)

        return JSONResponse({"ok": True})
    except Exception as exc:
        logger.error("Update issue API error: %s", exc)
        return JSONResponse(
            {"error": {"code": "update_failed", "message": str(exc)}},
            status_code=500,
        )


@app.get("/api/v1/issues/{identifier}/detail")
async def api_issue_full_detail(identifier: str):
    """Return full issue detail for the slide-out panel."""
    try:
        orch = _get_orchestrator()
        issue = orch.tracker.fetch_issue_detail(identifier)
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
            "labels": issue.labels,
            "created_at": issue.created_at.isoformat() if issue.created_at else None,
            "updated_at": issue.updated_at.isoformat() if issue.updated_at else None,
        }
        if issue.issue_type == "epic":
            children = orch.tracker.fetch_children(issue.id)
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
        return JSONResponse(result)
    except Exception as exc:
        logger.error("Issue detail API error: %s", exc)
        return JSONResponse(
            {"error": {"code": "unavailable", "message": str(exc)}},
            status_code=503,
        )


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
  <title>umpah</title>
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
      overflow-y: auto;
      overflow-x: hidden;
      gap: 0;
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
      gap: 0.5rem;
      padding: 0.5rem;
      overflow-x: auto;
    }
    .swimlane.collapsed .swimlane-columns {
      display: none;
    }
    .swimlane-col {
      flex: 1;
      min-width: 200px;
    }
    .swimlane-col-header {
      font-size: 0.7rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-muted);
      padding: 0.3rem 0.5rem;
      margin-bottom: 0.25rem;
    }
    .swimlane-col-body {
      min-height: 40px;
      padding: 0 0.25rem;
    }

    .column {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 10px;
      min-width: 280px;
      max-width: 340px;
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
    }
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
    <h1>umpah</h1>
    <div style="display: flex; align-items: center; gap: 1rem;">
      <span class="status" id="status-text">Loading...</span>
      <div class="view-toggle">
        <button id="btn-flat" class="active" onclick="setViewMode('flat')">Flat</button>
        <button id="btn-swimlane" onclick="setViewMode('swimlane')">Swimlanes</button>
      </div>
      <button onclick="openCreateDialog()">+ Create</button>
      <button onclick="refreshBoard()">Refresh</button>
    </div>
  </div>
  <div class="main-area">
    <div class="board" id="board"></div>
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
let viewMode = 'flat';
let collapsedSwimlanes = {};

async function fetchIssues() {
  const res = await fetch('/api/v1/issues');
  if (!res.ok) return null;
  return await res.json();
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
  boardData = data;
  allIssuesFlat = flattenIssues(data);
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
      <div class="column-header">
        <span class="col-title">${COLUMN_LABELS[col]}</span>
        <span class="col-count">${issues.length}</span>
      </div>
      <div class="column-body" data-state="${col}"></div>
    `;

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
      sc.className = 'swimlane-col';
      sc.innerHTML = `
        <div class="swimlane-col-header">${COLUMN_LABELS[col]} (${colIssues.length})</div>
        <div class="swimlane-col-body" data-state="${col}"></div>
      `;
      const scBody = sc.querySelector('.swimlane-col-body');
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
      sc.className = 'swimlane-col';
      sc.innerHTML = `
        <div class="swimlane-col-header">${COLUMN_LABELS[col]} (${colIssues.length})</div>
        <div class="swimlane-col-body" data-state="${col}"></div>
      `;
      const scBody = sc.querySelector('.swimlane-col-body');
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
    el.addEventListener('focus', () => { card.draggable = false; });
    el.addEventListener('blur', async () => {
      card.draggable = true;
      const field = el.dataset.field;
      const id = el.dataset.id;
      const newValue = el.textContent.trim();
      await updateIssue(id, {[field]: newValue});
    });
    el.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); el.blur(); }
      if (e.key === 'Escape') el.blur();
    });
  }

  return card;
}

function setupDropZone(body) {
  body.addEventListener('dragover', e => {
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
    const updates = {};
    if (targetState !== dragState.sourceState) {
      updates.status = targetState;
    }
    if (Object.keys(updates).length > 0) {
      await updateIssue(identifier, updates);
    }
    const data = await fetchIssues();
    if (data) renderBoard(data);
  });
}

function clearAllIndicators() {
  document.querySelectorAll('.drop-indicator').forEach(el => el.classList.remove('visible'));
  document.querySelectorAll('.column-body, .swimlane-col-body').forEach(el => el.classList.remove('drag-over'));
}

function esc(s) {
  if (!s) return '';
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

async function refreshBoard() {
  document.getElementById('status-text').textContent = 'Refreshing...';
  const data = await fetchIssues();
  if (data) renderBoard(data);
}

// --- Detail panel ---
async function openDetailPanel(identifier) {
  const panel = document.getElementById('detail-panel');
  const body = document.getElementById('detail-panel-body');
  body.innerHTML = '<div style="color:var(--text-muted);font-size:0.8rem;">Loading...</div>';
  panel.classList.add('open');

  const res = await fetch(`/api/v1/issues/${encodeURIComponent(identifier)}/detail`);
  if (!res.ok) {
    body.innerHTML = '<div style="color:var(--red);font-size:0.8rem;">Failed to load</div>';
    return;
  }
  const detail = await res.json();
  document.getElementById('detail-panel-title').textContent = detail.identifier;

  const pClass = `p${detail.priority ?? 4}`;
  let html = `
    <div class="detail-field">
      <div class="detail-field-label">Title</div>
      <div class="detail-field-value">${esc(detail.title)}</div>
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
      <div class="detail-field-value">${esc(detail.description || 'No description')}</div>
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

  body.innerHTML = html;
}

function closeDetailPanel() {
  document.getElementById('detail-panel').classList.remove('open');
}

// --- Create dialog ---
let createParentId = null;

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
  }
});

// Initial load + auto-refresh every 10s
refreshBoard();
setInterval(refreshBoard, 10000);
</script>

<div class="dialog-overlay" id="create-dialog" onclick="if(event.target===this)closeCreateDialog()">
  <div class="dialog">
    <h2 id="create-dialog-title">Create Issue</h2>
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
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve the kanban dashboard."""
    return DASHBOARD_HTML


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


def _esc(s: str) -> str:
    """Basic HTML escaping."""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
