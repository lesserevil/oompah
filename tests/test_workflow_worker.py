from __future__ import annotations

import asyncio
import time

import pytest

from oompah.task_transition_service import (
    TransitionAuthority,
    TransitionDisposition,
    TransitionIntent,
    TransitionOutcome,
)
from oompah.workflow_jobs import (
    WorkflowFailureCategory,
    WorkflowJobSpec,
    WorkflowJobState,
    WorkflowJobStore,
)
from oompah.workflow_worker import (
    DurableWorkflowWorker,
    EffectObservation,
    EffectResult,
    RevalidationResult,
    VerificationResult,
    WorkflowActionDomain,
    WorkflowRunDisposition,
)


class Clock:
    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class ProcessDeath(BaseException):
    """An uncatchable test fault representing process termination."""


class ScriptedHandler:
    domain = WorkflowActionDomain.FORGE

    def __init__(self, *, transition: bool = False) -> None:
        self.generation = "g1"
        self.evidence_revision = "facts-g1"
        self.head_sha = "a" * 40
        self.current = True
        self.external_applied = False
        self.external_receipt = {"external_id": "effect-1"}
        self.apply_calls = 0
        self.inspect_calls = 0
        self.verify_calls = 0
        self.revalidate_calls = 0
        self.transition_calls = 0
        self.transition = transition
        self.verify_result = True
        self.verify_reason = None
        self.delay_operation: str | None = None
        self.delay_seconds = 0.0
        self.apply_error_after_effect: Exception | None = None
        self.started: asyncio.Event | None = None
        self.release: asyncio.Event | None = None

    async def _delay(self, operation: str, context) -> None:
        if self.delay_operation == operation:
            if self.started is not None:
                self.started.set()
            if self.release is not None:
                await self.release.wait()
                context.check_interrupted()
            elif self.delay_seconds:
                await asyncio.sleep(self.delay_seconds)

    async def revalidate(self, context):
        self.revalidate_calls += 1
        await self._delay("revalidate", context)
        return RevalidationResult(
            generation=self.generation,
            evidence_revision=self.evidence_revision,
            head_sha=self.head_sha,
            current=self.current,
            details={"source": "test"},
        )

    async def inspect(self, context):
        self.inspect_calls += 1
        await self._delay("inspect", context)
        return EffectObservation(
            applied=self.external_applied,
            receipt=self.external_receipt if self.external_applied else {},
        )

    async def apply(self, context):
        self.apply_calls += 1
        await self._delay("apply", context)
        self.external_applied = True
        if self.apply_error_after_effect is not None:
            error = self.apply_error_after_effect
            self.apply_error_after_effect = None
            raise error
        return EffectResult(receipt=self.external_receipt)

    async def verify(self, context, effect):
        self.verify_calls += 1
        await self._delay("verify", context)
        return VerificationResult(
            verified=self.verify_result and self.external_applied,
            receipt={"observed_external_id": effect.receipt.get("external_id")},
            reason=self.verify_reason,
        )

    async def build_transition(self, context, verification):
        self.transition_calls += 1
        await self._delay("build_transition", context)
        if not self.transition:
            return None
        return TransitionIntent(
            project_id=context.job.project_id,
            task_id=context.job.task_id,
            expected_status="Open",
            expected_version="version-1",
            requested_status="In Progress",
            actor="workflow-worker",
            authority=TransitionAuthority.WORKER,
            reason_code="transition.worker_effect_verified",
            idempotency_key=f"{context.job.idempotency_key}:transition",
            originating_job=context.job.job_id,
            evidence_generation=context.job.generation,
        )


class RecordingTransitionService:
    def __init__(self) -> None:
        self.calls = 0
        self.applied_count = 0
        self.applied = False
        self.raise_after_apply = False
        self.disposition: TransitionDisposition | None = None
        self.reason_code: str | None = None

    async def execute(self, intent: TransitionIntent) -> TransitionOutcome:
        self.calls += 1
        if self.disposition is not None:
            disposition = self.disposition
        elif self.applied:
            disposition = TransitionDisposition.ALREADY_APPLIED
        else:
            self.applied = True
            self.applied_count += 1
            if self.raise_after_apply:
                self.raise_after_apply = False
                raise RuntimeError("transport ended after transition commit")
            disposition = TransitionDisposition.APPLIED
        return TransitionOutcome(
            transition_id="transition-1",
            project_id=intent.project_id,
            task_id=intent.task_id,
            disposition=disposition,
            reason_code=self.reason_code or f"transition.{disposition.value}",
            observed_status="Open",
            observed_version="version-1",
            requested_status="In Progress",
            applied_status=(
                "In Progress"
                if disposition
                in {
                    TransitionDisposition.APPLIED,
                    TransitionDisposition.ALREADY_APPLIED,
                    TransitionDisposition.RECOVERED,
                }
                else None
            ),
            retryable=disposition is TransitionDisposition.RETRYABLE,
        )


def job_spec(
    *,
    action: str = "forge_effect",
    max_attempts: int = 3,
) -> WorkflowJobSpec:
    return WorkflowJobSpec(
        project_id="project-a",
        task_id="OOMPAH-1",
        generation="g1",
        action=action,
        idempotency_key=f"{action}:g1",
        expected_evidence_revision="facts-g1",
        expected_head_sha="a" * 40,
        max_attempts=max_attempts,
    )


def worker(
    store,
    handler,
    *,
    transition_service=None,
    phase_observer=None,
    lease_seconds: float = 30,
    heartbeat_seconds: float = 10,
    operation_timeout_seconds: float = 1,
):
    services = (
        {"project-a": transition_service} if transition_service is not None else {}
    )
    return DurableWorkflowWorker(
        store=store,
        handlers={"forge_effect": handler},
        transition_services=services,
        worker_id="worker-1",
        lease_seconds=lease_seconds,
        heartbeat_seconds=heartbeat_seconds,
        operation_timeout_seconds=operation_timeout_seconds,
        retry_delay_seconds=5,
        phase_observer=phase_observer,
    )


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def store(tmp_path, clock):
    value = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"), clock=clock)
    yield value
    value.close()


@pytest.mark.asyncio
async def test_worker_executes_effect_verifies_checkpoints_and_completes(store):
    queued = store.enqueue(job_spec())
    handler = ScriptedHandler()

    result = await worker(store, handler).run_once()

    assert result.disposition is WorkflowRunDisposition.COMPLETED
    completed = store.get(queued.job_id)
    assert completed.state is WorkflowJobState.COMPLETED
    assert completed.phase == "complete"
    assert completed.checkpoint["verification"]["observed_external_id"] == "effect-1"
    assert handler.apply_calls == 1
    assert [event.event_type for event in store.events(queued.job_id)] == [
        "enqueued",
        "claimed",
        "checkpointed",
        "checkpointed",
        "checkpointed",
        "completed",
    ]


@pytest.mark.asyncio
async def test_worker_routes_transition_and_persists_result(store):
    queued = store.enqueue(job_spec())
    handler = ScriptedHandler(transition=True)
    transitions = RecordingTransitionService()

    result = await worker(store, handler, transition_service=transitions).run_once()

    assert result.disposition is WorkflowRunDisposition.COMPLETED
    completed = store.get(queued.job_id)
    assert completed.result_transition["disposition"] == "applied"
    assert completed.checkpoint["transition"]["transition_id"] == "transition-1"
    assert transitions.applied_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("generation", "g2"),
        ("evidence_revision", "facts-g2"),
        ("head_sha", "b" * 40),
        ("current", False),
    ],
)
async def test_stale_revalidation_supersedes_without_external_effect(
    store, field, value
):
    queued = store.enqueue(job_spec())
    handler = ScriptedHandler()
    setattr(handler, field, value)

    result = await worker(store, handler).run_once()

    assert result.disposition is WorkflowRunDisposition.SUPERSEDED
    assert store.get(queued.job_id).state is WorkflowJobState.SUPERSEDED
    assert handler.inspect_calls == 0
    assert handler.apply_calls == 0


@pytest.mark.asyncio
async def test_effect_already_applied_skips_apply_and_still_verifies(store):
    store.enqueue(job_spec())
    handler = ScriptedHandler()
    handler.external_applied = True

    result = await worker(store, handler).run_once()

    assert result.disposition is WorkflowRunDisposition.COMPLETED
    assert handler.apply_calls == 0
    assert handler.verify_calls == 1


@pytest.mark.asyncio
async def test_effect_succeeded_before_error_is_recovered_without_duplication(
    store, clock
):
    queued = store.enqueue(job_spec())
    handler = ScriptedHandler()
    handler.apply_error_after_effect = RuntimeError("connection lost after create")
    runner = worker(store, handler)

    first = await runner.run_once()
    clock.advance(5)
    second = await runner.run_once()

    assert first.disposition is WorkflowRunDisposition.RETRY_SCHEDULED
    assert second.disposition is WorkflowRunDisposition.COMPLETED
    assert handler.apply_calls == 1
    assert store.get(queued.job_id).attempts == 2


@pytest.mark.asyncio
async def test_unverified_effect_retries_and_resumes_from_probe(store, clock):
    store.enqueue(job_spec())
    handler = ScriptedHandler()
    handler.verify_result = False
    handler.verify_reason = "provider has not converged"
    runner = worker(store, handler)

    first = await runner.run_once()
    handler.verify_result = True
    clock.advance(5)
    second = await runner.run_once()

    assert first.disposition is WorkflowRunDisposition.RETRY_SCHEDULED
    assert second.disposition is WorkflowRunDisposition.COMPLETED
    assert handler.apply_calls == 1
    assert handler.verify_calls == 2


@pytest.mark.asyncio
async def test_transition_applied_before_transport_error_replays_safely(store, clock):
    queued = store.enqueue(job_spec())
    handler = ScriptedHandler(transition=True)
    transitions = RecordingTransitionService()
    transitions.raise_after_apply = True
    runner = worker(store, handler, transition_service=transitions)

    first = await runner.run_once()
    clock.advance(5)
    second = await runner.run_once()

    assert first.disposition is WorkflowRunDisposition.RETRY_SCHEDULED
    assert second.disposition is WorkflowRunDisposition.COMPLETED
    assert transitions.calls == 2
    assert transitions.applied_count == 1
    assert (
        store.get(queued.job_id).result_transition["disposition"] == "already_applied"
    )


@pytest.mark.asyncio
async def test_retryable_transition_outcome_schedules_job_retry(store):
    store.enqueue(job_spec())
    handler = ScriptedHandler(transition=True)
    transitions = RecordingTransitionService()
    transitions.disposition = TransitionDisposition.RETRYABLE

    result = await worker(store, handler, transition_service=transitions).run_once()

    assert result.disposition is WorkflowRunDisposition.RETRY_SCHEDULED
    assert result.state is WorkflowJobState.RETRY_WAIT


@pytest.mark.asyncio
async def test_rejected_transition_becomes_explicit_action_required(store):
    store.enqueue(job_spec())
    handler = ScriptedHandler(transition=True)
    transitions = RecordingTransitionService()
    transitions.disposition = TransitionDisposition.REJECTED

    result = await worker(store, handler, transition_service=transitions).run_once()

    assert result.disposition is WorkflowRunDisposition.ACTION_REQUIRED
    assert result.state is WorkflowJobState.EXHAUSTED
    assert store.list_jobs()[0].failure_category is WorkflowFailureCategory.POLICY


@pytest.mark.asyncio
async def test_stale_transition_race_supersedes_for_automatic_reassessment(store):
    queued = store.enqueue(job_spec())
    handler = ScriptedHandler(transition=True)
    transitions = RecordingTransitionService()
    transitions.disposition = TransitionDisposition.REJECTED
    transitions.reason_code = "transition.stale_version"

    result = await worker(store, handler, transition_service=transitions).run_once()

    assert result.disposition is WorkflowRunDisposition.SUPERSEDED
    observed = store.get(queued.job_id)
    assert observed.state is WorkflowJobState.SUPERSEDED
    assert observed.superseded_by_generation == "reassess:g1"


@pytest.mark.asyncio
async def test_missing_handler_is_action_required_not_a_lost_job(store):
    queued = store.enqueue(job_spec(action="unregistered"))

    result = await worker(store, ScriptedHandler()).run_once()

    assert result.disposition is WorkflowRunDisposition.ACTION_REQUIRED
    assert store.get(queued.job_id).state is WorkflowJobState.EXHAUSTED


@pytest.mark.asyncio
async def test_handler_timeout_is_bounded_and_retryable(store):
    store.enqueue(job_spec())
    handler = ScriptedHandler()
    handler.delay_operation = "apply"
    handler.delay_seconds = 0.1

    result = await worker(
        store,
        handler,
        operation_timeout_seconds=0.01,
    ).run_once()

    assert result.disposition is WorkflowRunDisposition.RETRY_SCHEDULED
    failed = store.list_jobs()[0]
    assert failed.failure_category is WorkflowFailureCategory.TIMEOUT
    assert "apply exceeded" in failed.last_error


@pytest.mark.asyncio
async def test_lost_lease_fences_worker_before_post_effect_checkpoint(store, clock):
    queued = store.enqueue(job_spec())
    handler = ScriptedHandler()

    def expire_after_effect(phase, _job):
        if phase == "effect_returned":
            clock.advance(31)
            assert store.recover_expired() == 1

    result = await worker(store, handler, phase_observer=expire_after_effect).run_once()

    assert result.disposition is WorkflowRunDisposition.LEASE_LOST
    assert store.get(queued.job_id).state is WorkflowJobState.QUEUED
    assert handler.external_applied is True


@pytest.mark.asyncio
async def test_heartbeat_renews_lease_during_long_effect(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "real-clock.sqlite3"), clock=time.time)
    try:
        queued = store.enqueue(job_spec())
        handler = ScriptedHandler()
        handler.delay_operation = "apply"
        handler.delay_seconds = 0.15

        result = await worker(
            store,
            handler,
            lease_seconds=0.08,
            heartbeat_seconds=0.02,
            operation_timeout_seconds=1,
        ).run_once()

        assert result.disposition is WorkflowRunDisposition.COMPLETED
        renewals = [
            event
            for event in store.events(queued.job_id)
            if event.event_type == "renewed"
        ]
        assert len(renewals) >= 2
    finally:
        store.close()


@pytest.mark.asyncio
async def test_interrupt_is_cooperative_and_persists_retry(store):
    queued = store.enqueue(job_spec())
    handler = ScriptedHandler()
    handler.delay_operation = "apply"
    handler.started = asyncio.Event()
    handler.release = asyncio.Event()
    runner = worker(store, handler)

    invocation = asyncio.create_task(runner.run_once())
    await handler.started.wait()
    runner.interrupt()
    handler.release.set()
    result = await invocation

    assert result.disposition is WorkflowRunDisposition.RETRY_SCHEDULED
    assert store.get(queued.job_id).state is WorkflowJobState.RETRY_WAIT
    assert (await runner.run_once()).disposition is WorkflowRunDisposition.STOPPED


@pytest.mark.asyncio
async def test_graceful_drain_stops_claims_without_interrupting_active_work(store):
    store.enqueue(job_spec())
    handler = ScriptedHandler()
    handler.delay_operation = "apply"
    handler.started = asyncio.Event()
    handler.release = asyncio.Event()
    runner = worker(store, handler)

    invocation = asyncio.create_task(runner.run_once())
    await handler.started.wait()
    assert await runner.drain(timeout_seconds=0.01) is False
    handler.release.set()
    result = await invocation

    assert result.disposition is WorkflowRunDisposition.COMPLETED
    assert await runner.drain(timeout_seconds=1) is True
    assert (await runner.run_once()).disposition is WorkflowRunDisposition.STOPPED


@pytest.mark.asyncio
async def test_cancelled_invocation_schedules_restart_safe_retry(store):
    queued = store.enqueue(job_spec())
    handler = ScriptedHandler()
    handler.delay_operation = "apply"
    handler.started = asyncio.Event()
    handler.release = asyncio.Event()
    runner = worker(store, handler)

    invocation = asyncio.create_task(runner.run_once())
    await handler.started.wait()
    invocation.cancel()
    with pytest.raises(asyncio.CancelledError):
        await invocation

    assert store.get(queued.job_id).state is WorkflowJobState.RETRY_WAIT


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "crash_phase",
    [
        "leased",
        "revalidated",
        "effect_pending",
        "effect_returned",
        "verify_returned",
        "effect_verified",
        "transition_returned",
        "transition_applied",
        "completed",
    ],
)
async def test_restart_after_every_saga_boundary_is_idempotent(
    tmp_path, clock, crash_phase
):
    path = str(tmp_path / f"crash-{crash_phase}.sqlite3")
    store = WorkflowJobStore(path, clock=clock)
    queued = store.enqueue(job_spec())
    handler = ScriptedHandler(transition=True)
    transitions = RecordingTransitionService()
    crashed = False

    def kill_once(phase, _job):
        nonlocal crashed
        if phase == crash_phase and not crashed:
            crashed = True
            raise ProcessDeath(phase)

    with pytest.raises(ProcessDeath):
        await worker(
            store,
            handler,
            transition_service=transitions,
            phase_observer=kill_once,
        ).run_once()
    store.close()

    reopened = WorkflowJobStore(path, clock=clock)
    try:
        observed = reopened.get(queued.job_id)
        if observed.state is WorkflowJobState.RUNNING:
            assert reopened.recover_abandoned() == 1
            result = await worker(
                reopened,
                handler,
                transition_service=transitions,
            ).run_once()
            assert result.disposition is WorkflowRunDisposition.COMPLETED
        else:
            assert observed.state is WorkflowJobState.COMPLETED
        assert reopened.get(queued.job_id).state is WorkflowJobState.COMPLETED
        assert handler.apply_calls <= 1
        assert transitions.applied_count <= 1
        reopened.integrity_check()
    finally:
        reopened.close()


@pytest.mark.asyncio
async def test_idle_worker_does_not_create_authority(store):
    result = await worker(store, ScriptedHandler()).run_once()

    assert result.disposition is WorkflowRunDisposition.IDLE
    assert result.job_id is None


def test_worker_configuration_rejects_unbounded_or_invalid_timing(store):
    handler = ScriptedHandler()

    with pytest.raises(ValueError, match="less than"):
        worker(store, handler, lease_seconds=10, heartbeat_seconds=10)
    with pytest.raises(ValueError, match="timeout"):
        worker(store, handler, operation_timeout_seconds=0)

    handler.domain = "unknown"
    with pytest.raises(ValueError, match="known domain"):
        worker(store, handler)
