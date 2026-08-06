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
    """Return the canonical finish-order projection used for integration.

    A container's dependencies on its descendants are lifecycle rollup edges,
    not delivery ordering. Dependencies are retained only when they point
    outside the source task/container that declared them; a leaf's explicit
    sibling prerequisite is therefore preserved while a container's direct
    child rollup is removed.
    """

    aliases: dict[str, str] = {}
    unique_issues: dict[str, Issue] = {}
    for candidate in issues_by_id.values():
        canonical = str(candidate.identifier or candidate.id or "").strip()
        if not canonical:
            continue
        unique_issues[canonical] = candidate
        for alias in issue_aliases(candidate):
            aliases[alias] = canonical

    issue_id = str(issue.identifier or issue.id or "").strip()
    if not issue_id:
        return ()

    def _canonical_ref(ref: BlockerRef) -> str:
        value = _ref_identifier(ref)
        return aliases.get(value, value)

    def _is_descendant(candidate: Issue, ancestor_id: str) -> bool:
        ancestor = unique_issues.get(ancestor_id)
        candidate_project = str(candidate.project_id or "").strip()
        ancestor_project = str(getattr(ancestor, "project_id", "") or "").strip()
        if (
            candidate_project
            and ancestor_project
            and candidate_project != ancestor_project
        ):
            return False
        current: Issue | None = candidate
        visited: set[str] = set()
        while current is not None:
            parent_alias = str(current.parent_id or "").strip()
            if not parent_alias:
                return False
            parent_id = aliases.get(parent_alias, parent_alias)
            if parent_id in visited:
                return False
            visited.add(parent_id)
            if parent_id == ancestor_id:
                return True
            current = issues_by_id.get(parent_alias) or unique_issues.get(parent_id)
        return False

    result: list[str] = []
    seen_dependencies: set[str] = set()
    seen_ancestors: set[str] = set()
    current: Issue | None = issue
    while current is not None:
        current_id = str(current.identifier or current.id or "").strip()
        for ref in current.blocked_by or []:
            dependency = _canonical_ref(ref)
            if not dependency or dependency == issue_id:
                continue
            dependency_issue = unique_issues.get(dependency)
            container_rollup = bool(
                dependency_issue is not None
                and (
                    dependency == current_id
                    or _is_descendant(dependency_issue, current_id)
                )
            )
            if container_rollup or dependency in seen_dependencies:
                continue
            seen_dependencies.add(dependency)
            result.append(dependency)
        parent_alias = str(current.parent_id or "").strip()
        if not parent_alias:
            break
        parent_id = aliases.get(parent_alias, parent_alias)
        if parent_id in seen_ancestors:
            break
        seen_ancestors.add(parent_id)
        current = issues_by_id.get(parent_alias) or unique_issues.get(parent_id)
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
