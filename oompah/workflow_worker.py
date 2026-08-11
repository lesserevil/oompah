"""Resumable worker for durable workflow jobs.

The worker owns orchestration, not domain behavior.  Domain handlers revalidate
facts and implement idempotent external effects; the worker supplies durable
leases, bounded calls, restart checkpoints, transition-service routing, and
late-worker fencing.
"""

from __future__ import annotations

import asyncio
import inspect
import math
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

from oompah.task_transition_service import (
    TaskTransitionService,
    TransitionDisposition,
    TransitionIntent,
    TransitionOutcome,
)
from oompah.workflow_jobs import (
    WorkflowFailureCategory,
    WorkflowJob,
    WorkflowJobLeaseLost,
    WorkflowJobState,
    WorkflowJobStore,
)


class WorkflowActionDomain(str, Enum):
    TRACKER = "tracker"
    GIT = "git"
    FORGE = "forge"
    AUDIT = "audit"


class WorkflowRunDisposition(str, Enum):
    IDLE = "idle"
    COMPLETED = "completed"
    RETRY_SCHEDULED = "retry_scheduled"
    SUPERSEDED = "superseded"
    ACTION_REQUIRED = "action_required"
    LEASE_LOST = "lease_lost"
    STOPPED = "stopped"


@dataclass(frozen=True, slots=True)
class RevalidationResult:
    """Fresh authority observed immediately before an external effect."""

    generation: str
    evidence_revision: str | None = None
    head_sha: str | None = None
    current: bool = True
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.generation or "").strip():
            raise ValueError("revalidation generation is required")


@dataclass(frozen=True, slots=True)
class EffectObservation:
    """Idempotency probe made before applying an external effect."""

    applied: bool
    receipt: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EffectResult:
    """Receipt returned by an idempotent external-effect call."""

    receipt: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """Durable proof that the intended external effect is observable."""

    verified: bool
    receipt: Mapping[str, Any] = field(default_factory=dict)
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class WorkflowRunResult:
    disposition: WorkflowRunDisposition
    job_id: str | None
    state: WorkflowJobState | None
    reason: str
    attempts: int = 0


class WorkflowActionError(RuntimeError):
    """Typed domain failure that the worker can route safely."""

    def __init__(
        self,
        message: str,
        *,
        category: WorkflowFailureCategory | str = WorkflowFailureCategory.UNKNOWN,
        retryable: bool = True,
        retry_delay_seconds: float | None = None,
    ) -> None:
        super().__init__(message)
        self.category = WorkflowFailureCategory(category)
        self.retryable = bool(retryable)
        if retry_delay_seconds is not None and retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds cannot be negative")
        self.retry_delay_seconds = (
            float(retry_delay_seconds) if retry_delay_seconds is not None else None
        )


class WorkflowActionTimedOut(WorkflowActionError):
    def __init__(
        self,
        operation: str,
        timeout_seconds: float,
        *,
        detached_call: asyncio.Future[Any] | None = None,
    ) -> None:
        super().__init__(
            f"{operation} exceeded {timeout_seconds:g}s timeout",
            category=WorkflowFailureCategory.TIMEOUT,
            retryable=True,
        )
        self.operation = str(operation)
        self.detached_call = detached_call


class WorkflowActionInterrupted(WorkflowActionError):
    def __init__(self) -> None:
        super().__init__(
            "workflow action interrupted before the next persistence boundary",
            category=WorkflowFailureCategory.TRANSIENT,
            retryable=True,
        )


class WorkflowAdministrativeDeferral(WorkflowActionError):
    """Non-failure admission deferral before an external effect starts.

    ``effect_not_started`` is reserved for an admission boundary which can
    prove it rejected the operation before delegating to the effect handler.
    The worker still refuses to restore the attempt after a durable effect
    receipt exists.
    """

    def __init__(
        self,
        message: str,
        *,
        retry_delay_seconds: float | None = None,
        effect_not_started: bool = False,
    ) -> None:
        super().__init__(
            message,
            category=WorkflowFailureCategory.TRANSIENT,
            retryable=True,
            retry_delay_seconds=retry_delay_seconds,
        )
        self.effect_not_started = bool(effect_not_started)


class WorkflowActionSuperseded(WorkflowActionError):
    """Signal that fresh domain evidence terminally fenced this action."""

    def __init__(self, message: str, *, replacement_generation: str) -> None:
        super().__init__(
            message,
            category=WorkflowFailureCategory.STALE_EVIDENCE,
            retryable=False,
        )
        self.replacement_generation = str(replacement_generation or "").strip()
        if not self.replacement_generation:
            raise ValueError("replacement_generation is required")


@dataclass(slots=True)
class WorkflowJobContext:
    """Lease-aware context passed to domain handlers."""

    job: WorkflowJob
    _lease_lost: asyncio.Event
    _interrupted: asyncio.Event
    _lease_validator: Callable[[], bool] | None = None

    @property
    def idempotency_key(self) -> str:
        return self.job.idempotency_key

    def check_interrupted(self) -> None:
        if self._lease_validator is not None:
            try:
                lease_is_live = bool(self._lease_validator())
            except Exception:
                # A lease read is an authority boundary, not an availability
                # hint.  If SQLite (or an adapter around it) cannot prove the
                # exact token is still current, fail closed before another
                # external-effect or persistence boundary.
                lease_is_live = False
            if not lease_is_live:
                self._lease_lost.set()
        if self._lease_lost.is_set():
            raise WorkflowJobLeaseLost(
                f"workflow job lease was lost: {self.job.job_id}"
            )
        if self._interrupted.is_set():
            raise WorkflowActionInterrupted()

    def fence_external_effects(self) -> None:
        """Withdraw late-effect authority before abandoning an invocation."""

        self._lease_lost.set()


class WorkflowActionHandler(Protocol):
    """Idempotent tracker/Git/forge/audit action contract."""

    domain: WorkflowActionDomain

    async def revalidate(self, context: WorkflowJobContext) -> RevalidationResult: ...

    async def inspect(self, context: WorkflowJobContext) -> EffectObservation: ...

    async def apply(self, context: WorkflowJobContext) -> EffectResult: ...

    async def verify(
        self,
        context: WorkflowJobContext,
        effect: EffectResult,
    ) -> VerificationResult: ...

    async def build_transition(
        self,
        context: WorkflowJobContext,
        verification: VerificationResult,
    ) -> TransitionIntent | None: ...


class TransitionExecutor(Protocol):
    async def execute(self, intent: TransitionIntent) -> TransitionOutcome: ...


PhaseObserver = Callable[[str, WorkflowJob], object | Awaitable[object]]
QuarantineRecycleObserver = Callable[
    [WorkflowJob], object | Awaitable[object]
]


class DurableWorkflowWorker:
    """Claim and resume one durable workflow saga at a time per invocation."""

    _SUCCESSFUL_TRANSITIONS = frozenset(
        {
            TransitionDisposition.APPLIED,
            TransitionDisposition.ALREADY_APPLIED,
            TransitionDisposition.STAGED,
            TransitionDisposition.RECOVERED,
        }
    )
    _STALE_TRANSITION_REASONS = frozenset(
        {
            "transition.stale_status",
            "transition.stale_version",
            "transition.generation_mismatch",
            "transition.head_missing",
            "transition.head_mismatch",
            "transition.stale_precondition",
            "transition.owner_retirement_generation_mismatch",
        }
    )

    def __init__(
        self,
        *,
        store: WorkflowJobStore,
        handlers: Mapping[str, WorkflowActionHandler],
        transition_services: Mapping[str, TransitionExecutor | TaskTransitionService],
        worker_id: str,
        lease_seconds: float = 30,
        heartbeat_seconds: float = 10,
        operation_timeout_seconds: float = 60,
        retry_delay_seconds: float = 5,
        quarantine_persist_timeout_seconds: float = 5,
        quarantine_recycle_seconds: float = 60,
        phase_observer: PhaseObserver | None = None,
        quarantine_recycle_observer: QuarantineRecycleObserver | None = None,
    ) -> None:
        self.store = store
        self.handlers = {
            str(action).strip(): handler for action, handler in handlers.items()
        }
        if not self.handlers or any(not action for action in self.handlers):
            raise ValueError("at least one named workflow action handler is required")
        for handler in self.handlers.values():
            try:
                WorkflowActionDomain(handler.domain)
            except (AttributeError, ValueError) as exc:
                raise ValueError(
                    "every workflow action handler must declare a known domain"
                ) from exc
        self.transition_services = {
            str(project).strip(): service
            for project, service in transition_services.items()
        }
        if any(not project for project in self.transition_services):
            raise ValueError("transition service project ids cannot be empty")
        self.worker_id = str(worker_id or "").strip()
        if not self.worker_id:
            raise ValueError("worker_id is required")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        if heartbeat_seconds <= 0 or heartbeat_seconds >= lease_seconds:
            raise ValueError(
                "heartbeat_seconds must be positive and less than lease_seconds"
            )
        if operation_timeout_seconds <= 0:
            raise ValueError("operation_timeout_seconds must be positive")
        if retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds cannot be negative")
        quarantine_persist_timeout = float(quarantine_persist_timeout_seconds)
        if (
            not math.isfinite(quarantine_persist_timeout)
            or quarantine_persist_timeout <= 0
        ):
            raise ValueError(
                "quarantine_persist_timeout_seconds must be finite and positive"
            )
        if quarantine_recycle_seconds <= 0:
            raise ValueError("quarantine_recycle_seconds must be positive")
        self.lease_seconds = float(lease_seconds)
        self.heartbeat_seconds = float(heartbeat_seconds)
        self.operation_timeout_seconds = float(operation_timeout_seconds)
        self.retry_delay_seconds = float(retry_delay_seconds)
        self.quarantine_persist_timeout_seconds = quarantine_persist_timeout
        self.quarantine_recycle_seconds = float(quarantine_recycle_seconds)
        self.phase_observer = phase_observer
        self.quarantine_recycle_observer = quarantine_recycle_observer
        self._accepting = True
        self._interrupted = asyncio.Event()
        self._active: set[asyncio.Task[Any]] = set()
        self._quarantined_calls: set[asyncio.Future[Any]] = set()
        self._quarantine_monitors: set[asyncio.Task[Any]] = set()

    @property
    def accepting(self) -> bool:
        return self._accepting

    @property
    def active_count(self) -> int:
        return len(self._active)

    @property
    def quarantined_call_count(self) -> int:
        return sum(not call.done() for call in self._quarantined_calls)

    @property
    def quarantine_monitor_count(self) -> int:
        return sum(not monitor.done() for monitor in self._quarantine_monitors)

    def interrupt(self) -> None:
        """Request cooperative interruption at the next safe boundary."""

        self._accepting = False
        self._interrupted.set()

    async def drain(self, *, timeout_seconds: float | None = None) -> bool:
        """Stop new claims and wait for current invocations without cancelling them."""

        self._accepting = False
        active = tuple(task for task in self._active if not task.done())
        if not active:
            return True
        waiter = asyncio.gather(*active, return_exceptions=True)
        try:
            if timeout_seconds is None:
                await waiter
            else:
                if timeout_seconds <= 0:
                    raise ValueError("timeout_seconds must be positive")
                await asyncio.wait_for(asyncio.shield(waiter), timeout_seconds)
        except TimeoutError:
            return False
        return True

    async def _notify(self, phase: str, job: WorkflowJob) -> None:
        if self.phase_observer is None:
            return
        result = self.phase_observer(phase, job)
        if inspect.isawaitable(result):
            await result

    async def _bounded(
        self,
        operation: str,
        call: Awaitable[Any],
        *,
        timeout_seconds: float | None = None,
        timeout_fence: Callable[[], None] | None = None,
    ) -> Any:
        timeout = (
            self.operation_timeout_seconds
            if timeout_seconds is None
            else float(timeout_seconds)
        )
        task = asyncio.ensure_future(call)
        try:
            done, _pending = await asyncio.wait({task}, timeout=timeout)
            if done:
                return await task
            if timeout_fence is not None:
                timeout_fence()
            # Cancelling a to_thread awaiter cannot terminate its underlying
            # thread. Detach the now-authority-fenced awaiter and let the caller
            # durably quarantine the exact lease rather than blocking forever.
            self._detach_quarantined_call(task)
            raise WorkflowActionTimedOut(
                operation,
                timeout,
                detached_call=task,
            )
        except asyncio.CancelledError:
            if timeout_fence is not None:
                timeout_fence()
            self._detach_quarantined_call(task)
            raise

    def _detach_quarantined_call(self, task: asyncio.Future[Any]) -> None:
        self._quarantined_calls.add(task)

        def _consume(completed: asyncio.Future[Any]) -> None:
            self._quarantined_calls.discard(completed)
            if completed.cancelled():
                return
            try:
                completed.exception()
            except BaseException:
                pass

        task.add_done_callback(_consume)

    def _track_quarantine_monitor(self, monitor: asyncio.Task[Any]) -> None:
        self._quarantine_monitors.add(monitor)
        monitor.add_done_callback(self._quarantine_monitors.discard)

    def _monitor_quarantined_call(
        self,
        context: WorkflowJobContext,
        failure: WorkflowActionTimedOut,
    ) -> None:
        """Settle one exact quarantine when its detached awaiter really ends."""

        call = failure.detached_call
        if call is None:
            return
        job_id = context.job.job_id
        lease_token = str(context.job.lease_token or "")
        operation = failure.operation
        settled = asyncio.Event()

        async def recover() -> None:
            effect_receipt: Mapping[str, Any] | None = None
            error: str | None = None
            category = WorkflowFailureCategory.UNKNOWN
            retryable = True
            try:
                value = await asyncio.shield(call)
                if operation == "apply":
                    if isinstance(value, EffectResult):
                        effect_receipt = dict(value.receipt)
                    else:
                        category = WorkflowFailureCategory.PERMANENT
                        retryable = False
                        error = "late apply returned an invalid effect result"
            except asyncio.CancelledError:
                # Loop/process shutdown leaves the durable quarantine for the
                # startup dead-owner recovery path.  Never manufacture a call
                # outcome merely because its monitor was cancelled.
                return
            except Exception as exc:  # noqa: BLE001 - detached adapter boundary
                if isinstance(exc, WorkflowActionError):
                    category = exc.category
                    retryable = exc.retryable
                error = f"late {operation} failed: {type(exc).__name__}"
            try:
                recovered = await asyncio.to_thread(
                    self.store.settle_quarantined_call,
                    job_id,
                    lease_token,
                    operation=operation,
                    effect_receipt=effect_receipt,
                    failure_category=category,
                    error=error,
                    retryable=retryable,
                    retry_delay_seconds=self.retry_delay_seconds,
                )
            except WorkflowJobLeaseLost:
                settled.set()
                return
            except Exception:
                # The immutable quarantine remains the safe fallback.  Its
                # health row and bounded recycle request stay visible.
                return
            settled.set()
            await self._notify("quarantine_settled", recovered)

        async def request_recycle() -> None:
            try:
                await asyncio.wait_for(
                    settled.wait(),
                    timeout=self.quarantine_recycle_seconds,
                )
                return
            except TimeoutError:
                pass
            # A completed adapter is not sufficient proof that its durable
            # settlement committed.  If that store write failed, retain the
            # exact quarantine and cross the same bounded recycle boundary as
            # a call which never returned; startup recovery can then inspect
            # the external effect without overlap.
            try:
                current = await asyncio.to_thread(self.store.get, job_id)
            except Exception:
                return
            if (
                current.state is not WorkflowJobState.RUNNING
                or current.phase != "quarantined"
                or str(current.lease_token or "") != lease_token
            ):
                return
            try:
                current = await asyncio.to_thread(
                    self.store.mark_quarantine_recycle_requested,
                    job_id,
                    lease_token,
                )
            except Exception:
                return
            await self._notify("quarantine_recycle_requested", current)
            observer = self.quarantine_recycle_observer
            if observer is None:
                return
            handler = self.handlers.get(current.action)
            prepare = getattr(handler, "prepare_quarantine_recycle", None)
            if callable(prepare):
                try:
                    prepared = prepare(current)
                    if inspect.isawaitable(prepared):
                        await prepared
                except Exception:
                    return
            try:
                result = observer(current)
                if inspect.isawaitable(result):
                    await result
            except Exception:
                # The durable quarantine remains operator-visible and a later
                # controller pass may coalesce another service-level request.
                return

        self._track_quarantine_monitor(
            asyncio.create_task(
                recover(),
                name=f"workflow-quarantine-settle:{job_id}",
            )
        )
        self._track_quarantine_monitor(
            asyncio.create_task(
                request_recycle(),
                name=f"workflow-quarantine-recycle:{job_id}",
            )
        )

    async def _checkpoint(
        self,
        context: WorkflowJobContext,
        *,
        phase: str,
        checkpoint: Mapping[str, Any],
    ) -> None:
        context.check_interrupted()
        context.job = await asyncio.to_thread(
            self.store.checkpoint,
            context.job.job_id,
            context.job.lease_token,
            phase=phase,
            checkpoint=checkpoint,
        )
        await self._notify(phase, context.job)

    async def _compensate_transition_failure(
        self,
        handler: WorkflowActionHandler,
        context: WorkflowJobContext,
        failure: TransitionOutcome | WorkflowActionError,
        *,
        checkpoint: Mapping[str, Any],
    ) -> None:
        compensate = getattr(handler, "compensate_transition_failure", None)
        if not callable(compensate):
            return
        result = await self._bounded(
            "compensate_transition_failure",
            compensate(context, failure),
        )
        if result is None:
            return
        if not isinstance(result, Mapping):
            raise WorkflowActionError(
                "handler returned invalid transition compensation",
                category=WorkflowFailureCategory.PERMANENT,
                retryable=False,
            )
        if isinstance(failure, TransitionOutcome):
            message = f"transition rejected: {failure.reason_code}"
            category = WorkflowFailureCategory.POLICY
            stale = failure.reason_code in self._STALE_TRANSITION_REASONS
            details = dict(failure.details or {})
            replacement_generation = str(
                details.get("observed_generation")
                or f"reassess:{context.job.generation}"
            )
        else:
            message = str(failure)
            category = failure.category
            stale = False
            replacement_generation = f"reassess:{context.job.generation}"
        compensation = dict(result)
        compensation["terminal_failure"] = {
            "message": message,
            "category": category.value,
        }
        compensation["settlement"] = "superseded" if stale else "exhausted"
        if stale:
            compensation["replacement_generation"] = replacement_generation
        durable_checkpoint = dict(checkpoint)
        durable_checkpoint["transition_compensation"] = compensation
        raw_disposition = result.get("disposition")
        if isinstance(raw_disposition, Mapping):
            verification = dict(durable_checkpoint.get("verification") or {})
            verification["disposition"] = dict(raw_disposition)
            durable_checkpoint["verification"] = verification
        await self._checkpoint(
            context,
            phase="transition_compensated",
            checkpoint=durable_checkpoint,
        )

    async def _settle_transition_compensation(
        self,
        context: WorkflowJobContext,
    ) -> WorkflowRunResult | None:
        """Treat a durable compensation as a terminal transition replay barrier."""

        checkpoint = context.job.checkpoint or {}
        raw = checkpoint.get("transition_compensation")
        if not isinstance(raw, Mapping):
            return None
        failure = raw.get("terminal_failure")
        failure = failure if isinstance(failure, Mapping) else {}
        message = str(
            failure.get("message")
            or raw.get("reason_code")
            or "transition was durably compensated"
        ).strip()
        settlement = str(raw.get("settlement") or "exhausted").strip()
        if settlement == "superseded":
            replacement = str(
                raw.get("replacement_generation")
                or f"reassess:{context.job.generation}"
            ).strip()
            superseded = await asyncio.to_thread(
                self.store.supersede,
                context.job.job_id,
                generation=context.job.generation,
                replacement_generation=replacement,
                reason=message,
            )
            return WorkflowRunResult(
                WorkflowRunDisposition.SUPERSEDED,
                superseded.job_id,
                superseded.state,
                message,
                superseded.attempts,
            )
        try:
            category = WorkflowFailureCategory(
                str(failure.get("category") or WorkflowFailureCategory.POLICY.value)
            )
        except ValueError:
            category = WorkflowFailureCategory.POLICY
        raise WorkflowActionError(
            message,
            category=category,
            retryable=False,
        )

    async def _heartbeat(
        self,
        context: WorkflowJobContext,
        stopped: asyncio.Event,
    ) -> None:
        while not stopped.is_set():
            try:
                await asyncio.wait_for(stopped.wait(), self.heartbeat_seconds)
                return
            except TimeoutError:
                pass
            try:
                context.job = await asyncio.to_thread(
                    self.store.renew,
                    context.job.job_id,
                    context.job.lease_token,
                    lease_seconds=self.lease_seconds,
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                context._lease_lost.set()
                return

    @staticmethod
    def _revalidation_checkpoint(result: RevalidationResult) -> dict[str, Any]:
        return {
            "generation": result.generation,
            "evidence_revision": result.evidence_revision,
            "head_sha": result.head_sha,
            "details": dict(result.details),
        }

    @staticmethod
    def _effect_result(observation: EffectObservation | EffectResult) -> EffectResult:
        return EffectResult(receipt=dict(observation.receipt))

    def _is_current(self, job: WorkflowJob, result: RevalidationResult) -> bool:
        if not result.current or result.generation != job.generation:
            return False
        if (
            job.expected_evidence_revision is not None
            and result.evidence_revision != job.expected_evidence_revision
        ):
            return False
        return not (
            job.expected_head_sha is not None
            and result.head_sha != job.expected_head_sha
        )

    async def _fail(
        self,
        context: WorkflowJobContext,
        failure: WorkflowActionError,
    ) -> WorkflowRunResult:
        try:
            job = await asyncio.to_thread(
                self.store.fail,
                context.job.job_id,
                context.job.lease_token,
                category=failure.category,
                error=str(failure),
                retryable=failure.retryable,
                retry_delay_seconds=(
                    failure.retry_delay_seconds
                    if failure.retry_delay_seconds is not None
                    else self.retry_delay_seconds
                ),
            )
        except WorkflowJobLeaseLost:
            return WorkflowRunResult(
                WorkflowRunDisposition.LEASE_LOST,
                context.job.job_id,
                WorkflowJobState.RUNNING,
                "lease lost before failure checkpoint",
                context.job.attempts,
            )
        disposition = (
            WorkflowRunDisposition.RETRY_SCHEDULED
            if job.state is WorkflowJobState.RETRY_WAIT
            else WorkflowRunDisposition.ACTION_REQUIRED
        )
        return WorkflowRunResult(
            disposition,
            job.job_id,
            job.state,
            str(failure),
            job.attempts,
        )

    async def _defer(
        self,
        context: WorkflowJobContext,
        failure: WorkflowActionError,
    ) -> WorkflowRunResult:
        """Release proven pre-effect ownership without spending an attempt."""

        try:
            job = await asyncio.to_thread(
                self.store.defer_owned_without_attempt,
                context.job.job_id,
                context.job.lease_token,
                reason=str(failure),
                retry_delay_seconds=(
                    failure.retry_delay_seconds
                    if failure.retry_delay_seconds is not None
                    else self.retry_delay_seconds
                ),
            )
        except WorkflowJobLeaseLost:
            return WorkflowRunResult(
                WorkflowRunDisposition.LEASE_LOST,
                context.job.job_id,
                WorkflowJobState.RUNNING,
                "lease lost before administrative deferral checkpoint",
                context.job.attempts,
            )
        return WorkflowRunResult(
            WorkflowRunDisposition.RETRY_SCHEDULED,
            job.job_id,
            job.state,
            str(failure),
            job.attempts,
        )

    async def _quarantine(
        self,
        context: WorkflowJobContext,
        failure: WorkflowActionError,
    ) -> WorkflowRunResult:
        """Persist a finite terminal path without releasing late-effect authority."""

        context.fence_external_effects()
        try:
            job = await asyncio.wait_for(
                asyncio.to_thread(
                    self.store.quarantine_owned,
                    context.job.job_id,
                    str(context.job.lease_token or ""),
                    category=failure.category,
                    error=str(failure),
                ),
                timeout=self.quarantine_persist_timeout_seconds,
            )
        except Exception as exc:  # store boundary is itself hard-bounded above
            return WorkflowRunResult(
                WorkflowRunDisposition.LEASE_LOST,
                context.job.job_id,
                WorkflowJobState.RUNNING,
                f"late-effect authority fenced; quarantine unavailable: {type(exc).__name__}",
                context.job.attempts,
            )
        return WorkflowRunResult(
            WorkflowRunDisposition.ACTION_REQUIRED,
            job.job_id,
            job.state,
            str(failure),
            job.attempts,
        )

    async def _execute_claimed(self, job: WorkflowJob) -> WorkflowRunResult:
        handler = self.handlers.get(job.action)
        lease_lost = asyncio.Event()
        context = WorkflowJobContext(
            job,
            lease_lost,
            self._interrupted,
            lambda: self.store.owns_live_lease(
                context.job.job_id,
                str(context.job.lease_token or ""),
            ),
        )
        heartbeat_stop = asyncio.Event()
        heartbeat = asyncio.create_task(self._heartbeat(context, heartbeat_stop))
        effect_authority_started = False
        try:
            await self._notify("leased", context.job)
            context.check_interrupted()
            if handler is None:
                raise WorkflowActionError(
                    f"no handler registered for workflow action {job.action!r}",
                    category=WorkflowFailureCategory.POLICY,
                    retryable=False,
                )

            compensated = await self._settle_transition_compensation(context)
            if compensated is not None:
                return compensated

            revalidation = await self._bounded(
                "revalidate", handler.revalidate(context)
            )
            context.check_interrupted()
            if not isinstance(revalidation, RevalidationResult):
                raise WorkflowActionError(
                    "handler returned an invalid revalidation result",
                    category=WorkflowFailureCategory.PERMANENT,
                    retryable=False,
                )
            if not self._is_current(context.job, revalidation):
                replacement = str(revalidation.generation or "unknown").strip()
                if replacement == context.job.generation:
                    replacement = f"reassess:{replacement}"
                superseded = await asyncio.to_thread(
                    self.store.supersede,
                    context.job.job_id,
                    generation=context.job.generation,
                    replacement_generation=replacement,
                    reason="workflow evidence changed after job enqueue",
                )
                return WorkflowRunResult(
                    WorkflowRunDisposition.SUPERSEDED,
                    superseded.job_id,
                    superseded.state,
                    "workflow evidence changed after job enqueue",
                    superseded.attempts,
                )
            resume_checkpoint = dict(context.job.checkpoint or {})
            resume_checkpoint["revalidation"] = self._revalidation_checkpoint(
                revalidation
            )
            await self._checkpoint(
                context,
                phase="revalidated",
                checkpoint=resume_checkpoint,
            )

            saved_effect = resume_checkpoint.get("effect")
            saved_verification = resume_checkpoint.get("verification")
            saved_transition_intent = resume_checkpoint.get("transition_intent")
            saved_transition = resume_checkpoint.get("transition")
            if isinstance(saved_effect, Mapping):
                effect = EffectResult(dict(saved_effect))
            else:
                observation = await self._bounded(
                    "inspect", handler.inspect(context)
                )
                context.check_interrupted()
                if not isinstance(observation, EffectObservation):
                    raise WorkflowActionError(
                        "handler returned an invalid effect observation",
                        category=WorkflowFailureCategory.PERMANENT,
                        retryable=False,
                    )
                if observation.applied:
                    effect = self._effect_result(observation)
                else:
                    await self._checkpoint(
                        context,
                        phase="effect_pending",
                        checkpoint={
                            "revalidation": self._revalidation_checkpoint(
                                revalidation
                            ),
                            "effect_observed": False,
                        },
                    )
                    handler_timeout = getattr(
                        handler,
                        "operation_timeout_seconds",
                        self.operation_timeout_seconds,
                    )
                    context.check_interrupted()
                    effect_authority_started = True
                    effect = await self._bounded(
                        "apply",
                        handler.apply(context),
                        timeout_seconds=handler_timeout,
                        timeout_fence=context.fence_external_effects,
                    )
                    if not isinstance(effect, EffectResult):
                        raise WorkflowActionError(
                            "handler returned an invalid effect result",
                            category=WorkflowFailureCategory.PERMANENT,
                            retryable=False,
                        )
                # Persist the exact returned/observed receipt before asking the
                # backend to verify it. A process crash in that gap must replay
                # verification, never the external effect.
                await self._checkpoint(
                    context,
                    phase="effect_returned",
                    checkpoint={
                        "revalidation": self._revalidation_checkpoint(
                            revalidation
                        ),
                        "effect": dict(effect.receipt),
                    },
                )
                await self._notify("effect_returned", context.job)
                context.check_interrupted()

            if isinstance(saved_verification, Mapping):
                verification = VerificationResult(
                    True, dict(saved_verification)
                )
            else:
                verification = await self._bounded(
                    "verify", handler.verify(context, effect)
                )
                await self._notify("verify_returned", context.job)
                context.check_interrupted()
                if not isinstance(verification, VerificationResult):
                    raise WorkflowActionError(
                        "handler returned an invalid verification result",
                        category=WorkflowFailureCategory.PERMANENT,
                        retryable=False,
                    )
                if not verification.verified:
                    raise WorkflowActionError(
                        verification.reason
                        or "external effect is not yet verifiable",
                        category=WorkflowFailureCategory.TRANSIENT,
                        retryable=True,
                    )
                await self._checkpoint(
                    context,
                    phase="effect_verified",
                    checkpoint={
                        "revalidation": self._revalidation_checkpoint(
                            revalidation
                        ),
                        "effect": dict(effect.receipt),
                        "verification": dict(verification.receipt),
                    },
                )

            transition = (
                TransitionOutcome.from_dict(saved_transition, replayed=True)
                if isinstance(saved_transition, Mapping)
                else None
            )
            if transition is None:
                try:
                    intent = (
                        TransitionIntent.from_dict(saved_transition_intent)
                        if isinstance(saved_transition_intent, Mapping)
                        else await self._bounded(
                            "build_transition",
                            handler.build_transition(context, verification),
                        )
                    )
                except WorkflowActionError as exc:
                    if not exc.retryable:
                        await self._compensate_transition_failure(
                            handler,
                            context,
                            exc,
                            checkpoint={
                                "revalidation": self._revalidation_checkpoint(
                                    revalidation
                                ),
                                "effect": dict(effect.receipt),
                                "verification": dict(verification.receipt),
                            },
                        )
                    raise
                except (TypeError, ValueError) as exc:
                    failure = WorkflowActionError(
                        "workflow checkpoint contains an invalid transition intent",
                        category=WorkflowFailureCategory.PERMANENT,
                        retryable=False,
                    )
                    await self._compensate_transition_failure(
                        handler,
                        context,
                        failure,
                        checkpoint={
                            "revalidation": self._revalidation_checkpoint(
                                revalidation
                            ),
                            "effect": dict(effect.receipt),
                            "verification": dict(verification.receipt),
                        },
                    )
                    raise failure from exc
                context.check_interrupted()
            else:
                intent = None
            if intent is not None:
                if not isinstance(intent, TransitionIntent):
                    failure = WorkflowActionError(
                        "handler returned an invalid transition intent",
                        category=WorkflowFailureCategory.PERMANENT,
                        retryable=False,
                    )
                    await self._compensate_transition_failure(
                        handler,
                        context,
                        failure,
                        checkpoint={
                            "revalidation": self._revalidation_checkpoint(
                                revalidation
                            ),
                            "effect": dict(effect.receipt),
                            "verification": dict(verification.receipt),
                        },
                    )
                    raise failure
                if (
                    intent.project_id != context.job.project_id
                    or intent.task_id != context.job.task_id
                ):
                    failure = WorkflowActionError(
                        "handler transition intent escaped the job scope",
                        category=WorkflowFailureCategory.POLICY,
                        retryable=False,
                    )
                    await self._compensate_transition_failure(
                        handler,
                        context,
                        failure,
                        checkpoint={
                            "revalidation": self._revalidation_checkpoint(
                                revalidation
                            ),
                            "effect": dict(effect.receipt),
                            "verification": dict(verification.receipt),
                        },
                    )
                    raise failure
                if not isinstance(saved_transition_intent, Mapping):
                    # Persist the exact immutable intent before entering the
                    # transition service.  If the process dies after the
                    # tracker commits but before either service or worker can
                    # journal the outcome, restart must replay this original
                    # pre-commit intent rather than rebuild one from the
                    # already-mutated tracker projection.
                    await self._checkpoint(
                        context,
                        phase="transition_intent",
                        checkpoint={
                            "revalidation": self._revalidation_checkpoint(
                                revalidation
                            ),
                            "effect": dict(effect.receipt),
                            "verification": dict(verification.receipt),
                            "transition_intent": intent.to_dict(),
                        },
                    )
                service = self.transition_services.get(context.job.project_id)
                if service is None:
                    failure = WorkflowActionError(
                        "no transition service registered for the job project",
                        category=WorkflowFailureCategory.POLICY,
                        retryable=False,
                    )
                    await self._compensate_transition_failure(
                        handler,
                        context,
                        failure,
                        checkpoint={
                            "revalidation": self._revalidation_checkpoint(
                                revalidation
                            ),
                            "effect": dict(effect.receipt),
                            "verification": dict(verification.receipt),
                            "transition_intent": intent.to_dict(),
                        },
                    )
                    raise failure
                transition_checkpoint = {
                    "revalidation": self._revalidation_checkpoint(revalidation),
                    "effect": dict(effect.receipt),
                    "verification": dict(verification.receipt),
                    "transition_intent": intent.to_dict(),
                }
                final_attempt = context.job.attempts >= context.job.max_attempts
                try:
                    transition = await self._bounded(
                        "transition",
                        service.execute(intent),
                    )
                except WorkflowActionError as exc:
                    terminal_failure = bool(
                        not isinstance(exc, WorkflowActionTimedOut)
                        and (not exc.retryable or final_attempt)
                    )
                    if terminal_failure:
                        await self._compensate_transition_failure(
                            handler,
                            context,
                            exc,
                            checkpoint=transition_checkpoint,
                        )
                    raise
                except Exception as exc:  # noqa: BLE001 - typed retry boundary
                    failure = WorkflowActionError(
                        f"transition service failed: {type(exc).__name__}: {exc}",
                        category=WorkflowFailureCategory.UNKNOWN,
                        retryable=True,
                    )
                    if final_attempt:
                        await self._compensate_transition_failure(
                            handler,
                            context,
                            failure,
                            checkpoint=transition_checkpoint,
                        )
                    raise failure from exc
                await self._notify("transition_returned", context.job)
                context.check_interrupted()
                if transition.disposition in {
                    TransitionDisposition.RETRYABLE,
                    TransitionDisposition.WAITING,
                }:
                    failure = WorkflowActionError(
                        f"transition deferred: {transition.reason_code}",
                        category=WorkflowFailureCategory.TRANSIENT,
                        retryable=True,
                    )
                    if final_attempt:
                        await self._compensate_transition_failure(
                            handler,
                            context,
                            failure,
                            checkpoint=transition_checkpoint,
                        )
                    raise failure
                if transition.disposition is TransitionDisposition.REJECTED:
                    await self._compensate_transition_failure(
                        handler,
                        context,
                        transition,
                        checkpoint=transition_checkpoint,
                    )
                if (
                    transition.disposition is TransitionDisposition.REJECTED
                    and transition.reason_code in self._STALE_TRANSITION_REASONS
                ):
                    details = dict(transition.details or {})
                    replacement = str(
                        details.get("observed_generation")
                        or f"reassess:{context.job.generation}"
                    )
                    superseded = await asyncio.to_thread(
                        self.store.supersede,
                        context.job.job_id,
                        generation=context.job.generation,
                        replacement_generation=replacement,
                        reason=f"transition evidence changed: {transition.reason_code}",
                    )
                    return WorkflowRunResult(
                        WorkflowRunDisposition.SUPERSEDED,
                        superseded.job_id,
                        superseded.state,
                        f"transition evidence changed: {transition.reason_code}",
                        superseded.attempts,
                    )
                if transition.disposition not in self._SUCCESSFUL_TRANSITIONS:
                    raise WorkflowActionError(
                        f"transition rejected: {transition.reason_code}",
                        category=WorkflowFailureCategory.POLICY,
                        retryable=False,
                    )
                await self._checkpoint(
                    context,
                    phase="transition_applied",
                    checkpoint={
                        "revalidation": self._revalidation_checkpoint(revalidation),
                        "effect": dict(effect.receipt),
                        "verification": dict(verification.receipt),
                        "transition_intent": intent.to_dict(),
                        "transition": transition.to_dict(),
                    },
                )

            completion_landing_facts: tuple[Mapping[str, Any], ...] = ()
            completion_evidence = getattr(
                handler, "completion_landing_facts", None
            )
            if callable(completion_evidence):
                published = completion_evidence(context, verification)
                if inspect.isawaitable(published):
                    published = await self._bounded(
                        "build_completion_evidence", published
                    )
                if isinstance(published, (str, bytes)) or not isinstance(
                    published, Sequence
                ):
                    raise WorkflowActionError(
                        "handler returned invalid completion landing facts",
                        category=WorkflowFailureCategory.PERMANENT,
                        retryable=False,
                    )
                if any(not isinstance(item, Mapping) for item in published):
                    raise WorkflowActionError(
                        "handler returned invalid completion landing fact",
                        category=WorkflowFailureCategory.PERMANENT,
                        retryable=False,
                    )
                completion_landing_facts = tuple(published)
                context.check_interrupted()

            finalize_transition = getattr(handler, "finalize_transition", None)
            if transition is not None and callable(finalize_transition):
                await self._bounded(
                    "finalize_transition",
                    finalize_transition(context, transition),
                )
                context.check_interrupted()

            completed = await asyncio.to_thread(
                self.store.complete,
                context.job.job_id,
                context.job.lease_token,
                result_transition=transition.to_dict() if transition else None,
                landing_facts=completion_landing_facts,
            )
            await self._notify("completed", completed)
            return WorkflowRunResult(
                WorkflowRunDisposition.COMPLETED,
                completed.job_id,
                completed.state,
                "workflow action completed",
                completed.attempts,
            )
        except WorkflowJobLeaseLost:
            return WorkflowRunResult(
                WorkflowRunDisposition.LEASE_LOST,
                context.job.job_id,
                WorkflowJobState.RUNNING,
                "workflow job lease was lost",
                context.job.attempts,
            )
        except WorkflowActionSuperseded as exc:
            superseded = await asyncio.to_thread(
                self.store.supersede,
                context.job.job_id,
                generation=context.job.generation,
                replacement_generation=exc.replacement_generation,
                reason=str(exc),
            )
            return WorkflowRunResult(
                WorkflowRunDisposition.SUPERSEDED,
                superseded.job_id,
                superseded.state,
                str(exc),
                superseded.attempts,
            )
        except WorkflowAdministrativeDeferral as exc:
            checkpoint = context.job.checkpoint or {}
            effect_is_durable = isinstance(checkpoint.get("effect"), Mapping)
            if not effect_is_durable and (
                not effect_authority_started or exc.effect_not_started
            ):
                return await self._defer(context, exc)
            return await self._fail(context, exc)
        except WorkflowActionInterrupted as exc:
            if not effect_authority_started:
                return await self._defer(context, exc)
            return await self._fail(context, exc)
        except WorkflowActionError as exc:
            if isinstance(exc, WorkflowActionTimedOut):
                result = await self._quarantine(context, exc)
                if result.disposition is WorkflowRunDisposition.ACTION_REQUIRED:
                    self._monitor_quarantined_call(context, exc)
                return result
            return await self._fail(context, exc)
        except asyncio.CancelledError:
            context.fence_external_effects()
            try:
                await asyncio.shield(
                    self._quarantine(
                        context,
                        WorkflowActionError(
                            "workflow invocation was cancelled",
                            category=WorkflowFailureCategory.ABANDONED,
                            retryable=False,
                        ),
                    )
                )
            finally:
                raise
        except Exception as exc:  # noqa: BLE001 - durable unknown-failure boundary
            return await self._fail(
                context,
                WorkflowActionError(
                    f"unhandled {type(exc).__name__}: {exc}",
                    category=WorkflowFailureCategory.UNKNOWN,
                    retryable=True,
                ),
            )
        finally:
            heartbeat_stop.set()
            heartbeat.cancel()
            try:
                await heartbeat
            except asyncio.CancelledError:
                pass

    async def run_once(
        self,
        *,
        project_id: str | None = None,
        project_ids: Sequence[str] | None = None,
        actions: Sequence[str] | None = None,
        fair_across_projects: bool = False,
    ) -> WorkflowRunResult:
        if not self._accepting:
            return WorkflowRunResult(
                WorkflowRunDisposition.STOPPED,
                None,
                None,
                "worker is draining",
            )
        current = asyncio.current_task()
        if current is not None:
            self._active.add(current)
        try:
            # Default claims are domain-scoped.  Otherwise a worker can lease
            # a durable action for which it has no handler and exhaust it as a
            # policy error.  Terminal-audit jobs are especially sensitive:
            # their dedicated adapter owns typed-result finalization.
            claim_actions = (
                tuple(sorted(self.handlers)) if actions is None else tuple(actions)
            )
            if not claim_actions:
                return WorkflowRunResult(
                    WorkflowRunDisposition.IDLE,
                    None,
                    None,
                    "worker has no registered workflow actions",
                )
            job = await self.claim_next(
                project_id=project_id,
                project_ids=project_ids,
                actions=claim_actions,
                fair_across_projects=fair_across_projects,
            )
            if job is None:
                return WorkflowRunResult(
                    WorkflowRunDisposition.IDLE,
                    None,
                    None,
                    "no due workflow job",
                )
            return await self._execute_claimed(job)
        finally:
            if current is not None:
                self._active.discard(current)

    async def claim_next(
        self,
        *,
        project_id: str | None = None,
        project_ids: Sequence[str] | None = None,
        actions: Sequence[str] | None = None,
        required_snapshot_generation: int | None = None,
        fair_across_projects: bool = False,
    ) -> WorkflowJob | None:
        """Claim one exact durable row without waiting for its effect.

        Runtime schedulers use this small admission boundary to retain the
        resulting invocation in a bounded background lane.  A claim remains
        restart-safe even if the process exits before ``execute_claimed`` is
        admitted: its lease expires back into the ordinary recovery path.
        """

        if not self._accepting:
            return None
        claim_actions = (
            tuple(sorted(self.handlers)) if actions is None else tuple(actions)
        )
        if not claim_actions:
            return None
        return await asyncio.to_thread(
            self.store.claim_next,
            lease_owner=self.worker_id,
            lease_seconds=self.lease_seconds,
            project_id=project_id,
            project_ids=project_ids,
            actions=claim_actions,
            required_snapshot_generation=required_snapshot_generation,
            fair_across_projects=fair_across_projects,
        )

    async def has_claimable(
        self,
        *,
        project_id: str | None = None,
        project_ids: Sequence[str] | None = None,
        actions: Sequence[str] | None = None,
        required_snapshot_generation: int | None = None,
    ) -> bool:
        """Probe exact admission eligibility without spending an attempt."""

        if not self._accepting:
            return False
        claim_actions = (
            tuple(sorted(self.handlers)) if actions is None else tuple(actions)
        )
        if not claim_actions:
            return False
        return await asyncio.to_thread(
            self.store.has_claimable,
            project_id=project_id,
            project_ids=project_ids,
            actions=claim_actions,
            required_snapshot_generation=required_snapshot_generation,
        )

    async def execute_claimed(self, job: WorkflowJob) -> WorkflowRunResult:
        """Execute a row already leased by :meth:`claim_next`.

        Unlike new admission this method deliberately remains available after
        ``drain`` fences claims.  Shutdown first waits for the runtime's claim
        pass, so every lease returned to it must either start its independent
        heartbeat here or recover durably after a process crash.
        """

        if not isinstance(job, WorkflowJob):
            raise TypeError("job must be a WorkflowJob")
        current = asyncio.current_task()
        if current is not None:
            self._active.add(current)
        try:
            return await self._execute_claimed(job)
        finally:
            if current is not None:
                self._active.discard(current)
