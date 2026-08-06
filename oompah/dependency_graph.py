"""Dependency-graph helpers shared by dispatch and ordered integration."""

from __future__ import annotations

from collections import deque
from typing import Iterable, Mapping, Sequence

from oompah.models import BlockerRef, Issue
from oompah.statuses import ARCHIVED, MERGED, canonicalize_status


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


def dependency_parent_has_landed(
    issue: Issue,
    issues_by_id: Mapping[str, Issue],
) -> bool:
    """Return whether a dependency's parent epic has landed externally."""

    parent_id = str(issue.parent_id or "").strip()
    if not parent_id:
        return False
    parent = issues_by_id.get(parent_id)
    return (
        parent is not None
        and canonicalize_status(parent.state) in {MERGED, ARCHIVED}
    )


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


def integration_dependencies(
    issue: Issue,
    issues_by_id: Mapping[str, Issue],
) -> tuple[str, ...]:
    """Return finish dependencies for ordered integration, excluding container rollup edges.

    Implicit parent->child rollup edges occur when a parent task has finish
    dependencies on its children for rollup. These edges must be excluded from
    integration queue dependencies to prevent deadlock: otherwise a child
    would wait on itself (inherited from parent) and its siblings.

    Preserves:
    - Externally inherited finish-order prerequisites from ancestors
    - Explicitly declared sibling dependencies
    - Ancestor dependencies outside the current delivery container

    Excludes:
    - The immediate parent task
    - Siblings whose only path to this task is through inherited parent rollup
    """

    # Get all effective dependencies (includes inherited from ancestors)
    all_deps = effective_dependencies(issue, issues_by_id)
    if not all_deps:
        return ()

    # Build set of container rollup dependencies to filter out
    excluded: set[str] = set()

    # Exclude the immediate parent if present
    parent_id = str(issue.parent_id or "").strip()
    if parent_id:
        excluded.add(parent_id)
        parent = issues_by_id.get(parent_id)

        # Find all siblings (other children of the same parent)
        if parent is not None:
            # Check if parent has rollup dependencies on its children
            parent_finish_deps = set(
                effective_dependencies(parent, issues_by_id, hard_start=False)
            )
            # Find other children of parent
            for candidate_id, candidate in issues_by_id.items():
                parent_of_candidate = str(
                    candidate.parent_id or ""
                ).strip()
                if (
                    parent_of_candidate == parent_id
                    and candidate_id != str(issue.identifier or issue.id or "").strip()
                ):
                    # This is a sibling.
                    # Only exclude if it's ONLY in our dependencies because
                    # it's in parent's rollup deps (not explicitly on this task)
                    task_id = str(issue.identifier or issue.id or "").strip()
                    task_explicit_deps = set(
                        _ref_identifier(ref)
                        for ref in (issue.blocked_by or [])
                    )
                    is_explicit_on_task = candidate_id in task_explicit_deps
                    is_in_parent_rollup = candidate_id in parent_finish_deps

                    # Only exclude if: not explicit on task AND in parent rollup
                    if not is_explicit_on_task and is_in_parent_rollup:
                        excluded.add(candidate_id)

    # Filter out excluded dependencies
    result = [
        dep for dep in all_deps if dep not in excluded
    ]
    return tuple(result)


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
