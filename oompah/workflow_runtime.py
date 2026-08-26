"""Production lifecycle wiring for the durable workflow domains.

The domain modules deliberately contain no process-global state.  This module
is the small composition root that gives them a shared job ledger, a
project-scoped fact collector, a transition service, and one worker.  Keeping
that wiring here is important: constructing a controller in an API handler (or
in a legacy maintenance pass) would create a second owner for the same task.

``WorkflowRuntime`` is useful in tests as well as in the service bootstrap.  A
caller may provide action handlers for temporary tracker/forge doubles; the
production bootstrap uses the handlers registered by the orchestrator.  The
runtime never invents a tracker or silently falls back from a project-scoped
tracker to the management tracker.
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import logging
import os
import re
import subprocess
import threading
import time
import uuid
from collections import deque
from collections.abc import Callable, Mapping, Sequence
from contextlib import ExitStack
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from oompah.epic_workflow import (
    EPIC_ACTIONS,
    EpicAction,
    EpicFactCollector,
    EpicWorkflowController,
    is_epic_rollup_issue,
)
from oompah.events import EventType
from oompah.implementation_workflow import (
    FACT_IMPLEMENTATION_LANE,
    IMPERATIVE_IMPLEMENTATION_LANE,
    IMPLEMENTATION_ACTIONS,
    IMPLEMENTATION_ORDERING_NAMESPACE,
    ImplementationWorkflowController,
)
from oompah.integration_workflow import (
    INTEGRATION_ACTIONS,
    IntegrationLandingRequestResolver,
    IntegrationWorkflowController,
)
from oompah.review_workflow import ReviewWorkflowController
from oompah.review_workflow_adapter import FreshReviewFactSource
from oompah.scm import detect_provider, extract_repo_slug
from oompah.statuses import (
    ARCHIVED,
    IN_PROGRESS,
    IN_REVIEW,
    IN_VALIDATION,
    MERGED,
    READY_TO_INTEGRATE,
    canonicalize_status,
)
from oompah.task_transition_service import (
    CoordinatorTerminalAdapter,
    TaskTransitionService,
    TransitionAuthority,
    TransitionJournal,
    issue_authority_version,
    issue_exact_head,
)
from oompah.workflow_contract import LIFECYCLE_FINAL_STATUSES, TaskDisposition
from oompah.workflow_controller import (
    ControllerObservation,
    ControllerPass,
    UniversalTotalityLivenessController,
)
from oompah.workflow_fact_model import (
    FactDomain,
    FactState,
    LandingState,
    WorkflowFacts,
)
from oompah.workflow_facts import GitLandingCollector, WorkflowFactCollector
from oompah.workflow_jobs import (
    WorkflowFailureCategory,
    WorkflowJobPublicationError,
    WorkflowJobStore,
    WorkflowSnapshotPublication,
)
from oompah.workflow_liveness_metrics import DecisionLivenessFacts
from oompah.workflow_reasons import LivenessPolicy
from oompah.workflow_shadow import (
    aggregate_workflow_domain_mode,
    normalize_workflow_domain_modes,
)
from oompah.workflow_scheduler import WorkflowReconcileResult
from oompah.workflow_worker import (
    EffectObservation,
    EffectResult,
    RevalidationResult,
    VerificationResult,
    WorkflowAdministrativeDeferral,
    WorkflowActionDomain,
    WorkflowActionError,
    WorkflowActionHandler,
    WorkflowJobContext,
    DurableWorkflowWorker,
)
from oompah.work_decision import (
    REVIEW_ACTION_JOBS,
    WorkDecision,
    epic_immediate_target_landings,
    evaluate_task,
)

logger = logging.getLogger(__name__)

LEGACY_PROJECT_ID = "legacy"
DEFAULT_RUNTIME_DECISION_LIMIT = 100
DEFAULT_RUNTIME_BATCH_SIZE = 32
MAX_RUNTIME_LIVENESS_DOMAIN_LIMIT = 1000

_DOMAIN_ACTIONS = {
    "implementation": IMPLEMENTATION_ACTIONS,
    "review": REVIEW_ACTION_JOBS,
    "integration": INTEGRATION_ACTIONS,
    "epic": EPIC_ACTIONS,
}
RUNTIME_ACTIONS = frozenset().union(*_DOMAIN_ACTIONS.values())
# These exact lifecycle effects must remain admissible while a forge or
# validation gate is waiting.  The shared lane may also execute them, but the
# reserved lane never admits data-plane work.
RUNTIME_CONTROL_ACTIONS = frozenset(
    {
        "authority_revocation",
        "direct_owner_claim",
        "validation_submission",
        "worker_exit",
        "implementation_recovery",
        "integration_recovery",
        "terminal_audit_done",
    }
)
_RUNTIME_PROCESS_GENERATION = uuid.uuid4().hex
_RUNTIME_OWNER_PATTERN = re.compile(
    r"^workflow-runtime:(?P<pid>[1-9][0-9]*):"
    r"(?:(?P<start_ticks>[1-9][0-9]*):)?"
    r"(?:p(?P<process_generation>[0-9a-f]{32}):)?[0-9a-f]+$"
)


def _process_start_ticks(pid: int) -> int | None:
    """Return the Linux process generation used by durable owner fencing."""

    try:
        raw = Path(f"/proc/{int(pid)}/stat").read_text(encoding="utf-8")
        return int(raw[raw.rfind(")") + 2 :].split()[19])
    except (OSError, ValueError, IndexError):
        return None

if sum(len(actions) for actions in _DOMAIN_ACTIONS.values()) != len(RUNTIME_ACTIONS):
    raise RuntimeError("durable workflow domain action sets overlap")
if not RUNTIME_CONTROL_ACTIONS < RUNTIME_ACTIONS:
    raise RuntimeError("durable workflow control actions must be runtime actions")

_LIVENESS_ACTION_OWNER = {
    **{action: "implementation" for action in IMPLEMENTATION_ACTIONS},
    **{action: "review" for action in REVIEW_ACTION_JOBS},
    **{action: "integration" for action in INTEGRATION_ACTIONS},
    **{action: "epic" for action in EPIC_ACTIONS},
    "facts_refresh": "none",
    "dependency_refresh": "none",
    "terminal_audit": "terminal_audit",
    "terminal_audit_recovery": "terminal_audit",
}
_LIVENESS_ACTION_OWNER["historical_audit_replay_batch"] = "excluded"
_EXPECTED_LIVENESS_ACTIONS = RUNTIME_ACTIONS | {
    "facts_refresh",
    "dependency_refresh",
    "terminal_audit",
    "terminal_audit_recovery",
}
if set(_LIVENESS_ACTION_OWNER) != _EXPECTED_LIVENESS_ACTIONS:
    raise RuntimeError("workflow liveness action ownership registry is incomplete")


class _WorkflowReconciliationInterrupted(BaseException):
    """Internal cooperative stop before a workflow snapshot is published."""


class _WorkflowReconciliationDeadlineExceeded(BaseException):
    """Internal fail-closed stop at the absolute restart reconstruction deadline."""


class WorkflowRuntimeError(RuntimeError):
    """Raised when durable runtime composition is invalid."""


class WorkflowPublicationSuperseded(WorkflowRuntimeError):
    """Raised when a concurrent authority change invalidates a staged cut."""


class _WorkflowProjectAuthorityChanged(RuntimeError):
    """Retry one project whose exactly-scoped tracker authority changed."""

    def __init__(self, changed_tasks: frozenset[str]) -> None:
        super().__init__("scoped tracker authority changed")
        self.changed_tasks = changed_tasks


class _WorkflowScopedPublicationChanged(WorkflowPublicationSuperseded):
    """Retry a cut when final preflight proves an exact ordinary task delta."""

    def __init__(self, project_id: str, changed_tasks: frozenset[str]) -> None:
        super().__init__("tracker authority changed before publication")
        self.project_id = project_id
        self.changed_tasks = changed_tasks


class _WorkflowFinalPublicationChanged(WorkflowPublicationSuperseded):
    """Retry a whole cut after the final constant-time tracker CAS changes."""


def _tracker_publication_revision(
    source: Callable[[], int | None],
    *,
    unavailable_reason: str,
) -> int:
    """Read one native mutation token or supersede an unstable snapshot."""

    revision = source()
    if revision is None:
        raise WorkflowPublicationSuperseded(unavailable_reason)
    return int(revision)


@dataclass(frozen=True, slots=True)
class _WorkflowAdmissionCut:
    """Exact published world snapshot permitted to admit durable effects."""

    snapshot_generation: int
    project_ids: tuple[str, ...]


class WorkflowRuntimeHandlerFactory(Protocol):
    def __call__(
        self, binding: "WorkflowProjectBinding"
    ) -> Mapping[str, WorkflowActionHandler]: ...


@dataclass(slots=True)
class WorkflowProjectBinding:
    """All durable workflow dependencies for one managed project."""

    project_id: str
    tracker: Any
    collector: WorkflowFactCollector
    transition_service: TaskTransitionService
    implementation_controller: Any | None = None
    review_controller: ReviewWorkflowController | None = None
    integration_controller: IntegrationWorkflowController | None = None
    epic_collector: EpicFactCollector | None = None
    epic_controller: EpicWorkflowController | None = None
    terminal_audit_workflow: Any | None = None
    transition_journal: TransitionJournal | None = None
    dispatch_enabled: Callable[[], bool] | None = None
    lifecycle_interrupted: Callable[[], bool] | None = None
    terminal_audit_proof_source: Callable[
        [WorkDecision, Mapping[str, Any], str], bool
    ] | None = None
    terminal_audit_snapshot_proof_source: Callable[
        [WorkDecision, Mapping[str, Any]], bool
    ] | None = None
    terminal_audit_lane_proof_source: Callable[
        [WorkDecision, Mapping[str, Any], str | None], bool
    ] | None = None
    terminal_audit_publication_lock: Callable[[], Any] | None = None
    terminal_authority_revision_source: Callable[[], int] | None = None
    terminal_authority_changes_source: Callable[
        [int], tuple[int, frozenset[str] | None]
    ] | None = None
    workflow_authority_revision_source: Callable[[], int] | None = None
    tracker_authority_revision_source: Callable[[], str | None] | None = None
    tracker_publication_revision_source: Callable[[], int | None] | None = None
    tracker_publication_changes_source: Callable[
        [int], tuple[int, frozenset[str] | None]
    ] | None = None
    tracker_authority_changes_source: Callable[
        [str, str], frozenset[str] | None
    ] | None = None
    tracker_terminal_authority_changes_source: Callable[
        [str, str], frozenset[str] | None
    ] | None = None

    @property
    def enabled(self) -> bool:
        """Whether this project's durable worker may claim new work."""

        try:
            return self.read_enabled_state()
        except Exception:
            # Pause/configuration authority is a correctness boundary.  A
            # failed read must never be interpreted as permission to mutate.
            return False

    def read_enabled_state(self) -> bool:
        """Read pause authority while preserving failures for reconciliation."""

        if self.dispatch_enabled is None:
            return True
        return bool(self.dispatch_enabled())

    @property
    def interrupted(self) -> bool:
        """Whether a process-wide lifecycle fence interrupted evaluation."""

        if self.lifecycle_interrupted is None:
            return False
        try:
            return bool(self.lifecycle_interrupted())
        except Exception:
            # Unknown lifecycle authority cannot safely become rollout
            # qualification evidence.  Treat it as an interruption, which is
            # neutral and requires a later complete sweep.
            return True

    @property
    def controllers(self) -> tuple[Any, ...]:
        return tuple(
            controller
            for controller in (
                self.implementation_controller,
                self.review_controller,
                self.integration_controller,
                self.epic_controller,
                self.terminal_audit_workflow,
            )
            if controller is not None
        )


@dataclass(frozen=True, slots=True)
class WorkflowRuntimeEvent:
    """Redacted lifecycle event retained for diagnostics and tests."""

    phase: str
    job_id: str
    project_id: str
    task_id: str
    action: str


@dataclass(frozen=True, slots=True)
class WorkflowEffectCleanup:
    """Typed retained-invocation exit when no WorkflowRunResult exists."""

    cancelled: bool
    error_type: str | None
    job_id: None = None


class _UnavailableHandler:
    """Fail closed when a domain has not supplied an external-effect adapter.

    The handler is only used to make the worker composition total during
    shadow/off migrations.  The runtime does not claim jobs when no real
    handlers were registered, so this cannot turn a missing adapter into a
    fake successful transition.
    """

    domain = WorkflowActionDomain.TRACKER

    def __init__(self, action: str) -> None:
        self.action = action

    async def revalidate(self, context: WorkflowJobContext) -> RevalidationResult:
        return RevalidationResult(context.job.generation)

    async def inspect(self, context: WorkflowJobContext) -> EffectObservation:
        return EffectObservation(False)

    async def apply(self, context: WorkflowJobContext) -> EffectResult:
        raise WorkflowActionError(
            f"no durable handler registered for workflow action {self.action}",
            category=WorkflowFailureCategory.POLICY,
            retryable=False,
        )

    async def verify(
        self, context: WorkflowJobContext, effect: EffectResult
    ) -> VerificationResult:
        return VerificationResult(False, reason="durable handler is unavailable")

    async def build_transition(
        self, context: WorkflowJobContext, verification: VerificationResult
    ) -> None:
        return None


class _ProjectRoutedHandler:
    """Route one action to the handler bound to the job's exact project."""

    def __init__(
        self,
        action: str,
        handlers: Mapping[str, WorkflowActionHandler],
        *,
        project_enabled: Mapping[str, Callable[[], bool]] | None = None,
    ) -> None:
        if not handlers:
            raise ValueError("project-routed handlers cannot be empty")
        self.action = action
        self.handlers = dict(handlers)
        domains = {
            WorkflowActionDomain(handler.domain) for handler in handlers.values()
        }
        if len(domains) != 1:
            raise WorkflowRuntimeError(
                f"workflow action {action} has inconsistent project handler domains"
            )
        self.domain = domains.pop()
        self._project_enabled = dict(project_enabled or {})
        timeouts = [
            float(value)
            for handler in handlers.values()
            for value in (getattr(handler, "operation_timeout_seconds", None),)
            if value is not None
        ]
        if timeouts:
            self.operation_timeout_seconds = max(timeouts)

    def _handler(self, context: WorkflowJobContext) -> WorkflowActionHandler:
        enabled = self._project_enabled.get(context.job.project_id)
        if enabled is not None:
            try:
                may_run = bool(enabled())
            except Exception:
                may_run = False
            if not may_run:
                raise WorkflowAdministrativeDeferral(
                    "durable workflow project is paused or quiesced",
                    effect_not_started=True,
                )
        try:
            return self.handlers[context.job.project_id]
        except KeyError as exc:
            raise WorkflowActionError(
                "no durable handler registered for workflow action "
                f"{self.action} in project {context.job.project_id}",
                category=WorkflowFailureCategory.POLICY,
                retryable=False,
            ) from exc

    async def _call(self, name: str, context: WorkflowJobContext, *args: Any) -> Any:
        result = getattr(self._handler(context), name)(context, *args)
        return await result if inspect.isawaitable(result) else result

    async def revalidate(self, context: WorkflowJobContext) -> RevalidationResult:
        return await self._call("revalidate", context)

    async def inspect(self, context: WorkflowJobContext) -> EffectObservation:
        return await self._call("inspect", context)

    async def apply(self, context: WorkflowJobContext) -> EffectResult:
        return await self._call("apply", context)

    async def verify(
        self, context: WorkflowJobContext, effect: EffectResult
    ) -> VerificationResult:
        return await self._call("verify", context, effect)

    async def build_transition(
        self, context: WorkflowJobContext, verification: VerificationResult
    ) -> Any:
        return await self._call("build_transition", context, verification)

    async def prepare_quarantine_recycle(self, job: Any) -> None:
        """Delegate durable process-boundary transfer to the owning leaf."""

        handler = self.handlers.get(str(getattr(job, "project_id", "") or ""))
        prepare = getattr(handler, "prepare_quarantine_recycle", None)
        if not callable(prepare):
            return
        result = prepare(job)
        if inspect.isawaitable(result):
            await result


class WorkflowRuntime:
    """Own the durable workflow services for the lifetime of one process."""

    def __init__(
        self,
        *,
        project_bindings: Mapping[str, WorkflowProjectBinding],
        store: WorkflowJobStore,
        journals: Mapping[str, TransitionJournal],
        mode: str = "off",
        domain_modes: Mapping[str, str] | None = None,
        rollout_require_qualification: bool = False,
        rollout_min_shadow_sweeps: int = 3,
        rollout_min_shadow_seconds: int = 300,
        handlers: Mapping[str, WorkflowActionHandler] | None = None,
        decision_limit: int = DEFAULT_RUNTIME_DECISION_LIMIT,
        batch_size: int = DEFAULT_RUNTIME_BATCH_SIZE,
        max_concurrent: int = 4,
        control_reserved_slots: int = 1,
        worker: DurableWorkflowWorker | None = None,
        handler_coverage: Mapping[str, Sequence[str]] | None = None,
        abandoned_lease_owners: Sequence[str] = (),
        topology_signature: tuple[Any, ...] | None = None,
        topology_source: Callable[[], tuple[Any, ...]] | None = None,
        topology_change_handler: Callable[[], Any] | None = None,
        transition_observer: Callable[[Any], None] | None = None,
        effect_completion_observer: Callable[[Any], None] | None = None,
        quarantine_recycle_observer: Callable[[Any], Any] | None = None,
        quarantine_persist_timeout_seconds: float = 5,
        quarantine_recycle_seconds: float = 60,
        liveness_controller: UniversalTotalityLivenessController | None = None,
        persist_liveness_state: Callable[[Mapping[str, Any]], None] | None = None,
        projection_publisher: Callable[..., Any] | None = None,
        projection_epoch_source: Callable[[], int] | None = None,
    ) -> None:
        normalized_mode = str(mode or "off").strip().lower()
        if normalized_mode not in {"off", "shadow", "enforce"}:
            raise ValueError("workflow runtime mode must be off, shadow, or enforce")
        if decision_limit < 1:
            raise ValueError("decision_limit must be positive")
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        if max_concurrent < 2:
            raise ValueError("max_concurrent must be at least two")
        if control_reserved_slots < 1:
            raise ValueError("control_reserved_slots must be positive")
        if control_reserved_slots >= max_concurrent:
            raise ValueError(
                "control_reserved_slots must leave at least one shared slot"
            )
        self.mode = normalized_mode
        self.domain_modes = normalize_workflow_domain_modes(
            domain_modes,
            fallback=normalized_mode,
        )
        aggregate_mode = aggregate_workflow_domain_mode(self.domain_modes)
        if domain_modes is not None and aggregate_mode != normalized_mode:
            raise ValueError(
                "workflow runtime mode must match the aggregate domain modes"
            )
        self.rollout_require_qualification = bool(
            rollout_require_qualification
        )
        self.rollout_min_shadow_sweeps = max(
            int(rollout_min_shadow_sweeps), 1
        )
        self.rollout_min_shadow_seconds = max(
            int(rollout_min_shadow_seconds), 0
        )
        self.store = store
        if liveness_controller is not None and liveness_controller.store is not store:
            raise ValueError(
                "runtime and liveness controller must share one workflow job store"
            )
        if (projection_publisher is None) != (projection_epoch_source is None):
            raise ValueError(
                "projection publisher and publication epoch source must be "
                "configured together"
            )
        if (liveness_controller is None) != (projection_publisher is None):
            raise ValueError(
                "liveness controller and canonical projection publication "
                "must be configured together"
            )
        self.liveness_controller = liveness_controller
        self._persist_liveness_state = persist_liveness_state
        self._projection_publisher = projection_publisher
        self._projection_epoch_source = projection_epoch_source
        self.project_bindings = dict(project_bindings)
        if liveness_controller is not None:
            policy_epoch = liveness_controller.liveness_policy.epoch
            # A canonical liveness generation must prove every identity the
            # bounded liveness projection can represent in that same
            # generation. Rotating smaller owning-domain windows across later
            # generations can never close an exact-current proof gap.
            owning_limit = min(
                MAX_RUNTIME_LIVENESS_DOMAIN_LIMIT,
                liveness_controller.liveness.max_task_records,
            )
            for binding in self.project_bindings.values():
                for controller in (
                    binding.implementation_controller,
                    binding.review_controller,
                    binding.integration_controller,
                    binding.epic_controller,
                ):
                    if controller is None or not hasattr(
                        controller, "decision_limit"
                    ):
                        continue
                    effective_limit = max(
                        int(controller.decision_limit), owning_limit
                    )
                    controller.decision_limit = effective_limit
                    scheduler = getattr(controller, "scheduler", None)
                    if scheduler is not None:
                        scheduler.decision_limit = max(
                            int(scheduler.decision_limit), effective_limit
                        )
            self._bind_policy_epoch(policy_epoch)
        self.journals = dict(journals)
        self.decision_limit = int(decision_limit)
        self.batch_size = int(batch_size)
        self.max_concurrent = int(max_concurrent)
        self.control_reserved_slots = int(control_reserved_slots)
        self._lock = threading.RLock()
        self._reconcile_condition = threading.Condition(self._lock)
        self._active_reconciles = 0
        self._reconcile_tasks: set[asyncio.Task[dict[str, Any]]] = set()
        self._started = False
        self._draining = False
        self._last_reconcile: dict[str, Any] = {}
        self._admission_cut: _WorkflowAdmissionCut | None = None
        self._latest_decisions: dict[tuple[str, str], Any] = {}
        self._events: list[WorkflowRuntimeEvent] = []
        self._terminal_publication_lock_metrics: dict[str, float | int] = {
            "acquisitions": 0,
            "superseded": 0,
            "wait_seconds_total": 0.0,
            "wait_seconds_max": 0.0,
            "wait_seconds_last": 0.0,
            "hold_seconds_total": 0.0,
            "hold_seconds_max": 0.0,
            "hold_seconds_last": 0.0,
        }
        self._effect_tasks: dict[asyncio.Task[Any], str] = {}
        self._effect_results: deque[Any] = deque(maxlen=128)
        # Claiming awaits SQLite off-loop. Keep the capacity observation,
        # exact claim, and retained-task publication inside one async critical
        # section so overlapping reconciles cannot both spend the same slot.
        self._effect_admission_lock = asyncio.Lock()
        self._closed = False
        self._reconcile_thread = threading.local()
        for binding in self.project_bindings.values():
            collectors = [
                getattr(binding, "collector", None),
                getattr(binding, "epic_collector", None),
                *(
                    getattr(controller, "collector", None)
                    for controller in (
                        binding.implementation_controller,
                        binding.review_controller,
                        binding.integration_controller,
                        binding.epic_controller,
                    )
                    if controller is not None
                ),
            ]
            for collector in {
                id(item): item for item in collectors if item is not None
            }.values():
                if not hasattr(collector, "cooperative_checkpoint"):
                    continue
                collector.cooperative_checkpoint = self._reconciliation_checkpoint
        self._topology_signature = topology_signature
        self._topology_source = topology_source
        self._topology_change_handler = topology_change_handler
        self._transition_observer = transition_observer
        self._effect_completion_observer = effect_completion_observer
        self._quarantine_recycle_observer = quarantine_recycle_observer
        self._abandoned_lease_owners = frozenset(
            str(owner).strip() for owner in abandoned_lease_owners if str(owner).strip()
        )
        supplied = dict(handlers or {})
        unknown_actions = set(supplied) - RUNTIME_ACTIONS
        if unknown_actions:
            raise WorkflowRuntimeError(
                "handlers were registered outside durable domain ownership: "
                + ", ".join(sorted(unknown_actions))
            )
        normalized_coverage = {
            action: frozenset(str(project_id) for project_id in projects)
            for action, projects in (handler_coverage or {}).items()
        }
        self._handler_coverage = {
            action: normalized_coverage.get(
                action,
                (
                    frozenset(self.project_bindings)
                    if action in supplied and len(self.project_bindings) == 1
                    else frozenset()
                ),
            )
            for action in RUNTIME_ACTIONS
        }
        self._handlers_configured = bool(supplied)
        # Terminal audit jobs are deliberately absent. TerminalAuditWorkflow
        # owns launch recovery and finalization, including unsafe historical
        # archives which may leave a queued record after coordinator rejection.
        worker_handlers = {
            action: supplied.get(action, _UnavailableHandler(action))
            for action in sorted(RUNTIME_ACTIONS)
        }
        self.handlers = supplied
        process_start_ticks = _process_start_ticks(os.getpid())
        runtime_owner = (
            f"workflow-runtime:{os.getpid()}:{process_start_ticks}:"
            f"p{_RUNTIME_PROCESS_GENERATION}:"
            f"{uuid.uuid4().hex}"
            if process_start_ticks is not None
            else (
                f"workflow-runtime:{os.getpid()}:p{_RUNTIME_PROCESS_GENERATION}:"
                f"{uuid.uuid4().hex}"
            )
        )
        self.worker = worker or DurableWorkflowWorker(
            store=store,
            handlers=worker_handlers,
            transition_services={
                project_id: binding.transition_service
                for project_id, binding in self.project_bindings.items()
            },
            worker_id=runtime_owner,
            quarantine_persist_timeout_seconds=quarantine_persist_timeout_seconds,
            quarantine_recycle_seconds=quarantine_recycle_seconds,
            phase_observer=self.record_event,
            quarantine_recycle_observer=quarantine_recycle_observer,
        )
        self._validate_enforce_ready()

    @classmethod
    def from_orchestrator(
        cls,
        orchestrator: Any,
        *,
        terminal_transition_coordinator: Any | None = None,
        handlers: Mapping[str, WorkflowActionHandler] | None = None,
        mode: str | None = None,
        state_dir: str | os.PathLike[str] | None = None,
    ) -> "WorkflowRuntime":
        """Construct one runtime from the already-created service objects."""

        project_store = orchestrator.project_store
        projects = list(project_store.list_all())
        if projects:
            project_rows = [
                (
                    str(project.id),
                    orchestrator._tracker_for_project(str(project.id)),
                    project,
                )
                for project in projects
            ]
        else:
            project_rows = [(LEGACY_PROJECT_ID, orchestrator.tracker, None)]

        configured_state_path = getattr(
            orchestrator, "_state_path", ".oompah/service_state.json"
        )
        # Restrict the accepted test/production boundary to concrete paths;
        # a MagicMock advertises ``__fspath__`` and would otherwise create a
        # directory named after the mock during bootstrap tests.
        if not isinstance(configured_state_path, (str, Path)):
            configured_state_path = ".oompah/service_state.json"
        root = (
            Path(state_dir).expanduser().resolve()
            if state_dir is not None
            else Path(configured_state_path).expanduser().resolve().parent
        )
        root.mkdir(parents=True, exist_ok=True)
        journal = TransitionJournal(str(root / "task_transitions.sqlite3"))
        store = orchestrator.workflow_job_store
        terminal_workflow = getattr(orchestrator, "terminal_audit_workflow", None)
        if terminal_workflow is None:
            from oompah.terminal_audit_workflow import TerminalAuditWorkflow

            terminal_workflow = TerminalAuditWorkflow(store)
            orchestrator.terminal_audit_workflow = terminal_workflow
        if getattr(terminal_workflow, "store", None) is not store:
            raise WorkflowRuntimeError(
                "terminal audit workflow must share the production workflow ledger"
            )

        def topology_source() -> tuple[Any, ...]:
            """Return the binding-relevant managed-project configuration."""

            current_projects = list(project_store.list_all())
            if not current_projects:
                # A legacy tracker is replaced on config reload.  Its identity
                # is deliberately part of the binding revision so enforce
                # mode restarts instead of continuing through a stale adapter.
                return ((LEGACY_PROJECT_ID, id(orchestrator.tracker)),)
            fields = (
                "id",
                "repo_path",
                "repo_url",
                "branch",
                "default_branch",
                "tracker_kind",
                "tracker_owner",
                "tracker_repo",
                "github_project_node_id",
                "forge_kind",
                "forge_base_url",
                "access_token",
                "status_actor_login",
            )
            return tuple(
                tuple(getattr(project, field, None) for field in fields)
                for project in sorted(
                    current_projects, key=lambda value: str(value.id)
                )
            )

        async def topology_change_handler() -> None:
            restart = getattr(orchestrator, "graceful_restart", None)
            if not callable(restart):
                raise WorkflowRuntimeError(
                    "workflow project bindings changed and require restart"
                )
            result = restart(request_id=f"workflow-topology:{uuid.uuid4().hex}")
            if inspect.isawaitable(result):
                await result
        configured_mode = mode
        if configured_mode is None:
            configured_mode = getattr(
                orchestrator.config, "workflow_engine_mode", "off"
            )
        if not isinstance(configured_mode, str):
            configured_mode = "off"
        configured_mode = configured_mode.strip().lower()
        if configured_mode not in {"off", "shadow", "enforce"}:
            configured_mode = "off"
        configured_domain_modes = normalize_workflow_domain_modes(
            getattr(orchestrator.config, "workflow_domain_modes", None),
            fallback=configured_mode,
        )
        configured_limit = getattr(
            orchestrator.config,
            "workflow_runtime_decision_limit",
            DEFAULT_RUNTIME_DECISION_LIMIT,
        )
        configured_batch = getattr(
            orchestrator.config,
            "workflow_runtime_batch_size",
            DEFAULT_RUNTIME_BATCH_SIZE,
        )
        configured_concurrency = getattr(
            orchestrator.config,
            "workflow_runtime_max_concurrent",
            4,
        )
        configured_control_slots = getattr(
            orchestrator.config,
            "workflow_runtime_control_reserved_slots",
            1,
        )
        if not isinstance(configured_limit, int) or isinstance(configured_limit, bool):
            configured_limit = DEFAULT_RUNTIME_DECISION_LIMIT
        if not isinstance(configured_batch, int) or isinstance(configured_batch, bool):
            configured_batch = DEFAULT_RUNTIME_BATCH_SIZE
        if not isinstance(configured_concurrency, int) or isinstance(
            configured_concurrency, bool
        ):
            configured_concurrency = 4
        if not isinstance(configured_control_slots, int) or isinstance(
            configured_control_slots, bool
        ):
            configured_control_slots = 1
        bindings: dict[str, WorkflowProjectBinding] = {}
        journals = {project_id: journal for project_id, _, _ in project_rows}

        # The source callbacks close over the binding being built.  Durable
        # implementation dispositions normally supersede the legacy running
        # map, but an exact direct-owner retirement marker is a prerequisite
        # fence: it must remain visible until its revocation effect completes.
        for project_id, tracker, project in project_rows:
            holder: dict[str, WorkflowProjectBinding] = {}

            def dispatch_enabled(*, _project_id=project_id) -> bool:
                globally_blocked = getattr(
                    orchestrator, "_dispatch_is_blocked", None
                )
                if callable(globally_blocked) and globally_blocked():
                    return False
                project_paused = getattr(orchestrator, "_is_project_paused", None)
                if callable(project_paused) and project_paused(_project_id):
                    return False
                return True

            def lifecycle_interrupted() -> bool:
                globally_blocked = getattr(
                    orchestrator, "_dispatch_is_blocked", None
                )
                return (
                    bool(globally_blocked()) if callable(globally_blocked) else False
                )

            def source(issue: Any, domain: FactDomain, *, _holder=holder) -> Any:
                legacy_value: Any = None
                legacy_sources = getattr(
                    orchestrator, "_workflow_shadow_sources", None
                )
                if callable(legacy_sources):
                    legacy_source = legacy_sources(issue).get(domain)
                    legacy_value = (
                        legacy_source(issue)
                        if callable(legacy_source)
                        else legacy_source
                    )
                    if (
                        domain is FactDomain.IMPLEMENTATION_AUTHORITY
                        and isinstance(legacy_value, Mapping)
                        and legacy_value.get("ownership_source") == "direct_owner"
                    ):
                        return legacy_value
                binding = _holder.get("binding")
                if (
                    domain is FactDomain.IMPLEMENTATION_AUTHORITY
                    and binding is not None
                ):
                    controller = binding.implementation_controller
                    if controller is not None:
                        try:
                            authority = controller.implementation_authority(issue)
                            refresh = getattr(
                                orchestrator,
                                "_refresh_durable_implementation_authority",
                                None,
                            )
                            return (
                                refresh(issue, authority)
                                if callable(refresh)
                                else authority
                            )
                        except Exception:  # evidence boundary: preserve a fact error
                            raise
                return legacy_value

            sources = {
                domain: (
                    lambda issue, domain=domain, _source=source: _source(
                        issue, domain
                    )
                )
                for domain in (
                    FactDomain.TERMINAL_AUDIT,
                    FactDomain.REVIEW_CI,
                    FactDomain.IMPLEMENTATION_AUTHORITY,
                    FactDomain.DUPLICATE_INVESTIGATION,
                    FactDomain.RETRY_BUDGET,
                    FactDomain.CONFIG,
                )
            }
            repo_path = getattr(project, "repo_path", "") if project is not None else ""

            def refresh_target(
                target: str,
                *,
                _project=project,
                _repo_path=repo_path or ".",
            ) -> str | None:
                runtime = getattr(orchestrator, "workflow_runtime", None)
                runtime_enforce = getattr(runtime, "enforce", None)
                enforce = (
                    runtime_enforce
                    if isinstance(runtime_enforce, bool)
                    else configured_mode == "enforce"
                )
                if not enforce:
                    return None
                remote_ref = f"refs/remotes/origin/{target}"
                fetched = orchestrator._run_project_network_git(
                    _project,
                    [
                        "git",
                        "fetch",
                        "--prune",
                        "origin",
                        f"+refs/heads/{target}:{remote_ref}",
                    ],
                    cwd=_repo_path,
                    timeout=60,
                )
                if fetched.returncode != 0:
                    raise WorkflowRuntimeError(
                        "authoritative target fetch failed: "
                        f"{str(fetched.stderr or '').strip()[:500]}"
                    )
                resolved = subprocess.run(
                    ["git", "rev-parse", "--verify", f"{remote_ref}^{{commit}}"],
                    cwd=_repo_path,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=10,
                )
                revision = str(resolved.stdout or "").strip().lower()
                if resolved.returncode != 0 or not re.fullmatch(
                    r"[0-9a-f]{40,64}", revision
                ):
                    raise WorkflowRuntimeError(
                        f"authoritative target {target} is unavailable after fetch"
                    )
                return revision

            landing = GitLandingCollector(
                repo_path or ".",
                project_id=project_id,
                target_refresher=refresh_target,
            )
            collector = WorkflowFactCollector(
                project_id=project_id,
                tracker=tracker,
                sources=sources,
                landing_collector=landing,
                integration_queue=getattr(orchestrator, "integration_queue", None),
            )
            # Review decisions must never consume the legacy project sweep's
            # `_reviews_cache`: runtime reconciliation happens before that
            # sweep refreshes it.  Give only the review lane a fresh,
            # project-scoped provider source so sibling domains retain their
            # existing bounded fact costs.
            review_sources = dict(sources)
            review_sources[FactDomain.REVIEW_CI] = FreshReviewFactSource(
                orchestrator,
                project_id=project_id,
            )
            review_collector = WorkflowFactCollector(
                project_id=project_id,
                tracker=tracker,
                sources=review_sources,
                landing_collector=landing,
                integration_queue=getattr(orchestrator, "integration_queue", None),
            )
            review_controller = ReviewWorkflowController(
                collector=review_collector,
                store=store,
                decision_limit=configured_limit,
            )
            epic_collector = EpicFactCollector(
                project_id=project_id,
                tracker=tracker,
                default_branch=str(
                    getattr(project, "default_branch", None)
                    or getattr(project, "branch", None)
                    or "main"
                ),
                landing_collector=landing,
                sources=sources,
            )
            epic_controller = EpicWorkflowController(
                collector=epic_collector,
                store=store,
                decision_limit=configured_limit,
            )
            forge_review_resolver = None
            repo_url = str(getattr(project, "repo_url", "") or "").strip()
            if repo_url:
                try:
                    forge_provider = detect_provider(
                        repo_url,
                        access_token=getattr(project, "access_token", None),
                    )
                    forge_repo = extract_repo_slug(repo_url)

                    def forge_review_resolver(
                        branch: str,
                        *,
                        _provider=forge_provider,
                        _repo=forge_repo,
                    ) -> Any | None:
                        return _provider.find_pr_for_branch(_repo, branch)

                except Exception:  # noqa: BLE001 - optional evidence source
                    forge_review_resolver = None
            integration_controller = IntegrationWorkflowController(
                collector=collector,
                store=store,
                landing_request_resolver=IntegrationLandingRequestResolver(
                    project_id=project_id,
                    tracker=tracker,
                    integration_queue=getattr(orchestrator, "integration_queue", None),
                    project_store=project_store,
                    workflow_store=store,
                    forge_review_resolver=forge_review_resolver,
                    landing_collector=landing,
                    parent_source_head_resolver=(
                        lambda branch, _project_id=project_id: (
                            project_store.remote_branch_head(_project_id, branch)
                        )
                    ),
                    project_default_branch=str(
                        getattr(project, "default_branch", None)
                        or getattr(project, "branch", None)
                        or "main"
                    ),
                ),
                decision_limit=configured_limit,
            )

            def workflow_transition_guard(
                intent: Any,
                _issue: Any | None = None,
                *,
                _controller=epic_controller,
                _integration_controller=integration_controller,
                _review_controller=review_controller,
                _tracker=tracker,
                _store=store,
            ) -> str | None:
                guarded_reason = str(intent.reason_code or "").strip()
                invalidate = getattr(_tracker, "invalidate_read_cache", None)
                if callable(invalidate):
                    invalidate()
                guarded_issue = _tracker.fetch_issue_detail(intent.task_id)
                if guarded_issue is None:
                    return "guarded issue is unavailable"
                if not str(getattr(guarded_issue, "project_id", None) or "").strip():
                    # Native Markdown task files omit their managed project ID.
                    # Match the normalized issue used to construct the intent
                    # before comparing its lifecycle authority projection.
                    guarded_issue = replace(
                        guarded_issue,
                        project_id=intent.project_id,
                    )
                if issue_authority_version(guarded_issue) != intent.expected_version:
                    return "task transition authority changed"
                if guarded_reason == "implementation.validation_submission":
                    validation_guard = getattr(
                        orchestrator,
                        "_validation_submission_transition_conflict",
                        None,
                    )
                    if not callable(validation_guard):
                        return "validation submission authority is unavailable"
                    return validation_guard(intent, guarded_issue)
                if not intent.precondition_revision or guarded_reason not in {
                    "terminal.immediate_target_landing_proven",
                    "epic.rebase_target_superseded",
                }:
                    return None
                if (
                    guarded_reason == "terminal.immediate_target_landing_proven"
                    and str(getattr(guarded_issue, "issue_type", "") or "")
                    .strip()
                    .lower()
                    != "epic"
                ):
                    # Review and integration both use the same terminal reason,
                    # but their evidence revisions come from different fact
                    # domains.  Resolve the immutable originating job before
                    # choosing the guard; comparing a review revision with the
                    # integration controller's revision rejects every healthy
                    # landed review and can strand it in In Review forever.
                    origin_job = None
                    try:
                        origin_job = _store.get(intent.originating_job)
                    except KeyError:
                        # Pre-ledger callers and focused transition tests retain
                        # the original integration guard. Production workflow
                        # jobs are durable and always resolve here.
                        pass
                    except Exception:
                        return "terminal workflow origin is unavailable"
                    if origin_job is not None:
                        if (
                            origin_job.project_id != intent.project_id
                            or origin_job.task_id != intent.task_id
                        ):
                            return "terminal workflow origin changed"
                        if origin_job.action == "review_terminal_stage":
                            if (
                                intent.authority
                                is not TransitionAuthority.ORCHESTRATOR
                            ):
                                return "review terminal stage requires orchestrator authority"
                            if (
                                not intent.evidence_generation
                                or origin_job.generation
                                != intent.evidence_generation
                                or origin_job.expected_evidence_revision
                                != intent.precondition_revision
                            ):
                                return "review terminal workflow authority changed"
                            review_batch = _review_controller.evaluate(
                                (guarded_issue,)
                            )
                            if len(review_batch.tasks) != 1:
                                return "review is no longer eligible for terminalization"
                            review_decision = review_batch.tasks[0].decision
                            if (
                                review_decision.evidence_revision
                                != intent.precondition_revision
                            ):
                                return "review landing evidence changed"
                            if (
                                "review_terminal_stage"
                                not in review_decision.durable_jobs
                            ):
                                return "review landing no longer authorizes terminalization"
                            return None
                        if origin_job.action != "parent_rollup_review":
                            return "terminal workflow origin no longer authorizes landing"
                    requests = _integration_controller.landing_requests_for(
                        guarded_issue
                    )
                    facts = _integration_controller.collector.collect(
                        guarded_issue.identifier,
                        landing_requests=requests,
                    )
                    decision = evaluate_task(guarded_issue, facts)
                    if decision.evidence_revision != intent.precondition_revision:
                        return "task landing evidence changed"
                    if "parent_rollup_review" not in decision.durable_jobs:
                        return "task landing no longer authorizes terminalization"
                    if issue_exact_head(guarded_issue) is None:
                        exact_landings = tuple(
                            landing
                            for landing in facts.landings
                            if landing.project_id == intent.project_id
                            and landing.state is LandingState.LANDED
                            and landing.durable
                            and landing.revision == intent.exact_head
                            and any(
                                request.source == landing.source
                                and request.target == landing.target
                                and request.revision == landing.revision
                                and request.authoritative_target
                                and request.prior is not None
                                and request.prior.durable
                                and request.prior.state is LandingState.LANDED
                                and request.prior.project_id == intent.project_id
                                and request.prior.source == landing.source
                                and request.prior.target == landing.target
                                and request.prior.revision == landing.revision
                                for request in requests
                            )
                        )
                        if len(exact_landings) != 1:
                            return "task composed landing head changed"
                    return None
                if guarded_reason == "epic.rebase_target_superseded":
                    epic_id = str(
                        getattr(guarded_issue, "parent_id", None) or ""
                    ).strip()
                    if not epic_id:
                        return "rebase helper no longer has an owning epic"
                    epic = _tracker.fetch_issue_detail(epic_id)
                else:
                    epic = guarded_issue
                if epic is None:
                    return "epic is unavailable"
                auto_close = (
                    guarded_reason
                    == "terminal.immediate_target_landing_proven"
                )
                mutable_epic_head = issue_exact_head(epic)
                if auto_close:
                    if (
                        str(getattr(epic, "issue_type", "") or "")
                        .strip()
                        .lower()
                        != "epic"
                    ):
                        return "epic auto-close target is not an epic"
                    if intent.authority != TransitionAuthority.ORCHESTRATOR:
                        return "epic auto-close requires orchestrator authority"
                    if mutable_epic_head is None:
                        if str(getattr(epic, "parent_id", None) or "").strip():
                            return (
                                "headless nested epic cannot use canonical "
                                "landing fallback"
                            )
                        if canonicalize_status(epic.state) != IN_PROGRESS:
                            return "headless root epic is not In Progress"
                # A terminal guard evaluates one exact epic while the project
                # mutation fence is held.  Do not use the persistent project
                # controller for that narrow read: ``evaluate`` replaces its
                # project-wide projection cache and would make unrelated epics
                # temporarily disappear from runtime/UI observations.
                guard_controller = EpicWorkflowController(
                    collector=_controller.collector,
                    store=_controller.store,
                    scheduler=_controller.scheduler,
                    decision_limit=_controller.decision_limit,
                )
                batch = guard_controller.evaluate((epic,), persist_evidence=False)
                if not batch.tasks:
                    return "epic is no longer eligible for guarded workflow mutation"
                evaluated = batch.tasks[0]
                decision = evaluated.decision
                if decision.evidence_revision != intent.precondition_revision:
                    return "epic workflow evidence or containment changed"
                if auto_close and EpicAction.AUTO_CLOSE.value not in decision.durable_jobs:
                    return "epic auto-close is no longer authorized"
                if auto_close and mutable_epic_head is not None:
                    if (
                        not intent.exact_head
                        or mutable_epic_head != intent.exact_head
                    ):
                        return "epic mutable landing head changed"
                elif auto_close:
                    canonical_landings = tuple(
                        landing
                        for landing in epic_immediate_target_landings(
                            evaluated.facts
                        )
                        if landing.project_id == intent.project_id
                        and landing.state is LandingState.LANDED
                        and landing.durable
                    )
                    if len(canonical_landings) != 1:
                        return "epic canonical landing authority changed"
                    if (
                        not intent.exact_head
                        or canonical_landings[0].revision != intent.exact_head
                    ):
                        return "epic canonical landing head changed"
                return None

            terminal_adapter = (
                CoordinatorTerminalAdapter(
                    terminal_transition_coordinator,
                    mutation_guard=workflow_transition_guard,
                )
                if terminal_transition_coordinator is not None
                else None
            )
            transition_service = TaskTransitionService(
                project_id=project_id,
                tracker=tracker,
                journal=journal,
                terminal_adapter=terminal_adapter,
                write_lock=lambda _project_id=project_id: (
                    project_store.project_write_lock(_project_id)
                ),
                mutation_guard=workflow_transition_guard,
                direct_owner_claim_guard=getattr(
                    orchestrator,
                    "_direct_owner_claim_transition_conflict",
                    None,
                ),
                direct_owner_retirement_guard=getattr(
                    orchestrator,
                    "_direct_owner_submission_transition_conflict",
                    None,
                ),
            )

            def terminal_audit_proof_source(
                decision: WorkDecision,
                observed: Mapping[str, Any],
                action: str,
                *,
                _project_id=project_id,
                _tracker=tracker,
            ) -> bool:
                """Re-read exact pending audit authority under its write lock."""

                lock_source = getattr(project_store, "project_write_lock", None)
                audit_store_source = getattr(orchestrator, "_audit_store", None)
                if not callable(lock_source) or not callable(audit_store_source):
                    return False
                from oompah.auditor_dispatch import AuditorDispatchLane

                with lock_source(_project_id):
                    invalidate = getattr(_tracker, "invalidate_read_cache", None)
                    if callable(invalidate):
                        invalidate()
                    current = _tracker.fetch_issue_detail(decision.task_id)
                    if current is None:
                        return False
                    if not getattr(current, "project_id", None):
                        current.project_id = _project_id
                    if canonicalize_status(current.state) != IN_VALIDATION:
                        return False
                    document = audit_store_source(current).read(
                        current.identifier
                    )
                    record = AuditorDispatchLane.pending_record(
                        document.pending_chain,
                        project_id=_project_id,
                        task_id=decision.task_id,
                    )
                    if record is None:
                        return False
                    expected = {
                        "audit_id": record.audit_id,
                        "request_state": record.request_state.value,
                        "target_state": record.target_state.value,
                        "evidence_fingerprint": (
                            record.evidence_fingerprint.digest
                        ),
                        "source_generation": record.source_generation,
                        "audit_generation": terminal_workflow.generation(record),
                    }
                    if any(observed.get(key) != value for key, value in expected.items()):
                        return False
                    return store.terminal_audit_lane_materialized(
                        project_id=_project_id,
                        task_id=decision.task_id,
                        audit_id=record.audit_id,
                        target_state=record.target_state.value,
                        evidence_fingerprint=record.evidence_fingerprint.digest,
                        audit_generation=terminal_workflow.generation(record),
                        source_generation=record.source_generation,
                        obligation_action=action,
                    )

            def terminal_audit_snapshot_proof_source(
                decision: WorkDecision,
                observed: Mapping[str, Any],
                *,
                _project_id=project_id,
                _tracker=tracker,
                _collector=collector,
            ) -> bool:
                """Recollect the exact terminal disposition at publication."""

                lock_source = getattr(project_store, "project_write_lock", None)
                source = _collector.sources.get(FactDomain.TERMINAL_AUDIT)
                if not callable(lock_source) or not callable(source):
                    return False
                with lock_source(_project_id):
                    invalidate = getattr(_tracker, "invalidate_read_cache", None)
                    if callable(invalidate):
                        invalidate()
                    current = _tracker.fetch_issue_detail(decision.task_id)
                    if current is None:
                        return False
                    if not getattr(current, "project_id", None):
                        current.project_id = _project_id
                    fresh = source(current)
                    return isinstance(fresh, Mapping) and dict(fresh) == dict(
                        observed
                    )

            def terminal_audit_lane_proof_source(
                decision: WorkDecision,
                observed: Mapping[str, Any],
                action: str | None,
                *,
                _project_id=project_id,
            ) -> bool:
                """Prove only SQLite-owned audit authority at the marker.

                Terminal metadata is fenced separately by the project's
                monotonic authority revision.  Keeping this proof store-only
                avoids a full native-tracker refresh for every retained task
                while the project mutation lock is held.
                """

                request_state = str(observed.get("request_state") or "")
                if request_state not in {"pending", "in_progress"}:
                    return True
                required_action = action
                if required_action is None:
                    terminal_actions = tuple(
                        candidate
                        for candidate in decision.durable_jobs
                        if _LIVENESS_ACTION_OWNER.get(candidate)
                        == "terminal_audit"
                    )
                    if len(terminal_actions) != 1:
                        return False
                    required_action = terminal_actions[0]
                audit_id = str(observed.get("audit_id") or "")
                target_state = str(observed.get("target_state") or "")
                evidence = str(observed.get("evidence_fingerprint") or "")
                audit_generation = str(observed.get("audit_generation") or "")
                source_generation = observed.get("source_generation")
                if (
                    not audit_id
                    or not target_state
                    or not evidence
                    or not audit_generation
                    or isinstance(source_generation, bool)
                    or not isinstance(source_generation, int)
                ):
                    return False
                return store.terminal_audit_lane_materialized(
                    project_id=_project_id,
                    task_id=decision.task_id,
                    audit_id=audit_id,
                    target_state=target_state,
                    evidence_fingerprint=evidence,
                    audit_generation=audit_generation,
                    source_generation=source_generation,
                    obligation_action=required_action,
                )

            binding = WorkflowProjectBinding(
                project_id=project_id,
                tracker=tracker,
                collector=collector,
                transition_service=transition_service,
                implementation_controller=ImplementationWorkflowController(
                    collector=collector,
                    store=store,
                    decision_limit=configured_limit,
                ),
                review_controller=review_controller,
                integration_controller=integration_controller,
                epic_collector=epic_collector,
                epic_controller=epic_controller,
                terminal_audit_workflow=terminal_workflow,
                transition_journal=journal,
                terminal_audit_proof_source=terminal_audit_proof_source,
                terminal_audit_snapshot_proof_source=(
                    terminal_audit_snapshot_proof_source
                ),
                terminal_audit_lane_proof_source=(
                    terminal_audit_lane_proof_source
                ),
                terminal_audit_publication_lock=(
                    lambda _project_id=project_id: project_store.project_write_lock(
                        _project_id
                    )
                )
                if callable(getattr(project_store, "project_write_lock", None))
                else None,
                terminal_authority_revision_source=(
                    lambda _project_id=project_id: int(
                        project_store.terminal_authority_revision(_project_id)
                    )
                )
                if callable(
                    getattr(project_store, "terminal_authority_revision", None)
                )
                else None,
                terminal_authority_changes_source=(
                    lambda revision, _project_id=project_id: (
                        project_store.terminal_authority_changes_since(
                            _project_id, revision
                        )
                    )
                )
                if callable(
                    getattr(project_store, "terminal_authority_changes_since", None)
                )
                else None,
                workflow_authority_revision_source=(
                    lambda _project_id=project_id: int(
                        project_store.workflow_authority_revision(_project_id)
                    )
                )
                if callable(
                    getattr(project_store, "workflow_authority_revision", None)
                )
                else None,
                tracker_authority_revision_source=(
                    lambda _tracker=tracker: _tracker.get_state_branch_generation()
                )
                if callable(
                    getattr(tracker, "get_state_branch_generation", None)
                )
                else None,
                tracker_publication_revision_source=(
                    lambda _tracker=tracker: _tracker.get_publication_revision()
                )
                if callable(
                    getattr(tracker, "get_publication_revision", None)
                )
                else None,
                tracker_publication_changes_source=(
                    lambda revision, _tracker=tracker: (
                        _tracker.publication_task_changes_since(revision)
                    )
                )
                if callable(
                    getattr(tracker, "publication_task_changes_since", None)
                )
                else None,
                tracker_authority_changes_source=(
                    lambda expected, current, _tracker=tracker: (
                        _tracker.task_authority_changes_between(expected, current)
                    )
                )
                if callable(
                    getattr(tracker, "task_authority_changes_between", None)
                )
                else None,
                tracker_terminal_authority_changes_source=(
                    lambda expected, current, _tracker=tracker: (
                        _tracker.terminal_metadata_changes_between(expected, current)
                    )
                )
                if callable(
                    getattr(tracker, "terminal_metadata_changes_between", None)
                )
                else None,
                dispatch_enabled=dispatch_enabled,
                lifecycle_interrupted=lifecycle_interrupted,
            )
            holder["binding"] = binding
            bindings[project_id] = binding

        registered_handlers = handlers
        handler_coverage: dict[str, set[str]] | None = None
        if registered_handlers is None:
            static_handlers = getattr(
                orchestrator, "workflow_action_handlers", None
            )
            if static_handlers is not None and not isinstance(static_handlers, Mapping):
                raise WorkflowRuntimeError(
                    "workflow action handlers must be a mapping"
                )

            # Domain factories are independent composition units.  Treating the
            # generic factory as an alternative to a domain factory made the
            # final OOMPAH-804 domain disappear as soon as any sibling domain
            # registered itself.  Compose every advertised factory instead and
            # make ownership collisions an initialization error.
            factories: list[tuple[str, WorkflowRuntimeHandlerFactory]] = []
            generic = getattr(orchestrator, "workflow_action_handler_factory", None)
            if callable(generic):
                factories.append(("generic", generic))
            configured_factories = getattr(
                orchestrator, "workflow_action_handler_factories", ()
            )
            if configured_factories:
                if not isinstance(configured_factories, Sequence):
                    raise WorkflowRuntimeError(
                        "workflow action handler factories must be a sequence"
                    )
                for index, factory in enumerate(configured_factories):
                    if not callable(factory):
                        raise WorkflowRuntimeError(
                            "workflow action handler factories must be callable"
                        )
                    factories.append((f"configured[{index}]", factory))
            for domain in sorted(_DOMAIN_ACTIONS):
                factory = getattr(
                    orchestrator,
                    f"workflow_{domain}_action_handler_factory",
                    None,
                )
                if callable(factory):
                    factories.append((domain, factory))

            project_handlers: dict[str, dict[str, WorkflowActionHandler]] = {}
            owners: dict[tuple[str, str], str] = {}
            for action, handler in dict(static_handlers or {}).items():
                if action not in RUNTIME_ACTIONS:
                    raise WorkflowRuntimeError(
                        "workflow action handlers contained unknown action: "
                        f"{action}"
                    )
                for binding in bindings.values():
                    project_handlers.setdefault(action, {})[binding.project_id] = handler
                    owners[(binding.project_id, action)] = "static"

            for binding in bindings.values():
                for factory_name, factory in factories:
                    produced = factory(binding)
                    if not isinstance(produced, Mapping):
                        raise WorkflowRuntimeError(
                            f"workflow {factory_name} action handler factory "
                            "must return a mapping"
                        )
                    unknown = set(produced) - RUNTIME_ACTIONS
                    if unknown:
                        raise WorkflowRuntimeError(
                            f"workflow {factory_name} action handler factory "
                            "returned unknown actions: "
                            + ", ".join(sorted(unknown))
                        )
                    for action, handler in produced.items():
                        identity = (binding.project_id, action)
                        previous = owners.get(identity)
                        if previous is not None:
                            raise WorkflowRuntimeError(
                                "duplicate workflow action ownership for "
                                f"{binding.project_id}:{action}: "
                                f"{previous}, {factory_name}"
                            )
                        owners[identity] = factory_name
                        project_handlers.setdefault(action, {})[
                            binding.project_id
                        ] = handler

            if project_handlers:
                registered_handlers = {
                    action: _ProjectRoutedHandler(
                        action,
                        routed,
                        project_enabled={
                            project_id: binding.dispatch_enabled
                            for project_id, binding in bindings.items()
                            if binding.dispatch_enabled is not None
                        },
                    )
                    for action, routed in project_handlers.items()
                }
                handler_coverage = {
                    action: set(routed) for action, routed in project_handlers.items()
                }

        def transition_observer(job: Any) -> None:
            orchestrator.event_bus.emit(
                EventType.ISSUE_STATE_CHANGED,
                {
                    "project_id": str(job.project_id),
                    "identifier": str(job.task_id),
                    "change": "durable-workflow-transition-applied",
                },
            )
            # A committed transition is already part of the exact published
            # workflow cut.  Preserve its UI notification while keeping the
            # scheduler wake on the admission-only lane; the paired effect
            # completion callback then coalesces onto this same event key
            # instead of contaminating the burst with an ordinary world scan.
            orchestrator._request_workflow_batch_continuation(
                reason="workflow_transition_applied"
            )

        def effect_completion_observer(result: Any) -> None:
            # Completion is the replenishment edge for detached execution.
            # Idle admission probes are impossible because the runtime claims
            # before spawning, so every callback represents durable progress
            # and may safely request one coalesced admission-only pass.
            # Retained ownership is removed before this callback, so publish
            # the matching lightweight state projection before scheduling
            # more admission. Exception/cancellation cleanup deliberately
            # carries no WorkflowRunResult but needs the same convergence.
            try:
                orchestrator._notify_state_only()
            except Exception:  # noqa: BLE001 - admission wake is flow-critical
                logger.exception(
                    "Failed to publish durable workflow completion state"
                )
            orchestrator._request_workflow_batch_continuation(
                reason="workflow_effect_completed"
            )

        async def quarantine_recycle_observer(job: Any) -> None:
            """Coalesce one durable stuck-call recycle into service lifecycle."""

            restart = getattr(orchestrator, "graceful_restart", None)
            if not callable(restart):
                raise WorkflowRuntimeError(
                    "quarantined workflow call requires a service restart"
                )
            request_id = f"workflow-quarantine:{getattr(job, 'job_id', 'unknown')}"
            result = restart(request_id=request_id)
            if inspect.isawaitable(result):
                await result

        def publish_projection(
            decisions: Sequence[Any],
            generation: int,
            *,
            live_keys: set[tuple[str, str]],
            publication_epoch: int,
            unavailable_projects: set[str],
            scan_complete: bool,
            incomplete_keys: set[tuple[str, str]],
            incomplete_reason: str | None,
        ) -> Any:
            return orchestrator._publish_work_decisions(
                list(decisions),
                generation,
                source="controller",
                live_keys=live_keys,
                publication_epoch=publication_epoch,
                failed_projects=unavailable_projects,
                scan_complete=scan_complete,
                incomplete_keys=incomplete_keys,
                incomplete_reason=incomplete_reason,
                defer_memory=True,
            )

        runtime = cls(
            project_bindings=bindings,
            store=store,
            journals=journals,
            mode=configured_mode,
            domain_modes=configured_domain_modes,
            rollout_require_qualification=bool(
                getattr(
                    orchestrator.config,
                    "workflow_rollout_require_qualification",
                    False,
                )
            ),
            rollout_min_shadow_sweeps=int(
                getattr(
                    orchestrator.config,
                    "workflow_rollout_min_shadow_sweeps",
                    3,
                )
            ),
            rollout_min_shadow_seconds=int(
                getattr(
                    orchestrator.config,
                    "workflow_rollout_min_shadow_seconds",
                    300,
                )
            ),
            handlers=registered_handlers,
            decision_limit=configured_limit,
            batch_size=configured_batch,
            max_concurrent=configured_concurrency,
            control_reserved_slots=configured_control_slots,
            handler_coverage=handler_coverage,
            abandoned_lease_owners=getattr(
                orchestrator, "workflow_abandoned_lease_owners", ()
            ),
            topology_signature=topology_source(),
            topology_source=topology_source,
            topology_change_handler=topology_change_handler,
            transition_observer=transition_observer,
            effect_completion_observer=effect_completion_observer,
            quarantine_recycle_observer=quarantine_recycle_observer,
            quarantine_persist_timeout_seconds=float(
                getattr(
                    orchestrator.config,
                    "workflow_quarantine_persist_timeout_seconds",
                    5,
                )
            ),
            quarantine_recycle_seconds=float(
                getattr(
                    orchestrator.config,
                    "workflow_quarantine_recycle_seconds",
                    60,
                )
            ),
            liveness_controller=getattr(
                orchestrator, "workflow_controller", None
            ),
            persist_liveness_state=getattr(
                orchestrator, "_persist_workflow_liveness_state", None
            ),
            projection_publisher=(
                publish_projection
                if callable(
                    getattr(orchestrator, "_publish_work_decisions", None)
                )
                else None
            ),
            projection_epoch_source=(
                (lambda: int(orchestrator._work_decision_publication_epoch))
                if callable(
                    getattr(orchestrator, "_publish_work_decisions", None)
                )
                and hasattr(orchestrator, "_work_decision_publication_epoch")
                else None
            ),
        )
        runtime._integration_maintenance_scheduler = getattr(
            orchestrator,
            "schedule_workflow_integration_maintenance",
            None,
        )
        return runtime

    @property
    def enforce(self) -> bool:
        return self.mode == "enforce"

    @property
    def restart_reconstruction_pending(self) -> bool:
        """Whether enforce mode still owes its first authoritative world cut."""

        if not self.enforce or self.liveness_controller is None:
            return False
        try:
            return bool(
                self.liveness_controller.liveness_snapshot()
                .restart_reconstruction_pending
            )
        except Exception:  # noqa: BLE001 - launch admission must fail closed
            logger.exception(
                "Workflow restart reconstruction authority is unavailable"
            )
            return True

    def _bind_policy_epoch(self, policy_epoch: str) -> None:
        """Bind universal and owning schedulers to one semantic policy cut."""

        controller = self.liveness_controller
        if controller is not None:
            controller.scheduler.configure_policy_epoch(policy_epoch)
        for binding in self.project_bindings.values():
            for domain_controller in (
                binding.implementation_controller,
                binding.review_controller,
                binding.integration_controller,
                binding.epic_controller,
            ):
                scheduler = getattr(domain_controller, "scheduler", None)
                if scheduler is not None:
                    scheduler.configure_policy_epoch(policy_epoch)

    def _capture_liveness_policy(self) -> LivenessPolicy | None:
        """Capture and bind one immutable policy for a complete runtime pass."""

        controller = self.liveness_controller
        if controller is None:
            return None
        with controller.liveness_observation_lock:
            policy = controller.liveness_policy
            self._bind_policy_epoch(policy.epoch)
            return policy

    def _validate_enforce_ready(self) -> None:
        if not self.enforce:
            return
        incomplete_bindings: list[str] = []
        for project_id, binding in sorted(self.project_bindings.items()):
            missing = [
                name
                for name, controller in (
                    ("implementation", binding.implementation_controller),
                    ("review", binding.review_controller),
                    ("integration", binding.integration_controller),
                    ("epic", binding.epic_controller),
                    ("terminal_audit", binding.terminal_audit_workflow),
                )
                if controller is None
            ]
            if missing:
                incomplete_bindings.append(f"{project_id}({','.join(missing)})")
        if incomplete_bindings:
            raise WorkflowRuntimeError(
                "enforce mode requires every durable domain binding: "
                + ", ".join(incomplete_bindings)
            )
        missing_handlers = [
            f"{project_id}:{action}"
            for project_id in sorted(self.project_bindings)
            for action in sorted(RUNTIME_ACTIONS)
            if project_id not in self._handler_coverage.get(action, ())
        ]
        if missing_handlers:
            raise WorkflowRuntimeError(
                "enforce mode requires total project-routed handler coverage: "
                + ", ".join(missing_handlers)
            )

    def set_mode(self, mode: str) -> None:
        normalized = str(mode or "off").strip().lower()
        if normalized not in {"off", "shadow", "enforce"}:
            raise ValueError("workflow runtime mode must be off, shadow, or enforce")
        with self._lock:
            if self._started and normalized != self.mode:
                raise WorkflowRuntimeError(
                    "workflow runtime mode changes require a graceful service restart"
                )
            previous = self.mode
            self.mode = normalized
            try:
                self._validate_enforce_ready()
            except Exception:
                self.mode = previous
                raise

    def set_domain_modes(self, modes: Mapping[str, str]) -> None:
        """Validate a rollout-map reload without transferring live authority."""

        normalized = normalize_workflow_domain_modes(modes)
        aggregate = aggregate_workflow_domain_mode(normalized)
        with self._lock:
            if aggregate != self.mode:
                raise WorkflowRuntimeError(
                    "workflow domain modes do not match the aggregate runtime mode"
                )
            if self._started and normalized != self.domain_modes:
                raise WorkflowRuntimeError(
                    "workflow domain mode changes require a graceful service restart"
                )
            self.domain_modes = normalized

    @property
    def legacy_lifecycle_writers_enabled(self) -> bool:
        """Deprecated compatibility projection; legacy writers stay retired.

        Rollout modes control durable evaluation and effects.  They no longer
        transfer authority back to process-local reconcilers, so this value is
        false in ``off`` and ``shadow`` as well as ``enforce``.
        """

        return False

    @property
    def started(self) -> bool:
        return self._started

    @staticmethod
    def _runtime_owner_is_dead(owner: str) -> bool:
        match = _RUNTIME_OWNER_PATTERN.fullmatch(owner)
        if match is None:
            return False
        pid = int(match.group("pid"))
        expected_start = match.group("start_ticks")
        expected_process_generation = match.group("process_generation")
        observed_start = _process_start_ticks(pid)
        if (
            expected_start is not None
            and observed_start is not None
            and int(expected_start) != observed_start
        ):
            # PID reuse is a dead owner generation, never a live lease.
            return True
        if (
            pid == os.getpid()
            and expected_process_generation is not None
            and expected_process_generation != _RUNTIME_PROCESS_GENERATION
        ):
            # ``exec`` preserves the PID and Linux start tick.  The module boot
            # generation is therefore the remaining proof that the old
            # runtime image (and every thread it owned) no longer exists.
            return True
        if observed_start is not None:
            return False
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            return False
        return False

    def _recover_runtime_jobs(self) -> dict[str, int]:
        """Recover only expired or proven-dead durable-domain ownership."""

        expired = 0
        for project_id in self.project_bindings:
            expired += self.store.recover_expired(
                project_id=project_id,
                actions=tuple(RUNTIME_ACTIONS),
                limit=self.batch_size,
            )
        abandoned = 0
        seen: set[tuple[str, str, str, str]] = set()
        running = self.store.list_jobs(
            states=("running",), limit=max(self.batch_size, self.decision_limit)
        )
        for job in running:
            owner = str(job.lease_owner or "")
            identity = (owner, job.project_id, job.action, job.phase)
            if identity in seen or job.action not in RUNTIME_ACTIONS:
                continue
            if (
                owner not in self._abandoned_lease_owners
                and not self._runtime_owner_is_dead(owner)
            ):
                continue
            seen.add(identity)
            abandoned += self.store.recover_abandoned(
                lease_owner=owner,
                project_id=job.project_id,
                actions=(job.action,),
                phases=(job.phase,),
                limit=self.batch_size,
            )
        return {
            "expired": expired,
            "abandoned": abandoned,
            "recovered": expired + abandoned,
        }

    def _rearm_legacy_standalone_capacity_exhaustion(self) -> int:
        """Migrate exact legacy capacity waits to non-substantive retries."""

        rearmed = 0
        for project_id, binding in self.project_bindings.items():
            handler = self.handlers.get("standalone_delivery")
            routed = getattr(handler, "handlers", None)
            project_handler = (
                routed.get(project_id)
                if isinstance(routed, Mapping)
                else handler
            )
            backend = (
                getattr(project_handler, "backend", None)
                if project_handler is not None
                else None
            )
            proves_capacity_wait = getattr(
                backend, "legacy_exhaustion_is_capacity_wait", None
            )
            if not callable(proves_capacity_wait) or not binding.enabled:
                continue
            candidates = self.store.list_jobs(
                project_id=project_id,
                states=("exhausted",),
                actions=("standalone_delivery",),
                limit=self.decision_limit,
                newest_first=True,
            )
            current_by_task: dict[str, set[str]] = {}
            for job in candidates:
                current_ids = current_by_task.setdefault(
                    job.task_id,
                    {
                        current.job_id
                        for current in self.store.current_exhausted_jobs(
                            project_id=project_id,
                            task_id=job.task_id,
                        )
                    },
                )
                if job.job_id not in current_ids:
                    continue
                if not proves_capacity_wait(job):
                    continue
                self.store.rearm_exhausted_job(
                    job.job_id,
                    generation=job.generation,
                    phase="intent",
                    reason="legacy standalone review-capacity wait",
                )
                rearmed += 1
        return rearmed

    async def start(self) -> dict[str, int]:
        """Run integrity checks and recover ownership left by a crash."""

        with self._lock:
            if self._started:
                return dict(self._last_reconcile.get("recovery", {}))
            self._draining = False
        self.store.integrity_check()
        self.store.prepare_rollout(
            self.domain_modes,
            require_qualification=self.rollout_require_qualification,
            min_shadow_sweeps=self.rollout_min_shadow_sweeps,
            min_shadow_seconds=self.rollout_min_shadow_seconds,
        )
        for journal in set(self.journals.values()):
            journal.integrity_check()
        recovery = (
            self._recover_runtime_jobs()
            if self.enforce
            else {"expired": 0, "abandoned": 0, "recovered": 0}
        )
        legacy_capacity_rearmed = (
            self._rearm_legacy_standalone_capacity_exhaustion()
            if self.enforce
            else 0
        )
        if legacy_capacity_rearmed:
            recovery["legacy_standalone_capacity_rearmed"] = (
                legacy_capacity_rearmed
            )
        with self._lock:
            self._started = True
            self._last_reconcile = {"recovery": dict(recovery)}
        logger.info(
            "Durable workflow runtime started mode=%s projects=%d recovered=%d",
            self.mode,
            len(self.project_bindings),
            recovery["recovered"],
        )
        return recovery

    def _issues(self, binding: WorkflowProjectBinding) -> list[Any]:
        operation = getattr(binding.tracker, "fetch_all_issues_enriched", None)
        if not callable(operation):
            operation = binding.tracker.fetch_all_issues
        issues = operation()
        if not isinstance(issues, Sequence):
            raise WorkflowRuntimeError(
                f"tracker for project {binding.project_id!r} returned a non-sequence"
            )
        scoped: list[Any] = []
        for issue in issues:
            issue_project = str(getattr(issue, "project_id", None) or "")
            if issue_project and issue_project != binding.project_id:
                continue
            # Tracker-native rows do not all persist the managed project ID.
            # Normalize it before any controller hashes authority evidence so
            # the production handler and transition service observe the same
            # project-scoped revision when they re-fetch the task.
            if not issue_project:
                issue.project_id = binding.project_id
            scoped.append(issue)
        return scoped

    def _issues_with_authority(
        self, binding: WorkflowProjectBinding
    ) -> tuple[list[Any], str | None, str | None]:
        """Fetch one project corpus with its exact tracker generation.

        Native trackers expose an atomic list+generation read.  Using it once
        per reconciliation both avoids per-task refreshes and lets final
        publication reject any owner/status mutation that raced the scan.
        A native tracker whose state branch is explicitly disabled uses a
        grouped corpus digest that is checked with one final project-wide
        refresh. Other unversioned trackers fail closed in enforce mode;
        publishing general lifecycle decisions without status authority is
        not safe.
        """

        tracker = binding.tracker
        operation = getattr(tracker, "fetch_all_issues_with_generation", None)
        if (
            getattr(tracker, "supports_generation_bound_reads", False) is True
            and callable(operation)
        ):
            raw_issues, generation = operation()
            if not isinstance(raw_issues, Sequence):
                raise WorkflowRuntimeError(
                    f"tracker for project {binding.project_id!r} returned a "
                    "non-sequence"
                )
            # Reuse the normal project-scope normalization without performing
            # another tracker fetch.
            scoped: list[Any] = []
            for issue in raw_issues:
                issue_project = str(getattr(issue, "project_id", None) or "")
                if issue_project and issue_project != binding.project_id:
                    continue
                if not issue_project:
                    issue.project_id = binding.project_id
                scoped.append(issue)
            normalized_generation = (
                generation.strip() if isinstance(generation, str) else ""
            )
            unavailable = (
                not normalized_generation
                or normalized_generation == "unavailable"
                or normalized_generation.startswith("unavailable:")
            )
            if unavailable:
                if getattr(tracker, "state_branch_enabled", False) is True:
                    raise WorkflowRuntimeError(
                        "generation-bound tracker returned no authority revision"
                    )
                return (
                    scoped,
                    self._tracker_corpus_authority_digest(scoped),
                    "legacy_digest",
                )
            return scoped, normalized_generation, "generation"
        if self.enforce:
            raise WorkflowRuntimeError(
                "tracker does not provide generation-bound publication authority"
            )
        return self._issues(binding), None, None

    @staticmethod
    def _authoritative_issue_index(issues: Sequence[Any]) -> dict[str, Any]:
        """Index one project corpus by canonical tracker identity aliases.

        Native task lookup is case-insensitive.  Dependency facts must use the
        same semantics without scanning the corpus per edge, while rejecting
        two rows that collapse to one canonical alias.
        """

        indexed: dict[str, Any] = {}
        for issue in issues:
            aliases = {
                str(getattr(issue, "identifier", "") or "").strip(),
                str(getattr(issue, "id", "") or "").strip(),
            }
            for alias in aliases - {""}:
                canonical_alias = alias.casefold()
                existing = indexed.get(canonical_alias)
                if existing is not None and existing is not issue:
                    raise WorkflowRuntimeError(
                        "tracker authority contains an ambiguous task identity"
                    )
                indexed[canonical_alias] = issue
        return indexed

    @staticmethod
    def _authoritative_children_index(
        issues: Sequence[Any],
    ) -> dict[str, tuple[Any, ...]]:
        """Index direct containment once for an authoritative project cut."""

        indexed: dict[str, dict[str, Any]] = {}
        for issue in issues:
            parent_id = str(getattr(issue, "parent_id", "") or "").strip()
            identifier = str(getattr(issue, "identifier", "") or "").strip()
            if not parent_id or not identifier:
                continue
            indexed.setdefault(parent_id.casefold(), {})[identifier.casefold()] = issue
        return {
            parent_id: tuple(
                child_by_id[identifier]
                for identifier in sorted(child_by_id)
            )
            for parent_id, child_by_id in indexed.items()
        }

    @staticmethod
    def _dependency_target_identities(
        issues: Sequence[Any],
        authoritative_issues: Mapping[str, Any],
    ) -> tuple[frozenset[str], bool]:
        """Return canonical dependency-target aliases and ambiguity state."""

        targets: set[str] = set()
        ambiguous = False
        for issue in issues:
            blockers = (
                *tuple(getattr(issue, "blocked_by", ()) or ()),
                *tuple(getattr(issue, "start_blocked_by", ()) or ()),
            )
            for blocker in blockers:
                reference = str(
                    getattr(blocker, "identifier", None)
                    or getattr(blocker, "id", None)
                    or ""
                ).strip()
                if not reference:
                    ambiguous = True
                    continue
                target = authoritative_issues.get(reference.casefold())
                if target is None:
                    # A missing or project-filtered row cannot prove whether a
                    # concurrent task delta changes this dependency edge.
                    ambiguous = True
                    continue
                aliases = {
                    str(getattr(target, "identifier", "") or "").strip(),
                    str(getattr(target, "id", "") or "").strip(),
                } - {""}
                if not aliases:
                    ambiguous = True
                    continue
                targets.update(alias.casefold() for alias in aliases)
        return frozenset(targets), ambiguous

    @staticmethod
    def _tracker_corpus_authority_digest(issues: Sequence[Any]) -> str:
        """Return a stable digest for an explicitly legacy native corpus."""

        rows: list[dict[str, Any]] = []
        for issue in issues:
            serializer = getattr(issue, "to_dict", None)
            if callable(serializer):
                raw = serializer()
            elif hasattr(issue, "__dataclass_fields__"):
                raw = asdict(issue)
            else:
                raw = vars(issue)
            rows.append(
                {
                    "identifier": str(getattr(issue, "identifier", "")),
                    "value": raw,
                }
            )
        rows.sort(key=lambda row: row["identifier"])
        encoded = json.dumps(
            rows,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _remember(self, batch: Any) -> None:
        with self._lock:
            for item in getattr(batch, "tasks", ()):
                decision = item.decision
                self._latest_decisions[
                    (decision.project_id, decision.task_id)
                ] = decision

    def _replace_project_decisions(
        self,
        project_id: str,
        batches: Sequence[Any],
        *,
        exclude_identities: set[tuple[str, str]] | None = None,
    ) -> dict[tuple[str, str], Any]:
        """Atomically publish one project's complete in-memory decision cut."""

        excluded_keys = exclude_identities or set()
        with self._lock:
            previous = {
                key: decision
                for key, decision in self._latest_decisions.items()
                if key[0] == project_id
            }
            retained = {
                key: decision
                for key, decision in self._latest_decisions.items()
                if key[0] != project_id
            }
            for batch in batches:
                for item in getattr(batch, "tasks", ()):
                    decision = item.decision
                    identity = (decision.project_id, decision.task_id)
                    if identity not in excluded_keys:
                        retained[identity] = decision
            self._latest_decisions = retained
            return previous

    def _publish_runtime_projection(
        self,
        decisions: Sequence[WorkDecision],
        *,
        authoritative_project_ids: Sequence[str],
        exclude_identities: set[tuple[str, str]] | None = None,
    ) -> None:
        """Replace successful projects with one domain-owned projection cut."""

        projects = set(authoritative_project_ids)
        excluded_keys = exclude_identities or set()
        with self._lock:
            retained = {
                key: decision
                for key, decision in self._latest_decisions.items()
                if key[0] not in projects
            }
            retained.update(
                {
                    (decision.project_id, decision.task_id): decision
                    for decision in decisions
                    if decision.project_id in projects
                    and (decision.project_id, decision.task_id) not in excluded_keys
                }
            )
            self._latest_decisions = retained

    @staticmethod
    def _add_projection(
        projections: dict[tuple[str, str], WorkDecision],
        decision: WorkDecision,
        *,
        domain: str,
    ) -> None:
        identity = (decision.project_id, decision.task_id)
        previous = projections.get(identity)
        if previous is not None and (
            previous.decision_revision != decision.decision_revision
        ):
            raise WorkflowRuntimeError(
                "conflicting owning-domain projections for "
                f"{decision.project_id}/{decision.task_id}: {domain}"
            )
        projections[identity] = decision

    def _domain_projection_and_proofs(
        self,
        prepared: Sequence[Mapping[str, Any]],
        reconciled: Sequence[tuple[Mapping[str, Any], str, Any, Any, Any]],
        observation: ControllerObservation,
        *,
        snapshot_generation: int,
        workflow_facts: Mapping[tuple[str, str], WorkflowFacts],
    ) -> tuple[
        tuple[WorkDecision, ...],
        dict[tuple[str, str], set[str]],
        dict[tuple[str, str], DecisionLivenessFacts],
    ]:
        """Build the public cut and prove actions through their owning lanes.

        The universal pass explains every task but is not a scheduler.  A
        durable obligation is materialized only when the controller that owns
        that action published its own exact decision revision and durable job.
        """

        projections: dict[tuple[str, str], WorkDecision] = {}
        proven: dict[tuple[str, str], set[str]] = {}
        live_identities = set(observation.expected_identities)
        projection_facts: dict[
            tuple[str, str], DecisionLivenessFacts
        ] = {}
        for _item, domain, controller, batch, result in reconciled:
            for task_decision in batch.tasks:
                decision = task_decision.decision
                if (decision.project_id, decision.task_id) not in live_identities:
                    # Owning domains may schedule direct terminal maintenance,
                    # but canonical liveness accepts only the active
                    # non-terminal topology represented by this observation.
                    continue
                self._add_projection(projections, decision, domain=domain)
                projection_facts[
                    (decision.project_id, decision.task_id)
                ] = DecisionLivenessFacts.from_workflow_facts(
                    decision, task_decision.facts
                )
                owned_actions = {
                    action
                    for action in decision.durable_jobs
                    if _LIVENESS_ACTION_OWNER.get(action) == domain
                }
                if not owned_actions or not result.snapshot_accepted:
                    continue
                cursor = self.store.schedule_cursor(
                    project_id=decision.project_id,
                    task_id=decision.task_id,
                )
                if (
                    cursor is None
                    or cursor.snapshot_generation != snapshot_generation
                    or cursor.decision_revision
                    != controller.scheduler.decision_revision(decision)
                    or not cursor.materialized
                ):
                    continue
                schedules, jobs = controller.scheduler._materialized_totals(
                    (decision,)
                )
                if schedules == 1 and jobs == len(decision.durable_jobs):
                    proven.setdefault(
                        (decision.project_id, decision.task_id), set()
                    ).update(owned_actions)

        for item in prepared:
            implementation_batch = item["implementation_batch"]
            for task_decision in implementation_batch.tasks:
                decision = task_decision.decision
                identity = (decision.project_id, decision.task_id)
                if identity not in live_identities:
                    continue
                if identity in projections:
                    # A status-selected implementation candidate can evaluate
                    # to an integration-owned maintenance handoff.  The
                    # specialized managed domain remains authoritative.
                    continue
                self._add_projection(
                    projections, decision, domain="implementation"
                )
                projection_facts[
                    identity
                ] = DecisionLivenessFacts.from_workflow_facts(
                    decision, task_decision.facts
                )
                for action in decision.durable_jobs:
                    if _LIVENESS_ACTION_OWNER.get(action) != "implementation":
                        continue
                    source_revision = (
                        item["binding"]
                        .implementation_controller.scheduler.decision_revision(
                            decision
                        )
                    )
                    if self.store.event_lane_materialized(
                        project_id=decision.project_id,
                        task_id=decision.task_id,
                        ordering_namespace=IMPLEMENTATION_ORDERING_NAMESPACE,
                        scheduling_lane=FACT_IMPLEMENTATION_LANE,
                        source_revision=source_revision,
                        actions=(action,),
                    ) or self.store.protected_event_lane_materialized(
                        project_id=decision.project_id,
                        task_id=decision.task_id,
                        ordering_namespace=IMPLEMENTATION_ORDERING_NAMESPACE,
                        source_revision=source_revision,
                        scheduling_lanes=(IMPERATIVE_IMPLEMENTATION_LANE,),
                        actions=tuple(IMPLEMENTATION_ACTIONS),
                    ):
                        proven.setdefault(
                            (decision.project_id, decision.task_id), set()
                        ).add(action)

        # Some statuses are explanatory-only and have no specialized domain
        # controller.  Fill only those gaps; never replace an owning domain's
        # decision with the universal controller's independently collected
        # revision.
        for decision in observation.decisions:
            identity = (decision.project_id, decision.task_id)
            if (
                decision.reason_code == "retry.exhausted"
                and decision.disposition is TaskDisposition.ACTION_REQUIRED
            ):
                # Current durable exhaustion is a cross-domain liveness
                # invariant.  It must override an owning domain's otherwise
                # normal retry projection; otherwise one publication cut can
                # report actionable exhaustion and informational retry for
                # the same task.
                projections[identity] = decision
                projection_facts[identity] = observation.decision_facts.get(
                    identity, DecisionLivenessFacts()
                )
                proven.pop(identity, None)
            elif identity not in projections:
                projections[identity] = decision
                projection_facts[identity] = observation.decision_facts.get(
                    identity, DecisionLivenessFacts()
                )
        bindings_by_project = {
            str(item["project_id"]): item["binding"] for item in prepared
        }
        for identity, decision in projections.items():
            terminal_actions = {
                action
                for action in decision.durable_jobs
                if _LIVENESS_ACTION_OWNER.get(action) == "terminal_audit"
            }
            if not terminal_actions:
                continue
            facts = workflow_facts.get(identity)
            terminal = (
                facts.fact(FactDomain.TERMINAL_AUDIT)
                if isinstance(facts, WorkflowFacts)
                else None
            )
            value = (
                terminal.value
                if terminal is not None
                and terminal.state is FactState.KNOWN
                and isinstance(terminal.value, Mapping)
                else None
            )
            if value is None or str(value.get("request_state") or "") not in {
                "pending",
                "in_progress",
            }:
                continue
            binding = bindings_by_project.get(decision.project_id)
            proof_source = getattr(
                binding, "terminal_audit_proof_source", None
            )
            if not callable(proof_source):
                raise WorkflowRuntimeError(
                    "terminal-audit authority proof is unavailable"
                )
            try:
                materialized = bool(
                    proof_source(decision, value, next(iter(terminal_actions)))
                ) if len(terminal_actions) == 1 else False
            except Exception:  # noqa: BLE001 - proof failure is incomplete
                logger.exception(
                    "Terminal-audit liveness proof failed for %s/%s",
                    decision.project_id,
                    decision.task_id,
                )
                materialized = False
            if materialized:
                proven.setdefault(identity, set()).update(terminal_actions)
        return (
            tuple(projections[key] for key in sorted(projections)),
            proven,
            projection_facts,
        )

    def _liveness_reconciliation(
        self,
        observation: ControllerObservation,
        *,
        snapshot_generation: int,
        domain_results: Sequence[WorkflowReconcileResult],
        proven_actions: Mapping[tuple[str, str], set[str]],
    ) -> WorkflowReconcileResult:
        """Prove every universal durable obligation through its exact owner."""

        required: list[tuple[WorkDecision, tuple[str, ...]]] = []
        jobs_materialized = schedules_materialized = 0
        for decision in observation.decisions:
            actions = tuple(
                action
                for action in decision.durable_jobs
                if _LIVENESS_ACTION_OWNER.get(action) != "excluded"
            )
            if not actions:
                continue
            required.append((decision, actions))
            current = proven_actions.get(
                (decision.project_id, decision.task_id), set()
            )
            materialized = sum(action in current for action in actions)
            jobs_materialized += materialized
            schedules_materialized += int(materialized == len(actions))
        return WorkflowReconcileResult(
            snapshot_generation=snapshot_generation,
            snapshot_accepted=True,
            decisions_seen=len(observation.decisions),
            decisions_applied=len(observation.decisions),
            stale_rejected=sum(item.stale_rejected for item in domain_results),
            jobs_created=sum(item.jobs_created for item in domain_results),
            jobs_replayed=sum(item.jobs_replayed for item in domain_results),
            jobs_superseded=sum(item.jobs_superseded for item in domain_results),
            jobs_required=sum(len(actions) for _decision, actions in required),
            jobs_materialized=jobs_materialized,
            schedules_required=len(required),
            schedules_materialized=schedules_materialized,
            truncated=(
                observation.truncated
                or any(item.truncated for item in domain_results)
            ),
        )

    def _restore_project_decisions(
        self,
        project_id: str,
        previous: Mapping[tuple[str, str], Any],
    ) -> None:
        with self._lock:
            retained = {
                key: decision
                for key, decision in self._latest_decisions.items()
                if key[0] != project_id
            }
            retained.update(previous)
            self._latest_decisions = retained

    @staticmethod
    def _scope_domain_decisions(
        domain: str,
        batch: Any,
        allowed_actions: Sequence[str],
    ) -> Any:
        """Keep one managed batch inside its durable action ownership.

        ``evaluate_task`` may return an explicitly unowned refresh hint when
        the task list and its freshly collected task fact straddle a tracker
        update.  The unified runtime itself provides the next authoritative
        scan, so materializing that hint in a managed domain would be both
        ownerless and incorrect.  Drop only actions registered to ``none``;
        an action owned by another domain (or an unknown action) remains a
        composition error.
        """

        allowed = frozenset(allowed_actions)
        scoped_tasks = []
        changed = False
        for decision in batch.decisions:
            unknown = set(decision.durable_jobs) - allowed
            forbidden = {
                action
                for action in unknown
                if _LIVENESS_ACTION_OWNER.get(action) != "none"
            }
            if forbidden:
                raise WorkflowRuntimeError(
                    f"{domain} decision produced non-{domain} durable jobs: "
                    + ", ".join(sorted(forbidden))
                )
        for item in batch.tasks:
            durable_jobs = tuple(
                action
                for action in item.decision.durable_jobs
                if action in allowed
            )
            if durable_jobs == item.decision.durable_jobs:
                scoped_tasks.append(item)
                continue
            changed = True
            scoped_tasks.append(
                replace(
                    item,
                    decision=replace(
                        item.decision,
                        durable_jobs=durable_jobs,
                        decision_revision=None,
                    ),
                )
            )
        return replace(batch, tasks=tuple(scoped_tasks)) if changed else batch

    def _admit_reconcile(self) -> bool:
        """Acquire one reconcile operation unless shutdown fenced admission."""

        with self._reconcile_condition:
            if not self._started:
                raise WorkflowRuntimeError("workflow runtime must be started first")
            if self._draining:
                return False
            self._active_reconciles += 1
            return True

    def _release_reconcile(self) -> None:
        with self._reconcile_condition:
            if self._active_reconciles <= 0:
                raise WorkflowRuntimeError("workflow reconcile ownership underflow")
            self._active_reconciles -= 1
            self._reconcile_condition.notify_all()

    def _wait_for_reconciles(self, timeout_seconds: float | None) -> bool:
        with self._reconcile_condition:
            return self._reconcile_condition.wait_for(
                lambda: self._active_reconciles == 0,
                timeout=timeout_seconds,
            )

    def reconcile(self) -> dict[str, Any]:
        """Collect facts and materialize durable jobs for every project."""

        if not self._admit_reconcile():
            return {"mode": self.mode, "skipped": True}
        try:
            return self._reconcile_once()
        finally:
            self._release_reconcile()

    def _reconciliation_checkpoint(self) -> None:
        """Yield the GIL and stop a pre-publication corpus pass on drain."""

        if not bool(getattr(self._reconcile_thread, "active", False)):
            return
        time.sleep(0)
        deadline_at = getattr(self._reconcile_thread, "deadline_at", None)
        if (
            bool(getattr(self._reconcile_thread, "correction_active", False))
            and deadline_at is not None
            and time.monotonic() >= float(deadline_at)
        ):
            raise _WorkflowReconciliationDeadlineExceeded
        with self._lock:
            if self._draining:
                raise _WorkflowReconciliationInterrupted

    def _enter_landing_observation_scopes(self, stack: ExitStack) -> None:
        """Bind request and landing caches to one complete world attempt."""

        seen: set[int] = set()
        for binding in self.project_bindings.values():
            integration_controller = getattr(
                binding, "integration_controller", None
            )
            scoped_objects = (
                getattr(integration_controller, "landing_request_resolver", None),
                getattr(
                    getattr(binding.review_controller, "collector", None),
                    "sources",
                    {},
                ).get(FactDomain.REVIEW_CI),
                getattr(binding.collector, "landing_collector", None),
                getattr(
                    getattr(binding.review_controller, "collector", None),
                    "landing_collector",
                    None,
                ),
                getattr(
                    getattr(integration_controller, "collector", None),
                    "landing_collector",
                    None,
                ),
                getattr(binding.epic_collector, "landing_collector", None),
            )
            for scoped_object in scoped_objects:
                identity = id(scoped_object)
                if scoped_object is None or identity in seen:
                    continue
                seen.add(identity)
                scope = getattr(scoped_object, "observation_scope", None)
                if callable(scope):
                    stack.enter_context(scope())

    def _reconcile_once(self) -> dict[str, Any]:
        """Run one admitted pass with cooperative lifecycle interruption."""

        started_at = time.monotonic()
        restart_budget_seconds = 120.0
        if self.liveness_controller is not None:
            restart_budget_seconds = float(
                self.liveness_controller.liveness_policy.seconds.get(
                    "restart_convergence", restart_budget_seconds
                )
            )
        deadline_at = started_at + restart_budget_seconds
        historical_deadline_seconds_remaining: float | None = None
        if self.liveness_controller is not None:
            try:
                restart_health = self.liveness_controller.liveness_snapshot()
                raw_deadline = restart_health.restart_deadline_at
                if (
                    restart_health.restart_reconstruction_pending
                    and raw_deadline
                ):
                    parsed_deadline = datetime.fromisoformat(
                        str(raw_deadline).replace("Z", "+00:00")
                    )
                    if parsed_deadline.tzinfo is None:
                        raise ValueError("restart deadline is timezone-naive")
                    clock = getattr(
                        self.liveness_controller,
                        "_clock",
                        lambda: datetime.now(timezone.utc),
                    )
                    current = clock()
                    if current.tzinfo is None:
                        raise ValueError("liveness clock is timezone-naive")
                    historical_deadline_seconds_remaining = (
                        (
                            parsed_deadline.astimezone(timezone.utc)
                            - current.astimezone(timezone.utc)
                        ).total_seconds()
                    )
            except (AttributeError, TypeError, ValueError, OverflowError):
                # Corrupt liveness time authority is already fail-closed in
                # the controller. Keep the policy budget as a final bound.
                pass
        scoped_publication_retries = 0
        accumulated_seconds: dict[str, float] = {}
        self._reconcile_thread.active = True
        self._reconcile_thread.deadline_at = deadline_at
        self._reconcile_thread.correction_active = False
        try:
            while True:
                self._reconciliation_checkpoint()
                with ExitStack() as observation_scopes:
                    self._enter_landing_observation_scopes(observation_scopes)
                    report = self._reconcile_world_once()
                current_seconds = report.get("reconciliation_phases", {}).get(
                    "seconds", {}
                )
                if isinstance(current_seconds, Mapping):
                    for name, raw_seconds in current_seconds.items():
                        accumulated_seconds[str(name)] = (
                            accumulated_seconds.get(str(name), 0.0)
                            + float(raw_seconds)
                        )
                scoped_retry = report.pop("_scoped_publication_retry", None)
                if not scoped_retry:
                    if (
                        report.get("requires_reconcile") is True
                        and time.monotonic() >= deadline_at
                    ):
                        report["restart_deadline_exceeded"] = True
                    break
                scoped_publication_retries += 1
                if time.monotonic() >= deadline_at:
                    report["scoped_publication_retry_exhausted"] = True
                    report["restart_deadline_exceeded"] = True
                    break
                self._reconcile_thread.correction_active = True
        except _WorkflowReconciliationInterrupted:
            partial = getattr(self._reconcile_thread, "report", None)
            report = dict(partial) if isinstance(partial, Mapping) else {
                "mode": self.mode,
            }
            report["skipped"] = True
            report["reason"] = (
                "workflow reconciliation interrupted by lifecycle drain"
            )
            with self._lock:
                self._last_reconcile = dict(report)
        except _WorkflowReconciliationDeadlineExceeded:
            partial = getattr(self._reconcile_thread, "report", None)
            report = dict(partial) if isinstance(partial, Mapping) else {
                "mode": self.mode,
            }
            report["requires_reconcile"] = True
            report["reconcile_reason"] = "restart_reconciliation_deadline"
            report["restart_deadline_exceeded"] = True
        finally:
            self._reconcile_thread.active = False
            self._reconcile_thread.deadline_at = None
            self._reconcile_thread.correction_active = False
            self._reconcile_thread.report = None
        phases = report.setdefault("reconciliation_phases", {})
        phases["seconds"] = {
            name: round(seconds, 6)
            for name, seconds in sorted(accumulated_seconds.items())
        }
        phases["scoped_publication_retries"] = scoped_publication_retries
        phases["restart_budget_seconds"] = restart_budget_seconds
        phases["deadline_seconds_remaining"] = round(
            max(0.0, deadline_at - time.monotonic()), 6
        )
        phases["historical_restart_deadline_seconds_remaining"] = (
            round(historical_deadline_seconds_remaining, 6)
            if historical_deadline_seconds_remaining is not None
            else None
        )
        phases["total_seconds"] = round(time.monotonic() - started_at, 6)
        with self._lock:
            self._last_reconcile = dict(report)
        return report

    def _reconcile_world_once(self) -> dict[str, Any]:
        """Run one admitted synchronous reconciliation."""

        if not self._started:
            raise WorkflowRuntimeError("workflow runtime must be started first")
        if self.mode != "off" and not self._binding_topology_current():
            raise WorkflowRuntimeError(
                "workflow project bindings changed and require restart"
            )
        if self._draining or self.mode == "off":
            return {"mode": self.mode, "skipped": True}
        report: dict[str, Any] = {"mode": self.mode, "projects": {}}
        phase_totals: dict[str, float] = {}
        project_phases: dict[str, dict[str, float]] = {}
        report["reconciliation_phases"] = {
            "seconds": phase_totals,
            "projects": project_phases,
        }

        def record_phase(
            name: str,
            started_at: float,
            *,
            project_id: str | None = None,
        ) -> None:
            elapsed = time.monotonic() - started_at
            phase_totals[name] = round(phase_totals.get(name, 0.0) + elapsed, 6)
            if project_id is not None:
                project = project_phases.setdefault(project_id, {})
                project[name] = round(project.get(name, 0.0) + elapsed, 6)

        self._reconcile_thread.report = report
        policy_cut = self._capture_liveness_policy()
        liveness_slo_seconds = (
            policy_cut.seconds if policy_cut is not None else None
        )
        project_correction_deadline = float(
            getattr(self._reconcile_thread, "deadline_at", time.monotonic())
        )
        if not self.enforce:
            shadow_updates: list[tuple[str, tuple[Any, ...]]] = []
            for project_id, binding in sorted(self.project_bindings.items()):
                try:
                    if not binding.enabled:
                        report["projects"][project_id] = {
                            "skipped": True,
                            "reason": "project paused or orchestrator quiesced",
                        }
                        continue
                    issues, _tracker_revision, _tracker_mode = (
                        self._issues_with_authority(binding)
                    )
                    authoritative_issues = self._authoritative_issue_index(
                        issues
                    )
                    authoritative_children = self._authoritative_children_index(
                        issues
                    )
                    task_issues = [
                        issue
                        for issue in issues
                        if not is_epic_rollup_issue(
                            issue,
                            authoritative_children=authoritative_children,
                        )
                    ]
                    epic_issues = [
                        issue
                        for issue in issues
                        if is_epic_rollup_issue(
                            issue,
                            authoritative_children=authoritative_children,
                        )
                        and canonicalize_status(issue.state) != IN_VALIDATION
                    ]
                    report["projects"][project_id] = {"issues": len(issues)}
                    named_batches: list[tuple[str, Any]] = []
                    if self.domain_modes["implementation"] != "off":
                        named_batches.append(
                            (
                                "implementation",
                                binding.implementation_controller.evaluate(
                                    task_issues,
                                    liveness_slo_seconds=liveness_slo_seconds,
                                    authoritative_issues=authoritative_issues,
                                    authoritative_children=authoritative_children,
                                ),
                            )
                        )
                    if self.domain_modes["review"] != "off":
                        named_batches.append(
                            (
                                "review",
                                binding.review_controller.evaluate(
                                    task_issues,
                                    liveness_slo_seconds=liveness_slo_seconds,
                                    authoritative_issues=authoritative_issues,
                                    authoritative_children=authoritative_children,
                                ),
                            )
                        )
                    if self.domain_modes["integration"] != "off":
                        named_batches.append(
                            (
                                "integration",
                                binding.integration_controller.evaluate(
                                    task_issues,
                                    liveness_slo_seconds=liveness_slo_seconds,
                                    authoritative_issues=authoritative_issues,
                                    authoritative_children=authoritative_children,
                                ),
                            )
                        )
                    if self.domain_modes["epic"] != "off":
                        named_batches.append(
                            (
                                "epic",
                                binding.epic_controller.evaluate(
                                    epic_issues,
                                    persist_evidence=False,
                                    liveness_slo_seconds=liveness_slo_seconds,
                                    authoritative_issues=authoritative_issues,
                                    authoritative_children=authoritative_children,
                                ),
                            )
                        )
                    batches = [batch for _name, batch in named_batches]
                    shadow_updates.append((project_id, tuple(batches)))
                    report["projects"][project_id] = {
                        "issues": len(issues),
                        **{
                            name: {"decisions_seen": len(batch.tasks)}
                            for name, batch in named_batches
                        },
                    }
                except Exception as exc:
                    logger.exception(
                        "Durable workflow reconcile failed for %s", project_id
                    )
                    report["projects"][project_id] = {
                        "error": type(exc).__name__,
                    }
            shadow_policy_current = True
            policy_lock = (
                self.liveness_controller.liveness_observation_lock
                if self.liveness_controller is not None
                else None
            )
            if policy_lock is not None:
                policy_lock.acquire()
            try:
                if policy_cut is not None:
                    current_policy = self.liveness_controller.liveness_policy
                    shadow_policy_current = (
                        current_policy.epoch == policy_cut.epoch
                    )
                    self._bind_policy_epoch(current_policy.epoch)
                if shadow_policy_current:
                    for project_id, batches in shadow_updates:
                        self._replace_project_decisions(project_id, batches)
                else:
                    for project_id, _batches in shadow_updates:
                        report["projects"][project_id] = {
                            "error": "WorkflowLivenessPolicyChanged",
                        }
            finally:
                if policy_lock is not None:
                    policy_lock.release()
            with self._lock:
                self._last_reconcile = report
            # Paused/quiesced projects are deliberately excluded from the
            # shadow observation cut.  They must remain mutation-free, but
            # they are not missing coverage for the enabled projects that the
            # rollout is qualifying.  An entirely paused topology still fails
            # closed because it provides no active-project evidence.
            all_project_results = tuple(report["projects"].values())
            errors = [
                str(value.get("error"))
                for value in all_project_results
                if isinstance(value, Mapping) and value.get("error")
            ]
            with self._lock:
                draining = self._draining
            # A graceful stop fences new work before waiting for this admitted
            # reconcile.  That also disables project bindings, so a sweep
            # already in source I/O can finish with an intentionally partial
            # cut.  The operator-requested interruption is not evidence that
            # a domain is unhealthy and must not poison its last successful
            # shadow qualification.  Genuine source/evaluation errors remain
            # failures even if shutdown begins later in the same pass.
            lifecycle_interrupted = draining or any(
                binding.interrupted for binding in self.project_bindings.values()
            )
            if lifecycle_interrupted and not errors:
                return report
            project_results = tuple(
                report["projects"].get(project_id)
                for project_id, binding in sorted(self.project_bindings.items())
                if binding.enabled
            )
            if not project_results or any(
                not isinstance(value, Mapping)
                or value.get("skipped")
                or any(
                    mode != "off" and domain not in value
                    for domain, mode in self.domain_modes.items()
                )
                for value in project_results
            ):
                errors.append("shadow sweep did not cover every active project")
            self.store.record_rollout_sweep(
                {
                    domain: ("; ".join(errors) if errors else None)
                    for domain, mode in self.domain_modes.items()
                    if mode == "shadow"
                }
            )
            return report

        # The job-store generation is global. Capture one generation before
        # source I/O, then accept, materialize, and publish one union cut for
        # every project whose source scan succeeded.
        projection_epoch = (
            int(self._projection_epoch_source())
            if self._projection_epoch_source is not None
            else None
        )
        if projection_epoch is not None and projection_epoch < 1:
            raise WorkflowRuntimeError(
                "work-decision publication epoch must be positive"
            )
        generation = self.store.allocate_snapshot_generation()
        prepared: list[dict[str, Any]] = []
        liveness_tasks: list[Any] = []
        liveness_facts: dict[tuple[str, str], Any] = {}
        source_errors: dict[str, str] = {}
        excluded_projects: dict[str, str] = {}
        project_retry_counts: dict[str, int] = {}

        def restore_prepared_caches() -> None:
            for item in prepared:
                binding = item["binding"]
                binding.implementation_controller._latest = dict(
                    item["implementation_checkpoint"]
                )
                binding.review_controller.restore_projection_checkpoint(
                    item["review_checkpoint"]
                )
                binding.integration_controller._latest = dict(
                    item["integration_checkpoint"]
                )
                binding.epic_controller._latest = dict(
                    item["epic_latest_checkpoint"]
                )
                binding.epic_controller._landings = dict(
                    item["epic_landings_checkpoint"]
                )

        def tracker_changes_for(
            item: Mapping[str, Any],
        ) -> frozenset[str] | None:
            """Return scoped changes, or raise when exact scope is unavailable."""

            binding = item["binding"]
            expected_authority = item.get("tracker_authority_revision")
            if expected_authority is None:
                return None
            # Explicit legacy mode has no state-branch journal. Its one
            # grouped corpus refresh remains the exact fail-closed proof at
            # publication; repeating that O(N) read at every project
            # checkpoint would recreate the large-corpus cost this path is
            # intended to remove.
            if item.get("tracker_authority_mode") == "legacy_digest":
                return None
            authority_source = binding.tracker_authority_revision_source
            if not callable(authority_source):
                raise WorkflowPublicationSuperseded(
                    "tracker authority changed before project publication"
                )
            current_authority = authority_source()
            if current_authority == expected_authority:
                return None
            changes_source = binding.tracker_authority_changes_source
            changes = (
                changes_source(str(expected_authority), str(current_authority))
                if callable(changes_source)
                and item.get("tracker_authority_mode") != "legacy_digest"
                and current_authority is not None
                else None
            )
            if changes is None:
                raise WorkflowPublicationSuperseded(
                    "tracker authority changed before publication"
                )
            canonical_changes = frozenset(
                str(task_id or "").strip().casefold()
                for task_id in changes
                if str(task_id or "").strip()
            )
            if not canonical_changes or len(canonical_changes) != len(changes):
                raise WorkflowPublicationSuperseded(
                    "tracker authority changed before publication"
                )
            # O986 owns terminal-metadata-only churn. Preserve its safe final
            # exclusion path instead of repeatedly recollecting the entire
            # project when the general journal proves that no ordinary task
            # authority changed. Final preflight revalidates this same range
            # and excludes the affected terminal task decisions.
            terminal_changes_source = (
                binding.tracker_terminal_authority_changes_source
            )
            terminal_changes = (
                terminal_changes_source(
                    str(expected_authority), str(current_authority)
                )
                if callable(terminal_changes_source)
                and current_authority is not None
                else None
            )
            if terminal_changes is not None:
                canonical_terminal_changes = frozenset(
                    str(task_id or "").strip().casefold()
                    for task_id in terminal_changes
                    if str(task_id or "").strip()
                )
                if (
                    len(canonical_terminal_changes) == len(terminal_changes)
                    and canonical_terminal_changes == canonical_changes
                ):
                    return None
            return canonical_changes

        project_queue = deque(sorted(self.project_bindings.items()))
        while project_queue:
            project_id, binding = project_queue.popleft()
            workflow_authority_revision = None
            try:
                workflow_revision_source = (
                    binding.workflow_authority_revision_source
                )
                publication_lock_source = (
                    binding.terminal_audit_publication_lock
                )
                if callable(workflow_revision_source) and callable(
                    publication_lock_source
                ):
                    # Pause/config eligibility and its revision must be one
                    # atomic observation. Reading enabled first and the token
                    # second could pair a stale True with a post-pause token.
                    with publication_lock_source():
                        binding_enabled = binding.read_enabled_state()
                        workflow_authority_revision = int(
                            workflow_revision_source()
                        )
                else:
                    binding_enabled = binding.read_enabled_state()
                    if callable(workflow_revision_source):
                        workflow_authority_revision = int(
                            workflow_revision_source()
                        )
            except Exception as exc:
                logger.exception(
                    "Durable workflow pause authority read failed for %s",
                    project_id,
                )
                report["projects"][project_id] = {
                    "error": type(exc).__name__,
                }
                source_errors[project_id] = type(exc).__name__
                continue
            if not binding_enabled:
                exclusion_reason = "project paused or orchestrator quiesced"
                report["projects"][project_id] = {
                    "skipped": True,
                    "reason": exclusion_reason,
                }
                excluded_projects[project_id] = exclusion_reason
                continue
            try:
                terminal_authority_revision = None
                revision_source = binding.terminal_authority_revision_source
                if callable(revision_source):
                    # Capture before any tracker/fact I/O.  A terminal metadata
                    # mutation anywhere in the ensuing corpus scan advances
                    # this project-wide token and makes final publication
                    # supersede instead of mixing generations.
                    terminal_authority_revision = int(revision_source())
                tracker_publication_revision_source = (
                    binding.tracker_publication_revision_source
                )
                tracker_publication_revision_before = (
                    _tracker_publication_revision(
                        tracker_publication_revision_source,
                        unavailable_reason=(
                            "tracker publication revision unavailable during "
                            "source collection"
                        ),
                    )
                    if callable(tracker_publication_revision_source)
                    else None
                )
                phase_started = time.monotonic()
                (
                    issues,
                    tracker_authority_revision,
                    tracker_authority_mode,
                ) = (
                    self._issues_with_authority(binding)
                )
                self._reconciliation_checkpoint()
                record_phase("issue_loading", phase_started, project_id=project_id)
                tracker_publication_revision = (
                    _tracker_publication_revision(
                        tracker_publication_revision_source,
                        unavailable_reason=(
                            "tracker publication revision unavailable during "
                            "source collection"
                        ),
                    )
                    if callable(tracker_publication_revision_source)
                    else None
                )
                # The generation-bound corpus below is the authority cut. A
                # mutation before that cut is harmless; a mutation after it
                # is detected by the scoped project correction check after
                # fact collection. Keep the earlier process token only for
                # phase diagnostics instead of globally discarding fresh work.
                if (
                    tracker_publication_revision_before is not None
                    and tracker_publication_revision
                    != tracker_publication_revision_before
                    and not callable(binding.tracker_authority_changes_source)
                ):
                    raise WorkflowPublicationSuperseded(
                        "tracker authority changed during source collection"
                    )
                phase_started = time.monotonic()
                authoritative_issues = self._authoritative_issue_index(issues)
                authoritative_children = self._authoritative_children_index(issues)
                task_issues = [
                    issue
                    for issue in issues
                    if not is_epic_rollup_issue(
                        issue,
                        authoritative_children=authoritative_children,
                    )
                ]
                epic_issues = [
                    issue
                    for issue in issues
                    if is_epic_rollup_issue(
                        issue,
                        authoritative_children=authoritative_children,
                    )
                    and canonicalize_status(issue.state) != IN_VALIDATION
                ]
                (
                    dependency_target_identities,
                    dependency_target_membership_ambiguous,
                ) = self._dependency_target_identities(
                    issues,
                    authoritative_issues,
                )
                record_phase("issue_index", phase_started, project_id=project_id)
                report["projects"][project_id] = {"issues": len(issues)}
                implementation_checkpoint = dict(
                    binding.implementation_controller._latest
                )
                try:
                    phase_started = time.monotonic()
                    implementation_batch = (
                        binding.implementation_controller.evaluate(
                            task_issues,
                            liveness_slo_seconds=liveness_slo_seconds,
                            authoritative_issues=authoritative_issues,
                            authoritative_children=authoritative_children,
                        )
                    )
                    record_phase(
                        "implementation",
                        phase_started,
                        project_id=project_id,
                    )
                finally:
                    binding.implementation_controller._latest = (
                        implementation_checkpoint
                    )
                review_checkpoint = (
                    binding.review_controller.projection_checkpoint()
                )
                phase_started = time.monotonic()
                review_batch = binding.review_controller.evaluate(
                    task_issues,
                    liveness_slo_seconds=liveness_slo_seconds,
                    authoritative_issues=authoritative_issues,
                    authoritative_children=authoritative_children,
                )
                review_batch = self._scope_domain_decisions(
                    "review", review_batch, REVIEW_ACTION_JOBS
                )
                record_phase("review", phase_started, project_id=project_id)

                integration_checkpoint = dict(
                    binding.integration_controller._latest
                )
                try:
                    phase_started = time.monotonic()
                    integration_batch = binding.integration_controller.evaluate(
                        task_issues,
                        liveness_slo_seconds=liveness_slo_seconds,
                        authoritative_issues=authoritative_issues,
                        authoritative_children=authoritative_children,
                    )
                    record_phase(
                        "integration",
                        phase_started,
                        project_id=project_id,
                    )
                finally:
                    binding.integration_controller._latest = (
                        integration_checkpoint
                    )
                integration_batch = self._scope_domain_decisions(
                    "integration", integration_batch, INTEGRATION_ACTIONS
                )

                epic_latest_checkpoint = dict(binding.epic_controller._latest)
                epic_landings_checkpoint = dict(binding.epic_controller._landings)
                try:
                    phase_started = time.monotonic()
                    epic_batch = binding.epic_controller.evaluate(
                        epic_issues,
                        persist_evidence=False,
                        liveness_slo_seconds=liveness_slo_seconds,
                        authoritative_issues=authoritative_issues,
                        authoritative_children=authoritative_children,
                    )
                    evaluated_epic_landings = dict(
                        binding.epic_controller._landings
                    )
                    record_phase("epic", phase_started, project_id=project_id)
                finally:
                    binding.epic_controller._latest = epic_latest_checkpoint
                    binding.epic_controller._landings = (
                        epic_landings_checkpoint
                    )
                epic_batch = self._scope_domain_decisions(
                    "epic", epic_batch, EPIC_ACTIONS
                )

                project_liveness_tasks = [
                    issue
                    for issue in issues
                    if canonicalize_status(issue.state)
                    not in LIFECYCLE_FINAL_STATUSES
                ]
                project_liveness_identities = {
                    (project_id, issue.identifier)
                    for issue in project_liveness_tasks
                }
                phase_started = time.monotonic()
                # Reuse the exact owning-domain fact cut where one exists.
                # A generic recollection can omit domain-specific landing
                # requests and therefore hash differently from the cursor it
                # must inspect for exhaustion/current authority.
                project_liveness_facts: dict[tuple[str, str], WorkflowFacts] = {}
                for owning_batch in (
                    implementation_batch,
                    review_batch,
                    integration_batch,
                    epic_batch,
                ):
                    for task_decision in owning_batch.tasks:
                        identity = (
                            project_id,
                            task_decision.task.identifier,
                        )
                        if identity in project_liveness_identities and isinstance(
                            task_decision.facts, WorkflowFacts
                        ):
                            project_liveness_facts[identity] = (
                                task_decision.facts
                            )
                # Most active work already has an owning-domain fact cut.
                # Collect only identities that no domain evaluated, and use
                # the project child index so containment stays O(1) per task.
                for issue in project_liveness_tasks:
                    identity = (project_id, issue.identifier)
                    if identity in project_liveness_facts:
                        continue
                    project_liveness_facts[identity] = binding.collector.collect(
                        issue.identifier,
                        authoritative_issues=authoritative_issues,
                        authoritative_children=authoritative_children,
                    )
                record_phase("liveness_facts", phase_started, project_id=project_id)
                domains = (
                    ("review", binding.review_controller, review_batch),
                    ("integration", binding.integration_controller, integration_batch),
                    ("epic", binding.epic_controller, epic_batch),
                )
                expected = {
                    (project_id, issue.identifier)
                    for issue in task_issues
                    if issue.state == IN_REVIEW
                } | {
                    (decision.project_id, decision.task_id)
                    for decision in integration_batch.decisions
                } | {
                    (project_id, issue.identifier)
                    for issue in epic_issues
                    if canonicalize_status(issue.state) not in {MERGED, ARCHIVED}
                }
                evaluated = {
                    (decision.project_id, decision.task_id)
                    for _name, _controller, batch in domains
                    for decision in batch.decisions
                }
                prepared_item = {
                        "project_id": project_id,
                        "binding": binding,
                        "issues": issues,
                        "task_issues": task_issues,
                        "implementation_batch": implementation_batch,
                        "implementation_checkpoint": implementation_checkpoint,
                        "review_batch": review_batch,
                        "review_checkpoint": review_checkpoint,
                        "integration_batch": integration_batch,
                        "integration_checkpoint": integration_checkpoint,
                        "epic_batch": epic_batch,
                        "epic_latest_checkpoint": epic_latest_checkpoint,
                        "epic_landings_checkpoint": epic_landings_checkpoint,
                        "evaluated_epic_landings": evaluated_epic_landings,
                        "domains": domains,
                        "expected": expected,
                        "evaluated": evaluated,
                        "terminal_authority_revision": (
                            terminal_authority_revision
                        ),
                        "tracker_authority_revision": (
                            tracker_authority_revision
                        ),
                        "tracker_publication_revision": (
                            tracker_publication_revision
                        ),
                        "tracker_authority_mode": tracker_authority_mode,
                        "dependency_target_identities": (
                            dependency_target_identities
                        ),
                        "dependency_target_membership_ambiguous": (
                            dependency_target_membership_ambiguous
                        ),
                        "workflow_authority_revision": (
                            workflow_authority_revision
                        ),
                    }
                phase_started = time.monotonic()
                scoped_changes = tracker_changes_for(prepared_item)
                record_phase(
                    "authority_correction",
                    phase_started,
                    project_id=project_id,
                )
                if scoped_changes is not None:
                    binding.review_controller.restore_projection_checkpoint(
                        review_checkpoint
                    )
                    if time.monotonic() >= project_correction_deadline:
                        raise WorkflowPublicationSuperseded(
                            "tracker authority did not stabilize within the restart "
                            "correction deadline"
                        )
                    self._reconcile_thread.correction_active = True
                    raise _WorkflowProjectAuthorityChanged(scoped_changes)
                prepared.append(prepared_item)
                liveness_tasks.extend(project_liveness_tasks)
                liveness_facts.update(project_liveness_facts)
                report["projects"][project_id] = {
                    "issues": len(issues),
                    "authority_corrections": project_retry_counts.get(project_id, 0),
                }

                # A stable project collected earlier can change while a later
                # project is evaluated. Recheck every retained cut before the
                # queue can drain, then discard and retry only that project.
                for stable_item in tuple(prepared):
                    phase_started = time.monotonic()
                    stable_changes = tracker_changes_for(stable_item)
                    record_phase(
                        "authority_correction",
                        phase_started,
                        project_id=str(stable_item["project_id"]),
                    )
                    if stable_changes is None:
                        continue
                    stable_project_id = str(stable_item["project_id"])
                    if time.monotonic() >= project_correction_deadline:
                        raise WorkflowPublicationSuperseded(
                            "tracker authority did not stabilize within the restart "
                            "correction deadline"
                        )
                    stable_binding = stable_item["binding"]
                    stable_binding.review_controller.restore_projection_checkpoint(
                        stable_item["review_checkpoint"]
                    )
                    prepared.remove(stable_item)
                    stable_task_ids = {
                        str(issue.identifier)
                        for issue in stable_item["issues"]
                    }
                    liveness_tasks[:] = [
                        task
                        for task in liveness_tasks
                        if not (
                            str(getattr(task, "project_id", "") or "")
                            == stable_project_id
                            and str(getattr(task, "identifier", "") or "")
                            in stable_task_ids
                        )
                    ]
                    for identity in tuple(liveness_facts):
                        if identity[0] == stable_project_id:
                            liveness_facts.pop(identity, None)
                    if any(
                        str(getattr(task, "project_id", "") or "")
                        == stable_project_id
                        and str(getattr(task, "identifier", "") or "")
                        in stable_task_ids
                        for task in liveness_tasks
                    ):
                        raise WorkflowRuntimeError(
                            "scoped project retry retained duplicate liveness rows"
                        )
                    project_retry_counts[stable_project_id] = (
                        project_retry_counts.get(stable_project_id, 0) + 1
                    )
                    self._reconcile_thread.correction_active = True
                    report["projects"][stable_project_id] = {
                        "issues": len(stable_item["issues"]),
                        "authority_corrections": project_retry_counts[
                            stable_project_id
                        ],
                        "corrected_tasks": len(stable_changes),
                    }
                    project_queue.append((stable_project_id, stable_binding))
            except _WorkflowProjectAuthorityChanged as exc:
                project_retry_counts[project_id] = (
                    project_retry_counts.get(project_id, 0) + 1
                )
                report["projects"][project_id] = {
                    "issues": len(issues),
                    "authority_corrections": project_retry_counts[project_id],
                    "corrected_tasks": len(exc.changed_tasks),
                }
                project_queue.append((project_id, binding))
                continue
            except WorkflowPublicationSuperseded as exc:
                restore_prepared_caches()
                reason = str(exc)
                superseded_projects = {
                    candidate_project_id
                    for candidate_project_id, candidate_binding in (
                        self.project_bindings.items()
                    )
                    if candidate_binding.enabled
                } | {
                    str(item["project_id"]) for item in prepared
                } | {
                    project_id
                }
                for superseded_project_id in sorted(superseded_projects):
                    logger.info(
                        "Durable workflow publication superseded for %s: %s",
                        superseded_project_id,
                        reason,
                    )
                    report["projects"][superseded_project_id] = {
                        "publication_superseded": True,
                        "reason": reason,
                    }
                report["requires_reconcile"] = True
                report["reconcile_reason"] = "publication_authority_changed"
                with self._lock:
                    self._last_reconcile = report
                return report
            except Exception as exc:
                logger.exception(
                    "Durable workflow source evaluation failed for %s", project_id
                )
                report["projects"][project_id] = {
                    "error": type(exc).__name__,
                }
                source_errors[project_id] = type(exc).__name__

        self._reconciliation_checkpoint()
        publication_started = time.monotonic()
        authoritative_projects = tuple(
            item["project_id"] for item in prepared
        )
        expected_identities = tuple(
            sorted(identity for item in prepared for identity in item["expected"])
        )
        expected_identity_set = set(expected_identities)
        evaluated_identities = tuple(
            sorted(identity for item in prepared for identity in item["evaluated"])
        )
        authority = self.store.capture_snapshot_authority(
            authoritative_project_ids=authoritative_projects,
            evaluated_identities=evaluated_identities,
            full_project_scope=True,
        )
        all_domains = [
            (item, name, controller, batch)
            for item in prepared
            for name, controller, batch in item["domains"]
        ]
        lifecycle_statuses: dict[tuple[str, str], set[str]] = {}
        for item in prepared:
            project_id = str(item["project_id"])
            for issue in item["issues"]:
                identity = (project_id, str(issue.identifier))
                lifecycle_statuses.setdefault(identity, set()).add(
                    canonicalize_status(issue.state)
                )
        lifecycle_final_tasks = tuple(
            sorted(
                (*identity, next(iter(statuses)))
                for identity, statuses in lifecycle_statuses.items()
                if len(statuses) == 1
                and next(iter(statuses)) in LIFECYCLE_FINAL_STATUSES
                and identity not in expected_identity_set
            )
        )

        def reject_domains() -> None:
            for item, name, controller, batch in all_domains:
                report["projects"][item["project_id"]][name] = asdict(
                    controller.scheduler.rejected_snapshot(
                        generation, batch.decisions
                    )
                )

        if not self.store.accept_snapshot_generation(generation):
            if self.liveness_controller is not None:
                with self.liveness_controller.liveness_observation_lock:
                    self._bind_policy_epoch(
                        self.liveness_controller.liveness_policy.epoch
                    )
            reject_domains()
            with self._lock:
                self._last_reconcile = report
            return report

        liveness_controller = self.liveness_controller
        liveness_lock = (
            liveness_controller.liveness_observation_lock
            if liveness_controller is not None
            else None
        )
        liveness_lock_held = False
        if liveness_lock is not None:
            liveness_lock.acquire()
            liveness_lock_held = True
        observation: ControllerObservation | None = None
        observation_committed = False
        marker_committed = False
        try:
            if liveness_controller is not None:
                current_policy = liveness_controller.liveness_policy
                if (
                    policy_cut is None
                    or current_policy.epoch != policy_cut.epoch
                ):
                    # Owner decisions were evaluated from an older policy
                    # cut. Reject the accepted generation before any cursor,
                    # job, projection, or liveness publication can mix the
                    # old deadlines with the new semantic epoch.
                    self._bind_policy_epoch(current_policy.epoch)
                    reject_domains()
                    if self.store.snapshot_generation_is_current(generation):
                        self.store.restore_snapshot_authority(
                            authority, snapshot_generation=generation
                        )
                    with self._lock:
                        self._last_reconcile = report
                    return report
                self._bind_policy_epoch(policy_cut.epoch)
                observation = liveness_controller.prepare_runtime_observation(
                    tuple(liveness_tasks),
                    facts_by_task=liveness_facts,
                    snapshot_generation=generation,
                    source_scan_complete=not source_errors,
                    source_errors=source_errors,
                    excluded_projects=excluded_projects,
                )
                if observation is None:
                    reject_domains()
                    if self.store.snapshot_generation_is_current(generation):
                        self.store.restore_snapshot_authority(
                            authority, snapshot_generation=generation
                        )
                    with self._lock:
                        self._last_reconcile = report
                    return report
                if observation.policy_epoch != policy_cut.epoch:
                    reject_domains()
                    if self.store.snapshot_generation_is_current(generation):
                        self.store.restore_snapshot_authority(
                            authority, snapshot_generation=generation
                        )
                    with self._lock:
                        self._last_reconcile = report
                    return report
                # Bind every owning lane to the exact liveness-policy cut
                # held by this observation. Absolute reassessment timestamps
                # remain outside semantic revisions; SLO changes do not.
                self._bind_policy_epoch(observation.policy_epoch)
            membership = self.store.reconcile_snapshot_membership(
                snapshot_generation=generation,
                authoritative_project_ids=authoritative_projects,
                expected_identities=expected_identities,
                evaluated_identities=evaluated_identities,
            )
            if not membership.accepted:
                reject_domains()
                with self._lock:
                    self._last_reconcile = report
                return report

            for project_id, task_id, status in lifecycle_final_tasks:
                self.store.record_lifecycle_final_authority(
                    project_id=project_id,
                    task_id=task_id,
                    status=status,
                    snapshot_generation=generation,
                )

            reconciled: list[tuple[dict[str, Any], str, Any, Any, Any]] = []
            for item, name, controller, batch in all_domains:
                result = controller.scheduler.reconcile_accepted(
                    batch.decisions,
                    snapshot_generation=generation,
                    record_metrics=False,
                )
                if not result.snapshot_accepted:
                    break
                reconciled.append((item, name, controller, batch, result))
            if len(reconciled) != len(all_domains):
                reject_domains()
                if self.store.snapshot_generation_is_current(generation):
                    self.store.restore_snapshot_authority(
                        authority, snapshot_generation=generation
                    )
                with self._lock:
                    self._last_reconcile = report
                return report

            projection_decisions: tuple[WorkDecision, ...] = ()
            proven_actions: dict[tuple[str, str], set[str]] = {}
            publication_observation = observation
            if observation is not None:
                (
                    projection_decisions,
                    proven_actions,
                    projection_facts,
                ) = (
                    self._domain_projection_and_proofs(
                        prepared,
                        reconciled,
                        observation,
                        snapshot_generation=generation,
                        workflow_facts=liveness_facts,
                    )
                )
                publication_observation = replace(
                    observation,
                    decisions=projection_decisions,
                    decision_facts=projection_facts,
                )
            liveness_reconciliation = (
                self._liveness_reconciliation(
                    publication_observation,
                    snapshot_generation=generation,
                    domain_results=tuple(item[4] for item in reconciled),
                    proven_actions=proven_actions,
                )
                if publication_observation is not None
                else None
            )

            with self._lock:
                runtime_checkpoint = dict(self._latest_decisions)
            publication_excluded_identities: set[tuple[str, str]] = set()
            tracker_scoped_publication_advances = 0
            tracker_scoped_publication_exclusions: set[tuple[str, str]] = set()
            durable_publication_identities = {
                (decision.project_id, decision.task_id.casefold())
                for _item, _name, _controller, batch in all_domains
                for decision in batch.decisions
                if decision.durable_jobs
            }

            def accept_task_scoped_tracker_delta(
                project_id: str,
                binding: WorkflowProjectBinding,
                expected_revision: int,
                current_revision: int,
            ) -> bool:
                """Exclude journal-proven unrelated tasks from this exact cut."""

                nonlocal tracker_scoped_publication_advances
                if current_revision == expected_revision:
                    return True
                changes_source = binding.tracker_publication_changes_source
                if not callable(changes_source):
                    return False
                try:
                    observed_revision, raw_changed_tasks = changes_source(
                        expected_revision
                    )
                except Exception:  # noqa: BLE001 - authority proof fails closed
                    return False
                if (
                    int(observed_revision) != current_revision
                    or raw_changed_tasks is None
                    or not raw_changed_tasks
                ):
                    return False
                changed_by_key = {
                    str(task_id or "").strip().casefold(): str(task_id or "").strip()
                    for task_id in raw_changed_tasks
                    if str(task_id or "").strip()
                }
                if len(changed_by_key) != len(raw_changed_tasks):
                    return False
                prepared_item = prepared_by_project[project_id]
                protected_tasks = {
                    task_id
                    for candidate_project, task_id in durable_publication_identities
                    if candidate_project == project_id
                }
                dependency_targets = frozenset(
                    prepared_item.get("dependency_target_identities") or ()
                )
                changed_tasks = frozenset(changed_by_key)
                if (
                    not protected_tasks
                    or prepared_item.get(
                        "dependency_target_membership_ambiguous", False
                    )
                    or not changed_tasks.isdisjoint(protected_tasks)
                    or not changed_tasks.isdisjoint(dependency_targets)
                ):
                    return False

                known_task_ids: dict[str, str] = {}
                for issue in prepared_item["issues"]:
                    identifier = str(getattr(issue, "identifier", "") or "").strip()
                    issue_id = str(getattr(issue, "id", "") or "").strip()
                    if identifier:
                        known_task_ids[identifier.casefold()] = identifier
                    if issue_id and identifier:
                        known_task_ids[issue_id.casefold()] = identifier
                excluded = {
                    (
                        project_id,
                        known_task_ids.get(task_key, changed_by_key[task_key]),
                    )
                    for task_key in changed_tasks
                }
                publication_excluded_identities.update(excluded)
                tracker_scoped_publication_exclusions.update(excluded)
                tracker_scoped_publication_advances += 1
                return True

            def restore_caches() -> None:
                with self._lock:
                    self._latest_decisions = dict(runtime_checkpoint)
                restore_prepared_caches()

            def rollback_authority() -> None:
                self.store.restore_snapshot_authority(
                    authority, snapshot_generation=generation
                )

            def publish() -> WorkflowSnapshotPublication:
                liveness_publication: WorkflowSnapshotPublication | None = None
                projection_publication: Any | None = None
                try:
                    for item in prepared:
                        binding = item["binding"]
                        binding.implementation_controller._latest = {
                            task.task.identifier: task
                            for task in item["implementation_batch"].tasks
                        }
                        binding.review_controller.commit_snapshot_projection(
                            item["task_issues"], item["review_batch"], generation
                        )
                        binding.integration_controller._latest = {
                            task.task.identifier: task
                            for task in item["integration_batch"].tasks
                        }
                        binding.epic_controller._latest = {
                            task.task.identifier: task
                            for task in item["epic_batch"].tasks
                        }
                        binding.epic_controller._landings = dict(
                            item["evaluated_epic_landings"]
                        )
                        self._replace_project_decisions(
                            item["project_id"],
                            (
                                item["implementation_batch"],
                                item["review_batch"],
                                item["integration_batch"],
                                item["epic_batch"],
                            ),
                            exclude_identities=publication_excluded_identities,
                        )
                    if publication_observation is not None:
                        self._publish_runtime_projection(
                            projection_decisions,
                            authoritative_project_ids=authoritative_projects,
                            exclude_identities=publication_excluded_identities,
                        )
                        if self._projection_publisher is not None:
                            if projection_epoch is None:  # pragma: no cover
                                raise WorkflowRuntimeError(
                                    "work-decision publication epoch is unavailable"
                                )
                            projection_keys = {
                                (decision.project_id, decision.task_id)
                                for decision in projection_decisions
                            }
                            live_keys = set(
                                publication_observation.expected_identities
                            )
                            incomplete_keys = live_keys - projection_keys
                            projection_publication = self._projection_publisher(
                                projection_decisions,
                                generation,
                                live_keys=live_keys,
                                publication_epoch=projection_epoch,
                                unavailable_projects=(
                                    set(source_errors) | set(excluded_projects)
                                ),
                                scan_complete=bool(
                                    publication_observation.source_scan_complete
                                    and not publication_observation.truncated
                                    and not incomplete_keys
                                ),
                                incomplete_keys=incomplete_keys,
                                incomplete_reason=(
                                    "controller snapshot did not cover every "
                                    "active non-terminal task"
                                    if incomplete_keys
                                    or publication_observation.truncated
                                    else None
                                ),
                            )
                            if not bool(
                                getattr(
                                    projection_publication, "accepted", False
                                )
                            ):
                                raise WorkflowRuntimeError(
                                    "canonical work-decision projection rejected: "
                                    + str(
                                        getattr(
                                            projection_publication,
                                            "rejection",
                                            "unknown",
                                        )
                                    )
                                )
                            commit_memory = getattr(
                                projection_publication,
                                "commit_memory",
                                None,
                            )
                            if not callable(commit_memory):
                                raise WorkflowRuntimeError(
                                    "canonical projection returned no memory "
                                    "commit operation"
                                )
                            commit_memory()
                        assert liveness_controller is not None
                        assert liveness_reconciliation is not None
                        liveness_publication = (
                            liveness_controller.stage_runtime_observation(
                                publication_observation,
                                reconciliation=liveness_reconciliation,
                                persist_liveness_state=(
                                    self._persist_liveness_state
                                ),
                            )
                        )
                except Exception as publish_exc:
                    errors: list[Exception] = []
                    if (
                        liveness_publication is not None
                        and liveness_publication.rollback is not None
                    ):
                        try:
                            liveness_publication.rollback()
                        except Exception as exc:
                            errors.append(exc)
                    rollback_projection = getattr(
                        projection_publication, "rollback", None
                    )
                    if callable(rollback_projection):
                        try:
                            rollback_projection()
                        except Exception as exc:
                            errors.append(exc)
                    try:
                        restore_caches()
                    except Exception as exc:
                        errors.append(exc)
                    if errors:
                        cause = ExceptionGroup(
                            "runtime publication and compensation failed",
                            [publish_exc, *errors],
                        )
                        raise WorkflowJobPublicationError(
                            "runtime snapshot publication could not be "
                            "compensated",
                            rollback_failed=True,
                        ) from cause
                    raise

                def rollback() -> None:
                    errors: list[Exception] = []
                    if (
                        liveness_publication is not None
                        and liveness_publication.rollback is not None
                    ):
                        try:
                            liveness_publication.rollback()
                        except Exception as exc:
                            errors.append(exc)
                    rollback_projection = getattr(
                        projection_publication, "rollback", None
                    )
                    if callable(rollback_projection):
                        try:
                            rollback_projection()
                        except Exception as exc:
                            errors.append(exc)
                    try:
                        restore_caches()
                    except Exception as exc:
                        errors.append(exc)
                    if len(errors) == 1:
                        raise errors[0]
                    if errors:
                        raise ExceptionGroup(
                            "runtime snapshot compensators failed", errors
                        )

                return WorkflowSnapshotPublication(
                    result=(
                        liveness_publication.result
                        if liveness_publication is not None
                        else None
                    ),
                    rollback=rollback,
                    rollback_authority=rollback_authority,
                )

            # Terminal-audit metadata and its workflow lane live in separate
            # stores. Production bindings capture project-wide authority
            # revisions before source I/O, then retain the established
            # project-before-job-store lock order through publication. The
            # final native state-branch proofs are constant-time revision
            # comparisons plus SQLite-only lane checks. Explicit legacy
            # native mode performs at most one grouped corpus refresh; other
            # unversioned trackers fail closed. Legacy/test terminal bindings
            # without revision support retain the older exact proof fallback.
            terminal_publication_proofs: list[
                tuple[WorkflowProjectBinding, WorkDecision, Mapping[str, Any], str]
            ] = []
            terminal_snapshot_proofs: list[
                tuple[WorkflowProjectBinding, WorkDecision, Mapping[str, Any]]
            ] = []
            bindings_by_project = {
                str(item["project_id"]): item["binding"] for item in prepared
            }
            for decision in projection_decisions:
                identity = (decision.project_id, decision.task_id)
                terminal_actions = {
                    action
                    for action in proven_actions.get(identity, set())
                    if _LIVENESS_ACTION_OWNER.get(action) == "terminal_audit"
                }
                facts = liveness_facts.get(identity)
                observation_fact = (
                    facts.fact(FactDomain.TERMINAL_AUDIT)
                    if isinstance(facts, WorkflowFacts)
                    else None
                )
                observed = (
                    observation_fact.value
                    if observation_fact is not None
                    and observation_fact.state is FactState.KNOWN
                    and isinstance(observation_fact.value, Mapping)
                    else None
                )
                binding = bindings_by_project.get(decision.project_id)
                if (
                    isinstance(observed, Mapping)
                    and (
                        str(observed.get("request_state") or "")
                        in {"pending", "in_progress"}
                        or (
                            isinstance(
                                observed.get("terminal_provenance"),
                                Mapping,
                            )
                            and (
                                binding is None
                                or not callable(
                                    binding.terminal_authority_revision_source
                                )
                            )
                        )
                    )
                ):
                    if binding is None:
                        raise WorkflowRuntimeError(
                            "terminal-audit snapshot proof lost its binding"
                        )
                    terminal_snapshot_proofs.append(
                        (binding, decision, observed)
                    )
                if not terminal_actions:
                    continue
                if binding is None or observed is None:
                    raise WorkflowRuntimeError(
                        "terminal-audit publication proof lost its authority"
                    )
                for action in sorted(terminal_actions):
                    terminal_publication_proofs.append(
                        (binding, decision, observed, action)
                    )

            proof_bindings = [
                item[0] for item in terminal_publication_proofs
            ] + [item[0] for item in terminal_snapshot_proofs]
            unique_proof_bindings = {
                binding.project_id: binding for binding in proof_bindings
            }
            prepared_by_project = {
                str(item["project_id"]): item for item in prepared
            }
            unversioned_snapshot_counts: dict[str, int] = {}
            for binding, _decision, _observed in terminal_snapshot_proofs:
                if callable(binding.terminal_authority_revision_source):
                    continue
                count = unversioned_snapshot_counts.get(binding.project_id, 0) + 1
                unversioned_snapshot_counts[binding.project_id] = count
                if count > 1:
                    raise WorkflowRuntimeError(
                        "unversioned terminal-audit publication cannot prove "
                        "multiple task snapshots without a grouped authority source"
                    )
            publication_bindings = dict(unique_proof_bindings)
            for project_id, item in prepared_by_project.items():
                binding = item["binding"]
                if (
                    (
                        item.get("tracker_authority_revision") is not None
                        and (
                            item.get("tracker_authority_mode") == "legacy_digest"
                            or callable(binding.tracker_authority_revision_source)
                        )
                    )
                    or (
                        item.get("terminal_authority_revision") is not None
                        and callable(binding.terminal_authority_revision_source)
                    )
                    or (
                        item.get("workflow_authority_revision") is not None
                        and callable(binding.workflow_authority_revision_source)
                    )
                ):
                    publication_bindings[project_id] = binding

            # State-branch generation and scoped-diff proofs can execute Git
            # commands.  Complete them before taking any project publication
            # lock, then retain the native tracker's process-local mutation
            # revision for the constant-time final CAS below.
            tracker_terminal_changes: dict[str, frozenset[str]] = {}
            tracker_publication_revisions: dict[str, int] = {}
            if publication_bindings and liveness_lock_held:
                # Health and operator controls use the liveness observation
                # lock.  Do not retain it across tracker/Git preflight; the
                # policy epoch is revalidated immediately after reacquisition.
                assert liveness_lock is not None
                liveness_lock.release()
                liveness_lock_held = False
            for project_id, binding in sorted(publication_bindings.items()):
                expected_tracker_revision = prepared_by_project[project_id].get(
                    "tracker_authority_revision"
                )
                if expected_tracker_revision is None:
                    continue
                tracker_authority_mode = prepared_by_project[project_id].get(
                    "tracker_authority_mode"
                )
                publication_revision_source = (
                    binding.tracker_publication_revision_source
                )
                if not callable(publication_revision_source):
                    raise WorkflowRuntimeError(
                        "tracker publication revision source is unavailable"
                    )
                publication_revision_before = _tracker_publication_revision(
                    publication_revision_source,
                    unavailable_reason=(
                        "tracker publication revision unavailable during "
                        "publication preflight"
                    ),
                )
                tracker_revision_source = binding.tracker_authority_revision_source
                if tracker_authority_mode == "legacy_digest":
                    (
                        _current_issues,
                        current_tracker_revision,
                        current_tracker_mode,
                    ) = self._issues_with_authority(binding)
                    if current_tracker_mode != "legacy_digest":
                        current_tracker_revision = None
                else:
                    current_tracker_revision = (
                        tracker_revision_source()
                        if callable(tracker_revision_source)
                        else None
                    )
                    if isinstance(current_tracker_revision, str):
                        current_tracker_revision = current_tracker_revision.strip()
                    if (
                        not current_tracker_revision
                        or current_tracker_revision == "unavailable"
                        or str(current_tracker_revision).startswith("unavailable:")
                    ):
                        current_tracker_revision = None
                if current_tracker_revision != expected_tracker_revision:
                    changes_source = (
                        binding.tracker_terminal_authority_changes_source
                    )
                    scoped_tracker_changes = (
                        changes_source(
                            str(expected_tracker_revision),
                            str(current_tracker_revision),
                        )
                        if callable(changes_source)
                        and tracker_authority_mode != "legacy_digest"
                        and current_tracker_revision is not None
                        else None
                    )
                    if scoped_tracker_changes is None:
                        general_changes_source = (
                            binding.tracker_authority_changes_source
                        )
                        general_changes = (
                            general_changes_source(
                                str(expected_tracker_revision),
                                str(current_tracker_revision),
                            )
                            if callable(general_changes_source)
                            and tracker_authority_mode != "legacy_digest"
                            and current_tracker_revision is not None
                            else None
                        )
                        if general_changes is None:
                            raise WorkflowPublicationSuperseded(
                                "tracker authority changed before publication"
                            )
                        canonical_general_changes = frozenset(
                            str(task_id or "").strip().casefold()
                            for task_id in general_changes
                            if str(task_id or "").strip()
                        )
                        if (
                            not canonical_general_changes
                            or len(canonical_general_changes) != len(general_changes)
                        ):
                            raise WorkflowPublicationSuperseded(
                                "tracker authority changed before publication"
                            )
                        raise _WorkflowScopedPublicationChanged(
                            project_id,
                            canonical_general_changes,
                        )
                    canonical_changes = frozenset(
                        str(task_id or "").strip().casefold()
                        for task_id in scoped_tracker_changes
                        if str(task_id or "").strip()
                    )
                    if len(canonical_changes) != len(scoped_tracker_changes):
                        raise WorkflowPublicationSuperseded(
                            "tracker authority changed before publication"
                        )
                    prepared_item = prepared_by_project[project_id]
                    dependency_targets = frozenset(
                        prepared_item.get("dependency_target_identities") or ()
                    )
                    if canonical_changes and (
                        prepared_item.get(
                            "dependency_target_membership_ambiguous", False
                        )
                        or not canonical_changes.isdisjoint(dependency_targets)
                    ):
                        # A task status is cross-row dependency evidence.  If
                        # a changed audit task is a dependency target (or that
                        # membership cannot be proven), excluding only its own
                        # decision would publish stale dependents.
                        if callable(binding.tracker_authority_changes_source):
                            raise _WorkflowScopedPublicationChanged(
                                project_id,
                                canonical_changes,
                            )
                        raise WorkflowPublicationSuperseded(
                            "tracker authority changed before publication"
                        )
                    tracker_terminal_changes[project_id] = canonical_changes
                publication_revision_after = _tracker_publication_revision(
                    publication_revision_source,
                    unavailable_reason=(
                        "tracker publication revision unavailable during "
                        "publication preflight"
                    ),
                )
                if publication_revision_after != publication_revision_before:
                    if not accept_task_scoped_tracker_delta(
                        project_id,
                        binding,
                        publication_revision_before,
                        publication_revision_after,
                    ):
                        if callable(binding.tracker_authority_changes_source):
                            raise _WorkflowFinalPublicationChanged(
                                "tracker authority changed during publication preflight"
                            )
                        raise WorkflowPublicationSuperseded(
                            "tracker authority changed during publication preflight"
                        )
                tracker_publication_revisions[project_id] = (
                    publication_revision_after
                )
            if publication_bindings and liveness_lock is not None:
                liveness_lock.acquire()
                liveness_lock_held = True
                if (
                    observation is not None
                    and liveness_controller is not None
                    and liveness_controller.liveness_policy.epoch
                    != observation.policy_epoch
                ):
                    raise WorkflowPublicationSuperseded(
                        "liveness policy changed during publication preflight"
                    )

            if not publication_bindings:
                published, publication_result = (
                    self.store.publish_snapshot_generation(
                        generation,
                        publish,
                        rollback_authority=rollback_authority,
                    )
                )
            else:
                wait_started = time.monotonic()
                first_lock_acquired: float | None = None
                all_locks_acquired: float | None = None
                superseded = False
                try:
                    with ExitStack() as publication_locks:
                        for project_id in sorted(publication_bindings):
                            binding = publication_bindings[project_id]
                            lock_source = binding.terminal_audit_publication_lock
                            if not callable(lock_source):
                                raise WorkflowRuntimeError(
                                    "terminal-audit publication lock is unavailable"
                                )
                            publication_locks.enter_context(lock_source())
                            if first_lock_acquired is None:
                                first_lock_acquired = time.monotonic()
                        all_locks_acquired = time.monotonic()

                        def publish_after_terminal_proof(
                        ) -> WorkflowSnapshotPublication:
                            nonlocal liveness_reconciliation
                            nonlocal projection_decisions
                            nonlocal publication_observation
                            nonlocal superseded
                            for project_id, binding in sorted(
                                publication_bindings.items()
                            ):
                                expected_tracker_revision = prepared_by_project[
                                    project_id
                                ].get("tracker_authority_revision")
                                if expected_tracker_revision is not None:
                                    publication_revision_source = (
                                        binding.tracker_publication_revision_source
                                    )
                                    expected_publication_revision = (
                                        tracker_publication_revisions.get(project_id)
                                    )
                                    if (
                                        expected_publication_revision is None
                                        or not callable(publication_revision_source)
                                    ):
                                        superseded = True
                                        raise WorkflowPublicationSuperseded(
                                            "tracker authority changed before publication"
                                        )
                                    try:
                                        current_publication_revision = (
                                            _tracker_publication_revision(
                                                publication_revision_source,
                                                unavailable_reason=(
                                                    "tracker publication revision "
                                                    "unavailable before publication"
                                                ),
                                            )
                                        )
                                    except WorkflowPublicationSuperseded:
                                        superseded = True
                                        raise
                                    if (
                                        current_publication_revision
                                        != expected_publication_revision
                                    ):
                                        if not accept_task_scoped_tracker_delta(
                                            project_id,
                                            binding,
                                            expected_publication_revision,
                                            current_publication_revision,
                                        ):
                                            superseded = True
                                            if callable(
                                                binding.tracker_authority_changes_source
                                            ):
                                                raise _WorkflowFinalPublicationChanged(
                                                    "tracker authority changed before publication"
                                                )
                                            raise WorkflowPublicationSuperseded(
                                                "tracker authority changed before publication"
                                            )
                                revision_source = (
                                    binding.terminal_authority_revision_source
                                )
                                if callable(revision_source):
                                    expected_revision = prepared_by_project[
                                        project_id
                                    ].get("terminal_authority_revision")
                                    current_revision = int(revision_source())
                                    if expected_revision is None:
                                        superseded = True
                                        raise WorkflowPublicationSuperseded(
                                            "terminal-audit disposition changed "
                                            "before publication"
                                        )
                                    if current_revision != int(expected_revision):
                                        changes_source = (
                                            binding.terminal_authority_changes_source
                                        )
                                        scoped_changes = (
                                            changes_source(int(expected_revision))
                                            if callable(changes_source)
                                            else (current_revision, None)
                                        )
                                        changed_revision, changed_tasks = scoped_changes
                                        active_audit_tasks = {
                                            decision.task_id.casefold()
                                            for (
                                                proof_binding,
                                                decision,
                                                observed,
                                            ) in terminal_snapshot_proofs
                                            if proof_binding is binding
                                            and str(observed.get("request_state") or "")
                                            in {"pending", "in_progress"}
                                        }
                                        raw_changed_tasks = changed_tasks or ()
                                        canonical_changed_tasks = frozenset(
                                            str(task_id or "").strip().casefold()
                                            for task_id in raw_changed_tasks
                                            if str(task_id or "").strip()
                                        )
                                        if (
                                            int(changed_revision) != current_revision
                                            or not changed_tasks
                                            or len(canonical_changed_tasks)
                                            != len(raw_changed_tasks)
                                            or not canonical_changed_tasks
                                            <= active_audit_tasks
                                            or (
                                                project_id
                                                in tracker_terminal_changes
                                                and tracker_terminal_changes[project_id]
                                                != canonical_changed_tasks
                                            )
                                        ):
                                            superseded = True
                                            raise WorkflowPublicationSuperseded(
                                                "terminal-audit disposition changed "
                                                "before publication"
                                            )
                                        publication_excluded_identities.update(
                                            (project_id, task_id)
                                            for task_id in changed_tasks
                                        )
                                    elif tracker_terminal_changes.get(project_id):
                                        superseded = True
                                        raise WorkflowPublicationSuperseded(
                                            "tracker authority changed before publication"
                                        )
                                elif tracker_terminal_changes.get(project_id):
                                    superseded = True
                                    raise WorkflowPublicationSuperseded(
                                        "tracker authority changed before publication"
                                    )
                                workflow_revision_source = (
                                    binding.workflow_authority_revision_source
                                )
                                if callable(workflow_revision_source):
                                    expected_workflow_revision = (
                                        prepared_by_project[project_id].get(
                                            "workflow_authority_revision"
                                        )
                                    )
                                    if (
                                        expected_workflow_revision is None
                                        or int(workflow_revision_source())
                                        != int(expected_workflow_revision)
                                    ):
                                        superseded = True
                                        raise WorkflowPublicationSuperseded(
                                            "workflow authority changed before "
                                            "publication"
                                        )

                            # The store invokes this callback under its marker
                            # transaction.  Project locks fence metadata; these
                            # proofs touch only SQLite lane authority in native
                            # production bindings, never tracker refresh I/O.
                            for binding, decision, observed in terminal_snapshot_proofs:
                                revision_source = (
                                    binding.terminal_authority_revision_source
                                )
                                proof_source = (
                                    binding.terminal_audit_lane_proof_source
                                    if callable(revision_source)
                                    else binding.terminal_audit_snapshot_proof_source
                                )
                                if not callable(proof_source):
                                    raise WorkflowRuntimeError(
                                        "terminal-audit snapshot proof is unavailable"
                                    )
                                accepted = (
                                    proof_source(decision, observed, None)
                                    if callable(revision_source)
                                    else proof_source(decision, observed)
                                )
                                if not accepted:
                                    superseded = True
                                    raise WorkflowPublicationSuperseded(
                                        "terminal-audit disposition changed before "
                                        "publication"
                                    )
                            for binding, decision, observed, action in (
                                terminal_publication_proofs
                            ):
                                revision_source = (
                                    binding.terminal_authority_revision_source
                                )
                                proof_source = (
                                    binding.terminal_audit_lane_proof_source
                                    if callable(revision_source)
                                    else binding.terminal_audit_proof_source
                                )
                                if not callable(proof_source):
                                    raise WorkflowRuntimeError(
                                        "terminal-audit authority proof is unavailable"
                                    )
                                if not proof_source(decision, observed, action):
                                    superseded = True
                                    raise WorkflowPublicationSuperseded(
                                        "terminal-audit authority changed before "
                                        "publication"
                                    )
                            if (
                                publication_excluded_identities
                                and publication_observation is not None
                            ):
                                projection_decisions = tuple(
                                    decision
                                    for decision in projection_decisions
                                    if (decision.project_id, decision.task_id)
                                    not in publication_excluded_identities
                                )
                                filtered_facts = {
                                    identity: facts
                                    for identity, facts in (
                                        publication_observation.decision_facts.items()
                                    )
                                    if identity not in publication_excluded_identities
                                }
                                publication_observation = replace(
                                    publication_observation,
                                    decisions=tuple(
                                        decision
                                        for decision in publication_observation.decisions
                                        if (decision.project_id, decision.task_id)
                                        not in publication_excluded_identities
                                    ),
                                    decision_facts=filtered_facts,
                                    escalations=tuple(
                                        escalation
                                        for escalation in (
                                            publication_observation.escalations
                                        )
                                        if (
                                            escalation.project_id,
                                            escalation.task_id,
                                        )
                                        not in publication_excluded_identities
                                    ),
                                    source_scan_complete=False,
                                    source_scan_deferred=True,
                                )
                                liveness_reconciliation = (
                                    self._liveness_reconciliation(
                                        publication_observation,
                                        snapshot_generation=generation,
                                        domain_results=tuple(
                                            item[4] for item in reconciled
                                        ),
                                        proven_actions=proven_actions,
                                    )
                                )
                            return publish()

                        published, publication_result = (
                            self.store.publish_snapshot_generation(
                                generation,
                                publish_after_terminal_proof,
                                rollback_authority=rollback_authority,
                            )
                        )
                finally:
                    # Record only after ExitStack releases every project lock:
                    # metrics take the runtime lock and must never introduce a
                    # project-lock -> runtime-lock ordering edge.
                    released_at = time.monotonic()
                    waited_until = (
                        all_locks_acquired
                        or first_lock_acquired
                        or released_at
                    )
                    self._record_terminal_publication_lock_timing(
                        wait_seconds=max(0.0, waited_until - wait_started),
                        hold_seconds=max(
                            0.0,
                            released_at
                            - (first_lock_acquired or released_at),
                        ),
                        superseded=superseded,
                    )
            if not published:
                reject_domains()
                if self.store.snapshot_generation_is_current(generation):
                    self.store.restore_snapshot_authority(
                        authority, snapshot_generation=generation
                    )
                with self._lock:
                    self._last_reconcile = report
                return report
            # The marker is now durable.  Everything below is non-authoritative
            # bookkeeping and must never route the committed generation back
            # through the pre-commit authority compensator.
            marker_committed = True
            report["reconciliation_phases"][
                "tracker_scoped_publication_advances"
            ] = tracker_scoped_publication_advances
            report["reconciliation_phases"][
                "tracker_scoped_publication_exclusions"
            ] = len(tracker_scoped_publication_exclusions)
            observation_committed = observation is not None
            if publication_observation is not None:
                if not isinstance(publication_result, ControllerPass):
                    logger.error(
                        "runtime liveness publication returned no controller pass"
                    )
                    assert liveness_controller is not None
                    liveness_controller.abort_runtime_observation(generation)
                else:
                    assert liveness_controller is not None
                    try:
                        finalized = liveness_controller.commit_runtime_observation(
                            publication_observation, publication_result
                        )
                        if not finalized:
                            liveness_controller.abort_runtime_observation(
                                generation
                            )
                    except Exception:
                        logger.exception(
                            "Runtime liveness bookkeeping failed after the "
                            "snapshot marker committed"
                        )
                        liveness_controller.abort_runtime_observation(generation)
                try:
                    assert liveness_controller is not None
                    health = liveness_controller.liveness_snapshot()
                    report["liveness"] = {
                        "snapshot_generation": generation,
                        "scan_complete": health.scan_complete,
                        "status": health.status,
                    }
                except Exception:
                    logger.exception(
                        "Runtime liveness health read failed after the snapshot "
                        "marker committed"
                    )
        except WorkflowPublicationSuperseded as exc:
            if self.store.snapshot_generation_is_current(generation):
                restored = self.store.restore_snapshot_authority(
                    authority, snapshot_generation=generation
                )
                if authoritative_projects and not restored:
                    raise WorkflowRuntimeError(
                        "superseded workflow snapshot could not restore its "
                        "durable authority checkpoint"
                    ) from exc
            restore = locals().get("restore_caches")
            if callable(restore):
                restore()
            reason = str(exc)
            for item in prepared:
                project_id = item["project_id"]
                logger.info(
                    "Durable workflow publication superseded for %s: %s",
                    project_id,
                    reason,
                )
                report["projects"][project_id] = {
                    "publication_superseded": True,
                    "reason": reason,
                }
            report["requires_reconcile"] = True
            report["reconcile_reason"] = "publication_authority_changed"
            if isinstance(
                exc,
                (
                    _WorkflowScopedPublicationChanged,
                    _WorkflowFinalPublicationChanged,
                ),
            ):
                report["_scoped_publication_retry"] = {
                    "project_id": getattr(exc, "project_id", None),
                    "changed_tasks": len(getattr(exc, "changed_tasks", ())),
                }
            with self._lock:
                self._last_reconcile = report
            return report
        except Exception as exc:
            if marker_committed:
                logger.exception(
                    "Post-commit workflow bookkeeping failed after snapshot "
                    "generation %s became authoritative",
                    generation,
                )
                report["postcommit_error"] = type(exc).__name__
                with self._lock:
                    self._last_reconcile = report
                return report
            if self.store.snapshot_generation_is_current(generation):
                restored = self.store.restore_snapshot_authority(
                    authority, snapshot_generation=generation
                )
                if authoritative_projects and not restored:
                    raise WorkflowRuntimeError(
                        "failed shared workflow snapshot could not restore its "
                        "durable authority checkpoint"
                    ) from exc
            restore = locals().get("restore_caches")
            if callable(restore):
                restore()
            for item in prepared:
                logger.exception(
                    "Durable workflow publication failed for %s",
                    item["project_id"],
                )
                report["projects"][item["project_id"]] = {
                    "error": type(exc).__name__,
                }
            with self._lock:
                self._last_reconcile = report
            return report
        finally:
            if (
                liveness_controller is not None
                and observation is not None
                and not observation_committed
            ):
                liveness_controller.abort_runtime_observation(generation)
            if liveness_lock is not None and liveness_lock_held:
                liveness_lock.release()

        for item, name, controller, _batch, result in reconciled:
            controller.scheduler.record_reconcile_metrics(result)
            report["projects"][item["project_id"]][name] = asdict(result)
        for item in prepared:
            project_id = item["project_id"]
            binding = item["binding"]
            project_report = report["projects"][project_id]
            project_report["snapshot"] = {
                "generation": generation,
                "members": sum(
                    member_project == project_id
                    for member_project, _task_id in expected_identities
                ),
                "jobs_superseded": membership.jobs_superseded,
                "published": True,
            }
            try:
                # Implementation is an imperative event lane. It is deliberately
                # outside managed membership, but cannot be exposed until the
                # shared managed cut has published. Its source-generation CAS
                # makes the next pass deterministic after a partial failure.
                implementation_batch = item["implementation_batch"]
                implementation_result = (
                    binding.implementation_controller.reconcile_evaluated(
                        implementation_batch,
                        snapshot_generation=generation,
                    )
                )
                project_report["implementation"] = asdict(implementation_result)
                for task in item["epic_batch"].tasks:
                    durable = tuple(
                        landing.to_dict()
                        for landing in task.facts.landings
                        if landing.durable
                    )
                    if durable:
                        self.store.record_landing_facts(
                            project_id=project_id,
                            task_id=task.task.identifier,
                            facts=durable,
                        )
                maintenance = getattr(
                    self, "_integration_maintenance_scheduler", None
                )
                if callable(maintenance):
                    history_job = maintenance(binding)
                    project_report["integration_history_job"] = (
                        history_job.job_id if history_job is not None else None
                    )
            except Exception as exc:
                logger.exception(
                    "Post-publication implementation reconcile failed for %s",
                    project_id,
                )
                report["projects"][project_id] = {
                    "error": type(exc).__name__,
                    "snapshot": dict(project_report["snapshot"]),
                }
        record_phase("snapshot_publication", publication_started)
        with self._lock:
            self._last_reconcile = report
        return report

    async def reconcile_async(
        self,
        *,
        admit_workers: bool = True,
    ) -> dict[str, Any]:
        """Async form used by the orchestrator's event-driven scheduler."""

        if not self._admit_reconcile():
            return {"mode": self.mode, "skipped": True}
        try:
            operation = asyncio.create_task(
                self._run_owned_reconcile_async(admit_workers=admit_workers),
                name="workflow-runtime-reconcile",
            )
        except BaseException:
            self._release_reconcile()
            raise
        with self._lock:
            self._reconcile_tasks.add(operation)
        operation.add_done_callback(self._reconcile_task_finished)
        return await asyncio.shield(operation)

    def _reconcile_task_finished(
        self,
        task: asyncio.Task[dict[str, Any]],
    ) -> None:
        with self._lock:
            self._reconcile_tasks.discard(task)
        try:
            task.exception()
        except asyncio.CancelledError:
            pass
        finally:
            # The callback runs even when loop teardown cancels the task before
            # its coroutine receives a first turn; a coroutine-local finally
            # cannot cover that pre-start state.
            self._release_reconcile()

    async def _run_owned_reconcile_async(
        self,
        *,
        admit_workers: bool,
    ) -> dict[str, Any]:
        """Retain reconcile authority until the actual operation finishes."""

        return await self._reconcile_async_once(admit_workers=admit_workers)

    async def _run_sync_reconcile_async(self) -> dict[str, Any]:
        """Keep a cancelled event-loop task fenced until its thread exits."""

        # Keep the executor awaitable as a bare Future. asyncio.run() cancels
        # every remaining Task during loop teardown, but it does not cancel
        # this Future; the owned reconcile task below can therefore defer its
        # cancellation until the executor target has actually returned.
        thread_future = asyncio.get_running_loop().run_in_executor(
            None,
            self._reconcile_once,
        )
        current_task = asyncio.current_task()
        cancellation_received = False
        while not thread_future.done():
            try:
                await asyncio.shield(thread_future)
            except asyncio.CancelledError:
                cancellation_received = True
                if current_task is not None and current_task.cancelling():
                    current_task.uncancel()
        if cancellation_received:
            try:
                thread_future.result()
            except Exception:  # noqa: BLE001 - cancellation remains caller-visible
                logger.exception(
                    "Workflow reconcile thread failed while cancellation was deferred"
                )
            raise asyncio.CancelledError
        return thread_future.result()

    def _refresh_admission_cut(
        self,
        report: Mapping[str, Any],
        project_ids: Sequence[str],
    ) -> _WorkflowAdmissionCut | None:
        """Publish the exact successful world cut used by fast admission."""

        generations: set[int] = set()
        projects = report.get("projects")
        if isinstance(projects, Mapping):
            for project_id in project_ids:
                project_report = projects.get(project_id)
                snapshot = (
                    project_report.get("snapshot")
                    if isinstance(project_report, Mapping)
                    else None
                )
                generation = (
                    snapshot.get("generation")
                    if isinstance(snapshot, Mapping)
                    and snapshot.get("published") is True
                    else None
                )
                if isinstance(generation, bool) or not isinstance(generation, int):
                    generations.clear()
                    break
                generations.add(generation)
        cut = None
        normalized_projects = tuple(sorted(set(project_ids)))
        if len(generations) == 1 and normalized_projects:
            generation = generations.pop()
            if self.store.published_snapshot_generation_is_current(generation):
                cut = _WorkflowAdmissionCut(generation, normalized_projects)
        with self._lock:
            self._admission_cut = cut
        return cut

    @staticmethod
    def _admission_skip(
        reason: str,
        *,
        requires_reconcile: bool,
        snapshot_generation: int | None = None,
    ) -> dict[str, Any]:
        return {
            "admission_only": True,
            "skipped": True,
            "reason": reason,
            "requires_reconcile": requires_reconcile,
            "snapshot_generation": snapshot_generation,
            "worker": {
                "skipped": True,
                "reason": reason,
                "batch_saturated": False,
            },
        }

    async def continue_admission_async(self) -> dict[str, Any]:
        """Admit one bounded slice from the exact last-published world cut.

        This path deliberately performs no tracker read, fact collection,
        controller evaluation, or snapshot publication.  Managed decisions
        remain bound to the cached published cut.  Imperative control events
        may use the reserved lane before that cut exists (or while a new cut
        is being assembled): their immutable event generation and the job
        store's task-ownership predicate are their independent authority.
        """

        if not self._admit_reconcile():
            return self._admission_skip(
                "workflow runtime is draining",
                requires_reconcile=False,
            )
        try:
            with self._lock:
                cut = self._admission_cut
                draining = self._draining
            if draining or not self.worker.accepting:
                return self._admission_skip(
                    "workflow runtime is not accepting effects",
                    requires_reconcile=False,
                    snapshot_generation=(
                        cut.snapshot_generation if cut is not None else None
                    ),
                )
            if not self._binding_topology_current():
                with self._lock:
                    if self._admission_cut == cut:
                        self._admission_cut = None
                return self._admission_skip(
                    "workflow project bindings changed",
                    requires_reconcile=True,
                    snapshot_generation=(
                        cut.snapshot_generation if cut is not None else None
                    ),
                )
            cut_is_current = bool(
                cut is not None
                and self.store.published_snapshot_generation_is_current(
                    cut.snapshot_generation
                )
            )
            if not cut_is_current:
                with self._lock:
                    if self._admission_cut == cut:
                        self._admission_cut = None
                enabled_project_rows: list[str] = []
                for project_id, binding in sorted(self.project_bindings.items()):
                    try:
                        enabled = binding.read_enabled_state()
                    except Exception:
                        logger.exception(
                            "Workflow control admission could not read pause "
                            "authority for %s",
                            project_id,
                        )
                        continue
                    if enabled:
                        enabled_project_rows.append(project_id)
                enabled_projects = tuple(enabled_project_rows)
                worker_report = (
                    await self._run_due(enabled_projects, control_only=True)
                    if self.enforce and self._handlers_configured
                    else None
                )
                reason = (
                    "no published workflow admission cut is available"
                    if cut is None
                    else "workflow admission cut is stale"
                )
                report = self._admission_skip(
                    reason,
                    requires_reconcile=True,
                    snapshot_generation=(
                        cut.snapshot_generation if cut is not None else None
                    ),
                )
                if worker_report is not None:
                    report["projects"] = list(enabled_projects)
                    report["worker"] = worker_report
                    with self._lock:
                        last = dict(self._last_reconcile)
                        last["worker"] = dict(worker_report)
                        last["admission"] = dict(report)
                        self._last_reconcile = last
                return report
            assert cut is not None
            try:
                enabled_projects = tuple(
                    project_id
                    for project_id in cut.project_ids
                    if self.project_bindings[project_id].read_enabled_state()
                )
            except Exception:
                enabled_projects = ()
            if enabled_projects != cut.project_ids:
                return self._admission_skip(
                    "workflow project admission changed",
                    requires_reconcile=True,
                    snapshot_generation=cut.snapshot_generation,
                )

            worker_report = await self._run_due(
                cut.project_ids,
                required_snapshot_generation=cut.snapshot_generation,
            )
            still_current = self.store.published_snapshot_generation_is_current(
                cut.snapshot_generation
            )
            queue_drained_after_completion = bool(
                worker_report.get("completed", 0)
                and not worker_report.get("scheduled", 0)
                and not worker_report.get("active", 0)
            )
            report = {
                "mode": self.mode,
                "admission_only": True,
                # Completion can change the facts from which the next durable
                # generation is derived. Drain the already-published queue
                # through this cheap path, then rebuild the world exactly once
                # at the empty boundary instead of once per concurrency slice.
                "requires_reconcile": (
                    not still_current or queue_drained_after_completion
                ),
                "reconcile_reason": (
                    "admission_cut_stale"
                    if not still_current
                    else (
                        "published_queue_drained"
                        if queue_drained_after_completion
                        else None
                    )
                ),
                "snapshot_generation": cut.snapshot_generation,
                "projects": list(cut.project_ids),
                "worker": worker_report,
            }
            with self._lock:
                last = dict(self._last_reconcile)
                last["worker"] = dict(worker_report)
                last["admission"] = dict(report)
                self._last_reconcile = last
                if not still_current and self._admission_cut == cut:
                    self._admission_cut = None
            return report
        finally:
            self._release_reconcile()

    async def _reconcile_async_once(
        self,
        *,
        admit_workers: bool = True,
    ) -> dict[str, Any]:
        """Run one admitted reconciliation without nested ownership."""

        if self.mode != "off" and self._topology_source is not None:
            try:
                current_topology = self._topology_source()
            except Exception as exc:
                report = {
                    "mode": self.mode,
                    "skipped": True,
                    "reason": "workflow project binding refresh failed",
                    "error": type(exc).__name__,
                }
            else:
                report = {
                    "mode": self.mode,
                    "skipped": True,
                    "reason": "workflow project bindings changed",
                    "restart_requested": True,
                }
                if current_topology == self._topology_signature:
                    report = {}
            if report:
                with self._lock:
                    self._last_reconcile = dict(report)
                    self._admission_cut = None
                if self._topology_change_handler is not None:
                    result = self._topology_change_handler()
                    if inspect.isawaitable(result):
                        await result
                return report

        report = await self._run_sync_reconcile_async()
        if self._handlers_configured and self.enforce:
            raw_project_reports = report.get("projects", {})
            project_reports = (
                raw_project_reports
                if isinstance(raw_project_reports, Mapping)
                else {}
            )
            publication_unstable = bool(report.get("requires_reconcile")) or any(
                isinstance(result, Mapping)
                and result.get("publication_superseded") is True
                for result in project_reports.values()
            )
            if publication_unstable:
                with self._lock:
                    self._admission_cut = None
                report["worker"] = {
                    "skipped": True,
                    "reason": (
                        "workflow publication requires reconciliation before "
                        "durable admission"
                    ),
                    "projects": sorted(project_reports),
                    "batch_saturated": False,
                }
                with self._lock:
                    self._last_reconcile = report
                return report
            failed_projects = sorted(
                project_id
                for project_id, result in project_reports.items()
                if "error" in result
            )
            runnable_projects = sorted(
                project_id
                for project_id, result in project_reports.items()
                if "error" not in result and not result.get("skipped", False)
            )
            if not runnable_projects:
                with self._lock:
                    self._admission_cut = None
                report["worker"] = {
                    "skipped": True,
                    "reason": (
                        "no reconciled project is eligible for durable work"
                    ),
                    "projects": failed_projects,
                    "batch_saturated": False,
                }
            else:
                # A failed project must not stall unrelated healthy projects.
                # Exact project claims also keep paused projects' queued rows
                # durable without consuming attempts while they are disabled.
                admission_cut = self._refresh_admission_cut(
                    report, runnable_projects
                )
                if admit_workers:
                    report["worker"] = await self._run_due(
                        runnable_projects,
                        required_snapshot_generation=(
                            admission_cut.snapshot_generation
                            if admission_cut is not None
                            else None
                        ),
                    )
                else:
                    report["worker"] = {
                        "skipped": True,
                        "reason": (
                            "workflow worker admission deferred until the "
                            "restart audit-priority boundary"
                        ),
                        "projects": runnable_projects,
                        "batch_saturated": False,
                    }
                if failed_projects:
                    report["worker"]["failed_projects"] = failed_projects
            with self._lock:
                self._last_reconcile = report
        return report

    async def _run_due(
        self,
        project_ids: Sequence[str],
        *,
        required_snapshot_generation: int | None = None,
        control_only: bool = False,
    ) -> dict[str, Any]:
        active_projects = tuple(
            dict.fromkeys(str(value) for value in project_ids)
        )
        with self._lock:
            completed = tuple(self._effect_results)
            self._effect_results.clear()
            active_by_lane = {
                lane: sum(
                    task_lane == lane
                    for task_lane in self._effect_tasks.values()
                )
                for lane in ("control", "shared")
            }
        scheduled = 0
        admission_saturated = False
        async with self._effect_admission_lock:
            if active_projects and not self._draining and self.worker.accepting:
                remaining = self.batch_size
                lane_limits = (
                    (
                        "control",
                        self.control_reserved_slots,
                        tuple(sorted(RUNTIME_CONTROL_ACTIONS)),
                    ),
                    (
                        "shared",
                        self.max_concurrent - self.control_reserved_slots,
                        tuple(sorted(RUNTIME_ACTIONS)),
                    ),
                )
                if control_only:
                    lane_limits = lane_limits[:1]
                for lane, capacity, actions in lane_limits:
                    with self._lock:
                        lane_active = sum(
                            task_lane == lane
                            for task_lane in self._effect_tasks.values()
                        )
                    free = max(capacity - lane_active, 0)
                    for _index in range(min(free, remaining)):
                        job = await self.worker.claim_next(
                            project_ids=active_projects,
                            actions=actions,
                            required_snapshot_generation=(
                                required_snapshot_generation
                            ),
                            fair_across_projects=True,
                        )
                        if job is None:
                            break
                        task = asyncio.create_task(
                            self.worker.execute_claimed(job),
                            name=f"workflow-effect:{lane}:{job.job_id}",
                        )
                        with self._lock:
                            self._effect_tasks[task] = lane
                        task.add_done_callback(self._effect_finished)
                        scheduled += 1
                        remaining -= 1
                    if remaining <= 0:
                        break

                admission_saturated = scheduled >= self.batch_size
                if scheduled and not admission_saturated:
                    # A runtime whose concurrency is smaller than its batch
                    # size can fill every execution slot without ever reaching
                    # the historical per-pass cap.  Request a continuation
                    # only when an exact eligible suffix remains.  Requiring a
                    # new admission prevents repeated ticks from spinning while
                    # the same long-running effects still occupy the lanes;
                    # their completion callbacks provide the replenishment
                    # edge instead.
                    for lane, capacity, actions in lane_limits:
                        with self._lock:
                            lane_active = sum(
                                task_lane == lane
                                for task_lane in self._effect_tasks.values()
                            )
                        if lane_active < capacity:
                            continue
                        if await self.worker.has_claimable(
                            project_ids=active_projects,
                            actions=actions,
                            required_snapshot_generation=(
                                required_snapshot_generation
                            ),
                        ):
                            admission_saturated = True
                            break

        with self._lock:
            if not scheduled and self._effect_results:
                completed = (*completed, *self._effect_results)
                self._effect_results.clear()
            active_by_lane = {
                lane: sum(
                    task_lane == lane
                    for task_lane in self._effect_tasks.values()
                )
                for lane in ("control", "shared")
            }
        active = sum(active_by_lane.values())
        completed_count = len(completed)
        if not completed and not scheduled and not active:
            return {
                "disposition": "idle",
                "job_id": None,
                "state": None,
                "reason": "no eligible durable workflow project",
                "processed": 0,
                "completed": 0,
                "scheduled": 0,
                "active": 0,
                "active_lanes": active_by_lane,
                "batch_saturated": False,
            }
        result = completed[-1] if completed else None
        return {
            "disposition": (
                result.disposition.value if result is not None else "scheduled"
            ),
            "job_id": result.job_id if result is not None else None,
            "state": (
                result.state.value
                if result is not None and result.state is not None
                else None
            ),
            "reason": (
                result.reason
                if result is not None
                else "durable effects admitted without blocking reconciliation"
            ),
            # ``processed`` historically meant rows claimed by this pass.
            # Claims are now admitted rather than awaited, so retain that
            # operational meaning and expose completions separately.
            "processed": scheduled,
            "completed": completed_count,
            "scheduled": scheduled,
            "active": active,
            "active_lanes": active_by_lane,
            # Completion callbacks replenish concurrency.  This signal also
            # covers an exact claimable suffix blocked by lane concurrency
            # when max_concurrent is smaller than the per-pass batch cap.
            "batch_saturated": admission_saturated,
        }

    def _effect_finished(self, task: asyncio.Task[Any]) -> None:
        """Retire one retained invocation and publish a replenishment edge."""

        result: Any | None = None
        completion: Any = WorkflowEffectCleanup(
            cancelled=task.cancelled(),
            error_type=None,
        )
        failure: BaseException | None = None
        try:
            result = task.result()
        except asyncio.CancelledError:
            pass
        except Exception as exc:  # noqa: BLE001 - worker claim boundary observable
            failure = exc
            completion = WorkflowEffectCleanup(
                cancelled=False,
                error_type=type(exc).__name__,
            )
        with self._lock:
            if task not in self._effect_tasks:
                return
            if result is not None:
                self._effect_results.append(result)
                completion = result
            self._effect_tasks.pop(task, None)
        if failure is not None:
            logger.error(
                "Detached durable workflow invocation failed",
                exc_info=(type(failure), failure, failure.__traceback__),
            )
        # State convergence is unconditional after retained ownership exits.
        # The production observer independently fences new admission during
        # drain/pause/quiesce while still refreshing its lightweight snapshot.
        if self._effect_completion_observer is not None:
            try:
                self._effect_completion_observer(completion)
            except Exception:  # noqa: BLE001 - observation cannot fail the job
                logger.exception("Failed to publish durable workflow completion")

    def _record_terminal_publication_lock_timing(
        self,
        *,
        wait_seconds: float,
        hold_seconds: float,
        superseded: bool = False,
    ) -> None:
        """Record truthful final-CAS lock timing without affecting authority."""

        wait = max(float(wait_seconds), 0.0)
        hold = max(float(hold_seconds), 0.0)
        with self._lock:
            metrics = self._terminal_publication_lock_metrics
            metrics["acquisitions"] = int(metrics["acquisitions"]) + 1
            metrics["superseded"] = int(metrics["superseded"]) + int(superseded)
            for prefix, value in (("wait", wait), ("hold", hold)):
                total = f"{prefix}_seconds_total"
                maximum = f"{prefix}_seconds_max"
                last = f"{prefix}_seconds_last"
                metrics[total] = float(metrics[total]) + value
                metrics[maximum] = max(float(metrics[maximum]), value)
                metrics[last] = value

    def _lifecycle_handlers(self) -> tuple[WorkflowActionHandler, ...]:
        """Return unique project-leaf handlers which may own background work."""

        unique: dict[int, WorkflowActionHandler] = {}
        for handler in self.handlers.values():
            routed = getattr(handler, "handlers", None)
            candidates = routed.values() if isinstance(routed, Mapping) else (handler,)
            for candidate in candidates:
                unique.setdefault(id(candidate), candidate)
        return tuple(unique.values())

    @property
    def pending_mutation_count(self) -> int:
        return sum(
            int(getattr(handler, "pending_mutation_count", 0) or 0)
            for handler in self._lifecycle_handlers()
        )

    @staticmethod
    def is_control_action(action: Any) -> bool:
        """Return whether an effect owns reserved runtime capacity."""

        normalized = str(getattr(action, "value", action) or "")
        return normalized in RUNTIME_CONTROL_ACTIONS

    @property
    def pending_operation_count(self) -> int:
        """Operations which make closing stores unsafe."""

        with self._lock:
            active_reconciles = self._active_reconciles
            retained_effects = len(self._effect_tasks)
        return (
            active_reconciles
            + max(self.worker.active_count, retained_effects)
            + self.pending_mutation_count
        )

    async def _drain_handler_mutations(
        self, *, timeout_seconds: float | None
    ) -> bool:
        drains = [
            getattr(handler, "drain_mutations")
            for handler in self._lifecycle_handlers()
            if callable(getattr(handler, "drain_mutations", None))
            and int(getattr(handler, "pending_mutation_count", 0) or 0) > 0
        ]
        if not drains:
            return True
        if timeout_seconds is not None and timeout_seconds <= 0:
            return False
        pending = [drain(timeout_seconds=None) for drain in drains]
        waiter = asyncio.gather(*pending, return_exceptions=True)
        try:
            if timeout_seconds is None:
                results = await waiter
            else:
                results = await asyncio.wait_for(
                    asyncio.shield(waiter), timeout_seconds
                )
        except TimeoutError:
            return False
        return all(
            not isinstance(result, BaseException) and result is not False
            for result in results
        )

    async def drain(self, *, timeout_seconds: float | None = 10.0) -> bool:
        with self._lock:
            self._draining = True
        if timeout_seconds is not None and timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        loop = asyncio.get_running_loop()
        deadline = (
            None if timeout_seconds is None else loop.time() + timeout_seconds
        )
        reconciles_drained = await asyncio.to_thread(
            self._wait_for_reconciles,
            timeout_seconds,
        )
        if not reconciles_drained:
            return False
        remaining = None if deadline is None else max(0.0, deadline - loop.time())
        worker_drained = await self.worker.drain(timeout_seconds=remaining)
        if not worker_drained:
            return False
        with self._lock:
            retained = tuple(self._effect_tasks)
        if retained:
            remaining = None if deadline is None else max(0.0, deadline - loop.time())
            if remaining is not None and remaining <= 0:
                return False
            settlement = loop.create_future()
            callback_pending = set(retained)

            def observe_settlement(task: asyncio.Task[Any]) -> None:
                callback_pending.discard(task)
                if not callback_pending and not settlement.done():
                    settlement.set_result(None)

            # These callbacks are registered after ``_effect_finished`` and
            # therefore run after its result publication and retained-entry
            # removal.  Waiting on task completion alone is insufficient: a
            # done task can still have its settlement callback queued.
            for task in retained:
                task.add_done_callback(observe_settlement)
            try:
                if remaining is None:
                    await settlement
                else:
                    await asyncio.wait_for(asyncio.shield(settlement), remaining)
            except TimeoutError:
                return False
            with self._lock:
                if any(task in self._effect_tasks for task in retained):
                    return False
        remaining = None if deadline is None else max(0.0, deadline - loop.time())
        return await self._drain_handler_mutations(timeout_seconds=remaining)

    def close(self) -> None:
        """Close transition journals; the orchestrator owns the job store."""

        if self._closed:
            return
        pending = self.pending_operation_count
        if pending:
            raise WorkflowRuntimeError(
                "cannot close workflow runtime while "
                f"{pending} operation(s) are still running"
            )
        for journal in set(self.journals.values()):
            journal.close()
        self._closed = True

    def projections(self) -> tuple[dict[str, Any], ...]:
        rows: list[dict[str, Any]] = []
        with self._lock:
            decisions = tuple(self._latest_decisions.values())
        for decision in sorted(
            decisions, key=lambda item: (item.project_id, item.task_id)
        ):
            rows.append(decision.to_dict())
        return tuple(rows)

    def _binding_topology_current(self) -> bool:
        if self._topology_source is None:
            return True
        try:
            return self._topology_source() == self._topology_signature
        except Exception:
            return False

    def health_snapshot(self) -> dict[str, Any]:
        with self._lock:
            last = dict(self._last_reconcile)
            admission_cut = self._admission_cut
            retained_effects = len(self._effect_tasks)
            terminal_publication_lock = dict(
                self._terminal_publication_lock_metrics
            )
        controller_health = (
            self.liveness_controller.health_snapshot()
            if self.liveness_controller is not None
            else None
        )
        rollout_gate = self.store.rollout_readiness(
            min_shadow_sweeps=self.rollout_min_shadow_sweeps,
            min_shadow_seconds=self.rollout_min_shadow_seconds,
        )
        rollout = rollout_gate.pop("rollout")
        return {
            "mode": self.mode,
            "domain_modes": dict(self.domain_modes),
            "rollout": rollout,
            "rollout_gate": rollout_gate,
            "started": self._started,
            "draining": self._draining,
            "admission_cut": (
                {
                    "snapshot_generation": admission_cut.snapshot_generation,
                    "projects": list(admission_cut.project_ids),
                }
                if admission_cut is not None
                else None
            ),
            "legacy_lifecycle_writers_enabled": self.legacy_lifecycle_writers_enabled,
            "projects": sorted(self.project_bindings),
            "controllers": {
                project_id: [
                    type(controller).__name__ for controller in binding.controllers
                ]
                for project_id, binding in sorted(self.project_bindings.items())
            },
            "worker": {
                "accepting": self.worker.accepting,
                "active": self.worker.active_count,
                "quarantined_calls": self.worker.quarantined_call_count,
                "quarantine_monitors": self.worker.quarantine_monitor_count,
                "max_concurrent": self.max_concurrent,
                "control_reserved_slots": self.control_reserved_slots,
                "retained": retained_effects,
                "handlers_configured": self._handlers_configured,
            },
            "terminal_publication_lock": terminal_publication_lock,
            "last_reconcile": last,
            "controller": controller_health,
            "liveness": (
                controller_health.get("liveness")
                if isinstance(controller_health, Mapping)
                else None
            ),
            "binding_topology_current": self._binding_topology_current(),
            "jobs": self.store.health_snapshot(),
        }

    def record_event(self, phase: str, job: Any) -> None:
        with self._lock:
            self._events.append(
                WorkflowRuntimeEvent(
                    str(phase),
                    str(job.job_id),
                    str(job.project_id),
                    str(job.task_id),
                    str(job.action),
                )
            )
            del self._events[:-128]
        if (
            str(phase) == "transition_applied"
            and self._transition_observer is not None
        ):
            try:
                self._transition_observer(job)
            except Exception:  # noqa: BLE001 - observation cannot fail the job
                logger.exception(
                    "Failed to publish durable workflow transition for %s",
                    getattr(job, "task_id", "unknown"),
                )
        if (
            str(phase) == "quarantine_settled"
            and self._effect_completion_observer is not None
        ):
            try:
                self._effect_completion_observer(job)
            except Exception:  # noqa: BLE001 - observation cannot fail recovery
                logger.exception(
                    "Failed to publish quarantined workflow recovery for %s",
                    getattr(job, "task_id", "unknown"),
                )


def build_workflow_runtime(orchestrator: Any, **kwargs: Any) -> WorkflowRuntime:
    """Public bootstrap helper kept small for startup and integration tests."""

    return WorkflowRuntime.from_orchestrator(orchestrator, **kwargs)
