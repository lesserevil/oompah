"""Production composition and lifecycle coverage for the durable runtime."""

from __future__ import annotations

import asyncio
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from oompah.epic_workflow import EpicFactCollector, EpicWorkflowController
from oompah.implementation_workflow import ImplementationWorkflowController
from oompah.integration import IntegrationRecord
from oompah.integration_workflow import (
    INTEGRATION_ACTIONS,
    IntegrationWorkflowController,
)
from oompah.models import BlockerRef, Issue
from oompah.review_workflow import ReviewWorkflowController
from oompah.task_transition_service import (
    TaskTransitionService,
    TransitionAuthority,
    TransitionIntent,
    TransitionJournal,
    issue_authority_version,
)
from oompah.terminal_audit_workflow import TerminalAuditWorkflow
from oompah.workflow_facts import FactDomain, LandingState, WorkflowFactCollector
from oompah.workflow_jobs import (
    WorkflowJobSpec,
    WorkflowJobState,
    WorkflowJobStore,
    WorkflowRolloutGateError,
)
from oompah.workflow_runtime import (
    RUNTIME_ACTIONS,
    WorkflowProjectBinding,
    WorkflowRuntime,
    WorkflowRuntimeError,
)
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
        return [
            issue for issue in self.issues.values() if issue.parent_id == identifier
        ]


def make_issue(
    identifier: str,
    state: str = "In Review",
    *,
    project_id: str = "project-1",
    issue_type: str = "task",
    parent_id: str | None = None,
) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=identifier,
        description="runtime test task",
        state=state,
        project_id=project_id,
        issue_type=issue_type,
        parent_id=parent_id,
        blocked_by=[BlockerRef(identifier="DONE-1", state="Done")],
        integration=IntegrationRecord(
            state="ready", task_branch=identifier, base_branch="main", head_sha="a" * 40
        ),
        work_branch=identifier,
        target_branch="main",
    )


def make_binding(
    tmp_path: Path,
    tracker: NativeTracker,
    store: WorkflowJobStore,
    project_id: str = "project-1",
):
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
    journal = TransitionJournal(str(tmp_path / f"{project_id}-transitions.sqlite3"))
    service = TaskTransitionService(
        project_id=project_id, tracker=tracker, journal=journal
    )
    terminal = TerminalAuditWorkflow(store)
    epic_collector = EpicFactCollector(project_id=project_id, tracker=tracker)
    binding = WorkflowProjectBinding(
        project_id=project_id,
        tracker=tracker,
        collector=collector,
        transition_service=service,
        implementation_controller=ImplementationWorkflowController(
            collector=collector, store=store
        ),
        review_controller=ReviewWorkflowController(collector=collector, store=store),
        integration_controller=IntegrationWorkflowController(
            collector=collector, store=store
        ),
        epic_collector=epic_collector,
        epic_controller=EpicWorkflowController(
            collector=epic_collector, store=store
        ),
        terminal_audit_workflow=terminal,
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
    integration_queue = object()
    tracker = NativeTracker([make_issue("TASK-BOOT")])
    orchestrator = type(
        "OrchestratorDouble",
        (),
        {
            "project_store": ProjectStore(),
            "tracker": tracker,
            "config": Config(),
            "workflow_job_store": store,
            "integration_queue": integration_queue,
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
    assert binding.implementation_controller is not None
    assert binding.review_controller is not None
    assert binding.integration_controller is not None
    assert binding.collector.integration_queue is integration_queue
    assert binding.review_controller.collector.integration_queue is integration_queue
    assert binding.epic_controller is not None
    assert binding.terminal_audit_workflow is orchestrator.terminal_audit_workflow
    assert binding.transition_journal is not None
    runtime.close()
    store.close()


def test_runtime_authority_source_refreshes_live_durable_lease(tmp_path):
    class ProjectStore:
        def list_all(self):
            return []

    class Config:
        workflow_engine_mode = "shadow"
        workflow_runtime_decision_limit = 17
        workflow_runtime_batch_size = 9

    refreshed = []
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    task = make_issue("TASK-LIVE", state="In Progress", project_id="legacy")
    tracker = NativeTracker([task])

    def refresh(_self, issue, authority):
        refreshed.append((issue.identifier, dict(authority)))
        return {**authority, "lease_expires_at": "2099-01-01T00:00:00+00:00"}

    orchestrator = type(
        "OrchestratorDouble",
        (),
        {
            "project_store": ProjectStore(),
            "tracker": tracker,
            "config": Config(),
            "workflow_job_store": store,
            "_state_path": str(tmp_path / "service-state.json"),
            "_refresh_durable_implementation_authority": refresh,
        },
    )()
    runtime = WorkflowRuntime.from_orchestrator(orchestrator)
    binding = runtime.project_bindings["legacy"]
    binding.implementation_controller.implementation_authority = lambda _issue: {
        "state": "active",
        "generation": "generation-1",
        "run_id": "run-1",
        "lease_expires_at": "2020-01-01T00:00:00+00:00",
    }

    facts = binding.collector.collect(task.identifier)
    authority = facts.fact(FactDomain.IMPLEMENTATION_AUTHORITY).value

    assert refreshed == [
        (
            task.identifier,
            {
                "state": "active",
                "generation": "generation-1",
                "run_id": "run-1",
                "lease_expires_at": "2020-01-01T00:00:00+00:00",
            },
        )
    ]
    assert authority["lease_expires_at"] == "2099-01-01T00:00:00+00:00"
    runtime.close()
    store.close()


def test_runtime_factory_invokes_legacy_fact_callbacks_before_hashing(tmp_path):
    class ProjectStore:
        def list_all(self):
            return []

    class Config:
        workflow_engine_mode = "shadow"
        workflow_runtime_decision_limit = 17
        workflow_runtime_batch_size = 9

    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    task = make_issue("TASK-FACT-SOURCES", project_id="legacy")
    tracker = NativeTracker([task])
    requested: list[tuple[str, str]] = []

    def shadow_sources(_self, requested_issue):
        return {
            domain: (
                lambda current, domain=domain: requested.append(
                    (domain.value, current.identifier)
                )
                or {"domain": domain.value, "task_id": current.identifier}
            )
            for domain in (
                FactDomain.TERMINAL_AUDIT,
                FactDomain.REVIEW_CI,
                FactDomain.IMPLEMENTATION_AUTHORITY,
                FactDomain.DUPLICATE_INVESTIGATION,
                FactDomain.RETRY_BUDGET,
                FactDomain.CONFIG,
            )
        }

    orchestrator = type(
        "OrchestratorDouble",
        (),
        {
            "project_store": ProjectStore(),
            "tracker": tracker,
            "config": Config(),
            "workflow_job_store": store,
            "_state_path": str(tmp_path / "service-state.json"),
            "_workflow_shadow_sources": shadow_sources,
        },
    )()
    runtime = WorkflowRuntime.from_orchestrator(orchestrator)

    facts = runtime.project_bindings["legacy"].collector.collect(task.identifier)

    for domain in (
        FactDomain.TERMINAL_AUDIT,
        FactDomain.REVIEW_CI,
        FactDomain.DUPLICATE_INVESTIGATION,
        FactDomain.RETRY_BUDGET,
        FactDomain.CONFIG,
    ):
        assert facts.fact(domain).value == {
            "domain": domain.value,
            "task_id": task.identifier,
        }
        assert (domain.value, task.identifier) in requested
    assert facts.fact(FactDomain.IMPLEMENTATION_AUTHORITY).value == {
        "lease_expires_at": None
    }
    assert (
        FactDomain.IMPLEMENTATION_AUTHORITY.value,
        task.identifier,
    ) not in requested
    runtime.close()
    store.close()


def test_runtime_factory_keeps_fact_sources_scoped_to_each_project(tmp_path):
    projects = [
        SimpleNamespace(
            id=project_id,
            repo_path=str(tmp_path),
            default_branch="main",
            branch="main",
        )
        for project_id in ("project-a", "project-b")
    ]

    class ProjectStore:
        def list_all(self):
            return projects

    class Config:
        workflow_engine_mode = "shadow"
        workflow_runtime_decision_limit = 17
        workflow_runtime_batch_size = 9

    issues = {
        project.id: make_issue(
            f"TASK-{project.id[-1].upper()}",
            state="In Progress",
            project_id=project.id,
        )
        for project in projects
    }
    for issue in issues.values():
        issue.integration = None
        issue.work_branch = None
    trackers = {
        project_id: NativeTracker([issue])
        for project_id, issue in issues.items()
    }
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    orchestrator = SimpleNamespace(
        project_store=ProjectStore(),
        config=Config(),
        workflow_job_store=store,
        _state_path=str(tmp_path / "service-state.json"),
        _tracker_for_project=lambda project_id: trackers[project_id],
    )
    runtime = WorkflowRuntime.from_orchestrator(orchestrator)
    for project_id, binding in runtime.project_bindings.items():
        binding.implementation_controller.implementation_authority = (
            lambda _issue, project_id=project_id: {"project_id": project_id}
        )

    observed = {
        project_id: binding.collector.collect(
            issues[project_id].identifier
        ).fact(FactDomain.IMPLEMENTATION_AUTHORITY).value["project_id"]
        for project_id, binding in runtime.project_bindings.items()
    }

    assert observed == {
        "project-a": "project-a",
        "project-b": "project-b",
    }
    runtime.close()
    store.close()


def test_runtime_scopes_projectless_tracker_rows_before_controller_hashing(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    task = make_issue("TASK-UNSCOPED", project_id=None)
    tracker = NativeTracker([task])
    binding, journal = make_binding(tmp_path, tracker, store)
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="shadow",
    )

    issues = runtime._issues(binding)

    assert issues[0].project_id == "project-1"
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
        mode="enforce",
        handlers=complete_handlers(),
        abandoned_lease_owners=("crashed-worker",),
    )
    recovery = asyncio.run(runtime.start())

    assert recovery["recovered"] == 1
    # An abandoned lease is requeued immediately; a retry-wait lease remains
    # durable until its retry_at boundary and is then claimed by the worker.
    assert store.get(queued.job_id).state is WorkflowJobState.QUEUED
    assert runtime.legacy_lifecycle_writers_enabled is False
    runtime.close()
    store.close()


class CompleteHandler:
    domain = "tracker"

    async def revalidate(self, context):
        return RevalidationResult(
            context.job.generation,
            evidence_revision=context.job.expected_evidence_revision,
            head_sha=context.job.expected_head_sha,
        )

    async def inspect(self, context):
        return EffectObservation(False)

    async def apply(self, context):
        return EffectResult({"accepted": True})

    async def verify(self, context, effect):
        return VerificationResult(True, effect.receipt)

    async def build_transition(self, context, verification):
        return None


def complete_handlers(handler=None):
    return {action: handler or CompleteHandler() for action in RUNTIME_ACTIONS}


def test_enforce_runtime_has_one_writer_and_drains_worker(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([make_issue("TASK-2")])
    binding, journal = make_binding(tmp_path, tracker, store)
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
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


def test_shadow_runtime_compares_decisions_without_durable_mutation(tmp_path):
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
    assert runtime.legacy_lifecycle_writers_enabled is False
    assert runtime.health_snapshot()["legacy_lifecycle_writers_enabled"] is False
    assert runtime.health_snapshot()["worker"]["handlers_configured"] is False
    assert store.list_jobs() == ()
    assert runtime.projections()[0]["task_id"] == "TASK-3"
    runtime.close()
    store.close()


def test_shadow_runtime_evaluates_only_enabled_rollout_domains(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([make_issue("TASK-DOMAIN", state="In Review")])
    binding, journal = make_binding(tmp_path, tracker, store)
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="shadow",
        domain_modes={
            "implementation": "shadow",
            "review": "off",
            "integration": "off",
            "epic": "off",
        },
    )

    asyncio.run(runtime.start())
    report = runtime.reconcile()

    assert set(report["projects"]["project-1"]) == {
        "issues",
        "implementation",
    }
    assert runtime.health_snapshot()["domain_modes"]["review"] == "off"
    rollout = {row["domain"]: row for row in store.rollout_snapshot()}
    assert rollout["implementation"]["successful_shadow_sweeps"] == 1
    assert rollout["review"]["successful_shadow_sweeps"] == 0
    runtime.close()
    store.close()


def test_shadow_rollout_ignores_paused_projects_for_active_coverage(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    active_binding, active_journal = make_binding(
        tmp_path,
        NativeTracker([make_issue("TASK-ACTIVE", project_id="project-active")]),
        store,
        project_id="project-active",
    )
    paused_binding, paused_journal = make_binding(
        tmp_path,
        NativeTracker([make_issue("TASK-PAUSED", project_id="project-paused")]),
        store,
        project_id="project-paused",
    )
    paused_binding.dispatch_enabled = lambda: False
    runtime = WorkflowRuntime(
        project_bindings={
            "project-active": active_binding,
            "project-paused": paused_binding,
        },
        store=store,
        journals={
            "project-active": active_journal,
            "project-paused": paused_journal,
        },
        mode="shadow",
        domain_modes={
            "implementation": "shadow",
            "review": "off",
            "integration": "off",
            "epic": "off",
        },
    )

    asyncio.run(runtime.start())
    report = runtime.reconcile()

    assert report["projects"]["project-active"]["issues"] == 1
    assert report["projects"]["project-paused"] == {
        "skipped": True,
        "reason": "project paused or orchestrator quiesced",
    }
    rollout = {row["domain"]: row for row in store.rollout_snapshot()}
    assert rollout["implementation"]["successful_shadow_sweeps"] == 1
    assert rollout["implementation"]["failed_shadow_sweeps"] == 0
    runtime.close()
    store.close()


def test_shadow_rollout_does_not_qualify_without_active_projects(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    binding, journal = make_binding(
        tmp_path,
        NativeTracker([make_issue("TASK-PAUSED")]),
        store,
    )
    binding.dispatch_enabled = lambda: False
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="shadow",
        domain_modes={
            "implementation": "shadow",
            "review": "off",
            "integration": "off",
            "epic": "off",
        },
    )

    asyncio.run(runtime.start())
    runtime.reconcile()

    rollout = {row["domain"]: row for row in store.rollout_snapshot()}
    assert rollout["implementation"]["successful_shadow_sweeps"] == 0
    assert rollout["implementation"]["failed_shadow_sweeps"] == 1
    assert (
        rollout["implementation"]["last_error"]
        == "shadow sweep did not cover every active project"
    )
    runtime.close()
    store.close()


def test_graceful_drain_does_not_poison_active_shadow_qualification(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([make_issue("TASK-DRAIN-SHADOW")])
    binding, journal = make_binding(tmp_path, tracker, store)
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="shadow",
        rollout_min_shadow_sweeps=1,
        rollout_min_shadow_seconds=0,
    )

    asyncio.run(runtime.start())
    runtime.reconcile()
    before = {
        row["domain"]: dict(row) for row in store.rollout_snapshot()
    }["review"]
    fetch_entered = threading.Event()
    release_fetch = threading.Event()
    original_fetch = tracker.fetch_all_issues_enriched

    def blocked_fetch():
        fetch_entered.set()
        assert release_fetch.wait(5), "tracker barrier timed out"
        return original_fetch()

    tracker.fetch_all_issues_enriched = blocked_fetch
    binding.dispatch_enabled = lambda: not runtime._draining

    async def exercise():
        reconcile_task = asyncio.create_task(runtime.reconcile_async())
        drain_task = None
        try:
            assert await asyncio.to_thread(fetch_entered.wait, 2)
            drain_task = asyncio.create_task(runtime.drain(timeout_seconds=2))
            await asyncio.sleep(0)
            assert runtime.health_snapshot()["draining"] is True
            assert drain_task.done() is False
            release_fetch.set()
            report = await asyncio.wait_for(reconcile_task, timeout=2)
            assert await asyncio.wait_for(drain_task, timeout=2) is True
            return report
        finally:
            release_fetch.set()
            await asyncio.gather(reconcile_task, return_exceptions=True)
            if drain_task is not None:
                await asyncio.gather(drain_task, return_exceptions=True)

    report = asyncio.run(exercise())

    assert report["projects"]["project-1"]["issues"] == 1
    after = {
        row["domain"]: dict(row) for row in store.rollout_snapshot()
    }["review"]
    assert after == before
    promoted = store.prepare_rollout(
        {
            "implementation": "shadow",
            "review": "enforce",
            "integration": "shadow",
            "epic": "shadow",
        },
        require_qualification=True,
        min_shadow_sweeps=1,
        min_shadow_seconds=0,
    )
    assert {row["domain"]: row["mode"] for row in promoted}["review"] == "enforce"
    runtime.close()
    store.close()


def test_quiesce_gap_preserves_mixed_mode_shadow_qualification(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([make_issue("TASK-QUIESCE-SHADOW")])
    binding, journal = make_binding(tmp_path, tracker, store)
    qualifying_runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="shadow",
        rollout_min_shadow_sweeps=1,
        rollout_min_shadow_seconds=0,
    )
    asyncio.run(qualifying_runtime.start())
    qualifying_runtime.reconcile()
    qualifying_runtime.close()

    mixed_modes = {
        "implementation": "enforce",
        "review": "shadow",
        "integration": "shadow",
        "epic": "shadow",
    }
    mixed_binding, mixed_journal = make_binding(tmp_path, tracker, store)
    mixed_runtime = WorkflowRuntime(
        project_bindings={"project-1": mixed_binding},
        store=store,
        journals={"project-1": mixed_journal},
        mode="shadow",
        domain_modes=mixed_modes,
        rollout_require_qualification=True,
        rollout_min_shadow_sweeps=1,
        rollout_min_shadow_seconds=0,
    )
    asyncio.run(mixed_runtime.start())
    before = {
        row["domain"]: dict(row) for row in store.rollout_snapshot()
    }["review"]
    source_entered = threading.Event()
    release_source = threading.Event()
    lifecycle_blocked = threading.Event()
    original_fetch = tracker.fetch_all_issues_enriched

    def blocked_fetch():
        source_entered.set()
        assert release_source.wait(5), "tracker barrier timed out"
        return original_fetch()

    tracker.fetch_all_issues_enriched = blocked_fetch
    mixed_binding.dispatch_enabled = lambda: not lifecycle_blocked.is_set()
    mixed_binding.lifecycle_interrupted = lifecycle_blocked.is_set

    async def exercise():
        reconcile_task = asyncio.create_task(mixed_runtime.reconcile_async())
        try:
            assert await asyncio.to_thread(source_entered.wait, 2)
            lifecycle_blocked.set()
            release_source.set()
            return await asyncio.wait_for(reconcile_task, timeout=2)
        finally:
            release_source.set()
            await asyncio.gather(reconcile_task, return_exceptions=True)

    report = asyncio.run(exercise())

    assert report["projects"]["project-1"]["issues"] == 1
    after = {
        row["domain"]: dict(row) for row in store.rollout_snapshot()
    }["review"]
    assert after == before
    mixed_runtime.close()

    promoted_modes = dict(mixed_modes, review="enforce")
    promoted_binding, promoted_journal = make_binding(tmp_path, tracker, store)
    promoted_runtime = WorkflowRuntime(
        project_bindings={"project-1": promoted_binding},
        store=store,
        journals={"project-1": promoted_journal},
        mode="shadow",
        domain_modes=promoted_modes,
        rollout_require_qualification=True,
        rollout_min_shadow_sweeps=1,
        rollout_min_shadow_seconds=0,
    )
    asyncio.run(promoted_runtime.start())
    assert promoted_runtime.health_snapshot()["domain_modes"] == promoted_modes
    promoted_runtime.close()
    store.close()


def test_graceful_drain_still_records_genuine_shadow_failure(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([make_issue("TASK-DRAIN-SHADOW-ERROR")])
    binding, journal = make_binding(tmp_path, tracker, store)
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="shadow",
        rollout_min_shadow_sweeps=1,
        rollout_min_shadow_seconds=0,
    )

    asyncio.run(runtime.start())
    runtime.reconcile()
    before = {
        row["domain"]: dict(row) for row in store.rollout_snapshot()
    }["review"]
    fetch_entered = threading.Event()
    release_fetch = threading.Event()

    def failing_fetch():
        fetch_entered.set()
        assert release_fetch.wait(5), "tracker barrier timed out"
        raise RuntimeError("genuine source failure")

    tracker.fetch_all_issues_enriched = failing_fetch
    binding.dispatch_enabled = lambda: not runtime._draining

    async def exercise():
        reconcile_task = asyncio.create_task(runtime.reconcile_async())
        drain_task = None
        try:
            assert await asyncio.to_thread(fetch_entered.wait, 2)
            drain_task = asyncio.create_task(runtime.drain(timeout_seconds=2))
            await asyncio.sleep(0)
            assert runtime.health_snapshot()["draining"] is True
            release_fetch.set()
            await asyncio.wait_for(reconcile_task, timeout=2)
            assert await asyncio.wait_for(drain_task, timeout=2) is True
        finally:
            release_fetch.set()
            await asyncio.gather(reconcile_task, return_exceptions=True)
            if drain_task is not None:
                await asyncio.gather(drain_task, return_exceptions=True)

    asyncio.run(exercise())

    after = {
        row["domain"]: dict(row) for row in store.rollout_snapshot()
    }["review"]
    assert after["successful_shadow_sweeps"] == before["successful_shadow_sweeps"]
    assert after["failed_shadow_sweeps"] == before["failed_shadow_sweeps"] + 1
    assert after["last_failure_at"] >= after["last_success_at"]
    assert "RuntimeError" in after["last_error"]
    with pytest.raises(
        WorkflowRolloutGateError, match="review: latest shadow sweep did not succeed"
    ):
        store.prepare_rollout(
            {
                "implementation": "shadow",
                "review": "enforce",
                "integration": "shadow",
                "epic": "shadow",
            },
            require_qualification=True,
            min_shadow_sweeps=1,
            min_shadow_seconds=0,
        )
    runtime.close()
    store.close()


def test_runtime_rejects_domain_map_with_different_aggregate_mode(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([make_issue("TASK-MODE")])
    binding, journal = make_binding(tmp_path, tracker, store)

    with pytest.raises(ValueError, match="aggregate domain modes"):
        WorkflowRuntime(
            project_bindings={"project-1": binding},
            store=store,
            journals={"project-1": journal},
            mode="off",
            domain_modes={
                "implementation": "shadow",
                "review": "off",
                "integration": "off",
                "epic": "off",
            },
        )

    journal.close()
    store.close()


def test_enforce_cutover_rejects_partial_handler_coverage(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([make_issue("TASK-CUTOVER")])
    binding, journal = make_binding(tmp_path, tracker, store)

    with pytest.raises(WorkflowRuntimeError, match="total project-routed"):
        WorkflowRuntime(
            project_bindings={"project-1": binding},
            store=store,
            journals={"project-1": journal},
            mode="enforce",
            handlers={"review_refresh": CompleteHandler()},
        )

    journal.close()
    store.close()


def test_factory_routes_same_action_to_exact_project(tmp_path):
    class Project:
        def __init__(self, project_id):
            self.id = project_id
            self.repo_path = str(tmp_path)
            self.default_branch = "main"

    projects = [Project("project-a"), Project("project-b")]
    trackers = {
        project.id: NativeTracker(
            [make_issue(f"TASK-{project.id[-1]}", project_id=project.id)]
        )
        for project in projects
    }

    class ProjectStore:
        def list_all(self):
            return projects

    class Config:
        workflow_engine_mode = "enforce"
        workflow_runtime_decision_limit = 20
        workflow_runtime_batch_size = 4

    seen = []

    class ProjectHandler(CompleteHandler):
        def __init__(self, project_id):
            self.project_id = project_id

        async def apply(self, context):
            seen.append((self.project_id, context.job.project_id))
            return await super().apply(context)

    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    orchestrator = type(
        "OrchestratorDouble",
        (),
        {
            "project_store": ProjectStore(),
            "config": Config(),
            "workflow_job_store": store,
            "_state_path": str(tmp_path / "service-state.json"),
            "_tracker_for_project": lambda self, project_id: trackers[project_id],
            "workflow_action_handler_factory": lambda self, binding: {
                action: ProjectHandler(binding.project_id) for action in RUNTIME_ACTIONS
            },
        },
    )()
    runtime = WorkflowRuntime.from_orchestrator(orchestrator, state_dir=tmp_path)
    for project_id in trackers:
        store.enqueue(
            WorkflowJobSpec(
                project_id=project_id,
                task_id=f"ROUTE-{project_id}",
                generation="route-1",
                action="review_refresh",
                idempotency_key=f"route-{project_id}",
            )
        )

    asyncio.run(runtime.start())
    asyncio.run(runtime.worker.run_once(actions=("review_refresh",)))
    asyncio.run(runtime.worker.run_once(actions=("review_refresh",)))

    assert set(seen) == {
        ("project-a", "project-a"),
        ("project-b", "project-b"),
    }
    runtime.close()
    store.close()


def test_factory_composes_generic_and_domain_handlers_for_every_project(tmp_path):
    class Project:
        def __init__(self, project_id):
            self.id = project_id
            self.repo_path = str(tmp_path)
            self.default_branch = "main"

    projects = [Project("project-a"), Project("project-b")]
    trackers = {
        project.id: NativeTracker(
            [make_issue(f"TASK-{project.id[-1]}", project_id=project.id)]
        )
        for project in projects
    }

    class ProjectStore:
        def list_all(self):
            return projects

    class Config:
        workflow_engine_mode = "enforce"
        workflow_runtime_decision_limit = 20
        workflow_runtime_batch_size = 4

    store = WorkflowJobStore(str(tmp_path / "composed-jobs.sqlite3"))
    orchestrator = type(
        "ComposedOrchestratorDouble",
        (),
        {
            "project_store": ProjectStore(),
            "config": Config(),
            "workflow_job_store": store,
            "_state_path": str(tmp_path / "composed-service-state.json"),
            "_tracker_for_project": lambda self, project_id: trackers[project_id],
            "workflow_action_handler_factory": lambda self, binding: {
                action: CompleteHandler()
                for action in RUNTIME_ACTIONS - INTEGRATION_ACTIONS
            },
            "workflow_integration_action_handler_factory": lambda self, binding: {
                action: CompleteHandler() for action in INTEGRATION_ACTIONS
            },
        },
    )()

    runtime = WorkflowRuntime.from_orchestrator(orchestrator, state_dir=tmp_path)

    assert set(runtime.worker.handlers) == RUNTIME_ACTIONS
    assert all(
        set(runtime._handler_coverage[action]) == {"project-a", "project-b"}
        for action in RUNTIME_ACTIONS
    )
    runtime.close()
    store.close()


def test_factory_rejects_duplicate_action_ownership(tmp_path):
    class Project:
        id = "project-a"
        repo_path = str(tmp_path)
        default_branch = "main"

    class ProjectStore:
        def list_all(self):
            return [Project()]

    class Config:
        workflow_engine_mode = "enforce"
        workflow_runtime_decision_limit = 20
        workflow_runtime_batch_size = 4

    tracker = NativeTracker([make_issue("TASK-A", project_id="project-a")])
    store = WorkflowJobStore(str(tmp_path / "duplicate-jobs.sqlite3"))
    orchestrator = type(
        "DuplicateOrchestratorDouble",
        (),
        {
            "project_store": ProjectStore(),
            "config": Config(),
            "workflow_job_store": store,
            "_state_path": str(tmp_path / "duplicate-service-state.json"),
            "_tracker_for_project": lambda self, _project_id: tracker,
            "workflow_action_handler_factory": lambda self, binding: {
                action: CompleteHandler() for action in RUNTIME_ACTIONS
            },
            "workflow_integration_action_handler_factory": lambda self, binding: {
                "integration_attempt": CompleteHandler()
            },
        },
    )()

    with pytest.raises(WorkflowRuntimeError, match="duplicate workflow action ownership"):
        WorkflowRuntime.from_orchestrator(orchestrator, state_dir=tmp_path)

    store.close()


def test_enforce_runtime_refreshes_remote_target_before_landing_decision(tmp_path):
    origin = tmp_path / "origin.git"
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "--bare", str(origin)], check=True)
    subprocess.run(["git", "init", "-b", "main", str(repo)], check=True)
    subprocess.run(
        ["git", "config", "user.email", "runtime@example.invalid"],
        cwd=repo,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Runtime Test"], cwd=repo, check=True
    )
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "base"], cwd=repo, check=True
    )
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run(["git", "checkout", "-b", "epic-TOP"], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "epic"], cwd=repo, check=True
    )
    epic_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run(["git", "checkout", "main"], cwd=repo, check=True)
    subprocess.run(["git", "remote", "add", "origin", str(origin)], cwd=repo, check=True)
    subprocess.run(
        ["git", "push", "origin", "main", "epic-TOP"], cwd=repo, check=True
    )
    subprocess.run(
        ["git", "merge", "--no-ff", "epic-TOP", "-m", "land epic"],
        cwd=repo,
        check=True,
    )
    merged = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run(["git", "push", "origin", "main"], cwd=repo, check=True)
    subprocess.run(
        ["git", "update-ref", "refs/heads/main", base], cwd=repo, check=True
    )
    subprocess.run(
        ["git", "update-ref", "refs/remotes/origin/main", base],
        cwd=repo,
        check=True,
    )

    project = SimpleNamespace(
        id="project-1",
        repo_path=str(repo),
        default_branch="main",
        branch="main",
        access_token=None,
        forge_kind="github",
    )
    project_lock = threading.RLock()

    class ProjectStore:
        def list_all(self):
            return [project]

        def project_write_lock(self, _project_id):
            return project_lock

    class Config:
        workflow_engine_mode = "enforce"
        workflow_runtime_decision_limit = 20
        workflow_runtime_batch_size = 4

    issue = Issue(
        id="TOP",
        identifier="TOP",
        title="TOP",
        description="remote landing runtime fixture",
        state="In Review",
        project_id="project-1",
        issue_type="epic",
        work_branch="epic-TOP",
        target_branch="main",
        head_sha=epic_head,
    )
    # A rollup with no children is intentionally not auto-close eligible even
    # when its own branch is landed.  Include an explicitly abandoned direct
    # child so this fixture exercises both authoritative target refresh and the
    # valid auto-close mutation guard.
    child = Issue(
        id="CHILD",
        identifier="CHILD",
        title="CHILD",
        description="abandoned child fixture",
        state="Archived",
        project_id="project-1",
        parent_id="TOP",
    )
    landed_task = Issue(
        id="LANDED-TASK",
        identifier="LANDED-TASK",
        title="LANDED-TASK",
        description="ordinary landed task guard fixture",
        state="Done",
        project_id="project-1",
        issue_type="task",
        work_branch="epic-TOP",
        target_branch="main",
        head_sha=epic_head,
        integration=IntegrationRecord(
            state="integrated",
            mode="queue",
            task_branch="epic-TOP",
            base_branch="main",
            head_sha=epic_head,
            integrated_sha=epic_head,
        ),
    )
    tracker = NativeTracker([issue, child, landed_task])
    store = WorkflowJobStore(str(tmp_path / "remote-jobs.sqlite3"))

    def network_git(_project, args, *, cwd, timeout):
        return subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )

    orchestrator = SimpleNamespace(
        project_store=ProjectStore(),
        config=Config(),
        workflow_job_store=store,
        _state_path=str(tmp_path / "remote-service-state.json"),
        _tracker_for_project=lambda _project_id: tracker,
        _run_project_network_git=network_git,
        workflow_action_handler_factory=lambda _binding: {
            action: CompleteHandler() for action in RUNTIME_ACTIONS
        },
    )
    runtime = WorkflowRuntime.from_orchestrator(
        orchestrator,
        state_dir=tmp_path,
        terminal_transition_coordinator=MagicMock(),
    )
    orchestrator.workflow_runtime = runtime

    binding = runtime.project_bindings["project-1"]
    facts = binding.epic_collector.collect("TOP")
    own = next(
        landing
        for landing in facts.landings
        if landing.source == "epic-TOP" and landing.target == "main"
    )

    assert own.state is LandingState.LANDED
    assert own.proof["target_sha"] == merged
    assert subprocess.run(
        ["git", "rev-parse", "refs/heads/main"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip() == base

    decision = binding.epic_controller.evaluate(
        (issue,), persist_evidence=False
    ).tasks[0].decision
    sentinel = object()
    binding.epic_controller._latest = {"UNRELATED": sentinel}
    guard = binding.transition_service.terminal_adapter._mutation_guard
    intent = TransitionIntent(
        project_id="project-1",
        task_id="TOP",
        expected_status="In Review",
        expected_version=issue_authority_version(issue),
        requested_status="Merged",
        actor="oompah",
        authority=TransitionAuthority.ORCHESTRATOR,
        reason_code="terminal.immediate_target_landing_proven",
        idempotency_key="auto-close-guard-projection",
        originating_job="epic-auto-close-job",
        precondition_revision=decision.evidence_revision,
    )

    assert guard(intent) is None
    assert binding.epic_controller._latest == {"UNRELATED": sentinel}

    task_decision = binding.integration_controller.evaluate(
        (landed_task,)
    ).tasks[0].decision
    task_intent = TransitionIntent(
        project_id="project-1",
        task_id=landed_task.identifier,
        expected_status="Done",
        expected_version=issue_authority_version(landed_task),
        requested_status="Merged",
        actor="oompah",
        authority=TransitionAuthority.ORCHESTRATOR,
        reason_code="terminal.immediate_target_landing_proven",
        idempotency_key="ordinary-landed-task-guard",
        originating_job="ordinary-landed-task-job",
        precondition_revision=task_decision.evidence_revision,
    )

    assert task_decision.durable_jobs == ("parent_rollup_review",)
    assert guard(task_intent) is None

    ordinary_intent = TransitionIntent(
        project_id="project-1",
        task_id="TOP",
        expected_status="In Review",
        expected_version=issue_authority_version(issue),
        requested_status="Archived",
        actor="oompah",
        authority=TransitionAuthority.ORCHESTRATOR,
        reason_code="terminal.operator_requested",
        idempotency_key="ordinary-terminal-cas",
        originating_job="ordinary-terminal-job",
    )
    assert guard(ordinary_intent) is None
    issue.labels = ["merge-conflict"]
    assert guard(ordinary_intent) == "task transition authority changed"
    issue.labels = []

    helper = Issue(
        id="REBASE-1",
        identifier="REBASE-1",
        title="Rebase epic-TOP onto main",
        description="runtime rebase guard fixture",
        state="Needs Rebase",
        project_id="project-1",
        issue_type="task",
        parent_id="TOP",
        target_branch="main",
    )
    tracker.issues[helper.identifier] = helper
    rebase_revision = EpicWorkflowController(
        collector=binding.epic_controller.collector,
        store=binding.epic_controller.store,
    ).evaluate((issue,), persist_evidence=False).tasks[0].decision.evidence_revision
    rebase_intent = TransitionIntent(
        project_id="project-1",
        task_id=helper.identifier,
        expected_status="Needs Rebase",
        expected_version=issue_authority_version(helper),
        requested_status="Archived",
        actor="oompah",
        authority=TransitionAuthority.ORCHESTRATOR,
        reason_code="epic.rebase_target_superseded",
        idempotency_key="rebase-retirement-guard",
        originating_job="epic-rebase-job",
        precondition_revision=rebase_revision,
    )

    assert guard(rebase_intent) is None
    tracker.issues["REBASE-2"] = Issue(
        id="REBASE-2",
        identifier="REBASE-2",
        title="Rebase epic-TOP onto main",
        description="concurrent sibling fixture",
        state="Needs Rebase",
        project_id="project-1",
        issue_type="task",
        parent_id="TOP",
        target_branch="main",
    )
    assert guard(rebase_intent) == "epic workflow evidence or containment changed"
    assert binding.epic_controller._latest == {"UNRELATED": sentinel}
    runtime.close()
    store.close()


def test_restart_recovery_is_scoped_and_leaves_terminal_finalization_owned(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([make_issue("TASK-RECOVER")])
    binding, journal = make_binding(tmp_path, tracker, store)
    implementation = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-RECOVER",
            generation="implementation-1",
            action="implementation_start",
            idempotency_key="implementation-recovery",
        )
    )
    terminal = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-AUDIT",
            generation="audit-1",
            action="terminal_audit",
            idempotency_key="terminal-finalization",
        )
    )
    queued_terminal = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-UNSAFE-ARCHIVE",
            generation="audit-queued",
            action="terminal_audit",
            idempotency_key="terminal-queued-after-rejection",
        )
    )
    claimed_implementation = store.claim_next(
        lease_owner="known-dead",
        lease_seconds=10_000,
        actions=("implementation_start",),
    )
    claimed_terminal = store.claim_next(
        lease_owner="terminal-audit", lease_seconds=10_000, actions=("terminal_audit",)
    )
    assert claimed_implementation is not None
    assert claimed_terminal is not None
    terminal = store.checkpoint(
        terminal.job_id,
        claimed_terminal.lease_token,
        phase="finalizing",
        checkpoint={"attempt_id": "audit-attempt"},
    )
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
        abandoned_lease_owners=("known-dead",),
    )

    recovery = asyncio.run(runtime.start())
    recovered_state = store.get(implementation.job_id).state
    generic_result = asyncio.run(runtime.worker.run_once())
    idle_result = asyncio.run(runtime.worker.run_once())

    assert recovery["abandoned"] == 1
    assert recovered_state is WorkflowJobState.QUEUED
    assert store.get(terminal.job_id).state is WorkflowJobState.RUNNING
    assert store.get(terminal.job_id).phase == "finalizing"
    assert store.get(queued_terminal.job_id).state is WorkflowJobState.QUEUED
    assert generic_result.job_id == implementation.job_id
    assert idle_result.job_id is None
    runtime.close()
    store.close()


def test_epics_have_one_domain_owner_and_new_facts_supersede_old_job(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    epic = make_issue("EPIC-1", state="Open", issue_type="epic")
    tracker = NativeTracker([epic])
    binding, journal = make_binding(tmp_path, tracker, store)
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
    )

    asyncio.run(runtime.start())
    first = runtime.reconcile()
    first_jobs = store.list_jobs(task_id="EPIC-1")
    tracker.issues["CHILD-1"] = make_issue(
        "CHILD-1", state="Open", parent_id="EPIC-1"
    )
    second = runtime.reconcile()
    jobs = store.list_jobs(task_id="EPIC-1")

    assert first["projects"]["project-1"]["implementation"]["decisions_seen"] == 0
    assert first["projects"]["project-1"]["review"]["decisions_seen"] == 0
    assert first["projects"]["project-1"]["integration"]["decisions_seen"] == 0
    assert first["projects"]["project-1"]["epic"]["decisions_seen"] == 1
    assert len(first_jobs) == 1
    assert first_jobs[0].action in RUNTIME_ACTIONS
    assert second["projects"]["project-1"]["epic"]["jobs_superseded"] == 1
    assert sum(job.state is WorkflowJobState.QUEUED for job in jobs) == 1
    assert sum(job.state is WorkflowJobState.SUPERSEDED for job in jobs) == 1
    runtime.close()
    store.close()


def test_runtime_routes_direct_maintenance_audit_through_integration_domain(
    tmp_path,
):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    parent = make_issue("EPIC-1", state="In Progress", issue_type="epic")
    maintenance = make_issue(
        "MAINT-1",
        state="Open",
        parent_id=parent.identifier,
    )
    maintenance.title = "Rebase epic-EPIC-1 onto main"
    maintenance.work_branch = "epic-EPIC-1"
    maintenance.target_branch = "epic-EPIC-1"
    maintenance.head_sha = "b" * 40
    maintenance.integration = IntegrationRecord(
        state="integrated",
        mode="queue",
        task_branch="epic-EPIC-1",
        base_branch="epic-EPIC-1",
        head_sha="b" * 40,
        integrated_sha="b" * 40,
        maintenance_publication_proven=True,
    )
    tracker = NativeTracker([parent, maintenance])
    binding, journal = make_binding(tmp_path, tracker, store)
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
    )

    asyncio.run(runtime.start())
    report = runtime.reconcile()

    assert "error" not in report["projects"]["project-1"]
    assert report["projects"]["project-1"]["integration"]["decisions_seen"] == 1
    jobs = store.list_jobs(task_id=maintenance.identifier)
    assert len(jobs) == 1
    assert jobs[0].action == "terminal_audit_done"
    runtime.close()
    store.close()


def test_shared_snapshot_keeps_review_integration_and_epic_jobs_claimable(
    tmp_path,
):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    review = make_issue("TASK-REVIEW", state="In Review")
    integration = make_issue("TASK-INTEGRATE", state="Ready to Integrate")
    epic = make_issue("EPIC-SHARED", state="Open", issue_type="epic")
    tracker = NativeTracker([review, integration, epic])
    binding, journal = make_binding(tmp_path, tracker, store)
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
    )

    asyncio.run(runtime.start())
    report = runtime.reconcile()

    project = report["projects"]["project-1"]
    generation = project["snapshot"]["generation"]
    assert project["snapshot"]["published"] is True
    assert {
        project[domain]["snapshot_generation"]
        for domain in ("review", "integration", "epic")
    } == {generation}
    assert all(
        project[domain]["snapshot_accepted"] is True
        for domain in ("review", "integration", "epic")
    )
    assert store.snapshot_membership() == (
        ("project-1", "EPIC-SHARED", generation),
        ("project-1", "TASK-INTEGRATE", generation),
        ("project-1", "TASK-REVIEW", generation),
    )

    claimed = []
    for index in range(3):
        job = store.claim_next(
            lease_owner=f"shared-worker-{index}",
            lease_seconds=30,
        )
        assert job is not None
        claimed.append(job)
    assert {job.task_id for job in claimed} == {
        "EPIC-SHARED",
        "TASK-INTEGRATE",
        "TASK-REVIEW",
    }

    runtime.close()
    store.close()


def test_shared_snapshot_generation_keeps_multiple_projects_claimable(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker_a = NativeTracker(
        [make_issue("A-REVIEW", state="In Review", project_id="project-a")]
    )
    tracker_b = NativeTracker(
        [
            make_issue(
                "B-INTEGRATE",
                state="Ready to Integrate",
                project_id="project-b",
            ),
            make_issue(
                "B-EPIC",
                state="Open",
                project_id="project-b",
                issue_type="epic",
            ),
        ]
    )
    binding_a, journal_a = make_binding(
        tmp_path, tracker_a, store, project_id="project-a"
    )
    binding_b, journal_b = make_binding(
        tmp_path, tracker_b, store, project_id="project-b"
    )
    handlers = complete_handlers()
    runtime = WorkflowRuntime(
        project_bindings={"project-a": binding_a, "project-b": binding_b},
        store=store,
        journals={"project-a": journal_a, "project-b": journal_b},
        mode="enforce",
        handlers=handlers,
        handler_coverage={
            action: ("project-a", "project-b") for action in handlers
        },
    )

    asyncio.run(runtime.start())
    report = runtime.reconcile()

    project_a = report["projects"]["project-a"]
    project_b = report["projects"]["project-b"]
    generation = project_a["snapshot"]["generation"]
    assert project_b["snapshot"]["generation"] == generation
    assert store.snapshot_membership() == (
        ("project-a", "A-REVIEW", generation),
        ("project-b", "B-EPIC", generation),
        ("project-b", "B-INTEGRATE", generation),
    )

    claimed = []
    for index in range(3):
        job = store.claim_next(
            lease_owner=f"multi-project-worker-{index}",
            lease_seconds=30,
        )
        assert job is not None
        claimed.append(job)
    assert {(job.project_id, job.task_id) for job in claimed} == {
        ("project-a", "A-REVIEW"),
        ("project-b", "B-EPIC"),
        ("project-b", "B-INTEGRATE"),
    }

    runtime.close()
    store.close()


def test_post_publish_implementation_failure_recovers_on_next_snapshot(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([make_issue("TASK-RECOVER", state="In Review")])
    binding, journal = make_binding(tmp_path, tracker, store)
    implementation = binding.implementation_controller
    original_reconcile = implementation.reconcile
    calls = 0

    def fail_once(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("implementation event lane unavailable")
        return original_reconcile(*args, **kwargs)

    implementation.reconcile = fail_once
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
    )

    asyncio.run(runtime.start())
    first = asyncio.run(runtime.reconcile_async())

    assert first["projects"]["project-1"]["error"] == "RuntimeError"
    assert first["projects"]["project-1"]["snapshot"]["published"] is True
    assert first["worker"]["skipped"] is True
    queued = store.list_jobs(
        project_id="project-1",
        task_id="TASK-RECOVER",
        states=("queued",),
    )
    assert len(queued) == 1

    second = asyncio.run(runtime.reconcile_async())

    assert "error" not in second["projects"]["project-1"]
    assert second["worker"]["processed"] == 1
    recovered = store.list_jobs(
        project_id="project-1",
        task_id="TASK-RECOVER",
        states=("completed",),
    )
    assert len(recovered) == 1
    assert store.get(queued[0].job_id).state in {
        WorkflowJobState.COMPLETED,
        WorkflowJobState.SUPERSEDED,
    }

    runtime.close()
    store.close()


def test_epic_terminal_audit_job_is_not_reconciled_by_epic_domain(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    epic = make_issue("EPIC-AUDIT", state="In Validation", issue_type="epic")
    tracker = NativeTracker([epic])
    binding, journal = make_binding(tmp_path, tracker, store)
    audit_job = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id=epic.identifier,
            generation="audit-generation",
            action="terminal_audit",
            idempotency_key="unsafe-revisionless-archive-audit",
        )
    )
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="shadow",
    )

    asyncio.run(runtime.start())
    report = runtime.reconcile()

    assert report["projects"]["project-1"]["epic"]["decisions_seen"] == 0
    assert store.get(audit_job.job_id).state is WorkflowJobState.QUEUED
    runtime.close()
    store.close()


def test_reconcile_async_executes_effects_on_callers_event_loop(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([make_issue("TASK-LOOP")])
    binding, journal = make_binding(tmp_path, tracker, store)
    observed_loops = []

    class LoopHandler(CompleteHandler):
        async def apply(self, context):
            observed_loops.append(asyncio.get_running_loop())
            return await super().apply(context)

    handler = LoopHandler()
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(handler),
    )

    async def exercise():
        expected = asyncio.get_running_loop()
        await runtime.start()
        report = await runtime.reconcile_async()
        return expected, report

    expected_loop, report = asyncio.run(exercise())

    assert report["worker"]["processed"] == 1
    assert observed_loops == [expected_loop]
    runtime.close()
    store.close()


def test_drain_waits_for_reconcile_before_store_close(tmp_path):
    """An admitted reconcile remains explicit store-mutation authority."""

    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([make_issue("TASK-DRAIN-RECONCILE")])
    binding, journal = make_binding(tmp_path, tracker, store)
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="shadow",
    )
    reconcile_entered = threading.Event()
    release_reconcile = threading.Event()
    original_record_rollout_sweep = store.record_rollout_sweep

    def _blocked_record_rollout_sweep(*args, **kwargs):
        reconcile_entered.set()
        assert release_reconcile.wait(5), "reconcile barrier timed out"
        return original_record_rollout_sweep(*args, **kwargs)

    store.record_rollout_sweep = _blocked_record_rollout_sweep

    async def _exercise():
        await runtime.start()
        reconcile_task = asyncio.create_task(runtime.reconcile_async())
        drain_task = None
        try:
            assert await asyncio.to_thread(reconcile_entered.wait, 2)
            assert runtime.pending_operation_count >= 1
            with pytest.raises(
                WorkflowRuntimeError,
                match="cannot close workflow runtime while .* operation",
            ):
                runtime.close()

            drain_task = asyncio.create_task(runtime.drain(timeout_seconds=2))
            await asyncio.sleep(0)
            assert runtime.health_snapshot()["draining"] is True
            assert drain_task.done() is False
            assert store._authority_lock_fd >= 0

            release_reconcile.set()
            report = await asyncio.wait_for(reconcile_task, timeout=2)
            assert await asyncio.wait_for(drain_task, timeout=2) is True
            assert report["mode"] == "shadow"
            assert runtime.pending_operation_count == 0
        finally:
            release_reconcile.set()
            await asyncio.gather(reconcile_task, return_exceptions=True)
            if drain_task is not None:
                await asyncio.gather(drain_task, return_exceptions=True)

    asyncio.run(_exercise())
    store.integrity_check()
    runtime.close()
    store.close()


def test_cancelled_reconcile_retains_authority_until_thread_finishes(tmp_path):
    """Caller cancellation cannot abandon a live reconcile worker thread."""

    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([make_issue("TASK-CANCEL-RECONCILE")])
    binding, journal = make_binding(tmp_path, tracker, store)
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="shadow",
    )
    reconcile_entered = threading.Event()
    release_reconcile = threading.Event()
    original_record_rollout_sweep = store.record_rollout_sweep

    def _blocked_record_rollout_sweep(*args, **kwargs):
        reconcile_entered.set()
        assert release_reconcile.wait(5), "reconcile barrier timed out"
        return original_record_rollout_sweep(*args, **kwargs)

    store.record_rollout_sweep = _blocked_record_rollout_sweep

    async def _exercise():
        await runtime.start()
        reconcile_task = asyncio.create_task(runtime.reconcile_async())
        drain_task = None
        try:
            assert await asyncio.to_thread(reconcile_entered.wait, 2)
            reconcile_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await reconcile_task

            assert runtime.pending_operation_count >= 1
            with pytest.raises(
                WorkflowRuntimeError,
                match="cannot close workflow runtime while .* operation",
            ):
                runtime.close()

            drain_task = asyncio.create_task(runtime.drain(timeout_seconds=2))
            await asyncio.sleep(0)
            assert drain_task.done() is False
            assert store._authority_lock_fd >= 0

            release_reconcile.set()
            assert await asyncio.wait_for(drain_task, timeout=2) is True
            assert runtime.pending_operation_count == 0
        finally:
            release_reconcile.set()
            if drain_task is not None:
                await asyncio.gather(drain_task, return_exceptions=True)

    asyncio.run(_exercise())
    store.integrity_check()
    runtime.close()
    store.close()


def test_loop_teardown_cancellation_waits_for_executor_mutation(tmp_path):
    """Loop teardown cannot hide a still-running executor mutation."""

    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([make_issue("TASK-CANCEL-EXECUTOR")])
    binding, journal = make_binding(tmp_path, tracker, store)
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="shadow",
    )
    reconcile_entered = threading.Event()
    release_reconcile = threading.Event()
    original_record_rollout_sweep = store.record_rollout_sweep

    def _blocked_record_rollout_sweep(*args, **kwargs):
        reconcile_entered.set()
        assert release_reconcile.wait(5), "reconcile barrier timed out"
        return original_record_rollout_sweep(*args, **kwargs)

    store.record_rollout_sweep = _blocked_record_rollout_sweep

    async def _exercise():
        await runtime.start()
        reconcile_task = asyncio.create_task(runtime.reconcile_async())
        drain_task = None
        try:
            assert await asyncio.to_thread(reconcile_entered.wait, 2)
            owned_task = next(iter(runtime._reconcile_tasks))

            # asyncio.run() cancels every remaining Task at exit. The owned
            # task must defer that cancellation while its bare executor Future
            # continues the uncancellable mutation.
            owned_task.cancel()
            await asyncio.sleep(0)

            assert runtime.pending_operation_count >= 1
            assert reconcile_task.done() is False
            with pytest.raises(
                WorkflowRuntimeError,
                match="cannot close workflow runtime while .* operation",
            ):
                runtime.close()

            drain_task = asyncio.create_task(runtime.drain(timeout_seconds=2))
            await asyncio.sleep(0)
            assert drain_task.done() is False
            assert store._authority_lock_fd >= 0

            release_reconcile.set()
            with pytest.raises(asyncio.CancelledError):
                await reconcile_task
            assert await asyncio.wait_for(drain_task, timeout=2) is True
            assert runtime.pending_operation_count == 0
        finally:
            release_reconcile.set()
            if drain_task is not None:
                await asyncio.gather(drain_task, return_exceptions=True)

    asyncio.run(_exercise())
    store.integrity_check()
    runtime.close()
    store.close()


def test_cancelled_queued_reconcile_retains_authority_until_executor_runs(tmp_path):
    """Cancellation cannot open a queue-to-executor ownership gap."""

    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    runtime = WorkflowRuntime(
        project_bindings={},
        store=store,
        journals={},
        mode="off",
    )
    blocker_started = threading.Event()
    release_blocker = threading.Event()

    def _block_default_executor():
        blocker_started.set()
        assert release_blocker.wait(5), "executor barrier timed out"

    async def _exercise():
        loop = asyncio.get_running_loop()
        executor = ThreadPoolExecutor(max_workers=1)
        loop.set_default_executor(executor)
        blocker = loop.run_in_executor(None, _block_default_executor)
        for _ in range(100):
            if blocker_started.is_set():
                break
            await asyncio.sleep(0.01)
        assert blocker_started.is_set()

        await runtime.start()
        caller = asyncio.create_task(runtime.reconcile_async())
        try:
            for _ in range(100):
                if executor._work_queue.qsize() >= 1:
                    break
                await asyncio.sleep(0)
            assert executor._work_queue.qsize() >= 1

            owned_task = next(iter(runtime._reconcile_tasks))
            owned_task.cancel()
            await asyncio.sleep(0)

            assert caller.done() is False
            assert runtime.pending_operation_count == 1
            with pytest.raises(
                WorkflowRuntimeError,
                match="cannot close workflow runtime while 1 operation",
            ):
                runtime.close()

            drain_task = asyncio.create_task(runtime.drain(timeout_seconds=2))
            await asyncio.sleep(0)
            assert drain_task.done() is False

            release_blocker.set()
            await blocker
            with pytest.raises(asyncio.CancelledError):
                await caller
            assert await asyncio.wait_for(drain_task, timeout=2) is True
            assert runtime.pending_operation_count == 0
        finally:
            release_blocker.set()

    asyncio.run(_exercise())
    store.integrity_check()
    runtime.close()
    store.close()


def test_prestart_reconcile_task_cancellation_releases_admission(tmp_path):
    """A task cancelled before its first turn cannot strand shutdown."""

    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    runtime = WorkflowRuntime(
        project_bindings={},
        store=store,
        journals={},
        mode="off",
    )

    async def _exercise():
        await runtime.start()
        caller = asyncio.create_task(runtime.reconcile_async())
        await asyncio.sleep(0)
        owned_task = next(iter(runtime._reconcile_tasks))
        assert owned_task.get_coro().cr_await is None

        owned_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await caller
        await asyncio.sleep(0)

        assert runtime.pending_operation_count == 0
        assert await runtime.drain(timeout_seconds=1) is True

    asyncio.run(_exercise())
    runtime.close()
    store.close()


def test_domain_limits_are_applied_after_semantic_eligibility(tmp_path):
    """Stable irrelevant rows must not hide a later actionable task forever."""

    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))

    implementation_tracker = NativeTracker(
        [make_issue("A-DONE", state="Done"), make_issue("Z-OPEN", state="Open")]
    )
    implementation_binding, implementation_journal = make_binding(
        tmp_path, implementation_tracker, store
    )
    implementation = ImplementationWorkflowController(
        collector=implementation_binding.collector,
        store=store,
        decision_limit=1,
    )
    assert [item.task.identifier for item in implementation.evaluate(
        list(implementation_tracker.issues.values())
    ).tasks] == ["Z-OPEN"]

    review_tracker = NativeTracker(
        [
            make_issue("A-DONE", state="Done", project_id="project-review"),
            make_issue(
                "Z-REVIEW", state="In Review", project_id="project-review"
            ),
        ]
    )
    review_binding, review_journal = make_binding(
        tmp_path, review_tracker, store, project_id="project-review"
    )
    review = ReviewWorkflowController(
        collector=review_binding.collector,
        store=store,
        decision_limit=1,
    )
    assert [item.task.identifier for item in review.evaluate(
        list(review_tracker.issues.values())
    ).tasks] == ["Z-REVIEW"]

    integration_tracker = NativeTracker(
        [
            make_issue(
                "A-MERGED",
                state="Merged",
                project_id="project-integration",
            ),
            make_issue(
                "Z-READY",
                state="Ready to Integrate",
                project_id="project-integration",
            ),
        ]
    )
    integration_binding, integration_journal = make_binding(
        tmp_path,
        integration_tracker,
        store,
        project_id="project-integration",
    )
    integration = IntegrationWorkflowController(
        collector=integration_binding.collector,
        store=store,
        decision_limit=1,
    )
    assert [item.task.identifier for item in integration.evaluate(
        list(integration_tracker.issues.values())
    ).tasks] == ["Z-READY"]

    epic_tracker = NativeTracker(
        [
            make_issue("A-MERGED", state="Merged", issue_type="epic"),
            make_issue("Z-EPIC", state="Open", issue_type="epic"),
        ]
    )
    epic = EpicWorkflowController(
        collector=EpicFactCollector(project_id="project-1", tracker=epic_tracker),
        store=store,
        decision_limit=1,
    )
    assert [item.task.identifier for item in epic.evaluate(
        list(epic_tracker.issues.values()), persist_evidence=False
    ).tasks] == ["Z-EPIC"]

    for journal in {
        implementation_journal,
        review_journal,
        integration_journal,
    }:
        journal.close()
    store.close()


def test_failed_project_does_not_stall_healthy_project_worker(tmp_path):
    class FailingTracker(NativeTracker):
        def fetch_all_issues_enriched(self):
            raise RuntimeError("tracker unavailable")

        fetch_all_issues = fetch_all_issues_enriched

    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    bad_tracker = FailingTracker([])
    good_tracker = NativeTracker(
        [make_issue("GOOD-DONE", state="Merged", project_id="project-good")]
    )
    bad_binding, bad_journal = make_binding(
        tmp_path, bad_tracker, store, project_id="project-bad"
    )
    good_binding, good_journal = make_binding(
        tmp_path, good_tracker, store, project_id="project-good"
    )
    handlers = complete_handlers()
    runtime = WorkflowRuntime(
        project_bindings={
            "project-bad": bad_binding,
            "project-good": good_binding,
        },
        store=store,
        journals={
            "project-bad": bad_journal,
            "project-good": good_journal,
        },
        mode="enforce",
        handlers=handlers,
        handler_coverage={action: ("project-bad", "project-good") for action in handlers},
    )
    job = store.enqueue(
        WorkflowJobSpec(
            project_id="project-good",
            task_id="GOOD-DONE",
            generation="healthy-project-1",
            action="review_refresh",
            idempotency_key="healthy-project-worker",
        )
    )

    asyncio.run(runtime.start())
    report = asyncio.run(runtime.reconcile_async())

    assert report["projects"]["project-bad"]["error"] == "RuntimeError"
    assert report["worker"]["failed_projects"] == ["project-bad"]
    assert report["worker"]["processed"] == 1
    assert store.get(job.job_id).state is WorkflowJobState.COMPLETED
    runtime.close()
    store.close()


def test_paused_project_keeps_due_job_unclaimed_until_resumed(tmp_path):
    enabled = False
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([make_issue("TASK-PAUSED", state="Merged")])
    binding, journal = make_binding(tmp_path, tracker, store)
    binding.dispatch_enabled = lambda: enabled
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
    )
    job = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-PAUSED",
            generation="paused-project-1",
            action="review_refresh",
            idempotency_key="paused-project-job",
        )
    )

    asyncio.run(runtime.start())
    paused_report = asyncio.run(runtime.reconcile_async())
    assert paused_report["projects"]["project-1"]["skipped"] is True
    assert store.get(job.job_id).state is WorkflowJobState.QUEUED

    enabled = True
    resumed_report = asyncio.run(runtime.reconcile_async())
    assert resumed_report["worker"]["processed"] == 1
    assert store.get(job.job_id).state is WorkflowJobState.COMPLETED
    runtime.close()
    store.close()


def test_started_runtime_rejects_live_mode_cutover(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([make_issue("TASK-MODE", state="Done")])
    binding, journal = make_binding(tmp_path, tracker, store)
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="shadow",
    )

    asyncio.run(runtime.start())
    with pytest.raises(WorkflowRuntimeError, match="graceful service restart"):
        runtime.set_mode("enforce")
    assert runtime.mode == "shadow"
    runtime.close()
    store.close()


def test_multi_project_enforce_rejects_unscoped_static_handlers(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker_a = NativeTracker([])
    tracker_b = NativeTracker([])
    binding_a, journal_a = make_binding(
        tmp_path, tracker_a, store, project_id="project-a"
    )
    binding_b, journal_b = make_binding(
        tmp_path, tracker_b, store, project_id="project-b"
    )

    with pytest.raises(WorkflowRuntimeError, match="project-routed"):
        WorkflowRuntime(
            project_bindings={"project-a": binding_a, "project-b": binding_b},
            store=store,
            journals={"project-a": journal_a, "project-b": journal_b},
            mode="enforce",
            handlers=complete_handlers(),
        )

    journal_a.close()
    journal_b.close()
    store.close()


def test_enforce_topology_change_requests_restart_before_claiming(tmp_path):
    class Project:
        def __init__(self, project_id):
            self.id = project_id
            self.repo_path = str(tmp_path)
            self.default_branch = "main"

    projects = [Project("project-a")]

    class ProjectStore:
        def list_all(self):
            return list(projects)

    class Config:
        workflow_engine_mode = "enforce"
        workflow_runtime_decision_limit = 20
        workflow_runtime_batch_size = 4

    restart_requests = []
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    trackers = {
        "project-a": NativeTracker(
            [make_issue("TASK-A", state="Done", project_id="project-a")]
        )
    }

    class OrchestratorDouble:
        project_store = ProjectStore()
        config = Config()
        workflow_job_store = store
        _state_path = str(tmp_path / "service-state.json")

        def _tracker_for_project(self, project_id):
            return trackers[project_id]

        def workflow_action_handler_factory(self, binding):
            return complete_handlers()

        async def graceful_restart(self, *, request_id=None):
            restart_requests.append(request_id)

    runtime = WorkflowRuntime.from_orchestrator(
        OrchestratorDouble(), state_dir=tmp_path
    )
    asyncio.run(runtime.start())
    projects.append(Project("project-b"))

    report = asyncio.run(runtime.reconcile_async())

    assert report["restart_requested"] is True
    assert report["reason"] == "workflow project bindings changed"
    assert len(restart_requests) == 1
    assert store.list_jobs() == ()
    runtime.close()
    store.close()
