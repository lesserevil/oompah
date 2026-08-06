"""Immutable executor facts consumed by integration queue diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from oompah.container_dependency_graph import ContainerDependencyCycle
from oompah.dependency_graph import issue_index
from oompah.integration_queue import IntegrationQueueItem
from oompah.models import Issue
from oompah.statuses import is_terminal_status


@dataclass(frozen=True)
class IntegrationDependencyProjection:
    """One queue row's dependency result from an executor-owned snapshot."""

    project_id: str
    epic_id: str
    task_id: str
    task_branch: str
    head_sha: str
    base_branch: str | None
    base_sha: str | None
    candidate_head_sha: str | None
    candidate_base_sha: str | None
    dependencies: tuple[str, ...]
    unresolved: tuple[str, ...]
    unreachable: tuple[str, ...]
    container_cycle: ContainerDependencyCycle | None = None
    dependency_authoritative: bool = True

    def matches(self, item: IntegrationQueueItem) -> bool:
        """Return whether these facts belong to the exact durable row."""

        return (
            self.project_id,
            self.epic_id,
            self.task_id,
            self.task_branch,
            self.head_sha,
            self.base_branch,
            self.base_sha,
            self.candidate_head_sha,
            self.candidate_base_sha,
        ) == (
            item.project_id,
            item.epic_id,
            item.task_id,
            item.task_branch,
            item.head_sha,
            item.base_branch,
            item.base_sha,
            item.candidate_head_sha,
            item.candidate_base_sha,
        )


def build_integration_dependency_projections(
    issues: Sequence[Issue],
    queue_items: Sequence[IntegrationQueueItem],
    dependency_map: Mapping[str, tuple[str, ...]],
    satisfied: set[str],
    *,
    container_cycles: Sequence[ContainerDependencyCycle] = (),
    dependency_authoritative: bool = True,
) -> tuple[IntegrationDependencyProjection, ...]:
    """Normalize claim and wait facts from one raw executor snapshot.

    Cycle reconciliation can publish cycle evidence for a cancelled row before
    that row receives a target reachability scan.  Such callers set
    ``dependency_authoritative=False`` so diagnostics retain the cycle without
    presenting the empty ``satisfied`` input as an unreachable dependency.
    """

    index = issue_index(issues)
    result: list[IntegrationDependencyProjection] = []
    for item in queue_items:
        issue = index.get(item.task_id)
        task_aliases = {
            str(value).strip()
            for value in (
                item.task_id,
                getattr(issue, "id", None),
                getattr(issue, "identifier", None),
            )
            if str(value or "").strip()
        }
        container_cycle = next(
            (
                cycle
                for cycle in container_cycles
                if task_aliases & set(cycle.affected_tasks)
            ),
            None,
        )
        dependencies = tuple(dependency_map.get(item.task_id, ()))
        unresolved: list[str] = []
        unreachable: list[str] = []
        if dependency_authoritative:
            for dependency in dependencies:
                blocker = index.get(dependency)
                if blocker is None or not is_terminal_status(blocker.state):
                    unresolved.append(dependency)
                elif dependency not in satisfied:
                    unreachable.append(dependency)
        result.append(
            IntegrationDependencyProjection(
                project_id=item.project_id,
                epic_id=item.epic_id,
                task_id=item.task_id,
                task_branch=item.task_branch,
                head_sha=item.head_sha,
                base_branch=item.base_branch,
                base_sha=item.base_sha,
                candidate_head_sha=item.candidate_head_sha,
                candidate_base_sha=item.candidate_base_sha,
                dependencies=dependencies,
                unresolved=tuple(unresolved),
                unreachable=tuple(unreachable),
                container_cycle=container_cycle,
                dependency_authoritative=dependency_authoritative,
            )
        )
    return tuple(result)
