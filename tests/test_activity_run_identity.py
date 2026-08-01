"""Regression coverage for activity identity across sequential worker runs."""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

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
    html = (Path(__file__).resolve().parents[1] / "oompah" / "templates" / "dashboard.html").read_text(
        encoding="utf-8"
    )
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

    orch._notify_activity("EXOCOMP-143", Activity(), run_id="implementation-run")

    assert received[0]["run_id"] == "implementation-run"


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
    assert "data.run_id" in refresh_body
    assert "requestGeneration" in refresh_body
    assert "nextRunId" in sync_body
    assert "clearActivityPanelData" in sync_body


def test_server_activity_contract_exposes_run_identity():
    server_code = (Path(__file__).resolve().parents[1] / "oompah" / "server.py").read_text(
        encoding="utf-8"
    )

    activity_body = server_code[server_code.index("async def api_agent_activity"):]
    assert '"run_id": getattr(entry, "run_id", None)' in activity_body
    assert '"run_id": run_id' in server_code[server_code.index("def _on_agent_activity"):]
