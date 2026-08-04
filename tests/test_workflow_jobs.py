from __future__ import annotations

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from oompah.workflow_jobs import (
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


def test_enqueue_persists_every_execution_fence_and_event(store):
    job = store.enqueue(spec())

    assert job.state is WorkflowJobState.QUEUED
    assert job.attempts == 0
    assert job.expected_evidence_revision == "facts-g1"
    assert job.expected_head_sha == "head-g1"
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


def test_expired_recovery_is_bounded(store, clock):
    for index in range(3):
        store.enqueue(spec(f"key-{index}", task=f"T-{index}"))
        claim(store)
    clock.advance(31)

    assert store.recover_expired(limit=2) == 2
    assert len(store.list_jobs(states=(WorkflowJobState.RUNNING,))) == 1
    assert store.recover_expired(limit=2) == 1


def test_abandoned_recovery_can_be_scoped_to_process_owner(store):
    store.enqueue(spec("a", task="T-a"))
    store.enqueue(spec("b", task="T-b"))
    first = store.claim_next(lease_owner="old-a", lease_seconds=30)
    second = store.claim_next(lease_owner="old-b", lease_seconds=30)

    assert store.recover_abandoned(lease_owner="old-a") == 1
    assert store.get(first.job_id).state is WorkflowJobState.QUEUED
    assert store.get(second.job_id).state is WorkflowJobState.RUNNING


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
            old_spec.revision,
            json.dumps(old_spec.to_dict(), sort_keys=True, separators=(",", ":")),
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
        assert claim(upgraded).job_id == "old-job"
        upgraded.integrity_check()
    finally:
        upgraded.close()


def test_future_schema_is_rejected(tmp_path):
    path = tmp_path / "future.sqlite3"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        INSERT INTO schema_meta VALUES ('workflow_jobs_version', '999');
        """
    )
    connection.close()

    with pytest.raises(WorkflowJobStoreError, match="newer"):
        WorkflowJobStore(str(path))


def test_integrity_check_detects_tampered_spec(store):
    job = store.enqueue(spec())
    store._conn.execute(  # noqa: SLF001 - deliberate corruption boundary test
        "UPDATE workflow_jobs SET spec_revision = 'tampered' WHERE job_id = ?",
        (job.job_id,),
    )
    store._conn.commit()  # noqa: SLF001

    with pytest.raises(WorkflowJobCorruptionError, match="revision mismatch"):
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
