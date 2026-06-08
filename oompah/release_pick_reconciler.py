"""Release-pick reconciliation loop (TASK-455.1 / TASK-455.3).

Idempotent background pass that scans source tasks and epics with
``oompah.backports`` metadata, evaluates each target branch entry, and
advances waiting or stale entries without creating duplicates.

Overview
--------

The reconciler is called once per background tick by the orchestrator (wired
into :meth:`~oompah.orchestrator.Orchestrator._reconcile_release_picks_pass`).
It performs three operations:

1. **Create child tasks** for ``waiting`` entries that have no matching child
   yet.  The child task is created under the source task (as a Backlog
   parent-child), carries ``oompah.backport_of`` pointing back to the source,
   and has ``oompah.target_branch`` set to the target branch name.  A
   target-branch worktree is also created (via ``project_store``) so that the
   cherry-pick agent has an isolated working copy rooted at
   ``origin/<target_branch>``.  The parent entry is advanced from
   ``waiting`` → ``task_created``.

2. **Heal stale ``waiting`` entries** where a child task already exists in the
   tracker (e.g. created by an earlier pass that crashed before writing the
   parent metadata).  The entry is advanced to ``task_created`` without
   creating a duplicate.

3. **Mirror terminal child outcomes** back to the parent entry.  When a child
   task reaches Done, Merged, or Archived the corresponding backports entry is
   advanced to ``merged`` or ``archived`` to keep the source task's metadata
   up to date.

The pass is idempotent: child tasks are never duplicated, and re-running with
no new information leaves everything unchanged.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from oompah.release_pick_schema import (
    BackportEntry,
    ReleasePick,
    backports_to_raw,
    parse_backport_of,
    parse_backports,
)
from oompah.statuses import ARCHIVED, DONE, MERGED, canonicalize_status

if TYPE_CHECKING:
    from oompah.models import Issue
    from oompah.projects import ProjectStore
    from oompah.scm import SCMProvider
    from oompah.tracker import BacklogMdTracker

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class ReconcileResult:
    """Summary of one release-pick reconciliation pass.

    Attributes:
        scanned: Number of source tasks that had ``oompah.backports`` metadata
            and were examined.
        advanced: Number of backport entries whose status was advanced.
        created: Number of new child backport tasks that were created.
        errors: Number of non-fatal errors encountered during the pass
            (bad metadata, tracker write failures, etc.).
    """

    scanned: int = 0
    advanced: int = 0
    created: int = 0
    errors: int = 0

    @property
    def changed(self) -> bool:
        """True when any entries were advanced or child tasks created."""
        return self.advanced > 0 or self.created > 0


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def reconcile_release_picks(
    tracker: "BacklogMdTracker",
    *,
    project_store: "ProjectStore | None" = None,
    project_id: "str | None" = None,
    scm: "SCMProvider | None" = None,
    repo: "str | None" = None,
) -> ReconcileResult:
    """Run one idempotent release-pick reconciliation pass.

    Scans all issues (active and completed) for ``oompah.backports`` metadata.
    For each source task that has backport entries the pass:

    * Advances ``waiting`` entries to ``task_created`` by creating a child
      backport task (or healing a stale entry when the child already exists).
      When *project_store* and *project_id* are supplied a target-branch
      worktree is also created for the new child so the cherry-pick agent has
      an isolated working copy rooted at ``origin/<target_branch>``.
    * Advances ``task_created`` entries that have resolved commits to
      ``pr_open`` (or ``conflict``) by cherry-picking the commits onto the
      child worktree, pushing the branch, and opening a PR.  Requires
      *project_store*, *project_id*, *scm*, and *repo* to all be supplied.
    * Advances non-terminal entries whose child task is Done/Merged/Archived
      to ``merged`` or ``archived`` to mirror the child's outcome.

    Terminal entries (``merged``, ``archived``) are left untouched.

    The pass is designed to be safe to run concurrently with the normal
    dispatch loop — it only writes metadata fields and creates new tasks; it
    never modifies existing task status.

    Args:
        tracker: The :class:`~oompah.tracker.BacklogMdTracker` for the project
            to reconcile.
        project_store: Optional :class:`~oompah.projects.ProjectStore` used to
            create target-branch worktrees alongside child tasks and to resolve
            the worktree path for cherry-pick operations.  When omitted
            worktrees are not created (useful in tests and legacy
            single-tracker mode).
        project_id: Project identifier passed to *project_store* for worktree
            path resolution.  Required when *project_store* is supplied.
        scm: Optional :class:`~oompah.scm.SCMProvider` used to open PRs
            against the release branch.  When omitted the cherry-pick+PR step
            is skipped even if commits are resolved.
        repo: Repository slug (e.g. ``"org/repo"``) passed to *scm*.
            Required when *scm* is supplied.

    Returns:
        :class:`ReconcileResult` summarising changes made during this pass.
    """
    result = ReconcileResult()

    # --- Load all issues once -------------------------------------------
    try:
        all_issues = tracker.fetch_all_issues()
    except Exception as exc:  # noqa: BLE001 — best-effort pass
        logger.warning("release_pick_reconciler: fetch_all_issues failed: %s", exc)
        result.errors += 1
        return result

    # --- Build a lookup of existing child tasks --------------------------
    # Maps (source_id_upper, target_branch) → list[Issue]
    # so we can detect and avoid duplicates without additional queries.
    child_index: dict[tuple[str, str], list[Issue]] = _build_child_index(
        tracker, all_issues
    )

    # --- Process each source task with oompah.backports ------------------
    for source in all_issues:
        try:
            meta = tracker.get_metadata(source.identifier)
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "release_pick_reconciler: get_metadata failed for %s: %s",
                source.identifier,
                exc,
            )
            continue

        raw_backports = meta.get("oompah.backports")
        if not raw_backports:
            continue

        try:
            entries = parse_backports(raw_backports)
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "release_pick_reconciler: bad oompah.backports on %s: %s",
                source.identifier,
                exc,
            )
            result.errors += 1
            continue

        if not entries:
            continue

        result.scanned += 1
        entries, n_advanced, n_created, n_errors = _reconcile_entries(
            tracker, source, entries, child_index,
            project_store=project_store,
            project_id=project_id,
            scm=scm,
            repo=repo,
        )
        result.advanced += n_advanced
        result.created += n_created
        result.errors += n_errors

        if n_advanced or n_created:
            try:
                tracker.set_metadata_field(
                    source.identifier,
                    "oompah.backports",
                    backports_to_raw(entries),
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "release_pick_reconciler: failed to write backports for %s: %s",
                    source.identifier,
                    exc,
                )
                result.errors += 1

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_child_index(
    tracker: "BacklogMdTracker",
    all_issues: "list[Issue]",
) -> "dict[tuple[str, str], list[Issue]]":
    """Build a lookup of child backport tasks.

    Returns a dict mapping ``(source_identifier_upper, target_branch)`` →
    ``list[Issue]``.  Each issue in the list has ``oompah.backport_of``
    pointing to the source.

    Non-backport tasks and tasks with unreadable metadata are silently
    skipped so a single bad task never breaks the whole index.
    """
    index: dict[tuple[str, str], list[Issue]] = {}
    for issue in all_issues:
        try:
            meta = tracker.get_metadata(issue.identifier)
        except Exception:  # noqa: BLE001
            continue
        raw_bof = meta.get("oompah.backport_of")
        if not raw_bof:
            continue
        try:
            bof = parse_backport_of(raw_bof)
        except Exception:  # noqa: BLE001
            continue
        if bof is None:
            continue
        branch = (issue.target_branch or "").strip()
        key = (bof.source.upper(), branch)
        index.setdefault(key, []).append(issue)
    return index


def _reconcile_entries(
    tracker: "BacklogMdTracker",
    source: "Issue",
    entries: "list[BackportEntry]",
    child_index: "dict[tuple[str, str], list[Issue]]",
    *,
    project_store: "ProjectStore | None" = None,
    project_id: "str | None" = None,
    scm: "SCMProvider | None" = None,
    repo: "str | None" = None,
) -> "tuple[list[BackportEntry], int, int, int]":
    """Reconcile the backport entries for one source task.

    Mutates *entries* in place and returns the updated list plus counters
    ``(entries, n_advanced, n_created, n_errors)``.
    """
    n_advanced = 0
    n_created = 0
    n_errors = 0

    for i, entry in enumerate(entries):
        if entry.status.is_terminal:
            continue

        key = (source.identifier.upper(), entry.branch)
        children = child_index.get(key, [])

        # --- Case 1: terminal child — mirror its outcome -----------------
        terminal_child = _most_terminal_child(children)
        if terminal_child is not None:
            child_state = canonicalize_status(terminal_child.state)
            new_status = (
                ReleasePick.ARCHIVED
                if child_state == ARCHIVED
                else ReleasePick.MERGED
            )
            if entry.status != new_status:
                entries[i] = BackportEntry(
                    branch=entry.branch,
                    status=new_status,
                    task_id=entry.task_id or terminal_child.identifier,
                    pr_url=entry.pr_url,
                )
                n_advanced += 1
                logger.info(
                    "release_pick_reconciler: %s branch=%r child=%s terminal → %s",
                    source.identifier,
                    entry.branch,
                    terminal_child.identifier,
                    new_status.value,
                )
            continue

        # --- Case 2: task_created with resolved commits — cherry-pick+PR ---
        if (
            entry.status == ReleasePick.TASK_CREATED
            and entry.commits
            and entry.task_id
            and project_store is not None
            and project_id is not None
            and scm is not None
            and repo is not None
        ):
            live_child = _best_live_child(children) if children else None
            if live_child is None and entry.task_id:
                # Try to find the child by task_id directly
                for issue in child_index.get(key, []):
                    if issue.identifier == entry.task_id:
                        live_child = issue
                        break
            if live_child is not None:
                try:
                    updated = _cherry_pick_and_open_pr(
                        tracker, source, entry, live_child,
                        project_store=project_store,
                        project_id=project_id,
                        scm=scm,
                        repo=repo,
                    )
                    entries[i] = updated
                    n_advanced += 1
                    logger.info(
                        "release_pick_reconciler: %s branch=%r"
                        " cherry-pick+PR → %s",
                        source.identifier,
                        entry.branch,
                        updated.status.value,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "release_pick_reconciler: cherry-pick+PR failed for"
                        " %s branch=%r: %s",
                        source.identifier,
                        entry.branch,
                        exc,
                    )
                    n_errors += 1
            continue

        # --- Case 3: waiting — create child or heal stale ----------------
        if entry.status == ReleasePick.WAITING:
            live_child = _best_live_child(children)
            if live_child is not None:
                # Child exists but parent still says waiting — heal it.
                entries[i] = BackportEntry(
                    branch=entry.branch,
                    status=ReleasePick.TASK_CREATED,
                    task_id=entry.task_id or live_child.identifier,
                    pr_url=entry.pr_url,
                )
                n_advanced += 1
                logger.info(
                    "release_pick_reconciler: %s branch=%r healed → task_created"
                    " (existing child=%s)",
                    source.identifier,
                    entry.branch,
                    live_child.identifier,
                )
            else:
                # No child at all — create one.
                try:
                    child = _create_backport_child(tracker, source, entry)
                    entries[i] = BackportEntry(
                        branch=entry.branch,
                        status=ReleasePick.TASK_CREATED,
                        task_id=child.identifier,
                        pr_url=entry.pr_url,
                    )
                    # Register in the index so subsequent passes for the
                    # same (source, branch) don't double-create.
                    child_index.setdefault(key, []).append(child)
                    n_created += 1
                    n_advanced += 1
                    logger.info(
                        "release_pick_reconciler: created child %s for %s branch=%r",
                        child.identifier,
                        source.identifier,
                        entry.branch,
                    )
                    # Create target-branch worktree for the cherry-pick agent.
                    if project_store is not None and project_id is not None:
                        try:
                            _create_backport_worktree(
                                child, entry, project_store, project_id
                            )
                        except Exception as wt_exc:  # noqa: BLE001
                            logger.warning(
                                "release_pick_reconciler: failed to create"
                                " worktree for child %s (branch=%r): %s",
                                child.identifier,
                                entry.branch,
                                wt_exc,
                            )
                            n_errors += 1
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "release_pick_reconciler: failed to create child for"
                        " %s branch=%r: %s",
                        source.identifier,
                        entry.branch,
                        exc,
                    )
                    n_errors += 1

    return entries, n_advanced, n_created, n_errors


def _most_terminal_child(children: "list[Issue]") -> "Issue | None":
    """Return the most terminal (Done/Merged/Archived) child issue, or None.

    Prefers Merged > Archived > Done so that a successfully merged backport
    is always picked over an archived or merely done one.
    """
    _rank = {MERGED: 0, ARCHIVED: 1, DONE: 2}
    terminal = [
        c
        for c in children
        if canonicalize_status(c.state) in _rank
    ]
    if not terminal:
        return None
    return min(terminal, key=lambda c: _rank.get(canonicalize_status(c.state), 99))


def _best_live_child(children: "list[Issue]") -> "Issue | None":
    """Return the first non-terminal child issue, or None."""
    _terminal = {MERGED, ARCHIVED, DONE}
    for child in children:
        if canonicalize_status(child.state) not in _terminal:
            return child
    return None


def _create_backport_child(
    tracker: "BacklogMdTracker",
    source: "Issue",
    entry: "BackportEntry",
) -> "Issue":
    """Create a child backport task in the tracker.

    The new task:

    * Has the source task as its Backlog parent (``--parent``).
    * Title: ``"Backport <source.title> to <entry.branch>"``.
    * ``backport`` label.
    * ``oompah.backport_of`` frontmatter pointing at the source.
    * ``oompah.target_branch`` set to ``entry.branch``.

    Callers that have a *project_store* should call
    :func:`_create_backport_worktree` immediately after this function to
    create the corresponding target-branch worktree for the cherry-pick agent.

    Args:
        tracker: Tracker to create the task in.
        source: Source task being backported.
        entry: The ``BackportEntry`` describing the target branch.

    Returns:
        The newly created :class:`~oompah.models.Issue`.

    Raises:
        :class:`~oompah.tracker.TrackerError`: When task creation fails.
    """
    title = f"Backport {source.title} to {entry.branch}"
    description = (
        f"Cherry-pick backport of {source.identifier} ({source.title}) "
        f"to branch `{entry.branch}`.\n\n"
        f"Source task: {source.identifier}"
    )
    child = tracker.create_issue(
        title=title,
        issue_type="task",
        description=description,
        labels=["backport"],
        parent=source.identifier,
    )
    tracker.set_metadata_field(
        child.identifier,
        "oompah.backport_of",
        {"source": source.identifier, "status": ReleasePick.TASK_CREATED.value},
    )
    tracker.set_metadata_field(
        child.identifier,
        "oompah.target_branch",
        entry.branch,
    )
    refreshed = tracker.fetch_issue_detail(child.identifier)
    return refreshed if refreshed is not None else child


def _cherry_pick_and_open_pr(
    tracker: "BacklogMdTracker",
    source: "Issue",
    entry: "BackportEntry",
    child_issue: "Issue",
    *,
    project_store: "ProjectStore",
    project_id: str,
    scm: "SCMProvider",
    repo: str,
) -> "BackportEntry":
    """Delegate to :func:`~oompah.cherry_pick_pr_creator.cherry_pick_push_and_open_pr`.

    Thin wrapper that imports the cherry-pick module lazily to keep the
    reconciler importable without the SCM or subprocess stack present.

    Returns the updated :class:`BackportEntry` with the new status and
    optional ``pr_url``.
    """
    from oompah.cherry_pick_pr_creator import cherry_pick_push_and_open_pr

    return cherry_pick_push_and_open_pr(
        tracker,
        source,
        entry,
        child_issue,
        project_store=project_store,
        project_id=project_id,
        scm=scm,
        repo=repo,
    )


def _create_backport_worktree(
    child: "Issue",
    entry: "BackportEntry",
    project_store: "ProjectStore",
    project_id: str,
) -> None:
    """Create a target-branch worktree for a newly created backport child task.

    The worktree is rooted at ``origin/<entry.branch>`` so the cherry-pick
    agent works on an isolated copy of the release branch rather than the
    project's default branch.

    This is a best-effort call — callers should catch any exceptions and
    decide whether to count them as errors.

    Args:
        child: The newly created child backport task.
        entry: The ``BackportEntry`` with the target branch name.
        project_store: Store used to create the worktree.
        project_id: Project identifier for path resolution.

    Raises:
        Any exception raised by :meth:`~oompah.projects.ProjectStore.create_worktree`.
    """
    project_store.create_worktree(
        project_id,
        child.identifier,
        base_branch=entry.branch,
    )
    logger.info(
        "release_pick_reconciler: created worktree for child %s"
        " (base=origin/%s)",
        child.identifier,
        entry.branch,
    )
