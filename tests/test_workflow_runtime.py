"""Production composition and lifecycle coverage for the durable runtime."""

from __future__ import annotations

import asyncio
import os
import subprocess
import threading
import time
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import oompah.workflow_runtime as workflow_runtime_module

from oompah.epic_workflow import (
    EPIC_ACTIONS,
    EpicFactCollector,
    EpicWorkflowController,
)
from oompah.implementation_workflow import (
    ImplementationAction,
    ImplementationWorkflowController,
)
from oompah.integration import IntegrationRecord
from oompah.integration_workflow import (
    INTEGRATION_ACTIONS,
    IntegrationWorkflowController,
)
from oompah.models import BlockerRef, Issue
from oompah.review_workflow import ReviewWorkflowController
from oompah.terminal_audit import (
    EvidenceFingerprint,
    RequestState,
    TargetState,
    TerminalAuditRecord,
)
from oompah.terminal_audit_metadata import (
    TerminalAuditMetadata,
    TerminalAuditMetadataStore,
)
from oompah.task_transition_service import (
    TaskTransitionService,
    TransitionAuthority,
    TransitionIntent,
    TransitionJournal,
    issue_authority_version,
)
from oompah.terminal_audit_workflow import TerminalAuditWorkflow
from oompah.workflow_facts import FactDomain, LandingState, WorkflowFactCollector
from oompah.workflow_fact_model import LandingFact
from oompah.workflow_controller import UniversalTotalityLivenessController
from oompah.workflow_jobs import (
    ACTIVE_JOB_STATES,
    WorkflowFailureCategory,
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
    _ProjectRoutedHandler,
)
from oompah.workflow_worker import (
    DurableWorkflowWorker,
    EffectObservation,
    EffectResult,
    RevalidationResult,
    VerificationResult,
    WorkflowRunDisposition,
    WorkflowRunResult,
)
from oompah.work_decision import evaluate_task
from oompah.work_decision_projection import (
    operator_actionable_alerts,
    work_decision_alert,
)
from tests.fixtures_workflow_incidents import (
    INCIDENTS_BY_ID,
    materialize_git,
    materialize_native_tracker,
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
        workflow_runtime_max_concurrent = 6
        workflow_runtime_control_reserved_slots = 2
        workflow_quarantine_recycle_seconds = 23

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
    controller = UniversalTotalityLivenessController(store=store)
    persist_liveness = MagicMock()
    orchestrator.workflow_controller = controller
    orchestrator._persist_workflow_liveness_state = persist_liveness
    orchestrator._work_decision_publication_epoch = 1
    orchestrator._publish_work_decisions = MagicMock()

    runtime = WorkflowRuntime.from_orchestrator(orchestrator)

    assert runtime.mode == "shadow"
    assert runtime.decision_limit == 17
    assert runtime.batch_size == 9
    assert runtime.max_concurrent == 6
    assert runtime.control_reserved_slots == 2
    assert runtime.worker.quarantine_recycle_seconds == 23
    assert runtime.worker.quarantine_recycle_observer is not None
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
    assert runtime.liveness_controller is controller
    assert runtime._persist_liveness_state is persist_liveness  # noqa: SLF001
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

    facts = binding.review_controller.collector.collect(
        task.identifier,
        landing_requests=binding.review_controller._landing_request(task),
    )
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


def test_terminal_audit_proof_rejects_metadata_race_until_current_job_exists(
    tmp_path,
):
    from oompah.orchestrator import Orchestrator

    class AuditTracker(NativeTracker):
        def __init__(self, issues):
            super().__init__(issues)
            self.metadata = {}

        def get_metadata(self, identifier):
            return self.metadata.get(identifier, {})

        def set_metadata_field(self, identifier, key, value):
            self.metadata.setdefault(identifier, {})[key] = value

        def invalidate_read_cache(self):
            return None

    class ProjectStore:
        def __init__(self):
            self.lock = threading.RLock()

        def list_all(self):
            return []

        def project_write_lock(self, project_id):
            assert project_id == "legacy"
            return self.lock

    class Config:
        workflow_engine_mode = "shadow"
        workflow_runtime_decision_limit = 17
        workflow_runtime_batch_size = 9

    task = make_issue("TASK-AUDIT-RACE", state="In Validation", project_id="legacy")
    tracker = AuditTracker([task])
    project_store = ProjectStore()
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    workflow = TerminalAuditWorkflow(store)
    metadata = TerminalAuditMetadataStore(tracker, project_store, "legacy")

    class OrchestratorDouble:
        config = Config()
        workflow_job_store = store
        terminal_audit_workflow = workflow
        _state_path = str(tmp_path / "service-state.json")

        def __init__(self):
            self.project_store = project_store
            self.tracker = tracker

        def _audit_store(self, _issue):
            return metadata

        def _workflow_shadow_sources(self, issue):
            return Orchestrator._workflow_shadow_sources(self, issue)

        def _workflow_shadow_running_entry(self, _issue, *, auditor):
            assert auditor
            return None

    record_a = TerminalAuditRecord(
        audit_id="audit-a",
        project_id="legacy",
        task_id=task.identifier,
        target_state=TargetState.DONE,
        evidence_fingerprint=EvidenceFingerprint("a" * 64),
        request_state=RequestState.PENDING,
        source_generation=1,
    )
    record_b = TerminalAuditRecord(
        audit_id="audit-b",
        project_id="legacy",
        task_id=task.identifier,
        target_state=TargetState.DONE,
        evidence_fingerprint=EvidenceFingerprint("b" * 64),
        request_state=RequestState.PENDING,
        source_generation=2,
    )
    metadata.write(
        task.identifier,
        TerminalAuditMetadata(pending_chain=[record_a]),
    )
    workflow.ensure(record_a)
    runtime = WorkflowRuntime.from_orchestrator(
        OrchestratorDouble(), state_dir=tmp_path
    )
    binding = runtime.project_bindings["legacy"]
    proof = binding.terminal_audit_proof_source
    assert proof is not None

    facts_a = binding.collector.collect(task.identifier)
    observed_a = facts_a.fact(FactDomain.TERMINAL_AUDIT).value
    decision_a = evaluate_task(task, facts_a)
    assert isinstance(observed_a, Mapping)
    assert observed_a["audit_id"] == record_a.audit_id
    assert decision_a.durable_jobs == ("terminal_audit",)

    metadata.write(
        task.identifier,
        TerminalAuditMetadata(pending_chain=[record_b]),
    )

    assert not proof(decision_a, observed_a, "terminal_audit")

    facts_b = binding.collector.collect(task.identifier)
    observed_b = facts_b.fact(FactDomain.TERMINAL_AUDIT).value
    decision_b = evaluate_task(task, facts_b)
    assert isinstance(observed_b, Mapping)
    assert observed_b["audit_id"] == record_b.audit_id
    assert decision_b.durable_jobs == ("terminal_audit",)
    assert not proof(decision_b, observed_b, "terminal_audit")

    mismatched_audit = {**observed_b, "audit_id": record_a.audit_id}
    workflow.ensure(record_b)

    assert not proof(decision_b, mismatched_audit, "terminal_audit")
    assert proof(decision_b, observed_b, "terminal_audit")

    runtime.close()
    store.close()


def test_terminal_audit_authority_is_revalidated_before_snapshot_marker(
    tmp_path, monkeypatch
):
    task = make_issue("TASK-AUDIT-FENCE", state="In Validation")
    store = WorkflowJobStore(str(tmp_path / "jobs-fence.sqlite3"))
    tracker = NativeTracker([task])
    binding, journal = make_binding(tmp_path, tracker, store)
    workflow = binding.terminal_audit_workflow
    assert workflow is not None
    record_a = TerminalAuditRecord(
        audit_id="audit-a",
        project_id="project-1",
        task_id=task.identifier,
        target_state=TargetState.DONE,
        evidence_fingerprint=EvidenceFingerprint("a" * 64),
        request_state=RequestState.PENDING,
        source_generation=1,
    )
    record_b = TerminalAuditRecord(
        audit_id="audit-b",
        project_id="project-1",
        task_id=task.identifier,
        target_state=TargetState.DONE,
        evidence_fingerprint=EvidenceFingerprint("b" * 64),
        request_state=RequestState.PENDING,
        source_generation=2,
    )
    workflow.ensure(record_a)
    observed = {
        "phase": "queued",
        "workflow_phase": "queued",
        "audit_job_present": True,
        "audit_id": record_a.audit_id,
        "request_state": record_a.request_state.value,
        "target_state": record_a.target_state.value,
        "evidence_fingerprint": record_a.evidence_fingerprint.digest,
        "source_generation": record_a.source_generation,
        "audit_generation": workflow.generation(record_a),
    }
    binding.collector.sources[FactDomain.TERMINAL_AUDIT] = lambda _issue: observed
    current = [record_a]
    proof_calls = []
    proof_fences = []

    def proof(_decision, value, action):
        proof_fences.append(
            (store._conn.in_transaction, store._authority_lock_depth > 0)
        )
        record = current[0]
        accepted = all(
            value.get(key) == expected
            for key, expected in {
                "audit_id": record.audit_id,
                "target_state": record.target_state.value,
                "evidence_fingerprint": record.evidence_fingerprint.digest,
                "source_generation": record.source_generation,
                "audit_generation": workflow.generation(record),
            }.items()
        ) and store.terminal_audit_lane_materialized(
            project_id="project-1",
            task_id=task.identifier,
            audit_id=record.audit_id,
            target_state=record.target_state.value,
            evidence_fingerprint=record.evidence_fingerprint.digest,
            audit_generation=workflow.generation(record),
            source_generation=record.source_generation,
            obligation_action=action,
        )
        proof_calls.append(accepted)
        if len(proof_calls) == 1:
            # Metadata changes after the scan proof but before publication.
            current[0] = record_b
        return accepted

    binding.terminal_audit_proof_source = proof
    binding.terminal_audit_snapshot_proof_source = (
        lambda _decision, _observed: True
    )
    audit_lock = threading.RLock()
    binding.terminal_audit_publication_lock = lambda: audit_lock
    controller = UniversalTotalityLivenessController(store=store)
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
        liveness_controller=controller,
        **accepted_projection_wiring(),
    )
    publications = []
    original_publish = store.publish_snapshot_generation

    def track_publish(*args, **kwargs):
        publications.append(args[0])
        return original_publish(*args, **kwargs)

    monkeypatch.setattr(store, "publish_snapshot_generation", track_publish)
    asyncio.run(runtime.start())
    report = runtime.reconcile()

    assert proof_calls == [True, False]
    assert proof_fences == [(False, False), (True, True)]
    assert len(publications) == 1
    assert report["projects"]["project-1"]["error"] == "WorkflowRuntimeError"
    runtime.close()
    store.close()


@pytest.mark.parametrize("workflow_phase", ["running", "finalizing"])
def test_active_terminal_audit_proof_shares_store_publication_fence(
    tmp_path, workflow_phase
):
    task = make_issue("TASK-AUDIT-ACTIVE", state="In Validation")
    path = str(tmp_path / f"jobs-active-{workflow_phase}.sqlite3")
    store = WorkflowJobStore(path)
    competing_store = WorkflowJobStore(path)
    tracker = NativeTracker([task])
    binding, journal = make_binding(tmp_path, tracker, store)
    workflow = binding.terminal_audit_workflow
    assert workflow is not None
    record = TerminalAuditRecord(
        audit_id="audit-active",
        project_id="project-1",
        task_id=task.identifier,
        target_state=TargetState.DONE,
        evidence_fingerprint=EvidenceFingerprint("a" * 64),
        request_state=RequestState.IN_PROGRESS,
        source_generation=1,
    )
    workflow.ensure(record)
    running = store.claim_next(
        lease_owner="audit-worker", lease_seconds=30
    )
    assert running is not None
    running = store.checkpoint(
        running.job_id,
        running.lease_token,
        phase=workflow_phase,
        checkpoint={"audit_id": record.audit_id},
    )
    observed = {
        "phase": "active",
        "workflow_phase": workflow_phase,
        "audit_job_present": True,
        "audit_id": record.audit_id,
        "request_state": record.request_state.value,
        "target_state": record.target_state.value,
        "evidence_fingerprint": record.evidence_fingerprint.digest,
        "source_generation": record.source_generation,
        "audit_generation": workflow.generation(record),
        "active_job_id": running.job_id,
        "job_id": running.job_id,
        "actively_working": True,
        "lease_expires_at": datetime.fromtimestamp(
            running.lease_expires_at, tz=timezone.utc
        ).isoformat(),
    }
    binding.collector.sources[FactDomain.TERMINAL_AUDIT] = lambda _issue: observed
    audit_lock = threading.RLock()
    binding.terminal_audit_publication_lock = lambda: audit_lock
    completion_started = threading.Event()
    completion_errors = []
    completion_threads = []
    proof_fences = []

    def complete_concurrently():
        completion_started.set()
        try:
            competing_store.complete(running.job_id, running.lease_token)
        except Exception as exc:  # pragma: no cover - assertion reports detail
            completion_errors.append(exc)

    def proof(_decision, value):
        proof_fences.append(
            (store._conn.in_transaction, store._authority_lock_depth > 0)
        )
        assert value["audit_id"] == record.audit_id
        contender = threading.Thread(target=complete_concurrently)
        completion_threads.append(contender)
        contender.start()
        assert completion_started.wait(timeout=1)
        contender.join(timeout=0.05)
        assert contender.is_alive()
        return store.terminal_audit_lane_materialized(
            project_id="project-1",
            task_id=task.identifier,
            audit_id=record.audit_id,
            target_state=record.target_state.value,
            evidence_fingerprint=record.evidence_fingerprint.digest,
            audit_generation=workflow.generation(record),
            source_generation=record.source_generation,
            obligation_action="terminal_audit",
        )

    binding.terminal_audit_snapshot_proof_source = proof
    controller = UniversalTotalityLivenessController(store=store)
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
        liveness_controller=controller,
        **accepted_projection_wiring(),
    )

    asyncio.run(runtime.start())
    report = runtime.reconcile()
    for contender in completion_threads:
        contender.join(timeout=2)

    assert proof_fences == [(True, True)]
    assert not completion_errors
    assert completion_threads and not completion_threads[0].is_alive()
    assert store.get(running.job_id).state is WorkflowJobState.COMPLETED
    assert report["liveness"]["scan_complete"] is True
    runtime.close()
    competing_store.close()
    store.close()


def test_action_required_terminal_disposition_is_revalidated_at_marker(
    tmp_path
):
    task = make_issue("TASK-AUDIT-ACTION", state="In Validation")
    store = WorkflowJobStore(str(tmp_path / "jobs-action.sqlite3"))
    tracker = NativeTracker([task])
    binding, journal = make_binding(tmp_path, tracker, store)
    observed = {
        "phase": "queued",
        "workflow_phase": "action_required",
        "audit_job_present": True,
        "audit_id": "audit-action",
        "request_state": RequestState.PENDING.value,
        "target_state": TargetState.DONE.value,
        "evidence_fingerprint": "a" * 64,
        "source_generation": 1,
        "audit_generation": "audit:" + "b" * 64,
        "action_required": True,
        "action_code": "audit.action_required",
    }
    binding.collector.sources[FactDomain.TERMINAL_AUDIT] = lambda _issue: observed
    binding.terminal_audit_publication_lock = lambda: threading.RLock()
    proof_fences = []

    def changed_disposition(_decision, value):
        assert value["action_required"] is True
        proof_fences.append(
            (store._conn.in_transaction, store._authority_lock_depth > 0)
        )
        return False

    binding.terminal_audit_snapshot_proof_source = changed_disposition
    controller = UniversalTotalityLivenessController(store=store)
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
        liveness_controller=controller,
        **accepted_projection_wiring(),
    )

    asyncio.run(runtime.start())
    report = runtime.reconcile()

    assert proof_fences == [(True, True)]
    assert report["projects"]["project-1"]["error"] == "WorkflowRuntimeError"
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


async def wait_for_runtime_effects(runtime, *, timeout_seconds=2.0):
    async def wait_until_idle():
        while runtime.health_snapshot()["worker"]["retained"]:
            await asyncio.sleep(0.001)

    await asyncio.wait_for(wait_until_idle(), timeout_seconds)


def accepted_projection_wiring():
    def publisher(*_args, **_kwargs):
        return SimpleNamespace(
            accepted=True,
            rejection=None,
            commit_memory=lambda: None,
            rollback=lambda: None,
        )

    return {
        "projection_publisher": publisher,
        "projection_epoch_source": lambda: 1,
    }


def test_due_batch_reports_saturation_until_claimable_suffix_drains(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([])
    binding, journal = make_binding(tmp_path, tracker, store)

    future = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-FUTURE",
            generation="future-1",
            action="review_refresh",
            idempotency_key="future-job",
        )
    )
    claimed = store.claim_next(
        lease_owner="future-worker",
        lease_seconds=30,
        project_id="project-1",
        actions=("review_refresh",),
    )
    assert claimed is not None and claimed.job_id == future.job_id
    store.fail(
        claimed.job_id,
        claimed.lease_token,
        category=WorkflowFailureCategory.TRANSIENT,
        error="not due yet",
        retryable=True,
        retry_delay_seconds=3_600,
    )

    claimable = tuple(
        store.enqueue(
            WorkflowJobSpec(
                project_id="project-1",
                task_id=f"TASK-{index}",
                generation=f"generation-{index}",
                action="review_refresh",
                idempotency_key=f"claimable-{index}",
            )
        )
        for index in range(3)
    )
    ineligible = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-AUDIT",
            generation="audit-1",
            action="terminal_audit",
            idempotency_key="ineligible-audit",
        )
    )
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
        batch_size=2,
    )

    async def exercise():
        await runtime.start()
        first = await runtime._run_due(("project-1",))
        await wait_for_runtime_effects(runtime)
        second = await runtime._run_due(("project-1",))
        await wait_for_runtime_effects(runtime)
        third = await runtime._run_due(("project-1",))
        await wait_for_runtime_effects(runtime)
        return first, second, third

    first, second, third = asyncio.run(exercise())

    assert first["processed"] == 2
    assert first["batch_saturated"] is True
    assert second["processed"] == 1
    assert second["batch_saturated"] is False
    assert third["processed"] == 0
    assert third["batch_saturated"] is False
    assert all(
        store.get(job.job_id).state is WorkflowJobState.COMPLETED
        for job in claimable
    )
    assert store.get(future.job_id).state is WorkflowJobState.RETRY_WAIT
    assert store.get(ineligible.job_id).state is WorkflowJobState.QUEUED
    runtime.close()
    store.close()


def test_due_batch_preserves_durable_fairness_across_continuations(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    bindings = {}
    journals = {}
    for project_id in ("project-a", "project-b", "project-c"):
        tracker = NativeTracker([])
        binding, journal = make_binding(
            tmp_path, tracker, store, project_id=project_id
        )
        bindings[project_id] = binding
        journals[project_id] = journal
        for index in range(2):
            store.enqueue(
                WorkflowJobSpec(
                    project_id=project_id,
                    task_id=f"{project_id}-{index}",
                    generation=f"generation-{index}",
                    action="review_refresh",
                    idempotency_key=f"{project_id}-{index}",
                )
            )
    runtime = WorkflowRuntime(
        project_bindings=bindings,
        store=store,
        journals=journals,
        mode="enforce",
        handlers=complete_handlers(),
        handler_coverage={
            action: tuple(bindings) for action in complete_handlers()
        },
        batch_size=2,
    )

    async def exercise():
        await runtime.start()
        reports = []
        completed_counts = []
        for _ in range(3):
            reports.append(await runtime._run_due(tuple(bindings)))
            await wait_for_runtime_effects(runtime)
            completed_counts.append(
                {
                    project_id: len(
                        store.list_jobs(
                            project_id=project_id, states=("completed",)
                        )
                    )
                    for project_id in bindings
                }
            )
        return reports, completed_counts

    reports, completed_counts = asyncio.run(exercise())

    assert [report["processed"] for report in reports] == [2, 2, 2]
    assert all(report["batch_saturated"] is True for report in reports)
    assert completed_counts == [
        {"project-a": 1, "project-b": 1, "project-c": 0},
        {"project-a": 2, "project-b": 1, "project-c": 1},
        {"project-a": 2, "project-b": 2, "project-c": 2},
    ]
    runtime.close()
    store.close()


@pytest.mark.timeout(30)
def test_long_delivery_cannot_block_control_jobs_or_projection_generations(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([])
    binding, journal = make_binding(tmp_path, tracker, store)
    delivery_started = asyncio.Event()
    release_delivery = asyncio.Event()
    completed = set()
    completed_events = {
        action: asyncio.Event()
        for action in (
            "standalone_delivery",
            "authority_revocation",
            "validation_submission",
        )
    }

    class BlockingDeliveryHandler(CompleteHandler):
        async def apply(self, context):
            if context.job.action == "standalone_delivery":
                delivery_started.set()
                await release_delivery.wait()
            completed.add(context.job.action)
            completed_events[context.job.action].set()
            return await super().apply(context)

    for task_id, action, priority in (
        ("TASK-DELIVERY", "standalone_delivery", 0),
        ("TASK-REVOKE", "authority_revocation", 0),
        ("TASK-SUBMIT", "validation_submission", 10),
    ):
        store.enqueue(
            WorkflowJobSpec(
                project_id="project-1",
                task_id=task_id,
                generation=f"generation-{task_id}",
                action=action,
                idempotency_key=f"effect-{task_id}",
                priority=priority,
            )
        )

    publications = []

    def publisher(*_args, **kwargs):
        publications.append(kwargs.get("snapshot_generation", _args[1]))
        return SimpleNamespace(
            accepted=True,
            rejection=None,
            commit_memory=lambda: None,
            rollback=lambda: None,
        )

    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(BlockingDeliveryHandler()),
        max_concurrent=2,
        control_reserved_slots=1,
        liveness_controller=UniversalTotalityLivenessController(store=store),
        projection_publisher=publisher,
        projection_epoch_source=lambda: 1,
    )

    async def exercise():
        await runtime.start()
        first = await asyncio.wait_for(runtime.reconcile_async(), 1)
        await asyncio.wait_for(delivery_started.wait(), 1)
        await asyncio.wait_for(
            completed_events["authority_revocation"].wait(),
            10,
        )

        # The long shared-lane delivery remains leased. A second complete
        # controller pass and the reserved submission effect still finish.
        second = await asyncio.wait_for(runtime.reconcile_async(), 1)
        await asyncio.wait_for(
            completed_events["validation_submission"].wait(),
            10,
        )
        delivery = next(
            job
            for job in store.list_jobs(task_id="TASK-DELIVERY")
            if job.action == "standalone_delivery"
        )
        assert delivery.state is WorkflowJobState.RUNNING
        assert len(publications) >= 2
        assert publications[-1] > publications[-2]
        assert first["worker"]["scheduled"] == 2
        assert second["worker"]["scheduled"] == 1

        release_delivery.set()
        await wait_for_runtime_effects(runtime)

    asyncio.run(exercise())

    assert completed == {
        "standalone_delivery",
        "authority_revocation",
        "validation_submission",
    }
    runtime.close()
    store.close()


def test_reserved_lane_and_shared_concurrency_are_hard_bounded(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([])
    binding, journal = make_binding(tmp_path, tracker, store)
    release = asyncio.Event()
    all_started = asyncio.Event()
    active = {"control": 0, "data": 0, "total": 0}
    maximum = dict(active)

    class MeasuringHandler(CompleteHandler):
        async def apply(self, context):
            kind = (
                "control"
                if context.job.action == "authority_revocation"
                else "data"
            )
            active[kind] += 1
            active["total"] += 1
            for key in active:
                maximum[key] = max(maximum[key], active[key])
            if active["total"] == 4:
                all_started.set()
            try:
                await release.wait()
                return await super().apply(context)
            finally:
                active[kind] -= 1
                active["total"] -= 1

    store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="CONTROL",
            generation="control-1",
            action="authority_revocation",
            idempotency_key="control-1",
            priority=100,
        )
    )
    for index in range(5):
        store.enqueue(
            WorkflowJobSpec(
                project_id="project-1",
                task_id=f"DATA-{index}",
                generation=f"data-{index}",
                action="standalone_delivery",
                idempotency_key=f"data-{index}",
                priority=0,
            )
        )
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(MeasuringHandler()),
        batch_size=8,
        max_concurrent=4,
        control_reserved_slots=1,
    )

    async def exercise():
        await runtime.start()
        report = await runtime._run_due(("project-1",))
        await asyncio.wait_for(all_started.wait(), 1)
        assert report["active_lanes"] == {"control": 1, "shared": 3}
        assert runtime.health_snapshot()["worker"]["retained"] == 4
        release.set()
        await wait_for_runtime_effects(runtime)

    asyncio.run(exercise())

    assert maximum == {"control": 1, "data": 3, "total": 4}
    runtime.close()
    store.close()


@pytest.mark.parametrize(
    ("shared_rows", "expected_saturated"),
    ((3, False), (4, True)),
)
def test_due_continues_only_for_claimable_suffix_beyond_concurrency(
    tmp_path, shared_rows, expected_saturated
):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([])
    binding, journal = make_binding(tmp_path, tracker, store)
    release = asyncio.Event()
    all_capacity_started = asyncio.Event()
    active = 0

    class BlockingHandler(CompleteHandler):
        async def apply(self, context):
            nonlocal active
            active += 1
            if active == 4:
                all_capacity_started.set()
            try:
                await release.wait()
                return await super().apply(context)
            finally:
                active -= 1

    store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="CONTROL-SATURATION",
            generation="control-saturation",
            action="authority_revocation",
            idempotency_key="control-saturation",
            priority=100,
        )
    )
    for index in range(shared_rows):
        store.enqueue(
            WorkflowJobSpec(
                project_id="project-1",
                task_id=f"DATA-SATURATION-{index}",
                generation=f"data-saturation-{index}",
                action="standalone_delivery",
                idempotency_key=f"data-saturation-{index}",
                priority=0,
            )
        )
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(BlockingHandler()),
        batch_size=8,
        max_concurrent=4,
        control_reserved_slots=1,
    )

    async def exercise():
        await runtime.start()
        first = await runtime._run_due(("project-1",))
        await asyncio.wait_for(all_capacity_started.wait(), 1)
        while_busy = await runtime._run_due(("project-1",))
        release.set()
        await wait_for_runtime_effects(runtime)
        replenished = await runtime._run_due(("project-1",))
        await wait_for_runtime_effects(runtime)
        return first, while_busy, replenished

    first, while_busy, replenished = asyncio.run(exercise())

    assert first["scheduled"] == 4
    assert first["active_lanes"] == {"control": 1, "shared": 3}
    assert first["batch_saturated"] is expected_saturated
    assert while_busy["scheduled"] == 0
    assert while_busy["batch_saturated"] is False
    assert replenished["scheduled"] == shared_rows - 3
    assert replenished["batch_saturated"] is False
    assert not store.list_jobs(states=("queued", "retry_wait", "running"))
    runtime.close()
    store.close()


def test_fast_admission_drains_multiple_slices_without_world_reconcile(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))

    class CountingTracker(NativeTracker):
        fetch_count = 0

        def fetch_all_issues_enriched(self):
            self.fetch_count += 1
            return super().fetch_all_issues_enriched()

    tracker = CountingTracker([])
    binding, journal = make_binding(tmp_path, tracker, store)
    for index in range(5):
        store.enqueue(
            WorkflowJobSpec(
                project_id="project-1",
                task_id=f"FAST-SLICE-{index}",
                generation=f"fast-slice-{index}",
                action="review_refresh",
                idempotency_key=f"fast-slice-{index}",
            )
        )
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
        batch_size=8,
        max_concurrent=2,
        control_reserved_slots=1,
    )

    async def exercise():
        await runtime.start()
        first = await runtime.reconcile_async()
        await wait_for_runtime_effects(runtime)
        continuations = []
        while store.list_jobs(states=("queued", "retry_wait", "running")):
            continuations.append(await runtime.continue_admission_async())
            await wait_for_runtime_effects(runtime)
        return first, continuations

    first, continuations = asyncio.run(exercise())

    generation = first["projects"]["project-1"]["snapshot"]["generation"]
    assert first["worker"]["scheduled"] == 1
    assert len(continuations) == 4
    assert all(report["admission_only"] is True for report in continuations)
    assert all(report["requires_reconcile"] is False for report in continuations)
    assert all(
        report["snapshot_generation"] == generation
        for report in continuations
    )
    assert tracker.fetch_count == 1
    health = store.health_snapshot()
    assert health["captured_snapshot_generation"] == generation
    assert health["accepted_snapshot_generation"] == generation
    assert health["published_snapshot_generation"] == generation
    assert len(store.list_jobs(states=("completed",))) == 5
    runtime.close()
    store.close()


def test_fast_admission_rejects_stale_snapshot_without_claiming(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([])
    binding, journal = make_binding(tmp_path, tracker, store)
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
    )

    asyncio.run(runtime.start())
    first = asyncio.run(runtime.reconcile_async())
    generation = first["projects"]["project-1"]["snapshot"]["generation"]
    job = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="STALE-FAST-CUT",
            generation="stale-fast-cut",
            action="review_refresh",
            idempotency_key="stale-fast-cut",
        )
    )
    assert store.allocate_snapshot_generation() > generation

    report = asyncio.run(runtime.continue_admission_async())

    assert report["requires_reconcile"] is True
    assert report["reason"] == "workflow admission cut is stale"
    assert store.get(job.job_id).state is WorkflowJobState.QUEUED
    runtime.close()
    store.close()


def test_fast_admission_requests_one_world_scan_after_queue_drains(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([])
    binding, journal = make_binding(tmp_path, tracker, store)
    store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="FINAL-FAST-SLICE",
            generation="final-fast-slice",
            action="review_refresh",
            idempotency_key="final-fast-slice",
        )
    )
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
        max_concurrent=2,
        control_reserved_slots=1,
    )

    async def exercise():
        completion_published = asyncio.Event()
        runtime._effect_completion_observer = (
            lambda _result: completion_published.set()
        )
        await runtime.start()
        first = await runtime.reconcile_async()
        await asyncio.wait_for(completion_published.wait(), 1)
        final = await runtime.continue_admission_async()
        return first, final

    first, final = asyncio.run(exercise())

    assert first["worker"]["scheduled"] == 1
    assert final["worker"]["completed"] == 1
    assert final["worker"]["scheduled"] == 0
    assert final["worker"]["active"] == 0
    assert final["requires_reconcile"] is True
    assert final["reconcile_reason"] == "published_queue_drained"
    runtime.close()
    store.close()


def test_done_effect_remains_retained_until_completion_callback_settles(tmp_path):
    """A done Task cannot open a close/drain gap before callback settlement."""

    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([])
    binding, journal = make_binding(tmp_path, tracker, store)
    effect_entered = threading.Event()
    release_effect = threading.Event()

    class FencedHandler(CompleteHandler):
        async def apply(self, context):
            effect_entered.set()
            assert await asyncio.to_thread(release_effect.wait, 2)
            return await super().apply(context)

    store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="CALLBACK-PENDING",
            generation="callback-pending",
            action="review_refresh",
            idempotency_key="callback-pending",
        )
    )
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(FencedHandler()),
    )
    callback_entered = threading.Event()
    release_callback = threading.Event()
    drain_entered = threading.Event()
    original_effect_finished = runtime._effect_finished
    original_worker_drain = runtime.worker.drain
    completed_task = None

    def fenced_effect_finished(task):
        nonlocal completed_task
        completed_task = task
        callback_entered.set()
        assert release_callback.wait(2), "effect callback barrier timed out"
        original_effect_finished(task)

    runtime._effect_finished = fenced_effect_finished

    async def observed_worker_drain(*, timeout_seconds=None):
        drain_entered.set()
        return await original_worker_drain(timeout_seconds=timeout_seconds)

    runtime.worker.drain = observed_worker_drain

    async def exercise():
        await runtime.start()
        report = await runtime.reconcile_async()
        drained = await runtime.drain(timeout_seconds=2)
        return report, drained

    with ThreadPoolExecutor(max_workers=1) as executor:
        run = executor.submit(asyncio.run, exercise())
        try:
            assert effect_entered.wait(2), "workflow effect never entered"
            assert drain_entered.wait(2), "runtime drain never entered"
            release_effect.set()
            assert callback_entered.wait(2), "effect callback never entered"
            assert completed_task is not None and completed_task.done()
            assert run.done() is False
            assert runtime.health_snapshot()["worker"]["retained"] == 1
            assert runtime.pending_operation_count == 1
            with pytest.raises(
                WorkflowRuntimeError,
                match="cannot close workflow runtime while 1 operation",
            ):
                runtime.close()
        finally:
            release_effect.set()
            release_callback.set()
        report, drained = run.result(timeout=2)

    assert report["worker"]["scheduled"] == 1
    assert drained is True
    assert runtime.health_snapshot()["worker"]["retained"] == 0
    assert runtime.pending_operation_count == 0
    assert len(runtime._effect_results) == 1
    original_effect_finished(completed_task)
    assert len(runtime._effect_results) == 1
    runtime.close()
    store.close()


@pytest.mark.parametrize("settles_during_admission", (False, True))
def test_fast_admission_cannot_observe_idle_before_callback_settlement(
    tmp_path, settles_during_admission
):
    """A ready continuation cannot pass a completed callback in the same loop."""

    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([])
    binding, journal = make_binding(tmp_path, tracker, store)
    effect_entered = asyncio.Event()
    release_effect = asyncio.Event()
    continuation_waiting = asyncio.Event()

    store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="CALLBACK-GAP-ADMISSION",
            generation="callback-gap-admission",
            action="review_refresh",
            idempotency_key="callback-gap-admission",
        )
    )
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
        max_concurrent=4 if settles_during_admission else 2,
        control_reserved_slots=1,
    )

    async def execute_immediately_after_release(job):
        effect_entered.set()
        await release_effect.wait()
        completed = store.complete(job.job_id, str(job.lease_token or ""))
        return WorkflowRunResult(
            WorkflowRunDisposition.COMPLETED,
            completed.job_id,
            completed.state,
            "completed in callback-gap proof",
            completed.attempts,
        )

    runtime.worker.execute_claimed = execute_immediately_after_release

    async def no_yield_claim(**_kwargs):
        return None

    async def continue_after_release():
        continuation_waiting.set()
        await release_effect.wait()
        retained_task = next(iter(runtime._effect_tasks))
        assert retained_task.done()
        assert not runtime._effect_results
        return await runtime.continue_admission_async()

    async def exercise():
        completion_published = asyncio.Event()
        runtime._effect_completion_observer = (
            lambda _result: completion_published.set()
        )
        await runtime.start()
        first = await runtime.reconcile_async()
        await asyncio.wait_for(effect_entered.wait(), 1)
        if not settles_during_admission:
            runtime.worker.claim_next = no_yield_claim
        continuation = asyncio.create_task(continue_after_release())
        await asyncio.wait_for(continuation_waiting.wait(), 1)
        release_effect.set()
        gap = await asyncio.wait_for(continuation, 1)
        await asyncio.wait_for(completion_published.wait(), 1)
        settled = await runtime.continue_admission_async()
        return first, gap, settled

    first, gap, settled = asyncio.run(exercise())

    assert first["worker"]["scheduled"] == 1
    assert gap["worker"]["completed"] == int(settles_during_admission)
    assert gap["worker"]["scheduled"] == 0
    assert gap["worker"]["active"] == int(not settles_during_admission)
    assert gap["worker"]["active_lanes"] == {
        "control": 0,
        "shared": int(not settles_during_admission),
    }
    assert gap["requires_reconcile"] is settles_during_admission
    assert settled["worker"]["completed"] == int(not settles_during_admission)
    assert settled["worker"]["active"] == 0
    assert settled["requires_reconcile"] is (not settles_during_admission)
    if settles_during_admission:
        assert gap["reconcile_reason"] == "published_queue_drained"
    else:
        assert settled["reconcile_reason"] == "published_queue_drained"
    runtime.close()
    store.close()


def test_fast_admission_rechecks_project_pause_before_claiming(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([])
    binding, journal = make_binding(tmp_path, tracker, store)
    enabled = True
    binding.dispatch_enabled = lambda: enabled
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
    )

    asyncio.run(runtime.start())
    asyncio.run(runtime.reconcile_async())
    job = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="PAUSED-FAST-CUT",
            generation="paused-fast-cut",
            action="review_refresh",
            idempotency_key="paused-fast-cut",
        )
    )
    enabled = False

    report = asyncio.run(runtime.continue_admission_async())

    assert report["requires_reconcile"] is True
    assert report["reason"] == "workflow project admission changed"
    assert store.get(job.job_id).state is WorkflowJobState.QUEUED
    runtime.close()
    store.close()


def test_concurrent_due_callers_cannot_spend_the_same_lane_reservation(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([])
    binding, journal = make_binding(tmp_path, tracker, store)
    release_effects = asyncio.Event()
    four_started = asyncio.Event()
    active = 0

    class BlockingHandler(CompleteHandler):
        async def apply(self, context):
            nonlocal active
            active += 1
            if active == 4:
                four_started.set()
            try:
                await release_effects.wait()
                return await super().apply(context)
            finally:
                active -= 1

    for index in range(4):
        store.enqueue(
            WorkflowJobSpec(
                project_id="project-1",
                task_id=f"CONTROL-RACE-{index}",
                generation=f"control-race-{index}",
                action="authority_revocation",
                idempotency_key=f"control-race-{index}",
                priority=100,
            )
        )
    for index in range(8):
        store.enqueue(
            WorkflowJobSpec(
                project_id="project-1",
                task_id=f"DATA-RACE-{index}",
                generation=f"data-race-{index}",
                action="standalone_delivery",
                idempotency_key=f"data-race-{index}",
                priority=0,
            )
        )
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(BlockingHandler()),
        batch_size=8,
        max_concurrent=4,
        control_reserved_slots=1,
    )
    first_claim_entered = asyncio.Event()
    release_claims = asyncio.Event()
    claim_calls = 0
    original_claim = runtime.worker.claim_next

    async def delayed_claim(**kwargs):
        nonlocal claim_calls
        claim_calls += 1
        first_claim_entered.set()
        await release_claims.wait()
        return await original_claim(**kwargs)

    runtime.worker.claim_next = delayed_claim

    async def exercise():
        await runtime.start()
        first = asyncio.create_task(runtime._run_due(("project-1",)))
        await asyncio.wait_for(first_claim_entered.wait(), 1)
        second = asyncio.create_task(runtime._run_due(("project-1",)))
        # The first caller is suspended inside claim_next. The second caller
        # must remain outside admission instead of observing the same slots.
        await asyncio.sleep(0)
        assert claim_calls == 1
        release_claims.set()
        reports = await asyncio.wait_for(asyncio.gather(first, second), 1)
        await asyncio.wait_for(four_started.wait(), 1)

        assert sum(report["scheduled"] for report in reports) == 4
        assert runtime.health_snapshot()["worker"]["retained"] == 4
        assert reports[-1]["active_lanes"] == {"control": 1, "shared": 3}

        release_effects.set()
        await wait_for_runtime_effects(runtime)

    asyncio.run(exercise())

    runtime.close()
    store.close()


def test_concurrent_runtime_keeps_same_task_effects_serialized(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([])
    binding, journal = make_binding(tmp_path, tracker, store)
    release_first = asyncio.Event()
    first_started = asyncio.Event()
    observed = []

    class SerialHandler(CompleteHandler):
        async def apply(self, context):
            observed.append(context.job.action)
            if context.job.action == "authority_revocation":
                first_started.set()
                await release_first.wait()
            return await super().apply(context)

    for action in ("authority_revocation", "standalone_delivery"):
        store.enqueue(
            WorkflowJobSpec(
                project_id="project-1",
                task_id="TASK-SAME",
                generation=f"generation-{action}",
                action=action,
                idempotency_key=f"same-{action}",
                priority=0,
            )
        )
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(SerialHandler()),
        max_concurrent=4,
        control_reserved_slots=1,
    )

    async def exercise():
        await runtime.start()
        report = await runtime._run_due(("project-1",))
        await asyncio.wait_for(first_started.wait(), 1)
        assert report["scheduled"] == 1
        assert observed == ["authority_revocation"]
        queued = store.list_jobs(task_id="TASK-SAME", states=("queued",))
        assert [job.action for job in queued] == ["standalone_delivery"]
        release_first.set()
        await wait_for_runtime_effects(runtime)
        follow_up = await runtime._run_due(("project-1",))
        assert follow_up["scheduled"] == 1
        await wait_for_runtime_effects(runtime)

    asyncio.run(exercise())

    assert observed == ["authority_revocation", "standalone_delivery"]
    runtime.close()
    store.close()


def test_detached_effect_heartbeats_and_drains_without_duplicate_apply(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([])
    binding, journal = make_binding(tmp_path, tracker, store)
    started = asyncio.Event()
    release = asyncio.Event()
    apply_calls = 0

    class LeaseHandler(CompleteHandler):
        async def apply(self, context):
            nonlocal apply_calls
            apply_calls += 1
            started.set()
            await release.wait()
            return await super().apply(context)

    handler = LeaseHandler()
    worker = DurableWorkflowWorker(
        store=store,
        handlers=complete_handlers(handler),
        transition_services={"project-1": binding.transition_service},
        worker_id="detached-heartbeat-worker",
        lease_seconds=0.15,
        heartbeat_seconds=0.03,
        operation_timeout_seconds=2,
    )
    queued = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-LEASE",
            generation="lease-1",
            action="standalone_delivery",
            idempotency_key="lease-1",
        )
    )
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(handler),
        worker=worker,
        max_concurrent=2,
        control_reserved_slots=1,
    )

    async def exercise():
        await runtime.start()
        report = await runtime._run_due(("project-1",))
        assert report["scheduled"] == 1
        await asyncio.wait_for(started.wait(), 1)
        await asyncio.sleep(0.22)
        live = store.get(queued.job_id)
        assert live.state is WorkflowJobState.RUNNING
        assert live.lease_expires_at is not None
        assert live.lease_expires_at > time.time()
        assert await runtime.drain(timeout_seconds=0.02) is False
        release.set()
        assert await runtime.drain(timeout_seconds=1) is True

    asyncio.run(exercise())

    assert apply_calls == 1
    assert store.get(queued.job_id).state is WorkflowJobState.COMPLETED
    assert store.list_jobs(task_id="TASK-LEASE", states=("queued", "retry_wait")) == ()
    runtime.close()
    store.close()


def test_claim_execution_gap_recovers_after_restart_without_lost_effect(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([])
    binding, journal = make_binding(tmp_path, tracker, store)
    apply_calls = 0

    class CountingHandler(CompleteHandler):
        async def apply(self, context):
            nonlocal apply_calls
            apply_calls += 1
            return await super().apply(context)

    abandoned_owner = "workflow-runtime:999999:deadbeef"
    first_worker = DurableWorkflowWorker(
        store=store,
        handlers=complete_handlers(CountingHandler()),
        transition_services={"project-1": binding.transition_service},
        worker_id=abandoned_owner,
    )
    queued = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-CLAIM-GAP",
            generation="claim-gap-1",
            action="standalone_delivery",
            idempotency_key="claim-gap-1",
        )
    )
    claimed = asyncio.run(
        first_worker.claim_next(
            project_ids=("project-1",), actions=("standalone_delivery",)
        )
    )
    assert claimed is not None
    assert store.get(queued.job_id).state is WorkflowJobState.RUNNING

    handler = CountingHandler()
    restarted = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(handler),
        abandoned_lease_owners=(abandoned_owner,),
        max_concurrent=2,
        control_reserved_slots=1,
    )

    async def recover_and_execute():
        recovery = await restarted.start()
        assert recovery["abandoned"] == 1
        report = await restarted._run_due(("project-1",))
        assert report["scheduled"] == 1
        await wait_for_runtime_effects(restarted)

    asyncio.run(recover_and_execute())

    assert apply_calls == 1
    assert store.get(queued.job_id).state is WorkflowJobState.COMPLETED
    restarted.close()
    store.close()


def test_runtime_owner_identity_fences_reused_pid_generation(monkeypatch):
    current_pid = os.getpid()
    monkeypatch.setattr(
        workflow_runtime_module,
        "_process_start_ticks",
        lambda pid: 9001 if pid in {123, current_pid} else None,
    )

    assert WorkflowRuntime._runtime_owner_is_dead(
        "workflow-runtime:123:8999:deadbeef"
    )
    assert not WorkflowRuntime._runtime_owner_is_dead(
        "workflow-runtime:123:9001:deadbeef"
    )
    assert not WorkflowRuntime._runtime_owner_is_dead(
        "workflow-runtime:123:deadbeef"
    )
    assert not WorkflowRuntime._runtime_owner_is_dead("another-owner")
    current_ticks = workflow_runtime_module._process_start_ticks(current_pid)
    if current_ticks is not None:
        assert WorkflowRuntime._runtime_owner_is_dead(
            f"workflow-runtime:{current_pid}:{current_ticks}:"
            f"p{'f' * 32}:deadbeef"
        )
        assert not WorkflowRuntime._runtime_owner_is_dead(
            f"workflow-runtime:{current_pid}:{current_ticks}:"
            f"p{workflow_runtime_module._RUNTIME_PROCESS_GENERATION}:deadbeef"
        )


def test_quarantine_recovers_after_same_pid_exec_without_duplicate_apply(
    tmp_path,
):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([])
    binding, journal = make_binding(tmp_path, tracker, store)
    process_ticks = workflow_runtime_module._process_start_ticks(os.getpid())
    assert process_ticks is not None
    current_generation = workflow_runtime_module._RUNTIME_PROCESS_GENERATION
    previous_generation = (
        "0" * 32 if current_generation != "0" * 32 else "1" * 32
    )
    old_owner = (
        f"workflow-runtime:{os.getpid()}:{process_ticks}:"
        f"p{previous_generation}:deadbeef"
    )
    first_worker = DurableWorkflowWorker(
        store=store,
        handlers=complete_handlers(),
        transition_services={"project-1": binding.transition_service},
        worker_id=old_owner,
    )
    queued = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-QUARANTINE-EXEC",
            generation="quarantine-exec-1",
            action="standalone_delivery",
            idempotency_key="quarantine-exec-1",
        )
    )
    claimed = asyncio.run(
        first_worker.claim_next(
            project_ids=("project-1",), actions=("standalone_delivery",)
        )
    )
    assert claimed is not None
    quarantined = store.quarantine_owned(
        claimed.job_id,
        claimed.lease_token,
        category=WorkflowFailureCategory.TIMEOUT,
        error="synchronous adapter did not return",
    )
    store.mark_quarantine_recycle_requested(
        quarantined.job_id,
        quarantined.lease_token,
    )

    class ObservingHandler(CompleteHandler):
        def __init__(self):
            self.apply_calls = 0

        async def inspect(self, context):
            return EffectObservation(True, {"accepted": True})

        async def apply(self, context):
            self.apply_calls += 1
            return await super().apply(context)

    handler = ObservingHandler()
    restarted = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(handler),
        max_concurrent=2,
        control_reserved_slots=1,
    )

    async def recover_and_execute():
        recovery = await restarted.start()
        assert recovery == {"expired": 0, "abandoned": 1, "recovered": 1}
        report = await restarted._run_due(("project-1",))
        assert report["scheduled"] == 1
        await wait_for_runtime_effects(restarted)

    asyncio.run(recover_and_execute())

    assert handler.apply_calls == 0
    assert store.get(queued.job_id).state is WorkflowJobState.COMPLETED
    restarted.close()
    store.close()


@pytest.mark.parametrize("same_worker_identity", (True, False))
def test_live_same_process_quarantine_marker_never_proves_abandonment(
    tmp_path,
    same_worker_identity,
):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([])
    binding, journal = make_binding(tmp_path, tracker, store)
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
        max_concurrent=2,
        control_reserved_slots=1,
    )
    if same_worker_identity:
        live_owner = runtime.worker.worker_id
    else:
        process_ticks = workflow_runtime_module._process_start_ticks(os.getpid())
        assert process_ticks is not None
        live_owner = (
            f"workflow-runtime:{os.getpid()}:{process_ticks}:"
            f"p{workflow_runtime_module._RUNTIME_PROCESS_GENERATION}:feedface"
        )
    queued = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-LIVE-QUARANTINE",
            generation="live-quarantine-1",
            action="standalone_delivery",
            idempotency_key="live-quarantine-1",
        )
    )
    claimed = store.claim_next(
        lease_owner=live_owner,
        lease_seconds=30,
        actions=("standalone_delivery",),
    )
    assert claimed is not None
    quarantined = store.quarantine_owned(
        claimed.job_id,
        claimed.lease_token,
        category=WorkflowFailureCategory.TIMEOUT,
        error="live adapter is still running",
    )
    store.mark_quarantine_recycle_requested(
        quarantined.job_id,
        quarantined.lease_token,
    )

    recovery = asyncio.run(runtime.start())

    assert recovery == {"expired": 0, "abandoned": 0, "recovered": 0}
    retained = store.get(queued.job_id)
    assert retained.state is WorkflowJobState.RUNNING
    assert retained.phase == "quarantined"
    runtime.close()
    store.close()


def test_runtime_rejects_liveness_without_canonical_projection_publisher(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([])
    binding, journal = make_binding(tmp_path, tracker, store)
    controller = UniversalTotalityLivenessController(store=store)

    with pytest.raises(ValueError, match="canonical projection publication"):
        WorkflowRuntime(
            project_bindings={"project-1": binding},
            store=store,
            journals={"project-1": journal},
            mode="enforce",
            handlers=complete_handlers(),
            liveness_controller=controller,
        )

    journal.close()
    store.close()


def test_runtime_binds_owner_deadlines_and_jobs_to_one_live_policy_cut(
    tmp_path, monkeypatch
):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    task = make_issue("TASK-POLICY-EPOCH", state="In Review")
    tracker = NativeTracker([task])
    binding, journal = make_binding(tmp_path, tracker, store)
    controller = UniversalTotalityLivenessController(
        store=store,
        liveness_slo_seconds={"review_reassessment": 61},
    )
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
        liveness_controller=controller,
        **accepted_projection_wiring(),
    )
    expected_epoch = controller.liveness_policy.epoch

    assert controller.scheduler.policy_epoch == expected_epoch
    assert all(
        domain.scheduler.policy_epoch == expected_epoch
        for domain in (
            binding.implementation_controller,
            binding.review_controller,
            binding.integration_controller,
            binding.epic_controller,
        )
    )

    asyncio.run(runtime.start())
    runtime.reconcile()
    first_item = binding.review_controller._latest[task.identifier]
    first_deadline = datetime.fromisoformat(
        first_item.decision.next_reassessment_at
    )
    first_collected = datetime.fromisoformat(first_item.facts.collected_at)
    assert (first_deadline - first_collected).total_seconds() == 61
    first_cursor = store.schedule_cursor(
        project_id="project-1", task_id=task.identifier
    )
    assert first_cursor is not None
    assert first_cursor.decision_revision == (
        binding.review_controller.scheduler.decision_revision(
            first_item.decision
        )
    )
    assert first_cursor.job_generation.endswith(
        f":reassess={first_deadline.timestamp():.6f}"
    )
    review_job = next(
        job
        for job in store.list_jobs(task_id=task.identifier)
        if job.action in {"review_refresh", "review_monitor"}
    )
    running = store.claim_next(
        lease_owner="failed-review", lease_seconds=30,
        task_id=task.identifier,
        actions=(review_job.action,),
    )
    assert running is not None
    store.fail(
        running.job_id,
        running.lease_token,
        category=WorkflowFailureCategory.PERMANENT,
        error="permanent review failure",
        retryable=False,
    )
    facts = binding.review_controller.collector.collect(
        task.identifier,
        landing_requests=binding.review_controller._landing_request(task),
    )
    exhausted = controller.evaluate(
        (task,), facts={task.identifier: facts}
    )[0]

    assert exhausted.reason_code == "retry.exhausted"
    original_evaluate = binding.review_controller.evaluate

    def evaluate_then_reload(tasks, **kwargs):
        batch = original_evaluate(tasks, **kwargs)
        controller.reconfigure_liveness(
            max_task_records=controller.liveness.max_task_records,
            max_project_records=controller.liveness.max_project_records,
            snapshot_stale_seconds=(
                controller.liveness.snapshot_stale_seconds
            ),
            slo_seconds={"review_reassessment": 62},
        )
        return batch

    monkeypatch.setattr(
        binding.review_controller, "evaluate", evaluate_then_reload
    )
    rejected = runtime.reconcile()
    monkeypatch.setattr(
        binding.review_controller, "evaluate", original_evaluate
    )
    reloaded_epoch = controller.liveness_policy.epoch
    assert reloaded_epoch != expected_epoch
    assert rejected["projects"]["project-1"]["review"][
        "snapshot_accepted"
    ] is False
    assert store.schedule_cursor(
        project_id="project-1", task_id=task.identifier
    ) == first_cursor
    assert binding.review_controller._latest[
        task.identifier
    ].decision.next_reassessment_at == first_item.decision.next_reassessment_at
    assert runtime.projections()[0]["next_reassessment_at"] == (
        first_item.decision.next_reassessment_at
    )
    assert [
        domain.scheduler.policy_epoch
        for domain in (
            binding.implementation_controller,
            binding.review_controller,
            binding.integration_controller,
            binding.epic_controller,
        )
    ] == [reloaded_epoch] * 4

    runtime.reconcile()

    assert controller.scheduler.policy_epoch == reloaded_epoch
    assert all(
        domain.scheduler.policy_epoch == reloaded_epoch
        for domain in (
            binding.implementation_controller,
            binding.review_controller,
            binding.integration_controller,
            binding.epic_controller,
        )
    )
    second_item = binding.review_controller._latest[task.identifier]
    second_deadline = datetime.fromisoformat(
        second_item.decision.next_reassessment_at
    )
    second_collected = datetime.fromisoformat(second_item.facts.collected_at)
    assert (second_deadline - second_collected).total_seconds() == 62
    second_cursor = store.schedule_cursor(
        project_id="project-1", task_id=task.identifier
    )
    assert second_cursor is not None
    assert second_cursor.decision_revision != first_cursor.decision_revision
    assert second_cursor.job_generation.endswith(
        f":reassess={second_deadline.timestamp():.6f}"
    )
    assert runtime.projections()[0]["next_reassessment_at"] == (
        second_item.decision.next_reassessment_at
    )
    runtime.close()
    store.close()


def test_runtime_current_exhaustion_overrides_normal_owner_retry_projection(
    tmp_path,
):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    task = make_issue("TASK-LANDING-EXHAUSTED", state="Ready to Integrate")
    task.integration = IntegrationRecord(
        state="integrated",
        mode="queue",
        task_branch=task.identifier,
        base_branch="main",
        head_sha="a" * 40,
        integrated_sha="a" * 40,
    )
    tracker = NativeTracker([task])
    binding, journal = make_binding(tmp_path, tracker, store)
    controller = UniversalTotalityLivenessController(store=store)
    publications = []

    def publisher(decisions, generation, **_kwargs):
        publications.append((tuple(decisions), generation))
        return SimpleNamespace(
            accepted=True,
            rejection=None,
            commit_memory=lambda: None,
            rollback=lambda: None,
        )

    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
        liveness_controller=controller,
        projection_publisher=publisher,
        projection_epoch_source=lambda: 1,
    )

    asyncio.run(runtime.start())
    runtime.reconcile()
    first_domain = binding.integration_controller._latest[task.identifier].decision
    assert first_domain.reason_code == "integration.landing_unproven"
    assert first_domain.durable_jobs == ("integration_landing_refresh",)
    landing_refresh = next(
        job
        for job in store.list_jobs(task_id=task.identifier)
        if job.action == "integration_landing_refresh"
    )
    running = store.claim_next(
        lease_owner="failed-integration",
        lease_seconds=30,
        task_id=task.identifier,
        actions=("integration_landing_refresh",),
    )
    assert running is not None
    assert running.job_id == landing_refresh.job_id
    store.fail(
        running.job_id,
        running.lease_token,
        category=WorkflowFailureCategory.PERMANENT,
        error="landing refresh exhausted",
        retryable=False,
    )
    assert store.health_snapshot()["current_states"]["exhausted"] == 1

    # Change semantic evidence while the owning integration controller still
    # reaches the ordinary informational retry decision.  This was the live
    # revision-drift path that hid the durable exhaustion from the API.
    binding.collector.sources[FactDomain.CONFIG] = lambda _issue: {"version": 2}
    runtime.reconcile()

    owner_decision = binding.integration_controller._latest[
        task.identifier
    ].decision
    assert owner_decision.reason_code == "integration.landing_unproven"
    assert not owner_decision.action_required
    projection = next(
        item
        for item in runtime.projections()
        if item["task_id"] == task.identifier
    )
    assert projection["reason_code"] == "retry.exhausted"
    assert projection["disposition"] == "action_required"
    assert projection["action_required"] is True
    assert projection["alert_level"] == "critical"
    published_decision = next(
        decision
        for decision in publications[-1][0]
        if decision.task_id == task.identifier
    )
    assert published_decision.reason_code == "retry.exhausted"
    assert published_decision.action_required
    alert = work_decision_alert(published_decision)
    assert alert is not None
    assert operator_actionable_alerts((alert,)) == [alert]
    assert alert["task_id"] == task.identifier
    assert alert["reason_code"] == "retry.exhausted"
    runtime.close()
    store.close()


def test_runtime_epic_facts_prevent_stale_generic_exhaustion_override(tmp_path):
    scenario = INCIDENTS_BY_ID["OOMPAH-748"]
    replay = materialize_native_tracker(tmp_path, scenario)
    git = materialize_git(tmp_path, scenario)
    task_id = replay.identifiers["child"]
    epic = replay.tracker.fetch_issue_detail(task_id)
    assert epic is not None and epic.parent_id
    source = f"epic-{epic.identifier}"
    target = f"epic-{epic.parent_id}"
    revision = git.commits["child-head"]
    subprocess.run(
        [
            "git",
            "update-ref",
            f"refs/heads/{target}",
            git.commits["child-on-parent"],
        ],
        cwd=git.path,
        check=True,
    )
    replay.tracker.set_metadata_field(
        task_id,
        "oompah.integration",
        IntegrationRecord(
            state="integrated",
            mode="queue",
            task_branch=source,
            base_branch=target,
            head_sha=revision,
            integrated_sha=revision,
        ).to_dict(),
    )
    replay.tracker.set_metadata_field(task_id, "oompah.work_branch", source)
    replay.tracker.set_metadata_field(task_id, "oompah.target_branch", target)

    project_id = "historical-incidents"
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    binding, journal = make_binding(
        tmp_path,
        replay.tracker,
        store,
        project_id=project_id,
    )
    epic_collector = EpicFactCollector(
        project_id=project_id,
        tracker=replay.tracker,
        repo_path=str(git.path),
        sources=binding.collector.sources,
    )
    binding.epic_collector = epic_collector
    binding.epic_controller = EpicWorkflowController(
        collector=epic_collector,
        store=store,
    )
    generic = evaluate_task(epic, binding.collector.collect(task_id))
    # The generic collector intentionally lacks the exact containment branch
    # authority required by the epic decision path. Runtime composition below
    # replaces this malformed snapshot with the epic collector's canonical
    # facts before publishing liveness.
    assert generic.reason_code == "evidence.containment_malformed"
    assert generic.durable_jobs == ("epic_terminal_validation",)
    stale = store.enqueue(
        WorkflowJobSpec(
            project_id=project_id,
            task_id=task_id,
            generation=generic.decision_revision,
            action="epic_terminal_validation",
            idempotency_key="stale-generic-terminal-validation",
        )
    )
    running = store.claim_next(
        lease_owner="failed-generic-validation",
        lease_seconds=30,
        task_id=task_id,
        actions=("epic_terminal_validation",),
    )
    assert running is not None and running.job_id == stale.job_id
    store.fail(
        running.job_id,
        running.lease_token,
        category=WorkflowFailureCategory.PERMANENT,
        error="stale generic containment exhausted",
        retryable=False,
    )

    publications = []

    def publisher(decisions, generation, **_kwargs):
        publications.append((tuple(decisions), generation))
        return SimpleNamespace(
            accepted=True,
            rejection=None,
            commit_memory=lambda: None,
            rollback=lambda: None,
        )

    runtime = WorkflowRuntime(
        project_bindings={project_id: binding},
        store=store,
        journals={project_id: journal},
        mode="enforce",
        handlers=complete_handlers(),
        liveness_controller=UniversalTotalityLivenessController(store=store),
        projection_publisher=publisher,
        projection_epoch_source=lambda: 1,
    )

    asyncio.run(runtime.start())
    report = asyncio.run(runtime.reconcile_async())

    projection = next(
        item for item in runtime.projections() if item["task_id"] == task_id
    )
    published = next(
        decision for decision in publications[-1][0] if decision.task_id == task_id
    )
    owner = binding.epic_controller._latest[task_id].decision
    assert report["projects"][project_id]["epic"]["decisions_seen"] == 2
    assert owner.reason_code == "terminal.immediate_target_landing_proven"
    assert projection["reason_code"] == owner.reason_code
    assert published.reason_code == owner.reason_code
    assert not projection["action_required"]
    assert store.get(stale.job_id).state is WorkflowJobState.EXHAUSTED
    runtime.close()
    store.close()


def test_shadow_owner_projection_uses_configured_liveness_policy(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    task = make_issue("TASK-SHADOW-POLICY", state="In Review")
    binding, journal = make_binding(tmp_path, NativeTracker([task]), store)
    controller = UniversalTotalityLivenessController(
        store=store,
        liveness_slo_seconds={"review_reassessment": 61},
    )
    captured = []
    original_evaluate = binding.review_controller.evaluate

    def capture_review_batch(tasks, **kwargs):
        batch = original_evaluate(tasks, **kwargs)
        captured.append(batch)
        return batch

    binding.review_controller.evaluate = capture_review_batch
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="shadow",
        liveness_controller=controller,
        **accepted_projection_wiring(),
    )

    asyncio.run(runtime.start())
    runtime.reconcile()

    item = captured[0].tasks[0]
    deadline = datetime.fromisoformat(item.decision.next_reassessment_at)
    collected = datetime.fromisoformat(item.facts.collected_at)
    assert (deadline - collected).total_seconds() == 61
    assert runtime.projections()[0]["next_reassessment_at"] == (
        item.decision.next_reassessment_at
    )
    runtime.close()
    store.close()


def test_runtime_injects_policy_seconds_into_every_owner_controller(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tasks = [
        make_issue("TASK-OPEN-POLICY", state="Open"),
        make_issue("TASK-REVIEW-POLICY", state="In Review"),
        make_issue("TASK-INTEGRATION-POLICY", state="Ready to Integrate"),
        make_issue(
            "EPIC-ROLLUP-POLICY",
            state="Decomposed",
            issue_type="epic",
        ),
    ]
    binding, journal = make_binding(tmp_path, NativeTracker(tasks), store)
    controller = UniversalTotalityLivenessController(
        store=store,
        liveness_slo_seconds={
            "dispatch_latency": 41,
            "review_reassessment": 42,
            "integration_lease": 43,
            "rollup_reassessment": 44,
        },
    )
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
        liveness_controller=controller,
        **accepted_projection_wiring(),
    )

    asyncio.run(runtime.start())
    runtime.reconcile()

    owner_items = (
        (
            binding.implementation_controller._latest["TASK-OPEN-POLICY"],
            41,
        ),
        (
            binding.review_controller._latest["TASK-REVIEW-POLICY"],
            42,
        ),
        (
            binding.integration_controller._latest[
                "TASK-INTEGRATION-POLICY"
            ],
            43,
        ),
        (
            binding.epic_controller._latest["EPIC-ROLLUP-POLICY"],
            44,
        ),
    )
    for item, expected_seconds in owner_items:
        deadline = datetime.fromisoformat(
            item.decision.next_reassessment_at
        )
        collected = datetime.fromisoformat(item.facts.collected_at)
        assert (deadline - collected).total_seconds() == expected_seconds

    runtime.close()
    store.close()


def test_enforce_runtime_owns_liveness_restart_reconstruction(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([])
    binding, journal = make_binding(tmp_path, tracker, store)
    controller = UniversalTotalityLivenessController(store=store)
    controller.restore_liveness_state(None)
    persisted = []
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
        liveness_controller=controller,
        persist_liveness_state=lambda state: persisted.append(dict(state)),
        **accepted_projection_wiring(),
    )

    asyncio.run(runtime.start())
    assert controller.liveness_snapshot().restart_reconstruction_pending

    first = runtime.reconcile()
    first_health = controller.liveness_snapshot()
    second = runtime.reconcile()
    second_health = controller.liveness_snapshot()

    assert first["liveness"]["scan_complete"] is True
    assert first_health.restart_reconstruction_pending is False
    assert first_health.scan_complete and first_health.healthy
    assert second["liveness"]["snapshot_generation"] > first["liveness"][
        "snapshot_generation"
    ]
    assert second_health.restart_convergence_count == (
        first_health.restart_convergence_count
    )
    assert controller.health_snapshot()["controller"]["passes"] == 2
    assert runtime.health_snapshot()["liveness"]["scan_complete"] is True
    assert persisted[-1]["accepted_snapshot_generation"] == (
        second_health.snapshot_generation
    )
    runtime.close()
    store.close()


def test_runtime_liveness_fails_closed_for_unmaterialized_owner_recovery(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([make_issue("TASK-OWNER", state="In Progress")])
    binding, journal = make_binding(tmp_path, tracker, store)
    controller = UniversalTotalityLivenessController(store=store)
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
        liveness_controller=controller,
        **accepted_projection_wiring(),
    )

    asyncio.run(runtime.start())
    runtime.reconcile()
    health = controller.liveness_snapshot()
    projection = runtime.projections()[0]

    assert projection["reason_code"] == "implementation.recovery_scheduled"
    assert projection["durable_jobs"] == ["implementation_recovery"]
    assert not health.scan_complete
    assert not health.reconciliation_complete
    assert health.required_recovery_count == 1
    assert health.materialized_recovery_count == 0

    runtime.reconcile()
    recovered = controller.liveness_snapshot()
    assert recovered.scan_complete
    assert recovered.reconciliation_complete
    assert recovered.required_recovery_count == 1
    assert recovered.materialized_recovery_count == 1
    runtime.close()
    store.close()


def test_runtime_reactivates_fact_submission_superseded_by_owner_event(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    task = make_issue("TASK-SUBMISSION-REARM", state="In Progress")
    task.head_sha = "a" * 40
    tracker = NativeTracker([task])
    binding, journal = make_binding(tmp_path, tracker, store)
    binding.collector.sources[FactDomain.CONFIG] = lambda _issue: {
        "version": 1,
        "implementation_pending_action": "validation_submission",
        "implementation_pending_payload": {
            "owner_id": "direct-owner",
            "head_sha": task.head_sha,
            "work_branch": task.work_branch,
        },
    }
    controller = UniversalTotalityLivenessController(store=store)
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
        liveness_controller=controller,
        **accepted_projection_wiring(),
    )

    asyncio.run(runtime.start())
    first = runtime.reconcile()
    original = next(
        job
        for job in store.list_jobs(task_id=task.identifier)
        if job.action == ImplementationAction.VALIDATION_SUBMISSION.value
    )
    assert first["projects"]["project-1"]["implementation"][
        "jobs_materialized"
    ] == 1

    imperative = binding.implementation_controller.schedule_event(
        project_id="project-1",
        task_id=task.identifier,
        action=ImplementationAction.DIRECT_OWNER_CLAIM,
        payload={
            "claim_id": "claim-1",
            "owner_id": "direct-owner",
            "expected_status": task.state,
            "work_branch": task.work_branch,
            "head_sha": task.head_sha,
        },
        expected_evidence_revision=issue_authority_version(task),
        expected_head_sha=task.head_sha,
    )
    assert store.get(original.job_id).state is WorkflowJobState.SUPERSEDED
    running = store.claim_next(
        lease_owner="owner-worker",
        lease_seconds=30,
        task_id=task.identifier,
        actions=(ImplementationAction.DIRECT_OWNER_CLAIM.value,),
    )
    assert running is not None and running.job_id == imperative.job_id
    store.complete(running.job_id, running.lease_token)

    second = runtime.reconcile()
    second_health = controller.liveness_snapshot()
    replacements = [
        job
        for job in store.list_jobs(task_id=task.identifier)
        if job.action == ImplementationAction.VALIDATION_SUBMISSION.value
        and job.state in ACTIVE_JOB_STATES
    ]
    assert not second_health.reconciliation_complete
    assert second["projects"]["project-1"]["implementation"][
        "jobs_created"
    ] == 1
    assert second["projects"]["project-1"]["implementation"][
        "jobs_materialized"
    ] == 1
    assert len(replacements) == 1
    assert replacements[0].job_id != original.job_id
    assert replacements[0].generation != original.generation

    runtime.reconcile()
    recovered = controller.liveness_snapshot()
    assert recovered.scan_complete
    assert recovered.reconciliation_complete
    assert recovered.required_recovery_count == 1
    assert recovered.materialized_recovery_count == 1
    runtime.close()
    store.close()


def test_runtime_liveness_expands_owner_window_for_101_review_tasks(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tasks = [
        make_issue(f"TASK-{index:03d}", state="In Review")
        for index in range(101)
    ]
    tracker = NativeTracker(tasks)
    binding, journal = make_binding(tmp_path, tracker, store)
    binding.review_controller = ReviewWorkflowController(
        collector=binding.collector,
        store=store,
        decision_limit=100,
    )
    controller = UniversalTotalityLivenessController(store=store)
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
        liveness_controller=controller,
        **accepted_projection_wiring(),
    )

    asyncio.run(runtime.start())
    reports = [runtime.reconcile() for _ in range(3)]
    health = controller.liveness_snapshot()
    jobs = store.list_jobs(limit=1000)

    assert binding.review_controller.decision_limit >= 101
    assert all(
        report["projects"]["project-1"]["review"]["decisions_seen"]
        == 101
        for report in reports
    )
    assert health.scan_complete and health.reconciliation_complete
    assert health.required_recovery_count == 101
    assert health.materialized_recovery_count == 101
    assert len(jobs) < 202
    runtime.close()
    store.close()


def test_runtime_atomically_publishes_canonical_owning_projection(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([make_issue("TASK-PROJECTION", state="In Progress")])
    binding, journal = make_binding(tmp_path, tracker, store)
    controller = UniversalTotalityLivenessController(store=store)
    calls = []

    class Publication:
        accepted = True
        rejection = None

        def __init__(self):
            self.committed = False
            self.rolled_back = False

        def commit_memory(self):
            self.committed = True

        def rollback(self):
            self.rolled_back = True

    publication = Publication()

    def publisher(decisions, generation, **kwargs):
        calls.append((tuple(decisions), generation, kwargs))
        return publication

    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
        liveness_controller=controller,
        projection_publisher=publisher,
        projection_epoch_source=lambda: 11,
    )

    asyncio.run(runtime.start())
    report = runtime.reconcile()

    assert report["projects"]["project-1"]["snapshot"]["published"]
    assert len(calls) == 1
    decisions, generation, kwargs = calls[0]
    assert [(item.project_id, item.task_id) for item in decisions] == [
        ("project-1", "TASK-PROJECTION")
    ]
    assert decisions[0].decision_revision == runtime.projections()[0][
        "decision_revision"
    ]
    assert generation == report["liveness"]["snapshot_generation"]
    assert kwargs["publication_epoch"] == 11
    assert kwargs["live_keys"] == {("project-1", "TASK-PROJECTION")}
    assert publication.committed
    assert not publication.rolled_back
    runtime.close()
    store.close()


def test_canonical_projection_excludes_terminal_domain_maintenance(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    active = make_issue("TASK-ACTIVE", state="Open")
    terminal = make_issue(
        "TASK-TERMINAL", state="Merged", parent_id="EPIC-1"
    )
    terminal.title = "Rebase epic-EPIC-1 onto main"
    terminal.work_branch = "epic-EPIC-1"
    terminal.target_branch = "epic-EPIC-1"
    terminal.head_sha = "b" * 40
    terminal.integration = IntegrationRecord(
        state="integrated",
        mode="queue",
        task_branch="epic-EPIC-1",
        base_branch="epic-EPIC-1",
        head_sha="b" * 40,
        integrated_sha="b" * 40,
        maintenance_publication_proven=True,
    )
    tracker = NativeTracker([active, terminal])
    binding, journal = make_binding(tmp_path, tracker, store)
    controller = UniversalTotalityLivenessController(store=store)
    published = []

    def publisher(decisions, _generation, *, live_keys, **_kwargs):
        keys = {(item.project_id, item.task_id) for item in decisions}
        assert keys <= live_keys
        published.append(keys)
        return SimpleNamespace(
            accepted=True,
            rejection=None,
            commit_memory=lambda: None,
            rollback=lambda: None,
        )

    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
        liveness_controller=controller,
        projection_publisher=publisher,
        projection_epoch_source=lambda: 1,
    )

    asyncio.run(runtime.start())
    report = runtime.reconcile()

    assert "error" not in report["projects"]["project-1"]
    assert published == [{("project-1", active.identifier)}]
    assert ("project-1", terminal.identifier) not in {
        (item["project_id"], item["task_id"])
        for item in runtime.projections()
    }
    runtime.close()
    store.close()


def test_runtime_publishes_lifecycle_final_exhaustion_authority(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    terminal = make_issue(
        "EPIC-FINAL-CLEANUP",
        state="Merged",
        issue_type="epic",
    )
    cleanup = store.materialize_event(
        project_id="project-1",
        task_id=terminal.identifier,
        decision_revision="cleanup-generation",
        action="epic_cleanup",
        idempotency_namespace="epic-cleanup",
        scheduling_lane="epic-event:epic_cleanup",
    )
    assert cleanup.job is not None
    running = store.claim_next(
        lease_owner="failed-worker",
        lease_seconds=30,
        task_id=terminal.identifier,
    )
    assert running is not None
    store.fail(
        running.job_id,
        running.lease_token,
        category=WorkflowFailureCategory.PERMANENT,
        error="cleanup failed permanently",
        retryable=False,
    )

    tracker = NativeTracker([terminal])
    binding, journal = make_binding(tmp_path, tracker, store)
    controller = UniversalTotalityLivenessController(store=store)
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
        liveness_controller=controller,
        **accepted_projection_wiring(),
    )

    asyncio.run(runtime.start())
    report = runtime.reconcile()

    assert report["projects"]["project-1"]["snapshot"]["published"]
    assert not store.current_exhausted_jobs(
        project_id="project-1", task_id=terminal.identifier
    )
    assert store.health_snapshot()["current_states"]["exhausted"] == 0
    runtime.close()
    store.close()


def test_runtime_publishes_done_zero_job_exhaustion_authority(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    project_id = "project-1"
    task_id = "TASK-DONE-WAITING"
    first = store.allocate_snapshot_generation()
    assert store.accept_snapshot_generation(first)
    assert store.reconcile_snapshot_membership(
        snapshot_generation=first,
        authoritative_project_ids=(project_id,),
        expected_identities=((project_id, task_id),),
    ).accepted
    cursor = store.activate_schedule(
        project_id=project_id,
        task_id=task_id,
        decision_revision="landing-refresh-required",
        snapshot_generation=first,
    )
    assert store.reconcile_schedule(
        project_id=project_id,
        task_id=task_id,
        snapshot_generation=first,
        job_generation=cursor.job_generation,
        specs=(
            WorkflowJobSpec(
                project_id=project_id,
                task_id=task_id,
                generation=cursor.job_generation,
                action="integration_landing_refresh",
                idempotency_key="runtime:landing-refresh",
            ),
        ),
    ).accepted
    assert store.publish_snapshot_generation(first, lambda: None)[0]
    running = store.claim_next(
        lease_owner="failed-worker",
        lease_seconds=30,
        task_id=task_id,
    )
    assert running is not None
    store.fail(
        running.job_id,
        running.lease_token,
        category=WorkflowFailureCategory.PERMANENT,
        error="refresh failed permanently",
        retryable=False,
    )

    done = make_issue(task_id, state="Done")
    done.integration = IntegrationRecord(
        state="integrated",
        task_branch=task_id,
        base_branch="main",
        head_sha="a" * 40,
        integrated_sha="a" * 40,
    )

    class NotLandedCollector:
        project_id = "project-1"

        def collect_many(self, requests):
            return tuple(
                LandingFact(
                    request.source,
                    request.target,
                    request.revision,
                    {
                        "kind": "not_ancestor",
                        "source_sha": request.revision,
                    },
                    "2026-08-09T00:00:00+00:00",
                    project_id,
                    state=LandingState.NOT_LANDED,
                )
                for request in requests
            )

    tracker = NativeTracker([done])
    binding, journal = make_binding(tmp_path, tracker, store)
    binding.collector.landing_collector = NotLandedCollector()
    controller = UniversalTotalityLivenessController(store=store)
    runtime = WorkflowRuntime(
        project_bindings={project_id: binding},
        store=store,
        journals={project_id: journal},
        mode="enforce",
        handlers=complete_handlers(),
        liveness_controller=controller,
        **accepted_projection_wiring(),
    )

    asyncio.run(runtime.start())
    report = runtime.reconcile()

    assert report["projects"][project_id]["snapshot"]["published"]
    assert runtime.projections()[0]["reason_code"] == "landing.waiting"
    assert not store.current_exhausted_jobs(
        project_id=project_id, task_id=task_id
    )
    retirement = store._conn.execute(  # noqa: SLF001 - exact authority proof
        "SELECT authority_kind FROM workflow_job_retirements WHERE job_id = ?",
        (running.job_id,),
    ).fetchone()
    assert retirement is not None
    assert retirement["authority_kind"] == "managed_zero_job"
    runtime.close()
    store.close()


def test_postcommit_liveness_failure_clears_inflight_without_rollback(
    tmp_path, monkeypatch
):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([])
    binding, journal = make_binding(tmp_path, tracker, store)
    controller = UniversalTotalityLivenessController(store=store)
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
        liveness_controller=controller,
        **accepted_projection_wiring(),
    )
    authority_rollbacks = []
    original_restore = store.restore_snapshot_authority

    def track_restore(*args, **kwargs):
        authority_rollbacks.append((args, kwargs))
        return original_restore(*args, **kwargs)

    monkeypatch.setattr(store, "restore_snapshot_authority", track_restore)
    monkeypatch.setattr(
        controller,
        "commit_runtime_observation",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("postcommit bookkeeping failed")
        ),
    )

    asyncio.run(runtime.start())
    report = runtime.reconcile()

    assert report["liveness"]["snapshot_generation"] >= 1
    assert authority_rollbacks == []
    assert controller._inflight_generations == set()  # noqa: SLF001
    runtime.close()
    store.close()


def test_postmarker_abort_failure_does_not_restore_committed_authority(
    tmp_path, monkeypatch
):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    task = make_issue("TASK-POSTMARKER", state="In Review")
    tracker = NativeTracker([task])
    binding, journal = make_binding(tmp_path, tracker, store)
    controller = UniversalTotalityLivenessController(store=store)
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
        liveness_controller=controller,
        **accepted_projection_wiring(),
    )
    authority_rollbacks = []
    original_restore = store.restore_snapshot_authority
    original_publish = store.publish_snapshot_generation

    def track_restore(*args, **kwargs):
        authority_rollbacks.append((args, kwargs))
        return original_restore(*args, **kwargs)

    def discard_publication_result(*args, **kwargs):
        published, _result = original_publish(*args, **kwargs)
        return published, None

    monkeypatch.setattr(store, "restore_snapshot_authority", track_restore)
    monkeypatch.setattr(
        store, "publish_snapshot_generation", discard_publication_result
    )
    monkeypatch.setattr(
        controller,
        "abort_runtime_observation",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("post-marker abort failed")
        ),
    )

    asyncio.run(runtime.start())
    report = runtime.reconcile()

    assert report["postcommit_error"] == "RuntimeError"
    assert authority_rollbacks == []
    assert any(
        project_id == "project-1" and task_id == task.identifier
        for project_id, task_id, _generation in store.snapshot_membership()
    )
    cursor = store.schedule_cursor(
        project_id="project-1", task_id=task.identifier
    )
    assert cursor is not None and cursor.materialized
    assert runtime.projections()
    runtime.close()
    store.close()


def test_runtime_liveness_and_projection_roll_back_with_rejected_marker(
    tmp_path, monkeypatch
):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([])
    binding, journal = make_binding(tmp_path, tracker, store)
    controller = UniversalTotalityLivenessController(store=store)
    controller.restore_liveness_state(None)
    prior_state = controller.liveness_state()
    persisted = []
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
        liveness_controller=controller,
        persist_liveness_state=lambda state: persisted.append(dict(state)),
        **accepted_projection_wiring(),
    )

    def reject_publication(generation, publisher, *, rollback_authority=None):
        publication = publisher()
        assert publication.rollback is not None
        publication.rollback()
        durable_rollback = publication.rollback_authority or rollback_authority
        if durable_rollback is not None:
            durable_rollback()
        return False, None

    monkeypatch.setattr(store, "publish_snapshot_generation", reject_publication)
    asyncio.run(runtime.start())
    report = runtime.reconcile()

    assert "liveness" not in report
    assert controller.liveness_state() == prior_state
    assert controller.health_snapshot()["controller"]["passes"] == 0
    assert runtime.projections() == ()
    assert persisted[-1] == prior_state
    runtime.close()
    store.close()


def test_midpublisher_rollback_failure_quarantines_snapshot_generation(
    tmp_path, monkeypatch
):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([make_issue("TASK-SPLIT", state="In Review")])
    binding, journal = make_binding(tmp_path, tracker, store)
    controller = UniversalTotalityLivenessController(store=store)
    external = {"published": False, "rollback_calls": 0}

    class FailedRollbackPublication:
        accepted = True
        rejection = None

        def commit_memory(self):
            external["published"] = True

        def rollback(self):
            external["rollback_calls"] += 1
            raise RuntimeError("projection rollback failed")

    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
        liveness_controller=controller,
        projection_publisher=lambda *_args, **_kwargs: (
            FailedRollbackPublication()
        ),
        projection_epoch_source=lambda: 1,
    )
    monkeypatch.setattr(
        controller,
        "stage_runtime_observation",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("liveness stage failed")
        ),
    )

    asyncio.run(runtime.start())
    report = runtime.reconcile()
    health = store.health_snapshot()

    assert report["projects"]["project-1"]["error"] == (
        "WorkflowJobStoreError"
    )
    assert external == {"published": True, "rollback_calls": 1}
    assert health["accepted_snapshot_generation"] == (
        health["published_snapshot_generation"]
    )
    assert health["accepted_snapshot_generation"] == 0
    assert not store.snapshot_generation_is_current(
        health["captured_snapshot_generation"]
    )
    assert runtime.projections() == ()
    runtime.close()
    store.close()


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


def test_epic_task_fact_race_does_not_reject_the_project_snapshot(tmp_path):
    stale = make_issue("EPIC-RACE", state="In Progress", issue_type="epic")
    current = make_issue("EPIC-RACE", state="Done", issue_type="epic")

    class RacingTracker(NativeTracker):
        def fetch_all_issues_enriched(self):
            return [stale]

        fetch_all_issues = fetch_all_issues_enriched

        def fetch_issue_detail(self, identifier):
            assert identifier == current.identifier
            return current

    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = RacingTracker([current])
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
    assert "error" not in project
    assert project["snapshot"]["published"] is True
    assert project["epic"]["decisions_seen"] == 1
    assert project["epic"]["jobs_required"] == 0
    assert binding.epic_controller.projections()[0].durable_jobs == ()
    assert store.list_jobs(task_id=current.identifier) == ()
    runtime.close()
    store.close()


@pytest.mark.parametrize("action", ["review_refresh", "unknown_action"])
def test_domain_scoping_still_rejects_foreign_or_unknown_actions(action):
    batch = SimpleNamespace(
        decisions=(SimpleNamespace(durable_jobs=(action,)),),
    )

    with pytest.raises(
        WorkflowRuntimeError,
        match=f"epic decision produced non-epic durable jobs: {action}",
    ):
        WorkflowRuntime._scope_domain_decisions("epic", batch, EPIC_ACTIONS)


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
    original_reconcile = implementation.reconcile_evaluated
    calls = 0

    def fail_once(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("implementation event lane unavailable")
        return original_reconcile(*args, **kwargs)

    implementation.reconcile_evaluated = fail_once
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

    async def recover():
        report = await runtime.reconcile_async()
        await wait_for_runtime_effects(runtime)
        return report

    second = asyncio.run(recover())

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
        await wait_for_runtime_effects(runtime)
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
    async def reconcile_and_wait():
        result = await runtime.reconcile_async()
        await wait_for_runtime_effects(runtime)
        return result

    report = asyncio.run(reconcile_and_wait())

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
    async def resume_and_wait():
        result = await runtime.reconcile_async()
        await wait_for_runtime_effects(runtime)
        return result

    resumed_report = asyncio.run(resume_and_wait())
    assert resumed_report["worker"]["processed"] == 1
    assert store.get(job.job_id).state is WorkflowJobState.COMPLETED
    runtime.close()
    store.close()


def test_pause_race_after_claim_defers_without_consuming_attempt(tmp_path):
    now = [1000.0]
    enabled = True
    store = WorkflowJobStore(
        str(tmp_path / "pause-race.sqlite3"), clock=lambda: now[0]
    )
    leaf = CompleteHandler()
    routed = _ProjectRoutedHandler(
        "review_refresh",
        {"project-1": leaf},
        project_enabled={"project-1": lambda: enabled},
    )
    job = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-PAUSE-RACE",
            generation="pause-race-1",
            action="review_refresh",
            idempotency_key="pause-race-job",
            max_attempts=1,
        )
    )

    async def exercise():
        nonlocal enabled
        paused_once = False

        def pause_after_claim(phase, _job):
            nonlocal enabled, paused_once
            if phase == "leased" and not paused_once:
                paused_once = True
                enabled = False

        runner = DurableWorkflowWorker(
            store=store,
            handlers={"review_refresh": routed},
            transition_services={},
            worker_id="pause-race-worker",
            retry_delay_seconds=5,
            phase_observer=pause_after_claim,
        )
        deferred = await runner.run_once()
        enabled = True
        now[0] += 5
        completed = await runner.run_once()
        return deferred, completed

    deferred, completed = asyncio.run(exercise())

    assert deferred.disposition is WorkflowRunDisposition.RETRY_SCHEDULED
    assert deferred.attempts == 0
    assert completed.disposition is WorkflowRunDisposition.COMPLETED
    assert store.get(job.job_id).attempts == 1
    assert [event.event_type for event in store.events(job.job_id)].count(
        "administrative_deferred"
    ) == 1
    store.close()


def test_paused_project_preserves_managed_membership_jobs_and_liveness(
    tmp_path,
):
    enabled = True
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([make_issue("TASK-PAUSED", state="In Review")])
    binding, journal = make_binding(tmp_path, tracker, store)
    binding.dispatch_enabled = lambda: enabled
    controller = UniversalTotalityLivenessController(store=store)
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
        liveness_controller=controller,
        **accepted_projection_wiring(),
    )

    asyncio.run(runtime.start())
    runtime.reconcile()
    membership = store.snapshot_membership()
    cursor = store.schedule_cursor(
        project_id="project-1", task_id="TASK-PAUSED"
    )
    jobs = store.list_jobs(project_id="project-1", task_id="TASK-PAUSED")
    assert membership
    assert cursor is not None
    assert jobs

    enabled = False
    paused_report = runtime.reconcile()
    health = controller.liveness_snapshot()

    assert paused_report["projects"]["project-1"]["skipped"] is True
    assert store.snapshot_membership() == membership
    assert store.schedule_cursor(
        project_id="project-1", task_id="TASK-PAUSED"
    ) == cursor
    assert store.list_jobs(
        project_id="project-1", task_id="TASK-PAUSED"
    ) == jobs
    assert health.scan_complete
    assert health.coverage_scope == "active_projects"
    assert not health.global_coverage_complete
    assert health.active_project_count == 0
    assert health.excluded_project_count == 1
    assert health.excluded_task_count == 1
    runtime.close()
    store.close()


def test_pause_authority_read_failure_is_incomplete_not_excluded(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([make_issue("TASK-PAUSE-ERROR", state="Open")])
    binding, journal = make_binding(tmp_path, tracker, store)

    def failed_pause_read():
        raise RuntimeError("pause authority unavailable")

    binding.dispatch_enabled = failed_pause_read
    controller = UniversalTotalityLivenessController(store=store)
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
        liveness_controller=controller,
        **accepted_projection_wiring(),
    )

    asyncio.run(runtime.start())
    report = runtime.reconcile()
    health = controller.liveness_snapshot()

    assert binding.enabled is False
    assert report["projects"]["project-1"]["error"] == "RuntimeError"
    assert health.source_error_count == 1
    assert health.excluded_project_count == 0
    assert not health.scan_complete
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
