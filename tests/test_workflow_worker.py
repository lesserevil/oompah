from __future__ import annotations

import asyncio
import threading
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
    WorkflowJob,
    WorkflowJobLeaseLost,
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
    WorkflowAdministrativeDeferral,
    WorkflowActionDomain,
    WorkflowActionError,
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
        self.apply_context = None
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
                context.check_interrupted()

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
        self.apply_context = context
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


class FinalizingHandler(ScriptedHandler):
    def __init__(self) -> None:
        super().__init__(transition=True)
        self.finalized: list[TransitionOutcome] = []

    async def finalize_transition(self, _context, transition):
        self.finalized.append(transition)


class LandingFinalizingHandler(FinalizingHandler):
    def __init__(self) -> None:
        super().__init__()
        self.completion_steps: list[str] = []

    async def completion_landing_facts(self, _context, _verification):
        self.completion_steps.append("landing_evidence")
        return ()

    async def finalize_transition(self, context, transition):
        self.completion_steps.append("transition_finalizer")
        await super().finalize_transition(context, transition)


def job_spec(
    *,
    action: str = "forge_effect",
    max_attempts: int = 3,
    generation: str = "g1",
    evidence_revision: str | None = None,
    head_sha: str | None = None,
) -> WorkflowJobSpec:
    expected_evidence = evidence_revision or f"facts-{generation}"
    expected_head = head_sha or ("a" * 40 if generation == "g1" else "b" * 40)
    return WorkflowJobSpec(
        project_id="project-a",
        task_id="OOMPAH-1",
        generation=generation,
        action=action,
        idempotency_key=f"{action}:{generation}",
        expected_evidence_revision=expected_evidence,
        expected_head_sha=expected_head,
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
    retry_delay_seconds: float = 5,
    quarantine_persist_timeout_seconds: float = 5,
    quarantine_recycle_seconds: float = 60,
    quarantine_recycle_observer=None,
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
        retry_delay_seconds=retry_delay_seconds,
        quarantine_persist_timeout_seconds=quarantine_persist_timeout_seconds,
        quarantine_recycle_seconds=quarantine_recycle_seconds,
        phase_observer=phase_observer,
        quarantine_recycle_observer=quarantine_recycle_observer,
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
    assert completed.checkpoint["transition_intent"]["expected_status"] == "Open"
    assert completed.checkpoint["transition"]["transition_id"] == "transition-1"
    assert transitions.applied_count == 1


@pytest.mark.asyncio
async def test_transition_finalizer_runs_after_durable_checkpoint(store):
    queued = store.enqueue(job_spec())
    handler = FinalizingHandler()
    transitions = RecordingTransitionService()

    result = await worker(store, handler, transition_service=transitions).run_once()

    assert result.disposition is WorkflowRunDisposition.COMPLETED
    assert len(handler.finalized) == 1
    assert handler.finalized[0].disposition is TransitionDisposition.APPLIED
    assert store.get(queued.job_id).checkpoint["transition"]["disposition"] == "applied"


@pytest.mark.asyncio
async def test_completion_evidence_is_validated_before_transition_finalizer(store):
    queued = store.enqueue(job_spec())
    handler = LandingFinalizingHandler()
    transitions = RecordingTransitionService()

    result = await worker(store, handler, transition_service=transitions).run_once()

    assert result.disposition is WorkflowRunDisposition.COMPLETED
    assert handler.completion_steps == [
        "landing_evidence",
        "transition_finalizer",
    ]
    assert len(handler.finalized) == 1
    assert store.get(queued.job_id).state is WorkflowJobState.COMPLETED


@pytest.mark.asyncio
async def test_restart_replays_saved_transition_through_exact_finalizer(
    tmp_path, clock
):
    path = str(tmp_path / "finalizer-restart.sqlite3")
    store = WorkflowJobStore(path, clock=clock)
    queued = store.enqueue(job_spec())
    handler = FinalizingHandler()
    transitions = RecordingTransitionService()

    def crash_after_transition(phase, _job):
        if phase == "transition_applied":
            raise ProcessDeath(phase)

    with pytest.raises(ProcessDeath):
        await worker(
            store,
            handler,
            transition_service=transitions,
            phase_observer=crash_after_transition,
        ).run_once()
    store.close()

    reopened = WorkflowJobStore(path, clock=clock)
    try:
        assert reopened.recover_abandoned() == 1
        result = await worker(
            reopened,
            handler,
            transition_service=transitions,
        ).run_once()

        assert result.disposition is WorkflowRunDisposition.COMPLETED
        assert transitions.calls == 1
        assert len(handler.finalized) == 1
        assert handler.finalized[0].replayed is True
        assert reopened.get(queued.job_id).state is WorkflowJobState.COMPLETED
    finally:
        reopened.close()


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
async def test_same_generation_recurring_revalidation_waits_for_exact_deadline(
    store, clock
):
    generation = "g1:reassess=1100.000000"
    queued = store.enqueue(
        job_spec(
            generation=generation,
            evidence_revision="facts-g1",
            head_sha="a" * 40,
        )
    )
    handler = ScriptedHandler()
    handler.generation = generation
    handler.current = False

    result = await worker(store, handler).run_once()
    waiting = store.get(queued.job_id)

    assert result.disposition is WorkflowRunDisposition.RETRY_SCHEDULED
    assert waiting.state is WorkflowJobState.RETRY_WAIT
    assert waiting.generation == generation
    assert waiting.attempts == 0
    assert waiting.retry_at == 1100
    assert waiting.superseded_by_generation is None
    assert handler.inspect_calls == 0
    assert handler.apply_calls == 0

    clock.advance(99)
    assert (await worker(store, handler).run_once()).disposition is (
        WorkflowRunDisposition.IDLE
    )
    assert store.get(queued.job_id).state is WorkflowJobState.RETRY_WAIT


@pytest.mark.asyncio
async def test_nonrecurring_same_generation_revalidation_remains_superseded(store):
    queued = store.enqueue(job_spec())
    handler = ScriptedHandler()
    handler.current = False

    result = await worker(store, handler).run_once()

    assert result.disposition is WorkflowRunDisposition.SUPERSEDED
    assert store.get(queued.job_id).state is WorkflowJobState.SUPERSEDED


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
async def test_default_worker_does_not_claim_unregistered_action(store):
    queued = store.enqueue(job_spec(action="unregistered"))

    # Workers claim their registered action set by default so one domain
    # cannot steal another domain's rows.  An explicitly requested unknown
    # action still fails closed rather than disappearing.
    result = await worker(store, ScriptedHandler()).run_once()

    assert result.disposition is WorkflowRunDisposition.IDLE
    assert store.get(queued.job_id).state is WorkflowJobState.QUEUED


@pytest.mark.asyncio
async def test_default_worker_reserves_terminal_audit_for_its_owner(store):
    terminal = store.enqueue(job_spec(action="terminal_audit"))
    ordinary = store.enqueue(job_spec())
    handler = ScriptedHandler()

    result = await worker(store, handler).run_once()

    assert result.disposition is WorkflowRunDisposition.COMPLETED
    assert store.get(ordinary.job_id).state is WorkflowJobState.COMPLETED
    assert store.get(terminal.job_id).state is WorkflowJobState.QUEUED


@pytest.mark.asyncio
async def test_explicit_unregistered_claim_remains_fail_closed(store):
    queued = store.enqueue(job_spec(action="unregistered"))
    result = await worker(store, ScriptedHandler()).run_once(
        actions=("unregistered",)
    )

    assert result.disposition is WorkflowRunDisposition.ACTION_REQUIRED
    assert store.get(queued.job_id).state is WorkflowJobState.EXHAUSTED


@pytest.mark.asyncio
async def test_handler_timeout_is_bounded_and_durably_quarantined(store):
    store.enqueue(job_spec())
    handler = ScriptedHandler()
    handler.delay_operation = "apply"
    handler.delay_seconds = 0.1

    started = time.monotonic()
    result = await worker(
        store,
        handler,
        operation_timeout_seconds=0.01,
    ).run_once()
    elapsed = time.monotonic() - started

    assert result.disposition is WorkflowRunDisposition.ACTION_REQUIRED
    failed = store.list_jobs()[0]
    assert failed.state is WorkflowJobState.RUNNING
    assert failed.phase == "quarantined"
    assert failed.lease_expires_at is None
    assert failed.failure_category is WorkflowFailureCategory.TIMEOUT
    assert "apply exceeded" in failed.last_error
    with pytest.raises(WorkflowJobLeaseLost):
        handler.apply_context.check_interrupted()
    assert handler.external_applied is False
    assert elapsed < 0.08


@pytest.mark.asyncio
async def test_handler_can_extend_apply_bound_for_domain_safe_command(store):
    store.enqueue(job_spec())
    handler = ScriptedHandler()
    handler.delay_operation = "apply"
    handler.delay_seconds = 0.05
    handler.operation_timeout_seconds = 0.2

    result = await worker(
        store,
        handler,
        operation_timeout_seconds=0.01,
    ).run_once()

    assert result.disposition is WorkflowRunDisposition.COMPLETED


@pytest.mark.asyncio
async def test_timed_out_thread_effect_returns_without_releasing_retry_authority(store):
    store.enqueue(job_spec())
    handler = ScriptedHandler()
    mutations = []

    async def threaded_apply(context):
        handler.apply_calls += 1
        handler.apply_context = context

        def late_effect():
            time.sleep(0.08)
            context.check_interrupted()
            mutations.append("mutated")

        await asyncio.to_thread(late_effect)
        return EffectResult(receipt=handler.external_receipt)

    handler.apply = threaded_apply
    started = time.monotonic()

    result = await worker(
        store,
        handler,
        operation_timeout_seconds=0.01,
    ).run_once()

    assert result.disposition is WorkflowRunDisposition.ACTION_REQUIRED
    assert time.monotonic() - started < 0.07
    quarantined = store.list_jobs()[0]
    assert quarantined.state is WorkflowJobState.RUNNING
    assert quarantined.phase == "quarantined"
    assert quarantined.lease_expires_at is None
    assert mutations == []
    replacement = worker(store, ScriptedHandler())
    assert (await replacement.run_once()).disposition is WorkflowRunDisposition.IDLE
    await asyncio.sleep(0.1)
    assert mutations == []
    assert (await replacement.run_once()).disposition is WorkflowRunDisposition.IDLE


@pytest.mark.asyncio
async def test_late_success_checkpoints_receipt_without_duplicate_apply(
    store, monkeypatch
):
    queued = store.enqueue(job_spec())
    handler = ScriptedHandler()
    handler.started = asyncio.Event()
    handler.release = asyncio.Event()
    quarantine_started = threading.Event()
    release_quarantine = threading.Event()
    quarantine_owned = store.quarantine_owned

    def delayed_quarantine(*args, **kwargs):
        quarantine_started.set()
        assert release_quarantine.wait(timeout=2)
        return quarantine_owned(*args, **kwargs)

    monkeypatch.setattr(store, "quarantine_owned", delayed_quarantine)

    async def late_apply(_context):
        handler.apply_calls += 1
        handler.started.set()
        await handler.release.wait()
        handler.external_applied = True
        return EffectResult(receipt=handler.external_receipt)

    handler.apply = late_apply
    runner = worker(
        store,
        handler,
        operation_timeout_seconds=0.01,
        quarantine_persist_timeout_seconds=1,
    )

    timed_out_call = asyncio.create_task(runner.run_once())
    await handler.started.wait()
    assert await asyncio.to_thread(quarantine_started.wait, 0.5)
    # The store barrier, rather than scheduler luck, keeps quarantine
    # persistence beyond the adapter's 10ms execution budget.  Its independent
    # authority deadline must still allow the exact lease fence to commit.
    await asyncio.sleep(0.15)
    assert not timed_out_call.done()
    release_quarantine.set()
    timed_out = await timed_out_call

    assert timed_out.disposition is WorkflowRunDisposition.ACTION_REQUIRED
    assert store.get(queued.job_id).phase == "quarantined"
    assert (await worker(store, ScriptedHandler()).run_once()).disposition is (
        WorkflowRunDisposition.IDLE
    )

    handler.release.set()
    async with asyncio.timeout(0.5):
        while store.get(queued.job_id).phase != "effect_returned":
            await asyncio.sleep(0.005)

    recovered = store.get(queued.job_id)
    assert recovered.state is WorkflowJobState.QUEUED
    assert recovered.attempts == 0
    assert recovered.checkpoint["effect"] == handler.external_receipt

    resumed = await runner.run_once()
    assert resumed.disposition is WorkflowRunDisposition.COMPLETED
    assert handler.apply_calls == 1


@pytest.mark.asyncio
async def test_true_lease_loss_during_quarantine_remains_lease_lost(
    store, monkeypatch
):
    store.enqueue(job_spec())
    handler = ScriptedHandler()
    handler.delay_operation = "apply"
    handler.delay_seconds = 0.1

    def lose_lease(*_args, **_kwargs):
        raise WorkflowJobLeaseLost("replaced before quarantine")

    monkeypatch.setattr(store, "quarantine_owned", lose_lease)

    result = await worker(
        store,
        handler,
        operation_timeout_seconds=0.01,
        quarantine_persist_timeout_seconds=1,
    ).run_once()

    assert result.disposition is WorkflowRunDisposition.LEASE_LOST
    assert "WorkflowJobLeaseLost" in result.reason


@pytest.mark.asyncio
async def test_late_failure_terminalizes_before_same_task_replacement(store):
    original = store.enqueue(job_spec(max_attempts=1))
    replacement = store.enqueue(job_spec(generation="g2"))
    handler = ScriptedHandler()
    handler.started = asyncio.Event()
    handler.release = asyncio.Event()

    async def late_failure(_context):
        handler.apply_calls += 1
        handler.started.set()
        await handler.release.wait()
        raise RuntimeError("late transport failure")

    handler.apply = late_failure
    runner = worker(store, handler, operation_timeout_seconds=0.01)

    timed_out = await runner.run_once()
    await handler.started.wait()
    assert timed_out.disposition is WorkflowRunDisposition.ACTION_REQUIRED
    assert (await runner.run_once()).disposition is WorkflowRunDisposition.IDLE
    assert store.get(replacement.job_id).state is WorkflowJobState.QUEUED

    handler.release.set()
    async with asyncio.timeout(0.5):
        while store.get(original.job_id).state is WorkflowJobState.RUNNING:
            await asyncio.sleep(0.005)

    failed = store.get(original.job_id)
    assert failed.state is WorkflowJobState.EXHAUSTED
    assert failed.attempts == 1
    handler.generation = "g2"
    handler.evidence_revision = "facts-g2"
    handler.head_sha = "b" * 40
    handler.apply = ScriptedHandler.apply.__get__(handler, ScriptedHandler)

    flowed = await runner.run_once()
    assert flowed.disposition is WorkflowRunDisposition.COMPLETED
    assert store.get(replacement.job_id).state is WorkflowJobState.COMPLETED
    assert handler.apply_calls == 2


@pytest.mark.asyncio
async def test_permanently_blocked_call_requests_one_bounded_recycle(store):
    queued = store.enqueue(job_spec())
    handler = ScriptedHandler()
    handler.started = asyncio.Event()
    handler.release = asyncio.Event()
    requested = asyncio.Event()
    recycle_calls = []

    async def blocked_apply(_context):
        handler.apply_calls += 1
        handler.started.set()
        await handler.release.wait()
        handler.external_applied = True
        return EffectResult(receipt=handler.external_receipt)

    async def request_recycle(job):
        recycle_calls.append(job.job_id)
        requested.set()

    handler.apply = blocked_apply
    runner = worker(
        store,
        handler,
        operation_timeout_seconds=0.01,
        quarantine_recycle_seconds=0.02,
        quarantine_recycle_observer=request_recycle,
    )

    timed_out = await runner.run_once()
    await handler.started.wait()
    assert timed_out.disposition is WorkflowRunDisposition.ACTION_REQUIRED
    await asyncio.wait_for(requested.wait(), timeout=0.5)

    quarantined = store.get(queued.job_id)
    marker = quarantined.checkpoint["quarantine_recycle"]
    assert marker["lease_token"] == quarantined.lease_token
    assert marker["lease_owner"] == quarantined.lease_owner
    assert recycle_calls == [queued.job_id]
    for _ in range(3):
        assert (await runner.run_once()).disposition is WorkflowRunDisposition.IDLE
    await asyncio.sleep(0.05)
    assert recycle_calls == [queued.job_id]

    handler.release.set()
    async with asyncio.timeout(0.5):
        while store.get(queued.job_id).phase != "effect_returned":
            await asyncio.sleep(0.005)
    assert (await runner.run_once()).disposition is WorkflowRunDisposition.COMPLETED
    assert handler.apply_calls == 1


@pytest.mark.asyncio
async def test_completed_call_settlement_store_failure_requests_safe_recycle(
    store,
    monkeypatch,
):
    queued = store.enqueue(job_spec())
    handler = ScriptedHandler()
    handler.started = asyncio.Event()
    handler.release = asyncio.Event()
    requested = asyncio.Event()
    recycle_calls = []

    async def late_apply(_context):
        handler.apply_calls += 1
        handler.started.set()
        await handler.release.wait()
        handler.external_applied = True
        return EffectResult(receipt=handler.external_receipt)

    async def request_recycle(job):
        recycle_calls.append(job.job_id)
        requested.set()

    handler.apply = late_apply
    original_settle = store.settle_quarantined_call
    settlement_calls = 0

    def unavailable_settlement(*args, **kwargs):
        nonlocal settlement_calls
        settlement_calls += 1
        raise OSError("transient SQLite transport failure")

    runner = worker(
        store,
        handler,
        operation_timeout_seconds=0.01,
        quarantine_recycle_seconds=0.05,
        quarantine_recycle_observer=request_recycle,
    )
    timed_out = await runner.run_once()
    await handler.started.wait()
    assert timed_out.disposition is WorkflowRunDisposition.ACTION_REQUIRED
    monkeypatch.setattr(store, "settle_quarantined_call", unavailable_settlement)
    assert runner.quarantine_monitor_count == 2

    handler.release.set()
    while runner.quarantine_monitor_count:
        await asyncio.sleep(0)

    retained = store.get(queued.job_id)
    assert requested.is_set()
    assert settlement_calls == 1
    assert retained.state is WorkflowJobState.RUNNING
    assert retained.phase == "quarantined"
    assert retained.checkpoint["quarantine_recycle"]["lease_token"] == (
        retained.lease_token
    )
    assert recycle_calls == [queued.job_id]

    monkeypatch.setattr(store, "settle_quarantined_call", original_settle)
    recovered = original_settle(
        retained.job_id,
        retained.lease_token,
        operation="apply",
        effect_receipt=handler.external_receipt,
    )
    assert recovered.phase == "effect_returned"
    assert "quarantine_recycle" not in recovered.checkpoint


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
async def test_heartbeat_renews_lease_during_long_effect(store, clock, monkeypatch):
    queued = store.enqueue(job_spec())
    handler = ScriptedHandler()
    handler.delay_operation = "apply"
    handler.started = asyncio.Event()
    handler.release = asyncio.Event()
    renewals_observed = asyncio.Event()
    event_loop = asyncio.get_running_loop()
    original_renew = store.renew
    renewal_count = 0
    renewal_tokens: list[str] = []
    initial_lease_expires_at: float | None = None
    renewal_lock = threading.Lock()

    def observed_renew(
        job_id: str,
        lease_token: str,
        *,
        lease_seconds: float,
        now: float | None = None,
    ) -> WorkflowJob:
        nonlocal initial_lease_expires_at, renewal_count
        with renewal_lock:
            if initial_lease_expires_at is None:
                initial_lease_expires_at = store.get(job_id).lease_expires_at
        clock.advance(0.05)
        renewed = original_renew(
            job_id,
            lease_token,
            lease_seconds=lease_seconds,
            now=now,
        )
        with renewal_lock:
            renewal_count += 1
            renewal_tokens.append(lease_token)
            if renewal_count >= 2:
                event_loop.call_soon_threadsafe(renewals_observed.set)
        return renewed

    monkeypatch.setattr(store, "renew", observed_renew)

    invocation = asyncio.create_task(
        worker(
            store,
            handler,
            lease_seconds=0.08,
            heartbeat_seconds=0.01,
            operation_timeout_seconds=1,
        ).run_once()
    )
    try:
        await asyncio.wait_for(handler.started.wait(), timeout=1)
        await asyncio.wait_for(renewals_observed.wait(), timeout=1)

        assert invocation.done() is False
        assert handler.external_applied is False
        leased = store.get(queued.job_id)
        assert leased.lease_token is not None
        assert store.owns_live_lease(leased.job_id, leased.lease_token) is True
        with renewal_lock:
            observed_tokens = tuple(renewal_tokens)
            observed_initial_expiry = initial_lease_expires_at
        assert observed_initial_expiry is not None
        assert clock.now > observed_initial_expiry
        assert len(observed_tokens) >= 2
        assert set(observed_tokens) == {leased.lease_token}
    finally:
        handler.release.set()
        result = await asyncio.wait_for(invocation, timeout=1)

    assert result.disposition is WorkflowRunDisposition.COMPLETED
    assert handler.apply_calls == 1
    renewals = [
        event
        for event in store.events(queued.job_id)
        if event.event_type == "renewed"
    ]
    assert len(renewals) >= 2


@pytest.mark.asyncio
async def test_heartbeat_transport_error_fails_closed_before_effect_commit(
    store, monkeypatch
):
    queued = store.enqueue(job_spec())
    handler = ScriptedHandler()
    handler.delay_operation = "apply"
    handler.delay_seconds = 0.05

    def broken_renew(*_args, **_kwargs):
        raise OSError("simulated SQLite transport failure")

    monkeypatch.setattr(store, "renew", broken_renew)
    result = await worker(
        store,
        handler,
        lease_seconds=1,
        heartbeat_seconds=0.01,
        operation_timeout_seconds=1,
    ).run_once()

    assert result.disposition is WorkflowRunDisposition.LEASE_LOST
    assert store.get(queued.job_id).state is WorkflowJobState.RUNNING
    assert handler.external_applied is False


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
async def test_pre_effect_lifecycle_drain_does_not_consume_attempt_after_restart(
    store, clock
):
    queued = store.enqueue(job_spec(max_attempts=1))
    handler = ScriptedHandler()
    handler.delay_operation = "revalidate"
    handler.started = asyncio.Event()
    handler.release = asyncio.Event()
    draining_worker = worker(store, handler)

    invocation = asyncio.create_task(draining_worker.run_once())
    await handler.started.wait()
    draining_worker.interrupt()
    handler.release.set()
    deferred = await invocation

    assert deferred.disposition is WorkflowRunDisposition.RETRY_SCHEDULED
    waiting = store.get(queued.job_id)
    assert waiting.state is WorkflowJobState.RETRY_WAIT
    assert waiting.attempts == 0
    assert store.events(queued.job_id)[-1].event_type == "administrative_deferred"

    clock.advance(5)
    resumed = await worker(store, ScriptedHandler()).run_once()

    assert resumed.disposition is WorkflowRunDisposition.COMPLETED
    assert store.get(queued.job_id).attempts == 1


@pytest.mark.asyncio
async def test_administrative_cycles_beyond_max_attempts_resume_with_backoff(
    store, clock
):
    queued = store.enqueue(job_spec(max_attempts=2))
    handler = ScriptedHandler()
    original_revalidate = handler.revalidate
    remaining_deferrals = 5

    async def administratively_deferred(context):
        nonlocal remaining_deferrals
        if remaining_deferrals:
            remaining_deferrals -= 1
            raise WorkflowAdministrativeDeferral("resource admission deferred")
        return await original_revalidate(context)

    handler.revalidate = administratively_deferred
    runner = worker(store, handler)
    observed_delays = []

    for _ in range(5):
        result = await runner.run_once()
        waiting = store.get(queued.job_id)
        assert result.disposition is WorkflowRunDisposition.RETRY_SCHEDULED
        assert waiting.state is WorkflowJobState.RETRY_WAIT
        assert waiting.attempts == 0
        observed_delays.append(waiting.retry_at - clock.now)
        clock.advance(waiting.retry_at - clock.now)

    completed = await runner.run_once()

    assert observed_delays == [5, 10, 20, 40, 80]
    assert completed.disposition is WorkflowRunDisposition.COMPLETED
    assert store.get(queued.job_id).attempts == 1


@pytest.mark.asyncio
async def test_proven_apply_admission_deferral_preserves_exact_checkpoint(
    store, clock
):
    queued = store.enqueue(job_spec(max_attempts=1))
    handler = ScriptedHandler()
    original_apply = handler.apply
    blocked = True

    async def guarded_apply(context):
        nonlocal blocked
        if blocked:
            blocked = False
            raise WorkflowAdministrativeDeferral(
                "project paused at effect admission",
                effect_not_started=True,
            )
        return await original_apply(context)

    handler.apply = guarded_apply
    runner = worker(store, handler)

    deferred = await runner.run_once()
    waiting = store.get(queued.job_id)

    assert deferred.disposition is WorkflowRunDisposition.RETRY_SCHEDULED
    assert waiting.attempts == 0
    assert waiting.phase == "effect_pending"
    assert waiting.checkpoint == {
        "effect_observed": False,
        "revalidation": {
            "details": {"source": "test"},
            "evidence_revision": "facts-g1",
            "generation": "g1",
            "head_sha": "a" * 40,
        },
    }

    clock.advance(5)
    completed = await runner.run_once()
    assert completed.disposition is WorkflowRunDisposition.COMPLETED
    assert store.get(queued.job_id).attempts == 1


@pytest.mark.asyncio
async def test_genuine_pre_effect_failures_still_increment_and_exhaust(store, clock):
    queued = store.enqueue(job_spec(max_attempts=2))
    handler = ScriptedHandler()

    async def unavailable(_context):
        raise WorkflowActionError(
            "provider transport failed",
            category=WorkflowFailureCategory.TRANSPORT,
            retryable=True,
        )

    handler.revalidate = unavailable
    runner = worker(store, handler)

    first = await runner.run_once()
    clock.advance(5)
    second = await runner.run_once()

    assert first.disposition is WorkflowRunDisposition.RETRY_SCHEDULED
    assert second.disposition is WorkflowRunDisposition.ACTION_REQUIRED
    exhausted = store.get(queued.job_id)
    assert exhausted.state is WorkflowJobState.EXHAUSTED
    assert exhausted.attempts == 2
    assert exhausted.failure_category is WorkflowFailureCategory.TRANSPORT


@pytest.mark.asyncio
async def test_uncertain_post_effect_deferral_is_not_given_free_attempt(store):
    queued = store.enqueue(job_spec(max_attempts=1))
    handler = ScriptedHandler()

    async def effect_then_defer(_context):
        handler.apply_calls += 1
        handler.external_applied = True
        raise WorkflowAdministrativeDeferral("pause raced with effect return")

    handler.apply = effect_then_defer

    result = await worker(store, handler).run_once()

    assert result.disposition is WorkflowRunDisposition.ACTION_REQUIRED
    exhausted = store.get(queued.job_id)
    assert exhausted.state is WorkflowJobState.EXHAUSTED
    assert exhausted.attempts == 1
    assert exhausted.failure_category is WorkflowFailureCategory.TRANSIENT
    assert [event.event_type for event in store.events(queued.job_id)][-1] == (
        "exhausted"
    )


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
async def test_cancelled_invocation_quarantines_late_effect_authority(store):
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

    observed = store.get(queued.job_id)
    assert observed.state is WorkflowJobState.RUNNING
    assert observed.phase == "quarantined"
    assert observed.lease_expires_at is None


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
        "transition_intent",
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
    with pytest.raises(ValueError, match="quarantine_persist_timeout_seconds"):
        worker(store, handler, quarantine_persist_timeout_seconds=0)
    for nonfinite in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError, match="finite and positive"):
            worker(
                store,
                handler,
                quarantine_persist_timeout_seconds=nonfinite,
            )

    handler.domain = "unknown"
    with pytest.raises(ValueError, match="known domain"):
        worker(store, handler)
