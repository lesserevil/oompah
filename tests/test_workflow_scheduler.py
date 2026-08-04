from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from oompah.work_decision import PermittedAction, WorkDecision
from oompah.workflow_contract import TaskDisposition, WorkflowOwner
from oompah.workflow_jobs import (
    WorkflowJobSpec,
    WorkflowJobState,
    WorkflowJobStore,
)
from oompah.workflow_reasons import AlertSeverity
from oompah.workflow_scheduler import WorkflowJobScheduler
from oompah.workflow_worker import (
    WorkflowRunDisposition,
    WorkflowRunResult,
)


class Clock:
    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def store(tmp_path, clock: Clock):
    value = WorkflowJobStore(str(tmp_path / "scheduler.sqlite3"), clock=clock)
    yield value
    value.close()


def decision(
    *,
    project: str = "project-a",
    task: str = "OOMPAH-1",
    evidence: str = "facts-1",
    jobs: tuple[str, ...] = ("implementation_recovery",),
) -> WorkDecision:
    return WorkDecision(
        project_id=project,
        task_id=task,
        status="In Progress",
        disposition=TaskDisposition.RETRY_SCHEDULED,
        reason_code="implementation.recovery_scheduled",
        responsible_owner=WorkflowOwner.DISPATCHER,
        unmet_prerequisites=(),
        evidence_revision=evidence,
        next_reassessment_at=None,
        permitted_actions=(PermittedAction.RECOVER_IMPLEMENTATION,),
        action_required=False,
        alert_level=AlertSeverity.INFO,
        durable_jobs=jobs,
    )


def direct_spec(
    key: str,
    *,
    project: str = "project-a",
    task: str = "OOMPAH-1",
    action: str = "action",
    priority: int = 100,
) -> WorkflowJobSpec:
    return WorkflowJobSpec(
        project_id=project,
        task_id=task,
        generation="generation-1",
        action=action,
        idempotency_key=key,
        priority=priority,
    )


def test_snapshot_generations_are_durable_across_store_restarts(tmp_path):
    path = str(tmp_path / "restart.sqlite3")
    first = WorkflowJobStore(path)
    assert first.allocate_snapshot_generation() == 1
    first.close()

    reopened = WorkflowJobStore(path)
    try:
        assert reopened.allocate_snapshot_generation() == 2
    finally:
        reopened.close()


def test_bounded_decision_window_resumes_after_restart(tmp_path):
    path = str(tmp_path / "window.sqlite3")
    decisions = tuple(decision(task=f"OOMPAH-{number}") for number in (3, 1, 2))
    first = WorkflowJobStore(path)
    WorkflowJobScheduler(store=first, decision_limit=2).reconcile(decisions)
    first.close()

    reopened = WorkflowJobStore(path)
    try:
        WorkflowJobScheduler(store=reopened, decision_limit=2).reconcile(decisions)
        assert {job.task_id for job in reopened.list_jobs()} == {
            "OOMPAH-1",
            "OOMPAH-2",
            "OOMPAH-3",
        }
    finally:
        reopened.close()


def test_stale_slow_scan_cannot_replace_newer_task_schedule(store):
    scheduler = WorkflowJobScheduler(store=store)
    slow = scheduler.begin_scan()
    fast = scheduler.begin_scan()

    newer = scheduler.reconcile(
        (decision(evidence="facts-2"),), snapshot_generation=fast
    )
    stale = scheduler.reconcile(
        (decision(evidence="facts-1"),), snapshot_generation=slow
    )

    assert newer.jobs_created == 1
    assert stale.stale_rejected == 1
    cursor = store.schedule_cursor(project_id="project-a", task_id="OOMPAH-1")
    assert cursor.snapshot_generation == fast
    assert cursor.decision_revision == decision(evidence="facts-2").decision_revision


def test_duplicate_scheduling_replays_one_durable_job(store):
    scheduler = WorkflowJobScheduler(store=store)
    current = decision()

    first = scheduler.reconcile((current,))
    second = scheduler.reconcile((current,))

    assert first.jobs_created == 1
    assert second.jobs_created == 0
    assert second.jobs_replayed == 1
    assert len(store.list_jobs()) == 1
    assert (
        store.schedule_cursor(project_id="project-a", task_id="OOMPAH-1").job_generation
        == store.list_jobs()[0].generation
    )


def test_decision_batch_rolls_back_all_tasks_on_late_enqueue_failure(
    tmp_path, clock
):
    calls = 0

    def job_id():
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("simulated late enqueue failure")
        return f"job-{calls}"

    store = WorkflowJobStore(
        str(tmp_path / "batch-rollback.sqlite3"),
        clock=clock,
        id_factory=job_id,
    )
    scheduler = WorkflowJobScheduler(store=store)

    with pytest.raises(RuntimeError, match="late enqueue"):
        scheduler.reconcile(
            (decision(task="OOMPAH-1"), decision(task="OOMPAH-2"))
        )

    assert store.list_jobs() == ()
    assert store.schedule_cursor(
        project_id="project-a", task_id="OOMPAH-1"
    ) is None
    assert store.schedule_cursor(
        project_id="project-a", task_id="OOMPAH-2"
    ) is None
    store.close()


def test_scheduling_batch_rolls_back_interrupt_and_allows_next_batch(store):
    class BatchInterrupted(BaseException):
        pass

    with pytest.raises(BatchInterrupted):
        with store.scheduling_batch():
            store.activate_schedule(
                project_id="project-a",
                task_id="OOMPAH-1",
                decision_revision=decision().decision_revision,
                snapshot_generation=1,
            )
            raise BatchInterrupted

    assert store.schedule_cursor(
        project_id="project-a", task_id="OOMPAH-1"
    ) is None
    with store.scheduling_batch():
        store.activate_schedule(
            project_id="project-a",
            task_id="OOMPAH-1",
            decision_revision=decision().decision_revision,
            snapshot_generation=2,
        )
    assert store.schedule_cursor(
        project_id="project-a", task_id="OOMPAH-1"
    ).snapshot_generation == 2


def test_recurring_semantic_decision_gets_new_activation_after_supersession(store):
    scheduler = WorkflowJobScheduler(store=store)
    first_decision = decision(evidence="facts-1")
    changed_decision = decision(evidence="facts-2")

    scheduler.reconcile((first_decision,))
    scheduler.reconcile((changed_decision,))
    returned = scheduler.reconcile((first_decision,))

    jobs = store.list_jobs()
    assert returned.jobs_created == 1
    assert len(jobs) == 3
    assert [job.state for job in jobs] == [
        WorkflowJobState.SUPERSEDED,
        WorkflowJobState.SUPERSEDED,
        WorkflowJobState.QUEUED,
    ]
    assert jobs[0].generation != jobs[2].generation


def test_decision_without_jobs_supersedes_obsolete_automatic_work(store):
    scheduler = WorkflowJobScheduler(store=store)
    scheduler.reconcile((decision(),))

    result = scheduler.reconcile((decision(evidence="facts-2", jobs=()),))

    assert result.jobs_superseded == 1
    assert store.list_jobs()[0].state is WorkflowJobState.SUPERSEDED


def test_concurrent_identical_reconciliation_is_idempotent(tmp_path, clock):
    path = str(tmp_path / "concurrent.sqlite3")
    stores = [WorkflowJobStore(path, clock=clock) for _ in range(8)]
    schedulers = [WorkflowJobScheduler(store=value) for value in stores]
    generations = [scheduler.begin_scan() for scheduler in schedulers]
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(
                pool.map(
                    lambda item: item[0].reconcile(
                        (decision(),), snapshot_generation=item[1]
                    ),
                    zip(schedulers, generations, strict=True),
                )
            )
        jobs = stores[0].list_jobs()
        assert len([job for job in jobs if job.is_active]) == 1
        assert sum(result.jobs_created for result in results) >= 1
        assert stores[0].schedule_cursor(
            project_id="project-a", task_id="OOMPAH-1"
        ).snapshot_generation == max(generations)
    finally:
        for value in stores:
            value.close()


def test_claims_serialize_distinct_actions_for_one_task(store):
    store.enqueue(direct_spec("one", action="first"))
    store.enqueue(direct_spec("two", action="second"))

    first = store.claim_next(lease_owner="worker-a", lease_seconds=30)
    blocked = store.claim_next(lease_owner="worker-b", lease_seconds=30)
    store.complete(first.job_id, first.lease_token)
    second = store.claim_next(lease_owner="worker-b", lease_seconds=30)

    assert blocked is None
    assert second is not None
    assert second.task_id == first.task_id


def test_fair_claiming_rotates_projects_and_survives_restart(tmp_path, clock):
    path = str(tmp_path / "fair.sqlite3")
    store = WorkflowJobStore(path, clock=clock)
    for number in range(3):
        store.enqueue(
            direct_spec(
                f"a-{number}",
                project="project-a",
                task=f"A-{number}",
                priority=1,
            )
        )
    store.enqueue(direct_spec("b-1", project="project-b", task="B-1"))

    first = store.claim_next(
        lease_owner="worker", lease_seconds=30, fair_across_projects=True
    )
    store.complete(first.job_id, first.lease_token)
    store.close()
    reopened = WorkflowJobStore(path, clock=clock)
    try:
        second = reopened.claim_next(
            lease_owner="worker", lease_seconds=30, fair_across_projects=True
        )
        assert (first.project_id, second.project_id) == ("project-a", "project-b")
    finally:
        reopened.close()


def test_health_snapshot_exposes_queue_lease_retry_and_cursor_state(store, clock):
    scheduler = WorkflowJobScheduler(store=store)
    scheduler.reconcile((decision(),))
    running = store.claim_next(lease_owner="worker", lease_seconds=1)
    clock.advance(2)

    health = scheduler.health_snapshot()

    assert health["jobs"]["leases"] == {"running": 1, "expired": 1}
    assert health["jobs"]["schedule_cursor_count"] == 1
    assert health["jobs"]["latest_snapshot_generation"] == 1
    assert "lease_token" not in str(health)
    assert running.lease_token not in str(health)


class CompletingWorker:
    def __init__(self, store: WorkflowJobStore) -> None:
        self.store = store
        self.projects: list[str] = []
        self.active_count = 0
        self.drain_calls = 0

    async def run_once(self, *, fair_across_projects: bool = False):
        job = self.store.claim_next(
            lease_owner="completer",
            lease_seconds=30,
            fair_across_projects=fair_across_projects,
        )
        if job is None:
            return WorkflowRunResult(WorkflowRunDisposition.IDLE, None, None, "idle")
        self.projects.append(job.project_id)
        completed = self.store.complete(job.job_id, job.lease_token)
        return WorkflowRunResult(
            WorkflowRunDisposition.COMPLETED,
            completed.job_id,
            completed.state,
            "completed",
            completed.attempts,
        )

    async def drain(self, *, timeout_seconds=None):
        self.drain_calls += 1
        return True


@pytest.mark.asyncio
async def test_scheduler_runs_bounded_parallel_work_with_project_fairness(store):
    store.enqueue(direct_spec("a-1", project="project-a", task="A-1", priority=1))
    store.enqueue(direct_spec("a-2", project="project-a", task="A-2", priority=1))
    store.enqueue(direct_spec("b-1", project="project-b", task="B-1"))
    worker = CompletingWorker(store)
    scheduler = WorkflowJobScheduler(store=store, worker=worker, concurrency=2)

    batch = await scheduler.run_due(limit=3)

    assert batch.attempted == 3
    assert worker.projects[:2] == ["project-a", "project-b"]
    assert batch.dispositions == {"completed": 3}


@pytest.mark.asyncio
async def test_event_wakeups_coalesce_and_timeout_full_sync_recovers(store):
    scheduler = WorkflowJobScheduler(store=store)
    calls = 0

    async def source():
        nonlocal calls
        calls += 1
        if calls == 1:
            scheduler.wake("task changed")
            scheduler.wake("duplicate task event")
        return (decision(),)

    await scheduler.serve(
        source,
        full_sync_interval_seconds=0.01,
        max_cycles=3,
    )

    health = scheduler.health_snapshot()["scheduler"]
    assert calls == 3
    assert health["wakeups"] == 2
    assert health["coalesced_wakeups"] == 1
    assert health["full_syncs"] == 3
    assert len(store.list_jobs()) == 1


@pytest.mark.asyncio
async def test_graceful_drain_stops_claims_and_drains_worker(store):
    worker = CompletingWorker(store)
    scheduler = WorkflowJobScheduler(store=store, worker=worker)

    drained = await scheduler.drain(timeout_seconds=1)
    batch = await scheduler.run_due()

    assert drained is True
    assert worker.drain_calls == 1
    assert scheduler.accepting is False
    assert batch.attempted == 0


def test_exclusive_restart_recovers_abandoned_job_immediately(tmp_path, clock):
    path = str(tmp_path / "abandoned.sqlite3")
    first = WorkflowJobStore(path, clock=clock)
    first.enqueue(direct_spec("restart"))
    claimed = first.claim_next(lease_owner="old-process", lease_seconds=300)
    first.close()

    reopened = WorkflowJobStore(path, clock=clock)
    try:
        scheduler = WorkflowJobScheduler(store=reopened)
        recovered = scheduler.recover_startup(abandoned=True)
        assert recovered == {"expired": 0, "abandoned": 1}
        assert reopened.get(claimed.job_id).state is WorkflowJobState.QUEUED
    finally:
        reopened.close()


def test_reconciliation_is_bounded_and_deterministic(store):
    scheduler = WorkflowJobScheduler(store=store, decision_limit=2)
    result = scheduler.reconcile(
        tuple(decision(task=f"OOMPAH-{number}") for number in (3, 1, 2))
    )

    assert result.decisions_seen == 2
    assert result.truncated is True
    assert [job.task_id for job in store.list_jobs()] == ["OOMPAH-1", "OOMPAH-2"]

    scheduler.reconcile(
        tuple(decision(task=f"OOMPAH-{number}") for number in (3, 1, 2))
    )
    assert [job.task_id for job in store.list_jobs()] == [
        "OOMPAH-1",
        "OOMPAH-2",
        "OOMPAH-3",
    ]


def test_explicit_zero_snapshot_generation_is_rejected(store):
    scheduler = WorkflowJobScheduler(store=store)

    with pytest.raises(ValueError, match="positive"):
        scheduler.reconcile((decision(),), snapshot_generation=0)


def test_scheduler_rejects_unbounded_parallelism(store):
    with pytest.raises(ValueError, match="cannot exceed"):
        WorkflowJobScheduler(store=store, concurrency=65)
