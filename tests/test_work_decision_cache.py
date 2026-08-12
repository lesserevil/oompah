"""Behavioural regressions for the authoritative WorkDecision cache."""

from __future__ import annotations

import asyncio
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

import oompah.orchestrator as orchestrator_module
import oompah.server as server_module
from oompah.models import Issue, Project
from oompah.orchestrator import Orchestrator
from oompah.projects import ProjectError, ProjectStore
from oompah.state_branch_migration import (
    MigrationResult,
    StateBranchVerificationResult,
)
from oompah.work_decision import PermittedAction, UnmetPrerequisite, WorkDecision
from oompah.workflow_contract import TaskDisposition, WorkflowOwner
from oompah.workflow_facts import (
    FactDomain,
    FactObservation,
    LandingFact,
    LandingState,
    REQUIRED_FACT_DOMAINS,
    WorkflowFacts,
)
from oompah.workflow_jobs import WorkflowJobPublicationError, WorkflowJobSpec
from oompah.workflow_reasons import AlertSeverity


def _orchestrator(*, mode: str = "enforce") -> Orchestrator:
    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator.config = SimpleNamespace(workflow_engine_mode=mode)
    orchestrator._work_decisions_lock = threading.RLock()
    orchestrator._work_decisions = {}
    orchestrator._work_decision_source = None
    orchestrator._work_decision_generation = 0
    orchestrator._work_decision_publication_epoch = 1
    orchestrator._work_decision_updated_at = None
    orchestrator._work_decision_unavailable_projects = set()
    orchestrator._work_decision_incomplete_projects = set()
    orchestrator._work_decision_incomplete_keys = set()
    orchestrator._work_decision_incomplete_reason = None
    orchestrator._work_decision_snapshot_complete = False
    orchestrator._workflow_shadow_scan_cursor = 0
    return orchestrator


def _decision(
    task_id: str,
    *,
    project_id: str = "project-a",
    reason: str = "dispatch.eligible",
    action_required: bool = False,
) -> WorkDecision:
    return WorkDecision(
        project_id=project_id,
        task_id=task_id,
        status="Needs Human" if action_required else "Open",
        disposition=(
            TaskDisposition.ACTION_REQUIRED
            if action_required
            else TaskDisposition.RUNNABLE
        ),
        reason_code=reason,
        responsible_owner=(
            WorkflowOwner.OPERATOR
            if action_required
            else WorkflowOwner.DISPATCHER
        ),
        unmet_prerequisites=(
            (UnmetPrerequisite("operator.action_required", task_id),)
            if action_required
            else ()
        ),
        evidence_revision=f"evidence-{reason}",
        next_reassessment_at="2026-08-06T05:00:00+00:00",
        permitted_actions=(
            (PermittedAction.RESOLVE_OPERATOR_ACTION,)
            if action_required
            else (PermittedAction.CLAIM_IMPLEMENTATION,)
        ),
        action_required=action_required,
        alert_level=(
            AlertSeverity.WARNING if action_required else AlertSeverity.NONE
        ),
    )


def test_shadow_cannot_overwrite_authoritative_controller_snapshot() -> None:
    orchestrator = _orchestrator(mode="enforce")
    controller = _decision("TASK-1", action_required=True)
    shadow = _decision("TASK-1", reason="implementation.recovery_scheduled")

    assert orchestrator._cache_work_decisions(
        [controller],
        4,
        source="controller",
        live_keys={("project-a", "TASK-1")},
        publication_epoch=orchestrator._work_decision_publication_epoch,
    )
    assert not orchestrator._cache_work_decisions(
        [shadow],
        99,
        source="shadow",
        live_keys={("project-a", "TASK-1")},
        publication_epoch=orchestrator._work_decision_publication_epoch,
    )

    projection = orchestrator.work_decision_projection("project-a", "TASK-1")
    assert projection is not None
    assert projection["reason_code"] == controller.reason_code
    assert projection["action_required"] is True


def test_same_or_older_controller_generation_cannot_win_a_race() -> None:
    orchestrator = _orchestrator()
    newest = _decision("TASK-1", reason="dispatch.eligible")
    stale = _decision("TASK-1", reason="implementation.recovery_scheduled")
    live = {("project-a", "TASK-1")}

    assert orchestrator._cache_work_decisions(
        [newest],
        8,
        source="controller",
        live_keys=live,
        publication_epoch=orchestrator._work_decision_publication_epoch,
    )
    assert not orchestrator._cache_work_decisions(
        [stale],
        8,
        source="controller",
        live_keys=live,
        publication_epoch=orchestrator._work_decision_publication_epoch,
    )
    assert not orchestrator._cache_work_decisions(
        [stale],
        7,
        source="controller",
        live_keys=live,
        publication_epoch=orchestrator._work_decision_publication_epoch,
    )

    projection = orchestrator.work_decision_projection("project-a", "TASK-1")
    assert projection is not None
    assert projection["reason_code"] == "dispatch.eligible"


def test_truncated_publication_prunes_terminal_keys_outside_scan_window() -> None:
    orchestrator = _orchestrator()
    initial = [_decision(f"TASK-{index:03d}") for index in range(105)]
    all_live = {("project-a", decision.task_id) for decision in initial}
    assert orchestrator._cache_work_decisions(
        initial,
        1,
        source="controller",
        live_keys=all_live,
        publication_epoch=orchestrator._work_decision_publication_epoch,
    )

    # The next bounded controller result contains only the first 100 tasks.
    # TASK-104 has become terminal and is absent from the independently
    # collected full live set. TASK-100..103 remain live, but their retained
    # internal rows must not be published as current decisions until a later
    # rotating window evaluates them.
    still_live = all_live - {("project-a", "TASK-104")}
    assert orchestrator._cache_work_decisions(
        initial[:100],
        2,
        source="controller",
        live_keys=still_live,
        publication_epoch=orchestrator._work_decision_publication_epoch,
        scan_complete=False,
    )

    assert orchestrator.work_decision_projection("project-a", "TASK-104") is None
    assert orchestrator.work_decision_projection("project-a", "TASK-103") is None
    assert len(orchestrator.work_decision_projections()) == 100
    assert orchestrator.work_decision_availability(
        "project-a", "TASK-103"
    ) == "incomplete"
    projection, _alerts = orchestrator.work_decision_snapshot()
    assert projection["availability"] == "incomplete"
    assert projection["complete"] is False
    assert projection["incomplete_projects"] == ["project-a"]
    assert projection["incomplete_tasks"] == [
        {"project_id": "project-a", "task_id": f"TASK-{index:03d}"}
        for index in range(100, 104)
    ]


def test_cache_miss_reads_are_immutable_and_do_not_run_policy() -> None:
    orchestrator = _orchestrator()
    orchestrator.workflow_controller = Mock()
    orchestrator.workflow_shadow = Mock()

    assert orchestrator.work_decision_projection(
        "project-a", "TASK-MISSING", task=Mock()
    ) is None
    assert orchestrator.work_decision_projection(
        "project-a", "TASK-MISSING", task=Mock()
    ) is None
    orchestrator.workflow_controller.evaluate.assert_not_called()
    orchestrator.workflow_shadow.diagnostic.assert_not_called()
    assert orchestrator._work_decision_generation == 0
    assert orchestrator._work_decision_updated_at is None


def test_alert_snapshot_transitions_and_clears_with_decision_revision() -> None:
    orchestrator = _orchestrator()
    blocked = _decision("TASK-1", action_required=True)
    recovered = _decision("TASK-1", reason="dispatch.eligible")
    live = {("project-a", "TASK-1")}

    orchestrator._cache_work_decisions(
        [blocked],
        1,
        source="controller",
        live_keys=live,
        publication_epoch=orchestrator._work_decision_publication_epoch,
    )
    blocked_projection, blocked_alerts = orchestrator.work_decision_snapshot()
    assert blocked_projection["publication_epoch"] == 1
    assert blocked_projection["items"][0]["action_required"] is True
    assert blocked_alerts[0]["task_id"] == "TASK-1"

    orchestrator._cache_work_decisions(
        [recovered],
        2,
        source="controller",
        live_keys=live,
        publication_epoch=orchestrator._work_decision_publication_epoch,
    )
    recovered_projection, recovered_alerts = orchestrator.work_decision_snapshot()
    assert recovered_projection["items"][0]["action_required"] is False
    assert recovered_alerts == []


def test_controller_decision_only_change_uses_full_issue_observer() -> None:
    orchestrator = _orchestrator()
    issue = Issue(
        id="id-1",
        identifier="TASK-1",
        title="Task",
        state="Open",
        project_id="project-a",
    )
    orchestrator.project_store = Mock()
    orchestrator.project_store.list_all.return_value = []
    orchestrator.tracker = Mock()
    orchestrator.tracker.fetch_all_issues.return_value = [issue]
    orchestrator.workflow_controller = Mock()
    orchestrator.workflow_controller.full_sync.side_effect = (
        SimpleNamespace(
            decisions=(_decision("TASK-1", reason="dispatch.eligible"),),
            snapshot_generation=1,
            action_required=(),
            reconciliation=SimpleNamespace(
                jobs_created=0, jobs_replayed=0, jobs_superseded=0
            ),
            truncated=False,
        ),
        SimpleNamespace(
            decisions=(_decision("TASK-1", reason="dispatch.eligible"),),
            snapshot_generation=2,
            action_required=(),
            reconciliation=SimpleNamespace(
                jobs_created=0, jobs_replayed=0, jobs_superseded=0
            ),
            truncated=False,
        ),
    )
    orchestrator._notify_observers = Mock()

    orchestrator._run_workflow_controller_sweep()
    orchestrator._run_workflow_controller_sweep()

    # The first projection becomes part of issue/detail payloads. Merely
    # advancing controller generation with identical decision content does
    # not create a redundant refresh.
    orchestrator._notify_observers.assert_called_once_with()


def test_controller_reconciliation_truncation_fails_task_projection_closed() -> None:
    orchestrator = _orchestrator()
    issue = Issue(
        id="id-1",
        identifier="TASK-1",
        title="Task",
        state="Open",
        project_id="project-a",
    )
    orchestrator.project_store = Mock()
    orchestrator.project_store.list_all.return_value = []
    orchestrator.tracker = Mock()
    orchestrator.tracker.fetch_all_issues.return_value = [issue]
    orchestrator.workflow_controller = Mock(decision_limit=100)
    orchestrator.workflow_controller.full_sync.return_value = SimpleNamespace(
        decisions=(_decision("TASK-1"),),
        snapshot_generation=1,
        action_required=(),
        reconciliation=SimpleNamespace(
            jobs_created=0,
            jobs_replayed=0,
            jobs_superseded=0,
            truncated=True,
        ),
        truncated=True,
    )
    orchestrator._notify_observers = Mock()

    result = orchestrator._run_workflow_controller_sweep()

    assert result["truncated"] is True
    assert orchestrator.work_decision_projection("project-a", "TASK-1") is None
    assert orchestrator.work_decision_availability(
        "project-a", "TASK-1"
    ) == "incomplete"
    snapshot, _alerts = orchestrator.work_decision_snapshot()
    assert snapshot["availability"] == "incomplete"
    assert snapshot["complete"] is False
    assert "reconciliation reached" in snapshot["incomplete_reason"]


def test_mode_aba_rejects_publication_from_original_configuration_epoch(
    tmp_path,
) -> None:
    config = orchestrator_module.ServiceConfig(
        workspace_root=str(tmp_path / "workspace-original")
    )
    config.workflow_engine_mode = "enforce"
    orchestrator = Orchestrator(
        config,
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(tmp_path / "service_state.json"),
    )
    issue = Issue(
        id="id-1",
        identifier="TASK-1",
        title="Task",
        state="Open",
        project_id="project-a",
    )
    orchestrator.project_store = Mock()
    orchestrator.project_store.list_all.return_value = []
    orchestrator.tracker = Mock()
    orchestrator.tracker.fetch_all_issues.return_value = [issue]
    stale_controller = Mock()
    orchestrator.workflow_controller = stale_controller
    orchestrator._notify_observers = Mock()
    orchestrator._set_refresh_requested = Mock()
    orchestrator._post_event = Mock()

    # Deterministically model enforce -> shadow -> enforce while an original
    # controller sweep is still evaluating. The source string is controller at
    # both ends and its generation is otherwise publishable; only the monotonic
    # configuration epoch distinguishes the stale sweep.
    def complete_after_aba(_candidates, *, facts):
        del facts
        shadow = orchestrator_module.ServiceConfig(
            workspace_root=str(tmp_path / "workspace-shadow")
        )
        shadow.workflow_engine_mode = "shadow"
        orchestrator.reload_config(shadow, "shadow prompt")
        enforce = orchestrator_module.ServiceConfig(
            workspace_root=str(tmp_path / "workspace-enforce")
        )
        enforce.workflow_engine_mode = "enforce"
        orchestrator.reload_config(enforce, "enforce prompt")
        return SimpleNamespace(
            decisions=(_decision("TASK-1"),),
            snapshot_generation=1,
            action_required=(),
            reconciliation=SimpleNamespace(
                jobs_created=0,
                jobs_replayed=0,
                jobs_superseded=0,
            ),
            truncated=False,
        )

    stale_controller.full_sync.side_effect = complete_after_aba

    orchestrator._run_workflow_controller_sweep()

    assert orchestrator.work_decision_projection("project-a", "TASK-1") is None
    assert orchestrator.config.workflow_engine_mode == "enforce"
    assert orchestrator._work_decision_publication_epoch == 3
    persisted = json.loads((tmp_path / "service_state.json").read_text())
    assert persisted["work_decision_availability"]["publication_epoch"] == 3
    assert persisted["work_decision_availability"]["source"] is None


def test_controller_sweep_retains_cached_decisions_for_failed_projects() -> None:
    orchestrator = _orchestrator(mode="enforce")
    project_a = SimpleNamespace(id="project-a")
    project_b = SimpleNamespace(id="project-b")
    tracker_a = Mock()
    tracker_b = Mock()
    issue_a = Issue(
        id="id-a",
        identifier="TASK-1",
        title="A",
        state="Open",
        project_id="project-a",
    )
    tracker_a.fetch_all_issues.return_value = [issue_a]
    tracker_b.fetch_all_issues.side_effect = RuntimeError("tracker unavailable")
    orchestrator.project_store = Mock()
    orchestrator.project_store.list_all.return_value = [project_a, project_b]
    orchestrator._tracker_for_project = Mock(
        side_effect=lambda project_id: (
            tracker_a if project_id == "project-a" else tracker_b
        )
    )
    orchestrator.workflow_controller = Mock()
    orchestrator.workflow_controller.full_sync.return_value = SimpleNamespace(
        decisions=(
            _decision(
                "TASK-1",
                project_id="project-a",
                reason="dispatch.eligible",
            ),
        ),
        snapshot_generation=2,
        action_required=(),
        reconciliation=SimpleNamespace(
            jobs_created=0,
            jobs_replayed=0,
            jobs_superseded=0,
        ),
        truncated=False,
    )
    orchestrator._notify_observers = Mock()
    orchestrator._cache_work_decisions(
        [
            _decision("TASK-1", project_id="project-a"),
            _decision(
                "TASK-1",
                project_id="project-b",
                reason="implementation.recovery_scheduled",
            ),
        ],
        1,
        source="controller",
        live_keys={("project-a", "TASK-1"), ("project-b", "TASK-1")},
        publication_epoch=orchestrator._work_decision_publication_epoch,
    )

    orchestrator._run_workflow_controller_sweep()

    # The row remains internal so a later successful project read can update it,
    # but an unavailable project can never expose that stale row as current.
    retained = orchestrator._work_decisions[("project-b", "TASK-1")]
    assert retained.reason_code == "implementation.recovery_scheduled"
    assert orchestrator.work_decision_projection("project-b", "TASK-1") is None
    snapshot, _alerts = orchestrator.work_decision_snapshot()
    assert snapshot["availability"] == "partial"
    assert snapshot["complete"] is False
    assert snapshot["unavailable_projects"] == ["project-b"]
    assert [item["project_id"] for item in snapshot["items"]] == ["project-a"]


def test_failed_project_unavailability_survives_cold_restart(tmp_path) -> None:
    state_path = str(tmp_path / "service_state.json")
    first_config = orchestrator_module.ServiceConfig(
        workspace_root=str(tmp_path / "workspace-a")
    )
    first_config.workflow_engine_mode = "enforce"
    first = Orchestrator(
        first_config,
        str(tmp_path / "WORKFLOW.md"),
        state_path=state_path,
    )
    first._cache_work_decisions(
        [],
        1,
        source="controller",
        live_keys=set(),
        failed_projects={"project-b"},
        publication_epoch=first._work_decision_publication_epoch,
    )

    second_config = orchestrator_module.ServiceConfig(
        workspace_root=str(tmp_path / "workspace-b")
    )
    second_config.workflow_engine_mode = "enforce"
    second = Orchestrator(
        second_config,
        str(tmp_path / "WORKFLOW.md"),
        state_path=state_path,
    )

    snapshot, alerts = second.work_decision_snapshot()
    assert snapshot["items"] == []
    assert snapshot["availability"] == "unavailable"
    assert snapshot["complete"] is False
    assert snapshot["unavailable_projects"] == ["project-b"]
    assert second.work_decision_availability("project-b") == "unavailable"
    assert alerts == []

    second._cache_work_decisions(
        [],
        1,
        source="controller",
        live_keys=set(),
        publication_epoch=second._work_decision_publication_epoch,
    )
    recovered, _alerts = second.work_decision_snapshot()
    assert recovered["availability"] == "ready"
    assert recovered["complete"] is True
    assert recovered["unavailable_projects"] == []


def test_bounded_scan_incompleteness_survives_cold_restart(tmp_path) -> None:
    state_path = str(tmp_path / "service_state.json")
    first_config = orchestrator_module.ServiceConfig(
        workspace_root=str(tmp_path / "workspace-first")
    )
    first_config.workflow_engine_mode = "enforce"
    first = Orchestrator(
        first_config,
        str(tmp_path / "WORKFLOW.md"),
        state_path=state_path,
    )
    first._cache_work_decisions(
        [_decision("TASK-1")],
        1,
        source="controller",
        live_keys={("project-a", "TASK-1"), ("project-a", "TASK-2")},
        publication_epoch=first._work_decision_publication_epoch,
        scan_complete=False,
    )

    restarted_config = orchestrator_module.ServiceConfig(
        workspace_root=str(tmp_path / "workspace-restarted")
    )
    restarted_config.workflow_engine_mode = "enforce"
    restarted = Orchestrator(
        restarted_config,
        str(tmp_path / "WORKFLOW.md"),
        state_path=state_path,
    )

    snapshot, alerts = restarted.work_decision_snapshot()
    assert snapshot["availability"] == "incomplete"
    assert snapshot["complete"] is False
    assert snapshot["items"] == []
    assert snapshot["incomplete_tasks"] == [
        {"project_id": "project-a", "task_id": "TASK-2"}
    ]
    assert restarted.work_decision_availability(
        "project-a", "TASK-2"
    ) == "incomplete"
    assert alerts == []


def test_public_reload_atomically_clears_and_wakes_decision_projection(
    tmp_path,
) -> None:
    config = orchestrator_module.ServiceConfig(
        workspace_root=str(tmp_path / "workspace-a")
    )
    config.workflow_engine_mode = "enforce"
    orchestrator = Orchestrator(
        config,
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(tmp_path / "service_state.json"),
    )
    orchestrator._cache_work_decisions(
        [_decision("TASK-1")],
        1,
        source="controller",
        live_keys={("project-a", "TASK-1")},
        publication_epoch=orchestrator._work_decision_publication_epoch,
    )
    previous_epoch = orchestrator._work_decision_publication_epoch
    previous_tracker = orchestrator.tracker
    orchestrator._reviews_cache = {
        "project-a": [SimpleNamespace(source_branch="old-review")]
    }
    orchestrator._unmerged_review_branches = {"old-review"}
    orchestrator._merged_branches = {"old-merged"}
    orchestrator._merged_branches_dirty = False
    orchestrator._set_stale_cache("project-a", "reviews", ["old-review"])
    orchestrator._notify_observers = Mock()
    orchestrator._set_refresh_requested = Mock()
    orchestrator._post_event = Mock()
    orchestrator.agent_profile_store._load = Mock()
    orchestrator.agent_profile_store.list_all = Mock(return_value=[])

    replacement = orchestrator_module.ServiceConfig(
        workspace_root=str(tmp_path / "workspace-b")
    )
    replacement.workflow_engine_mode = "shadow"
    orchestrator.reload_config(replacement, "replacement prompt")

    snapshot, _alerts = orchestrator.work_decision_snapshot()
    assert orchestrator.config is replacement
    assert orchestrator.tracker is not previous_tracker
    assert orchestrator.workflow_shadow.mode == "shadow"
    assert snapshot["publication_epoch"] == previous_epoch + 1
    assert snapshot["source"] is None
    assert snapshot["items"] == []
    assert snapshot["availability"] == "pending"
    assert orchestrator._reviews_cache == {}
    assert orchestrator._unmerged_review_branches == set()
    assert orchestrator._merged_branches == set()
    assert orchestrator._merged_branches_dirty is True
    assert orchestrator._stale_caches == {}
    orchestrator._notify_observers.assert_called_once_with()
    orchestrator._set_refresh_requested.assert_called_once_with()
    event = orchestrator._post_event.call_args.args[0]
    assert event.event_type == orchestrator_module.DispatchEventType.REFRESH_REQUESTED


def test_failed_decision_publication_preserves_exact_prior_public_and_durable_cut(
    tmp_path,
) -> None:
    state_path = tmp_path / "service_state.json"
    config = orchestrator_module.ServiceConfig(
        workspace_root=str(tmp_path / "workspace")
    )
    config.workflow_engine_mode = "enforce"
    orchestrator = Orchestrator(
        config,
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(state_path),
    )
    old_decision = _decision("TASK-1", reason="dispatch.eligible")
    assert orchestrator._cache_work_decisions(
        [old_decision],
        1,
        source="controller",
        live_keys={("project-a", "TASK-1")},
        publication_epoch=orchestrator._work_decision_publication_epoch,
    )
    previous_snapshot = orchestrator.work_decision_snapshot()
    previous_generation = orchestrator._work_decision_generation
    previous_durable_state = state_path.read_bytes()
    orchestrator._save_state = Mock(return_value=False)

    published = orchestrator._cache_work_decisions(
        [_decision("TASK-1", reason="implementation.recovery_scheduled")],
        2,
        source="controller",
        live_keys={("project-a", "TASK-1")},
        publication_epoch=orchestrator._work_decision_publication_epoch,
    )

    assert published is False
    assert orchestrator.work_decision_snapshot() == previous_snapshot
    assert orchestrator._work_decision_generation == previous_generation
    assert state_path.read_bytes() == previous_durable_state


def test_failed_reload_persistence_keeps_prior_runtime_and_sends_no_notifications(
    tmp_path,
) -> None:
    state_path = tmp_path / "service_state.json"
    config = orchestrator_module.ServiceConfig(
        workspace_root=str(tmp_path / "workspace-a")
    )
    config.workflow_engine_mode = "enforce"
    orchestrator = Orchestrator(
        config,
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(state_path),
    )
    orchestrator._cache_work_decisions(
        [_decision("TASK-1")],
        1,
        source="controller",
        live_keys={("project-a", "TASK-1")},
        publication_epoch=orchestrator._work_decision_publication_epoch,
    )
    previous_snapshot = orchestrator.work_decision_snapshot()
    previous_tracker = orchestrator.tracker
    previous_controller = orchestrator.workflow_controller
    previous_epoch = orchestrator._work_decision_publication_epoch
    previous_durable_state = state_path.read_bytes()
    orchestrator._notify_observers = Mock()
    orchestrator._set_refresh_requested = Mock()
    orchestrator._post_event = Mock()
    orchestrator.agent_profile_store._load = Mock()
    orchestrator.agent_profile_store.list_all = Mock(return_value=[])
    orchestrator._save_state = Mock(return_value=False)
    replacement = orchestrator_module.ServiceConfig(
        workspace_root=str(tmp_path / "workspace-b")
    )
    replacement.workflow_engine_mode = "shadow"

    with pytest.raises(RuntimeError, match="availability could not be persisted"):
        orchestrator.reload_config(replacement, "replacement prompt")

    assert orchestrator.config is config
    assert orchestrator.tracker is previous_tracker
    assert orchestrator.workflow_controller is previous_controller
    assert orchestrator._work_decision_publication_epoch == previous_epoch
    assert orchestrator.work_decision_snapshot() == previous_snapshot
    assert state_path.read_bytes() == previous_durable_state
    orchestrator._notify_observers.assert_not_called()
    orchestrator._set_refresh_requested.assert_not_called()
    orchestrator._post_event.assert_not_called()


def test_failed_reload_liveness_save_restores_pending_epoch_and_runtime_authority(
    tmp_path,
) -> None:
    state_path = tmp_path / "service_state.json"
    config = orchestrator_module.ServiceConfig(
        workspace_root=str(tmp_path / "workspace-a")
    )
    config.workflow_engine_mode = "enforce"
    orchestrator = Orchestrator(
        config,
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(state_path),
    )
    assert orchestrator._cache_work_decisions(
        [_decision("TASK-1")],
        1,
        source="controller",
        live_keys={("project-a", "TASK-1")},
        publication_epoch=orchestrator._work_decision_publication_epoch,
    )
    orchestrator._persist_workflow_liveness_state(
        orchestrator.workflow_controller.liveness_state()
    )
    previous_snapshot = orchestrator.work_decision_snapshot()
    previous_epoch = orchestrator._work_decision_publication_epoch
    previous_tracker = orchestrator.tracker
    previous_workspace_mgr = orchestrator.workspace_mgr
    previous_prompt = orchestrator._prompt_template
    previous_liveness = orchestrator.workflow_controller.liveness_state()
    previous_policy = orchestrator.workflow_controller.liveness_policy
    previous_store = orchestrator.workflow_job_store.health_snapshot()
    previous_durable = json.loads(state_path.read_text(encoding="utf-8"))
    orchestrator._notify_observers = Mock()
    orchestrator._set_refresh_requested = Mock()
    orchestrator._post_event = Mock()
    orchestrator.agent_profile_store._load = Mock()
    orchestrator.agent_profile_store.list_all = Mock(return_value=[])
    orchestrator._persist_workflow_liveness_state = Mock(
        side_effect=OSError("injected liveness persistence failure")
    )
    replacement = orchestrator_module.ServiceConfig(
        workspace_root=str(tmp_path / "workspace-b")
    )
    replacement.workflow_engine_mode = "shadow"
    replacement.workflow_liveness_max_task_records = (
        config.workflow_liveness_max_task_records + 1
    )
    replacement.workflow_liveness_slo_seconds = dict(
        config.workflow_liveness_slo_seconds
    )
    replacement.workflow_liveness_slo_seconds["dispatch_latency"] += 1

    with pytest.raises(OSError, match="injected liveness persistence failure"):
        orchestrator.reload_config(replacement, "replacement prompt")

    assert orchestrator.config is config
    assert orchestrator.tracker is previous_tracker
    assert orchestrator.workspace_mgr is previous_workspace_mgr
    assert orchestrator._prompt_template == previous_prompt
    assert orchestrator.workflow_shadow.mode == "enforce"
    assert orchestrator._work_decision_publication_epoch == previous_epoch
    assert orchestrator.work_decision_snapshot() == previous_snapshot
    assert orchestrator.workflow_controller.liveness_policy is previous_policy
    assert orchestrator.workflow_controller.liveness_state() == previous_liveness
    assert orchestrator.workflow_job_store.health_snapshot() == previous_store
    restored = json.loads(state_path.read_text(encoding="utf-8"))
    assert restored["work_decision_availability"] == previous_durable[
        "work_decision_availability"
    ]
    assert restored["workflow_liveness"] == previous_durable[
        "workflow_liveness"
    ]
    orchestrator._notify_observers.assert_not_called()
    orchestrator._set_refresh_requested.assert_not_called()
    orchestrator._post_event.assert_not_called()


def test_real_shadow_publication_failure_rolls_back_registry_cursor_and_notifications(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_path = tmp_path / "service_state.json"
    config = orchestrator_module.ServiceConfig(
        workspace_root=str(tmp_path / "workspace")
    )
    config.workflow_engine_mode = "shadow"
    orchestrator = Orchestrator(
        config,
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(state_path),
    )
    issue = Issue(
        id="done-id",
        identifier="TASK-DONE",
        title="Done",
        state="Done",
        project_id="project-a",
        parent_id="EPIC-1",
        target_branch="epic-parent",
    )
    tracker = Mock()
    tracker.fetch_all_issues.return_value = [issue]
    orchestrator.project_store = Mock()
    orchestrator.project_store.list_all.return_value = [SimpleNamespace(id="project-a")]
    orchestrator._tracker_for_project = Mock(return_value=tracker)
    orchestrator._workflow_shadow_sources = Mock(return_value={})
    orchestrator._legacy_workflow_projections = Mock(return_value=())
    orchestrator._notify_observers = Mock()
    orchestrator._notify_state_only = Mock()

    class _Collector:
        def __init__(self, **_kwargs):
            pass

        def collect(self, _identifier):
            return _done_facts(issue)

    monkeypatch.setattr(orchestrator_module, "WorkflowFactCollector", _Collector)
    previous_summary = orchestrator.workflow_shadow.summary()
    previous_snapshot = orchestrator.work_decision_snapshot()
    previous_state = state_path.read_bytes() if state_path.exists() else None
    orchestrator._save_state = Mock(return_value=False)

    result = orchestrator._run_workflow_shadow_sweep()

    assert result["publication_accepted"] is False
    assert result["publication_rejection"] == "persistence_failed"
    assert orchestrator.workflow_shadow.summary() == previous_summary
    assert orchestrator.workflow_shadow.diagnostic("project-a", "TASK-DONE") is None
    assert orchestrator._workflow_shadow_generation == 0
    assert orchestrator._workflow_shadow_scan_cursor == 0
    assert orchestrator.work_decision_snapshot() == previous_snapshot
    assert (state_path.read_bytes() if state_path.exists() else None) == previous_state
    orchestrator._notify_observers.assert_not_called()
    orchestrator._notify_state_only.assert_not_called()


def test_real_controller_publication_failure_rolls_back_jobs_metrics_and_generation(
    tmp_path,
) -> None:
    state_path = tmp_path / "service_state.json"
    config = orchestrator_module.ServiceConfig(
        workspace_root=str(tmp_path / "workspace")
    )
    config.workflow_engine_mode = "enforce"
    orchestrator = Orchestrator(
        config,
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(state_path),
    )
    issue = Issue(
        id="done-id",
        identifier="TASK-DONE",
        title="Done",
        state="Done",
        project_id="project-a",
        parent_id="EPIC-1",
        target_branch="epic-parent",
    )
    tracker = Mock()
    tracker.fetch_all_issues.return_value = [issue]
    orchestrator.project_store = Mock()
    orchestrator.project_store.list_all.return_value = [SimpleNamespace(id="project-a")]
    orchestrator._tracker_for_project = Mock(return_value=tracker)
    orchestrator._collect_universal_workflow_facts = Mock(
        return_value=_done_facts(issue)
    )
    orchestrator._notify_observers = Mock()
    orchestrator._notify_state_only = Mock()
    controller = orchestrator.workflow_controller
    previous_controller = controller.health_snapshot()
    previous_store = orchestrator.workflow_job_store.health_snapshot()
    previous_snapshot = orchestrator.work_decision_snapshot()
    previous_state = state_path.read_bytes() if state_path.exists() else None
    orchestrator._save_state = Mock(return_value=False)

    result = orchestrator._run_workflow_controller_sweep()

    assert result["publication_accepted"] is False
    assert result["publication_rejection"] == "persistence_failed"
    current_controller = controller.health_snapshot()
    assert current_controller["controller"] == previous_controller["controller"]
    assert current_controller["liveness"] == previous_controller["liveness"]
    current_store = orchestrator.workflow_job_store.health_snapshot()
    assert current_store["captured_snapshot_generation"] == (
        previous_store["captured_snapshot_generation"] + 1
    )
    assert {
        key: value
        for key, value in current_store.items()
        if key != "captured_snapshot_generation"
    } == {
        key: value
        for key, value in previous_store.items()
        if key != "captured_snapshot_generation"
    }
    assert orchestrator.work_decision_snapshot() == previous_snapshot
    assert (state_path.read_bytes() if state_path.exists() else None) == previous_state
    orchestrator._notify_observers.assert_not_called()
    orchestrator._notify_state_only.assert_not_called()


def test_rejected_controller_pass_never_publishes_or_prunes_cached_decisions(
    tmp_path,
) -> None:
    config = orchestrator_module.ServiceConfig(
        workspace_root=str(tmp_path / "workspace")
    )
    config.workflow_engine_mode = "enforce"
    orchestrator = Orchestrator(
        config,
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(tmp_path / "service_state.json"),
    )
    tracker = Mock()
    tracker.fetch_all_issues.return_value = [
        Issue(
            id="task-1",
            identifier="TASK-1",
            title="Task 1",
            state="Open",
            project_id="project-a",
        )
    ]
    orchestrator.project_store = Mock()
    orchestrator.project_store.list_all.return_value = [
        SimpleNamespace(id="project-a")
    ]
    orchestrator._tracker_for_project = Mock(return_value=tracker)
    assert orchestrator._cache_work_decisions(
        [_decision("TASK-1"), _decision("TASK-2")],
        1,
        source="controller",
        live_keys={
            ("project-a", "TASK-1"),
            ("project-a", "TASK-2"),
        },
        publication_epoch=orchestrator._work_decision_publication_epoch,
    )
    before = orchestrator.work_decision_snapshot()
    rejected_controller = Mock()
    rejected_controller.begin_scan.return_value = 2
    rejected_controller.full_sync.return_value = SimpleNamespace(
        accepted=False,
        decisions=(
            _decision(
                "TASK-1",
                reason="implementation.recovery_scheduled",
            ),
        ),
        snapshot_generation=2,
        action_required=(),
        reconciliation=SimpleNamespace(
            snapshot_accepted=False,
            jobs_created=1,
            jobs_replayed=0,
            jobs_superseded=1,
            truncated=False,
        ),
        truncated=False,
    )
    orchestrator.workflow_controller = rejected_controller
    orchestrator._notify_observers = Mock()
    orchestrator._notify_state_only = Mock()

    result = orchestrator._run_workflow_controller_sweep()

    assert result["accepted"] is False
    assert result["publication_accepted"] is False
    assert result["publication_rejection"] == "stale_generation"
    assert orchestrator.work_decision_snapshot() == before
    assert set(orchestrator._work_decisions) == {
        ("project-a", "TASK-1"),
        ("project-a", "TASK-2"),
    }
    orchestrator._notify_observers.assert_not_called()
    orchestrator._notify_state_only.assert_not_called()


def test_commit_and_state_restore_failure_is_reported_without_publication() -> None:
    orchestrator = _orchestrator(mode="enforce")
    orchestrator._state_io_lock = threading.RLock()
    orchestrator._save_state = Mock(
        side_effect=[True, OSError("state restoration failed")]
    )

    class _FailedProducer:
        def commit(self):
            raise WorkflowJobPublicationError(
                "commit and rollback failed", rollback_failed=True
            )

    result = orchestrator._publish_work_decisions(
        [_decision("TASK-1")],
        1,
        source="controller",
        live_keys={("project-a", "TASK-1")},
        publication_epoch=orchestrator._work_decision_publication_epoch,
        producer_transaction=_FailedProducer(),
    )

    assert result.accepted is False
    assert result.rejection == "durable_commit_and_store_rollback_failed"
    assert orchestrator.work_decision_projection("project-a", "TASK-1") is None
    assert orchestrator._work_decision_generation == 0


def test_staged_projection_rollback_restores_memory_when_state_restore_fails() -> None:
    orchestrator = _orchestrator(mode="enforce")
    assert orchestrator._cache_work_decisions(
        [_decision("TASK-1")],
        1,
        source="controller",
        live_keys={("project-a", "TASK-1")},
        publication_epoch=orchestrator._work_decision_publication_epoch,
    )
    previous_snapshot = orchestrator.work_decision_snapshot()
    orchestrator._state_io_lock = threading.RLock()
    orchestrator._save_state = Mock(side_effect=[True, False])
    publication = orchestrator._publish_work_decisions(
        [_decision("TASK-1", reason="implementation.recovery_scheduled")],
        2,
        source="controller",
        live_keys={("project-a", "TASK-1")},
        publication_epoch=orchestrator._work_decision_publication_epoch,
        defer_memory=True,
    )
    publication.commit_memory()
    assert orchestrator._work_decision_generation == 2

    with pytest.raises(OSError, match="availability was not restored"):
        publication.rollback()

    assert orchestrator.work_decision_snapshot() == previous_snapshot
    assert orchestrator._work_decision_generation == 1


def test_real_shadow_aba_rolls_back_old_registry_without_extra_notification(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = orchestrator_module.ServiceConfig(
        workspace_root=str(tmp_path / "workspace-a")
    )
    config.workflow_engine_mode = "shadow"
    orchestrator = Orchestrator(
        config,
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(tmp_path / "service_state.json"),
    )
    issue = Issue(
        id="done-id",
        identifier="TASK-DONE",
        title="Done",
        state="Done",
        project_id="project-a",
        parent_id="EPIC-1",
        target_branch="epic-parent",
    )
    tracker = Mock()
    tracker.fetch_all_issues.return_value = [issue]
    orchestrator.project_store = Mock()
    orchestrator.project_store.list_all.return_value = [SimpleNamespace(id="project-a")]
    orchestrator._tracker_for_project = Mock(return_value=tracker)
    orchestrator._workflow_shadow_sources = Mock(return_value={})
    orchestrator._legacy_workflow_projections = Mock(return_value=())
    orchestrator._notify_observers = Mock()
    orchestrator._notify_state_only = Mock()
    orchestrator._set_refresh_requested = Mock()
    orchestrator._post_event = Mock()
    orchestrator.agent_profile_store._load = Mock()
    orchestrator.agent_profile_store.list_all = Mock(return_value=[])
    original_shadow = orchestrator.workflow_shadow
    original_evaluator = original_shadow._evaluator
    reloaded = False

    def evaluator(task, facts, *, now=None):
        nonlocal reloaded
        if not reloaded:
            reloaded = True
            replacement = orchestrator_module.ServiceConfig(
                workspace_root=str(tmp_path / "workspace-b")
            )
            replacement.workflow_engine_mode = "shadow"
            orchestrator.reload_config(replacement, "replacement prompt")
        return original_evaluator(task, facts, now=now)

    original_shadow._evaluator = evaluator

    class _Collector:
        def __init__(self, **_kwargs):
            pass

        def collect(self, _identifier):
            return _done_facts(issue)

    monkeypatch.setattr(orchestrator_module, "WorkflowFactCollector", _Collector)
    previous_summary = original_shadow.summary()

    result = orchestrator._run_workflow_shadow_sweep()

    assert result["publication_accepted"] is False
    assert result["publication_rejection"] == "stale_epoch"
    assert original_shadow.summary() == previous_summary
    assert original_shadow.diagnostic("project-a", "TASK-DONE") is None
    assert orchestrator._workflow_shadow_generation == 0
    assert orchestrator._workflow_shadow_scan_cursor == 0
    assert orchestrator.work_decision_snapshot()[0]["availability"] == "pending"
    orchestrator._notify_observers.assert_called_once_with()
    orchestrator._notify_state_only.assert_not_called()


def test_real_controller_aba_rolls_back_old_scheduler_and_durable_store(
    tmp_path,
) -> None:
    config = orchestrator_module.ServiceConfig(
        workspace_root=str(tmp_path / "workspace-a")
    )
    config.workflow_engine_mode = "enforce"
    orchestrator = Orchestrator(
        config,
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(tmp_path / "service_state.json"),
    )
    issue = Issue(
        id="done-id",
        identifier="TASK-DONE",
        title="Done",
        state="Done",
        project_id="project-a",
        parent_id="EPIC-1",
        target_branch="epic-parent",
    )
    tracker = Mock()
    tracker.fetch_all_issues.return_value = [issue]
    orchestrator.project_store = Mock()
    orchestrator.project_store.list_all.return_value = [SimpleNamespace(id="project-a")]
    orchestrator._tracker_for_project = Mock(return_value=tracker)
    orchestrator._notify_observers = Mock()
    orchestrator._notify_state_only = Mock()
    orchestrator._set_refresh_requested = Mock()
    orchestrator._post_event = Mock()
    orchestrator.agent_profile_store._load = Mock()
    orchestrator.agent_profile_store.list_all = Mock(return_value=[])
    original_controller = orchestrator.workflow_controller
    previous_controller = original_controller.health_snapshot()
    previous_store = orchestrator.workflow_job_store.health_snapshot()
    reloaded = False

    def facts_provider(_issue):
        nonlocal reloaded
        if not reloaded:
            reloaded = True
            replacement = orchestrator_module.ServiceConfig(
                workspace_root=str(tmp_path / "workspace-b")
            )
            replacement.workflow_engine_mode = "enforce"
            orchestrator.reload_config(replacement, "replacement prompt")
        return _done_facts(issue)

    orchestrator._collect_universal_workflow_facts = facts_provider

    result = orchestrator._run_workflow_controller_sweep()

    assert result["publication_accepted"] is False
    assert result["publication_rejection"] == "stale_epoch"
    current_controller = original_controller.health_snapshot()
    assert current_controller["controller"] == previous_controller["controller"]
    current_store = orchestrator.workflow_job_store.health_snapshot()
    assert current_store["captured_snapshot_generation"] == 2
    assert current_store["accepted_snapshot_generation"] == 1
    assert current_store["published_snapshot_generation"] == 0
    assert current_store["states"] == previous_store["states"]
    assert current_store["snapshot_membership_count"] == 0
    assert orchestrator.work_decision_snapshot()[0]["availability"] == "pending"
    orchestrator._notify_observers.assert_called_once_with()
    orchestrator._notify_state_only.assert_not_called()


def test_shadow_sweep_and_reload_have_no_cross_thread_lock_inversion(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = orchestrator_module.ServiceConfig(
        workspace_root=str(tmp_path / "workspace-a")
    )
    config.workflow_engine_mode = "shadow"
    orchestrator = Orchestrator(
        config,
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(tmp_path / "service_state.json"),
    )
    issue = Issue(
        id="done-id",
        identifier="TASK-DONE",
        title="Done",
        state="Done",
        project_id="project-a",
        parent_id="EPIC-1",
        target_branch="epic-parent",
    )
    tracker = Mock()
    tracker.fetch_all_issues.return_value = [issue]
    orchestrator.project_store = Mock()
    orchestrator.project_store.list_all.return_value = [SimpleNamespace(id="project-a")]
    orchestrator._tracker_for_project = Mock(return_value=tracker)
    orchestrator._workflow_shadow_sources = Mock(return_value={})
    orchestrator._legacy_workflow_projections = Mock(return_value=())
    orchestrator._notify_observers = Mock()
    orchestrator._notify_state_only = Mock()
    orchestrator._set_refresh_requested = Mock()
    orchestrator._post_event = Mock()
    orchestrator.agent_profile_store._load = Mock()
    orchestrator.agent_profile_store.list_all = Mock(return_value=[])
    evaluation_started = threading.Event()
    release_evaluation = threading.Event()
    reload_finished = threading.Event()
    failures: list[BaseException] = []
    original_evaluator = orchestrator.workflow_shadow._evaluator

    def evaluator(task, facts, *, now=None):
        evaluation_started.set()
        assert release_evaluation.wait(timeout=2)
        return original_evaluator(task, facts, now=now)

    orchestrator.workflow_shadow._evaluator = evaluator

    class _Collector:
        def __init__(self, **_kwargs):
            pass

        def collect(self, _identifier):
            return _done_facts(issue)

    monkeypatch.setattr(orchestrator_module, "WorkflowFactCollector", _Collector)

    def sweep():
        try:
            orchestrator._run_workflow_shadow_sweep()
        except BaseException as exc:  # pragma: no cover - asserted below
            failures.append(exc)

    def reload():
        try:
            replacement = orchestrator_module.ServiceConfig(
                workspace_root=str(tmp_path / "workspace-b")
            )
            replacement.workflow_engine_mode = "shadow"
            orchestrator.reload_config(replacement, "replacement prompt")
        except BaseException as exc:  # pragma: no cover - asserted below
            failures.append(exc)
        finally:
            reload_finished.set()

    sweep_thread = threading.Thread(target=sweep, daemon=True)
    reload_thread = threading.Thread(target=reload, daemon=True)
    sweep_thread.start()
    assert evaluation_started.wait(timeout=2)
    reload_thread.start()
    reload_completed_while_evaluation_was_blocked = reload_finished.wait(timeout=1)
    release_evaluation.set()
    sweep_thread.join(timeout=2)
    reload_thread.join(timeout=2)

    assert reload_completed_while_evaluation_was_blocked is True
    assert not sweep_thread.is_alive()
    assert not reload_thread.is_alive()
    assert failures == []


def _done_facts(issue: Issue) -> WorkflowFacts:
    observed_at = datetime(2026, 8, 6, tzinfo=timezone.utc).isoformat()
    observations = {
        domain: FactObservation.missing(
            domain, observed_at=observed_at, source="test"
        )
        for domain in REQUIRED_FACT_DOMAINS
    }
    observations.update(
        {
            FactDomain.TASK: FactObservation.known(
                FactDomain.TASK,
                {
                    "identifier": issue.identifier,
                    "project_id": issue.project_id,
                    "status": issue.state,
                    "issue_type": issue.issue_type,
                    "parent_id": issue.parent_id,
                },
                observed_at=observed_at,
                source="test",
            ),
            FactDomain.DEPENDENCIES: FactObservation.known(
                FactDomain.DEPENDENCIES,
                {"finish": [], "hard_start": []},
                observed_at=observed_at,
                source="test",
            ),
            FactDomain.CONTAINMENT: FactObservation.known(
                FactDomain.CONTAINMENT,
                {"parent_id": issue.parent_id, "children": []},
                observed_at=observed_at,
                source="test",
            ),
            FactDomain.RETRY_BUDGET: FactObservation.known(
                FactDomain.RETRY_BUDGET,
                {"remaining": 3},
                observed_at=observed_at,
                source="test",
            ),
            FactDomain.CONFIG: FactObservation.known(
                FactDomain.CONFIG,
                {"version": 1},
                observed_at=observed_at,
                source="test",
            ),
        }
    )
    landing = LandingFact(
        "task-branch",
        "epic-parent",
        "a" * 40,
        {"kind": LandingState.NOT_LANDED.value},
        observed_at,
        "project-a",
        state=LandingState.NOT_LANDED,
        durable=False,
        error_code=None,
    )
    observations[FactDomain.LANDING] = FactObservation.known(
        FactDomain.LANDING,
        {"evidence_revisions": [landing.evidence_revision]},
        observed_at=observed_at,
        source="test",
    )
    return WorkflowFacts(
        "project-a",
        issue.identifier,
        observed_at,
        observations,
        landings=(landing,),
    )


def test_controller_full_coverage_overrides_small_recovery_job_limit(
    tmp_path,
) -> None:
    config = orchestrator_module.ServiceConfig(
        workspace_root=str(tmp_path / "workspace")
    )
    config.workflow_engine_mode = "enforce"
    config.workflow_shadow_scan_limit = 2
    orchestrator = Orchestrator(
        config,
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(tmp_path / "service_state.json"),
    )
    issues = [
        Issue(
            id=f"done-{index}",
            identifier=f"TASK-{index}",
            title=f"Done {index}",
            state="Done",
            project_id="project-a",
            parent_id="EPIC-1",
            target_branch="epic-parent",
        )
        for index in range(1, 4)
    ]
    tracker = Mock()
    tracker.fetch_all_issues.return_value = issues
    orchestrator.project_store = Mock()
    orchestrator.project_store.list_all.return_value = [SimpleNamespace(id="project-a")]
    orchestrator._tracker_for_project = Mock(return_value=tracker)
    orchestrator._collect_universal_workflow_facts = Mock(
        side_effect=lambda issue: _done_facts(issue)
    )
    orchestrator._notify_observers = Mock()
    orchestrator._notify_state_only = Mock()

    first_result = orchestrator._run_workflow_controller_sweep()
    first_snapshot, _alerts = orchestrator.work_decision_snapshot()
    second_result = orchestrator._run_workflow_controller_sweep()
    second_snapshot, _alerts = orchestrator.work_decision_snapshot()

    expected = {"TASK-1", "TASK-2", "TASK-3"}
    assert first_result["truncated"] is True
    assert first_result["omitted_tasks"] == 0
    assert second_result["truncated"] is False
    assert second_result["omitted_tasks"] == 0
    assert first_snapshot["availability"] == "incomplete"
    assert second_snapshot["availability"] == "ready"
    assert first_snapshot["complete"] is False
    assert second_snapshot["complete"] is True
    assert first_snapshot["items"] == []
    assert {item["task_id"] for item in second_snapshot["items"]} == expected
    assert {
        item["task_id"] for item in first_snapshot["incomplete_tasks"]
    } == expected
    assert second_snapshot["incomplete_tasks"] == []


def test_shadow_scan_cursor_rotates_every_live_task_through_bounded_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orchestrator = _orchestrator(mode="shadow")
    orchestrator.config.workflow_shadow_scan_limit = 2
    orchestrator._workflow_shadow_generation = 0
    orchestrator._workflow_shadow_generation_lock = threading.Lock()
    orchestrator.project_store = Mock()
    orchestrator.project_store.list_all.return_value = []
    issues = [
        Issue(
            id=f"id-{index}",
            identifier=f"TASK-{index}",
            title=f"Task {index}",
            state="Open",
            project_id="legacy",
        )
        for index in range(1, 4)
    ]
    orchestrator.tracker = Mock()
    orchestrator.tracker.fetch_all_issues.return_value = issues
    orchestrator.integration_queue = Mock()
    orchestrator.workflow_shadow = Mock()

    def evaluate(issue, _facts, _legacy, *, snapshot_generation):
        decision = _decision(
            issue.identifier,
            project_id="legacy",
            reason="dispatch.eligible",
        )
        return SimpleNamespace(
            accepted=True,
            changed=False,
            diagnostic={"decision": decision.to_dict()},
            snapshot_generation=snapshot_generation,
        )

    orchestrator.workflow_shadow.evaluate.side_effect = evaluate
    orchestrator._workflow_shadow_sources = Mock(return_value={})
    orchestrator._legacy_workflow_projections = Mock(return_value=())
    orchestrator._notify_observers = Mock()
    orchestrator._notify_state_only = Mock()

    class _Collector:
        def __init__(self, **_kwargs):
            pass

        def collect(self, _identifier):
            return object()

    monkeypatch.setattr(orchestrator_module, "WorkflowFactCollector", _Collector)

    first = orchestrator._run_workflow_shadow_sweep()
    first_ids = [
        call.args[0].identifier
        for call in orchestrator.workflow_shadow.evaluate.call_args_list
    ]
    orchestrator.workflow_shadow.evaluate.reset_mock()
    second = orchestrator._run_workflow_shadow_sweep()
    second_ids = [
        call.args[0].identifier
        for call in orchestrator.workflow_shadow.evaluate.call_args_list
    ]

    assert first_ids == ["TASK-1", "TASK-2"]
    assert second_ids == ["TASK-3", "TASK-1"]
    assert set(first_ids) | set(second_ids) == {"TASK-1", "TASK-2", "TASK-3"}
    assert (first["scan_offset"], first["next_scan_offset"]) == (0, 2)
    assert (second["scan_offset"], second["next_scan_offset"]) == (2, 1)
    snapshot, _alerts = orchestrator.work_decision_snapshot()
    assert snapshot["availability"] == "incomplete"
    assert snapshot["complete"] is False


def test_shadow_scan_cursor_survives_reload_and_restart_without_restarting_window(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_path = str(tmp_path / "service_state.json")
    config = orchestrator_module.ServiceConfig(
        workspace_root=str(tmp_path / "workspace-a")
    )
    config.workflow_engine_mode = "shadow"
    config.workflow_shadow_scan_limit = 2
    issues = [
        Issue(
            id=f"done-{index}",
            identifier=f"TASK-{index}",
            title=f"Done {index}",
            state="Done",
            project_id="project-a",
            parent_id="EPIC-1",
            target_branch="epic-parent",
        )
        for index in range(1, 4)
    ]
    by_identifier = {issue.identifier: issue for issue in issues}
    observed: list[str] = []

    class _Collector:
        def __init__(self, **_kwargs):
            pass

        def collect(self, identifier):
            observed.append(identifier)
            return _done_facts(by_identifier[identifier])

    monkeypatch.setattr(orchestrator_module, "WorkflowFactCollector", _Collector)

    def configure(orchestrator):
        tracker = Mock()
        tracker.fetch_all_issues.return_value = issues
        orchestrator.project_store = Mock()
        orchestrator.project_store.list_all.return_value = [
            SimpleNamespace(id="project-a")
        ]
        orchestrator._tracker_for_project = Mock(return_value=tracker)
        orchestrator._workflow_shadow_sources = Mock(return_value={})
        orchestrator._legacy_workflow_projections = Mock(return_value=())
        orchestrator._notify_observers = Mock()
        orchestrator._notify_state_only = Mock()

    first = Orchestrator(
        config,
        str(tmp_path / "WORKFLOW.md"),
        state_path=state_path,
    )
    configure(first)
    first.agent_profile_store._load = Mock()
    first.agent_profile_store.list_all = Mock(return_value=[])
    first._set_refresh_requested = Mock()
    first._post_event = Mock()

    first_result = first._run_workflow_shadow_sweep()
    first_window = observed[-2:]
    replacement = orchestrator_module.ServiceConfig(
        workspace_root=str(tmp_path / "workspace-b")
    )
    replacement.workflow_engine_mode = "shadow"
    replacement.workflow_shadow_scan_limit = 2
    first.reload_config(replacement, "replacement prompt")
    second_result = first._run_workflow_shadow_sweep()
    second_window = observed[-2:]

    restarted = Orchestrator(
        replacement,
        str(tmp_path / "WORKFLOW.md"),
        state_path=state_path,
    )
    configure(restarted)
    third_result = restarted._run_workflow_shadow_sweep()
    third_window = observed[-2:]

    assert first_window == ["TASK-1", "TASK-2"]
    assert second_window == ["TASK-3", "TASK-1"]
    assert third_window == ["TASK-2", "TASK-3"]
    assert (first_result["scan_offset"], first_result["next_scan_offset"]) == (0, 2)
    assert (second_result["scan_offset"], second_result["next_scan_offset"]) == (2, 1)
    assert (third_result["scan_offset"], third_result["next_scan_offset"]) == (1, 0)
    persisted = json.loads((tmp_path / "service_state.json").read_text())
    assert persisted["work_decision_availability"][
        "shadow_scan_cursor_version"
    ] == 1
    assert persisted["work_decision_availability"]["shadow_scan_cursor"] == 0


def test_shadow_diagnostic_cap_never_drops_rotating_authoritative_decisions(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = orchestrator_module.ServiceConfig(
        workspace_root=str(tmp_path / "workspace")
    )
    config.workflow_engine_mode = "shadow"
    config.workflow_shadow_scan_limit = 2
    config.workflow_diagnostic_max_bytes = 1024
    issues = [
        Issue(
            id=f"done-{index}",
            identifier=f"TASK-{index}",
            title=f"Done {index}",
            state="Done",
            project_id="project-a",
            parent_id="EPIC-1",
            target_branch="epic-parent",
        )
        for index in range(1, 4)
    ]
    by_identifier = {issue.identifier: issue for issue in issues}

    def rich_facts(issue):
        base = _done_facts(issue)
        observations = dict(base.observations)
        task_value = dict(observations[FactDomain.TASK].value)
        task_value["rich_evidence"] = "x" * 20_000
        observations[FactDomain.TASK] = FactObservation.known(
            FactDomain.TASK,
            task_value,
            observed_at=base.collected_at,
            source="test",
        )
        return WorkflowFacts(
            base.project_id,
            base.task_id,
            base.collected_at,
            observations,
            landings=base.landings,
        )

    class _Collector:
        def __init__(self, **_kwargs):
            pass

        def collect(self, identifier):
            return rich_facts(by_identifier[identifier])

    monkeypatch.setattr(orchestrator_module, "WorkflowFactCollector", _Collector)
    orchestrator = Orchestrator(
        config,
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(tmp_path / "service_state.json"),
    )
    tracker = Mock()
    tracker.fetch_all_issues.return_value = issues
    orchestrator.project_store = Mock()
    orchestrator.project_store.list_all.return_value = [SimpleNamespace(id="project-a")]
    orchestrator._tracker_for_project = Mock(return_value=tracker)
    orchestrator._workflow_shadow_sources = Mock(return_value={})
    orchestrator._legacy_workflow_projections = Mock(return_value=())
    orchestrator._notify_observers = Mock()
    orchestrator._notify_state_only = Mock()

    orchestrator._run_workflow_shadow_sweep()
    first_snapshot, _alerts = orchestrator.work_decision_snapshot()
    orchestrator._run_workflow_shadow_sweep()
    second_snapshot, _alerts = orchestrator.work_decision_snapshot()

    first_ids = {item["task_id"] for item in first_snapshot["items"]}
    second_ids = {item["task_id"] for item in second_snapshot["items"]}
    assert first_ids | second_ids == {"TASK-1", "TASK-2", "TASK-3"}
    assert set(orchestrator._work_decisions) == {
        ("project-a", "TASK-1"),
        ("project-a", "TASK-2"),
        ("project-a", "TASK-3"),
    }
    for task_id in ("TASK-1", "TASK-2", "TASK-3"):
        diagnostic = orchestrator.workflow_shadow.diagnostic("project-a", task_id)
        assert diagnostic is not None
        assert diagnostic["truncated"] is True


def test_old_config_tracker_factory_cannot_repopulate_cache_after_reload(
    tmp_path,
) -> None:
    config = orchestrator_module.ServiceConfig(
        workspace_root=str(tmp_path / "workspace-a")
    )
    orchestrator = Orchestrator(
        config,
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(tmp_path / "service_state.json"),
    )
    project = SimpleNamespace(id="project-a")
    orchestrator.project_store = Mock()
    orchestrator.project_store.get.return_value = project
    orchestrator.project_store.find_by_name.return_value = None
    orchestrator.agent_profile_store._load = Mock()
    orchestrator.agent_profile_store.list_all = Mock(return_value=[])
    orchestrator._notify_observers = Mock()
    orchestrator._set_refresh_requested = Mock()
    orchestrator._post_event = Mock()
    old_factory_started = threading.Event()
    release_old_factory = threading.Event()
    constructed: list[SimpleNamespace] = []

    def tracker_factory(_project, *, config=None):
        marker = str(config.workspace_root)
        tracker = SimpleNamespace(config_marker=marker)
        constructed.append(tracker)
        if marker.endswith("workspace-a"):
            old_factory_started.set()
            assert release_old_factory.wait(timeout=2)
        return tracker

    orchestrator._new_tracker_for_project = tracker_factory
    result: list[SimpleNamespace] = []
    failures: list[BaseException] = []

    def resolve_tracker():
        try:
            result.append(orchestrator._tracker_for_project("project-a"))
        except BaseException as exc:  # pragma: no cover - asserted below
            failures.append(exc)

    resolver = threading.Thread(target=resolve_tracker, daemon=True)
    resolver.start()
    assert old_factory_started.wait(timeout=2)
    replacement = orchestrator_module.ServiceConfig(
        workspace_root=str(tmp_path / "workspace-b")
    )
    orchestrator.reload_config(replacement, "replacement prompt")
    release_old_factory.set()
    resolver.join(timeout=2)

    assert not resolver.is_alive()
    assert failures == []
    assert result[0].config_marker.endswith("workspace-b")
    assert orchestrator._project_trackers["project-a"] is result[0]
    assert constructed[0] is not result[0]


def test_project_config_cut_fences_slow_old_tracker_factory_and_decisions(
    tmp_path,
) -> None:
    config = orchestrator_module.ServiceConfig(
        workspace_root=str(tmp_path / "workspace")
    )
    config.workflow_engine_mode = "enforce"
    orchestrator = Orchestrator(
        config,
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(tmp_path / "service_state.json"),
    )
    project = SimpleNamespace(id="project-a", tracker_version="old")
    project_lock = threading.Lock()

    def get_project(_project_id):
        with project_lock:
            return SimpleNamespace(**vars(project))

    def update_project(_project_id, **fields):
        with project_lock:
            for name, value in fields.items():
                setattr(project, name, value)
            return SimpleNamespace(**vars(project))

    orchestrator.project_store = Mock()
    orchestrator.project_store.get.side_effect = get_project
    orchestrator.project_store.find_by_name.return_value = None
    orchestrator.project_store.update.side_effect = update_project
    orchestrator._notify_observers = Mock()
    orchestrator._set_refresh_requested = Mock()
    orchestrator._post_event = Mock()
    old_factory_started = threading.Event()
    release_old_factory = threading.Event()

    def tracker_factory(factory_project, *, config=None):
        marker = factory_project.tracker_version
        if marker == "old":
            old_factory_started.set()
            assert release_old_factory.wait(timeout=2)
        return SimpleNamespace(config_marker=marker)

    orchestrator._new_tracker_for_project = tracker_factory
    orchestrator._cache_work_decisions(
        [_decision("TASK-1")],
        1,
        source="controller",
        live_keys={("project-a", "TASK-1")},
        publication_epoch=orchestrator._work_decision_publication_epoch,
    )
    resolved = []
    failures: list[BaseException] = []

    def resolve_tracker():
        try:
            resolved.append(orchestrator._tracker_for_project("project-a"))
        except BaseException as exc:  # pragma: no cover - asserted below
            failures.append(exc)

    resolver = threading.Thread(target=resolve_tracker, daemon=True)
    resolver.start()
    assert old_factory_started.wait(timeout=2)
    previous_epoch = orchestrator._work_decision_publication_epoch
    updated = orchestrator.update_project_tracker_configuration(
        "project-a", tracker_version="new"
    )
    release_old_factory.set()
    resolver.join(timeout=2)

    assert not resolver.is_alive()
    assert failures == []
    assert updated.tracker_version == "new"
    assert resolved[0].config_marker == "new"
    assert orchestrator._project_trackers["project-a"] is resolved[0]
    assert orchestrator._work_decision_publication_epoch == previous_epoch + 1
    assert orchestrator.work_decision_projection("project-a", "TASK-1") is None
    assert orchestrator.work_decision_availability("project-a", "TASK-1") == (
        "unavailable"
    )


def test_project_config_cut_rejects_inflight_old_tracker_decision_sweep(
    tmp_path,
) -> None:
    config = orchestrator_module.ServiceConfig(
        workspace_root=str(tmp_path / "workspace")
    )
    config.workflow_engine_mode = "enforce"
    orchestrator = Orchestrator(
        config,
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(tmp_path / "service_state.json"),
    )
    issue = Issue(
        id="done-id",
        identifier="TASK-DONE",
        title="Done",
        state="Done",
        project_id="project-a",
        parent_id="EPIC-1",
        target_branch="epic-parent",
    )
    project = SimpleNamespace(id="project-a", tracker_version="old")
    tracker = Mock()
    tracker.fetch_all_issues.return_value = [issue]
    orchestrator.project_store = Mock()
    orchestrator.project_store.list_all.return_value = [project]

    def update_project(_project_id, **fields):
        for name, value in fields.items():
            setattr(project, name, value)
        return project

    orchestrator.project_store.update.side_effect = update_project
    orchestrator._tracker_for_project = Mock(return_value=tracker)
    facts_started = threading.Event()
    release_facts = threading.Event()

    def slow_old_facts(_issue):
        facts_started.set()
        assert release_facts.wait(timeout=2)
        return _done_facts(issue)

    orchestrator._collect_universal_workflow_facts = slow_old_facts
    orchestrator._notify_observers = Mock()
    orchestrator._set_refresh_requested = Mock()
    orchestrator._post_event = Mock()

    with ThreadPoolExecutor(max_workers=1) as pool:
        sweep = pool.submit(orchestrator._run_workflow_controller_sweep)
        try:
            assert facts_started.wait(timeout=2)
            orchestrator.update_project_tracker_configuration(
                "project-a", tracker_version="new"
            )
        finally:
            release_facts.set()
        result = sweep.result(timeout=2)

    assert result["publication_accepted"] is False
    assert result["publication_rejection"] == "stale_epoch"
    assert orchestrator.work_decision_projection("project-a", "TASK-DONE") is None
    assert orchestrator.work_decision_availability(
        "project-a", "TASK-DONE"
    ) == "unavailable"


def test_project_config_cut_aborts_before_project_mutation_when_state_save_fails(
    tmp_path,
) -> None:
    config = orchestrator_module.ServiceConfig(
        workspace_root=str(tmp_path / "workspace")
    )
    config.workflow_engine_mode = "enforce"
    orchestrator = Orchestrator(
        config,
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(tmp_path / "service_state.json"),
    )
    project = SimpleNamespace(id="project-a", tracker_version="old")
    orchestrator.project_store = Mock()
    orchestrator.project_store.get.return_value = project
    orchestrator.project_store.update.return_value = SimpleNamespace(
        id="project-a", tracker_version="new"
    )
    cached_tracker = object()
    orchestrator._project_trackers[project.id] = cached_tracker
    orchestrator._branch_indexes[project.id] = object()
    orchestrator._stale_caches[project.id] = {"issues": object()}
    orchestrator._cache_work_decisions(
        [_decision("TASK-1")],
        1,
        source="controller",
        live_keys={(project.id, "TASK-1")},
        publication_epoch=orchestrator._work_decision_publication_epoch,
    )
    orchestrator._notify_observers = Mock()
    orchestrator._set_refresh_requested = Mock()
    orchestrator._post_event = Mock()
    orchestrator._save_state = Mock(return_value=False)
    previous_epoch = orchestrator._work_decision_publication_epoch
    previous_generation = orchestrator._project_tracker_generation
    previous_projection = orchestrator.work_decision_projection(
        project.id, "TASK-1"
    )

    with pytest.raises(RuntimeError, match="availability could not be persisted"):
        orchestrator.update_project_tracker_configuration(
            project.id, tracker_version="new"
        )

    orchestrator.project_store.update.assert_not_called()
    assert orchestrator._work_decision_publication_epoch == previous_epoch
    assert orchestrator._project_tracker_generation == previous_generation
    assert orchestrator._project_trackers[project.id] is cached_tracker
    assert orchestrator.work_decision_projection(
        project.id, "TASK-1"
    ) == previous_projection
    assert project.id in orchestrator._branch_indexes
    assert project.id in orchestrator._stale_caches
    orchestrator._notify_observers.assert_not_called()
    orchestrator._set_refresh_requested.assert_not_called()
    orchestrator._post_event.assert_not_called()


def test_project_config_cut_restores_availability_when_project_update_fails(
    tmp_path,
) -> None:
    config = orchestrator_module.ServiceConfig(
        workspace_root=str(tmp_path / "workspace")
    )
    config.workflow_engine_mode = "enforce"
    orchestrator = Orchestrator(
        config,
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(tmp_path / "service_state.json"),
    )
    project = SimpleNamespace(id="project-a", tracker_version="old")
    orchestrator.project_store = Mock()
    orchestrator.project_store.get.return_value = project
    orchestrator.project_store.update.side_effect = RuntimeError("store failed")
    orchestrator._notify_observers = Mock()
    orchestrator._set_refresh_requested = Mock()
    orchestrator._post_event = Mock()
    orchestrator._save_state = Mock(side_effect=(True, True))
    previous_epoch = orchestrator._work_decision_publication_epoch
    previous_generation = orchestrator._project_tracker_generation

    with pytest.raises(RuntimeError, match="store failed"):
        orchestrator.update_project_tracker_configuration(
            project.id, tracker_version="new"
        )

    assert orchestrator._save_state.call_count == 2
    pending = orchestrator._save_state.call_args_list[0].kwargs[
        "work_decision_availability"
    ]
    restored = orchestrator._save_state.call_args_list[1].kwargs[
        "work_decision_availability"
    ]
    assert pending["publication_epoch"] == previous_epoch + 1
    assert project.id in pending["unavailable_projects"]
    assert restored["publication_epoch"] == previous_epoch
    assert project.id not in restored["unavailable_projects"]
    assert orchestrator._work_decision_publication_epoch == previous_epoch
    assert orchestrator._project_tracker_generation == previous_generation
    orchestrator._notify_observers.assert_not_called()
    orchestrator._set_refresh_requested.assert_not_called()
    orchestrator._post_event.assert_not_called()


def test_project_config_cut_validates_before_retiring_checkpoint_writer(
    tmp_path,
) -> None:
    orchestrator, project = _endpoint_authority_orchestrator(
        tmp_path,
        migration_stage="",
    )

    class RetiringTracker:
        def __init__(self) -> None:
            self.retire = Mock(return_value=1)

        def retire_checkpoint_writer(self, *, reason):
            return self.retire(reason=reason)

    tracker = RetiringTracker()
    orchestrator._project_trackers[project.id] = tracker

    with pytest.raises(ProjectError, match="max_in_flight_prs"):
        orchestrator.update_project_tracker_configuration(
            project.id,
            max_in_flight_prs=0,
        )

    tracker.retire.assert_not_called()
    assert project.max_in_flight_prs != 0
    assert orchestrator._project_trackers[project.id] is tracker


def test_project_config_cut_rejects_late_old_generation_refresh(tmp_path) -> None:
    config = orchestrator_module.ServiceConfig(
        workspace_root=str(tmp_path / "workspace")
    )
    config.workflow_engine_mode = "enforce"
    orchestrator = Orchestrator(
        config,
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(tmp_path / "service_state.json"),
    )
    project = SimpleNamespace(id="project-a", tracker_version="old")

    def update_project(_project_id, **fields):
        for name, value in fields.items():
            setattr(project, name, value)
        return project

    orchestrator.project_store = Mock()
    orchestrator.project_store.get.return_value = project
    orchestrator.project_store.update.side_effect = update_project
    orchestrator._notify_observers = Mock()
    orchestrator._set_refresh_requested = Mock()
    orchestrator._post_event = Mock()

    async def exercise_race():
        refresh_started = asyncio.Event()
        release_refresh = asyncio.Event()

        async def old_refresh():
            refresh_started.set()
            await release_refresh.wait()
            return ["old-tracker-result"]

        refresh = asyncio.create_task(
            orchestrator._run_bounded_refresh(
                project.id,
                "issues",
                old_refresh,
                timeout_ms=5_000,
            )
        )
        await refresh_started.wait()
        orchestrator.update_project_tracker_configuration(
            project.id, tracker_version="new"
        )
        release_refresh.set()
        return await refresh

    data, is_fresh = asyncio.run(exercise_race())

    assert data == []
    assert is_fresh is False
    assert orchestrator._get_stale_cache(project.id, "issues") is None
    assert project.id not in orchestrator._stale_caches


def test_project_config_cut_rejects_late_old_merged_branch_refresh(
    tmp_path,
) -> None:
    config = orchestrator_module.ServiceConfig(
        workspace_root=str(tmp_path / "workspace")
    )
    config.workflow_engine_mode = "enforce"
    orchestrator = Orchestrator(
        config,
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(tmp_path / "service_state.json"),
    )
    project = SimpleNamespace(
        id="project-a",
        name="project-a",
        repo_url="https://github.com/example/project-a.git",
        access_token=None,
    )

    def update_project(_project_id, **fields):
        for name, value in fields.items():
            setattr(project, name, value)
        return project

    orchestrator.project_store = Mock()
    orchestrator.project_store.get.return_value = project
    orchestrator.project_store.list_all.return_value = [project]
    orchestrator.project_store.update.side_effect = update_project
    orchestrator.is_webhook_healthy = Mock(return_value=False)
    orchestrator._notify_observers = Mock()
    orchestrator._set_refresh_requested = Mock()
    orchestrator._post_event = Mock()
    provider_started = threading.Event()
    release_provider = threading.Event()
    provider = Mock()

    def old_provider_read(_slug):
        provider_started.set()
        assert release_provider.wait(timeout=2)
        return {"old-tracker-branch"}

    provider.list_merged_branches.side_effect = old_provider_read
    result: list[set[str]] = []
    failures: list[BaseException] = []

    def refresh():
        try:
            result.append(orchestrator._fetch_all_merged_branches())
        except BaseException as exc:  # pragma: no cover - asserted below
            failures.append(exc)

    with patch.object(orchestrator_module, "detect_provider", return_value=provider):
        worker = threading.Thread(target=refresh, daemon=True)
        worker.start()
        assert provider_started.wait(timeout=2)
        orchestrator.update_project_tracker_configuration(
            project.id,
            repo_url="https://github.com/example/project-a-renamed.git",
        )
        release_provider.set()
        worker.join(timeout=2)

    assert not worker.is_alive()
    assert failures == []
    assert result == [set()]
    assert orchestrator._get_stale_cache(project.id, "merged_branches") is None
    assert project.id not in orchestrator._stale_caches


@pytest.mark.parametrize("refresh_kind", ("reviews", "merged_branches"))
def test_project_config_cut_rejects_late_bounded_forge_refresh(
    tmp_path,
    refresh_kind,
) -> None:
    config = orchestrator_module.ServiceConfig(
        workspace_root=str(tmp_path / "workspace")
    )
    config.workflow_engine_mode = "enforce"
    orchestrator = Orchestrator(
        config,
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(tmp_path / "service_state.json"),
    )
    project = SimpleNamespace(
        id="project-a",
        name="project-a",
        repo_url="https://github.com/example/project-a.git",
        access_token=None,
    )

    def update_project(_project_id, **fields):
        for name, value in fields.items():
            setattr(project, name, value)
        return project

    orchestrator.project_store = Mock()
    orchestrator.project_store.get.return_value = project
    orchestrator.project_store.list_all.return_value = [project]
    orchestrator.project_store.update.side_effect = update_project
    orchestrator.is_webhook_healthy = Mock(return_value=False)
    orchestrator._notify_observers = Mock()
    orchestrator._set_refresh_requested = Mock()
    orchestrator._post_event = Mock()
    provider_started = threading.Event()
    release_provider = threading.Event()
    provider = Mock()
    if refresh_kind == "reviews":
        provider_result = [SimpleNamespace(source_branch="old-review")]
        provider.list_open_reviews.side_effect = lambda _slug: (
            provider_started.set(),
            release_provider.wait(timeout=2),
            provider_result,
        )[-1]
        orchestrator._reviews_cache = {
            project.id: [SimpleNamespace(source_branch="old-cached-review")]
        }
    else:
        provider_result = {"old-merged-branch"}
        provider.list_merged_branches.side_effect = lambda _slug: (
            provider_started.set(),
            release_provider.wait(timeout=2),
            provider_result,
        )[-1]
        orchestrator._set_stale_cache(
            project.id,
            "merged_branches",
            {"old-cached-branch"},
        )

    failures: list[BaseException] = []

    def cut_configuration():
        try:
            assert provider_started.wait(timeout=2)
            orchestrator.update_project_tracker_configuration(
                project.id,
                repo_url="https://github.com/example/project-a-renamed.git",
            )
        except BaseException as exc:  # pragma: no cover - asserted below
            failures.append(exc)
        finally:
            release_provider.set()

    updater = threading.Thread(target=cut_configuration, daemon=True)
    updater.start()
    with patch.object(orchestrator_module, "detect_provider", return_value=provider):
        result = asyncio.run(
            orchestrator._fetch_all_reviews_bounded()
            if refresh_kind == "reviews"
            else orchestrator._fetch_all_merged_branches_bounded()
        )
    updater.join(timeout=2)

    assert not updater.is_alive()
    assert failures == []
    if refresh_kind == "reviews":
        assert result == {project.id: []}
    else:
        assert result == set()
    assert orchestrator._get_stale_cache(project.id, refresh_kind) is None


@pytest.mark.parametrize("refresh_kind", ("reviews", "merged_branches"))
def test_project_config_cut_never_returns_mixed_generation_sync_forge_snapshot(
    tmp_path,
    refresh_kind,
) -> None:
    config = orchestrator_module.ServiceConfig(
        workspace_root=str(tmp_path / "workspace")
    )
    config.workflow_engine_mode = "enforce"
    orchestrator = Orchestrator(
        config,
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(tmp_path / "service_state.json"),
    )
    projects = [
        SimpleNamespace(
            id=f"project-{suffix}",
            name=f"project-{suffix}",
            repo_url=f"https://github.com/example/project-{suffix}.git",
            access_token=None,
        )
        for suffix in ("a", "b")
    ]
    by_id = {project.id: project for project in projects}

    def update_project(project_id, **fields):
        project = by_id[project_id]
        for name, value in fields.items():
            setattr(project, name, value)
        return project

    orchestrator.project_store = Mock()
    orchestrator.project_store.get.side_effect = by_id.get
    orchestrator.project_store.list_all.return_value = projects
    orchestrator.project_store.update.side_effect = update_project
    orchestrator.is_webhook_healthy = Mock(return_value=False)
    orchestrator._notify_observers = Mock()
    orchestrator._set_refresh_requested = Mock()
    orchestrator._post_event = Mock()
    second_provider_started = threading.Event()
    release_second_provider = threading.Event()
    providers = {project.id: Mock() for project in projects}
    if refresh_kind == "reviews":
        providers["project-a"].list_open_reviews.return_value = [
            SimpleNamespace(source_branch="old-a-review")
        ]
        providers["project-b"].list_open_reviews.side_effect = lambda _slug: (
            second_provider_started.set(),
            release_second_provider.wait(timeout=2),
            [SimpleNamespace(source_branch="old-b-review")],
        )[-1]
    else:
        providers["project-a"].list_merged_branches.return_value = {
            "old-a-branch"
        }
        providers["project-b"].list_merged_branches.side_effect = lambda _slug: (
            second_provider_started.set(),
            release_second_provider.wait(timeout=2),
            {"old-b-branch"},
        )[-1]

    failures: list[BaseException] = []

    def cut_configuration():
        try:
            assert second_provider_started.wait(timeout=2)
            orchestrator.update_project_tracker_configuration(
                "project-b",
                repo_url="https://github.com/example/project-b-renamed.git",
            )
        except BaseException as exc:  # pragma: no cover - asserted below
            failures.append(exc)
        finally:
            release_second_provider.set()

    def provider_for(repo_url, **_kwargs):
        project_id = "project-a" if "project-a" in repo_url else "project-b"
        return providers[project_id]

    updater = threading.Thread(target=cut_configuration, daemon=True)
    updater.start()
    with patch.object(orchestrator_module, "detect_provider", side_effect=provider_for):
        result = (
            orchestrator._fetch_all_reviews()
            if refresh_kind == "reviews"
            else orchestrator._fetch_all_merged_branches()
        )
    updater.join(timeout=2)

    assert not updater.is_alive()
    assert failures == []
    if refresh_kind == "reviews":
        assert result == {"project-a": [], "project-b": []}
    else:
        assert result == set()


def _endpoint_authority_orchestrator(
    tmp_path,
    *,
    migration_stage: str,
) -> tuple[Orchestrator, Project]:
    config = orchestrator_module.ServiceConfig(
        workspace_root=str(tmp_path / "workspace")
    )
    config.workflow_engine_mode = "enforce"
    orchestrator = Orchestrator(
        config,
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(tmp_path / "service_state.json"),
    )
    project = Project(
        id="project-a",
        name="project-a",
        repo_url="https://github.com/example/project-a.git",
        repo_path=str(tmp_path / "project-a"),
        default_branch="main",
        tracker_kind="oompah_md",
        state_branch_enabled=migration_stage in {"A", "B"},
        state_branch_shadow_write=migration_stage == "A",
        state_branch_migration_stage=migration_stage,
    )
    store = ProjectStore(
        path=str(tmp_path / "projects.json"),
        repos_root=str(tmp_path / "repos"),
        worktree_root=str(tmp_path / "worktrees"),
    )
    store._projects[project.id] = project  # noqa: SLF001 - endpoint fixture
    store._save()  # noqa: SLF001 - endpoint fixture
    orchestrator.project_store = store
    orchestrator._notify_observers = Mock()
    orchestrator._set_refresh_requested = Mock()
    orchestrator._post_event = Mock()
    return orchestrator, project


def test_project_patch_reports_failed_authority_persistence_without_mutation(
    tmp_path,
) -> None:
    orchestrator, project = _endpoint_authority_orchestrator(
        tmp_path, migration_stage=""
    )
    original_repo_url = project.repo_url
    previous_epoch = orchestrator._work_decision_publication_epoch
    previous_generation = orchestrator._project_tracker_generation
    update = Mock(wraps=orchestrator.project_store.update)
    orchestrator.project_store.update = update
    orchestrator._save_state = Mock(return_value=False)

    with ExitStack() as patches:
        patches.enter_context(patch.object(server_module, "_orchestrator", orchestrator))
        patches.enter_context(patch.object(server_module, "_log_watcher_manager", None))
        patches.enter_context(patch.object(server_module, "_gitlab_hook_manager", None))
        patches.enter_context(
            patch.object(
                server_module,
                "_ensure_tracker_agent_instructions_for_project",
            )
        )
        response = TestClient(server_module.app).patch(
            f"/api/v1/projects/{project.id}",
            json={
                "repo_url": "https://github.com/example/project-a-renamed.git"
            },
        )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "update_failed"
    assert "availability could not be persisted" in response.json()["error"][
        "message"
    ]
    update.assert_not_called()
    assert orchestrator.project_store.get(project.id).repo_url == original_repo_url
    assert orchestrator._work_decision_publication_epoch == previous_epoch
    assert orchestrator._project_tracker_generation == previous_generation
    orchestrator._notify_observers.assert_not_called()
    orchestrator._set_refresh_requested.assert_not_called()
    orchestrator._post_event.assert_not_called()


@pytest.mark.parametrize(
    ("endpoint_case", "migration_stage"),
    (
        ("repo_url", ""),
        ("default_branch", ""),
        ("stage_a", ""),
        ("stage_b", "A"),
        ("rollback", "B"),
    ),
)
def test_project_config_endpoints_publish_one_authority_cut_and_fence_old_sweep(
    tmp_path,
    endpoint_case,
    migration_stage,
) -> None:
    orchestrator, project = _endpoint_authority_orchestrator(
        tmp_path, migration_stage=migration_stage
    )
    issue = Issue(
        id="done-id",
        identifier="TASK-DONE",
        title="Done",
        state="Done",
        project_id=project.id,
        parent_id="EPIC-1",
        target_branch="epic-parent",
    )
    old_tracker = Mock()
    old_tracker.fetch_all_issues.return_value = [issue]
    with orchestrator._project_trackers_lock:
        orchestrator._project_trackers[project.id] = old_tracker
    orchestrator._branch_indexes[project.id] = object()
    orchestrator._stale_caches[project.id] = {"issues": object()}
    orchestrator._cache_work_decisions(
        [_decision(issue.identifier)],
        1,
        source="controller",
        live_keys={(project.id, issue.identifier)},
        publication_epoch=orchestrator._work_decision_publication_epoch,
    )
    facts_started = threading.Event()
    release_facts = threading.Event()

    def slow_old_facts(_issue):
        facts_started.set()
        assert release_facts.wait(timeout=2)
        return _done_facts(issue)

    orchestrator._collect_universal_workflow_facts = slow_old_facts
    previous_tracker_generation = orchestrator._project_tracker_generation
    previous_decision_epoch = orchestrator._work_decision_publication_epoch

    with ThreadPoolExecutor(max_workers=1) as pool:
        sweep = pool.submit(orchestrator._run_workflow_controller_sweep)
        try:
            assert facts_started.wait(timeout=2)
            with ExitStack() as patches:
                patches.enter_context(
                    patch.object(server_module, "_orchestrator", orchestrator)
                )
                patches.enter_context(
                    patch.object(server_module, "_log_watcher_manager", None)
                )
                patches.enter_context(
                    patch.object(server_module, "_gitlab_hook_manager", None)
                )
                patches.enter_context(
                    patch.object(
                        server_module,
                        "_ensure_tracker_agent_instructions_for_project",
                    )
                )
                patches.enter_context(
                    patch(
                        "oompah.state_branch_migration.migrate_stage_a",
                        return_value=MigrationResult(stage="A", ok=True),
                    )
                )
                patches.enter_context(
                    patch(
                        "oompah.state_branch_migration.migrate_stage_b",
                        return_value=MigrationResult(stage="B", ok=True),
                    )
                )
                patches.enter_context(
                    patch(
                        "oompah.state_branch_migration.rollback_migration",
                        return_value=MigrationResult(stage="rollback", ok=True),
                    )
                )
                patches.enter_context(
                    patch(
                        "oompah.state_branch_migration.verify_state_branch",
                        return_value=StateBranchVerificationResult(ok=True),
                    )
                )
                client = TestClient(server_module.app)
                if endpoint_case == "repo_url":
                    response = client.patch(
                        f"/api/v1/projects/{project.id}",
                        json={
                            "repo_url": (
                                "https://github.com/example/project-a-renamed.git"
                            )
                        },
                    )
                elif endpoint_case == "default_branch":
                    response = client.patch(
                        f"/api/v1/projects/{project.id}",
                        json={"default_branch": "develop"},
                    )
                else:
                    action = {
                        "stage_a": "A",
                        "stage_b": "B",
                        "rollback": "rollback",
                    }[endpoint_case]
                    response = client.post(
                        f"/api/v1/projects/{project.id}/state-branch/migrate",
                        json={"action": action, "confirm": True},
                    )
            assert response.status_code == 200, response.text
        finally:
            release_facts.set()
        sweep_result = sweep.result(timeout=2)

    updated = orchestrator.project_store.get(project.id)
    assert updated is not None
    if endpoint_case == "repo_url":
        assert updated.repo_url.endswith("project-a-renamed.git")
    elif endpoint_case == "default_branch":
        assert updated.default_branch == "develop"
    elif endpoint_case == "stage_a":
        assert updated.state_branch_enabled is True
        assert updated.state_branch_shadow_write is True
        assert updated.state_branch_migration_stage == "A"
    elif endpoint_case == "stage_b":
        assert updated.state_branch_enabled is True
        assert updated.state_branch_shadow_write is False
        assert updated.state_branch_migration_stage == "B"
    else:
        assert updated.state_branch_enabled is False
        assert updated.state_branch_shadow_write is False
        assert updated.state_branch_migration_stage == ""

    assert orchestrator._project_tracker_generation == (
        previous_tracker_generation + 1
    )
    assert orchestrator._work_decision_publication_epoch == (
        previous_decision_epoch + 1
    )
    assert project.id not in orchestrator._project_trackers
    assert project.id not in orchestrator._branch_indexes
    assert project.id not in orchestrator._stale_caches
    assert orchestrator.work_decision_projection(project.id, issue.identifier) is None
    assert (
        orchestrator.work_decision_availability(project.id, issue.identifier)
        == "unavailable"
    )
    assert orchestrator._work_decision_snapshot_complete is False
    persisted = json.loads((tmp_path / "service_state.json").read_text())
    availability = persisted["work_decision_availability"]
    assert availability["publication_epoch"] == previous_decision_epoch + 1
    assert project.id in availability["unavailable_projects"]
    assert availability["complete"] is False
    assert sweep_result["publication_accepted"] is False
    assert sweep_result["publication_rejection"] == "stale_epoch"


def test_slow_controller_facts_do_not_block_workflow_lease_or_claim(tmp_path) -> None:
    config = orchestrator_module.ServiceConfig(
        workspace_root=str(tmp_path / "workspace")
    )
    config.workflow_engine_mode = "enforce"
    orchestrator = Orchestrator(
        config,
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(tmp_path / "service_state.json"),
    )
    issue = Issue(
        id="done-id",
        identifier="TASK-DONE",
        title="Done",
        state="Done",
        project_id="project-a",
        parent_id="EPIC-1",
        target_branch="epic-parent",
    )
    tracker = Mock()
    tracker.fetch_all_issues.return_value = [issue]
    orchestrator.project_store = Mock()
    orchestrator.project_store.list_all.return_value = [SimpleNamespace(id="project-a")]
    orchestrator._tracker_for_project = Mock(return_value=tracker)
    facts_started = threading.Event()
    release_facts = threading.Event()

    def slow_facts(_issue):
        facts_started.set()
        assert release_facts.wait(timeout=2)
        return _done_facts(issue)

    orchestrator._collect_universal_workflow_facts = slow_facts
    orchestrator._notify_observers = Mock()
    store = orchestrator.workflow_job_store
    leased = store.enqueue(
        WorkflowJobSpec(
            project_id="lease-project",
            task_id="LEASED",
            generation="lease:g1",
            action="terminal_audit",
            idempotency_key="lease:g1:audit",
        )
    )
    leased = store.claim_next(lease_owner="worker-a", lease_seconds=60)
    assert leased is not None
    store.enqueue(
        WorkflowJobSpec(
            project_id="claim-project",
            task_id="CLAIMABLE",
            generation="claim:g1",
            action="terminal_audit",
            idempotency_key="claim:g1:audit",
        )
    )

    with ThreadPoolExecutor(max_workers=3) as pool:
        sweep = pool.submit(orchestrator._run_workflow_controller_sweep)
        try:
            assert facts_started.wait(timeout=2)
            renewed = pool.submit(
                store.renew,
                leased.job_id,
                leased.lease_token,
                lease_seconds=60,
            ).result(timeout=1)
            claimed = pool.submit(
                store.claim_next,
                lease_owner="worker-b",
                lease_seconds=60,
                project_id="claim-project",
            ).result(timeout=1)
        finally:
            release_facts.set()
        result = sweep.result(timeout=2)

    assert renewed.job_id == leased.job_id
    assert claimed is not None
    assert claimed.task_id == "CLAIMABLE"
    assert result["publication_accepted"] is True


def test_tracker_read_stats_snapshot_survives_concurrent_reload(tmp_path) -> None:
    config = orchestrator_module.ServiceConfig(
        workspace_root=str(tmp_path / "workspace-a")
    )
    orchestrator = Orchestrator(
        config,
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(tmp_path / "service_state.json"),
    )
    read_started = threading.Event()
    release_read = threading.Event()

    class _BlockingStats:
        def read_stats(self):
            read_started.set()
            assert release_read.wait(timeout=2)
            return {"reads": 1}

    class _Stats:
        def read_stats(self):
            return {"reads": 2}

    with orchestrator._project_trackers_lock:
        orchestrator._project_trackers = {
            "project-a": _BlockingStats(),
            "project-b": _Stats(),
        }
    orchestrator.agent_profile_store._load = Mock()
    orchestrator.agent_profile_store.list_all = Mock(return_value=[])
    orchestrator._notify_observers = Mock()
    orchestrator._set_refresh_requested = Mock()
    orchestrator._post_event = Mock()
    snapshots = []
    failures: list[BaseException] = []

    def read_stats():
        try:
            snapshots.append(orchestrator._tracker_read_stats_snapshot())
        except BaseException as exc:  # pragma: no cover - asserted below
            failures.append(exc)

    reader = threading.Thread(target=read_stats, daemon=True)
    reader.start()
    assert read_started.wait(timeout=2)
    replacement = orchestrator_module.ServiceConfig(
        workspace_root=str(tmp_path / "workspace-b")
    )
    try:
        orchestrator.reload_config(replacement, "replacement prompt")
    finally:
        release_read.set()
    reader.join(timeout=2)

    assert not reader.is_alive()
    assert failures == []
    assert snapshots[0]["project-a"] == {"reads": 1}
    assert snapshots[0]["project-b"] == {"reads": 2}


def test_controller_tracker_construction_failure_isolated_to_one_project() -> None:
    orchestrator = _orchestrator(mode="enforce")
    project_bad = SimpleNamespace(id="project-bad")
    project_good = SimpleNamespace(id="project-good")
    issue = Issue(
        id="good-id",
        identifier="TASK-GOOD",
        title="Good",
        state="Open",
        project_id="project-good",
    )
    tracker = Mock()
    tracker.fetch_all_issues.return_value = [issue]
    orchestrator.project_store = Mock()
    orchestrator.project_store.list_all.return_value = [project_bad, project_good]

    def tracker_for(project_id):
        if project_id == "project-bad":
            raise RuntimeError("tracker construction failed")
        return tracker

    orchestrator._tracker_for_project = Mock(side_effect=tracker_for)
    orchestrator.workflow_controller = Mock(decision_limit=100)
    orchestrator.workflow_controller.full_sync.return_value = SimpleNamespace(
        decisions=(_decision("TASK-GOOD", project_id="project-good"),),
        snapshot_generation=1,
        action_required=(),
        reconciliation=SimpleNamespace(
            jobs_created=0,
            jobs_replayed=0,
            jobs_superseded=0,
            truncated=False,
        ),
        truncated=False,
    )
    orchestrator._notify_observers = Mock()

    result = orchestrator._run_workflow_controller_sweep()
    snapshot, _alerts = orchestrator.work_decision_snapshot()

    assert result["publication_accepted"] is True
    evaluated = orchestrator.workflow_controller.full_sync.call_args.args[0]
    assert [item.identifier for item in evaluated] == ["TASK-GOOD"]
    assert snapshot["availability"] == "partial"
    assert snapshot["unavailable_projects"] == ["project-bad"]
    assert [item["task_id"] for item in snapshot["items"]] == ["TASK-GOOD"]


def test_shadow_tracker_construction_failure_isolated_to_one_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orchestrator = _orchestrator(mode="shadow")
    orchestrator.config.workflow_shadow_scan_limit = 100
    orchestrator._workflow_shadow_generation = 0
    orchestrator._workflow_shadow_generation_lock = threading.Lock()
    project_bad = SimpleNamespace(id="project-bad")
    project_good = SimpleNamespace(id="project-good")
    issue = Issue(
        id="good-id",
        identifier="TASK-GOOD",
        title="Good",
        state="Open",
        project_id="project-good",
    )
    tracker = Mock()
    tracker.fetch_all_issues.return_value = [issue]
    orchestrator.project_store = Mock()
    orchestrator.project_store.list_all.return_value = [project_bad, project_good]

    def tracker_for(project_id):
        if project_id == "project-bad":
            raise RuntimeError("tracker construction failed")
        return tracker

    orchestrator._tracker_for_project = Mock(side_effect=tracker_for)
    orchestrator.integration_queue = Mock()
    orchestrator.workflow_shadow = Mock()
    orchestrator.workflow_shadow.evaluate.return_value = SimpleNamespace(
        accepted=True,
        changed=False,
        diagnostic={
            "decision": _decision(
                "TASK-GOOD", project_id="project-good"
            ).to_dict()
        },
    )
    orchestrator._workflow_shadow_sources = Mock(return_value={})
    orchestrator._legacy_workflow_projections = Mock(return_value=())
    orchestrator._notify_observers = Mock()
    orchestrator._notify_state_only = Mock()

    class _Collector:
        def __init__(self, **_kwargs):
            pass

        def collect(self, _identifier):
            return object()

    monkeypatch.setattr(orchestrator_module, "WorkflowFactCollector", _Collector)

    result = orchestrator._run_workflow_shadow_sweep()
    snapshot, _alerts = orchestrator.work_decision_snapshot()

    assert result["publication_accepted"] is True
    assert orchestrator.workflow_shadow.evaluate.call_args.args[0].identifier == (
        "TASK-GOOD"
    )
    assert snapshot["availability"] == "partial"
    assert snapshot["unavailable_projects"] == ["project-bad"]
    assert [item["task_id"] for item in snapshot["items"]] == ["TASK-GOOD"]


def test_done_flows_through_real_controller_cache_and_snapshot(tmp_path) -> None:
    config = orchestrator_module.ServiceConfig(
        workspace_root=str(tmp_path / "workspace")
    )
    config.workflow_engine_mode = "enforce"
    orchestrator = Orchestrator(
        config,
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(tmp_path / "service_state.json"),
    )
    done = Issue(
        id="done-id",
        identifier="TASK-DONE",
        title="Done awaiting landing",
        state="Done",
        project_id="project-a",
        parent_id="EPIC-1",
        target_branch="epic-parent",
    )
    tracker = Mock()
    tracker.fetch_all_issues.return_value = [done]
    project = SimpleNamespace(
        id="project-a",
        to_safe_dict=lambda: {"id": "project-a"},
    )
    orchestrator.project_store = Mock()
    orchestrator.project_store.list_all.return_value = [project]
    orchestrator._tracker_for_project = Mock(return_value=tracker)
    facts = _done_facts(done)
    orchestrator._collect_universal_workflow_facts = Mock(return_value=facts)
    orchestrator.workflow_controller._clock = lambda: datetime(
        2026, 8, 6, tzinfo=timezone.utc
    )
    orchestrator._notify_observers = Mock()

    orchestrator._run_workflow_controller_sweep()

    cached = orchestrator.work_decision_projection("project-a", "TASK-DONE")
    assert cached is not None
    assert cached["status"] == "Done"
    assert cached["reason_code"] == "landing.waiting"
    snapshot = orchestrator.get_snapshot()
    rows = snapshot["work_decision_projection"]["items"]
    assert [(row["project_id"], row["task_id"]) for row in rows] == [
        ("project-a", "TASK-DONE")
    ]


def test_shadow_and_controller_sweeps_both_cover_done_lifecycle_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orchestrator = _orchestrator(mode="enforce")
    orchestrator.config.workflow_shadow_scan_limit = 100
    orchestrator._workflow_shadow_generation = 0
    orchestrator._workflow_shadow_generation_lock = threading.Lock()
    orchestrator.project_store = Mock()
    orchestrator.project_store.list_all.return_value = []
    done = Issue(
        id="done-id",
        identifier="TASK-DONE",
        title="Done but not lifecycle-final",
        state="Done",
        project_id="legacy",
    )
    orchestrator.tracker = Mock()
    orchestrator.tracker.fetch_all_issues.return_value = [done]
    orchestrator.integration_queue = Mock()
    orchestrator.workflow_shadow = Mock()
    orchestrator.workflow_shadow.evaluate.return_value = SimpleNamespace(
        accepted=True,
        changed=False,
        diagnostic=None,
    )
    orchestrator._workflow_shadow_sources = Mock(return_value={})
    orchestrator._legacy_workflow_projections = Mock(return_value=())
    orchestrator._notify_observers = Mock()
    orchestrator._notify_state_only = Mock()

    class _Collector:
        def __init__(self, **_kwargs):
            pass

        def collect(self, _identifier):
            return object()

    monkeypatch.setattr(orchestrator_module, "WorkflowFactCollector", _Collector)
    orchestrator.workflow_controller = Mock()
    orchestrator.workflow_controller.full_sync.return_value = SimpleNamespace(
        decisions=(),
        snapshot_generation=1,
        action_required=(),
        reconciliation=SimpleNamespace(
            jobs_created=0,
            jobs_replayed=0,
            jobs_superseded=0,
        ),
        truncated=False,
    )

    orchestrator._run_workflow_shadow_sweep()
    orchestrator._run_workflow_controller_sweep()

    shadow_issue = orchestrator.workflow_shadow.evaluate.call_args.args[0]
    controller_issues = orchestrator.workflow_controller.full_sync.call_args.args[0]
    assert shadow_issue.identifier == "TASK-DONE"
    assert [issue.identifier for issue in controller_issues] == ["TASK-DONE"]
