"""Regression coverage for activity identity across sequential worker runs."""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import oompah.server as server_module
from oompah.config import ServiceConfig
from oompah.events import EventType
from oompah.models import Issue, RunningEntry
from oompah.orchestrator import Orchestrator


def _orchestrator(tmp_path) -> Orchestrator:
    return Orchestrator(
        config=ServiceConfig(),
        workflow_path="WORKFLOW.md",
        state_path=str(tmp_path / "service_state.json"),
    )


def _entry(issue: Issue, run_id: str) -> RunningEntry:
    return RunningEntry(
        worker_task=MagicMock(),
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        run_id=run_id,
    )


def _dashboard_script() -> str:
    path = (
        Path(__file__).resolve().parents[1]
        / "oompah"
        / "templates"
        / "dashboard.html"
    )
    html = path.read_text(encoding="utf-8")
    return max(re.findall(r"<script>(.*?)</script>", html, re.DOTALL), key=len)


def _function_body(script: str, name: str) -> str:
    match = re.search(
        rf"(?:async\s+)?function\s+{re.escape(name)}\s*\([^)]*\)\s*\{{",
        script,
    )
    assert match, f"missing dashboard function {name}"
    start = match.end() - 1
    depth = 0
    for index in range(start, len(script)):
        if script[index] == "{":
            depth += 1
        elif script[index] == "}":
            depth -= 1
            if depth == 0:
                return script[start + 1 : index]
    raise AssertionError(f"unterminated dashboard function {name}")


def test_running_snapshot_exposes_unique_run_identity(tmp_path):
    orch = _orchestrator(tmp_path)
    issue = Issue(id="i-1", identifier="EXOCOMP-143", title="task", state="Open")
    first = _entry(issue, "preflight-run")
    second = _entry(issue, "implementation-run")

    assert first.run_id != second.run_id
    orch.state.running[issue.id] = second

    row = orch.get_snapshot()["running"][0]
    assert row["run_id"] == "implementation-run"


def test_superseded_run_is_rejected_for_activity_and_exit(tmp_path):
    orch = _orchestrator(tmp_path)
    issue = Issue(id="i-1", identifier="EXOCOMP-143", title="task", state="Open")
    old = _entry(issue, "duplicate-run")
    new = _entry(issue, "implementation-run")
    orch.state.running[issue.id] = new

    assert not orch._is_current_run(issue.id, old.run_id)
    assert orch._is_current_run(issue.id, new.run_id)

    asyncio.run(orch._on_worker_exit(issue.id, "normal", None, run_id=old.run_id))
    assert orch.state.running[issue.id] is new


def test_activity_event_payload_carries_run_identity(tmp_path):
    orch = _orchestrator(tmp_path)
    received = []
    orch.event_bus.subscribe(
        EventType.AGENT_ACTIVITY, lambda _event_type, payload: received.append(payload)
    )

    class Activity:
        def to_dict(self):
            return {"kind": "message", "summary": "new run"}

    orch._notify_activity(
        "project-a",
        "EXOCOMP-143",
        Activity(),
        run_id="implementation-run",
    )

    assert received[0]["run_id"] == "implementation-run"
    assert received[0]["project_id"] == "project-a"


def test_dashboard_activity_state_is_run_keyed():
    script = _dashboard_script()
    open_body = _function_body(script, "openActivityPanel")
    push_body = _function_body(script, "handleActivityPush")
    refresh_body = _function_body(script, "refreshActivity")
    sync_body = _function_body(script, "syncOpenActivityPanel")

    assert "run_id" in script
    assert "provider_name" in open_body and "model_name" in open_body
    assert "setActivityProviderModel" in open_body
    assert "activeRunId" in push_body and "runId" in push_body
    assert "dataset.projectId" in push_body
    assert "data.run_id" in refresh_body
    assert "data.project_id" in refresh_body
    assert "requestGeneration" in refresh_body
    assert "nextRunId" in sync_body
    assert "clearActivityPanelData" in sync_body


def test_dashboard_activity_push_is_project_and_run_keyed() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for dashboard behavior tests")
    body = _function_body(_dashboard_script(), "handleActivityPush")
    program = f"""
let _activityEntries = [];
const overlay = {{classList: {{contains: value => value === 'open'}}}};
const title = {{dataset: {{
  identifier: 'TASK-1', projectId: 'project-b', runId: 'run-b',
}}}};
const activityBody = {{
  querySelector: () => null,
  appendChild: () => {{}},
  innerHTML: '', scrollTop: 0, scrollHeight: 0,
}};
const document = {{getElementById: id => id === 'activity-overlay' ? overlay :
  id === 'activity-title' ? title : activityBody}};
function renderActivityEntry(entry) {{ return null; }}
function renderActivitySummary(entries) {{}}
function handleActivityPush(projectId, identifier, runId, entry) {{{body}}}
handleActivityPush('project-a', 'TASK-1', 'run-b', {{summary: 'wrong project'}});
handleActivityPush('project-b', 'TASK-1', 'run-a', {{summary: 'wrong run'}});
handleActivityPush('project-b', 'TASK-1', 'run-b', {{summary: 'accepted'}});
title.dataset.runId = '';
handleActivityPush('project-b', 'TASK-1', 'run-b', {{summary: 'ended run'}});
console.log(JSON.stringify(_activityEntries.map(entry => entry.summary)));
"""
    completed = subprocess.run(
        [node, "-e", program],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(completed.stdout) == ["accepted"]


def test_dashboard_activity_refresh_rejects_cross_project_response() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for dashboard behavior tests")
    body = _function_body(_dashboard_script(), "refreshActivity")
    program = f"""
let _activityRunId = 'run-b';
let _activityRequestGeneration = 7;
let _activityEntries = [];
const title = {{dataset: {{
  identifier: 'TASK-1', projectId: 'project-b', runId: 'run-b',
}}}};
const providerModel = {{}};
const document = {{getElementById: id =>
  id === 'activity-title' ? title : providerModel}};
let payload = {{
  identifier: 'TASK-1', project_id: 'project-a', run_id: 'run-b',
  activity: [{{summary: 'wrong project'}}],
}};
async function fetch(_url) {{ return {{json: async () => payload}}; }}
const rendered = [];
function setActivityProviderModel() {{}}
function renderActivityList(entries) {{
  rendered.push(entries.map(entry => entry.summary));
}}
function renderActivitySummary() {{}}
async function refreshActivity(
  identifier, projectId, runId = _activityRunId || '',
  requestGeneration = _activityRequestGeneration
) {{{body}}}
(async () => {{
  await refreshActivity('TASK-1', 'project-b', 'run-b', 7);
  payload = {{
    identifier: 'TASK-1', project_id: 'project-b', run_id: 'run-b',
    activity: [{{summary: 'accepted'}}],
  }};
  await refreshActivity('TASK-1', 'project-b', 'run-b', 7);
  console.log(JSON.stringify(rendered));
}})();
"""
    completed = subprocess.run(
        [node, "-e", program],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(completed.stdout) == [["accepted"]]


def test_dashboard_activity_open_selects_exact_project_identity() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for dashboard behavior tests")
    body = _function_body(_dashboard_script(), "openActivityPanel")
    program = f"""
let _activityRequestGeneration = 0;
let activityPollTimer = null;
const WebSocket = {{OPEN: 1}};
const ws = {{readyState: WebSocket.OPEN}};
const lastRunningAgents = [
  {{issue_identifier: 'TASK-1', project_id: 'project-a', run_id: 'run-a'}},
  {{issue_identifier: 'TASK-1', project_id: 'project-b', run_id: 'run-b'}},
];
const title = {{dataset: {{}}}};
const providerModel = {{}};
const overlay = {{classList: {{add: () => {{}}}}}};
const document = {{getElementById: id => id === 'activity-title' ? title :
  id === 'activity-provider-model' ? providerModel : overlay}};
const selected = [];
function clearActivityPanelData() {{}}
function setActivityPanelIdentity(identifier, projectId, agent, runId) {{
  title.dataset.identifier = identifier;
  title.dataset.projectId = projectId;
  title.dataset.runId = runId;
  selected.push([projectId, agent.project_id, runId]);
}}
function setActivityProviderModel() {{}}
function initAgentLogVerboseToggle() {{}}
async function refreshActivity(identifier, projectId, runId, generation) {{
  selected.push([projectId, identifier, runId, generation]);
}}
async function openActivityPanel(identifier, projectId, runId) {{{body}}}
(async () => {{
  await openActivityPanel('TASK-1', 'project-b', 'stale-run');
  console.log(JSON.stringify(selected));
}})();
"""
    completed = subprocess.run(
        [node, "-e", program],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(completed.stdout) == [
        ["project-b", "project-b", "run-b"],
        ["project-b", "TASK-1", "run-b", 1],
    ]


def test_server_activity_contract_exposes_run_identity():
    server_code = (
        Path(__file__).resolve().parents[1] / "oompah" / "server.py"
    ).read_text(
        encoding="utf-8",
    )

    activity_body = server_code[server_code.index("async def api_agent_activity"):]
    assert '"run_id": getattr(entry, "run_id", None)' in activity_body
    assert '"project_id": entry_project_id' in activity_body
    activity_observer = server_code[server_code.index("def _on_agent_activity") :]
    assert '"run_id": run_id' in activity_observer
    assert '"project_id": project_id' in activity_observer


@pytest.mark.asyncio
async def test_server_activity_lookup_selects_project_scoped_duplicate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    issue_a = Issue(
        id="a", identifier="TASK-1", title="A", state="Open", project_id="project-a"
    )
    issue_b = Issue(
        id="b", identifier="TASK-1", title="B", state="Open", project_id="project-b"
    )
    issue_legacy = Issue(
        id="legacy", identifier="TASK-1", title="Legacy", state="Open"
    )
    entry_a = _entry(issue_a, "run-a")
    entry_b = _entry(issue_b, "run-b")
    entry_legacy = _entry(issue_legacy, "run-legacy")
    orch = MagicMock()
    monkeypatch.setattr(server_module, "_get_orchestrator", lambda: orch)
    monkeypatch.setattr(
        server_module,
        "_running_items_snapshot",
        lambda _orch: (
            (issue_a.id, entry_a),
            (issue_b.id, entry_b),
            (issue_legacy.id, entry_legacy),
        ),
    )
    monkeypatch.setattr(
        server_module,
        "_issue_terminal_audit_summary",
        lambda *_args, **_kwargs: None,
    )

    selected = await server_module.api_agent_activity(
        "TASK-1", project_id="project-b"
    )
    selected_payload = json.loads(selected.body)
    assert selected_payload["project_id"] == "project-b"
    assert selected_payload["run_id"] == "run-b"

    legacy = await server_module.api_agent_activity("TASK-1", project_id="")
    legacy_payload = json.loads(legacy.body)
    assert legacy_payload["project_id"] is None
    assert legacy_payload["run_id"] == "run-legacy"

    ambiguous = await server_module.api_agent_activity("TASK-1")
    assert ambiguous.status_code == 409
    assert json.loads(ambiguous.body)["error"]["code"] == "ambiguous_task_identity"
