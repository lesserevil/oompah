"""Resolve the commit set to cherry-pick for a release-pick (TASK-455.2).

Given a source :class:`~oompah.models.Issue` and a
:class:`~oompah.release_pick_schema.BackportEntry`, determines which commits
should be cherry-picked onto the target release branch.

Resolution order
----------------

1. **Explicit commits in metadata** (``entry.commits`` is non-empty) — the
   commits are already known (from a previous run or from operator-supplied
   metadata). Return them immediately without any I/O.

2. **SCM PR lookup** — when an SCM provider and repo slug are supplied, find
   the merged PR whose *source* (head) branch matches the source task's
   branch name (``source_task.branch_name``), then call
   :meth:`SCMProvider.get_pr_commits` to fetch the ordered list of SHAs.
   Only *merged* PRs are considered; open or closed-without-merge PRs are
   skipped.

3. **Git rev-list fallback** — when a local ``repo_path`` is supplied but the
   SCM lookup found nothing (or no SCM is available), run::

       git rev-list --reverse
           origin/<source_task.branch_name>
           ^origin/<default_branch>

   in the repository to derive the commits that are on the source branch but
   not on the default branch.  This is the cheapest strategy when the
   commits have already been pushed but no PR was opened (e.g. direct-push
   workflows).

Recording
---------

After resolving, :func:`resolve_and_record_commits` writes the commit list
back into the source task's ``oompah.backports`` frontmatter (via
:meth:`tracker.set_metadata_field`) so that subsequent runs are idempotent
and the cherry-pick step (TASK-455.4) has a stable commit list to work from.
"""

from __future__ import annotations

import logging
import subprocess
from typing import TYPE_CHECKING, Any

from oompah.models import Issue
from oompah.release_pick_schema import (
    BackportEntry,
    backports_to_raw,
    parse_backports,
)

if TYPE_CHECKING:
    from oompah.scm import SCMProvider

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core resolution function
# ---------------------------------------------------------------------------


def resolve_commits_for_entry(
    source_task: Issue,
    entry: BackportEntry,
    *,
    scm: "SCMProvider | None" = None,
    repo: str | None = None,
    repo_path: str | None = None,
    default_branch: str = "main",
) -> list[str]:
    """Resolve the commit SHAs to cherry-pick for *entry*.

    Resolution order (first non-empty result wins):

    1. **Explicit commits** — ``entry.commits`` is already populated.
       Return it unchanged.
    2. **SCM PR lookup** — if *scm* and *repo* are provided, find the
       merged PR for ``source_task.branch_name`` and fetch its commits.
    3. **Git rev-list** — if *repo_path* is provided, run
       ``git rev-list --reverse origin/<branch> ^origin/<default_branch>``
       in the local repository checkout.

    Args:
        source_task: The source :class:`~oompah.models.Issue` whose
            commits we want to cherry-pick.
        entry: The :class:`~oompah.release_pick_schema.BackportEntry`
            describing the target branch.  When ``entry.commits`` is
            already non-empty this function returns immediately.
        scm: Optional :class:`~oompah.scm.SCMProvider` instance (GitHub
            or GitLab).  Required for the SCM-PR strategy.
        repo: Repository slug (e.g. ``"org/repo"``).  Required alongside
            *scm* for the SCM-PR strategy.
        repo_path: Path to a local git repository clone.  Used as a
            fallback when SCM lookup is unavailable or yields no commits.
        default_branch: Name of the default/source branch against which
            the rev-list exclusion is computed (e.g. ``"main"``).
            Defaults to ``"main"``.

    Returns:
        Ordered list of full-length commit SHAs (oldest first), or an
        empty list when all strategies fail to find commits.
    """
    # ------------------------------------------------------------------
    # Strategy 1: explicit commits already in metadata
    # ------------------------------------------------------------------
    if entry.commits:
        logger.debug(
            "resolve_commits: %s → %s: using %d explicit commit(s) from metadata",
            source_task.identifier,
            entry.branch,
            len(entry.commits),
        )
        return list(entry.commits)

    branch = source_task.branch_name or source_task.identifier

    # ------------------------------------------------------------------
    # Strategy 2: SCM PR lookup
    # ------------------------------------------------------------------
    if scm is not None and repo:
        commits = _resolve_via_scm(scm, repo, branch, source_task.identifier, entry.branch)
        if commits:
            return commits

    # ------------------------------------------------------------------
    # Strategy 3: git rev-list fallback
    # ------------------------------------------------------------------
    if repo_path:
        commits = _resolve_via_git(
            repo_path, branch, default_branch, source_task.identifier, entry.branch
        )
        if commits:
            return commits

    logger.debug(
        "resolve_commits: %s → %s: no commits resolved (branch=%r, scm=%s, repo_path=%s)",
        source_task.identifier,
        entry.branch,
        branch,
        "yes" if scm and repo else "no",
        "yes" if repo_path else "no",
    )
    return []


# ---------------------------------------------------------------------------
# Resolve-and-record helper
# ---------------------------------------------------------------------------


def resolve_and_record_commits(
    tracker: Any,
    source_task: Issue,
    entry: BackportEntry,
    *,
    scm: "SCMProvider | None" = None,
    repo: str | None = None,
    repo_path: str | None = None,
    default_branch: str = "main",
) -> BackportEntry:
    """Resolve commits for *entry* and persist them to *source_task*'s metadata.

    Calls :func:`resolve_commits_for_entry`.  When commits are resolved
    **and the entry did not already have them**, updates the matching entry
    in the source task's ``oompah.backports`` list and writes it back via
    ``tracker.set_metadata_field``.

    The function is idempotent: if ``entry.commits`` is already populated,
    no metadata write is performed.

    Args:
        tracker: A tracker instance exposing ``get_metadata(identifier)``
            and ``set_metadata_field(identifier, key, value)``.
        source_task: The source :class:`~oompah.models.Issue`.
        entry: The :class:`~oompah.release_pick_schema.BackportEntry` to
            resolve commits for.
        scm: Optional :class:`~oompah.scm.SCMProvider` instance.
        repo: Repository slug used with *scm*.
        repo_path: Path to local repository checkout (git fallback).
        default_branch: Default branch name for the rev-list exclusion.

    Returns:
        The :class:`~oompah.release_pick_schema.BackportEntry` with
        ``commits`` populated (or the original entry unchanged when
        resolution yields nothing).

    Raises:
        Exception: Propagated from ``tracker.set_metadata_field`` when
            the metadata write fails.  Callers should catch this if they
            want to continue on partial failure.
    """
    # Skip resolution + write when commits are already present
    if entry.commits:
        logger.debug(
            "resolve_and_record_commits: %s → %s: commits already resolved (%d), skipping write",
            source_task.identifier,
            entry.branch,
            len(entry.commits),
        )
        return entry

    resolved = resolve_commits_for_entry(
        source_task,
        entry,
        scm=scm,
        repo=repo,
        repo_path=repo_path,
        default_branch=default_branch,
    )

    if not resolved:
        logger.debug(
            "resolve_and_record_commits: %s → %s: no commits resolved, skipping write",
            source_task.identifier,
            entry.branch,
        )
        return entry

    # Build the updated entry
    updated_entry = BackportEntry(
        branch=entry.branch,
        status=entry.status,
        task_id=entry.task_id,
        pr_url=entry.pr_url,
        commits=resolved,
    )

    # Update the full backports list, replacing only the matching branch
    _write_commits_to_metadata(tracker, source_task.identifier, updated_entry)

    return updated_entry


# ---------------------------------------------------------------------------
# Strategy implementations
# ---------------------------------------------------------------------------


def _resolve_via_scm(
    scm: "SCMProvider",
    repo: str,
    branch: str,
    source_identifier: str,
    target_branch: str,
) -> list[str]:
    """Find the merged PR for *branch* and return its commits via the SCM API.

    Returns an empty list when no merged PR is found or on any error.
    """
    try:
        pr = scm.find_pr_for_branch(repo, branch)
    except Exception as exc:
        logger.debug(
            "resolve_commits (SCM): find_pr_for_branch failed for %s branch %r: %s",
            source_identifier,
            branch,
            exc,
        )
        return []

    if pr is None:
        logger.debug(
            "resolve_commits (SCM): no PR found for %s branch %r",
            source_identifier,
            branch,
        )
        return []

    if pr.state != "merged":
        logger.debug(
            "resolve_commits (SCM): PR %s for %s branch %r is %r (not merged), skipping",
            pr.id,
            source_identifier,
            branch,
            pr.state,
        )
        return []

    try:
        commits = scm.get_review_commits(repo, pr.id)
    except Exception as exc:
        logger.debug(
            "resolve_commits (SCM): get_pr_commits failed for %s PR %s: %s",
            source_identifier,
            pr.id,
            exc,
        )
        return []

    if not commits:
        logger.debug(
            "resolve_commits (SCM): PR %s for %s → %s returned no commits",
            pr.id,
            source_identifier,
            target_branch,
        )
        return []

    logger.debug(
        "resolve_commits (SCM): resolved %d commit(s) for %s → %s via PR %s",
        len(commits),
        source_identifier,
        target_branch,
        pr.id,
    )
    return list(commits)


def _resolve_via_git(
    repo_path: str,
    branch: str,
    default_branch: str,
    source_identifier: str,
    target_branch: str,
) -> list[str]:
    """Run ``git rev-list`` to find commits on *branch* not on *default_branch*.

    Returns an empty list on any subprocess error or when no commits are found.
    """
    remote_branch = f"origin/{branch}"
    remote_default = f"origin/{default_branch}"
    try:
        result = subprocess.run(
            ["git", "rev-list", "--reverse", remote_branch, f"^{remote_default}"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        logger.debug(
            "resolve_commits (git): rev-list failed for %s branch %r: %s",
            source_identifier,
            branch,
            exc,
        )
        return []

    if result.returncode != 0:
        logger.debug(
            "resolve_commits (git): rev-list non-zero exit for %s branch %r: %s",
            source_identifier,
            branch,
            result.stderr.strip(),
        )
        return []

    commits = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not commits:
        logger.debug(
            "resolve_commits (git): no commits found on %r not on %r for %s → %s",
            remote_branch,
            remote_default,
            source_identifier,
            target_branch,
        )
        return []

    logger.debug(
        "resolve_commits (git): resolved %d commit(s) for %s → %s",
        len(commits),
        source_identifier,
        target_branch,
    )
    return commits


# ---------------------------------------------------------------------------
# Metadata write helper
# ---------------------------------------------------------------------------


def _write_commits_to_metadata(
    tracker: Any,
    source_identifier: str,
    updated_entry: BackportEntry,
) -> None:
    """Replace the matching BackportEntry in the source task's backports list.

    Reads the current ``oompah.backports`` from *tracker*, finds the entry
    whose ``branch`` matches *updated_entry.branch*, replaces it, and writes
    the updated list back.

    If no matching entry is found (e.g. it was removed concurrently), the
    *updated_entry* is appended to the list.

    Args:
        tracker: Tracker instance.
        source_identifier: Identifier of the source task.
        updated_entry: Updated entry with commits populated.
    """
    try:
        meta = tracker.get_metadata(source_identifier) or {}
    except Exception as exc:
        logger.warning(
            "resolve_and_record_commits: failed to read metadata for %s: %s",
            source_identifier,
            exc,
        )
        raise

    raw_backports = meta.get("oompah.backports")
    entries = parse_backports(raw_backports)

    replaced = False
    for i, e in enumerate(entries):
        if e.branch == updated_entry.branch:
            # Preserve all fields from the live entry but stamp the commits
            entries[i] = BackportEntry(
                branch=e.branch,
                status=e.status,
                task_id=e.task_id,
                pr_url=e.pr_url,
                commits=updated_entry.commits,
            )
            replaced = True
            break

    if not replaced:
        logger.debug(
            "_write_commits_to_metadata: branch %r not in current backports for %s, appending",
            updated_entry.branch,
            source_identifier,
        )
        entries.append(updated_entry)

    tracker.set_metadata_field(
        source_identifier,
        "oompah.backports",
        backports_to_raw(entries),
    )
    logger.debug(
        "resolve_and_record_commits: wrote %d commit(s) to %s → %s",
        len(updated_entry.commits),
        source_identifier,
        updated_entry.branch,
    )
