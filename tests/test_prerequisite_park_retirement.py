from __future__ import annotations

import pytest

from oompah.workflow_jobs import (
    WorkflowFailureCategory,
    WorkflowJobLeaseLost,
    WorkflowJobSpec,
    WorkflowJobState,
    WorkflowJobStore,
)


PROJECT_ID = "project-1"
TASK_ID = "TRICKLE-PARKED"
FACT_LANE = "event:implementation:fact"
IMPERATIVE_LANE = "event:implementation:imperative"
NESTED_REPAIR_LANE = "nested-dispatch-topology"
PARKED_LANES = (FACT_LANE, IMPERATIVE_LANE, NESTED_REPAIR_LANE)


@pytest.fixture
def store(tmp_path):
    value = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    yield value
    value.close()


def _materialize_event(
    store: WorkflowJobStore,
    *,
    lane: str,
    revision: str,
    action: str,
):
    write = store.materialize_event(
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        decision_revision=revision,
        action=action,
        idempotency_namespace=f"park:{lane}",
        scheduling_lane=lane,
        max_attempts=3,
    )
    assert write.accepted
    assert write.job is not None
    return write.job


def _claim_action(store: WorkflowJobStore, action: str):
    job = store.claim_next(
        lease_owner="worker-a",
        lease_seconds=30,
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        actions=(action,),
    )
    assert job is not None
    return job


def _stage_zero_job_park(
    store: WorkflowJobStore,
    *,
    revision: str = "implementation-prerequisite-park",
):
    snapshot = store.allocate_snapshot_generation()
    assert store.accept_snapshot_generation(snapshot)
    assert store.reconcile_snapshot_membership(
        snapshot_generation=snapshot,
        authoritative_project_ids=(PROJECT_ID,),
        expected_identities=((PROJECT_ID, TASK_ID),),
    ).accepted
    cursor = store.activate_schedule(
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        decision_revision=revision,
        snapshot_generation=snapshot,
    )
    write = store.reconcile_schedule(
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        snapshot_generation=snapshot,
        job_generation=cursor.job_generation,
        specs=(),
        record_authority_cut=True,
        authority_kind="managed_zero_job",
        retired_scheduling_lanes=PARKED_LANES,
    )
    assert write.accepted
    return snapshot, cursor, write


def test_zero_job_park_atomically_retires_exact_active_and_exhausted_lanes(store):
    nested = _materialize_event(
        store,
        lane=NESTED_REPAIR_LANE,
        revision="nested-1",
        action="nested_dispatch_topology_repair",
    )
    nested_running = _claim_action(store, nested.action)
    nested_exhausted = store.fail(
        nested_running.job_id,
        nested_running.lease_token,
        category=WorkflowFailureCategory.PERMANENT,
        error="repair exhausted",
        retryable=False,
    )
    imperative = _materialize_event(
        store,
        lane=IMPERATIVE_LANE,
        revision="imperative-1",
        action="focus_handoff",
    )
    imperative_running = _claim_action(store, imperative.action)
    imperative_waiting = store.fail(
        imperative_running.job_id,
        imperative_running.lease_token,
        category=WorkflowFailureCategory.TRANSIENT,
        error="transport unavailable",
        retryable=True,
        retry_delay_seconds=60,
    )
    fact = _materialize_event(
        store,
        lane=FACT_LANE,
        revision="fact-1",
        action="implementation_retry",
    )
    fact_running = _claim_action(store, fact.action)
    unrelated = _materialize_event(
        store,
        lane="epic-event:epic_cleanup",
        revision="cleanup-1",
        action="epic_cleanup",
    )

    snapshot, cursor, write = _stage_zero_job_park(store)

    assert write.superseded == 2
    assert store.get(imperative_waiting.job_id).state is WorkflowJobState.SUPERSEDED
    assert store.get(fact_running.job_id).state is WorkflowJobState.SUPERSEDED
    assert store.get(unrelated.job_id).state is WorkflowJobState.QUEUED
    # Staged proof is not execution authority until its exact snapshot publishes.
    assert store.current_exhausted_jobs(
        project_id=PROJECT_ID, task_id=TASK_ID
    ) == (nested_exhausted,)
    with pytest.raises(WorkflowJobLeaseLost):
        store.fail(
            fact_running.job_id,
            fact_running.lease_token,
            category=WorkflowFailureCategory.TRANSIENT,
            error="late worker result",
            retryable=True,
        )

    assert store.publish_snapshot_generation(snapshot, lambda: None)[0]

    assert not store.current_exhausted_jobs(
        project_id=PROJECT_ID, task_id=TASK_ID
    )
    assert store.schedule_cursor(
        project_id=PROJECT_ID, task_id=TASK_ID
    ).job_generation == cursor.job_generation
    assert store.get(unrelated.job_id).state is WorkflowJobState.QUEUED


def test_failed_publication_restores_unmanaged_lane_authority_and_fails_closed(
    store,
):
    nested = _materialize_event(
        store,
        lane=NESTED_REPAIR_LANE,
        revision="nested-1",
        action="nested_dispatch_topology_repair",
    )
    nested_running = _claim_action(store, nested.action)
    nested_exhausted = store.fail(
        nested_running.job_id,
        nested_running.lease_token,
        category=WorkflowFailureCategory.PERMANENT,
        error="repair exhausted",
        retryable=False,
    )
    imperative = _materialize_event(
        store,
        lane=IMPERATIVE_LANE,
        revision="imperative-1",
        action="focus_handoff",
    )
    imperative_running = _claim_action(store, imperative.action)
    imperative_waiting = store.fail(
        imperative_running.job_id,
        imperative_running.lease_token,
        category=WorkflowFailureCategory.TRANSIENT,
        error="retry later",
        retryable=True,
        retry_delay_seconds=60,
    )
    unrelated = _materialize_event(
        store,
        lane="epic-event:epic_cleanup",
        revision="cleanup-1",
        action="epic_cleanup",
    )
    unrelated_running = _claim_action(store, unrelated.action)
    checkpoint = store.capture_snapshot_authority(
        evaluated_identities=((PROJECT_ID, TASK_ID),),
        full_project_scope=False,
    )

    snapshot, _cursor, _write = _stage_zero_job_park(store)
    assert store.get(imperative_waiting.job_id).state is WorkflowJobState.SUPERSEDED
    unrelated_completed = store.complete(
        unrelated_running.job_id,
        unrelated_running.lease_token,
    )

    def reject_publication():
        raise RuntimeError("injected publication failure")

    with pytest.raises(RuntimeError, match="publication failure"):
        store.publish_snapshot_generation(
            snapshot,
            reject_publication,
            rollback_authority=lambda: store.restore_snapshot_authority(
                checkpoint,
                snapshot_generation=snapshot,
            ),
        )

    assert store.get(imperative_waiting.job_id).state is WorkflowJobState.RETRY_WAIT
    assert store.current_exhausted_jobs(
        project_id=PROJECT_ID, task_id=TASK_ID
    ) == (nested_exhausted,)
    assert store.get(unrelated_completed.job_id).state is WorkflowJobState.COMPLETED
    assert store.health_snapshot()["published_snapshot_generation"] == 0


def test_replacement_materialized_after_staged_cut_survives_publication(store):
    old = _materialize_event(
        store,
        lane=IMPERATIVE_LANE,
        revision="imperative-1",
        action="focus_handoff",
    )
    old_running = _claim_action(store, old.action)
    old_exhausted = store.fail(
        old_running.job_id,
        old_running.lease_token,
        category=WorkflowFailureCategory.PERMANENT,
        error="old handoff exhausted",
        retryable=False,
    )

    snapshot, _cursor, _write = _stage_zero_job_park(store)
    replacement = _materialize_event(
        store,
        lane=IMPERATIVE_LANE,
        revision="imperative-2",
        action="focus_handoff",
    )
    assert replacement.job_id != old_exhausted.job_id
    assert replacement.state is WorkflowJobState.QUEUED

    assert store.publish_snapshot_generation(snapshot, lambda: None)[0]

    assert store.get(replacement.job_id).state is WorkflowJobState.QUEUED
    assert not store.current_exhausted_jobs(
        project_id=PROJECT_ID, task_id=TASK_ID
    )
    claimed = _claim_action(store, replacement.action)
    assert claimed.job_id == replacement.job_id


def test_replacement_after_staged_cut_wins_failed_publication_rollback(store):
    old = _materialize_event(
        store,
        lane=IMPERATIVE_LANE,
        revision="imperative-1",
        action="focus_handoff",
    )
    checkpoint = store.capture_snapshot_authority(
        evaluated_identities=((PROJECT_ID, TASK_ID),),
        full_project_scope=False,
    )
    snapshot, _cursor, _write = _stage_zero_job_park(store)
    replacement = _materialize_event(
        store,
        lane=IMPERATIVE_LANE,
        revision="imperative-2",
        action="focus_handoff",
    )

    def reject_publication():
        raise RuntimeError("injected publication failure")

    with pytest.raises(RuntimeError, match="publication failure"):
        store.publish_snapshot_generation(
            snapshot,
            reject_publication,
            rollback_authority=lambda: store.restore_snapshot_authority(
                checkpoint,
                snapshot_generation=snapshot,
            ),
        )

    assert store.get(old.job_id).state is WorkflowJobState.SUPERSEDED
    assert store.get(replacement.job_id).state is WorkflowJobState.QUEUED
    claimed = _claim_action(store, replacement.action)
    assert claimed.job_id == replacement.job_id


def test_explicit_rearm_after_staged_cut_survives_publication(store):
    old = _materialize_event(
        store,
        lane=NESTED_REPAIR_LANE,
        revision="nested-1",
        action="nested_dispatch_topology_repair",
    )
    old_running = _claim_action(store, old.action)
    exhausted = store.fail(
        old_running.job_id,
        old_running.lease_token,
        category=WorkflowFailureCategory.PERMANENT,
        error="repair exhausted",
        retryable=False,
    )

    snapshot, _cursor, _write = _stage_zero_job_park(store)
    rearmed = store.rearm_exhausted_job(
        exhausted.job_id,
        generation=exhausted.generation,
        phase="queued",
        reason="fresh exact repair authority",
    )
    assert rearmed.state is WorkflowJobState.QUEUED

    assert store.publish_snapshot_generation(snapshot, lambda: None)[0]

    assert store.get(rearmed.job_id).state is WorkflowJobState.QUEUED
    assert not store.current_exhausted_jobs(
        project_id=PROJECT_ID, task_id=TASK_ID
    )
    claimed = _claim_action(store, rearmed.action)
    assert claimed.job_id == rearmed.job_id


def test_published_exact_lane_retirement_survives_store_restart(tmp_path):
    database = tmp_path / "workflow.sqlite3"
    first = WorkflowJobStore(str(database))
    nested = _materialize_event(
        first,
        lane=NESTED_REPAIR_LANE,
        revision="nested-1",
        action="nested_dispatch_topology_repair",
    )
    nested_running = _claim_action(first, nested.action)
    nested_exhausted = first.fail(
        nested_running.job_id,
        nested_running.lease_token,
        category=WorkflowFailureCategory.PERMANENT,
        error="repair exhausted",
        retryable=False,
    )
    imperative = _materialize_event(
        first,
        lane=IMPERATIVE_LANE,
        revision="imperative-1",
        action="focus_handoff",
    )
    snapshot, _cursor, _write = _stage_zero_job_park(first)
    assert first.publish_snapshot_generation(snapshot, lambda: None)[0]
    first.close()

    reopened = WorkflowJobStore(str(database))
    try:
        assert reopened.get(imperative.job_id).state is WorkflowJobState.SUPERSEDED
        assert reopened.get(nested_exhausted.job_id).state is WorkflowJobState.EXHAUSTED
        assert not reopened.current_exhausted_jobs(
            project_id=PROJECT_ID, task_id=TASK_ID
        )
        assert reopened.claim_next(
            lease_owner="worker-after-restart",
            lease_seconds=30,
            project_id=PROJECT_ID,
            task_id=TASK_ID,
        ) is None
    finally:
        reopened.close()


def test_retired_lanes_require_an_authoritative_zero_job_cut(store):
    snapshot = store.allocate_snapshot_generation()
    assert store.accept_snapshot_generation(snapshot)
    cursor = store.activate_schedule(
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        decision_revision="not-a-zero-job-park",
        snapshot_generation=snapshot,
    )
    managed = WorkflowJobSpec(
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        generation=cursor.job_generation,
        action="implementation_retry",
        idempotency_key="managed:implementation-retry",
    )

    with pytest.raises(ValueError, match="zero-job"):
        store.reconcile_schedule(
            project_id=PROJECT_ID,
            task_id=TASK_ID,
            snapshot_generation=snapshot,
            job_generation=cursor.job_generation,
            specs=(managed,),
            record_authority_cut=True,
            authority_kind="managed_decision",
            retired_scheduling_lanes=PARKED_LANES,
        )
    with pytest.raises(ValueError, match="authority cut"):
        store.reconcile_schedule(
            project_id=PROJECT_ID,
            task_id=TASK_ID,
            snapshot_generation=snapshot,
            job_generation=cursor.job_generation,
            specs=(),
            record_authority_cut=False,
            authority_kind="managed_zero_job",
            retired_scheduling_lanes=PARKED_LANES,
        )
    with pytest.raises(ValueError, match="retired_scheduling_lane"):
        store.reconcile_schedule(
            project_id=PROJECT_ID,
            task_id=TASK_ID,
            snapshot_generation=snapshot,
            job_generation=cursor.job_generation,
            specs=(),
            record_authority_cut=True,
            authority_kind="managed_zero_job",
            retired_scheduling_lanes=("",),
        )
