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
import logging
import os
import threading
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

from oompah.integration_workflow import IntegrationWorkflowController
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
from oompah.workflow_scheduler import WorkflowJobScheduler
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
from oompah.work_decision import evaluate_task

logger = logging.getLogger(__name__)

LEGACY_PROJECT_ID = "legacy"
DEFAULT_RUNTIME_DECISION_LIMIT = 100
DEFAULT_RUNTIME_BATCH_SIZE = 32

# These names are intentionally bounded.  New domain adapters can add their
# own handler to the bootstrap without changing the worker's composition root.
_IMPLEMENTATION_ACTIONS = frozenset(
    {
        "implementation_start",
        "direct_owner_claim",
        "duplicate_screening",
        "focus_handoff",
        "worker_exit",
        "validation_submission",
        "authority_revocation",
        "implementation_retry",
        "implementation_recovery",
    }
)
_INTEGRATION_ACTIONS = frozenset(
    {
        "integration_landing_refresh",
        "integration_terminal_stage",
        "standalone_delivery",
        "epic_branch_reconciliation",
    }
)


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
    integration_controller: IntegrationWorkflowController | None = None
    terminal_audit_workflow: Any | None = None
    transition_journal: TransitionJournal | None = None

    @property
    def controllers(self) -> tuple[Any, ...]:
        return tuple(
            controller
            for controller in (
                self.implementation_controller,
                self.integration_controller,
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
        self._handlers_configured = bool(handlers)
        supplied = dict(handlers or {})
        # DurableWorkflowWorker requires a total action map.  Missing actions
        # are represented explicitly but are never claimed unless a real
        # handler was supplied for at least one action.
        all_actions = set(supplied)
        all_actions.update(
            {
                "terminal_audit",
                "review_monitor",
                "review_refresh",
                "review_ci_repair",
                "review_conflict_repair",
                "review_closed_repair",
                "review_head_reconciliation",
                "review_landing_refresh",
                "review_terminal_stage",
                "review_capacity_recheck",
                *_IMPLEMENTATION_ACTIONS,
                *_INTEGRATION_ACTIONS,
            }
        )
        worker_handlers = {
            action: supplied.get(action, _UnavailableHandler(action))
            for action in sorted(all_actions)
        }
        self.handlers = supplied
        self.worker = worker or DurableWorkflowWorker(
            store=store,
            handlers=worker_handlers,
            transition_services={
                project_id: binding.transition_service
                for project_id, binding in self.project_bindings.items()
            },
            worker_id=f"workflow-runtime-{uuid.uuid4().hex}",
            phase_observer=self.record_event,
        )

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
                (str(project.id), orchestrator._tracker_for_project(str(project.id)), project)
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
        bindings: dict[str, WorkflowProjectBinding] = {}
        journals = {project_id: journal for project_id, _, _ in project_rows}

        # The source callbacks close over the binding being built.  This lets
        # implementation authority come from the durable implementation
        # controller instead of the legacy in-memory running map as soon as
        # that adapter is present.
        for project_id, tracker, project in project_rows:
            holder: dict[str, WorkflowProjectBinding] = {}

            def source(issue: Any, domain: FactDomain, *, _holder=holder) -> Any:
                binding = _holder.get("binding")
                if domain is FactDomain.IMPLEMENTATION_AUTHORITY and binding is not None:
                    controller = binding.implementation_controller
                    if controller is not None:
                        try:
                            return controller.implementation_authority(issue)
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
            implementation_controller = None
            try:
                from oompah.implementation_workflow import ImplementationWorkflowController

                implementation_controller = ImplementationWorkflowController(
                    collector=collector,
                    store=store,
                    decision_limit=DEFAULT_RUNTIME_DECISION_LIMIT,
                )
            except ImportError:
                # The implementation adapter is delivered independently.  A
                # shadow/off checkout must remain importable while it is being
                # integrated; enforce mode reports the missing domain below.
                logger.info("implementation workflow adapter is not installed")

            terminal_workflow = getattr(orchestrator, "terminal_audit_workflow", None)
            binding = WorkflowProjectBinding(
                project_id=project_id,
                tracker=tracker,
                collector=collector,
                transition_service=transition_service,
                implementation_controller=implementation_controller,
                integration_controller=IntegrationWorkflowController(
                    collector=collector,
                    store=store,
                    decision_limit=DEFAULT_RUNTIME_DECISION_LIMIT,
                ),
                terminal_audit_workflow=terminal_workflow,
                transition_journal=journal,
            )
            holder["binding"] = binding
            bindings[project_id] = binding

        configured_mode = mode
        if configured_mode is None:
            configured_mode = getattr(orchestrator.config, "workflow_engine_mode", "off")
        if not isinstance(configured_mode, str):
            configured_mode = "off"
        configured_mode = configured_mode.strip().lower()
        if configured_mode not in {"off", "shadow", "enforce"}:
            configured_mode = "off"
        configured_limit = getattr(
            orchestrator.config, "workflow_runtime_decision_limit", DEFAULT_RUNTIME_DECISION_LIMIT
        )
        configured_batch = getattr(
            orchestrator.config, "workflow_runtime_batch_size", DEFAULT_RUNTIME_BATCH_SIZE
        )
        if not isinstance(configured_limit, int) or isinstance(configured_limit, bool):
            configured_limit = DEFAULT_RUNTIME_DECISION_LIMIT
        if not isinstance(configured_batch, int) or isinstance(configured_batch, bool):
            configured_batch = DEFAULT_RUNTIME_BATCH_SIZE
        registered_handlers = handlers
        if registered_handlers is None:
            registered_handlers = getattr(
                orchestrator, "workflow_action_handlers", None
            )
        factory = getattr(orchestrator, "workflow_action_handler_factory", None)
        if registered_handlers is None and callable(factory):
            collected: dict[str, WorkflowActionHandler] = {}
            for binding in bindings.values():
                produced = factory(binding)
                if not isinstance(produced, Mapping):
                    raise WorkflowRuntimeError(
                        "workflow action handler factory must return a mapping"
                    )
                collected.update(produced)
            registered_handlers = collected
        return cls(
            project_bindings=bindings,
            store=store,
            journals=journals,
            mode=configured_mode,
            handlers=registered_handlers,
            decision_limit=configured_limit,
            batch_size=configured_batch,
        )

    @property
    def enforce(self) -> bool:
        return self.mode == "enforce"

    def set_mode(self, mode: str) -> None:
        normalized = str(mode or "off").strip().lower()
        if normalized not in {"off", "shadow", "enforce"}:
            raise ValueError("workflow runtime mode must be off, shadow, or enforce")
        with self._lock:
            self.mode = normalized

    @property
    def legacy_lifecycle_writers_enabled(self) -> bool:
        """Whether legacy lifecycle writers may run in this process."""

        return not self.enforce

    @property
    def started(self) -> bool:
        return self._started

    async def start(self) -> dict[str, int]:
        """Run integrity checks and recover ownership left by a crash."""

        with self._lock:
            if self._started:
                return dict(self._last_reconcile.get("recovery", {}))
            self._draining = False
        self.store.integrity_check()
        for journal in set(self.journals.values()):
            journal.integrity_check()
        recovery = self.store.recover_abandoned(limit=self.batch_size)
        recovery += self.store.recover_expired(limit=self.batch_size)
        with self._lock:
            self._started = True
            self._last_reconcile = {"recovery": {"recovered": recovery}}
        logger.info(
            "Durable workflow runtime started mode=%s projects=%d recovered=%d",
            self.mode,
            len(self.project_bindings),
            recovery,
        )
        return {"recovered": recovery}

    def _issues(self, binding: WorkflowProjectBinding) -> list[Any]:
        operation = getattr(binding.tracker, "fetch_all_issues_enriched", None)
        if not callable(operation):
            operation = binding.tracker.fetch_all_issues
        issues = operation()
        if not isinstance(issues, Sequence):
            raise WorkflowRuntimeError(
                f"tracker for project {binding.project_id!r} returned a non-sequence"
            )
        return [
            issue
            for issue in issues
            if not getattr(issue, "project_id", None)
            or str(issue.project_id) == binding.project_id
        ]

    def _reconcile_decision_lane(
        self, binding: WorkflowProjectBinding, issues: Sequence[Any]
    ) -> Any:
        decisions = []
        for issue in issues[: self.decision_limit]:
            facts = binding.collector.collect(issue.identifier)
            decision = evaluate_task(issue, facts)
            self._latest_decisions[(binding.project_id, issue.identifier)] = decision
            actions = tuple(
                action
                for action in decision.durable_jobs
                if action not in _IMPLEMENTATION_ACTIONS
                and action not in _INTEGRATION_ACTIONS
            )
            if actions:
                # Keep one decision revision for all non-domain-specific
                # actions; filtering is part of the scheduler projection and
                # does not change the accepted decision itself.
                from dataclasses import replace

                decisions.append(replace(decision, durable_jobs=actions, decision_revision=None))
        scheduler = WorkflowJobScheduler(
            store=self.store, decision_limit=self.decision_limit
        )
        return scheduler.reconcile(decisions)

    def reconcile(self) -> dict[str, Any]:
        """Collect facts and materialize durable jobs for every project."""

        if not self._started:
            raise WorkflowRuntimeError("workflow runtime must be started first")
        if self._draining or self.mode == "off":
            return {"mode": self.mode, "skipped": True}
        report: dict[str, Any] = {"mode": self.mode, "projects": {}}
        for project_id, binding in sorted(self.project_bindings.items()):
            try:
                issues = self._issues(binding)
                project_report: dict[str, Any] = {"issues": len(issues)}
                if binding.implementation_controller is not None:
                    _, result = binding.implementation_controller.reconcile(issues)
                    project_report["implementation"] = asdict(result)
                if binding.integration_controller is not None:
                    _, result = binding.integration_controller.reconcile(issues)
                    project_report["integration"] = asdict(result)
                project_report["decision_lane"] = self._reconcile_decision_lane(
                    binding, issues
                )
                project_report["decision_lane"] = asdict(project_report["decision_lane"])
                report["projects"][project_id] = project_report
            except Exception as exc:  # one project must not hide its peers
                logger.exception("Durable workflow reconcile failed for %s", project_id)
                report["projects"][project_id] = {
                    "error": type(exc).__name__,
                }
        if self._handlers_configured and self.enforce:
            batch = awaitable_run_due(
                self.worker, self.batch_size, tuple(self.handlers)
            )
            report["worker"] = batch
        with self._lock:
            self._last_reconcile = report
        return report

    async def reconcile_async(self) -> dict[str, Any]:
        """Async form used by the orchestrator's event-driven scheduler."""

        return await asyncio.to_thread(self.reconcile)

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
        for decision in sorted(
            self._latest_decisions.values(), key=lambda item: (item.project_id, item.task_id)
        ):
            rows.append(decision.to_dict())
        return tuple(rows)

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
                project_id: [type(controller).__name__ for controller in binding.controllers]
                for project_id, binding in sorted(self.project_bindings.items())
            },
            "worker": {
                "accepting": self.worker.accepting,
                "active": self.worker.active_count,
                "handlers_configured": self._handlers_configured,
            },
            "last_reconcile": last,
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


def awaitable_run_due(
    worker: DurableWorkflowWorker,
    batch_size: int,
    actions: Sequence[str],
) -> dict[str, Any]:
    """Run a bounded worker batch from a synchronous reconcile thread."""

    async def _run() -> list[Any]:
        # A temporary loop is deliberate: reconciles are called from the
        # orchestrator tick pool and must not attach futures to the API loop.
        results: list[Any] = []
        for _ in range(max(1, int(batch_size))):
            result = await worker.run_once(
                actions=tuple(actions), fair_across_projects=True
            )
            results.append(result)
            if result.job_id is None:
                break
        return results

    results = asyncio.run(_run())
    result = results[-1]
    return {
        "disposition": result.disposition.value,
        "job_id": result.job_id,
        "state": result.state.value if result.state else None,
        "reason": result.reason,
        "processed": sum(item.job_id is not None for item in results),
    }


def build_workflow_runtime(orchestrator: Any, **kwargs: Any) -> WorkflowRuntime:
    """Public bootstrap helper kept small for startup and integration tests."""

    return WorkflowRuntime.from_orchestrator(orchestrator, **kwargs)
