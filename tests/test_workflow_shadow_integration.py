from __future__ import annotations

import asyncio
import base64
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.config import ServiceConfig
from oompah.http_auth import HtpasswdCredentials, VerificationError
from oompah.models import Issue, WorkflowDefinition
from oompah.orchestrator import Orchestrator
from oompah.workflow_contract import TaskDisposition, WorkflowOwner
from oompah.workflow_shadow import LegacyWorkflowProjection


def issue(identifier: str = "OOMPAH-1", *, state: str = "Open") -> Issue:
    return Issue(
        id=f"id-{identifier}",
        identifier=identifier,
        title=f"Task {identifier}",
        state=state,
        project_id="project-a",
        work_branch=identifier,
        target_branch="main",
    )


def fake_tracker(issues: list[Issue]):
    tracker = MagicMock()
    by_id = {item.identifier: item for item in issues}
    tracker.fetch_all_issues.return_value = list(issues)
    tracker.fetch_issue_detail.side_effect = by_id.get
    tracker.fetch_children.return_value = []
    return tracker


def orchestrator(tmp_path, *, mode: str = "shadow", scan_limit: int = 100):
    config = ServiceConfig(
        workspace_root=str(tmp_path / "workspaces"),
        workflow_engine_mode=mode,
        workflow_shadow_scan_limit=scan_limit,
    )
    value = Orchestrator(
        config,
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(tmp_path / "state.json"),
    )
    return value


def attach_project(orch: Orchestrator, tracker) -> None:
    orch.project_store = MagicMock()
    project = SimpleNamespace(id="project-a")
    project.to_safe_dict = lambda: {"id": "project-a"}
    orch.project_store.list_all.return_value = [project]
    orch._tracker_for_project = MagicMock(return_value=tracker)
    orch._notify_state_only = MagicMock()


def test_config_defaults_to_off_and_reads_environment_modes(monkeypatch):
    assert ServiceConfig().workflow_engine_mode == "off"

    monkeypatch.setenv("OOMPAH_WORKFLOW_ENGINE_MODE", "shadow")
    monkeypatch.setenv("OOMPAH_WORKFLOW_SHADOW_SCAN_LIMIT", "17")
    monkeypatch.setenv("OOMPAH_WORKFLOW_DIAGNOSTIC_MAX_BYTES", "4096")
    config = ServiceConfig.from_workflow(
        WorkflowDefinition(config={}, prompt_template="test")
    )

    assert config.workflow_engine_mode == "shadow"
    assert config.workflow_shadow_scan_limit == 17
    assert config.workflow_diagnostic_max_bytes == 4096


def test_config_rejects_unknown_mode_and_clamps_bounds():
    with pytest.raises(ValueError, match="one of"):
        ServiceConfig(workflow_engine_mode="unknown")

    config = ServiceConfig(
        workflow_shadow_scan_limit=10_000,
        workflow_diagnostic_max_bytes=1,
    )
    assert config.workflow_shadow_scan_limit == 1000
    assert config.workflow_diagnostic_max_bytes == 1024


def test_orchestrator_shadow_sweep_is_read_only_and_bounded(tmp_path):
    issues = [issue(f"OOMPAH-{number}") for number in range(1, 4)]
    tracker = fake_tracker(issues)
    orch = orchestrator(tmp_path, scan_limit=2)
    attach_project(orch, tracker)

    result = orch._run_workflow_shadow_sweep()

    assert result["evaluated"] == 2
    assert orch.workflow_shadow.summary()["tracked_task_count"] == 2
    tracker.update_issue.assert_not_called()
    tracker.add_comment.assert_not_called()
    tracker.add_label.assert_not_called()
    tracker.remove_label.assert_not_called()
    orch._notify_state_only.assert_called_once()


def test_orchestrator_enforce_sweep_materializes_universal_recovery(tmp_path):
    current = issue(state="In Progress")
    tracker = fake_tracker([current])
    orch = orchestrator(tmp_path, mode="enforce")
    attach_project(orch, tracker)

    result = orch._run_workflow_controller_sweep()

    assert result["evaluated"] == 1
    assert result["jobs_created"] == 1
    assert result["action_required"] == 0
    jobs = orch.workflow_job_store.list_jobs()
    assert len(jobs) == 1
    assert jobs[0].reason_code == "implementation.recovery_scheduled"
    tracker.update_issue.assert_not_called()
    tracker.add_comment.assert_not_called()


def test_orchestrator_shadow_compares_legacy_consumers_without_alerts(tmp_path):
    current = issue()
    tracker = fake_tracker([current])
    orch = orchestrator(tmp_path)
    attach_project(orch, tracker)
    orch._legacy_workflow_projections = MagicMock(
        return_value=(
            LegacyWorkflowProjection(
                "dispatch",
                disposition=TaskDisposition.BLOCKED,
                owner=WorkflowOwner.OPERATOR,
            ),
            LegacyWorkflowProjection("ui", status="Open"),
        )
    )
    alerts_before = list(orch._alerts)

    result = orch._run_workflow_shadow_sweep()

    assert result["changed"] == 1
    diagnostic = orch.workflow_shadow.diagnostic("project-a", "OOMPAH-1")
    assert diagnostic["state"] == "diverged"
    assert set(diagnostic["divergence"]["mismatches"]) == {"dispatch"}
    assert orch._alerts == alerts_before


def test_off_mode_skips_tracker_scan(tmp_path):
    tracker = fake_tracker([issue()])
    orch = orchestrator(tmp_path, mode="off")
    attach_project(orch, tracker)

    result = orch._run_workflow_shadow_sweep()

    assert result == {"evaluated": 0, "changed": 0, "mode": "off"}
    tracker.fetch_all_issues.assert_not_called()


def test_config_reload_changes_shadow_mode_without_dropping_diagnostics(tmp_path):
    tracker = fake_tracker([issue()])
    orch = orchestrator(tmp_path)
    attach_project(orch, tracker)
    orch._run_workflow_shadow_sweep()
    assert orch.workflow_shadow.summary()["tracked_task_count"] == 1

    replacement = ServiceConfig(
        workspace_root=str(tmp_path / "replacement"),
        workflow_engine_mode="off",
        workflow_diagnostic_max_bytes=2048,
    )
    orch.reload_config(replacement, "prompt")

    assert orch.workflow_shadow.mode == "off"
    assert orch.workflow_shadow.max_diagnostic_bytes == 2048
    assert orch.workflow_shadow.summary()["tracked_task_count"] == 1


def test_state_and_websocket_message_share_shadow_summary(tmp_path, monkeypatch):
    tracker = fake_tracker([issue()])
    orch = orchestrator(tmp_path)
    attach_project(orch, tracker)
    orch._run_workflow_shadow_sweep()
    snapshot = orch.get_snapshot()
    assert snapshot["workflow_shadow"]["tracked_task_count"] == 1
    assert snapshot["workflow_jobs"]["schema_version"] == 3
    assert snapshot["workflow_jobs"]["states"] == {}

    monkeypatch.setattr(server_module, "_orchestrator", orch)
    server_module._update_state_snapshot(snapshot)
    message = server_module._current_state_message()

    assert message["type"] == "state"
    assert message["data"]["workflow_shadow"] == snapshot["workflow_shadow"]


def _credentials() -> HtpasswdCredentials:
    credentials = HtpasswdCredentials(enabled=True)

    def verify(username: str, password: str) -> None:
        if (username, password) != ("operator", "correct"):
            raise VerificationError("Invalid credentials")

    credentials.verifier = verify
    credentials.htpasswd_path = "/test/.htpasswd"
    return credentials


def _authorization(username: str, password: str) -> str:
    encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {encoded}"


def test_workflow_diagnostic_api_is_authenticated_and_returns_safe_payload(
    tmp_path, monkeypatch
):
    tracker = fake_tracker([issue()])
    orch = orchestrator(tmp_path)
    attach_project(orch, tracker)
    orch._run_workflow_shadow_sweep()
    monkeypatch.setattr(server_module, "_orchestrator", orch)
    monkeypatch.setattr(server_module, "_http_credentials", _credentials())
    client = TestClient(server_module.app, raise_server_exceptions=False)
    path = "/api/v1/projects/project-a/tasks/OOMPAH-1/workflow-diagnostic"

    denied = client.get(path)
    accepted = client.get(
        path,
        headers={"Authorization": _authorization("operator", "correct")},
    )

    assert denied.status_code == 401
    assert accepted.status_code == 200
    payload = accepted.json()
    assert payload["diagnostic"]["task_id"] == "OOMPAH-1"
    assert payload["workflow_shadow"]["mode"] == "shadow"
    assert "correct" not in accepted.text


def test_workflow_diagnostic_api_returns_not_evaluated(tmp_path, monkeypatch):
    orch = orchestrator(tmp_path)
    monkeypatch.setattr(server_module, "_orchestrator", orch)
    monkeypatch.setattr(server_module, "_http_credentials", None)
    client = TestClient(server_module.app, raise_server_exceptions=False)

    response = client.get(
        "/api/v1/projects/project-a/tasks/UNKNOWN/workflow-diagnostic"
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_evaluated"


@pytest.mark.asyncio
async def test_graceful_drain_waits_for_shadow_evaluation(tmp_path):
    orch = orchestrator(tmp_path)
    orch._tick_pool = MagicMock()
    orch._refresh_pool = MagicMock()
    future = asyncio.get_running_loop().create_future()
    orch._workflow_shadow_future = future
    asyncio.get_running_loop().call_soon(future.set_result, None)

    await orch._drain_background_work()

    assert future.done()
    orch._tick_pool.shutdown.assert_called_once_with(
        wait=True,
        cancel_futures=False,
    )
