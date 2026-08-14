"""Durable scheduler boundaries for external-prerequisite parking."""

from __future__ import annotations

import pytest

from oompah.work_decision import PermittedAction, WorkDecision
from oompah.workflow_contract import TaskDisposition, WorkflowOwner
from oompah.workflow_jobs import (
    WorkflowFailureCategory,
    WorkflowJob,
    WorkflowJobState,
    WorkflowJobStore,
)
from oompah.workflow_reasons import AlertSeverity
from oompah.workflow_scheduler import WorkflowJobScheduler


PROJECT_ID = "project-a"
PARK_REASON = "implementation.external_prerequisite"
PARK_LANES = (
    "event:implementation:fact",
    "event:implementation:imperative",
    "nested-dispatch-topology",
)
RESOLUTION_LANE = "event:implementation-prerequisite-resolution"
UNRELATED_LANE = "epic-event:epic_cleanup"


def zero_job_decision(
    *,
    task_id: str,
    reason_code: str = PARK_REASON,
    evidence_revision: str = "facts-1",
) -> WorkDecision:
    if reason_code == PARK_REASON:
        disposition = TaskDisposition.BLOCKED
        owner = WorkflowOwner.DISPATCHER
        actions = (PermittedAction.WAIT_DEPENDENCY,)
    else:
        disposition = TaskDisposition.OWNED
        owner = WorkflowOwner.IMPLEMENTER
        actions = (PermittedAction.CONTINUE_IMPLEMENTATION,)
    return WorkDecision(
        project_id=PROJECT_ID,
        task_id=task_id,
        status="In Progress",
        disposition=disposition,
        reason_code=reason_code,
        responsible_owner=owner,
        unmet_prerequisites=(),
        evidence_revision=evidence_revision,
        next_reassessment_at=None,
        permitted_actions=actions,
        action_required=False,
        alert_level=AlertSeverity.NONE,
        durable_jobs=(),
    )


def scheduler(store: WorkflowJobStore) -> WorkflowJobScheduler:
    return WorkflowJobScheduler(
        store=store,
        zero_job_retired_lanes_by_reason={PARK_REASON: PARK_LANES},
    )


def prerequisite_action_decision(*, task_id: str) -> WorkDecision:
    return WorkDecision(
        project_id=PROJECT_ID,
        task_id=task_id,
        status="In Progress",
        disposition=TaskDisposition.RETRY_SCHEDULED,
        reason_code=PARK_REASON,
        responsible_owner=WorkflowOwner.DISPATCHER,
        unmet_prerequisites=(),
        evidence_revision="facts-action",
        next_reassessment_at=None,
        permitted_actions=(PermittedAction.RECONCILE_IMPLEMENTATION,),
        action_required=False,
        alert_level=AlertSeverity.NONE,
        durable_jobs=("authority_revocation",),
    )


def materialize_event(
    store: WorkflowJobStore,
    *,
    task_id: str,
    lane: str,
    revision: str,
) -> WorkflowJob:
    write = store.materialize_event(
        project_id=PROJECT_ID,
        task_id=task_id,
        decision_revision=revision,
        action=f"test_{revision}",
        idempotency_namespace=f"prerequisite-park-test:{revision}",
        scheduling_lane=lane,
    )
    assert write.job is not None
    return write.job


def due_lanes(store: WorkflowJobStore) -> set[str]:
    return {job.scheduling_lane for job in store.due_jobs(project_id=PROJECT_ID)}


def test_scheduler_forwards_exact_park_lanes_only_for_matching_zero_job_reason(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    store = WorkflowJobStore(str(tmp_path / "forwarding.sqlite3"))
    try:
        value = scheduler(store)
        calls: dict[str, tuple[str, ...]] = {}
        original = store.reconcile_schedule

        def record_lanes(**kwargs):
            calls[str(kwargs["task_id"])] = tuple(
                kwargs.get("retired_scheduling_lanes", ())
            )
            return original(**kwargs)

        monkeypatch.setattr(store, "reconcile_schedule", record_lanes)
        park = zero_job_decision(task_id="OOMPAH-PARK")
        ordinary = zero_job_decision(
            task_id="OOMPAH-OWNED",
            reason_code="implementation.active",
        )
        pending_action = prerequisite_action_decision(
            task_id="OOMPAH-PARK-ACTION"
        )

        result = value.reconcile((park, ordinary, pending_action))

        assert result.snapshot_accepted
        assert value.retired_scheduling_lanes(park) == PARK_LANES
        assert value.retired_scheduling_lanes(ordinary) == ()
        assert value.retired_scheduling_lanes(pending_action) == ()
        assert calls == {
            park.task_id: PARK_LANES,
            ordinary.task_id: (),
            pending_action.task_id: (),
        }
    finally:
        store.close()


def test_ordinary_zero_job_decision_preserves_configured_event_lane(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "ordinary-zero.sqlite3"))
    try:
        task_id = "OOMPAH-ORDINARY-ZERO"
        event = materialize_event(
            store,
            task_id=task_id,
            lane=PARK_LANES[0],
            revision="ordinary-event",
        )

        result = scheduler(store).reconcile(
            (
                zero_job_decision(
                    task_id=task_id,
                    reason_code="implementation.active",
                ),
            )
        )

        assert result.snapshot_accepted
        assert result.jobs_superseded == 0
        assert store.get(event.job_id).state is WorkflowJobState.QUEUED
        assert due_lanes(store) == {PARK_LANES[0]}
    finally:
        store.close()


def test_prerequisite_park_converges_across_repeat_and_restart_without_retiring_resolution(
    tmp_path,
):
    database = tmp_path / "park-restart.sqlite3"
    task_id = "OOMPAH-PARK-RESTART"
    store = WorkflowJobStore(str(database))
    exhausted = materialize_event(
        store,
        task_id=task_id,
        lane=PARK_LANES[0],
        revision="fact-exhaustion",
    )
    claimed = store.claim_next(
        lease_owner="failed-fact-worker",
        lease_seconds=30,
        generation=exhausted.generation,
    )
    assert claimed is not None and claimed.job_id == exhausted.job_id
    exhausted = store.fail(
        claimed.job_id,
        claimed.lease_token,
        error="captured prerequisite cannot run here",
        category=WorkflowFailureCategory.PERMANENT,
        retryable=False,
    )
    scoped_active = tuple(
        materialize_event(
            store,
            task_id=task_id,
            lane=lane,
            revision=f"scoped-{index}",
        )
        for index, lane in enumerate(PARK_LANES[1:], start=1)
    )
    resolution = materialize_event(
        store,
        task_id=task_id,
        lane=RESOLUTION_LANE,
        revision="resolution",
    )
    unrelated = materialize_event(
        store,
        task_id=task_id,
        lane=UNRELATED_LANE,
        revision="unrelated",
    )
    assert store.current_exhausted_jobs(
        project_id=PROJECT_ID, task_id=task_id
    ) == (exhausted,)

    park = zero_job_decision(task_id=task_id)
    first = scheduler(store).reconcile((park,))
    repeated = scheduler(store).reconcile((park,))

    assert first.snapshot_accepted and repeated.snapshot_accepted
    assert first.jobs_required == first.jobs_materialized == 0
    assert repeated.jobs_required == repeated.jobs_materialized == 0
    assert first.truncated is repeated.truncated is False
    assert store.current_exhausted_jobs(
        project_id=PROJECT_ID, task_id=task_id
    ) == ()
    assert store.get(exhausted.job_id).state is WorkflowJobState.EXHAUSTED
    assert all(
        store.get(job.job_id).state is WorkflowJobState.SUPERSEDED
        for job in scoped_active
    )
    assert store.get(resolution.job_id).state is WorkflowJobState.QUEUED
    assert store.get(unrelated.job_id).state is WorkflowJobState.QUEUED
    assert due_lanes(store) == {RESOLUTION_LANE, UNRELATED_LANE}
    store.close()

    reopened = WorkflowJobStore(str(database))
    try:
        assert reopened.current_exhausted_jobs(
            project_id=PROJECT_ID, task_id=task_id
        ) == ()
        assert due_lanes(reopened) == {RESOLUTION_LANE, UNRELATED_LANE}

        restarted = scheduler(reopened).reconcile((park,))

        assert restarted.snapshot_accepted
        assert restarted.jobs_required == restarted.jobs_materialized == 0
        assert restarted.truncated is False
        assert reopened.current_exhausted_jobs(
            project_id=PROJECT_ID, task_id=task_id
        ) == ()
        assert reopened.get(resolution.job_id).state is WorkflowJobState.QUEUED
        assert reopened.get(unrelated.job_id).state is WorkflowJobState.QUEUED
        assert due_lanes(reopened) == {RESOLUTION_LANE, UNRELATED_LANE}
    finally:
        reopened.close()
