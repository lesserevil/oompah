"""Shared-decision and durable-job integration domain coverage."""

from __future__ import annotations

import os
import subprocess
from dataclasses import replace
from types import SimpleNamespace
import pytest

from oompah.integration import IntegrationRecord
from oompah.integration_queue import (
    STANDALONE_RECLASSIFICATION_REASON,
    IntegrationQueueStore,
)
from oompah.integration_executor import IntegrationExecutionResult
from oompah.integration_workflow import (
    INTEGRATION_ACTIONS,
    IntegrationActionHandler,
    OrchestratorIntegrationActionBackend,
    IntegrationRoute,
    IntegrationWorkflowController,
    IntegrationWorkflowHandler,
    classify_integration_result,
    schedule_project_historical_replay,
)
from oompah.models import BlockerRef, Issue
from oompah.statuses import IN_VALIDATION
from oompah.workflow_contract import READY_TO_INTEGRATE, TaskDisposition
from oompah.workflow_facts import (
    FactDomain,
    GitLandingCollector,
    LandingFact,
    LandingRequest,
    LandingState,
    WorkflowFactCollector,
)
from oompah.workflow_jobs import WorkflowJobSpec, WorkflowJobState, WorkflowJobStore
from oompah.work_decision import evaluate_task
from oompah.workflow_worker import (
    DurableWorkflowWorker,
    EffectObservation,
    EffectResult,
    RevalidationResult,
    VerificationResult,
    WorkflowActionDomain,
    WorkflowActionError,
    WorkflowActionSuperseded,
    WorkflowRunDisposition,
)


class Tracker:
    def __init__(self, issues):
        self.issues = {issue.identifier: issue for issue in issues}

    def fetch_issue_detail(self, identifier):
        return self.issues.get(identifier)

    def fetch_children(self, identifier):
        return [
            issue for issue in self.issues.values() if issue.parent_id == identifier
        ]

    def fetch_all_issues(self):
        return list(self.issues.values())


class RecordingActionBackend:
    def __init__(self):
        self.calls = []

    def revalidate_action(self, action, context):
        self.calls.append(("revalidate", action, context))
        return RevalidationResult("generation-1")

    def observe_action(self, action, context):
        self.calls.append(("observe", action, context))
        return EffectObservation(False)

    def apply_action(self, action, context):
        self.calls.append(("apply", action, context))
        return EffectResult({"action": action})

    def verify_action(self, action, context, effect):
        self.calls.append(("verify", action, context))
        return VerificationResult(True, effect.receipt)

    def build_action_transition(self, action, context, verification):
        self.calls.append(("transition", action, context))
        return None


@pytest.mark.asyncio
@pytest.mark.parametrize("action", sorted(INTEGRATION_ACTIONS))
async def test_action_handler_never_collapses_maintenance_into_integrate(action):
    backend = RecordingActionBackend()
    context = object()
    handler = IntegrationActionHandler(
        action,
        backend,
        domain=WorkflowActionDomain.GIT,
    )

    revalidation = await handler.revalidate(context)
    observation = await handler.inspect(context)
    effect = await handler.apply(context)
    verification = await handler.verify(context, effect)
    transition = await handler.build_transition(context, verification)

    assert revalidation.generation == "generation-1"
    assert not observation.applied
    assert effect.receipt == {"action": action}
    assert verification.verified
    assert transition is None
    assert [call[:2] for call in backend.calls] == [
        ("revalidate", action),
        ("observe", action),
        ("apply", action),
        ("verify", action),
        ("transition", action),
    ]


@pytest.mark.asyncio
async def test_production_standalone_handler_invokes_only_exact_task_scope():
    selected = issue("TASK-A")
    selected.parent_id = None
    selected.integration = replace(selected.integration, mode="standalone")
    sibling = issue("TASK-B")
    sibling.parent_id = None
    tracker = Tracker([selected, sibling])
    calls = []

    def deliver(
        project_id,
        task_id,
        *,
        expected_task_branch,
        expected_head_sha,
        workflow_generation,
        workflow_authority_check,
    ):
        calls.append(
            (
                project_id,
                task_id,
                expected_task_branch,
                expected_head_sha,
                workflow_generation,
                workflow_authority_check(),
            )
        )
        delivered = tracker.fetch_issue_detail(task_id)
        delivered.state = "In Review"
        delivered.review_number = "17"
        delivered.review_head = delivered.integration.head_sha

    fact_collector = collector(tracker)
    decision = evaluate_task(selected, fact_collector.collect("TASK-A"))
    assert decision.durable_jobs == ("standalone_delivery",)
    orchestrator = SimpleNamespace(
        _reconcile_one_standalone_ready_to_integrate_task=deliver,
    )
    binding = SimpleNamespace(
        project_id="project-1",
        tracker=tracker,
        collector=fact_collector,
    )
    backend = OrchestratorIntegrationActionBackend(orchestrator, binding)
    context = SimpleNamespace(
        job=SimpleNamespace(
            project_id="project-1",
            task_id="TASK-A",
            generation="generation-1",
            job_id="job-1",
            lease_token="lease-1",
            checkpoint={
                "revalidation": {
                    "evidence_revision": decision.evidence_revision,
                    "details": {
                        "task_branch": "TASK-A",
                        "task_head": "a" * 40,
                        "task_target": "main",
                    },
                }
            },
        ),
        check_interrupted=lambda: None,
    )

    effect = await backend.apply_action("standalone_delivery", context)

    assert calls == [
        (
            "project-1",
            "TASK-A",
            "TASK-A",
            "a" * 40,
            "job-1:generation-1:lease-1",
            True,
        )
    ]
    assert effect.receipt["review_number"] == "17"
    assert tracker.fetch_issue_detail("TASK-B").state == READY_TO_INTEGRATE
    selected.integration = replace(selected.integration, head_sha="b" * 40)
    assert not backend.verify_action(
        "standalone_delivery", context, effect
    ).verified


@pytest.mark.asyncio
async def test_standalone_delivery_rejects_replacement_after_revalidation():
    selected = issue("TASK-A")
    selected.parent_id = None
    selected.integration = replace(selected.integration, mode="standalone")
    tracker = Tracker([selected])
    fact_collector = collector(tracker)
    decision = evaluate_task(selected, fact_collector.collect("TASK-A"))
    deliveries = []
    backend = OrchestratorIntegrationActionBackend(
        SimpleNamespace(
            _reconcile_one_standalone_ready_to_integrate_task=(
                lambda *args, **kwargs: deliveries.append((args, kwargs))
            ),
        ),
        SimpleNamespace(
            project_id="project-1",
            tracker=tracker,
            collector=fact_collector,
        ),
    )
    context = SimpleNamespace(
        job=SimpleNamespace(
            project_id="project-1",
            task_id="TASK-A",
            generation="generation-1",
            checkpoint={
                "revalidation": {
                    "evidence_revision": decision.evidence_revision,
                    "details": {
                        "task_branch": "TASK-A",
                        "task_head": "a" * 40,
                    },
                }
            },
        ),
        check_interrupted=lambda: None,
    )
    selected.integration = replace(selected.integration, head_sha="b" * 40)

    with pytest.raises(WorkflowActionError, match="submission changed"):
        await backend.apply_action("standalone_delivery", context)

    observation = backend.observe_action("standalone_delivery", context)
    assert not observation.applied
    assert deliveries == []


def test_standalone_observation_requires_exact_review_and_target_receipt():
    selected = issue("TASK-A")
    selected.parent_id = None
    selected.target_branch = "release"
    selected.integration = replace(selected.integration, mode="standalone")
    selected.state = IN_VALIDATION
    tracker = Tracker([selected])
    backend = OrchestratorIntegrationActionBackend(
        SimpleNamespace(
            project_store=SimpleNamespace(
                get=lambda _project_id: SimpleNamespace(default_branch="main")
            )
        ),
        SimpleNamespace(project_id="project-1", tracker=tracker),
    )
    context = SimpleNamespace(
        job=SimpleNamespace(
            project_id="project-1",
            task_id="TASK-A",
            generation="generation-1",
            checkpoint={
                "revalidation": {
                    "details": {
                        "task_branch": "TASK-A",
                        "task_head": "a" * 40,
                        "task_target": "release",
                    }
                }
            },
        )
    )

    assert not backend.observe_action("standalone_delivery", context).applied

    selected.review_number = "42"
    selected.review_head = "a" * 40
    assert backend.observe_action("standalone_delivery", context).applied

    effect = EffectResult(
        {
            "review_number": "42",
            "review_head": "a" * 40,
            "target_branch": "release",
            "submission_branch": "TASK-A",
            "submission_head": "a" * 40,
        }
    )
    assert backend.verify_action(
        "standalone_delivery", context, effect
    ).verified

    selected.review_number = "43"
    assert not backend.verify_action(
        "standalone_delivery", context, effect
    ).verified
    selected.review_number = "42"

    selected.integration = replace(selected.integration, mode="queue")
    assert not backend.observe_action("standalone_delivery", context).applied
    selected.integration = replace(selected.integration, mode="standalone")

    selected.target_branch = "other-release"
    assert not backend.observe_action("standalone_delivery", context).applied


class MetadataTracker(Tracker):
    def set_metadata_field(self, identifier, field, value):
        assert field == "oompah.integration"
        self.issues[identifier].integration = IntegrationRecord.from_dict(value)


def landed_fact(*, revision="a" * 40, target_sha="c" * 40):
    return SimpleNamespace(
        state=LandingState.LANDED,
        revision=revision,
        proof={"kind": "git_ancestry", "target_sha": target_sha},
        to_dict=lambda: {
            "state": "landed",
            "revision": revision,
            "source": "TASK-A",
            "target": "epic/E-1",
            "proof": {"kind": "git_ancestry", "target_sha": target_sha},
        },
    )


def integration_backend_context(tmp_path, *, execute):
    task = issue("TASK-A", head="a" * 40)
    task.parent_id = "E-1"
    task.integration = replace(
        task.integration,
        mode="queue",
        base_branch="epic/E-1",
        base_sha="b" * 40,
    )
    tracker = MetadataTracker([task])
    queue = IntegrationQueueStore(str(tmp_path / "integration.sqlite3"))
    queued = queue.enqueue(
        project_id="project-1",
        epic_id="E-1",
        task_id="TASK-A",
        task_branch="TASK-A",
        head_sha="a" * 40,
        base_sha="b" * 40,
    )
    delivery = {"landed": False}

    def execute_and_observe(*args, **kwargs):
        result = execute(*args, **kwargs)
        if result.integrated:
            delivery["landed"] = True
        return result

    orchestrator = SimpleNamespace(
        integration_queue=queue,
        project_store=SimpleNamespace(
            epic_branch_name=lambda epic_id: f"epic/{epic_id}"
        ),
        _execute_integration_item=execute_and_observe,
    )
    fact_collector = collector(tracker)
    current_facts = fact_collector.collect(task.identifier)
    current_decision = evaluate_task(task, current_facts)
    binding = SimpleNamespace(
        project_id="project-1",
        tracker=tracker,
        collector=fact_collector,
    )
    backend = OrchestratorIntegrationActionBackend(orchestrator, binding)
    backend._landing = lambda issue: landed_fact() if delivery["landed"] else None
    context = SimpleNamespace(
        job=SimpleNamespace(
            project_id="project-1",
            task_id="TASK-A",
            generation="generation-1",
            job_id="job-1",
            idempotency_key="idempotency-1",
            checkpoint={
                "revalidation": {
                    "head_sha": "a" * 40,
                    "evidence_revision": current_decision.evidence_revision,
                    "details": {
                        "integration_queue_generation": queued.authority_generation(),
                        "integration_queue_branch": queued.task_branch,
                        "integration_queue_head": queued.head_sha,
                        "task_branch": queued.task_branch,
                        "task_head": queued.head_sha,
                        "task_parent": task.parent_id,
                    },
                },
            },
        ),
        check_interrupted=lambda: None,
    )
    return backend, context, queue, tracker


@pytest.mark.asyncio
async def test_workflow_integration_attempt_uses_job_authority_without_queue_lease(
    tmp_path,
):
    calls = []

    def execute(
        row,
        *,
        commit_allowed,
        gate_generation,
        retry_forced,
        rebase_intent_prepare,
        rebase_intent_abort,
        rebased_head_prepare,
        rebased_head_checkpoint,
    ):
        calls.append(
            (row.state, row.lease_owner, gate_generation, retry_forced)
        )
        assert commit_allowed()
        return IntegrationExecutionResult(
            "integrated",
            "landed",
            expected_epic_sha="b" * 40,
            rebased_task_sha="a" * 40,
            integrated_sha="c" * 40,
        )

    backend, context, queue, tracker = integration_backend_context(
        tmp_path, execute=execute
    )

    effect = await backend.apply_action("integration_attempt", context)
    verification = backend.verify_action("integration_attempt", context, effect)

    assert calls == [
        ("ready", None, "workflow:job-1:generation-1", False)
    ]
    assert queue.get("project-1", "TASK-A").state == "integrated"
    assert queue.get("project-1", "TASK-A").integrated_sha == "c" * 40
    assert tracker.fetch_issue_detail("TASK-A").integration.state == "integrated"
    assert effect.receipt["route"] == "landed"
    assert verification.verified


def test_exact_queue_authority_rejects_late_tracker_state_change(tmp_path):
    backend, context, queue, tracker = integration_backend_context(
        tmp_path,
        execute=lambda *_args, **_kwargs: None,
    )
    row = queue.get("project-1", "TASK-A")
    assert row is not None
    assert backend._exact_authority(
        context,
        queue_generation=row.authority_generation(),
        task_branch=row.task_branch,
        head_sha=row.head_sha,
    )

    task = tracker.fetch_issue_detail("TASK-A")
    task.integration = replace(task.integration, state="blocked")

    assert not backend._exact_authority(
        context,
        queue_generation=row.authority_generation(),
        task_branch=row.task_branch,
        head_sha=row.head_sha,
    )


@pytest.mark.asyncio
async def test_integration_attempt_rechecks_evidence_for_same_queue_generation(
    tmp_path,
):
    executed = []
    backend, context, queue, tracker = integration_backend_context(
        tmp_path,
        execute=lambda row, **kwargs: executed.append(row),
    )
    queued = queue.get("project-1", "TASK-A")
    tracker.fetch_issue_detail("TASK-A").target_branch = "release"

    with pytest.raises(WorkflowActionError, match="evidence changed"):
        await backend.apply_action("integration_attempt", context)

    assert executed == []
    assert queue.get("project-1", "TASK-A") == queued


@pytest.mark.asyncio
async def test_scheduled_integration_attempt_recovers_missing_queue_row(tmp_path):
    task = issue("TASK-A", head="a" * 40)
    task.parent_id = "E-1"
    task.integration = replace(
        task.integration,
        mode="queue",
        base_branch="epic/E-1",
    )
    tracker = MetadataTracker([task])
    fact_collector = collector(tracker)
    decision = evaluate_task(task, fact_collector.collect(task.identifier))
    assert decision.durable_jobs == ("integration_attempt",)
    jobs = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    controller = IntegrationWorkflowController(
        collector=fact_collector,
        store=jobs,
    )
    _batch, scheduled = controller.reconcile([task])
    assert scheduled.jobs_created == 1
    assert jobs.list_jobs()[0].action == "integration_attempt"
    jobs.close()
    queue = IntegrationQueueStore(str(tmp_path / "integration.sqlite3"))
    executed = []

    def execute(row, **_kwargs):
        executed.append((row.epic_id, row.task_branch, row.head_sha))
        return IntegrationExecutionResult(
            "integrated",
            "landed after queue recovery",
            expected_epic_sha="b" * 40,
            rebased_task_sha=row.head_sha,
            integrated_sha="c" * 40,
        )

    orchestrator = SimpleNamespace(
        integration_queue=queue,
        project_store=SimpleNamespace(
            epic_branch_name=lambda epic_id: f"epic/{epic_id}"
        ),
        _execute_integration_item=execute,
    )
    backend = OrchestratorIntegrationActionBackend(
        orchestrator,
        SimpleNamespace(
            project_id="project-1",
            tracker=tracker,
            collector=fact_collector,
        ),
    )
    backend._landing = lambda _issue: None
    context = SimpleNamespace(
        job=SimpleNamespace(
            project_id="project-1",
            task_id=task.identifier,
            generation="generation-1",
            job_id="job-1",
            checkpoint={
                "revalidation": {
                    "evidence_revision": decision.evidence_revision,
                    "details": {
                        "integration_queue_present": False,
                        "task_branch": task.integration.task_branch,
                        "task_head": task.integration.head_sha,
                    },
                }
            },
        ),
        check_interrupted=lambda: None,
    )

    effect = await backend.apply_action("integration_attempt", context)

    assert executed == [("E-1", "TASK-A", "a" * 40)]
    recovered = queue.get("project-1", task.identifier)
    assert recovered is not None
    assert recovered.state == "integrated"
    assert recovered.epic_id == "E-1"
    assert effect.receipt["route"] == "landed"


@pytest.mark.asyncio
async def test_integration_attempt_rehomes_exact_row_after_task_reparent(tmp_path):
    task = issue("TASK-A", head="a" * 40)
    task.parent_id = "E-NEW"
    task.integration = replace(
        task.integration,
        mode="queue",
        base_branch="epic/E-NEW",
    )
    tracker = MetadataTracker([task])
    fact_collector = collector(tracker)
    decision = evaluate_task(task, fact_collector.collect(task.identifier))
    queue = IntegrationQueueStore(str(tmp_path / "integration.sqlite3"))
    stale = queue.enqueue(
        project_id="project-1",
        epic_id="E-OLD",
        task_id=task.identifier,
        task_branch=task.integration.task_branch,
        head_sha=task.integration.head_sha,
    )
    executed = []

    def execute(row, **_kwargs):
        executed.append(row.epic_id)
        return IntegrationExecutionResult("ci_failure", "focused gate failed")

    orchestrator = SimpleNamespace(
        integration_queue=queue,
        project_store=SimpleNamespace(
            epic_branch_name=lambda epic_id: f"epic/{epic_id}"
        ),
        _execute_integration_item=execute,
    )
    backend = OrchestratorIntegrationActionBackend(
        orchestrator,
        SimpleNamespace(
            project_id="project-1",
            tracker=tracker,
            collector=fact_collector,
        ),
    )
    backend._landing = lambda _issue: None
    context = SimpleNamespace(
        job=SimpleNamespace(
            project_id="project-1",
            task_id=task.identifier,
            generation="generation-1",
            job_id="job-1",
            checkpoint={
                "revalidation": {
                    "evidence_revision": decision.evidence_revision,
                    "details": {
                        "integration_queue_present": True,
                        "integration_queue_generation": (
                            stale.authority_generation()
                        ),
                        "integration_queue_epic": stale.epic_id,
                        "integration_queue_branch": stale.task_branch,
                        "integration_queue_head": stale.head_sha,
                        "task_parent": task.parent_id,
                        "task_branch": task.integration.task_branch,
                        "task_head": task.integration.head_sha,
                    },
                }
            },
        ),
        check_interrupted=lambda: None,
    )

    effect = await backend.apply_action("integration_attempt", context)

    current = queue.get("project-1", task.identifier)
    assert executed == ["E-NEW"]
    assert current is not None
    assert current.epic_id == "E-NEW"
    assert current.state == "blocked"
    assert effect.receipt["route"] == "ci_fix"


@pytest.mark.asyncio
async def test_reparented_queue_normalizes_target_before_landing_shortcut(tmp_path):
    task = issue("TASK-A", head="a" * 40)
    task.parent_id = "E-NEW"
    task.integration = replace(
        task.integration,
        mode="standalone",
        base_branch="epic/E-OLD",
        base_sha="b" * 40,
    )
    tracker = MetadataTracker([task])
    fact_collector = collector(tracker)
    decision = evaluate_task(task, fact_collector.collect(task.identifier))
    queue = IntegrationQueueStore(str(tmp_path / "integration.sqlite3"))
    stale = queue.enqueue(
        project_id="project-1",
        epic_id="E-OLD",
        task_id=task.identifier,
        task_branch=task.integration.task_branch,
        head_sha=task.integration.head_sha,
        base_sha=task.integration.base_sha,
    )
    executed = []
    orchestrator = SimpleNamespace(
        integration_queue=queue,
        project_store=SimpleNamespace(
            epic_branch_name=lambda epic_id: f"epic/{epic_id}"
        ),
        _execute_integration_item=lambda row, **kwargs: executed.append(row),
        request_refresh=lambda: None,
    )
    backend = OrchestratorIntegrationActionBackend(
        orchestrator,
        SimpleNamespace(
            project_id="project-1",
            tracker=tracker,
            collector=fact_collector,
        ),
    )
    backend._landing = lambda current: (
        LandingFact(
            current.integration.task_branch,
            current.integration.base_branch,
            current.integration.head_sha,
            {"kind": "git_ancestry", "target_sha": "c" * 40},
            "2026-08-05T00:00:00+00:00",
            "project-1",
            state=LandingState.LANDED,
        )
        if current.integration.base_branch == "epic/E-OLD"
        else None
    )
    context = SimpleNamespace(
        job=SimpleNamespace(
            project_id="project-1",
            task_id=task.identifier,
            generation="generation-1",
            job_id="job-1",
            checkpoint={
                "revalidation": {
                    "evidence_revision": decision.evidence_revision,
                    "details": {
                        "integration_queue_present": True,
                        "integration_queue_generation": stale.authority_generation(),
                        "integration_queue_epic": stale.epic_id,
                        "integration_queue_branch": stale.task_branch,
                        "integration_queue_head": stale.head_sha,
                        "task_parent": task.parent_id,
                        "task_branch": task.integration.task_branch,
                        "task_head": task.integration.head_sha,
                    },
                }
            },
        ),
        check_interrupted=lambda: None,
    )

    with pytest.raises(WorkflowActionSuperseded, match="normalized"):
        await backend.apply_action("integration_attempt", context)

    current = queue.get("project-1", task.identifier)
    record = tracker.fetch_issue_detail(task.identifier).integration
    assert executed == []
    assert current is not None
    assert current.epic_id == "E-NEW"
    assert current.state == "ready"
    assert record.mode == "queue"
    assert record.base_branch == "epic/E-NEW"
    assert record.state == "ready"


@pytest.mark.asyncio
@pytest.mark.parametrize("replacement_parent", [None, "E-NEW"])
async def test_containment_change_finishes_prepared_private_publication_before_repair(
    tmp_path,
    replacement_parent,
):
    task = issue("TASK-A", head="d" * 40)
    task.parent_id = replacement_parent
    task.integration = replace(
        task.integration,
        mode="queue",
        base_branch="epic/E-OLD",
        base_sha="e" * 40,
        head_sha="d" * 40,
    )
    tracker = MetadataTracker([task])
    fact_collector = collector(tracker)
    queue = IntegrationQueueStore(str(tmp_path / "integration.sqlite3"))
    predecessor = queue.enqueue(
        project_id="project-1",
        epic_id="E-OLD",
        task_id=task.identifier,
        task_branch=task.integration.task_branch,
        head_sha="a" * 40,
        base_sha="e" * 40,
    )
    prepared = queue.prepare_task_publication(
        "project-1",
        task.identifier,
        expected_generation=predecessor.authority_generation(),
        head_sha=task.integration.head_sha,
        base_sha=task.integration.base_sha,
    )
    assert prepared is not None
    assert prepared.rebased_publication_pending
    executions = []

    def execute(
        row,
        *,
        commit_allowed,
        rebased_head_checkpoint,
        **_kwargs,
    ):
        executions.append(row.authority_generation())
        assert commit_allowed()
        # Clearing the durable private-publication bit intentionally revokes
        # old-container delivery authority.  The next job owns containment
        # repair; this invocation must not proceed to the old epic.
        assert not rebased_head_checkpoint(row.head_sha, row.base_sha)
        assert not commit_allowed()
        return IntegrationExecutionResult(
            "stale_head",
            "prepared private publication completed after containment changed",
            expected_epic_sha=row.base_sha,
            rebased_task_sha=row.head_sha,
        )

    orchestrator = SimpleNamespace(
        integration_queue=queue,
        project_store=SimpleNamespace(
            epic_branch_name=lambda epic_id: f"epic/{epic_id}",
            get=lambda _project_id: SimpleNamespace(default_branch="main"),
        ),
        _execute_integration_item=execute,
        request_refresh=lambda: None,
    )
    backend = OrchestratorIntegrationActionBackend(
        orchestrator,
        SimpleNamespace(
            project_id="project-1",
            tracker=tracker,
            collector=fact_collector,
        ),
    )
    backend._landing = lambda current: LandingFact(
        current.integration.task_branch,
        current.integration.base_branch,
        current.integration.head_sha,
        {"kind": "git_ancestry", "target_sha": "f" * 40},
        "2026-08-05T00:00:00+00:00",
        "project-1",
        state=LandingState.LANDED,
    )

    def context_for(row):
        decision = evaluate_task(task, fact_collector.collect(task.identifier))
        assert decision.durable_jobs == ("integration_attempt",)
        return SimpleNamespace(
            job=SimpleNamespace(
                project_id="project-1",
                task_id=task.identifier,
                generation="generation-1",
                job_id="job-1",
                checkpoint={
                    "revalidation": {
                        "evidence_revision": decision.evidence_revision,
                        "details": {
                            "integration_queue_present": True,
                            "integration_queue_generation": (
                                row.authority_generation()
                            ),
                            "integration_queue_epic": row.epic_id,
                            "integration_queue_branch": row.task_branch,
                            "integration_queue_head": row.head_sha,
                            "task_parent": replacement_parent or "",
                            "task_branch": task.integration.task_branch,
                            "task_head": task.integration.head_sha,
                        },
                    }
                },
            ),
            check_interrupted=lambda: None,
        )

    with pytest.raises(WorkflowActionError, match="publication completed"):
        await backend.apply_action("integration_attempt", context_for(prepared))

    published = queue.get("project-1", task.identifier)
    assert published is not None
    assert not published.rebased_publication_pending
    assert executions == [prepared.authority_generation()]

    with pytest.raises(WorkflowActionSuperseded):
        await backend.apply_action("integration_attempt", context_for(published))

    repaired = queue.get("project-1", task.identifier)
    record = tracker.fetch_issue_detail(task.identifier).integration
    assert executions == [prepared.authority_generation()]
    if replacement_parent is None:
        assert repaired is not None
        assert repaired.state == "cancelled"
        assert repaired.last_error == STANDALONE_RECLASSIFICATION_REASON
        assert record.mode == "standalone"
        assert record.base_branch == "main"
    else:
        assert repaired is not None
        assert repaired.state == "ready"
        assert repaired.epic_id == replacement_parent
        assert record.mode == "queue"
        assert record.base_branch == f"epic/{replacement_parent}"


@pytest.mark.asyncio
async def test_integration_attempt_rejects_mixed_parent_and_queue_snapshot(tmp_path):
    task = issue("TASK-A", head="a" * 40)
    task.parent_id = "E-OLD"
    task.integration = replace(task.integration, mode="queue")
    tracker = MetadataTracker([task])
    fact_collector = collector(tracker)
    old_decision = evaluate_task(task, fact_collector.collect(task.identifier))
    queue = IntegrationQueueStore(str(tmp_path / "integration.sqlite3"))
    replacement = queue.enqueue(
        project_id="project-1",
        epic_id="E-NEW",
        task_id=task.identifier,
        task_branch=task.integration.task_branch,
        head_sha=task.integration.head_sha,
    )
    task.parent_id = "E-NEW"
    executed = []
    backend = OrchestratorIntegrationActionBackend(
        SimpleNamespace(
            integration_queue=queue,
            project_store=SimpleNamespace(
                epic_branch_name=lambda epic_id: f"epic/{epic_id}"
            ),
            _execute_integration_item=lambda row, **kwargs: executed.append(row),
        ),
        SimpleNamespace(
            project_id="project-1",
            tracker=tracker,
            collector=fact_collector,
        ),
    )
    context = SimpleNamespace(
        job=SimpleNamespace(
            project_id="project-1",
            task_id=task.identifier,
            generation="generation-1",
            job_id="job-1",
            checkpoint={
                "revalidation": {
                    "evidence_revision": old_decision.evidence_revision,
                    "details": {
                        "integration_queue_present": True,
                        "integration_queue_generation": (
                            replacement.authority_generation()
                        ),
                        "integration_queue_epic": replacement.epic_id,
                        "integration_queue_branch": replacement.task_branch,
                        "integration_queue_head": replacement.head_sha,
                        "task_parent": "E-OLD",
                        "task_branch": task.integration.task_branch,
                        "task_head": task.integration.head_sha,
                    },
                }
            },
        ),
        check_interrupted=lambda: None,
    )

    with pytest.raises(WorkflowActionError, match="task generation changed"):
        await backend.apply_action("integration_attempt", context)

    assert executed == []
    assert queue.get("project-1", task.identifier) == replacement


@pytest.mark.asyncio
async def test_unparented_queue_generation_reclassifies_to_standalone(tmp_path):
    task = issue("TASK-A", head="a" * 40)
    task.parent_id = None
    task.integration = replace(
        task.integration,
        mode="queue",
        base_branch="epic/E-OLD",
        base_sha="b" * 40,
    )
    tracker = MetadataTracker([task])
    fact_collector = collector(tracker)
    decision = evaluate_task(task, fact_collector.collect(task.identifier))
    assert decision.durable_jobs == ("integration_attempt",)
    queue = IntegrationQueueStore(str(tmp_path / "integration.sqlite3"))
    queued = queue.enqueue(
        project_id="project-1",
        epic_id="E-OLD",
        task_id=task.identifier,
        task_branch=task.integration.task_branch,
        head_sha=task.integration.head_sha,
    )
    backend = OrchestratorIntegrationActionBackend(
        SimpleNamespace(
            integration_queue=queue,
            project_store=SimpleNamespace(
                epic_branch_name=lambda epic_id: f"epic/{epic_id}",
                get=lambda _project_id: SimpleNamespace(default_branch="main"),
            ),
        ),
        SimpleNamespace(
            project_id="project-1",
            tracker=tracker,
            collector=fact_collector,
        ),
    )
    context = SimpleNamespace(
        job=SimpleNamespace(
            project_id="project-1",
            task_id=task.identifier,
            generation="generation-1",
            job_id="job-1",
            checkpoint={
                "revalidation": {
                    "evidence_revision": decision.evidence_revision,
                    "details": {
                        "integration_queue_present": True,
                        "integration_queue_generation": queued.authority_generation(),
                        "integration_queue_epic": queued.epic_id,
                        "integration_queue_branch": queued.task_branch,
                        "integration_queue_head": queued.head_sha,
                        "task_parent": "",
                        "task_branch": task.integration.task_branch,
                        "task_head": task.integration.head_sha,
                        "task_target": "main",
                    },
                }
            },
        ),
        check_interrupted=lambda: None,
    )

    with pytest.raises(WorkflowActionSuperseded, match="parent removal"):
        await backend.apply_action("integration_attempt", context)

    record = tracker.fetch_issue_detail(task.identifier).integration
    assert record.mode == "standalone"
    assert record.base_branch == "main"
    assert record.base_sha is None
    retired = queue.get("project-1", task.identifier)
    assert retired is not None
    assert retired.state == "cancelled"
    assert retired.last_error == STANDALONE_RECLASSIFICATION_REASON


@pytest.mark.asyncio
async def test_unparented_queue_reclassification_preserves_explicit_target(tmp_path):
    task = issue("TASK-A", head="a" * 40)
    task.parent_id = None
    task.target_branch = "release/next"
    task.integration = replace(
        task.integration,
        mode="queue",
        base_branch="epic/E-OLD",
        base_sha="b" * 40,
    )
    tracker = MetadataTracker([task])
    fact_collector = collector(tracker)
    decision = evaluate_task(task, fact_collector.collect(task.identifier))
    queue = IntegrationQueueStore(str(tmp_path / "integration.sqlite3"))
    queued = queue.enqueue(
        project_id="project-1",
        epic_id="E-OLD",
        task_id=task.identifier,
        task_branch=task.integration.task_branch,
        head_sha=task.integration.head_sha,
    )
    backend = OrchestratorIntegrationActionBackend(
        SimpleNamespace(
            integration_queue=queue,
            project_store=SimpleNamespace(
                epic_branch_name=lambda epic_id: f"epic/{epic_id}",
                get=lambda _project_id: SimpleNamespace(default_branch="main"),
            ),
        ),
        SimpleNamespace(
            project_id="project-1",
            tracker=tracker,
            collector=fact_collector,
        ),
    )
    context = SimpleNamespace(
        job=SimpleNamespace(
            project_id="project-1",
            task_id=task.identifier,
            generation="generation-1",
            job_id="job-1",
            checkpoint={
                "revalidation": {
                    "evidence_revision": decision.evidence_revision,
                    "details": {
                        "integration_queue_present": True,
                        "integration_queue_generation": queued.authority_generation(),
                        "integration_queue_epic": queued.epic_id,
                        "integration_queue_branch": queued.task_branch,
                        "integration_queue_head": queued.head_sha,
                        "task_parent": "",
                        "task_branch": task.integration.task_branch,
                        "task_head": task.integration.head_sha,
                        "task_target": "release/next",
                    },
                }
            },
        ),
        check_interrupted=lambda: None,
    )

    with pytest.raises(WorkflowActionSuperseded, match="parent removal"):
        await backend.apply_action("integration_attempt", context)

    record = tracker.fetch_issue_detail(task.identifier).integration
    assert record.mode == "standalone"
    assert record.base_branch == "release/next"


@pytest.mark.asyncio
async def test_unparented_queue_reclassification_fences_target_change(tmp_path):
    task = issue("TASK-A", head="a" * 40)
    task.parent_id = None
    task.target_branch = "release/next"
    task.integration = replace(
        task.integration,
        mode="queue",
        base_branch="epic/E-OLD",
        base_sha="b" * 40,
    )
    tracker = MetadataTracker([task])
    fact_collector = collector(tracker)
    decision = evaluate_task(task, fact_collector.collect(task.identifier))
    queue = IntegrationQueueStore(str(tmp_path / "integration.sqlite3"))
    queued = queue.enqueue(
        project_id="project-1",
        epic_id="E-OLD",
        task_id=task.identifier,
        task_branch=task.integration.task_branch,
        head_sha=task.integration.head_sha,
    )
    original_retire = queue.retire_task_generation

    def racing_retire(*args, action, **kwargs):
        def change_target_then_reclassify(current):
            task.target_branch = "release/hotfix"
            return action(current)

        return original_retire(
            *args,
            action=change_target_then_reclassify,
            **kwargs,
        )

    queue.retire_task_generation = racing_retire
    backend = OrchestratorIntegrationActionBackend(
        SimpleNamespace(
            integration_queue=queue,
            project_store=SimpleNamespace(
                epic_branch_name=lambda epic_id: f"epic/{epic_id}",
                get=lambda _project_id: SimpleNamespace(default_branch="main"),
            ),
        ),
        SimpleNamespace(
            project_id="project-1",
            tracker=tracker,
            collector=fact_collector,
        ),
    )
    context = SimpleNamespace(
        job=SimpleNamespace(
            project_id="project-1",
            task_id=task.identifier,
            generation="generation-1",
            job_id="job-1",
            checkpoint={
                "revalidation": {
                    "evidence_revision": decision.evidence_revision,
                    "details": {
                        "integration_queue_present": True,
                        "integration_queue_generation": queued.authority_generation(),
                        "integration_queue_epic": queued.epic_id,
                        "integration_queue_branch": queued.task_branch,
                        "integration_queue_head": queued.head_sha,
                        "task_parent": "",
                        "task_branch": task.integration.task_branch,
                        "task_head": task.integration.head_sha,
                        "task_target": "release/next",
                    },
                }
            },
        ),
        check_interrupted=lambda: None,
    )

    with pytest.raises(WorkflowActionError, match="authority changed"):
        await backend.apply_action("integration_attempt", context)

    record = tracker.fetch_issue_detail(task.identifier).integration
    current = queue.get("project-1", task.identifier)
    assert record.mode == "queue"
    assert record.base_branch == "epic/E-OLD"
    assert current is not None
    assert current.state == "ready"


@pytest.mark.asyncio
async def test_standalone_apply_repairs_tracker_first_reclassification_gap(tmp_path):
    task = issue("TASK-A", head="a" * 40)
    task.parent_id = None
    task.integration = replace(task.integration, mode="standalone")
    tracker = MetadataTracker([task])
    fact_collector = collector(tracker)
    decision = evaluate_task(task, fact_collector.collect(task.identifier))
    queue = IntegrationQueueStore(str(tmp_path / "integration.sqlite3"))
    queued = queue.enqueue(
        project_id="project-1",
        epic_id="E-OLD",
        task_id=task.identifier,
        task_branch=task.integration.task_branch,
        head_sha=task.integration.head_sha,
    )
    calls = []

    def deliver(*args, **kwargs):
        calls.append((args, kwargs))
        task.state = "In Review"
        task.review_number = "17"
        task.review_head = task.integration.head_sha

    backend = OrchestratorIntegrationActionBackend(
        SimpleNamespace(
            integration_queue=queue,
            _reconcile_one_standalone_ready_to_integrate_task=deliver,
        ),
        SimpleNamespace(
            project_id="project-1",
            tracker=tracker,
            collector=fact_collector,
        ),
    )
    context = SimpleNamespace(
        job=SimpleNamespace(
            project_id="project-1",
            task_id=task.identifier,
            generation="generation-1",
            job_id="job-1",
            lease_token="lease-1",
            checkpoint={
                "revalidation": {
                    "evidence_revision": decision.evidence_revision,
                    "details": {
                        "task_parent": "",
                        "task_branch": task.integration.task_branch,
                        "task_head": task.integration.head_sha,
                        "task_target": "main",
                    },
                }
            },
        ),
        check_interrupted=lambda: None,
    )

    effect = await backend.apply_action("standalone_delivery", context)

    assert effect.receipt["review_number"] == "17"
    assert len(calls) == 1
    retired = queue.get("project-1", task.identifier)
    assert retired is not None
    assert retired.state == "cancelled"
    assert retired.last_error == STANDALONE_RECLASSIFICATION_REASON


@pytest.mark.asyncio
async def test_standalone_apply_canonicalizes_legacy_delivery_mode(tmp_path):
    task = issue("TASK-A", head="a" * 40)
    task.parent_id = None
    task.integration = replace(task.integration, mode=None)
    tracker = MetadataTracker([task])
    fact_collector = collector(tracker)
    decision = evaluate_task(task, fact_collector.collect(task.identifier))
    assert decision.durable_jobs == ("standalone_delivery",)
    deliveries = []
    backend = OrchestratorIntegrationActionBackend(
        SimpleNamespace(
            integration_queue=IntegrationQueueStore(
                str(tmp_path / "integration.sqlite3")
            ),
            _reconcile_one_standalone_ready_to_integrate_task=(
                lambda *args, **kwargs: deliveries.append((args, kwargs))
            ),
            request_refresh=lambda: None,
        ),
        SimpleNamespace(
            project_id="project-1",
            tracker=tracker,
            collector=fact_collector,
        ),
    )
    context = SimpleNamespace(
        job=SimpleNamespace(
            project_id="project-1",
            task_id=task.identifier,
            generation="generation-1",
            job_id="job-1",
            lease_token="lease-1",
            checkpoint={
                "revalidation": {
                    "evidence_revision": decision.evidence_revision,
                    "details": {
                        "task_parent": "",
                        "task_branch": task.integration.task_branch,
                        "task_head": task.integration.head_sha,
                        "task_target": "main",
                    },
                }
            },
        ),
        check_interrupted=lambda: None,
    )

    with pytest.raises(WorkflowActionSuperseded, match="canonicalized"):
        await backend.apply_action("standalone_delivery", context)

    assert tracker.fetch_issue_detail(task.identifier).integration.mode == "standalone"
    assert deliveries == []


@pytest.mark.asyncio
async def test_replacement_private_head_fences_late_workflow_executor(tmp_path):
    holder = {}

    def execute(
        row,
        *,
        commit_allowed,
        gate_generation,
        retry_forced,
        rebase_intent_prepare,
        rebase_intent_abort,
        rebased_head_prepare,
        rebased_head_checkpoint,
    ):
        queue = holder["queue"]
        queue.enqueue(
            project_id="project-1",
            epic_id="E-1",
            task_id="TASK-A",
            task_branch="TASK-A",
            head_sha="d" * 40,
            base_sha="b" * 40,
            explicit_retry=True,
        )
        assert not commit_allowed()
        return IntegrationExecutionResult(
            "stale_head", "private head changed during executor"
        )

    backend, context, queue, tracker = integration_backend_context(
        tmp_path, execute=execute
    )
    holder["queue"] = queue

    with pytest.raises(WorkflowActionError, match="private head changed"):
        await backend.apply_action("integration_attempt", context)

    assert queue.get("project-1", "TASK-A").head_sha == "d" * 40
    assert tracker.fetch_issue_detail("TASK-A").integration.state == "ready"


def test_integration_attempt_observe_verify_and_transition_reject_replacement(
    tmp_path,
):
    backend, context, queue, tracker = integration_backend_context(
        tmp_path,
        execute=lambda *args, **kwargs: IntegrationExecutionResult(
            "ci_failure", "unused"
        ),
    )
    original = queue.get("project-1", "TASK-A")
    assert original is not None
    replacement = queue.enqueue(
        project_id="project-1",
        epic_id="E-1",
        task_id="TASK-A",
        task_branch="TASK-A",
        head_sha="b" * 40,
        base_sha="b" * 40,
        explicit_retry=True,
    )
    task = tracker.fetch_issue_detail("TASK-A")
    task.integration = replace(task.integration, head_sha="b" * 40)

    observation = backend.observe_action("integration_attempt", context)
    assert not observation.applied

    effect = EffectResult(
        {
            "route": IntegrationRoute.CI_FIX.value,
            "queue_generation": original.authority_generation(),
            "queue_branch": original.task_branch,
            "queue_head": original.head_sha,
        }
    )
    verification = backend.verify_action(
        "integration_attempt", context, effect
    )
    assert not verification.verified
    with pytest.raises(WorkflowActionError, match="generation changed"):
        backend.build_action_transition(
            "integration_attempt", context, verification
        )
    assert queue.get("project-1", "TASK-A") == replacement


@pytest.mark.asyncio
async def test_executor_status_cannot_adopt_an_uncheckpointed_head(tmp_path):
    backend, context, queue, tracker = integration_backend_context(
        tmp_path,
        execute=lambda *args, **kwargs: IntegrationExecutionResult(
            "stale_head",
            "origin advanced to an unrelated head",
            rebased_task_sha="d" * 40,
        ),
    )

    with pytest.raises(WorkflowActionError, match="unrelated head"):
        await backend.apply_action("integration_attempt", context)

    current = queue.get("project-1", "TASK-A")
    assert current.head_sha == "a" * 40
    assert current.rebased_from_head_sha is None
    assert tracker.fetch_issue_detail("TASK-A").integration.head_sha == "a" * 40


@pytest.mark.asyncio
async def test_restart_repairs_tracker_after_queue_effect_checkpoint(tmp_path):
    backend, context, queue, tracker = integration_backend_context(
        tmp_path,
        execute=lambda *args, **kwargs: IntegrationExecutionResult(
            "integrated", "unused"
        ),
    )
    queued = queue.get("project-1", "TASK-A")
    finished = queue.finish_task_generation(
        "project-1",
        "TASK-A",
        expected_generation=queued.authority_generation(),
        state="integrated",
    )
    assert finished is not None
    context.job.checkpoint["revalidation"]["details"][
        "integration_queue_generation"
    ] = finished.authority_generation()
    backend._landing = lambda issue: landed_fact(
        revision="a" * 40,
        target_sha="c" * 40,
    )

    effect = await backend.apply_action("integration_attempt", context)

    assert effect.receipt["queue_state"] == "integrated"
    record = tracker.fetch_issue_detail("TASK-A").integration
    assert record.state == "integrated"
    assert record.head_sha == "a" * 40
    assert record.integrated_sha == "c" * 40


@pytest.mark.asyncio
async def test_restart_accepts_already_integrated_tracker_without_peer_replay(
    tmp_path,
):
    backend, context, queue, tracker = integration_backend_context(
        tmp_path,
        execute=lambda *args, **kwargs: IntegrationExecutionResult(
            "integrated", "unused"
        ),
    )
    queued = queue.get("project-1", "TASK-A")
    finished = queue.finish_task_generation(
        "project-1",
        "TASK-A",
        expected_generation=queued.authority_generation(),
        state="integrated",
        integrated_sha="c" * 40,
    )
    assert finished is not None
    tracker.set_metadata_field(
        "TASK-A",
        "oompah.integration",
        IntegrationRecord(
            state="integrated",
            task_branch="TASK-A",
            base_branch="epic/E-1",
            base_sha="b" * 40,
            head_sha="a" * 40,
            integrated_sha="c" * 40,
        ).to_dict(),
    )
    context.job.checkpoint["revalidation"]["details"][
        "integration_queue_generation"
    ] = finished.authority_generation()
    backend._landing = lambda issue: landed_fact(
        revision="a" * 40,
        target_sha="c" * 40,
    )
    backend.orchestrator._notify_integrated_task_peers = (
        lambda **kwargs: pytest.fail("already-checkpointed peers were replayed")
    )

    effect = await backend.apply_action("integration_attempt", context)

    assert effect.receipt["coordination_notified"] == 0
    assert tracker.fetch_issue_detail("TASK-A").integration.state == "integrated"


def test_restart_repairs_queue_first_rebased_tracker_checkpoint(tmp_path):
    backend, context, queue, tracker = integration_backend_context(
        tmp_path,
        execute=lambda *args, **kwargs: IntegrationExecutionResult(
            "epic_head_race", "unused"
        ),
    )
    queued = queue.get("project-1", "TASK-A")
    advanced = queue.advance_task_generation(
        "project-1",
        "TASK-A",
        expected_generation=queued.authority_generation(),
        head_sha="d" * 40,
        base_sha="e" * 40,
    )
    assert advanced is not None
    context.job.checkpoint["revalidation"]["details"].update(
        {
            "integration_queue_generation": advanced.authority_generation(),
            "integration_queue_branch": advanced.task_branch,
            "integration_queue_head": advanced.head_sha,
        }
    )

    repaired_issue, repaired_row = backend._repair_rebased_tracker_checkpoint(
        context
    )

    assert repaired_row == advanced
    assert repaired_issue.integration.state == "ready"
    assert repaired_issue.integration.head_sha == "d" * 40
    assert repaired_issue.integration.base_sha == "e" * 40


def test_revalidation_does_not_repair_queue_first_rebased_tracker_checkpoint(
    tmp_path,
):
    backend, context, queue, tracker = integration_backend_context(
        tmp_path,
        execute=lambda *args, **kwargs: IntegrationExecutionResult(
            "epic_head_race", "unused"
        ),
    )
    queued = queue.get("project-1", "TASK-A")
    advanced = queue.advance_task_generation(
        "project-1",
        "TASK-A",
        expected_generation=queued.authority_generation(),
        head_sha="d" * 40,
        base_sha="e" * 40,
    )
    assert advanced is not None
    fact_collector = collector(tracker)
    backend.binding.collector = fact_collector
    decision = evaluate_task(
        tracker.fetch_issue_detail("TASK-A"),
        fact_collector.collect("TASK-A"),
    )
    context.job.expected_evidence_revision = decision.evidence_revision

    revalidation = backend.revalidate_action("integration_attempt", context)

    assert revalidation.current
    assert queue.get("project-1", "TASK-A") == advanced
    record = tracker.fetch_issue_detail("TASK-A").integration
    assert record.head_sha == "a" * 40
    assert record.base_sha == "b" * 40


def test_rebased_tracker_repair_cas_loss_has_no_tracker_side_effect(tmp_path):
    backend, context, queue, tracker = integration_backend_context(
        tmp_path,
        execute=lambda *args, **kwargs: IntegrationExecutionResult(
            "epic_head_race", "unused"
        ),
    )
    queued = queue.get("project-1", "TASK-A")
    advanced = queue.advance_task_generation(
        "project-1",
        "TASK-A",
        expected_generation=queued.authority_generation(),
        head_sha="d" * 40,
        base_sha="e" * 40,
    )
    assert advanced is not None
    context.job.checkpoint["revalidation"]["details"].update(
        {
            "integration_queue_generation": advanced.authority_generation(),
            "integration_queue_branch": advanced.task_branch,
            "integration_queue_head": advanced.head_sha,
        }
    )
    queue.run_if_generation = lambda *args, **kwargs: False

    with pytest.raises(WorkflowActionError, match="during tracker repair"):
        backend._repair_rebased_tracker_checkpoint(context)

    record = tracker.fetch_issue_detail("TASK-A").integration
    assert record.head_sha == "a" * 40
    assert record.base_sha == "b" * 40


@pytest.mark.asyncio
async def test_executor_callback_checkpoints_rebase_before_retry_result(tmp_path):
    def execute(
        row,
        *,
        commit_allowed,
        rebased_head_prepare,
        rebased_head_checkpoint,
        **_kwargs,
    ):
        assert commit_allowed()
        assert rebased_head_prepare("d" * 40, "e" * 40)
        assert rebased_head_checkpoint("d" * 40, "e" * 40)
        assert commit_allowed()
        return IntegrationExecutionResult(
            "epic_head_race",
            "epic parent advanced after the push",
            expected_epic_sha="e" * 40,
            rebased_task_sha="d" * 40,
        )

    backend, context, queue, tracker = integration_backend_context(
        tmp_path,
        execute=execute,
    )

    with pytest.raises(WorkflowActionError, match="advanced after the push"):
        await backend.apply_action("integration_attempt", context)

    assert queue.get("project-1", "TASK-A").head_sha == "d" * 40
    assert tracker.fetch_issue_detail("TASK-A").integration.head_sha == "d" * 40


@pytest.mark.asyncio
async def test_peer_coordination_replays_before_integrated_metadata(tmp_path):
    backend, context, queue, tracker = integration_backend_context(
        tmp_path,
        execute=lambda *args, **kwargs: IntegrationExecutionResult(
            "integrated", "unused"
        ),
    )
    queued = queue.get("project-1", "TASK-A")
    assert queue.finish_task_generation(
        "project-1",
        "TASK-A",
        expected_generation=queued.authority_generation(),
        state="integrated",
    ) is not None
    current = queue.get("project-1", "TASK-A")
    context.job.checkpoint["revalidation"]["details"][
        "integration_queue_generation"
    ] = current.authority_generation()
    backend._landing = lambda issue: landed_fact()
    calls = []

    def notify(**kwargs):
        calls.append(kwargs["integrated_sha"])
        if len(calls) == 1:
            raise RuntimeError("coordination store unavailable")
        return 1

    backend.orchestrator._notify_integrated_task_peers = notify

    with pytest.raises(WorkflowActionError, match="coordination"):
        await backend.apply_action("integration_attempt", context)
    assert tracker.fetch_issue_detail("TASK-A").integration.state == "ready"

    effect = await backend.apply_action("integration_attempt", context)

    assert calls == ["c" * 40, "c" * 40]
    assert effect.receipt["coordination_notified"] == 1
    assert tracker.fetch_issue_detail("TASK-A").integration.state == "integrated"


@pytest.mark.asyncio
async def test_peer_coordination_cannot_commit_metadata_after_authority_fence(
    tmp_path,
):
    backend, context, queue, tracker = integration_backend_context(
        tmp_path,
        execute=lambda *args, **kwargs: IntegrationExecutionResult(
            "integrated", "unused"
        ),
    )
    queued = queue.get("project-1", "TASK-A")
    assert queue.finish_task_generation(
        "project-1",
        "TASK-A",
        expected_generation=queued.authority_generation(),
        state="integrated",
        integrated_sha="c" * 40,
    ) is not None
    current = queue.get("project-1", "TASK-A")
    context.job.checkpoint["revalidation"]["details"][
        "integration_queue_generation"
    ] = current.authority_generation()
    backend._landing = lambda issue: landed_fact()
    authority = {"live": True}

    def check_interrupted():
        if not authority["live"]:
            raise RuntimeError("workflow lease fenced")

    def notify(**_kwargs):
        authority["live"] = False
        return 1

    context.check_interrupted = check_interrupted
    backend.orchestrator._notify_integrated_task_peers = notify

    with pytest.raises(RuntimeError, match="workflow lease fenced"):
        await backend.apply_action("integration_attempt", context)

    assert tracker.fetch_issue_detail("TASK-A").integration.state == "ready"


@pytest.mark.asyncio
async def test_parent_ancestry_race_checkpoints_rebased_private_authority(tmp_path):
    def execute(
        _row,
        *,
        rebased_head_prepare,
        rebased_head_checkpoint,
        **_kwargs,
    ):
        assert rebased_head_prepare("d" * 40, "e" * 40)
        assert rebased_head_checkpoint("d" * 40, "e" * 40)
        return IntegrationExecutionResult(
            "epic_head_race",
            "epic parent advanced",
            expected_epic_sha="e" * 40,
            rebased_task_sha="d" * 40,
        )

    backend, context, queue, tracker = integration_backend_context(
        tmp_path,
        execute=execute,
    )
    with pytest.raises(WorkflowActionError, match="epic parent advanced") as error:
        await backend.apply_action("integration_attempt", context)

    assert error.value.retryable
    current = queue.get("project-1", "TASK-A")
    assert current.head_sha == "d" * 40
    assert current.rebased_from_head_sha == "a" * 40
    record = tracker.fetch_issue_detail("TASK-A").integration
    assert record.state == "ready"
    assert record.head_sha == "d" * 40
    assert record.base_sha == "e" * 40


@pytest.mark.asyncio
async def test_ci_failure_has_durable_queue_receipt_and_exact_transition(tmp_path):
    backend, context, queue, tracker = integration_backend_context(
        tmp_path,
        execute=lambda *args, **kwargs: IntegrationExecutionResult(
            "ci_failure",
            "combined tree failed",
            expected_epic_sha="b" * 40,
            rebased_task_sha="a" * 40,
        ),
    )

    effect = await backend.apply_action("integration_attempt", context)
    verification = backend.verify_action("integration_attempt", context, effect)
    transition = backend.build_action_transition(
        "integration_attempt", context, verification
    )

    assert queue.get("project-1", "TASK-A").state == "blocked"
    assert tracker.fetch_issue_detail("TASK-A").integration.state == "blocked"
    assert verification.verified
    assert transition is not None
    assert transition.task_id == "TASK-A"
    assert transition.requested_status == "Needs CI Fix"
    assert transition.exact_head == "a" * 40


@pytest.mark.asyncio
async def test_restart_repairs_transition_after_blocked_queue_checkpoint(tmp_path):
    backend, context, queue, tracker = integration_backend_context(
        tmp_path,
        execute=lambda *args, **kwargs: IntegrationExecutionResult(
            "ci_failure", "unused"
        ),
    )
    queued = queue.get("project-1", "TASK-A")
    blocked = queue.finish_task_generation(
        "project-1",
        "TASK-A",
        expected_generation=queued.authority_generation(),
        state="blocked",
        error="ci_failure:combined tree failed before receipt",
    )
    assert blocked is not None
    context.job.checkpoint["revalidation"]["details"][
        "integration_queue_generation"
    ] = blocked.authority_generation()

    effect = await backend.apply_action("integration_attempt", context)
    verification = backend.verify_action("integration_attempt", context, effect)
    transition = backend.build_action_transition(
        "integration_attempt", context, verification
    )

    assert effect.receipt["recovered_after_queue_checkpoint"] is True
    assert verification.verified
    record = tracker.fetch_issue_detail("TASK-A").integration
    assert record.state == "blocked"
    assert record.last_error == "combined tree failed before receipt"
    assert transition is not None
    assert transition.requested_status == "Needs CI Fix"


@pytest.mark.asyncio
async def test_terminal_actions_stage_only_the_exact_integrated_history_row(
    tmp_path,
):
    selected = issue("TASK-A", state="integrated", head="a" * 40)
    selected.parent_id = "E-1"
    selected.integration = replace(
        selected.integration,
        state="integrated",
        integrated_sha="a" * 40,
    )
    sibling = issue("TASK-B", state="integrated", head="b" * 40)
    sibling.parent_id = "E-1"
    sibling.integration = replace(
        sibling.integration,
        state="integrated",
        integrated_sha="b" * 40,
    )
    tracker = Tracker([selected, sibling])
    queue = IntegrationQueueStore(str(tmp_path / "integration.sqlite3"))
    for task, head in (("TASK-A", "a" * 40), ("TASK-B", "b" * 40)):
        queue.enqueue(
            project_id="project-1",
            epic_id="E-1",
            task_id=task,
            task_branch=task,
            head_sha=head,
        )
        claimed = queue.claim_next(
            project_id="project-1",
            epic_id="E-1",
            lease_owner=f"legacy-{task}",
            dependency_map={task: []},
            satisfied=set(),
        )
        assert claimed is not None
        assert queue.complete("project-1", task, lease_owner=f"legacy-{task}")
    staged = []

    async def stage(row, **_kwargs):
        staged.append(row.task_id)
        tracker.fetch_issue_detail(row.task_id).state = "In Validation"

    orchestrator = SimpleNamespace(
        integration_queue=queue,
        _stage_integrated_task_audit=stage,
    )
    backend = OrchestratorIntegrationActionBackend(
        orchestrator,
        SimpleNamespace(project_id="project-1", tracker=tracker),
    )
    backend._landing = lambda issue: landed_fact(
        revision=issue.integration.integrated_sha,
        target_sha=issue.integration.integrated_sha,
    )
    context = SimpleNamespace(
        job=SimpleNamespace(
            project_id="project-1",
            task_id="TASK-A",
            generation="generation-1",
            checkpoint={
                "revalidation": {
                    "head_sha": "a" * 40,
                    "details": {
                        "integration_queue_generation": queue.get(
                            "project-1", "TASK-A"
                        ).authority_generation(),
                        "integration_queue_branch": "TASK-A",
                        "integration_queue_head": "a" * 40,
                    }
                }
            },
        ),
        check_interrupted=lambda: None,
    )

    effect = await backend.apply_action("integration_terminal_stage", context)
    verification = backend.verify_action(
        "integration_terminal_stage", context, effect
    )

    assert staged == ["TASK-A"]
    assert verification.verified
    assert tracker.fetch_issue_detail("TASK-B").state == READY_TO_INTEGRATE


@pytest.mark.asyncio
async def test_historical_batch_uses_project_replay_without_staging_live_task(tmp_path):
    live = issue("TASK-A")
    live.integration = replace(
        live.integration,
        state="ready",
        head_sha="a" * 40,
    )
    tracker = Tracker([live])
    calls = []

    async def replay(*, project_id, expected_cursor):
        calls.append((project_id, expected_cursor))
        return {
            "batch_size": 32,
            "replayed": 1,
            "deferred": False,
            "cursor": "next-batch",
            "error": None,
            "batch_completed": True,
        }

    backend = OrchestratorIntegrationActionBackend(
        SimpleNamespace(
            _replay_project_integrated_audit_batch=replay,
        ),
        SimpleNamespace(project_id="project-1", tracker=tracker),
    )
    context = SimpleNamespace(
        job=SimpleNamespace(
            project_id="project-1",
            task_id="__oompah_integration_history__",
            generation="generation-1",
            payload={"cursor": "cursor-before-batch"},
        )
    )

    effect = await backend.apply_action("historical_audit_replay_batch", context)
    verification = backend.verify_action(
        "historical_audit_replay_batch", context, effect
    )

    assert calls == [("project-1", "cursor-before-batch")]
    assert verification.verified
    assert tracker.fetch_issue_detail("TASK-A").state == READY_TO_INTEGRATE


@pytest.mark.asyncio
async def test_historical_replay_materializes_successor_generations_until_exhausted(
    tmp_path,
):
    queue = IntegrationQueueStore(str(tmp_path / "integration.sqlite3"))
    for index in range(3):
        task_id = f"HIST-{index}"
        queue.enqueue(
            project_id="project-1",
            epic_id="E-1",
            task_id=task_id,
            task_branch=f"branch-{task_id}",
            head_sha=str(index + 1) * 40,
        )
        claimed = queue.claim_next(
            project_id="project-1",
            epic_id="E-1",
            lease_owner=f"legacy-{index}",
            dependency_map={task_id: ()},
            satisfied=set(),
        )
        assert claimed is not None
        assert queue.complete(
            "project-1", task_id, lease_owner=f"legacy-{index}"
        )

    jobs = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    orchestrator = SimpleNamespace(
        integration_queue=queue,
        workflow_job_store=jobs,
        _maintenance_cursors={},
    )
    replayed = []

    async def replay(*, project_id, expected_cursor):
        cursor_name = f"integration_audit:{project_id}"
        assert orchestrator._maintenance_cursors.get(cursor_name) == expected_cursor
        rows = queue.items(
            project_id=project_id,
            states=("integrated",),
            limit=2,
            after=expected_cursor,
        )
        selected = rows[0]
        replayed.append(selected.task_id)
        cursor = queue.cursor_for(selected)
        orchestrator._maintenance_cursors[cursor_name] = cursor
        return {
            "batch_size": 1,
            "replayed": 1,
            "deferred": len(rows) > 1,
            "cursor": cursor,
            "error": None,
            "batch_completed": True,
        }

    orchestrator._replay_project_integrated_audit_batch = replay
    first_history = schedule_project_historical_replay(
        orchestrator, jobs, "project-1"
    )
    assert first_history is not None
    live = jobs.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="LIVE-TASK",
            generation="live-generation",
            action="integration_attempt",
            idempotency_key="live-generation",
            priority=0,
        )
    )
    claimed_live = jobs.claim_next(lease_owner="live-worker", lease_seconds=30)
    assert claimed_live is not None and claimed_live.job_id == live.job_id
    jobs.complete(live.job_id, claimed_live.lease_token)

    backend = OrchestratorIntegrationActionBackend(
        orchestrator,
        SimpleNamespace(project_id="project-1", tracker=Tracker([])),
    )
    history_worker = DurableWorkflowWorker(
        store=jobs,
        handlers={
            "historical_audit_replay_batch": IntegrationActionHandler(
                "historical_audit_replay_batch",
                backend,
                domain=WorkflowActionDomain.AUDIT,
            )
        },
        transition_services={},
        worker_id="history-worker",
        lease_seconds=30,
        heartbeat_seconds=10,
    )

    results = [await history_worker.run_once() for _ in range(3)]

    assert {result.disposition for result in results} == {
        WorkflowRunDisposition.COMPLETED
    }
    assert replayed == ["HIST-0", "HIST-1", "HIST-2"]
    history_jobs = [
        job for job in jobs.list_jobs() if job.action == "historical_audit_replay_batch"
    ]
    assert len(history_jobs) == 3
    assert len({job.generation for job in history_jobs}) == 3
    assert schedule_project_historical_replay(
        orchestrator, jobs, "project-1"
    ) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("existing_queue_row", [False, True])
async def test_missing_integration_fact_recovers_through_real_decision_and_worker(
    tmp_path,
    existing_queue_row,
):
    task = issue("TASK-A")
    task.parent_id = "E-1"
    task.integration = None
    task.work_branch = "TASK-A"
    task.head_sha = "a" * 40
    tracker = MetadataTracker([task])
    queue = IntegrationQueueStore(str(tmp_path / "integration-queue.sqlite3"))
    if existing_queue_row:
        queue.enqueue(
            project_id="project-1",
            epic_id="E-1",
            task_id="TASK-A",
            task_branch="TASK-A",
            head_sha="a" * 40,
        )
    fact_collector = collector(tracker)
    jobs = WorkflowJobStore(str(tmp_path / "workflow-jobs.sqlite3"))
    controller = IntegrationWorkflowController(
        collector=fact_collector,
        store=jobs,
    )
    _batch, scheduled = controller.reconcile([task])
    assert scheduled.jobs_created == 1
    assert jobs.list_jobs()[0].action == "integration_recovery"
    orchestrator = SimpleNamespace(
        integration_queue=queue,
        project_store=SimpleNamespace(
            epic_branch_name=lambda epic_id: f"epic/{epic_id}"
        ),
        request_refresh=lambda: None,
    )
    backend = OrchestratorIntegrationActionBackend(
        orchestrator,
        SimpleNamespace(
            project_id="project-1",
            tracker=tracker,
            collector=fact_collector,
        ),
    )
    worker = DurableWorkflowWorker(
        store=jobs,
        handlers={
            "integration_recovery": IntegrationActionHandler(
                "integration_recovery",
                backend,
                domain=WorkflowActionDomain.TRACKER,
            )
        },
        transition_services={},
        worker_id="recovery-worker",
        lease_seconds=30,
        heartbeat_seconds=10,
    )

    result = await worker.run_once()

    assert result.disposition is WorkflowRunDisposition.COMPLETED
    recovered = queue.get("project-1", "TASK-A")
    assert recovered is not None
    assert recovered.state == "ready"
    record = tracker.fetch_issue_detail("TASK-A").integration
    assert record.state == "ready"
    assert record.task_branch == "TASK-A"
    assert record.head_sha == "a" * 40


@pytest.mark.asyncio
async def test_missing_integration_fact_rejects_stale_existing_queue_row(tmp_path):
    task = issue("TASK-A")
    task.parent_id = "E-1"
    task.integration = None
    task.work_branch = "TASK-A"
    task.head_sha = "b" * 40
    tracker = MetadataTracker([task])
    queue = IntegrationQueueStore(str(tmp_path / "integration-queue.sqlite3"))
    queued = queue.enqueue(
        project_id="project-1",
        epic_id="E-1",
        task_id="TASK-A",
        task_branch="TASK-A",
        head_sha="a" * 40,
    )
    fact_collector = collector(tracker)
    decision = evaluate_task(task, fact_collector.collect("TASK-A"))
    backend = OrchestratorIntegrationActionBackend(
        SimpleNamespace(
            integration_queue=queue,
            project_store=SimpleNamespace(
                epic_branch_name=lambda epic_id: f"epic/{epic_id}"
            ),
        ),
        SimpleNamespace(
            project_id="project-1",
            tracker=tracker,
            collector=fact_collector,
        ),
    )
    context = SimpleNamespace(
        job=SimpleNamespace(
            project_id="project-1",
            task_id="TASK-A",
            generation="generation-1",
            checkpoint={
                "revalidation": {
                    "evidence_revision": decision.evidence_revision,
                    "details": {
                        "integration_queue_present": True,
                        "integration_queue_generation": (
                            queued.authority_generation()
                        ),
                        "integration_queue_branch": queued.task_branch,
                        "integration_queue_head": queued.head_sha,
                        "task_branch": task.work_branch,
                        "task_head": task.head_sha,
                    }
                }
            },
        ),
        check_interrupted=lambda: None,
    )

    with pytest.raises(WorkflowActionError, match="task authority"):
        await backend.apply_action("integration_recovery", context)

    assert tracker.fetch_issue_detail("TASK-A").integration is None
    assert queue.get("project-1", "TASK-A") == queued


@pytest.mark.asyncio
async def test_integration_recovery_rejects_replacement_after_revalidation(tmp_path):
    task = issue("TASK-A")
    task.parent_id = "E-1"
    task.integration = None
    task.work_branch = "TASK-A"
    task.head_sha = "a" * 40
    tracker = MetadataTracker([task])
    fact_collector = collector(tracker)
    decision = evaluate_task(task, fact_collector.collect("TASK-A"))
    queue = IntegrationQueueStore(str(tmp_path / "integration-queue.sqlite3"))
    original = queue.enqueue(
        project_id="project-1",
        epic_id="E-1",
        task_id="TASK-A",
        task_branch="TASK-A",
        head_sha="a" * 40,
    )
    backend = OrchestratorIntegrationActionBackend(
        SimpleNamespace(
            integration_queue=queue,
            project_store=SimpleNamespace(
                epic_branch_name=lambda epic_id: f"epic/{epic_id}"
            ),
        ),
        SimpleNamespace(
            project_id="project-1",
            tracker=tracker,
            collector=fact_collector,
        ),
    )
    context = SimpleNamespace(
        job=SimpleNamespace(
            project_id="project-1",
            task_id="TASK-A",
            checkpoint={
                "revalidation": {
                    "evidence_revision": decision.evidence_revision,
                    "details": {
                        "integration_queue_present": True,
                        "integration_queue_generation": original.authority_generation(),
                        "integration_queue_branch": original.task_branch,
                        "integration_queue_head": original.head_sha,
                        "task_branch": "TASK-A",
                        "task_head": "a" * 40,
                    },
                }
            },
        ),
        check_interrupted=lambda: None,
    )
    replacement = queue.enqueue(
        project_id="project-1",
        epic_id="E-1",
        task_id="TASK-A",
        task_branch="TASK-A",
        head_sha="b" * 40,
    )

    with pytest.raises(WorkflowActionError, match="generation changed"):
        await backend.apply_action("integration_recovery", context)

    assert tracker.fetch_issue_detail("TASK-A").integration is None
    assert queue.get("project-1", "TASK-A") == replacement


@pytest.mark.asyncio
async def test_integration_recovery_rejects_task_revision_change_after_revalidation(
    tmp_path,
):
    task = issue("TASK-A")
    task.parent_id = "E-1"
    task.integration = None
    task.work_branch = "TASK-A"
    task.head_sha = "a" * 40
    tracker = MetadataTracker([task])
    fact_collector = collector(tracker)
    decision = evaluate_task(task, fact_collector.collect("TASK-A"))
    queue = IntegrationQueueStore(str(tmp_path / "integration-queue.sqlite3"))
    backend = OrchestratorIntegrationActionBackend(
        SimpleNamespace(
            integration_queue=queue,
            project_store=SimpleNamespace(
                epic_branch_name=lambda epic_id: f"epic/{epic_id}"
            ),
        ),
        SimpleNamespace(
            project_id="project-1",
            tracker=tracker,
            collector=fact_collector,
        ),
    )
    context = SimpleNamespace(
        job=SimpleNamespace(
            project_id="project-1",
            task_id="TASK-A",
            checkpoint={
                "revalidation": {
                    "evidence_revision": decision.evidence_revision,
                    "details": {
                        "integration_queue_present": False,
                        "task_branch": "TASK-A",
                        "task_head": "a" * 40,
                    },
                }
            },
        ),
        check_interrupted=lambda: None,
    )
    task.head_sha = "b" * 40

    with pytest.raises(WorkflowActionError, match="evidence changed"):
        await backend.apply_action("integration_recovery", context)

    assert tracker.fetch_issue_detail("TASK-A").integration is None
    assert queue.get("project-1", "TASK-A") is None


@pytest.mark.asyncio
async def test_terminal_stage_rejects_queue_record_branch_mismatch(tmp_path):
    selected = issue("TASK-A", state="integrated", head="a" * 40)
    selected.parent_id = "E-1"
    selected.integration = replace(
        selected.integration,
        state="integrated",
        task_branch="replacement-branch",
        integrated_sha="a" * 40,
    )
    tracker = Tracker([selected])
    queue = IntegrationQueueStore(str(tmp_path / "integration.sqlite3"))
    queue.enqueue(
        project_id="project-1",
        epic_id="E-1",
        task_id="TASK-A",
        task_branch="TASK-A",
        head_sha="a" * 40,
    )
    claimed = queue.claim_next(
        project_id="project-1",
        epic_id="E-1",
        lease_owner="legacy",
        dependency_map={"TASK-A": ()},
        satisfied=set(),
    )
    assert claimed is not None
    assert queue.complete("project-1", "TASK-A", lease_owner="legacy")
    staged = []
    backend = OrchestratorIntegrationActionBackend(
        SimpleNamespace(
            integration_queue=queue,
            _stage_integrated_task_audit=(
                lambda row, **_kwargs: staged.append(row.task_id)
            ),
        ),
        SimpleNamespace(project_id="project-1", tracker=tracker),
    )
    backend._landing = lambda issue: landed_fact()
    context = SimpleNamespace(
        job=SimpleNamespace(
            project_id="project-1",
            task_id="TASK-A",
            generation="generation-1",
            checkpoint={
                "revalidation": {
                    "details": {
                        "integration_queue_generation": queue.get(
                            "project-1", "TASK-A"
                        ).authority_generation(),
                        "integration_queue_branch": "TASK-A",
                        "integration_queue_head": "a" * 40,
                    }
                }
            },
        ),
        check_interrupted=lambda: None,
    )

    with pytest.raises(WorkflowActionError, match="terminal tracker landing"):
        await backend.apply_action("integration_terminal_stage", context)

    assert staged == []


def test_stale_revalidation_is_read_only_for_legacy_tracker_checkpoint(tmp_path):
    selected = issue("TASK-A", state="integrated", head="b" * 40)
    selected.parent_id = "E-1"
    selected.integration = replace(
        selected.integration,
        state="integrated",
        base_branch="epic/E-1",
        integrated_sha="c" * 40,
    )
    tracker = MetadataTracker([selected])
    queue = IntegrationQueueStore(str(tmp_path / "integration.sqlite3"))
    predecessor = queue.enqueue(
        project_id="project-1",
        epic_id="E-1",
        task_id="TASK-A",
        task_branch="TASK-A",
        head_sha="a" * 40,
    )
    fact_collector = collector(tracker)
    peer_notices = []
    backend = OrchestratorIntegrationActionBackend(
        SimpleNamespace(
            integration_queue=queue,
            project_store=SimpleNamespace(
                epic_branch_name=lambda epic_id: f"epic/{epic_id}"
            ),
            _notify_integrated_task_peers=(
                lambda **kwargs: peer_notices.append(kwargs)
            ),
        ),
        SimpleNamespace(
            project_id="project-1",
            tracker=tracker,
            collector=fact_collector,
        ),
    )
    backend._landing = lambda _issue: landed_fact(
        revision="c" * 40,
        target_sha="d" * 40,
    )
    context = SimpleNamespace(
        job=SimpleNamespace(
            project_id="project-1",
            task_id="TASK-A",
            generation="legacy-generation",
            expected_evidence_revision="",
        ),
        check_interrupted=lambda: None,
    )

    before_record = selected.integration
    revalidation = backend.revalidate_action(
        "integration_terminal_stage", context
    )

    assert not revalidation.current
    assert queue.get("project-1", "TASK-A") == predecessor
    assert selected.integration == before_record
    assert peer_notices == []


@pytest.mark.asyncio
async def test_terminal_apply_normalizes_exact_legacy_checkpoint_then_notifies(
    tmp_path,
):
    selected = issue("TASK-A", state="integrated", head="b" * 40)
    selected.parent_id = "E-1"
    selected.integration = replace(
        selected.integration,
        state="integrated",
        mode="queue",
        base_branch="epic/E-1",
        integrated_sha="c" * 40,
    )
    tracker = MetadataTracker([selected])
    queue = IntegrationQueueStore(str(tmp_path / "integration.sqlite3"))
    predecessor = queue.enqueue(
        project_id="project-1",
        epic_id="E-1",
        task_id="TASK-A",
        task_branch="TASK-A",
        head_sha="a" * 40,
    )
    peer_notices = []

    async def stage(row, **_kwargs):
        selected.state = "In Validation"

    backend = OrchestratorIntegrationActionBackend(
        SimpleNamespace(
            integration_queue=queue,
            _stage_integrated_task_audit=stage,
            _notify_integrated_task_peers=(
                lambda **kwargs: peer_notices.append(kwargs)
            ),
        ),
        SimpleNamespace(project_id="project-1", tracker=tracker),
    )
    backend._landing = lambda _issue: landed_fact(
        revision="c" * 40,
        target_sha="d" * 40,
    )
    context = SimpleNamespace(
        job=SimpleNamespace(
            project_id="project-1",
            task_id="TASK-A",
            generation="legacy-generation",
            checkpoint={
                "revalidation": {
                    "head_sha": "b" * 40,
                    "details": {
                        "integration_queue_generation": (
                            predecessor.authority_generation()
                        ),
                        "integration_queue_branch": predecessor.task_branch,
                        "integration_queue_head": predecessor.head_sha,
                    },
                }
            },
        ),
        check_interrupted=lambda: None,
    )

    effect = await backend.apply_action("integration_terminal_stage", context)

    normalized = queue.get("project-1", "TASK-A")
    assert normalized is not None
    assert normalized.state == "integrated"
    assert normalized.rebased_from_head_sha == predecessor.head_sha
    assert normalized.head_sha == "b" * 40
    assert normalized.integrated_sha == "c" * 40
    assert peer_notices == [
        {
            "project_id": "project-1",
            "task_id": "TASK-A",
            "epic_id": "E-1",
            "integrated_sha": "c" * 40,
        }
    ]
    assert effect.receipt["queue_generation"] == normalized.authority_generation()


@pytest.mark.asyncio
async def test_terminal_legacy_checkpoint_cas_loss_has_no_peer_side_effect(
    tmp_path,
):
    selected = issue("TASK-A", state="integrated", head="b" * 40)
    selected.parent_id = "E-1"
    selected.integration = replace(
        selected.integration,
        state="integrated",
        mode="queue",
        base_branch="epic/E-1",
        integrated_sha="c" * 40,
    )
    tracker = MetadataTracker([selected])
    queue = IntegrationQueueStore(str(tmp_path / "integration.sqlite3"))
    predecessor = queue.enqueue(
        project_id="project-1",
        epic_id="E-1",
        task_id="TASK-A",
        task_branch="TASK-A",
        head_sha="a" * 40,
    )
    peer_notices = []
    backend = OrchestratorIntegrationActionBackend(
        SimpleNamespace(
            integration_queue=queue,
            _stage_integrated_task_audit=(
                lambda *_args, **_kwargs: pytest.fail("audit was staged")
            ),
            _notify_integrated_task_peers=(
                lambda **kwargs: peer_notices.append(kwargs)
            ),
        ),
        SimpleNamespace(project_id="project-1", tracker=tracker),
    )
    backend._landing = lambda _issue: landed_fact(
        revision="c" * 40,
        target_sha="d" * 40,
    )
    queue.normalize_legacy_tracker_checkpoint = lambda *args, **kwargs: None
    context = SimpleNamespace(
        job=SimpleNamespace(
            project_id="project-1",
            task_id="TASK-A",
            generation="legacy-generation",
            checkpoint={
                "revalidation": {
                    "head_sha": "b" * 40,
                    "details": {
                        "integration_queue_generation": (
                            predecessor.authority_generation()
                        ),
                        "integration_queue_branch": predecessor.task_branch,
                        "integration_queue_head": predecessor.head_sha,
                    },
                }
            },
        ),
        check_interrupted=lambda: None,
    )

    with pytest.raises(WorkflowActionError, match="before normalization"):
        await backend.apply_action("integration_terminal_stage", context)

    assert queue.get("project-1", "TASK-A") == predecessor
    assert peer_notices == []


@pytest.mark.asyncio
async def test_epic_branch_repair_receives_only_the_job_queue_row(tmp_path):
    selected = issue("TASK-A")
    selected.parent_id = "E-1"
    sibling = issue("TASK-B")
    sibling.parent_id = "E-1"
    tracker = Tracker([selected, sibling])
    queue = IntegrationQueueStore(str(tmp_path / "integration.sqlite3"))
    for task in (selected, sibling):
        queue.enqueue(
            project_id="project-1",
            epic_id="E-1",
            task_id=task.identifier,
            task_branch=task.identifier,
            head_sha=task.integration.head_sha,
        )
    captured = []

    def repair(**kwargs):
        assert kwargs["authority_check"]()
        captured.append(tuple(item.task_id for item in kwargs["queue_items"]))
        return True

    orchestrator = SimpleNamespace(
        integration_queue=queue,
        _integration_dependency_map=lambda issues, rows: {"TASK-A": ()},
        _integration_satisfied_dependencies=lambda *args, **kwargs: set(),
        _detect_and_repair_integration_queue_staleness_block=repair,
    )
    backend = OrchestratorIntegrationActionBackend(
        orchestrator,
        SimpleNamespace(project_id="project-1", tracker=tracker),
    )
    context = SimpleNamespace(
        job=SimpleNamespace(
            project_id="project-1",
            task_id="TASK-A",
            generation="generation-1",
            checkpoint={
                "revalidation": {
                    "details": {
                        "integration_queue_generation": queue.get(
                            "project-1", "TASK-A"
                        ).authority_generation()
                    }
                }
            },
        ),
        check_interrupted=lambda: None,
    )

    effect = await backend.apply_action("epic_branch_reconciliation", context)

    assert captured == [("TASK-A",)]
    assert effect.receipt["repair_scheduled"] is True


def issue(identifier, *, dependencies=(), state="ready", head=None):
    head = head or (identifier[-1].lower() * 40)
    return Issue(
        id=identifier,
        identifier=identifier,
        title=f"Integrate {identifier}",
        description="Actionable integration fixture",
        state=READY_TO_INTEGRATE,
        project_id="project-1",
        blocked_by=[
            BlockerRef(identifier=dependency, state="Open")
            for dependency in dependencies
        ],
        work_branch=identifier,
        target_branch="main",
        integration=IntegrationRecord(
            state=state,
            task_branch=identifier,
            base_branch="main",
            head_sha=head,
        ),
    )


def collector(tracker, landing_collector=None):
    return WorkflowFactCollector(
        project_id="project-1",
        tracker=tracker,
        landing_collector=landing_collector,
        sources={
            FactDomain.TERMINAL_AUDIT: lambda _: {"phase": "queued"},
            FactDomain.REVIEW_CI: lambda _: {"state": "open"},
            FactDomain.IMPLEMENTATION_AUTHORITY: lambda _: {},
            FactDomain.RETRY_BUDGET: lambda _: {"remaining": 3},
            FactDomain.CONFIG: lambda _: {"version": 1},
        },
    )


@pytest.mark.parametrize(
    ("parent_id", "record_mode", "record_state", "expected_mode", "expected_job"),
    [
        (None, None, "ready", "standalone", "standalone_delivery"),
        ("", "standalone", "ready", "standalone", "standalone_delivery"),
        ("E-1", "standalone", "ready", "queue", "integration_attempt"),
        (None, "queue", "queued", "queue", "integration_attempt"),
    ],
)
def test_production_facts_route_only_actual_standalone_records_to_direct_delivery(
    parent_id,
    record_mode,
    record_state,
    expected_mode,
    expected_job,
):
    task = issue("TASK-A", state=record_state)
    task.parent_id = parent_id
    task.integration = replace(task.integration, mode=record_mode)
    fact_collector = collector(Tracker([task]))

    facts = fact_collector.collect("TASK-A")
    decision = evaluate_task(task, facts)

    assert facts.fact(FactDomain.INTEGRATION).value["mode"] == expected_mode
    assert decision.durable_jobs == (expected_job,)


def test_synthetic_top_level_mapping_cannot_select_queue_delivery():
    task = issue("TASK-A")
    task.parent_id = None
    task.integration = {
        "state": "ready",
        "mode": "queue",
        "task_branch": "TASK-A",
        "base_branch": "main",
        "head_sha": "a" * 40,
    }
    fact_collector = collector(Tracker([task]))

    facts = fact_collector.collect("TASK-A")
    decision = evaluate_task(task, facts)

    assert facts.fact(FactDomain.INTEGRATION).value["mode"] == "standalone"
    assert decision.durable_jobs == ("standalone_delivery",)


def test_controller_evaluates_every_topological_head_and_schedules_one_job(tmp_path):
    tasks = [
        issue("TASK-A"),
        issue("TASK-B"),
        issue("TASK-C", dependencies=("TASK-A",)),
        issue("TASK-D", dependencies=("TASK-B",)),
    ]
    tracker = Tracker(tasks)
    store = WorkflowJobStore(str(tmp_path / "integration.sqlite3"))
    controller = IntegrationWorkflowController(
        collector=collector(tracker), store=store
    )

    batch, scheduled = controller.reconcile(tasks)

    assert batch.topological_batches == (("TASK-A", "TASK-B"), ("TASK-C", "TASK-D"))
    assert batch.cyclic_tasks == ()
    assert {item.task.identifier for item in batch.tasks} == {
        "TASK-A",
        "TASK-B",
        "TASK-C",
        "TASK-D",
    }
    assert {
        item.decision.disposition
        for item in batch.tasks
        if item.task.identifier in {"TASK-A", "TASK-B"}
    } == {TaskDisposition.RETRY_SCHEDULED}
    assert scheduled.jobs_created == 2
    assert {job.task_id for job in store.list_jobs()} == {"TASK-A", "TASK-B"}
    store.close()


def test_bounded_controller_rotates_across_all_eligible_integrations(tmp_path):
    tasks = [issue(f"TASK-{suffix}") for suffix in "ABC"]
    store = WorkflowJobStore(str(tmp_path / "integration.sqlite3"))
    controller = IntegrationWorkflowController(
        collector=collector(Tracker(tasks)), store=store, decision_limit=1
    )

    observed = {
        controller.evaluate(tasks).tasks[0].task.identifier for _ in range(3)
    }

    assert observed == {"TASK-A", "TASK-B", "TASK-C"}
    store.close()


def test_dependency_cycle_is_visible_without_hiding_other_ready_work(tmp_path):
    tasks = [
        issue("TASK-A", dependencies=("TASK-B",)),
        issue("TASK-B", dependencies=("TASK-A",)),
        issue("TASK-C"),
    ]
    store = WorkflowJobStore(str(tmp_path / "cycles.sqlite3"))
    controller = IntegrationWorkflowController(
        collector=collector(Tracker(tasks)), store=store
    )

    batch, _ = controller.reconcile(tasks)

    assert batch.topological_batches == (("TASK-C",),)
    assert batch.cyclic_tasks == ("TASK-A", "TASK-B")
    assert {item.decision.disposition for item in batch.tasks[:2]} == {
        TaskDisposition.BLOCKED
    }
    assert {job.task_id for job in store.list_jobs()} == {"TASK-C"}
    store.close()


def test_decision_and_queue_projection_have_exact_reason_parity(tmp_path):
    tasks = [issue("TASK-A"), issue("TASK-B", dependencies=("TASK-A",))]
    store = WorkflowJobStore(str(tmp_path / "projection.sqlite3"))
    controller = IntegrationWorkflowController(
        collector=collector(Tracker(tasks)), store=store
    )
    batch, _ = controller.reconcile(tasks)

    projections = {item.task_id: item for item in controller.projections()}

    for item in batch.tasks:
        projection = projections[item.task.identifier]
        assert projection.reason_code == item.decision.reason_code
        assert projection.disposition == item.decision.disposition.value
        assert projection.waiting_on == tuple(
            unmet.subject for unmet in item.decision.unmet_prerequisites
        )
        assert projection.action_required == item.decision.action_required
    assert projections["TASK-A"].active_job_state == "queued"
    assert projections["TASK-B"].active_job_state is None
    store.close()


@pytest.mark.timeout(30)  # 402 SQLite job writes at WAL-mode throughput takes ~17 s
def test_hundreds_of_history_rows_do_not_hide_eligible_heads(tmp_path):
    history = [issue(f"HISTORY-{index:03d}") for index in range(400)]
    ready = [issue("TASK-X"), issue("TASK-Y")]
    tracker = Tracker([*history, *ready])
    store = WorkflowJobStore(str(tmp_path / "history.sqlite3"))
    controller = IntegrationWorkflowController(
        collector=collector(tracker), store=store
    )

    batch, scheduled = controller.reconcile([*history, *ready])

    assert len(batch.tasks) == 402
    assert scheduled.jobs_created == 402
    assert {"TASK-X", "TASK-Y"} <= {job.task_id for job in store.list_jobs(limit=1000)}
    assert {"TASK-X", "TASK-Y"} <= {
        projection.task_id for projection in controller.projections()
    }
    store.close()


@pytest.mark.parametrize(
    ("status", "route", "retryable"),
    [
        ("integrated", IntegrationRoute.LANDED, False),
        ("conflict", IntegrationRoute.REBASE, False),
        ("needs_rebase", IntegrationRoute.REBASE, False),
        ("ci_failure", IntegrationRoute.CI_FIX, False),
        ("worktree_recovery", IntegrationRoute.RETRY, True),
        ("missing_epic", IntegrationRoute.RETRY, True),
        ("authentication_failed", IntegrationRoute.RETRY, True),
        ("stale_head", IntegrationRoute.SUPERSEDED, False),
        ("dirty_worktree", IntegrationRoute.ACTION_REQUIRED, False),
        ("unknown", IntegrationRoute.ACTION_REQUIRED, False),
    ],
)
def test_every_executor_result_has_one_bounded_route(status, route, retryable):
    classified = classify_integration_result(
        IntegrationExecutionResult(status, f"{status} result")
    )
    assert classified.route is route
    assert classified.retryable is retryable


def git(repo, *args):
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "Integration Harness",
            "GIT_AUTHOR_EMAIL": "integration@example.invalid",
            "GIT_COMMITTER_NAME": "Integration Harness",
            "GIT_COMMITTER_EMAIL": "integration@example.invalid",
        },
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


class GitBackend:
    def __init__(self, repo, *, generation, head):
        self.repo = repo
        self.generation = generation
        self.head = head
        self.collector = GitLandingCollector(repo, project_id="project-1")
        self.integration_calls = 0

    def revalidate(self, context):
        return RevalidationResult(
            self.generation,
            evidence_revision=context.job.expected_evidence_revision,
            head_sha=self.head,
        )

    def observe_landing(self, context):
        return self.collector.collect(
            LandingRequest("task", "main", context.job.expected_head_sha)
        )

    def integrate(self, context):
        self.integration_calls += 1
        git(self.repo, "merge", "--no-ff", "task", "-m", "integrate task")
        return IntegrationExecutionResult(
            "integrated",
            "integrated",
            integrated_sha=git(self.repo, "rev-parse", "HEAD"),
        )

    def build_transition(self, context, verification):
        return None


@pytest.mark.asyncio
async def test_handler_proves_exact_head_with_real_git_and_survives_ref_deletion(
    tmp_path,
):
    git(tmp_path, "init", "-b", "main")
    (tmp_path / "base.txt").write_text("base\n")
    git(tmp_path, "add", "base.txt")
    git(tmp_path, "commit", "-m", "base")
    git(tmp_path, "checkout", "-b", "task")
    (tmp_path / "task.txt").write_text("task\n")
    git(tmp_path, "add", "task.txt")
    git(tmp_path, "commit", "-m", "task")
    head = git(tmp_path, "rev-parse", "HEAD")
    git(tmp_path, "checkout", "main")

    path = str(tmp_path / "jobs.sqlite3")
    store = WorkflowJobStore(path)
    store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-1",
            generation="generation-1",
            action="integration_attempt",
            idempotency_key="TASK-1:integration",
            expected_head_sha=head,
        )
    )
    backend = GitBackend(tmp_path, generation="generation-1", head=head)
    worker = DurableWorkflowWorker(
        store=store,
        handlers={"integration_attempt": IntegrationWorkflowHandler(backend)},
        transition_services={},
        worker_id="integrator",
        lease_seconds=30,
        heartbeat_seconds=10,
    )

    result = await worker.run_once()

    assert result.disposition is WorkflowRunDisposition.COMPLETED
    assert backend.integration_calls == 1
    assert store.list_jobs()[0].state is WorkflowJobState.COMPLETED
    git(tmp_path, "branch", "-D", "task")
    landing = backend.collector.collect(LandingRequest("task", "main", head))
    assert landing.state is LandingState.LANDED
    store.close()


@pytest.mark.asyncio
async def test_changed_source_head_does_not_invalidate_recorded_exact_landing(tmp_path):
    git(tmp_path, "init", "-b", "main")
    (tmp_path / "value.txt").write_text("base\n")
    git(tmp_path, "add", "value.txt")
    git(tmp_path, "commit", "-m", "base")
    git(tmp_path, "checkout", "-b", "task")
    (tmp_path / "value.txt").write_text("first\n")
    git(tmp_path, "commit", "-am", "first")
    first_head = git(tmp_path, "rev-parse", "HEAD")
    git(tmp_path, "checkout", "main")
    git(tmp_path, "merge", "--no-ff", "task", "-m", "land first")
    git(tmp_path, "checkout", "task")
    (tmp_path / "value.txt").write_text("second\n")
    git(tmp_path, "commit", "-am", "second")
    git(tmp_path, "checkout", "main")

    landing = GitLandingCollector(tmp_path, project_id="project-1").collect(
        LandingRequest("task", "main", first_head)
    )

    assert landing.state is LandingState.LANDED
    assert landing.revision == first_head


def test_integrated_record_uses_landing_fact_to_schedule_terminal_stage(tmp_path):
    git(tmp_path, "init", "-b", "main")
    (tmp_path / "value.txt").write_text("base\n")
    git(tmp_path, "add", "value.txt")
    git(tmp_path, "commit", "-m", "base")
    git(tmp_path, "checkout", "-b", "TASK-A")
    (tmp_path / "value.txt").write_text("task\n")
    git(tmp_path, "commit", "-am", "task")
    head = git(tmp_path, "rev-parse", "HEAD")
    git(tmp_path, "checkout", "main")
    git(tmp_path, "merge", "--no-ff", "TASK-A", "-m", "integrate")
    task = issue("TASK-A", state="integrated", head=head)
    task.integration = replace(task.integration, integrated_sha=head)
    tracker = Tracker([task])
    store = WorkflowJobStore(str(tmp_path / "landing.sqlite3"))
    controller = IntegrationWorkflowController(
        collector=collector(
            tracker, GitLandingCollector(tmp_path, project_id="project-1")
        ),
        store=store,
    )

    batch, scheduled = controller.reconcile([task])

    decision = batch.tasks[0].decision
    assert decision.reason_code == "integration.landing_proven"
    assert decision.recommended_status == "In Validation"
    assert decision.durable_jobs == ("integration_terminal_stage",)
    assert scheduled.jobs_created == 1
    store.close()


def test_unproven_integrated_record_is_informational_and_retry_scheduled(tmp_path):
    task = issue("TASK-A", state="integrated", head="a" * 40)
    store = WorkflowJobStore(str(tmp_path / "unproven.sqlite3"))
    controller = IntegrationWorkflowController(
        collector=collector(Tracker([task])), store=store
    )

    batch, scheduled = controller.reconcile([task])

    decision = batch.tasks[0].decision
    assert decision.reason_code == "integration.landing_unproven"
    assert decision.alert_level.value == "info"
    assert not decision.action_required
    assert decision.durable_jobs == ("integration_landing_refresh",)
    assert scheduled.jobs_created == 1
    store.close()


class ResultBackend:
    def __init__(self, result):
        self.result = result

    def revalidate(self, context):
        return RevalidationResult(context.job.generation)

    def observe_landing(self, context):
        return None

    def integrate(self, context):
        return self.result

    def build_transition(self, context, verification):
        return None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "disposition", "state"),
    [
        (
            "worktree_recovery",
            WorkflowRunDisposition.RETRY_SCHEDULED,
            WorkflowJobState.RETRY_WAIT,
        ),
        (
            "dirty_worktree",
            WorkflowRunDisposition.ACTION_REQUIRED,
            WorkflowJobState.EXHAUSTED,
        ),
    ],
)
async def test_recovery_is_retryable_but_unsafe_mutation_is_actionable(
    tmp_path, status, disposition, state
):
    store = WorkflowJobStore(str(tmp_path / f"{status}.sqlite3"))
    store.enqueue(
        WorkflowJobSpec(
            "project-1",
            "TASK-1",
            "generation-1",
            "integration_attempt",
            f"TASK-1:{status}",
        )
    )
    worker = DurableWorkflowWorker(
        store=store,
        handlers={
            "integration_attempt": IntegrationWorkflowHandler(
                ResultBackend(IntegrationExecutionResult(status, status))
            )
        },
        transition_services={},
        worker_id="integrator",
        lease_seconds=30,
        heartbeat_seconds=10,
    )

    result = await worker.run_once()

    assert result.disposition is disposition
    assert store.list_jobs()[0].state is state
    store.close()
