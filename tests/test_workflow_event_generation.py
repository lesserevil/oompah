"""Regression coverage for event identity and managed snapshot isolation."""

from __future__ import annotations

from types import SimpleNamespace

from oompah.epic_workflow import EpicAction, EpicWorkflowController
from oompah.implementation_workflow import (
    ImplementationAction,
    ImplementationWorkflowController,
)
from oompah.work_decision import PermittedAction, WorkDecision
from oompah.workflow_contract import TaskDisposition, WorkflowOwner
from oompah.workflow_jobs import WorkflowJobStore
from oompah.workflow_reasons import AlertSeverity
from oompah.workflow_scheduler import WorkflowJobScheduler


def _managed_decision() -> WorkDecision:
    return WorkDecision(
        project_id="project-1",
        task_id="MANAGED-1",
        status="In Progress",
        disposition=TaskDisposition.RETRY_SCHEDULED,
        reason_code="implementation.recovery_scheduled",
        responsible_owner=WorkflowOwner.DISPATCHER,
        unmet_prerequisites=(),
        evidence_revision="facts-1",
        next_reassessment_at=None,
        permitted_actions=(PermittedAction.RECOVER_IMPLEMENTATION,),
        action_required=False,
        alert_level=AlertSeverity.INFO,
        durable_jobs=("implementation_recovery",),
    )


def _snapshot_generations(store: WorkflowJobStore) -> tuple[int, int, int]:
    health = store.health_snapshot()
    return (
        health["captured_snapshot_generation"],
        health["accepted_snapshot_generation"],
        health["published_snapshot_generation"],
    )


def test_imperative_event_generations_do_not_poison_managed_claim_fence(
    tmp_path,
) -> None:
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    scheduler = WorkflowJobScheduler(store=store)
    managed = scheduler.reconcile((_managed_decision(),))
    assert managed.snapshot_accepted
    managed_job = store.list_jobs(task_id="MANAGED-1")[0]
    assert _snapshot_generations(store) == (1, 1, 1)

    assert store.allocate_event_generation() == 2

    implementation = ImplementationWorkflowController(
        collector=SimpleNamespace(project_id="project-1"),
        store=store,
    )
    _batch, fallback = implementation.reconcile([])
    assert fallback.snapshot_generation == 3
    implementation.schedule_event(
        project_id="project-1",
        task_id="IMPERATIVE-1",
        action=ImplementationAction.START,
    )

    epic = EpicWorkflowController(
        collector=SimpleNamespace(project_id="project-1"),
        store=store,
    )
    epic_job = epic.schedule_action(
        task_id="EPIC-1",
        action=EpicAction.READINESS,
    )
    assert epic_job.generation.startswith("epic-maintenance:5:")

    assert _snapshot_generations(store) == (1, 1, 1)
    claimed = store.claim_next(
        lease_owner="managed-worker",
        lease_seconds=30,
        task_id="MANAGED-1",
    )
    assert claimed is not None
    assert claimed.job_id == managed_job.job_id
    assert store.allocate_snapshot_generation() == 6
    store.close()
