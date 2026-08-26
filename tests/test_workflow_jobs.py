from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from oompah.workflow_fact_model import LandingFact, LandingState
from oompah.workflow_jobs import (
    ACTIVE_JOB_STATES,
    MAX_SCAN_LIMIT,
    WORKFLOW_JOB_SCHEMA_VERSION,
    WorkflowFailureCategory,
    WorkflowJobCorruptionError,
    WorkflowJobIdempotencyConflict,
    WorkflowJobLeaseLost,
    WorkflowJobSpec,
    WorkflowJobState,
    WorkflowJobStore,
    WorkflowJobStoreError,
    WorkflowRolloutGateError,
    WorkflowSnapshotPublication,
)


class Clock:
    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def spec(
    key: str = "audit:g1",
    *,
    project: str = "project-a",
    task: str = "OOMPAH-1",
    generation: str = "g1",
    action: str = "terminal_audit",
    phase: str = "intent",
    payload: dict | None = None,
    scheduling_lane: str = "decision",
    priority: int = 100,
    max_attempts: int = 3,
) -> WorkflowJobSpec:
    return WorkflowJobSpec(
        project_id=project,
        task_id=task,
        generation=generation,
        action=action,
        idempotency_key=key,
        phase=phase,
        payload=payload,
        scheduling_lane=scheduling_lane,
        expected_evidence_revision=f"facts-{generation}",
        expected_head_sha=f"head-{generation}",
        priority=priority,
        max_attempts=max_attempts,
    )


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def store(tmp_path, clock: Clock):
    value = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"), clock=clock)
    yield value
    value.close()


def claim(store: WorkflowJobStore, **kwargs):
    return store.claim_next(lease_owner="worker-a", lease_seconds=30, **kwargs)


def test_spec_is_strict_and_revision_is_stable():
    first = spec()
    second = spec()

    assert first.revision == second.revision
    assert len(first.revision) == 64
    with pytest.raises(ValueError, match="project_id"):
        WorkflowJobSpec("", "task", "g", "action", "key")
    with pytest.raises(ValueError, match="positive"):
        WorkflowJobSpec("p", "task", "g", "action", "key", max_attempts=0)


def test_spec_payload_is_canonical_json_and_part_of_identity():
    first = spec(payload={"z": [3, {"b": True, "a": None}], "a": "value"})
    reordered = spec(payload={"a": "value", "z": [3, {"a": None, "b": True}]})
    changed = spec(payload={"a": "different"})

    assert first.to_dict()["payload"] == {
        "a": "value",
        "z": [3, {"a": None, "b": True}],
    }
    with pytest.raises(TypeError):
        first.payload["a"] = "mutated"  # type: ignore[index]
    with pytest.raises(TypeError):
        first.payload["z"][1]["a"] = "mutated"  # type: ignore[index]
    assert first.payload["z"][0] == 3
    assert first.revision == reordered.revision
    assert first.revision != changed.revision
    with pytest.raises(TypeError, match="mapping"):
        spec(payload=["not", "an", "object"])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="JSON serializable"):
        spec(payload={"not-json": {1, 2}})


def test_closed_store_recovers_sqlite_and_authority_lock(tmp_path, clock):
    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"), clock=clock)
    store.close()

    assert store._authority_lock_fd == -1

    queued = store.enqueue(spec())

    assert queued.state is WorkflowJobState.QUEUED
    assert store.get(queued.job_id) == queued
    assert store._authority_lock_fd >= 0
    store.close()


def test_repeated_close_recovery_cycles_do_not_close_unrelated_fd(tmp_path, clock):
    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"), clock=clock)

    for index in range(3):
        store.close()
        retired_fd = store._authority_lock_fd
        assert retired_fd == -1
        with open(tmp_path / f"sentinel-{index}", "w", encoding="utf-8") as sentinel:
            sentinel_fd = sentinel.fileno()
            store.close()
            os.fstat(sentinel_fd)
        queued = store.enqueue(
            spec(key=f"audit:g{index}", generation=f"g{index}")
        )
        assert queued.state is WorkflowJobState.QUEUED
        assert store._authority_lock_fd >= 0

    store.close()


def test_close_rejected_during_authority_mutation(store):
    with store.snapshot_authority_guard():
        with pytest.raises(
            WorkflowJobStoreError,
            match="during an authority mutation",
        ):
            store.close()

    store.close()
    assert store._authority_lock_fd == -1


def test_enqueue_persists_every_execution_fence_and_event(store):
    job = store.enqueue(spec(payload={"review_id": 42, "refresh": True}))

    assert job.state is WorkflowJobState.QUEUED
    assert job.attempts == 0
    assert job.expected_evidence_revision == "facts-g1"
    assert job.expected_head_sha == "head-g1"
    assert job.payload == {"refresh": True, "review_id": 42}
    assert job.lease_token is None
    assert job.to_dict()["state"] == "queued"
    assert [event.event_type for event in store.events(job.job_id)] == ["enqueued"]


def test_identical_enqueue_is_idempotent_and_does_not_add_event(store):
    first = store.enqueue(spec())
    second = store.enqueue(spec())

    assert second == first
    assert len(store.list_jobs()) == 1
    assert len(store.events(first.job_id)) == 1


def test_idempotency_conflict_cannot_alias_different_work(store):
    store.enqueue(spec())

    with pytest.raises(WorkflowJobIdempotencyConflict):
        store.enqueue(spec(generation="g2"))


def test_idempotency_conflict_cannot_alias_different_payload(store):
    store.enqueue(spec(payload={"review_id": 41}))

    with pytest.raises(WorkflowJobIdempotencyConflict):
        store.enqueue(spec(payload={"review_id": 42}))


def test_event_cursor_enqueue_and_supersession_are_one_transaction(store):
    first = store.materialize_event(
        project_id="project-1",
        task_id="TASK-1",
        decision_revision="event-1",
        action="focus_handoff",
        idempotency_namespace="implementation-event",
        scheduling_lane="event:implementation",
        payload={"focus": "testing"},
    )
    cursor_before = store._conn.execute(  # noqa: SLF001
        "SELECT * FROM workflow_event_cursors"
    ).fetchone()

    def fail_id():
        raise RuntimeError("crash before enqueue")

    store._id_factory = fail_id  # noqa: SLF001
    with pytest.raises(RuntimeError, match="crash before enqueue"):
        store.materialize_event(
            project_id="project-1",
            task_id="TASK-1",
            decision_revision="event-2",
            action="validation_submission",
            idempotency_namespace="implementation-event",
            scheduling_lane="event:implementation",
            payload={"head_sha": "a" * 40},
        )

    cursor_after = store._conn.execute(  # noqa: SLF001
        "SELECT * FROM workflow_event_cursors"
    ).fetchone()
    assert dict(cursor_after) == dict(cursor_before)
    assert store.get(first.job.job_id).state is WorkflowJobState.QUEUED
    assert len(store.list_jobs()) == 1


def test_event_lane_materialization_requires_exact_current_authority(
    store, clock
):
    write = store.materialize_event(
        project_id="project-1",
        task_id="TASK-1",
        decision_revision="event-1",
        action="implementation_retry",
        idempotency_namespace="implementation-event",
        scheduling_lane="event:implementation:fact",
        ordering_namespace="implementation-ordering",
        source_generation=1,
        source_revision="source-1",
    )

    assert write.job is not None
    assert store.event_lane_materialized(
        project_id="project-1",
        task_id="TASK-1",
        ordering_namespace="implementation-ordering",
        scheduling_lane="event:implementation:fact",
        source_revision="source-1",
        actions=("implementation_retry",),
    )
    for override in (
        {"ordering_namespace": "wrong-ordering"},
        {"scheduling_lane": "event:implementation:imperative"},
        {"source_revision": "wrong-source"},
        {"actions": ("implementation_recovery",)},
    ):
        arguments = {
            "project_id": "project-1",
            "task_id": "TASK-1",
            "ordering_namespace": "implementation-ordering",
            "scheduling_lane": "event:implementation:fact",
            "source_revision": "source-1",
            "actions": ("implementation_retry",),
            **override,
        }
        assert not store.event_lane_materialized(**arguments)

    running = claim(store)
    assert running is not None
    assert store.event_lane_materialized(
        project_id="project-1",
        task_id="TASK-1",
        ordering_namespace="implementation-ordering",
        scheduling_lane="event:implementation:fact",
        source_revision="source-1",
        actions=("implementation_retry",),
    )
    clock.advance(31)
    assert not store.event_lane_materialized(
        project_id="project-1",
        task_id="TASK-1",
        ordering_namespace="implementation-ordering",
        scheduling_lane="event:implementation:fact",
        source_revision="source-1",
        actions=("implementation_retry",),
    )


def test_event_lane_retry_wait_is_live_authority(store):
    write = store.materialize_event(
        project_id="project-1",
        task_id="TASK-1",
        decision_revision="event-1",
        action="implementation_retry",
        idempotency_namespace="implementation-event",
        scheduling_lane="event:implementation:fact",
        ordering_namespace="implementation-ordering",
        source_generation=1,
        source_revision="source-1",
    )
    assert write.job is not None
    running = claim(store)
    assert running is not None
    waiting = store.fail(
        running.job_id,
        running.lease_token,
        category=WorkflowFailureCategory.TRANSIENT,
        error="retry later",
        retryable=True,
        retry_delay_seconds=60,
    )

    assert waiting.state is WorkflowJobState.RETRY_WAIT
    assert store.event_lane_materialized(
        project_id="project-1",
        task_id="TASK-1",
        ordering_namespace="implementation-ordering",
        scheduling_lane="event:implementation:fact",
        source_revision="source-1",
        actions=("implementation_retry",),
    )


def test_administrative_deferral_preserves_checkpoint_and_failure_budget(
    store, clock
):
    queued = store.enqueue(spec(max_attempts=1))
    running = claim(store)
    assert running is not None
    checkpointed = store.checkpoint(
        running.job_id,
        running.lease_token,
        phase="revalidated",
        checkpoint={"revalidation": {"generation": "g1"}},
    )

    first = store.defer_owned_without_attempt(
        checkpointed.job_id,
        checkpointed.lease_token,
        reason="operator pause",
        retry_delay_seconds=5,
    )

    assert first.state is WorkflowJobState.RETRY_WAIT
    assert first.attempts == 0
    assert first.generation == queued.generation
    assert first.phase == checkpointed.phase
    assert first.checkpoint == checkpointed.checkpoint
    assert first.retry_at == clock.now + 5
    assert first.failure_category is None
    assert first.last_error is None
    event = store.events(queued.job_id)[-1]
    assert event.event_type == "administrative_deferred"
    assert event.payload == {
        "deferral_count": 1,
        "reason": "operator pause",
        "restored_attempts": 0,
        "retry_at": clock.now + 5,
        "retry_delay_seconds": 5.0,
    }

    clock.advance(5)
    resumed = claim(store)
    assert resumed is not None
    second = store.defer_owned_without_attempt(
        resumed.job_id,
        resumed.lease_token,
        reason="graceful restart",
        retry_delay_seconds=5,
    )

    assert second.attempts == 0
    assert second.retry_at == clock.now + 10
    assert second.checkpoint == checkpointed.checkpoint
    assert store.events(queued.job_id)[-1].payload["deferral_count"] == 2


def test_reassessment_deferral_preserves_exact_deadline_and_failure_budget(
    store, clock
):
    queued = store.enqueue(spec(max_attempts=1))
    running = claim(store)
    assert running is not None

    waiting = store.defer_owned_until(
        running.job_id,
        running.lease_token,
        reason="fresh evidence asks for same-generation reassessment",
        retry_at=clock.now + 90,
    )

    assert waiting.state is WorkflowJobState.RETRY_WAIT
    assert waiting.attempts == 0
    assert waiting.generation == queued.generation
    assert waiting.retry_at == clock.now + 90
    assert waiting.last_error == (
        "fresh evidence asks for same-generation reassessment"
    )
    event = store.events(queued.job_id)[-1]
    assert event.event_type == "reassessment_deferred"
    assert event.payload == {
        "reason": "fresh evidence asks for same-generation reassessment",
        "replacement_generation": None,
        "restored_attempts": 0,
        "retry_at": clock.now + 90,
    }


def test_due_reassessment_deferral_retires_generation_for_scheduler_rotation(
    store, clock
):
    queued = store.enqueue(spec(max_attempts=1))
    running = claim(store)
    assert running is not None

    due = store.defer_owned_until(
        running.job_id,
        running.lease_token,
        reason="same-generation reassessment deadline is due",
        retry_at=clock.now,
    )

    assert due.state is WorkflowJobState.SUPERSEDED
    assert due.attempts == 0
    assert due.retry_at is None
    assert due.superseded_by_generation == f"reassess:{queued.generation}"
    assert store.events(queued.job_id)[-1].event_type == "reassessment_due"


def test_reassessment_deferral_survives_restart_and_reclaims_at_exact_deadline(
    tmp_path, clock
):
    path = str(tmp_path / "reassessment-restart.sqlite3")
    first = WorkflowJobStore(path, clock=clock)
    queued = first.enqueue(spec(generation="g1:reassess=1090.000000"))
    running = claim(first)
    assert running is not None
    first.defer_owned_until(
        running.job_id,
        running.lease_token,
        reason="wait for authoritative recurring deadline",
        retry_at=1090,
    )
    first.close()

    reopened = WorkflowJobStore(path, clock=clock)
    try:
        waiting = reopened.get(queued.job_id)
        assert waiting.state is WorkflowJobState.RETRY_WAIT
        assert waiting.reassessment_deadline == 1090
        assert waiting.retry_at == 1090
        assert claim(reopened) is None

        clock.advance(90)
        reclaimed = claim(reopened)
        assert reclaimed is not None
        assert reclaimed.job_id == queued.job_id
        assert reclaimed.generation == queued.generation
        assert reclaimed.attempts == 1
    finally:
        reopened.close()


def test_administrative_deferral_fences_aba_lease_across_restart(tmp_path, clock):
    path = str(tmp_path / "administrative-restart.sqlite3")
    store = WorkflowJobStore(path, clock=clock)
    queued = store.enqueue(spec(max_attempts=1))
    first = claim(store)
    assert first is not None
    store.defer_owned_without_attempt(
        first.job_id,
        first.lease_token,
        reason="lifecycle drain",
        retry_delay_seconds=5,
    )
    store.close()

    clock.advance(5)
    reopened = WorkflowJobStore(path, clock=clock)
    try:
        replacement = reopened.claim_next(
            lease_owner="worker-after-restart",
            lease_seconds=30,
        )
        assert replacement is not None
        assert replacement.job_id == queued.job_id
        assert replacement.generation == queued.generation
        assert replacement.lease_token != first.lease_token
        assert replacement.attempts == 1

        with pytest.raises(WorkflowJobLeaseLost):
            reopened.defer_owned_without_attempt(
                first.job_id,
                first.lease_token,
                reason="late pre-restart callback",
                retry_delay_seconds=5,
            )

        observed = reopened.get(queued.job_id)
        assert observed.state is WorkflowJobState.RUNNING
        assert observed.lease_token == replacement.lease_token
        assert observed.attempts == 1

        superseded = reopened.supersede(
            queued.job_id,
            generation=queued.generation,
            replacement_generation="g2",
            reason="new evidence generation",
        )
        with pytest.raises(WorkflowJobLeaseLost):
            reopened.defer_owned_without_attempt(
                replacement.job_id,
                replacement.lease_token,
                reason="late replacement callback",
                retry_delay_seconds=5,
            )
        assert superseded.state is WorkflowJobState.SUPERSEDED
        assert superseded.superseded_by_generation == "g2"
        assert reopened.get(queued.job_id) == superseded
    finally:
        reopened.close()


@pytest.mark.parametrize(
    "active_state",
    [
        WorkflowJobState.QUEUED,
        WorkflowJobState.RUNNING,
        WorkflowJobState.RETRY_WAIT,
    ],
)
def test_newer_source_replays_exact_active_event_without_mutating_job(
    store, active_state
):
    write = store.materialize_event(
        project_id="project-1",
        task_id="TASK-1",
        decision_revision="event-1",
        action="implementation_retry",
        idempotency_namespace="implementation-event",
        scheduling_lane="event:implementation:fact",
        ordering_namespace="implementation-ordering",
        source_generation=1,
        source_revision="source-1",
    )
    assert write.job is not None
    current = write.job
    if active_state in {WorkflowJobState.RUNNING, WorkflowJobState.RETRY_WAIT}:
        running = claim(store)
        assert running is not None
        current = running
        if active_state is WorkflowJobState.RETRY_WAIT:
            current = store.fail(
                running.job_id,
                running.lease_token,
                category=WorkflowFailureCategory.TRANSIENT,
                error="retry later",
                retryable=True,
                retry_delay_seconds=60,
            )
    assert current.state is active_state
    jobs_before = store.list_jobs(task_id="TASK-1")
    events_before = store.events(current.job_id)
    execution_state_before = (
        current.state,
        current.attempts,
        current.lease_owner,
        current.lease_token,
        current.lease_expires_at,
        current.retry_at,
        current.failure_category,
        current.last_error,
    )

    replay = store.materialize_event(
        project_id="project-1",
        task_id="TASK-1",
        decision_revision="event-1",
        action="implementation_retry",
        idempotency_namespace="implementation-event",
        scheduling_lane="event:implementation:fact",
        ordering_namespace="implementation-ordering",
        source_generation=2,
        source_revision="source-1",
    )

    assert replay.accepted
    assert not replay.created
    assert replay.job is not None
    assert replay.job == current
    assert store.list_jobs(task_id="TASK-1") == jobs_before
    assert store.events(current.job_id) == events_before
    persisted = store.get(current.job_id)
    assert (
        persisted.state,
        persisted.attempts,
        persisted.lease_owner,
        persisted.lease_token,
        persisted.lease_expires_at,
        persisted.retry_at,
        persisted.failure_category,
        persisted.last_error,
    ) == execution_state_before


def test_newer_source_reactivates_event_when_cursor_job_is_absent(store):
    write = store.materialize_event(
        project_id="project-1",
        task_id="TASK-1",
        decision_revision="event-1",
        action="implementation_retry",
        idempotency_namespace="implementation-event",
        scheduling_lane="event:implementation:fact",
        ordering_namespace="implementation-ordering",
        source_generation=1,
        source_revision="source-1",
    )
    assert write.job is not None
    missing_generation = "missing-generation"
    missing_key = f"implementation-event:event-1:{missing_generation}"
    store._conn.execute(  # noqa: SLF001
        """
        UPDATE workflow_event_cursors
           SET event_generation = ?
         WHERE project_id = ? AND task_id = ? AND event_namespace = ?
        """,
        (
            missing_generation,
            "project-1",
            "TASK-1",
            "event:implementation:fact",
        ),
    )
    store._conn.commit()  # noqa: SLF001
    assert (
        store._conn.execute(  # noqa: SLF001
            """
        SELECT 1 FROM workflow_jobs
         WHERE project_id = ? AND idempotency_key = ?
        """,
            ("project-1", missing_key),
        ).fetchone()
        is None
    )

    replacement = store.materialize_event(
        project_id="project-1",
        task_id="TASK-1",
        decision_revision="event-1",
        action="implementation_retry",
        idempotency_namespace="implementation-event",
        scheduling_lane="event:implementation:fact",
        ordering_namespace="implementation-ordering",
        source_generation=2,
        source_revision="source-1",
    )

    assert replacement.accepted
    assert replacement.created
    assert replacement.job is not None
    assert replacement.job.job_id != write.job.job_id
    assert replacement.job.generation != missing_generation
    assert replacement.job.state is WorkflowJobState.QUEUED
    assert len(store.list_jobs(task_id="TASK-1")) == 2
    assert store.get(write.job.job_id).state is WorkflowJobState.SUPERSEDED
    assert store.event_lane_materialized(
        project_id="project-1",
        task_id="TASK-1",
        ordering_namespace="implementation-ordering",
        scheduling_lane="event:implementation:fact",
        source_revision="source-1",
        actions=("implementation_retry",),
    )


def test_event_lane_materialization_rejects_historical_cursor_and_job(store):
    first = store.materialize_event(
        project_id="project-1",
        task_id="TASK-1",
        decision_revision="event-1",
        action="implementation_retry",
        idempotency_namespace="implementation-event",
        scheduling_lane="event:implementation:fact",
        ordering_namespace="implementation-ordering",
        source_generation=1,
        source_revision="source-1",
    )
    second = store.materialize_event(
        project_id="project-1",
        task_id="TASK-1",
        decision_revision="event-2",
        action="implementation_recovery",
        idempotency_namespace="implementation-event",
        scheduling_lane="event:implementation:fact",
        ordering_namespace="implementation-ordering",
        source_generation=2,
        source_revision="source-2",
    )

    assert first.job is not None
    assert second.job is not None
    assert store.get(first.job.job_id).state is WorkflowJobState.SUPERSEDED
    assert not store.event_lane_materialized(
        project_id="project-1",
        task_id="TASK-1",
        ordering_namespace="implementation-ordering",
        scheduling_lane="event:implementation:fact",
        source_revision="source-1",
        actions=("implementation_retry",),
    )
    assert store.event_lane_materialized(
        project_id="project-1",
        task_id="TASK-1",
        ordering_namespace="implementation-ordering",
        scheduling_lane="event:implementation:fact",
        source_revision="source-2",
        actions=("implementation_recovery",),
    )


@pytest.mark.parametrize(
    "terminal_state", ["superseded", "cancelled", "completed", "exhausted"]
)
def test_event_lane_materialization_rejects_retired_current_job(
    store, terminal_state
):
    write = store.materialize_event(
        project_id="project-1",
        task_id="TASK-1",
        decision_revision="event-1",
        action="implementation_retry",
        idempotency_namespace="implementation-event",
        scheduling_lane="event:implementation:fact",
        ordering_namespace="implementation-ordering",
        source_generation=1,
        source_revision="source-1",
    )
    assert write.job is not None
    if terminal_state == "superseded":
        store.supersede(
            write.job.job_id,
            generation=write.job.generation,
            replacement_generation="replacement",
            reason="test retirement",
        )
    elif terminal_state == "cancelled":
        store.cancel(
            write.job.job_id,
            generation=write.job.generation,
            reason="test retirement",
        )
    else:
        running = claim(store)
        assert running is not None
        if terminal_state == "completed":
            store.complete(running.job_id, running.lease_token)
        else:
            store.fail(
                running.job_id,
                running.lease_token,
                error="terminal failure",
                category=WorkflowFailureCategory.PERMANENT,
                retryable=False,
            )

    assert not store.event_lane_materialized(
        project_id="project-1",
        task_id="TASK-1",
        ordering_namespace="implementation-ordering",
        scheduling_lane="event:implementation:fact",
        source_revision="source-1",
        actions=("implementation_retry",),
    )

    same_source = store.materialize_event(
        project_id="project-1",
        task_id="TASK-1",
        decision_revision="event-1",
        action="implementation_retry",
        idempotency_namespace="implementation-event",
        scheduling_lane="event:implementation:fact",
        ordering_namespace="implementation-ordering",
        source_generation=1,
        source_revision="source-1",
    )
    assert same_source.accepted
    assert not same_source.created
    assert same_source.job is not None
    assert same_source.job.job_id == write.job.job_id
    assert same_source.job.state not in ACTIVE_JOB_STATES
    assert store.get(write.job.job_id).state is WorkflowJobState(terminal_state)
    assert store.health_snapshot()["states"].get("exhausted", 0) == (
        1 if terminal_state == "exhausted" else 0
    )

    newer_source = store.materialize_event(
        project_id="project-1",
        task_id="TASK-1",
        decision_revision="event-1",
        action="implementation_retry",
        idempotency_namespace="implementation-event",
        scheduling_lane="event:implementation:fact",
        ordering_namespace="implementation-ordering",
        source_generation=2,
        source_revision="source-1",
    )
    assert newer_source.accepted
    assert newer_source.created
    assert newer_source.job is not None
    assert newer_source.job.job_id != write.job.job_id
    assert newer_source.job.generation != write.job.generation
    assert newer_source.job.state is WorkflowJobState.QUEUED
    assert store.get(write.job.job_id).state is WorkflowJobState(terminal_state)
    health = store.health_snapshot()
    assert health["states"].get("exhausted", 0) == (
        1 if terminal_state == "exhausted" else 0
    )
    assert health["current_states"]["exhausted"] == 0
    assert store.event_lane_materialized(
        project_id="project-1",
        task_id="TASK-1",
        ordering_namespace="implementation-ordering",
        scheduling_lane="event:implementation:fact",
        source_revision="source-1",
        actions=("implementation_retry",),
    )

    jobs_before_replay = store.list_jobs(task_id="TASK-1")
    replacement_events = store.events(newer_source.job.job_id)
    replay = store.materialize_event(
        project_id="project-1",
        task_id="TASK-1",
        decision_revision="event-1",
        action="implementation_retry",
        idempotency_namespace="implementation-event",
        scheduling_lane="event:implementation:fact",
        ordering_namespace="implementation-ordering",
        source_generation=2,
        source_revision="source-1",
    )
    assert replay.accepted
    assert not replay.created
    assert replay.job is not None
    assert replay.job.job_id == newer_source.job.job_id
    assert store.list_jobs(task_id="TASK-1") == jobs_before_replay
    assert store.events(newer_source.job.job_id) == replacement_events


def test_active_replacement_hides_historical_exhaustion_across_restart(
    tmp_path, clock
):
    database = tmp_path / "workflow.sqlite3"
    store = WorkflowJobStore(str(database), clock=clock)
    failed = store.materialize_event(
        project_id="project-1",
        task_id="TASK-1",
        decision_revision="event-1",
        action="implementation_retry",
        idempotency_namespace="implementation-event",
        scheduling_lane="event:implementation:fact",
        ordering_namespace="implementation-ordering",
        source_generation=1,
        source_revision="source-1",
    )
    assert failed.job is not None
    running = claim(store)
    assert running is not None
    store.fail(
        running.job_id,
        running.lease_token,
        error="terminal failure",
        category=WorkflowFailureCategory.PERMANENT,
        retryable=False,
    )
    health = store.health_snapshot()
    assert health["states"]["exhausted"] == 1
    assert health["current_states"]["exhausted"] == 1
    assert [
        job.job_id
        for job in store.current_exhausted_jobs(
            project_id="project-1", task_id="TASK-1"
        )
    ] == [failed.job.job_id]

    replacement = store.materialize_event(
        project_id="project-1",
        task_id="TASK-1",
        decision_revision="event-1",
        action="implementation_retry",
        idempotency_namespace="implementation-event",
        scheduling_lane="event:implementation:fact",
        ordering_namespace="implementation-ordering",
        source_generation=2,
        source_revision="source-1",
    )
    assert replacement.created
    assert replacement.job is not None
    assert replacement.job.state is WorkflowJobState.QUEUED
    assert store.get(failed.job.job_id).state is WorkflowJobState.EXHAUSTED
    health = store.health_snapshot()
    assert health["states"]["exhausted"] == 1
    assert health["current_states"]["exhausted"] == 0
    assert not store.current_exhausted_jobs(
        project_id="project-1", task_id="TASK-1"
    )
    jobs_before_restart = store.list_jobs(task_id="TASK-1")
    store.close()

    reopened = WorkflowJobStore(str(database), clock=clock)
    replay = reopened.materialize_event(
        project_id="project-1",
        task_id="TASK-1",
        decision_revision="event-1",
        action="implementation_retry",
        idempotency_namespace="implementation-event",
        scheduling_lane="event:implementation:fact",
        ordering_namespace="implementation-ordering",
        source_generation=2,
        source_revision="source-1",
    )
    assert replay.accepted
    assert not replay.created
    assert replay.job is not None
    assert replay.job.job_id == replacement.job.job_id
    assert reopened.list_jobs(task_id="TASK-1") == jobs_before_restart
    assert reopened.get(failed.job.job_id).state is WorkflowJobState.EXHAUSTED
    health = reopened.health_snapshot()
    assert health["states"]["exhausted"] == 1
    assert health["current_states"]["exhausted"] == 0
    assert not reopened.current_exhausted_jobs(
        project_id="project-1", task_id="TASK-1"
    )
    reopened.close()


def test_replacement_exhaustion_is_current_health(store):
    first = store.materialize_event(
        project_id="project-1",
        task_id="TASK-1",
        decision_revision="event-1",
        action="implementation_retry",
        idempotency_namespace="implementation-event",
        scheduling_lane="event:implementation:fact",
        ordering_namespace="implementation-ordering",
        source_generation=1,
        source_revision="source-1",
    )
    assert first.job is not None
    running = claim(store)
    assert running is not None
    store.fail(
        running.job_id,
        running.lease_token,
        error="first terminal failure",
        category=WorkflowFailureCategory.PERMANENT,
        retryable=False,
    )

    replacement = store.materialize_event(
        project_id="project-1",
        task_id="TASK-1",
        decision_revision="event-1",
        action="implementation_retry",
        idempotency_namespace="implementation-event",
        scheduling_lane="event:implementation:fact",
        ordering_namespace="implementation-ordering",
        source_generation=2,
        source_revision="source-1",
    )
    assert replacement.job is not None
    running = claim(store)
    assert running is not None
    assert running.job_id == replacement.job.job_id
    store.fail(
        running.job_id,
        running.lease_token,
        error="replacement terminal failure",
        category=WorkflowFailureCategory.PERMANENT,
        retryable=False,
    )

    health = store.health_snapshot()
    assert health["states"]["exhausted"] == 2
    assert health["current_states"]["exhausted"] == 1
    assert [
        job.job_id
        for job in store.current_exhausted_jobs(
            project_id="project-1", task_id="TASK-1"
        )
    ] == [replacement.job.job_id]


def test_stale_later_lane_enqueue_does_not_hide_current_exhaustion(store):
    lane = "terminal-audit:Done"
    current = store.enqueue_replacing_lane(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-1",
            generation="generation-2",
            action="terminal_audit",
            idempotency_key="terminal-audit:current",
            scheduling_lane=lane,
        ),
        source_generation=2,
    )
    assert current.job is not None
    running = claim(store)
    assert running is not None
    assert running.job_id == current.job.job_id
    store.fail(
        running.job_id,
        running.lease_token,
        error="terminal failure",
        category=WorkflowFailureCategory.PERMANENT,
        retryable=False,
    )

    stale = store.enqueue_replacing_lane(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-1",
            generation="generation-1",
            action="terminal_audit",
            idempotency_key="terminal-audit:stale",
            scheduling_lane=lane,
        ),
        source_generation=1,
    )
    assert not stale.accepted
    assert stale.created
    assert stale.job is not None
    assert stale.job.state is WorkflowJobState.SUPERSEDED
    assert stale.job.enqueue_sequence > current.job.enqueue_sequence
    health = store.health_snapshot()
    assert health["states"]["exhausted"] == 1
    assert health["current_states"]["exhausted"] == 1

    replacement = store.enqueue_replacing_lane(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-1",
            generation="generation-3",
            action="terminal_audit",
            idempotency_key="terminal-audit:replacement",
            scheduling_lane=lane,
        ),
        source_generation=3,
    )
    assert replacement.accepted
    assert replacement.created
    assert replacement.job is not None
    assert replacement.job.state is WorkflowJobState.QUEUED
    health = store.health_snapshot()
    assert health["states"]["exhausted"] == 1
    assert health["current_states"]["exhausted"] == 0


def test_managed_cursor_hides_exhaustion_only_after_materialization(store):
    project_id = "project-1"
    task_id = "TASK-1"
    first_snapshot = store.allocate_snapshot_generation()
    assert store.accept_snapshot_generation(first_snapshot)
    membership = store.reconcile_snapshot_membership(
        snapshot_generation=first_snapshot,
        authoritative_project_ids=(project_id,),
        expected_identities=((project_id, task_id),),
    )
    assert membership.accepted
    first_cursor = store.activate_schedule(
        project_id=project_id,
        task_id=task_id,
        decision_revision="decision-1",
        snapshot_generation=first_snapshot,
    )
    first_write = store.reconcile_schedule(
        project_id=project_id,
        task_id=task_id,
        snapshot_generation=first_snapshot,
        job_generation=first_cursor.job_generation,
        specs=(
            WorkflowJobSpec(
                project_id=project_id,
                task_id=task_id,
                generation=first_cursor.job_generation,
                action="implementation_retry",
                idempotency_key="managed:first",
            ),
        ),
    )
    assert first_write.accepted
    published, _result = store.publish_snapshot_generation(
        first_snapshot, lambda: None
    )
    assert published
    running = claim(store, task_id=task_id)
    assert running is not None
    store.fail(
        running.job_id,
        running.lease_token,
        error="terminal failure",
        category=WorkflowFailureCategory.PERMANENT,
        retryable=False,
    )
    health = store.health_snapshot()
    assert health["states"]["exhausted"] == 1
    assert health["current_states"]["exhausted"] == 1
    assert len(
        store.current_exhausted_jobs(
            project_id=project_id, task_id=task_id
        )
    ) == 1

    second_snapshot = store.allocate_snapshot_generation()
    assert store.accept_snapshot_generation(second_snapshot)
    second_cursor = store.activate_schedule(
        project_id=project_id,
        task_id=task_id,
        decision_revision="decision-2",
        snapshot_generation=second_snapshot,
    )
    assert not second_cursor.materialized
    health = store.health_snapshot()
    assert health["states"]["exhausted"] == 1
    assert health["current_states"]["exhausted"] == 1
    assert len(
        store.current_exhausted_jobs(
            project_id=project_id, task_id=task_id
        )
    ) == 1

    second_write = store.reconcile_schedule(
        project_id=project_id,
        task_id=task_id,
        snapshot_generation=second_snapshot,
        job_generation=second_cursor.job_generation,
        specs=(
            WorkflowJobSpec(
                project_id=project_id,
                task_id=task_id,
                generation=second_cursor.job_generation,
                action="parent_rollup_review",
                idempotency_key="managed:second",
            ),
        ),
    )
    assert second_write.accepted
    assert store.schedule_cursor(
        project_id=project_id, task_id=task_id
    ).materialized
    health = store.health_snapshot()
    assert health["states"]["exhausted"] == 1
    assert health["current_states"]["exhausted"] == 1
    published, _result = store.publish_snapshot_generation(
        second_snapshot, lambda: None
    )
    assert published
    health = store.health_snapshot()
    assert health["current_states"]["exhausted"] == 0
    assert not store.current_exhausted_jobs(
        project_id=project_id, task_id=task_id
    )


def test_managed_zero_job_or_retired_replacement_fails_closed(store):
    project_id = "project-1"
    task_id = "TASK-AMBIGUOUS"
    first_snapshot = store.allocate_snapshot_generation()
    assert store.accept_snapshot_generation(first_snapshot)
    assert store.reconcile_snapshot_membership(
        snapshot_generation=first_snapshot,
        authoritative_project_ids=(project_id,),
        expected_identities=((project_id, task_id),),
    ).accepted
    first_cursor = store.activate_schedule(
        project_id=project_id,
        task_id=task_id,
        decision_revision="decision-1",
        snapshot_generation=first_snapshot,
    )
    assert store.reconcile_schedule(
        project_id=project_id,
        task_id=task_id,
        snapshot_generation=first_snapshot,
        job_generation=first_cursor.job_generation,
        specs=(
            WorkflowJobSpec(
                project_id=project_id,
                task_id=task_id,
                generation=first_cursor.job_generation,
                action="integration_landing_refresh",
                idempotency_key="managed:ambiguous:first",
            ),
        ),
    ).accepted
    published, _result = store.publish_snapshot_generation(
        first_snapshot, lambda: None
    )
    assert published
    running = claim(store, task_id=task_id)
    assert running is not None
    failed = store.fail(
        running.job_id,
        running.lease_token,
        error="terminal failure",
        category=WorkflowFailureCategory.PERMANENT,
        retryable=False,
    )

    second_snapshot = store.allocate_snapshot_generation()
    assert store.accept_snapshot_generation(second_snapshot)
    second_cursor = store.activate_schedule(
        project_id=project_id,
        task_id=task_id,
        decision_revision="decision-2",
        snapshot_generation=second_snapshot,
    )
    assert store.reconcile_schedule(
        project_id=project_id,
        task_id=task_id,
        snapshot_generation=second_snapshot,
        job_generation=second_cursor.job_generation,
        specs=(),
    ).accepted

    assert store.current_exhausted_jobs(
        project_id=project_id, task_id=task_id
    ) == (failed,)
    assert store.health_snapshot()["current_states"]["exhausted"] == 1

    third_snapshot = store.allocate_snapshot_generation()
    assert store.accept_snapshot_generation(third_snapshot)
    third_cursor = store.activate_schedule(
        project_id=project_id,
        task_id=task_id,
        decision_revision="decision-3",
        snapshot_generation=third_snapshot,
    )
    third_write = store.reconcile_schedule(
        project_id=project_id,
        task_id=task_id,
        snapshot_generation=third_snapshot,
        job_generation=third_cursor.job_generation,
        specs=(
            WorkflowJobSpec(
                project_id=project_id,
                task_id=task_id,
                generation=third_cursor.job_generation,
                action="parent_rollup_review",
                idempotency_key="managed:ambiguous:third",
            ),
        ),
    )
    assert third_write.accepted
    replacement = next(
        job
        for job in store.list_jobs(task_id=task_id)
        if job.generation == third_cursor.job_generation
    )
    store.cancel(
        replacement.job_id,
        generation=replacement.generation,
        reason="replacement retired before recovery",
    )

    assert store.current_exhausted_jobs(
        project_id=project_id, task_id=task_id
    ) == (failed,)
    assert store.health_snapshot()["current_states"]["exhausted"] == 1


def test_published_zero_job_cut_survives_restart_and_unselected_snapshot(tmp_path):
    database = tmp_path / "zero-job.sqlite3"
    store = WorkflowJobStore(str(database))
    project_id = "project-1"
    task_id = "TASK-ZERO"
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
        decision_revision="decision-job",
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
                idempotency_key="zero:first",
            ),
        ),
    ).accepted
    assert store.publish_snapshot_generation(first, lambda: None)[0]
    running = claim(store, task_id=task_id)
    assert running is not None
    store.fail(
        running.job_id,
        running.lease_token,
        error="terminal failure",
        category=WorkflowFailureCategory.PERMANENT,
        retryable=False,
    )

    second = store.allocate_snapshot_generation()
    assert store.accept_snapshot_generation(second)
    zero_cursor = store.activate_schedule(
        project_id=project_id,
        task_id=task_id,
        decision_revision="decision-blocked",
        snapshot_generation=second,
    )
    assert store.reconcile_schedule(
        project_id=project_id,
        task_id=task_id,
        snapshot_generation=second,
        job_generation=zero_cursor.job_generation,
        specs=(),
        record_authority_cut=True,
        authority_kind="managed_zero_job",
    ).accepted
    assert len(
        store.current_exhausted_jobs(project_id=project_id, task_id=task_id)
    ) == 1
    assert store.publish_snapshot_generation(second, lambda: None)[0]
    assert not store.current_exhausted_jobs(project_id=project_id, task_id=task_id)
    store.close()

    reopened = WorkflowJobStore(str(database))
    assert not reopened.current_exhausted_jobs(
        project_id=project_id, task_id=task_id
    )
    later = reopened.allocate_snapshot_generation()
    assert reopened.accept_snapshot_generation(later)
    assert reopened.reconcile_snapshot_membership(
        snapshot_generation=later,
        authoritative_project_ids=(project_id,),
        expected_identities=((project_id, task_id),),
    ).accepted
    unchanged = reopened.activate_schedule(
        project_id=project_id,
        task_id=task_id,
        decision_revision="decision-blocked",
        snapshot_generation=later,
    )
    # A bounded-but-unselected task advances the durable cursor without
    # materializing another schedule. That mutable cursor must not invalidate
    # the already-published retirement cut.
    assert unchanged.materialized
    assert reopened.publish_snapshot_generation(later, lambda: None)[0]
    assert not reopened.current_exhausted_jobs(
        project_id=project_id, task_id=task_id
    )
    reopened.close()


def test_unpublished_or_skipped_zero_job_cut_stays_fail_closed(store):
    project_id = "project-1"
    task_id = "TASK-SKIPPED-CUT"
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
        decision_revision="decision-job",
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
                idempotency_key="skipped:first",
            ),
        ),
    ).accepted
    assert store.publish_snapshot_generation(first, lambda: None)[0]
    running = claim(store, task_id=task_id)
    assert running is not None
    store.fail(
        running.job_id,
        running.lease_token,
        error="terminal failure",
        category=WorkflowFailureCategory.PERMANENT,
        retryable=False,
    )

    skipped = store.allocate_snapshot_generation()
    assert store.accept_snapshot_generation(skipped)
    skipped_cursor = store.activate_schedule(
        project_id=project_id,
        task_id=task_id,
        decision_revision="decision-zero",
        snapshot_generation=skipped,
    )
    assert store.reconcile_schedule(
        project_id=project_id,
        task_id=task_id,
        snapshot_generation=skipped,
        job_generation=skipped_cursor.job_generation,
        specs=(),
        record_authority_cut=True,
    ).accepted

    later = store.allocate_snapshot_generation()
    assert store.accept_snapshot_generation(later)
    assert store.publish_snapshot_generation(later, lambda: None)[0]
    assert len(
        store.current_exhausted_jobs(project_id=project_id, task_id=task_id)
    ) == 1


@pytest.mark.parametrize(
    ("authority_kind", "decision_revision", "snapshot_shape"),
    (
        ("unknown_authority", "decision-zero", "null"),
        ("managed_zero_job", "decision-zero", "null"),
        ("terminal_audit_handoff", "missing-handoff", "null"),
        ("terminal_audit_handoff", "decision-zero", "published"),
        ("terminal_audit_handoff", " ", "null"),
        ("lifecycle_final", "lifecycle-final:Open", "published"),
        ("managed_zero_job", "wrong-decision", "published"),
    ),
)
def test_malformed_retirement_proofs_fail_closed(
    store,
    authority_kind,
    decision_revision,
    snapshot_shape,
):
    project_id = "project-1"
    task_id = "TASK-MALFORMED-PROOF"
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
        decision_revision="decision-job",
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
                idempotency_key="malformed:first",
            ),
        ),
    ).accepted
    assert store.publish_snapshot_generation(first, lambda: None)[0]
    running = claim(store, task_id=task_id)
    assert running is not None
    exhausted = store.fail(
        running.job_id,
        running.lease_token,
        error="terminal failure",
        category=WorkflowFailureCategory.PERMANENT,
        retryable=False,
    )

    second = store.allocate_snapshot_generation()
    assert store.accept_snapshot_generation(second)
    assert store.reconcile_snapshot_membership(
        snapshot_generation=second,
        authoritative_project_ids=(project_id,),
        expected_identities=(),
    ).accepted
    zero_cursor = store.activate_schedule(
        project_id=project_id,
        task_id=task_id,
        decision_revision="decision-zero",
        snapshot_generation=second,
    )
    assert store.reconcile_schedule(
        project_id=project_id,
        task_id=task_id,
        snapshot_generation=second,
        job_generation=zero_cursor.job_generation,
        specs=(),
        record_authority_cut=True,
    ).accepted
    assert store.publish_snapshot_generation(second, lambda: None)[0]
    assert not store.current_exhausted_jobs(
        project_id=project_id, task_id=task_id
    )

    store._conn.execute(  # noqa: SLF001 - corrupt the persisted proof shape
        """
        UPDATE workflow_job_retirements
           SET authority_kind = ?, decision_revision = ?,
               snapshot_generation = ?
         WHERE job_id = ?
        """,
        (
            authority_kind,
            decision_revision,
            second if snapshot_shape == "published" else None,
            exhausted.job_id,
        ),
    )
    store._conn.commit()  # noqa: SLF001

    assert store.current_exhausted_jobs(
        project_id=project_id, task_id=task_id
    ) == (exhausted,)
    assert store.health_snapshot()["current_states"]["exhausted"] == 1


def test_lifecycle_authority_rejects_nonfinal_status(store):
    snapshot = store.allocate_snapshot_generation()
    assert store.accept_snapshot_generation(snapshot)

    with pytest.raises(ValueError, match="lifecycle-final"):
        store.record_lifecycle_final_authority(
            project_id="project-1",
            task_id="TASK-NONFINAL",
            status="Open",
            snapshot_generation=snapshot,
        )

    assert store._conn.execute(  # noqa: SLF001 - no invalid proof persisted
        "SELECT COUNT(*) FROM workflow_job_retirements"
    ).fetchone()[0] == 0


def test_lifecycle_authority_rejects_active_membership_relationship(store):
    project_id = "project-1"
    task_id = "TASK-STILL-ACTIVE"
    snapshot = store.allocate_snapshot_generation()
    assert store.accept_snapshot_generation(snapshot)
    assert store.reconcile_snapshot_membership(
        snapshot_generation=snapshot,
        authoritative_project_ids=(project_id,),
        expected_identities=((project_id, task_id),),
    ).accepted

    with pytest.raises(WorkflowJobStoreError, match="active membership"):
        store.record_lifecycle_final_authority(
            project_id=project_id,
            task_id=task_id,
            status="Merged",
            snapshot_generation=snapshot,
        )


def test_managed_authority_kind_must_match_job_cut(store):
    snapshot = store.allocate_snapshot_generation()
    assert store.accept_snapshot_generation(snapshot)
    cursor = store.activate_schedule(
        project_id="project-1",
        task_id="TASK-KIND-MISMATCH",
        decision_revision="zero-job",
        snapshot_generation=snapshot,
    )

    with pytest.raises(ValueError, match="does not match"):
        store.reconcile_schedule(
            project_id="project-1",
            task_id="TASK-KIND-MISMATCH",
            snapshot_generation=snapshot,
            job_generation=cursor.job_generation,
            specs=(),
            record_authority_cut=True,
            authority_kind="managed_decision",
        )


def test_published_replay_cannot_retire_its_own_exhausted_job(store):
    project_id = "project-1"
    task_id = "TASK-EXHAUSTED-REPLAY"
    first = store.allocate_snapshot_generation()
    assert store.accept_snapshot_generation(first)
    assert store.reconcile_snapshot_membership(
        snapshot_generation=first,
        authoritative_project_ids=(project_id,),
        expected_identities=((project_id, task_id),),
    ).accepted
    first_cursor = store.activate_schedule(
        project_id=project_id,
        task_id=task_id,
        decision_revision="unchanged-decision",
        snapshot_generation=first,
    )
    current_spec = WorkflowJobSpec(
        project_id=project_id,
        task_id=task_id,
        generation=first_cursor.job_generation,
        action="integration_landing_refresh",
        idempotency_key="replay:current",
    )
    assert store.reconcile_schedule(
        project_id=project_id,
        task_id=task_id,
        snapshot_generation=first,
        job_generation=first_cursor.job_generation,
        specs=(current_spec,),
        record_authority_cut=True,
    ).accepted
    assert store.publish_snapshot_generation(first, lambda: None)[0]
    running = claim(store, task_id=task_id)
    assert running is not None
    exhausted = store.fail(
        running.job_id,
        running.lease_token,
        error="terminal failure",
        category=WorkflowFailureCategory.PERMANENT,
        retryable=False,
    )

    second = store.allocate_snapshot_generation()
    assert store.accept_snapshot_generation(second)
    replay_cursor = store.activate_schedule(
        project_id=project_id,
        task_id=task_id,
        decision_revision="unchanged-decision",
        snapshot_generation=second,
    )
    assert replay_cursor.job_generation == first_cursor.job_generation
    assert store.reconcile_schedule(
        project_id=project_id,
        task_id=task_id,
        snapshot_generation=second,
        job_generation=replay_cursor.job_generation,
        specs=(current_spec,),
        record_authority_cut=True,
    ).accepted
    assert store.publish_snapshot_generation(second, lambda: None)[0]

    assert store.current_exhausted_jobs(
        project_id=project_id, task_id=task_id
    ) == (exhausted,)


def test_managed_zero_job_cut_does_not_retire_existing_event_exhaustion(store):
    project_id = "project-1"
    task_id = "TASK-DOMAIN-SCOPE"
    event = store.materialize_event(
        project_id=project_id,
        task_id=task_id,
        decision_revision="event-generation",
        action="epic_cleanup",
        idempotency_namespace="cleanup",
        scheduling_lane="epic-event:epic_cleanup",
    )
    assert event.job is not None
    event_running = claim(store, task_id=task_id)
    assert event_running is not None
    event_exhausted = store.fail(
        event_running.job_id,
        event_running.lease_token,
        error="event terminal failure",
        category=WorkflowFailureCategory.PERMANENT,
        retryable=False,
    )

    snapshot = store.allocate_snapshot_generation()
    assert store.accept_snapshot_generation(snapshot)
    cursor = store.activate_schedule(
        project_id=project_id,
        task_id=task_id,
        decision_revision="managed-zero-job",
        snapshot_generation=snapshot,
    )
    assert store.reconcile_schedule(
        project_id=project_id,
        task_id=task_id,
        snapshot_generation=snapshot,
        job_generation=cursor.job_generation,
        specs=(),
        record_authority_cut=True,
    ).accepted
    assert store.publish_snapshot_generation(snapshot, lambda: None)[0]

    assert store.current_exhausted_jobs(
        project_id=project_id, task_id=task_id
    ) == (event_exhausted,)


def test_concurrent_publication_serializes_exact_zero_job_authority(tmp_path):
    database = tmp_path / "concurrent-authority.sqlite3"
    store = WorkflowJobStore(str(database))
    peer = WorkflowJobStore(str(database))
    project_id = "project-1"
    task_id = "TASK-CONCURRENT-CUT"
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
        decision_revision="decision-job",
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
                idempotency_key="concurrent:first",
            ),
        ),
    ).accepted
    assert store.publish_snapshot_generation(first, lambda: None)[0]
    running = claim(store, task_id=task_id)
    assert running is not None
    store.fail(
        running.job_id,
        running.lease_token,
        error="terminal failure",
        category=WorkflowFailureCategory.PERMANENT,
        retryable=False,
    )

    second = store.allocate_snapshot_generation()
    assert store.accept_snapshot_generation(second)
    zero_cursor = store.activate_schedule(
        project_id=project_id,
        task_id=task_id,
        decision_revision="decision-zero",
        snapshot_generation=second,
    )
    assert store.reconcile_schedule(
        project_id=project_id,
        task_id=task_id,
        snapshot_generation=second,
        job_generation=zero_cursor.job_generation,
        specs=(),
        record_authority_cut=True,
    ).accepted

    publication_started = threading.Event()
    release_publication = threading.Event()
    allocation_completed = threading.Event()

    def publish():
        publication_started.set()
        assert release_publication.wait(timeout=2)

    def allocate_peer_generation():
        generation = peer.allocate_snapshot_generation()
        allocation_completed.set()
        return generation

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            publication = pool.submit(
                store.publish_snapshot_generation, second, publish
            )
            assert publication_started.wait(timeout=2)
            allocation = pool.submit(allocate_peer_generation)
            assert not allocation_completed.wait(timeout=0.05)
            release_publication.set()
            assert publication.result(timeout=2)[0]
            assert allocation.result(timeout=2) == second + 1

        assert not store.current_exhausted_jobs(
            project_id=project_id, task_id=task_id
        )
    finally:
        release_publication.set()
        peer.close()
        store.close()


def test_terminal_audit_handoff_retires_only_prior_managed_exhaustion(store):
    project_id = "project-1"
    task_id = "TASK-AUDIT-HANDOFF"
    snapshot = store.allocate_snapshot_generation()
    assert store.accept_snapshot_generation(snapshot)
    assert store.reconcile_snapshot_membership(
        snapshot_generation=snapshot,
        authoritative_project_ids=(project_id,),
        expected_identities=((project_id, task_id),),
    ).accepted
    cursor = store.activate_schedule(
        project_id=project_id,
        task_id=task_id,
        decision_revision="integration-decision",
        snapshot_generation=snapshot,
    )
    assert store.reconcile_schedule(
        project_id=project_id,
        task_id=task_id,
        snapshot_generation=snapshot,
        job_generation=cursor.job_generation,
        specs=(
            WorkflowJobSpec(
                project_id=project_id,
                task_id=task_id,
                generation=cursor.job_generation,
                action="integration_landing_refresh",
                idempotency_key="handoff:managed",
            ),
        ),
    ).accepted
    assert store.publish_snapshot_generation(snapshot, lambda: None)[0]
    running = claim(store, task_id=task_id)
    assert running is not None

    audit = store.enqueue_replacing_lane(
        WorkflowJobSpec(
            project_id=project_id,
            task_id=task_id,
            generation="audit-generation",
            action="terminal_audit",
            idempotency_key="handoff:audit",
            scheduling_lane="terminal-audit:Done",
        ),
        source_generation=2,
        retire_managed_exhaustion=True,
    )
    assert audit.accepted and audit.job is not None
    store.fail(
        running.job_id,
        running.lease_token,
        error="managed terminal failure after handoff",
        category=WorkflowFailureCategory.PERMANENT,
        retryable=False,
    )
    assert not store.current_exhausted_jobs(project_id=project_id, task_id=task_id)
    audit_running = claim(store, task_id=task_id)
    assert audit_running is not None and audit_running.job_id == audit.job.job_id
    store.fail(
        audit_running.job_id,
        audit_running.lease_token,
        error="audit terminal failure",
        category=WorkflowFailureCategory.PERMANENT,
        retryable=False,
    )
    assert [
        job.job_id
        for job in store.current_exhausted_jobs(
            project_id=project_id, task_id=task_id
        )
    ] == [audit.job.job_id]

    checkpoint = store.capture_snapshot_authority(
        authoritative_project_ids=(),
        evaluated_identities=((project_id, task_id),),
        full_project_scope=False,
    )
    replacement = store.allocate_snapshot_generation()
    assert store.accept_snapshot_generation(replacement)
    replacement_cursor = store.activate_schedule(
        project_id=project_id,
        task_id=task_id,
        decision_revision="later-zero-job",
        snapshot_generation=replacement,
    )
    assert store.reconcile_schedule(
        project_id=project_id,
        task_id=task_id,
        snapshot_generation=replacement,
        job_generation=replacement_cursor.job_generation,
        specs=(),
        record_authority_cut=True,
    ).accepted
    assert store.restore_snapshot_authority(
        checkpoint, snapshot_generation=replacement
    )
    handoff = store._conn.execute(  # noqa: SLF001 - exact authority proof
        "SELECT authority_kind, snapshot_generation "
        "FROM workflow_job_retirements WHERE job_id = ?",
        (running.job_id,),
    ).fetchone()
    assert handoff is not None
    assert handoff["authority_kind"] == "terminal_audit_handoff"
    assert handoff["snapshot_generation"] is None
    assert [
        job.job_id
        for job in store.current_exhausted_jobs(
            project_id=project_id, task_id=task_id
        )
    ] == [audit.job.job_id]


def test_published_lifecycle_cut_survives_membership_until_explicit_rearm(store):
    project_id = "project-1"
    task_id = "EPIC-FINAL"
    cleanup = store.materialize_event(
        project_id=project_id,
        task_id=task_id,
        decision_revision="cleanup-generation",
        action="epic_cleanup",
        idempotency_namespace="epic-cleanup",
        scheduling_lane="epic-event:epic_cleanup",
    )
    assert cleanup.job is not None
    running = claim(store, task_id=task_id)
    assert running is not None
    snapshot = store.allocate_snapshot_generation()
    assert store.accept_snapshot_generation(snapshot)
    assert store.record_lifecycle_final_authority(
        project_id=project_id,
        task_id=task_id,
        status="Merged",
        snapshot_generation=snapshot,
    ) == 1
    store.fail(
        running.job_id,
        running.lease_token,
        error="cleanup terminal failure after authority staged",
        category=WorkflowFailureCategory.PERMANENT,
        retryable=False,
    )
    assert len(
        store.current_exhausted_jobs(project_id=project_id, task_id=task_id)
    ) == 1
    assert store.publish_snapshot_generation(snapshot, lambda: None)[0]
    assert not store.current_exhausted_jobs(project_id=project_id, task_id=task_id)

    membership_only = store.allocate_snapshot_generation()
    assert store.accept_snapshot_generation(membership_only)
    assert store.reconcile_snapshot_membership(
        snapshot_generation=membership_only,
        authoritative_project_ids=(project_id,),
        expected_identities=((project_id, task_id),),
    ).accepted
    assert store.publish_snapshot_generation(membership_only, lambda: None)[0]
    assert not store.current_exhausted_jobs(
        project_id=project_id, task_id=task_id
    )

    rearmed = store.rearm_terminal_job(
        cleanup.job.job_id,
        generation=cleanup.job.generation,
        phase="queued",
        reason="new exact lifecycle authority",
    )
    assert rearmed.state is WorkflowJobState.QUEUED
    rerun = claim(store, task_id=task_id)
    assert rerun is not None
    store.fail(
        rerun.job_id,
        rerun.lease_token,
        error="new activation failed",
        category=WorkflowFailureCategory.PERMANENT,
        retryable=False,
    )
    assert len(
        store.current_exhausted_jobs(project_id=project_id, task_id=task_id)
    ) == 1


def test_snapshot_rollback_cannot_restore_retirement_over_explicit_rearm(store):
    project_id = "project-1"
    task_id = "EPIC-REARM-ROLLBACK"
    cleanup = store.materialize_event(
        project_id=project_id,
        task_id=task_id,
        decision_revision="cleanup-generation",
        action="epic_cleanup",
        idempotency_namespace="epic-cleanup",
        scheduling_lane="epic-event:epic_cleanup",
    )
    assert cleanup.job is not None
    running = claim(store, task_id=task_id)
    assert running is not None
    exhausted = store.fail(
        running.job_id,
        running.lease_token,
        error="initial cleanup failed",
        category=WorkflowFailureCategory.PERMANENT,
        retryable=False,
    )

    lifecycle = store.allocate_snapshot_generation()
    assert store.accept_snapshot_generation(lifecycle)
    assert store.record_lifecycle_final_authority(
        project_id=project_id,
        task_id=task_id,
        status="Merged",
        snapshot_generation=lifecycle,
    ) == 1
    assert store.publish_snapshot_generation(lifecycle, lambda: None)[0]
    assert not store.current_exhausted_jobs(
        project_id=project_id, task_id=task_id
    )

    checkpoint = store.capture_snapshot_authority(
        authoritative_project_ids=(project_id,),
        evaluated_identities=((project_id, task_id),),
        full_project_scope=True,
    )
    failed_snapshot = store.allocate_snapshot_generation()
    assert store.accept_snapshot_generation(failed_snapshot)

    rearmed = store.rearm_terminal_job(
        exhausted.job_id,
        generation=exhausted.generation,
        phase="queued",
        reason="fresh lifecycle activation",
    )
    assert rearmed.state is WorkflowJobState.QUEUED
    assert store.restore_snapshot_authority(
        checkpoint, snapshot_generation=failed_snapshot
    )
    assert store.get(exhausted.job_id).state is WorkflowJobState.QUEUED
    assert store._conn.execute(  # noqa: SLF001 - exact ABA fence assertion
        "SELECT 1 FROM workflow_job_retirements WHERE job_id = ?",
        (exhausted.job_id,),
    ).fetchone() is None

    rerun = claim(store, task_id=task_id)
    assert rerun is not None and rerun.job_id == exhausted.job_id
    failed_again = store.fail(
        rerun.job_id,
        rerun.lease_token,
        error="fresh activation failed",
        category=WorkflowFailureCategory.PERMANENT,
        retryable=False,
    )
    assert store.current_exhausted_jobs(
        project_id=project_id, task_id=task_id
    ) == (failed_again,)


def test_snapshot_rollback_cannot_release_live_quarantined_call(store):
    project_id = "project-1"
    task_id = "TASK-QUARANTINE-ROLLBACK"
    published = store.allocate_snapshot_generation()
    assert store.accept_snapshot_generation(published)
    assert store.reconcile_snapshot_membership(
        snapshot_generation=published,
        authoritative_project_ids=(project_id,),
        expected_identities=((project_id, task_id),),
    ).accepted
    cursor = store.activate_schedule(
        project_id=project_id,
        task_id=task_id,
        decision_revision="managed-call",
        snapshot_generation=published,
    )
    assert store.reconcile_schedule(
        project_id=project_id,
        task_id=task_id,
        snapshot_generation=published,
        job_generation=cursor.job_generation,
        specs=(
            WorkflowJobSpec(
                project_id=project_id,
                task_id=task_id,
                generation=cursor.job_generation,
                action="authority_revocation",
                idempotency_key="quarantine-rollback:managed",
            ),
        ),
    ).accepted
    assert store.publish_snapshot_generation(published, lambda: None)[0]
    running = claim(store, task_id=task_id)
    assert running is not None

    checkpoint = store.capture_snapshot_authority(
        authoritative_project_ids=(project_id,),
        evaluated_identities=((project_id, task_id),),
        full_project_scope=True,
    )
    failed_snapshot = store.allocate_snapshot_generation()
    assert store.accept_snapshot_generation(failed_snapshot)
    quarantined = store.quarantine_owned(
        running.job_id,
        running.lease_token,
        category=WorkflowFailureCategory.TIMEOUT,
        error="detached adapter did not return",
    )

    assert store.restore_snapshot_authority(
        checkpoint, snapshot_generation=failed_snapshot
    )
    preserved = store.get(quarantined.job_id)
    assert preserved.state is WorkflowJobState.RUNNING
    assert preserved.phase == "quarantined"
    assert preserved.lease_token == quarantined.lease_token
    assert preserved.lease_expires_at is None

    replacement = store.enqueue(
        WorkflowJobSpec(
            project_id=project_id,
            task_id=task_id,
            generation="replacement",
            action="direct_owner_claim",
            idempotency_key="quarantine-rollback:replacement",
        )
    )
    assert claim(store, task_id=task_id) is None
    store.settle_quarantined_call(
        quarantined.job_id,
        quarantined.lease_token,
        operation="apply",
        failure_category=WorkflowFailureCategory.PERMANENT,
        error="late adapter failure",
        retryable=False,
    )
    released = claim(store, task_id=task_id)
    assert released is not None and released.job_id == replacement.job_id


def test_missing_event_cursor_generation_fails_closed(store):
    write = store.materialize_event(
        project_id="project-1",
        task_id="TASK-AMBIGUOUS",
        decision_revision="event-1",
        action="implementation_retry",
        idempotency_namespace="implementation-event",
        scheduling_lane="event:implementation:fact",
        ordering_namespace="implementation-ordering",
        source_generation=1,
        source_revision="source-1",
    )
    assert write.job is not None
    running = claim(store, task_id="TASK-AMBIGUOUS")
    assert running is not None
    failed = store.fail(
        running.job_id,
        running.lease_token,
        error="terminal failure",
        category=WorkflowFailureCategory.PERMANENT,
        retryable=False,
    )
    store._conn.execute(  # noqa: SLF001 - simulate persisted partial authority
        """
        UPDATE workflow_event_cursors
           SET event_generation = 'missing-generation'
         WHERE project_id = 'project-1' AND task_id = 'TASK-AMBIGUOUS'
        """
    )
    store._conn.commit()  # noqa: SLF001

    assert store.current_exhausted_jobs(
        project_id="project-1", task_id="TASK-AMBIGUOUS"
    ) == (failed,)
    assert store.health_snapshot()["current_states"]["exhausted"] == 1


def test_unowned_exhaustion_remains_current_health(store):
    job = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-1",
            generation="generation-1",
            action="implementation_retry",
            idempotency_key="direct:1",
        )
    )
    running = claim(store)
    assert running is not None
    assert running.job_id == job.job_id
    store.fail(
        running.job_id,
        running.lease_token,
        error="terminal failure",
        category=WorkflowFailureCategory.PERMANENT,
        retryable=False,
    )

    health = store.health_snapshot()
    assert health["states"]["exhausted"] == 1
    assert health["current_states"]["exhausted"] == 1


def test_terminal_audit_lane_materialization_requires_exact_current_record(
    store, clock,
):
    evidence = "e" * 64
    generation = "audit:" + "a" * 64
    write = store.enqueue_replacing_lane(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-1",
            generation=generation,
            action="terminal_audit",
            idempotency_key="terminal-audit:project-1:TASK-1:Done:evidence",
            scheduling_lane="terminal-audit:Done",
            expected_evidence_revision=evidence,
        ),
        source_generation=7,
    )
    assert write.job is not None
    arguments = {
        "project_id": "project-1",
        "task_id": "TASK-1",
        "audit_id": "audit-1",
        "target_state": "Done",
        "evidence_fingerprint": evidence,
        "audit_generation": generation,
        "source_generation": 7,
    }

    assert store.terminal_audit_lane_materialized(**arguments)
    assert store.terminal_audit_lane_materialized(
        **arguments,
        obligation_action="terminal_audit_recovery",
    )
    for override in (
        {"target_state": "Merged"},
        {"evidence_fingerprint": "f" * 64},
        {"audit_generation": "audit:" + "b" * 64},
        {"source_generation": 8},
    ):
        assert not store.terminal_audit_lane_materialized(
            **{**arguments, **override}
        )

    running = claim(store)
    assert running is not None
    store.checkpoint(
        running.job_id,
        running.lease_token,
        phase="running",
        checkpoint={"audit_id": "audit-1"},
    )
    assert store.terminal_audit_lane_materialized(
        **arguments,
        obligation_action="terminal_audit_recovery",
    )
    assert not store.terminal_audit_lane_materialized(
        **{**arguments, "audit_id": "audit-sibling"}
    )
    store.checkpoint(
        running.job_id,
        running.lease_token,
        phase="finalizing",
        checkpoint={"audit_id": "audit-1"},
    )
    assert store.terminal_audit_lane_materialized(**arguments)
    clock.advance(31)
    assert not store.terminal_audit_lane_materialized(**arguments)
    assert not store.terminal_audit_lane_materialized(
        **arguments,
        obligation_action="terminal_audit_recovery",
    )

    store.cancel(
        write.job.job_id,
        generation=write.job.generation,
        reason="record retired",
    )
    assert not store.terminal_audit_lane_materialized(**arguments)


@pytest.mark.parametrize("terminal_state", ["completed", "exhausted"])
def test_pending_terminal_audit_rejects_terminal_job_as_liveness_proof(
    store, terminal_state
):
    evidence = "e" * 64
    generation = "audit:" + "a" * 64
    write = store.enqueue_replacing_lane(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-1",
            generation=generation,
            action="terminal_audit",
            idempotency_key=f"terminal-audit:{terminal_state}",
            phase="queued",
            scheduling_lane="terminal-audit:Done",
            expected_evidence_revision=evidence,
        ),
        source_generation=7,
    )
    assert write.job is not None
    running = claim(store)
    assert running is not None
    if terminal_state == "completed":
        store.complete(running.job_id, running.lease_token)
    else:
        store.fail(
            running.job_id,
            running.lease_token,
            error="terminal failure",
            category=WorkflowFailureCategory.PERMANENT,
            retryable=False,
        )

    arguments = {
        "project_id": "project-1",
        "task_id": "TASK-1",
        "audit_id": "audit-1",
        "target_state": "Done",
        "evidence_fingerprint": evidence,
        "audit_generation": generation,
        "source_generation": 7,
    }
    assert not store.terminal_audit_lane_materialized(**arguments)
    assert not store.terminal_audit_lane_materialized(
        **arguments, obligation_action="terminal_audit_recovery"
    )


def test_payload_round_trips_across_store_restart(tmp_path, clock):
    path = str(tmp_path / "payload-restart.sqlite3")
    first = WorkflowJobStore(path, clock=clock)
    created = first.enqueue(
        spec(payload={"nested": {"enabled": True}, "targets": ["a", "b"]})
    )
    first.close()

    reopened = WorkflowJobStore(path, clock=clock)
    try:
        observed = reopened.get(created.job_id)
        assert observed.to_dict()["payload"] == {
            "nested": {"enabled": True},
            "targets": ["a", "b"],
        }
        assert observed.payload["targets"] == ("a", "b")
        assert reopened.enqueue(
            spec(payload={"targets": ["a", "b"], "nested": {"enabled": True}})
        ).job_id == created.job_id
        reopened.integrity_check()
    finally:
        reopened.close()


def test_idempotency_is_project_scoped(store):
    first = store.enqueue(spec(project="project-a"))
    second = store.enqueue(spec(project="project-b"))

    assert first.job_id != second.job_id
    assert len(store.list_jobs(project_id="project-a")) == 1
    assert len(store.list_jobs(project_id="project-b")) == 1


def test_concurrent_identical_enqueues_create_one_row(tmp_path, clock):
    path = str(tmp_path / "concurrent-enqueue.sqlite3")
    stores = [WorkflowJobStore(path, clock=clock) for _ in range(8)]
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            jobs = list(pool.map(lambda item: item.enqueue(spec()), stores))

        assert len({job.job_id for job in jobs}) == 1
        assert len(stores[0].list_jobs()) == 1
    finally:
        for item in stores:
            item.close()


def test_claim_order_is_priority_then_available_time_then_fifo(store, clock):
    later_low = store.enqueue(spec("later-low", task="T-1", priority=50))
    clock.advance(1)
    first_high = store.enqueue(spec("first-high", task="T-2", priority=10))
    clock.advance(1)
    second_high = store.enqueue(spec("second-high", task="T-3", priority=10))

    assert claim(store).job_id == first_high.job_id
    assert claim(store).job_id == second_high.job_id
    assert claim(store).job_id == later_low.job_id


def test_due_projection_is_bounded_deterministic_and_non_mutating(store):
    jobs = [
        store.enqueue(spec(f"key-{index}", task=f"T-{index}")) for index in range(4)
    ]

    due = store.due_jobs(limit=2)

    assert [job.job_id for job in due] == [jobs[0].job_id, jobs[1].job_id]
    assert all(job.state is WorkflowJobState.QUEUED for job in store.list_jobs())
    with pytest.raises(ValueError, match="between"):
        store.due_jobs(limit=MAX_SCAN_LIMIT + 1)


def test_claim_filters_exact_project_task_generation_and_action(store):
    wanted = store.enqueue(
        spec("wanted", task="T", generation="g2", action="review_refresh")
    )
    store.enqueue(spec("old", task="T", generation="g1", action="review_refresh"))
    store.enqueue(spec("other-action", task="T", generation="g2", action="audit"))
    store.enqueue(
        spec(
            "other-project",
            project="project-b",
            task="T",
            generation="g2",
            action="review_refresh",
        )
    )

    observed = claim(
        store,
        project_id="project-a",
        task_id="T",
        generation="g2",
        actions=("review_refresh",),
    )

    assert observed.job_id == wanted.job_id


def test_claimable_probe_shares_exact_claim_eligibility_without_mutation(store, clock):
    eligible = store.enqueue(spec("eligible", task="ELIGIBLE", action="review_refresh"))
    future = store.enqueue(spec("future", task="FUTURE", action="review_refresh"))
    future_claim = claim(store, task_id="FUTURE", actions=("review_refresh",))
    store.fail(
        future_claim.job_id,
        future_claim.lease_token,
        category=WorkflowFailureCategory.TRANSIENT,
        error="not due",
        retryable=True,
        retry_delay_seconds=60,
    )
    store.enqueue(spec("serial-first", task="SERIAL", action="review_refresh"))
    blocked = store.enqueue(
        spec("serial-second", task="SERIAL", action="integration_attempt")
    )
    running = claim(store, task_id="SERIAL", actions=("review_refresh",))
    before = {
        job.job_id: (job.state, job.attempts, job.lease_token)
        for job in store.list_jobs()
    }

    assert store.has_claimable(project_ids=("project-a",), actions=("review_refresh",))
    assert not store.has_claimable(
        project_id="project-a",
        task_id="FUTURE",
        actions=("review_refresh",),
    )
    assert not store.has_claimable(
        project_id="project-a",
        task_id="SERIAL",
        actions=("integration_attempt",),
    )
    assert not store.has_claimable(project_id="project-a", actions=("terminal_audit",))
    after = {
        job.job_id: (job.state, job.attempts, job.lease_token)
        for job in store.list_jobs()
    }

    assert before == after
    assert (
        claim(
            store,
            project_ids=("project-a",),
            actions=("review_refresh",),
        ).job_id
        == eligible.job_id
    )
    assert store.get(future.job_id).state is WorkflowJobState.RETRY_WAIT
    assert store.get(blocked.job_id).state is WorkflowJobState.QUEUED
    assert store.get(running.job_id).state is WorkflowJobState.RUNNING
    assert clock.now == 1000.0


def test_delayed_claimable_probe_uses_post_lock_time_for_retry_eligibility(
    store, clock
):
    store.enqueue(spec(action="review_refresh"))
    running = claim(store, actions=("review_refresh",))
    store.fail(
        running.job_id,
        running.lease_token,
        category=WorkflowFailureCategory.TRANSIENT,
        error="retry",
        retryable=True,
        retry_delay_seconds=10,
    )
    probe_started = threading.Event()

    def delayed_probe():
        probe_started.set()
        return store.has_claimable(actions=("review_refresh",))

    pool = ThreadPoolExecutor(max_workers=1)
    store._lock.acquire()  # noqa: SLF001 - deliberate lock-wait regression
    try:
        future = pool.submit(delayed_probe)
        assert probe_started.wait(timeout=2)
        clock.advance(20)
    finally:
        store._lock.release()  # noqa: SLF001
    try:
        assert future.result(timeout=2) is True
    finally:
        pool.shutdown(wait=True)

    assert store.get(running.job_id).state is WorkflowJobState.RETRY_WAIT
    assert store.get(running.job_id).attempts == 1


def test_claim_filters_allowed_projects_with_durable_fair_rotation(store):
    project_a_first = store.enqueue(
        spec("a-1", project="project-a", task="A-1")
    )
    project_a_second = store.enqueue(
        spec("a-2", project="project-a", task="A-2")
    )
    project_b = store.enqueue(spec("b-1", project="project-b", task="B-1"))
    project_c = store.enqueue(spec("c-1", project="project-c", task="C-1"))
    excluded = store.enqueue(spec("d-1", project="project-d", task="D-1"))

    observed = tuple(
        claim(
            store,
            project_ids=("project-a", "project-b", "project-c"),
            fair_across_projects=True,
        )
        for _ in range(4)
    )

    assert [job.job_id for job in observed] == [
        project_a_first.job_id,
        project_b.job_id,
        project_c.job_id,
        project_a_second.job_id,
    ]
    assert store.get(excluded.job_id).state is WorkflowJobState.QUEUED
    assert store.health_snapshot()["fair_project_count"] == 3
    with pytest.raises(ValueError, match="mutually exclusive"):
        claim(store, project_id="project-a", project_ids=("project-a",))
    with pytest.raises(ValueError, match="cannot be empty"):
        claim(store, project_ids=())
    with pytest.raises(TypeError, match="must be a sequence"):
        claim(store, project_ids="project-a")  # type: ignore[arg-type]


def test_concurrent_claimers_never_duplicate_ownership(tmp_path, clock):
    path = str(tmp_path / "concurrent-claim.sqlite3")
    seed = WorkflowJobStore(path, clock=clock)
    for index in range(12):
        seed.enqueue(spec(f"job-{index}", task=f"T-{index}"))
    seed.close()
    stores = [WorkflowJobStore(path, clock=clock) for _ in range(12)]
    try:
        with ThreadPoolExecutor(max_workers=12) as pool:
            claimed = list(
                pool.map(
                    lambda pair: pair[1].claim_next(
                        lease_owner=f"worker-{pair[0]}", lease_seconds=30
                    ),
                    enumerate(stores),
                )
            )

        assert all(job is not None for job in claimed)
        assert len({job.job_id for job in claimed if job is not None}) == 12
        assert all(job.state is WorkflowJobState.RUNNING for job in claimed)
    finally:
        for item in stores:
            item.close()


def test_claim_increments_attempt_and_issues_opaque_lease(store):
    enqueued = store.enqueue(spec())

    running = claim(store)

    assert running.job_id == enqueued.job_id
    assert running.state is WorkflowJobState.RUNNING
    assert running.attempts == 1
    assert running.lease_owner == "worker-a"
    assert running.lease_token
    assert running.lease_expires_at == 1030.0


def test_renew_requires_current_unexpired_token(store, clock):
    store.enqueue(spec())
    running = claim(store)
    clock.advance(5)

    renewed = store.renew(running.job_id, running.lease_token, lease_seconds=60)

    assert renewed.lease_expires_at == 1065.0
    with pytest.raises(WorkflowJobLeaseLost):
        store.renew(running.job_id, "wrong-token", lease_seconds=60)
    clock.advance(61)
    with pytest.raises(WorkflowJobLeaseLost):
        store.renew(running.job_id, running.lease_token, lease_seconds=60)


def test_checkpoint_survives_restart_and_preserves_resume_phase(tmp_path, clock):
    path = str(tmp_path / "restart.sqlite3")
    first = WorkflowJobStore(path, clock=clock)
    first.enqueue(spec())
    running = claim(first)
    checkpointed = first.checkpoint(
        running.job_id,
        running.lease_token,
        phase="effect_applied",
        checkpoint={"review_id": 42, "verified": False},
    )
    first.close()

    reopened = WorkflowJobStore(path, clock=clock)
    try:
        observed = reopened.get(checkpointed.job_id)
        assert observed.phase == "effect_applied"
        assert observed.checkpoint == {"review_id": 42, "verified": False}
        assert [event.event_type for event in reopened.events(observed.job_id)] == [
            "enqueued",
            "claimed",
            "checkpointed",
        ]
        reopened.integrity_check()
    finally:
        reopened.close()


def test_complete_persists_result_and_fences_late_worker(store):
    store.enqueue(spec())
    running = claim(store)

    completed = store.complete(
        running.job_id,
        running.lease_token,
        result_transition={"transition_id": "transition-1", "applied": True},
    )

    assert completed.state is WorkflowJobState.COMPLETED
    assert completed.result_transition["transition_id"] == "transition-1"
    assert completed.completed_at == 1000.0
    assert completed.lease_token is None
    with pytest.raises(WorkflowJobLeaseLost):
        store.complete(running.job_id, running.lease_token)


def _durable_landing_fact(*, revision: str = "a" * 40) -> LandingFact:
    return LandingFact(
        "TASK-A",
        "main",
        revision,
        {
            "kind": "git_ancestry",
            "source_sha": revision,
            "target_sha": "b" * 40,
        },
        "2026-08-09T09:00:00+00:00",
        "project-a",
        state=LandingState.LANDED,
        durable=True,
    )


def test_complete_atomically_persists_idempotent_landing_fact(store):
    store.enqueue(spec(action="integration_landing_refresh", task="TASK-A"))
    running = claim(store)
    fact = _durable_landing_fact()
    reobserved = fact.to_dict()
    reobserved["observed_at"] = "2026-08-09T09:01:00+00:00"

    completed = store.complete(
        running.job_id,
        running.lease_token,
        landing_facts=(fact.to_dict(), reobserved),
    )

    assert completed.state is WorkflowJobState.COMPLETED
    assert store.landing_facts(project_id="project-a", task_id="TASK-A") == (
        fact.to_dict(),
    )
    event = store.events(running.job_id)[-1]
    assert event.payload["landing_facts"] == 2
    assert event.payload["landing_facts_inserted"] == 1


def test_complete_fences_landing_fact_with_stale_lease(store, clock):
    store.enqueue(spec(action="integration_landing_refresh", task="TASK-A"))
    stale = claim(store)
    clock.advance(31)
    current = claim(store)

    with pytest.raises(WorkflowJobLeaseLost):
        store.complete(
            stale.job_id,
            stale.lease_token,
            landing_facts=(_durable_landing_fact().to_dict(),),
        )

    assert store.landing_facts(project_id="project-a", task_id="TASK-A") == ()
    assert store.get(current.job_id).state is WorkflowJobState.RUNNING


def test_complete_rejects_stale_landing_evidence_revision_atomically(store):
    store.enqueue(spec(action="integration_landing_refresh", task="TASK-A"))
    running = claim(store)
    stale = _durable_landing_fact().to_dict()
    stale["revision"] = "c" * 40

    with pytest.raises(WorkflowJobStoreError, match="evidence revision"):
        store.complete(
            running.job_id,
            running.lease_token,
            landing_facts=(stale,),
        )

    assert store.landing_facts(project_id="project-a", task_id="TASK-A") == ()
    assert store.get(running.job_id).state is WorkflowJobState.RUNNING


def test_fail_schedules_retry_then_claims_only_when_due(store, clock):
    store.enqueue(spec(max_attempts=3))
    running = claim(store)

    waiting = store.fail(
        running.job_id,
        running.lease_token,
        category=WorkflowFailureCategory.TRANSPORT,
        error="provider unavailable",
        retryable=True,
        retry_delay_seconds=10,
    )

    assert waiting.state is WorkflowJobState.RETRY_WAIT
    assert waiting.retry_at == 1010.0
    assert claim(store) is None
    clock.advance(10)
    retried = claim(store)
    assert retried.job_id == running.job_id
    assert retried.attempts == 2


def test_nonretryable_failure_is_terminal(store):
    store.enqueue(spec())
    running = claim(store)

    failed = store.fail(
        running.job_id,
        running.lease_token,
        category="permanent",
        error="invalid immutable request",
        retryable=False,
    )

    assert failed.state is WorkflowJobState.EXHAUSTED
    assert failed.failure_category is WorkflowFailureCategory.PERMANENT
    assert failed.completed_at == 1000.0
    assert claim(store) is None


def test_retry_exhaustion_is_terminal_at_max_attempts(store):
    store.enqueue(spec(max_attempts=1))
    running = claim(store)

    exhausted = store.fail(
        running.job_id,
        running.lease_token,
        category="transient",
        error="again",
        retryable=True,
    )

    assert exhausted.state is WorkflowJobState.EXHAUSTED
    assert exhausted.retry_at is None


def test_expired_lease_is_recovered_and_old_worker_is_fenced(store, clock):
    store.enqueue(spec(max_attempts=3))
    first = claim(store)
    clock.advance(31)

    second = claim(store)

    assert second.job_id == first.job_id
    assert second.lease_token != first.lease_token
    assert second.attempts == 2
    with pytest.raises(WorkflowJobLeaseLost):
        store.complete(first.job_id, first.lease_token)
    assert [event.event_type for event in store.events(first.job_id)] == [
        "enqueued",
        "claimed",
        "recovered",
        "claimed",
    ]


def test_expired_final_attempt_becomes_exhausted(store, clock):
    store.enqueue(spec(max_attempts=1))
    running = claim(store)
    clock.advance(31)

    assert store.recover_expired() == 1
    exhausted = store.get(running.job_id)
    assert exhausted.state is WorkflowJobState.EXHAUSTED
    assert exhausted.failure_category is WorkflowFailureCategory.LEASE_EXPIRED
    assert claim(store) is None


def test_exact_owner_can_quarantine_after_deadline_before_replacement_claim(
    store, clock
):
    store.enqueue(spec(max_attempts=3))
    running = claim(store)
    clock.advance(31)

    quarantined = store.quarantine_owned(
        running.job_id,
        running.lease_token,
        category=WorkflowFailureCategory.TIMEOUT,
        error="adapter did not return",
    )

    assert quarantined.state is WorkflowJobState.RUNNING
    assert quarantined.phase == "quarantined"
    assert quarantined.lease_expires_at is None
    assert store.recover_expired() == 0
    assert claim(store) is None
    with pytest.raises(WorkflowJobStoreError, match="quarantined"):
        store.supersede(
            running.job_id,
            generation=running.generation,
            replacement_generation="g2",
            reason="newer generation",
        )
    with pytest.raises(WorkflowJobStoreError, match="quarantined"):
        store.cancel(
            running.job_id,
            generation=running.generation,
            reason="operator cancellation",
        )
    assert store.supersede_task_generation(
        project_id=running.project_id,
        task_id=running.task_id,
        keep_generation="g2",
        reason="newer generation",
    ) == 0
    assert store.events(running.job_id)[-1].event_type == "quarantined"
    store.integrity_check()


def test_late_quarantined_receipt_resumes_same_attempt_without_overlap(store):
    store.enqueue(spec(max_attempts=1))
    running = claim(store)
    store.checkpoint(
        running.job_id,
        running.lease_token,
        phase="effect_pending",
        checkpoint={"effect_observed": False},
    )
    quarantined = store.quarantine_owned(
        running.job_id,
        running.lease_token,
        category=WorkflowFailureCategory.TIMEOUT,
        error="adapter did not return",
    )

    settled = store.settle_quarantined_call(
        quarantined.job_id,
        quarantined.lease_token,
        operation="apply",
        effect_receipt={"external_id": "late-effect"},
    )

    assert settled.state is WorkflowJobState.QUEUED
    assert settled.phase == "effect_returned"
    assert settled.attempts == 0
    assert settled.checkpoint["effect"] == {"external_id": "late-effect"}
    assert settled.lease_owner is None
    resumed = claim(store)
    assert resumed.job_id == running.job_id
    assert resumed.attempts == 1
    assert resumed.lease_token != running.lease_token
    assert store.events(running.job_id)[-1].event_type == "claimed"
    store.integrity_check()


def test_quarantined_control_call_blocks_same_task_data_lane_only(store):
    control = store.enqueue(
        spec(
            "revoke:g1",
            action="authority_revocation",
            scheduling_lane="event:implementation:direct-owner-revocation:claim-1",
        )
    )
    running = claim(store, actions=("authority_revocation",))
    assert running is not None and running.job_id == control.job_id
    store.quarantine_owned(
        running.job_id,
        running.lease_token,
        category=WorkflowFailureCategory.TIMEOUT,
        error="direct-owner revocation adapter did not return",
    )
    blocked = store.enqueue(
        spec(
            "claim:g2",
            generation="g2",
            action="direct_owner_claim",
            scheduling_lane="event:implementation:imperative",
        )
    )
    unrelated = store.enqueue(
        spec(
            "claim:other",
            task="OOMPAH-2",
            action="direct_owner_claim",
            scheduling_lane="event:implementation:imperative",
        )
    )

    selected = claim(store, actions=("direct_owner_claim",))

    assert selected is not None and selected.job_id == unrelated.job_id
    assert store.get(blocked.job_id).state is WorkflowJobState.QUEUED
    assert store.get(control.job_id).phase == "quarantined"


def test_event_replacement_waits_for_exact_quarantine_settlement(store):
    lane = "event:implementation:imperative"
    first = store.materialize_event(
        project_id="project-a",
        task_id="OOMPAH-1",
        decision_revision="revoke-1",
        action="authority_revocation",
        idempotency_namespace="implementation",
        scheduling_lane=lane,
        ordering_namespace="implementation-decision",
        source_generation=store.allocate_event_generation(),
        max_attempts=1,
    ).job
    assert first is not None
    running = claim(store, actions=("authority_revocation",))
    assert running is not None and running.job_id == first.job_id
    quarantined = store.quarantine_owned(
        running.job_id,
        running.lease_token,
        category=WorkflowFailureCategory.TIMEOUT,
        error="authority revocation did not return",
    )

    replacement_write = store.materialize_event(
        project_id="project-a",
        task_id="OOMPAH-1",
        decision_revision="claim-2",
        action="direct_owner_claim",
        idempotency_namespace="implementation",
        scheduling_lane=lane,
        ordering_namespace="implementation-decision",
        source_generation=store.allocate_event_generation(),
    )

    assert replacement_write.job is not None
    assert replacement_write.superseded == 0
    assert store.get(first.job_id).phase == "quarantined"
    assert claim(store, actions=("direct_owner_claim",)) is None

    store.settle_quarantined_call(
        quarantined.job_id,
        quarantined.lease_token,
        operation="apply",
        failure_category=WorkflowFailureCategory.PERMANENT,
        error="late authority revocation failed",
        retryable=False,
    )
    replacement = claim(store, actions=("direct_owner_claim",))
    assert replacement is not None
    assert replacement.job_id == replacement_write.job.job_id


def test_late_quarantined_failure_releases_task_and_spends_attempt(store):
    store.enqueue(spec(max_attempts=1))
    running = claim(store)
    quarantined = store.quarantine_owned(
        running.job_id,
        running.lease_token,
        category=WorkflowFailureCategory.TIMEOUT,
        error="adapter did not return",
    )

    settled = store.settle_quarantined_call(
        quarantined.job_id,
        quarantined.lease_token,
        operation="apply",
        failure_category=WorkflowFailureCategory.UNKNOWN,
        error="late apply failed: RuntimeError",
        retryable=True,
    )

    assert settled.state is WorkflowJobState.EXHAUSTED
    assert settled.phase == "quarantine_recovered"
    assert settled.attempts == 1
    assert settled.lease_owner is None
    assert store.events(running.job_id)[-1].event_type == "quarantine_settled"
    store.integrity_check()


def test_quarantine_recycle_marker_is_exact_and_idempotent(store):
    store.enqueue(spec())
    running = claim(store)
    quarantined = store.quarantine_owned(
        running.job_id,
        running.lease_token,
        category=WorkflowFailureCategory.TIMEOUT,
        error="adapter did not return",
    )

    first = store.mark_quarantine_recycle_requested(
        quarantined.job_id, quarantined.lease_token
    )
    replay = store.mark_quarantine_recycle_requested(
        quarantined.job_id, quarantined.lease_token
    )

    assert replay.checkpoint["quarantine_recycle"] == first.checkpoint[
        "quarantine_recycle"
    ]
    assert [
        event.event_type
        for event in store.events(running.job_id)
        if event.event_type == "quarantine_recycle_requested"
    ] == ["quarantine_recycle_requested"]
    assert store.health_snapshot()["leases"]["quarantined"] == 1
    with pytest.raises(WorkflowJobLeaseLost):
        store.mark_quarantine_recycle_requested(
            quarantined.job_id, "wrong-token"
        )


def test_quarantine_recycle_marker_is_retired_and_replaced_across_lease_aba(store):
    store.enqueue(spec())
    first_claim = claim(store)
    first_quarantine = store.quarantine_owned(
        first_claim.job_id,
        first_claim.lease_token,
        category=WorkflowFailureCategory.TIMEOUT,
        error="first adapter timeout",
    )
    first_marked = store.mark_quarantine_recycle_requested(
        first_quarantine.job_id,
        first_quarantine.lease_token,
    )
    stale_marker = dict(first_marked.checkpoint["quarantine_recycle"])

    first_settlement = store.settle_quarantined_call(
        first_quarantine.job_id,
        first_quarantine.lease_token,
        operation="inspect",
    )
    assert "quarantine_recycle" not in first_settlement.checkpoint

    second_claim = claim(store)
    assert second_claim.lease_token != first_claim.lease_token
    store.checkpoint(
        second_claim.job_id,
        second_claim.lease_token,
        phase="effect_pending",
        checkpoint={"quarantine_recycle": stale_marker},
    )
    second_quarantine = store.quarantine_owned(
        second_claim.job_id,
        second_claim.lease_token,
        category=WorkflowFailureCategory.TIMEOUT,
        error="second adapter timeout",
    )
    second_marked = store.mark_quarantine_recycle_requested(
        second_quarantine.job_id,
        second_quarantine.lease_token,
    )

    replacement = second_marked.checkpoint["quarantine_recycle"]
    assert replacement["lease_token"] == second_claim.lease_token
    assert replacement["lease_owner"] == second_claim.lease_owner
    assert replacement != stale_marker
    requests = [
        event
        for event in store.events(first_claim.job_id)
        if event.event_type == "quarantine_recycle_requested"
    ]
    assert len(requests) == 2
    assert requests[-1].payload["replaced_stale_marker"] is True


def test_expired_recovery_is_bounded(store, clock):
    for index in range(3):
        store.enqueue(spec(f"key-{index}", task=f"T-{index}"))
        claim(store)
    clock.advance(31)

    assert store.recover_expired(limit=2) == 2
    assert len(store.list_jobs(states=(WorkflowJobState.RUNNING,))) == 1
    assert store.recover_expired(limit=2) == 1


def test_preserved_finalizer_cannot_starve_expired_recovery_limit(store, clock):
    store.enqueue(spec("final", task="T-final"))
    finalizing = claim(store)
    store.checkpoint(
        finalizing.job_id,
        finalizing.lease_token,
        phase="finalizing",
        checkpoint={"audit_id": "audit-final", "attempt_id": "attempt-final"},
    )
    store.enqueue(spec("ordinary", task="T-ordinary", action="forge_effect"))
    ordinary = claim(store, actions=("forge_effect",))
    clock.advance(31)

    assert store.recover_expired(limit=1) == 1
    assert store.get(finalizing.job_id).state is WorkflowJobState.RUNNING
    assert store.get(ordinary.job_id).state is WorkflowJobState.QUEUED


def test_sql_filters_apply_before_list_limit(store):
    store.enqueue(spec("ordinary", task="T-ordinary", action="forge_effect"))
    ordinary = claim(store, actions=("forge_effect",))
    store.enqueue(spec("final", task="T-final"))
    finalizing = claim(store, actions=("terminal_audit",))
    store.checkpoint(
        finalizing.job_id,
        finalizing.lease_token,
        phase="finalizing",
        checkpoint={"audit_id": "audit-final", "attempt_id": "attempt-final"},
    )

    selected = store.list_jobs(
        states=(WorkflowJobState.RUNNING,),
        actions=("terminal_audit",),
        phases=("finalizing",),
        limit=1,
    )

    assert [job.job_id for job in selected] == [finalizing.job_id]
    assert store.get(ordinary.job_id).state is WorkflowJobState.RUNNING


def test_abandoned_recovery_can_be_scoped_to_process_owner(store):
    store.enqueue(spec("a", task="T-a"))
    store.enqueue(spec("b", task="T-b"))
    first = store.claim_next(lease_owner="old-a", lease_seconds=30)
    second = store.claim_next(lease_owner="old-b", lease_seconds=30)

    assert store.recover_abandoned(lease_owner="old-a") == 1
    assert store.get(first.job_id).state is WorkflowJobState.QUEUED
    assert store.get(second.job_id).state is WorkflowJobState.RUNNING


def test_preserved_finalizer_cannot_starve_abandoned_recovery_limit(store):
    store.enqueue(spec("final", task="T-final"))
    finalizing = claim(store)
    store.checkpoint(
        finalizing.job_id,
        finalizing.lease_token,
        phase="finalizing",
        checkpoint={"audit_id": "audit-final", "attempt_id": "attempt-final"},
    )
    store.enqueue(spec("ordinary", task="T-ordinary", action="forge_effect"))
    ordinary = claim(store, actions=("forge_effect",))

    assert store.recover_abandoned(lease_owner="worker-a", limit=1) == 1
    assert store.get(finalizing.job_id).state is WorkflowJobState.RUNNING
    assert store.get(ordinary.job_id).state is WorkflowJobState.QUEUED


def test_recovery_filters_project_action_and_phase_without_touching_terminal(store):
    store.enqueue(
        spec(
            "implementation",
            project="project-a",
            task="TASK-I",
            action="implementation_start",
            phase="applying",
        )
    )
    store.enqueue(
        spec(
            "terminal",
            project="project-a",
            task="TASK-A",
            action="terminal_audit",
            phase="finalizing",
        )
    )
    implementation = store.claim_next(
        lease_owner="old-runtime",
        lease_seconds=30,
        actions=("implementation_start",),
    )
    terminal = store.claim_next(
        lease_owner="terminal-audit",
        lease_seconds=30,
        actions=("terminal_audit",),
    )

    assert store.recover_abandoned(
        lease_owner="old-runtime",
        project_id="project-a",
        actions=("implementation_start",),
        phases=("applying",),
    ) == 1
    assert store.get(implementation.job_id).state is WorkflowJobState.QUEUED
    assert store.get(terminal.job_id).state is WorkflowJobState.RUNNING


def test_claim_compatible_running_action_is_explicit_and_task_scoped(store):
    """A repair may overlap its pre-effect owner without widening exclusion."""

    store.enqueue(
        spec(
            "implementation",
            task="TASK-NESTED",
            action="implementation_start",
        )
    )
    implementation = store.claim_next(
        lease_owner="implementation-runtime",
        lease_seconds=30,
        actions=("implementation_start",),
    )
    assert implementation is not None
    store.enqueue(
        spec(
            "repair",
            task="TASK-NESTED",
            generation="repair-generation",
            action="nested_dispatch_topology_repair",
        )
    )
    store.enqueue(
        spec(
            "unrelated",
            task="TASK-NESTED",
            generation="unrelated-generation",
            action="unrelated_workflow_action",
        )
    )

    assert (
        store.claim_next(
            lease_owner="ordinary-runtime",
            lease_seconds=30,
            task_id="TASK-NESTED",
            actions=("unrelated_workflow_action",),
        )
        is None
    )
    repair = store.claim_next(
        lease_owner="topology-runtime",
        lease_seconds=30,
        task_id="TASK-NESTED",
        actions=("nested_dispatch_topology_repair",),
        compatible_running_actions=("implementation_start",),
    )

    assert repair is not None
    assert repair.action == "nested_dispatch_topology_repair"
    assert store.get(implementation.job_id).state is WorkflowJobState.RUNNING
    assert (
        store.claim_next(
            lease_owner="other-runtime",
            lease_seconds=30,
            task_id="TASK-NESTED",
            actions=("unrelated_workflow_action",),
            compatible_running_actions=("implementation_start",),
        )
        is None
    )


def test_supersede_revokes_running_lease_and_never_revives_on_enqueue(store):
    original_spec = spec()
    store.enqueue(original_spec)
    running = claim(store)

    superseded = store.supersede(
        running.job_id,
        generation="g1",
        replacement_generation="g2",
        reason="new facts",
    )
    replayed = store.enqueue(original_spec)

    assert superseded.state is WorkflowJobState.SUPERSEDED
    assert superseded.superseded_by_generation == "g2"
    assert replayed.state is WorkflowJobState.SUPERSEDED
    with pytest.raises(WorkflowJobLeaseLost):
        store.complete(running.job_id, running.lease_token)


def test_supersede_requires_exact_generation(store):
    job = store.enqueue(spec())

    with pytest.raises(WorkflowJobStoreError, match="generation"):
        store.supersede(
            job.job_id,
            generation="stale",
            replacement_generation="g2",
            reason="new facts",
        )
    assert store.get(job.job_id).state is WorkflowJobState.QUEUED


def test_bulk_supersession_is_task_project_scoped_and_bounded(store):
    old_a = store.enqueue(spec("old-a", task="T", generation="old-a"))
    old_b = store.enqueue(spec("old-b", task="T", generation="old-b"))
    current = store.enqueue(spec("current", task="T", generation="current"))
    other_task = store.enqueue(spec("other", task="OTHER", generation="old"))
    other_project = store.enqueue(
        spec("old-a", project="project-b", task="T", generation="old-a")
    )

    assert (
        store.supersede_task_generation(
            project_id="project-a",
            task_id="T",
            keep_generation="current",
            reason="new decision",
            limit=1,
        )
        == 1
    )
    assert (
        store.supersede_task_generation(
            project_id="project-a",
            task_id="T",
            keep_generation="current",
            reason="new decision",
        )
        == 1
    )

    assert store.get(old_a.job_id).state is WorkflowJobState.SUPERSEDED
    assert store.get(old_b.job_id).state is WorkflowJobState.SUPERSEDED
    assert store.get(current.job_id).state is WorkflowJobState.QUEUED
    assert store.get(other_task.job_id).state is WorkflowJobState.QUEUED
    assert store.get(other_project.job_id).state is WorkflowJobState.QUEUED


def test_cancel_is_terminal_idempotent_and_generation_fenced(store):
    job = store.enqueue(spec())

    cancelled = store.cancel(job.job_id, generation="g1", reason="operator request")
    repeated = store.cancel(job.job_id, generation="g1", reason="repeated request")
    supersede_attempt = store.supersede(
        job.job_id,
        generation="g1",
        replacement_generation="g2",
        reason="new facts",
    )

    assert cancelled.state is WorkflowJobState.CANCELLED
    assert repeated == cancelled
    assert supersede_attempt.state is WorkflowJobState.CANCELLED
    assert claim(store) is None


def test_event_history_is_append_only(store):
    job = store.enqueue(spec())

    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        store._conn.execute(  # noqa: SLF001 - deliberate corruption boundary test
            "UPDATE workflow_job_events SET event_type = 'changed' WHERE job_id = ?",
            (job.job_id,),
        )
    store._conn.rollback()  # noqa: SLF001


def test_schema_v1_is_upgraded_without_losing_job(tmp_path):
    path = tmp_path / "v1.sqlite3"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        INSERT INTO schema_meta VALUES ('workflow_jobs_version', '1');
        CREATE TABLE workflow_jobs (
            enqueue_sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL UNIQUE,
            project_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            generation TEXT NOT NULL,
            action TEXT NOT NULL,
            phase TEXT NOT NULL,
            idempotency_key TEXT NOT NULL,
            spec_revision TEXT NOT NULL,
            spec_json TEXT NOT NULL,
            state TEXT NOT NULL,
            priority INTEGER NOT NULL,
            attempts INTEGER NOT NULL,
            max_attempts INTEGER NOT NULL,
            lease_owner TEXT,
            lease_token TEXT,
            lease_expires_at REAL,
            retry_at REAL,
            failure_category TEXT,
            last_error TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            completed_at REAL,
            UNIQUE(project_id, idempotency_key)
        );
        """
    )
    old_spec = spec()
    legacy_spec_dict = old_spec.to_dict()
    legacy_spec_dict.pop("payload")
    legacy_spec_revision = hashlib.sha256(
        json.dumps(
            legacy_spec_dict,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode()
    ).hexdigest()
    connection.execute(
        """
        INSERT INTO workflow_jobs(
            job_id, project_id, task_id, generation, action, phase,
            idempotency_key, spec_revision, spec_json, state, priority,
            attempts, max_attempts, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "old-job",
            old_spec.project_id,
            old_spec.task_id,
            old_spec.generation,
            old_spec.action,
            old_spec.phase,
            old_spec.idempotency_key,
            legacy_spec_revision,
            json.dumps(legacy_spec_dict, sort_keys=True, separators=(",", ":")),
            "queued",
            old_spec.priority,
            0,
            old_spec.max_attempts,
            1.0,
            1.0,
        ),
    )
    connection.commit()
    connection.close()

    upgraded = WorkflowJobStore(str(path))
    try:
        assert upgraded.schema_version == WORKFLOW_JOB_SCHEMA_VERSION
        assert upgraded.get("old-job").expected_head_sha is None
        assert not upgraded.get("old-job").workflow_managed
        assert upgraded.get("old-job").payload is None
        assert upgraded.enqueue(old_spec).job_id == "old-job"
        assert claim(upgraded).job_id == "old-job"
        upgraded.integrity_check()
    finally:
        upgraded.close()


def test_future_schema_is_rejected_without_double_closing_authority_fd(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "future.sqlite3"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        INSERT INTO schema_meta VALUES ('workflow_jobs_version', '999');
        """
    )
    connection.close()

    real_close = os.close
    close_calls: list[int] = []

    def tracked_close(fd: int) -> None:
        close_calls.append(fd)
        real_close(fd)

    monkeypatch.setattr("oompah.workflow_jobs.os.close", tracked_close)

    with pytest.raises(WorkflowJobStoreError, match="newer"):
        WorkflowJobStore(str(path))

    assert len(close_calls) == 1


def test_interrupted_column_first_migration_rewrites_legacy_specs_on_restart(
    tmp_path,
):
    """A committed ALTER with an old version marker must resume data migration."""

    path = str(tmp_path / "interrupted.sqlite3")
    first = WorkflowJobStore(path)
    original_spec = spec()
    job = first.enqueue(original_spec)
    legacy = original_spec.to_dict()
    legacy.pop("payload")
    legacy.pop("scheduling_lane")
    legacy_json = json.dumps(legacy, sort_keys=True, separators=(",", ":"))
    first._conn.execute(  # noqa: SLF001 - simulate a killed v3 migration
        "UPDATE workflow_jobs SET spec_json = ?, spec_revision = ? WHERE job_id = ?",
        (legacy_json, hashlib.sha256(legacy_json.encode()).hexdigest(), job.job_id),
    )
    first._conn.execute(  # noqa: SLF001
        "UPDATE schema_meta SET value = '3' WHERE key = 'workflow_jobs_version'"
    )
    first._conn.commit()  # noqa: SLF001
    first.close()

    reopened = WorkflowJobStore(path)
    try:
        migrated = reopened.get(job.job_id)
        assert migrated.payload is None
        assert migrated.scheduling_lane == "decision"
        assert reopened.schema_version == WORKFLOW_JOB_SCHEMA_VERSION
        reopened.integrity_check()
    finally:
        reopened.close()


def test_schema_v6_upgrade_seeds_exact_last_publication(tmp_path):
    path = str(tmp_path / "v6-publication.sqlite3")
    first = WorkflowJobStore(path)
    generation = first.allocate_snapshot_generation()
    assert first.accept_snapshot_generation(generation)
    assert first.publish_snapshot_generation(generation, lambda: None)[0]
    first.close()

    connection = sqlite3.connect(path)
    connection.execute("DROP TABLE workflow_job_retirements")
    connection.execute("DROP TABLE workflow_retirement_authority_cuts")
    connection.execute("DROP TABLE workflow_snapshot_publications")
    connection.execute(
        "UPDATE schema_meta SET value = '6' WHERE key = 'workflow_jobs_version'"
    )
    connection.commit()
    connection.close()

    upgraded = WorkflowJobStore(path)
    try:
        publication = upgraded._conn.execute(  # noqa: SLF001
            "SELECT snapshot_generation FROM workflow_snapshot_publications"
        ).fetchone()
        assert publication is not None
        assert publication["snapshot_generation"] == generation
        assert upgraded.schema_version == WORKFLOW_JOB_SCHEMA_VERSION
    finally:
        upgraded.close()


def test_persisted_rollout_gate_survives_restart_and_allows_safe_rollback(
    tmp_path, clock: Clock
):
    path = str(tmp_path / "rollout.sqlite3")
    shadow = {domain: "shadow" for domain in (
        "implementation", "review", "integration", "epic"
    )}
    enforce = {domain: "enforce" for domain in shadow}
    first = WorkflowJobStore(path, clock=clock)
    first.prepare_rollout(
        shadow,
        require_qualification=True,
        min_shadow_sweeps=3,
        min_shadow_seconds=300,
    )
    for _ in range(3):
        first.record_rollout_sweep({domain: None for domain in shadow})
    assert not first.rollout_readiness(
        min_shadow_sweeps=3,
        min_shadow_seconds=300,
    )["all_domains_ready"]
    first.close()

    clock.advance(300)
    restarted = WorkflowJobStore(path, clock=clock)
    try:
        assert restarted.rollout_readiness(
            min_shadow_sweeps=3,
            min_shadow_seconds=300,
        )["all_domains_ready"]
        rows = restarted.prepare_rollout(
            enforce,
            require_qualification=True,
            min_shadow_sweeps=3,
            min_shadow_seconds=300,
        )
        assert {row["mode"] for row in rows} == {"enforce"}

        rolled_back = restarted.prepare_rollout(
            shadow,
            require_qualification=True,
            min_shadow_sweeps=3,
            min_shadow_seconds=300,
        )
        assert {row["mode"] for row in rolled_back} == {"shadow"}
        assert all(row["successful_shadow_sweeps"] == 0 for row in rolled_back)
    finally:
        restarted.close()


def test_rollout_gate_rejects_unqualified_enforce_atomically(store):
    shadow = {domain: "shadow" for domain in (
        "implementation", "review", "integration", "epic"
    )}
    store.prepare_rollout(
        shadow,
        require_qualification=True,
        min_shadow_sweeps=2,
        min_shadow_seconds=0,
    )
    store.record_rollout_sweep({domain: None for domain in shadow})

    with pytest.raises(WorkflowRolloutGateError, match="1/2"):
        store.prepare_rollout(
            {domain: "enforce" for domain in shadow},
            require_qualification=True,
            min_shadow_sweeps=2,
            min_shadow_seconds=0,
        )

    assert {row["mode"] for row in store.rollout_snapshot()} == {"shadow"}


def test_legacy_enforce_configuration_can_adopt_explicit_domain_controls(store):
    enforce = {domain: "enforce" for domain in (
        "implementation", "review", "integration", "epic"
    )}
    compatibility = store.prepare_rollout(
        enforce,
        require_qualification=False,
        min_shadow_sweeps=3,
        min_shadow_seconds=300,
    )

    assert all(row["successful_shadow_sweeps"] >= 3 for row in compatibility)
    adopted = store.prepare_rollout(
        enforce,
        require_qualification=True,
        min_shadow_sweeps=3,
        min_shadow_seconds=300,
    )

    assert {row["mode"] for row in adopted} == {"enforce"}


def test_post_callback_commit_failure_compensates_and_same_generation_retries(store):
    generation = store.allocate_snapshot_generation()
    assert store.accept_snapshot_generation(generation)
    external = {"generation": 0}
    connection = store._conn

    class FailPublishedCommitOnce:
        def __init__(self, wrapped):
            self.wrapped = wrapped
            self.armed = False
            self.failed = False

        def execute(self, sql, *args, **kwargs):
            result = self.wrapped.execute(sql, *args, **kwargs)
            if (
                not self.failed
                and "workflow_snapshot_published_generation" in str(sql)
                and "INSERT" in str(sql)
            ):
                self.armed = True
            return result

        def commit(self):
            if self.armed:
                self.armed = False
                self.failed = True
                raise sqlite3.OperationalError("injected post-callback failure")
            return self.wrapped.commit()

        def __getattr__(self, name):
            return getattr(self.wrapped, name)

    store._conn = FailPublishedCommitOnce(connection)

    def publish():
        previous = external["generation"]
        external["generation"] = generation
        return WorkflowSnapshotPublication(
            result="published",
            rollback=lambda: external.__setitem__("generation", previous),
        )

    with pytest.raises(sqlite3.OperationalError, match="post-callback"):
        store.publish_snapshot_generation(generation, publish)

    assert external["generation"] == 0
    assert store.health_snapshot()["published_snapshot_generation"] == 0

    accepted, result = store.publish_snapshot_generation(generation, publish)

    assert accepted
    assert result == "published"
    assert external["generation"] == generation
    assert store.health_snapshot()["published_snapshot_generation"] == generation


def test_commit_error_after_durable_marker_does_not_rollback_coherent_publication(
    store,
):
    generation = store.allocate_snapshot_generation()
    assert store.accept_snapshot_generation(generation)
    external = {"generation": 0, "rollbacks": 0}
    connection = store._conn

    class RaiseAfterPublishedCommitOnce:
        def __init__(self, wrapped):
            self.wrapped = wrapped
            self.armed = False
            self.failed = False

        def execute(self, sql, *args, **kwargs):
            result = self.wrapped.execute(sql, *args, **kwargs)
            if (
                not self.failed
                and "workflow_snapshot_published_generation" in str(sql)
                and "INSERT" in str(sql)
            ):
                self.armed = True
            return result

        def commit(self):
            result = self.wrapped.commit()
            if self.armed:
                self.armed = False
                self.failed = True
                raise sqlite3.OperationalError("injected error after durable commit")
            return result

        def __getattr__(self, name):
            return getattr(self.wrapped, name)

    store._conn = RaiseAfterPublishedCommitOnce(connection)

    def publish():
        external["generation"] = generation

        def rollback():
            external["generation"] = 0
            external["rollbacks"] += 1

        return WorkflowSnapshotPublication(result="published", rollback=rollback)

    accepted, result = store.publish_snapshot_generation(generation, publish)

    assert accepted
    assert result == "published"
    assert external == {"generation": generation, "rollbacks": 0}
    assert store.health_snapshot()["published_snapshot_generation"] == generation


def test_claim_is_atomically_bound_to_required_accepted_published_snapshot(store):
    generation = store.allocate_snapshot_generation()
    assert store.accept_snapshot_generation(generation)
    published, _ = store.publish_snapshot_generation(generation, lambda: None)
    assert published
    assert store.published_snapshot_generation_is_current(generation)
    first = store.enqueue(spec(key="snapshot-first", task="SNAPSHOT-FIRST"))

    claimed = claim(store, required_snapshot_generation=generation)

    assert claimed is not None and claimed.job_id == first.job_id
    second = store.enqueue(spec(key="snapshot-second", task="SNAPSHOT-SECOND"))
    replacement = store.allocate_snapshot_generation()
    assert replacement > generation
    assert store.published_snapshot_generation_is_current(generation)
    assert store.has_claimable(
        required_snapshot_generation=generation,
        task_id="SNAPSHOT-SECOND",
    )
    assert store.accept_snapshot_generation(replacement)
    assert not store.published_snapshot_generation_is_current(generation)
    assert not store.has_claimable(
        required_snapshot_generation=generation,
        task_id="SNAPSHOT-SECOND",
    )
    assert (
        claim(
            store,
            required_snapshot_generation=generation,
            task_id="SNAPSHOT-SECOND",
        )
        is None
    )
    assert store.get(second.job_id).state is WorkflowJobState.QUEUED


def test_published_bounded_scan_keeps_unevaluated_member_claimable(store):
    project_id = "project-1"
    task_a = "TASK-A"
    task_b = "TASK-B"
    first = store.allocate_snapshot_generation()
    assert store.accept_snapshot_generation(first)
    assert store.reconcile_snapshot_membership(
        snapshot_generation=first,
        authoritative_project_ids=(project_id,),
        expected_identities=((project_id, task_a), (project_id, task_b)),
    ).accepted
    first_jobs = {}
    for task_id in (task_a, task_b):
        cursor = store.activate_schedule(
            project_id=project_id,
            task_id=task_id,
            decision_revision=f"first-decision:{task_id}",
            snapshot_generation=first,
        )
        assert store.reconcile_schedule(
            project_id=project_id,
            task_id=task_id,
            snapshot_generation=first,
            job_generation=cursor.job_generation,
            specs=(
                spec(
                    key=f"first-job:{task_id}",
                    project=project_id,
                    task=task_id,
                    generation=cursor.job_generation,
                ),
            ),
        ).accepted
        first_jobs[task_id] = next(
            job
            for job in store.list_jobs(task_id=task_id)
            if job.generation == cursor.job_generation
        )
    assert store.publish_snapshot_generation(first, lambda: None)[0]

    second = store.allocate_snapshot_generation()
    assert store.accept_snapshot_generation(second)
    assert store.reconcile_snapshot_membership(
        snapshot_generation=second,
        authoritative_project_ids=(project_id,),
        expected_identities=((project_id, task_a), (project_id, task_b)),
        evaluated_identities=((project_id, task_a),),
    ).accepted
    task_a_cursor = store.activate_schedule(
        project_id=project_id,
        task_id=task_a,
        decision_revision="second-decision:TASK-A",
        snapshot_generation=second,
    )
    assert store.reconcile_schedule(
        project_id=project_id,
        task_id=task_a,
        snapshot_generation=second,
        job_generation=task_a_cursor.job_generation,
        specs=(
            spec(
                key="second-job:TASK-A",
                project=project_id,
                task=task_a,
                generation=task_a_cursor.job_generation,
            ),
        ),
    ).accepted
    assert store.publish_snapshot_generation(second, lambda: None)[0]

    assert store.snapshot_membership() == (
        (project_id, task_a, second),
        (project_id, task_b, first),
    )
    assert store.schedule_cursor(
        project_id=project_id, task_id=task_b
    ).snapshot_generation == first
    assert store.has_claimable(
        task_id=task_b,
        required_snapshot_generation=second,
    )
    claimed = claim(
        store,
        task_id=task_b,
        required_snapshot_generation=second,
    )
    assert claimed is not None
    assert claimed.job_id == first_jobs[task_b].job_id


def test_integrity_check_detects_tampered_spec(store):
    job = store.enqueue(spec())
    store._conn.execute(  # noqa: SLF001 - deliberate corruption boundary test
        "UPDATE workflow_jobs SET spec_revision = 'tampered' WHERE job_id = ?",
        (job.job_id,),
    )
    store._conn.commit()  # noqa: SLF001

    with pytest.raises(WorkflowJobCorruptionError, match="revision mismatch"):
        store.integrity_check()


def test_integrity_check_detects_tampered_payload(store):
    job = store.enqueue(spec(payload={"review_id": 42}))
    store._conn.execute(  # noqa: SLF001 - deliberate corruption boundary test
        "UPDATE workflow_jobs SET payload_json = ? WHERE job_id = ?",
        ('{"review_id":41}', job.job_id),
    )
    store._conn.commit()  # noqa: SLF001

    with pytest.raises(WorkflowJobCorruptionError, match="payload mismatch"):
        store.integrity_check()


def test_json_checkpoints_reject_nonportable_values(store):
    store.enqueue(spec())
    running = claim(store)

    with pytest.raises(ValueError, match="JSON serializable"):
        store.checkpoint(
            running.job_id,
            running.lease_token,
            phase="bad",
            checkpoint={"not-json": {1, 2}},
        )


@pytest.mark.parametrize("operation", ("renew", "checkpoint", "complete", "fail"))
def test_delayed_worker_ack_uses_post_lock_time_and_rejects_expired_lease(
    store,
    clock,
    operation,
):
    store.enqueue(spec())
    running = store.claim_next(lease_owner="worker-a", lease_seconds=10)
    assert running is not None
    acknowledgement_started = threading.Event()

    def delayed_acknowledgement():
        acknowledgement_started.set()
        if operation == "renew":
            return store.renew(
                running.job_id,
                running.lease_token,
                lease_seconds=10,
            )
        if operation == "checkpoint":
            return store.checkpoint(
                running.job_id,
                running.lease_token,
                phase="working",
                checkpoint={"step": 1},
            )
        if operation == "complete":
            return store.complete(running.job_id, running.lease_token)
        return store.fail(
            running.job_id,
            running.lease_token,
            category=WorkflowFailureCategory.TRANSIENT,
            error="retry",
            retryable=True,
        )

    pool = ThreadPoolExecutor(max_workers=1)
    store._lock.acquire()  # noqa: SLF001 - deliberate lock-wait regression
    try:
        acknowledgement = pool.submit(delayed_acknowledgement)
        assert acknowledgement_started.wait(timeout=2)
        clock.advance(20)
    finally:
        store._lock.release()  # noqa: SLF001
    try:
        with pytest.raises(WorkflowJobLeaseLost):
            acknowledgement.result(timeout=2)
    finally:
        pool.shutdown(wait=True)


def test_delayed_claim_uses_post_lock_time_for_retry_eligibility(store, clock):
    store.enqueue(spec())
    running = claim(store)
    assert running is not None
    store.fail(
        running.job_id,
        running.lease_token,
        category=WorkflowFailureCategory.TRANSIENT,
        error="retry",
        retryable=True,
        retry_delay_seconds=10,
    )
    claim_started = threading.Event()

    def delayed_claim():
        claim_started.set()
        return store.claim_next(lease_owner="worker-b", lease_seconds=30)

    pool = ThreadPoolExecutor(max_workers=1)
    store._lock.acquire()  # noqa: SLF001 - deliberate lock-wait regression
    try:
        future = pool.submit(delayed_claim)
        assert claim_started.wait(timeout=2)
        clock.advance(20)
    finally:
        store._lock.release()  # noqa: SLF001
    try:
        claimed = future.result(timeout=2)
    finally:
        pool.shutdown(wait=True)

    assert claimed is not None
    assert claimed.job_id == running.job_id


def _archived_task_with_events(store, clock, *, project_id, task_id):
    """Create a job with events for a task and stage Archived retirement proof."""
    event = store.materialize_event(
        project_id=project_id,
        task_id=task_id,
        decision_revision="cleanup-generation",
        action="epic_cleanup",
        idempotency_namespace="epic-cleanup",
        scheduling_lane="epic-event:epic_cleanup",
    )
    assert event.job is not None
    running = claim(store, task_id=task_id)
    assert running is not None
    store.fail(
        running.job_id,
        running.lease_token,
        error="terminal",
        category=WorkflowFailureCategory.PERMANENT,
        retryable=False,
    )
    snapshot = store.allocate_snapshot_generation()
    assert store.accept_snapshot_generation(snapshot)
    assert (
        store.record_lifecycle_final_authority(
            project_id=project_id,
            task_id=task_id,
            status="Archived",
            snapshot_generation=snapshot,
        )
        >= 1
    )
    return event.job.job_id


def _event_counts(store):
    hot = store._conn.execute(  # noqa: SLF001 - test inspects storage
        "SELECT COUNT(*) AS c FROM workflow_job_events"
    ).fetchone()["c"]
    cold = store._conn.execute(  # noqa: SLF001
        "SELECT COUNT(*) AS c FROM workflow_job_events_archive"
    ).fetchone()["c"]
    return int(hot), int(cold)


def test_archive_lifecycle_final_events_moves_rows_to_cold_storage(store, clock):
    project_id = "project-arch"
    task_id = "OOMPAH-ARCHIVED"
    _archived_task_with_events(store, clock, project_id=project_id, task_id=task_id)

    hot_before, cold_before = _event_counts(store)
    assert hot_before > 0
    assert cold_before == 0

    result = store.archive_lifecycle_final_events()
    assert result["tasks"] == 1
    assert result["events"] == hot_before

    hot_after, cold_after = _event_counts(store)
    assert hot_after == 0
    assert cold_after == hot_before

    # Sequences are preserved verbatim in the cold table.
    archived = store._conn.execute(  # noqa: SLF001
        "SELECT sequence, task_id FROM workflow_job_events_archive ORDER BY sequence"
    ).fetchall()
    assert all(row["task_id"] == task_id for row in archived)
    assert [row["sequence"] for row in archived] == sorted(
        row["sequence"] for row in archived
    )


def test_archive_preserves_snapshot_authority_high_water(store, clock):
    project_id = "project-hw"
    task_id = "OOMPAH-HW"
    _archived_task_with_events(store, clock, project_id=project_id, task_id=task_id)

    before = store.capture_snapshot_authority(
        authoritative_project_ids=(),
        evaluated_identities=((project_id, task_id),),
        full_project_scope=False,
    ).job_event_sequence
    assert before > 0

    store.archive_lifecycle_final_events()

    # After relocating every hot event, MAX(sequence) over the hot table is 0,
    # but the persisted high-water mark keeps the ABA fence monotonic.
    hot_after, cold_after = _event_counts(store)
    assert hot_after == 0
    assert cold_after > 0
    after = store.capture_snapshot_authority(
        authoritative_project_ids=(),
        evaluated_identities=((project_id, task_id),),
        full_project_scope=False,
    ).job_event_sequence
    assert after == before


def test_archive_is_bounded_by_event_budget(store, clock):
    project_id = "project-budget"
    task_id = "OOMPAH-BUDGET"
    _archived_task_with_events(store, clock, project_id=project_id, task_id=task_id)
    hot_before, _ = _event_counts(store)
    assert hot_before >= 2

    result = store.archive_lifecycle_final_events(max_events=1)
    assert result["events"] == 1
    hot_after, cold_after = _event_counts(store)
    assert cold_after == 1
    assert hot_after == hot_before - 1


def test_archive_skips_non_archived_tasks(store, clock):
    project_id = "project-live"
    task_id = "OOMPAH-LIVE"
    event = store.materialize_event(
        project_id=project_id,
        task_id=task_id,
        decision_revision="cleanup-generation",
        action="epic_cleanup",
        idempotency_namespace="epic-cleanup",
        scheduling_lane="epic-event:epic_cleanup",
    )
    assert event.job is not None

    result = store.archive_lifecycle_final_events()
    assert result == {"tasks": 0, "events": 0}
    hot_after, cold_after = _event_counts(store)
    assert hot_after > 0
    assert cold_after == 0


def test_direct_event_delete_still_rejected_outside_archival(store, clock):
    project_id = "project-guard"
    task_id = "OOMPAH-GUARD"
    event = store.materialize_event(
        project_id=project_id,
        task_id=task_id,
        decision_revision="cleanup-generation",
        action="epic_cleanup",
        idempotency_namespace="epic-cleanup",
        scheduling_lane="epic-event:epic_cleanup",
    )
    assert event.job is not None
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        store._conn.execute("DELETE FROM workflow_job_events")  # noqa: SLF001


def test_migration_upgrades_legacy_unconditional_delete_trigger(tmp_path, clock):
    database = str(tmp_path / "legacy.sqlite3")
    store = WorkflowJobStore(database, clock=clock)
    _archived_task_with_events(store, clock, project_id="p", task_id="OOMPAH-LEGACY")
    # Simulate a pre-V8 store whose delete trigger is unconditional.
    store._conn.execute(  # noqa: SLF001
        "DROP TRIGGER IF EXISTS workflow_job_events_no_delete"
    )
    store._conn.executescript(  # noqa: SLF001
        "CREATE TRIGGER workflow_job_events_no_delete "
        "BEFORE DELETE ON workflow_job_events BEGIN "
        "SELECT RAISE(ABORT, 'workflow job events are append-only'); END;"
    )
    store._conn.commit()  # noqa: SLF001
    store.close()

    reopened = WorkflowJobStore(database, clock=clock)
    try:
        sql = reopened._conn.execute(  # noqa: SLF001
            "SELECT sql FROM sqlite_master "
            "WHERE name = 'workflow_job_events_no_delete'"
        ).fetchone()["sql"]
        assert "workflow_job_events_delete_guard" in sql
        # Archival now makes progress instead of raising IntegrityError.
        result = reopened.archive_lifecycle_final_events()
        assert result["events"] > 0
    finally:
        reopened.close()


def test_publication_rollback_emits_single_aggregate_event_per_task(store):
    project_id = "project-agg"
    task_id = "TASK-ROLLBACK-AGG"
    published = store.allocate_snapshot_generation()
    assert store.accept_snapshot_generation(published)
    assert store.reconcile_snapshot_membership(
        snapshot_generation=published,
        authoritative_project_ids=(project_id,),
        expected_identities=((project_id, task_id),),
    ).accepted
    cursor = store.activate_schedule(
        project_id=project_id,
        task_id=task_id,
        decision_revision="managed-multi",
        snapshot_generation=published,
    )
    specs = tuple(
        WorkflowJobSpec(
            project_id=project_id,
            task_id=task_id,
            generation=cursor.job_generation,
            action="authority_revocation",
            idempotency_key=f"rollback-agg:{index}",
        )
        for index in range(5)
    )
    assert store.reconcile_schedule(
        project_id=project_id,
        task_id=task_id,
        snapshot_generation=published,
        job_generation=cursor.job_generation,
        specs=specs,
    ).accepted
    assert store.publish_snapshot_generation(published, lambda: None)[0]

    checkpoint = store.capture_snapshot_authority(
        authoritative_project_ids=(project_id,),
        evaluated_identities=((project_id, task_id),),
        full_project_scope=True,
    )
    failed_snapshot = store.allocate_snapshot_generation()
    assert store.accept_snapshot_generation(failed_snapshot)
    assert store.restore_snapshot_authority(
        checkpoint, snapshot_generation=failed_snapshot
    )

    rows = store._conn.execute(  # noqa: SLF001 - assert bounded event emission
        "SELECT payload_json FROM workflow_job_events "
        "WHERE project_id = ? AND task_id = ? AND event_type = 'publication_rollback'",
        (project_id, task_id),
    ).fetchall()
    # Exactly one aggregate event, not one per superseded job.
    assert len(rows) == 1
    payload = json.loads(rows[0]["payload_json"])
    assert payload["job_count"] == len(specs)
    assert len(payload["job_ids"]) == len(specs)


def test_repeated_rollback_same_generation_is_idempotent(store):
    """Verify that rolling back different generations produces separate events."""
    project_id = "project-idempotent"
    task_id = "TASK-IDEMPOTENT-ROLLBACK"
    published = store.allocate_snapshot_generation()
    assert store.accept_snapshot_generation(published)
    assert store.reconcile_snapshot_membership(
        snapshot_generation=published,
        authoritative_project_ids=(project_id,),
        expected_identities=((project_id, task_id),),
    ).accepted
    cursor = store.activate_schedule(
        project_id=project_id,
        task_id=task_id,
        decision_revision="managed-multi",
        snapshot_generation=published,
    )
    specs = tuple(
        WorkflowJobSpec(
            project_id=project_id,
            task_id=task_id,
            generation=cursor.job_generation,
            action="authority_revocation",
            idempotency_key=f"idem-rollback:{index}",
        )
        for index in range(3)
    )
    assert store.reconcile_schedule(
        project_id=project_id,
        task_id=task_id,
        snapshot_generation=published,
        job_generation=cursor.job_generation,
        specs=specs,
    ).accepted
    assert store.publish_snapshot_generation(published, lambda: None)[0]

    checkpoint = store.capture_snapshot_authority(
        authoritative_project_ids=(project_id,),
        evaluated_identities=((project_id, task_id),),
        full_project_scope=True,
    )

    # Allocate and rollback first failed snapshot
    failed_snapshot_1 = store.allocate_snapshot_generation()
    assert store.accept_snapshot_generation(failed_snapshot_1)
    assert store.restore_snapshot_authority(
        checkpoint, snapshot_generation=failed_snapshot_1
    )

    # Count rollback events after first rollback
    rows_after_first = store._conn.execute(  # noqa: SLF001
        "SELECT payload_json FROM workflow_job_events "
        "WHERE project_id = ? AND task_id = ? AND event_type = 'publication_rollback'",
        (project_id, task_id),
    ).fetchall()
    assert len(rows_after_first) == 1
    first_payload = json.loads(rows_after_first[0]["payload_json"])

    # Allocate and rollback a second failed snapshot with the same checkpoint
    # This should produce a separate rollback event
    failed_snapshot_2 = store.allocate_snapshot_generation()
    assert store.accept_snapshot_generation(failed_snapshot_2)
    result = store.restore_snapshot_authority(
        checkpoint, snapshot_generation=failed_snapshot_2
    )
    assert result is True

    # Now check that we have one rollback event per generation
    rows_after_second = store._conn.execute(  # noqa: SLF001
        "SELECT payload_json FROM workflow_job_events "
        "WHERE project_id = ? AND task_id = ? AND event_type = 'publication_rollback'",
        (project_id, task_id),
    ).fetchall()
    assert len(rows_after_second) == 2, (
        "Should have 2 aggregate rollback events (one per generation)"
    )
    # Verify both events have the same job_ids (since they're rolling back the same state)
    second_payload = json.loads(rows_after_second[1]["payload_json"])
    assert first_payload["job_ids"] == second_payload["job_ids"], (
        "Both rollbacks should affect the same jobs"
    )


def _seed_rollback_events(store, clock, *, project_id, task_id, count):
    """Seed publication_rollback audit rows backed by real jobs."""
    job_ids = []
    for index in range(count):
        job = store.enqueue(
            spec(
                key=f"rollback-seed:{project_id}:{task_id}:{index}",
                project=project_id,
                task=task_id,
                generation=f"g-{index}",
                action="authority_revocation",
            )
        )
        job_ids.append(job.job_id)
    for index, job_id in enumerate(job_ids):
        row = store._conn.execute(  # noqa: SLF001
            "SELECT * FROM workflow_jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
        store._append_event_locked(  # noqa: SLF001
            row,
            "publication_rollback",
            payload={"snapshot_generation": index},
            now=clock.now,
        )
    store._conn.commit()  # noqa: SLF001


def _rollback_counts(store):
    hot = store._conn.execute(  # noqa: SLF001
        "SELECT count(*) AS c FROM workflow_job_events "
        "WHERE event_type = 'publication_rollback'"
    ).fetchone()["c"]
    cold = store._conn.execute(  # noqa: SLF001
        "SELECT count(*) AS c FROM workflow_job_events_archive "
        "WHERE event_type = 'publication_rollback'"
    ).fetchone()["c"]
    return int(hot), int(cold)


def test_archive_rollback_events_relocates_old_audit_rows(store, clock):
    _seed_rollback_events(
        store, clock, project_id="p", task_id="TRICKLE-X", count=50
    )
    hot_before, cold_before = _rollback_counts(store)
    assert hot_before == 50
    assert cold_before == 0

    result = store.archive_rollback_events(max_events=1000, keep_recent=10)
    assert result["events"] == 40

    hot_after, cold_after = _rollback_counts(store)
    assert hot_after == 10
    assert cold_after == 40


def test_archive_rollback_events_respects_keep_recent(store, clock):
    _seed_rollback_events(
        store, clock, project_id="p", task_id="TRICKLE-Y", count=5
    )
    # Fewer rollback rows than the retention window: nothing is relocated.
    result = store.archive_rollback_events(max_events=1000, keep_recent=10)
    assert result["events"] == 0
    hot_after, cold_after = _rollback_counts(store)
    assert hot_after == 5
    assert cold_after == 0


def test_archive_rollback_events_is_bounded(store, clock):
    _seed_rollback_events(
        store, clock, project_id="p", task_id="TRICKLE-Z", count=50
    )
    result = store.archive_rollback_events(max_events=5, keep_recent=0)
    assert result["events"] == 5
    hot_after, cold_after = _rollback_counts(store)
    assert hot_after == 45
    assert cold_after == 5


def test_archive_rollback_events_handles_batch_over_sqlite_variable_limit(
    store, clock
):
    # Regression: a range delete (not an IN-list) must relocate a batch larger
    # than SQLite's bound-variable limit without "too many SQL variables".
    count = 1200
    _seed_rollback_events(
        store, clock, project_id="p", task_id="TRICKLE-BIG", count=count
    )
    result = store.archive_rollback_events(max_events=count, keep_recent=0)
    assert result["events"] == count
    hot_after, cold_after = _rollback_counts(store)
    assert hot_after == 0
    assert cold_after == count



def test_archive_rollback_preserves_high_water(store, clock):
    _seed_rollback_events(
        store, clock, project_id="p", task_id="TRICKLE-HW", count=30
    )
    before = store.capture_snapshot_authority(
        authoritative_project_ids=(),
        evaluated_identities=(("p", "TRICKLE-HW"),),
        full_project_scope=False,
    ).job_event_sequence
    store.archive_rollback_events(max_events=1000, keep_recent=0)
    after = store.capture_snapshot_authority(
        authoritative_project_ids=(),
        evaluated_identities=(("p", "TRICKLE-HW"),),
        full_project_scope=False,
    ).job_event_sequence
    assert after == before


def test_vacuum_runs_without_error(store, clock):
    _seed_rollback_events(
        store, clock, project_id="p", task_id="TRICKLE-V", count=20
    )
    store.archive_rollback_events(max_events=1000, keep_recent=0)
    store.vacuum()
    hot, cold = _rollback_counts(store)
    assert hot == 0
    assert cold == 20
