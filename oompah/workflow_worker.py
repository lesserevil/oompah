"""Resumable worker for durable workflow jobs.

The worker owns orchestration, not domain behavior.  Domain handlers revalidate
facts and implement idempotent external effects; the worker supplies durable
leases, bounded calls, restart checkpoints, transition-service routing, and
late-worker fencing.
"""

from __future__ import annotations

import asyncio
import inspect
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
    def __init__(self, operation: str, timeout_seconds: float) -> None:
        super().__init__(
            f"{operation} exceeded {timeout_seconds:g}s timeout",
            category=WorkflowFailureCategory.TIMEOUT,
            retryable=True,
        )


class WorkflowActionInterrupted(WorkflowActionError):
    def __init__(self) -> None:
        super().__init__(
            "workflow action interrupted before the next persistence boundary",
            category=WorkflowFailureCategory.TRANSIENT,
            retryable=True,
        )


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

    @property
    def idempotency_key(self) -> str:
        return self.job.idempotency_key

    def check_interrupted(self) -> None:
        if self._lease_lost.is_set():
            raise WorkflowJobLeaseLost(
                f"workflow job lease was lost: {self.job.job_id}"
            )
        if self._interrupted.is_set():
            raise WorkflowActionInterrupted()


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
        phase_observer: PhaseObserver | None = None,
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
        self.lease_seconds = float(lease_seconds)
        self.heartbeat_seconds = float(heartbeat_seconds)
        self.operation_timeout_seconds = float(operation_timeout_seconds)
        self.retry_delay_seconds = float(retry_delay_seconds)
        self.phase_observer = phase_observer
        self._accepting = True
        self._interrupted = asyncio.Event()
        self._active: set[asyncio.Task[Any]] = set()

    @property
    def accepting(self) -> bool:
        return self._accepting

    @property
    def active_count(self) -> int:
        return len(self._active)

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

    async def _bounded(self, operation: str, call: Awaitable[Any]) -> Any:
        try:
            return await asyncio.wait_for(call, self.operation_timeout_seconds)
        except TimeoutError as exc:
            raise WorkflowActionTimedOut(
                operation, self.operation_timeout_seconds
            ) from exc

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
            except WorkflowJobLeaseLost:
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

    async def _execute_claimed(self, job: WorkflowJob) -> WorkflowRunResult:
        handler = self.handlers.get(job.action)
        lease_lost = asyncio.Event()
        context = WorkflowJobContext(job, lease_lost, self._interrupted)
        heartbeat_stop = asyncio.Event()
        heartbeat = asyncio.create_task(self._heartbeat(context, heartbeat_stop))
        try:
            await self._notify("leased", context.job)
            context.check_interrupted()
            if handler is None:
                raise WorkflowActionError(
                    f"no handler registered for workflow action {job.action!r}",
                    category=WorkflowFailureCategory.POLICY,
                    retryable=False,
                )

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
            if isinstance(saved_effect, Mapping) and isinstance(
                saved_verification, Mapping
            ):
                effect = EffectResult(dict(saved_effect))
                verification = VerificationResult(
                    True, dict(saved_verification)
                )
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
                    effect = await self._bounded("apply", handler.apply(context))
                    await self._notify("effect_returned", context.job)
                    context.check_interrupted()
                    if not isinstance(effect, EffectResult):
                        raise WorkflowActionError(
                            "handler returned an invalid effect result",
                            category=WorkflowFailureCategory.PERMANENT,
                            retryable=False,
                        )

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

            intent = await self._bounded(
                "build_transition", handler.build_transition(context, verification)
            )
            context.check_interrupted()
            transition: TransitionOutcome | None = None
            if intent is not None:
                if not isinstance(intent, TransitionIntent):
                    raise WorkflowActionError(
                        "handler returned an invalid transition intent",
                        category=WorkflowFailureCategory.PERMANENT,
                        retryable=False,
                    )
                if (
                    intent.project_id != context.job.project_id
                    or intent.task_id != context.job.task_id
                ):
                    raise WorkflowActionError(
                        "handler transition intent escaped the job scope",
                        category=WorkflowFailureCategory.POLICY,
                        retryable=False,
                    )
                service = self.transition_services.get(context.job.project_id)
                if service is None:
                    raise WorkflowActionError(
                        "no transition service registered for the job project",
                        category=WorkflowFailureCategory.POLICY,
                        retryable=False,
                    )
                transition = await self._bounded("transition", service.execute(intent))
                await self._notify("transition_returned", context.job)
                context.check_interrupted()
                if transition.disposition in {
                    TransitionDisposition.RETRYABLE,
                    TransitionDisposition.WAITING,
                }:
                    raise WorkflowActionError(
                        f"transition deferred: {transition.reason_code}",
                        category=WorkflowFailureCategory.TRANSIENT,
                        retryable=True,
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
                        "transition": transition.to_dict(),
                    },
                )

            completed = await asyncio.to_thread(
                self.store.complete,
                context.job.job_id,
                context.job.lease_token,
                result_transition=transition.to_dict() if transition else None,
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
        except WorkflowActionError as exc:
            return await self._fail(context, exc)
        except asyncio.CancelledError:
            try:
                await asyncio.shield(
                    self._fail(
                        context,
                        WorkflowActionError(
                            "workflow invocation was cancelled",
                            category=WorkflowFailureCategory.ABANDONED,
                            retryable=True,
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
            await heartbeat

    async def run_once(
        self,
        *,
        project_id: str | None = None,
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
            job = await asyncio.to_thread(
                self.store.claim_next,
                lease_owner=self.worker_id,
                lease_seconds=self.lease_seconds,
                project_id=project_id,
                actions=actions,
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
