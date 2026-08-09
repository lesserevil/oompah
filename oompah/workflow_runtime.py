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
import inspect
import logging
import os
import re
import subprocess
import threading
import uuid
from collections import deque
from collections.abc import Callable, Mapping, Sequence
from contextlib import ExitStack
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Protocol

from oompah.epic_workflow import (
    EPIC_ACTIONS,
    EpicAction,
    EpicFactCollector,
    EpicWorkflowController,
)
from oompah.events import EventType
from oompah.implementation_workflow import (
    FACT_IMPLEMENTATION_LANE,
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
    IN_REVIEW,
    IN_VALIDATION,
    MERGED,
    READY_TO_INTEGRATE,
    canonicalize_status,
)
from oompah.task_transition_service import (
    CoordinatorTerminalAdapter,
    TaskTransitionService,
    TransitionJournal,
    issue_authority_version,
)
from oompah.workflow_contract import LIFECYCLE_FINAL_STATUSES, TaskDisposition
from oompah.workflow_controller import (
    ControllerObservation,
    ControllerPass,
    UniversalTotalityLivenessController,
)
from oompah.workflow_fact_model import FactDomain, FactState, WorkflowFacts
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


class WorkflowRuntimeError(RuntimeError):
    """Raised when durable runtime composition is invalid."""


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
    terminal_audit_publication_lock: Callable[[], Any] | None = None

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
        self._latest_decisions: dict[tuple[str, str], Any] = {}
        self._events: list[WorkflowRuntimeEvent] = []
        self._effect_tasks: dict[asyncio.Task[Any], str] = {}
        self._effect_results: deque[Any] = deque(maxlen=128)
        # Claiming awaits SQLite off-loop. Keep the capacity observation,
        # exact claim, and retained-task publication inside one async critical
        # section so overlapping reconciles cannot both spend the same slot.
        self._effect_admission_lock = asyncio.Lock()
        self._closed = False
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

        # The source callbacks close over the binding being built.  This lets
        # implementation authority come from the durable implementation
        # controller instead of the legacy in-memory running map as soon as
        # that adapter is present.
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
                legacy_sources = getattr(orchestrator, "_workflow_shadow_sources", None)
                if callable(legacy_sources):
                    legacy_source = legacy_sources(issue).get(domain)
                    return (
                        legacy_source(issue)
                        if callable(legacy_source)
                        else legacy_source
                    )
                return None

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
                *,
                _controller=epic_controller,
                _integration_controller=integration_controller,
                _tracker=tracker,
            ) -> str | None:
                guarded_reason = str(intent.reason_code or "").strip()
                invalidate = getattr(_tracker, "invalidate_read_cache", None)
                if callable(invalidate):
                    invalidate()
                guarded_issue = _tracker.fetch_issue_detail(intent.task_id)
                if guarded_issue is None:
                    return "guarded issue is unavailable"
                if issue_authority_version(guarded_issue) != intent.expected_version:
                    return "task transition authority changed"
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
                decision = batch.tasks[0].decision
                if decision.evidence_revision != intent.precondition_revision:
                    return "epic workflow evidence or containment changed"
                if (
                    guarded_reason == "terminal.immediate_target_landing_proven"
                    and EpicAction.AUTO_CLOSE.value not in decision.durable_jobs
                ):
                    return "epic auto-close is no longer authorized"
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
                review_controller=ReviewWorkflowController(
                    collector=review_collector,
                    store=store,
                    decision_limit=configured_limit,
                ),
                integration_controller=integration_controller,
                epic_collector=epic_collector,
                epic_controller=epic_controller,
                terminal_audit_workflow=terminal_workflow,
                transition_journal=journal,
                terminal_audit_proof_source=terminal_audit_proof_source,
                terminal_audit_snapshot_proof_source=(
                    terminal_audit_snapshot_proof_source
                ),
                terminal_audit_publication_lock=(
                    lambda _project_id=project_id: project_store.project_write_lock(
                        _project_id
                    )
                )
                if callable(getattr(project_store, "project_write_lock", None))
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
            orchestrator.request_refresh()

        def effect_completion_observer(result: Any) -> None:
            # Completion is the replenishment edge for detached execution.
            # Idle admission probes are impossible because the runtime claims
            # before spawning, so every callback represents durable progress
            # and may safely request one coalesced controller pass.
            if getattr(result, "job_id", None) is not None:
                orchestrator.request_refresh()

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
    ) -> dict[tuple[str, str], Any]:
        """Atomically publish one project's complete in-memory decision cut."""

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
                    retained[(decision.project_id, decision.task_id)] = decision
            self._latest_decisions = retained
            return previous

    def _publish_runtime_projection(
        self,
        decisions: Sequence[WorkDecision],
        *,
        authoritative_project_ids: Sequence[str],
    ) -> None:
        """Replace successful projects with one domain-owned projection cut."""

        projects = set(authoritative_project_ids)
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
                    if self.store.event_lane_materialized(
                        project_id=decision.project_id,
                        task_id=decision.task_id,
                        ordering_namespace=IMPLEMENTATION_ORDERING_NAMESPACE,
                        scheduling_lane=FACT_IMPLEMENTATION_LANE,
                        source_revision=(
                            item["binding"]
                            .implementation_controller.scheduler.decision_revision(
                                decision
                            )
                        ),
                        actions=(action,),
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
            try:
                materialized = bool(
                    proof_source(decision, value, next(iter(terminal_actions)))
                ) if callable(proof_source) and len(terminal_actions) == 1 else False
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

    def _reconcile_once(self) -> dict[str, Any]:
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
        policy_cut = self._capture_liveness_policy()
        liveness_slo_seconds = (
            policy_cut.seconds if policy_cut is not None else None
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
                    issues = self._issues(binding)
                    task_issues = [
                        issue
                        for issue in issues
                        if str(getattr(issue, "issue_type", "") or "")
                        .strip()
                        .lower()
                        != "epic"
                    ]
                    epic_issues = [
                        issue
                        for issue in issues
                        if str(getattr(issue, "issue_type", "") or "")
                        .strip()
                        .lower()
                        == "epic"
                        and canonicalize_status(issue.state) != IN_VALIDATION
                    ]
                    named_batches: list[tuple[str, Any]] = []
                    if self.domain_modes["implementation"] != "off":
                        named_batches.append(
                            (
                                "implementation",
                                binding.implementation_controller.evaluate(
                                    task_issues,
                                    liveness_slo_seconds=liveness_slo_seconds,
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
        for project_id, binding in sorted(self.project_bindings.items()):
            try:
                binding_enabled = binding.read_enabled_state()
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
                issues = self._issues(binding)
                task_issues = [
                    issue
                    for issue in issues
                    if str(getattr(issue, "issue_type", "") or "").strip().lower()
                    != "epic"
                ]
                epic_issues = [
                    issue
                    for issue in issues
                    if str(getattr(issue, "issue_type", "") or "").strip().lower()
                    == "epic"
                    and canonicalize_status(issue.state) != IN_VALIDATION
                ]
                implementation_checkpoint = dict(
                    binding.implementation_controller._latest
                )
                try:
                    implementation_batch = (
                        binding.implementation_controller.evaluate(
                            task_issues,
                            liveness_slo_seconds=liveness_slo_seconds,
                        )
                    )
                finally:
                    binding.implementation_controller._latest = (
                        implementation_checkpoint
                    )
                review_checkpoint = (
                    binding.review_controller.projection_checkpoint()
                )
                review_batch = binding.review_controller.evaluate(
                    task_issues,
                    liveness_slo_seconds=liveness_slo_seconds,
                )
                review_batch = self._scope_domain_decisions(
                    "review", review_batch, REVIEW_ACTION_JOBS
                )

                integration_checkpoint = dict(
                    binding.integration_controller._latest
                )
                try:
                    integration_batch = binding.integration_controller.evaluate(
                        task_issues,
                        liveness_slo_seconds=liveness_slo_seconds,
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
                    epic_batch = binding.epic_controller.evaluate(
                        epic_issues,
                        persist_evidence=False,
                        liveness_slo_seconds=liveness_slo_seconds,
                    )
                    evaluated_epic_landings = dict(
                        binding.epic_controller._landings
                    )
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
                project_liveness_facts = {
                    (project_id, issue.identifier): binding.collector.collect(
                        issue.identifier
                    )
                    for issue in project_liveness_tasks
                }
                # Reuse the exact owning-domain fact cut where one exists.
                # A generic recollection can omit domain-specific landing
                # requests and therefore hash differently from the cursor it
                # must inspect for exhaustion/current authority.
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
                        if identity in project_liveness_facts and isinstance(
                            task_decision.facts, WorkflowFacts
                        ):
                            project_liveness_facts[identity] = (
                                task_decision.facts
                            )
                liveness_tasks.extend(project_liveness_tasks)
                liveness_facts.update(project_liveness_facts)

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
                prepared.append(
                    {
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
                    }
                )
                report["projects"][project_id] = {"issues": len(issues)}
            except Exception as exc:
                logger.exception(
                    "Durable workflow source evaluation failed for %s", project_id
                )
                report["projects"][project_id] = {
                    "error": type(exc).__name__,
                }
                source_errors[project_id] = type(exc).__name__

        authoritative_projects = tuple(
            item["project_id"] for item in prepared
        )
        expected_identities = tuple(
            sorted(identity for item in prepared for identity in item["expected"])
        )
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
        if liveness_lock is not None:
            liveness_lock.acquire()
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

            def restore_caches() -> None:
                with self._lock:
                    self._latest_decisions = dict(runtime_checkpoint)
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
                        )
                    if publication_observation is not None:
                        self._publish_runtime_projection(
                            projection_decisions,
                            authoritative_project_ids=authoritative_projects,
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
            # stores.  Revalidate every proof while holding the project's
            # metadata write lock through the durable snapshot marker, so a
            # pending-record replacement cannot race between proof and
            # publication.
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
                    and str(observed.get("request_state") or "")
                    in {"pending", "in_progress"}
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

            with ExitStack() as publication_locks:
                locked_projects: set[str] = set()
                proof_bindings = [
                    item[0] for item in terminal_publication_proofs
                ] + [item[0] for item in terminal_snapshot_proofs]
                for binding in sorted(
                    proof_bindings, key=lambda item: item.project_id
                ):
                    if binding.project_id in locked_projects:
                        continue
                    lock_source = binding.terminal_audit_publication_lock
                    if not callable(lock_source):
                        raise WorkflowRuntimeError(
                            "terminal-audit publication lock is unavailable"
                        )
                    publication_locks.enter_context(lock_source())
                    locked_projects.add(binding.project_id)
                def publish_after_terminal_proof() -> WorkflowSnapshotPublication:
                    # ``publish_snapshot_generation`` invokes this callback
                    # after acquiring the cross-process authority guard and
                    # opening its marker transaction.  Job claim/completion,
                    # retry, failure, and cancellation therefore cannot race
                    # this final proof-to-marker interval.
                    for binding, decision, observed in terminal_snapshot_proofs:
                        proof_source = (
                            binding.terminal_audit_snapshot_proof_source
                        )
                        if not callable(proof_source) or not proof_source(
                            decision, observed
                        ):
                            raise WorkflowRuntimeError(
                                "terminal-audit disposition changed before "
                                "publication"
                            )
                    for (
                        binding,
                        decision,
                        observed,
                        action,
                    ) in terminal_publication_proofs:
                        proof_source = binding.terminal_audit_proof_source
                        if not callable(proof_source) or not proof_source(
                            decision, observed, action
                        ):
                            raise WorkflowRuntimeError(
                                "terminal-audit authority changed before publication"
                            )
                    return publish()

                published, publication_result = (
                    self.store.publish_snapshot_generation(
                        generation,
                        publish_after_terminal_proof,
                        rollback_authority=rollback_authority,
                    )
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
            if liveness_lock is not None:
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
        with self._lock:
            self._last_reconcile = report
        return report

    async def reconcile_async(self) -> dict[str, Any]:
        """Async form used by the orchestrator's event-driven scheduler."""

        if not self._admit_reconcile():
            return {"mode": self.mode, "skipped": True}
        try:
            operation = asyncio.create_task(
                self._run_owned_reconcile_async(),
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

    async def _run_owned_reconcile_async(self) -> dict[str, Any]:
        """Retain reconcile authority until the actual operation finishes."""

        return await self._reconcile_async_once()

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

    async def _reconcile_async_once(self) -> dict[str, Any]:
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
                if self._topology_change_handler is not None:
                    result = self._topology_change_handler()
                    if inspect.isawaitable(result):
                        await result
                return report

        report = await self._run_sync_reconcile_async()
        if self._handlers_configured and self.enforce:
            failed_projects = sorted(
                project_id
                for project_id, result in report.get("projects", {}).items()
                if "error" in result
            )
            runnable_projects = sorted(
                project_id
                for project_id, result in report.get("projects", {}).items()
                if "error" not in result and not result.get("skipped", False)
            )
            if not runnable_projects:
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
                report["worker"] = await self._run_due(runnable_projects)
                if failed_projects:
                    report["worker"]["failed_projects"] = failed_projects
            with self._lock:
                self._last_reconcile = report
        return report

    async def _run_due(self, project_ids: Sequence[str]) -> dict[str, Any]:
        active_projects = tuple(
            dict.fromkeys(str(value) for value in project_ids)
        )
        with self._lock:
            completed = tuple(self._effect_results)
            self._effect_results.clear()
            active_by_lane = {
                lane: sum(
                    task_lane == lane and not task.done()
                    for task, task_lane in self._effect_tasks.items()
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
                for lane, capacity, actions in lane_limits:
                    with self._lock:
                        lane_active = sum(
                            task_lane == lane and not task.done()
                            for task, task_lane in self._effect_tasks.items()
                        )
                    free = max(capacity - lane_active, 0)
                    for _index in range(min(free, remaining)):
                        job = await self.worker.claim_next(
                            project_ids=active_projects,
                            actions=actions,
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
                                task_lane == lane and not task.done()
                                for task, task_lane in self._effect_tasks.items()
                            )
                        if lane_active < capacity:
                            continue
                        if await self.worker.has_claimable(
                            project_ids=active_projects,
                            actions=actions,
                        ):
                            admission_saturated = True
                            break

        with self._lock:
            active_by_lane = {
                lane: sum(
                    task_lane == lane and not task.done()
                    for task, task_lane in self._effect_tasks.items()
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

        with self._lock:
            self._effect_tasks.pop(task, None)
        try:
            result = task.result()
        except asyncio.CancelledError:
            return
        except Exception:  # noqa: BLE001 - worker claim boundary stays observable
            logger.exception("Detached durable workflow invocation failed")
            return
        with self._lock:
            self._effect_results.append(result)
            draining = self._draining
        if not draining and self._effect_completion_observer is not None:
            try:
                self._effect_completion_observer(result)
            except Exception:  # noqa: BLE001 - observation cannot fail the job
                logger.exception("Failed to publish durable workflow completion")

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

    @property
    def pending_operation_count(self) -> int:
        """Operations which make closing stores unsafe."""

        with self._lock:
            active_reconciles = self._active_reconciles
            retained_effects = sum(
                not task.done() for task in self._effect_tasks
            )
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
            retained = tuple(
                task for task in self._effect_tasks if not task.done()
            )
        if retained:
            remaining = None if deadline is None else max(0.0, deadline - loop.time())
            if remaining is not None and remaining <= 0:
                return False
            waiter = asyncio.gather(*retained, return_exceptions=True)
            try:
                if remaining is None:
                    await waiter
                else:
                    await asyncio.wait_for(asyncio.shield(waiter), remaining)
            except TimeoutError:
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
            retained_effects = sum(
                not task.done() for task in self._effect_tasks
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
