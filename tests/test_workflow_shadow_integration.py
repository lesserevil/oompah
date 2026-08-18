from __future__ import annotations

import asyncio
import base64
import json
from datetime import datetime, timedelta
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
from oompah.workflow_jobs import (
    WorkflowFailureCategory,
    WorkflowJobSpec,
)
from oompah.workflow_liveness_metrics import LIVENESS_STATE_SCHEMA_VERSION
from oompah.workflow_shadow import LegacyWorkflowProjection


_OWNED_ORCHESTRATORS: list[Orchestrator] = []


@pytest.fixture(autouse=True)
def _close_owned_orchestrators():
    """Close every executor and SQLite store created by this module."""

    first_owned = len(_OWNED_ORCHESTRATORS)
    try:
        yield
    finally:
        owned = _OWNED_ORCHESTRATORS[first_owned:]
        del _OWNED_ORCHESTRATORS[first_owned:]
        for orch in reversed(owned):
            orch._tick_pool.shutdown(wait=True, cancel_futures=True)
            orch._refresh_pool.shutdown(wait=True, cancel_futures=True)
            orch.coordination_store.close()
            orch.integration_queue.close()
            orch.review_capacity_store.close()
            orch.workflow_job_store.close()
            orch.task_transition_journal.close()


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
    _OWNED_ORCHESTRATORS.append(value)
    return value


def attach_project(orch: Orchestrator, tracker) -> None:
    orch.project_store = MagicMock()
    project = SimpleNamespace(id="project-a")
    project.to_safe_dict = lambda: {"id": "project-a"}
    orch.project_store.list_all.return_value = [project]
    orch._tracker_for_project = MagicMock(return_value=tracker)
    orch._notify_observers = MagicMock()
    orch._notify_state_only = MagicMock()


def close_owned_orchestrator(orch: Orchestrator) -> None:
    """Close one instance early when a test simulates a real process restart."""

    _OWNED_ORCHESTRATORS.remove(orch)
    orch._tick_pool.shutdown(wait=True, cancel_futures=True)
    orch._refresh_pool.shutdown(wait=True, cancel_futures=True)
    orch.coordination_store.close()
    orch.integration_queue.close()
    orch.review_capacity_store.close()
    orch.workflow_job_store.close()
    orch.task_transition_journal.close()


def test_config_defaults_to_off_and_reads_environment_modes(monkeypatch):
    assert ServiceConfig().workflow_engine_mode == "off"

    monkeypatch.setenv("OOMPAH_WORKFLOW_ENGINE_MODE", "shadow")
    monkeypatch.setenv("OOMPAH_WORKFLOW_SHADOW_SCAN_LIMIT", "17")
    monkeypatch.setenv("OOMPAH_WORKFLOW_DIAGNOSTIC_MAX_BYTES", "4096")
    monkeypatch.setenv("OOMPAH_WORKFLOW_LIVENESS_MAX_TASK_RECORDS", "23")
    monkeypatch.setenv("OOMPAH_WORKFLOW_LIVENESS_MAX_PROJECT_RECORDS", "7")
    monkeypatch.setenv("OOMPAH_WORKFLOW_LIVENESS_SNAPSHOT_STALE_SECONDS", "45")
    monkeypatch.setenv(
        "OOMPAH_WORKFLOW_LIVENESS_SLO_DISPATCH_LATENCY_SECONDS", "19"
    )
    config = ServiceConfig.from_workflow(
        WorkflowDefinition(config={}, prompt_template="test")
    )

    assert config.workflow_engine_mode == "shadow"
    assert config.workflow_shadow_scan_limit == 17
    assert config.workflow_diagnostic_max_bytes == 4096
    assert config.workflow_liveness_max_task_records == 23
    assert config.workflow_liveness_max_project_records == 7
    assert config.workflow_liveness_snapshot_stale_seconds == 45
    assert config.workflow_liveness_slo_seconds["dispatch_latency"] == 19


def test_config_rejects_unknown_mode_and_clamps_bounds():
    with pytest.raises(ValueError, match="one of"):
        ServiceConfig(workflow_engine_mode="unknown")

    config = ServiceConfig(
        workflow_shadow_scan_limit=10_000,
        workflow_diagnostic_max_bytes=1,
        workflow_liveness_max_task_records=10_000,
        workflow_liveness_max_project_records=0,
        workflow_liveness_snapshot_stale_seconds=0,
    )
    assert config.workflow_shadow_scan_limit == 1000
    assert config.workflow_diagnostic_max_bytes == 1024
    assert config.workflow_liveness_max_task_records == 1000
    assert config.workflow_liveness_max_project_records == 1
    assert config.workflow_liveness_snapshot_stale_seconds == 1


def test_per_domain_environment_controls_form_a_read_only_mixed_canary(
    monkeypatch,
):
    monkeypatch.setenv("OOMPAH_WORKFLOW_IMPLEMENTATION_MODE", "shadow")
    monkeypatch.setenv("OOMPAH_WORKFLOW_REVIEW_MODE", "off")
    monkeypatch.setenv("OOMPAH_WORKFLOW_INTEGRATION_MODE", "shadow")
    monkeypatch.setenv("OOMPAH_WORKFLOW_EPIC_MODE", "off")
    monkeypatch.setenv("OOMPAH_WORKFLOW_ROLLOUT_MIN_SHADOW_SWEEPS", "7")
    monkeypatch.setenv("OOMPAH_WORKFLOW_ROLLOUT_MIN_SHADOW_SECONDS", "60")

    config = ServiceConfig.from_workflow(
        WorkflowDefinition(config={}, prompt_template="test")
    )

    assert config.workflow_domain_modes == {
        "implementation": "shadow",
        "review": "off",
        "integration": "shadow",
        "epic": "off",
    }
    assert config.workflow_engine_mode == "shadow"
    assert config.workflow_rollout_require_qualification
    assert config.workflow_rollout_min_shadow_sweeps == 7
    assert config.workflow_rollout_min_shadow_seconds == 60


def test_per_domain_enforcement_requires_every_domain():
    mixed = ServiceConfig(
        workflow_domain_modes={
            "implementation": "enforce",
            "review": "shadow",
            "integration": "shadow",
            "epic": "shadow",
        }
    )
    complete = ServiceConfig(
        workflow_domain_modes={
            "implementation": "enforce",
            "review": "enforce",
            "integration": "enforce",
            "epic": "enforce",
        }
    )

    assert mixed.workflow_engine_mode == "shadow"
    assert complete.workflow_engine_mode == "enforce"


def test_unknown_workflow_domain_is_rejected():
    with pytest.raises(ValueError, match="unknown workflow rollout domain"):
        ServiceConfig(workflow_domain_modes={"typo": "shadow"})


def test_invalid_slo_environment_uses_default_and_nonpositive_is_rejected(
    monkeypatch,
):
    monkeypatch.setenv(
        "OOMPAH_WORKFLOW_LIVENESS_SLO_DISPATCH_LATENCY_SECONDS",
        "not-an-integer",
    )
    fallback = ServiceConfig.from_workflow(
        WorkflowDefinition(config={}, prompt_template="test")
    )
    assert fallback.workflow_liveness_slo_seconds["dispatch_latency"] == 120

    monkeypatch.setenv(
        "OOMPAH_WORKFLOW_LIVENESS_SLO_DISPATCH_LATENCY_SECONDS", "0"
    )
    with pytest.raises(ValueError, match="dispatch_latency.*positive"):
        ServiceConfig.from_workflow(
            WorkflowDefinition(config={}, prompt_template="test")
        )


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
    orch._notify_observers.assert_called_once()
    orch._notify_state_only.assert_not_called()


def test_orchestrator_enforce_sweep_materializes_universal_recovery(tmp_path):
    current = issue(state="In Progress")
    tracker = fake_tracker([current])
    orch = orchestrator(tmp_path, mode="enforce")
    attach_project(orch, tracker)

    result = orch._run_workflow_controller_sweep()

    assert result["evaluated"] == 1
    assert result["jobs_created"] == 1
    assert result["action_required"] == 0
    assert result["liveness_status"] == "overdue"
    assert result["liveness_scan_complete"] is True
    jobs = orch.workflow_job_store.list_jobs()
    assert len(jobs) == 1
    assert jobs[0].reason_code == "implementation.recovery_scheduled"
    assert len(orch._load_state()["workflow_liveness"]["records"]) == 1
    tracker.update_issue.assert_not_called()
    tracker.add_comment.assert_not_called()
    snapshot = orch.get_snapshot()
    assert snapshot["workflow_liveness"]["enabled"] is True
    assert snapshot["workflow_liveness"]["healthy"] is False
    assert snapshot["health"]["workflow_liveness"]["projects"]["project-a"][
        "recovery_count"
    ] == 0
    assert not [
        alert
        for alert in snapshot["alerts"]
        if alert.get("source") == "workflow_liveness:action_required"
    ]


def test_orchestrator_newer_terminal_snapshot_retires_durable_recovery(tmp_path):
    current = issue(state="In Progress")
    tracker = fake_tracker([current])
    orch = orchestrator(tmp_path, mode="enforce")
    attach_project(orch, tracker)
    orch._run_workflow_controller_sweep()
    job = orch.workflow_job_store.list_jobs()[0]

    tracker.fetch_all_issues.return_value = [issue(state="Merged")]
    result = orch._run_workflow_controller_sweep()

    assert result["jobs_superseded"] == 1
    assert orch.workflow_job_store.get(job.job_id).state.value == "superseded"
    assert orch.workflow_job_store.schedule_cursor(
        project_id="project-a", task_id=current.identifier
    ) is None
    assert orch.workflow_job_store.snapshot_membership() == ()


def test_orchestrator_captures_generation_before_tracker_fetch(tmp_path):
    current = issue(state="In Progress")
    tracker = fake_tracker([current])
    orch = orchestrator(tmp_path, mode="enforce")
    attach_project(orch, tracker)

    def fetch_after_capture():
        jobs = orch.workflow_job_store.health_snapshot()
        assert jobs["captured_snapshot_generation"] == 1
        assert jobs["accepted_snapshot_generation"] == 0
        return [current]

    tracker.fetch_all_issues.side_effect = fetch_after_capture
    result = orch._run_workflow_controller_sweep()
    jobs = orch.workflow_job_store.health_snapshot()

    assert result["accepted"]
    assert jobs["accepted_snapshot_generation"] == 1
    assert jobs["published_snapshot_generation"] == 1


def test_orchestrator_incomplete_source_scan_fails_liveness_health_closed(tmp_path):
    tracker = fake_tracker([])
    tracker.fetch_all_issues.side_effect = TimeoutError("tracker timed out")
    orch = orchestrator(tmp_path, mode="enforce")
    attach_project(orch, tracker)

    result = orch._run_workflow_controller_sweep()
    snapshot = orch.get_snapshot()

    assert result["liveness_status"] == "incomplete"
    assert result["liveness_scan_complete"] is False
    assert snapshot["workflow_liveness"]["healthy"] is False
    assert snapshot["workflow_liveness"]["source_errors"] == {
        "project-a": "TimeoutError"
    }
    assert snapshot["health"]["status"] == "degraded"
    assert not [
        alert
        for alert in snapshot["alerts"]
        if alert.get("source") == "workflow_liveness:action_required"
    ]


def test_multi_project_partial_failure_retains_healthy_project_and_attribution(
    tmp_path,
):
    good = fake_tracker([issue("OOMPAH-good", state="In Progress")])
    failed = fake_tracker([])
    failed.fetch_all_issues.side_effect = TimeoutError("project unavailable")
    orch = orchestrator(tmp_path, mode="enforce")
    projects = [SimpleNamespace(id="project-a"), SimpleNamespace(id="project-b")]
    orch.project_store = MagicMock()
    orch.project_store.list_all.return_value = projects
    orch._tracker_for_project = MagicMock(
        side_effect=lambda project_id: good if project_id == "project-a" else failed
    )
    orch._notify_observers = MagicMock()
    orch._notify_state_only = MagicMock()

    result = orch._run_workflow_controller_sweep()
    health = orch.workflow_controller.liveness_snapshot()

    assert result["evaluated"] == 1
    assert result["liveness_status"] == "incomplete"
    assert {item.task_id for item in health.tasks} == {"OOMPAH-good"}
    assert health.source_errors == {"project-b": "TimeoutError"}
    assert health.projects["project-b"]["source_error"] == "TimeoutError"
    assert orch.workflow_job_store.list_jobs(project_id="project-a")
    orch._notify_observers.assert_called_once()
    orch._notify_state_only.assert_not_called()


def test_orchestrator_restart_restores_then_converges_liveness_state(tmp_path):
    current = issue(state="In Progress")
    tracker = fake_tracker([current])
    state_path = str(tmp_path / "restart-state.json")
    config = ServiceConfig(
        workspace_root=str(tmp_path / "workspaces"),
        workflow_engine_mode="enforce",
        workflow_liveness_slo_seconds={"restart_convergence": 30},
    )
    first = Orchestrator(
        config,
        str(tmp_path / "WORKFLOW.md"),
        state_path=state_path,
    )
    _OWNED_ORCHESTRATORS.append(first)
    attach_project(first, tracker)
    first_result = first._run_workflow_controller_sweep()
    assert first_result["liveness_status"] == "overdue"
    close_owned_orchestrator(first)

    restarted = Orchestrator(
        config,
        str(tmp_path / "WORKFLOW.md"),
        state_path=state_path,
    )
    _OWNED_ORCHESTRATORS.append(restarted)
    attach_project(restarted, tracker)
    before = restarted.workflow_controller.liveness_snapshot()
    second_result = restarted._run_workflow_controller_sweep()
    after = restarted.workflow_controller.liveness_snapshot()

    assert before.restored
    assert before.restart_reconstruction_pending
    assert before.status == "incomplete"
    assert second_result["liveness_status"] == "healthy"
    assert after.healthy
    assert after.scan_complete
    assert not after.restart_reconstruction_pending
    assert after.restart_convergence_count == 1
    assert restarted._load_state()["workflow_liveness"]["cumulative"][
        "restart_convergence_count"
    ] == 1


def test_orchestrator_nested_liveness_corruption_cannot_restart_false_green(
    tmp_path,
):
    state_path = tmp_path / "nested-corrupt-state.json"
    state_path.write_text(
        json.dumps(
            {
                "workflow_liveness": {
                    "schema_version": 5,
                    "records": [{"task_id": "truncated"}],
                }
            }
        ),
        encoding="utf-8",
    )
    current = issue(state="In Progress")
    tracker = fake_tracker([current])
    config = ServiceConfig(
        workspace_root=str(tmp_path / "workspaces"),
        workflow_engine_mode="enforce",
    )
    orch = Orchestrator(
        config,
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(state_path),
    )
    _OWNED_ORCHESTRATORS.append(orch)
    attach_project(orch, tracker)

    before = orch.workflow_controller.liveness_snapshot()
    result = orch._run_workflow_controller_sweep()
    after = orch.workflow_controller.liveness_snapshot()
    persisted = orch._load_state()["workflow_liveness"]

    assert before.status == "incomplete"
    assert result["liveness_status"] == "overdue"
    assert not after.healthy
    assert after.tasks[0].last_progress_at == "1970-01-01T00:00:00+00:00"
    assert after.recovery_count == 0
    assert set(persisted["event_signature_ledger"]["bits"]) == {"f"}


def test_orchestrator_action_required_decision_is_the_only_liveness_alert(tmp_path):
    current = issue(state="Needs Human")
    tracker = fake_tracker([current])
    orch = orchestrator(tmp_path, mode="enforce")
    attach_project(orch, tracker)

    result = orch._run_workflow_controller_sweep()
    snapshot = orch.get_snapshot()
    alerts = [
        alert
        for alert in snapshot["alerts"]
        if alert.get("source") == "workflow_liveness:action_required"
    ]

    assert result["action_required"] == 1
    assert snapshot["health"]["status"] == "degraded"
    assert len(alerts) == 1
    assert alerts[0]["tasks"] == ["project-a/OOMPAH-1"]


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
        workflow_liveness_max_task_records=7,
        workflow_liveness_max_project_records=3,
        workflow_liveness_snapshot_stale_seconds=42,
        workflow_liveness_slo_seconds={"dispatch_latency": 11},
    )
    orch.reload_config(replacement, "prompt")

    assert orch.workflow_shadow.mode == "off"
    assert orch.workflow_shadow.max_diagnostic_bytes == 2048
    assert orch.workflow_shadow.summary()["tracked_task_count"] == 1
    liveness_limits = orch.workflow_controller.liveness_snapshot().to_dict()[
        "limits"
    ]
    assert liveness_limits == {
        "max_task_records": 7,
        "max_project_records": 3,
        "snapshot_stale_seconds": 42,
    }
    assert orch.workflow_controller.liveness_slo_seconds[
        "dispatch_latency"
    ] == 11
    assert (
        orch._load_state()["workflow_liveness"]["schema_version"]
        == LIVENESS_STATE_SCHEMA_VERSION
    )
    assert orch.get_snapshot()["config"][
        "workflow_liveness_slo_seconds"
    ]["dispatch_latency"] == 11


def test_real_reload_rebases_existing_records_caps_by_priority_and_restores_epoch(
    tmp_path,
):
    state_path = str(tmp_path / "reload-state.json")
    tracker = fake_tracker(
        [
            issue("OOMPAH-normal", state="Open"),
            issue("OOMPAH-action", state="Needs Human"),
        ]
    )
    initial_config = ServiceConfig(
        workspace_root=str(tmp_path / "workspaces"),
        workflow_engine_mode="enforce",
        workflow_liveness_max_task_records=2,
    )
    orch = Orchestrator(
        initial_config,
        str(tmp_path / "WORKFLOW.md"),
        state_path=state_path,
    )
    _OWNED_ORCHESTRATORS.append(orch)
    attach_project(orch, tracker)
    orch._run_workflow_controller_sweep()
    before = orch.workflow_controller.liveness_snapshot()
    old_epoch = before.policy_epoch
    action_before = next(item for item in before.tasks if item.action_required)
    replacement = ServiceConfig(
        workspace_root=str(tmp_path / "replacement"),
        workflow_engine_mode="enforce",
        workflow_liveness_max_task_records=1,
        workflow_liveness_slo_seconds={"operator_visibility": 11},
    )

    orch.reload_config(replacement, "prompt")
    after = orch.workflow_controller.liveness_snapshot()
    persisted = orch._load_state()["workflow_liveness"]
    dashboard = orch.get_snapshot()

    assert after.policy_epoch != old_epoch
    assert after.policy_epoch == orch.workflow_controller.liveness_policy.epoch
    assert after.tracked_task_count == 1
    assert after.tasks[0].task_id == "OOMPAH-action"
    assert after.tasks[0].policy_epoch == after.policy_epoch
    assert after.tasks[0].next_reassessment_at == (
        datetime.fromisoformat(action_before.last_progress_at)
        + timedelta(seconds=11)
    ).isoformat()
    assert persisted["policy_epoch"] == after.policy_epoch
    assert persisted["records"][0]["policy_epoch"] == after.policy_epoch
    assert dashboard["config"][
        "workflow_liveness_policy_epoch"
    ] == after.policy_epoch
    assert dashboard["workflow_liveness"]["policy_epoch"] == after.policy_epoch
    assert dashboard["workflow_liveness"]["tasks"][0][
        "policy_epoch"
    ] == after.policy_epoch
    assert len(persisted["records"]) == 1
    assert persisted["records"][0]["task_id"] == "OOMPAH-action"
    close_owned_orchestrator(orch)

    restarted = Orchestrator(
        replacement,
        str(tmp_path / "WORKFLOW.md"),
        state_path=state_path,
    )
    _OWNED_ORCHESTRATORS.append(restarted)
    restored = restarted.workflow_controller.liveness_snapshot()

    assert restored.restored
    assert restored.policy_epoch == after.policy_epoch
    assert (
        restarted.workflow_controller.liveness_policy.epoch
        == restored.policy_epoch
    )
    assert restored.tasks[0].task_id == "OOMPAH-action"
    assert restored.tasks[0].policy_epoch == restored.policy_epoch
    assert restored.tasks[0].next_reassessment_at == (
        after.tasks[0].next_reassessment_at
    )


def test_config_reload_rejects_live_runtime_cutover_before_partial_apply(tmp_path):
    from oompah.workflow_runtime import WorkflowRuntimeError

    orch = orchestrator(tmp_path, mode="shadow")
    original = orch.config

    class StartedRuntime:
        def set_mode(self, mode):
            raise WorkflowRuntimeError("mode changes require restart")

    orch.workflow_runtime = StartedRuntime()
    replacement = ServiceConfig(
        workspace_root=str(tmp_path / "replacement"),
        workflow_engine_mode="enforce",
    )

    with pytest.raises(WorkflowRuntimeError, match="require restart"):
        orch.reload_config(replacement, "new prompt")

    assert orch.config is original
    assert orch.workflow_shadow.mode == "shadow"


def test_state_and_websocket_message_share_shadow_summary(tmp_path, monkeypatch):
    tracker = fake_tracker([issue()])
    orch = orchestrator(tmp_path)
    attach_project(orch, tracker)
    orch._run_workflow_shadow_sweep()
    snapshot = orch.get_snapshot()
    assert snapshot["workflow_shadow"]["tracked_task_count"] == 1
    assert snapshot["workflow_jobs"]["schema_version"] == 8
    assert snapshot["workflow_jobs"]["states"] == {}

    monkeypatch.setattr(server_module, "_orchestrator", orch)
    server_module._update_state_snapshot(snapshot)
    message = server_module._current_state_message()

    assert message["type"] == "state"
    assert message["data"]["workflow_shadow"] == snapshot["workflow_shadow"]
    assert message["data"]["workflow_liveness"] == snapshot["workflow_liveness"]


def test_snapshot_degrades_and_alerts_while_workflow_call_is_quarantined(tmp_path):
    tracker = fake_tracker([issue()])
    orch = orchestrator(tmp_path)
    attach_project(orch, tracker)
    queued = orch.workflow_job_store.enqueue(
        WorkflowJobSpec(
            project_id="project-a",
            task_id="OOMPAH-1",
            generation="quarantine-1",
            action="authority_revocation",
            idempotency_key="quarantine-health-1",
        )
    )
    claimed = orch.workflow_job_store.claim_next(
        lease_owner="workflow-runtime:999999:deadbeef",
        lease_seconds=30,
        actions=("authority_revocation",),
    )
    assert claimed is not None and claimed.job_id == queued.job_id
    orch.workflow_job_store.quarantine_owned(
        claimed.job_id,
        claimed.lease_token,
        category=WorkflowFailureCategory.TIMEOUT,
        error="adapter did not return",
    )

    snapshot = orch.get_snapshot()
    alert = next(
        item
        for item in snapshot["global_alerts"]
        if item["source"] == "workflow_jobs:quarantined_calls"
    )

    assert snapshot["health"]["status"] == "degraded"
    assert snapshot["health"]["workflow_jobs"]["quarantined"] == 1
    assert snapshot["workflow_jobs"]["leases"]["quarantined"] == 1
    assert alert["action_required"] is True
    assert alert["quarantined"] == 1


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
    orch._tick_pool.shutdown(wait=True, cancel_futures=True)
    orch._refresh_pool.shutdown(wait=True, cancel_futures=True)
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
