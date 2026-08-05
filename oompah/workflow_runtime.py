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
import threading
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

from oompah.epic_workflow import EPIC_ACTIONS, EpicFactCollector, EpicWorkflowController
from oompah.implementation_workflow import (
    IMPLEMENTATION_ACTIONS,
    ImplementationWorkflowController,
)
from oompah.integration_workflow import (
    INTEGRATION_ACTIONS,
    IntegrationWorkflowController,
)
from oompah.review_workflow import ReviewWorkflowController
from oompah.statuses import IN_VALIDATION, canonicalize_status
from oompah.task_transition_service import (
    CoordinatorTerminalAdapter,
    TaskTransitionService,
    TransitionJournal,
)
from oompah.workflow_facts import FactDomain, GitLandingCollector, WorkflowFactCollector
from oompah.workflow_jobs import (
    WorkflowFailureCategory,
    WorkflowJobStore,
)
from oompah.workflow_worker import (
    EffectObservation,
    EffectResult,
    RevalidationResult,
    VerificationResult,
    WorkflowActionDomain,
    WorkflowActionError,
    WorkflowActionHandler,
    WorkflowJobContext,
    DurableWorkflowWorker,
)
from oompah.work_decision import REVIEW_ACTION_JOBS

logger = logging.getLogger(__name__)

LEGACY_PROJECT_ID = "legacy"
DEFAULT_RUNTIME_DECISION_LIMIT = 100
DEFAULT_RUNTIME_BATCH_SIZE = 32

_DOMAIN_ACTIONS = {
    "implementation": IMPLEMENTATION_ACTIONS,
    "review": REVIEW_ACTION_JOBS,
    "integration": INTEGRATION_ACTIONS,
    "epic": EPIC_ACTIONS,
}
RUNTIME_ACTIONS = frozenset().union(*_DOMAIN_ACTIONS.values())
_RUNTIME_OWNER_PATTERN = re.compile(
    r"^workflow-runtime:(?P<pid>[1-9][0-9]*):[0-9a-f]+$"
)

if sum(len(actions) for actions in _DOMAIN_ACTIONS.values()) != len(RUNTIME_ACTIONS):
    raise RuntimeError("durable workflow domain action sets overlap")


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

    @property
    def enabled(self) -> bool:
        """Whether this project's durable worker may claim new work."""

        if self.dispatch_enabled is None:
            return True
        try:
            return bool(self.dispatch_enabled())
        except Exception:
            # Pause/configuration authority is a correctness boundary.  A
            # failed read must never be interpreted as permission to mutate.
            return False

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

    def _handler(self, context: WorkflowJobContext) -> WorkflowActionHandler:
        enabled = self._project_enabled.get(context.job.project_id)
        if enabled is not None:
            try:
                may_run = bool(enabled())
            except Exception:
                may_run = False
            if not may_run:
                raise WorkflowActionError(
                    "durable workflow project is paused or quiesced",
                    category=WorkflowFailureCategory.TRANSIENT,
                    retryable=True,
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


class WorkflowRuntime:
    """Own the durable workflow services for the lifetime of one process."""

    def __init__(
        self,
        *,
        project_bindings: Mapping[str, WorkflowProjectBinding],
        store: WorkflowJobStore,
        journals: Mapping[str, TransitionJournal],
        mode: str = "off",
        handlers: Mapping[str, WorkflowActionHandler] | None = None,
        decision_limit: int = DEFAULT_RUNTIME_DECISION_LIMIT,
        batch_size: int = DEFAULT_RUNTIME_BATCH_SIZE,
        worker: DurableWorkflowWorker | None = None,
        handler_coverage: Mapping[str, Sequence[str]] | None = None,
        abandoned_lease_owners: Sequence[str] = (),
        topology_signature: tuple[Any, ...] | None = None,
        topology_source: Callable[[], tuple[Any, ...]] | None = None,
        topology_change_handler: Callable[[], Any] | None = None,
    ) -> None:
        normalized_mode = str(mode or "off").strip().lower()
        if normalized_mode not in {"off", "shadow", "enforce"}:
            raise ValueError("workflow runtime mode must be off, shadow, or enforce")
        if decision_limit < 1:
            raise ValueError("decision_limit must be positive")
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        self.mode = normalized_mode
        self.store = store
        self.project_bindings = dict(project_bindings)
        self.journals = dict(journals)
        self.decision_limit = int(decision_limit)
        self.batch_size = int(batch_size)
        self._lock = threading.RLock()
        self._started = False
        self._draining = False
        self._last_reconcile: dict[str, Any] = {}
        self._latest_decisions: dict[tuple[str, str], Any] = {}
        self._events: list[WorkflowRuntimeEvent] = []
        self._closed = False
        self._topology_signature = topology_signature
        self._topology_source = topology_source
        self._topology_change_handler = topology_change_handler
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
        self.worker = worker or DurableWorkflowWorker(
            store=store,
            handlers=worker_handlers,
            transition_services={
                project_id: binding.transition_service
                for project_id, binding in self.project_bindings.items()
            },
            worker_id=f"workflow-runtime:{os.getpid()}:{uuid.uuid4().hex}",
            phase_observer=self.record_event,
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
        terminal_adapter = (
            CoordinatorTerminalAdapter(terminal_transition_coordinator)
            if terminal_transition_coordinator is not None
            else None
        )
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
        if not isinstance(configured_limit, int) or isinstance(configured_limit, bool):
            configured_limit = DEFAULT_RUNTIME_DECISION_LIMIT
        if not isinstance(configured_batch, int) or isinstance(configured_batch, bool):
            configured_batch = DEFAULT_RUNTIME_BATCH_SIZE
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
                    return legacy_sources(issue).get(domain)
                return None

            sources = {
                domain: (lambda issue, domain=domain: source(issue, domain))
                for domain in (
                    FactDomain.TERMINAL_AUDIT,
                    FactDomain.REVIEW_CI,
                    FactDomain.IMPLEMENTATION_AUTHORITY,
                    FactDomain.RETRY_BUDGET,
                    FactDomain.CONFIG,
                )
            }
            repo_path = getattr(project, "repo_path", "") if project is not None else ""
            landing = GitLandingCollector(repo_path or ".", project_id=project_id)
            transition_service = TaskTransitionService(
                project_id=project_id,
                tracker=tracker,
                journal=journal,
                terminal_adapter=terminal_adapter,
            )
            collector = WorkflowFactCollector(
                project_id=project_id,
                tracker=tracker,
                sources=sources,
                landing_collector=landing,
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
                    collector=collector,
                    store=store,
                    decision_limit=configured_limit,
                ),
                integration_controller=IntegrationWorkflowController(
                    collector=collector,
                    store=store,
                    decision_limit=configured_limit,
                ),
                epic_collector=epic_collector,
                epic_controller=EpicWorkflowController(
                    collector=epic_collector,
                    store=store,
                    decision_limit=configured_limit,
                ),
                terminal_audit_workflow=terminal_workflow,
                transition_journal=journal,
                dispatch_enabled=dispatch_enabled,
            )
            holder["binding"] = binding
            bindings[project_id] = binding

        registered_handlers = handlers
        handler_coverage: dict[str, set[str]] | None = None
        if registered_handlers is None:
            registered_handlers = getattr(
                orchestrator, "workflow_action_handlers", None
            )
        factory = getattr(orchestrator, "workflow_action_handler_factory", None)
        if registered_handlers is None and callable(factory):
            project_handlers: dict[str, dict[str, WorkflowActionHandler]] = {}
            for binding in bindings.values():
                produced = factory(binding)
                if not isinstance(produced, Mapping):
                    raise WorkflowRuntimeError(
                        "workflow action handler factory must return a mapping"
                    )
                unknown = set(produced) - RUNTIME_ACTIONS
                if unknown:
                    raise WorkflowRuntimeError(
                        "workflow action handler factory returned unknown actions: "
                        + ", ".join(sorted(unknown))
                    )
                for action, handler in produced.items():
                    project_handlers.setdefault(action, {})[
                        binding.project_id
                    ] = handler
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
        return cls(
            project_bindings=bindings,
            store=store,
            journals=journals,
            mode=configured_mode,
            handlers=registered_handlers,
            decision_limit=configured_limit,
            batch_size=configured_batch,
            handler_coverage=handler_coverage,
            abandoned_lease_owners=getattr(
                orchestrator, "workflow_abandoned_lease_owners", ()
            ),
            topology_signature=topology_source(),
            topology_source=topology_source,
            topology_change_handler=topology_change_handler,
        )

    @property
    def enforce(self) -> bool:
        return self.mode == "enforce"

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

    @property
    def legacy_lifecycle_writers_enabled(self) -> bool:
        """Whether legacy lifecycle writers may run in this process."""

        return not self.enforce

    @property
    def started(self) -> bool:
        return self._started

    @staticmethod
    def _runtime_owner_is_dead(owner: str) -> bool:
        match = _RUNTIME_OWNER_PATTERN.fullmatch(owner)
        if match is None:
            return False
        pid = int(match.group("pid"))
        if pid == os.getpid():
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

    def reconcile(self) -> dict[str, Any]:
        """Collect facts and materialize durable jobs for every project."""

        if not self._started:
            raise WorkflowRuntimeError("workflow runtime must be started first")
        if self.mode != "off" and not self._binding_topology_current():
            raise WorkflowRuntimeError(
                "workflow project bindings changed and require restart"
            )
        if self._draining or self.mode == "off":
            return {"mode": self.mode, "skipped": True}
        report: dict[str, Any] = {"mode": self.mode, "projects": {}}
        for project_id, binding in sorted(self.project_bindings.items()):
            try:
                if not binding.enabled:
                    with self._lock:
                        self._latest_decisions = {
                            key: decision
                            for key, decision in self._latest_decisions.items()
                            if key[0] != project_id
                        }
                    report["projects"][project_id] = {
                        "skipped": True,
                        "reason": "project paused or orchestrator quiesced",
                    }
                    continue
                issues = self._issues(binding)
                project_report: dict[str, Any] = {"issues": len(issues)}
                with self._lock:
                    self._latest_decisions = {
                        key: decision
                        for key, decision in self._latest_decisions.items()
                        if key[0] != project_id
                    }
                generation = (
                    self.store.allocate_snapshot_generation() if self.enforce else None
                )
                epic_issues = [
                    issue
                    for issue in issues
                    if str(getattr(issue, "issue_type", "") or "").strip().lower()
                    == "epic"
                    and canonicalize_status(getattr(issue, "state", None))
                    != IN_VALIDATION
                ]
                task_issues = [
                    issue
                    for issue in issues
                    if str(getattr(issue, "issue_type", "") or "").strip().lower()
                    != "epic"
                ]
                if binding.implementation_controller is not None:
                    if self.enforce:
                        batch, result = binding.implementation_controller.reconcile(
                            task_issues, snapshot_generation=generation
                        )
                        result_value = asdict(result)
                    else:
                        batch = binding.implementation_controller.evaluate(task_issues)
                        result_value = {"decisions_seen": len(batch.tasks)}
                    self._remember(batch)
                    project_report["implementation"] = result_value
                if binding.review_controller is not None:
                    if self.enforce:
                        batch, result = binding.review_controller.reconcile(
                            task_issues, snapshot_generation=generation
                        )
                        result_value = asdict(result)
                    else:
                        batch = binding.review_controller.evaluate(task_issues)
                        result_value = {"decisions_seen": len(batch.tasks)}
                    self._remember(batch)
                    project_report["review"] = result_value
                if binding.integration_controller is not None:
                    if self.enforce:
                        batch, result = binding.integration_controller.reconcile(
                            task_issues, snapshot_generation=generation
                        )
                        result_value = asdict(result)
                    else:
                        batch = binding.integration_controller.evaluate(task_issues)
                        result_value = {"decisions_seen": len(batch.tasks)}
                    self._remember(batch)
                    project_report["integration"] = result_value
                if binding.epic_controller is not None:
                    if self.enforce:
                        batch, result = binding.epic_controller.reconcile(
                            epic_issues, snapshot_generation=generation
                        )
                        result_value = asdict(result)
                    else:
                        batch = binding.epic_controller.evaluate(
                            epic_issues, persist_evidence=False
                        )
                        result_value = {"decisions_seen": len(batch.tasks)}
                    self._remember(batch)
                    project_report["epic"] = result_value
                report["projects"][project_id] = project_report
            except Exception as exc:  # one project must not hide its peers
                logger.exception("Durable workflow reconcile failed for %s", project_id)
                report["projects"][project_id] = {
                    "error": type(exc).__name__,
                }
        with self._lock:
            self._last_reconcile = report
        return report

    async def reconcile_async(self) -> dict[str, Any]:
        """Async form used by the orchestrator's event-driven scheduler."""

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

        report = await asyncio.to_thread(self.reconcile)
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
        results: list[Any] = []
        active_projects = list(dict.fromkeys(str(value) for value in project_ids))
        while active_projects and sum(
            item.job_id is not None for item in results
        ) < self.batch_size:
            progressed = False
            for project_id in tuple(active_projects):
                result = await self.worker.run_once(
                    project_id=project_id,
                    actions=tuple(sorted(RUNTIME_ACTIONS)),
                )
                results.append(result)
                if result.job_id is None:
                    active_projects.remove(project_id)
                else:
                    progressed = True
                if sum(item.job_id is not None for item in results) >= self.batch_size:
                    break
            if not progressed:
                break
        if not results:
            return {
                "disposition": "idle",
                "job_id": None,
                "state": None,
                "reason": "no eligible durable workflow project",
                "processed": 0,
            }
        result = results[-1]
        return {
            "disposition": result.disposition.value,
            "job_id": result.job_id,
            "state": result.state.value if result.state else None,
            "reason": result.reason,
            "processed": sum(item.job_id is not None for item in results),
        }

    async def drain(self, *, timeout_seconds: float = 10.0) -> bool:
        with self._lock:
            self._draining = True
        return await self.worker.drain(timeout_seconds=timeout_seconds)

    def close(self) -> None:
        """Close transition journals; the orchestrator owns the job store."""

        if self._closed:
            return
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
        return {
            "mode": self.mode,
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
                "handlers_configured": self._handlers_configured,
            },
            "last_reconcile": last,
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


def build_workflow_runtime(orchestrator: Any, **kwargs: Any) -> WorkflowRuntime:
    """Public bootstrap helper kept small for startup and integration tests."""

    return WorkflowRuntime.from_orchestrator(orchestrator, **kwargs)
