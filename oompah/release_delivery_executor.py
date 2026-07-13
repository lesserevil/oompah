"""Execute a claimed release delivery: cherry-pick, push, and open a PR (OOMPAH-195).

This module executes a :class:`~oompah.release_delivery_store.ReleaseDelivery`
from the ledger through the same cherry-pick/push/PR workflow as
:mod:`oompah.release_addendum_executor`, but all state is read and written
exclusively through the :class:`~oompah.release_delivery_store.ReleaseDeliveryStore`.

Design contract
---------------

*  The executor **first** checks whether the target branch is currently
   available.  If the target is no longer configured or no longer reachable
   remotely, the delivery is immediately transitioned to ``blocked`` with an
   actionable error — the cherry-pick is never attempted.
*  The work branch is derived deterministically from the delivery via
   :func:`~oompah.release_delivery_store.make_delivery_work_branch` and
   :func:`~oompah.release_delivery_store.make_delivery_worktree_key`, then
   persisted to the delivery record before any git operation.
*  The executor uses the immutable ``source_commits`` snapshot from the
   delivery; it never reads the source task's metadata.
*  All lifecycle transitions and evidence writes (work branch, PR URL/number,
   result commit SHAs, timestamps, errors) are performed via
   :meth:`~oompah.release_delivery_store.ReleaseDeliveryStore.update`.
*  On success, ``result_commits`` and ``pr_url``/``pr_number`` are persisted
   **before** transitioning to ``in_review``.
*  On conflict, the worktree is preserved and the delivery is transitioned to
   ``blocked`` with a diagnostic error.
*  **No child tracker task is created or modified.**
"""

from __future__ import annotations

import logging
import subprocess
from typing import TYPE_CHECKING, Any

from oompah.cherry_pick_pr_creator import (
    CherryPickConflictError,
    CherryPickError,
    _has_new_commits,
    apply_cherry_pick,
    push_branch,
)
from oompah.release_addendum_schema import AddendumStatus
from oompah.release_delivery_store import (
    ReleaseDelivery,
    ReleaseDeliveryStore,
    make_delivery_work_branch,
    make_delivery_worktree_key,
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

    Args:
        wt_path: Path to the git worktree.
        target_branch: Target release branch name (without the ``origin/``
            prefix).

    Returns:
        Ordered list of commit SHAs (oldest first) ahead of
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
    """Return an open PR for *work_branch*, or ``None``.

    Args:
        scm: SCM provider instance.
        repo: Repository slug (e.g. ``"org/repo"``).
        work_branch: The delivery's deterministic work branch name.

    Returns:
        An open PR object, or ``None`` when none exists or the query fails.
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


def _open_delivery_pr(
    scm: "SCMProvider",
    repo: str,
    delivery: ReleaseDelivery,
    *,
    source_title: str = "",
) -> tuple[str | None, str | None]:
    """Open a PR for the delivery's work branch against the target release branch.

    Args:
        scm: SCM provider instance.
        repo: Repository slug (e.g. ``"org/repo"``).
        delivery: The :class:`ReleaseDelivery` being executed.
        source_title: Human-readable source title for the PR title.

    Returns:
        A ``(pr_url, pr_number)`` tuple.  Either or both may be ``None``
        when the SCM call fails or returns no result.
    """
    source_label = delivery.source_identifier or delivery.id
    title = (
        f"{source_label}: Cherry-pick {source_title} to {delivery.target_branch}"
        if source_title
        else f"{source_label}: Release delivery to {delivery.target_branch}"
    )
    description = (
        f"Cherry-pick release delivery for {source_label} "
        + (f"({source_title}) " if source_title else "")
        + f"to `{delivery.target_branch}`.\n\n"
        f"Delivery ID: {delivery.id}\n"
        f"Commits: {', '.join(delivery.source_commits)}"
    )
    work_branch = delivery.work_branch or make_delivery_work_branch(delivery)

    try:
        result = scm.create_review(
            repo,
            title,
            work_branch,
            target_branch=delivery.target_branch,
            description=description,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "_open_delivery_pr: create_review failed for delivery %r → %s: %s",
            delivery.id,
            delivery.target_branch,
            exc,
        )
        return None, None

    if result is None:
        logger.warning(
            "_open_delivery_pr: create_review returned None for delivery %r → %s",
            delivery.id,
            delivery.target_branch,
        )
        return None, None

    pr_url = getattr(result, "url", None) or ""
    pr_number_raw = getattr(result, "id", None) or getattr(result, "number", None)
    pr_number = str(pr_number_raw) if pr_number_raw is not None else None
    logger.info(
        "_open_delivery_pr: opened PR for delivery %r → %s (id=%s url=%s)",
        delivery.id,
        delivery.target_branch,
        pr_number_raw,
        pr_url,
    )
    return (pr_url or None), pr_number


def _persist_blocked(
    store: ReleaseDeliveryStore,
    delivery_id: str,
    *,
    error: str,
) -> ReleaseDelivery | None:
    """Transition the delivery to ``blocked`` with a diagnostic error message.

    Args:
        store: The ledger store.
        delivery_id: The delivery to transition.
        error: Diagnostic message to store.

    Returns:
        The updated :class:`ReleaseDelivery` on success, or ``None`` when
        the transition write fails.
    """
    try:
        return store.update(
            delivery_id,
            status=AddendumStatus.BLOCKED,
            error=error,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "_persist_blocked: failed to transition delivery %r to blocked: %s",
            delivery_id,
            exc,
        )
        return None


def _is_target_available(
    delivery: ReleaseDelivery,
    *,
    project: Any,
    catalog: Any,
) -> tuple[bool, str]:
    """Check whether the delivery's target branch is currently available.

    Args:
        delivery: The :class:`ReleaseDelivery` to check.
        project: The project object (used to pass to the catalog).
        catalog: A :class:`~oompah.release_branch_catalog.ReleaseBranchCatalog`
            or ``None``.  When ``None``, the check is skipped and ``True`` is
            returned (for backward compatibility with tests that do not supply
            a catalog).

    Returns:
        ``(available, reason)`` where *reason* is an actionable error string
        when ``available`` is ``False``.
    """
    if catalog is None:
        return True, ""

    try:
        result = catalog.list_candidates(project)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "_is_target_available: catalog.list_candidates failed for delivery %r: %s",
            delivery.id,
            exc,
        )
        # Catalog error → do not block the delivery speculatively
        return True, ""

    branch_map = {b.name: b for b in result.branches}
    branch_entry = branch_map.get(delivery.target_branch)

    if branch_entry is None:
        return (
            False,
            f"Target branch {delivery.target_branch!r} is not configured as a "
            f"supported release branch for this project. "
            f"Add it to the project's supported_release_branches to enable delivery.",
        )

    if not branch_entry.available:
        return (
            False,
            f"Target branch {delivery.target_branch!r} is no longer available remotely. "
            f"It may have been deleted. Restore the branch or archive this delivery.",
        )

    return True, ""


# ---------------------------------------------------------------------------
# Public execution entry point
# ---------------------------------------------------------------------------


def cherry_pick_delivery(
    store: ReleaseDeliveryStore,
    delivery: ReleaseDelivery,
    *,
    project_store: "ProjectStore",
    project_id: str,
    scm: "SCMProvider",
    repo: str,
    source_title: str = "",
    project: Any = None,
    catalog: Any = None,
) -> ReleaseDelivery:
    """Apply cherry-pick commits, push the work branch, and open a release PR.

    Executes the full cherry-pick → push → PR-open pipeline for a single
    release delivery.  The caller must have already claimed the delivery
    (status is ``in_progress``) before calling this function.

    The executor checks target branch availability before any git operation
    and marks the delivery ``blocked`` immediately if the target is
    unconfigured or deleted.

    On success:
        - Persists ``work_branch``, ``result_commits``, ``pr_url``,
          ``pr_number`` on the delivery.
        - Transitions the delivery to ``in_review``.
        - Returns the updated delivery.

    On unavailable target:
        - Transitions the delivery to ``blocked`` with an actionable error.
        - Returns the updated delivery (or the original on write failure).

    On cherry-pick conflict:
        - Preserves the conflicted worktree with conflict markers intact.
        - Transitions the delivery to ``blocked`` with a diagnostic error.
        - Returns the updated delivery.

    On other execution failures:
        - Transitions the delivery to ``blocked`` with a diagnostic error.
        - Returns the updated delivery.

    **No child tracker task is created or modified.**

    Args:
        store: The :class:`~oompah.release_delivery_store.ReleaseDeliveryStore`
            for reading/writing delivery state.
        delivery: The :class:`ReleaseDelivery` to execute.  Must be
            ``in_progress``.
        project_store: Used to create or locate the release worktree.
        project_id: Project identifier for worktree path resolution.
        scm: SCM provider for finding existing PRs and opening new ones.
        repo: Repository slug (e.g. ``"org/repo"``).
        source_title: Human-readable title for the PR (optional).
        project: Project object passed to *catalog* for branch discovery.
            When ``None``, the availability check is skipped.
        catalog: Optional
            :class:`~oompah.release_branch_catalog.ReleaseBranchCatalog`
            for checking whether the target branch is still available.
            When ``None``, the check is skipped.

    Returns:
        The updated :class:`ReleaseDelivery`.  On success the status is
        ``in_review``; on failure the status is ``blocked``.
    """
    delivery_id = delivery.id

    # ------------------------------------------------------------------
    # Step 0: Check target branch availability.
    # ------------------------------------------------------------------
    if catalog is not None:
        available, reason = _is_target_available(delivery, project=project, catalog=catalog)
        if not available:
            logger.warning(
                "cherry_pick_delivery: %r: target branch %r unavailable: %s",
                delivery_id,
                delivery.target_branch,
                reason,
            )
            result = _persist_blocked(store, delivery_id, error=reason)
            return result if result is not None else delivery

    # ------------------------------------------------------------------
    # Step 1: Determine and persist the deterministic work branch.
    # ------------------------------------------------------------------
    work_branch = delivery.work_branch or make_delivery_work_branch(delivery)
    worktree_key = make_delivery_worktree_key(delivery)

    if delivery.work_branch is None:
        try:
            delivery = store.update(delivery_id, work_branch=work_branch)
        except Exception as exc:  # noqa: BLE001
            error = f"Failed to persist work_branch for delivery {delivery_id!r}: {exc}"
            logger.warning("cherry_pick_delivery: %s", error)
            result = _persist_blocked(store, delivery_id, error=str(error)[:600])
            return result if result is not None else delivery

    # ------------------------------------------------------------------
    # Step 2: Create or reuse the deterministic release worktree.
    # ------------------------------------------------------------------
    try:
        wt_path = project_store.create_worktree(
            project_id,
            worktree_key,
            base_branch=delivery.target_branch,
            branch_name=work_branch,
        )
    except Exception as exc:  # noqa: BLE001
        error = (
            f"Failed to create release worktree for {delivery.target_branch!r}: {exc}"
        )
        logger.warning(
            "cherry_pick_delivery: %r → %s: %s",
            delivery_id,
            delivery.target_branch,
            error,
        )
        result = _persist_blocked(store, delivery_id, error=str(error)[:600])
        return result if result is not None else delivery

    # ------------------------------------------------------------------
    # Step 3: Check for an existing PR — reuse it instead of opening another.
    # ------------------------------------------------------------------
    existing_pr = _find_existing_pr(scm, repo, work_branch)
    if existing_pr is not None:
        pr_url = getattr(existing_pr, "url", None) or ""
        pr_number_raw = getattr(existing_pr, "id", None) or getattr(existing_pr, "number", None)
        pr_number = str(pr_number_raw) if pr_number_raw is not None else None
        logger.info(
            "cherry_pick_delivery: %r → %s: reusing existing PR %s (%s)",
            delivery_id,
            delivery.target_branch,
            pr_number_raw,
            pr_url,
        )
        result_commits = _get_result_commits(wt_path, delivery.target_branch)
        try:
            updated = store.update(
                delivery_id,
                status=AddendumStatus.IN_REVIEW,
                pr_url=pr_url or None,
                pr_number=pr_number,
                result_commits=result_commits,
            )
            return updated
        except Exception as exc:  # noqa: BLE001
            error = f"Failed to persist in_review after finding existing PR: {exc}"
            logger.warning("cherry_pick_delivery: %r: %s", delivery_id, error)
            result = _persist_blocked(store, delivery_id, error=str(error)[:600])
            return result if result is not None else delivery

    # ------------------------------------------------------------------
    # Step 4: Cherry-pick the persisted commit snapshot onto the worktree.
    # The immutable source_commits list is used — never re-resolved from
    # task metadata.
    # ------------------------------------------------------------------
    if not _has_new_commits(wt_path, delivery.target_branch):
        try:
            apply_cherry_pick(wt_path, delivery.source_commits)
        except CherryPickConflictError as exc:
            # Preserve the worktree — leave conflict markers intact.
            error = (
                f"Cherry-pick conflict applying commits "
                f"{delivery.source_commits!r} to {delivery.target_branch!r}: {exc}"
            )
            logger.warning(
                "cherry_pick_delivery: %r → %s: conflict — worktree preserved at %s",
                delivery_id,
                delivery.target_branch,
                wt_path,
            )
            result = _persist_blocked(store, delivery_id, error=str(error)[:600])
            return result if result is not None else delivery

        except CherryPickError as exc:
            # Non-conflict failure (bad SHA, missing object, etc.).
            error = (
                f"Cherry-pick failed for commits "
                f"{delivery.source_commits!r} → {delivery.target_branch!r}: {exc}"
            )
            logger.warning(
                "cherry_pick_delivery: %r → %s: non-conflict failure: %s",
                delivery_id,
                delivery.target_branch,
                exc,
            )
            result = _persist_blocked(store, delivery_id, error=str(error)[:600])
            return result if result is not None else delivery

        except Exception as exc:  # noqa: BLE001
            error = f"Unexpected error during cherry-pick: {exc}"
            logger.warning(
                "cherry_pick_delivery: %r → %s: unexpected error: %s",
                delivery_id,
                delivery.target_branch,
                exc,
            )
            result = _persist_blocked(store, delivery_id, error=str(error)[:600])
            return result if result is not None else delivery

    # ------------------------------------------------------------------
    # Step 5: Push the work branch to origin.
    # ------------------------------------------------------------------
    try:
        push_branch(wt_path, work_branch)
    except Exception as exc:  # noqa: BLE001
        error = f"Failed to push {work_branch!r}: {exc}"
        logger.warning(
            "cherry_pick_delivery: %r → %s: push failed: %s",
            delivery_id,
            delivery.target_branch,
            exc,
        )
        result = _persist_blocked(store, delivery_id, error=str(error)[:600])
        return result if result is not None else delivery

    # ------------------------------------------------------------------
    # Step 6: Open a PR targeting <target_branch>.
    # ------------------------------------------------------------------
    pr_url, pr_number = _open_delivery_pr(scm, repo, delivery, source_title=source_title)

    # ------------------------------------------------------------------
    # Step 7: Collect result_commits (what was applied ahead of target).
    # ------------------------------------------------------------------
    result_commits = _get_result_commits(wt_path, delivery.target_branch)

    # ------------------------------------------------------------------
    # Step 8: Persist result evidence and transition to in_review atomically.
    # ------------------------------------------------------------------
    try:
        updated = store.update(
            delivery_id,
            status=AddendumStatus.IN_REVIEW,
            pr_url=pr_url,
            pr_number=pr_number,
            result_commits=result_commits,
        )
        logger.info(
            "cherry_pick_delivery: %r → %s: succeeded (pr=%s commits=%d)",
            delivery_id,
            delivery.target_branch,
            pr_url,
            len(result_commits),
        )
        return updated
    except Exception as exc:  # noqa: BLE001
        error = f"Failed to persist in_review after push+PR: {exc}"
        logger.warning(
            "cherry_pick_delivery: %r → %s: persist failed: %s",
            delivery_id,
            delivery.target_branch,
            exc,
        )
        result = _persist_blocked(store, delivery_id, error=str(error)[:600])
        return result if result is not None else delivery
