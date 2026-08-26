"""Shared-decision and durable-job integration domain coverage."""

from __future__ import annotations

import asyncio
from contextlib import nullcontext
import hashlib
import os
import subprocess
import threading
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock
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
    IntegrationLandingRequestResolver,
    OrchestratorIntegrationActionBackend,
    IntegrationRoute,
    IntegrationWorkflowController,
    IntegrationWorkflowHandler,
    StandaloneDeliveryOutcome,
    classify_integration_result,
    schedule_project_historical_replay,
)
from oompah.models import BlockerRef, EpicRebaseState, Issue
from oompah.orchestrator import Orchestrator
from oompah.statuses import IN_VALIDATION
from oompah.terminal_audit import (
    AuditAttempt,
    RequestState,
    TargetState,
    TerminalAuditRecord,
    Verdict,
    compute_evidence_fingerprint,
    compute_issue_evidence_fingerprint,
)
from oompah.terminal_audit_metadata import METADATA_KEY, TerminalAuditMetadata
from oompah.workflow_contract import READY_TO_INTEGRATE, TaskDisposition
from oompah.workflow_facts import (
    FactDomain,
    GitLandingCollector,
    LandingFact,
    LandingRequest,
    LandingState,
    WorkflowFactCollector,
)
from oompah.workflow_jobs import (
    WorkflowFailureCategory,
    WorkflowJobSpec,
    WorkflowJobState,
    WorkflowJobStore,
    WorkflowJobStoreError,
)
from oompah.work_decision import evaluate_task
from oompah.workflow_worker import (
    DurableWorkflowWorker,
    EffectObservation,
    EffectResult,
    RevalidationResult,
    VerificationResult,
    WorkflowActionDomain,
    WorkflowAdministrativeDeferral,
    WorkflowActionError,
    WorkflowActionSuperseded,
    WorkflowJobContext,
    WorkflowRunDisposition,
)


class Tracker:
    def __init__(self, issues, metadata=None):
        self.issues = {issue.identifier: issue for issue in issues}
        self.metadata = metadata or {}

    def fetch_issue_detail(self, identifier):
        return self.issues.get(identifier)

    def fetch_children(self, identifier):
        return [
            issue for issue in self.issues.values() if issue.parent_id == identifier
        ]

    def fetch_all_issues(self):
        return list(self.issues.values())

    def get_metadata(self, identifier):
        return self.metadata.get(identifier, {})


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
        workflow_local_authority_check,
    ):
        calls.append(
            (
                project_id,
                task_id,
                expected_task_branch,
                expected_head_sha,
                workflow_generation,
                workflow_authority_check(),
                workflow_local_authority_check(),
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
async def test_standalone_review_capacity_wait_is_administrative_deferral():
    selected = issue("TASK-CAPACITY")
    selected.parent_id = None
    selected.integration = replace(selected.integration, mode="standalone")
    tracker = Tracker([selected])
    fact_collector = collector(tracker)
    decision = evaluate_task(selected, fact_collector.collect(selected.identifier))
    calls = []

    def defer_for_capacity(*args, **kwargs):
        calls.append((args, kwargs))
        return "capacity_wait"

    backend = OrchestratorIntegrationActionBackend(
        SimpleNamespace(
            _reconcile_one_standalone_ready_to_integrate_task=(
                defer_for_capacity
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
            task_id=selected.identifier,
            generation="generation-capacity",
            job_id="job-capacity",
            lease_token="lease-capacity",
            checkpoint={
                "revalidation": {
                    "evidence_revision": decision.evidence_revision,
                    "details": {
                        "task_branch": selected.integration.task_branch,
                        "task_head": selected.integration.head_sha,
                        "task_target": "main",
                    },
                }
            },
        ),
        check_interrupted=lambda: None,
    )

    with pytest.raises(
        WorkflowAdministrativeDeferral,
        match="waiting for review capacity",
    ) as deferred:
        await backend.apply_action("standalone_delivery", context)

    assert deferred.value.effect_not_started is True
    assert len(calls) == 1
    assert tracker.fetch_issue_detail(selected.identifier).state == (
        READY_TO_INTEGRATE
    )


@pytest.mark.asyncio
async def test_standalone_remote_head_drift_supersedes_exact_accepted_generation():
    accepted_head = "a" * 40
    observed_head = "b" * 40
    selected = issue("TASK-DRIFT", head=accepted_head)
    selected.parent_id = None
    selected.integration = replace(selected.integration, mode="standalone")
    tracker = Tracker([selected])
    fact_collector = collector(tracker)
    decision = evaluate_task(selected, fact_collector.collect(selected.identifier))
    drift = StandaloneDeliveryOutcome(
        accepted_head=accepted_head,
        observed_branch_head=observed_head,
        observed_review_head=observed_head,
        review_id="14",
        reason="remote branch advanced beyond the accepted submission",
    )
    backend = OrchestratorIntegrationActionBackend(
        SimpleNamespace(
            _reconcile_one_standalone_ready_to_integrate_task=(
                lambda *_args, **_kwargs: drift
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
            task_id=selected.identifier,
            generation="generation-drift",
            job_id="job-drift",
            lease_token="lease-drift",
            checkpoint={
                "revalidation": {
                    "evidence_revision": decision.evidence_revision,
                    "details": {
                        "task_branch": selected.integration.task_branch,
                        "task_head": accepted_head,
                        "task_target": "main",
                    },
                }
            },
        ),
        check_interrupted=lambda: None,
    )

    with pytest.raises(WorkflowActionSuperseded) as raised:
        await backend.apply_action("standalone_delivery", context)

    assert accepted_head in str(raised.value)
    assert observed_head in str(raised.value)
    assert "review #14" in str(raised.value)
    assert "explicit exact-head resubmission is required" in str(raised.value)
    assert raised.value.replacement_generation == (
        f"standalone-resubmission-required:{observed_head}"
    )
    assert selected.state == READY_TO_INTEGRATE
    assert selected.integration.head_sha == accepted_head
    assert selected.review_number is None


@pytest.mark.asyncio
async def test_standalone_drift_outcome_for_another_accepted_head_fails_closed():
    accepted_head = "a" * 40
    selected = issue("TASK-DRIFT-RACE", head=accepted_head)
    selected.parent_id = None
    selected.integration = replace(selected.integration, mode="standalone")
    tracker = Tracker([selected])
    fact_collector = collector(tracker)
    decision = evaluate_task(selected, fact_collector.collect(selected.identifier))
    foreign_drift = StandaloneDeliveryOutcome(
        accepted_head="c" * 40,
        observed_branch_head="b" * 40,
        reason="a concurrent submission replaced the accepted head",
    )
    backend = OrchestratorIntegrationActionBackend(
        SimpleNamespace(
            _reconcile_one_standalone_ready_to_integrate_task=(
                lambda *_args, **_kwargs: foreign_drift
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
            task_id=selected.identifier,
            generation="generation-drift-race",
            job_id="job-drift-race",
            lease_token="lease-drift-race",
            checkpoint={
                "revalidation": {
                    "evidence_revision": decision.evidence_revision,
                    "details": {
                        "task_branch": selected.integration.task_branch,
                        "task_head": accepted_head,
                        "task_target": "main",
                    },
                }
            },
        ),
        check_interrupted=lambda: None,
    )

    with pytest.raises(
        WorkflowActionError,
        match="waiting for an exact forge effect",
    ):
        await backend.apply_action("standalone_delivery", context)

    assert selected.integration.head_sha == accepted_head


@pytest.mark.asyncio
async def test_concurrent_exact_resubmission_preserves_new_head_and_retires_old_job():
    accepted_head = "a" * 40
    observed_head = "b" * 40
    selected = issue("TASK-DRIFT-RESUBMIT-RACE", head=accepted_head)
    selected.parent_id = None
    selected.integration = replace(selected.integration, mode="standalone")
    tracker = Tracker([selected])
    fact_collector = collector(tracker)
    decision = evaluate_task(selected, fact_collector.collect(selected.identifier))

    def deliver(*_args, **_kwargs):
        selected.integration = replace(
            selected.integration,
            head_sha=observed_head,
        )
        return StandaloneDeliveryOutcome(
            accepted_head=accepted_head,
            observed_branch_head=observed_head,
            reason="remote branch advanced beyond the accepted submission",
        )

    backend = OrchestratorIntegrationActionBackend(
        SimpleNamespace(
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
            task_id=selected.identifier,
            generation="generation-resubmit-race",
            job_id="job-resubmit-race",
            lease_token="lease-resubmit-race",
            checkpoint={
                "revalidation": {
                    "evidence_revision": decision.evidence_revision,
                    "details": {
                        "task_branch": selected.integration.task_branch,
                        "task_head": accepted_head,
                        "task_target": "main",
                    },
                }
            },
        ),
        check_interrupted=lambda: None,
    )

    with pytest.raises(WorkflowActionSuperseded):
        await backend.apply_action("standalone_delivery", context)

    assert selected.integration.head_sha == observed_head
    assert selected.state == READY_TO_INTEGRATE


@pytest.mark.asyncio
async def test_capacity_deferrals_beyond_budget_preserve_standalone_attempts(
    tmp_path,
):
    selected = issue("TASK-CAPACITY-BUDGET")
    selected.parent_id = None
    selected.integration = replace(selected.integration, mode="standalone")
    tracker = Tracker([selected])
    fact_collector = collector(tracker)
    decision = evaluate_task(selected, fact_collector.collect(selected.identifier))
    capacity_blocked = [True]

    def deliver(*_args, **_kwargs):
        if capacity_blocked[0]:
            return "capacity_wait"
        selected.state = "In Review"
        selected.review_number = "17"
        selected.review_head = selected.integration.head_sha
        return None

    integration_queue = IntegrationQueueStore(
        str(tmp_path / "capacity-integration.sqlite3")
    )
    backend = OrchestratorIntegrationActionBackend(
        SimpleNamespace(
            integration_queue=integration_queue,
            _reconcile_one_standalone_ready_to_integrate_task=deliver,
        ),
        SimpleNamespace(
            project_id="project-1",
            tracker=tracker,
            collector=fact_collector,
        ),
    )
    store = WorkflowJobStore(str(tmp_path / "capacity-jobs.sqlite3"))
    queued = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id=selected.identifier,
            generation="capacity-generation",
            action="standalone_delivery",
            idempotency_key="capacity-generation:standalone",
            expected_evidence_revision=decision.evidence_revision,
            expected_head_sha=selected.integration.head_sha,
            max_attempts=2,
        )
    )
    worker = DurableWorkflowWorker(
        store=store,
        handlers={
            "standalone_delivery": IntegrationActionHandler(
                "standalone_delivery",
                backend,
                domain=WorkflowActionDomain.FORGE,
            )
        },
        transition_services={},
        worker_id="capacity-worker",
        retry_delay_seconds=0,
    )

    for _ in range(5):
        deferred = await worker.run_once()
        assert deferred.disposition is WorkflowRunDisposition.RETRY_SCHEDULED
        waiting = store.get(queued.job_id)
        assert waiting.state is WorkflowJobState.RETRY_WAIT
        assert waiting.attempts == 0

    capacity_blocked[0] = False
    completed = await worker.run_once()

    assert completed.disposition is WorkflowRunDisposition.COMPLETED
    assert store.get(queued.job_id).attempts == 1
    store.close()
    integration_queue.close()


@pytest.mark.asyncio
async def test_standalone_drift_preserves_retry_budget_across_restart_and_resubmit(
    tmp_path,
):
    accepted_head = "a" * 40
    observed_head = "b" * 40
    selected = issue("TASK-DRIFT-RESTART", head=accepted_head)
    selected.parent_id = None
    selected.integration = replace(selected.integration, mode="standalone")
    tracker = Tracker([selected])
    fact_collector = collector(tracker)
    drifted = [True]
    integration_queue = IntegrationQueueStore(
        str(tmp_path / "standalone-drift-integration.sqlite3")
    )

    def deliver(_project_id, task_id, **_kwargs):
        if drifted[0]:
            return StandaloneDeliveryOutcome(
                accepted_head=accepted_head,
                observed_branch_head=observed_head,
                observed_review_head=observed_head,
                review_id="14",
                reason="remote branch advanced beyond the accepted submission",
            )
        delivered = tracker.fetch_issue_detail(task_id)
        delivered.state = "In Review"
        delivered.review_number = "14"
        delivered.review_head = observed_head
        return None

    backend = OrchestratorIntegrationActionBackend(
        SimpleNamespace(
            integration_queue=integration_queue,
            _reconcile_one_standalone_ready_to_integrate_task=deliver,
        ),
        SimpleNamespace(
            project_id="project-1",
            tracker=tracker,
            collector=fact_collector,
        ),
    )
    database = tmp_path / "standalone-drift.sqlite3"
    store = WorkflowJobStore(str(database))
    old_decision = evaluate_task(
        selected,
        fact_collector.collect(selected.identifier),
    )
    stale = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id=selected.identifier,
            generation="stale-accepted-generation",
            action="standalone_delivery",
            idempotency_key="stale-accepted-generation:standalone",
            expected_evidence_revision=old_decision.evidence_revision,
            expected_head_sha=accepted_head,
            max_attempts=2,
        )
    )

    first = await DurableWorkflowWorker(
        store=store,
        handlers={
            "standalone_delivery": IntegrationActionHandler(
                "standalone_delivery",
                backend,
                domain=WorkflowActionDomain.FORGE,
            )
        },
        transition_services={},
        worker_id="drift-worker",
        retry_delay_seconds=0,
    ).run_once()

    assert first.disposition is WorkflowRunDisposition.SUPERSEDED
    retired = store.get(stale.job_id)
    assert retired.state is WorkflowJobState.SUPERSEDED
    assert retired.attempts == 1
    assert retired.max_attempts == 2
    assert observed_head in str(retired.last_error or "")
    assert selected.integration.head_sha == accepted_head
    assert selected.state == READY_TO_INTEGRATE
    store.close()

    reopened = WorkflowJobStore(str(database))
    idle = await DurableWorkflowWorker(
        store=reopened,
        handlers={
            "standalone_delivery": IntegrationActionHandler(
                "standalone_delivery",
                backend,
                domain=WorkflowActionDomain.FORGE,
            )
        },
        transition_services={},
        worker_id="restarted-drift-worker",
        retry_delay_seconds=0,
    ).run_once()
    assert idle.disposition is WorkflowRunDisposition.IDLE
    assert reopened.get(stale.job_id).state is WorkflowJobState.SUPERSEDED

    # Model the only authorized adoption path: an explicit exact-head submit
    # replaces the immutable integration record and creates a fresh decision.
    selected.integration = replace(selected.integration, head_sha=observed_head)
    drifted[0] = False
    replacement_decision = evaluate_task(
        selected,
        fact_collector.collect(selected.identifier),
    )
    replacement = reopened.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id=selected.identifier,
            generation="explicit-resubmission-generation",
            action="standalone_delivery",
            idempotency_key="explicit-resubmission-generation:standalone",
            expected_evidence_revision=replacement_decision.evidence_revision,
            expected_head_sha=observed_head,
            max_attempts=2,
        )
    )
    completed = await DurableWorkflowWorker(
        store=reopened,
        handlers={
            "standalone_delivery": IntegrationActionHandler(
                "standalone_delivery",
                backend,
                domain=WorkflowActionDomain.FORGE,
            )
        },
        transition_services={},
        worker_id="resubmitted-drift-worker",
        retry_delay_seconds=0,
    ).run_once()

    assert completed.disposition is WorkflowRunDisposition.COMPLETED
    assert reopened.get(replacement.job_id).state is WorkflowJobState.COMPLETED
    assert selected.integration.head_sha == observed_head
    assert selected.review_head == observed_head
    assert selected.state == "In Review"
    reopened.close()
    integration_queue.close()


def test_legacy_capacity_exhaustion_proof_uses_exact_checkpoint_submission():
    selected = issue("TASK-LEGACY-CAPACITY", head="a" * 40)
    selected.parent_id = None
    selected.integration = replace(selected.integration, mode="standalone")
    tracker = Tracker([selected])
    backend = OrchestratorIntegrationActionBackend(
        SimpleNamespace(_project_review_capacity=lambda _project_id: (1, 1, True)),
        SimpleNamespace(project_id="project-1", tracker=tracker),
    )
    job = SimpleNamespace(
        action="standalone_delivery",
        state=WorkflowJobState.EXHAUSTED,
        last_error="standalone delivery is waiting for an exact forge effect",
        task_id=selected.identifier,
        expected_head_sha=None,
        checkpoint={
            "revalidation": {
                "head_sha": selected.integration.head_sha,
                "details": {
                    "task_branch": selected.integration.task_branch,
                    "task_head": selected.integration.head_sha,
                },
            }
        },
    )

    assert backend.legacy_exhaustion_is_capacity_wait(job)

    job.checkpoint["revalidation"]["head_sha"] = "b" * 40
    job.checkpoint["revalidation"]["details"]["task_head"] = "b" * 40
    assert not backend.legacy_exhaustion_is_capacity_wait(job)


def test_legacy_capacity_exhaustion_proof_rejects_non_capacity_failure():
    selected = issue("TASK-LEGACY-FAILURE", head="a" * 40)
    selected.parent_id = None
    selected.integration = replace(selected.integration, mode="standalone")
    tracker = Tracker([selected])
    backend = OrchestratorIntegrationActionBackend(
        SimpleNamespace(_project_review_capacity=lambda _project_id: (0, 1, False)),
        SimpleNamespace(project_id="project-1", tracker=tracker),
    )
    job = SimpleNamespace(
        action="standalone_delivery",
        state=WorkflowJobState.EXHAUSTED,
        last_error="standalone delivery is waiting for an exact forge effect",
        task_id=selected.identifier,
        expected_head_sha=selected.integration.head_sha,
        checkpoint={
            "revalidation": {
                "details": {
                    "task_branch": selected.integration.task_branch,
                    "task_head": selected.integration.head_sha,
                }
            }
        },
    )

    assert not backend.legacy_exhaustion_is_capacity_wait(job)


@pytest.mark.asyncio
async def test_standalone_workflow_hot_check_ignores_project_lock_contention():
    """A busy project fence is unknown to the hot poll, not revocation."""

    selected = issue("TASK-CONTENTION")
    selected.parent_id = None
    selected.integration = replace(selected.integration, mode="standalone")
    tracker = Tracker([selected])
    project_lock = threading.RLock()
    lock_held = threading.Event()
    release_lock = threading.Event()
    full_started = threading.Event()
    full_result: list[bool] = []
    workflow_live = [True]

    def hold_project_lock() -> None:
        with project_lock:
            lock_held.set()
            assert release_lock.wait(timeout=2)

    holder = threading.Thread(target=hold_project_lock)
    holder.start()
    assert lock_held.wait(timeout=1)

    def deliver(
        _project_id,
        task_id,
        *,
        workflow_authority_check,
        workflow_local_authority_check,
        **_kwargs,
    ):
        assert workflow_local_authority_check()

        def run_full_check() -> None:
            full_started.set()
            full_result.append(workflow_authority_check())

        full = threading.Thread(target=run_full_check)
        full.start()
        assert full_started.wait(timeout=1)
        full.join(timeout=0.05)
        assert full.is_alive(), "full authority check did not wait for project lock"
        assert workflow_local_authority_check()
        release_lock.set()
        full.join(timeout=1)
        assert not full.is_alive()
        assert full_result == [True]
        delivered = tracker.fetch_issue_detail(task_id)
        delivered.state = "In Review"
        delivered.review_number = "17"
        delivered.review_head = delivered.integration.head_sha

    project = SimpleNamespace(default_branch="main")
    backend = OrchestratorIntegrationActionBackend(
        SimpleNamespace(
            project_store=SimpleNamespace(
                get=lambda _project_id: project,
                project_write_lock=lambda _project_id: project_lock,
            ),
            _reconcile_one_standalone_ready_to_integrate_task=deliver,
        ),
        SimpleNamespace(
            project_id="project-1",
            tracker=tracker,
            collector=collector(tracker),
        ),
    )
    decision = evaluate_task(selected, backend.binding.collector.collect(selected.id))
    context = SimpleNamespace(
        job=SimpleNamespace(
            project_id="project-1",
            task_id=selected.identifier,
            generation="generation-1",
            job_id="job-1",
            lease_token="lease-1",
            checkpoint={
                "revalidation": {
                    "evidence_revision": decision.evidence_revision,
                    "details": {
                        "task_branch": selected.integration.task_branch,
                        "task_head": selected.integration.head_sha,
                        "task_target": "main",
                    },
                }
            },
        ),
        check_interrupted=lambda: (
            None
            if workflow_live[0]
            else (_ for _ in ()).throw(RuntimeError("lease revoked"))
        ),
    )

    try:
        effect = await backend.apply_action("standalone_delivery", context)
    finally:
        release_lock.set()
        holder.join(timeout=1)

    assert not holder.is_alive()
    assert effect.receipt["review_number"] == "17"


@pytest.mark.asyncio
async def test_standalone_workflow_revocation_wins_during_project_contention():
    """A confirmed local lease loss still cancels while the project is busy."""

    selected = issue("TASK-CONTENTION-REVOKED")
    selected.parent_id = None
    selected.integration = replace(selected.integration, mode="standalone")
    tracker = Tracker([selected])
    project_lock = threading.RLock()
    lock_held = threading.Event()
    release_lock = threading.Event()
    workflow_live = [True]

    def hold_project_lock() -> None:
        with project_lock:
            lock_held.set()
            assert release_lock.wait(timeout=2)

    holder = threading.Thread(target=hold_project_lock)
    holder.start()
    assert lock_held.wait(timeout=1)

    def deliver(
        *_args,
        workflow_authority_check,
        workflow_local_authority_check,
        **_kwargs,
    ):
        assert workflow_local_authority_check()
        full_result: list[bool] = []

        def run_full_check() -> None:
            full_result.append(workflow_authority_check())

        full = threading.Thread(target=run_full_check)
        full.start()
        full.join(timeout=0.05)
        assert full.is_alive(), "full authority check did not wait for project lock"
        workflow_live[0] = False
        assert not workflow_local_authority_check()
        release_lock.set()
        full.join(timeout=1)
        assert not full.is_alive()
        assert full_result == [False]

    project = SimpleNamespace(default_branch="main")
    backend = OrchestratorIntegrationActionBackend(
        SimpleNamespace(
            project_store=SimpleNamespace(
                get=lambda _project_id: project,
                project_write_lock=lambda _project_id: project_lock,
            ),
            _reconcile_one_standalone_ready_to_integrate_task=deliver,
        ),
        SimpleNamespace(
            project_id="project-1",
            tracker=tracker,
            collector=collector(tracker),
        ),
    )
    decision = evaluate_task(selected, backend.binding.collector.collect(selected.id))
    context = SimpleNamespace(
        job=SimpleNamespace(
            project_id="project-1",
            task_id=selected.identifier,
            generation="generation-1",
            job_id="job-1",
            lease_token="lease-1",
            checkpoint={
                "revalidation": {
                    "evidence_revision": decision.evidence_revision,
                    "details": {
                        "task_branch": selected.integration.task_branch,
                        "task_head": selected.integration.head_sha,
                        "task_target": "main",
                    },
                }
            },
        ),
        check_interrupted=lambda: (
            None
            if workflow_live[0]
            else (_ for _ in ()).throw(RuntimeError("lease revoked"))
        ),
    )

    try:
        with pytest.raises(WorkflowActionError, match="waiting for an exact"):
            await backend.apply_action("standalone_delivery", context)
    finally:
        release_lock.set()
        holder.join(timeout=1)

    assert not holder.is_alive()
    assert tracker.fetch_issue_detail(selected.id).state == READY_TO_INTEGRATE


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
        if field == "oompah.integration":
            self.issues[identifier].integration = IntegrationRecord.from_dict(value)
            return
        if field == "oompah.target_branch":
            self.issues[identifier].target_branch = str(value or "").strip() or None
            return
        raise AssertionError(field)


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


def enqueue_durable_integration_job(store, context, *, max_attempts=5):
    revalidation = context.job.checkpoint["revalidation"]
    return store.enqueue(
        WorkflowJobSpec(
            project_id=context.job.project_id,
            task_id=context.job.task_id,
            generation=context.job.generation,
            action="integration_attempt",
            idempotency_key=context.job.idempotency_key,
            expected_evidence_revision=revalidation["evidence_revision"],
            expected_head_sha=revalidation["head_sha"],
            max_attempts=max_attempts,
        )
    )


def durable_integration_worker(
    store,
    backend,
    *,
    worker_id="integration-worker-1",
    lease_seconds=30,
    heartbeat_seconds=10,
    operation_timeout_seconds=1,
    phase_observer=None,
):
    return DurableWorkflowWorker(
        store=store,
        handlers={
            "integration_attempt": IntegrationActionHandler(
                "integration_attempt",
                backend,
                domain=WorkflowActionDomain.GIT,
            )
        },
        transition_services={},
        worker_id=worker_id,
        lease_seconds=lease_seconds,
        heartbeat_seconds=heartbeat_seconds,
        operation_timeout_seconds=operation_timeout_seconds,
        retry_delay_seconds=0,
        phase_observer=phase_observer,
    )


@pytest.mark.asyncio
async def test_workflow_integration_attempt_uses_job_authority_without_queue_lease(
    tmp_path,
):
    calls = []

    def execute(
        row,
        *,
        workflow_authority,
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
        assert workflow_authority()
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


def test_real_executor_wrapper_uses_exact_unleased_workflow_authority(
    tmp_path,
    monkeypatch,
):
    queue = IntegrationQueueStore(str(tmp_path / "integration.sqlite3"))
    row = queue.enqueue(
        project_id="project-1",
        epic_id="E-1",
        task_id="TASK-A",
        task_branch="TASK-A",
        head_sha="a" * 40,
        base_sha="b" * 40,
    )
    observed = {}
    clock = {"now": 1000.0}
    jobs = WorkflowJobStore(
        str(tmp_path / "workflow.sqlite3"),
        clock=lambda: clock["now"],
    )
    queued_job = jobs.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-A",
            generation="generation-1",
            action="integration_attempt",
            idempotency_key="integration:TASK-A:generation-1",
        )
    )
    claimed_job = jobs.claim_next(
        lease_owner="workflow-worker-1",
        lease_seconds=30,
    )
    assert claimed_job is not None
    assert claimed_job.job_id == queued_job.job_id
    lease_lost = asyncio.Event()
    interrupted = asyncio.Event()
    context = WorkflowJobContext(
        claimed_job,
        lease_lost,
        interrupted,
        lambda: jobs.owns_live_lease(
            context.job.job_id,
            str(context.job.lease_token or ""),
        ),
    )

    def workflow_authority():
        try:
            context.check_interrupted()
        except Exception:
            return False
        return True

    def execute_integration(**kwargs):
        observed.update(kwargs)
        assert kwargs["commit_allowed"]()
        candidate = kwargs["canonicalize_candidate"]("c" * 40, "d" * 40)
        assert candidate.is_current()
        assert candidate.owner.head_sha == "c" * 40
        assert candidate.owner.authority_generation == candidate.generation
        assert candidate.generation == (
            f"workflow:job-1:generation-1:candidate:{'c' * 40}:{'d' * 40}"
        )
        assert kwargs["gate_owner_factory"] is None
        clock["now"] += 31
        assert jobs.recover_expired() == 1
        replacement = jobs.claim_next(
            lease_owner="workflow-worker-2",
            lease_seconds=30,
        )
        assert replacement is not None
        assert replacement.lease_token != context.job.lease_token
        assert not candidate.is_current()
        return IntegrationExecutionResult(
            "cancelled",
            "workflow authority withdrawn",
        )

    monkeypatch.setattr(
        "oompah.orchestrator.execute_integration",
        execute_integration,
    )
    project = SimpleNamespace(
        id="project-1",
        repo_url="",
        repo_path=str(tmp_path),
        access_token=None,
        forge_kind="github",
    )
    orchestrator = SimpleNamespace(
        project_store=SimpleNamespace(
            get=lambda _project_id: project,
            epic_branch_name=lambda _epic_id: "epic/E-1",
            create_epic_worktree=lambda *_args, **_kwargs: str(
                tmp_path / "epic"
            ),
            create_worktree=lambda *_args, **_kwargs: str(tmp_path / "task"),
            project_write_lock=lambda _project_id: nullcontext(),
        ),
        _branch_quality_gate=object(),
        _quality_gate_command=lambda _project: "make test",
        _integration_dependency_authority=lambda *_args, **_kwargs: pytest.fail(
            "durable workflow authority must not require a queue lease"
        ),
        _canonicalize_integration_candidate=lambda *_args, **_kwargs: pytest.fail(
            "durable workflow candidates must not use leased queue CAS"
        ),
    )

    try:
        result = Orchestrator._execute_integration_item(
            orchestrator,
            row,
            workflow_authority=workflow_authority,
            gate_generation="workflow:job-1:generation-1",
        )
    finally:
        jobs.close()

    assert result.status == "cancelled"
    assert observed["gate_generation"] == "workflow:job-1:generation-1"


def test_executor_wrapper_rejects_ambiguous_workflow_authority():
    row = SimpleNamespace(lease_owner=None)

    def allowed():
        return True

    missing_generation = Orchestrator._execute_integration_item(
        SimpleNamespace(),
        row,
        workflow_authority=allowed,
    )
    mixed_authority = Orchestrator._execute_integration_item(
        SimpleNamespace(),
        row,
        commit_allowed=allowed,
        workflow_authority=allowed,
        gate_generation="workflow:job-1:generation-1",
    )
    leased_workflow = Orchestrator._execute_integration_item(
        SimpleNamespace(),
        SimpleNamespace(lease_owner="legacy-owner"),
        workflow_authority=allowed,
        gate_generation="workflow:job-1:generation-1",
    )

    for result in (missing_generation, mixed_authority, leased_workflow):
        assert result.status == "authority_unavailable"
        assert "exclusive, unleased, and generation-bound" in result.message

    withdrawn = Orchestrator._execute_integration_item(
        SimpleNamespace(),
        row,
        workflow_authority=lambda: False,
        gate_generation="workflow:job-1:generation-1",
    )

    def unavailable():
        raise OSError("workflow lease store unavailable")

    unavailable_result = Orchestrator._execute_integration_item(
        SimpleNamespace(),
        row,
        workflow_authority=unavailable,
        gate_generation="workflow:job-1:generation-1",
    )

    assert withdrawn.status == "cancelled"
    assert "before worktree recovery" in withdrawn.message
    assert unavailable_result.status == "authority_unavailable"
    assert "before worktree recovery" in unavailable_result.message


@pytest.mark.asyncio
@pytest.mark.timeout(10)
async def test_durable_integration_worker_heartbeats_unleased_effect(tmp_path):
    authority_checks = []
    clock = {"now": 0.0}
    clock_lock = threading.Lock()
    renewal_lock = threading.Lock()
    first_renewed_jobs = []
    renewed = threading.Event()

    def read_clock():
        with clock_lock:
            return clock["now"]

    def execute(row, *, workflow_authority, **_kwargs):
        authority_checks.append(workflow_authority())
        assert renewed.wait(timeout=2)
        # Cross the original lease deadline deterministically after the first
        # renewal.  The renewed lease remains current, while a missing or late
        # heartbeat would make the second authority check fail closed.
        with clock_lock:
            clock["now"] = max(clock["now"], 6.0)
        authority_checks.append(workflow_authority())
        return IntegrationExecutionResult(
            "integrated",
            "landed under renewed workflow authority",
            expected_epic_sha=row.base_sha,
            rebased_task_sha=row.head_sha,
            integrated_sha="c" * 40,
        )

    backend, context, queue, _tracker = integration_backend_context(
        tmp_path,
        execute=execute,
    )
    store = WorkflowJobStore(
        str(tmp_path / "durable-workflow.sqlite3"),
        clock=read_clock,
    )
    original_renew = store.renew

    def renew_after_advancing_clock(*args, **kwargs):
        with renewal_lock:
            if not first_renewed_jobs:
                with clock_lock:
                    clock["now"] = max(clock["now"], 4.0)
            job = original_renew(*args, **kwargs)
            if not first_renewed_jobs:
                assert job.lease_expires_at is not None
                assert job.lease_expires_at > 6.0
                first_renewed_jobs.append(job)
                renewed.set()
            return job

    store.renew = renew_after_advancing_clock
    try:
        queued = enqueue_durable_integration_job(store, context)
        result = await durable_integration_worker(
            store,
            backend,
            lease_seconds=5,
            heartbeat_seconds=0.05,
        ).run_once()

        assert result.disposition is WorkflowRunDisposition.COMPLETED
        completed = store.get(queued.job_id)
        assert completed.state is WorkflowJobState.COMPLETED
        assert completed.attempts == 1
        assert authority_checks == [True, True]
        assert first_renewed_jobs[0].lease_expires_at > 6.0
        assert len(
            [
                event
                for event in store.events(queued.job_id)
                if event.event_type == "renewed"
            ]
        ) >= 1
        integrated = queue.get("project-1", "TASK-A")
        assert integrated is not None
        assert integrated.state == "integrated"
        assert integrated.attempts == 1
    finally:
        store.close()


@pytest.mark.asyncio
async def test_timed_out_integration_quarantines_and_fences_late_executor(
    tmp_path,
):
    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()
    late_authority = []

    def execute(_row, *, workflow_authority, **_kwargs):
        started.set()
        release.wait(timeout=2)
        late_authority.append(workflow_authority())
        finished.set()
        return IntegrationExecutionResult(
            "cancelled",
            "timed-out executor lost workflow authority",
        )

    backend, context, queue, _tracker = integration_backend_context(
        tmp_path,
        execute=execute,
    )
    store = WorkflowJobStore(str(tmp_path / "timed-out-workflow.sqlite3"))
    try:
        queued = enqueue_durable_integration_job(store, context)
        result = await durable_integration_worker(
            store,
            backend,
            lease_seconds=1,
            heartbeat_seconds=0.02,
            operation_timeout_seconds=0.05,
        ).run_once()

        assert started.is_set()
        assert result.disposition is WorkflowRunDisposition.ACTION_REQUIRED
        quarantined = store.get(queued.job_id)
        assert quarantined.state is WorkflowJobState.RUNNING
        assert quarantined.phase == "quarantined"
        assert quarantined.lease_expires_at is None
        assert quarantined.attempts == 1
        release.set()
        assert await asyncio.to_thread(finished.wait, 1)
        assert late_authority == [False]
        current = queue.get("project-1", "TASK-A")
        assert current is not None
        assert current.state == "ready"
        assert current.attempts == 0
    finally:
        release.set()
        store.close()


@pytest.mark.asyncio
async def test_restart_replays_integration_receipt_without_reexecuting_effect(
    tmp_path,
):
    path = str(tmp_path / "restart-workflow.sqlite3")
    executions = []

    def execute(row, *, workflow_authority, **_kwargs):
        assert workflow_authority()
        executions.append(row.authority_generation())
        return IntegrationExecutionResult(
            "integrated",
            "landed before simulated process death",
            expected_epic_sha=row.base_sha,
            rebased_task_sha=row.head_sha,
            integrated_sha="c" * 40,
        )

    backend, context, queue, _tracker = integration_backend_context(
        tmp_path,
        execute=execute,
    )
    store = WorkflowJobStore(path)
    queued = enqueue_durable_integration_job(store, context)
    crashed = False

    class ProcessDeath(BaseException):
        pass

    def crash_after_effect(phase, _job):
        nonlocal crashed
        if phase == "effect_returned" and not crashed:
            crashed = True
            raise ProcessDeath()

    with pytest.raises(ProcessDeath):
        await durable_integration_worker(
            store,
            backend,
            phase_observer=crash_after_effect,
        ).run_once()
    assert store.get(queued.job_id).state is WorkflowJobState.RUNNING
    store.close()

    reopened = WorkflowJobStore(path)
    try:
        assert reopened.recover_abandoned() == 1
        result = await durable_integration_worker(
            reopened,
            backend,
            worker_id="integration-worker-2",
        ).run_once()

        assert result.disposition in {
            WorkflowRunDisposition.COMPLETED,
            WorkflowRunDisposition.SUPERSEDED,
        }
        assert len(executions) == 1
        integrated = queue.get("project-1", "TASK-A")
        assert integrated is not None
        assert integrated.state == "integrated"
        assert integrated.attempts == 1
        reopened.integrity_check()
    finally:
        reopened.close()


def test_executor_wrapper_keeps_legacy_unleased_rows_unauthorized(
    tmp_path,
    monkeypatch,
):
    queue = IntegrationQueueStore(str(tmp_path / "integration.sqlite3"))
    row = queue.enqueue(
        project_id="project-1",
        epic_id="E-1",
        task_id="TASK-A",
        task_branch="TASK-A",
        head_sha="a" * 40,
    )
    legacy_authority_checks = []

    def dependency_authority(*_args, **_kwargs):
        legacy_authority_checks.append(True)
        return lambda: False

    def execute_integration(**kwargs):
        assert not kwargs["commit_allowed"]()
        assert kwargs["gate_owner_factory"] is not None
        return IntegrationExecutionResult(
            "cancelled",
            "integration authority was withdrawn before preparation",
        )

    monkeypatch.setattr(
        "oompah.orchestrator.execute_integration",
        execute_integration,
    )
    project = SimpleNamespace(
        id="project-1",
        repo_url="",
        repo_path=str(tmp_path),
        access_token=None,
        forge_kind="github",
    )
    orchestrator = SimpleNamespace(
        project_store=SimpleNamespace(
            get=lambda _project_id: project,
            epic_branch_name=lambda _epic_id: "epic/E-1",
            create_epic_worktree=lambda *_args, **_kwargs: str(
                tmp_path / "epic"
            ),
            create_worktree=lambda *_args, **_kwargs: str(tmp_path / "task"),
            project_write_lock=lambda _project_id: nullcontext(),
        ),
        _branch_quality_gate=object(),
        _quality_gate_command=lambda _project: "make test",
        _integration_dependency_authority=dependency_authority,
        _canonicalize_integration_candidate=lambda *_args, **_kwargs: None,
    )

    result = Orchestrator._execute_integration_item(orchestrator, row)

    assert result.status == "cancelled"
    assert legacy_authority_checks == [True]


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
    nested_target = "epic/E-ROOT--task-E-NEW"
    task = issue("TASK-A", head="a" * 40)
    task.parent_id = "E-NEW"
    task.target_branch = nested_target
    task.integration = replace(
        task.integration,
        mode="queue",
        base_branch=nested_target,
        base_sha="b" * 40,
    )
    parent = issue("E-NEW")
    parent.work_branch = nested_target
    tracker = MetadataTracker([task, parent])
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
    assert current.base_branch == nested_target
    assert current.base_sha == "b" * 40
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
    parent = issue("E-NEW")
    parent.work_branch = "epic/E-NEW"
    tracker = MetadataTracker([task, parent])
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
    assert current.base_branch == "epic/E-NEW"
    assert current.base_sha is None
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
    tracked_issues = [task]
    if replacement_parent is not None:
        parent = issue(replacement_parent)
        parent.work_branch = f"epic/{replacement_parent}"
        tracked_issues.append(parent)
    tracker = MetadataTracker(tracked_issues)
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
        workflow_authority,
        rebased_head_checkpoint,
        **_kwargs,
    ):
        executions.append(row.authority_generation())
        assert workflow_authority()
        # Clearing the durable private-publication bit intentionally revokes
        # old-container delivery authority.  The next job owns containment
        # repair; this invocation must not proceed to the old epic.
        assert not rebased_head_checkpoint(row.head_sha, row.base_sha)
        assert not workflow_authority()
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
async def test_post_landed_parent_queue_reclassifies_and_delivers_after_restart(
    tmp_path,
):
    task = issue("TASK-A", head="a" * 40)
    task.parent_id = "E-1"
    task.target_branch = "epic/E-1"
    task.integration = replace(
        task.integration,
        mode="queue",
        base_branch="epic/E-1",
        base_sha="b" * 40,
    )
    parent = issue("E-1")
    parent.issue_type = "epic"
    parent.parent_id = None
    parent.work_branch = "epic/E-1"
    parent.target_branch = "main"
    parent.integration = None
    tracker = MetadataTracker([task, parent])
    fail_integration_write = {"once": False}
    write_metadata = tracker.set_metadata_field

    def write_with_failure(identifier, field, value):
        if field == "oompah.integration" and fail_integration_write["once"]:
            fail_integration_write["once"] = False
            raise RuntimeError("injected integration metadata failure")
        return write_metadata(identifier, field, value)

    tracker.set_metadata_field = write_with_failure
    fact_collector = collector(tracker)
    decision = evaluate_task(task, fact_collector.collect(task.identifier))
    queue = IntegrationQueueStore(str(tmp_path / "integration.sqlite3"))
    queued = queue.enqueue(
        project_id="project-1",
        epic_id=parent.identifier,
        task_id=task.identifier,
        task_branch=task.integration.task_branch,
        head_sha=task.integration.head_sha,
        base_branch=task.integration.base_branch,
        base_sha=task.integration.base_sha,
    )
    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    store.record_landing_facts(
        project_id="project-1",
        task_id=parent.identifier,
        facts=(
            _parent_scoped_child_fact(
                source=parent.work_branch,
                target=parent.target_branch,
                revision="c" * 40,
            ).to_dict(),
        ),
    )
    project_store = SimpleNamespace(
        epic_branch_name=lambda epic_id: f"epic/{epic_id}",
        get=lambda _project_id: SimpleNamespace(default_branch="main"),
    )
    resolver = IntegrationLandingRequestResolver(
        project_id="project-1",
        tracker=tracker,
        integration_queue=queue,
        project_store=project_store,
        project_default_branch="main",
        workflow_store=store,
        landing_collector=StableParentLandingCollector(),
        parent_source_head_resolver=lambda _branch: "c" * 40,
    )
    controller = IntegrationWorkflowController(
        collector=fact_collector,
        store=store,
        landing_request_resolver=resolver,
    )
    binding = SimpleNamespace(
        project_id="project-1",
        tracker=tracker,
        collector=fact_collector,
        integration_controller=controller,
    )
    backend = OrchestratorIntegrationActionBackend(
        SimpleNamespace(
            integration_queue=queue,
            project_store=project_store,
            _execute_integration_item=lambda *_args, **_kwargs: pytest.fail(
                "stale epic queue must not execute"
            ),
            request_refresh=lambda: None,
        ),
        binding,
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
                        "task_parent": task.parent_id,
                        "task_branch": task.integration.task_branch,
                        "task_head": task.integration.head_sha,
                        "task_target": task.target_branch,
                    },
                }
            },
        ),
        check_interrupted=lambda: None,
    )

    fail_integration_write["once"] = True
    with pytest.raises(RuntimeError, match="injected integration metadata failure"):
        await backend.apply_action("integration_attempt", context)

    partial = tracker.fetch_issue_detail(task.identifier)
    still_queued = queue.get("project-1", task.identifier)
    assert partial.target_branch == "main"
    assert partial.integration.mode == "queue"
    assert partial.integration.base_branch == "epic/E-1"
    assert still_queued is not None and still_queued.state == "ready"
    partial_decision = evaluate_task(
        partial,
        fact_collector.collect(partial.identifier),
    )
    assert partial_decision.durable_jobs == ("integration_attempt",)
    restart_context = SimpleNamespace(
        job=SimpleNamespace(
            project_id="project-1",
            task_id=task.identifier,
            generation="generation-restart",
            job_id="job-restart",
            checkpoint={
                "revalidation": {
                    "evidence_revision": partial_decision.evidence_revision,
                    "details": {
                        "integration_queue_present": True,
                        "integration_queue_generation": (
                            still_queued.authority_generation()
                        ),
                        "integration_queue_epic": still_queued.epic_id,
                        "integration_queue_branch": still_queued.task_branch,
                        "integration_queue_head": still_queued.head_sha,
                        "task_parent": partial.parent_id,
                        "task_branch": partial.integration.task_branch,
                        "task_head": partial.integration.head_sha,
                        "task_target": partial.target_branch,
                    },
                }
            },
        ),
        check_interrupted=lambda: None,
    )
    with pytest.raises(WorkflowActionSuperseded, match="parent landed"):
        await backend.apply_action("integration_attempt", restart_context)

    current = tracker.fetch_issue_detail(task.identifier)
    retired = queue.get("project-1", task.identifier)
    assert current.parent_id == parent.identifier
    assert current.target_branch == "main"
    assert current.integration.mode == "standalone"
    assert current.integration.base_branch == "main"
    assert retired is not None and retired.state == "cancelled"
    replacement = evaluate_task(current, fact_collector.collect(current.identifier))
    assert replacement.durable_jobs == ("standalone_delivery",)

    deliveries = []

    def deliver(*args, **kwargs):
        deliveries.append((args, kwargs))
        current.state = "In Review"
        current.review_number = "42"
        current.review_head = current.integration.head_sha

    restarted = OrchestratorIntegrationActionBackend(
        SimpleNamespace(
            integration_queue=queue,
            project_store=project_store,
            _reconcile_one_standalone_ready_to_integrate_task=deliver,
            request_refresh=lambda: None,
        ),
        binding,
    )
    standalone_context = SimpleNamespace(
        job=SimpleNamespace(
            project_id="project-1",
            task_id=task.identifier,
            generation="generation-2",
            job_id="job-2",
            lease_token="lease-2",
            checkpoint={
                "revalidation": {
                    "evidence_revision": replacement.evidence_revision,
                    "details": {
                        "task_parent": parent.identifier,
                        "task_branch": current.integration.task_branch,
                        "task_head": current.integration.head_sha,
                        "task_target": "main",
                    },
                }
            },
        ),
        check_interrupted=lambda: None,
    )
    effect = await restarted.apply_action("standalone_delivery", standalone_context)

    assert len(deliveries) == 1
    assert effect.receipt["review_number"] == "42"
    assert restarted.verify_action(
        "standalone_delivery", standalone_context, effect
    ).verified
    store.close()
    queue.close()


@pytest.mark.asyncio
async def test_parent_advance_after_standalone_submit_returns_child_to_queue(
    tmp_path,
):
    task = issue("TASK-A", head="a" * 40)
    task.parent_id = "E-1"
    task.target_branch = "main"
    task.integration = replace(
        task.integration,
        mode="standalone",
        post_landed_parent_id="E-1",
        base_branch="main",
        base_sha=None,
    )
    parent = issue("E-1")
    parent.issue_type = "epic"
    parent.parent_id = None
    parent.work_branch = "epic/E-1"
    parent.target_branch = "main"
    parent.integration = None
    tracker = MetadataTracker([task, parent])
    fail_integration_write = {"once": False}
    write_metadata = tracker.set_metadata_field

    def write_with_failure(identifier, field, value):
        if field == "oompah.integration" and fail_integration_write["once"]:
            fail_integration_write["once"] = False
            raise RuntimeError("injected integration metadata failure")
        return write_metadata(identifier, field, value)

    tracker.set_metadata_field = write_with_failure
    fact_collector = collector(tracker)
    standalone = evaluate_task(task, fact_collector.collect(task.identifier))
    assert standalone.durable_jobs == ("standalone_delivery",)

    queue = IntegrationQueueStore(str(tmp_path / "integration.sqlite3"))
    queued = queue.enqueue(
        project_id="project-1",
        epic_id=parent.identifier,
        task_id=task.identifier,
        task_branch=task.integration.task_branch,
        head_sha=task.integration.head_sha,
        base_branch="epic/E-1",
    )
    retired = queue.retire_task_generation(
        "project-1",
        task.identifier,
        expected_generation=queued.authority_generation(),
        reason=STANDALONE_RECLASSIFICATION_REASON,
    )
    assert retired is not None and retired.state == "cancelled"

    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    store.record_landing_facts(
        project_id="project-1",
        task_id=parent.identifier,
        facts=(
            _parent_scoped_child_fact(
                source=parent.work_branch,
                target=parent.target_branch,
                revision="c" * 40,
            ).to_dict(),
        ),
    )
    source_head = {"value": "c" * 40}
    project_store = SimpleNamespace(
        epic_branch_name=lambda epic_id: f"epic/{epic_id}",
        get=lambda _project_id: SimpleNamespace(default_branch="main"),
    )
    resolver = IntegrationLandingRequestResolver(
        project_id="project-1",
        tracker=tracker,
        integration_queue=queue,
        project_store=project_store,
        project_default_branch="main",
        workflow_store=store,
        landing_collector=StableParentLandingCollector(),
        parent_source_head_resolver=lambda _branch: source_head["value"],
    )
    assert resolver.post_landed_parent_target(task) == "main"
    controller = IntegrationWorkflowController(
        collector=fact_collector,
        store=store,
        landing_request_resolver=resolver,
    )
    deliveries = []

    def deliver_after_parent_advance(*_args, **kwargs):
        # The exact standalone check already passed.  Advance the parent before
        # the forge boundary; the workflow callback must revoke this effect.
        source_head["value"] = "d" * 40
        if kwargs["workflow_authority_check"]():
            deliveries.append("delivered")

    backend = OrchestratorIntegrationActionBackend(
        SimpleNamespace(
            integration_queue=queue,
            project_store=project_store,
            _reconcile_one_standalone_ready_to_integrate_task=(
                deliver_after_parent_advance
            ),
            request_refresh=lambda: None,
        ),
        SimpleNamespace(
            project_id="project-1",
            tracker=tracker,
            collector=fact_collector,
            integration_controller=controller,
        ),
    )
    context = SimpleNamespace(
        job=SimpleNamespace(
            project_id="project-1",
            task_id=task.identifier,
            generation="generation-standalone",
            job_id="job-standalone",
            checkpoint={
                "revalidation": {
                    "evidence_revision": standalone.evidence_revision,
                    "details": {
                        "task_parent": parent.identifier,
                        "task_branch": task.integration.task_branch,
                        "task_head": task.integration.head_sha,
                        "task_target": "main",
                    },
                }
            },
        ),
        check_interrupted=lambda: None,
    )

    # The parent advances after the exact standalone check but before the forge
    # effect.  No review/tracker mutation occurs; the next exact retry performs
    # natural queue compensation.
    with pytest.raises(WorkflowActionError, match="exact forge effect"):
        await backend.apply_action("standalone_delivery", context)

    unchanged = tracker.fetch_issue_detail(task.identifier)
    assert deliveries == []
    assert unchanged.target_branch == "main"
    assert unchanged.integration.mode == "standalone"

    fail_integration_write["once"] = True
    with pytest.raises(RuntimeError, match="injected integration metadata failure"):
        await backend.apply_action("standalone_delivery", context)

    partial = tracker.fetch_issue_detail(task.identifier)
    assert partial.target_branch == "epic/E-1"
    assert partial.integration.mode == "standalone"
    assert partial.integration.base_branch == "main"
    partial_decision = evaluate_task(
        partial,
        fact_collector.collect(partial.identifier),
    )
    assert partial_decision.durable_jobs == ("integration_attempt",)
    partial_context = SimpleNamespace(
        job=SimpleNamespace(
            project_id="project-1",
            task_id=task.identifier,
            generation="generation-partial-restart",
            job_id="job-partial-restart",
            checkpoint={
                "revalidation": {
                    "evidence_revision": partial_decision.evidence_revision,
                    "details": {
                        "integration_queue_present": True,
                        "integration_queue_generation": (
                            retired.authority_generation()
                        ),
                        "integration_queue_epic": retired.epic_id,
                        "integration_queue_branch": retired.task_branch,
                        "integration_queue_head": retired.head_sha,
                        "task_parent": parent.identifier,
                        "task_branch": partial.integration.task_branch,
                        "task_head": partial.integration.head_sha,
                        "task_target": partial.target_branch,
                    },
                }
            },
        ),
        check_interrupted=lambda: None,
    )
    with pytest.raises(WorkflowActionSuperseded, match="current parent queue"):
        await backend.apply_action("integration_attempt", partial_context)

    current = tracker.fetch_issue_detail(task.identifier)
    recovered = queue.get("project-1", task.identifier)
    assert deliveries == []
    assert current.target_branch == "epic/E-1"
    assert current.integration.mode == "queue"
    assert current.integration.post_landed_parent_id is None
    assert current.integration.base_branch == "epic/E-1"
    assert current.integration.base_sha is None
    assert recovered is not None
    assert recovered.state == "cancelled"
    assert recovered.last_error == STANDALONE_RECLASSIFICATION_REASON
    assert recovered.epic_id == parent.identifier
    replacement = evaluate_task(current, fact_collector.collect(current.identifier))
    assert replacement.durable_jobs == ("integration_attempt",)

    # A restarted backend consumes the replacement decision and owns the
    # exact cancelled-row CAS.  The stale standalone action never needs a
    # cross-store queue transaction.
    restarted = OrchestratorIntegrationActionBackend(
        SimpleNamespace(
            integration_queue=queue,
            project_store=project_store,
            request_refresh=lambda: None,
        ),
        SimpleNamespace(
            project_id="project-1",
            tracker=tracker,
            collector=fact_collector,
            integration_controller=controller,
        ),
    )
    repair_context = SimpleNamespace(
        job=SimpleNamespace(
            project_id="project-1",
            task_id=task.identifier,
            generation="generation-queue-repair",
            job_id="job-queue-repair",
            checkpoint={
                "revalidation": {
                    "evidence_revision": replacement.evidence_revision,
                    "details": {
                        "integration_queue_present": True,
                        "integration_queue_generation": (
                            recovered.authority_generation()
                        ),
                        "integration_queue_epic": recovered.epic_id,
                        "integration_queue_branch": recovered.task_branch,
                        "integration_queue_head": recovered.head_sha,
                        "task_parent": parent.identifier,
                        "task_branch": current.integration.task_branch,
                        "task_head": current.integration.head_sha,
                        "task_target": current.target_branch,
                    },
                }
            },
        ),
        check_interrupted=lambda: None,
    )
    with pytest.raises(WorkflowActionSuperseded, match="restored to the parent"):
        await restarted.apply_action("integration_attempt", repair_context)

    restored = queue.get("project-1", task.identifier)
    assert restored is not None
    assert restored.state == "ready"
    assert restored.epic_id == parent.identifier
    assert restored.base_branch == "epic/E-1"
    store.close()
    queue.close()


@pytest.mark.asyncio
async def test_parent_relanding_wins_inverse_compensation_race_without_queue_write(
    tmp_path,
):
    task = issue("TASK-A", head="a" * 40)
    task.parent_id = "E-1"
    task.target_branch = "main"
    task.integration = replace(
        task.integration,
        mode="standalone",
        post_landed_parent_id="E-1",
        base_branch="main",
        base_sha=None,
    )
    parent = issue("E-1")
    parent.issue_type = "epic"
    parent.work_branch = "epic/E-1"
    parent.target_branch = "main"
    parent.integration = None
    tracker = MetadataTracker([task, parent])
    writes = []
    write_metadata = tracker.set_metadata_field

    def record_write(*args, **kwargs):
        writes.append((args, kwargs))
        return write_metadata(*args, **kwargs)

    tracker.set_metadata_field = record_write
    fact_collector = collector(tracker)
    decision = evaluate_task(task, fact_collector.collect(task.identifier))
    assert decision.durable_jobs == ("standalone_delivery",)
    queue = IntegrationQueueStore(str(tmp_path / "integration.sqlite3"))
    queued = queue.enqueue(
        project_id="project-1",
        epic_id=parent.identifier,
        task_id=task.identifier,
        task_branch=task.integration.task_branch,
        head_sha=task.integration.head_sha,
        base_branch=parent.work_branch,
    )
    retired = queue.retire_task_generation(
        "project-1",
        task.identifier,
        expected_generation=queued.authority_generation(),
        reason=STANDALONE_RECLASSIFICATION_REASON,
    )
    assert retired is not None

    class RelandingResolver:
        def __init__(self):
            self.calls = 0

        def __call__(self, _issue, *, include_ready=False):
            assert not include_ready
            return ()

        def post_landed_parent_target(self, _issue):
            self.calls += 1
            # Standalone apply first observes an invalid route.  The parent
            # re-lands before the compensation authority cut.
            return None if self.calls == 1 else "main"

        def current_parent_queue_target(self, _issue):
            return "epic/E-1"

    resolver = RelandingResolver()
    project_store = SimpleNamespace(
        epic_branch_name=lambda epic_id: f"epic/{epic_id}",
        get=lambda _project_id: SimpleNamespace(default_branch="main"),
        project_write_lock=lambda _project_id: nullcontext(),
    )
    deliveries = []
    backend = OrchestratorIntegrationActionBackend(
        SimpleNamespace(
            integration_queue=queue,
            project_store=project_store,
            _reconcile_one_standalone_ready_to_integrate_task=(
                lambda *_args, **_kwargs: deliveries.append("delivered")
            ),
            request_refresh=lambda: None,
        ),
        SimpleNamespace(
            project_id="project-1",
            tracker=tracker,
            collector=fact_collector,
            integration_controller=SimpleNamespace(
                landing_request_resolver=resolver,
            ),
        ),
    )
    context = SimpleNamespace(
        job=SimpleNamespace(
            project_id="project-1",
            task_id=task.identifier,
            generation="generation-inverse-race",
            job_id="job-inverse-race",
            checkpoint={
                "revalidation": {
                    "evidence_revision": decision.evidence_revision,
                    "details": {
                        "task_parent": parent.identifier,
                        "task_branch": task.integration.task_branch,
                        "task_head": task.integration.head_sha,
                        "task_target": task.target_branch,
                    },
                }
            },
        ),
        check_interrupted=lambda: None,
    )

    with pytest.raises(WorkflowActionSuperseded, match="landing became current"):
        await backend.apply_action("standalone_delivery", context)

    current = tracker.fetch_issue_detail(task.identifier)
    unchanged = queue.get("project-1", task.identifier)
    assert writes == []
    assert deliveries == []
    assert current.target_branch == "main"
    assert current.integration.mode == "standalone"
    assert current.integration.base_branch == "main"
    assert unchanged == retired
    replacement = evaluate_task(current, fact_collector.collect(current.identifier))
    assert replacement.durable_jobs == ("standalone_delivery",)
    queue.close()


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
    def racing_retire(*_args, **_kwargs):
        task.target_branch = "release/hotfix"
        return None

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
        workflow_authority,
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
        assert not workflow_authority()
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
        workflow_authority,
        rebased_head_prepare,
        rebased_head_checkpoint,
        **_kwargs,
    ):
        assert workflow_authority()
        assert rebased_head_prepare("d" * 40, "e" * 40)
        assert rebased_head_checkpoint("d" * 40, "e" * 40)
        assert workflow_authority()
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
async def test_legacy_queue_claim_fences_late_workflow_executor(tmp_path):
    holder = {}

    def execute(row, *, workflow_authority, **_kwargs):
        assert workflow_authority()
        claimed = holder["queue"].claim_next(
            project_id=row.project_id,
            epic_id=row.epic_id,
            lease_owner="legacy-integrator",
            dependency_map={row.task_id: ()},
            satisfied=set(),
        )
        assert claimed is not None
        assert claimed.lease_owner == "legacy-integrator"
        assert not workflow_authority()
        return IntegrationExecutionResult(
            "cancelled",
            "legacy queue claim replaced workflow authority",
        )

    backend, context, queue, _tracker = integration_backend_context(
        tmp_path,
        execute=execute,
    )
    holder["queue"] = queue

    with pytest.raises(WorkflowActionError, match="replaced workflow authority"):
        await backend.apply_action("integration_attempt", context)

    current = queue.get("project-1", "TASK-A")
    assert current is not None
    assert current.state == "integrating"
    assert current.lease_owner == "legacy-integrator"


@pytest.mark.asyncio
async def test_peer_coordination_replays_before_integrated_metadata(tmp_path):
    backend, context, queue, tracker = integration_backend_context(
        tmp_path,
        execute=lambda *args, **kwargs: IntegrationExecutionResult(
            "integrated", "unused"
        ),
    )
    queued = queue.get("project-1", "TASK-A")
    assert (
        queue.finish_task_generation(
            "project-1",
            "TASK-A",
            expected_generation=queued.authority_generation(),
            state="integrated",
        )
        is not None
    )
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
    nested_target = "epic-OOMPAH-768--task-OOMPAH-804"
    task = issue("TASK-A")
    task.parent_id = "E-1"
    task.integration = None
    task.work_branch = "TASK-A"
    task.target_branch = nested_target
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
            base_branch=nested_target,
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
    assert recovered.base_branch == nested_target
    record = tracker.fetch_issue_detail("TASK-A").integration
    assert record.state == "ready"
    assert record.task_branch == "TASK-A"
    assert record.base_branch == nested_target
    assert record.head_sha == "a" * 40


@pytest.mark.asyncio
async def test_integration_recovery_preserves_recorded_nested_target(tmp_path):
    nested_target = "epic-OOMPAH-768--task-OOMPAH-804"
    task = issue("TASK-A")
    task.parent_id = "E-1"
    task.target_branch = "epic/E-1"
    task.integration = replace(task.integration, base_branch=nested_target)
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
            generation="generation-1",
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

    await backend.apply_action("integration_recovery", context)

    recovered = queue.get("project-1", "TASK-A")
    assert recovered is not None
    assert recovered.base_branch == nested_target
    assert tracker.fetch_issue_detail("TASK-A").integration.base_branch == nested_target


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


def collector(tracker, landing_collector=None, implementation_authority=None):
    return WorkflowFactCollector(
        project_id="project-1",
        tracker=tracker,
        landing_collector=landing_collector,
        sources={
            FactDomain.TERMINAL_AUDIT: lambda _: {"phase": "queued"},
            FactDomain.REVIEW_CI: lambda _: {"state": "open"},
            FactDomain.IMPLEMENTATION_AUTHORITY: (
                implementation_authority or (lambda _: {})
            ),
            FactDomain.RETRY_BUDGET: lambda _: {"remaining": 3},
            FactDomain.CONFIG: lambda _: {"version": 1},
        },
    )


def direct_maintenance_issue(*, state=READY_TO_INTEGRATE):
    project_id = "project-1"
    parent_id = "EPIC-1"
    generation = "f" * 64
    return Issue(
        id="REBASE-1",
        identifier="REBASE-1",
        title="Rebase legacy-epic-source onto epic-EPIC-0",
        description="Publish one exact nested epic generation",
        state=state,
        project_id=project_id,
        parent_id=parent_id,
        work_branch="legacy-epic-source",
        target_branch="epic-EPIC-0",
        integration=IntegrationRecord(
            state="ready",
            mode="queue",
            task_branch="legacy-epic-source",
            base_branch="epic-EPIC-0",
            base_sha="b" * 40,
            head_sha="c" * 40,
        ),
        create_once={
            "version": 1,
            "project_id": project_id,
            "operation_kind": "epic_rebase_helper",
            "creation_marker": "oompah-epic-rebase-reservation-v1:"
            + hashlib.sha256(
                f"{project_id}\0{parent_id}\0{generation}".encode()
            ).hexdigest(),
        },
        epic_rebase_target={
            "version": 1,
            "epic_identifier": parent_id,
            "epic_branch": "legacy-epic-source",
            "target_branch": "epic-EPIC-0",
            "parent_id": "EPIC-0",
            "resolution": "authoritative_parent",
        },
        epic_rebase_authority={
            "version": 1,
            "generation": generation,
            "task_id": "REBASE-1",
            "epic_identifier": parent_id,
            "epic_branch": "legacy-epic-source",
            "epic_head": "a" * 40,
            "target_branch": "epic-EPIC-0",
            "target_head": "b" * 40,
        },
    )


@pytest.mark.parametrize("state", [READY_TO_INTEGRATE, "Done"])
def test_direct_maintenance_ready_uses_only_task_scoped_completion(
    tmp_path, state
):
    task = direct_maintenance_issue(state=state)
    tracker = Tracker([task])
    store = WorkflowJobStore(str(tmp_path / "maintenance.sqlite3"))
    controller = IntegrationWorkflowController(
        collector=collector(tracker), store=store
    )

    batch, scheduled = controller.reconcile([task])

    assert batch.decisions[0].durable_jobs == (
        "direct_epic_maintenance_completion",
    )
    assert batch.tasks[0].landing_requests == ()
    assert scheduled.jobs_created == 1
    jobs = store.list_jobs(task_id=task.identifier)
    assert [job.action for job in jobs] == [
        "direct_epic_maintenance_completion"
    ]
    store.close()


@pytest.mark.asyncio
async def test_direct_maintenance_action_completes_exact_generation_and_replays(
    tmp_path,
):
    task = direct_maintenance_issue(state="Done")
    parent = Issue(
        id="EPIC-1",
        identifier="EPIC-1",
        title="Nested epic",
        state="Open",
        project_id="project-1",
        labels=["epic:rebasing"],
    )
    tracker = Tracker([task, parent])
    fact_collector = collector(tracker)
    store = WorkflowJobStore(str(tmp_path / "maintenance-action.sqlite3"))
    controller = IntegrationWorkflowController(
        collector=fact_collector, store=store
    )
    decision = controller.evaluate([task]).decisions[0]
    calls = []

    async def complete(current, record, project_id, *, _authority_owned=False):
        assert _authority_owned is True
        calls.append((current.identifier, record.head_sha, project_id))
        completed = replace(
            record,
            state="integrated",
            base_branch=record.task_branch,
            integrated_sha=record.head_sha,
            maintenance_publication_proven=True,
        )
        current.integration = completed
        parent.labels = ["epic:rebased"]
        return True, "completed", completed

    orchestrator = SimpleNamespace(
        integration_queue=SimpleNamespace(get=lambda *_args: None),
        project_store=SimpleNamespace(
            get=lambda _project_id: SimpleNamespace(default_branch="main")
        ),
        complete_direct_epic_maintenance_submission=complete,
        _get_epic_rebase_state=lambda *_args, **_kwargs: EpicRebaseState.REBASED,
        request_refresh=lambda: None,
    )
    backend = OrchestratorIntegrationActionBackend(
        orchestrator,
        SimpleNamespace(
            project_id="project-1",
            tracker=tracker,
            collector=fact_collector,
            integration_controller=controller,
        ),
    )
    job = SimpleNamespace(
        project_id="project-1",
        task_id=task.identifier,
        generation="generation-1",
        expected_evidence_revision=decision.evidence_revision,
        checkpoint={},
    )
    context = SimpleNamespace(job=job, check_interrupted=lambda: None)
    revalidation = backend.revalidate_action(
        "direct_epic_maintenance_completion", context
    )
    job.checkpoint = {
        "revalidation": {
            "generation": revalidation.generation,
            "evidence_revision": revalidation.evidence_revision,
            "head_sha": revalidation.head_sha,
            "details": dict(revalidation.details),
        }
    }

    assert not backend.observe_action(
        "direct_epic_maintenance_completion", context
    ).applied
    effect = await backend.apply_action(
        "direct_epic_maintenance_completion", context
    )
    verification = backend.verify_action(
        "direct_epic_maintenance_completion", context, effect
    )

    assert verification.verified
    assert calls == [("REBASE-1", "c" * 40, "project-1")]
    assert backend.observe_action(
        "direct_epic_maintenance_completion", context
    ).applied
    assert parent.labels == ["epic:rebased"]
    assert backend.build_action_transition(
        "direct_epic_maintenance_completion", context, verification
    ) is None
    store.close()


@pytest.mark.asyncio
async def test_direct_maintenance_action_rejects_changed_head(tmp_path):
    task = direct_maintenance_issue()
    tracker = Tracker([task])
    fact_collector = collector(tracker)
    store = WorkflowJobStore(str(tmp_path / "maintenance-stale.sqlite3"))
    controller = IntegrationWorkflowController(
        collector=fact_collector, store=store
    )
    decision = controller.evaluate([task]).decisions[0]
    complete = AsyncMock()
    backend = OrchestratorIntegrationActionBackend(
        SimpleNamespace(
            integration_queue=SimpleNamespace(get=lambda *_args: None),
            project_store=SimpleNamespace(
                get=lambda _project_id: SimpleNamespace(default_branch="main")
            ),
            complete_direct_epic_maintenance_submission=complete,
        ),
        SimpleNamespace(
            project_id="project-1",
            tracker=tracker,
            collector=fact_collector,
            integration_controller=controller,
        ),
    )
    job = SimpleNamespace(
        project_id="project-1",
        task_id=task.identifier,
        generation="generation-1",
        expected_evidence_revision=decision.evidence_revision,
        checkpoint={},
    )
    context = SimpleNamespace(job=job, check_interrupted=lambda: None)
    revalidation = backend.revalidate_action(
        "direct_epic_maintenance_completion", context
    )
    job.checkpoint = {
        "revalidation": {
            "generation": revalidation.generation,
            "evidence_revision": revalidation.evidence_revision,
            "head_sha": revalidation.head_sha,
            "details": dict(revalidation.details),
        }
    }
    task.integration = replace(task.integration, head_sha="d" * 40)

    with pytest.raises(WorkflowActionError, match="authority changed"):
        await backend.apply_action("direct_epic_maintenance_completion", context)

    complete.assert_not_awaited()
    store.close()


def test_exact_owner_revocation_wakes_one_standalone_delivery(tmp_path):
    """OOMPAH-1085/1093: no gate exists until exact retirement completes."""

    task = issue("TASK-OWNER-HANDOFF")
    task.parent_id = None
    task.integration = replace(task.integration, mode="standalone")
    tracker = Tracker([task])
    authority = {
        "owner_id": "alice",
        "generation": "claim-owner-handoff",
        "ownership_source": "direct_owner",
        "lease_expires_at": None,
        "retirement_pending": True,
        "state": "retirement_pending",
    }
    fact_collector = collector(
        tracker,
        implementation_authority=lambda _task: dict(authority),
    )
    store = WorkflowJobStore(str(tmp_path / "owner-handoff-jobs.sqlite3"))
    controller = IntegrationWorkflowController(
        collector=fact_collector,
        store=store,
    )

    blocked, blocked_result = controller.reconcile([task])

    assert blocked.decisions[0].reason_code == "integration.owner_retirement_pending"
    assert blocked_result.jobs_created == 0
    assert store.list_jobs(task_id=task.identifier) == ()

    # Exact authority_revocation completion removes the captured claim and its
    # state-only notification requests this authoritative follow-up cut.
    authority.clear()
    released, released_result = controller.reconcile([task])
    duplicate, duplicate_result = controller.reconcile([task])

    assert released.decisions[0].durable_jobs == ("standalone_delivery",)
    assert released_result.jobs_created == 1
    assert duplicate.decisions[0].durable_jobs == ("standalone_delivery",)
    assert duplicate_result.jobs_created == 0
    deliveries = store.list_jobs(
        task_id=task.identifier,
        actions=("standalone_delivery",),
    )
    assert len(deliveries) == 1
    assert deliveries[0].state is WorkflowJobState.QUEUED
    store.close()


class UnavailableLandingCollector:
    def __init__(self):
        self.project_id = "project-1"
        self.requests = []

    def collect_many(self, requests):
        self.requests.extend(requests)
        return tuple(
            LandingFact(
                request.source,
                request.target,
                request.revision,
                {"kind": "target_unavailable"},
                "2026-08-09T00:00:00+00:00",
                "project-1",
                state=LandingState.UNKNOWN,
                error_code="target_unavailable",
            )
            for request in requests
        )


def integrated_queue_row(queue, task, *, parent_id, base_branch=None):
    queued = queue.enqueue(
        project_id="project-1",
        epic_id=parent_id,
        task_id=task.identifier,
        task_branch=task.identifier,
        head_sha="a" * 40,
        base_branch=base_branch,
    )
    integrated = queue.finish_task_generation(
        "project-1",
        task.identifier,
        expected_generation=queued.authority_generation(),
        state="integrated",
    )
    assert integrated is not None
    return integrated


def _parent_scoped_child_fact(
    *,
    source="TASK-A",
    target="epic/E-1",
    revision="a" * 40,
    target_sha=None,
    project_id="project-1",
):
    target_sha = target_sha or revision
    return LandingFact(
        source,
        target,
        revision,
        {
            "kind": "git_ancestry",
            "source_sha": revision,
            "target_sha": target_sha,
        },
        "2026-08-09T14:00:00+00:00",
        project_id,
        state=LandingState.LANDED,
        durable=True,
    )


class StableParentLandingCollector:
    def collect(self, request):
        assert request.prior is not None
        return request.prior


def _parent_scoped_child_fixture(*, revision="a" * 40):
    task = issue("TASK-A")
    task.state = "Done"
    task.parent_id = "E-1"
    task.target_branch = None
    task.integration = None
    parent = issue("E-1")
    parent.issue_type = "epic"
    parent.state = "Done"
    parent.work_branch = "epic/E-1"
    parent.target_branch = "main"
    return task, parent, _parent_scoped_child_fact(revision=revision)


def test_landing_request_resolver_scopes_parent_head_observations(tmp_path):
    task = issue("TASK-A")
    task.state = "Done"
    task.parent_id = "E-1"
    task.work_branch = "TASK-A"
    parent = issue("E-1")
    parent.issue_type = "epic"
    parent.state = "Merged"
    parent.work_branch = "epic/E-1"
    parent.target_branch = "main"
    parent.integration = None
    tracker = Tracker([task, parent])
    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    store.record_landing_facts(
        project_id="project-1",
        task_id=parent.identifier,
        facts=(
            _parent_scoped_child_fact(
                source=parent.work_branch,
                target=parent.target_branch,
                revision="b" * 40,
            ).to_dict(),
        ),
    )
    landing_fact_calls = 0
    original_latest = store.latest_landing_facts_for_pair

    def latest_landing_facts_for_pair(**kwargs):
        nonlocal landing_fact_calls
        landing_fact_calls += 1
        return original_latest(**kwargs)

    store.latest_landing_facts_for_pair = latest_landing_facts_for_pair

    resolver = IntegrationLandingRequestResolver(
        project_id="project-1",
        tracker=tracker,
        project_store=SimpleNamespace(
            epic_branch_name=lambda epic_id: f"epic/{epic_id}"
        ),
        project_default_branch="main",
        workflow_store=store,
        landing_collector=StableParentLandingCollector(),
        parent_source_head_resolver=lambda _branch: "b" * 40,
    )
    authoritative = {item.identifier: item for item in (task, parent)}
    children = {parent.identifier.casefold(): (task,)}

    with resolver.observation_scope():
        first = resolver(
            task,
            authoritative_issues=authoritative,
            authoritative_children=children,
        )
        second = resolver(
            task,
            authoritative_issues=authoritative,
            authoritative_children=children,
        )
    assert first == second
    # One lookup resolves the terminal parent head and one resolves the
    # parent's child-landing fact. The repeated request reuses both.
    assert landing_fact_calls == 2

    resolver(
        task,
        authoritative_issues=authoritative,
        authoritative_children=children,
    )
    assert landing_fact_calls == 3
    store.close()


def test_post_landed_parent_target_requires_fresh_exact_landing_fact(tmp_path):
    task = issue("TASK-A")
    task.parent_id = "E-1"
    parent = issue("E-1")
    parent.issue_type = "epic"
    parent.parent_id = None
    parent.work_branch = "epic/E-1"
    parent.target_branch = "main"
    parent.integration = None
    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    fact = _parent_scoped_child_fact(
        source="epic/E-1", target="main", revision="b" * 40
    )
    store.record_landing_facts(
        project_id="project-1",
        task_id=parent.identifier,
        facts=(fact.to_dict(),),
    )
    resolver = IntegrationLandingRequestResolver(
        project_id="project-1",
        tracker=Tracker([task, parent]),
        project_store=SimpleNamespace(
            epic_branch_name=lambda epic_id: f"epic/{epic_id}"
        ),
        project_default_branch="main",
        workflow_store=store,
        landing_collector=StableParentLandingCollector(),
        parent_source_head_resolver=lambda _branch: "b" * 40,
    )

    assert resolver.post_landed_parent_target(task) == "main"
    resolver.parent_source_head_resolver = lambda _branch: None
    assert resolver.post_landed_parent_target(task) == "main"
    resolver.parent_source_head_resolver = lambda _branch: "d" * 40
    assert resolver.post_landed_parent_target(task) is None
    resolver.parent_source_head_resolver = lambda _branch: "b" * 40
    parent.parent_id = "ROOT"
    parent.target_branch = None
    nested_fact = _parent_scoped_child_fact(
        source="epic/E-1", target="epic/ROOT", revision="b" * 40
    )
    store.record_landing_facts(
        project_id="project-1",
        task_id=parent.identifier,
        facts=(nested_fact.to_dict(),),
    )
    assert resolver.post_landed_parent_target(task) == "epic/ROOT"
    resolver.tracker.issues[task.identifier] = replace(task, parent_id="OTHER")
    assert resolver.post_landed_parent_target(task) is None
    store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("task_id", "parent_id"),
    (
        ("OOMPAH-787", "OOMPAH-771"),
        ("OOMPAH-794", "OOMPAH-767"),
        ("OOMPAH-797", "OOMPAH-771"),
        ("OOMPAH-798", "OOMPAH-767"),
        ("OOMPAH-889", "OOMPAH-763"),
        ("OOMPAH-894", "OOMPAH-763"),
        ("OOMPAH-910", "OOMPAH-763"),
        ("OOMPAH-911", "OOMPAH-763"),
        ("OOMPAH-914", "OOMPAH-763"),
        ("OOMPAH-915", "OOMPAH-763"),
        ("OOMPAH-916", "OOMPAH-763"),
        ("OOMPAH-917", "OOMPAH-763"),
        ("OOMPAH-918", "OOMPAH-763"),
        ("OOMPAH-919", "OOMPAH-763"),
        ("OOMPAH-920", "OOMPAH-763"),
        ("OOMPAH-921", "OOMPAH-763"),
        ("OOMPAH-926", "OOMPAH-763"),
        ("OOMPAH-929", "OOMPAH-763"),
        ("OOMPAH-930", "OOMPAH-763"),
        ("OOMPAH-931", "OOMPAH-763"),
    ),
)
async def test_composed_done_child_carries_parent_landing_head_through_rollup(
    tmp_path,
    task_id,
    parent_id,
):
    revision = "3" * 40
    target = f"epic-{parent_id}"
    task = issue(task_id)
    task.state = "Done"
    task.parent_id = parent_id
    task.work_branch = None
    task.target_branch = None
    task.integration = None
    parent = issue(parent_id)
    parent.issue_type = "epic"
    # This test exercises the terminal path; the shared parent has already
    # landed on its immediate target.
    parent.state = "Merged"
    parent.work_branch = target
    parent.target_branch = "main"
    tracker = Tracker([task, parent])
    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    fact = _parent_scoped_child_fact(
        source=task_id,
        target=target,
        revision=revision,
    )
    store.record_landing_facts(
        project_id="project-1",
        task_id=parent_id,
        facts=(fact.to_dict(),),
    )
    queue = IntegrationQueueStore(str(tmp_path / "integration.sqlite3"))
    controller = IntegrationWorkflowController(
        collector=collector(tracker, PriorOnlyLandingCollector()),
        store=store,
        landing_request_resolver=IntegrationLandingRequestResolver(
            project_id="project-1",
            tracker=tracker,
            integration_queue=queue,
            project_store=SimpleNamespace(
                epic_branch_name=lambda epic_id: f"epic-{epic_id}"
            ),
            project_default_branch="main",
            workflow_store=store,
        ),
    )
    task_decision = controller.evaluate((task,)).tasks[0]
    assert task_decision.decision.durable_jobs == ("parent_rollup_review",)
    orchestrator = SimpleNamespace(
        integration_queue=queue,
        project_store=SimpleNamespace(
            get=lambda _project_id: SimpleNamespace(default_branch="main"),
            epic_branch_name=lambda epic_id: f"epic-{epic_id}",
        ),
    )
    backend = OrchestratorIntegrationActionBackend(
        orchestrator,
        SimpleNamespace(
            project_id="project-1",
            tracker=tracker,
            collector=controller.collector,
            integration_controller=controller,
        ),
    )
    job = SimpleNamespace(
        project_id="project-1",
        task_id=task_id,
        generation="generation-2",
        job_id=f"job-{task_id}",
        idempotency_key=f"{task_id}:rollup:generation-2",
        expected_evidence_revision=task_decision.decision.evidence_revision,
        checkpoint={},
    )
    context = SimpleNamespace(job=job, check_interrupted=lambda: None)

    revalidation = backend.revalidate_action("parent_rollup_review", context)
    assert revalidation.current
    assert revalidation.details["rollup_exact_head"] == revision
    assert revalidation.details["rollup_head_authority"] == "composed_landing"
    job.checkpoint = {
        "revalidation": {
            "evidence_revision": revalidation.evidence_revision,
            "details": dict(revalidation.details),
        }
    }
    effect = await backend.apply_action("parent_rollup_review", context)
    verification = backend.verify_action(
        "parent_rollup_review", context, effect
    )
    transition = backend.build_action_transition(
        "parent_rollup_review", context, verification
    )

    assert verification.verified
    assert transition is not None
    assert transition.exact_head == revision
    assert transition.precondition_revision == task_decision.decision.evidence_revision
    assert transition.requested_status == "Merged"
    task.parent_id = f"{parent_id}-changed"
    with pytest.raises(WorkflowActionError, match="evidence changed|head changed") as error:
        backend.build_action_transition(
            "parent_rollup_review", context, verification
        )
    assert error.value.retryable
    store.close()
    queue.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutation",
    ("missing", "wrong_source", "wrong_target", "wrong_revision", "mutable"),
)
async def test_parent_rollup_revalidation_fails_closed_without_current_composed_head(
    tmp_path,
    mutation,
):
    task, parent, fact = _parent_scoped_child_fixture(revision="3" * 40)
    if mutation == "wrong_revision":
        # Retain one exact current-task revision so the differently revised
        # parent row is provably stale instead of becoming the only candidate.
        task.head_sha = fact.revision
    if mutation == "missing":
        facts = ()
    else:
        fields = {
            "source": "OTHER" if mutation == "wrong_source" else fact.source,
            "target": "epic/E-OTHER" if mutation == "wrong_target" else fact.target,
            "revision": "4" * 40 if mutation == "wrong_revision" else fact.revision,
        }
        changed = _parent_scoped_child_fact(**fields)
        if mutation == "mutable":
            raw_changed = changed.to_dict()
            raw_changed["durable"] = False
            raw_changed.pop("evidence_revision")
            changed = LandingFact.from_dict(raw_changed)
        facts = (changed.to_dict(),)
    tracker = Tracker([task, parent])
    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    if facts:
        store.record_landing_facts(
            project_id="project-1", task_id=parent.identifier, facts=facts
        )
    queue = IntegrationQueueStore(str(tmp_path / "integration.sqlite3"))
    controller = IntegrationWorkflowController(
        collector=collector(tracker, PriorOnlyLandingCollector()),
        store=store,
        landing_request_resolver=IntegrationLandingRequestResolver(
            project_id="project-1",
            tracker=tracker,
            integration_queue=queue,
            project_store=SimpleNamespace(
                epic_branch_name=lambda epic_id: f"epic/{epic_id}"
            ),
            workflow_store=store,
        ),
    )
    decision = controller.evaluate((task,)).tasks[0].decision
    backend = OrchestratorIntegrationActionBackend(
        SimpleNamespace(
            integration_queue=queue,
            project_store=SimpleNamespace(
                get=lambda _project_id: SimpleNamespace(default_branch="main")
            ),
        ),
        SimpleNamespace(
            project_id="project-1",
            tracker=tracker,
            collector=controller.collector,
            integration_controller=controller,
        ),
    )
    context = SimpleNamespace(
        job=SimpleNamespace(
            project_id="project-1",
            task_id=task.identifier,
            generation="generation-2",
            expected_evidence_revision=decision.evidence_revision,
            checkpoint={},
        )
    )

    revalidation = backend.revalidate_action("parent_rollup_review", context)

    assert not revalidation.current
    assert revalidation.details.get("rollup_head_authority") != "composed_landing"
    store.close()
    queue.close()


def test_done_child_consumes_parent_scoped_canonical_landing_after_restart(tmp_path):
    git(tmp_path, "init", "-b", "main")
    (tmp_path / "base.txt").write_text("base\n")
    git(tmp_path, "add", "base.txt")
    git(tmp_path, "commit", "-m", "base")
    git(tmp_path, "checkout", "-b", "TASK-A")
    (tmp_path / "child.txt").write_text("accepted child\n")
    git(tmp_path, "add", "child.txt")
    git(tmp_path, "commit", "-m", "accepted child")
    child_head = git(tmp_path, "rev-parse", "HEAD")
    git(tmp_path, "branch", "epic/E-1", child_head)
    git(tmp_path, "checkout", "main")
    git(tmp_path, "branch", "-D", "TASK-A")

    task, parent, fact = _parent_scoped_child_fixture(revision=child_head)
    parent.state = "Merged"
    tracker = Tracker([task, parent])
    store_path = tmp_path / "workflow.sqlite3"
    store = WorkflowJobStore(str(store_path))
    assert store.record_landing_facts(
        project_id="project-1",
        task_id=parent.identifier,
        facts=(fact.to_dict(),),
    ) == 1
    resolver = IntegrationLandingRequestResolver(
        project_id="project-1",
        tracker=tracker,
        project_store=SimpleNamespace(
            epic_branch_name=lambda epic_id: f"epic/{epic_id}"
        ),
        project_default_branch="main",
        workflow_store=store,
    )
    controller = IntegrationWorkflowController(
        collector=collector(
            tracker,
            GitLandingCollector(tmp_path, project_id="project-1"),
        ),
        store=store,
        landing_request_resolver=resolver,
    )

    batch = controller.evaluate([task])

    request = batch.tasks[0].landing_requests[0]
    assert (request.source, request.target, request.revision) == (
        "TASK-A",
        "epic/E-1",
        child_head,
    )
    assert request.prior == fact
    assert request.authoritative_target
    landing = batch.tasks[0].facts.landings[0]
    assert (
        landing.source,
        landing.target,
        landing.revision,
        landing.proof,
        landing.state,
        landing.durable,
    ) == (
        fact.source,
        fact.target,
        fact.revision,
        fact.proof,
        LandingState.LANDED,
        True,
    )
    assert batch.tasks[0].decision.reason_code == (
        "terminal.immediate_target_landing_proven"
    )
    assert batch.tasks[0].decision.durable_jobs == ("parent_rollup_review",)
    # Import is observational: the canonical fact remains parent-owned and no
    # second child-scoped copy is manufactured.
    assert store.latest_landing_facts(
        project_id="project-1", task_id=task.identifier
    ) == ()
    store.close()

    restarted = WorkflowJobStore(str(store_path))
    restarted_resolver = IntegrationLandingRequestResolver(
        project_id="project-1",
        tracker=tracker,
        project_store=SimpleNamespace(
            epic_branch_name=lambda epic_id: f"epic/{epic_id}"
        ),
        project_default_branch="main",
        workflow_store=restarted,
    )
    restarted_request = restarted_resolver(task)[0]
    assert restarted_request.prior == fact
    assert restarted_request.revision == child_head
    restarted.close()


@pytest.mark.parametrize("terminal_parent_state", ("Merged", "Archived"))
def test_done_child_defers_rollup_job_until_parent_is_terminal(
    tmp_path, terminal_parent_state
):
    task, parent, fact = _parent_scoped_child_fixture()
    tracker = Tracker([task, parent])
    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    store.record_landing_facts(
        project_id="project-1",
        task_id=parent.identifier,
        facts=(fact.to_dict(),),
    )
    controller = IntegrationWorkflowController(
        collector=collector(tracker, PriorOnlyLandingCollector()),
        store=store,
        landing_request_resolver=IntegrationLandingRequestResolver(
            project_id="project-1",
            tracker=tracker,
            project_store=SimpleNamespace(
                epic_branch_name=lambda epic_id: f"epic/{epic_id}"
            ),
            project_default_branch="main",
            workflow_store=store,
        ),
    )

    waiting, waiting_reconcile = controller.reconcile((task,))

    assert waiting.tasks[0].decision.reason_code == (
        "rollup.waiting_parent_landing"
    )
    assert waiting.tasks[0].decision.durable_jobs == ()
    assert waiting_reconcile.jobs_required == 0
    assert waiting_reconcile.jobs_materialized == 0
    assert store.list_jobs(project_id="project-1", task_id=task.identifier) == ()

    parent.state = terminal_parent_state
    terminal, terminal_reconcile = controller.reconcile((task,))

    assert terminal.tasks[0].decision.durable_jobs == ("parent_rollup_review",)
    assert terminal_reconcile.jobs_required == 1
    assert terminal_reconcile.jobs_materialized == 1
    store.close()


@pytest.mark.parametrize(
    ("fact_kwargs", "task_update", "parent_update"),
    [
        ({"source": "OTHER"}, {}, {}),
        ({"target": "epic/E-OTHER"}, {}, {}),
        ({}, {"head_sha": "b" * 40}, {}),
        ({}, {}, {"work_branch": "epic/E-NEW"}),
    ],
    ids=(
        "wrong-source",
        "wrong-route",
        "stale-revision",
        "changed-current-target",
    ),
)
def test_parent_scoped_child_landing_rejects_noncurrent_authority(
    tmp_path, fact_kwargs, task_update, parent_update
):
    task, parent, _fact = _parent_scoped_child_fixture()
    for field, value in task_update.items():
        setattr(task, field, value)
    for field, value in parent_update.items():
        setattr(parent, field, value)
    fact = _parent_scoped_child_fact(**fact_kwargs)
    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    store.record_landing_facts(
        project_id="project-1",
        task_id=parent.identifier,
        facts=(fact.to_dict(),),
    )
    resolver = IntegrationLandingRequestResolver(
        project_id="project-1",
        tracker=Tracker([task, parent]),
        project_store=SimpleNamespace(
            epic_branch_name=lambda epic_id: f"epic/{epic_id}"
        ),
        project_default_branch="main",
        workflow_store=store,
    )

    assert resolver(task) == ()
    store.close()


def test_parent_scoped_child_landing_requires_current_direct_containment(tmp_path):
    task, parent, fact = _parent_scoped_child_fixture()

    class StaleContainmentTracker(Tracker):
        def fetch_children(self, _identifier):
            return ()

    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    store.record_landing_facts(
        project_id="project-1",
        task_id=parent.identifier,
        facts=(fact.to_dict(),),
    )
    resolver = IntegrationLandingRequestResolver(
        project_id="project-1",
        tracker=StaleContainmentTracker([task, parent]),
        project_store=SimpleNamespace(
            epic_branch_name=lambda epic_id: f"epic/{epic_id}"
        ),
        workflow_store=store,
    )

    assert resolver(task) == ()
    store.close()


def test_landing_resolver_uses_authoritative_parent_indexes_without_fanout(
    tmp_path,
):
    task, parent, _fact = _parent_scoped_child_fixture()

    class NoFanoutTracker(Tracker):
        def fetch_issue_detail(self, _identifier):
            raise AssertionError("authoritative parent must not be refetched")

        def fetch_children(self, _identifier):
            raise AssertionError("authoritative children must not be rescanned")

    store = WorkflowJobStore(str(tmp_path / "indexed-parent.sqlite3"))
    resolver = IntegrationLandingRequestResolver(
        project_id="project-1",
        tracker=NoFanoutTracker([task, parent]),
        project_store=SimpleNamespace(
            epic_branch_name=lambda epic_id: f"epic/{epic_id}"
        ),
        workflow_store=store,
    )
    authoritative_issues = {
        item.identifier.casefold(): item for item in (task, parent)
    }
    authoritative_children = {parent.identifier.casefold(): (task,)}

    request = resolver(
        task,
        include_ready=True,
        authoritative_issues=authoritative_issues,
        authoritative_children=authoritative_children,
    )[0]

    assert (request.source, request.target) == (
        task.work_branch,
        parent.work_branch,
    )
    store.close()


def test_parent_scoped_child_landing_is_not_hidden_by_large_epic(tmp_path):
    task, parent, _fact = _parent_scoped_child_fixture()
    task.identifier = task.id = "TASK-Z"
    task.title = "Integrate TASK-Z"
    task.work_branch = "TASK-Z"
    fact = _parent_scoped_child_fact(source="TASK-Z")
    distractors = tuple(
        _parent_scoped_child_fact(source=f"A-NOISE-{index:04d}").to_dict()
        for index in range(1000)
    )
    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    assert store.record_landing_facts(
        project_id="project-1",
        task_id=parent.identifier,
        facts=(*distractors, fact.to_dict()),
    ) == 1001
    resolver = IntegrationLandingRequestResolver(
        project_id="project-1",
        tracker=Tracker([task, parent]),
        project_store=SimpleNamespace(
            epic_branch_name=lambda epic_id: f"epic/{epic_id}"
        ),
        workflow_store=store,
    )

    request = resolver(task)[0]

    assert request.prior == fact
    assert all(
        row["source"] != "TASK-Z"
        for row in store.latest_landing_facts(
            project_id="project-1",
            task_id=parent.identifier,
            limit=1000,
        )
    )
    store.close()


def test_parent_scoped_child_landing_rejects_foreign_project_fact():
    task, parent, _fact = _parent_scoped_child_fixture()
    foreign = _parent_scoped_child_fact(project_id="foreign-project")

    class ForeignStore:
        def latest_landing_facts_for_pair(self, **_kwargs):
            return (foreign.to_dict(),)

    resolver = IntegrationLandingRequestResolver(
        project_id="project-1",
        tracker=Tracker([task, parent]),
        project_store=SimpleNamespace(
            epic_branch_name=lambda epic_id: f"epic/{epic_id}"
        ),
        workflow_store=ForeignStore(),
    )

    assert resolver(task) == ()


def test_parent_scoped_child_landing_rejects_ambiguous_parent_rows():
    task, parent, first = _parent_scoped_child_fixture()
    second = _parent_scoped_child_fact(revision="b" * 40)

    class AmbiguousStore:
        def latest_landing_facts_for_pair(self, **_kwargs):
            return (first.to_dict(), second.to_dict())

    resolver = IntegrationLandingRequestResolver(
        project_id="project-1",
        tracker=Tracker([task, parent]),
        project_store=SimpleNamespace(
            epic_branch_name=lambda epic_id: f"epic/{epic_id}"
        ),
        workflow_store=AmbiguousStore(),
    )

    assert resolver(task) == ()


def test_parent_scoped_child_landing_revalidates_current_target_history(tmp_path):
    git(tmp_path, "init", "-b", "main")
    (tmp_path / "base.txt").write_text("base\n")
    git(tmp_path, "add", "base.txt")
    git(tmp_path, "commit", "-m", "base")
    base = git(tmp_path, "rev-parse", "HEAD")
    git(tmp_path, "checkout", "-b", "TASK-A")
    (tmp_path / "child.txt").write_text("formerly landed child\n")
    git(tmp_path, "add", "child.txt")
    git(tmp_path, "commit", "-m", "child")
    child_head = git(tmp_path, "rev-parse", "HEAD")
    git(tmp_path, "branch", "epic/E-1", child_head)
    # The current parent target was rewritten and no longer contains the
    # target head bound into the otherwise-valid durable fact.
    git(tmp_path, "branch", "-f", "epic/E-1", base)
    git(tmp_path, "checkout", "main")
    git(tmp_path, "branch", "-D", "TASK-A")

    task, parent, fact = _parent_scoped_child_fixture(revision=child_head)
    tracker = Tracker([task, parent])
    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    store.record_landing_facts(
        project_id="project-1",
        task_id=parent.identifier,
        facts=(fact.to_dict(),),
    )
    controller = IntegrationWorkflowController(
        collector=collector(
            tracker,
            GitLandingCollector(tmp_path, project_id="project-1"),
        ),
        store=store,
        landing_request_resolver=IntegrationLandingRequestResolver(
            project_id="project-1",
            tracker=tracker,
            project_store=SimpleNamespace(
                epic_branch_name=lambda epic_id: f"epic/{epic_id}"
            ),
            workflow_store=store,
        ),
    )

    batch = controller.evaluate([task])

    assert batch.tasks[0].facts.landings[0].state is LandingState.NOT_LANDED
    assert batch.tasks[0].decision.reason_code == "landing.waiting"
    assert batch.tasks[0].decision.disposition is TaskDisposition.BLOCKED
    store.close()


def test_legacy_done_child_uses_queue_revision_and_immediate_parent_target(tmp_path):
    task = issue("TASK-A", state="integrated", head="a" * 40)
    task.state = "Done"
    task.parent_id = "E-1"
    task.target_branch = "main"
    task.integration = None
    parent = issue("E-1")
    parent.work_branch = "epic/E-ROOT--task-E-1"
    tracker = Tracker([task, parent])
    queue = IntegrationQueueStore(str(tmp_path / "integration.sqlite3"))
    integrated_queue_row(queue, task, parent_id="E-1")
    landing_collector = UnavailableLandingCollector()
    jobs = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    resolver = IntegrationLandingRequestResolver(
        project_id="project-1",
        tracker=tracker,
        integration_queue=queue,
        project_store=SimpleNamespace(
            epic_branch_name=lambda epic_id: f"epic/{epic_id}"
        ),
        project_default_branch="main",
    )
    controller = IntegrationWorkflowController(
        collector=collector(tracker, landing_collector),
        store=jobs,
        landing_request_resolver=resolver,
    )

    batch = controller.evaluate([task])
    request = batch.tasks[0].landing_requests[0]

    assert (request.source, request.target, request.revision) == (
        "TASK-A",
        "epic/E-ROOT--task-E-1",
        "a" * 40,
    )
    assert request.authoritative_target
    assert request.trusted_target_revision is None
    backend = OrchestratorIntegrationActionBackend(
        SimpleNamespace(
            integration_queue=queue,
            project_store=SimpleNamespace(
                get=lambda _project_id: SimpleNamespace(default_branch="main"),
                epic_branch_name=lambda epic_id: f"epic/{epic_id}",
            ),
        ),
        SimpleNamespace(
            project_id="project-1",
            tracker=tracker,
            collector=controller.collector,
            integration_controller=controller,
        ),
    )
    assert backend._landing_request(task) == (request,)
    jobs.close()
    queue.close()


def test_deleted_parent_ref_uses_final_exact_head_for_full_patch_proof(tmp_path):
    git(tmp_path, "init", "-b", "main")
    (tmp_path / "value.txt").write_text("base\n")
    git(tmp_path, "add", "value.txt")
    git(tmp_path, "commit", "-m", "base")
    git(tmp_path, "checkout", "-b", "legacy-child")
    (tmp_path / "value.txt").write_text("legacy child\n")
    git(tmp_path, "commit", "-am", "legacy child")
    child_head = git(tmp_path, "rev-parse", "HEAD")
    git(tmp_path, "checkout", "main")
    (tmp_path / "parent.txt").write_text("parent-only history\n")
    git(tmp_path, "add", "parent.txt")
    git(tmp_path, "commit", "-m", "parent-only history")
    git(tmp_path, "cherry-pick", child_head)
    parent_head = git(tmp_path, "rev-parse", "HEAD")
    # Neither mutable legacy ref survives, but both exact objects do.
    git(tmp_path, "branch", "-D", "legacy-child")

    task = issue("TASK-A", state="integrated", head=child_head)
    task.state = "Done"
    task.parent_id = "E-1"
    task.target_branch = None
    task.work_branch = "legacy-child"
    task.integration = IntegrationRecord(
        state="working",
        task_branch="legacy-child",
        base_branch="epic/E-1",
    )
    parent = issue("E-1")
    parent.issue_type = "epic"
    parent.state = "Merged"
    parent.work_branch = "epic/E-1"
    parent.integration = IntegrationRecord(
        state="ready",
        task_branch="E-1",
        head_sha=parent_head,
    )
    tracker = Tracker([task, parent])
    queue = IntegrationQueueStore(str(tmp_path / "integration.sqlite3"))
    queued = queue.enqueue(
        project_id="project-1",
        epic_id="E-1",
        task_id="TASK-A",
        task_branch="legacy-child",
        head_sha=child_head,
    )
    assert (
        queue.finish_task_generation(
            "project-1",
            "TASK-A",
            expected_generation=queued.authority_generation(),
            state="integrated",
        )
        is not None
    )

    def missing_remote_target(_target):
        raise RuntimeError("pruned target ref")

    landing_collector = GitLandingCollector(
        tmp_path,
        project_id="project-1",
        target_refresher=missing_remote_target,
    )
    jobs = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    resolver = IntegrationLandingRequestResolver(
        project_id="project-1",
        tracker=tracker,
        integration_queue=queue,
        project_store=SimpleNamespace(
            epic_branch_name=lambda epic_id: f"epic/{epic_id}"
        ),
        project_default_branch="main",
    )
    controller = IntegrationWorkflowController(
        collector=collector(tracker, landing_collector),
        store=jobs,
        landing_request_resolver=resolver,
    )

    batch = controller.evaluate([task])

    request = batch.tasks[0].landing_requests[0]
    landing = batch.tasks[0].facts.landings[0]
    assert request.trusted_target_revision == parent_head
    assert (request.source, request.target, request.revision) == (
        "legacy-child",
        "epic/E-1",
        child_head,
    )
    assert landing.state is LandingState.LANDED
    assert landing.proof["kind"] == "patch_id"
    assert landing.proof["patches"] == 1
    assert landing.proof["target_sha"] == parent_head
    assert batch.tasks[0].decision.reason_code == (
        "terminal.immediate_target_landing_proven"
    )
    assert batch.tasks[0].decision.durable_jobs == ("parent_rollup_review",)

    unavailable = landing_collector.collect(
        replace(request, trusted_target_revision="f" * 40)
    )
    assert unavailable.state is LandingState.UNKNOWN
    assert unavailable.proof["kind"] == "target_unavailable"

    git(tmp_path, "checkout", "-b", "unmatched-child", child_head)
    (tmp_path / "unmatched.txt").write_text("not in the accepted parent\n")
    git(tmp_path, "add", "unmatched.txt")
    git(tmp_path, "commit", "-m", "unmatched child patch")
    unmatched_head = git(tmp_path, "rev-parse", "HEAD")
    git(tmp_path, "checkout", "main")
    git(tmp_path, "branch", "-D", "unmatched-child")
    unmatched = landing_collector.collect(
        LandingRequest(
            "unmatched-child",
            "epic/E-1",
            unmatched_head,
            authoritative_target=True,
            trusted_target_revision=parent_head,
        )
    )
    assert unmatched.state is LandingState.NOT_LANDED
    assert unmatched.proof["kind"] == "not_ancestor"
    jobs.close()
    queue.close()


def _completed_parent_audit(
    task,
    selected_sha,
    *,
    audit_id="audit-1",
    selected_ref="origin/epic/E-1",
):
    task_id = task.identifier
    fingerprint = compute_issue_evidence_fingerprint(task, "project-1")
    attempt = AuditAttempt(
        attempt_id=f"attempt-{audit_id}",
        target_state=TargetState.MERGED,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.COMPLETED,
        verdict=Verdict.PASS,
        selected_ref=selected_ref,
        selected_sha=selected_sha,
    )
    return TerminalAuditRecord(
        audit_id=audit_id,
        project_id="project-1",
        task_id=task_id,
        target_state=TargetState.MERGED,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.COMPLETED,
        attempts=[attempt],
        selected_ref=selected_ref,
        selected_sha=selected_sha,
    )


def _legacy_child_and_terminal_parent():
    task = issue("TASK-A", state="integrated", head="a" * 40)
    task.state = "Done"
    task.parent_id = "E-1"
    task.target_branch = None
    task.integration = replace(task.integration, base_branch=None)
    parent = issue("E-1")
    parent.state = "Merged"
    parent.work_branch = "epic/E-1"
    parent.target_branch = "main"
    parent.integration = None
    return task, parent


def test_terminal_audit_parent_head_is_persisted_and_survives_restart(tmp_path):
    task, parent = _legacy_child_and_terminal_parent()
    accepted_head = "b" * 40
    metadata = {
        parent.identifier: {
            METADATA_KEY: TerminalAuditMetadata(
                pending_chain=[
                    _completed_parent_audit(parent, accepted_head)
                ]
            ).to_dict()
        }
    }
    tracker = Tracker([task, parent], metadata=metadata)
    store_path = tmp_path / "workflow.sqlite3"
    store = WorkflowJobStore(str(store_path))
    resolver = IntegrationLandingRequestResolver(
        project_id="project-1",
        tracker=tracker,
        project_store=SimpleNamespace(
            epic_branch_name=lambda epic_id: f"epic/{epic_id}"
        ),
        project_default_branch="main",
        workflow_store=store,
    )

    assert resolver(task)[0].trusted_target_revision == accepted_head
    persisted = store.latest_landing_facts(
        project_id="project-1", task_id=parent.identifier
    )
    assert len(persisted) == 1
    assert persisted[0]["revision"] == accepted_head
    assert persisted[0]["proof"]["kind"] == "terminal_audit"
    store.close()

    restarted = WorkflowJobStore(str(store_path))
    resolver = IntegrationLandingRequestResolver(
        project_id="project-1",
        tracker=Tracker([task, parent]),
        project_store=SimpleNamespace(
            epic_branch_name=lambda epic_id: f"epic/{epic_id}"
        ),
        project_default_branch="main",
        workflow_store=restarted,
        forge_review_resolver=lambda _branch: (_ for _ in ()).throw(
            AssertionError("persisted backfill must precede forge lookup")
        ),
    )
    assert resolver(task)[0].trusted_target_revision == accepted_head
    restarted.close()


def test_conflicting_terminal_audit_parent_heads_fail_closed(tmp_path):
    task, parent = _legacy_child_and_terminal_parent()
    metadata = {
        parent.identifier: {
            METADATA_KEY: TerminalAuditMetadata(
                pending_chain=[
                    _completed_parent_audit(
                        parent, "b" * 40, audit_id="audit-1"
                    ),
                    _completed_parent_audit(
                        parent, "c" * 40, audit_id="audit-2"
                    ),
                ]
            ).to_dict()
        }
    }
    forge_calls = []
    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    resolver = IntegrationLandingRequestResolver(
        project_id="project-1",
        tracker=Tracker([task, parent], metadata=metadata),
        project_store=SimpleNamespace(
            epic_branch_name=lambda epic_id: f"epic/{epic_id}"
        ),
        project_default_branch="main",
        workflow_store=store,
        forge_review_resolver=lambda branch: forge_calls.append(branch),
    )

    assert resolver(task)[0].trusted_target_revision is None
    assert forge_calls == []
    assert store.latest_landing_facts(
        project_id="project-1", task_id=parent.identifier
    ) == ()
    store.close()


def test_terminal_audit_parent_head_from_wrong_source_ref_fails_closed(tmp_path):
    task, parent = _legacy_child_and_terminal_parent()
    metadata = {
        parent.identifier: {
            METADATA_KEY: TerminalAuditMetadata(
                pending_chain=[
                    _completed_parent_audit(
                        parent,
                        "b" * 40,
                        selected_ref="origin/main",
                    )
                ]
            ).to_dict()
        }
    }
    forge_calls = []
    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    resolver = IntegrationLandingRequestResolver(
        project_id="project-1",
        tracker=Tracker([task, parent], metadata=metadata),
        project_store=SimpleNamespace(
            epic_branch_name=lambda epic_id: f"epic/{epic_id}"
        ),
        project_default_branch="main",
        workflow_store=store,
        forge_review_resolver=lambda branch: forge_calls.append(branch),
    )

    assert resolver(task)[0].trusted_target_revision is None
    assert forge_calls == []
    assert store.latest_landing_facts(
        project_id="project-1", task_id=parent.identifier
    ) == ()
    store.close()


def test_stale_terminal_audit_parent_head_is_not_current_authority(tmp_path):
    task, parent = _legacy_child_and_terminal_parent()
    stale_audit = _completed_parent_audit(parent, "b" * 40)
    parent.description = "requirements changed after terminal audit"
    metadata = {
        parent.identifier: {
            METADATA_KEY: TerminalAuditMetadata(
                pending_chain=[stale_audit]
            ).to_dict()
        }
    }
    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    resolver = IntegrationLandingRequestResolver(
        project_id="project-1",
        tracker=Tracker([task, parent], metadata=metadata),
        project_store=SimpleNamespace(
            epic_branch_name=lambda epic_id: f"epic/{epic_id}"
        ),
        project_default_branch="main",
        workflow_store=store,
    )

    assert resolver(task)[0].trusted_target_revision is None
    assert store.latest_landing_facts(
        project_id="project-1", task_id=parent.identifier
    ) == ()
    store.close()


def test_conflicting_queue_and_forge_parent_heads_fail_closed(tmp_path):
    task, parent = _legacy_child_and_terminal_parent()
    queue_head = "b" * 40
    forge_head = "c" * 40
    queue = IntegrationQueueStore(str(tmp_path / "integration.sqlite3"))
    queued = queue.enqueue(
        project_id="project-1",
        epic_id="ROOT",
        task_id=parent.identifier,
        task_branch=parent.work_branch,
        head_sha=queue_head,
        base_branch=parent.target_branch,
    )
    assert queue.finish_task_generation(
        "project-1",
        parent.identifier,
        expected_generation=queued.authority_generation(),
        state="integrated",
    ) is not None
    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    resolver = IntegrationLandingRequestResolver(
        project_id="project-1",
        tracker=Tracker([task, parent]),
        integration_queue=queue,
        project_store=SimpleNamespace(
            epic_branch_name=lambda epic_id: f"epic/{epic_id}"
        ),
        project_default_branch="main",
        workflow_store=store,
        forge_review_resolver=lambda _branch: SimpleNamespace(
            id="42",
            state="merged",
            source_branch=parent.work_branch,
            target_branch=parent.target_branch,
            head_sha=forge_head,
        ),
    )

    assert resolver(task)[0].trusted_target_revision is None
    assert store.latest_landing_facts(
        project_id="project-1", task_id=parent.identifier
    ) == ()
    store.close()
    queue.close()


def test_terminal_parent_head_is_not_used_when_backfill_persistence_fails(
    tmp_path, monkeypatch
):
    task, parent = _legacy_child_and_terminal_parent()
    accepted_head = "b" * 40
    metadata = {
        parent.identifier: {
            METADATA_KEY: TerminalAuditMetadata(
                pending_chain=[
                    _completed_parent_audit(parent, accepted_head)
                ]
            ).to_dict()
        }
    }
    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    monkeypatch.setattr(
        store,
        "record_landing_facts",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("disk unavailable")),
    )
    resolver = IntegrationLandingRequestResolver(
        project_id="project-1",
        tracker=Tracker([task, parent], metadata=metadata),
        project_store=SimpleNamespace(
            epic_branch_name=lambda epic_id: f"epic/{epic_id}"
        ),
        project_default_branch="main",
        workflow_store=store,
    )

    assert resolver(task)[0].trusted_target_revision is None
    store.close()


def test_merged_forge_parent_head_backfills_when_audit_has_no_binding(tmp_path):
    task, parent = _legacy_child_and_terminal_parent()
    accepted_head = "d" * 40
    fingerprint = compute_evidence_fingerprint(
        "requirements", "project-1", parent.identifier
    )
    unbound_audit = TerminalAuditRecord(
        audit_id="legacy-audit",
        project_id="project-1",
        task_id=parent.identifier,
        target_state=TargetState.MERGED,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.COMPLETED,
        attempts=[
            AuditAttempt(
                attempt_id="legacy-attempt",
                target_state=TargetState.MERGED,
                evidence_fingerprint=fingerprint,
                request_state=RequestState.COMPLETED,
                verdict=Verdict.PASS,
            )
        ],
    )
    review = SimpleNamespace(
        id="42",
        state="merged",
        source_branch=parent.work_branch,
        target_branch=parent.target_branch,
        head_sha=accepted_head,
    )
    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    resolver = IntegrationLandingRequestResolver(
        project_id="project-1",
        tracker=Tracker(
            [task, parent],
            metadata={
                parent.identifier: {
                    METADATA_KEY: TerminalAuditMetadata(
                        pending_chain=[unbound_audit]
                    ).to_dict()
                }
            },
        ),
        project_store=SimpleNamespace(
            epic_branch_name=lambda epic_id: f"epic/{epic_id}"
        ),
        project_default_branch="main",
        workflow_store=store,
        forge_review_resolver=lambda _branch: review,
    )

    assert resolver(task)[0].trusted_target_revision == accepted_head
    persisted = store.latest_landing_facts(
        project_id="project-1", task_id=parent.identifier
    )
    assert persisted[0]["proof"] == {
        "authority": "terminal_parent_head_backfill",
        "authority_id": "42",
        "kind": "forge_merge",
        "source_sha": accepted_head,
    }
    store.close()


def test_wrong_target_forge_parent_head_fails_closed(tmp_path):
    task, parent = _legacy_child_and_terminal_parent()
    review = SimpleNamespace(
        id="42",
        state="merged",
        source_branch=parent.work_branch,
        target_branch="release",
        head_sha="d" * 40,
    )
    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    resolver = IntegrationLandingRequestResolver(
        project_id="project-1",
        tracker=Tracker([task, parent]),
        project_store=SimpleNamespace(
            epic_branch_name=lambda epic_id: f"epic/{epic_id}"
        ),
        project_default_branch="main",
        workflow_store=store,
        forge_review_resolver=lambda _branch: review,
    )

    assert resolver(task)[0].trusted_target_revision is None
    assert store.latest_landing_facts(
        project_id="project-1", task_id=parent.identifier
    ) == ()
    store.close()


def test_legacy_landing_target_precedence_and_unparented_default(tmp_path):
    task = issue("TASK-A", state="integrated", head="b" * 40)
    task.state = "Done"
    task.parent_id = "E-1"
    task.integration = replace(task.integration, base_branch=None)
    parent = issue("E-1")
    parent.work_branch = "epic/E-1"
    tracker = Tracker([task, parent])
    queue = IntegrationQueueStore(str(tmp_path / "integration.sqlite3"))
    integrated_queue_row(
        queue,
        task,
        parent_id="E-1",
        base_branch="queue/E-1",
    )
    resolver = IntegrationLandingRequestResolver(
        project_id="project-1",
        tracker=tracker,
        integration_queue=queue,
        project_store=SimpleNamespace(
            epic_branch_name=lambda epic_id: f"canonical/{epic_id}"
        ),
        project_default_branch="release",
    )

    request = resolver(task)[0]

    assert (request.source, request.target, request.revision) == (
        "TASK-A",
        "queue/E-1",
        "b" * 40,
    )
    standalone = issue("TASK-S", state="integrated", head="c" * 40)
    standalone.parent_id = None
    standalone.target_branch = None
    standalone.integration = replace(standalone.integration, base_branch=None)
    standalone_request = resolver(standalone)[0]
    assert standalone_request.target == "release"
    canonical_child = issue("TASK-C", state="integrated", head="c" * 40)
    canonical_child.parent_id = "E-2"
    canonical_child.integration = replace(canonical_child.integration, base_branch=None)
    canonical_parent = issue("E-2")
    canonical_parent.work_branch = None
    tracker.issues[canonical_child.identifier] = canonical_child
    tracker.issues[canonical_parent.identifier] = canonical_parent
    canonical_request = resolver(canonical_child)[0]
    assert canonical_request.target == "canonical/E-2"
    queue.close()


def test_corrected_landing_generation_replaces_exhaustion_across_restart(tmp_path):
    database = tmp_path / "workflow.sqlite3"
    task = issue("TASK-A", state="integrated", head="a" * 40)
    task.state = "Done"
    task.parent_id = "E-1"
    task.integration = replace(task.integration, base_branch=None)
    parent = issue("E-1")
    parent.work_branch = "epic/E-1"
    tracker = Tracker([task, parent])

    def legacy_request(issue, *, include_ready=False):
        if issue.integration.state != "integrated" and not include_ready:
            return ()
        return (
            LandingRequest(
                issue.integration.task_branch,
                issue.target_branch,
                issue.integration.integrated_sha or issue.integration.head_sha,
                authoritative_target=True,
            ),
        )

    store = WorkflowJobStore(str(database))
    old_controller = IntegrationWorkflowController(
        collector=collector(tracker, UnavailableLandingCollector()),
        store=store,
        landing_request_resolver=legacy_request,
    )
    old_batch, old_scheduled = old_controller.reconcile([task])
    assert old_batch.tasks[0].landing_requests[0].target == "main"
    assert old_scheduled.jobs_created == 1
    running = store.claim_next(lease_owner="test", lease_seconds=30)
    assert running is not None
    exhausted = store.fail(
        running.job_id,
        running.lease_token,
        category=WorkflowFailureCategory.PERMANENT,
        error="wrong legacy target exhausted",
        retryable=False,
    )
    assert exhausted.state is WorkflowJobState.EXHAUSTED
    assert store.health_snapshot()["current_states"]["exhausted"] == 1
    store.close()

    reopened = WorkflowJobStore(str(database))
    resolver = IntegrationLandingRequestResolver(
        project_id="project-1",
        tracker=tracker,
        project_store=SimpleNamespace(
            epic_branch_name=lambda epic_id: f"epic/{epic_id}"
        ),
        project_default_branch="main",
    )
    controller = IntegrationWorkflowController(
        collector=collector(tracker, UnavailableLandingCollector()),
        store=reopened,
        landing_request_resolver=resolver,
    )
    new_batch, replacement = controller.reconcile([task])

    assert new_batch.tasks[0].landing_requests[0].target == "epic/E-1"
    assert replacement.jobs_created == 1
    assert len(reopened.list_jobs(task_id="TASK-A")) == 2
    assert reopened.get(exhausted.job_id).state is WorkflowJobState.EXHAUSTED
    health = reopened.health_snapshot()
    assert health["states"]["exhausted"] == 1
    assert health["current_states"]["exhausted"] == 0

    _batch, replay = controller.reconcile([task])
    assert replay.jobs_created == 0
    assert len(reopened.list_jobs(task_id="TASK-A")) == 2
    reopened.close()


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


def landing_refresh_fact(
    *,
    proof_kind: str = "git_ancestry",
    revision: str = "a" * 40,
) -> LandingFact:
    proof = {
        "kind": proof_kind,
        "source_sha": revision,
        "target_sha": "b" * 40,
    }
    if proof_kind == "patch_id":
        proof["patches"] = 1
    return LandingFact(
        "TASK-A",
        "main",
        revision,
        proof,
        "2026-08-09T09:00:00+00:00",
        "project-1",
        state=LandingState.LANDED,
        durable=True,
    )


class LandingRefreshActionBackend:
    def __init__(self, fact, *, task_head=None):
        self.fact = fact
        self.task_head = task_head or fact.revision
        self.apply_calls = 0
        self.verify_calls = 0

    @staticmethod
    def _receipt(action, context):
        return {
            "action": action,
            "project_id": context.job.project_id,
            "task_id": context.job.task_id,
            "job_generation": context.job.generation,
        }

    def revalidate_action(self, action, context):
        return RevalidationResult(
            context.job.generation,
            evidence_revision=context.job.expected_evidence_revision,
            details={
                "task_head": self.task_head,
                "landing_source": self.fact.source,
                "landing_target": self.fact.target,
                "landing_revision": self.task_head,
            },
        )

    def observe_action(self, action, context):
        return EffectObservation(False, self._receipt(action, context))

    def apply_action(self, action, context):
        self.apply_calls += 1
        return EffectResult(
            {**self._receipt(action, context), "landing": self.fact.to_dict()}
        )

    def verify_action(self, action, context, effect):
        self.verify_calls += 1
        return VerificationResult(True, dict(effect.receipt))

    def build_action_transition(self, action, context, verification):
        return None


def landing_refresh_worker(store, backend, *, retry_delay_seconds=0):
    return DurableWorkflowWorker(
        store=store,
        handlers={
            "integration_landing_refresh": IntegrationActionHandler(
                "integration_landing_refresh",
                backend,
                domain=WorkflowActionDomain.GIT,
            )
        },
        transition_services={},
        worker_id="landing-refresh",
        lease_seconds=30,
        heartbeat_seconds=10,
        retry_delay_seconds=retry_delay_seconds,
    )


def enqueue_landing_refresh(store):
    return store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-A",
            generation="generation-1",
            action="integration_landing_refresh",
            idempotency_key="TASK-A:landing-refresh",
            expected_evidence_revision="facts-1",
            max_attempts=3,
        )
    )


@pytest.mark.asyncio
async def test_landing_fact_persistence_failure_retries_then_replays(
    tmp_path,
    monkeypatch,
):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    enqueue_landing_refresh(store)
    fact = landing_refresh_fact()
    backend = LandingRefreshActionBackend(fact)
    worker = landing_refresh_worker(store, backend)
    original_insert = store._insert_landing_fact_rows_locked
    attempts = 0

    def fail_once(**kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise WorkflowJobStoreError("injected landing persistence failure")
        return original_insert(**kwargs)

    monkeypatch.setattr(store, "_insert_landing_fact_rows_locked", fail_once)

    first = await worker.run_once()
    second = await worker.run_once()

    assert first.disposition is WorkflowRunDisposition.RETRY_SCHEDULED
    assert second.disposition is WorkflowRunDisposition.COMPLETED
    assert backend.apply_calls == 1
    assert backend.verify_calls == 1
    assert store.landing_facts(project_id="project-1", task_id="TASK-A") == (
        fact.to_dict(),
    )
    store.close()


@pytest.mark.asyncio
async def test_landing_completion_rejects_stale_source_revision(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    enqueue_landing_refresh(store)
    fact = landing_refresh_fact(revision="b" * 40)
    backend = LandingRefreshActionBackend(fact, task_head="a" * 40)

    result = await landing_refresh_worker(store, backend).run_once()

    assert result.disposition is WorkflowRunDisposition.RETRY_SCHEDULED
    assert store.landing_facts(project_id="project-1", task_id="TASK-A") == ()
    assert store.list_jobs()[0].state is WorkflowJobState.RETRY_WAIT
    store.close()


class PriorOnlyLandingCollector:
    project_id = "project-1"

    def collect_many(self, requests):
        return tuple(
            request.prior
            if request.prior is not None
            else LandingFact(
                request.source,
                request.target,
                request.revision,
                {"kind": "source_unavailable"},
                "2026-08-09T09:01:00+00:00",
                "project-1",
                state=LandingState.UNKNOWN,
                error_code="source_unavailable",
            )
            for request in requests
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("proof_kind", ("git_ancestry", "patch_id"))
async def test_verified_landing_fact_replays_after_restart_and_suppresses_refresh(
    tmp_path,
    proof_kind,
):
    path = str(tmp_path / "jobs.sqlite3")
    now = [1000.0]
    first = WorkflowJobStore(path, clock=lambda: now[0])
    job = enqueue_landing_refresh(first)
    running = first.claim_next(lease_owner="crashed-worker", lease_seconds=30)
    assert running is not None and running.job_id == job.job_id
    fact = landing_refresh_fact(proof_kind=proof_kind)
    receipt = {
        "action": "integration_landing_refresh",
        "project_id": "project-1",
        "task_id": "TASK-A",
        "job_generation": "generation-1",
        "landing": fact.to_dict(),
    }
    first.checkpoint(
        running.job_id,
        running.lease_token,
        phase="effect_verified",
        checkpoint={
            "revalidation": {
                "generation": "generation-1",
                "evidence_revision": "facts-1",
                "head_sha": None,
                "details": {"task_head": fact.revision},
            },
            "effect": receipt,
            "verification": receipt,
        },
    )
    first.close()

    now[0] += 31
    reopened = WorkflowJobStore(path, clock=lambda: now[0])
    backend = LandingRefreshActionBackend(fact)
    completed = await landing_refresh_worker(reopened, backend).run_once()

    assert completed.disposition is WorkflowRunDisposition.COMPLETED
    assert backend.apply_calls == 0
    assert backend.verify_calls == 0
    assert reopened.landing_facts(
        project_id="project-1", task_id="TASK-A"
    ) == (fact.to_dict(),)

    task = issue("TASK-A", state="integrated", head=fact.revision)
    task.integration = replace(task.integration, integrated_sha=fact.revision)
    tracker = Tracker([task])
    controller = IntegrationWorkflowController(
        collector=collector(tracker, PriorOnlyLandingCollector()),
        store=reopened,
    )

    batch, _scheduled = controller.reconcile([task])
    decision = batch.tasks[0].decision

    assert decision.reason_code == "integration.landing_proven"
    assert decision.durable_jobs == ("integration_terminal_stage",)
    landing_refreshes = reopened.list_jobs(
        task_id="TASK-A", actions=("integration_landing_refresh",)
    )
    assert len(landing_refreshes) == 1
    assert landing_refreshes[0].state is WorkflowJobState.COMPLETED
    reopened.close()


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
