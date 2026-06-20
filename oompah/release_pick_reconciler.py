"""Release-pick reconciliation loop (TASK-455.1 / TASK-455.3 / TASK-455.6).

Idempotent background pass that scans source tasks and epics with
``oompah.backports`` metadata, evaluates each target branch entry, and
advances waiting or stale entries without creating duplicates.

Overview
--------

The reconciler is called once per background tick by the orchestrator (wired
into :meth:`~oompah.orchestrator.Orchestrator._reconcile_release_picks_pass`).
It performs four operations:

1. **Create child tasks** for ``waiting`` entries that have no matching child
   yet.  The child task is created under the source task as a native
   parent-child relationship, carries ``oompah.backport_of`` pointing back to the source,
   and has ``oompah.target_branch`` set to the target branch name.  A
   target-branch worktree is also created (via ``project_store``) so that the
   cherry-pick agent has an isolated working copy rooted at
   ``origin/<target_branch>``.  The parent entry is advanced from
   ``waiting`` → ``task_created``.

2. **Heal stale ``waiting`` entries** where a child task already exists in the
   tracker (e.g. created by an earlier pass that crashed before writing the
   parent metadata).  The entry is advanced to ``task_created`` without
   creating a duplicate.

3. **Track PR outcomes** for ``pr_open`` and ``cherry_picking`` entries
   (TASK-455.6).  When the SCM provider is available, each entry's PR is
   queried.  A merged PR advances the entry to ``merged`` and marks the child
   task as Merged.  A PR closed without merging escalates the entry to
   ``needs_human`` and posts an actionable comment on the source task.  An
   open PR is left unchanged (check on next pass).

4. **Mirror terminal child outcomes** back to the parent entry.  When a child
   task reaches Done, Merged, or Archived the corresponding backports entry is
   advanced to ``merged`` or ``archived`` to keep the source task's metadata
   up to date.

The pass is idempotent: child tasks are never duplicated, and re-running with
no new information leaves everything unchanged.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, TYPE_CHECKING

from oompah.release_pick_schema import (
    BackportEntry,
    ReleasePick,
    backports_to_raw,
    parse_backport_of,
    parse_backports,
)
from oompah.statuses import ARCHIVED, DONE, MERGED, NEEDS_HUMAN, canonicalize_status

if TYPE_CHECKING:
    from oompah.models import Issue
    from oompah.projects import ProjectStore
    from oompah.scm import ReviewRequest, SCMProvider
    from oompah.tracker import TrackerProtocol

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
    tracker: "TrackerProtocol",
    *,
    project_store: "ProjectStore | None" = None,
    project_id: "str | None" = None,
    scm: "SCMProvider | None" = None,
    repo: "str | None" = None,
    should_stop: Callable[[], bool] | None = None,
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
        tracker: The :class:`~oompah.tracker.TrackerProtocol` implementation for the project
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
        should_stop: Optional cooperative stop callback. When it returns
            ``True``, the pass exits at a safe boundary and resumes next run.

    Returns:
        :class:`ReconcileResult` summarising changes made during this pass.
    """
    result = ReconcileResult()

    if should_stop is not None and should_stop():
        return result

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
    child_index = _build_child_index(
        tracker,
        all_issues,
        should_stop=should_stop,
    )
    if child_index is None:
        return result

    # --- Process each source task with oompah.backports ------------------
    for source in all_issues:
        if should_stop is not None and should_stop():
            break
        try:
            raw_backports = _release_pick_metadata_value(
                tracker,
                source,
                attr="backports",
                key="oompah.backports",
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "release_pick_reconciler: get_metadata failed for %s: %s",
                source.identifier,
                exc,
            )
            continue

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
    tracker: "TrackerProtocol",
    all_issues: "list[Issue]",
    *,
    should_stop: Callable[[], bool] | None = None,
) -> "dict[tuple[str, str], list[Issue]] | None":
    """Build a lookup of child backport tasks.

    Returns a dict mapping ``(source_identifier_upper, target_branch)`` →
    ``list[Issue]``.  Each issue in the list has ``oompah.backport_of``
    pointing to the source.

    Non-backport tasks and tasks with unreadable metadata are silently
    skipped so a single bad task never breaks the whole index.
    """
    index: dict[tuple[str, str], list[Issue]] = {}
    for issue in all_issues:
        if should_stop is not None and should_stop():
            return None
        try:
            raw_bof = _release_pick_metadata_value(
                tracker,
                issue,
                attr="backport_of",
                key="oompah.backport_of",
            )
        except Exception:  # noqa: BLE001
            continue
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


def _release_pick_metadata_value(
    tracker: "TrackerProtocol",
    issue: "Issue",
    *,
    attr: str,
    key: str,
) -> Any:
    """Return release-pick metadata, preferring values loaded with the issue."""
    if getattr(issue, "release_pick_metadata_loaded", False):
        return getattr(issue, attr, None)
    return tracker.get_metadata(issue.identifier).get(key)


def _reconcile_entries(
    tracker: "TrackerProtocol",
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

        # --- Case 2: pr_open/cherry_picking — check PR outcome via SCM ---
        if (
            entry.status in (ReleasePick.PR_OPEN, ReleasePick.CHERRY_PICKING)
            and entry.task_id
            and scm is not None
            and repo is not None
        ):
            try:
                updated = _check_pr_outcome(
                    tracker, source, entry, children,
                    scm=scm, repo=repo,
                )
                if updated is not entry:
                    entries[i] = updated
                    n_advanced += 1
                    logger.info(
                        "release_pick_reconciler: %s branch=%r PR outcome → %s",
                        source.identifier,
                        entry.branch,
                        updated.status.value,
                    )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "release_pick_reconciler: PR outcome check failed for"
                    " %s branch=%r: %s",
                    source.identifier,
                    entry.branch,
                    exc,
                )
                n_errors += 1
            continue

        # --- Case 3: task_created with resolved commits — cherry-pick+PR ---
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
                    # AC#2: When a conflict is detected, surface an
                    # actionable comment on the SOURCE task so operators
                    # watching the source GitHub Issue are alerted.
                    if updated.status == ReleasePick.CONFLICT:
                        _post_conflict_source_comment(
                            tracker,
                            source,
                            entry,
                            live_child,
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

        # --- Case 4: waiting — create child or heal stale ----------------
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


def _post_conflict_source_comment(
    tracker: "TrackerProtocol",
    source: "Issue",
    entry: "BackportEntry",
    child: "Issue",
) -> None:
    """Post an actionable conflict comment on the *source* task.

    Called when a cherry-pick conflict is detected so that operators watching
    the source task are alerted and can take action.
    The child task already gets a diagnostic comment (from
    :func:`~oompah.cherry_pick_pr_creator.cherry_pick_push_and_open_pr`);
    this adds a parallel, human-readable notice to the source.

    Failures are caught and logged — the parent reconcile pass must not fail
    because a comment could not be posted.

    Args:
        tracker: Tracker to post the comment on.
        source: Source task whose backport entry has a conflict.
        entry: The ``BackportEntry`` with ``status=CONFLICT``.
        child: The child backport task with the conflicted worktree.
    """
    comment = (
        f"⚠️ **Backport conflict** for branch `{entry.branch}`.\n\n"
        f"The cherry-pick of {source.identifier} ({source.title}) onto "
        f"`{entry.branch}` produced merge conflicts in child task "
        f"{child.identifier}.\n\n"
        f"**Action required**:\n"
        f"1. Switch to the child task {child.identifier} to see the "
        f"conflict details.\n"
        f"2. Resolve the conflicts in the worktree and run "
        f"`git cherry-pick --continue && git push`.\n"
        f"3. Once the PR is open, the backport status will automatically "
        f"advance from `conflict` to `pr_open`.\n\n"
        f"The worktree has been preserved with conflict markers in place "
        f"so no work is lost."
    )
    try:
        tracker.add_comment(source.identifier, comment, author="oompah")
        logger.info(
            "release_pick_reconciler: posted conflict comment on source %s"
            " (branch=%r child=%s)",
            source.identifier,
            entry.branch,
            child.identifier,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "release_pick_reconciler: failed to post conflict comment on"
            " source %s: %s",
            source.identifier,
            exc,
        )


def _check_pr_outcome(
    tracker: "TrackerProtocol",
    source: "Issue",
    entry: "BackportEntry",
    children: "list[Issue]",
    *,
    scm: "SCMProvider",
    repo: str,
) -> "BackportEntry":
    """Check the PR status for a backport entry and advance accordingly.

    Queries the SCM provider for the PR associated with the child task's
    branch.  Based on the PR state:

    * **merged**: Advance entry to ``merged``, mark the child task as Merged,
      and update the child's ``oompah.backport_of`` metadata.
    * **closed** (unmerged): Escalate entry to ``needs_human`` with an
      actionable comment on the *source* task, and update the child's
      ``oompah.backport_of`` metadata.
    * **open**: No change (return original entry, will be re-checked next pass).
    * **not found**: No change (return original entry).

    Any exception from the SCM provider is caught and logged; the original
    entry is returned unchanged so the pass remains non-fatal.

    Args:
        tracker: Tracker for reading/writing task metadata and status.
        source: Source task being backported.
        entry: The ``BackportEntry`` with PR-related status to check.
        children: List of child issues for this (source, branch) pair.
        scm: SCM provider for querying PR status.
        repo: Repository slug (e.g. ``"org/repo"``).

    Returns:
        Updated ``BackportEntry`` if the PR state changed the entry; the
        *same* object otherwise (identity comparison is safe for callers).
    """
    # Find the live child task to determine the PR branch name.
    live_child = _best_live_child(children)
    if live_child is None and entry.task_id:
        # Fall back to any child whose identifier matches task_id even if terminal
        # (so we can detect a merged PR for a child that was already closed).
        for child in children:
            if child.identifier == entry.task_id:
                live_child = child
                break

    if live_child is None:
        logger.debug(
            "release_pick_reconciler: no child for %s branch=%r, "
            "cannot check PR outcome",
            source.identifier,
            entry.branch,
        )
        return entry

    # Use target_branch if available; fall back to the child identifier.
    branch_name = live_child.target_branch or live_child.identifier

    # --- Query SCM ---------------------------------------------------------
    pr: "ReviewRequest | None" = None
    try:
        pr = scm.find_pr_for_branch(repo, branch_name)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "release_pick_reconciler: find_pr_for_branch failed for %s "
            "branch=%r: %s",
            source.identifier,
            branch_name,
            exc,
        )
        return entry

    if pr is None:
        logger.debug(
            "release_pick_reconciler: no PR found for %s branch=%r",
            source.identifier,
            branch_name,
        )
        return entry

    pr_state = (pr.state or "").lower()
    logger.debug(
        "release_pick_reconciler: PR check for %s branch=%r: state=%s",
        source.identifier,
        branch_name,
        pr_state,
    )

    # --- PR merged: advance entry to merged, mark child Merged ------------
    if pr_state == "merged":
        try:
            if canonicalize_status(live_child.state) != MERGED:
                tracker.update_issue(live_child.identifier, status=MERGED)
                logger.info(
                    "release_pick_reconciler: marked child %s Merged (PR merged)",
                    live_child.identifier,
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "release_pick_reconciler: failed to mark child %s Merged: %s",
                live_child.identifier,
                exc,
            )

        # Mirror merged status into the child's backport_of metadata.
        try:
            from oompah.release_pick_schema import BackportOf

            bof_raw = tracker.get_metadata(live_child.identifier).get(
                "oompah.backport_of"
            )
            if bof_raw:
                bof = BackportOf.from_raw(bof_raw)
                bof.status = ReleasePick.MERGED
                tracker.set_metadata_field(
                    live_child.identifier,
                    "oompah.backport_of",
                    bof.to_raw(),
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "release_pick_reconciler: failed to update backport_of for %s: %s",
                live_child.identifier,
                exc,
            )

        return BackportEntry(
            branch=entry.branch,
            status=ReleasePick.MERGED,
            task_id=entry.task_id or live_child.identifier,
            pr_url=entry.pr_url or pr.url,
            commits=entry.commits,
        )

    # --- PR closed (unmerged): escalate to needs_human --------------------
    if pr_state == "closed":
        actionable_comment = (
            f"Backport PR #{pr.id} ({pr.url}) for branch `{branch_name}` was "
            f"closed without merging. The cherry-pick changes need to be "
            f"re-applied or the backport abandoned.\n\n"
            f"**Action required**:\n"
            f"1. Check the PR at {pr.url} for closure reason.\n"
            f"2. If the changes are still needed, reopen the PR or create a "
            f"new one.\n"
            f"3. If the backport is no longer needed, mark this entry as "
            f"`archived`.\n"
            f"4. If there are conflicts, resolve them and push a new branch."
        )
        try:
            tracker.add_comment(
                source.identifier, actionable_comment, author="oompah"
            )
            logger.warning(
                "release_pick_reconciler: escalated %s branch=%r to "
                "needs_human (PR closed unmerged)",
                source.identifier,
                branch_name,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "release_pick_reconciler: failed to add escalation comment "
                "for %s: %s",
                source.identifier,
                exc,
            )

        # Mirror needs_human status into the child's backport_of metadata.
        try:
            from oompah.release_pick_schema import BackportOf

            bof_raw = tracker.get_metadata(live_child.identifier).get(
                "oompah.backport_of"
            )
            if bof_raw:
                bof = BackportOf.from_raw(bof_raw)
                bof.status = ReleasePick.NEEDS_HUMAN
                tracker.set_metadata_field(
                    live_child.identifier,
                    "oompah.backport_of",
                    bof.to_raw(),
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "release_pick_reconciler: failed to update backport_of for %s: %s",
                live_child.identifier,
                exc,
            )

        return BackportEntry(
            branch=entry.branch,
            status=ReleasePick.NEEDS_HUMAN,
            task_id=entry.task_id or live_child.identifier,
            pr_url=entry.pr_url or pr.url,
            commits=entry.commits,
        )

    # --- PR still open: no change -----------------------------------------
    return entry

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
    tracker: "TrackerProtocol",
    source: "Issue",
    entry: "BackportEntry",
) -> "Issue":
    """Create a child backport task in the tracker.

    The new task:

    * Has the source task as its parent.
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
    tracker: "TrackerProtocol",
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
