"""Container-level dependency and code-reachability analysis.

Task dependencies are not the whole delivery graph for shared epics.  A task
in one private epic can wait for a task in another private epic, while the
other task waits for a commit which is still confined to the first epic.  The
task graph is acyclic in that case, but neither epic has an authorized
delivery order.

This module deliberately models only *known* reachability facts.  A terminal
task whose parent epic is still nonterminal is treated as confined to that
epic.  Once the parent epic has landed, the edge is omitted: the default
branch is then an authorized delivery path.  No sibling branch is ever
considered an implicit synchronization target here.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from oompah.dependency_graph import (
    effective_dependencies,
    integration_dependencies,
)
from oompah.models import Issue
from oompah.statuses import READY_TO_INTEGRATE, canonicalize_status, is_terminal_status


def _identifier(issue: Issue) -> str:
    return str(issue.identifier or issue.id or "").strip()


def _aliases(issue: Issue) -> set[str]:
    return {
        str(value).strip()
        for value in (issue.id, issue.identifier)
        if str(value or "").strip()
    }


def _is_epic(issue: Issue, parent_ids: set[str]) -> bool:
    return (
        str(issue.issue_type or "").strip().lower() == "epic"
        or any(
            str(label).strip().lower() == "epic"
            for label in (issue.labels or [])
        )
        or bool(_aliases(issue) & parent_ids)
    )


def _same_project(first: Issue, second: Issue) -> bool:
    first_project = str(first.project_id or "").strip()
    second_project = str(second.project_id or "").strip()
    return not first_project or not second_project or first_project == second_project


@dataclass(frozen=True)
class ContainerDependencyEdge:
    """One authorized-delivery dependency between two epic containers."""

    consumer: str
    provider: str
    dependent_tasks: tuple[str, ...] = ()
    prerequisite_tasks: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "consumer": self.consumer,
            "provider": self.provider,
            "dependent_tasks": list(self.dependent_tasks),
            "prerequisite_tasks": list(self.prerequisite_tasks),
        }


@dataclass(frozen=True)
class ContainerDependencyCycle:
    """A deterministic cycle in the required-code/container graph."""

    path: tuple[str, ...]
    edges: tuple[ContainerDependencyEdge, ...]
    affected_tasks: tuple[str, ...]
    affected_ready_tasks: tuple[str, ...]
    prerequisite_shas: tuple[tuple[str, str], ...]
    authoritative_container: str | None
    selected_repair: str = "needs_human_authorized_delivery_order"

    @property
    def containers(self) -> tuple[str, ...]:
        """Return the closed container path without a duplicate final node."""

        return self.path[:-1]

    @property
    def message_path(self) -> str:
        return " -> ".join(self.path)

    def to_dict(self) -> dict[str, object]:
        return {
            "path": list(self.path),
            "containers": list(self.containers),
            "edges": [edge.to_dict() for edge in self.edges],
            "affected_tasks": list(self.affected_tasks),
            "affected_ready_tasks": list(self.affected_ready_tasks),
            "prerequisite_shas": {
                task: sha for task, sha in self.prerequisite_shas
            },
            "authoritative_container": self.authoritative_container,
            "selected_repair": self.selected_repair,
            "repair_plan": {
                "kind": (
                    "common_authoritative_parent"
                    if self.authoritative_container
                    else "needs_authorized_delivery_order"
                ),
                "authoritative_container": self.authoritative_container,
                "prerequisite_shas": {
                    task: sha for task, sha in self.prerequisite_shas
                },
                "dependent_containers": list(self.containers),
                "policy": "parent_only",
            },
        }


def _container_resolver(
    issues: Sequence[Issue],
) -> tuple[dict[str, Issue], dict[str, str], set[str]]:
    index: dict[str, Issue] = {}
    for issue in issues:
        for alias in _aliases(issue):
            index[alias] = issue
    parent_ids = {
        str(issue.parent_id).strip()
        for issue in issues
        if str(issue.parent_id or "").strip()
    }
    epic_ids = {
        _identifier(issue)
        for issue in issues
        if _is_epic(issue, parent_ids)
    }
    return index, {
        alias: _identifier(issue)
        for issue in issues
        for alias in _aliases(issue)
        if _identifier(issue)
    }, epic_ids


def container_for_issue(
    issue: Issue,
    issues_by_alias: Mapping[str, Issue],
    epic_ids: set[str] | None = None,
) -> Issue | None:
    """Return the nearest epic container owning ``issue``.

    Parent chains are bounded by the number of visited aliases so malformed
    decomposition metadata cannot make queue analysis loop forever.
    """

    if epic_ids is None:
        epic_ids = {
            _identifier(candidate)
            for candidate in issues_by_alias.values()
            if str(candidate.issue_type or "").strip().lower() == "epic"
        }
    current = issue
    visited: set[str] = set()
    while current is not None:
        current_id = _identifier(current)
        if current_id in epic_ids:
            return current
        parent_id = str(current.parent_id or "").strip()
        if not parent_id or parent_id in visited:
            return None
        visited.add(parent_id)
        current = issues_by_alias.get(parent_id)
    return None


def _dependency_identifiers(
    issue: Issue,
    issues_by_alias: Mapping[str, Issue],
    *,
    include_hard_start: bool,
) -> tuple[str, ...]:
    """Return own and inherited dependency identifiers for one issue."""

    result = list(integration_dependencies(issue, issues_by_alias))
    if include_hard_start:
        result.extend(
            dependency
            for dependency in effective_dependencies(
                issue,
                issues_by_alias,
                hard_start=True,
            )
            if dependency not in result
        )
    return tuple(result)


def container_dependency_edges(
    issues: Iterable[Issue],
    *,
    include_hard_start: bool = False,
) -> tuple[ContainerDependencyEdge, ...]:
    """Build deterministic container edges from a task dependency snapshot.

    An edge is emitted only when both containers are still nonterminal and
    the prerequisite code is therefore confined to its provider container.
    This is the important distinction from ordinary task-level cycle checks.
    """

    snapshot = tuple(issues)
    index, _aliases_by_identifier, epic_ids = _container_resolver(snapshot)
    grouped: dict[tuple[str, str], dict[str, set[str]]] = defaultdict(
        lambda: {"dependent": set(), "prerequisite": set()}
    )
    for issue in snapshot:
        if is_terminal_status(issue.state):
            continue
        consumer = container_for_issue(issue, index, epic_ids)
        if consumer is None or is_terminal_status(consumer.state):
            continue
        consumer_id = _identifier(consumer)
        if not consumer_id:
            continue
        for dependency_id in _dependency_identifiers(
            issue,
            index,
            include_hard_start=include_hard_start,
        ):
            dependency = index.get(dependency_id)
            if dependency is None or not _same_project(issue, dependency):
                continue
            provider = container_for_issue(dependency, index, epic_ids)
            if provider is None or is_terminal_status(provider.state):
                continue
            provider_id = _identifier(provider)
            if not provider_id or provider_id == consumer_id:
                continue
            edge = grouped[(consumer_id, provider_id)]
            edge["dependent"].add(_identifier(issue))
            edge["prerequisite"].add(_identifier(dependency))

    return tuple(
        ContainerDependencyEdge(
            consumer=consumer,
            provider=provider,
            dependent_tasks=tuple(sorted(values["dependent"])),
            prerequisite_tasks=tuple(sorted(values["prerequisite"])),
        )
        for (consumer, provider), values in sorted(grouped.items())
    )


def build_container_dependency_graph(
    issues: Iterable[Issue],
    *,
    include_hard_start: bool = False,
) -> dict[str, tuple[str, ...]]:
    """Return ``consumer -> provider`` adjacency for the container graph."""

    adjacency: dict[str, set[str]] = defaultdict(set)
    for edge in container_dependency_edges(
        issues,
        include_hard_start=include_hard_start,
    ):
        adjacency[edge.consumer].add(edge.provider)
        adjacency.setdefault(edge.provider, set())
    return {
        container: tuple(sorted(dependencies))
        for container, dependencies in sorted(adjacency.items())
    }


def _cycle_path(
    start: str,
    adjacency: Mapping[str, set[str]],
    component: set[str],
) -> tuple[str, ...] | None:
    """Return the shortest deterministic closed path within one component."""

    frontier: list[tuple[str, tuple[str, ...]]] = [(start, (start,))]
    while frontier:
        node, path = frontier.pop(0)
        for neighbor in sorted(adjacency.get(node, set())):
            if neighbor not in component:
                continue
            if neighbor == start and len(path) > 1:
                return (*path, start)
            if neighbor not in path:
                frontier.append((neighbor, (*path, neighbor)))
    return None


def _strongly_connected_components(
    adjacency: Mapping[str, set[str]],
) -> list[set[str]]:
    """Return SCCs in deterministic order without a third-party graph lib."""

    index = 0
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[set[str]] = []

    def visit(node: str) -> None:
        nonlocal index
        indices[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)
        for neighbor in sorted(adjacency.get(node, set())):
            if neighbor not in indices:
                visit(neighbor)
                lowlinks[node] = min(lowlinks[node], lowlinks[neighbor])
            elif neighbor in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[neighbor])
        if lowlinks[node] != indices[node]:
            return
        component: set[str] = set()
        while True:
            member = stack.pop()
            on_stack.remove(member)
            component.add(member)
            if member == node:
                break
        components.append(component)

    for node in sorted(adjacency):
        if node not in indices:
            visit(node)
    return sorted(components, key=lambda component: tuple(sorted(component)))


def _authoritative_ancestor(
    path: tuple[str, ...],
    index: Mapping[str, Issue],
) -> str | None:
    """Return a common parent epic, if one authoritatively owns the cycle."""

    chains: list[list[str]] = []
    for container_id in path[:-1]:
        current = index.get(container_id)
        chain: list[str] = []
        seen: set[str] = set()
        while current is not None:
            parent_id = str(current.parent_id or "").strip()
            if not parent_id or parent_id in seen:
                break
            seen.add(parent_id)
            parent = index.get(parent_id)
            if parent is None:
                break
            chain.append(_identifier(parent))
            current = parent
        chains.append(chain)
    if not chains:
        return None
    common = set(chains[0]).intersection(*chains[1:])
    if not common:
        return None
    # The first common ancestor on the first deterministic chain is the
    # nearest shared authoritative container.
    return next((candidate for candidate in chains[0] if candidate in common), None)


def find_container_dependency_cycles(
    issues: Iterable[Issue],
    *,
    ready_task_ids: Iterable[str] = (),
    include_hard_start: bool = False,
) -> tuple[ContainerDependencyCycle, ...]:
    """Find all container cycles in a project snapshot.

    Results are stable across restarts and are split by strongly connected
    component so an unrelated integration group can continue independently.
    """

    snapshot = tuple(issues)
    index, aliases_by_identifier, epic_ids = _container_resolver(snapshot)
    edges = container_dependency_edges(
        snapshot,
        include_hard_start=include_hard_start,
    )
    adjacency: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        adjacency[edge.consumer].add(edge.provider)
        adjacency.setdefault(edge.provider, set())
    ready_aliases = {str(value).strip() for value in ready_task_ids if str(value).strip()}
    ready_aliases = {
        aliases_by_identifier.get(value, value) for value in ready_aliases
    }
    issue_containers: dict[str, str] = {}
    for issue in snapshot:
        container = container_for_issue(issue, index, epic_ids)
        if container is not None:
            issue_containers[_identifier(issue)] = _identifier(container)

    by_pair: dict[tuple[str, str], ContainerDependencyEdge] = {
        (edge.consumer, edge.provider): edge for edge in edges
    }
    cycles: list[ContainerDependencyCycle] = []
    for component in _strongly_connected_components(adjacency):
        if len(component) == 1:
            node = next(iter(component))
            if node not in adjacency.get(node, set()):
                continue
        start = min(component)
        path = _cycle_path(start, adjacency, component)
        if path is None:
            continue
        cycle_edges = tuple(
            by_pair[(consumer, provider)]
            for consumer, provider in zip(path, path[1:])
            if (consumer, provider) in by_pair
        )
        affected = tuple(
            sorted(
                identifier
                for identifier, container in issue_containers.items()
                if container in component
            )
        )
        affected_ready = tuple(
            identifier for identifier in affected if identifier in ready_aliases
        )
        prerequisite_shas: dict[str, str] = {}
        for issue in snapshot:
            identifier = _identifier(issue)
            if identifier not in affected:
                continue
            record = getattr(issue, "integration", None)
            sha = str(getattr(record, "integrated_sha", "") or "").strip()
            if sha and is_terminal_status(issue.state):
                prerequisite_shas[identifier] = sha
        cycles.append(
            ContainerDependencyCycle(
                path=path,
                edges=cycle_edges,
                affected_tasks=affected,
                affected_ready_tasks=affected_ready,
                prerequisite_shas=tuple(sorted(prerequisite_shas.items())),
                authoritative_container=_authoritative_ancestor(path, index),
            )
        )
    return tuple(cycles)


def container_dependency_cycle_for_new_edge(
    issues: Sequence[Issue],
    blocked_identifier: str,
    blocker_identifier: str,
    *,
    include_hard_start: bool = False,
) -> ContainerDependencyCycle | None:
    """Return the first container cycle created by a proposed task edge."""

    snapshot = tuple(issues)
    index, _aliases_by_identifier, epic_ids = _container_resolver(snapshot)
    blocked = index.get(blocked_identifier) or index.get(str(blocked_identifier).strip())
    blocker = index.get(blocker_identifier) or index.get(str(blocker_identifier).strip())
    if blocked is None or blocker is None or not _same_project(blocked, blocker):
        return None
    consumer = container_for_issue(blocked, index, epic_ids)
    provider = container_for_issue(blocker, index, epic_ids)
    if (
        consumer is None
        or provider is None
        or _identifier(consumer) == _identifier(provider)
        or is_terminal_status(consumer.state)
        or is_terminal_status(provider.state)
    ):
        return None

    existing = list(container_dependency_edges(
        snapshot,
        include_hard_start=include_hard_start,
    ))
    consumer_id = _identifier(consumer)
    provider_id = _identifier(provider)
    pair = (consumer_id, provider_id)
    edge = next((item for item in existing if (item.consumer, item.provider) == pair), None)
    if edge is None:
        existing.append(
            ContainerDependencyEdge(
                consumer=consumer_id,
                provider=provider_id,
                dependent_tasks=(_identifier(blocked),),
                prerequisite_tasks=(_identifier(blocker),),
            )
        )
    else:
        existing[existing.index(edge)] = ContainerDependencyEdge(
            consumer=edge.consumer,
            provider=edge.provider,
            dependent_tasks=tuple(sorted(set(edge.dependent_tasks) | {_identifier(blocked)})),
            prerequisite_tasks=tuple(sorted(set(edge.prerequisite_tasks) | {_identifier(blocker)})),
        )

    adjacency: dict[str, set[str]] = defaultdict(set)
    for item in existing:
        adjacency[item.consumer].add(item.provider)
        adjacency.setdefault(item.provider, set())
    for component in _strongly_connected_components(adjacency):
        if consumer_id not in component or provider_id not in component:
            continue
        if len(component) == 1:
            continue
        path = _cycle_path(consumer_id, adjacency, component)
        if path is None or provider_id not in path:
            continue
        edge_by_pair = {(item.consumer, item.provider): item for item in existing}
        cycle_edges = tuple(
            edge_by_pair[(left, right)]
            for left, right in zip(path, path[1:])
        )
        ready = [
            _identifier(issue)
            for issue in snapshot
            if _identifier(issue)
            and canonicalize_status(issue.state) == READY_TO_INTEGRATE
            and (
                container_for_issue(issue, index, epic_ids) is not None
                and _identifier(container_for_issue(issue, index, epic_ids)) in component
            )
        ]
        affected = tuple(
            sorted(
                _identifier(issue)
                for issue in snapshot
                if _identifier(issue)
                and (
                    container_for_issue(issue, index, epic_ids) is not None
                    and _identifier(container_for_issue(issue, index, epic_ids))
                    in component
                )
            )
        )
        prerequisite_shas = {
            _identifier(issue): str(
                getattr(getattr(issue, "integration", None), "integrated_sha", "")
                or ""
            ).strip()
            for issue in snapshot
            if _identifier(issue)
            and is_terminal_status(issue.state)
            and _identifier(issue) in affected
            and str(
                getattr(getattr(issue, "integration", None), "integrated_sha", "")
                or ""
            ).strip()
        }
        return ContainerDependencyCycle(
            path=path,
            edges=cycle_edges,
            affected_tasks=affected,
            affected_ready_tasks=tuple(sorted(ready)),
            prerequisite_shas=tuple(sorted(prerequisite_shas.items())),
            authoritative_container=_authoritative_ancestor(path, index),
        )
    return None


# Friendly aliases used by callers that describe this as reachability rather
# than container dependency analysis.
build_container_reachability_graph = build_container_dependency_graph
find_container_reachability_cycles = find_container_dependency_cycles
container_reachability_cycle_for_new_edge = container_dependency_cycle_for_new_edge


__all__ = [
    "ContainerDependencyCycle",
    "ContainerDependencyEdge",
    "build_container_dependency_graph",
    "build_container_reachability_graph",
    "container_dependency_cycle_for_new_edge",
    "container_dependency_edges",
    "container_for_issue",
    "container_reachability_cycle_for_new_edge",
    "find_container_dependency_cycles",
    "find_container_reachability_cycles",
]
