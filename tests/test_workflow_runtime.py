"""Production composition and lifecycle coverage for the durable runtime."""

from __future__ import annotations

import asyncio
from pathlib import Path

from oompah.integration import IntegrationRecord
from oompah.models import BlockerRef, Issue
from oompah.task_transition_service import TaskTransitionService, TransitionJournal
from oompah.workflow_facts import FactDomain, WorkflowFactCollector
from oompah.workflow_jobs import WorkflowJobSpec, WorkflowJobState, WorkflowJobStore
from oompah.workflow_runtime import WorkflowProjectBinding, WorkflowRuntime
from oompah.workflow_worker import (
    EffectObservation,
    EffectResult,
    RevalidationResult,
    VerificationResult,
)


class NativeTracker:
    def __init__(self, issues: list[Issue]):
        self.issues = {issue.identifier: issue for issue in issues}

    def fetch_all_issues_enriched(self):
        return list(self.issues.values())

    fetch_all_issues = fetch_all_issues_enriched

    def fetch_issue_detail(self, identifier):
        return self.issues.get(identifier)

    def fetch_children(self, identifier):
        return [issue for issue in self.issues.values() if issue.parent_id == identifier]


def make_issue(identifier: str, state: str = "In Review") -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=identifier,
        description="runtime test task",
        state=state,
        project_id="project-1",
        blocked_by=[BlockerRef(identifier="DONE-1", state="Done")],
        integration=IntegrationRecord(
            state="ready", task_branch=identifier, base_branch="main", head_sha="a" * 40
        ),
        work_branch=identifier,
        target_branch="main",
    )


def make_binding(tmp_path: Path, tracker: NativeTracker, store: WorkflowJobStore):
    project_id = "project-1"
    collector = WorkflowFactCollector(
        project_id=project_id,
        tracker=tracker,
        sources={
            FactDomain.TERMINAL_AUDIT: lambda _: {"phase": "none"},
            FactDomain.REVIEW_CI: lambda _: {"state": "open", "ci": "pending"},
            FactDomain.IMPLEMENTATION_AUTHORITY: lambda _: {"lease_expires_at": None},
            FactDomain.RETRY_BUDGET: lambda _: {"remaining": 3},
            FactDomain.CONFIG: lambda _: {"version": 1},
        },
    )
    journal = TransitionJournal(str(tmp_path / "transitions.sqlite3"))
    service = TaskTransitionService(
        project_id=project_id, tracker=tracker, journal=journal
    )
    from oompah.integration_workflow import IntegrationWorkflowController

    binding = WorkflowProjectBinding(
        project_id=project_id,
        tracker=tracker,
        collector=collector,
        transition_service=service,
        integration_controller=IntegrationWorkflowController(
            collector=collector, store=store
        ),
        transition_journal=journal,
    )
    return binding, journal


def test_runtime_factory_migrates_native_tracker_startup_objects(tmp_path):
    class ProjectStore:
        def list_all(self):
            return []

    class Config:
        workflow_engine_mode = "shadow"
        workflow_runtime_decision_limit = 17
        workflow_runtime_batch_size = 9

    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([make_issue("TASK-BOOT")])
    orchestrator = type(
        "OrchestratorDouble",
        (),
        {
            "project_store": ProjectStore(),
            "tracker": tracker,
            "config": Config(),
            "workflow_job_store": store,
            "_state_path": str(tmp_path / "service-state.json"),
        },
    )()

    runtime = WorkflowRuntime.from_orchestrator(orchestrator)

    assert runtime.mode == "shadow"
    assert runtime.decision_limit == 17
    assert runtime.batch_size == 9
    assert tuple(runtime.project_bindings) == ("legacy",)
    binding = runtime.project_bindings["legacy"]
    assert binding.transition_service.project_id == "legacy"
    assert binding.integration_controller is not None
    assert binding.transition_journal is not None
    runtime.close()
    store.close()


def test_runtime_shares_ledger_and_recovers_leased_job(tmp_path):
    store_path = str(tmp_path / "jobs.sqlite3")
    store = WorkflowJobStore(store_path)
    tracker = NativeTracker([make_issue("TASK-1")])
    binding, journal = make_binding(tmp_path, tracker, store)
    spec = WorkflowJobSpec(
        project_id="project-1",
        task_id="TASK-1",
        generation="generation-1",
        action="review_refresh",
        idempotency_key="runtime-recovery-1",
    )
    queued = store.enqueue(spec)
    claimed = store.claim_next(
        lease_owner="crashed-worker", lease_seconds=60, now=1_000
    )
    assert claimed is not None and claimed.job_id == queued.job_id

    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="off",
    )
    recovery = asyncio.run(runtime.start())

    assert recovery["recovered"] == 1
    # An abandoned lease is requeued immediately; a retry-wait lease remains
    # durable until its retry_at boundary and is then claimed by the worker.
    assert store.get(queued.job_id).state is WorkflowJobState.QUEUED
    assert runtime.legacy_lifecycle_writers_enabled is True
    runtime.close()
    store.close()


class CompleteHandler:
    domain = "tracker"

    async def revalidate(self, context):
        return RevalidationResult(context.job.generation)

    async def inspect(self, context):
        return EffectObservation(False)

    async def apply(self, context):
        return EffectResult({"accepted": True})

    async def verify(self, context, effect):
        return VerificationResult(True, effect.receipt)

    async def build_transition(self, context, verification):
        return None


def test_enforce_runtime_has_one_writer_and_drains_worker(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([make_issue("TASK-2")])
    binding, journal = make_binding(tmp_path, tracker, store)
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers={"review_refresh": CompleteHandler()},
    )
    job = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-2",
            generation="generation-2",
            action="review_refresh",
            idempotency_key="runtime-enforce-1",
        )
    )

    asyncio.run(runtime.start())
    result = asyncio.run(runtime.worker.run_once())

    assert result.job_id == job.job_id
    assert store.get(job.job_id).state is WorkflowJobState.COMPLETED
    assert runtime.legacy_lifecycle_writers_enabled is False
    health = runtime.health_snapshot()
    assert health["mode"] == "enforce"
    assert health["legacy_lifecycle_writers_enabled"] is False
    assert health["worker"]["handlers_configured"] is True
    assert asyncio.run(runtime.drain(timeout_seconds=1)) is True
    runtime.close()
    store.close()


def test_shadow_runtime_materializes_decisions_without_running_effects(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([make_issue("TASK-3", state="In Review")])
    binding, journal = make_binding(tmp_path, tracker, store)
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="shadow",
    )

    asyncio.run(runtime.start())
    report = runtime.reconcile()

    assert report["mode"] == "shadow"
    assert report["projects"]["project-1"]["issues"] == 1
    assert runtime.legacy_lifecycle_writers_enabled is True
    assert runtime.health_snapshot()["worker"]["handlers_configured"] is False
    assert store.due_jobs(limit=10)
    runtime.close()
    store.close()
