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

import asyncio
import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol

from oompah.integration import ACCEPTED_SUBMISSION_STATES, IntegrationRecord
from oompah.models import Issue
from oompah.projects import sanitize_branch_identifier
from oompah.statuses import (
    ARCHIVED,
    BACKLOG,
    DONE,
    IN_PROGRESS,
    IN_REVIEW,
    MERGED,
    OPEN,
    canonicalize_status,
    epic_rollup_state,
)
from oompah.task_transition_service import (
    TransitionAuthority,
    TransitionIntent,
    issue_authority_version,
    issue_exact_head,
)
from oompah.work_decision import (
    PermittedAction,
    WorkDecision,
    epic_immediate_target_landings,
    evaluate_task,
)
from oompah.workflow_contract import TaskDisposition, WorkflowOwner
from oompah.workflow_fact_model import (
    CollectedValue,
    FactDomain,
    FactObservation,
    FactState,
    LandingFact,
    LandingRequest,
    LandingState,
    WorkflowFacts,
    _parse_time,
)
from oompah.workflow_facts import GitLandingCollector, WorkflowFactCollector
from oompah.workflow_reasons import AlertSeverity
from oompah.workflow_jobs import (
    WorkflowEventWrite,
    WorkflowFailureCategory,
    WorkflowJob,
    WorkflowJobStore,
)
from oompah.workflow_scheduler import WorkflowJobScheduler, WorkflowReconcileResult
from oompah.workflow_worker import (
    EffectObservation,
    EffectResult,
    RevalidationResult,
    VerificationResult,
    WorkflowActionDomain,
    WorkflowActionError,
    WorkflowActionSuperseded,
    WorkflowJobContext,
)

DEFAULT_EPIC_DECISION_LIMIT = 1000
_EXACT_HEAD_RE = re.compile(r"^[0-9a-f]{40,64}$")
_RETAINED_CHILD_PROVENANCE_SCHEMA_VERSION = 1


class EpicTargetResolutionError(ValueError):
    """The containment graph cannot provide a safe immediate target."""


class EpicProjectScopeError(ValueError):
    """An issue conflicts with the project bound to its workflow."""


def _evaluate_epic_rollup(
    issue: Issue,
    facts: WorkflowFacts,
    *,
    liveness_slo_seconds: Mapping[str, int] | None = None,
) -> WorkDecision:
    """Evaluate delivery plus the independent rollup-status obligation."""

    decision_issue = (
        issue
        if str(issue.issue_type or "").strip().lower() == "epic"
        else replace(issue, issue_type="epic")
    )
    decision = evaluate_task(
        decision_issue,
        facts,
        liveness_slo_seconds=liveness_slo_seconds,
    )
    current = canonicalize_status(issue.state)
    # Delivery and landing obligations are more specific than the aggregate
    # status projection once a rollup is dispatchable.  A Backlog rollup must
    # still activate first so its descendants can acquire hierarchy authority.
    if decision.durable_jobs and current != BACKLOG:
        return decision
    if current not in {BACKLOG, OPEN}:
        return decision
    containment = facts.fact(FactDomain.CONTAINMENT)
    children = (
        containment.value.get("children")
        if containment.state is FactState.KNOWN
        and isinstance(containment.value, Mapping)
        else None
    )
    if not isinstance(children, (list, tuple)) or not children:
        return decision
    statuses = [
        child.get("status")
        for child in children
        if isinstance(child, Mapping)
    ]
    rolled = canonicalize_status(epic_rollup_state(statuses))
    if rolled not in {OPEN, IN_PROGRESS} or rolled == current:
        return decision
    target = OPEN if current == BACKLOG else rolled
    return replace(
        decision,
        disposition=TaskDisposition.RUNNABLE,
        reason_code="rollup.status_reconciliation",
        responsible_owner=WorkflowOwner.ROLLUP,
        unmet_prerequisites=(),
        permitted_actions=(PermittedAction.ROLLUP_CHILDREN,),
        action_required=False,
        alert_level=AlertSeverity.NONE,
        durable_jobs=(EpicAction.ROLLUP_RECONCILIATION.value,),
        recommended_status=target,
        decision_revision=None,
    )


def normalize_issue_project_scope(issue: Issue, project_id: object) -> Issue:
    """Return ``issue`` bound to its authoritative workflow project.

    Native Markdown issues do not persist a project identifier because their
    repository is already the project boundary.  Workflow snapshots must
    nevertheless include that boundary before computing authority versions.
    An explicit, conflicting project remains a fail-closed error.
    """

    bound_project_id = str(project_id or "").strip()
    if not bound_project_id:
        raise EpicProjectScopeError("epic workflow project binding is required")
    observed_project_id = str(issue.project_id or "").strip()
    if observed_project_id and observed_project_id != bound_project_id:
        raise EpicProjectScopeError(
            "issue project identity conflicts with its workflow binding"
        )
    if observed_project_id == bound_project_id:
        return issue
    return replace(issue, project_id=bound_project_id)


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

_EPIC_READ_ONLY_ACTIONS = frozenset(
    {
        EpicAction.READINESS,
        EpicAction.CHILD_LANDING_VERIFICATION,
        EpicAction.TARGET_RESOLUTION,
        EpicAction.RESTART_RECONCILIATION,
    }
)
_EPIC_EXTERNAL_ACTIONS = frozenset(
    {
        EpicAction.ROLLUP_REVIEW_CREATION,
        EpicAction.TERMINAL_VALIDATION,
        EpicAction.REBASE_REPAIR,
        EpicAction.CLEANUP,
    }
)


def _required_text(value: object, name: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise ValueError(f"{name} is required")
    return result


def _exact_head(value: object) -> str | None:
    """Return only immutable full-length Git object identities."""

    candidate = str(value or "").strip().lower()
    return candidate if _EXACT_HEAD_RE.fullmatch(candidate) else None


def epic_branch(identifier: str) -> str:
    """Return the service-owned branch identity for an epic."""

    raw = _required_text(identifier, "identifier")
    return f"epic-{sanitize_branch_identifier(raw)}"


def is_epic_rollup_issue(
    issue: Issue,
    *,
    authoritative_children: Mapping[str, Sequence[Issue]] | None = None,
    tracker: Any | None = None,
) -> bool:
    """Return whether *issue* owns a child rollup in this authority cut.

    Declared epics and inferred parents-with-children have always shared the
    same orchestration contract.  Keeping that inference here prevents the
    durable runtime, target resolver, and mutation adapter from assigning an
    inferred parent to different workflow domains.
    """

    if str(issue.issue_type or "").strip().lower() == "epic":
        return True
    identifier = str(issue.identifier or issue.id or "").strip()
    if not identifier:
        return False
    if authoritative_children is not None:
        return bool(authoritative_children.get(identifier.casefold(), ()))
    if tracker is None:
        return False
    fetch_children = getattr(tracker, "fetch_children", None)
    if not callable(fetch_children):
        return False
    children = fetch_children(identifier)
    # Tracker adapters return a concrete sequence.  Some callers use partial
    # protocol doubles where an undeclared attribute resolves to an opaque
    # sentinel; that is not authoritative child evidence and must not change
    # the workflow domain assigned to the task.
    if not isinstance(children, Sequence) or isinstance(children, (str, bytes)):
        return False
    return bool(children)


def resolve_epic_target(
    epic: Issue,
    *,
    parent: Issue | None,
    default_branch: str = "main",
    parent_is_rollup: bool | None = None,
) -> str:
    """Resolve an epic's immediate target without consulting lifecycle state."""

    if parent is not None:
        confirmed_parent = (
            str(parent.issue_type or "").strip().lower() == "epic"
            if parent_is_rollup is None
            else bool(parent_is_rollup)
        )
        if not confirmed_parent:
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
        # A live implementation head supersedes an older reviewed generation.
        # The persisted review head remains the fallback after branch pruning.
        getattr(issue, "head_sha", None)
        or getattr(issue, "review_head", None)
        or integration.get("integrated_sha")
        or integration.get("head_sha")
    )
    normalized = str(value).strip() if value else ""
    return normalized if re.fullmatch(r"[0-9a-fA-F]{7,64}", normalized) else None


def _accepted_standalone_landing(
    issue: Issue,
    *,
    expected_target: str,
) -> tuple[str, str, str] | None:
    """Return an exact service-selected live-target child route."""

    integration = getattr(issue, "integration", None)
    if not isinstance(integration, IntegrationRecord):
        return None
    state = str(integration.state or "").strip().lower()
    mode = str(integration.mode or "").strip().lower()
    source = str(integration.task_branch or "").strip()
    target = str(integration.base_branch or "").strip()
    explicit_target = str(getattr(issue, "target_branch", "") or "").strip()
    revision = _exact_head(integration.integrated_sha or integration.head_sha)
    if not (
        state in ACCEPTED_SUBMISSION_STATES
        and mode == "standalone"
        and str(integration.post_landed_parent_id or "").strip()
        == str(issue.parent_id or "").strip()
        and source
        and target == expected_target
        and explicit_target == target
        and revision
    ):
        return None
    return source, target, revision


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
        cooperative_checkpoint: Callable[[], None] | None = None,
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
        self.sources = {
            FactDomain(domain): source for domain, source in (sources or {}).items()
        }
        self.clock = clock
        self.cooperative_checkpoint = cooperative_checkpoint

    def _retained_terminal_provenance(
        self,
        child: Issue,
        *,
        parent_id: str,
        status: str,
        source: str,
        target: str,
        revision: str | None,
        authority_version: str,
    ) -> Mapping[str, Any] | None:
        """Compose one exact owner-retention proof for parent rollup.

        The terminal-audit source is the authenticated adapter over the durable
        owner marker.  This projection deliberately remains containment
        evidence: retention waives one parent's delivery obligation, but it is
        not evidence that Git contains the child's commits.
        """

        provider = self.sources.get(FactDomain.TERMINAL_AUDIT)
        exact_revision = _exact_head(revision)
        if (
            provider is None
            or status != DONE
            or not exact_revision
            or not parent_id
            or not source
            or not target
            or not authority_version
        ):
            return None
        try:
            observed = provider(child)
        except Exception:  # noqa: BLE001 - authenticated fact-provider boundary
            return None
        if isinstance(observed, FactObservation):
            if (
                observed.domain is not FactDomain.TERMINAL_AUDIT
                or observed.state is not FactState.KNOWN
            ):
                return None
            observed = observed.value
        elif isinstance(observed, CollectedValue):
            try:
                observed_at = _parse_time(observed.observed_at, "observed_at")
                now = (
                    self.clock()
                    if self.clock is not None
                    else datetime.now(timezone.utc)
                )
                if now.tzinfo is None:
                    return None
                stale = bool(
                    observed.stale_after_seconds is not None
                    and (now.astimezone(timezone.utc) - observed_at).total_seconds()
                    > observed.stale_after_seconds
                )
            except (TypeError, ValueError, OverflowError):
                return None
            if stale:
                return None
            observed = observed.value
        if not isinstance(observed, Mapping):
            return None
        raw = observed.get("terminal_provenance")
        if not isinstance(raw, Mapping):
            return None
        generation = raw.get("authority_generation")
        valid = bool(
            isinstance(raw.get("schema_version"), int)
            and not isinstance(raw.get("schema_version"), bool)
            and raw.get("schema_version") == 1
            and raw.get("marker_present") is True
            and isinstance(raw.get("marker_version"), int)
            and not isinstance(raw.get("marker_version"), bool)
            and raw.get("marker_version") == 1
            and raw.get("project_id") == self.project_id
            and raw.get("task_id") == child.identifier
            and raw.get("retained") is True
            and raw.get("malformed") is False
            and isinstance(generation, int)
            and not isinstance(generation, bool)
            and generation >= 0
            and isinstance(raw.get("authorized_by"), str)
            and str(raw.get("authorized_by") or "").strip()
            and isinstance(raw.get("actor_source"), str)
            and str(raw.get("actor_source") or "").strip()
            and isinstance(raw.get("marked_at"), str)
            and str(raw.get("marked_at") or "").strip()
            and isinstance(raw.get("updated_at"), str)
            and str(raw.get("updated_at") or "").strip()
        )
        if not valid:
            return None
        return {
            "schema_version": _RETAINED_CHILD_PROVENANCE_SCHEMA_VERSION,
            "kind": "owner_terminal_provenance",
            "project_id": self.project_id,
            "parent_id": parent_id,
            "task_id": child.identifier,
            "status": status,
            "landing_source": source,
            "landing_target": target,
            "revision": exact_revision,
            "authority_version": authority_version,
            "marker_version": int(raw["marker_version"]),
            "provenance_authority_generation": generation,
            "authorized_by": str(raw["authorized_by"]).strip(),
            "actor_source": str(raw["actor_source"]).strip(),
        }

    @staticmethod
    def _authoritative_issue(
        issues: Mapping[str, Issue] | None,
        identifier: str,
    ) -> Issue | None:
        if issues is None:
            return None
        return issues.get(identifier) or issues.get(identifier.casefold())

    def _graph(
        self,
        root: Issue,
        *,
        authoritative_issues: Mapping[str, Issue] | None = None,
        authoritative_children: Mapping[str, Sequence[Issue]] | None = None,
    ) -> EpicGraph:
        direct: list[Mapping[str, Any]] = []
        seen: set[str] = {root.identifier}
        cycle: str | None = None
        parent = None
        parent_id = str(root.parent_id or "").strip() or None
        if parent_id:
            parent = (
                self._authoritative_issue(authoritative_issues, parent_id)
                if authoritative_issues is not None
                else self.tracker.fetch_issue_detail(parent_id)
            )
            if parent is None:
                raise EpicTargetResolutionError(
                    f"parent {parent_id} for {root.identifier} is unavailable"
                )
            if parent.project_id and str(parent.project_id) != self.project_id:
                raise EpicTargetResolutionError(
                    f"parent {parent.identifier} for {root.identifier} escaped "
                    f"project {self.project_id}"
                )
        parent_is_rollup = None
        if parent is not None:
            parent_is_rollup = is_epic_rollup_issue(
                parent,
                authoritative_children=authoritative_children,
                tracker=None if authoritative_children is not None else self.tracker,
            )
        root_target = resolve_epic_target(
            root,
            parent=parent,
            default_branch=self.default_branch,
            parent_is_rollup=parent_is_rollup,
        )

        def visit(parent: Issue, ancestors: tuple[str, ...]) -> None:
            nonlocal cycle
            children = (
                authoritative_children.get(parent.identifier.casefold(), ())
                if authoritative_children is not None
                else self.tracker.fetch_children(parent.identifier)
            )
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
                nested = is_epic_rollup_issue(
                    child,
                    authoritative_children=authoritative_children,
                    tracker=None if authoritative_children is not None else self.tracker,
                )
                maintenance = _is_maintenance(child)
                target = epic_branch(parent.identifier)
                source = epic_branch(identifier) if nested else _source_branch(child)
                revision = _revision(child)
                standalone_landing = (
                    None
                    if nested or maintenance or parent.identifier != root.identifier
                    else _accepted_standalone_landing(
                        child,
                        expected_target=root_target,
                    )
                )
                if standalone_landing is not None:
                    source, target, revision = standalone_landing
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
                    authority_version = issue_authority_version(child)
                    projected: dict[str, Any] = {
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
                        "prefer_live_source": nested,
                        "authority_version": authority_version,
                        "exact_head": issue_exact_head(child),
                    }
                    provenance_child = (
                        child
                        if child.project_id
                        else replace(child, project_id=self.project_id)
                    )
                    retained = (
                        None
                        if maintenance or archived
                        else self._retained_terminal_provenance(
                            provenance_child,
                            parent_id=root.identifier,
                            status=status,
                            source=source,
                            target=target,
                            revision=revision,
                            authority_version=authority_version,
                        )
                    )
                    if retained is not None:
                        projected["retained_terminal_provenance"] = retained
                    direct.append(projected)
                # Walk every node, not only declared epics.  A malformed
                # task->epic->task cycle must be rejected before any rollup
                # review can be created.
                visit(child, (*ancestors, identifier))

        visit(root, (root.identifier,))
        return EpicGraph(
            parent_id=parent_id,
            epic_branch=epic_branch(root.identifier),
            target_branch=root_target,
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
        return prior_landings.get(
            (request.source, request.target)
        ) or prior_landings.get(f"{request.source}->{request.target}")

    def collect(
        self,
        task_id: str,
        *,
        prior_landings: Mapping[Any, LandingFact] | None = None,
        epic_revision: str | None = None,
        authoritative_issues: Mapping[str, Issue] | None = None,
        authoritative_children: Mapping[str, Sequence[Issue]] | None = None,
    ) -> WorkflowFacts:
        if self.cooperative_checkpoint is not None:
            self.cooperative_checkpoint()
        task_id = _required_text(task_id, "task_id")
        root = (
            self._authoritative_issue(authoritative_issues, task_id)
            if authoritative_issues is not None
            else self.tracker.fetch_issue_detail(task_id)
        )
        if root is None:
            collector = WorkflowFactCollector(
                project_id=self.project_id,
                tracker=self.tracker,
                sources=self.sources,
                clock=self.clock,
                cooperative_checkpoint=self.cooperative_checkpoint,
            )
            return collector.collect(
                task_id,
                authoritative_issues=authoritative_issues,
                authoritative_children=authoritative_children,
            )
        try:
            graph = self._graph(
                root,
                authoritative_issues=authoritative_issues,
                authoritative_children=authoritative_children,
            )
        except Exception as exc:  # noqa: BLE001 - evidence boundary

            def failed(_current: Issue, error: Exception = exc) -> Any:
                raise error

            base = WorkflowFactCollector(
                project_id=self.project_id,
                tracker=self.tracker,
                sources=self.sources,
                containment_source=failed,
                clock=self.clock,
                cooperative_checkpoint=self.cooperative_checkpoint,
            )
            return base.collect(
                task_id,
                authoritative_issues=authoritative_issues,
                authoritative_children=authoritative_children,
            )
        requested_epic_revision = _exact_head(epic_revision) or _revision(root)
        requests = [
            LandingRequest(
                str(child["landing_source"]),
                str(child["landing_target"]),
                child.get("revision"),
                prior=self._prior(
                    prior_landings,
                    LandingRequest(
                        str(child["landing_source"]),
                        str(child["landing_target"]),
                        child.get("revision"),
                    ),
                ),
                prefer_live_source=bool(child.get("prefer_live_source")),
                authoritative_target=True,
                trusted_target_revision=requested_epic_revision,
            )
            for child in graph.children
            if child.get("requires_landing")
            and child.get("retained_terminal_provenance") is None
        ]
        # The epic's own landing is deliberately included as a separate fact.
        # Rollup readiness only consumes child facts; auto-close/terminal
        # validation can consume this exact immediate-target fact later.
        requests.append(
            LandingRequest(
                graph.epic_branch,
                graph.target_branch,
                requested_epic_revision,
                prior=self._prior(
                    prior_landings,
                    LandingRequest(
                        graph.epic_branch,
                        graph.target_branch,
                        requested_epic_revision,
                    ),
                ),
                prefer_live_source=True,
                authoritative_target=True,
            )
        )
        base = WorkflowFactCollector(
            project_id=self.project_id,
            tracker=self.tracker,
            sources=self.sources,
            containment_source=lambda current: (
                graph.to_dict() if current.identifier == root.identifier else None
            ),
            landing_collector=self.landing_collector,
            clock=self.clock,
            cooperative_checkpoint=self.cooperative_checkpoint,
        )
        return base.collect(
            task_id,
            landing_requests=tuple(requests),
            authoritative_issues=authoritative_issues,
            authoritative_children=authoritative_children,
        )


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
            store=store,
            decision_limit=decision_limit,
            protected_event_lane_prefixes=("epic-event:",),
        )
        self.decision_limit = decision_limit
        self._latest: dict[str, EpicTaskDecision] = {}
        self._landings: dict[tuple[str, str], LandingFact] = {}

    def evaluate(
        self,
        tasks: Sequence[Issue],
        *,
        persist_evidence: bool = True,
        liveness_slo_seconds: Mapping[str, int] | None = None,
        authoritative_issues: Mapping[str, Issue] | None = None,
        authoritative_children: Mapping[str, Sequence[Issue]] | None = None,
    ) -> EpicDecisionBatch:
        # Select from actionable epics before applying the decision bound.
        # Terminal rows are stable and would otherwise permanently occupy the
        # same leading window, starving later active epics.
        selected = list(
            sorted(
                {
                    task.identifier: task
                    for task in tasks
                    if is_epic_rollup_issue(
                        task,
                        authoritative_children=authoritative_children,
                        tracker=(
                            None
                            if authoritative_children is not None
                            else self.collector.tracker
                        ),
                    )
                    and canonicalize_status(task.state) not in {MERGED, ARCHIVED}
                }.items()
            )
        )
        if len(selected) > self.decision_limit:
            offset = self.store.allocate_decision_window(
                total=len(selected),
                limit=self.decision_limit,
                scope=f"{self.collector.project_id}:epic",
            )
            selected = (selected[offset:] + selected[:offset])[
                : self.decision_limit
            ]
        evaluated: list[EpicTaskDecision] = []
        for _, task in selected:
            prior = dict(self._landings)
            try:
                persisted = self.store.latest_landing_facts(
                    project_id=self.collector.project_id,
                    task_id=task.identifier,
                    limit=DEFAULT_EPIC_DECISION_LIMIT,
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
            facts = self.collector.collect(
                task.identifier,
                prior_landings=prior,
                authoritative_issues=authoritative_issues,
                authoritative_children=authoritative_children,
            )
            for landing in facts.landings:
                if landing.durable:
                    self._landings[(landing.source, landing.target)] = landing
            durable = [
                landing.to_dict() for landing in facts.landings if landing.durable
            ]
            if durable and persist_evidence:
                self.store.record_landing_facts(
                    project_id=self.collector.project_id,
                    task_id=task.identifier,
                    facts=durable,
                )
            evaluated.append(
                EpicTaskDecision(
                    task,
                    facts,
                    _evaluate_epic_rollup(
                        task,
                        facts,
                        liveness_slo_seconds=liveness_slo_seconds,
                    ),
                )
            )
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
        payload: Mapping[str, Any] | None = None,
    ) -> WorkflowJob:
        """Materialize an explicit epic maintenance action idempotently.

        Rebase/repair, terminal validation, cleanup, and restart recovery may
        be requested by different maintenance loops.  They all enter the same
        job ledger with the same task/generation fence, so a restart cannot
        duplicate an external effect or revive superseded work.
        """

        write = self.schedule_action_write(
            task_id=task_id,
            action=action,
            generation=generation,
            expected_evidence_revision=expected_evidence_revision,
            expected_head_sha=expected_head_sha,
            priority=priority,
            max_attempts=max_attempts,
            payload=payload,
        )
        if write.job is None:  # no ordering/protection fence is used above
            raise RuntimeError("epic event materialization did not return a job")
        return write.job

    def schedule_action_write(
        self,
        *,
        task_id: str,
        action: EpicAction | str,
        generation: str | None = None,
        expected_evidence_revision: str | None = None,
        expected_head_sha: str | None = None,
        priority: int = 100,
        max_attempts: int = 5,
        payload: Mapping[str, Any] | None = None,
    ) -> WorkflowEventWrite:
        """Return the durable materialization result for an epic event.

        ``schedule_action`` retains its historical job-returning API.  Startup
        seeders use this richer result so a replayed idempotency key is not
        reported as a newly-enqueued job.
        """

        normalized_action = EpicAction(action)
        project_id = _required_text(self.collector.project_id, "project_id")
        identifier = _required_text(task_id, "task_id")
        job_generation = generation or (
            f"epic-maintenance:{self.store.allocate_event_generation()}"
        )
        write = self.store.materialize_event(
            project_id=project_id,
            task_id=identifier,
            decision_revision=job_generation,
            action=normalized_action.value,
            idempotency_namespace=f"epic-action:{normalized_action.value}",
            scheduling_lane=f"epic-event:{normalized_action.value}",
            expected_evidence_revision=expected_evidence_revision,
            expected_head_sha=expected_head_sha,
            priority=priority,
            max_attempts=max_attempts,
            payload=payload,
            reason=f"superseded by newer {normalized_action.value} evidence",
        )
        if write.job is None:  # no ordering/protection fence is used above
            raise RuntimeError("epic event materialization did not return a job")
        return write

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
            EpicProjection.from_decision(
                item.decision, active.get(item.task.identifier)
            )
            for item in self._latest.values()
        )


class EpicWorkflowBackend(Protocol):
    """Task-scoped effect boundary for durable epic actions."""

    def revalidate(
        self, context: WorkflowJobContext
    ) -> RevalidationResult | Awaitable[RevalidationResult]: ...

    def inspect(
        self, context: WorkflowJobContext
    ) -> EffectObservation | Awaitable[EffectObservation]: ...

    def apply(
        self, context: WorkflowJobContext
    ) -> EffectResult | Awaitable[EffectResult]: ...

    def verify(
        self,
        context: WorkflowJobContext,
        effect: EffectResult,
    ) -> VerificationResult | Awaitable[VerificationResult]: ...

    def build_transition(
        self,
        context: WorkflowJobContext,
        verification: VerificationResult,
    ) -> Any | Awaitable[Any]: ...


class EpicWorkflowEffectPort(Protocol):
    """Project-bound, task-scoped epic effects supplied by the orchestrator.

    The durable backend owns evidence revalidation and lifecycle intents.  The
    port owns only effects that cannot be expressed as a
    :class:`TransitionIntent`: creating or retiring one exact rollup review,
    synchronizing its exact terminal metadata, ensuring one exact rebase
    helper, and cleaning one exact landed epic.  A port method must never
    invoke a whole-project sweep.
    """

    def inspect_epic_effect(
        self,
        action: EpicAction,
        epic: Issue,
        facts: WorkflowFacts,
        payload: Mapping[str, Any],
    ) -> Mapping[str, Any] | None | Awaitable[Mapping[str, Any] | None]: ...

    def apply_epic_effect(
        self,
        action: EpicAction,
        epic: Issue,
        facts: WorkflowFacts,
        payload: Mapping[str, Any],
        *,
        idempotency_key: str,
        originating_job: str,
        evidence_generation: str,
    ) -> Mapping[str, Any] | Awaitable[Mapping[str, Any]]: ...

    def verify_epic_effect(
        self,
        action: EpicAction,
        epic: Issue,
        facts: WorkflowFacts,
        payload: Mapping[str, Any],
        receipt: Mapping[str, Any],
    ) -> Mapping[str, Any] | None | Awaitable[Mapping[str, Any] | None]: ...


@dataclass(frozen=True, slots=True)
class _EpicActionSnapshot:
    epic: Issue
    facts: WorkflowFacts
    decision: WorkDecision


@dataclass(frozen=True, slots=True)
class _AutoCloseLandingAuthority:
    """Immutable immediate-target landing consumed by one auto-close job."""

    exact_head: str
    source: str
    target: str
    landing_evidence_revision: str

    def receipt(self) -> dict[str, str]:
        return {
            "auto_close_exact_head": self.exact_head,
            "auto_close_landing_source": self.source,
            "auto_close_landing_target": self.target,
            "auto_close_landing_evidence_revision": (
                self.landing_evidence_revision
            ),
        }


class ProductionEpicWorkflowBackend:
    """Production evidence and intent boundary for all epic actions.

    Every worker phase re-reads the exact project tracker and collects fresh
    containment plus target-relative landing facts.  Durable landing evidence
    is written only by this enforce-mode backend; shadow evaluation passes
    ``persist_evidence=False`` and never constructs a worker handler.
    """

    def __init__(
        self,
        *,
        controller: EpicWorkflowController,
        tracker: Any,
        effects: EpicWorkflowEffectPort,
        persist_evidence: bool = True,
    ) -> None:
        self.controller = controller
        self.collector = controller.collector
        self.tracker = tracker
        self.effects = effects
        self.persist_evidence = bool(persist_evidence)

    @staticmethod
    def _payload(context: WorkflowJobContext) -> Mapping[str, Any]:
        return context.job.payload or {}

    def _fresh_snapshot(self, context: WorkflowJobContext) -> _EpicActionSnapshot:
        epic = self.tracker.fetch_issue_detail(context.job.task_id)
        if epic is None:
            raise WorkflowActionError(
                f"epic {context.job.task_id} is unavailable",
                category=WorkflowFailureCategory.TRANSIENT,
                retryable=True,
            )
        if str(self.collector.project_id or "").strip() != context.job.project_id:
            raise WorkflowActionError(
                "epic workflow task resolved outside its project binding",
                category=WorkflowFailureCategory.POLICY,
                retryable=False,
            )
        try:
            epic = normalize_issue_project_scope(epic, context.job.project_id)
        except EpicProjectScopeError as exc:
            raise WorkflowActionError(
                "epic workflow task resolved outside its project binding",
                category=WorkflowFailureCategory.POLICY,
                retryable=False,
            ) from exc
        if not is_epic_rollup_issue(epic, tracker=self.tracker):
            raise WorkflowActionError(
                f"{epic.identifier} is not an epic",
                category=WorkflowFailureCategory.POLICY,
                retryable=False,
            )

        prior: dict[tuple[str, str], LandingFact] = {}
        for raw in self.controller.store.latest_landing_facts(
            project_id=context.job.project_id,
            task_id=epic.identifier,
            limit=DEFAULT_EPIC_DECISION_LIMIT,
        ):
            try:
                landing = LandingFact.from_dict(raw)
            except (TypeError, ValueError):
                continue
            if landing.durable:
                prior[(landing.source, landing.target)] = landing
        cleanup_revision = (
            context.job.expected_head_sha
            if context.job.action == EpicAction.CLEANUP.value
            else None
        )
        facts = self.collector.collect(
            epic.identifier,
            prior_landings=prior,
            epic_revision=cleanup_revision,
        )
        durable = tuple(
            landing.to_dict() for landing in facts.landings if landing.durable
        )
        if durable and self.persist_evidence:
            self.controller.store.record_landing_facts(
                project_id=context.job.project_id,
                task_id=epic.identifier,
                facts=durable,
            )
        return _EpicActionSnapshot(epic, facts, _evaluate_epic_rollup(epic, facts))

    async def _load_snapshot(self, context: WorkflowJobContext) -> _EpicActionSnapshot:
        """Collect tracker and Git evidence without blocking lease heartbeats."""

        snapshot = await asyncio.to_thread(self._fresh_snapshot, context)
        return await _resolve_backend(snapshot)

    @staticmethod
    async def _observe_external(
        operation: Callable[..., Any], /, *args: Any, **kwargs: Any
    ) -> Any:
        """Run synchronous forge/tracker observations outside the event loop."""

        result = await asyncio.to_thread(operation, *args, **kwargs)
        return await _resolve_backend(result)

    @staticmethod
    def _containment(snapshot: _EpicActionSnapshot) -> Mapping[str, Any]:
        fact = snapshot.facts.fact(FactDomain.CONTAINMENT)
        if fact.state is not FactState.KNOWN or not isinstance(fact.value, Mapping):
            return {}
        return fact.value

    @classmethod
    def _own_landing(cls, snapshot: _EpicActionSnapshot) -> LandingFact | None:
        containment = cls._containment(snapshot)
        source = str(containment.get("epic_branch") or "").strip()
        target = str(containment.get("target_branch") or "").strip()
        if not source or not target:
            return None
        return next(
            (
                landing
                for landing in snapshot.facts.landings
                if landing.source == source and landing.target == target
            ),
            None,
        )

    @classmethod
    def _auto_close_landing_authority(
        cls,
        snapshot: _EpicActionSnapshot,
    ) -> _AutoCloseLandingAuthority | None:
        """Return one canonical durable landing for a headless auto-close.

        The containment fact owns the source and immediate target even after
        mutable task branch fields have been cleared.  Requiring one exact,
        durable positive fact makes an ambiguous or stale landing set fail
        closed without restoring mutable issue-head authority.
        """

        candidates = tuple(
            landing
            for landing in epic_immediate_target_landings(snapshot.facts)
            if landing.project_id == snapshot.facts.project_id
            and landing.state is LandingState.LANDED
            and landing.durable
            and _exact_head(landing.revision) is not None
        )
        if len(candidates) != 1:
            return None
        landing = candidates[0]
        revision = _exact_head(landing.revision)
        if revision is None:
            return None
        proof_source = landing.proof.get("source_sha")
        if proof_source is not None and _exact_head(proof_source) != revision:
            return None
        evidence_revision = str(landing.evidence_revision or "").strip()
        if not evidence_revision:
            return None
        return _AutoCloseLandingAuthority(
            revision,
            landing.source,
            landing.target,
            evidence_revision,
        )

    @staticmethod
    def _revalidation_details(context: WorkflowJobContext) -> Mapping[str, Any]:
        checkpoint = context.job.checkpoint or {}
        revalidation = checkpoint.get("revalidation", {})
        if not isinstance(revalidation, Mapping):
            return {}
        details = revalidation.get("details", {})
        return details if isinstance(details, Mapping) else {}

    @staticmethod
    def _revalidated_evidence_revision(context: WorkflowJobContext) -> str:
        checkpoint = context.job.checkpoint or {}
        revalidation = checkpoint.get("revalidation", {})
        if not isinstance(revalidation, Mapping):
            return ""
        return str(revalidation.get("evidence_revision") or "").strip()

    @staticmethod
    def _serialized_auto_close_authority(
        raw: Mapping[str, Any],
    ) -> _AutoCloseLandingAuthority | None:
        exact_head = _exact_head(raw.get("auto_close_exact_head"))
        source = str(raw.get("auto_close_landing_source") or "").strip()
        target = str(raw.get("auto_close_landing_target") or "").strip()
        evidence_revision = str(
            raw.get("auto_close_landing_evidence_revision") or ""
        ).strip()
        if not all((exact_head, source, target, evidence_revision)):
            return None
        return _AutoCloseLandingAuthority(
            exact_head,
            source,
            target,
            evidence_revision,
        )

    @classmethod
    def _checkpoint_auto_close_authority(
        cls,
        context: WorkflowJobContext,
    ) -> _AutoCloseLandingAuthority | None:
        return cls._serialized_auto_close_authority(
            cls._revalidation_details(context)
        )

    @classmethod
    def _receipt_auto_close_authority(
        cls,
        receipt: Mapping[str, Any],
    ) -> _AutoCloseLandingAuthority | None:
        return cls._serialized_auto_close_authority(receipt)

    @classmethod
    def _cleanup_head(cls, snapshot: _EpicActionSnapshot) -> str | None:
        """Return the exact source generation observed for cleanup."""

        own = cls._own_landing(snapshot)
        return _exact_head(getattr(own, "revision", None))

    @classmethod
    def _cleanup_generation_is_current(
        cls,
        context: WorkflowJobContext,
        snapshot: _EpicActionSnapshot,
    ) -> bool:
        """Fence cleanup to the immutable generation captured at enqueue."""

        expected = _exact_head(context.job.expected_head_sha)
        observed = cls._cleanup_head(snapshot)
        return bool(expected and observed and expected == observed)

    @classmethod
    def _is_action_current(
        cls,
        action: EpicAction,
        snapshot: _EpicActionSnapshot,
        payload: Mapping[str, Any],
    ) -> bool:
        if action is EpicAction.AUTO_CLOSE:
            # A successful auto-close transition may stage terminal validation
            # instead of applying Merged immediately.  From that point onward
            # the terminal-audit workflow owns lifecycle progress, so a
            # delayed event-lane copy must not replay the external retirement
            # effect or ask the coordinator to terminalize the epic again.
            # Keep this source-state fence aligned with
            # TerminalTransitionCoordinator._landed_epic_validation_binding.
            status = canonicalize_status(snapshot.epic.state)
            if status not in {IN_PROGRESS, IN_REVIEW, DONE}:
                return False
            authority = cls._auto_close_landing_authority(snapshot)
            mutable_head = _exact_head(issue_exact_head(snapshot.epic))
            if mutable_head is not None:
                landing_matches_task = bool(
                    authority is not None
                    and authority.exact_head == mutable_head
                )
            else:
                landing_matches_task = bool(
                    authority is not None
                    and str(snapshot.epic.issue_type or "").strip().lower()
                    == "epic"
                    and not str(snapshot.epic.parent_id or "").strip()
                    and status == IN_PROGRESS
                )
            return bool(
                action.value in snapshot.decision.durable_jobs
                and snapshot.decision.reason_code
                == "terminal.immediate_target_landing_proven"
                and landing_matches_task
            )
        if action is EpicAction.CLEANUP:
            own = cls._own_landing(snapshot)
            status = canonicalize_status(snapshot.epic.state)
            children = cls._containment(snapshot).get("children")
            containment_terminal = bool(
                isinstance(children, (list, tuple))
                and all(
                    isinstance(child, Mapping)
                    and canonicalize_status(child.get("status"))
                    in {DONE, MERGED, ARCHIVED}
                    for child in children
                )
            )
            if status == ARCHIVED:
                return containment_terminal
            return bool(
                status == MERGED
                and own is not None
                and own.state is LandingState.LANDED
                and containment_terminal
            )
        if action is EpicAction.REBASE_REPAIR:
            # A stale rebase request must not mutate the newly resolved target
            # merely because fresh facts still request *some* rebase repair.
            # Check the event's exact immediate target before the generic
            # durable-job authorization below.
            return bool(
                action.value in snapshot.decision.durable_jobs
                and cls._rebase_target_is_current(snapshot, payload)
            )
        if action.value in snapshot.decision.durable_jobs:
            return True
        if action in {
            EpicAction.READINESS,
            EpicAction.TARGET_RESOLUTION,
            EpicAction.TERMINAL_VALIDATION,
            EpicAction.RESTART_RECONCILIATION,
        }:
            return canonicalize_status(snapshot.epic.state) not in {MERGED, ARCHIVED}
        return False

    @classmethod
    def _rebase_target_is_current(
        cls,
        snapshot: _EpicActionSnapshot,
        payload: Mapping[str, Any],
    ) -> bool:
        """Fence a rebase artifact to its exact non-terminal target.

        Before an effect exists, ``_is_action_current`` additionally requires
        the fresh decision to authorize REBASE_REPAIR.  After helper creation,
        that helper itself may remove the action from the decision; restart and
        verification may then observe only this narrower artifact fence.
        """

        expected_target = str(payload.get("target_branch") or "").strip()
        actual_target = str(
            cls._containment(snapshot).get("target_branch") or ""
        ).strip()
        return bool(
            expected_target
            and expected_target == actual_target
            and canonicalize_status(snapshot.epic.state) not in {MERGED, ARCHIVED}
        )

    @classmethod
    def _require_action_current(
        cls,
        context: WorkflowJobContext,
        action: EpicAction,
        snapshot: _EpicActionSnapshot,
        payload: Mapping[str, Any],
    ) -> None:
        """Fence every effect phase with a fresh authorization snapshot."""

        current = cls._is_action_current(action, snapshot, payload)
        if action is EpicAction.AUTO_CLOSE:
            current = bool(
                current
                and cls._auto_close_landing_authority(snapshot)
                == cls._checkpoint_auto_close_authority(context)
                and snapshot.decision.evidence_revision
                == cls._revalidated_evidence_revision(context)
            )
        if action is EpicAction.CLEANUP:
            current = current and cls._cleanup_generation_is_current(
                context, snapshot
            )
        if current:
            return
        raise WorkflowActionSuperseded(
            f"fresh epic evidence no longer authorizes {action.value}",
            replacement_generation=f"reassess:{snapshot.decision.evidence_revision}",
        )

    @classmethod
    def _snapshot_details(
        cls,
        action: EpicAction,
        snapshot: _EpicActionSnapshot,
    ) -> dict[str, Any]:
        containment = cls._containment(snapshot)
        own = cls._own_landing(snapshot)
        details = {
            "action": action.value,
            "reason_code": snapshot.decision.reason_code,
            "epic_branch": containment.get("epic_branch"),
            "target_branch": containment.get("target_branch"),
            "own_landing_state": own.state.value if own is not None else None,
        }
        if action is EpicAction.AUTO_CLOSE:
            authority = cls._auto_close_landing_authority(snapshot)
            if authority is not None:
                details.update(authority.receipt())
        return details

    async def revalidate(self, context: WorkflowJobContext) -> RevalidationResult:
        action = EpicAction(context.job.action)
        snapshot = await self._load_snapshot(context)
        payload = self._payload(context)
        current = self._is_action_current(action, snapshot, payload)
        if action is EpicAction.CLEANUP:
            current = current and self._cleanup_generation_is_current(
                context, snapshot
            )
        if action is EpicAction.REBASE_REPAIR:
            requested_revision = str(payload.get("evidence_revision") or "").strip()
            saved_effect = (context.job.checkpoint or {}).get("effect")
            if isinstance(saved_effect, Mapping):
                # Creating the helper can itself remove REBASE_REPAIR from the
                # fresh decision.  A durable receipt is restart authority to
                # verify that exact already-created effect, but never to apply
                # a helper to a different target or a terminal epic.
                current = self._rebase_target_is_current(snapshot, payload)
            # A new fresh decision which still authorizes the same target is
            # stronger current authority than the event callback's earlier
            # observation revision.  Only consult an older request revision
            # as crash-recovery evidence after the fresh decision no longer
            # authorizes creation.  Once an effect receipt exists, creation
            # itself may have changed containment by adding the maintenance
            # child; restart must replay verification rather than supersede
            # the already-observed effect.
            if (
                not current
                and requested_revision
                and not isinstance(saved_effect, Mapping)
                and requested_revision != snapshot.decision.evidence_revision
            ):
                # The helper-task write itself changes containment.  A process
                # can die after that write but before returning the receipt;
                # observe the exact helper before treating the old generation
                # as stale so restart resumes verification without creating a
                # duplicate helper.
                observed = await self._observe_external(
                    self.effects.inspect_epic_effect,
                    action,
                    snapshot.epic,
                    snapshot.facts,
                    payload,
                )
                current = observed is not None
                if not current:
                    recoverable = getattr(
                        self.effects, "recoverable_epic_effect", None
                    )
                    if callable(recoverable):
                        current = bool(
                            await self._observe_external(
                                recoverable,
                                action,
                                snapshot.epic,
                                snapshot.facts,
                                payload,
                            )
                        )
        auto_close_authority = (
            self._auto_close_landing_authority(snapshot)
            if action is EpicAction.AUTO_CLOSE
            else None
        )
        return RevalidationResult(
            context.job.generation,
            evidence_revision=snapshot.decision.evidence_revision,
            head_sha=(
                self._cleanup_head(snapshot)
                if action is EpicAction.CLEANUP
                else (
                    auto_close_authority.exact_head
                    if auto_close_authority is not None
                    else issue_exact_head(snapshot.epic)
                )
            ),
            current=current,
            details=self._snapshot_details(action, snapshot),
        )

    @classmethod
    def _rollup_status(cls, snapshot: _EpicActionSnapshot) -> str | None:
        children = cls._containment(snapshot).get("children")
        if not isinstance(children, (list, tuple)):
            return None
        statuses = [
            child.get("status") for child in children if isinstance(child, Mapping)
        ]
        return canonicalize_status(epic_rollup_state(statuses)) or None

    @classmethod
    def _transition_target(
        cls, action: EpicAction, snapshot: _EpicActionSnapshot
    ) -> str | None:
        if action is EpicAction.ROLLUP_RECONCILIATION:
            target = cls._rollup_status(snapshot)
            if (
                canonicalize_status(snapshot.epic.state) == BACKLOG
                and target == IN_PROGRESS
            ):
                # Backlog promotion is a two-step lifecycle transition. The
                # next generation observes Open and completes In Progress.
                return OPEN
            return target
        if action is EpicAction.ROLLUP_REVIEW_CREATION:
            return IN_REVIEW
        if action is EpicAction.AUTO_CLOSE:
            own = cls._own_landing(snapshot)
            if own is not None and own.state is LandingState.LANDED:
                return MERGED
        return None

    @staticmethod
    def _transition_reason(action: EpicAction) -> str:
        if action is EpicAction.ROLLUP_REVIEW_CREATION:
            return "rollup.review_created"
        if action is EpicAction.AUTO_CLOSE:
            return "terminal.immediate_target_landing_proven"
        return "rollup.reconciled"

    @classmethod
    def _transition_receipt(
        cls,
        action: EpicAction,
        snapshot: _EpicActionSnapshot,
        *,
        requested_status: str,
        extra: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        receipt = dict(extra or {})
        effect_head = _exact_head(receipt.get("source_head"))
        if action is EpicAction.AUTO_CLOSE:
            authority = cls._auto_close_landing_authority(snapshot)
            if authority is None:
                raise WorkflowActionError(
                    "epic auto-close has no exact immediate-target landing revision",
                    category=WorkflowFailureCategory.TRANSIENT,
                    retryable=True,
                )
            effect_head = authority.exact_head
            receipt.update(authority.receipt())
        receipt.update(
            {
                "action": action.value,
                "task_id": snapshot.epic.identifier,
                "requested_status": requested_status,
                "expected_status": canonicalize_status(snapshot.epic.state),
                "expected_version": issue_authority_version(snapshot.epic),
                "exact_head": effect_head
                or _exact_head(issue_exact_head(snapshot.epic)),
                "reason_code": cls._transition_reason(action),
                "evidence_revision": snapshot.decision.evidence_revision,
            }
        )
        return receipt

    async def inspect(self, context: WorkflowJobContext) -> EffectObservation:
        action = EpicAction(context.job.action)
        snapshot = await self._load_snapshot(context)
        payload = self._payload(context)
        if action in _EPIC_READ_ONLY_ACTIONS:
            return EffectObservation(
                True,
                {
                    **self._snapshot_details(action, snapshot),
                    "evidence_revision": snapshot.decision.evidence_revision,
                },
            )
        if action is EpicAction.ROLLUP_RECONCILIATION:
            target = self._transition_target(action, snapshot)
            if target is None:
                return EffectObservation(True, {"action": action.value, "noop": True})
            receipt = self._transition_receipt(
                action, snapshot, requested_status=target
            )
            return EffectObservation(
                canonicalize_status(snapshot.epic.state) == target,
                receipt,
            )
        if action in _EPIC_EXTERNAL_ACTIONS:
            observed = await self._observe_external(
                self.effects.inspect_epic_effect,
                action,
                snapshot.epic,
                snapshot.facts,
                payload,
            )
            if observed is None:
                return EffectObservation(False)
            receipt = dict(observed)
            if action is EpicAction.ROLLUP_REVIEW_CREATION:
                receipt = self._transition_receipt(
                    action,
                    snapshot,
                    requested_status=IN_REVIEW,
                    extra=receipt,
                )
            return EffectObservation(True, receipt)
        if action is EpicAction.AUTO_CLOSE:
            self._require_action_current(context, action, snapshot, payload)
            target = self._transition_target(action, snapshot)
            if target is None:
                return EffectObservation(True, {"action": action.value, "noop": True})
            observed = await self._observe_external(
                self.effects.inspect_epic_effect,
                action,
                snapshot.epic,
                snapshot.facts,
                payload,
            )
            if observed is None:
                return EffectObservation(False)
            receipt = self._transition_receipt(
                action,
                snapshot,
                requested_status=target,
                extra=dict(observed),
            )
            return EffectObservation(
                canonicalize_status(snapshot.epic.state) == target,
                receipt,
            )
        raise WorkflowActionError(
            f"unsupported epic action {action.value}",
            category=WorkflowFailureCategory.POLICY,
            retryable=False,
        )

    async def apply(self, context: WorkflowJobContext) -> EffectResult:
        action = EpicAction(context.job.action)
        snapshot = await self._load_snapshot(context)
        payload = self._payload(context)
        self._require_action_current(context, action, snapshot, payload)
        if action is EpicAction.ROLLUP_RECONCILIATION:
            target = self._transition_target(action, snapshot)
            if target is None:
                return EffectResult({"action": action.value, "noop": True})
            return EffectResult(
                self._transition_receipt(action, snapshot, requested_status=target)
            )
        if action is EpicAction.AUTO_CLOSE:
            target = self._transition_target(action, snapshot)
            if target is None:
                return EffectResult({"action": action.value, "noop": True})
            receipt = await _resolve_backend(
                self.effects.apply_epic_effect(
                    action,
                    snapshot.epic,
                    snapshot.facts,
                    payload,
                    idempotency_key=context.idempotency_key,
                    originating_job=context.job.job_id,
                    evidence_generation=context.job.generation,
                )
            )
            if not isinstance(receipt, Mapping):
                raise WorkflowActionError(
                    "epic auto-close retirement did not return a durable receipt",
                    category=WorkflowFailureCategory.PERMANENT,
                    retryable=False,
                )
            return EffectResult(
                self._transition_receipt(
                    action,
                    snapshot,
                    requested_status=target,
                    extra=dict(receipt),
                )
            )
        if action in _EPIC_EXTERNAL_ACTIONS:
            receipt = await _resolve_backend(
                self.effects.apply_epic_effect(
                    action,
                    snapshot.epic,
                    snapshot.facts,
                    payload,
                    idempotency_key=context.idempotency_key,
                    originating_job=context.job.job_id,
                    evidence_generation=context.job.generation,
                )
            )
            if not isinstance(receipt, Mapping):
                raise WorkflowActionError(
                    "epic effect did not return a durable receipt",
                    category=WorkflowFailureCategory.PERMANENT,
                    retryable=False,
                )
            normalized = dict(receipt)
            if action is EpicAction.ROLLUP_REVIEW_CREATION:
                normalized = self._transition_receipt(
                    action,
                    snapshot,
                    requested_status=IN_REVIEW,
                    extra=normalized,
                )
            return EffectResult(normalized)
        if action in _EPIC_READ_ONLY_ACTIONS:
            return EffectResult(
                {
                    **self._snapshot_details(action, snapshot),
                    "evidence_revision": snapshot.decision.evidence_revision,
                }
            )
        raise WorkflowActionError(
            f"unsupported epic action {action.value}",
            category=WorkflowFailureCategory.POLICY,
            retryable=False,
        )

    async def verify(
        self,
        context: WorkflowJobContext,
        effect: EffectResult,
    ) -> VerificationResult:
        action = EpicAction(context.job.action)
        snapshot = await self._load_snapshot(context)
        payload = self._payload(context)
        if action is EpicAction.REBASE_REPAIR:
            # The exact helper may itself make the rebase action disappear from
            # the fresh decision.  Verification is allowed to inspect that
            # already-created artifact only while its original target and epic
            # terminality remain current; ``verify_epic_effect`` proves the
            # exact helper identity/bookkeeping before completion.
            if not self._rebase_target_is_current(snapshot, payload):
                raise WorkflowActionSuperseded(
                    "fresh epic evidence no longer authorizes rebase verification",
                    replacement_generation=(
                        f"reassess:{snapshot.decision.evidence_revision}"
                    ),
                )
        else:
            self._require_action_current(context, action, snapshot, payload)
        if action in _EPIC_EXTERNAL_ACTIONS:
            verified = await self._observe_external(
                self.effects.verify_epic_effect,
                action,
                snapshot.epic,
                snapshot.facts,
                payload,
                effect.receipt,
            )
            if verified is None:
                return VerificationResult(
                    False,
                    reason=f"{action.value} effect is not yet observable",
                )
            receipt = dict(verified)
            if action is EpicAction.ROLLUP_REVIEW_CREATION:
                receipt = self._transition_receipt(
                    action,
                    snapshot,
                    requested_status=IN_REVIEW,
                    extra=receipt,
                )
            return VerificationResult(True, receipt)
        if action is EpicAction.AUTO_CLOSE:
            target = self._transition_target(action, snapshot)
            if target is None:
                return VerificationResult(True, {"action": action.value, "noop": True})
            verified = await self._observe_external(
                self.effects.verify_epic_effect,
                action,
                snapshot.epic,
                snapshot.facts,
                payload,
                effect.receipt,
            )
            if verified is None:
                return VerificationResult(
                    False,
                    reason="epic auto-close review retirement is not yet observable",
                )
            return VerificationResult(
                True,
                self._transition_receipt(
                    action,
                    snapshot,
                    requested_status=target,
                    extra=dict(verified),
                ),
            )
        if action is EpicAction.ROLLUP_RECONCILIATION:
            target = self._transition_target(action, snapshot)
            if target is None:
                return VerificationResult(True, {"action": action.value, "noop": True})
            return VerificationResult(
                True,
                self._transition_receipt(action, snapshot, requested_status=target),
            )
        return VerificationResult(
            True,
            {
                **self._snapshot_details(action, snapshot),
                "evidence_revision": snapshot.decision.evidence_revision,
            },
        )

    async def build_transition(
        self,
        context: WorkflowJobContext,
        verification: VerificationResult,
    ) -> TransitionIntent | None:
        receipt = verification.receipt
        action = EpicAction(context.job.action)
        if action is EpicAction.AUTO_CLOSE:
            snapshot = await self._load_snapshot(context)
            self._require_action_current(
                context,
                action,
                snapshot,
                self._payload(context),
            )
            current_authority = self._auto_close_landing_authority(snapshot)
            receipt_authority = self._receipt_auto_close_authority(receipt)
            if current_authority is None or current_authority != receipt_authority:
                raise WorkflowActionSuperseded(
                    "epic auto-close landing authority changed before transition",
                    replacement_generation=(
                        f"reassess:{snapshot.decision.evidence_revision}"
                    ),
                )
        requested = str(receipt.get("requested_status") or "").strip()
        if not requested:
            return None
        expected_status = str(receipt.get("expected_status") or "").strip()
        expected_version = str(receipt.get("expected_version") or "").strip()
        reason_code = str(receipt.get("reason_code") or "").strip()
        if not expected_status or not expected_version or not reason_code:
            raise WorkflowActionError(
                "epic transition receipt is incomplete",
                category=WorkflowFailureCategory.PERMANENT,
                retryable=False,
            )
        if canonicalize_status(expected_status) == canonicalize_status(requested):
            return None
        exact_head = _exact_head(receipt.get("exact_head"))
        return TransitionIntent(
            project_id=context.job.project_id,
            task_id=context.job.task_id,
            expected_status=expected_status,
            expected_version=expected_version,
            requested_status=requested,
            actor="oompah",
            authority=TransitionAuthority.ORCHESTRATOR,
            reason_code=reason_code,
            idempotency_key=f"{context.idempotency_key}:transition",
            originating_job=context.job.job_id,
            evidence_generation=context.job.generation,
            exact_head=exact_head,
            precondition_revision=(
                str(receipt.get("evidence_revision") or "").strip() or None
                if reason_code == "terminal.immediate_target_landing_proven"
                else None
            ),
        )


async def _resolve_backend(value: Any) -> Any:
    import inspect

    return await value if inspect.isawaitable(value) else value


class EpicWorkflowHandler:
    """Validate and execute one exact epic-domain action."""

    domain = WorkflowActionDomain.TRACKER

    def __init__(self, backend: EpicWorkflowBackend) -> None:
        self.backend = backend

    async def revalidate(self, context: WorkflowJobContext) -> RevalidationResult:
        result = await _resolve_backend(self.backend.revalidate(context))
        if not isinstance(result, RevalidationResult):
            raise WorkflowActionError("epic backend returned invalid revalidation")
        return result

    async def inspect(self, context: WorkflowJobContext) -> EffectObservation:
        result = await _resolve_backend(self.backend.inspect(context))
        if not isinstance(result, EffectObservation):
            raise WorkflowActionError("epic backend returned invalid observation")
        return result

    async def apply(self, context: WorkflowJobContext) -> EffectResult:
        result = await _resolve_backend(self.backend.apply(context))
        if not isinstance(result, EffectResult):
            raise WorkflowActionError("epic backend returned invalid effect")
        return result

    async def verify(
        self, context: WorkflowJobContext, effect: EffectResult
    ) -> VerificationResult:
        result = await _resolve_backend(self.backend.verify(context, effect))
        if not isinstance(result, VerificationResult):
            raise WorkflowActionError("epic backend returned invalid verification")
        return result

    async def build_transition(
        self, context: WorkflowJobContext, verification: VerificationResult
    ) -> Any:
        return await _resolve_backend(
            self.backend.build_transition(context, verification)
        )

    @property
    def pending_mutation_count(self) -> int:
        effects = getattr(self.backend, "effects", None)
        return int(getattr(effects, "pending_mutation_count", 0) or 0)

    async def drain_mutations(self, *, timeout_seconds: float | None = None) -> bool:
        effects = getattr(self.backend, "effects", None)
        drain = getattr(effects, "drain_mutations", None)
        if not callable(drain):
            return True
        result = drain(timeout_seconds=timeout_seconds)
        resolved = await _resolve_backend(result)
        return resolved is not False


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
    "EpicWorkflowBackend",
    "EpicWorkflowEffectPort",
    "EpicWorkflowHandler",
    "ProductionEpicWorkflowBackend",
    "epic_branch",
    "is_epic_rollup_issue",
    "resolve_epic_target",
]
