"""Execute a claimed release addendum: cherry-pick, push, and open a PR.

This module extracts the generic cherry-pick/push/PR operations from the
legacy release-pick reconciler (``cherry_pick_pr_creator``) so they operate
directly on a :class:`~oompah.release_addendum_schema.ReleaseAddendum`
without touching child tasks or backport metadata (section 8 of
``plans/release-branch-addendums.md``).

Design contract
---------------

*  The worktree is created (or reused) deterministically from the addendum's
   ``worktree_key`` and ``work_branch`` fields, rooted at
   ``origin/<target_branch>``.
*  An existing PR for ``work_branch`` is reused rather than opening a second
   one.
*  On success the addendum is transitioned to ``in_review`` with ``pr_url``
   and ``result_commits`` persisted.
*  On cherry-pick conflict the worktree is **preserved** (conflict markers
   left intact for operator inspection), the addendum is transitioned to
   ``blocked`` with a diagnostic, and an actionable comment is posted on the
   source task.
*  On any other execution failure the addendum is similarly transitioned to
   ``blocked`` with a diagnostic comment on the source task.
*  **No child tracker task is ever created or modified.** The source task's
   own status (``Merged``) is never altered.

The caller (orchestrator queue worker) is responsible for holding the
in-progress lease before calling :func:`cherry_pick_addendum` and for
releasing it on success or terminal failure.
"""

from __future__ import annotations

import logging
import subprocess
from typing import TYPE_CHECKING, Any

from oompah.cherry_pick_pr_creator import (
    CherryPickConflictError,
    CherryPickError,
    apply_cherry_pick,
    push_branch,
    _has_new_commits,
)
from oompah.release_addendum_schema import (
    AddendumRepository,
    AddendumStatus,
    ReleaseAddendum,
)

if TYPE_CHECKING:
    from oompah.projects import ProjectStore
    from oompah.scm import SCMProvider

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_result_commits(wt_path: str, target_branch: str) -> list[str]:
    """Return the SHAs on HEAD that are not in ``origin/<target_branch>``.

    These are the commits cherry-picked onto the work branch, captured as
    evidence at ``in_review`` time.

    Args:
        wt_path: Path to the git worktree.
        target_branch: Target release branch name (without the ``origin/``
            prefix).

    Returns:
        Ordered list of commit SHAs (oldest first) that are ahead of
        ``origin/<target_branch>``.  Returns an empty list on any error.
    """
    try:
        result = subprocess.run(
            ["git", "rev-list", "--reverse", "HEAD", f"^origin/{target_branch}"],
            cwd=wt_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return [s.strip() for s in result.stdout.splitlines() if s.strip()]
    except Exception:  # noqa: BLE001
        pass
    return []


def _find_existing_pr(
    scm: "SCMProvider",
    repo: str,
    work_branch: str,
) -> Any:
    """Query the SCM for an existing open PR whose source branch is ``work_branch``.

    Args:
        scm: SCM provider instance.
        repo: Repository slug (e.g. ``"org/repo"``).
        work_branch: The addendum's deterministic work branch name.

    Returns:
        A :class:`~oompah.scm.ReviewRequest` when an open PR exists, or
        ``None`` when no PR is found or the query fails.
    """
    try:
        pr = scm.find_pr_for_branch(repo, work_branch)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "_find_existing_pr: find_pr_for_branch failed for branch %r: %s",
            work_branch,
            exc,
        )
        return None

    if pr is None:
        return None

    pr_state = (getattr(pr, "state", "") or "").lower()
    if pr_state == "open":
        return pr

    return None


def _open_release_pr(
    scm: "SCMProvider",
    repo: str,
    source_identifier: str,
    source_title: str,
    addendum: ReleaseAddendum,
) -> str | None:
    """Open a PR for the addendum's work branch against the target release branch.

    Args:
        scm: SCM provider instance.
        repo: Repository slug (e.g. ``"org/repo"``).
        source_identifier: Source task identifier (e.g. ``"FOO-10"``).
        source_title: Human-readable source task title (used in PR title).
        addendum: The :class:`ReleaseAddendum` being executed.

    Returns:
        The PR URL string on success, or ``None`` when the SCM call fails or
        returns no result.
    """
    title = (
        f"{source_identifier}: Cherry-pick {source_title} to {addendum.target_branch}"
        if source_title
        else f"{source_identifier}: Release addendum to {addendum.target_branch}"
    )
    description = (
        f"Cherry-pick release addendum for {source_identifier} "
        f"({source_title}) to `{addendum.target_branch}`.\n\n"
        f"Source task: {source_identifier}\n"
        f"Commits: {', '.join(addendum.commits)}"
    )

    try:
        result = scm.create_review(
            repo,
            title,
            addendum.work_branch,
            target_branch=addendum.target_branch,
            description=description,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "_open_release_pr: create_review failed for %s → %s: %s",
            source_identifier,
            addendum.target_branch,
            exc,
        )
        return None

    if result is None:
        logger.warning(
            "_open_release_pr: create_review returned None for %s → %s",
            source_identifier,
            addendum.target_branch,
        )
        return None

    pr_url = getattr(result, "url", None) or ""
    logger.info(
        "_open_release_pr: opened PR for %s → %s (id=%s url=%s)",
        source_identifier,
        addendum.target_branch,
        getattr(result, "id", "?"),
        pr_url,
    )
    return pr_url or None


def _post_source_comment(
    tracker: Any,
    source_identifier: str,
    message: str,
) -> None:
    """Post *message* on the source task as the ``oompah`` author.

    Failures are caught and logged — the caller must not fail because a
    comment could not be posted.

    Args:
        tracker: Tracker instance.
        source_identifier: Source task identifier.
        message: Markdown comment body.
    """
    try:
        tracker.add_comment(source_identifier, message, author="oompah")
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "_post_source_comment: failed to post comment on %s: %s",
            source_identifier,
            exc,
        )


def _persist_blocked(
    tracker: Any,
    source_identifier: str,
    addendum: ReleaseAddendum,
    *,
    error: str,
) -> ReleaseAddendum:
    """Transition the addendum to ``blocked`` with a diagnostic error message.

    Args:
        tracker: Tracker instance.
        source_identifier: Source task identifier.
        addendum: The addendum to transition.
        error: Diagnostic message to store.

    Returns:
        The updated :class:`ReleaseAddendum` after the transition, or the
        original when the transition write fails.
    """
    try:
        repo = AddendumRepository(tracker)
        updated = repo.transition(
            source_identifier,
            addendum.id,
            AddendumStatus.BLOCKED,
            error=error,
        )
        return next(a for a in updated if a.id == addendum.id)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "_persist_blocked: failed to transition %r to blocked: %s",
            addendum.id,
            exc,
        )
        return addendum


# ---------------------------------------------------------------------------
# Public execution entry point
# ---------------------------------------------------------------------------


def cherry_pick_addendum(
    tracker: Any,
    source_identifier: str,
    addendum: ReleaseAddendum,
    *,
    project_store: "ProjectStore",
    project_id: str,
    scm: "SCMProvider",
    repo: str,
    source_title: str = "",
) -> ReleaseAddendum:
    """Apply cherry-pick commits, push the work branch, and open a release PR.

    Executes the full cherry-pick → push → PR-open pipeline for a single
    release addendum.  The caller must have already claimed the addendum
    (status is ``in_progress``) before calling this function.

    On success:
        - Transitions the addendum to ``in_review``.
        - Persists ``pr_url`` and ``result_commits`` on the addendum.
        - Returns the updated addendum.

    On cherry-pick conflict:
        - Preserves the conflicted worktree with conflict markers intact.
        - Transitions the addendum to ``blocked`` with a diagnostic error.
        - Posts an actionable comment on the source task.
        - Returns the updated addendum.

    On other execution failures:
        - Transitions the addendum to ``blocked`` with a diagnostic error.
        - Posts an actionable comment on the source task.
        - Returns the updated addendum (or the original when the transition
          write itself fails).

    **No child task is created.** The source task's status is never altered.

    Args:
        tracker: Tracker instance for reading/writing addendum metadata and
            posting comments.
        source_identifier: Identifier of the source task or epic (e.g.
            ``"FOO-10"``).
        addendum: The :class:`ReleaseAddendum` to execute.  Must be
            ``in_progress``.
        project_store: Used to create or locate the release worktree.
        project_id: Project identifier for worktree path resolution.
        scm: SCM provider for finding existing PRs and opening new ones.
        repo: Repository slug (e.g. ``"org/repo"``).
        source_title: Human-readable source task title for the PR title.

    Returns:
        The updated :class:`ReleaseAddendum` after execution.  On success
        the status is ``in_review``; on failure the status is ``blocked``.
    """
    # ------------------------------------------------------------------
    # Step 1: Create or reuse the deterministic release worktree.
    # Rooted at origin/<target_branch> with the addendum's work_branch.
    # ------------------------------------------------------------------
    try:
        wt_path = project_store.create_worktree(
            project_id,
            addendum.worktree_key,
            base_branch=addendum.target_branch,
            branch_name=addendum.work_branch,
        )
    except Exception as exc:  # noqa: BLE001
        error = (
            f"Failed to create release worktree for {addendum.target_branch!r}: {exc}"
        )
        logger.warning(
            "cherry_pick_addendum: %s → %s: %s",
            source_identifier,
            addendum.target_branch,
            error,
        )
        _post_source_comment(
            tracker,
            source_identifier,
            (
                f"⚠️ **Release addendum blocked** for branch `{addendum.target_branch}`.\n\n"
                f"Could not create the release worktree:\n```\n{exc}\n```\n\n"
                f"Source task: {source_identifier}"
            ),
        )
        return _persist_blocked(
            tracker, source_identifier, addendum, error=str(error)
        )

    # ------------------------------------------------------------------
    # Step 2: Check for an existing PR — reuse it instead of opening another.
    # ------------------------------------------------------------------
    existing_pr = _find_existing_pr(scm, repo, addendum.work_branch)
    if existing_pr is not None:
        pr_url = getattr(existing_pr, "url", None) or ""
        logger.info(
            "cherry_pick_addendum: %s → %s: reusing existing PR %s (%s)",
            source_identifier,
            addendum.target_branch,
            getattr(existing_pr, "id", "?"),
            pr_url,
        )
        result_commits = _get_result_commits(wt_path, addendum.target_branch)
        try:
            repo_obj = AddendumRepository(tracker)
            updated = repo_obj.transition(
                source_identifier,
                addendum.id,
                AddendumStatus.IN_REVIEW,
                pr_url=pr_url or None,
                result_commits=result_commits,
            )
            return next(a for a in updated if a.id == addendum.id)
        except Exception as exc:  # noqa: BLE001
            error = f"Failed to persist in_review after finding existing PR: {exc}"
            logger.warning(
                "cherry_pick_addendum: %s → %s: %s",
                source_identifier,
                addendum.target_branch,
                error,
            )
            return _persist_blocked(
                tracker, source_identifier, addendum, error=str(error)
            )

    # ------------------------------------------------------------------
    # Step 3: Cherry-pick the persisted commit snapshot onto the worktree.
    # apply_cherry_pick is idempotent: it skips when commits already exist
    # and raises CherryPickConflictError when CHERRY_PICK_HEAD is present.
    # For the addendum case we also check explicitly since the upstream
    # tracking may not be set before the first push.
    # ------------------------------------------------------------------
    if not _has_new_commits(wt_path, addendum.target_branch):
        try:
            apply_cherry_pick(wt_path, addendum.commits)
        except CherryPickConflictError as exc:
            # Preserve the worktree — leave conflict markers intact.
            error = (
                f"Cherry-pick conflict applying commits "
                f"{addendum.commits!r} to {addendum.target_branch!r}: {exc}"
            )
            logger.warning(
                "cherry_pick_addendum: %s → %s: conflict — worktree preserved at %s",
                source_identifier,
                addendum.target_branch,
                wt_path,
            )
            _post_source_comment(
                tracker,
                source_identifier,
                (
                    f"⚠️ **Release addendum conflict** for branch `{addendum.target_branch}`.\n\n"
                    f"The cherry-pick of {source_identifier} onto "
                    f"`{addendum.target_branch}` produced merge conflicts.\n\n"
                    f"The worktree at `{wt_path}` has been **preserved** with conflict "
                    f"markers in place. Resolve the conflicts, then retry:\n\n"
                    f"```\ngit cherry-pick --continue\ngit push\n```\n\n"
                    f"Commits: `{', '.join(addendum.commits)}`\n\n"
                    f"Conflict details:\n```\n{str(exc)[:400]}\n```"
                ),
            )
            return _persist_blocked(
                tracker, source_identifier, addendum, error=str(error)[:600]
            )
        except CherryPickError as exc:
            # Non-conflict failure (bad SHA, missing object, etc.).
            error = (
                f"Cherry-pick failed for commits "
                f"{addendum.commits!r} → {addendum.target_branch!r}: {exc}"
            )
            logger.warning(
                "cherry_pick_addendum: %s → %s: non-conflict failure: %s",
                source_identifier,
                addendum.target_branch,
                exc,
            )
            _post_source_comment(
                tracker,
                source_identifier,
                (
                    f"⚠️ **Release addendum blocked** for branch `{addendum.target_branch}`.\n\n"
                    f"Cherry-pick failed with a non-conflict error:\n```\n{str(exc)[:400]}\n```\n\n"
                    f"Commits: `{', '.join(addendum.commits)}`\n\n"
                    f"Source task: {source_identifier}"
                ),
            )
            return _persist_blocked(
                tracker, source_identifier, addendum, error=str(error)[:600]
            )
        except Exception as exc:  # noqa: BLE001
            # Unexpected failure during cherry-pick.
            error = f"Unexpected error during cherry-pick: {exc}"
            logger.warning(
                "cherry_pick_addendum: %s → %s: unexpected error: %s",
                source_identifier,
                addendum.target_branch,
                exc,
            )
            _post_source_comment(
                tracker,
                source_identifier,
                (
                    f"⚠️ **Release addendum blocked** for branch `{addendum.target_branch}`.\n\n"
                    f"Unexpected error during cherry-pick:\n```\n{str(exc)[:400]}\n```\n\n"
                    f"Source task: {source_identifier}"
                ),
            )
            return _persist_blocked(
                tracker, source_identifier, addendum, error=str(error)[:600]
            )

    # ------------------------------------------------------------------
    # Step 4: Push the work branch to origin.
    # ------------------------------------------------------------------
    try:
        push_branch(wt_path, addendum.work_branch)
    except Exception as exc:  # noqa: BLE001
        error = f"Failed to push {addendum.work_branch!r}: {exc}"
        logger.warning(
            "cherry_pick_addendum: %s → %s: push failed: %s",
            source_identifier,
            addendum.target_branch,
            exc,
        )
        _post_source_comment(
            tracker,
            source_identifier,
            (
                f"⚠️ **Release addendum blocked** for branch `{addendum.target_branch}`.\n\n"
                f"Failed to push work branch `{addendum.work_branch}`:\n```\n{str(exc)[:400]}\n```\n\n"
                f"Source task: {source_identifier}"
            ),
        )
        return _persist_blocked(
            tracker, source_identifier, addendum, error=str(error)[:600]
        )

    # ------------------------------------------------------------------
    # Step 5: Open a PR targeting <target_branch>.
    # ------------------------------------------------------------------
    pr_url = _open_release_pr(scm, repo, source_identifier, source_title, addendum)

    # ------------------------------------------------------------------
    # Step 6: Collect result_commits (what was applied ahead of target).
    # ------------------------------------------------------------------
    result_commits = _get_result_commits(wt_path, addendum.target_branch)

    # ------------------------------------------------------------------
    # Step 7: Persist in_review + execution evidence.
    # ------------------------------------------------------------------
    try:
        repo_obj = AddendumRepository(tracker)
        updated = repo_obj.transition(
            source_identifier,
            addendum.id,
            AddendumStatus.IN_REVIEW,
            pr_url=pr_url,
            result_commits=result_commits,
        )
        result = next(a for a in updated if a.id == addendum.id)
        logger.info(
            "cherry_pick_addendum: %s → %s: succeeded (pr=%s commits=%d)",
            source_identifier,
            addendum.target_branch,
            pr_url,
            len(result_commits),
        )
        return result
    except Exception as exc:  # noqa: BLE001
        error = f"Failed to persist in_review after push+PR: {exc}"
        logger.warning(
            "cherry_pick_addendum: %s → %s: persist failed: %s",
            source_identifier,
            addendum.target_branch,
            exc,
        )
        return _persist_blocked(
            tracker, source_identifier, addendum, error=str(error)[:600]
        )
