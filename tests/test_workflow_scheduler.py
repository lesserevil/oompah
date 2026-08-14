from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from threading import Event

import pytest

from oompah.work_decision import (
    PermittedAction,
    WorkDecision,
    decision_scheduling_revision,
)
from oompah.workflow_contract import TaskDisposition, WorkflowOwner
from oompah.workflow_jobs import (
    WorkflowFailureCategory,
    WorkflowJobLeaseLost,
    WorkflowJobSpec,
    WorkflowJobState,
    WorkflowJobStore,
)
from oompah.workflow_reasons import AlertSeverity
from oompah.workflow_scheduler import WorkflowJobScheduler
from oompah.workflow_worker import (
    DurableWorkflowWorker,
    RevalidationResult,
    WorkflowActionDomain,
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


class SameGenerationReassessmentHandler:
    """Return a fresh negative decision without naming newer authority."""

    domain = WorkflowActionDomain.TRACKER

    async def revalidate(self, context):
        return RevalidationResult(
            generation=context.job.generation,
            evidence_revision=context.job.expected_evidence_revision,
            head_sha=context.job.expected_head_sha,
            current=False,
        )


def reassessment_worker(store: WorkflowJobStore) -> DurableWorkflowWorker:
    return DurableWorkflowWorker(
        store=store,
        handlers={
            "implementation_recovery": SameGenerationReassessmentHandler()
        },
        transition_services={},
        worker_id="reassessment-worker",
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
        converged = WorkflowJobScheduler(
            store=reopened, decision_limit=2
        ).reconcile(decisions)
        assert {job.task_id for job in reopened.list_jobs()} == {
            "OOMPAH-1",
            "OOMPAH-2",
            "OOMPAH-3",
        }
        assert converged.jobs_materialized == 3
        assert converged.schedules_materialized == 3
        claimable = set()
        for index in range(3):
            claimed = reopened.claim_next(
                lease_owner=f"restart-worker-{index}", lease_seconds=30
            )
            assert claimed is not None
            claimable.add(claimed.task_id)
        assert claimable == {"OOMPAH-1", "OOMPAH-2", "OOMPAH-3"}
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
    assert cursor.decision_revision == decision_scheduling_revision(
        decision(evidence="facts-2")
    )


def test_protected_same_action_event_satisfies_current_schedule(store):
    scheduler = WorkflowJobScheduler(
        store=store,
        protected_event_lane_prefixes=("epic-event:",),
    )
    current = decision(jobs=("child_landing_verification",))
    first = scheduler.reconcile((current,))
    managed = store.list_jobs()[0]
    event = store.materialize_event(
        project_id=current.project_id,
        task_id=current.task_id,
        decision_revision="event-revision",
        action="child_landing_verification",
        idempotency_namespace="epic-action:child_landing_verification",
        scheduling_lane="epic-event:child_landing_verification",
    )

    replay = scheduler.reconcile((current,))

    assert first.jobs_materialized == 1
    assert store.get(managed.job_id).state is WorkflowJobState.SUPERSEDED
    assert event.job is not None
    assert store.get(event.job.job_id).state is WorkflowJobState.QUEUED
    assert replay.jobs_materialized == 1
    assert replay.schedules_materialized == 1
    assert replay.truncated is False


def test_protected_different_action_cannot_satisfy_current_schedule(store):
    scheduler = WorkflowJobScheduler(
        store=store,
        protected_event_lane_prefixes=("epic-event:",),
    )
    current = decision(jobs=("child_landing_verification",))
    scheduler.reconcile((current,))
    store.materialize_event(
        project_id=current.project_id,
        task_id=current.task_id,
        decision_revision="event-revision",
        action="epic_restart_reconciliation",
        idempotency_namespace="epic-action:epic_restart_reconciliation",
        scheduling_lane="epic-event:epic_restart_reconciliation",
    )

    replay = scheduler.reconcile((current,))

    assert replay.jobs_required == 1
    assert replay.jobs_materialized == 0
    assert replay.truncated is True


def test_completed_recurring_action_rearms_only_after_reassessment_deadline(
    store, clock
):
    scheduler = WorkflowJobScheduler(store=store)

    def due(at: float) -> WorkDecision:
        return replace(
            decision(),
            next_reassessment_at=datetime.fromtimestamp(
                at, tz=timezone.utc
            ).isoformat(),
            decision_revision=None,
        )

    first_result = scheduler.reconcile((due(1010),))
    first = store.list_jobs()[0]
    initial_cursor = store.schedule_cursor(
        project_id=first.project_id, task_id=first.task_id
    )
    assert initial_cursor is not None
    assert store.schedule_specs_materialized(
        project_id=first.project_id,
        task_id=first.task_id,
        decision_revision=initial_cursor.decision_revision,
        job_generation=initial_cursor.job_generation,
        idempotency_keys=(first.idempotency_key,),
    )
    claimed = store.claim_next(
        lease_owner="worker-1", lease_seconds=30, now=clock.now
    )
    assert claimed is not None and claimed.job_id == first.job_id
    assert store.schedule_specs_materialized(
        project_id=first.project_id,
        task_id=first.task_id,
        decision_revision=initial_cursor.decision_revision,
        job_generation=initial_cursor.job_generation,
        idempotency_keys=(first.idempotency_key,),
    )
    store.complete(claimed.job_id, claimed.lease_token, now=clock.now)

    clock.advance(5)
    before = scheduler.reconcile((due(1020),))
    first_cursor = store.schedule_cursor(
        project_id=first.project_id, task_id=first.task_id
    )
    assert first_result.jobs_created == 1
    assert before.jobs_created == 0
    assert len(store.list_jobs()) == 1
    assert first_cursor is not None
    assert store.schedule_specs_materialized(
        project_id=first.project_id,
        task_id=first.task_id,
        decision_revision=first_cursor.decision_revision,
        job_generation=first_cursor.job_generation,
        idempotency_keys=(first.idempotency_key,),
    )

    clock.advance(5)
    after = scheduler.reconcile((due(1020),))
    jobs = store.list_jobs()
    current = store.schedule_cursor(
        project_id=first.project_id, task_id=first.task_id
    )
    assert after.jobs_created == 1
    assert len(jobs) == 2
    assert current is not None and current.job_generation != first.generation
    assert store.schedule_specs_materialized(
        project_id=first.project_id,
        task_id=first.task_id,
        decision_revision=current.decision_revision,
        job_generation=current.job_generation,
        idempotency_keys=(jobs[-1].idempotency_key,),
    )


@pytest.mark.asyncio
async def test_same_generation_reassessment_does_not_amplify_before_deadline(
    tmp_path, clock
):
    path = str(tmp_path / "recurring-reassessment.sqlite3")

    def recurring(deadline: float) -> WorkDecision:
        return replace(
            decision(),
            next_reassessment_at=datetime.fromtimestamp(
                deadline, tz=timezone.utc
            ).isoformat(),
            decision_revision=None,
        )

    first_store = WorkflowJobStore(path, clock=clock)
    first_scheduler = WorkflowJobScheduler(store=first_store)
    first = first_scheduler.reconcile((recurring(1100),))
    original = first_store.list_jobs()[0]

    deferred = await reassessment_worker(first_store).run_once()
    waiting = first_store.get(original.job_id)

    assert first.jobs_created == 1
    assert deferred.disposition is WorkflowRunDisposition.RETRY_SCHEDULED
    assert waiting.state is WorkflowJobState.RETRY_WAIT
    assert waiting.retry_at == 1100
    assert waiting.attempts == 0

    # Production world cuts compute a fresh absolute deadline each time. The
    # semantic scheduling revision deliberately excludes that timestamp, so
    # every pre-deadline scan must retain the original generation and job.
    for advance in (10, 20, 30):
        clock.advance(advance)
        replay = first_scheduler.reconcile((recurring(clock.now + 100),))
        assert replay.jobs_created == 0
        assert replay.jobs_materialized == 1
        assert replay.schedules_materialized == 1
        assert replay.truncated is False
        assert first_store.list_jobs() == (waiting,)
    first_store.close()

    reopened = WorkflowJobStore(path, clock=clock)
    try:
        restarted_scheduler = WorkflowJobScheduler(store=reopened)
        restarted = restarted_scheduler.reconcile((recurring(clock.now + 100),))
        persisted = reopened.get(original.job_id)

        assert restarted.jobs_created == 0
        assert restarted.jobs_materialized == 1
        assert restarted.schedules_materialized == 1
        assert persisted.state is WorkflowJobState.RETRY_WAIT
        assert persisted.retry_at == 1100
        assert len(reopened.list_jobs()) == 1

        clock.advance(39)
        assert (
            await reassessment_worker(reopened).run_once()
        ).disposition is WorkflowRunDisposition.IDLE
        before_due = restarted_scheduler.reconcile(
            (recurring(clock.now + 100),)
        )
        assert before_due.jobs_created == 0
        assert before_due.jobs_materialized == 1
        assert len(reopened.list_jobs()) == 1

        clock.advance(1)
        due = await reassessment_worker(reopened).run_once()
        retired = reopened.get(original.job_id)
        assert due.disposition is WorkflowRunDisposition.SUPERSEDED
        assert retired.state is WorkflowJobState.SUPERSEDED
        assert retired.superseded_by_generation == (
            f"reassess:{original.generation}"
        )

        replacement = restarted_scheduler.reconcile(
            (recurring(clock.now + 100),)
        )
        jobs = reopened.list_jobs()
        assert replacement.jobs_created == 1
        assert replacement.jobs_materialized == 1
        assert replacement.schedules_materialized == 1
        assert len(jobs) == 2
        assert jobs[-1].state is WorkflowJobState.QUEUED
        assert jobs[-1].generation != original.generation
    finally:
        reopened.close()


def test_superseded_current_action_rearms_immediately_for_unchanged_decision(
    store, clock
):
    scheduler = WorkflowJobScheduler(store=store)
    current = replace(
        decision(),
        next_reassessment_at=datetime.fromtimestamp(
            1100, tz=timezone.utc
        ).isoformat(),
        decision_revision=None,
    )
    first_result = scheduler.reconcile((current,))
    first = store.list_jobs()[0]
    store.supersede(
        first.job_id,
        generation=first.generation,
        replacement_generation=f"reassess:{first.generation}",
        reason="fresh worker evidence changed",
    )

    replacement_result = scheduler.reconcile((current,))
    jobs = store.list_jobs()
    cursor = store.schedule_cursor(
        project_id=first.project_id, task_id=first.task_id
    )

    assert first_result.jobs_created == 1
    assert replacement_result.jobs_created == 1
    assert replacement_result.jobs_materialized == 1
    assert replacement_result.truncated is False
    assert len(jobs) == 2
    assert jobs[-1].state is WorkflowJobState.QUEUED
    assert jobs[-1].generation != first.generation
    assert cursor is not None
    assert cursor.job_generation == jobs[-1].generation


def test_superseded_recurring_action_rearms_after_store_restart(tmp_path, clock):
    path = str(tmp_path / "superseded-restart.sqlite3")
    current = replace(
        decision(),
        next_reassessment_at=datetime.fromtimestamp(
            1100, tz=timezone.utc
        ).isoformat(),
        decision_revision=None,
    )
    first_store = WorkflowJobStore(path, clock=clock)
    first_scheduler = WorkflowJobScheduler(store=first_store)
    first_scheduler.reconcile((current,))
    original = first_store.list_jobs()[0]
    first_store.supersede(
        original.job_id,
        generation=original.generation,
        replacement_generation=f"reassess:{original.generation}",
        reason="fresh worker evidence changed",
    )
    first_store.close()

    reopened = WorkflowJobStore(path, clock=clock)
    try:
        recovered = WorkflowJobScheduler(store=reopened).reconcile((current,))
        jobs = reopened.list_jobs()

        assert recovered.jobs_required == 1
        assert recovered.jobs_created == 1
        assert recovered.jobs_materialized == 1
        assert recovered.schedules_materialized == 1
        assert recovered.truncated is False
        assert len(jobs) == 2
        assert jobs[-1].state is WorkflowJobState.QUEUED
        assert jobs[-1].generation != original.generation
        assert jobs[-1].idempotency_key != original.idempotency_key
    finally:
        reopened.close()


def test_cancelled_recurring_action_remains_explicitly_revoked(store, clock):
    scheduler = WorkflowJobScheduler(store=store)
    current = replace(
        decision(),
        next_reassessment_at=datetime.fromtimestamp(
            1010, tz=timezone.utc
        ).isoformat(),
        decision_revision=None,
    )
    scheduler.reconcile((current,))
    first = store.list_jobs()[0]
    store.cancel(
        first.job_id,
        generation=first.generation,
        reason="operator revoked current execution authority",
    )

    clock.advance(60)
    replay = scheduler.reconcile((current,))

    assert replay.jobs_created == 0
    assert replay.jobs_materialized == 0
    assert replay.truncated is True
    assert len(store.list_jobs()) == 1
    assert store.get(first.job_id).state is WorkflowJobState.CANCELLED


def test_completed_protected_event_releases_superseded_managed_rearm(
    store, clock
):
    scheduler = WorkflowJobScheduler(
        store=store,
        protected_event_lane_prefixes=("epic-event:",),
    )
    current = replace(
        decision(jobs=("child_landing_verification",)),
        next_reassessment_at=datetime.fromtimestamp(
            1100, tz=timezone.utc
        ).isoformat(),
        decision_revision=None,
    )
    scheduler.reconcile((current,))
    managed = store.list_jobs()[0]
    event = store.materialize_event(
        project_id=current.project_id,
        task_id=current.task_id,
        decision_revision="event-revision",
        action="child_landing_verification",
        idempotency_namespace="epic-action:child_landing_verification",
        scheduling_lane="epic-event:child_landing_verification",
    )
    assert event.job is not None

    protected = scheduler.reconcile((current,))
    assert protected.jobs_created == 0
    assert protected.jobs_materialized == 1
    assert len(store.list_jobs()) == 2

    claimed = store.claim_next(
        lease_owner="event-worker",
        lease_seconds=30,
        generation=event.job.generation,
        now=clock.now,
    )
    assert claimed is not None and claimed.job_id == event.job.job_id
    store.complete(claimed.job_id, claimed.lease_token, now=clock.now)

    replacement = scheduler.reconcile((current,))
    jobs = store.list_jobs()

    assert store.get(managed.job_id).state is WorkflowJobState.SUPERSEDED
    assert replacement.jobs_created == 1
    assert replacement.jobs_materialized == 1
    assert replacement.truncated is False
    assert len(jobs) == 3
    assert jobs[-1].state is WorkflowJobState.QUEUED
    assert jobs[-1].generation != managed.generation


def test_latest_protected_event_prevents_managed_rearm_across_supersession_chain(
    store, clock
):
    scheduler = WorkflowJobScheduler(
        store=store,
        protected_event_lane_prefixes=("epic-event:",),
    )
    current = replace(
        decision(jobs=("child_landing_verification",)),
        next_reassessment_at=datetime.fromtimestamp(
            1100, tz=timezone.utc
        ).isoformat(),
        decision_revision=None,
    )
    scheduler.reconcile((current,))
    managed = store.list_jobs()[0]
    event_b = store.materialize_event(
        project_id=current.project_id,
        task_id=current.task_id,
        decision_revision="event-b",
        action="child_landing_verification",
        idempotency_namespace="epic-action:child_landing_verification",
        scheduling_lane="epic-event:child_landing_verification",
    )
    event_c = store.materialize_event(
        project_id=current.project_id,
        task_id=current.task_id,
        decision_revision="event-c",
        action="child_landing_verification",
        idempotency_namespace="epic-action:child_landing_verification",
        scheduling_lane="epic-event:child_landing_verification",
    )
    assert event_b.job is not None and event_c.job is not None
    assert store.get(managed.job_id).state is WorkflowJobState.SUPERSEDED
    assert store.get(event_b.job.job_id).state is WorkflowJobState.SUPERSEDED
    assert store.get(event_c.job.job_id).state is WorkflowJobState.QUEUED

    protected = scheduler.reconcile((current,))

    assert protected.jobs_created == 0
    assert protected.jobs_materialized == 1
    assert protected.truncated is False
    assert len(store.list_jobs()) == 3

    claimed = store.claim_next(
        lease_owner="event-worker",
        lease_seconds=30,
        generation=event_c.job.generation,
        now=clock.now,
    )
    assert claimed is not None and claimed.job_id == event_c.job.job_id
    store.complete(claimed.job_id, claimed.lease_token, now=clock.now)

    replacement = scheduler.reconcile((current,))

    assert replacement.jobs_created == 1
    assert replacement.jobs_materialized == 1
    assert replacement.truncated is False
    assert len(store.list_jobs()) == 4
    assert store.list_jobs()[-1].state is WorkflowJobState.QUEUED


def test_protected_event_defers_completed_managed_rearm_past_deadline(
    store, clock
):
    scheduler = WorkflowJobScheduler(
        store=store,
        protected_event_lane_prefixes=("epic-event:",),
    )
    current = replace(
        decision(jobs=("child_landing_verification",)),
        next_reassessment_at=datetime.fromtimestamp(
            1010, tz=timezone.utc
        ).isoformat(),
        decision_revision=None,
    )
    scheduler.reconcile((current,))
    managed = store.list_jobs()[0]
    claimed = store.claim_next(
        lease_owner="managed-worker",
        lease_seconds=30,
        generation=managed.generation,
        now=clock.now,
    )
    assert claimed is not None and claimed.job_id == managed.job_id
    store.complete(claimed.job_id, claimed.lease_token, now=clock.now)
    event = store.materialize_event(
        project_id=current.project_id,
        task_id=current.task_id,
        decision_revision="event-after-managed-completion",
        action="child_landing_verification",
        idempotency_namespace="epic-action:child_landing_verification",
        scheduling_lane="epic-event:child_landing_verification",
    )
    assert event.job is not None

    clock.advance(60)
    protected = scheduler.reconcile((current,))

    assert protected.jobs_created == 0
    assert protected.jobs_materialized == 1
    assert protected.truncated is False
    assert len(store.list_jobs()) == 2

    event_claim = store.claim_next(
        lease_owner="event-worker",
        lease_seconds=30,
        generation=event.job.generation,
        now=clock.now,
    )
    assert event_claim is not None and event_claim.job_id == event.job.job_id
    store.complete(event_claim.job_id, event_claim.lease_token, now=clock.now)

    replacement = scheduler.reconcile((current,))

    assert replacement.jobs_created == 1
    assert replacement.jobs_materialized == 1
    assert replacement.truncated is False
    assert len(store.list_jobs()) == 3
    assert store.list_jobs()[-1].state is WorkflowJobState.QUEUED


def test_exhausted_recurring_action_remains_fenced_after_deadline(store, clock):
    scheduler = WorkflowJobScheduler(store=store)
    current = replace(
        decision(),
        next_reassessment_at=datetime.fromtimestamp(
            1010, tz=timezone.utc
        ).isoformat(),
        decision_revision=None,
    )
    scheduler.reconcile((current,))
    first = store.list_jobs()[0]
    claimed = store.claim_next(
        lease_owner="worker-1", lease_seconds=30, now=clock.now
    )
    assert claimed is not None
    store.fail(
        claimed.job_id,
        claimed.lease_token,
        category=WorkflowFailureCategory.PERMANENT,
        error="terminal failure",
        retryable=False,
        now=clock.now,
    )

    clock.advance(60)
    replay = scheduler.reconcile((current,))
    cursor = store.schedule_cursor(
        project_id=first.project_id, task_id=first.task_id
    )

    assert replay.jobs_created == 0
    assert replay.jobs_materialized == 0
    assert replay.truncated is True
    assert len(store.list_jobs()) == 1
    assert store.get(first.job_id).state is WorkflowJobState.EXHAUSTED
    assert cursor is not None and cursor.job_generation == first.generation


def test_completed_action_without_reassessment_deadline_remains_terminal(
    store, clock
):
    scheduler = WorkflowJobScheduler(store=store)
    first = scheduler.reconcile((decision(),))
    job = store.list_jobs()[0]
    initial_cursor = store.schedule_cursor(
        project_id=job.project_id, task_id=job.task_id
    )
    claimed = store.claim_next(
        lease_owner="worker-1", lease_seconds=30, now=clock.now
    )
    assert claimed is not None
    store.complete(claimed.job_id, claimed.lease_token, now=clock.now)

    clock.advance(60)
    replay = scheduler.reconcile((decision(),))
    current_cursor = store.schedule_cursor(
        project_id=job.project_id, task_id=job.task_id
    )

    assert first.jobs_created == 1
    assert replay.jobs_created == 0
    assert len(store.list_jobs()) == 1
    assert store.get(job.job_id).state is WorkflowJobState.COMPLETED
    assert current_cursor is not None and initial_cursor is not None
    assert current_cursor.job_generation == initial_cursor.job_generation


def test_expired_running_schedule_does_not_prove_materialization(store, clock):
    scheduler = WorkflowJobScheduler(store=store)
    scheduler.reconcile((decision(),))
    job = store.list_jobs()[0]
    cursor = store.schedule_cursor(
        project_id=job.project_id, task_id=job.task_id
    )
    running = store.claim_next(
        lease_owner="worker-1", lease_seconds=10, now=clock.now
    )
    assert cursor is not None and running is not None
    clock.advance(11)

    assert not store.schedule_specs_materialized(
        project_id=job.project_id,
        task_id=job.task_id,
        decision_revision=cursor.decision_revision,
        job_generation=cursor.job_generation,
        idempotency_keys=(job.idempotency_key,),
    )


def test_retry_wait_schedule_proves_materialization(store):
    scheduler = WorkflowJobScheduler(store=store)
    scheduler.reconcile((decision(),))
    job = store.list_jobs()[0]
    cursor = store.schedule_cursor(
        project_id=job.project_id, task_id=job.task_id
    )
    running = store.claim_next(lease_owner="worker-1", lease_seconds=10)
    assert cursor is not None and running is not None
    waiting = store.fail(
        running.job_id,
        running.lease_token,
        category=WorkflowFailureCategory.TRANSIENT,
        error="retry later",
        retryable=True,
        retry_delay_seconds=60,
    )

    assert waiting.state is WorkflowJobState.RETRY_WAIT
    assert store.schedule_specs_materialized(
        project_id=job.project_id,
        task_id=job.task_id,
        decision_revision=cursor.decision_revision,
        job_generation=cursor.job_generation,
        idempotency_keys=(job.idempotency_key,),
    )


def test_scheduling_revision_encodes_recurrence_and_policy_not_absolute_time():
    nonrecurring = decision()
    recurring_a = replace(
        nonrecurring,
        next_reassessment_at=datetime.fromtimestamp(
            1010, tz=timezone.utc
        ).isoformat(),
        decision_revision=None,
    )
    recurring_b = replace(
        nonrecurring,
        next_reassessment_at=datetime.fromtimestamp(
            2020, tz=timezone.utc
        ).isoformat(),
        decision_revision=None,
    )

    recurring_revision = decision_scheduling_revision(
        recurring_a, policy_epoch="policy-a"
    )

    assert recurring_revision == decision_scheduling_revision(
        recurring_b, policy_epoch="policy-a"
    )
    assert recurring_revision != decision_scheduling_revision(
        nonrecurring, policy_epoch="policy-a"
    )
    assert recurring_revision != decision_scheduling_revision(
        recurring_a, policy_epoch="policy-b"
    )
    assert decision_scheduling_revision(
        nonrecurring, policy_epoch="policy-a"
    ) == decision_scheduling_revision(
        nonrecurring, policy_epoch="policy-b"
    )


def test_policy_epoch_change_creates_new_semantic_activation(store):
    scheduler = WorkflowJobScheduler(store=store, policy_epoch="policy-a")
    recurring = replace(
        decision(),
        next_reassessment_at=datetime.fromtimestamp(
            1010, tz=timezone.utc
        ).isoformat(),
        decision_revision=None,
    )

    first = scheduler.reconcile((recurring,))
    first_cursor = store.schedule_cursor(
        project_id="project-a", task_id="OOMPAH-1"
    )
    scheduler.configure_policy_epoch("policy-b")
    second = scheduler.reconcile((recurring,))
    second_cursor = store.schedule_cursor(
        project_id="project-a", task_id="OOMPAH-1"
    )

    assert first.jobs_created == 1
    assert second.jobs_created == 1
    assert second.jobs_superseded == 1
    assert first_cursor is not None and second_cursor is not None
    assert first_cursor.decision_revision != second_cursor.decision_revision


def test_scheduler_rejects_multiple_jobs_for_one_decision(store):
    scheduler = WorkflowJobScheduler(store=store)

    with pytest.raises(ValueError, match="at most one durable job"):
        scheduler.reconcile((decision(jobs=("job-a", "job-b")),))

    assert store.list_jobs() == ()


def test_concurrent_global_fence_rejects_old_task_absent_from_newer_snapshot(
    store,
):
    scheduler = WorkflowJobScheduler(store=store)
    slow_generation = scheduler.begin_scan()
    slow_ready = Event()
    release_slow = Event()

    def finish_slow_scan():
        slow_ready.set()
        assert release_slow.wait(timeout=2)
        return scheduler.reconcile(
            (decision(task="OOMPAH-old"),),
            snapshot_generation=slow_generation,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        future = pool.submit(finish_slow_scan)
        assert slow_ready.wait(timeout=2)
        newer = scheduler.reconcile(())
        release_slow.set()
        stale = future.result(timeout=2)

    assert newer.snapshot_accepted
    assert not stale.snapshot_accepted
    assert stale.stale_rejected == 1
    assert store.list_jobs() == ()
    assert store.schedule_cursor(
        project_id="project-a", task_id="OOMPAH-old"
    ) is None
    assert scheduler.health_snapshot()["scheduler"]["stale_decisions"] == 0


def test_newer_authoritative_snapshot_retires_published_task_across_restart(
    tmp_path,
):
    path = str(tmp_path / "retired-membership.sqlite3")
    first_store = WorkflowJobStore(path)
    first_scheduler = WorkflowJobScheduler(store=first_store)
    published = first_scheduler.reconcile((decision(task="OOMPAH-retired"),))

    assert published.jobs_created == 1
    assert first_store.schedule_cursor(
        project_id="project-a", task_id="OOMPAH-retired"
    ) is not None

    retired = first_scheduler.reconcile(
        (),
        authoritative_project_ids=("project-a",),
    )

    assert retired.snapshot_accepted
    assert retired.jobs_superseded == 1
    assert first_store.get(first_store.list_jobs()[0].job_id).state is (
        WorkflowJobState.SUPERSEDED
    )
    assert first_store.schedule_cursor(
        project_id="project-a", task_id="OOMPAH-retired"
    ) is None
    assert first_store.snapshot_membership() == ()
    first_store.close()

    reopened = WorkflowJobStore(path)
    try:
        assert reopened.schedule_cursor(
            project_id="project-a", task_id="OOMPAH-retired"
        ) is None
        assert reopened.snapshot_membership() == ()
        assert reopened.claim_next(
            lease_owner="worker-after-restart", lease_seconds=30
        ) is None
        assert reopened.health_snapshot()["schedule_cursor_count"] == 0
    finally:
        reopened.close()


def test_schedule_reconciliation_never_supersedes_direct_enqueue_jobs(store):
    direct = store.enqueue(direct_spec("manual-job"))
    scheduler = WorkflowJobScheduler(store=store)

    first = scheduler.reconcile((decision(evidence="facts-1"),))
    first_managed = next(
        job for job in store.list_jobs() if job.workflow_managed
    )
    second = scheduler.reconcile((decision(evidence="facts-2"),))
    second_managed = [
        job
        for job in store.list_jobs()
        if job.workflow_managed and job.job_id != first_managed.job_id
    ]

    assert first.jobs_created == 1
    assert second.jobs_created == 1
    assert store.get(direct.job_id).state is WorkflowJobState.QUEUED
    assert not store.get(direct.job_id).workflow_managed
    assert store.get(first_managed.job_id).state is WorkflowJobState.SUPERSEDED
    assert len(second_managed) == 1
    assert second_managed[0].state is WorkflowJobState.QUEUED

    retired = scheduler.reconcile(
        (), authoritative_project_ids=("project-a",)
    )

    assert retired.jobs_superseded == 1
    assert store.get(direct.job_id).state is WorkflowJobState.QUEUED
    assert store.get(second_managed[0].job_id).state is WorkflowJobState.SUPERSEDED


def test_v4_migration_never_reclassifies_direct_job_as_workflow_managed(tmp_path):
    path = str(tmp_path / "migration.sqlite3")
    first = WorkflowJobStore(path)
    direct = first.enqueue(direct_spec("workflow-decision:looks-managed"))
    first._conn.execute(  # noqa: SLF001 - simulate an existing v4 cursor
        """
        INSERT INTO workflow_schedule_cursors(
            project_id, task_id, snapshot_generation, decision_revision,
            job_generation, materialized_job_generation, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("project-a", "OOMPAH-1", 0, "old", "generation-1", "generation-1", 0),
    )
    first._conn.execute(  # noqa: SLF001 - exercise the migration boundary
        "INSERT OR REPLACE INTO schema_meta(key, value) VALUES(?, ?)",
        ("workflow_jobs_version", "4"),
    )
    first._conn.commit()  # noqa: SLF001
    first.close()

    reopened = WorkflowJobStore(path)
    try:
        assert not reopened.get(direct.job_id).workflow_managed
        WorkflowJobScheduler(store=reopened).reconcile((decision(evidence="facts-2"),))
        assert reopened.get(direct.job_id).state is WorkflowJobState.QUEUED
        assert not reopened.get(direct.job_id).workflow_managed
    finally:
        reopened.close()


def test_newer_authoritative_snapshot_revokes_active_claim_for_absent_task(store):
    scheduler = WorkflowJobScheduler(store=store)
    scheduler.reconcile(
        tuple(
            decision(task=task)
            for task in ("OOMPAH-a-retry", "OOMPAH-b-running", "OOMPAH-c-queued")
        )
    )
    retry_claim = store.claim_next(lease_owner="worker-a", lease_seconds=30)
    assert retry_claim is not None
    waiting = store.fail(
        retry_claim.job_id,
        retry_claim.lease_token,
        category=WorkflowFailureCategory.TRANSPORT,
        error="provider unavailable",
        retryable=True,
        retry_delay_seconds=60,
    )
    claimed = store.claim_next(lease_owner="worker-b", lease_seconds=30)

    assert claimed is not None
    assert claimed.state is WorkflowJobState.RUNNING
    assert waiting.state is WorkflowJobState.RETRY_WAIT

    retired = scheduler.reconcile(
        (),
        authoritative_project_ids=("project-a",),
    )

    assert retired.jobs_superseded == 3
    assert all(
        job.state is WorkflowJobState.SUPERSEDED
        for job in store.list_jobs()
    )
    assert store.get(claimed.job_id).state is WorkflowJobState.SUPERSEDED
    with pytest.raises(WorkflowJobLeaseLost, match="lease"):
        store.renew(claimed.job_id, claimed.lease_token, lease_seconds=30)
    assert store.claim_next(lease_owner="worker-c", lease_seconds=30) is None


def test_duplicate_scheduling_replays_one_durable_job(store):
    scheduler = WorkflowJobScheduler(store=store)
    current = decision()

    first = scheduler.reconcile((current,))
    second = scheduler.reconcile((current,))

    assert first.jobs_created == 1
    assert first.jobs_required == 1
    assert first.jobs_materialized == 1
    assert second.jobs_created == 0
    assert second.jobs_replayed == 1
    assert second.jobs_required == 1
    assert second.jobs_materialized == 1
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

    first_generation = store.allocate_snapshot_generation()
    assert store.accept_snapshot_generation(first_generation)
    with pytest.raises(BatchInterrupted):
        with store.scheduling_batch():
            store.activate_schedule(
                project_id="project-a",
                task_id="OOMPAH-1",
                decision_revision=decision().decision_revision,
                snapshot_generation=first_generation,
            )
            raise BatchInterrupted

    assert store.schedule_cursor(
        project_id="project-a", task_id="OOMPAH-1"
    ) is None
    second_generation = store.allocate_snapshot_generation()
    assert store.accept_snapshot_generation(second_generation)
    with store.scheduling_batch():
        store.activate_schedule(
            project_id="project-a",
            task_id="OOMPAH-1",
            decision_revision=decision().decision_revision,
            snapshot_generation=second_generation,
        )
    assert store.schedule_cursor(
        project_id="project-a", task_id="OOMPAH-1"
    ).snapshot_generation == second_generation


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

    assert health["jobs"]["leases"] == {
        "running": 1,
        "expired": 1,
        "quarantined": 0,
        "oldest_quarantined_age_seconds": None,
    }
    assert health["jobs"]["schedule_cursor_count"] == 1
    assert health["jobs"]["latest_snapshot_generation"] == 1
    assert health["jobs"]["captured_snapshot_generation"] == 1
    assert health["jobs"]["accepted_snapshot_generation"] == 1
    assert health["jobs"]["published_snapshot_generation"] == 1
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
    assert result.jobs_required == 3
    assert result.jobs_materialized == 2
    assert result.schedules_required == 3
    assert result.schedules_materialized == 2
    assert [job.task_id for job in store.list_jobs()] == ["OOMPAH-1", "OOMPAH-2"]

    converged = scheduler.reconcile(
        tuple(decision(task=f"OOMPAH-{number}") for number in (3, 1, 2))
    )
    assert converged.jobs_required == 3
    assert converged.jobs_materialized == 3
    assert converged.schedules_required == 3
    assert converged.schedules_materialized == 3
    assert converged.truncated is False
    assert [job.task_id for job in store.list_jobs()] == [
        "OOMPAH-1",
        "OOMPAH-2",
        "OOMPAH-3",
    ]


def test_zero_job_semantic_cleanup_window_cannot_report_false_green(store):
    scheduler = WorkflowJobScheduler(store=store, decision_limit=2)
    decisions = tuple(
        decision(task=f"OOMPAH-{number}", jobs=())
        for number in range(3)
    )

    first = scheduler.reconcile(decisions)
    converged = scheduler.reconcile(decisions)

    assert first.jobs_required == first.jobs_materialized == 0
    assert first.schedules_required == 3
    assert first.schedules_materialized == 2
    assert converged.schedules_materialized == 3
    assert store.list_jobs() == ()


def test_explicit_zero_snapshot_generation_is_rejected(store):
    scheduler = WorkflowJobScheduler(store=store)

    with pytest.raises(ValueError, match="positive"):
        scheduler.reconcile((decision(),), snapshot_generation=0)


def test_scheduler_rejects_unbounded_parallelism(store):
    with pytest.raises(ValueError, match="cannot exceed"):
        WorkflowJobScheduler(store=store, concurrency=65)
