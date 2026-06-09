"""Cherry-pick, push, and PR-open step for release picks (TASK-455.4 / TASK-455.5).

Given a resolved :class:`~oompah.release_pick_schema.BackportEntry` with
``commits`` populated (set by TASK-455.2) and a child task with an existing
worktree (created by TASK-455.3), this module:

1. Applies the commits via ``git cherry-pick`` in the child worktree (skipped
   when the worktree already has new commits, for idempotent re-runs).
2. Pushes the child branch to ``origin``.
3. Opens a pull/merge request against the target release branch via the
   configured SCM provider.
4. Marks the child backport task ``In Review``.
5. Writes ``pr_url`` back to both the source task's ``oompah.backports``
   entry and the child task's ``oompah.backport_of`` metadata.

The operation is idempotent at the entry level: when the entry has already
reached ``pr_open`` (or any other post-``task_created`` status), the caller
should not call this module — the reconciler handles that gate.

Conflict handling (TASK-455.5)
-------------------------------

When ``git cherry-pick`` exits with conflict markers the module:

1. **Does NOT abort** the cherry-pick — the worktree is left intact with
   conflict markers in place so the developer can inspect and resolve them.
2. Raises :class:`CherryPickConflictError`.
3. The caller (:func:`cherry_pick_push_and_open_pr`) catches this and:
   a. Marks the child task ``Needs Rebase`` (the backlog status for merge
      conflicts) with a diagnostic comment describing the conflicts.
   b. Updates the child task's ``oompah.backport_of`` metadata to
      ``conflict`` status.
   c. Returns a :class:`~oompah.release_pick_schema.BackportEntry` with
      ``status=CONFLICT`` so the reconciler advances the source entry.

Later ticks will find the entry in ``conflict`` status and skip it (none of
the reconciler's advance-cases match ``CONFLICT``).  Additionally, if the
worktree still has an in-progress cherry-pick (``CHERRY_PICK_HEAD`` present),
:func:`apply_cherry_pick` detects this and raises :class:`CherryPickConflictError`
immediately rather than starting a second cherry-pick on top of the first.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from typing import TYPE_CHECKING, Any

from oompah.release_pick_schema import BackportEntry, ReleasePick
from oompah.statuses import IN_REVIEW, NEEDS_REBASE

if TYPE_CHECKING:
    from oompah.models import Issue
    from oompah.projects import ProjectStore
    from oompah.scm import SCMProvider
    from oompah.tracker import BacklogMdTracker

logger = logging.getLogger(__name__)

#: Timeout in seconds for individual git operations.
_GIT_TIMEOUT = 120


# ---------------------------------------------------------------------------
# Public exceptions
# ---------------------------------------------------------------------------


class CherryPickConflictError(Exception):
    """Raised when ``git cherry-pick`` fails due to merge conflicts.

    The worktree is left **intact** with conflict markers in place when this
    is raised from a live cherry-pick failure.  When raised because a
    cherry-pick is already in progress (``CHERRY_PICK_HEAD`` detected), the
    existing conflict state is similarly preserved.

    Callers should mark the corresponding task ``Needs Rebase`` and record
    a diagnostic comment; they must **not** attempt another cherry-pick until
    the conflicts have been resolved.
    """


class CherryPickError(Exception):
    """Raised when ``git cherry-pick`` fails for reasons other than conflicts."""


# ---------------------------------------------------------------------------
# Internal utilities
# ---------------------------------------------------------------------------


def _sanitize_identifier(value: str) -> str:
    """Return a branch-safe name derived from *value*.

    Mirrors :func:`oompah.projects._sanitize_identifier` so the branch
    name used here always matches the one created in the worktree.

    Args:
        value: Raw identifier string.

    Returns:
        String with non-alphanumeric characters (except ``.``, ``_``,
        ``-``) replaced by ``_``, with leading/trailing special chars
        stripped.
    """
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip())
    return cleaned.strip("._-") or "unnamed"


def _has_new_commits(wt_path: str, base_branch: str) -> bool:
    """Return True when the worktree has commits beyond ``origin/<base_branch>``.

    Used to detect whether the cherry-pick has already been applied in a
    previous (potentially crashed) run so we can skip re-running it.

    Args:
        wt_path: Path to the git worktree.
        base_branch: Target branch name (without ``origin/`` prefix).

    Returns:
        True when ``git rev-list HEAD ^origin/<base_branch>`` yields at
        least one commit; False on errors or when no commits are ahead.
    """
    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD", f"^origin/{base_branch}"],
            cwd=wt_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False
    if result.returncode != 0:
        return False
    count_str = result.stdout.strip()
    try:
        return int(count_str) > 0
    except ValueError:
        return False


def _has_cherry_pick_in_progress(wt_path: str) -> bool:
    """Return True when the worktree has a cherry-pick in progress.

    Checks for the presence of the ``CHERRY_PICK_HEAD`` file that git creates
    when a cherry-pick starts and removes when it completes or is aborted.
    When this file is present the worktree contains unresolved conflict markers
    and a new ``git cherry-pick`` cannot be started without first resolving or
    aborting the in-progress one.

    This is used to detect a **conflicted worktree from a previous run** so
    that later background ticks skip the cherry-pick instead of attempting to
    run it a second time on top of the existing conflict state.

    Args:
        wt_path: Path to the git worktree.

    Returns:
        True when ``CHERRY_PICK_HEAD`` exists in the git dir; False on any
        error or when the file is absent.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=wt_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return False
        git_dir = result.stdout.strip()
        if not os.path.isabs(git_dir):
            git_dir = os.path.join(wt_path, git_dir)
        cherry_pick_head = os.path.join(git_dir, "CHERRY_PICK_HEAD")
        return os.path.exists(cherry_pick_head)
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# Core building blocks
# ---------------------------------------------------------------------------


def apply_cherry_pick(wt_path: str, commits: list[str]) -> None:
    """Apply *commits* to the worktree at *wt_path* via ``git cherry-pick``.

    Skips the cherry-pick silently when the worktree already has commits
    ahead of ``origin/<whatever>`` (i.e. cherry-pick was already done in a
    previous run that crashed before writing status back).

    For conflict detection the base branch is inferred from the worktree's
    upstream tracking reference.  If that cannot be determined the check is
    skipped and we always run the cherry-pick.

    When ``git cherry-pick`` produces conflicts the worktree is **left
    intact** — the conflict markers remain in the working tree and
    ``CHERRY_PICK_HEAD`` is preserved so that the developer can inspect the
    conflicts and resolve them manually.  The cherry-pick is **not aborted**
    automatically.

    Args:
        wt_path: Absolute path to the git worktree.
        commits: Ordered list of commit SHAs to cherry-pick (oldest first).

    Raises:
        ValueError: When *commits* is empty.
        CherryPickConflictError: When a cherry-pick is already in progress
            (``CHERRY_PICK_HEAD`` present) *or* when the cherry-pick produces
            merge conflicts.  In both cases the worktree is left intact.
        CherryPickError: When the cherry-pick fails for any other reason.
    """
    if not commits:
        raise ValueError("commits list must not be empty")

    # ------------------------------------------------------------------
    # Guard: detect a conflicted worktree from a previous run.
    # If CHERRY_PICK_HEAD exists the worktree already has conflict markers
    # from an earlier run.  Raise immediately so later ticks do not try to
    # start a second cherry-pick on top of the existing conflict state.
    # ------------------------------------------------------------------
    if _has_cherry_pick_in_progress(wt_path):
        logger.warning(
            "apply_cherry_pick: worktree %s has a cherry-pick in progress"
            " (CHERRY_PICK_HEAD exists) — skipping to avoid overwriting"
            " existing conflict markers",
            wt_path,
        )
        raise CherryPickConflictError(
            f"cherry-pick in {wt_path!r} is already in progress "
            "(CHERRY_PICK_HEAD exists from a previous conflicted run); "
            "resolve or abort the in-progress cherry-pick first"
        )

    # ------------------------------------------------------------------
    # Idempotency: skip if cherry-pick already applied in a prior run
    # ------------------------------------------------------------------
    try:
        upstream_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
            cwd=wt_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        upstream = upstream_result.stdout.strip()  # e.g. "origin/release/1.0"
        if upstream.startswith("origin/"):
            base = upstream[len("origin/"):]
            if _has_new_commits(wt_path, base):
                logger.info(
                    "apply_cherry_pick: worktree %s already has new commits"
                    " ahead of origin/%s — skipping cherry-pick (idempotent re-run)",
                    wt_path,
                    base,
                )
                return
    except Exception:  # noqa: BLE001
        pass  # can't determine upstream — proceed with cherry-pick

    # ------------------------------------------------------------------
    # Run the cherry-pick
    # ------------------------------------------------------------------
    result = subprocess.run(
        ["git", "cherry-pick", *commits],
        cwd=wt_path,
        capture_output=True,
        text=True,
        timeout=_GIT_TIMEOUT,
    )

    if result.returncode == 0:
        logger.info(
            "apply_cherry_pick: successfully cherry-picked %d commit(s) in %s",
            len(commits),
            wt_path,
        )
        return

    stderr = result.stderr or ""
    stdout = result.stdout or ""
    combined = (stdout + "\n" + stderr).lower()

    # Distinguish conflict failures from other failures.
    # NOTE: We intentionally do NOT call ``git cherry-pick --abort`` here.
    # The worktree is left intact with the conflict markers in place so that
    # the developer can inspect the conflicting files and resolve them.
    conflict_markers = (
        "conflict",
        "merge conflict",
        "patch failed",
        "after resolving the conflicts",
        "patch does not apply",
    )
    if any(m in combined for m in conflict_markers):
        logger.warning(
            "apply_cherry_pick: conflict detected in %s for commits %r"
            " — leaving worktree intact (not aborting)",
            wt_path,
            commits,
        )
        raise CherryPickConflictError(
            f"cherry-pick of {commits!r} in {wt_path!r} produced conflicts: "
            f"{stderr[:400]}"
        )

    # Non-conflict failure: this is unexpected (bad SHA, missing object, etc.).
    # Abort so the worktree stays usable for manual investigation.
    subprocess.run(
        ["git", "cherry-pick", "--abort"],
        cwd=wt_path,
        capture_output=True,
        text=True,
        timeout=30,
    )
    raise CherryPickError(
        f"cherry-pick of {commits!r} in {wt_path!r} failed "
        f"(exit={result.returncode}): {stderr[:400]}"
    )


def push_branch(wt_path: str, branch_name: str) -> None:
    """Push *branch_name* to ``origin`` from the worktree at *wt_path*.

    Uses ``-u`` to set the upstream tracking reference so subsequent
    ``git push`` / ``git pull`` commands work without explicit arguments.
    Uses ``--force-with-lease`` to handle idempotent re-pushes safely.

    Args:
        wt_path: Absolute path to the git worktree.
        branch_name: Local branch name to push.

    Raises:
        subprocess.CalledProcessError: When ``git push`` exits non-zero.
    """
    subprocess.run(
        ["git", "push", "-u", "--force-with-lease", "origin", branch_name],
        cwd=wt_path,
        capture_output=True,
        text=True,
        check=True,
        timeout=_GIT_TIMEOUT,
    )
    logger.info(
        "push_branch: pushed %s from %s to origin",
        branch_name,
        wt_path,
    )


def open_backport_pr(
    scm: "SCMProvider",
    repo: str,
    source: "Issue",
    child_issue: "Issue",
    entry: BackportEntry,
) -> "str | None":
    """Open a PR for the backport branch against the target release branch.

    The PR source branch is the sanitized child-task identifier
    (``_sanitize_identifier(child_issue.identifier)``), which matches the
    branch created by :func:`~oompah.projects.ProjectStore.create_worktree`.

    Args:
        scm: SCM provider (GitHub, GitLab).
        repo: Repository slug (e.g. ``"org/repo"``).
        source: Source task being backported.
        child_issue: Child backport task.
        entry: The :class:`~oompah.release_pick_schema.BackportEntry` with
            the target branch name.

    Returns:
        The PR URL string on success, or ``None`` when the SCM call fails or
        returns no result.
    """
    branch_name = _sanitize_identifier(child_issue.identifier)
    title = f"{child_issue.identifier}: Backport {source.title} to {entry.branch}"
    description = (
        f"Cherry-pick backport of {source.identifier} "
        f"({source.title}) to `{entry.branch}`.\n\n"
        f"Source task: {source.identifier}"
    )

    try:
        result = scm.create_review(
            repo,
            title,
            branch_name,
            target_branch=entry.branch,
            description=description,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "open_backport_pr: create_review failed for %s → %s: %s",
            child_issue.identifier,
            entry.branch,
            exc,
        )
        return None

    if result is None:
        logger.warning(
            "open_backport_pr: create_review returned None for %s → %s",
            child_issue.identifier,
            entry.branch,
        )
        return None

    pr_url = getattr(result, "url", None) or ""
    logger.info(
        "open_backport_pr: opened PR for %s → %s (id=%s url=%s)",
        child_issue.identifier,
        entry.branch,
        result.id,
        pr_url,
    )
    return pr_url or None


# ---------------------------------------------------------------------------
# Metadata helpers
# ---------------------------------------------------------------------------


def _write_child_backport_of(
    tracker: "BacklogMdTracker",
    child_identifier: str,
    source_identifier: str,
    status: ReleasePick,
    *,
    pr_url: "str | None" = None,
) -> None:
    """Write (or update) ``oompah.backport_of`` on a child backport task.

    Args:
        tracker: Tracker to write to.
        child_identifier: Child task identifier.
        source_identifier: Source task identifier.
        status: Release-pick status to stamp on the child.
        pr_url: Optional PR URL to store alongside the status.
    """
    raw: dict[str, Any] = {
        "source": source_identifier,
        "status": status.value,
    }
    if pr_url:
        raw["pr_url"] = pr_url

    try:
        tracker.set_metadata_field(
            child_identifier,
            "oompah.backport_of",
            raw,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "_write_child_backport_of: failed to write oompah.backport_of"
            " for %s: %s",
            child_identifier,
            exc,
        )


# ---------------------------------------------------------------------------
# Orchestrating entry point
# ---------------------------------------------------------------------------


def cherry_pick_push_and_open_pr(
    tracker: "BacklogMdTracker",
    source: "Issue",
    entry: BackportEntry,
    child_issue: "Issue",
    *,
    project_store: "ProjectStore",
    project_id: str,
    scm: "SCMProvider",
    repo: str,
) -> BackportEntry:
    """Apply cherry-pick commits, push the branch, and open a PR.

    Executes the full cherry-pick → push → PR-open pipeline for a single
    backport entry.  On success the entry is advanced to ``pr_open`` (or
    ``cherry_picking`` when the SCM call fails to return a URL) and both
    the source and child task metadata are updated.

    On conflict the entry is advanced to ``conflict`` and the child task
    metadata is stamped accordingly.  The caller (reconciler) is responsible
    for writing the updated entry back to the source task's frontmatter.

    Args:
        tracker: Tracker for reading/writing task metadata and status.
        source: Source task being backported.
        entry: The :class:`~oompah.release_pick_schema.BackportEntry`
            describing this pick.  Must have ``commits`` and ``task_id``
            populated.
        child_issue: The child backport task.
        project_store: Used to resolve the worktree path.
        project_id: Project identifier for path resolution.
        scm: SCM provider for opening the PR.
        repo: Repository slug (e.g. ``"org/repo"``).

    Returns:
        An updated :class:`~oompah.release_pick_schema.BackportEntry` with
        the new status and optional ``pr_url``.

    Raises:
        CherryPickError: When ``git cherry-pick`` fails for a reason other
            than conflicts.
        subprocess.CalledProcessError: When ``git push`` fails.
        Any exception from :func:`~oompah.projects.ProjectStore.worktree_path_for`
            when the worktree path cannot be resolved.
    """
    wt_path = project_store.worktree_path_for(project_id, child_issue.identifier)
    branch_name = _sanitize_identifier(child_issue.identifier)

    # ------------------------------------------------------------------
    # Step 1: Cherry-pick commits
    # ------------------------------------------------------------------
    try:
        apply_cherry_pick(wt_path, entry.commits)
    except CherryPickConflictError as exc:
        logger.warning(
            "cherry_pick_push_and_open_pr: conflict for %s → %s: %s",
            source.identifier,
            entry.branch,
            exc,
        )

        # Mark the child task Needs Rebase (the canonical status for merge
        # conflicts) so it is visible in the backlog and can be dispatched
        # to a rebase agent.
        try:
            tracker.update_issue(child_issue.identifier, status=NEEDS_REBASE)
            logger.info(
                "cherry_pick_push_and_open_pr: marked %s Needs Rebase (conflict)",
                child_issue.identifier,
            )
        except Exception as update_exc:  # noqa: BLE001
            logger.warning(
                "cherry_pick_push_and_open_pr: failed to mark %s Needs Rebase: %s",
                child_issue.identifier,
                update_exc,
            )

        # Add a diagnostic comment to the child task so the developer (or a
        # rebase agent) knows exactly what happened and what files need fixing.
        diagnostic = (
            f"**Cherry-pick conflict** when applying commits "
            f"`{', '.join(entry.commits)}` to branch `{entry.branch}`.\n\n"
            f"The worktree at `{wt_path}` has been left intact with conflict "
            f"markers in place. Resolve the conflicts, then run:\n\n"
            f"```\ngit cherry-pick --continue\ngit push\n```\n\n"
            f"Conflict details:\n```\n{exc}\n```"
        )
        try:
            tracker.add_comment(
                child_issue.identifier,
                diagnostic,
                author="oompah",
            )
        except Exception as comment_exc:  # noqa: BLE001
            logger.warning(
                "cherry_pick_push_and_open_pr: failed to add diagnostic"
                " comment to %s: %s",
                child_issue.identifier,
                comment_exc,
            )

        _write_child_backport_of(
            tracker,
            child_issue.identifier,
            source.identifier,
            ReleasePick.CONFLICT,
        )
        return BackportEntry(
            branch=entry.branch,
            status=ReleasePick.CONFLICT,
            task_id=entry.task_id,
            pr_url=entry.pr_url,
            commits=entry.commits,
        )
    # CherryPickError and other exceptions propagate to caller

    # ------------------------------------------------------------------
    # Step 2: Push the child branch
    # ------------------------------------------------------------------
    push_branch(wt_path, branch_name)

    # ------------------------------------------------------------------
    # Step 3: Open the PR via SCM
    # ------------------------------------------------------------------
    pr_url = open_backport_pr(scm, repo, source, child_issue, entry)

    # ------------------------------------------------------------------
    # Step 4: Mark child task In Review
    # ------------------------------------------------------------------
    try:
        tracker.update_issue(child_issue.identifier, status=IN_REVIEW)
        logger.info(
            "cherry_pick_push_and_open_pr: marked %s In Review",
            child_issue.identifier,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "cherry_pick_push_and_open_pr: failed to mark %s In Review: %s",
            child_issue.identifier,
            exc,
        )

    # ------------------------------------------------------------------
    # Step 5: Write PR metadata to child task
    # ------------------------------------------------------------------
    new_status = ReleasePick.PR_OPEN if pr_url else ReleasePick.CHERRY_PICKING
    _write_child_backport_of(
        tracker,
        child_issue.identifier,
        source.identifier,
        new_status,
        pr_url=pr_url,
    )

    # ------------------------------------------------------------------
    # Step 6: Return updated entry (caller writes it to source metadata)
    # ------------------------------------------------------------------
    return BackportEntry(
        branch=entry.branch,
        status=new_status,
        task_id=entry.task_id,
        pr_url=pr_url,
        commits=entry.commits,
    )
