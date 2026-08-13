"""Production composition and lifecycle coverage for the durable runtime."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import shlex
import subprocess
import threading
import time
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

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
from oompah.oompah_md_tracker import OompahMarkdownTracker
from oompah.provenance_suppression import (
    authorize_new_revision,
    mark_provenance_only,
)
from oompah.quality_gate import BranchQualityGate
from oompah.review_workflow import ReviewWorkflowController
from oompah.terminal_audit import (
    ContributorIdentity,
    EvidenceFingerprint,
    RequestState,
    TargetState,
    TerminalAuditRecord,
)
from oompah.terminal_audit_metadata import (
    TerminalAuditMetadata,
    TerminalAuditMetadataStore,
)
from oompah.terminal_audit_enforcement import TerminalAuditEnforcement
from oompah.task_transition_service import (
    TaskTransitionService,
    TransitionAuthority,
    TransitionIntent,
    TransitionJournal,
    issue_authority_version,
)
from oompah.terminal_audit_workflow import TerminalAuditWorkflow
from oompah.workflow_facts import FactDomain, LandingState, WorkflowFactCollector
from oompah.workflow_fact_model import FactState, LandingFact
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
    RUNTIME_CONTROL_ACTIONS,
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
    supports_generation_bound_reads = True
    state_branch_enabled = True

    def __init__(self, issues: list[Issue]):
        self.issues = {issue.identifier: issue for issue in issues}
        self.authority_generation = "test-native:1"
        self.publication_revision = 1

    def fetch_all_issues_enriched(self):
        return list(self.issues.values())

    fetch_all_issues = fetch_all_issues_enriched

    def fetch_all_issues_with_generation(self):
        return self.fetch_all_issues(), self.authority_generation

    def get_state_branch_generation(self):
        return self.authority_generation

    def get_publication_revision(self):
        return self.publication_revision

    def fetch_issue_detail(self, identifier):
        return self.issues.get(identifier)

    def fetch_children(self, identifier):
        return [
            issue for issue in self.issues.values() if issue.parent_id == identifier
        ]


class ScopedMutationTracker(NativeTracker):
    """Generation-bound tracker double with an exact per-task change journal."""

    def __init__(self, issues: list[Issue]):
        super().__init__(issues)
        self._generation = 1
        self._changes: dict[int, str] = {}
        self._refresh_generation()

    def _refresh_generation(self):
        self.authority_generation = f"test-native:{self._generation}"
        self.publication_revision = self._generation

    def mutate(self, identifier: str, *, state: str | None = None):
        current = self.issues[identifier]
        self.issues[identifier] = replace(
            current,
            state=state or current.state,
            title=f"{current.title} generation {self._generation + 1}",
        )
        self._generation += 1
        self._changes[self._generation] = identifier
        self._refresh_generation()

    def task_authority_changes_between(self, expected: str, current: str):
        try:
            expected_generation = int(expected.rsplit(":", 1)[1])
            current_generation = int(current.rsplit(":", 1)[1])
        except (IndexError, ValueError):
            return None
        if current_generation < expected_generation:
            return None
        return frozenset(
            self._changes[generation]
            for generation in range(expected_generation + 1, current_generation + 1)
            if generation in self._changes
        )

    def publication_task_changes_since(self, revision: int):
        current = self.publication_revision
        if revision < 1 or revision > current:
            return current, None
        return current, frozenset(
            self._changes[generation]
            for generation in range(revision + 1, current + 1)
            if generation in self._changes
        )

    def terminal_metadata_changes_between(self, _expected: str, _current: str):
        return None


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
        blocked_by=[],
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
    publication_lock = threading.RLock()
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
        terminal_audit_publication_lock=lambda: publication_lock,
        tracker_authority_revision_source=(
            tracker.get_state_branch_generation
            if callable(getattr(tracker, "get_state_branch_generation", None))
            else None
        ),
        tracker_publication_revision_source=(
            tracker.get_publication_revision
            if callable(getattr(tracker, "get_publication_revision", None))
            else None
        ),
        tracker_publication_changes_source=(
            tracker.publication_task_changes_since
            if callable(
                getattr(tracker, "publication_task_changes_since", None)
            )
            else None
        ),
        tracker_authority_changes_source=(
            tracker.task_authority_changes_between
            if callable(getattr(tracker, "task_authority_changes_between", None))
            else None
        ),
        tracker_terminal_authority_changes_source=(
            tracker.terminal_metadata_changes_between
            if callable(getattr(tracker, "terminal_metadata_changes_between", None))
            else None
        ),
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
        workflow_quarantine_persist_timeout_seconds = 19
        workflow_quarantine_recycle_seconds = 23

    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    integration_queue = object()
    tracker = ScopedMutationTracker([make_issue("TASK-BOOT")])
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
    assert runtime.worker.quarantine_persist_timeout_seconds == 19
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
    assert binding.tracker_publication_revision_source is not None
    assert binding.tracker_publication_changes_source is not None
    tracker.publication_revision = None
    assert binding.tracker_publication_revision_source() is None
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


def test_runtime_authority_source_preserves_direct_owner_retirement_fence(tmp_path):
    class ProjectStore:
        def list_all(self):
            return []

    class Config:
        workflow_engine_mode = "shadow"
        workflow_runtime_decision_limit = 17
        workflow_runtime_batch_size = 9

    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    task = make_issue("TASK-RETIRING", state="Ready to Integrate", project_id="legacy")
    tracker = NativeTracker([task])
    retirement = {
        "owner_id": "operator",
        "generation": "claim-retiring",
        "ownership_source": "direct_owner",
        "lease_expires_at": None,
        "retirement_pending": True,
        "state": "retirement_pending",
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
            "_workflow_shadow_sources": lambda _self, _issue: {
                FactDomain.IMPLEMENTATION_AUTHORITY: lambda _current: retirement,
            },
        },
    )()
    runtime = WorkflowRuntime.from_orchestrator(orchestrator)
    binding = runtime.project_bindings["legacy"]
    binding.implementation_controller.implementation_authority = lambda _issue: {
        "lease_expires_at": None,
        "state": "submitted",
    }

    facts = binding.collector.collect(task.identifier)

    assert facts.fact(FactDomain.IMPLEMENTATION_AUTHORITY).value == retirement
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
    ) in requested
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

    # An owner repair transition is a stronger authority change than the
    # previously collected terminal-audit envelope.  The publication proof
    # must reject that old cut immediately, before restart recovery gets a
    # chance to durably cancel the orphaned metadata and workflow job.
    for status in ("Needs CI Fix", "Open", "Needs Human", "Done", "Merged", "Archived"):
        task.state = status
        assert not proof(decision_b, observed_b, "terminal_audit")
        repaired_facts = binding.collector.collect(task.identifier)
        repaired_value = repaired_facts.fact(FactDomain.TERMINAL_AUDIT).value
        assert repaired_value is None or "audit_id" not in repaired_value

    runtime.close()
    store.close()


def test_repair_status_orphan_cannot_deadlock_restart_world_publication(tmp_path):
    """An OOMPAH-940-shaped orphan converges on the next stable world cut."""

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

    task = make_issue("TASK-AUDIT-ORPHAN", state="In Validation", project_id="legacy")
    tracker = AuditTracker([task])
    project_store = ProjectStore()
    store = WorkflowJobStore(str(tmp_path / "orphan-jobs.sqlite3"))
    workflow = TerminalAuditWorkflow(store)
    metadata = TerminalAuditMetadataStore(tracker, project_store, "legacy")
    record = TerminalAuditRecord(
        audit_id="audit-orphan",
        project_id="legacy",
        task_id=task.identifier,
        target_state=TargetState.DONE,
        evidence_fingerprint=EvidenceFingerprint("a" * 64),
        request_state=RequestState.IN_PROGRESS,
        source_generation=7,
    )
    metadata.write(
        task.identifier,
        TerminalAuditMetadata(pending_chain=[record]),
    )
    orphan_job = workflow.ensure(record)

    class OrchestratorDouble:
        config = Config()
        workflow_job_store = store
        terminal_audit_workflow = workflow
        _state_path = str(tmp_path / "orphan-service-state.json")

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

    # Build the actual service terminal-audit source and publication proofs,
    # then place them in the compact runtime fixture whose unrelated fact
    # domains are deterministic.  The task moves to its owner repair state
    # after the audit generation was already durably materialized.
    task.state = "Needs CI Fix"
    enforcer = TerminalAuditEnforcement(
        str(tmp_path / "orphan-enforcement-state.json"),
        terminal_states=("Done", "Merged", "Archived"),
        project_store=project_store,
    )
    assert enforcer.recover_pending_audits([("legacy", tracker)]) == []
    sync = Orchestrator.__new__(Orchestrator)
    sync.workflow_job_store = store
    sync.terminal_audit_workflow = workflow
    sync._terminal_audit_enforcement = enforcer
    sync._maintenance_status = {}
    sync._running_values_snapshot = lambda: []
    sync._tracker_for_project = lambda _project_id: tracker
    sync.project_store = project_store
    sync._sync_terminal_audit_workflow_jobs()
    assert store.get(orphan_job.job_id).state is WorkflowJobState.CANCELLED

    factory_runtime = WorkflowRuntime.from_orchestrator(
        OrchestratorDouble(),
        state_dir=tmp_path / "factory-runtime",
    )
    factory_binding = factory_runtime.project_bindings["legacy"]
    binding, journal = make_binding(tmp_path, tracker, store, "legacy")
    binding.collector.sources[FactDomain.TERMINAL_AUDIT] = (
        factory_binding.collector.sources[FactDomain.TERMINAL_AUDIT]
    )
    binding.terminal_audit_proof_source = (
        factory_binding.terminal_audit_proof_source
    )
    binding.terminal_audit_snapshot_proof_source = (
        factory_binding.terminal_audit_snapshot_proof_source
    )
    binding.terminal_audit_lane_proof_source = (
        factory_binding.terminal_audit_lane_proof_source
    )
    binding.terminal_audit_publication_lock = (
        factory_binding.terminal_audit_publication_lock
    )
    factory_runtime.close()

    controller = UniversalTotalityLivenessController(store=store)
    controller.restore_liveness_state(None)
    runtime = WorkflowRuntime(
        project_bindings={"legacy": binding},
        store=store,
        journals={"legacy": journal},
        mode="enforce",
        handlers=complete_handlers(),
        liveness_controller=controller,
        **accepted_projection_wiring(),
    )

    asyncio.run(runtime.start())
    first = runtime.reconcile()
    second = runtime.reconcile()
    health = store.health_snapshot()

    assert first["projects"]["legacy"].get("publication_superseded") is not True
    assert second["projects"]["legacy"].get("publication_superseded") is not True
    assert controller.liveness_snapshot().scan_complete
    assert not runtime.restart_reconstruction_pending
    assert health["accepted_snapshot_generation"] > 0
    assert health["accepted_snapshot_generation"] == health[
        "published_snapshot_generation"
    ]
    writes_after_convergence = tracker.metadata.get(task.identifier)
    assert enforcer.recover_pending_audits([("legacy", tracker)]) == []
    sync._sync_terminal_audit_workflow_jobs()
    assert tracker.metadata.get(task.identifier) == writes_after_convergence
    assert store.get(orphan_job.job_id).state is WorkflowJobState.CANCELLED
    runtime.close()
    store.close()


def test_native_tracker_generation_race_supersedes_stale_status_publication(
    tmp_path,
):
    """An owner status mutation after collection cannot publish the old cut."""

    task = make_issue("TASK-OWNER-RACE", state="Backlog")
    store = WorkflowJobStore(str(tmp_path / "jobs-owner-race.sqlite3"))
    tracker = NativeTracker([task])
    tracker.supports_generation_bound_reads = True
    tracker.fetch_all_issues_with_generation = lambda: (
        tracker.fetch_all_issues(),
        "native-head:1",
    )
    tracker.get_state_branch_generation = lambda: "native-head:2"
    binding, journal = make_binding(tmp_path, tracker, store)
    binding.tracker_authority_revision_source = (
        tracker.get_state_branch_generation
    )
    binding.tracker_terminal_authority_changes_source = (
        lambda _expected, _current: frozenset({task.identifier})
    )
    binding.terminal_audit_publication_lock = lambda: threading.RLock()
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

    assert report["requires_reconcile"] is True
    assert report["reconcile_reason"] == "publication_authority_changed"
    assert report["projects"]["project-1"] == {
        "publication_superseded": True,
        "reason": "tracker authority changed before publication",
    }
    health = store.health_snapshot()
    assert health["accepted_snapshot_generation"] == (
        health["published_snapshot_generation"]
    )
    runtime.close()
    store.close()


def test_native_cache_refresh_does_not_self_supersede_runtime_publication(
    tmp_path,
):
    """Defensive reads stay neutral while a real native write still fences."""

    tracker = OompahMarkdownTracker(
        active_states=["Open", "In Progress"],
        terminal_states=["Done", "Merged"],
        cwd=str(tmp_path / "native-refresh"),
        default_branch="main",
        git_sync=False,
    )
    task = tracker.create_issue(
        "Cache-neutral runtime publication",
        description="Publish a complete workflow snapshot.",
        initial_status="Backlog",
    )
    # Exercise the native generation-bound path without requiring a Git state
    # worktree in this focused CAS test. The production method combines its
    # durable commit with the same process-local publication revision.
    tracker.state_branch_enabled = True
    tracker.state_branch_name = "oompah/state/runtime-refresh"
    tracker._get_state_root = lambda: tracker.root_path  # type: ignore[method-assign]
    tracker._state_branch_generation_locked = lambda: (  # type: ignore[method-assign]
        f"{'a' * 40}:{tracker.get_publication_revision()}"
    )
    store = WorkflowJobStore(str(tmp_path / "native-refresh.sqlite3"))
    binding, journal = make_binding(tmp_path, tracker, store)
    original_config_source = binding.collector.sources[FactDomain.CONFIG]
    refreshed = False

    def refresh_during_collection(issue):
        nonlocal refreshed
        if not refreshed:
            refreshed = True
            tracker.invalidate_read_cache()
        return original_config_source(issue)

    binding.collector.sources[FactDomain.CONFIG] = refresh_during_collection
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
        liveness_controller=UniversalTotalityLivenessController(store=store),
        **accepted_projection_wiring(),
    )

    asyncio.run(runtime.start())
    publication_revision = tracker.get_publication_revision()
    report = runtime.reconcile()

    assert refreshed is True
    assert tracker.get_publication_revision() == publication_revision
    assert report["projects"]["project-1"]["snapshot"]["published"] is True
    assert not report.get("requires_reconcile", False)

    mutated = False

    def mutate_during_collection(issue):
        nonlocal mutated
        if not mutated:
            mutated = True
            tracker.update_issue(
                task.identifier,
                description="A real task mutation supersedes this cut.",
            )
        return original_config_source(issue)

    binding.collector.sources[FactDomain.CONFIG] = mutate_during_collection
    superseded = runtime.reconcile()

    assert mutated is True
    assert tracker.get_publication_revision() == publication_revision + 1
    assert superseded["requires_reconcile"] is True
    assert superseded["projects"]["project-1"] == {
        "publication_superseded": True,
        "reason": "tracker authority changed before publication",
    }
    runtime.close()
    store.close()


def test_dependency_status_race_cannot_publish_a_mixed_generation(tmp_path):
    """A dependency move after the corpus read supersedes the whole cut."""

    dependency = make_issue("TASK-DEPENDENCY", state="Merged")
    task = make_issue(
        "TASK-DEPENDENT", state="Ready to Integrate", parent_id="EPIC-1"
    )
    task.blocked_by = []
    task.start_blocked_by = [
        BlockerRef(identifier=dependency.identifier.lower())
    ]
    store = WorkflowJobStore(str(tmp_path / "dependency-race.sqlite3"))
    tracker = NativeTracker([task, dependency])
    tracker.fetch_all_issues_with_generation = lambda: (
        tracker.fetch_all_issues(),
        "dependency-head:1",
    )
    tracker.get_state_branch_generation = lambda: "dependency-head:2"
    binding, journal = make_binding(tmp_path, tracker, store)
    binding.tracker_authority_revision_source = (
        tracker.get_state_branch_generation
    )
    captured = []
    original_evaluate = binding.integration_controller.evaluate

    def capture_integration(tasks, **kwargs):
        batch = original_evaluate(tasks, **kwargs)
        captured.extend(batch.tasks)
        return batch

    binding.integration_controller.evaluate = capture_integration
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
        liveness_controller=UniversalTotalityLivenessController(store=store),
        **accepted_projection_wiring(),
    )

    asyncio.run(runtime.start())
    report = runtime.reconcile()

    dependent = next(
        item for item in captured if item.task.identifier == task.identifier
    )
    assert dependent.facts.fact(FactDomain.DEPENDENCIES).value[
        "hard_start"
    ][0]["status"] == "Merged"
    assert dependent.decision.reason_code == "integration.queued"
    assert report["projects"]["project-1"] == {
        "publication_superseded": True,
        "reason": "tracker authority changed before publication",
    }
    assert report["requires_reconcile"] is True
    assert store.health_snapshot()["accepted_snapshot_generation"] == 0
    runtime.close()
    store.close()


def test_runtime_filtered_foreign_dependency_ignores_embedded_state(tmp_path):
    """A foreign row filtered from the corpus cannot authorize its ref."""

    task = make_issue(
        "TASK-FILTERED-DEPENDENT",
        state="Ready to Integrate",
        parent_id="EPIC-1",
    )
    task.blocked_by = []
    task.start_blocked_by = [
        BlockerRef(identifier="FOREIGN-DEPENDENCY", state="Merged")
    ]
    foreign = make_issue(
        "FOREIGN-DEPENDENCY",
        state="Merged",
        project_id="project-2",
    )
    store = WorkflowJobStore(str(tmp_path / "filtered-foreign.sqlite3"))
    tracker = NativeTracker([task, foreign])
    binding, journal = make_binding(tmp_path, tracker, store)
    captured = []
    original_evaluate = binding.integration_controller.evaluate

    def capture_integration(tasks, **kwargs):
        batch = original_evaluate(tasks, **kwargs)
        captured.extend(batch.tasks)
        return batch

    binding.integration_controller.evaluate = capture_integration
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="shadow",
    )

    asyncio.run(runtime.start())
    report = runtime.reconcile()

    assert report["projects"]["project-1"]["issues"] == 1
    dependent = next(
        item for item in captured if item.task.identifier == task.identifier
    )
    dependencies = dependent.facts.fact(FactDomain.DEPENDENCIES)
    assert dependencies.state is FactState.ERROR
    assert dependencies.error_code == "dependency_state_unavailable"
    runtime.close()
    store.close()


def test_authoritative_issue_index_rejects_casefold_collision():
    first = make_issue("OOMPAH-CASE")
    second = make_issue("oompah-case")

    with pytest.raises(
        WorkflowRuntimeError,
        match="ambiguous task identity",
    ):
        WorkflowRuntime._authoritative_issue_index([first, second])


def test_terminal_status_delta_supersedes_dependent_integration_cut(tmp_path):
    """An audit task status race invalidates every decision that depends on it."""

    audit_task = make_issue("TASK-AUDIT-DEPENDENCY", state="In Validation")
    dependent_task = make_issue(
        "TASK-AUDIT-DEPENDENT",
        state="Ready to Integrate",
        parent_id="EPIC-1",
    )
    dependent_task.blocked_by = []
    dependent_task.start_blocked_by = [
        BlockerRef(identifier=audit_task.identifier, state="In Validation")
    ]
    store = WorkflowJobStore(str(tmp_path / "audit-dependency-race.sqlite3"))
    tracker = NativeTracker([audit_task, dependent_task])
    tracker.fetch_all_issues_with_generation = lambda: (
        tracker.fetch_all_issues(),
        "audit-status-head:1",
    )
    tracker.get_state_branch_generation = lambda: "audit-status-head:2"
    binding, journal = make_binding(tmp_path, tracker, store)
    binding.tracker_authority_revision_source = (
        tracker.get_state_branch_generation
    )
    workflow = binding.terminal_audit_workflow
    assert workflow is not None
    record = TerminalAuditRecord(
        audit_id="audit-dependency",
        project_id="project-1",
        task_id=audit_task.identifier,
        target_state=TargetState.DONE,
        evidence_fingerprint=EvidenceFingerprint("d" * 64),
        request_state=RequestState.IN_PROGRESS,
        source_generation=1,
    )
    workflow.ensure(record)
    observed = {
        "phase": "active",
        "workflow_phase": "running",
        "audit_job_present": True,
        "audit_id": record.audit_id,
        "request_state": record.request_state.value,
        "target_state": record.target_state.value,
        "evidence_fingerprint": record.evidence_fingerprint.digest,
        "source_generation": record.source_generation,
        "audit_generation": workflow.generation(record),
        "actively_working": True,
    }
    binding.collector.sources[FactDomain.TERMINAL_AUDIT] = (
        lambda issue: observed
        if issue.identifier == audit_task.identifier
        else {"phase": "none"}
    )
    terminal_revision = [0]
    binding.terminal_authority_revision_source = lambda: terminal_revision[0]

    def changed_tracker_tasks(_expected, _current):
        terminal_revision[0] = 1
        return frozenset({audit_task.identifier})

    binding.tracker_terminal_authority_changes_source = changed_tracker_tasks
    binding.terminal_authority_changes_source = lambda _expected: (
        terminal_revision[0],
        frozenset({audit_task.identifier}),
    )
    binding.terminal_audit_lane_proof_source = lambda *_args: True
    captured = []
    original_evaluate = binding.integration_controller.evaluate

    def capture_integration(tasks, **kwargs):
        batch = original_evaluate(tasks, **kwargs)
        captured.extend(batch.tasks)
        return batch

    binding.integration_controller.evaluate = capture_integration
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
        liveness_controller=UniversalTotalityLivenessController(store=store),
        **accepted_projection_wiring(),
    )

    asyncio.run(runtime.start())
    report = runtime.reconcile()

    dependent = next(
        item
        for item in captured
        if item.task.identifier == dependent_task.identifier
    )
    assert dependent.facts.fact(FactDomain.DEPENDENCIES).value[
        "hard_start"
    ][0]["status"] == "In Validation"
    assert report["projects"]["project-1"] == {
        "publication_superseded": True,
        "reason": "tracker authority changed before publication",
    }
    assert report["requires_reconcile"] is True
    assert store.health_snapshot()["accepted_snapshot_generation"] == 0
    assert runtime.projections() == ()
    runtime.close()
    store.close()


@pytest.mark.parametrize("mode", ("shadow", "enforce"))
def test_dependency_decision_converges_across_bounded_restart_scans(
    tmp_path, mode
):
    dependency = make_issue("TASK-RESTART-DEPENDENCY", state="Merged")
    task = make_issue(
        "TASK-RESTART-DEPENDENT",
        state="Ready to Integrate",
        parent_id="EPIC-1",
    )
    task.blocked_by = []
    task.start_blocked_by = [
        BlockerRef(identifier=dependency.identifier)
    ]
    tracker = NativeTracker([task, dependency])
    store = WorkflowJobStore(str(tmp_path / f"dependency-{mode}.sqlite3"))
    reasons = []

    for _restart_generation in range(2):
        binding, journal = make_binding(tmp_path, tracker, store)
        runtime = WorkflowRuntime(
            project_bindings={"project-1": binding},
            store=store,
            journals={"project-1": journal},
            mode=mode,
            handlers=complete_handlers() if mode == "enforce" else None,
            liveness_controller=UniversalTotalityLivenessController(
                store=store
            ),
            **accepted_projection_wiring(),
        )
        asyncio.run(runtime.start())
        report = runtime.reconcile()
        projection = next(
            item
            for item in runtime.projections()
            if item["task_id"] == task.identifier
        )
        reasons.append(projection["reason_code"])
        assert not report.get("requires_reconcile", False)
        runtime.close()

    assert reasons == ["integration.queued", "integration.queued"]
    store.close()


@pytest.mark.parametrize(
    ("unavailable_read", "expected_reason"),
    (
        (
            1,
            "tracker publication revision unavailable during source collection",
        ),
        (
            2,
            "tracker publication revision unavailable during source collection",
        ),
        (
            3,
            "tracker publication revision unavailable during publication preflight",
        ),
        (
            4,
            "tracker publication revision unavailable during publication preflight",
        ),
        (5, "tracker publication revision unavailable before publication"),
    ),
    ids=(
        "source-entry",
        "source-exit",
        "preflight-entry",
        "preflight-exit",
        "finalization",
    ),
)
def test_none_tracker_publication_revision_supersedes_snapshot(
    tmp_path,
    caplog,
    unavailable_read,
    expected_reason,
):
    task = make_issue("TASK-PUBLICATION-REVISION-NONE", state="Backlog")
    store = WorkflowJobStore(
        str(tmp_path / f"publication-revision-none-{unavailable_read}.sqlite3")
    )
    tracker = NativeTracker([task])
    binding, journal = make_binding(tmp_path, tracker, store)
    revision_reads = 0

    def publication_revision():
        nonlocal revision_reads
        revision_reads += 1
        return None if revision_reads == unavailable_read else 1

    binding.tracker_publication_revision_source = publication_revision
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
        liveness_controller=UniversalTotalityLivenessController(store=store),
        **accepted_projection_wiring(),
    )

    asyncio.run(runtime.start())
    with caplog.at_level(logging.INFO, logger="oompah.workflow_runtime"):
        report = runtime.reconcile()

    assert revision_reads == unavailable_read
    assert report["requires_reconcile"] is True
    assert report["reconcile_reason"] == "publication_authority_changed"
    assert report["projects"]["project-1"] == {
        "publication_superseded": True,
        "reason": expected_reason,
    }
    assert not any(
        record.levelno >= logging.ERROR
        and (
            "Durable workflow source evaluation failed" in record.message
            or "Durable workflow publication failed" in record.message
        )
        for record in caplog.records
    )
    health = store.health_snapshot()
    assert health["accepted_snapshot_generation"] == (
        health["published_snapshot_generation"]
    )
    assert runtime.projections() == ()
    assert store.list_jobs(project_id="project-1") == ()

    retry = runtime.reconcile()

    assert not retry.get("requires_reconcile", False)
    retry_snapshot = retry["projects"]["project-1"]["snapshot"]
    assert retry_snapshot["generation"] > 0
    assert retry_snapshot["members"] == 0
    assert retry_snapshot["jobs_superseded"] == 0
    assert retry_snapshot["published"] is True
    health = store.health_snapshot()
    assert health["accepted_snapshot_generation"] == (
        health["published_snapshot_generation"]
    )
    assert health["published_snapshot_generation"] == retry_snapshot["generation"]
    runtime.close()
    store.close()


def test_changed_tracker_publication_revision_during_source_supersedes(
    tmp_path,
    caplog,
):
    task = make_issue("TASK-PUBLICATION-REVISION-CHANGED", state="Backlog")
    store = WorkflowJobStore(str(tmp_path / "publication-revision-changed.sqlite3"))
    tracker = NativeTracker([task])
    binding, journal = make_binding(tmp_path, tracker, store)
    revision_reads = 0

    def publication_revision():
        nonlocal revision_reads
        revision_reads += 1
        return 1 if revision_reads == 1 else 2

    binding.tracker_publication_revision_source = publication_revision
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
        liveness_controller=UniversalTotalityLivenessController(store=store),
        **accepted_projection_wiring(),
    )

    asyncio.run(runtime.start())
    with caplog.at_level(logging.INFO, logger="oompah.workflow_runtime"):
        report = runtime.reconcile()

    assert revision_reads == 2
    assert report["requires_reconcile"] is True
    assert report["projects"]["project-1"] == {
        "publication_superseded": True,
        "reason": "tracker authority changed during source collection",
    }
    assert not any(
        record.levelno >= logging.ERROR
        and "Durable workflow source evaluation failed" in record.message
        for record in caplog.records
    )

    retry = runtime.reconcile()

    assert not retry.get("requires_reconcile", False)
    assert retry["projects"]["project-1"]["snapshot"]["published"] is True
    runtime.close()
    store.close()


@pytest.mark.parametrize(
    "unavailable_read",
    (1, 3, 5),
    ids=("source", "preflight", "finalization"),
)
def test_superseded_publication_does_not_admit_prior_shared_job(
    tmp_path,
    unavailable_read,
):
    task = make_issue("TASK-PRIOR-SHARED-JOB")
    store = WorkflowJobStore(
        str(tmp_path / f"prior-shared-job-{unavailable_read}.sqlite3")
    )
    tracker = NativeTracker([task])
    binding, journal = make_binding(tmp_path, tracker, store)
    applied_actions = []

    class RecordingHandler(CompleteHandler):
        async def apply(self, context):
            applied_actions.append(context.job.action)
            return await super().apply(context)

    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(RecordingHandler()),
        liveness_controller=UniversalTotalityLivenessController(store=store),
        **accepted_projection_wiring(),
    )

    asyncio.run(runtime.start())
    prior = runtime.reconcile()
    prior_generation = prior["projects"]["project-1"]["snapshot"]["generation"]
    prior_jobs = [
        job
        for job in store.list_jobs(
            project_id="project-1",
            states=(WorkflowJobState.QUEUED.value,),
        )
        if job.workflow_managed
    ]
    assert prior_jobs
    assert all(job.action not in RUNTIME_CONTROL_ACTIONS for job in prior_jobs)
    assert all(job.attempts == 0 for job in prior_jobs)
    revision_reads = 0

    def publication_revision():
        nonlocal revision_reads
        revision_reads += 1
        return None if revision_reads == unavailable_read else 1

    binding.tracker_publication_revision_source = publication_revision

    async def exercise():
        superseded = await runtime.reconcile_async()
        await asyncio.sleep(0)
        effects_before_retry = tuple(applied_actions)
        retained_before_retry = runtime.health_snapshot()["worker"]["retained"]
        prior_jobs_before_retry = tuple(
            (store.get(job.job_id).state, store.get(job.job_id).attempts)
            for job in prior_jobs
        )
        retry = await runtime.reconcile_async()
        await wait_for_runtime_effects(runtime)
        return (
            superseded,
            effects_before_retry,
            retained_before_retry,
            prior_jobs_before_retry,
            retry,
        )

    (
        superseded,
        effects_before_retry,
        retained_before_retry,
        prior_jobs_before_retry,
        retry,
    ) = asyncio.run(exercise())

    assert superseded["requires_reconcile"] is True
    assert superseded["worker"] == {
        "skipped": True,
        "reason": (
            "workflow publication requires reconciliation before durable admission"
        ),
        "projects": ["project-1"],
        "batch_saturated": False,
    }
    assert effects_before_retry == ()
    assert retained_before_retry == 0
    assert prior_jobs_before_retry == tuple(
        (WorkflowJobState.QUEUED, 0) for _job in prior_jobs
    )
    assert not retry.get("requires_reconcile", False)
    retry_generation = retry["projects"]["project-1"]["snapshot"]["generation"]
    assert retry_generation > prior_generation
    assert retry["worker"]["scheduled"] >= 1
    assert applied_actions
    runtime.close()
    store.close()


def test_source_supersession_marks_every_active_project(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "global-source-supersession.sqlite3"))
    first_tracker = NativeTracker(
        [make_issue("TASK-FIRST", state="Backlog", project_id="project-a")]
    )
    later_tracker = NativeTracker(
        [make_issue("TASK-LATER", state="Backlog", project_id="project-z")]
    )
    first_binding, first_journal = make_binding(
        tmp_path,
        first_tracker,
        store,
        "project-a",
    )
    later_binding, later_journal = make_binding(
        tmp_path,
        later_tracker,
        store,
        "project-z",
    )
    first_binding.tracker_publication_revision_source = lambda: None
    runtime = WorkflowRuntime(
        project_bindings={
            "project-a": first_binding,
            "project-z": later_binding,
        },
        store=store,
        journals={
            "project-a": first_journal,
            "project-z": later_journal,
        },
        mode="enforce",
        handlers=complete_handlers(),
        handler_coverage={
            action: ("project-a", "project-z") for action in RUNTIME_ACTIONS
        },
        liveness_controller=UniversalTotalityLivenessController(store=store),
        **accepted_projection_wiring(),
    )

    asyncio.run(runtime.start())
    report = runtime.reconcile()

    assert report["requires_reconcile"] is True
    assert report["projects"] == {
        project_id: {
            "publication_superseded": True,
            "reason": (
                "tracker publication revision unavailable during source collection"
            ),
        }
        for project_id in ("project-a", "project-z")
    }
    runtime.close()
    store.close()


def test_state_branch_diff_preflight_keeps_project_controls_responsive(tmp_path):
    task = make_issue("TASK-DIFF-PREFLIGHT", state="Backlog")
    store = WorkflowJobStore(str(tmp_path / "jobs-diff-preflight.sqlite3"))
    tracker = NativeTracker([task])
    tracker.authority_generation = "native-head:2"
    generation_reads = 0

    def current_generation():
        nonlocal generation_reads
        generation_reads += 1
        # The two project checkpoints see the generation-bound corpus cut;
        # the final publication preflight observes the concurrent change.
        return "native-head:2" if generation_reads <= 2 else "native-head:3"

    tracker.get_state_branch_generation = current_generation
    binding, journal = make_binding(tmp_path, tracker, store)
    project_lock = threading.RLock()
    binding.terminal_audit_publication_lock = lambda: project_lock
    diff_started = threading.Event()
    release_diff = threading.Event()

    def diff_authority(_expected, _current):
        diff_started.set()
        assert release_diff.wait(timeout=5)
        return frozenset({task.identifier})

    binding.tracker_terminal_authority_changes_source = diff_authority
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
        liveness_controller=UniversalTotalityLivenessController(store=store),
        **accepted_projection_wiring(),
    )

    asyncio.run(runtime.start())
    reports = []
    reconcile = threading.Thread(target=lambda: reports.append(runtime.reconcile()))
    reconcile.start()
    assert diff_started.wait(timeout=2)

    # A Git diff may block on the repository or transport.  It must not own
    # the project mutation fence or the runtime health lock while it waits.
    assert project_lock.acquire(timeout=0.2)
    try:
        tracker.issues["TASK-UNRELATED-CONTROL"] = make_issue(
            "TASK-UNRELATED-CONTROL", state="Open"
        )
        assert runtime.health_snapshot()["mode"] == "enforce"
    finally:
        project_lock.release()
        release_diff.set()
    reconcile.join(timeout=3)

    assert not reconcile.is_alive()
    assert reports[0]["projects"]["project-1"] == {
        "publication_superseded": True,
        "reason": "tracker authority changed before publication",
    }
    runtime.close()
    store.close()


@pytest.mark.parametrize("generation", (None, "unavailable", "unavailable:fetch"))
def test_enabled_native_tracker_missing_generation_fails_closed(
    tmp_path,
    generation,
):
    tracker = NativeTracker([make_issue("TASK-NATIVE-UNAVAILABLE")])
    tracker.fetch_all_issues_with_generation = lambda: (
        tracker.fetch_all_issues(),
        generation,
    )
    store = WorkflowJobStore(str(tmp_path / "native-unavailable.sqlite3"))
    binding, journal = make_binding(tmp_path, tracker, store)
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
        liveness_controller=UniversalTotalityLivenessController(store=store),
        **accepted_projection_wiring(),
    )

    asyncio.run(runtime.start())
    report = runtime.reconcile()

    assert report["projects"]["project-1"] == {
        "error": "WorkflowRuntimeError"
    }
    assert runtime.projections() == ()
    assert store.list_jobs(project_id="project-1") == ()
    runtime.close()
    store.close()


def test_disabled_native_tracker_uses_one_grouped_publication_refresh(tmp_path):
    tracker = NativeTracker([make_issue("TASK-NATIVE-LEGACY")])
    tracker.state_branch_enabled = False
    corpus_reads = 0
    original = tracker.fetch_all_issues

    def fetch_bound():
        nonlocal corpus_reads
        corpus_reads += 1
        return original(), None

    tracker.fetch_all_issues_with_generation = fetch_bound
    tracker.get_state_branch_generation = lambda: None
    store = WorkflowJobStore(str(tmp_path / "native-legacy.sqlite3"))
    binding, journal = make_binding(tmp_path, tracker, store)
    assert binding.tracker_publication_revision_source is not None
    assert binding.tracker_publication_revision_source() == 1
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
        liveness_controller=UniversalTotalityLivenessController(store=store),
        **accepted_projection_wiring(),
    )

    asyncio.run(runtime.start())
    report = runtime.reconcile()

    assert report["projects"]["project-1"]["snapshot"]["published"] is True
    assert corpus_reads == 2
    runtime.close()
    store.close()


def test_generic_unversioned_tracker_cannot_publish_enforce_cut(tmp_path):
    tracker = NativeTracker([make_issue("TASK-GENERIC-UNVERSIONED")])
    tracker.supports_generation_bound_reads = False
    store = WorkflowJobStore(str(tmp_path / "generic-unversioned.sqlite3"))
    binding, journal = make_binding(tmp_path, tracker, store)
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
        liveness_controller=UniversalTotalityLivenessController(store=store),
        **accepted_projection_wiring(),
    )

    asyncio.run(runtime.start())
    report = runtime.reconcile()

    assert report["projects"]["project-1"] == {
        "error": "WorkflowRuntimeError"
    }
    assert runtime.projections() == ()
    assert store.list_jobs(project_id="project-1") == ()
    runtime.close()
    store.close()


def test_terminal_publication_lock_health_metrics_are_bounded_and_complete(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "publication-lock-health.sqlite3"))
    tracker = NativeTracker([])
    binding, journal = make_binding(tmp_path, tracker, store)
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="shadow",
    )

    assert runtime.health_snapshot()["terminal_publication_lock"] == {
        "acquisitions": 0,
        "superseded": 0,
        "wait_seconds_total": 0.0,
        "wait_seconds_max": 0.0,
        "wait_seconds_last": 0.0,
        "hold_seconds_total": 0.0,
        "hold_seconds_max": 0.0,
        "hold_seconds_last": 0.0,
    }
    runtime._record_terminal_publication_lock_timing(
        wait_seconds=0.1,
        hold_seconds=0.2,
        superseded=True,
    )
    runtime._record_terminal_publication_lock_timing(
        wait_seconds=0.3,
        hold_seconds=0.0,
        superseded=False,
    )

    assert runtime.health_snapshot()["terminal_publication_lock"] == {
        "acquisitions": 2,
        "superseded": 1,
        "wait_seconds_total": pytest.approx(0.4),
        "wait_seconds_max": pytest.approx(0.3),
        "wait_seconds_last": pytest.approx(0.3),
        "hold_seconds_total": pytest.approx(0.2),
        "hold_seconds_max": pytest.approx(0.2),
        "hold_seconds_last": 0.0,
    }
    runtime.close()
    store.close()


def test_pause_racing_enabled_read_supersedes_stale_dispatchable_cut(tmp_path):
    from oompah.models import Project
    from oompah.projects import ProjectStore

    project_store = ProjectStore(
        path=str(tmp_path / "projects-pause.json"),
        repos_root=str(tmp_path / "repos"),
        worktree_root=str(tmp_path / "worktrees"),
    )
    project = Project(
        id="project-1",
        name="pause-race",
        repo_url="https://example.invalid/pause-race.git",
        repo_path=str(tmp_path / "repo"),
        branch="main",
    )
    project_store._projects[project.id] = project
    tracker = NativeTracker([make_issue("TASK-PAUSE-RACE", state="Backlog")])
    enabled_read = threading.Event()
    owner_attempted = threading.Event()
    owner_finished = threading.Event()

    def read_enabled():
        stale_enabled = not project.paused
        enabled_read.set()
        assert owner_attempted.wait(timeout=2)
        return stale_enabled

    original_bound = tracker.fetch_all_issues_with_generation

    def fetch_after_pause():
        assert owner_finished.wait(timeout=2)
        return original_bound()

    tracker.fetch_all_issues_with_generation = fetch_after_pause
    store = WorkflowJobStore(str(tmp_path / "pause-race.sqlite3"))
    binding, journal = make_binding(tmp_path, tracker, store)
    binding.dispatch_enabled = read_enabled
    binding.terminal_audit_publication_lock = (
        lambda: project_store.project_write_lock("project-1")
    )
    binding.workflow_authority_revision_source = (
        lambda: project_store.workflow_authority_revision("project-1")
    )
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
        liveness_controller=UniversalTotalityLivenessController(store=store),
        **accepted_projection_wiring(),
    )

    def pause_project():
        assert enabled_read.wait(timeout=2)
        owner_attempted.set()
        project_store.update("project-1", paused=True)
        owner_finished.set()

    owner = threading.Thread(target=pause_project)
    owner.start()
    asyncio.run(runtime.start())
    report = runtime.reconcile()
    owner.join(timeout=2)

    assert not owner.is_alive()
    assert report["projects"]["project-1"] == {
        "publication_superseded": True,
        "reason": "workflow authority changed before publication",
    }
    assert store.health_snapshot()["accepted_snapshot_generation"] == 0
    runtime.close()
    store.close()


def test_200_task_native_publication_never_refreshes_per_task_and_owner_is_bounded(
    tmp_path,
):
    from oompah.orchestrator import Orchestrator
    from oompah.projects import ProjectStore
    from oompah.terminal_transition_coordinator import (
        TerminalTransitionBusyError,
        TerminalTransitionCoordinator,
    )

    tasks = [
        make_issue(f"TASK-BULK-{index:03d}", state="Done")
        for index in range(200)
    ]
    store = WorkflowJobStore(str(tmp_path / "jobs-bulk-owner.sqlite3"))
    tracker = NativeTracker(tasks)
    detail_reads = 0
    invalidations = 0
    corpus_reads = 0
    original_detail = tracker.fetch_issue_detail
    original_corpus = tracker.fetch_all_issues

    def fetch_detail(identifier):
        nonlocal detail_reads
        detail_reads += 1
        return original_detail(identifier)

    def fetch_corpus():
        nonlocal corpus_reads
        corpus_reads += 1
        return original_corpus()

    def invalidate_read_cache():
        nonlocal invalidations
        invalidations += 1

    tracker.fetch_issue_detail = fetch_detail
    tracker.fetch_all_issues = fetch_corpus
    tracker.invalidate_read_cache = invalidate_read_cache
    tracker.fetch_all_issues_with_generation = lambda: (
        tracker.fetch_all_issues(),
        "native-bulk:1",
    )
    tracker.get_state_branch_generation = lambda: "native-bulk:1"
    binding, journal = make_binding(tmp_path, tracker, store)
    project_store = ProjectStore(
        path=str(tmp_path / "projects.json"),
        repos_root=str(tmp_path / "repos"),
        worktree_root=str(tmp_path / "worktrees"),
    )
    project_lock = project_store.project_write_lock("project-1")
    binding.terminal_audit_publication_lock = (
        lambda: project_store.project_write_lock("project-1")
    )
    binding.terminal_authority_revision_source = (
        lambda: project_store.terminal_authority_revision("project-1")
    )
    binding.workflow_authority_revision_source = (
        lambda: project_store.workflow_authority_revision("project-1")
    )
    binding.tracker_authority_revision_source = (
        tracker.get_state_branch_generation
    )
    binding.collector.sources[FactDomain.TERMINAL_AUDIT] = lambda issue: {
        "terminal_provenance": {
            "schema_version": 1,
            "marker_present": False,
            "project_id": "project-1",
            "task_id": issue.identifier,
            "retained": False,
            "malformed": False,
            "authority_generation": 0,
        }
    }
    lane_proofs = 0

    def prove_lane(_decision, _observed, _action):
        nonlocal lane_proofs
        lane_proofs += 1
        return True

    binding.terminal_audit_lane_proof_source = prove_lane
    controller = UniversalTotalityLivenessController(store=store)
    publish_entered = threading.Event()
    release_publish = threading.Event()

    owner_orchestrator = object.__new__(Orchestrator)
    owner_orchestrator.project_store = project_store
    owner_orchestrator.config = SimpleNamespace(owner_claim_ttl_hours=48)
    owner_orchestrator._owner_claims_lock = threading.RLock()
    owner_orchestrator.state = SimpleNamespace(owner_claims={})
    owner_orchestrator._persist_owner_claims_locked = lambda: True
    owner_orchestrator._scheduler_owns_project_issue = lambda *_args: False
    original_publish = store.publish_snapshot_generation

    def interleaved_publish(generation, callback, **kwargs):
        publish_entered.set()
        assert release_publish.wait(timeout=2)
        owner_orchestrator.grant_owner_claim(
            issue_id=tasks[0].id,
            project_id="project-1",
            owner_login="owner",
            claim_id="owner-raced-generation",
        )
        return original_publish(generation, callback, **kwargs)

    store.publish_snapshot_generation = interleaved_publish

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
    reports: list[dict[str, Any]] = []
    reconcile_thread = threading.Thread(
        target=lambda: reports.append(runtime.reconcile())
    )
    reconcile_thread.start()
    assert publish_entered.wait(timeout=2)
    detail_reads_before_publication = detail_reads

    class LockStore:
        def project_write_lock(self, _project_id):
            return project_lock

    operation_ran = False

    def owner_operation():
        nonlocal operation_ran
        operation_ran = True

    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=LockStore(),
        owner_control_lock_timeout_seconds=0.02,
    )
    started = time.monotonic()
    try:
        with pytest.raises(TerminalTransitionBusyError):
            coordinator._run_owner_control_serialized(
                "project-1", owner_operation
            )
    finally:
        release_publish.set()
        reconcile_thread.join(timeout=3)

    assert time.monotonic() - started < 0.5
    assert operation_ran is False
    assert not reconcile_thread.is_alive()
    assert reports[0]["projects"]["project-1"] == {
        "publication_superseded": True,
        "reason": "workflow authority changed before publication",
    }
    assert reports[0]["requires_reconcile"] is True
    assert store.health_snapshot()["accepted_snapshot_generation"] == 0
    assert corpus_reads == 1
    assert detail_reads == detail_reads_before_publication
    assert invalidations == 0
    assert lane_proofs == 0

    retried_owner_result = coordinator._run_owner_control_serialized(
        "project-1",
        lambda: owner_orchestrator.release_owner_claim(
            issue_id=tasks[0].id,
            project_id="project-1",
            expected_claim_id="owner-raced-generation",
        ),
    )
    assert retried_owner_result is True

    store.publish_snapshot_generation = original_publish
    detail_reads_before_retry = detail_reads
    retry_report = runtime.reconcile()
    assert retry_report["projects"]["project-1"]["snapshot"]["published"] is True
    assert corpus_reads == 2
    # Every owner and universal fact consumes the one generation-bound corpus;
    # dependency resolution must not reintroduce per-task detail reads.
    assert detail_reads - detail_reads_before_retry == 0
    assert invalidations == 0
    assert lane_proofs == 0
    runtime.close()
    store.close()


def test_real_terminal_revision_cas_fences_absent_to_retained_provenance(
    tmp_path,
):
    from oompah.projects import ProjectStore
    from oompah.provenance_suppression import load_provenance_suppression_status

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

    task = make_issue("TASK-REAL-TERMINAL-CAS", state="Done")
    tracker = AuditTracker([task])
    project_store = ProjectStore(
        path=str(tmp_path / "projects-terminal-cas.json"),
        repos_root=str(tmp_path / "repos"),
        worktree_root=str(tmp_path / "worktrees"),
    )
    metadata = TerminalAuditMetadataStore(
        tracker,
        project_store,
        "project-1",
    )
    store = WorkflowJobStore(str(tmp_path / "real-terminal-cas.sqlite3"))
    binding, journal = make_binding(tmp_path, tracker, store)
    binding.terminal_audit_publication_lock = (
        lambda: project_store.project_write_lock("project-1")
    )
    binding.terminal_authority_revision_source = (
        lambda: project_store.terminal_authority_revision("project-1")
    )

    def terminal_fact(issue):
        status = load_provenance_suppression_status(metadata, issue.identifier)
        marker = status.marker
        if marker is None:
            return {
                "terminal_provenance": {
                    "schema_version": 1,
                    "marker_present": False,
                    "project_id": "project-1",
                    "task_id": issue.identifier,
                    "retained": False,
                    "malformed": False,
                    "authority_generation": 0,
                }
            }
        return {
            "terminal_provenance": {
                "schema_version": 1,
                "marker_present": True,
                "marker_version": marker.version,
                "project_id": "project-1",
                "task_id": issue.identifier,
                "retained": marker.suppressed,
                "malformed": False,
                "authority_generation": marker.authority_generation,
                "authorized_by": marker.actor.identity,
                "actor_source": marker.actor.source,
                "marked_at": marker.marked_at,
                "updated_at": marker.updated_at,
            }
        }

    binding.collector.sources[FactDomain.TERMINAL_AUDIT] = terminal_fact
    original_publish = store.publish_snapshot_generation

    def retain_before_marker(generation, callback, **kwargs):
        mark_provenance_only(
            metadata,
            task.identifier,
            ContributorIdentity("owner", "api"),
            "Retain the completed revision as historical provenance.",
            now="2026-08-09T00:00:00+00:00",
        )
        return original_publish(generation, callback, **kwargs)

    store.publish_snapshot_generation = retain_before_marker
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
        liveness_controller=UniversalTotalityLivenessController(store=store),
        **accepted_projection_wiring(),
    )

    asyncio.run(runtime.start())
    report = runtime.reconcile()

    assert report["projects"]["project-1"] == {
        "publication_superseded": True,
        "reason": "terminal-audit disposition changed before publication",
    }
    assert store.health_snapshot()["accepted_snapshot_generation"] == 0

    store.publish_snapshot_generation = original_publish
    retry = runtime.reconcile()
    assert retry["projects"]["project-1"]["snapshot"]["published"] is True
    assert runtime.projections()[0]["reason_code"] == "terminal.provenance_retained"
    runtime.close()
    store.close()


def test_scoped_unrelated_active_audit_status_churn_keeps_review_publishable(
    tmp_path,
):
    audit_task = make_issue("TASK-AUDIT-CHURN", state="In Validation")
    review_task = make_issue("TASK-REVIEW-GREEN", state="In Review")
    store = WorkflowJobStore(str(tmp_path / "scoped-audit-churn.sqlite3"))
    settled_tasks = [
        make_issue(f"TASK-SETTLED-{index:03d}", state="Merged")
        for index in range(198)
    ]
    tracker = NativeTracker([audit_task, review_task, *settled_tasks])
    binding, journal = make_binding(tmp_path, tracker, store)
    workflow = binding.terminal_audit_workflow
    assert workflow is not None
    record = TerminalAuditRecord(
        audit_id="audit-churn",
        project_id="project-1",
        task_id=audit_task.identifier,
        target_state=TargetState.DONE,
        evidence_fingerprint=EvidenceFingerprint("a" * 64),
        request_state=RequestState.IN_PROGRESS,
        source_generation=1,
    )
    workflow.ensure(record)
    observed = {
        "phase": "active",
        "workflow_phase": "running",
        "audit_job_present": True,
        "audit_id": record.audit_id,
        "request_state": record.request_state.value,
        "target_state": record.target_state.value,
        "evidence_fingerprint": record.evidence_fingerprint.digest,
        "source_generation": record.source_generation,
        "audit_generation": workflow.generation(record),
        "actively_working": True,
    }
    binding.collector.sources[FactDomain.TERMINAL_AUDIT] = (
        lambda issue: observed
        if issue.identifier == audit_task.identifier
        else {"phase": "none"}
    )
    binding.collector.sources[FactDomain.REVIEW_CI] = (
        lambda issue: {"state": "open", "ci": "passed"}
        if issue.identifier == review_task.identifier
        else {"state": "open", "ci": "pending"}
    )
    revision = [0]
    binding.terminal_authority_revision_source = lambda: revision[0]
    binding.terminal_authority_changes_source = lambda expected: (
        revision[0],
        frozenset({audit_task.identifier}) if expected < revision[0] else frozenset(),
    )

    def diff_tracker_authority(expected, current):
        if expected == current:
            return frozenset()
        revision[0] += 1
        return frozenset({audit_task.identifier})

    binding.tracker_terminal_authority_changes_source = diff_tracker_authority
    binding.tracker_authority_changes_source = (
        lambda expected, current: (
            frozenset()
            if expected == current
            else frozenset({audit_task.identifier})
        )
    )
    proof_calls = []

    def prove_lane(decision, value, action):
        proof_calls.append((decision.task_id, action))
        return (
            decision.task_id == audit_task.identifier
            and value["audit_id"] == record.audit_id
            and store.terminal_audit_lane_materialized(
                project_id="project-1",
                task_id=audit_task.identifier,
                audit_id=record.audit_id,
                target_state=record.target_state.value,
                evidence_fingerprint=record.evidence_fingerprint.digest,
                audit_generation=workflow.generation(record),
                source_generation=record.source_generation,
                obligation_action=action or "terminal_audit",
            )
        )

    binding.terminal_audit_lane_proof_source = prove_lane
    controller = UniversalTotalityLivenessController(store=store)
    published_cuts = []

    def publish_projection(decisions, generation, **kwargs):
        published_cuts.append((tuple(decisions), generation, kwargs))
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
        projection_publisher=publish_projection,
        projection_epoch_source=lambda: 1,
    )
    asyncio.run(runtime.start())
    stable = runtime.reconcile()

    assert stable["projects"]["project-1"]["snapshot"]["published"] is True
    assert {decision["task_id"] for decision in runtime.projections()} == {
        audit_task.identifier,
        review_task.identifier,
    }

    tracker.fetch_all_issues_with_generation = lambda: (
        tracker.fetch_all_issues(),
        "test-native:1",
    )
    tracker.authority_generation = "test-native:2"
    report = runtime.reconcile()

    assert report["projects"]["project-1"]["snapshot"]["published"] is True
    assert report["projects"]["project-1"]["issues"] == 200
    assert "requires_reconcile" not in report
    assert proof_calls == [
        (audit_task.identifier, None),
        (audit_task.identifier, None),
    ]
    assert [
        job.action
        for job in store.list_jobs(
            project_id="project-1", task_id=review_task.identifier
        )
        if job.state in {WorkflowJobState.QUEUED, WorkflowJobState.RUNNING}
    ] == ["review_merge"]
    assert {
        (decision["task_id"], decision["reason_code"])
        for decision in runtime.projections()
    } == {(review_task.identifier, "review.ready_to_merge")}
    decisions, _generation, kwargs = published_cuts[-1]
    assert {decision.task_id for decision in decisions} == {
        review_task.identifier
    }
    assert kwargs["incomplete_keys"] == {
        ("project-1", audit_task.identifier)
    }
    assert kwargs["scan_complete"] is False
    runtime.close()
    store.close()


@pytest.mark.parametrize(
    "provider_state",
    ("authority_changed", "removed_before_publication", "missing_initially"),
)
def test_terminal_audit_authority_is_revalidated_before_snapshot_marker(
    tmp_path, monkeypatch, caplog, provider_state
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
            if provider_state == "removed_before_publication":
                binding.terminal_audit_proof_source = None
            else:
                # Metadata changes after the scan proof but before publication.
                current[0] = record_b
        return accepted

    binding.terminal_audit_proof_source = (
        None if provider_state == "missing_initially" else proof
    )
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
    with caplog.at_level(logging.INFO, logger="oompah.workflow_runtime"):
        report = runtime.reconcile()

    if provider_state in {"removed_before_publication", "missing_initially"}:
        expected_calls = [] if provider_state == "missing_initially" else [True]
        expected_fences = (
            [] if provider_state == "missing_initially" else [(False, False)]
        )
        assert proof_calls == expected_calls
        assert proof_fences == expected_fences
        assert len(publications) == int(provider_state != "missing_initially")
        assert report["projects"]["project-1"]["error"] == "WorkflowRuntimeError"
        assert "requires_reconcile" not in report
        assert any(
            record.levelno >= logging.ERROR
            and "Durable workflow publication failed" in record.message
            for record in caplog.records
        )
    else:
        assert len(publications) == 1
        assert proof_calls == [True, False]
        assert proof_fences == [(False, False), (True, True)]
        assert report["requires_reconcile"] is True
        assert report["reconcile_reason"] == "publication_authority_changed"
        assert report["projects"]["project-1"] == {
            "publication_superseded": True,
            "reason": "terminal-audit authority changed before publication",
        }
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


@pytest.mark.parametrize("provider_unavailable", (False, True))
def test_action_required_terminal_disposition_is_revalidated_at_marker(
    tmp_path, caplog, provider_unavailable
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

    proof_results = iter((False, True))

    def changed_disposition(_decision, value):
        assert value["action_required"] is True
        proof_fences.append(
            (store._conn.in_transaction, store._authority_lock_depth > 0)
        )
        return next(proof_results)

    binding.terminal_audit_snapshot_proof_source = (
        None if provider_unavailable else changed_disposition
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
    with caplog.at_level(logging.INFO, logger="oompah.workflow_runtime"):
        report = runtime.reconcile()

    if provider_unavailable:
        assert proof_fences == []
        assert report["projects"]["project-1"]["error"] == "WorkflowRuntimeError"
        assert any(
            record.levelno >= logging.ERROR
            and "Durable workflow publication failed" in record.message
            for record in caplog.records
        )
    else:
        assert proof_fences == [(True, True)]
        assert report["requires_reconcile"] is True
        assert report["reconcile_reason"] == "publication_authority_changed"
        assert report["projects"]["project-1"] == {
            "publication_superseded": True,
            "reason": "terminal-audit disposition changed before publication",
        }
        assert any(
            record.levelno == logging.INFO
            and "Durable workflow publication superseded" in record.message
            for record in caplog.records
        )
        assert not any(
            record.levelno >= logging.ERROR
            and "Durable workflow publication failed" in record.message
            for record in caplog.records
        )

        fresh = runtime.reconcile()

        assert proof_fences == [(True, True), (True, True)]
        assert fresh["projects"]["project-1"]["snapshot"]["published"] is True
        assert "requires_reconcile" not in fresh
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


def test_large_reconcile_cooperatively_releases_lifecycle_drain(tmp_path):
    """A current large-corpus fact pass cannot retain shutdown authority."""

    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker(
        [make_issue(f"TASK-{index:04d}") for index in range(256)]
    )
    binding, journal = make_binding(tmp_path, tracker, store)
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="shadow",
    )
    checkpoint_entered = threading.Event()
    release_checkpoint = threading.Event()
    checkpoint_calls = 0
    runtime_checkpoint = binding.collector.cooperative_checkpoint

    def blocked_checkpoint():
        nonlocal checkpoint_calls
        checkpoint_calls += 1
        if checkpoint_calls == 8:
            checkpoint_entered.set()
            assert release_checkpoint.wait(2), "lifecycle drain did not release scan"
        assert runtime_checkpoint is not None
        runtime_checkpoint()

    binding.collector.cooperative_checkpoint = blocked_checkpoint

    async def exercise():
        await runtime.start()
        reconcile = asyncio.create_task(runtime.reconcile_async())
        assert await asyncio.to_thread(checkpoint_entered.wait, 1)
        drain = asyncio.create_task(runtime.drain(timeout_seconds=1))
        for _ in range(100):
            if runtime._draining:
                break
            await asyncio.sleep(0)
        assert runtime._draining is True
        release_checkpoint.set()
        report = await asyncio.wait_for(reconcile, 1)
        assert await asyncio.wait_for(drain, 1) is True
        return report

    try:
        report = asyncio.run(exercise())
    finally:
        release_checkpoint.set()

    assert report["mode"] == "shadow"
    assert report["skipped"] is True
    assert report["reason"] == (
        "workflow reconciliation interrupted by lifecycle drain"
    )
    assert report["projects"]["project-1"]["issues"] == 256
    assert checkpoint_calls < 256
    runtime.close()
    store.close()


@pytest.mark.parametrize(
    ("domain", "state", "issue_type"),
    (
        ("review", "In Review", "task"),
        ("integration", "Ready to Integrate", "task"),
        ("epic", "Open", "epic"),
    ),
)
def test_each_domain_collector_cooperates_with_drain(
    tmp_path,
    domain,
    state,
    issue_type,
):
    """Distinct review/integration/epic collectors all receive the fence."""

    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker(
        [make_issue("DOMAIN-DRAIN", state=state, issue_type=issue_type)]
    )
    binding, journal = make_binding(tmp_path, tracker, store)
    if domain == "epic":
        selected_collector = binding.epic_collector
    else:
        selected_collector = WorkflowFactCollector(
            project_id="project-1",
            tracker=tracker,
            sources=binding.collector.sources,
        )
        getattr(binding, f"{domain}_controller").collector = selected_collector
    assert selected_collector is not None
    modes = {
        name: "shadow" if name == domain else "off"
        for name in ("implementation", "review", "integration", "epic")
    }
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="shadow",
        domain_modes=modes,
    )
    entered = threading.Event()
    release = threading.Event()
    runtime_checkpoint = selected_collector.cooperative_checkpoint
    assert runtime_checkpoint is not None

    def blocked_checkpoint():
        entered.set()
        assert release.wait(2), "lifecycle drain did not release domain collector"
        runtime_checkpoint()

    selected_collector.cooperative_checkpoint = blocked_checkpoint

    async def exercise():
        await runtime.start()
        reconcile = asyncio.create_task(runtime.reconcile_async())
        assert await asyncio.to_thread(entered.wait, 1)
        drain = asyncio.create_task(runtime.drain(timeout_seconds=1))
        for _ in range(100):
            if runtime._draining:
                break
            await asyncio.sleep(0)
        release.set()
        report = await asyncio.wait_for(reconcile, 1)
        assert await asyncio.wait_for(drain, 1) is True
        return report

    try:
        report = asyncio.run(exercise())
    finally:
        release.set()

    assert modes["implementation"] == "off"
    assert report["skipped"] is True
    assert report["projects"]["project-1"]["issues"] == 1
    runtime.close()
    store.close()


def test_revoked_retained_calls_preserve_fence_and_reserved_owner_control(
    tmp_path,
):
    """Stale calls stay fenced while priority-0 control uses its own slot."""

    assert "direct_owner_claim" in RUNTIME_CONTROL_ACTIONS
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([])
    binding, journal = make_binding(tmp_path, tracker, store)
    release_data = threading.Event()
    data_started = asyncio.Event()
    started_count = 0
    control_completed = asyncio.Event()

    class SleepingDataHandler(CompleteHandler):
        async def apply(self, context):
            nonlocal started_count
            if context.job.action == "standalone_delivery":
                started_count += 1
                if started_count == 3:
                    data_started.set()
                await asyncio.to_thread(release_data.wait)
            return await super().apply(context)

        async def build_transition(self, context, verification):
            if context.job.action == "direct_owner_claim":
                control_completed.set()
            return None

    for index in range(3):
        store.enqueue(
            WorkflowJobSpec(
                project_id="project-1",
                task_id=f"STALE-{index}",
                generation=f"stale-{index}",
                action="standalone_delivery",
                idempotency_key=f"stale-{index}",
            )
        )
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(SleepingDataHandler()),
        max_concurrent=4,
        control_reserved_slots=1,
    )

    async def exercise():
        await runtime.start()
        first = await runtime._run_due(("project-1",))
        await asyncio.wait_for(data_started.wait(), 1)
        running = store.list_jobs(states=(WorkflowJobState.RUNNING.value,))
        assert len(running) == 3
        for job in running:
            store.supersede(
                job.job_id,
                generation=job.generation,
                replacement_generation="lifecycle-final:Merged",
                reason="task became lifecycle-final",
            )
        store.enqueue(
            WorkflowJobSpec(
                project_id="project-1",
                task_id="OWNER-CLAIM",
                generation="owner-claim-1",
                action="direct_owner_claim",
                idempotency_key="owner-claim-1",
                priority=0,
            )
        )

        try:
            second = await runtime._run_due(("project-1",))
            await asyncio.wait_for(control_completed.wait(), 1)
            for _ in range(100):
                if runtime.health_snapshot()["worker"]["retained"] == 3:
                    break
                await asyncio.sleep(0.001)
            retained_before_release = runtime.health_snapshot()["worker"]
            assert retained_before_release["retained"] == 3
            assert retained_before_release["active"] == 3
        finally:
            release_data.set()
        await wait_for_runtime_effects(runtime)
        return first, second

    first, second = asyncio.run(exercise())

    assert first["scheduled"] == 3
    assert first["active_lanes"] == {"control": 0, "shared": 3}
    assert second["scheduled"] == 1
    assert second["active_lanes"]["shared"] == 3
    assert runtime.health_snapshot()["worker"]["retained"] == 0
    assert store.list_jobs(
        task_id="OWNER-CLAIM", states=(WorkflowJobState.COMPLETED.value,)
    )
    runtime.close()
    store.close()


def test_reserved_control_admission_uses_published_cut_during_inflight_scan(
    tmp_path,
):
    """An imperative owner claim cannot wait behind source collection."""

    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([])
    binding, journal = make_binding(tmp_path, tracker, store)
    control_completed = asyncio.Event()

    class ObservedControlHandler(CompleteHandler):
        async def apply(self, context):
            effect = await super().apply(context)
            if context.job.action == "direct_owner_claim":
                control_completed.set()
            return effect

    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(ObservedControlHandler()),
        max_concurrent=4,
        control_reserved_slots=1,
    )
    reconcile_entered = threading.Event()
    release_reconcile = threading.Event()
    runtime_checkpoint = binding.collector.cooperative_checkpoint
    assert runtime_checkpoint is not None

    def blocked_checkpoint():
        reconcile_entered.set()
        assert release_reconcile.wait(2), "world reconcile barrier timed out"
        runtime_checkpoint()

    async def exercise():
        await runtime.start()
        initial = await runtime.reconcile_async()
        assert initial["projects"]["project-1"]["snapshot"]["published"] is True
        binding.collector.cooperative_checkpoint = blocked_checkpoint
        tracker.issues["OWNER-CONTROL"] = make_issue(
            "OWNER-CONTROL", state="Open"
        )
        reconcile = asyncio.create_task(runtime.reconcile_async())
        assert await asyncio.to_thread(reconcile_entered.wait, 1)
        job = store.enqueue(
            WorkflowJobSpec(
                project_id="project-1",
                task_id="OWNER-CONTROL",
                generation="owner-control-1",
                action="direct_owner_claim",
                idempotency_key="owner-control-1",
                scheduling_lane="event:implementation:imperative",
                priority=0,
            )
        )
        try:
            admission = await runtime.continue_admission_async()
            await asyncio.wait_for(control_completed.wait(), 1)
            await wait_for_runtime_effects(runtime)
            assert not reconcile.done()
            completed = store.get(job.job_id)
        finally:
            release_reconcile.set()
        await asyncio.wait_for(reconcile, 2)
        return (
            admission,
            completed,
            initial["projects"]["project-1"]["snapshot"]["generation"],
        )

    try:
        admission, completed, published_generation = asyncio.run(exercise())
    finally:
        release_reconcile.set()

    assert admission["admission_only"] is True
    assert admission["requires_reconcile"] is False
    assert admission["snapshot_generation"] == published_generation
    assert admission["worker"]["scheduled"] == 1
    assert admission["worker"]["active_lanes"]["shared"] == 0
    assert completed.state is WorkflowJobState.COMPLETED
    runtime.close()
    store.close()


def test_control_admission_isolates_project_pause_read_failure(tmp_path):
    """One broken binding cannot starve another project's control event."""

    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    broken_binding, broken_journal = make_binding(
        tmp_path,
        NativeTracker([]),
        store,
        project_id="project-broken",
    )
    healthy_binding, healthy_journal = make_binding(
        tmp_path,
        NativeTracker([]),
        store,
        project_id="project-healthy",
    )

    def unavailable_pause_authority():
        raise OSError("pause authority unavailable")

    broken_binding.dispatch_enabled = unavailable_pause_authority
    job = store.enqueue(
        WorkflowJobSpec(
            project_id="project-healthy",
            task_id="OWNER-HEALTHY",
            generation="owner-healthy-1",
            action="direct_owner_claim",
            idempotency_key="owner-healthy-1",
            scheduling_lane="event:implementation:imperative",
            priority=0,
        )
    )
    runtime = WorkflowRuntime(
        project_bindings={
            "project-broken": broken_binding,
            "project-healthy": healthy_binding,
        },
        store=store,
        journals={
            "project-broken": broken_journal,
            "project-healthy": healthy_journal,
        },
        mode="enforce",
        handlers=complete_handlers(),
        handler_coverage={
            action: {"project-broken", "project-healthy"}
            for action in RUNTIME_ACTIONS
        },
    )

    async def exercise():
        await runtime.start()
        report = await runtime.continue_admission_async()
        await wait_for_runtime_effects(runtime)
        return report

    report = asyncio.run(exercise())

    assert report["projects"] == ["project-healthy"]
    assert report["worker"]["scheduled"] == 1
    assert store.get(job.job_id).state is WorkflowJobState.COMPLETED
    runtime.close()
    store.close()


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
    control_slot_replenished = asyncio.Event()
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

    jobs_by_action = {}
    for task_id, action, priority in (
        ("TASK-DELIVERY", "standalone_delivery", 0),
        ("TASK-REVOKE", "authority_revocation", 0),
        ("TASK-SUBMIT", "validation_submission", 10),
    ):
        jobs_by_action[action] = store.enqueue(
            WorkflowJobSpec(
                project_id="project-1",
                task_id=task_id,
                generation=f"generation-{task_id}",
                action=action,
                idempotency_key=f"effect-{task_id}",
                priority=priority,
            )
        )

    def observe_completion(result):
        if result.job_id == jobs_by_action["authority_revocation"].job_id:
            # The runtime invokes this observer only after removing the
            # completed task from its retained lane.  Waiting here, instead
            # of at the handler's earlier apply boundary, proves that the
            # reserved slot is observably available to the next admission.
            control_slot_replenished.set()

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
        effect_completion_observer=observe_completion,
    )

    async def exercise():
        await runtime.start()
        first = await asyncio.wait_for(runtime.reconcile_async(), 1)
        await asyncio.wait_for(delivery_started.wait(), 1)
        await asyncio.wait_for(
            completed_events["authority_revocation"].wait(),
            1,
        )
        await asyncio.wait_for(
            control_slot_replenished.wait(),
            1,
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

        def fetch_all_issues_with_generation(self):
            self.fetch_count += 1
            return super().fetch_all_issues_with_generation()

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
    replacement = store.allocate_snapshot_generation()
    assert replacement > generation
    assert store.accept_snapshot_generation(replacement)

    report = asyncio.run(runtime.continue_admission_async())

    assert report["requires_reconcile"] is True
    assert report["reason"] == "workflow admission cut is stale"
    assert store.get(job.job_id).state is WorkflowJobState.QUEUED
    runtime.close()
    store.close()


def test_fast_admission_uses_published_cut_during_unaccepted_scan_allocation(
    tmp_path,
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
    )

    async def exercise():
        await runtime.start()
        first = await runtime.reconcile_async()
        generation = first["projects"]["project-1"]["snapshot"]["generation"]
        job = store.enqueue(
            WorkflowJobSpec(
                project_id="project-1",
                task_id="CURRENT-PUBLISHED-CUT",
                generation="current-published-cut",
                action="review_refresh",
                idempotency_key="current-published-cut",
            )
        )
        replacement = store.allocate_snapshot_generation()
        assert replacement > generation
        assert store.published_snapshot_generation_is_current(generation)

        report = await runtime.continue_admission_async()
        await wait_for_runtime_effects(runtime)
        return generation, replacement, job, report

    generation, replacement, job, report = asyncio.run(exercise())

    assert report["requires_reconcile"] is False
    assert report["snapshot_generation"] == generation
    assert report["worker"]["scheduled"] == 1
    assert store.get(job.job_id).state is WorkflowJobState.COMPLETED
    health = store.health_snapshot()
    assert health["captured_snapshot_generation"] == replacement
    assert health["accepted_snapshot_generation"] == generation
    assert health["published_snapshot_generation"] == generation
    assert runtime.health_snapshot()["worker"]["retained"] == 0
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


@pytest.mark.parametrize(
    ("disposition", "state"),
    (
        (WorkflowRunDisposition.SUPERSEDED, WorkflowJobState.SUPERSEDED),
        (WorkflowRunDisposition.LEASE_LOST, WorkflowJobState.RUNNING),
        (WorkflowRunDisposition.RETRY_SCHEDULED, WorkflowJobState.RETRY_WAIT),
        (WorkflowRunDisposition.ACTION_REQUIRED, WorkflowJobState.EXHAUSTED),
    ),
)
def test_non_success_effect_exit_publishes_one_completion_wake(
    tmp_path, disposition, state
):
    store = WorkflowJobStore(str(tmp_path / "non-success.sqlite3"))
    tracker = NativeTracker([])
    binding, journal = make_binding(tmp_path, tracker, store)
    completions = []
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
        effect_completion_observer=completions.append,
    )
    result = WorkflowRunResult(
        disposition,
        "non-success-job",
        state,
        "non-success completion",
        1,
    )

    async def exercise():
        effect = asyncio.create_task(asyncio.sleep(0, result=result))
        with runtime._lock:
            runtime._effect_tasks[effect] = "shared"
        effect.add_done_callback(runtime._effect_finished)
        await effect
        await asyncio.sleep(0)

    asyncio.run(exercise())

    assert completions == [result]
    assert tuple(runtime._effect_results) == (result,)
    assert runtime.health_snapshot()["worker"]["retained"] == 0
    runtime.close()
    store.close()


def test_superseded_effect_wake_claims_next_current_durable_job(tmp_path):
    """A superseded retained call replenishes admission without a world scan."""

    store = WorkflowJobStore(str(tmp_path / "superseded-follow-up.sqlite3"))
    tracker = NativeTracker([])
    binding, journal = make_binding(tmp_path, tracker, store)
    first = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="OBSOLETE-PARENT",
            generation="obsolete-generation",
            action="review_refresh",
            idempotency_key="obsolete-parent",
            priority=0,
        )
    )
    second = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="CURRENT-EPIC",
            generation="current-generation",
            action="review_refresh",
            idempotency_key="current-epic",
            priority=1,
        )
    )
    generation = store.allocate_snapshot_generation()
    assert store.accept_snapshot_generation(generation) is True
    membership = store.reconcile_snapshot_membership(
        snapshot_generation=generation,
        authoritative_project_ids=("project-1",),
        expected_identities=(
            ("project-1", first.task_id),
            ("project-1", second.task_id),
        ),
    )
    assert membership.accepted is True
    published, _result = store.publish_snapshot_generation(
        generation,
        lambda: None,
    )
    assert published is True
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
        max_concurrent=2,
        control_reserved_slots=1,
    )
    runtime._refresh_admission_cut(
        {
            "projects": {
                "project-1": {
                    "snapshot": {"generation": generation, "published": True}
                }
            }
        },
        ("project-1",),
    )
    first_started = asyncio.Event()
    release_first = asyncio.Event()
    second_claimed = asyncio.Event()
    second_completed = asyncio.Event()
    completion_dispositions = []
    admission_wakes = []

    async def execute_claimed(job):
        if job.job_id == first.job_id:
            first_started.set()
            await release_first.wait()
            superseded = store.supersede(
                job.job_id,
                generation=job.generation,
                replacement_generation="replacement-generation",
                reason="obsolete owner completed after a newer generation",
            )
            return WorkflowRunResult(
                WorkflowRunDisposition.SUPERSEDED,
                superseded.job_id,
                superseded.state,
                "obsolete owner superseded",
                superseded.attempts,
            )
        second_claimed.set()
        completed = store.complete(job.job_id, str(job.lease_token or ""))
        second_completed.set()
        return WorkflowRunResult(
            WorkflowRunDisposition.COMPLETED,
            completed.job_id,
            completed.state,
            "current durable job completed",
            completed.attempts,
        )

    runtime.worker.execute_claimed = execute_claimed

    def completion_wake(result):
        completion_dispositions.append(result.disposition)
        admission_wakes.append(
            asyncio.create_task(runtime.continue_admission_async())
        )

    runtime._effect_completion_observer = completion_wake

    async def exercise():
        await runtime.start()
        first_admission = await runtime.continue_admission_async()
        await asyncio.wait_for(first_started.wait(), 1)
        assert store.get(second.job_id).state is WorkflowJobState.QUEUED
        release_first.set()
        await asyncio.wait_for(second_claimed.wait(), 1)
        await asyncio.wait_for(second_completed.wait(), 1)
        for _ in range(10):
            await asyncio.sleep(0)
            pending = [wake for wake in admission_wakes if not wake.done()]
            if pending:
                await asyncio.gather(*pending)
            if (
                runtime.health_snapshot()["worker"]["retained"] == 0
                and all(wake.done() for wake in admission_wakes)
            ):
                break
        return first_admission

    first_admission = asyncio.run(exercise())

    assert first_admission["worker"]["scheduled"] == 1
    assert store.get(first.job_id).state is WorkflowJobState.SUPERSEDED
    assert store.get(second.job_id).state is WorkflowJobState.COMPLETED
    assert completion_dispositions == [
        WorkflowRunDisposition.SUPERSEDED,
        WorkflowRunDisposition.COMPLETED,
    ]
    assert len(admission_wakes) == 2
    assert runtime.health_snapshot()["worker"]["retained"] == 0
    runtime.close()
    store.close()


def test_unaccepted_scan_allocation_does_not_stall_same_task_successor(
    tmp_path,
):
    """A slow captured scan cannot revoke the accepted published queue."""

    class BlockingTracker(NativeTracker):
        def __init__(self):
            super().__init__([])
            self.scan_entered = threading.Event()
            self.release_scan = threading.Event()

        def fetch_all_issues_with_generation(self):
            self.scan_entered.set()
            assert self.release_scan.wait(2), "replacement scan was not released"
            return super().fetch_all_issues_with_generation()

    project_id = "project-1"
    task_id = "CURRENT-EPIC"
    store = WorkflowJobStore(str(tmp_path / "allocated-scan.sqlite3"))
    tracker = BlockingTracker()
    binding, journal = make_binding(tmp_path, tracker, store)
    retained = store.enqueue(
        WorkflowJobSpec(
            project_id=project_id,
            task_id=task_id,
            generation="obsolete-event-generation",
            action="review_refresh",
            idempotency_key="obsolete-same-task-event",
            priority=0,
        )
    )
    published_generation = store.allocate_snapshot_generation()
    assert store.accept_snapshot_generation(published_generation)
    assert store.reconcile_snapshot_membership(
        snapshot_generation=published_generation,
        authoritative_project_ids=(project_id,),
        expected_identities=((project_id, task_id),),
    ).accepted
    cursor = store.activate_schedule(
        project_id=project_id,
        task_id=task_id,
        decision_revision="current-managed-decision",
        snapshot_generation=published_generation,
    )
    assert store.reconcile_schedule(
        project_id=project_id,
        task_id=task_id,
        snapshot_generation=published_generation,
        job_generation=cursor.job_generation,
        specs=(
            WorkflowJobSpec(
                project_id=project_id,
                task_id=task_id,
                generation=cursor.job_generation,
                action="review_refresh",
                idempotency_key="current-same-task-decision",
                priority=1,
            ),
        ),
    ).accepted
    successor = next(
        job
        for job in store.list_jobs(task_id=task_id)
        if job.workflow_managed
    )
    assert store.publish_snapshot_generation(
        published_generation, lambda: None
    )[0]

    runtime = WorkflowRuntime(
        project_bindings={project_id: binding},
        store=store,
        journals={project_id: journal},
        mode="enforce",
        handlers=complete_handlers(),
        max_concurrent=2,
        control_reserved_slots=1,
    )
    runtime._refresh_admission_cut(
        {
            "projects": {
                project_id: {
                    "snapshot": {
                        "generation": published_generation,
                        "published": True,
                    }
                }
            }
        },
        (project_id,),
    )
    retained_started = asyncio.Event()
    release_retained = asyncio.Event()
    successor_claimed = asyncio.Event()
    successor_completed = asyncio.Event()
    completion_wakes = []

    async def execute_claimed(job):
        if job.job_id == retained.job_id:
            retained_started.set()
            await release_retained.wait()
            superseded = store.supersede(
                job.job_id,
                generation=job.generation,
                replacement_generation=successor.generation,
                reason="obsolete event finished after current decision published",
            )
            return WorkflowRunResult(
                WorkflowRunDisposition.SUPERSEDED,
                superseded.job_id,
                superseded.state,
                "obsolete same-task event superseded",
                superseded.attempts,
            )
        assert job.job_id == successor.job_id
        successor_claimed.set()
        completed = store.complete(job.job_id, str(job.lease_token or ""))
        successor_completed.set()
        return WorkflowRunResult(
            WorkflowRunDisposition.COMPLETED,
            completed.job_id,
            completed.state,
            "current same-task decision completed",
            completed.attempts,
        )

    runtime.worker.execute_claimed = execute_claimed

    def completion_wake(_result):
        completion_wakes.append(
            asyncio.create_task(runtime.continue_admission_async())
        )

    runtime._effect_completion_observer = completion_wake

    async def exercise():
        await runtime.start()
        first_admission = await runtime.continue_admission_async()
        await asyncio.wait_for(retained_started.wait(), 1)
        replacement_scan = asyncio.create_task(runtime.reconcile_async())
        assert await asyncio.to_thread(tracker.scan_entered.wait, 1)
        captured_generation = store.health_snapshot()[
            "captured_snapshot_generation"
        ]
        assert captured_generation > published_generation
        assert store.health_snapshot()["accepted_snapshot_generation"] == (
            published_generation
        )

        # Model a genuine external tracker write while source collection is
        # blocked. It must still supersede the replacement scan, independently
        # of admission continuing from the previously accepted published cut.
        tracker.publication_revision += 1
        release_retained.set()
        await asyncio.wait_for(successor_claimed.wait(), 1)
        await asyncio.wait_for(successor_completed.wait(), 1)
        assert replacement_scan.done() is False
        tracker.release_scan.set()
        replacement_report = await asyncio.wait_for(replacement_scan, 2)
        for wake in tuple(completion_wakes):
            await asyncio.wait_for(asyncio.shield(wake), 1)
        return first_admission, replacement_report, captured_generation

    first_admission, replacement_report, captured_generation = asyncio.run(
        exercise()
    )

    assert first_admission["worker"]["scheduled"] == 1
    assert store.get(retained.job_id).state is WorkflowJobState.SUPERSEDED
    assert store.get(successor.job_id).state is WorkflowJobState.COMPLETED
    assert replacement_report["requires_reconcile"] is True
    assert replacement_report["projects"][project_id] == {
        "publication_superseded": True,
        "reason": "tracker authority changed during source collection",
    }
    health = store.health_snapshot()
    assert health["captured_snapshot_generation"] == captured_generation
    assert health["accepted_snapshot_generation"] == published_generation
    assert health["published_snapshot_generation"] == published_generation
    assert runtime.health_snapshot()["worker"]["retained"] == 0
    runtime.close()
    store.close()


@pytest.mark.parametrize("outcome", ("exception", "cancellation"))
@pytest.mark.parametrize("draining", (False, True))
def test_abnormal_effect_exit_publishes_one_cleanup_wake(
    tmp_path, outcome, draining
):
    store = WorkflowJobStore(str(tmp_path / f"{outcome}.sqlite3"))
    tracker = NativeTracker([])
    binding, journal = make_binding(tmp_path, tracker, store)
    completions = []
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
        effect_completion_observer=completions.append,
    )
    runtime._draining = draining

    async def fail():
        if outcome == "exception":
            raise RuntimeError("detached failure")
        await asyncio.Event().wait()

    async def exercise():
        effect = asyncio.create_task(fail())
        with runtime._lock:
            runtime._effect_tasks[effect] = "shared"
        effect.add_done_callback(runtime._effect_finished)
        if outcome == "cancellation":
            effect.cancel()
        with contextlib.suppress(asyncio.CancelledError, RuntimeError):
            await effect
        await asyncio.sleep(0)
        runtime._effect_finished(effect)

    asyncio.run(exercise())

    assert len(completions) == 1
    cleanup = completions[0]
    assert isinstance(cleanup, workflow_runtime_module.WorkflowEffectCleanup)
    assert cleanup.cancelled is (outcome == "cancellation")
    assert cleanup.error_type == (
        "RuntimeError" if outcome == "exception" else None
    )
    assert cleanup.job_id is None
    assert tuple(runtime._effect_results) == ()
    assert runtime.health_snapshot()["worker"]["retained"] == 0
    assert runtime.worker.active_count == 0
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


def test_quick_final_admission_preserves_one_queue_drain_reconcile(tmp_path):
    """A same-pass completion is consumed by the observer's next fast turn."""

    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    tracker = NativeTracker([])
    binding, journal = make_binding(tmp_path, tracker, store)
    store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="QUICK-FINAL-ADMISSION",
            generation="quick-final-admission",
            action="review_refresh",
            idempotency_key="quick-final-admission",
        )
    )
    generation = store.allocate_snapshot_generation()
    assert store.accept_snapshot_generation(generation) is True
    membership = store.reconcile_snapshot_membership(
        snapshot_generation=generation,
        authoritative_project_ids=("project-1",),
        expected_identities=(("project-1", "QUICK-FINAL-ADMISSION"),),
    )
    assert membership.accepted is True
    published, _result = store.publish_snapshot_generation(
        generation, lambda: None
    )
    assert published is True
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
    )
    runtime._refresh_admission_cut(
        {
            "projects": {
                "project-1": {
                    "snapshot": {"generation": generation, "published": True}
                }
            }
        },
        ("project-1",),
    )

    async def execute_immediately(job):
        completed = store.complete(job.job_id, str(job.lease_token or ""))
        return WorkflowRunResult(
            WorkflowRunDisposition.COMPLETED,
            completed.job_id,
            completed.state,
            "completed in same admission pass",
            completed.attempts,
        )

    runtime.worker.execute_claimed = execute_immediately
    completion_published = asyncio.Event()
    original_claim_next = runtime.worker.claim_next
    claimed_job = False
    post_schedule_empty_claims = 0
    completion_notifications = 0

    async def claim_after_callback_settlement(**kwargs):
        """Hold the first post-schedule miss until the callback has settled."""

        nonlocal claimed_job, post_schedule_empty_claims
        job = await original_claim_next(**kwargs)
        if job is not None:
            claimed_job = True
        elif claimed_job and post_schedule_empty_claims == 0:
            post_schedule_empty_claims += 1
            await asyncio.wait_for(completion_published.wait(), 1)
        return job

    runtime.worker.claim_next = claim_after_callback_settlement

    def observe_completion(_result):
        nonlocal completion_notifications
        completion_notifications += 1
        completion_published.set()

    async def exercise():
        runtime._effect_completion_observer = observe_completion
        await runtime.start()
        first = await runtime.continue_admission_async()
        pending_after_first = len(runtime._effect_results)
        retained_after_first = runtime.health_snapshot()["worker"]["retained"]
        second = await runtime.continue_admission_async()
        third = await runtime.continue_admission_async()
        return first, second, third, pending_after_first, retained_after_first

    first, second, third, pending_after_first, retained_after_first = asyncio.run(
        exercise()
    )

    assert first["worker"]["scheduled"] == 1
    assert first["worker"]["completed"] == 0
    assert first["worker"]["active"] == 0
    assert first["worker"]["active_lanes"] == {"control": 0, "shared": 0}
    assert first["requires_reconcile"] is False
    assert pending_after_first == 1
    assert retained_after_first == 0
    assert post_schedule_empty_claims == 1
    assert completion_notifications == 1
    assert second["worker"]["scheduled"] == 0
    assert second["worker"]["completed"] == 1
    assert second["worker"]["active"] == 0
    assert second["requires_reconcile"] is True
    assert second["reconcile_reason"] == "published_queue_drained"
    assert third["worker"]["completed"] == 0
    assert third["requires_reconcile"] is False
    assert sum(
        bool(report["requires_reconcile"])
        for report in (first, second, third)
    ) == 1
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


def test_detached_effect_heartbeats_and_drains_without_duplicate_apply(
    tmp_path, monkeypatch
):
    clock_lock = threading.Lock()
    clock = {"now": 1_000.0}

    def read_clock():
        with clock_lock:
            return clock["now"]

    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"), clock=read_clock)
    tracker = NativeTracker([])
    binding, journal = make_binding(tmp_path, tracker, store)
    started = asyncio.Event()
    release = asyncio.Event()
    renewal_entered = threading.Event()
    release_renewal = threading.Event()
    renewal_finished = threading.Event()
    renewal_calls = []
    renewed_jobs = []
    claimed_lease = []
    apply_calls = 0

    class LeaseHandler(CompleteHandler):
        async def apply(self, context):
            nonlocal apply_calls
            apply_calls += 1
            claimed_lease.append((context.job.job_id, context.job.lease_token))
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
    original_renew = store.renew

    def observed_renew(job_id, lease_token, *, lease_seconds, now=None):
        # Hold the worker's real heartbeat at the store boundary. This lets
        # the test capture the original lease before the renewal is committed
        # without estimating when a wall-clock heartbeat should have fired.
        renewal_calls.append((job_id, lease_token, lease_seconds))
        renewal_entered.set()
        assert release_renewal.wait(1), "heartbeat renewal barrier timed out"
        with clock_lock:
            clock["now"] += 0.05
        renewed = original_renew(
            job_id,
            lease_token,
            lease_seconds=lease_seconds,
            now=now,
        )
        renewed_jobs.append(renewed)
        renewal_finished.set()
        return renewed

    monkeypatch.setattr(store, "renew", observed_renew)
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
        assert await asyncio.to_thread(renewal_entered.wait, 1)
        leased = store.get(queued.job_id)
        assert claimed_lease == [(queued.job_id, leased.lease_token)]
        assert renewal_calls == [
            (queued.job_id, leased.lease_token, worker.lease_seconds)
        ]

        release_renewal.set()
        assert await asyncio.to_thread(renewal_finished.wait, 1)
        live = store.get(queued.job_id)
        assert live.state is WorkflowJobState.RUNNING
        assert live.lease_token == leased.lease_token
        assert live.lease_expires_at is not None
        assert leased.lease_expires_at is not None
        assert live.lease_expires_at > leased.lease_expires_at
        assert renewed_jobs[0].lease_expires_at is not None
        assert renewed_jobs[0].lease_expires_at > leased.lease_expires_at
        assert live.lease_expires_at >= renewed_jobs[0].lease_expires_at
        assert release.is_set() is False
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


@pytest.mark.timeout(20)
def test_large_corpus_restart_publishes_complete_snapshot_with_phase_telemetry(
    tmp_path,
):
    task_count = 1_878
    store = WorkflowJobStore(str(tmp_path / "large-restart.sqlite3"))

    class NoFanoutTracker(NativeTracker):
        def fetch_issue_detail(self, _identifier):
            raise AssertionError("runtime must reuse its authoritative issue index")

        def fetch_children(self, _identifier):
            raise AssertionError("runtime must reuse its authoritative child index")

    tasks = [
        make_issue(
            f"TASK-LARGE-{index:04d}",
            state="Backlog",
            parent_id="EPIC-LARGE" if index < 128 else None,
        )
        for index in range(task_count - 1)
    ]
    tasks.append(
        make_issue("EPIC-LARGE", state="Backlog", issue_type="epic")
    )
    tracker = NoFanoutTracker(tasks)
    binding, journal = make_binding(tmp_path, tracker, store)

    class ScopedLandingCollector:
        project_id = "project-1"

        def __init__(self):
            self.active = False
            self.entered = 0
            self.exited = 0

        @contextlib.contextmanager
        def observation_scope(self):
            self.entered += 1
            self.active = True
            try:
                yield
            finally:
                self.active = False
                self.exited += 1

        def collect_many(self, requests):
            assert self.active
            return tuple(
                LandingFact(
                    request.source,
                    request.target,
                    request.revision,
                    {"kind": "source_unavailable"},
                    datetime.now(timezone.utc).isoformat(),
                    self.project_id,
                    state=LandingState.UNKNOWN,
                    error_code="test_unavailable",
                )
                for request in requests
            )

    landing = ScopedLandingCollector()
    binding.collector.landing_collector = landing
    binding.epic_collector.landing_collector = landing
    controller = UniversalTotalityLivenessController(
        store=store,
        liveness_max_task_records=2_000,
    )
    controller.restore_liveness_state(None)
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

    assert report["projects"]["project-1"]["issues"] == task_count
    assert report["projects"]["project-1"]["snapshot"]["published"] is True
    assert report["liveness"]["scan_complete"] is True
    assert runtime.restart_reconstruction_pending is False
    phases = report["reconciliation_phases"]
    assert phases["total_seconds"] < 120
    assert set(phases["seconds"]) >= {
        "issue_loading",
        "issue_index",
        "liveness_facts",
        "authority_correction",
        "snapshot_publication",
    }
    assert phases["projects"]["project-1"]["liveness_facts"] > 0
    assert phases["projects"]["project-1"]["epic"] > 0
    assert (landing.entered, landing.exited, landing.active) == (1, 1, False)
    runtime.close()
    store.close()


@pytest.mark.timeout(20)
def test_repeated_scoped_mutations_converge_and_keep_control_responsive(tmp_path):
    tasks = [
        make_issue("TASK-GATED", state="In Review"),
        *[
            make_issue(f"TASK-MUTATION-{index:02d}", state="Backlog")
            for index in range(32)
        ],
    ]
    store = WorkflowJobStore(str(tmp_path / "scoped-retry.sqlite3"))
    tracker = ScopedMutationTracker(tasks)
    binding, journal = make_binding(tmp_path, tracker, store)
    mutation_count = 20
    mutation_ids = iter(
        tuple(
            f"TASK-MUTATION-{index % 4:02d}"
            for index in range(mutation_count)
        )
    )
    gated_calls = 0

    def mutate_during_collection(issue):
        nonlocal gated_calls
        if issue.identifier != "TASK-GATED":
            return {"version": 1}
        gated_calls += 1
        mutation_id = next(mutation_ids, None)
        if mutation_id is not None:
            tracker.mutate(mutation_id)
        return {"version": tracker._generation}

    binding.collector.sources[FactDomain.CONFIG] = mutate_during_collection
    original_checkpoint = binding.collector.cooperative_checkpoint

    def slow_cooperative_scan():
        time.sleep(0.001)
        assert original_checkpoint is not None
        original_checkpoint()

    binding.collector.cooperative_checkpoint = slow_cooperative_scan

    old_generation = store.allocate_snapshot_generation()
    assert store.accept_snapshot_generation(old_generation)
    assert store.reconcile_snapshot_membership(
        snapshot_generation=old_generation,
        authoritative_project_ids=("project-1",),
        expected_identities=(("project-1", "TASK-OLD-CUT"),),
    ).accepted
    old_cursor = store.activate_schedule(
        project_id="project-1",
        task_id="TASK-OLD-CUT",
        decision_revision="old-admissible-decision",
        snapshot_generation=old_generation,
    )
    old_spec = WorkflowJobSpec(
        project_id="project-1",
        task_id="TASK-OLD-CUT",
        generation=old_cursor.job_generation,
        action="review_refresh",
        idempotency_key="old-admissible-job",
    )
    old_job = store.enqueue(old_spec)
    assert store.reconcile_schedule(
        project_id="project-1",
        task_id="TASK-OLD-CUT",
        snapshot_generation=old_generation,
        job_generation=old_cursor.job_generation,
        specs=(old_spec,),
    ).accepted
    assert store.publish_snapshot_generation(old_generation, lambda: None)[0]

    controller = UniversalTotalityLivenessController(
        store=store,
        liveness_max_task_records=64,
    )
    controller.restore_liveness_state(None)
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
        liveness_controller=controller,
        **accepted_projection_wiring(),
    )
    runtime._refresh_admission_cut(
        {
            "projects": {
                "project-1": {
                    "snapshot": {
                        "generation": old_generation,
                        "published": True,
                    }
                }
            }
        },
        ("project-1",),
    )
    stale_claimed = threading.Event()
    original_execute_claimed = runtime.worker.execute_claimed

    async def record_claim(job):
        if job.job_id == old_job.job_id:
            stale_claimed.set()
        return await original_execute_claimed(job)

    runtime.worker.execute_claimed = record_claim

    gate_repo = tmp_path / "gate-repo"
    gate_repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=gate_repo, check=True)
    subprocess.run(["git", "config", "user.name", "oompah"], cwd=gate_repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "oompah@example.invalid"],
        cwd=gate_repo,
        check=True,
    )
    (gate_repo / "Makefile").write_text("test:\n\t@true\n", encoding="utf-8")
    subprocess.run(["git", "add", "Makefile"], cwd=gate_repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "gate baseline"], cwd=gate_repo, check=True)
    safety_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=gate_repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run(["git", "checkout", "-q", "-b", "work"], cwd=gate_repo, check=True)
    gate_started = tmp_path / "gate-started"
    gate_release = tmp_path / "gate-release"
    gate = BranchQualityGate(
        str(tmp_path / "quality-gate.json"),
        safety_head=safety_head,
        sandbox_launcher=lambda command, _snapshot, _root: [
            "/bin/sh",
            "-c",
            command,
        ],
    )
    gate_results = []

    def run_gate():
        gate_results.append(
            gate.run(
                repo_path=str(gate_repo),
                repo_identity="https://example.invalid/oompah/gate",
                target_branch="main",
                work_branch="work",
                command=(
                    f"touch {shlex.quote(str(gate_started))}; "
                    f"while [ ! -f {shlex.quote(str(gate_release))} ]; do "
                    "sleep 0.01; done"
                ),
            )
        )

    gate_thread = threading.Thread(target=run_gate, daemon=True)
    gate_thread.start()
    gate_start_deadline = time.monotonic() + 5
    while not gate_started.exists() and time.monotonic() < gate_start_deadline:
        time.sleep(0.01)
    assert gate_started.exists(), "independent branch quality gate did not start"

    async def exercise():
        await runtime.start()
        reconcile = asyncio.create_task(runtime.reconcile_async())
        try:
            await asyncio.sleep(0.02)
            assert runtime.health_snapshot()["mode"] == "enforce"
            assert runtime.restart_reconstruction_pending is True
            assert runtime.health_snapshot()["worker"]["retained"] == 0
            assert store.get(old_job.job_id).state is WorkflowJobState.QUEUED
            assert stale_claimed.is_set() is False
            return await asyncio.wait_for(reconcile, 10)
        finally:
            await asyncio.gather(reconcile, return_exceptions=True)

    try:
        report = asyncio.run(exercise())
        assert gate_thread.is_alive()
        assert gate_release.exists() is False
    finally:
        gate_release.write_text("release\n", encoding="utf-8")
        gate_thread.join(timeout=5)
        BranchQualityGate.cleanup_active_processes()

    assert report["projects"]["project-1"]["snapshot"]["published"] is True
    assert report["projects"]["project-1"]["authority_corrections"] == mutation_count
    assert runtime.restart_reconstruction_pending is False
    assert gated_calls >= mutation_count + 1
    assert stale_claimed.is_set() is False
    assert store.get(old_job.job_id).state is WorkflowJobState.SUPERSEDED
    assert len(gate_results) == 1 and gate_results[0].passed
    health = controller.liveness_snapshot()
    assert health.total_nonterminal_count == len(tasks)
    assert health.tracked_task_count == len(tasks)
    jobs = store.list_jobs(limit=1_000)
    assert len({job.job_id for job in jobs}) == len(jobs)
    runtime.close()
    store.close()


def test_final_preflight_scoped_mutation_retries_before_effect_publication(tmp_path):
    task = make_issue("TASK-FINAL-BARRIER", state="Backlog")
    store = WorkflowJobStore(str(tmp_path / "final-barrier.sqlite3"))
    tracker = ScopedMutationTracker([task])
    binding, journal = make_binding(tmp_path, tracker, store)
    controller = UniversalTotalityLivenessController(store=store)
    controller.restore_liveness_state(None)
    observed_titles: list[str] = []
    binding.collector.sources[FactDomain.CONFIG] = lambda issue: (
        observed_titles.append(issue.title) or {"version": tracker._generation}
    )
    original_publish = store.publish_snapshot_generation
    publication_calls = 0

    def mutate_at_final_barrier(generation, publish, **kwargs):
        nonlocal publication_calls
        publication_calls += 1
        if publication_calls <= 3:
            tracker.mutate(task.identifier)
        return original_publish(generation, publish, **kwargs)

    store.publish_snapshot_generation = mutate_at_final_barrier
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

    assert publication_calls == 4
    assert report["projects"]["project-1"]["snapshot"]["published"] is True
    assert report["reconciliation_phases"]["scoped_publication_retries"] == 3
    assert observed_titles[-1].endswith("generation 4")
    assert runtime.restart_reconstruction_pending is False
    assert store.list_jobs(limit=100) == ()
    runtime.close()
    store.close()


def _scoped_publication_runtime(tmp_path, tracker, store):
    binding, journal = make_binding(tmp_path, tracker, store)
    binding.collector.sources[FactDomain.REVIEW_CI] = lambda issue: (
        {"state": "open", "ci": "passed"}
        if issue.identifier == "TASK-READY-EXACT"
        else {"state": "open", "ci": "pending"}
    )
    controller = UniversalTotalityLivenessController(store=store)
    controller.restore_liveness_state(None)
    runtime = WorkflowRuntime(
        project_bindings={"project-1": binding},
        store=store,
        journals={"project-1": journal},
        mode="enforce",
        handlers=complete_handlers(),
        liveness_controller=controller,
        **accepted_projection_wiring(),
    )
    return runtime, controller


def test_final_publication_ignores_continuous_unrelated_tracker_churn(tmp_path):
    target = make_issue("TASK-READY-EXACT", state="In Review")
    unrelated = make_issue("TASK-UNRELATED-CHURN", state="Backlog")
    tracker = ScopedMutationTracker([target, unrelated])
    store = WorkflowJobStore(str(tmp_path / "continuous-scoped-churn.sqlite3"))
    runtime, controller = _scoped_publication_runtime(tmp_path, tracker, store)
    original_publish = store.publish_snapshot_generation
    publication_calls = 0

    def churn_at_every_final_barrier(generation, publish, **kwargs):
        nonlocal publication_calls
        publication_calls += 1
        for _ in range(64):
            tracker.mutate(unrelated.identifier)
        return original_publish(generation, publish, **kwargs)

    store.publish_snapshot_generation = churn_at_every_final_barrier
    asyncio.run(runtime.start())
    report = runtime.reconcile()

    assert publication_calls == 1
    assert report["projects"]["project-1"]["snapshot"]["published"] is True
    phases = report["reconciliation_phases"]
    assert phases["scoped_publication_retries"] == 0
    assert phases["tracker_scoped_publication_advances"] == 1
    assert phases["tracker_scoped_publication_exclusions"] == 1
    active = [
        job
        for job in store.list_jobs(
            project_id="project-1", task_id=target.identifier
        )
        if job.state in ACTIVE_JOB_STATES
    ]
    assert [job.action for job in active] == ["review_merge"]
    assert not store.list_jobs(
        project_id="project-1", task_id=unrelated.identifier
    )
    assert {row["task_id"] for row in runtime.projections()} == {
        target.identifier
    }
    health = controller.liveness_snapshot()
    assert health.scan_complete is False
    assert health.status != "overdue"
    assert runtime.health_snapshot()["last_reconcile"][
        "reconciliation_phases"
    ]["tracker_scoped_publication_exclusions"] == 1
    runtime.close()
    store.close()


def test_final_publication_retries_relevant_exact_task_drift(tmp_path):
    target = make_issue("TASK-READY-EXACT", state="In Review")
    unrelated = make_issue("TASK-UNRELATED-CHURN", state="Backlog")
    tracker = ScopedMutationTracker([target, unrelated])
    store = WorkflowJobStore(str(tmp_path / "relevant-final-drift.sqlite3"))
    runtime, _controller = _scoped_publication_runtime(tmp_path, tracker, store)
    original_publish = store.publish_snapshot_generation
    publication_calls = 0

    def mutate_target_once(generation, publish, **kwargs):
        nonlocal publication_calls
        publication_calls += 1
        if publication_calls == 1:
            tracker.mutate(target.identifier)
        return original_publish(generation, publish, **kwargs)

    store.publish_snapshot_generation = mutate_target_once
    asyncio.run(runtime.start())
    report = runtime.reconcile()

    assert publication_calls == 2
    assert report["projects"]["project-1"]["snapshot"]["published"] is True
    assert report["reconciliation_phases"]["scoped_publication_retries"] == 1
    assert report["reconciliation_phases"][
        "tracker_scoped_publication_advances"
    ] == 0
    active = [
        job
        for job in store.list_jobs(
            project_id="project-1", task_id=target.identifier
        )
        if job.state in ACTIVE_JOB_STATES
    ]
    assert len(active) == 1
    assert active[0].action == "review_merge"
    assert len({job.idempotency_key for job in active}) == 1
    runtime.close()
    store.close()


def test_task_scoped_publication_restart_reuses_one_exact_job(tmp_path):
    target = make_issue("TASK-READY-EXACT", state="In Review")
    unrelated = make_issue("TASK-UNRELATED-CHURN", state="Backlog")
    tracker = ScopedMutationTracker([target, unrelated])
    path = tmp_path / "scoped-publication-restart.sqlite3"
    store = WorkflowJobStore(str(path))
    runtime, _controller = _scoped_publication_runtime(tmp_path, tracker, store)
    original_publish = store.publish_snapshot_generation
    first_publication = True

    def churn_before_restart(generation, publish, **kwargs):
        nonlocal first_publication
        if first_publication:
            first_publication = False
            tracker.mutate(unrelated.identifier)
        return original_publish(generation, publish, **kwargs)

    store.publish_snapshot_generation = churn_before_restart
    asyncio.run(runtime.start())
    first = runtime.reconcile()
    first_active = [
        job
        for job in store.list_jobs(
            project_id="project-1", task_id=target.identifier
        )
        if job.state in ACTIVE_JOB_STATES
    ]
    assert first["reconciliation_phases"][
        "tracker_scoped_publication_exclusions"
    ] == 1
    assert len(first_active) == 1
    first_job_id = first_active[0].job_id
    runtime.close()
    store.close()

    reopened = WorkflowJobStore(str(path))
    restarted, restarted_controller = _scoped_publication_runtime(
        tmp_path, tracker, reopened
    )
    asyncio.run(restarted.start())
    second = restarted.reconcile()
    second_active = [
        job
        for job in reopened.list_jobs(
            project_id="project-1", task_id=target.identifier
        )
        if job.state in ACTIVE_JOB_STATES
    ]

    assert second["projects"]["project-1"]["snapshot"]["published"] is True
    assert second["reconciliation_phases"]["scoped_publication_retries"] == 0
    assert len(second_active) == 1
    assert second_active[0].job_id == first_job_id
    assert restarted_controller.liveness_snapshot().scan_complete is True
    assert restarted.restart_reconstruction_pending is False
    restarted.close()
    reopened.close()


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
    assert runtime.restart_reconstruction_pending

    first = runtime.reconcile()
    first_health = controller.liveness_snapshot()
    second = runtime.reconcile()
    second_health = controller.liveness_snapshot()

    assert first["liveness"]["scan_complete"] is True
    assert first_health.restart_reconstruction_pending is False
    assert not runtime.restart_reconstruction_pending
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


def test_overdue_restart_still_allows_stable_base_scan_to_publish(tmp_path):
    current = [datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)]
    store = WorkflowJobStore(str(tmp_path / "overdue-restart.sqlite3"))
    tracker = NativeTracker([make_issue("TASK-OVERDUE", state="Backlog")])
    binding, journal = make_binding(tmp_path, tracker, store)
    controller = UniversalTotalityLivenessController(
        store=store,
        clock=lambda: current[0],
    )
    controller.restore_liveness_state(None)
    current[0] = current[0].replace(minute=3)
    assert controller.liveness_snapshot().status == "restart_overdue"
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

    assert report["projects"]["project-1"]["snapshot"]["published"] is True
    assert report["reconciliation_phases"][
        "historical_restart_deadline_seconds_remaining"
    ] < 0
    assert runtime.restart_reconstruction_pending is False
    runtime.close()
    store.close()


@pytest.mark.parametrize("mode", ("off", "shadow"))
def test_non_enforce_runtime_never_fences_audits_for_liveness_restore(mode):
    runtime = object.__new__(WorkflowRuntime)
    runtime.mode = mode
    runtime.liveness_controller = MagicMock()

    assert runtime.restart_reconstruction_pending is False
    runtime.liveness_controller.liveness_snapshot.assert_not_called()


def test_restart_reconstruction_admission_fails_closed_on_health_read_error():
    runtime = object.__new__(WorkflowRuntime)
    runtime.mode = "enforce"
    runtime.liveness_controller = MagicMock()
    runtime.liveness_controller.liveness_snapshot.side_effect = RuntimeError(
        "unavailable"
    )

    assert runtime.restart_reconstruction_pending is True


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


def test_restart_liveness_accepts_protected_imperative_implementation_job(
    tmp_path,
):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    task = make_issue("TASK-PROTECTED", state="Open")
    tracker = NativeTracker([task])
    binding, journal = make_binding(tmp_path, tracker, store)
    protected = binding.implementation_controller.schedule_event(
        project_id="project-1",
        task_id=task.identifier,
        action=ImplementationAction.RETRY,
        payload={
            "owner_id": "prior-agent",
            "work_branch": task.work_branch,
            "expected_status": task.state,
        },
    )
    controller = UniversalTotalityLivenessController(store=store)
    controller.restore_liveness_state(None)
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
    report = runtime.reconcile()
    health = controller.liveness_snapshot()

    assert first["liveness"]["scan_complete"] is False
    assert report["projects"]["project-1"]["implementation"]["truncated"] is False
    assert report["liveness"]["scan_complete"] is True
    assert health.required_recovery_count == 1
    assert health.materialized_recovery_count == 1
    assert runtime.restart_reconstruction_pending is False
    assert store.get(protected.job_id).state is WorkflowJobState.QUEUED
    runtime.close()
    store.close()


def test_direct_validation_attempt_cannot_strand_terminal_audit_liveness(tmp_path):
    class MutableNativeTracker(NativeTracker):
        def __init__(self, issues):
            super().__init__(issues)
            self.updates = []

        def update_issue(self, identifier, **fields):
            self.updates.append((identifier, dict(fields)))
            current = self.issues[identifier]
            self.issues[identifier] = replace(current, state=fields["status"])

    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    task = make_issue("TASK-NAKED-VALIDATION", state="In Progress")
    task.assignment_id = "generation-1"
    tracker = MutableNativeTracker([task])
    binding, journal = make_binding(tmp_path, tracker, store)
    direct = TransitionIntent(
        project_id="project-1",
        task_id=task.identifier,
        expected_status=task.state,
        expected_version=issue_authority_version(task),
        requested_status="In Validation",
        actor="api",
        authority=TransitionAuthority.API,
        reason_code="api.status_updated",
        idempotency_key="naked-validation-runtime",
        originating_job="api:naked-validation-runtime",
        evidence_generation=task.assignment_id,
        exact_head="a" * 40,
    )

    outcome = asyncio.run(binding.transition_service.execute(direct))

    assert outcome.reason_code == "transition.audit_staging_required"
    assert tracker.issues[task.identifier].state == "In Progress"
    assert tracker.updates == []

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
    first = controller.liveness_snapshot()
    projection = runtime.projections()[0]

    assert projection["status"] == "In Progress"
    assert projection["durable_jobs"] == ["implementation_recovery"]
    assert first.required_recovery_count == 1
    assert first.materialized_recovery_count == 0
    assert not [
        job
        for job in store.list_jobs(task_id=task.identifier)
        if job.action == "terminal_audit"
    ]

    runtime.reconcile()
    converged = controller.liveness_snapshot()
    assert converged.scan_complete
    assert converged.reconciliation_complete
    assert converged.required_recovery_count == 1
    assert converged.materialized_recovery_count == 1
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


def test_advanced_direct_owner_branch_retires_stale_submission_across_restart(
    tmp_path,
):
    path = tmp_path / "jobs.sqlite3"
    old_head = "a" * 40
    current_head = "c" * 40
    task = make_issue("TASK-DIRECT-OWNER-ADVANCED", state="In Progress")
    task.head_sha = old_head
    task.assignment_id = "direct-owner-claim"
    tracker = NativeTracker([task])
    config = {
        "version": 1,
        "implementation_pending_action": "validation_submission",
        "implementation_pending_payload": {
            "owner_claim_id": task.assignment_id,
            "owner_login": "project-owner",
            "head_sha": old_head,
            "work_branch": task.work_branch,
        },
    }

    def install_sources(binding):
        binding.collector.sources[FactDomain.CONFIG] = lambda _issue: dict(config)
        binding.collector.sources[FactDomain.IMPLEMENTATION_AUTHORITY] = (
            lambda _issue: {
                "owner_id": "project-owner",
                "generation": task.assignment_id,
                "ownership_source": "direct_owner",
                "lease_expires_at": "2099-01-01T00:00:00+00:00",
            }
        )

    store = WorkflowJobStore(str(path))
    binding, journal = make_binding(tmp_path, tracker, store)
    install_sources(binding)
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
    stale = next(
        job
        for job in store.list_jobs(task_id=task.identifier)
        if job.action == ImplementationAction.VALIDATION_SUBMISSION.value
    )

    # A stable remote observation has proven the direct-owner branch is now
    # beyond the retained accepted head. The production config source parks
    # that metadata and publishes no replacement action or fabricated head.
    config.clear()
    config.update(
        {
            "version": 1,
            "accepted_submission_recovery_state": (
                "accepted_submission_branch_advanced"
            ),
            "accepted_submission_head": old_head,
            "accepted_submission_branch_head": current_head,
        }
    )
    reports = [runtime.reconcile() for _ in range(3)]
    parked_health = controller.liveness_snapshot()
    active_stale = [
        job
        for job in store.list_jobs(task_id=task.identifier)
        if job.action == ImplementationAction.VALIDATION_SUBMISSION.value
        and job.state in ACTIVE_JOB_STATES
    ]

    assert store.get(stale.job_id).state is WorkflowJobState.SUPERSEDED
    assert active_stale == []
    assert all(
        report["projects"]["project-1"]["implementation"]["jobs_required"]
        == 0
        for report in reports
    )
    assert parked_health.scan_complete
    assert parked_health.reconciliation_complete
    assert parked_health.required_recovery_count == 0
    assert parked_health.materialized_recovery_count == 0
    runtime.close()
    journal.close()
    store.close()

    # Restart must preserve the retirement. It may not rediscover the old
    # accepted head merely because process-local controller state disappeared.
    reopened_store = WorkflowJobStore(str(path))
    reopened_binding, reopened_journal = make_binding(
        tmp_path, tracker, reopened_store
    )
    install_sources(reopened_binding)
    reopened_controller = UniversalTotalityLivenessController(
        store=reopened_store
    )
    reopened_runtime = WorkflowRuntime(
        project_bindings={"project-1": reopened_binding},
        store=reopened_store,
        journals={"project-1": reopened_journal},
        mode="enforce",
        handlers=complete_handlers(),
        liveness_controller=reopened_controller,
        **accepted_projection_wiring(),
    )
    asyncio.run(reopened_runtime.start())
    reopened_runtime.reconcile()
    assert not [
        job
        for job in reopened_store.list_jobs(task_id=task.identifier)
        if job.action == ImplementationAction.VALIDATION_SUBMISSION.value
        and job.state in ACTIVE_JOB_STATES
    ]

    # Only the explicit exact-head resubmit changes accepted authority. It is
    # idempotently materialized once and is the sole current liveness proof.
    task.head_sha = current_head
    task.integration = replace(task.integration, head_sha=current_head)
    config.clear()
    config.update(
        {
            "version": 1,
            "accepted_submission_recovery_state": (
                "accepted_submission_exact_direct_owner"
            ),
            "accepted_submission_head": current_head,
            "accepted_submission_branch_head": current_head,
            "implementation_pending_action": "validation_submission",
            "implementation_pending_payload": {
                "owner_claim_id": task.assignment_id,
                "owner_login": "project-owner",
                "head_sha": current_head,
                "work_branch": task.work_branch,
            },
        }
    )
    resubmits = [reopened_runtime.reconcile() for _ in range(3)]
    resubmit_health = reopened_controller.liveness_snapshot()
    current_jobs = [
        job
        for job in reopened_store.list_jobs(task_id=task.identifier)
        if job.action == ImplementationAction.VALIDATION_SUBMISSION.value
        and job.state in ACTIVE_JOB_STATES
    ]

    assert len(current_jobs) == 1
    assert current_jobs[0].expected_head_sha == current_head
    assert current_jobs[0].payload["owner_claim_id"] == task.assignment_id
    assert sum(
        report["projects"]["project-1"]["implementation"]["jobs_created"]
        for report in resubmits
    ) == 1
    assert resubmit_health.scan_complete
    assert resubmit_health.reconciliation_complete
    assert resubmit_health.required_recovery_count == 1
    assert resubmit_health.materialized_recovery_count == 1
    reopened_runtime.close()
    reopened_journal.close()
    reopened_store.close()


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


def test_runtime_retires_exhausted_landing_refresh_for_retained_provenance(
    tmp_path,
):
    database = tmp_path / "jobs.sqlite3"
    store = WorkflowJobStore(str(database))
    project_id = "project-1"
    task_id = "TASK-PROVENANCE"
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
                idempotency_key="runtime:retained-provenance",
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
    tracker = NativeTracker([done])
    binding, journal = make_binding(tmp_path, tracker, store)
    binding.collector.sources[FactDomain.TERMINAL_AUDIT] = lambda _issue: {
        "terminal_provenance": {
            "schema_version": 1,
            "marker_present": True,
            "marker_version": 1,
            "project_id": project_id,
            "task_id": task_id,
            "retained": True,
            "malformed": False,
            "authority_generation": 0,
            "authorized_by": "owner",
            "actor_source": "api",
            "marked_at": "2026-08-09T00:00:00+00:00",
            "updated_at": "2026-08-09T00:00:00+00:00",
        }
    }
    binding.terminal_audit_snapshot_proof_source = (
        lambda _decision, observed: (
            binding.collector.sources[FactDomain.TERMINAL_AUDIT](done)
            == observed
        )
    )
    binding.terminal_audit_publication_lock = lambda: threading.RLock()
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
    assert runtime.projections()[0]["reason_code"] == "terminal.provenance_retained"
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

    reopened_store = WorkflowJobStore(str(database))
    restarted_binding, restarted_journal = make_binding(
        tmp_path,
        tracker,
        reopened_store,
    )
    restarted_binding.collector.sources[FactDomain.TERMINAL_AUDIT] = (
        binding.collector.sources[FactDomain.TERMINAL_AUDIT]
    )
    restarted_binding.terminal_audit_snapshot_proof_source = (
        lambda _decision, observed: (
            restarted_binding.collector.sources[FactDomain.TERMINAL_AUDIT](done)
            == observed
        )
    )
    restarted_binding.terminal_audit_publication_lock = lambda: threading.RLock()
    restarted_runtime = WorkflowRuntime(
        project_bindings={project_id: restarted_binding},
        store=reopened_store,
        journals={project_id: restarted_journal},
        mode="enforce",
        handlers=complete_handlers(),
        liveness_controller=UniversalTotalityLivenessController(
            store=reopened_store
        ),
        **accepted_projection_wiring(),
    )

    asyncio.run(restarted_runtime.start())
    restart_report = restarted_runtime.reconcile()

    assert restart_report["projects"][project_id]["snapshot"]["published"]
    assert restarted_runtime.projections()[0]["reason_code"] == (
        "terminal.provenance_retained"
    )
    assert not reopened_store.current_exhausted_jobs(
        project_id=project_id, task_id=task_id
    )
    restarted_runtime.close()
    reopened_store.close()


@pytest.mark.parametrize(
    ("authority_change", "seed_exhaustion"),
    (
        ("retained_unchanged", True),
        ("retained_to_revision", True),
        ("absent_to_retained", True),
        ("absent_unchanged", False),
        ("absent_to_retained", False),
        ("revision_unchanged", False),
        ("absent_revision_unchanged", False),
    ),
)
def test_production_provenance_publication_is_exact(
    tmp_path,
    authority_change,
    seed_exhaustion,
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
        workflow_engine_mode = "enforce"
        workflow_domain_modes = {}
        workflow_runtime_decision_limit = 17
        workflow_runtime_batch_size = 9
        workflow_runtime_max_concurrent = 4
        workflow_runtime_control_reserved_slots = 1

    project_id = "legacy"
    task_id = "TASK-PROVENANCE-RACE"
    task = make_issue(task_id, state="Done", project_id=project_id)
    task.integration = IntegrationRecord(
        state="integrated",
        task_branch=task_id,
        base_branch="main",
        head_sha="a" * 40,
        integrated_sha="a" * 40,
    )
    tracker = AuditTracker([task])
    project_store = ProjectStore()
    store = WorkflowJobStore(str(tmp_path / "production-race.sqlite3"))
    exhausted = None
    if seed_exhaustion:
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
                    idempotency_key="runtime:retained-provenance-race",
                ),
            ),
        ).accepted
        assert store.publish_snapshot_generation(first, lambda: None)[0]
        exhausted = store.claim_next(
            lease_owner="failed-worker",
            lease_seconds=30,
            task_id=task_id,
        )
        assert exhausted is not None
        exhausted = store.fail(
            exhausted.job_id,
            exhausted.lease_token,
            category=WorkflowFailureCategory.PERMANENT,
            error="refresh failed permanently",
            retryable=False,
        )

    metadata = TerminalAuditMetadataStore(tracker, project_store, project_id)
    owner = ContributorIdentity("owner", "api")
    if not authority_change.startswith("absent"):
        mark_provenance_only(
            metadata,
            task_id,
            owner,
            "Retain completed work as historical provenance.",
            now="2026-08-09T00:00:00+00:00",
        )
    if authority_change in {"revision_unchanged", "absent_revision_unchanged"}:
        authorize_new_revision(
            metadata,
            task_id,
            owner,
            "Owner authorized a new revision before collection.",
            now="2026-08-09T00:01:00+00:00",
        )
    terminal_workflow = TerminalAuditWorkflow(store)
    controller = UniversalTotalityLivenessController(store=store)

    class OrchestratorDouble:
        config = Config()
        workflow_job_store = store
        terminal_audit_workflow = terminal_workflow
        workflow_action_handlers = complete_handlers()
        workflow_controller = controller
        _state_path = str(tmp_path / "service-state.json")
        _work_decision_publication_epoch = 1

        def __init__(self):
            self.project_store = project_store
            self.tracker = tracker
            self.state = SimpleNamespace(retry_attempts={})

        def _audit_store(self, _issue):
            return metadata

        def _workflow_shadow_sources(self, issue):
            return Orchestrator._workflow_shadow_sources(self, issue)

        def _workflow_shadow_running_entry(self, _issue, *, auditor=None):
            return None

        def _publish_work_decisions(self, *_args, **_kwargs):
            return SimpleNamespace(
                accepted=True,
                rejection=None,
                commit_memory=lambda: None,
                rollback=lambda: None,
            )

    runtime = WorkflowRuntime.from_orchestrator(
        OrchestratorDouble(),
        state_dir=tmp_path,
        mode="enforce",
    )
    binding = runtime.project_bindings[project_id]
    production_proof = binding.terminal_audit_snapshot_proof_source
    assert production_proof is not None
    proof_fences = []

    def change_before_proof(decision, observed):
        proof_fences.append(
            (store._conn.in_transaction, store._authority_lock_depth > 0)
        )
        provenance = observed["terminal_provenance"]
        if authority_change == "retained_to_revision":
            assert provenance["marker_present"] is True
            assert provenance["retained"] is True
            authorize_new_revision(
                metadata,
                task_id,
                owner,
                "Owner authorized a new revision before publication.",
                now="2026-08-09T00:01:00+00:00",
            )
        elif authority_change == "absent_to_retained":
            assert provenance == {
                "schema_version": 1,
                "marker_present": False,
                "project_id": project_id,
                "task_id": task_id,
                "retained": False,
                "malformed": False,
                "authority_generation": 0,
            }
            mark_provenance_only(
                metadata,
                task_id,
                owner,
                "Owner retained historical provenance before publication.",
                now="2026-08-09T00:01:00+00:00",
            )
        elif authority_change == "absent_unchanged":
            assert provenance["marker_present"] is False
            assert provenance["retained"] is False
            assert provenance["authority_generation"] == 0
        elif authority_change in {
            "revision_unchanged",
            "absent_revision_unchanged",
        }:
            assert provenance["marker_present"] is True
            assert provenance["retained"] is False
            assert provenance["authority_generation"] == 1
        else:
            assert provenance["marker_present"] is True
            assert provenance["retained"] is True
        return production_proof(decision, observed)

    binding.terminal_audit_snapshot_proof_source = change_before_proof

    asyncio.run(runtime.start())
    report = runtime.reconcile()

    assert proof_fences == [(True, True)]
    if authority_change in {"retained_to_revision", "absent_to_retained"}:
        assert report["requires_reconcile"] is True
        assert report["reconcile_reason"] == "publication_authority_changed"
        assert report["projects"][project_id] == {
            "publication_superseded": True,
            "reason": "terminal-audit disposition changed before publication",
        }
        health = store.health_snapshot()
        assert health["accepted_snapshot_generation"] == (
            health["published_snapshot_generation"]
        )
        if exhausted is not None:
            assert store.current_exhausted_jobs(
                project_id=project_id,
                task_id=task_id,
            ) == (exhausted,)
            retirement = store._conn.execute(  # noqa: SLF001 - rollback proof
                "SELECT COUNT(*) AS count FROM workflow_job_retirements "
                "WHERE job_id = ?",
                (exhausted.job_id,),
            ).fetchone()
            assert retirement["count"] == 0
        else:
            assert health["accepted_snapshot_generation"] == 0
            staged_jobs = store.list_jobs(
                project_id=project_id,
                task_id=task_id,
                actions=("integration_landing_refresh",),
            )
            assert {job.state for job in staged_jobs} == {
                WorkflowJobState.SUPERSEDED
            }
            assert store.claim_next(
                lease_owner="stale-effect-probe",
                lease_seconds=30,
                task_id=task_id,
            ) is None
        if authority_change == "absent_to_retained":
            binding.terminal_audit_snapshot_proof_source = production_proof
            retry_report = runtime.reconcile()

            assert retry_report["projects"][project_id]["snapshot"]["published"]
            assert runtime.projections()[0]["reason_code"] == (
                "terminal.provenance_retained"
            )
            assert not store.current_exhausted_jobs(
                project_id=project_id,
                task_id=task_id,
            )
            if exhausted is not None:
                retry_retirement = store._conn.execute(  # noqa: SLF001
                    "SELECT authority_kind FROM workflow_job_retirements "
                    "WHERE job_id = ?",
                    (exhausted.job_id,),
                ).fetchone()
                assert retry_retirement["authority_kind"] == "managed_zero_job"
            else:
                prior_staged_jobs = store.list_jobs(
                    project_id=project_id,
                    task_id=task_id,
                    actions=("integration_landing_refresh",),
                )
                assert {job.state for job in prior_staged_jobs} == {
                    WorkflowJobState.SUPERSEDED
                }
                assert store.claim_next(
                    lease_owner="post-retain-effect-probe",
                    lease_seconds=30,
                    task_id=task_id,
                ) is None
    else:
        assert report["projects"][project_id]["snapshot"]["published"] is True
        if authority_change == "retained_unchanged":
            assert runtime.projections()[0]["reason_code"] == (
                "terminal.provenance_retained"
            )
            assert not store.current_exhausted_jobs(
                project_id=project_id,
                task_id=task_id,
            )
            assert exhausted is not None
            retirement = store._conn.execute(  # noqa: SLF001 - exact proof
                "SELECT authority_kind FROM workflow_job_retirements "
                "WHERE job_id = ?",
                (exhausted.job_id,),
            ).fetchone()
            assert retirement["authority_kind"] == "managed_zero_job"
        else:
            assert runtime.projections()[0]["durable_jobs"] == [
                "integration_landing_refresh"
            ]
            assert store.list_jobs(
                project_id=project_id,
                task_id=task_id,
                actions=("integration_landing_refresh",),
            )
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
    original_fetch = tracker.fetch_all_issues_with_generation

    def blocked_fetch():
        fetch_entered.set()
        assert release_fetch.wait(5), "tracker barrier timed out"
        return original_fetch()

    tracker.fetch_all_issues_with_generation = blocked_fetch
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
    original_fetch = tracker.fetch_all_issues_with_generation

    def blocked_fetch():
        source_entered.set()
        assert release_source.wait(5), "tracker barrier timed out"
        return original_fetch()

    tracker.fetch_all_issues_with_generation = blocked_fetch
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

    tracker.fetch_all_issues_with_generation = failing_fetch
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


def test_enforce_runtime_refreshes_remote_target_before_landing_decision(
    tmp_path, monkeypatch
):
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

        def epic_branch_name(self, epic_id):
            return f"epic-{epic_id}"

    class Config:
        workflow_engine_mode = "enforce"
        workflow_runtime_decision_limit = 20
        workflow_runtime_batch_size = 4

    issue = Issue(
        id="TOP",
        identifier="TOP",
        title="TOP",
        description="remote landing runtime fixture",
        state="In Progress",
        project_id="project-1",
        issue_type="epic",
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
    composed_task = Issue(
        id="COMPOSED-TASK",
        identifier="COMPOSED-TASK",
        title="COMPOSED-TASK",
        description="parent-scoped composed landing guard fixture",
        state="Done",
        project_id="project-1",
        issue_type="task",
        parent_id="TOP",
    )
    review_task = Issue(
        id="LANDED-REVIEW",
        identifier="LANDED-REVIEW",
        title="LANDED-REVIEW",
        description="review-owned terminal guard fixture",
        state="In Review",
        project_id="project-1",
        issue_type="task",
        work_branch="epic-TOP",
        target_branch="main",
        review_number="804",
        review_head=epic_head,
    )
    class FreshBlankProjectTracker(NativeTracker):
        blank_project_reads = False

        def fetch_issue_detail(self, identifier):
            current = super().fetch_issue_detail(identifier)
            if current is None or not self.blank_project_reads:
                return current
            return replace(current, project_id=None)

    tracker = FreshBlankProjectTracker(
        [issue, child, landed_task, composed_task, review_task]
    )
    store = WorkflowJobStore(str(tmp_path / "remote-jobs.sqlite3"))
    composed_landing = LandingFact(
        composed_task.identifier,
        "epic-TOP",
        epic_head,
        {
            "kind": "git_ancestry",
            "source_sha": epic_head,
            "target_sha": epic_head,
        },
        "2026-08-09T14:00:00+00:00",
        "project-1",
        state=LandingState.LANDED,
        durable=True,
    )
    store.record_landing_facts(
        project_id="project-1",
        task_id="TOP",
        facts=(composed_landing.to_dict(),),
    )

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
    async def stage_terminal_transition(**kwargs):
        kwargs["current_issue"].state = "In Validation"
        return SimpleNamespace(
            success=True,
            audit_id="audit-review-terminal",
            reason=None,
        )

    terminal_coordinator = SimpleNamespace(
        request_transition=AsyncMock(side_effect=stage_terminal_transition)
    )
    runtime = WorkflowRuntime.from_orchestrator(
        orchestrator,
        state_dir=tmp_path,
        terminal_transition_coordinator=terminal_coordinator,
    )
    orchestrator.workflow_runtime = runtime

    binding = runtime.project_bindings["project-1"]
    review_fact_version = {"value": 1}
    binding.review_controller.collector.sources[FactDomain.REVIEW_CI] = (
        lambda _issue: {
            "state": "merged",
            "present": True,
            "review_id": "804",
            "source_branch": "epic-TOP",
            "target_branch": "main",
            "head_sha": epic_head,
            "ci": "passed",
            "mergeable": True,
            "provider": "test",
            "fact_version": review_fact_version["value"],
        }
    )

    class LandedReviewCollector:
        project_id = "project-1"

        @staticmethod
        def collect_many(requests):
            return tuple(
                LandingFact(
                    request.source,
                    request.target,
                    request.revision,
                    {
                        "kind": "git_ancestry",
                        "source_sha": request.revision,
                        "target_sha": merged,
                    },
                    "2026-08-11T00:00:00+00:00",
                    "project-1",
                    state=LandingState.LANDED,
                    durable=True,
                )
                for request in requests
            )

    binding.review_controller.collector.landing_collector = (
        LandedReviewCollector()
    )
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
        expected_status="In Progress",
        expected_version=issue_authority_version(issue),
        requested_status="Merged",
        actor="oompah",
        authority=TransitionAuthority.ORCHESTRATOR,
        reason_code="terminal.immediate_target_landing_proven",
        idempotency_key="auto-close-guard-projection",
        originating_job="epic-auto-close-job",
        exact_head=epic_head,
        precondition_revision=decision.evidence_revision,
    )

    assert guard(intent) is None
    assert binding.epic_controller._latest == {"UNRELATED": sentinel}
    mismatched_epic_intent = TransitionIntent(
        **{
            **intent.to_dict(),
            "exact_head": "f" * 40,
        }
    )
    assert guard(mismatched_epic_intent) == "epic canonical landing head changed"
    unbound_epic_intent = TransitionIntent(
        **{
            **intent.to_dict(),
            "exact_head": None,
        }
    )
    assert guard(unbound_epic_intent) == "epic canonical landing head changed"
    non_orchestrator_intent = TransitionIntent(
        **{
            **intent.to_dict(),
            "authority": TransitionAuthority.INTEGRATOR,
        }
    )
    assert (
        guard(non_orchestrator_intent)
        == "epic auto-close requires orchestrator authority"
    )

    issue.parent_id = "PARENT"
    parented_intent = TransitionIntent(
        **{
            **intent.to_dict(),
            "expected_version": issue_authority_version(issue),
        }
    )
    assert guard(parented_intent) == (
        "headless nested epic cannot use canonical landing fallback"
    )
    issue.parent_id = None

    issue.state = "In Review"
    wrong_state_intent = TransitionIntent(
        **{
            **intent.to_dict(),
            "expected_status": "In Review",
            "expected_version": issue_authority_version(issue),
        }
    )
    assert guard(wrong_state_intent) == "headless root epic is not In Progress"
    issue.state = "In Progress"

    issue.review_head = epic_head
    headed_decision = EpicWorkflowController(
        collector=binding.epic_controller.collector,
        store=binding.epic_controller.store,
    ).evaluate((issue,), persist_evidence=False).tasks[0].decision
    headed_intent = TransitionIntent(
        **{
            **intent.to_dict(),
            "expected_version": issue_authority_version(issue),
            "precondition_revision": headed_decision.evidence_revision,
        }
    )
    assert guard(headed_intent) is None
    stale_headed_intent = TransitionIntent(
        **{
            **headed_intent.to_dict(),
            "exact_head": "f" * 40,
        }
    )
    assert guard(stale_headed_intent) == "epic mutable landing head changed"
    issue.review_head = None

    binding.epic_collector.default_branch = "changed-target"
    assert guard(intent) == "epic workflow evidence or containment changed"
    binding.epic_collector.default_branch = "main"

    canonical_selector = workflow_runtime_module.epic_immediate_target_landings
    monkeypatch.setattr(
        workflow_runtime_module,
        "epic_immediate_target_landings",
        lambda current: (
            *canonical_selector(current),
            *canonical_selector(current),
        ),
    )
    assert guard(intent) == "epic canonical landing authority changed"
    monkeypatch.setattr(
        workflow_runtime_module,
        "epic_immediate_target_landings",
        lambda current: tuple(
            replace(landing, project_id="other-project", evidence_revision=None)
            for landing in canonical_selector(current)
        ),
    )
    assert guard(intent) == "epic canonical landing authority changed"
    monkeypatch.setattr(
        workflow_runtime_module,
        "epic_immediate_target_landings",
        canonical_selector,
    )

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

    composed_decision = binding.integration_controller.evaluate(
        (composed_task,)
    ).tasks[0].decision
    composed_intent = TransitionIntent(
        project_id="project-1",
        task_id=composed_task.identifier,
        expected_status="Done",
        expected_version=issue_authority_version(composed_task),
        requested_status="Merged",
        actor="oompah",
        authority=TransitionAuthority.INTEGRATOR,
        reason_code="terminal.immediate_target_landing_proven",
        idempotency_key="composed-landed-task-guard",
        originating_job="composed-landed-task-job",
        exact_head=epic_head,
        precondition_revision=composed_decision.evidence_revision,
    )

    assert composed_decision.durable_jobs == ("parent_rollup_review",)
    tracker.blank_project_reads = True
    assert guard(composed_intent) is None
    assert tracker.issues[composed_task.identifier].project_id == "project-1"
    mismatched_composed_intent = TransitionIntent(
        **{
            **composed_intent.to_dict(),
            "exact_head": "f" * 40,
        }
    )
    assert guard(mismatched_composed_intent) == "task composed landing head changed"
    tracker.blank_project_reads = False

    # Review-owned terminalization uses a different fact projection than the
    # integration parent-rollup lane, despite sharing the public reason code.
    # The production guard must resolve the immutable originating action and
    # compare the review revision with fresh review facts.
    review_decision = binding.review_controller.evaluate(
        (review_task,)
    ).tasks[0].decision
    assert review_decision.durable_jobs == ("review_terminal_stage",)
    review_job = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id=review_task.identifier,
            generation="review-terminal-generation",
            action="review_terminal_stage",
            idempotency_key="review-terminal-runtime-guard",
            expected_evidence_revision=review_decision.evidence_revision,
        )
    )
    review_intent = TransitionIntent(
        project_id="project-1",
        task_id=review_task.identifier,
        expected_status="In Review",
        expected_version=issue_authority_version(review_task),
        requested_status="Merged",
        actor="oompah",
        authority=TransitionAuthority.ORCHESTRATOR,
        reason_code="terminal.immediate_target_landing_proven",
        idempotency_key="review-terminal-runtime-transition",
        originating_job=review_job.job_id,
        evidence_generation=review_job.generation,
        exact_head=epic_head,
        precondition_revision=review_decision.evidence_revision,
    )

    assert guard(review_intent) is None
    review_fact_version["value"] = 2
    assert guard(review_intent) == "review landing evidence changed"
    review_fact_version["value"] = 1
    wrong_review_generation = TransitionIntent(
        **{
            **review_intent.to_dict(),
            "evidence_generation": "wrong-review-generation",
        }
    )
    assert (
        guard(wrong_review_generation)
        == "review terminal workflow authority changed"
    )
    review_outcome = asyncio.run(
        binding.transition_service.execute(review_intent)
    )
    assert review_outcome.reason_code == "transition.terminal_staged"
    terminal_coordinator.request_transition.assert_awaited_once()
    terminal_request = terminal_coordinator.request_transition.await_args.kwargs
    assert terminal_request["workflow_revision"] == (
        review_decision.evidence_revision
    )

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


def test_epic_facts_use_the_generation_bound_project_cut_without_refetch(tmp_path):
    stale = make_issue("EPIC-RACE", state="In Progress", issue_type="epic")
    current = make_issue("EPIC-RACE", state="Done", issue_type="epic")

    class RacingTracker(NativeTracker):
        def fetch_all_issues_enriched(self):
            return [stale]

        fetch_all_issues = fetch_all_issues_enriched

        def fetch_issue_detail(self, _identifier):
            raise AssertionError("generation-bound epic cut must not be refetched")

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
    assert project["epic"]["jobs_required"] == 1
    assert binding.epic_controller.projections()[0].durable_jobs == (
        "rollup_reconciliation",
    )
    assert len(store.list_jobs(task_id=current.identifier)) == 1
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
