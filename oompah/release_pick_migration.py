"""Release-pick to release-addendum migration (OOMPAH-183).

One-time idempotent migration that converts ``oompah.backports`` entries on
source tasks into ``oompah.release_addendums`` entries and archives the
historical child backport tasks with an ``oompah``-authored redirect comment.

Status mapping (section 9 of plans/release-branch-addendums.md)
----------------------------------------------------------------

+------------------------------+-------------------+
| Legacy ReleasePick status    | New AddendumStatus|
+==============================+===================+
| waiting                      | open              |
| task_created                 | open              |
| cherry_picking               | open              |
| pr_open                      | in_review         |
| conflict                     | blocked           |
| needs_human                  | blocked           |
| merged                       | merged            |
| archived                     | archived          |
| skipped                      | archived          |
+------------------------------+-------------------+

Idempotency
-----------

A migration run is safe to repeat any number of times.  Before creating an
addendum for a ``(source_identifier, target_branch)`` pair the function
checks whether any addendum already exists for that branch on the source
task.  If one already exists it is left unchanged; the entry is counted as
``already_migrated``.  This covers partial first runs, process restarts, and
re-runs after a code update.

Commit handling
---------------

Legacy entries may lack a ``commits`` list (e.g. ``waiting`` entries that
were never processed).  Because the new schema requires a non-empty commit
snapshot the migration uses a sentinel value
``["migration-pending"]`` for non-terminal entries that have no commits,
and ``["migration-no-commits"]`` for terminal entries.  This keeps the
data structure valid while clearly flagging records that did not have
evidence at migration time.

Child-task archival
-------------------

When a legacy ``BackportEntry`` has a ``task_id``, the referenced child
task is archived (if not already archived) and receives an ``oompah``-authored
comment directing readers to the source task addendum.
"""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from oompah.release_addendum_schema import (
    AddendumStatus,
    ReleaseAddendum,
    make_addendum_id,
    make_work_branch,
    make_worktree_key,
    parse_addendums,
    addendums_to_raw,
)
from oompah.release_pick_schema import (
    ReleasePick,
    parse_backport_of,
    parse_backports,
)
from oompah.statuses import ARCHIVED

if TYPE_CHECKING:
    from oompah.models import Issue
    from oompah.tracker import TrackerProtocol

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Status mapping
# ---------------------------------------------------------------------------

#: Maps each legacy :class:`~oompah.release_pick_schema.ReleasePick` status
#: to the new :class:`~oompah.release_addendum_schema.AddendumStatus`.
LEGACY_STATUS_MAP: dict[ReleasePick, AddendumStatus] = {
    ReleasePick.WAITING: AddendumStatus.OPEN,
    ReleasePick.TASK_CREATED: AddendumStatus.OPEN,
    ReleasePick.CHERRY_PICKING: AddendumStatus.OPEN,
    ReleasePick.PR_OPEN: AddendumStatus.IN_REVIEW,
    ReleasePick.CONFLICT: AddendumStatus.BLOCKED,
    ReleasePick.NEEDS_HUMAN: AddendumStatus.BLOCKED,
    ReleasePick.MERGED: AddendumStatus.MERGED,
    ReleasePick.ARCHIVED: AddendumStatus.ARCHIVED,
    ReleasePick.SKIPPED: AddendumStatus.ARCHIVED,
}

#: Sentinel SHA used when a non-terminal legacy entry has no commit evidence.
MIGRATION_PENDING_COMMIT = "migration-pending"

#: Sentinel SHA used when a terminal legacy entry has no commit evidence.
MIGRATION_NO_COMMITS = "migration-no-commits"


def map_release_pick_status(old_status: ReleasePick) -> AddendumStatus:
    """Map a legacy :class:`ReleasePick` status to the new :class:`AddendumStatus`.

    Args:
        old_status: Legacy release-pick status.

    Returns:
        Corresponding :class:`~oompah.release_addendum_schema.AddendumStatus`.

    Raises:
        ValueError: When *old_status* has no mapping in :data:`LEGACY_STATUS_MAP`.
            This should never occur for well-formed data because every enum
            value is mapped.
    """
    result = LEGACY_STATUS_MAP.get(old_status)
    if result is None:
        raise ValueError(
            f"No status mapping for ReleasePick.{old_status.name!r}; "
            f"known statuses: {list(LEGACY_STATUS_MAP)}"
        )
    return result


# ---------------------------------------------------------------------------
# Migration result
# ---------------------------------------------------------------------------


@dataclass
class MigrationResult:
    """Summary of one migration pass.

    Attributes:
        scanned: Number of source tasks that had ``oompah.backports`` metadata
            and were examined.
        migrated: Number of backport entries successfully converted to addendums.
        already_migrated: Number of entries skipped because an addendum for
            that target branch already existed.
        children_archived: Number of child backport tasks successfully archived.
        errors: Number of non-fatal errors (bad metadata, write failures, etc.).
    """

    scanned: int = 0
    migrated: int = 0
    already_migrated: int = 0
    children_archived: int = 0
    errors: int = 0

    @property
    def changed(self) -> bool:
        """Return True when any addendums were migrated or child tasks archived."""
        return self.migrated > 0 or self.children_archived > 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _make_redirect_comment(source_identifier: str, target_branch: str) -> str:
    """Return the redirect comment text for an archived child backport task.

    Args:
        source_identifier: Identifier of the source task that owns the addendum.
        target_branch: Target release branch of the addendum.

    Returns:
        Comment text directing readers to the source task addendum.
    """
    return (
        f"This child backport task has been retired as part of the migration to "
        f"release addendums (OOMPAH-183). The equivalent release addendum is "
        f"attached to source task {source_identifier!r} (target branch: "
        f"{target_branch!r}). Please refer to that task for the current "
        f"delivery status."
    )


def build_addendum_from_entry(
    source_identifier: str,
    entry: "Any",  # BackportEntry
    default_branch: str,
    queued_at: str,
) -> ReleaseAddendum:
    """Convert one :class:`~oompah.release_pick_schema.BackportEntry` to a
    :class:`~oompah.release_addendum_schema.ReleaseAddendum`.

    Commits are taken from the entry when available; otherwise a sentinel
    value is used so the schema invariant of a non-empty list is satisfied.
    The ``pr_url`` is preserved as execution evidence when present.

    Args:
        source_identifier: Identifier of the source task.
        entry: Legacy :class:`~oompah.release_pick_schema.BackportEntry`.
        default_branch: Project default branch at migration time (used as
            ``source_branch``).
        queued_at: ISO-8601 UTC timestamp to record as ``queued_at``.

    Returns:
        New :class:`~oompah.release_addendum_schema.ReleaseAddendum`.
    """
    new_status = map_release_pick_status(entry.status)

    # Preserve available commits; use sentinel when absent.
    if entry.commits:
        commits = list(entry.commits)
    elif new_status.is_terminal:
        commits = [MIGRATION_NO_COMMITS]
    else:
        commits = [MIGRATION_PENDING_COMMIT]

    return ReleaseAddendum(
        id=make_addendum_id(source_identifier, entry.branch),
        source_branch=default_branch,
        target_branch=entry.branch,
        status=new_status,
        commits=commits,
        work_branch=make_work_branch(source_identifier, entry.branch),
        worktree_key=make_worktree_key(source_identifier, entry.branch),
        queued_at=queued_at,
        # Preserve PR URL from the legacy entry as execution evidence.
        pr_url=entry.pr_url if entry.pr_url else None,
    )


def _archive_child_task(
    tracker: "TrackerProtocol",
    child_id: str,
    source_identifier: str,
    target_branch: str,
) -> bool:
    """Archive a child backport task and post a redirect comment.

    Does nothing when the child task is already archived.

    Args:
        tracker: Tracker implementation for the project.
        child_id: Identifier of the child backport task to archive.
        source_identifier: Source task identifier (for the comment text).
        target_branch: Target branch of the backport (for the comment text).

    Returns:
        True when the task was archived, False when it was already archived
        or could not be found.
    """
    try:
        issue = tracker.fetch_issue_detail(child_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "release_pick_migration: cannot fetch child %s for archival: %s",
            child_id,
            exc,
        )
        return False

    if issue is None:
        logger.debug(
            "release_pick_migration: child %s not found; skipping archival",
            child_id,
        )
        return False

    # Already archived — add comment if missing, then return without re-archiving.
    if tracker.is_archived(issue):
        logger.debug(
            "release_pick_migration: child %s already archived; skipping",
            child_id,
        )
        return False

    # Post the redirect comment first so it's visible even if archival fails.
    try:
        comment_text = _make_redirect_comment(source_identifier, target_branch)
        tracker.add_comment(child_id, comment_text, author="oompah")
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "release_pick_migration: failed to add comment to child %s: %s",
            child_id,
            exc,
        )

    try:
        tracker.archive_issue(child_id)
        logger.info(
            "release_pick_migration: archived child %s (source=%s branch=%r)",
            child_id,
            source_identifier,
            target_branch,
        )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "release_pick_migration: failed to archive child %s: %s",
            child_id,
            exc,
        )
        return False


# ---------------------------------------------------------------------------
# Per-source-task migration
# ---------------------------------------------------------------------------


def migrate_source_task(
    tracker: "TrackerProtocol",
    source_identifier: str,
    default_branch: str,
    *,
    now: str | None = None,
) -> tuple[int, int, int]:
    """Migrate the backport entries for one source task.

    Reads ``oompah.backports`` from *source_identifier*, converts each entry
    to a :class:`~oompah.release_addendum_schema.ReleaseAddendum`, and writes
    the updated list to ``oompah.release_addendums``.  For entries that had a
    child task, the child is archived with a redirect comment.

    The migration is idempotent: entries whose target branch already has an
    addendum (in any state) are left unchanged.

    Args:
        tracker: Tracker implementation for the project.
        source_identifier: Identifier of the source task to migrate.
        default_branch: Project's default branch name, used as ``source_branch``
            in newly created addendums.
        now: Optional ISO-8601 timestamp override; defaults to current UTC time.
            Useful for deterministic testing.

    Returns:
        A tuple ``(migrated, already_migrated, children_archived)`` counting
        entries converted, entries skipped, and child tasks archived.
    """
    queued_at = now or _utcnow()
    migrated = 0
    already_migrated = 0
    children_archived = 0

    # Read existing addendums so we can skip already-migrated branches.
    try:
        raw_addendums = tracker.get_metadata(source_identifier).get(
            "oompah.release_addendums"
        )
        existing_addendums = parse_addendums(raw_addendums)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "release_pick_migration: cannot read addendums for %s: %s",
            source_identifier,
            exc,
        )
        return 0, 0, 0

    # Build set of target branches that already have an addendum (any state).
    existing_branches: set[str] = {a.target_branch for a in existing_addendums}

    # Read legacy backport entries.
    try:
        raw_backports = tracker.get_metadata(source_identifier).get("oompah.backports")
        entries = parse_backports(raw_backports)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "release_pick_migration: cannot read backports for %s: %s",
            source_identifier,
            exc,
        )
        return 0, 0, 0

    if not entries:
        return 0, 0, 0

    new_addendums: list[ReleaseAddendum] = list(existing_addendums)

    for entry in entries:
        if entry.branch in existing_branches:
            # Already have an addendum for this branch; leave it alone.
            already_migrated += 1
            logger.debug(
                "release_pick_migration: %s branch=%r already has addendum; skipping",
                source_identifier,
                entry.branch,
            )
            continue

        try:
            addendum = build_addendum_from_entry(
                source_identifier, entry, default_branch, queued_at
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "release_pick_migration: cannot build addendum for %s branch=%r: %s",
                source_identifier,
                entry.branch,
                exc,
            )
            continue

        new_addendums.append(addendum)
        existing_branches.add(entry.branch)
        migrated += 1

        logger.info(
            "release_pick_migration: migrated %s branch=%r %s → %s",
            source_identifier,
            entry.branch,
            entry.status.value,
            addendum.status.value,
        )

        # Archive the child backport task if one was linked.
        if entry.task_id:
            archived = _archive_child_task(
                tracker, entry.task_id, source_identifier, entry.branch
            )
            if archived:
                children_archived += 1

    # Persist the updated addendum list when we have new entries.
    if migrated > 0:
        try:
            tracker.set_metadata_field(
                source_identifier,
                "oompah.release_addendums",
                addendums_to_raw(new_addendums),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "release_pick_migration: failed to write addendums for %s: %s",
                source_identifier,
                exc,
            )
            # Return 0 migrated so the caller knows this source task's migration failed.
            return 0, already_migrated, children_archived

    return migrated, already_migrated, children_archived


# ---------------------------------------------------------------------------
# Full-project migration pass
# ---------------------------------------------------------------------------


def run_release_pick_migration(
    tracker: "TrackerProtocol",
    default_branch: str,
    *,
    now: str | None = None,
) -> MigrationResult:
    """Run one idempotent migration pass over all issues in the tracker.

    Scans every issue for ``oompah.backports`` metadata.  For each source task
    that has backport entries the function delegates to
    :func:`migrate_source_task`.

    This function is safe to run at startup on every process restart; it is a
    no-op when all backport entries have already been migrated.

    Args:
        tracker: Tracker implementation for the project.
        default_branch: Project's default branch name.
        now: Optional ISO-8601 timestamp override used in tests.

    Returns:
        :class:`MigrationResult` summarising all changes made.
    """
    result = MigrationResult()

    try:
        all_issues = tracker.fetch_all_issues()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "release_pick_migration: fetch_all_issues failed: %s", exc
        )
        result.errors += 1
        return result

    for issue in all_issues:
        # Only process issues that carry oompah.backports metadata.
        try:
            raw_backports = _get_backports_value(tracker, issue)
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "release_pick_migration: get_metadata failed for %s: %s",
                issue.identifier,
                exc,
            )
            continue

        if not raw_backports:
            continue

        result.scanned += 1
        try:
            migrated, already_migrated, children_archived = migrate_source_task(
                tracker,
                issue.identifier,
                default_branch,
                now=now,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "release_pick_migration: error migrating %s: %s",
                issue.identifier,
                exc,
            )
            result.errors += 1
            continue

        result.migrated += migrated
        result.already_migrated += already_migrated
        result.children_archived += children_archived

    logger.info(
        "release_pick_migration: pass complete — scanned=%d migrated=%d "
        "already_migrated=%d children_archived=%d errors=%d",
        result.scanned,
        result.migrated,
        result.already_migrated,
        result.children_archived,
        result.errors,
    )
    return result


def _get_backports_value(
    tracker: "TrackerProtocol",
    issue: "Issue",
) -> Any:
    """Return the raw ``oompah.backports`` value for *issue*.

    Prefers the value already loaded on the Issue object (when
    ``release_pick_metadata_loaded`` is True) to avoid redundant tracker
    reads during a reconciliation pass.

    Args:
        tracker: Tracker implementation.
        issue: Issue to inspect.

    Returns:
        Raw ``oompah.backports`` value, or ``None`` when absent.
    """
    if getattr(issue, "release_pick_metadata_loaded", False):
        return getattr(issue, "backports", None)
    return tracker.get_metadata(issue.identifier).get("oompah.backports")
