"""Release-addendum approval logic for POST /api/v1/issues/{identifier}/release-addendums.

This module implements the core approval flow from section 6 of
plans/release-branch-addendums.md:

1. Validate that the source task/epic is ``Merged`` on the project's default
   branch.
2. Deduplicate and validate target branches against the fresh
   :class:`~oompah.release_branch_catalog.ReleaseBranchCatalog`.
3. Resolve the ordered commit snapshot from the source task's merged PR.
4. Under a per-source-task :class:`asyncio.Lock`, atomically create only the
   missing ``open`` addendums and write the updated list to the tracker.
5. Publish one ``release_addendum_ready`` event per newly-created row.
6. Return the full updated addendum list with per-row ``queued`` flags.

Idempotency and concurrency guarantees
---------------------------------------

- A concurrent pair of requests for the same source identifier is serialised
  by ``_get_source_lock(identifier)``.
- The :class:`~oompah.release_addendum_schema.AddendumRepository` enforces
  *at most one active addendum per target branch*, so even if two callers
  race, the second will find the row already written and skip creation.
- Commit resolution is performed **before** the lock is acquired so that
  validation I/O does not hold the lock.  Under the lock only a re-check
  and the atomic write occur.

Event-failure recovery
-----------------------

If event publication fails after persistence the row remains ``open`` and
the function returns ``queued=False`` for that addendum.  The periodic
reconciler (OOMPAH-177) must pick it up.  The approval is *never* rolled
back because an in-memory wake-up failed.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from oompah.release_addendum_schema import (
    AddendumRepository,
    AddendumStatus,
    ReleaseAddendum,
    make_addendum_id,
    make_work_branch,
    make_worktree_key,
)

if TYPE_CHECKING:
    from oompah.release_branch_catalog import CatalogResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Per-source asyncio locks (module singleton)
# ---------------------------------------------------------------------------

#: Keyed by source task identifier; lazily created in the event loop.
_source_locks: dict[str, asyncio.Lock] = {}


def _get_source_lock(identifier: str) -> asyncio.Lock:
    """Return the per-source :class:`asyncio.Lock` for *identifier*.

    The lock is created lazily the first time it is requested.  Since
    FastAPI uses a single event loop, this is safe to call from any
    ``async`` request handler.

    Args:
        identifier: Source task or epic identifier (e.g. ``"FOO-10"``).

    Returns:
        The :class:`asyncio.Lock` for *identifier*.
    """
    if identifier not in _source_locks:
        _source_locks[identifier] = asyncio.Lock()
    return _source_locks[identifier]


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class ApprovalError(Exception):
    """Base class for errors raised during release-addendum approval."""


class SourceNotMergedError(ApprovalError):
    """Raised when the source task is not in ``Merged`` state on the default branch."""


class InvalidTargetBranchError(ApprovalError):
    """Raised when one or more target branches fail validation.

    Attributes:
        errors: List of human-readable validation error messages, one per
            invalid branch.
    """

    def __init__(self, errors: list[str]) -> None:
        self.errors = list(errors)
        super().__init__("; ".join(errors))


class CommitResolutionError(ApprovalError):
    """Raised when commits cannot be resolved for the source task."""


# ---------------------------------------------------------------------------
# Return value
# ---------------------------------------------------------------------------


@dataclass
class ApprovalResult:
    """Result returned by :func:`approve_release_addendums`.

    Attributes:
        addendums: Full updated addendum list for the source task (after
            creation of new rows).
        newly_created_ids: List of addendum IDs that were created in this
            call.  Empty when all requested branches already had active
            addendums (idempotent duplicate).
        event_failures: List of addendum IDs for which event publication
            failed.  These rows are durably ``open`` but were not
            immediately woken up.
    """

    addendums: list[ReleaseAddendum] = field(default_factory=list)
    newly_created_ids: list[str] = field(default_factory=list)
    event_failures: list[str] = field(default_factory=list)

    @property
    def queued(self) -> bool:
        """Return True when all newly-created addendums were successfully enqueued."""
        if not self.newly_created_ids:
            # Idempotent — nothing new was created
            return True
        return len(self.event_failures) == 0


# ---------------------------------------------------------------------------
# Commit resolution
# ---------------------------------------------------------------------------


def resolve_addendum_commits(
    source_task: Any,
    project: Any,
    *,
    scm: Any | None = None,
    repo: str | None = None,
) -> list[str]:
    """Resolve the ordered commit SHAs for the source task's merge to the default branch.

    Resolution order (first non-empty result wins):

    1. **SCM PR lookup** — find the merged PR whose head branch matches
       ``source_task.branch_name`` and fetch its commits via the SCM API.
    2. **Git rev-list** — run
       ``git rev-list --reverse origin/<branch> ^origin/<default_branch>``
       in the project's local repository checkout.

    Args:
        source_task: An :class:`~oompah.models.Issue` whose ``branch_name``
            identifies the source branch.  Falls back to
            ``source_task.identifier`` when ``branch_name`` is ``None``.
        project: A :class:`~oompah.models.Project` instance providing
            ``default_branch`` and ``repo_path``.
        scm: Optional SCM provider for PR-based commit lookup.
        repo: Repository slug (e.g. ``"org/repo"``).  Required alongside
            *scm*.

    Returns:
        Non-empty ordered list of full-length commit SHAs (oldest first).

    Raises:
        :exc:`CommitResolutionError`: When no commits can be resolved via
            either strategy.
    """
    from oompah.release_pick_commit_resolver import (
        _resolve_via_git,
        _resolve_via_scm,
    )

    source_identifier = source_task.identifier
    default_branch: str = getattr(project, "default_branch", "main") or "main"
    repo_path: str | None = getattr(project, "repo_path", None) or None
    branch: str = source_task.branch_name or source_task.identifier

    # Strategy 1: SCM PR lookup
    if scm is not None and repo:
        commits = _resolve_via_scm(scm, repo, branch, source_identifier, default_branch)
        if commits:
            return commits

    # Strategy 2: git rev-list fallback
    if repo_path:
        commits = _resolve_via_git(
            repo_path, branch, default_branch, source_identifier, default_branch
        )
        if commits:
            return commits

    raise CommitResolutionError(
        f"Cannot resolve commits for {source_identifier!r}: "
        f"no merged PR found and git rev-list returned no unique commits "
        f"(branch={branch!r}, default_branch={default_branch!r})"
    )


# ---------------------------------------------------------------------------
# Epic commit resolution
# ---------------------------------------------------------------------------


def resolve_epic_addendum_commits(
    epic: Any,
    tracker: Any,
    project: Any,
    *,
    scm: Any | None = None,
    repo: str | None = None,
) -> tuple[list[str], list[str]]:
    """Resolve commits and child IDs for an epic's addendum snapshot.

    The commit snapshot for an epic addendum is the ordered, deduplicated
    union of commits from all descendant tasks currently in the ``Merged``
    state on the project's default branch, in the order they were resolved.

    Only descendants that are ``Merged`` at the time of approval are included.
    Descendants that merge later are NOT added automatically — they require a
    separate approval.

    Args:
        epic: An :class:`~oompah.models.Issue` whose ``issue_type`` is
            ``"epic"``.  Its ``identifier`` is used to fetch children.
        tracker: Tracker instance with ``fetch_children`` support.
        project: A :class:`~oompah.models.Project` providing
            ``default_branch`` and ``repo_path``.
        scm: Optional SCM provider for PR-based commit lookup.
        repo: Repository slug (e.g. ``"org/repo"``).  Required alongside
            *scm*.

    Returns:
        Tuple of ``(commits, included_child_ids)`` where *commits* is the
        ordered, deduplicated list of full-length commit SHAs (oldest first)
        and *included_child_ids* is the list of child identifiers whose
        commits were included, in the order they were processed.

    Raises:
        :exc:`CommitResolutionError`: When no merged descendants are found or
            all per-child commit resolutions fail.
    """
    from oompah.statuses import canonicalize_status, MERGED

    try:
        children = tracker.fetch_children(epic.identifier) or []
    except Exception as exc:
        raise CommitResolutionError(
            f"Failed to fetch children of epic {epic.identifier!r}: {exc}"
        ) from exc

    merged_children = [
        c for c in children
        if canonicalize_status(c.state or "") == MERGED
    ]

    if not merged_children:
        raise CommitResolutionError(
            f"Epic {epic.identifier!r} has no Merged descendants; "
            "cannot create a release addendum snapshot with zero commits"
        )

    # Collect commits in child order, deduplicate by SHA
    seen_shas: set[str] = set()
    all_commits: list[str] = []
    included_child_ids: list[str] = []
    resolution_errors: list[str] = []

    for child in merged_children:
        try:
            child_commits = resolve_addendum_commits(
                child, project, scm=scm, repo=repo
            )
        except CommitResolutionError as exc:
            logger.debug(
                "resolve_epic_addendum_commits: could not resolve commits for "
                "child %s of epic %s: %s",
                child.identifier,
                epic.identifier,
                exc,
            )
            resolution_errors.append(f"{child.identifier}: {exc}")
            continue

        new_commits = [sha for sha in child_commits if sha not in seen_shas]
        if new_commits:
            seen_shas.update(new_commits)
            all_commits.extend(new_commits)
            included_child_ids.append(child.identifier)
        else:
            # All commits were already included by a previous child; still
            # record the child as included since its work is in the snapshot
            included_child_ids.append(child.identifier)

    if not all_commits:
        errors_detail = "; ".join(resolution_errors) if resolution_errors else "unknown"
        raise CommitResolutionError(
            f"Epic {epic.identifier!r}: could not resolve any commits from its "
            f"merged descendants. Per-child errors: {errors_detail}"
        )

    return all_commits, included_child_ids


# ---------------------------------------------------------------------------
# Target-branch validation
# ---------------------------------------------------------------------------


def validate_target_branches(
    target_branches: list[str],
    catalog_result: "CatalogResult",
    default_branch: str,
) -> tuple[list[str], list[str]]:
    """Validate and deduplicate *target_branches* against *catalog_result*.

    Validation rules (section 6 of plans/release-branch-addendums.md):

    - Duplicates in the request are silently deduplicated (first occurrence
      kept); the deduplicated list is returned.
    - Each branch must not be the project's ``default_branch``.
    - Each branch must appear in the catalog with ``available=True``.
    - Each branch must not have ``stale=True`` (stale-only candidates are
      rejected so that work is never queued for branches without live remote
      confirmation).

    Args:
        target_branches: Raw list from the request body.
        catalog_result: Fresh catalog from
            :class:`~oompah.release_branch_catalog.ReleaseBranchCatalog`.
        default_branch: Project's default branch name.

    Returns:
        Tuple of ``(valid_branches, errors)`` where *valid_branches* is the
        deduplicated, validated list and *errors* is a list of human-readable
        error messages.  When *errors* is non-empty the caller should reject
        the whole request.
    """
    seen: set[str] = set()
    deduped: list[str] = []
    for b in target_branches:
        if b not in seen:
            seen.add(b)
            deduped.append(b)

    # Build a lookup: name → ReleaseBranch
    catalog_by_name = {rb.name: rb for rb in catalog_result.branches}

    errors: list[str] = []
    for branch in deduped:
        if branch == default_branch:
            errors.append(
                f"Target branch {branch!r} is the project default branch and cannot be a release target"
            )
            continue

        catalog_entry = catalog_by_name.get(branch)
        if catalog_entry is None:
            errors.append(
                f"Target branch {branch!r} is not a configured supported release branch"
            )
        elif not catalog_entry.available:
            errors.append(
                f"Target branch {branch!r} is not currently available (deleted or historical)"
            )
        elif catalog_entry.stale:
            errors.append(
                f"Target branch {branch!r} is only known via stale discovery; "
                "retry when live branch discovery succeeds"
            )

    return deduped, errors


# ---------------------------------------------------------------------------
# Core approval function
# ---------------------------------------------------------------------------


async def approve_release_addendums(
    tracker: Any,
    source_task: Any,
    project: Any,
    target_branches: list[str],
    commits: list[str],
    *,
    included_child_ids: list[str] | None = None,
    event_bus: Any | None = None,
) -> ApprovalResult:
    """Atomically create open release addendums for each missing target branch.

    This function acquires the per-source-task lock before reading and
    writing, ensuring that concurrent requests for the same source
    identifier are serialised and cannot create duplicate rows.

    Args:
        tracker: Tracker instance with ``get_metadata`` / ``set_metadata_field``.
        source_task: Source :class:`~oompah.models.Issue` (already validated
            as ``Merged`` on default branch).
        project: Project providing ``default_branch`` and ``id``.
        target_branches: Deduplicated, validated list of target branch names.
        commits: Pre-resolved, non-empty list of commit SHAs to snapshot.
        included_child_ids: For epic addendums, the ordered list of descendant
            task identifiers whose commits are in *commits*.  ``None`` or
            empty for per-task addendums.
        event_bus: Optional :class:`~oompah.events.EventBus` for publishing
            ``release_addendum_ready`` events.

    Returns:
        :class:`ApprovalResult` with the full updated addendum list, newly
        created IDs, and any event-publication failures.
    """
    identifier = source_task.identifier
    source_branch: str = getattr(project, "default_branch", "main") or "main"
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    lock = _get_source_lock(identifier)

    async with lock:
        repo_obj = AddendumRepository(tracker)
        existing = repo_obj.read(identifier)

        newly_created_ids: list[str] = []
        updated = list(existing)

        for target_branch in target_branches:
            # Idempotency: skip if an active addendum already exists for this branch
            active_for_branch = [
                a for a in updated
                if a.target_branch == target_branch and a.status.is_active
            ]
            if active_for_branch:
                logger.debug(
                    "approve_release_addendums: %s → %s already has an active addendum, skipping",
                    identifier,
                    target_branch,
                )
                continue

            addendum_id = make_addendum_id(identifier, target_branch)
            addendum = ReleaseAddendum(
                id=addendum_id,
                source_branch=source_branch,
                target_branch=target_branch,
                status=AddendumStatus.OPEN,
                commits=list(commits),
                work_branch=make_work_branch(identifier, target_branch),
                worktree_key=make_worktree_key(identifier, target_branch),
                queued_at=now,
                included_child_ids=list(included_child_ids) if included_child_ids else [],
            )
            updated.append(addendum)
            newly_created_ids.append(addendum_id)

        # Write only if new rows were created
        if newly_created_ids:
            repo_obj.write(identifier, updated)
            logger.info(
                "approve_release_addendums: %s: created %d addendum(s): %s",
                identifier,
                len(newly_created_ids),
                newly_created_ids,
            )

    # Publish events outside the lock (failure must not roll back persistence)
    event_failures: list[str] = []
    if event_bus is not None and newly_created_ids:
        from oompah.events import EventType

        for addendum_id in newly_created_ids:
            try:
                event_bus.emit(
                    EventType.RELEASE_ADDENDUM_READY,
                    {
                        "addendum_id": addendum_id,
                        "source_identifier": identifier,
                        "project_id": project.id,
                    },
                )
                logger.debug(
                    "approve_release_addendums: emitted release_addendum_ready for %s",
                    addendum_id,
                )
            except Exception as exc:
                logger.warning(
                    "approve_release_addendums: event publication failed for %s: %s",
                    addendum_id,
                    exc,
                )
                event_failures.append(addendum_id)

    return ApprovalResult(
        addendums=updated,
        newly_created_ids=newly_created_ids,
        event_failures=event_failures,
    )
