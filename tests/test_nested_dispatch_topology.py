from __future__ import annotations

import asyncio
from dataclasses import replace
import subprocess
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oompah.integration import IntegrationRecord
from oompah.models import BlockerRef, Issue, Project
from oompah.orchestrator import NestedDispatchEvidence, Orchestrator
from oompah.projects import NestedDispatchTopology, ProjectError, ProjectStore
from oompah.workflow_jobs import WorkflowJobSpec, WorkflowJobState
from tests.test_epic_strategy import _make_orch, _make_project_record


def _issue(
    identifier: str,
    *,
    parent_id: str | None = None,
    issue_type: str = "task",
    state: str = "Open",
    hard_start: tuple[str, ...] = (),
    integration: IntegrationRecord | None = None,
) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=identifier,
        description="production-shaped nested dispatch fixture",
        state=state,
        issue_type=issue_type,
        parent_id=parent_id,
        project_id="proj-1",
        start_blocked_by=[
            BlockerRef(id=value, identifier=value) for value in hard_start
        ],
        integration=integration,
    )


def _oompah_770_796_fixture(tmp_path):
    project = _make_project_record(epic_strategy="shared")
    orchestrator = _make_orch(tmp_path, projects=[project])
    orchestrator._preflight_nested_epic_dispatch = (
        Orchestrator._preflight_nested_epic_dispatch.__get__(orchestrator)
    )
    orchestrator.config.parallel_epic_children_enabled = True
    root = _issue("OOMPAH-763", issue_type="epic", state="In Progress")
    nested = _issue(
        "OOMPAH-770",
        parent_id=root.identifier,
        issue_type="epic",
        state="In Progress",
        hard_start=("OOMPAH-785",),
    )
    child = _issue("OOMPAH-796", parent_id=nested.identifier)
    dependency = _issue(
        "OOMPAH-785",
        state="Done",
        integration=IntegrationRecord(
            state="integrated",
            integrated_sha="d" * 40,
        ),
    )
    issues = {
        item.identifier: item for item in (root, nested, child, dependency)
    }
    tracker = MagicMock()
    tracker.fetch_issue_detail.side_effect = lambda identifier: issues.get(identifier)
    orchestrator._tracker_for_issue = MagicMock(return_value=tracker)
    orchestrator._tracker_for_project = MagicMock(return_value=tracker)
    orchestrator.project_store.epic_child_branch_name.return_value = (
        "epic-OOMPAH-770--task-OOMPAH-796"
    )
    topology = NestedDispatchTopology(
        target_branch="epic-OOMPAH-763",
        target_head="f" * 40,
        nested_branch="epic-OOMPAH-770",
        nested_head="a" * 40,
        private_branch="epic-OOMPAH-770--task-OOMPAH-796",
        private_remote_head="a" * 40,
        private_local_head="a" * 40,
    )
    orchestrator.project_store.observe_nested_dispatch_topology.return_value = topology

    def reachable(*_args, **kwargs):
        ancestor = kwargs["ancestor"]
        descendant = kwargs["descendant"]
        return ancestor == descendant

    orchestrator.project_store.nested_dispatch_head_reachable.side_effect = reachable
    return orchestrator, tracker, child, nested, topology


def test_oompah_770_796_old_main_base_fails_closed_with_exact_heads(tmp_path):
    orchestrator, _tracker, child, _nested, topology = (
        _oompah_770_796_fixture(tmp_path)
    )

    evidence = orchestrator._preflight_nested_epic_dispatch(
        child,
        allow_repair=False,
    )

    assert evidence is not None
    assert evidence.ready is False
    assert evidence.reason_code == "nested_epic_base_stale"
    assert evidence.topology == topology
    assert evidence.required_heads == (
        ("OOMPAH-785", "d" * 40, evidence.required_heads[0][2]),
    )
    assert evidence.missing == ("epic-OOMPAH-763", "OOMPAH-785")
    assert child.integration is not None
    assert child.integration.wait_reason == "nested_epic_base_stale"
    assert child.integration.wait_generation == evidence.generation
    assert child.integration.required_base_missing == evidence.missing


def test_repaired_oompah_770_lineage_clears_restart_wait_and_resumes(tmp_path):
    orchestrator, _tracker, child, _nested, _topology = (
        _oompah_770_796_fixture(tmp_path)
    )
    child.integration = IntegrationRecord(
        state="working",
        last_error="unrelated retained diagnostic",
    )
    waiting = orchestrator._preflight_nested_epic_dispatch(
        child,
        allow_repair=False,
    )
    assert waiting is not None and not waiting.ready
    repaired = NestedDispatchTopology(
        target_branch="epic-OOMPAH-763",
        target_head="f" * 40,
        nested_branch="epic-OOMPAH-770",
        nested_head="f" * 40,
        private_branch="epic-OOMPAH-770--task-OOMPAH-796",
        private_remote_head="f" * 40,
        private_local_head="f" * 40,
    )
    orchestrator.project_store.observe_nested_dispatch_topology.return_value = repaired
    orchestrator.project_store.nested_dispatch_head_reachable.side_effect = None
    orchestrator.project_store.nested_dispatch_head_reachable.return_value = True

    resumed = orchestrator._preflight_nested_epic_dispatch(
        child,
        allow_repair=False,
    )

    assert resumed is not None and resumed.ready
    assert child.integration is not None
    assert child.integration.wait_reason is None
    assert child.integration.wait_generation is None
    assert child.integration.required_base_missing == ()
    assert child.integration.last_error == "unrelated retained diagnostic"
    assert orchestrator._should_dispatch(child) is True


def test_standalone_and_top_level_children_do_not_enter_nested_fence(tmp_path):
    orchestrator, tracker, _child, nested, _topology = (
        _oompah_770_796_fixture(tmp_path)
    )
    standalone = _issue("OOMPAH-900")
    top_level_child = _issue("OOMPAH-901", parent_id=nested.identifier)
    top_level_epic = replace(nested, parent_id=None, start_blocked_by=[])
    tracker.fetch_issue_detail.side_effect = lambda identifier: (
        top_level_epic if identifier == top_level_epic.identifier else None
    )

    assert orchestrator._collect_nested_dispatch_evidence(standalone) is None
    assert orchestrator._collect_nested_dispatch_evidence(top_level_child) is None
    orchestrator.project_store.observe_nested_dispatch_topology.assert_not_called()


def test_wrong_immediate_parent_target_fails_closed(tmp_path):
    orchestrator, _tracker, child, _nested, _topology = (
        _oompah_770_796_fixture(tmp_path)
    )
    orchestrator._resolve_epic_target_branch = MagicMock(return_value="main")

    evidence = orchestrator._collect_nested_dispatch_evidence(child)

    assert evidence is not None and not evidence.ready
    assert evidence.reason_code == "nested_lineage_unavailable"
    assert "expected epic-OOMPAH-763" in (evidence.detail or "")


def test_dependency_head_change_invalidates_status_claim_generation(tmp_path):
    orchestrator, tracker, child, _nested, _topology = (
        _oompah_770_796_fixture(tmp_path)
    )
    admitted = orchestrator._collect_nested_dispatch_evidence(child)
    assert admitted is not None
    dependency = tracker.fetch_issue_detail("OOMPAH-785")
    dependency.integration = IntegrationRecord(
        state="integrated",
        integrated_sha="e" * 40,
    )
    orchestrator.project_store.nested_dispatch_head_reachable.side_effect = None
    orchestrator.project_store.nested_dispatch_head_reachable.return_value = True
    orchestrator.project_store.project_write_lock.return_value = MagicMock(
        __enter__=MagicMock(return_value=None),
        __exit__=MagicMock(return_value=False),
    )

    accepted, _fresh = orchestrator._write_in_progress_if_scheduler_authorized(
        tracker,
        child,
        expected_nested_generation=admitted.generation,
    )

    assert accepted is False
    tracker.update_issue.assert_not_called()


@pytest.mark.parametrize("failure", [None, RuntimeError("tracker down")])
def test_declared_nested_parent_lookup_fails_closed(tmp_path, failure):
    orchestrator, tracker, child, _nested, _topology = (
        _oompah_770_796_fixture(tmp_path)
    )
    if failure is None:
        tracker.fetch_issue_detail.side_effect = lambda identifier: (
            child if identifier == child.identifier else None
        )
    else:
        tracker.fetch_issue_detail.side_effect = failure

    evidence = orchestrator._preflight_nested_epic_dispatch(
        child,
        allow_repair=False,
    )

    assert evidence is not None
    assert evidence.ready is False
    assert evidence.reason_code == "nested_lineage_unavailable"
    orchestrator.project_store.create_worktree.assert_not_called()
    orchestrator.project_store.create_epic_worktree.assert_not_called()


def test_inherited_hard_start_refresh_error_does_not_use_cached_terminal_state(
    tmp_path,
):
    orchestrator, tracker, child, _nested, _topology = (
        _oompah_770_796_fixture(tmp_path)
    )
    original = tracker.fetch_issue_detail.side_effect

    def fetch(identifier):
        if identifier == "OOMPAH-785":
            raise RuntimeError("fresh dependency read failed")
        return original(identifier)

    tracker.fetch_issue_detail.side_effect = fetch

    evidence = orchestrator._preflight_nested_epic_dispatch(
        child,
        allow_repair=False,
    )

    assert evidence is not None
    assert evidence.ready is False
    assert evidence.reason_code == "nested_lineage_unavailable"


def test_preclaim_dispatch_fence_creates_no_claim_worker_or_provider(tmp_path):
    orchestrator, _tracker, child, _nested, topology = (
        _oompah_770_796_fixture(tmp_path)
    )
    evidence = NestedDispatchEvidence(
        project_id="proj-1",
        task_id=child.identifier,
        task_authority="task-generation",
        nested_epic_id="OOMPAH-770",
        nested_authority="nested-generation",
        target_epic_id="OOMPAH-763",
        target_authority="target-generation",
        topology=topology,
        required_heads=(),
        topology_generation="topology-generation",
        generation="generation",
        ready=False,
        reason_code="nested_epic_base_stale",
    )
    orchestrator._preflight_nested_epic_dispatch = MagicMock(return_value=evidence)
    orchestrator._run_worker = MagicMock()

    admitted = asyncio.run(orchestrator._dispatch(child, attempt=None))

    assert admitted is False
    assert child.id not in orchestrator.state.claimed
    assert child.id not in orchestrator.state.running
    orchestrator._run_worker.assert_not_called()
    orchestrator.project_store.create_worktree.assert_not_called()


def test_status_claim_rechecks_exact_generation_under_project_fence(tmp_path):
    orchestrator, tracker, child, _nested, topology = (
        _oompah_770_796_fixture(tmp_path)
    )
    current = orchestrator._collect_nested_dispatch_evidence(child)
    assert current is not None
    changed = replace(
        current,
        generation="new-generation",
        ready=True,
        reason_code="nested_dispatch_reachable",
    )
    orchestrator._collect_nested_dispatch_evidence = MagicMock(return_value=changed)
    orchestrator.project_store.project_write_lock.return_value = MagicMock(
        __enter__=MagicMock(return_value=None),
        __exit__=MagicMock(return_value=False),
    )

    admitted, _fresh = orchestrator._write_in_progress_if_scheduler_authorized(
        tracker,
        child,
        expected_nested_generation=current.generation,
    )

    assert admitted is False
    tracker.update_issue.assert_not_called()


def test_workspace_rechecks_topology_before_any_allocation(tmp_path):
    orchestrator, _tracker, child, _nested, topology = (
        _oompah_770_796_fixture(tmp_path)
    )
    blocked = NestedDispatchEvidence(
        project_id="proj-1",
        task_id=child.identifier,
        task_authority="task",
        nested_epic_id="OOMPAH-770",
        nested_authority="nested",
        target_epic_id="OOMPAH-763",
        target_authority="target",
        topology=topology,
        required_heads=(),
        topology_generation="topology",
        generation="generation",
        ready=False,
        reason_code="nested_epic_base_stale",
    )
    orchestrator._preflight_nested_epic_dispatch = MagicMock(return_value=blocked)

    with pytest.raises(ProjectError, match="before workspace allocation"):
        orchestrator._create_workspace_for_issue(
            child,
            expected_nested_topology_generation="admitted-topology",
        )

    orchestrator.project_store.create_worktree.assert_not_called()
    orchestrator.project_store.create_epic_worktree.assert_not_called()


def test_worker_rechecks_topology_before_focus_or_provider_contact(tmp_path):
    orchestrator, _tracker, child, _nested, topology = (
        _oompah_770_796_fixture(tmp_path)
    )
    blocked = NestedDispatchEvidence(
        project_id="proj-1",
        task_id=child.identifier,
        task_authority="task",
        nested_epic_id="OOMPAH-770",
        nested_authority="nested",
        target_epic_id="OOMPAH-763",
        target_authority="target",
        topology=topology,
        required_heads=(),
        topology_generation="changed-topology",
        generation="changed-generation",
        ready=False,
        reason_code="nested_epic_base_stale",
    )
    orchestrator._preflight_nested_epic_dispatch = MagicMock(return_value=blocked)
    focus_selector = AsyncMock()

    with (
        patch("oompah.orchestrator.select_focus_async", focus_selector),
        pytest.raises(ProjectError, match="before provider admission"),
    ):
        asyncio.run(
            orchestrator._run_worker(
                child,
                attempt=None,
                expected_nested_topology_generation="admitted-topology",
            )
        )

    focus_selector.assert_not_awaited()


@pytest.mark.parametrize("transport", ["api", "acp", "cli"])
def test_worker_forwards_nested_topology_generation_to_transport(
    tmp_path,
    transport,
):
    orchestrator, _tracker, child, _nested, _topology = (
        _oompah_770_796_fixture(tmp_path)
    )
    admitted = orchestrator._collect_nested_dispatch_evidence(child)
    assert admitted is not None
    admitted = replace(
        admitted,
        ready=True,
        topology_generation="admitted-topology",
        reason_code="nested_dispatch_reachable",
    )
    orchestrator._preflight_nested_epic_dispatch = MagicMock(
        return_value=admitted
    )
    profile = MagicMock(mode=transport, model=None)
    orchestrator._reserve_auditor_for_contributor = AsyncMock(
        return_value=([], None)
    )
    orchestrator._stage_work_contributor_launch = AsyncMock(return_value=None)

    if transport == "cli":
        worker = orchestrator._run_cli_worker = AsyncMock()
    else:
        target = MagicMock()
        target.provider.mode = transport
        target.candidate_key = f"{transport}/model"
        target.role_name = None
        target.candidate = None
        orchestrator._resolve_dispatch_targets = MagicMock(return_value=[target])
        orchestrator._apply_project_provider_whitelist = MagicMock(
            return_value=([target], False)
        )
        orchestrator._reserve_auditor_for_contributor = AsyncMock(
            return_value=([target], None)
        )
        orchestrator._candidate_preflight = MagicMock(return_value=None)
        if transport == "api":
            worker = orchestrator._run_api_worker = AsyncMock()
        else:
            worker = orchestrator._run_acp_worker = AsyncMock()

    asyncio.run(
        orchestrator._run_worker(
            child,
            attempt=None,
            profile=profile,
            expected_nested_topology_generation="admitted-topology",
        )
    )

    assert worker.await_count == 1
    assert (
        worker.await_args.kwargs["expected_nested_topology_generation"]
        == "admitted-topology"
    )


def test_durable_repair_is_idempotent_and_recoverable_after_expired_lease(tmp_path):
    orchestrator, _tracker, child, _nested, topology = (
        _oompah_770_796_fixture(tmp_path)
    )
    evidence = orchestrator._collect_nested_dispatch_evidence(child)
    assert evidence is not None and not evidence.ready
    unrelated = WorkflowJobSpec(
        project_id="proj-1",
        task_id=child.identifier,
        generation="unrelated-generation",
        action="unrelated_workflow_action",
        idempotency_key="unrelated-workflow-action",
        reason_code="unrelated",
        payload={},
    )
    orchestrator.workflow_job_store.enqueue(unrelated)

    orchestrator._schedule_nested_dispatch_repair(evidence)
    orchestrator._schedule_nested_dispatch_repair(evidence)
    jobs = orchestrator.workflow_job_store.list_jobs(
        project_id="proj-1",
        task_id=child.identifier,
        actions=("nested_dispatch_topology_repair",),
    )
    assert len(jobs) == 1
    unrelated_jobs = orchestrator.workflow_job_store.list_jobs(
        project_id="proj-1",
        task_id=child.identifier,
        actions=("unrelated_workflow_action",),
    )
    assert len(unrelated_jobs) == 1
    assert unrelated_jobs[0].state is WorkflowJobState.QUEUED

    claimed = orchestrator.workflow_job_store.claim_next(
        lease_owner="crashed-process",
        lease_seconds=1,
        project_id="proj-1",
        task_id=child.identifier,
        generation=evidence.generation,
        actions=("nested_dispatch_topology_repair",),
        now=time.time(),
    )
    assert claimed is not None
    recovered = orchestrator.workflow_job_store.claim_next(
        lease_owner="restarted-process",
        lease_seconds=60,
        project_id="proj-1",
        task_id=child.identifier,
        generation=evidence.generation,
        actions=("nested_dispatch_topology_repair",),
        now=time.time() + 2,
    )
    assert recovered is not None
    assert recovered.job_id == claimed.job_id
    assert recovered.attempts == 2
    assert recovered.state is WorkflowJobState.RUNNING


def test_exact_repair_job_mutates_topology_once(tmp_path):
    orchestrator, tracker, child, _nested, topology = (
        _oompah_770_796_fixture(tmp_path)
    )
    evidence = orchestrator._collect_nested_dispatch_evidence(child)
    assert evidence is not None and not evidence.ready
    repaired = replace(
        topology,
        nested_head=topology.target_head,
        private_remote_head=topology.target_head,
        private_local_head=topology.target_head,
    )
    orchestrator._schedule_nested_dispatch_repair(evidence)
    orchestrator._collect_nested_dispatch_evidence = MagicMock(
        return_value=evidence
    )
    orchestrator.project_store.advance_nested_dispatch_topology.return_value = repaired
    orchestrator.project_store.project_write_lock.return_value = MagicMock(
        __enter__=MagicMock(return_value=None),
        __exit__=MagicMock(return_value=False),
    )
    tracker.fetch_issue_detail.return_value = child

    orchestrator._drive_nested_dispatch_repair(evidence)
    orchestrator._drive_nested_dispatch_repair(evidence)

    orchestrator.project_store.advance_nested_dispatch_topology.assert_called_once_with(
        "proj-1",
        expected=topology,
    )
    jobs = orchestrator.workflow_job_store.list_jobs(
        project_id="proj-1",
        task_id=child.identifier,
        actions=("nested_dispatch_topology_repair",),
    )
    assert len(jobs) == 1
    assert jobs[0].state is WorkflowJobState.COMPLETED


def test_preflight_repairs_inside_running_implementation_lease(tmp_path):
    """The pre-effect implementation owner cannot deadlock its own repair."""

    orchestrator, tracker, child, _nested, topology = (
        _oompah_770_796_fixture(tmp_path)
    )
    evidence = orchestrator._collect_nested_dispatch_evidence(child)
    assert evidence is not None and not evidence.ready
    implementation = WorkflowJobSpec(
        project_id="proj-1",
        task_id=child.identifier,
        generation="implementation-generation",
        action="implementation_start",
        idempotency_key="implementation-start",
        reason_code="dispatch.eligible",
        payload={},
    )
    orchestrator.workflow_job_store.enqueue(implementation)
    running = orchestrator.workflow_job_store.claim_next(
        lease_owner="implementation-runtime",
        lease_seconds=60,
        project_id="proj-1",
        task_id=child.identifier,
        actions=("implementation_start",),
    )
    assert running is not None
    repaired = replace(
        topology,
        nested_head=topology.target_head,
        private_remote_head=topology.target_head,
        private_local_head=topology.target_head,
    )
    observations = iter(
        (
            evidence,
            evidence,
            evidence,
            replace(evidence, topology=repaired, ready=True),
        )
    )
    orchestrator._collect_nested_dispatch_evidence = MagicMock(
        side_effect=lambda _issue: next(observations)
    )
    orchestrator.project_store.advance_nested_dispatch_topology.return_value = repaired
    orchestrator.project_store.project_write_lock.return_value = MagicMock(
        __enter__=MagicMock(return_value=None),
        __exit__=MagicMock(return_value=False),
    )
    tracker.fetch_issue_detail.return_value = child

    admitted = orchestrator._preflight_nested_epic_dispatch(child)

    assert admitted is not None and admitted.ready
    repairs = orchestrator.workflow_job_store.list_jobs(
        project_id="proj-1",
        task_id=child.identifier,
        actions=("nested_dispatch_topology_repair",),
    )
    assert len(repairs) == 1
    assert repairs[0].state is WorkflowJobState.COMPLETED
    assert orchestrator.workflow_job_store.get(running.job_id).state is WorkflowJobState.RUNNING


def test_startup_recovery_wakes_queued_repair_and_clears_wait(tmp_path):
    orchestrator, _tracker, child, _nested, topology = (
        _oompah_770_796_fixture(tmp_path)
    )
    waiting = orchestrator._preflight_nested_epic_dispatch(
        child,
        allow_repair=False,
    )
    assert waiting is not None and not waiting.ready
    orchestrator._schedule_nested_dispatch_repair(waiting)
    repaired = replace(
        topology,
        nested_head=topology.target_head,
        private_remote_head=topology.target_head,
        private_local_head=topology.target_head,
    )

    def advance(*_args, **_kwargs):
        orchestrator.project_store.observe_nested_dispatch_topology.return_value = (
            repaired
        )
        orchestrator.project_store.nested_dispatch_head_reachable.side_effect = None
        orchestrator.project_store.nested_dispatch_head_reachable.return_value = True
        return repaired

    orchestrator.project_store.advance_nested_dispatch_topology.side_effect = advance
    orchestrator._post_dispatch_refresh = MagicMock()

    result = orchestrator._recover_queued_nested_dispatch_repairs()

    jobs = orchestrator.workflow_job_store.list_jobs(
        project_id="proj-1",
        task_id=child.identifier,
        actions=("nested_dispatch_topology_repair",),
    )
    assert result == {
        "examined": 1,
        "driven": 1,
        "retired": 0,
        "waits_cleared": 1,
        "skipped_paused": 0,
        "failures": 0,
    }
    assert jobs[0].state is WorkflowJobState.COMPLETED
    assert child.integration is not None
    assert child.integration.wait_reason is None
    orchestrator._post_dispatch_refresh.assert_called_once_with()


def test_first_wait_materializes_repair_with_stabilized_task_authority(tmp_path):
    orchestrator, _tracker, child, _nested, _topology = (
        _oompah_770_796_fixture(tmp_path)
    )
    orchestrator._drive_nested_dispatch_repair = MagicMock(return_value=False)

    evidence = orchestrator._preflight_nested_epic_dispatch(child)

    assert evidence is not None and not evidence.ready
    jobs = orchestrator.workflow_job_store.list_jobs(
        project_id="proj-1",
        task_id=child.identifier,
        actions=("nested_dispatch_topology_repair",),
    )
    assert len(jobs) == 1
    assert jobs[0].generation == evidence.generation
    assert child.integration is not None
    assert child.integration.wait_generation == evidence.generation


def test_startup_recovery_leaves_paused_project_repair_untouched(tmp_path):
    orchestrator, _tracker, child, _nested, _topology = (
        _oompah_770_796_fixture(tmp_path)
    )
    evidence = orchestrator._collect_nested_dispatch_evidence(child)
    assert evidence is not None
    orchestrator._schedule_nested_dispatch_repair(evidence)
    orchestrator.project_store.list_all.return_value[0].paused = True
    orchestrator._post_dispatch_refresh = MagicMock()

    result = orchestrator._recover_queued_nested_dispatch_repairs()

    jobs = orchestrator.workflow_job_store.list_jobs(
        project_id="proj-1",
        task_id=child.identifier,
        actions=("nested_dispatch_topology_repair",),
    )
    assert result["examined"] == 0
    assert result["skipped_paused"] == 1
    assert jobs[0].state is WorkflowJobState.QUEUED
    orchestrator.project_store.advance_nested_dispatch_topology.assert_not_called()
    orchestrator._post_dispatch_refresh.assert_not_called()


def test_startup_recovery_supersedes_stale_topology_generation(tmp_path):
    orchestrator, _tracker, child, _nested, topology = (
        _oompah_770_796_fixture(tmp_path)
    )
    stale = orchestrator._collect_nested_dispatch_evidence(child)
    assert stale is not None
    orchestrator._schedule_nested_dispatch_repair(stale)
    changed = replace(topology, nested_head="b" * 40)
    orchestrator.project_store.observe_nested_dispatch_topology.return_value = changed
    fresh = orchestrator._collect_nested_dispatch_evidence(child)
    assert fresh is not None and fresh.generation != stale.generation
    orchestrator._post_dispatch_refresh = MagicMock()

    result = orchestrator._recover_queued_nested_dispatch_repairs()

    jobs = orchestrator.workflow_job_store.list_jobs(
        project_id="proj-1",
        task_id=child.identifier,
        actions=("nested_dispatch_topology_repair",),
    )
    assert result["retired"] == 1
    assert result["driven"] == 1
    assert len(jobs) == 2
    assert jobs[0].state is WorkflowJobState.SUPERSEDED
    assert jobs[0].superseded_by_generation == jobs[1].generation
    assert jobs[1].generation not in {stale.generation, fresh.generation}
    orchestrator.project_store.advance_nested_dispatch_topology.assert_called_once()
    orchestrator._post_dispatch_refresh.assert_called_once_with()


def test_startup_recovery_preserves_retry_backoff(tmp_path):
    orchestrator, _tracker, child, _nested, _topology = (
        _oompah_770_796_fixture(tmp_path)
    )
    evidence = orchestrator._collect_nested_dispatch_evidence(child)
    assert evidence is not None
    orchestrator._schedule_nested_dispatch_repair(evidence)
    claimed = orchestrator.workflow_job_store.claim_next(
        lease_owner="failed-repair",
        lease_seconds=60,
        project_id="proj-1",
        task_id=child.identifier,
        actions=("nested_dispatch_topology_repair",),
    )
    assert claimed is not None and claimed.lease_token
    retry = orchestrator.workflow_job_store.fail(
        claimed.job_id,
        claimed.lease_token,
        category="transient",
        error="temporary topology failure",
        retryable=True,
        retry_delay_seconds=3600,
    )
    orchestrator._post_dispatch_refresh = MagicMock()

    result = orchestrator._recover_queued_nested_dispatch_repairs()

    unchanged = orchestrator.workflow_job_store.get(claimed.job_id)
    assert result["examined"] == 1
    assert result["driven"] == 0
    assert unchanged.state is WorkflowJobState.RETRY_WAIT
    assert unchanged.retry_at == retry.retry_at
    assert unchanged.attempts == retry.attempts
    orchestrator._post_dispatch_refresh.assert_not_called()


def test_startup_recovery_is_bounded_and_ignores_unrelated_jobs(tmp_path):
    orchestrator, _tracker, child, _nested, _topology = (
        _oompah_770_796_fixture(tmp_path)
    )
    for index in range(2):
        orchestrator.workflow_job_store.enqueue(
            WorkflowJobSpec(
                project_id="proj-1",
                task_id=f"missing-{index}",
                generation=f"generation-{index}",
                action="nested_dispatch_topology_repair",
                idempotency_key=f"nested-repair-{index}",
            )
        )
    unrelated = orchestrator.workflow_job_store.enqueue(
        WorkflowJobSpec(
            project_id="proj-1",
            task_id=child.identifier,
            generation="unrelated-generation",
            action="unrelated_workflow_action",
            idempotency_key="unrelated-startup-work",
        )
    )
    orchestrator._post_dispatch_refresh = MagicMock()

    result = orchestrator._recover_queued_nested_dispatch_repairs(limit=1)

    repairs = orchestrator.workflow_job_store.list_jobs(
        project_id="proj-1",
        actions=("nested_dispatch_topology_repair",),
    )
    assert result["examined"] == 1
    assert [job.state for job in repairs] == [
        WorkflowJobState.CANCELLED,
        WorkflowJobState.QUEUED,
    ]
    assert orchestrator.workflow_job_store.get(unrelated.job_id).state is (
        WorkflowJobState.QUEUED
    )


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _topology_repo(tmp_path):
    remote = tmp_path / "remote.git"
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True)
    subprocess.run(["git", "clone", str(remote), str(repo)], check=True)
    _git(repo, "config", "user.name", "Topology Test")
    _git(repo, "config", "user.email", "topology@example.com")
    (repo / "base.txt").write_text("old main\n", encoding="utf-8")
    _git(repo, "add", "base.txt")
    _git(repo, "commit", "-m", "old main")
    _git(repo, "branch", "-M", "main")
    old = _git(repo, "rev-parse", "HEAD")
    for branch in (
        "epic-OOMPAH-763",
        "epic-OOMPAH-770",
        "epic-OOMPAH-770--task-OOMPAH-796",
    ):
        _git(repo, "branch", branch, old)
        _git(repo, "push", "origin", branch)
    _git(repo, "checkout", "epic-OOMPAH-763")
    (repo / "work-decision.txt").write_text(
        "OOMPAH-785 landing\n",
        encoding="utf-8",
    )
    _git(repo, "add", "work-decision.txt")
    _git(repo, "commit", "-m", "land prerequisite contracts")
    target = _git(repo, "rev-parse", "HEAD")
    _git(repo, "push", "origin", "epic-OOMPAH-763")
    _git(repo, "checkout", "main")
    store = ProjectStore(
        path=str(tmp_path / "projects.json"),
        repos_root=str(tmp_path / "repos"),
        worktree_root=str(tmp_path / "worktrees"),
    )
    store._projects["proj-1"] = Project(
        id="proj-1",
        name="oompah",
        repo_url=str(remote),
        repo_path=str(repo),
        default_branch="main",
    )
    return store, repo, old, target


def test_project_store_repairs_nested_then_private_branch(tmp_path):
    store, repo, old, target = _topology_repo(tmp_path)
    expected = store.observe_nested_dispatch_topology(
        "proj-1",
        target_branch="epic-OOMPAH-763",
        nested_branch="epic-OOMPAH-770",
        private_branch="epic-OOMPAH-770--task-OOMPAH-796",
    )
    assert expected.nested_head == old
    assert expected.private_local_head == old
    assert expected.private_remote_head == old

    repaired = store.advance_nested_dispatch_topology(
        "proj-1",
        expected=expected,
    )

    assert repaired.nested_head == target
    assert repaired.private_local_head == target
    assert repaired.private_remote_head == target
    assert _git(repo, "rev-parse", "refs/heads/epic-OOMPAH-770") == target


def test_local_only_private_checkpoint_is_never_overwritten(tmp_path):
    store, repo, _old, _target = _topology_repo(tmp_path)
    private = "epic-OOMPAH-770--task-OOMPAH-796"
    _git(repo, "push", "origin", f":refs/heads/{private}")
    _git(repo, "checkout", private)
    (repo / "local-only.txt").write_text("preserve me\n", encoding="utf-8")
    _git(repo, "add", "local-only.txt")
    _git(repo, "commit", "-m", "local-only recovery checkpoint")
    local_head = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "main")
    expected = store.observe_nested_dispatch_topology(
        "proj-1",
        target_branch="epic-OOMPAH-763",
        nested_branch="epic-OOMPAH-770",
        private_branch=private,
    )
    assert expected.private_remote_head is None
    assert expected.private_local_head == local_head

    with pytest.raises(ProjectError, match="unique commits"):
        store.advance_nested_dispatch_topology("proj-1", expected=expected)

    assert _git(repo, "rev-parse", f"refs/heads/{private}") == local_head
    assert (
        subprocess.run(
            ["git", "ls-remote", "--heads", "origin", private],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        == ""
    )


def test_topology_repair_cas_rejects_concurrent_parent_advance(tmp_path):
    store, repo, _old, _target = _topology_repo(tmp_path)
    expected = store.observe_nested_dispatch_topology(
        "proj-1",
        target_branch="epic-OOMPAH-763",
        nested_branch="epic-OOMPAH-770",
        private_branch="epic-OOMPAH-770--task-OOMPAH-796",
    )
    _git(repo, "checkout", "epic-OOMPAH-763")
    (repo / "concurrent.txt").write_text("new generation\n", encoding="utf-8")
    _git(repo, "add", "concurrent.txt")
    _git(repo, "commit", "-m", "concurrent parent advance")
    _git(repo, "push", "origin", "epic-OOMPAH-763")
    _git(repo, "checkout", "main")

    with pytest.raises(ProjectError, match="generation changed"):
        store.advance_nested_dispatch_topology("proj-1", expected=expected)

    assert (
        _git(repo, "rev-parse", "refs/remotes/origin/epic-OOMPAH-770")
        == expected.nested_head
    )
