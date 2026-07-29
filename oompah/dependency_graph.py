"""Dependency-graph helpers shared by dispatch and ordered integration."""

from __future__ import annotations

from collections import deque
from typing import Iterable, Mapping, Sequence

from oompah.models import BlockerRef, Issue


def _ref_identifier(ref: BlockerRef) -> str:
    return str(ref.identifier or ref.id or "").strip()


def issue_aliases(issue: Issue) -> set[str]:
    return {
        str(value).strip()
        for value in (issue.id, issue.identifier)
        if str(value or "").strip()
    }


def issue_index(issues: Iterable[Issue]) -> dict[str, Issue]:
    result: dict[str, Issue] = {}
    for issue in issues:
        for alias in issue_aliases(issue):
            result[alias] = issue
    return result


def effective_dependencies(
    issue: Issue,
    issues_by_id: Mapping[str, Issue],
    *,
    hard_start: bool = False,
) -> tuple[str, ...]:
    """Return own plus inherited ancestor dependencies without duplicates."""

    result: list[str] = []
    seen_dependencies: set[str] = set()
    seen_ancestors: set[str] = set()
    current: Issue | None = issue
    while current is not None:
        refs = (
            current.start_blocked_by
            if hard_start
            else current.blocked_by
        )
        for ref in refs or []:
            identifier = _ref_identifier(ref)
            if identifier and identifier not in seen_dependencies:
                seen_dependencies.add(identifier)
                result.append(identifier)
        parent_id = str(current.parent_id or "").strip()
        if not parent_id or parent_id in seen_ancestors:
            break
        seen_ancestors.add(parent_id)
        current = issues_by_id.get(parent_id)
    return tuple(result)


def combined_dependency_adjacency(
    issues: Sequence[Issue],
) -> tuple[dict[str, set[str]], dict[str, str]]:
    """Return canonical adjacency and an alias-to-canonical mapping."""

    aliases: dict[str, str] = {}
    adjacency: dict[str, set[str]] = {}
    for issue in issues:
        canonical = str(issue.identifier or issue.id or "").strip()
        if not canonical:
            continue
        adjacency.setdefault(canonical, set())
        for alias in issue_aliases(issue):
            aliases[alias] = canonical
    for issue in issues:
        canonical = str(issue.identifier or issue.id or "").strip()
        if not canonical:
            continue
        for ref in [*(issue.blocked_by or []), *(issue.start_blocked_by or [])]:
            identifier = _ref_identifier(ref)
            if identifier:
                adjacency[canonical].add(aliases.get(identifier, identifier))
    return adjacency, aliases


def dependency_cycle_for_new_edge(
    issues: Sequence[Issue],
    blocked_identifier: str,
    blocker_identifier: str,
) -> tuple[str, ...] | None:
    """Return an actionable cycle path if ``blocked -> blocker`` is invalid."""

    adjacency, aliases = combined_dependency_adjacency(issues)
    blocked = aliases.get(blocked_identifier, blocked_identifier)
    blocker = aliases.get(blocker_identifier, blocker_identifier)
    if blocked == blocker:
        return (blocked, blocked)
    adjacency.setdefault(blocked, set())
    adjacency.setdefault(blocker, set())

    # Adding blocked -> blocker creates a cycle iff blocker can already reach
    # blocked through either finish-order or hard-start edges.
    queue: deque[tuple[str, tuple[str, ...]]] = deque([(blocker, (blocker,))])
    visited = {blocker}
    while queue:
        node, path = queue.popleft()
        for dependency in sorted(adjacency.get(node, ())):
            next_path = (*path, dependency)
            if dependency == blocked:
                return (blocked, *next_path)
            if dependency not in visited:
                visited.add(dependency)
                queue.append((dependency, next_path))
    return None

