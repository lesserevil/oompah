"""Production composition and lifecycle coverage for the durable runtime."""

from __future__ import annotations

import asyncio
from pathlib import Path

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
from oompah.task_transition_service import TaskTransitionService, TransitionJournal
from oompah.terminal_audit_workflow import TerminalAuditWorkflow
from oompah.workflow_facts import FactDomain, WorkflowFactCollector
from oompah.workflow_jobs import WorkflowJobSpec, WorkflowJobState, WorkflowJobStore
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
    assert binding.implementation_controller is not None
    assert binding.review_controller is not None
    assert binding.integration_controller is not None
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
    assert runtime.legacy_lifecycle_writers_enabled is True
    assert runtime.health_snapshot()["worker"]["handlers_configured"] is False
    assert store.list_jobs() == ()
    assert runtime.projections()[0]["task_id"] == "TASK-3"
    runtime.close()
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
            make_issue("A-DONE", state="Done", project_id="project-integration"),
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
        [make_issue("GOOD-DONE", state="Done", project_id="project-good")]
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
    tracker = NativeTracker([make_issue("TASK-PAUSED", state="Done")])
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
