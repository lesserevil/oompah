"""Focused regression coverage for OOMPAH-843 validation contracts."""

from __future__ import annotations

import asyncio
import hashlib
import json
import subprocess
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from oompah import api_agent
from oompah.api_agent import (
    _exec_run_command,
    _execute_tool,
    _resolve_run_command_timeout_with_target,
)
from oompah.auditor import (
    AUDITOR_VALIDATION_DEADLINE_REASON,
    AuditorTargetContract,
    auditor_validation_timeout_message,
    build_auditor_validation_contract,
    check_auditor_command,
    is_recoverable_auditor_command_denial,
    resolve_auditor_validation_budget,
)
from oompah.acp_backends.base import turn_deadline_exceeded
from oompah.authority_boundary import auditor_policy
from oompah.config import ServiceConfig
from oompah.models import Issue, Project
from oompah.orchestrator import Orchestrator
from oompah.projects import ProjectError, ProjectStore
from oompah.prompt import render_prompt
from oompah.quality_gate import BranchQualityGate
from oompah.terminal_audit import (
    EvidenceFingerprint,
    RequestState,
    TargetState,
    TerminalAuditRecord,
)
from oompah.terminal_audit_metadata import TerminalAuditMetadata
from oompah.terminal_audit_health import (
    AuditHealthObservation,
    TerminalAuditHealth,
    build_terminal_audit_health,
)
from oompah.tool_liveness import ToolLivenessMonitor


def _project(project_id: str = "project-1", **overrides) -> Project:
    values = {
        "id": project_id,
        "name": project_id,
        "repo_url": f"https://example.invalid/{project_id}.git",
        "repo_path": f"/work/{project_id}",
        "auditor_validation_targets": ["focused", "test", "test-serial"],
        "auditor_validation_target_deadlines": {
            "focused": 300,
            "test": 1200,
            "test-serial": 1800,
        },
        "auditor_validation_target_expected_seconds": {
            "focused": 120,
            "test": 1080,
            "test-serial": 1500,
        },
    }
    values.update(overrides)
    return Project(**values)


def _issue() -> Issue:
    return Issue(
        id="task-1",
        identifier="OOMPAH-796",
        title="Validate a long branch gate",
        description="Run the compatible configured validation target.",
        state="In Validation",
        issue_type="task",
        project_id="project-1",
    )


def _target() -> AuditorTargetContract:
    return AuditorTargetContract(
        audit_id="audit-1",
        task_id="OOMPAH-796",
        project_id="project-1",
        target_state="Merged",
        evidence_fingerprint="a" * 64,
        previous_state="In Validation",
    )


def test_oompah_796_is_rejected_before_launch_when_gate_cannot_finish(monkeypatch):
    monkeypatch.delenv(
        "OOMPAH_AUDITOR_VALIDATION_TARGET_EXPECTED_SECONDS",
        raising=False,
    )
    project = _project(
        auditor_validation_target_deadlines={
            "focused": 300,
            "test": 720,
            "test-serial": 1800,
        }
    )

    contract = build_auditor_validation_contract(project)

    assert contract.feasible is False
    assert contract.configuration_error is not None
    assert "target 'test'" in contract.configuration_error
    assert "expected_seconds=1080" in contract.configuration_error
    assert "deadline_seconds=720" in contract.configuration_error


def test_compatible_contract_preserves_preference_order_and_sources(monkeypatch):
    monkeypatch.setenv(
        "OOMPAH_AUDITOR_VALIDATION_TARGET_EXPECTED_SECONDS",
        '{"test": 1000}',
    )
    project = _project(
        auditor_validation_target_expected_seconds={
            "focused": 120,
            "test-serial": 1500,
        },
    )

    contract = build_auditor_validation_contract(project)

    assert contract.feasible is True
    assert [item.target for item in contract.targets] == [
        "focused",
        "test",
        "test-serial",
    ]
    assert contract.budget_for_target("focused").expected_source == "project"
    assert contract.budget_for_target("test").expected_source == "environment"
    assert contract.budget_for_target("test-serial").expected_source == "project"


def test_explicit_target_without_duration_evidence_fails_closed(monkeypatch):
    monkeypatch.delenv(
        "OOMPAH_AUDITOR_VALIDATION_TARGET_EXPECTED_SECONDS",
        raising=False,
    )
    project = _project(
        auditor_validation_targets=["test"],
        auditor_validation_target_deadlines={"test": 1200},
        auditor_validation_target_expected_seconds={},
    )

    contract = build_auditor_validation_contract(project)

    assert contract.feasible is False
    assert contract.targets == ()
    assert "no configured or observed expected duration" in (
        contract.configuration_error or ""
    )


def test_explicit_deadline_for_implicit_default_requires_duration_evidence(
    monkeypatch,
):
    monkeypatch.delenv(
        "OOMPAH_AUDITOR_VALIDATION_TARGET_EXPECTED_SECONDS",
        raising=False,
    )
    project = Project(
        id="project-1",
        name="project-1",
        repo_url="https://example.invalid/project-1.git",
        repo_path="/work/project-1",
        auditor_validation_target_deadlines={"test": 1200},
    )

    contract = build_auditor_validation_contract(project)

    assert contract.feasible is False
    assert "target 'test' has no configured or observed expected duration" in (
        contract.configuration_error or ""
    )


def test_contract_isolated_by_project(monkeypatch):
    monkeypatch.delenv(
        "OOMPAH_AUDITOR_VALIDATION_TARGET_EXPECTED_SECONDS",
        raising=False,
    )
    first = _project("first")
    second = _project(
        "second",
        auditor_validation_target_deadlines={
            "focused": 30,
            "test": 2000,
            "test-serial": 2400,
        },
        auditor_validation_target_expected_seconds={
            "focused": 10,
            "test": 1500,
            "test-serial": 2000,
        },
    )

    first_budget, first_error = resolve_auditor_validation_budget(
        "make test",
        first,
        global_timeout_seconds=720,
    )
    second_budget, second_error = resolve_auditor_validation_budget(
        "make test",
        second,
        global_timeout_seconds=720,
    )

    assert first_error is None
    assert second_error is None
    assert first_budget.deadline_seconds == 1200
    assert second_budget.deadline_seconds == 2000


@pytest.mark.parametrize(
    "command",
    [
        "make focused extra",
        "MAKE focused",
        "make unknown",
        "make focused && git status",
    ],
)
def test_focused_make_target_must_be_explicit_and_exact(command):
    denial = check_auditor_command(command, project=_project())

    assert denial is not None
    assert "command was not executed" in denial
    assert is_recoverable_auditor_command_denial(denial) is False


def test_deadline_mapping_never_authorizes_an_unapproved_target():
    project = _project()
    project.auditor_validation_target_deadlines["secret-target"] = 2400

    contract = build_auditor_validation_contract(project)
    budget, error = resolve_auditor_validation_budget(
        "make secret-target",
        project,
    )

    assert contract.configuration_error is not None
    assert "unapproved target 'secret-target'" in contract.configuration_error
    assert budget is None
    assert error == contract.configuration_error


def test_project_round_trip_preserves_duration_evidence(monkeypatch):
    monkeypatch.delenv(
        "OOMPAH_AUDITOR_VALIDATION_TARGET_EXPECTED_SECONDS",
        raising=False,
    )
    project = _project()

    rebuilt = Project.from_dict(project.to_dict())

    assert rebuilt.auditor_validation_target_deadlines == (
        project.auditor_validation_target_deadlines
    )
    assert rebuilt.auditor_validation_target_expected_seconds == (
        project.auditor_validation_target_expected_seconds
    )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("auditor_validation_targets", "test", "must be a list"),
        (
            "auditor_validation_targets",
            ["test", "test"],
            "duplicate auditor validation target",
        ),
        (
            "auditor_validation_target_deadlines",
            {"test": True},
            "must be a positive integer",
        ),
        (
            "auditor_validation_target_expected_seconds",
            {"unknown": 1},
            "contains unapproved target",
        ),
    ],
)
def test_project_load_rejects_malformed_validation_configuration(
    field,
    value,
    message,
):
    data = _project().to_dict()
    data[field] = value

    with pytest.raises(ValueError, match=message):
        Project.from_dict(data)


def test_project_store_load_marks_impossible_contract(tmp_path, monkeypatch):
    monkeypatch.delenv(
        "OOMPAH_AUDITOR_VALIDATION_TARGET_EXPECTED_SECONDS",
        raising=False,
    )
    project = _project(
        auditor_validation_target_deadlines={
            "focused": 300,
            "test": 720,
            "test-serial": 1800,
        }
    )
    path = tmp_path / "projects.json"
    path.write_text(json.dumps([project.to_dict()]), encoding="utf-8")

    loaded = ProjectStore(path=str(path)).get(project.id)

    assert loaded is not None
    assert loaded.auditor_validation_contract_error is not None
    assert "expected_seconds=1080" in loaded.auditor_validation_contract_error


def test_quality_gate_history_uses_longest_completed_duration(tmp_path):
    state = tmp_path / "quality_gates.json"
    state.write_text(
        json.dumps(
            {
                "results": {
                    "pass": {
                        "status": "passed",
                        "repo_identity": "repo-1",
                        "command": "make test",
                        "duration_seconds": 719.2,
                    },
                    "failure": {
                        "status": "failed",
                        "repo_identity": "repo-1",
                        "command": "make test",
                        "duration_seconds": 1080.2,
                    },
                    "timeout": {
                        "status": "timed_out",
                        "repo_identity": "repo-1",
                        "command": "make test",
                        "duration_seconds": 2400,
                    },
                    "corrupt": {
                        "status": "passed",
                        "repo_identity": "repo-2",
                        "command": "make test",
                        "duration_seconds": True,
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    observed = BranchQualityGate(
        str(state)
    ).observed_command_durations_seconds()

    assert observed == {("repo-1", "make test"): 1081}


def test_startup_hydrates_observed_exact_gate_before_advertising_target(
    tmp_path,
    monkeypatch,
):
    monkeypatch.delenv(
        "OOMPAH_AUDITOR_VALIDATION_TARGET_EXPECTED_SECONDS",
        raising=False,
    )
    project = _project(
        auditor_validation_targets=["test"],
        auditor_validation_target_deadlines={"test": 1200},
        auditor_validation_target_expected_seconds={},
        test_command_full="make test",
    )
    projects_path = tmp_path / "projects.json"
    projects_path.write_text(
        json.dumps([project.to_dict()]),
        encoding="utf-8",
    )
    (tmp_path / "quality_gates.json").write_text(
        json.dumps(
            {
                "results": {
                    "observed": {
                        "status": "passed",
                        "repo_identity": project.repo_url,
                        "command": "make test",
                        "duration_seconds": 1080.2,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    store = ProjectStore(path=str(projects_path))

    orchestrator = Orchestrator(
        ServiceConfig(workspace_root=str(tmp_path / "workspace")),
        str(tmp_path / "WORKFLOW.md"),
        project_store=store,
        state_path=str(tmp_path / "service-state.json"),
    )
    try:
        loaded = store.get(project.id)
        contract = build_auditor_validation_contract(loaded)

        assert loaded.auditor_validation_contract_error is None
        assert loaded.auditor_validation_target_observed_seconds == {"test": 1081}
        assert contract.feasible is True
        assert contract.budget_for_target("test").expected_seconds == 1081
        assert contract.budget_for_target("test").expected_source == "observed"
    finally:
        orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
        orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)


def test_project_update_is_atomic_when_contract_would_be_impossible(
    tmp_path,
    monkeypatch,
):
    monkeypatch.delenv(
        "OOMPAH_AUDITOR_VALIDATION_TARGET_EXPECTED_SECONDS",
        raising=False,
    )
    project = _project()
    path = tmp_path / "projects.json"
    path.write_text(json.dumps([project.to_dict()]), encoding="utf-8")
    store = ProjectStore(path=str(path))

    with pytest.raises(ProjectError, match="expected_seconds=1080"):
        store.update(
            project.id,
            auditor_validation_target_deadlines={
                "focused": 300,
                "test": 720,
                "test-serial": 1800,
            },
        )

    assert store.get(project.id).auditor_validation_target_deadlines["test"] == 1200


def test_project_update_preserves_hydrated_observed_duration(tmp_path, monkeypatch):
    monkeypatch.delenv(
        "OOMPAH_AUDITOR_VALIDATION_TARGET_EXPECTED_SECONDS",
        raising=False,
    )
    project = _project(
        auditor_validation_targets=["test"],
        auditor_validation_target_deadlines={"test": 1200},
        auditor_validation_target_expected_seconds={},
        test_command_full="make test",
    )
    path = tmp_path / "projects.json"
    path.write_text(json.dumps([project.to_dict()]), encoding="utf-8")
    store = ProjectStore(path=str(path))
    loaded = store.get(project.id)
    loaded.auditor_validation_target_observed_seconds = {"test": 1081}

    updated = store.update(
        project.id,
        auditor_validation_target_deadlines={"test": 1300},
    )

    assert updated.auditor_validation_target_deadlines == {"test": 1300}
    assert updated.auditor_validation_target_observed_seconds == {"test": 1081}


def test_project_update_does_not_reuse_observation_after_gate_change(
    tmp_path,
    monkeypatch,
):
    monkeypatch.delenv(
        "OOMPAH_AUDITOR_VALIDATION_TARGET_EXPECTED_SECONDS",
        raising=False,
    )
    project = _project(
        auditor_validation_targets=["test"],
        auditor_validation_target_deadlines={"test": 1200},
        auditor_validation_target_expected_seconds={},
        test_command_full="make test",
    )
    path = tmp_path / "projects.json"
    path.write_text(json.dumps([project.to_dict()]), encoding="utf-8")
    store = ProjectStore(path=str(path))
    loaded = store.get(project.id)
    loaded.auditor_validation_target_observed_seconds = {"test": 1081}

    with pytest.raises(
        ProjectError,
        match="no configured or observed expected duration",
    ):
        store.update(
            project.id,
            test_command_full="make verify",
        )

    assert store.get(project.id).test_command_full == "make test"
    assert store.get(project.id).auditor_validation_target_observed_seconds == {
        "test": 1081
    }


def test_project_update_clears_stale_observation_when_configured_evidence_remains(
    tmp_path,
    monkeypatch,
):
    monkeypatch.delenv(
        "OOMPAH_AUDITOR_VALIDATION_TARGET_EXPECTED_SECONDS",
        raising=False,
    )
    project = _project(
        auditor_validation_targets=["test"],
        auditor_validation_target_deadlines={"test": 1200},
        auditor_validation_target_expected_seconds={"test": 900},
        test_command_full="make test",
    )
    path = tmp_path / "projects.json"
    path.write_text(json.dumps([project.to_dict()]), encoding="utf-8")
    store = ProjectStore(path=str(path))
    loaded = store.get(project.id)
    loaded.auditor_validation_target_observed_seconds = {"test": 1081}

    updated = store.update(project.id, test_command_full="make verify")

    assert updated.test_command_full == "make verify"
    assert updated.auditor_validation_target_observed_seconds == {}


def test_startup_surfaces_configuration_alert_separate_from_transport(
    tmp_path,
    monkeypatch,
):
    monkeypatch.delenv(
        "OOMPAH_AUDITOR_VALIDATION_TARGET_EXPECTED_SECONDS",
        raising=False,
    )
    project = _project(
        auditor_validation_target_deadlines={
            "focused": 300,
            "test": 720,
            "test-serial": 1800,
        }
    )
    path = tmp_path / "projects.json"
    path.write_text(json.dumps([project.to_dict()]), encoding="utf-8")
    store = ProjectStore(path=str(path))
    orchestrator = Orchestrator(
        ServiceConfig(workspace_root=str(tmp_path / "workspace")),
        str(tmp_path / "WORKFLOW.md"),
        project_store=store,
        state_path=str(tmp_path / "service-state.json"),
    )
    try:
        alerts = orchestrator.get_snapshot()["alerts"]
        matching = [
            alert
            for alert in alerts
            if "validation_contract_incompatible" in alert["source"]
        ]

        assert len(matching) == 1
        assert "expected_seconds=1080" in matching[0]["message"]
        assert "deadline_seconds=720" in matching[0]["message"]
        assert "transport" not in matching[0]["source"]
    finally:
        orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
        orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)


def test_dispatch_preflight_leaves_impossible_audit_pending_without_attempt(
    tmp_path,
    monkeypatch,
):
    monkeypatch.delenv(
        "OOMPAH_AUDITOR_VALIDATION_TARGET_EXPECTED_SECONDS",
        raising=False,
    )
    project = _project(
        auditor_validation_target_deadlines={
            "focused": 300,
            "test": 720,
            "test-serial": 1800,
        }
    )
    path = tmp_path / "projects.json"
    path.write_text(json.dumps([project.to_dict()]), encoding="utf-8")
    store = ProjectStore(path=str(path))
    orchestrator = Orchestrator(
        ServiceConfig(workspace_root=str(tmp_path / "workspace")),
        str(tmp_path / "WORKFLOW.md"),
        project_store=store,
        state_path=str(tmp_path / "service-state.json"),
    )
    record = TerminalAuditRecord(
        audit_id="audit-1",
        project_id=project.id,
        task_id="OOMPAH-796",
        target_state=TargetState.DONE,
        evidence_fingerprint=EvidenceFingerprint(
            hashlib.sha256(b"evidence").hexdigest()
        ),
        request_state=RequestState.PENDING,
    )
    document = TerminalAuditMetadata(pending_chain=[record])
    issue = _issue()
    audit_store = SimpleNamespace(read=lambda _identifier: document)
    persist = Mock(return_value=True)
    dispatch = Mock(side_effect=AssertionError("auditor launched"))
    selector = Mock(side_effect=AssertionError("auditor selector built"))
    health_refresh = Mock()
    try:
        monkeypatch.setattr(orchestrator, "_dispatch_is_blocked", lambda: False)
        monkeypatch.setattr(orchestrator, "_is_rate_limited", lambda: False)
        monkeypatch.setattr(orchestrator, "_available_slots", lambda: 1)
        monkeypatch.setattr(orchestrator, "_fetch_audit_candidates", lambda: [issue])
        monkeypatch.setattr(orchestrator, "_audit_store", lambda _issue: audit_store)
        monkeypatch.setattr(orchestrator, "_audit_selector", selector)
        monkeypatch.setattr(orchestrator, "_running_values_snapshot", lambda: [])
        monkeypatch.setattr(orchestrator, "_audit_update_record", persist)
        monkeypatch.setattr(orchestrator, "_dispatch", dispatch)
        monkeypatch.setattr(
            orchestrator,
            "_refresh_terminal_audit_health",
            health_refresh,
        )

        asyncio.run(orchestrator._dispatch_audit_lane())

        assert record.request_state == RequestState.PENDING
        assert record.attempts == []
        persist.assert_not_called()
        dispatch.assert_not_called()
        selector.assert_not_called()
        assert any(
            condition.kind == "validation_contract_incompatible"
            and condition.project_id == project.id
            and condition.task_id == "project-configuration"
            for condition in orchestrator._terminal_audit_manual_alerts.values()
        )
    finally:
        orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
        orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)


def test_project_configuration_alert_clears_without_a_dispatchable_audit(
    tmp_path,
    monkeypatch,
):
    monkeypatch.delenv(
        "OOMPAH_AUDITOR_VALIDATION_TARGET_EXPECTED_SECONDS",
        raising=False,
    )
    project = _project(
        auditor_validation_target_deadlines={
            "focused": 300,
            "test": 720,
            "test-serial": 1800,
        }
    )
    path = tmp_path / "projects.json"
    path.write_text(json.dumps([project.to_dict()]), encoding="utf-8")
    store = ProjectStore(path=str(path))
    orchestrator = Orchestrator(
        ServiceConfig(workspace_root=str(tmp_path / "workspace")),
        str(tmp_path / "WORKFLOW.md"),
        project_store=store,
        state_path=str(tmp_path / "service-state.json"),
    )
    try:
        assert any(
            condition.kind == "validation_contract_incompatible"
            for condition in orchestrator._terminal_audit_manual_alerts.values()
        )
        store.update(
            project.id,
            auditor_validation_target_deadlines={
                "focused": 300,
                "test": 1200,
                "test-serial": 1800,
            },
        )
        monkeypatch.setattr(orchestrator, "_dispatch_is_blocked", lambda: True)

        asyncio.run(orchestrator._dispatch_audit_lane())

        assert not any(
            condition.kind == "validation_contract_incompatible"
            for condition in orchestrator._terminal_audit_manual_alerts.values()
        )
    finally:
        orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
        orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)


def test_configuration_health_is_not_misclassified_as_transport_or_stale():
    record = TerminalAuditRecord(
        audit_id="audit-1",
        project_id="project-1",
        task_id="OOMPAH-796",
        target_state=TargetState.DONE,
        evidence_fingerprint=EvidenceFingerprint(
            hashlib.sha256(b"evidence").hexdigest()
        ),
        request_state=RequestState.PENDING,
        created_at="2026-01-01T00:00:00+00:00",
    )

    health = build_terminal_audit_health(
        [
            AuditHealthObservation(
                project_id="project-1",
                issue_identifier="OOMPAH-796",
                issue_created_at="2026-01-01T00:00:00+00:00",
                record=record,
                configuration_error=True,
            )
        ],
        stale_after_seconds=1,
    )

    assert health.pending_count == 1
    assert health.configuration_error_count == 1
    assert health.transport_failure_count == 0
    assert health.policy_incompatibility_count == 0
    assert health.stale_pending_count == 0
    assert health.degraded is True
    assert TerminalAuditHealth.from_dict(
        health.to_dict()
    ).configuration_error_count == 1


def test_api_agent_uses_target_deadline_even_with_eager_global_timeout(
    tmp_path,
    monkeypatch,
):
    monkeypatch.delenv(
        "OOMPAH_AUDITOR_VALIDATION_TARGET_EXPECTED_SECONDS",
        raising=False,
    )
    project = _project()
    store = SimpleNamespace(get=lambda project_id: project)
    captured: dict[str, object] = {}

    def fake_run_command(_workspace, _args, **kwargs):
        captured.update(kwargs)
        return "exit_code: 0"

    monkeypatch.setitem(api_agent._TOOL_DISPATCH, "run_command", fake_run_command)

    result = _execute_tool(
        tmp_path,
        "run_command",
        {"command": "make test"},
        cmd_timeout=720,
        project_id=project.id,
        task_identifier="OOMPAH-796",
        action_policy=auditor_policy(
            task_identifier="OOMPAH-796",
            project_id=project.id,
        ),
        project_store=store,
    )

    assert result == "exit_code: 0"
    assert captured["timeout"] == 1200
    assert AUDITOR_VALIDATION_DEADLINE_REASON in captured["timeout_error"]


def test_managed_api_auditor_without_project_identity_fails_closed(
    tmp_path,
    monkeypatch,
):
    forbidden = Mock(side_effect=AssertionError("command executed"))
    monkeypatch.setitem(api_agent._TOOL_DISPATCH, "run_command", forbidden)
    store = SimpleNamespace(get=Mock())

    result = _execute_tool(
        tmp_path,
        "run_command",
        {"command": "make test"},
        cmd_timeout=720,
        project_id=None,
        action_policy=auditor_policy(project_id=None),
        project_store=store,
    )

    assert "auditor project identity is unavailable" in result
    assert "reason=auditor_validation_configuration" in result
    store.get.assert_not_called()
    forbidden.assert_not_called()


def test_api_resolver_uses_injected_store_without_default_store_lookup(monkeypatch):
    monkeypatch.delenv(
        "OOMPAH_AUDITOR_VALIDATION_TARGET_EXPECTED_SECONDS",
        raising=False,
    )
    project = _project()
    store = Mock()
    store.get.return_value = project

    timeout = _resolve_run_command_timeout_with_target(
        "make test-serial",
        project_id=project.id,
        raw_global="720",
        project_store=store,
    )

    assert timeout == 1800
    store.get.assert_called_once_with(project.id)


def test_configured_focused_target_uses_validation_lease_even_when_name_is_not_heavy(
    tmp_path,
    monkeypatch,
):
    events: list[str] = []

    class FakeHandle:
        pass_fds: tuple[int, ...] = ()

        def attach_process(self, _process, *, timeout_seconds):
            events.append(f"attach:{timeout_seconds}")

        def release(self):
            events.append("release")

    class FakeLease:
        def acquire(self, _owner, *, is_cancelled=None):
            events.append("acquire")
            return FakeHandle()

    class FakeProcess:
        pid = 1
        returncode = 0

        def __init__(self, *_args, **_kwargs):
            events.append("popen")

        def communicate(self, timeout=None):
            return "", ""

    monkeypatch.setattr(api_agent.subprocess, "Popen", FakeProcess)

    result = _exec_run_command(
        tmp_path,
        {"command": "make focused"},
        timeout=300,
        validation_lease=FakeLease(),
        validation_owner=object(),
        require_validation_lease=True,
        configured_validation_target=True,
    )

    assert result == "exit_code: 0"
    assert events == ["acquire", "popen", "attach:300", "release"]


def test_queue_wait_does_not_consume_runtime_or_outer_turn_deadline(
    tmp_path,
    monkeypatch,
):
    class FakeClock:
        value = 0.0

        def monotonic(self):
            return self.value

        def advance(self, seconds):
            self.value += seconds

    clock = FakeClock()
    events: list[str] = []

    class FakeHandle:
        pass_fds: tuple[int, ...] = ()

        def attach_process(self, _process, *, timeout_seconds):
            events.append(f"attach:{timeout_seconds}")

        def release(self):
            events.append("release")

    class FakeLease:
        def acquire(self, _owner, **_kwargs):
            events.append("wait")
            clock.advance(600)
            return FakeHandle()

    class FakeProcess:
        pid = 101
        returncode = 0

        def __init__(self, *_args, **_kwargs):
            events.append("popen")

        def communicate(self, timeout=None):
            clock.advance(1080)
            return "completed after 1080 seconds", ""

        def poll(self):
            return self.returncode

    monitor = ToolLivenessMonitor()
    monkeypatch.setattr(api_agent.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(api_agent.subprocess, "Popen", FakeProcess)

    result = _exec_run_command(
        tmp_path,
        {"command": "make focused"},
        timeout=1200,
        tool_liveness=monitor,
        validation_lease=FakeLease(),
        validation_owner=object(),
        configured_validation_target=True,
    )

    assert "completed after 1080 seconds" in result
    assert "exit_code: 0" in result
    assert events == ["wait", "popen", "attach:1200", "release"]
    assert monitor.outer_deadline_extension_seconds() == 1680
    assert turn_deadline_exceeded(
        1200,
        tool_liveness=monitor,
        extension_baseline_seconds=0,
        now_monotonic=1680,
    ) is False
    clock.advance(1201)
    assert turn_deadline_exceeded(
        1200,
        tool_liveness=monitor,
        extension_baseline_seconds=0,
        now_monotonic=clock.value,
    ) is True


def test_true_validation_overrun_is_terminated_at_target_deadline(
    tmp_path,
    monkeypatch,
):
    class FakeClock:
        value = 0.0

        def monotonic(self):
            return self.value

        def advance(self, seconds):
            self.value += seconds

    clock = FakeClock()
    terminations: list[int] = []

    class FakeProcess:
        pid = 202
        returncode = None
        stdout = None
        stderr = None

        def __init__(self, *_args, **_kwargs):
            self.communicate_calls = 0

        def communicate(self, timeout=None):
            self.communicate_calls += 1
            if self.communicate_calls == 1:
                clock.advance(1201)
                raise subprocess.TimeoutExpired("make test", timeout)
            self.returncode = -15
            return "", ""

    monkeypatch.setattr(api_agent.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(api_agent.subprocess, "Popen", FakeProcess)
    monkeypatch.setattr(
        api_agent.os,
        "killpg",
        lambda pid, _signal: terminations.append(pid),
    )
    timeout_error = (
        "Error: exact target overran its deadline "
        f"[reason={AUDITOR_VALIDATION_DEADLINE_REASON}]"
    )

    result = _exec_run_command(
        tmp_path,
        {"command": "make test"},
        timeout=1200,
        timeout_error=timeout_error,
        configured_validation_target=True,
    )

    assert result == timeout_error
    assert terminations == [202]


def test_all_acp_catalogs_apply_the_same_project_target_deadline(
    tmp_path,
    monkeypatch,
):
    monkeypatch.delenv(
        "OOMPAH_AUDITOR_VALIDATION_TARGET_EXPECTED_SECONDS",
        raising=False,
    )
    project = _project()
    store = SimpleNamespace(get=lambda _project_id: project)
    captured: list[dict[str, object]] = []

    def fake_exec_run_command(_workspace, _args, **kwargs):
        captured.append(kwargs)
        return "exit_code: 0"

    monkeypatch.setattr(api_agent, "_exec_run_command", fake_exec_run_command)

    def named_tool(name, _description, _schema):
        def decorate(handler):
            handler.name = name
            handler.handler = handler
            return handler

        return decorate

    claude_sdk = types.ModuleType("claude_agent_sdk")
    claude_sdk.tool = named_tool
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", claude_sdk)
    opencode_sdk = types.ModuleType("opencode")
    opencode_sdk.tool = named_tool
    monkeypatch.setitem(sys.modules, "opencode", opencode_sdk)

    class CodexTool:
        def __init__(self, handler):
            self.name = handler.__name__
            self._handler = handler

        async def on_invoke_tool(self, _context, raw_arguments):
            return await self._handler(**json.loads(raw_arguments))

    agents_sdk = types.ModuleType("agents")
    agents_sdk.function_tool = CodexTool
    monkeypatch.setitem(sys.modules, "agents", agents_sdk)

    from oompah.acp_tools import (
        build_codex_tool_catalog,
        build_opencode_tool_catalog,
        build_tool_catalog,
    )

    common = {
        "project_store": store,
        "project_id": project.id,
        "task_identifier": "OOMPAH-796",
        "auditor": True,
        "action_policy": auditor_policy(
            task_identifier="OOMPAH-796",
            project_id=project.id,
        ),
    }
    claude_tools = build_tool_catalog(str(tmp_path), **common)
    opencode_tools = build_opencode_tool_catalog(str(tmp_path), **common)
    codex_tools = build_codex_tool_catalog(str(tmp_path), **common)

    claude_result = asyncio.run(
        next(tool for tool in claude_tools if tool.name == "run_command").handler(
            {"command": "make test"}
        )
    )
    opencode_result = asyncio.run(
        next(tool for tool in opencode_tools if tool.name == "run_command").handler(
            {"command": "make test"}
        )
    )
    codex_result = asyncio.run(
        next(tool for tool in codex_tools if tool.name == "run_command").on_invoke_tool(
            None,
            '{"command":"make test"}',
        )
    )

    assert claude_result["content"][0]["text"] == "exit_code: 0"
    assert opencode_result["content"][0]["text"] == "exit_code: 0"
    assert codex_result == "exit_code: 0"
    assert [kwargs["timeout"] for kwargs in captured] == [1200, 1200, 1200]
    assert all(
        AUDITOR_VALIDATION_DEADLINE_REASON in kwargs["timeout_error"]
        for kwargs in captured
    )


def test_timeout_response_forbids_predictably_slower_fallback():
    budget = build_auditor_validation_contract(_project()).budget_for_target("test")

    message = auditor_validation_timeout_message(budget)

    assert "deadline_seconds=1200" in message
    assert "expected_seconds=1080" in message
    assert "Do not fall back to a broader or predictably slower target" in message


def test_prompt_lists_effective_budgets_and_forbids_serial_timeout_loop(monkeypatch):
    monkeypatch.delenv(
        "OOMPAH_AUDITOR_VALIDATION_TARGET_EXPECTED_SECONDS",
        raising=False,
    )
    rendered = render_prompt(
        "Issue {{ issue.identifier }}",
        _issue(),
        project=_project(),
        auditor_context={
            "target": _target(),
            "evidence_summary": {"source_sha": "abc"},
            "comments": [],
        },
    )

    assert "Approved validation targets (preference order)" in rendered
    assert "make focused — expected_seconds=120; deadline_seconds=300" in rendered
    assert "make test — expected_seconds=1080; deadline_seconds=1200" in rendered
    assert "serial full-suite fallback" in rendered


def test_configuration_error_prevents_api_command_execution(tmp_path, monkeypatch):
    monkeypatch.delenv(
        "OOMPAH_AUDITOR_VALIDATION_TARGET_EXPECTED_SECONDS",
        raising=False,
    )
    project = _project(
        auditor_validation_target_deadlines={
            "focused": 300,
            "test": 720,
            "test-serial": 1800,
        }
    )
    forbidden = Mock(side_effect=AssertionError("command executed"))
    monkeypatch.setitem(api_agent._TOOL_DISPATCH, "run_command", forbidden)

    result = _execute_tool(
        Path(tmp_path),
        "run_command",
        {"command": "make test"},
        cmd_timeout=720,
        project_id=project.id,
        action_policy=auditor_policy(project_id=project.id),
        project_store=SimpleNamespace(get=lambda _project_id: project),
    )

    assert "auditor validation configuration is incompatible" in result
    assert "expected_seconds=1080" in result
    forbidden.assert_not_called()
