"""Landing-fact driven decisions for shared and nested epic rollups.

Epic rollups are a graph workflow, not a special case of a task status.  This
module collects one immutable graph snapshot, records every immediate landing
as a target-specific :class:`~oompah.workflow_facts.LandingFact`, and turns the
snapshot into the same durable jobs used by the other workflow domains.

The important boundary is intentional: a nested epic is eligible when its own
branch is proven on its immediate parent branch.  It is never made eligible by
reading the parent's status, because that status may itself be derived from
the nested epic.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import re
from typing import Any

from oompah.models import Issue
from oompah.statuses import ARCHIVED, MERGED, canonicalize_status
from oompah.work_decision import WorkDecision, evaluate_task
from oompah.workflow_facts import (
    FactDomain,
    GitLandingCollector,
    LandingFact,
    LandingRequest,
    WorkflowFactCollector,
    WorkflowFacts,
)
from oompah.workflow_jobs import WorkflowJob, WorkflowJobSpec, WorkflowJobStore
from oompah.workflow_scheduler import WorkflowJobScheduler, WorkflowReconcileResult


DEFAULT_EPIC_DECISION_LIMIT = 1000


class EpicTargetResolutionError(ValueError):
    """The containment graph cannot provide a safe immediate target."""


class EpicAction(str, Enum):
    """Durable epic actions exposed to workers and restart reconciliation."""

    READINESS = "epic_readiness"
    ROLLUP_RECONCILIATION = "rollup_reconciliation"
    CHILD_LANDING_VERIFICATION = "child_landing_verification"
    ROLLUP_REVIEW_CREATION = "rollup_review_creation"
    TARGET_RESOLUTION = "epic_target_resolution"
    AUTO_CLOSE = "epic_auto_close"
    TERMINAL_VALIDATION = "epic_terminal_validation"
    REBASE_REPAIR = "epic_rebase_repair"
    CLEANUP = "epic_cleanup"
    RESTART_RECONCILIATION = "epic_restart_reconciliation"


EPIC_ACTIONS = frozenset(item.value for item in EpicAction)


def _required_text(value: object, name: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise ValueError(f"{name} is required")
    return result


def epic_branch(identifier: str) -> str:
    """Return the service-owned branch identity for an epic."""

    return f"epic-{_required_text(identifier, 'identifier')}"


def resolve_epic_target(
    epic: Issue,
    *,
    parent: Issue | None,
    default_branch: str = "main",
) -> str:
    """Resolve an epic's immediate target without consulting lifecycle state."""

    if parent is not None:
        if str(parent.issue_type or "").strip().lower() != "epic":
            raise EpicTargetResolutionError(
                f"{epic.identifier} parent {parent.identifier} is not an epic"
            )
        return epic_branch(parent.identifier)
    return _required_text(default_branch, "default_branch")


def _integration_value(issue: Issue) -> Mapping[str, Any]:
    integration = getattr(issue, "integration", None)
    if hasattr(integration, "to_dict"):
        value = integration.to_dict()
        return value if isinstance(value, Mapping) else {}
    return integration if isinstance(integration, Mapping) else {}


def _source_branch(issue: Issue) -> str:
    return _required_text(
        getattr(issue, "work_branch", None)
        or getattr(issue, "branch_name", None)
        or issue.identifier,
        "source_branch",
    )


def _revision(issue: Issue) -> str | None:
    integration = _integration_value(issue)
    value = (
        getattr(issue, "head_sha", None)
        or integration.get("integrated_sha")
        or integration.get("head_sha")
    )
    normalized = str(value).strip() if value else ""
    return normalized if re.fullmatch(r"[0-9a-fA-F]{7,64}", normalized) else None


def _is_maintenance(issue: Issue) -> bool:
    title = str(getattr(issue, "title", "") or "").strip().lower()
    labels = {
        str(label).strip().lower() for label in (getattr(issue, "labels", None) or [])
    }
    return (
        (title.startswith("rebase ") and " onto " in title)
        or "merge-conflict" in labels
        or "ci-fix" in labels
    )


@dataclass(frozen=True, slots=True)
class EpicGraph:
    """Immutable direct-child facts plus the graph validation result."""

    parent_id: str | None
    epic_branch: str
    target_branch: str
    children: tuple[Mapping[str, Any], ...]
    acyclic: bool
    cycle: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "parent_id": self.parent_id,
            "epic_branch": self.epic_branch,
            "target_branch": self.target_branch,
            "children": [dict(child) for child in self.children],
            "acyclic": self.acyclic,
            "cycle": self.cycle,
        }


class EpicFactCollector:
    """Collect graph and Git facts through the shared fact collector."""

    def __init__(
        self,
        *,
        project_id: str,
        tracker: Any,
        default_branch: str = "main",
        repo_path: str | None = None,
        sources: Mapping[FactDomain | str, Callable[[Issue], Any]] | None = None,
        landing_collector: GitLandingCollector | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.project_id = _required_text(project_id, "project_id")
        self.tracker = tracker
        self.default_branch = _required_text(default_branch, "default_branch")
        if landing_collector is not None and repo_path is not None:
            raise ValueError("provide landing_collector or repo_path, not both")
        self.landing_collector = landing_collector or (
            GitLandingCollector(repo_path, project_id=self.project_id)
            if repo_path
            else None
        )
        self.sources = sources
        self.clock = clock

    def _graph(self, root: Issue) -> EpicGraph:
        direct: list[Mapping[str, Any]] = []
        seen: set[str] = {root.identifier}
        cycle: str | None = None

        def visit(parent: Issue, ancestors: tuple[str, ...]) -> None:
            nonlocal cycle
            children = self.tracker.fetch_children(parent.identifier)
            for child in children:
                if child.project_id and str(child.project_id) != self.project_id:
                    continue
                identifier = _required_text(child.identifier, "child.identifier")
                if child.parent_id and child.parent_id != parent.identifier:
                    cycle = f"{identifier}->{child.parent_id}"
                    continue
                if identifier in ancestors or identifier in seen:
                    cycle = "->".join((*ancestors, identifier))
                    continue
                seen.add(identifier)
                issue_type = str(child.issue_type or "task").strip().lower()
                nested = issue_type == "epic"
                maintenance = _is_maintenance(child)
                target = epic_branch(parent.identifier)
                source = epic_branch(identifier) if nested else _source_branch(child)
                revision = _revision(child)
                # A shared child may report the parent epic branch as its
                # work branch.  Without an exact head SHA that is not proof
                # of the child's work; use the task identity so the evidence
                # collector fails closed instead of proving source==target.
                if source == target and revision is None:
                    source = identifier
                status = canonicalize_status(child.state)
                archived = status == ARCHIVED
                # The decision for one epic consumes only its direct children.
                # Descendants are still walked below to reject malformed graph
                # cycles, but their readiness belongs to their immediate epic.
                # Folding them into every ancestor creates duplicate blockers
                # and makes a root decision depend on grandchildren that its
                # nested child already owns.
                if parent.identifier == root.identifier:
                    direct.append(
                        {
                            "identifier": identifier,
                            "status": status,
                            "issue_type": child.issue_type,
                            "parent_id": child.parent_id,
                            "kind": "archived"
                            if archived
                            else "nested_epic"
                            if nested
                            else "maintenance"
                            if maintenance
                            else "normal",
                            "maintenance": maintenance,
                            "requires_landing": not maintenance and not archived,
                            "landing_source": source,
                            "landing_target": target,
                            "revision": revision,
                        }
                    )
                # Walk every node, not only declared epics.  A malformed
                # task->epic->task cycle must be rejected before any rollup
                # review can be created.
                visit(child, (*ancestors, identifier))

        visit(root, (root.identifier,))
        parent = None
        parent_id = str(root.parent_id or "").strip() or None
        if parent_id:
            parent = self.tracker.fetch_issue_detail(parent_id)
            if parent is None:
                raise EpicTargetResolutionError(
                    f"parent {parent_id} for {root.identifier} is unavailable"
                )
        target = resolve_epic_target(
            root, parent=parent, default_branch=self.default_branch
        )
        return EpicGraph(
            parent_id=parent_id,
            epic_branch=epic_branch(root.identifier),
            target_branch=target,
            children=tuple(sorted(direct, key=lambda item: str(item["identifier"]))),
            acyclic=cycle is None,
            cycle=cycle,
        )

    @staticmethod
    def _prior(
        prior_landings: Mapping[Any, LandingFact] | None,
        request: LandingRequest,
    ) -> LandingFact | None:
        if not prior_landings:
            return None
        return prior_landings.get((request.source, request.target)) or prior_landings.get(
            f"{request.source}->{request.target}"
        )

    def collect(
        self,
        task_id: str,
        *,
        prior_landings: Mapping[Any, LandingFact] | None = None,
    ) -> WorkflowFacts:
        task_id = _required_text(task_id, "task_id")
        root = self.tracker.fetch_issue_detail(task_id)
        if root is None:
            collector = WorkflowFactCollector(
                project_id=self.project_id,
                tracker=self.tracker,
                sources=self.sources,
                clock=self.clock,
            )
            return collector.collect(task_id)
        try:
            graph = self._graph(root)
        except Exception as exc:  # noqa: BLE001 - evidence boundary
            def failed(_current: Issue, error: Exception = exc) -> Any:
                raise error

            base = WorkflowFactCollector(
                project_id=self.project_id,
                tracker=self.tracker,
                sources=self.sources,
                containment_source=failed,
                clock=self.clock,
            )
            return base.collect(task_id)
        requests = [
            LandingRequest(
                str(child["landing_source"]),
                str(child["landing_target"]),
                child.get("revision"),
                prior=self._prior(prior_landings, LandingRequest(
                    str(child["landing_source"]), str(child["landing_target"]), child.get("revision")
                )),
            )
            for child in graph.children
            if child.get("requires_landing")
        ]
        # The epic's own landing is deliberately included as a separate fact.
        # Rollup readiness only consumes child facts; auto-close/terminal
        # validation can consume this exact immediate-target fact later.
        requests.append(
            LandingRequest(
                graph.epic_branch,
                graph.target_branch,
                _revision(root),
                prior=self._prior(
                    prior_landings,
                    LandingRequest(graph.epic_branch, graph.target_branch, _revision(root)),
                ),
            )
        )
        base = WorkflowFactCollector(
            project_id=self.project_id,
            tracker=self.tracker,
            sources=self.sources,
            containment_source=lambda current: graph.to_dict()
            if current.identifier == root.identifier
            else None,
            landing_collector=self.landing_collector,
            clock=self.clock,
        )
        return base.collect(task_id, landing_requests=tuple(requests))


@dataclass(frozen=True, slots=True)
class EpicTaskDecision:
    task: Issue
    facts: WorkflowFacts
    decision: WorkDecision


@dataclass(frozen=True, slots=True)
class EpicDecisionBatch:
    tasks: tuple[EpicTaskDecision, ...]

    @property
    def decisions(self) -> tuple[WorkDecision, ...]:
        return tuple(item.decision for item in self.tasks)


@dataclass(frozen=True, slots=True)
class EpicProjection:
    project_id: str
    task_id: str
    disposition: str
    reason_code: str
    owner: str
    evidence_revision: str
    durable_jobs: tuple[str, ...]
    active_job_state: str | None = None

    @classmethod
    def from_decision(cls, decision: WorkDecision, job: WorkflowJob | None):
        return cls(
            decision.project_id,
            decision.task_id,
            decision.disposition.value,
            decision.reason_code,
            decision.responsible_owner.value,
            decision.evidence_revision,
            decision.durable_jobs,
            job.state.value if job else None,
        )


class EpicWorkflowController:
    """Evaluate epics and materialize one generation-fenced rollup job."""

    def __init__(
        self,
        *,
        collector: EpicFactCollector,
        store: WorkflowJobStore,
        scheduler: WorkflowJobScheduler | None = None,
        decision_limit: int = DEFAULT_EPIC_DECISION_LIMIT,
    ) -> None:
        if decision_limit < 1 or decision_limit > DEFAULT_EPIC_DECISION_LIMIT:
            raise ValueError(
                f"decision_limit must be between 1 and {DEFAULT_EPIC_DECISION_LIMIT}"
            )
        self.collector = collector
        self.store = store
        self.scheduler = scheduler or WorkflowJobScheduler(
            store=store, decision_limit=decision_limit
        )
        self.decision_limit = decision_limit
        self._latest: dict[str, EpicTaskDecision] = {}
        self._landings: dict[tuple[str, str], LandingFact] = {}

    def evaluate(self, tasks: Sequence[Issue]) -> EpicDecisionBatch:
        selected = dict(sorted({task.identifier: task for task in tasks}.items()))
        selected = dict(tuple(selected.items())[: self.decision_limit])
        evaluated: list[EpicTaskDecision] = []
        for task in selected.values():
            if str(task.issue_type or "").strip().lower() != "epic":
                continue
            if canonicalize_status(task.state) in {MERGED, ARCHIVED}:
                continue
            prior = dict(self._landings)
            try:
                persisted = self.store.landing_facts(
                    project_id=self.collector.project_id,
                    task_id=task.identifier,
                )
            except Exception:
                # Evidence storage is fail-closed for writes but must not
                # prevent a fresh Git observation from being evaluated.
                persisted = ()
            for raw in persisted:
                try:
                    landing = LandingFact.from_dict(raw)
                except (TypeError, ValueError):
                    continue
                if landing.durable:
                    prior[(landing.source, landing.target)] = landing
            facts = self.collector.collect(task.identifier, prior_landings=prior)
            for landing in facts.landings:
                if landing.durable:
                    self._landings[(landing.source, landing.target)] = landing
            durable = [landing.to_dict() for landing in facts.landings if landing.durable]
            if durable:
                self.store.record_landing_facts(
                    project_id=self.collector.project_id,
                    task_id=task.identifier,
                    facts=durable,
                )
            evaluated.append(EpicTaskDecision(task, facts, evaluate_task(task, facts)))
        self._latest = {item.task.identifier: item for item in evaluated}
        return EpicDecisionBatch(tuple(evaluated))

    def reconcile(
        self,
        tasks: Sequence[Issue],
        *,
        snapshot_generation: int | None = None,
    ) -> tuple[EpicDecisionBatch, WorkflowReconcileResult]:
        generation = (
            self.store.allocate_snapshot_generation()
            if snapshot_generation is None
            else int(snapshot_generation)
        )
        if generation < 1:
            raise ValueError("snapshot_generation must be a positive integer")
        batch = self.evaluate(tasks)
        return batch, self.scheduler.reconcile(
            batch.decisions, snapshot_generation=generation
        )

    def schedule_action(
        self,
        *,
        task_id: str,
        action: EpicAction | str,
        generation: str | None = None,
        expected_evidence_revision: str | None = None,
        expected_head_sha: str | None = None,
        priority: int = 100,
        max_attempts: int = 5,
    ) -> WorkflowJob:
        """Materialize an explicit epic maintenance action idempotently.

        Rebase/repair, terminal validation, cleanup, and restart recovery may
        be requested by different maintenance loops.  They all enter the same
        job ledger with the same task/generation fence, so a restart cannot
        duplicate an external effect or revive superseded work.
        """

        normalized_action = EpicAction(action)
        project_id = _required_text(self.collector.project_id, "project_id")
        identifier = _required_text(task_id, "task_id")
        job_generation = generation or (
            f"epic-maintenance:{self.store.allocate_snapshot_generation()}"
        )
        key = ":".join((project_id, identifier, normalized_action.value, job_generation))
        return self.store.enqueue(
            WorkflowJobSpec(
                project_id=project_id,
                task_id=identifier,
                generation=job_generation,
                action=normalized_action.value,
                idempotency_key=key,
                phase="intent",
                expected_evidence_revision=expected_evidence_revision,
                expected_head_sha=expected_head_sha,
                priority=priority,
                max_attempts=max_attempts,
            )
        )

    def reconcile_after_restart(
        self,
        tasks: Sequence[Issue],
        *,
        lease_owner: str,
        recovery_limit: int = 1000,
    ) -> tuple[int, EpicDecisionBatch, WorkflowReconcileResult]:
        """Recover one known-dead worker's leases, then rebuild decisions.

        The job store is shared by every workflow domain.  An unscoped
        ``recover_abandoned`` call could therefore steal live review, audit,
        or implementation work.  Startup must name the worker identity that
        this process has exclusively replaced.
        """

        owner = _required_text(lease_owner, "lease_owner")

        recovered = self.store.recover_abandoned(
            lease_owner=owner,
            project_id=self.collector.project_id,
            actions=tuple(EPIC_ACTIONS),
            limit=recovery_limit,
        )
        batch, scheduled = self.reconcile(tasks)
        return recovered, batch, scheduled

    def projections(self) -> tuple[EpicProjection, ...]:
        jobs = self.store.list_jobs(limit=self.decision_limit)
        active: dict[str, WorkflowJob] = {}
        for job in jobs:
            if job.is_active:
                current = active.get(job.task_id)
                if current is None or job.enqueue_sequence > current.enqueue_sequence:
                    active[job.task_id] = job
        return tuple(
            EpicProjection.from_decision(item.decision, active.get(item.task.identifier))
            for item in self._latest.values()
        )


__all__ = [
    "DEFAULT_EPIC_DECISION_LIMIT",
    "EPIC_ACTIONS",
    "EpicAction",
    "EpicDecisionBatch",
    "EpicFactCollector",
    "EpicGraph",
    "EpicProjection",
    "EpicTargetResolutionError",
    "EpicTaskDecision",
    "EpicWorkflowController",
    "epic_branch",
    "resolve_epic_target",
]
