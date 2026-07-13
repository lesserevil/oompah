"""PR polling for release addendums (OOMPAH-179).

Reconciles ``in_review`` addendum state against the actual PR outcome:

- **merged PR** → transition to ``merged``, record ``completed_at``, post
  oompah-authored comment on the source task.
- **closed-unmerged PR** → update ``error`` field in-place *without* changing
  status; post a comment directing the operator to use the retry action.  The
  addendum stays ``in_review`` until explicit retry.
- **open PR** → no change.
- **already terminal addendum** → idempotent no-op.

Design invariants
-----------------

- Calling :func:`poll_addendum_pr` twice with the same PR state is safe (the
  "closed" path is idempotent: it checks the stored ``error`` value before
  writing).
- Commits are *never* touched.  The snapshot persisted at approval time is
  the only authoritative list.
- No child tracker task is created; the source task's own status is never
  altered.
- All comments are posted with ``author="oompah"``.
"""

from __future__ import annotations

import dataclasses
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from oompah.release_addendum_schema import (
    AddendumRepository,
    AddendumStatus,
    InvalidTransitionError,
    ReleaseAddendum,
)

if TYPE_CHECKING:
    from oompah.scm import SCMProvider

logger = logging.getLogger(__name__)

# Stable prefix used by the closed-unmerged detector so the retry endpoint
# (and tests) can recognise the sentinel without a string literal dependency.
CLOSED_UNMERGED_ERROR_PREFIX = "PR closed without merge:"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _post_source_comment(
    tracker: Any,
    source_identifier: str,
    message: str,
) -> None:
    """Post *message* on the source task as the ``oompah`` author.

    Swallows exceptions — a failed comment must not prevent the state
    transition from being recorded.

    Args:
        tracker: Tracker instance.
        source_identifier: Source task or epic identifier.
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


def _update_addendum_evidence(
    tracker: Any,
    source_identifier: str,
    addendum_id: str,
    **evidence: Any,
) -> ReleaseAddendum | None:
    """Update execution-evidence fields on an addendum WITHOUT changing status.

    Reads the current addendum list, replaces the specified fields on the
    matching entry, and writes the list back atomically.

    Only fields present in *evidence* are changed; all other fields including
    ``commits`` and ``status`` are preserved.

    Args:
        tracker: Tracker instance.
        source_identifier: Source task or epic identifier.
        addendum_id: Stable addendum ``id`` to locate.
        **evidence: Field values to overwrite (e.g. ``error="…"``).

    Returns:
        The updated :class:`ReleaseAddendum` on success, or ``None`` when
        *addendum_id* is not found in the stored list.

    Raises:
        Propagates tracker errors from :meth:`AddendumRepository.write`.
    """
    repo = AddendumRepository(tracker)
    current = repo.read(source_identifier)
    idx = next((i for i, a in enumerate(current) if a.id == addendum_id), None)
    if idx is None:
        return None
    updated_addendum = dataclasses.replace(current[idx], **evidence)
    current[idx] = updated_addendum
    repo.write(source_identifier, current)
    return updated_addendum


# ---------------------------------------------------------------------------
# Core poll function
# ---------------------------------------------------------------------------


def poll_addendum_pr(
    tracker: Any,
    source_identifier: str,
    addendum: ReleaseAddendum,
    *,
    scm: "SCMProvider",
    repo: str,
    now: datetime | None = None,
) -> ReleaseAddendum:
    """Poll the PR for a single ``in_review`` addendum and update its state.

    This function is the atomic unit of PR reconciliation.  The orchestrator
    calls it once per ``in_review`` addendum on each reconciliation pass; it
    may also be triggered from an SCM webhook that signals a PR state change.

    Behaviour by PR state
    ---------------------

    ``merged``
        Transition the addendum to :attr:`~AddendumStatus.MERGED`, set
        ``completed_at``, and post an oompah comment on the source task.
        If the addendum is *already* ``merged`` (concurrent call), re-read
        and return without error.

    ``closed``
        Mark ``error`` field with :data:`CLOSED_UNMERGED_ERROR_PREFIX` + the
        PR URL and post an oompah comment explaining the close and how to
        retry.  Status remains ``in_review``; no replacement PR is opened.
        Idempotent: if ``error`` already contains the closed marker, skip.

    ``open`` or unknown
        No change; return the addendum unchanged.

    Not ``in_review``
        No-op; return immediately.

    Args:
        tracker: Tracker instance for reading/writing addendum metadata and
            posting comments.
        source_identifier: Source task or epic identifier (e.g. ``"FOO-10"``).
        addendum: The :class:`ReleaseAddendum` to poll.  Anything other than
            ``in_review`` is returned unchanged.
        scm: SCM provider for querying the PR state.
        repo: Repository slug (e.g. ``"org/repo"``).
        now: UTC timestamp override for ``completed_at``; defaults to
            :func:`~datetime.datetime.now`.

    Returns:
        The (possibly updated) :class:`ReleaseAddendum`.
    """
    if addendum.status is not AddendumStatus.IN_REVIEW:
        return addendum

    if not addendum.pr_url:
        logger.debug(
            "poll_addendum_pr: %s %r has no pr_url; skipping",
            source_identifier,
            addendum.id,
        )
        return addendum

    now = now or datetime.now(timezone.utc)

    # ------------------------------------------------------------------
    # Query the SCM for current PR state
    # ------------------------------------------------------------------
    try:
        pr = scm.find_pr_for_branch(repo, addendum.work_branch)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "poll_addendum_pr: %s %r: find_pr_for_branch failed: %s",
            source_identifier,
            addendum.id,
            exc,
        )
        return addendum

    if pr is None:
        # No PR found (deleted or not yet created) — leave unchanged.
        logger.debug(
            "poll_addendum_pr: %s %r: no PR found for branch %r",
            source_identifier,
            addendum.id,
            addendum.work_branch,
        )
        return addendum

    pr_state = (getattr(pr, "state", "") or "").lower()

    # ------------------------------------------------------------------
    # Handle each possible PR state
    # ------------------------------------------------------------------

    if pr_state == "merged":
        return _handle_merged(tracker, source_identifier, addendum, now=now)

    if pr_state == "closed":
        return _handle_closed(tracker, source_identifier, addendum)

    # PR is open or state is unrecognised — no change.
    return addendum


# ---------------------------------------------------------------------------
# Per-state handlers
# ---------------------------------------------------------------------------


def _handle_merged(
    tracker: Any,
    source_identifier: str,
    addendum: ReleaseAddendum,
    *,
    now: datetime,
) -> ReleaseAddendum:
    """Transition *addendum* to MERGED after a confirmed PR merge.

    Posts an oompah comment on the source task.

    Args:
        tracker: Tracker instance.
        source_identifier: Source task identifier.
        addendum: The ``in_review`` addendum.
        now: UTC timestamp for ``completed_at``.

    Returns:
        Updated (``merged``) addendum.
    """
    try:
        repo = AddendumRepository(tracker)
        updated = repo.transition(
            source_identifier,
            addendum.id,
            AddendumStatus.MERGED,
            completed_at=now.isoformat(),
        )
        result = next(a for a in updated if a.id == addendum.id)
    except InvalidTransitionError:
        # Race condition: another poller already transitioned — re-read.
        logger.debug(
            "_handle_merged: %s %r: already merged; transition skipped",
            source_identifier,
            addendum.id,
        )
        repo = AddendumRepository(tracker)
        current = repo.read(source_identifier)
        return next((a for a in current if a.id == addendum.id), addendum)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "_handle_merged: %s %r: failed to transition to merged: %s",
            source_identifier,
            addendum.id,
            exc,
        )
        return addendum

    _post_source_comment(
        tracker,
        source_identifier,
        (
            f"✅ Release addendum for `{addendum.target_branch}` merged.\n\n"
            f"PR: {addendum.pr_url}\n"
            f"Branch: `{addendum.target_branch}`"
        ),
    )
    return result


def _handle_closed(
    tracker: Any,
    source_identifier: str,
    addendum: ReleaseAddendum,
) -> ReleaseAddendum:
    """Update the error field when the PR was closed without merge.

    Status remains ``in_review``; no automatic transition or replacement PR.
    Idempotent: if the error field already contains the closed marker, skip.

    Args:
        tracker: Tracker instance.
        source_identifier: Source task identifier.
        addendum: The ``in_review`` addendum.

    Returns:
        Updated addendum (same status, new error message) or the original when
        already marked or the write fails.
    """
    error_msg = f"{CLOSED_UNMERGED_ERROR_PREFIX} {addendum.pr_url}"

    # Idempotent: already recorded.
    if addendum.error and addendum.error.startswith(CLOSED_UNMERGED_ERROR_PREFIX):
        return addendum

    try:
        updated = _update_addendum_evidence(
            tracker,
            source_identifier,
            addendum.id,
            error=error_msg,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "_handle_closed: %s %r: failed to update error for closed PR: %s",
            source_identifier,
            addendum.id,
            exc,
        )
        return addendum

    if updated is None:
        return addendum

    _post_source_comment(
        tracker,
        source_identifier,
        (
            f"⚠️ Release addendum PR for `{addendum.target_branch}` was closed without merge.\n\n"
            f"PR: {addendum.pr_url}\n"
            f"Branch: `{addendum.target_branch}`\n\n"
            f"No replacement PR has been opened automatically. "
            f"Use the **retry** action to re-queue this addendum and open a new PR."
        ),
    )
    return updated
