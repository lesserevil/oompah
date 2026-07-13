"""PR polling for release deliveries (OOMPAH-195).

Reconciles ``in_review`` delivery state against the actual PR outcome,
writing all transitions through the
:class:`~oompah.release_delivery_store.ReleaseDeliveryStore`:

- **merged PR** → transition to ``merged``, record ``completed_at``.
- **closed-unmerged PR** → update ``error`` field in-place *without* changing
  status; post no external comment (the operator can retry via the retry API).
  The delivery stays ``in_review`` until explicit retry.
- **open PR** → no change.
- **already terminal delivery** → idempotent no-op.

Design invariants
-----------------

- Calling :func:`poll_delivery_pr` twice with the same PR state is safe (the
  "closed" path checks the stored ``error`` value before writing).
- ``source_commits`` is **never** modified by the poller.
- No child tracker task is created; no source task status is altered.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from oompah.release_addendum_schema import AddendumStatus, InvalidTransitionError
from oompah.release_delivery_store import ReleaseDelivery, ReleaseDeliveryStore

if TYPE_CHECKING:
    from oompah.scm import SCMProvider

logger = logging.getLogger(__name__)

#: Stable prefix used by the closed-unmerged detector so the retry endpoint
#: (and tests) can recognise the sentinel without a string literal dependency.
CLOSED_UNMERGED_ERROR_PREFIX = "PR closed without merge:"


# ---------------------------------------------------------------------------
# Core poll function
# ---------------------------------------------------------------------------


def poll_delivery_pr(
    store: ReleaseDeliveryStore,
    delivery: ReleaseDelivery,
    *,
    scm: "SCMProvider",
    repo: str,
    now: datetime | None = None,
) -> ReleaseDelivery:
    """Poll the PR for a single ``in_review`` delivery and update its state.

    This is the atomic unit of PR reconciliation.  Call it once per
    ``in_review`` delivery on each reconciliation pass or from a SCM webhook.

    Behaviour by PR state
    ---------------------

    ``merged``
        Transition the delivery to ``merged``, set ``completed_at``.
        If the delivery is *already* ``merged`` (concurrent call), re-read
        and return without error.

    ``closed``
        Mark ``error`` field with :data:`CLOSED_UNMERGED_ERROR_PREFIX` + the
        PR URL.  Status remains ``in_review``; no replacement PR is opened.
        Idempotent: if ``error`` already contains the closed marker, skip.

    ``open`` or unknown
        No change; return the delivery unchanged.

    Not ``in_review``
        No-op; return immediately.

    Args:
        store: The :class:`~oompah.release_delivery_store.ReleaseDeliveryStore`
            for reading/writing delivery state.
        delivery: The :class:`ReleaseDelivery` to poll.  Anything other than
            ``in_review`` is returned unchanged.
        scm: SCM provider for querying the PR state.
        repo: Repository slug (e.g. ``"org/repo"``).
        now: UTC timestamp override for ``completed_at``; defaults to
            :func:`~datetime.datetime.now`.

    Returns:
        The (possibly updated) :class:`ReleaseDelivery`.
    """
    if delivery.status is not AddendumStatus.IN_REVIEW:
        return delivery

    if not delivery.pr_url:
        logger.debug(
            "poll_delivery_pr: delivery %r has no pr_url; skipping",
            delivery.id,
        )
        return delivery

    now = now or datetime.now(timezone.utc)

    # Determine the work branch to look up the PR
    work_branch = delivery.work_branch
    if not work_branch:
        from oompah.release_delivery_store import make_delivery_work_branch
        work_branch = make_delivery_work_branch(delivery)

    # ------------------------------------------------------------------
    # Query the SCM for current PR state
    # ------------------------------------------------------------------
    try:
        pr = scm.find_pr_for_branch(repo, work_branch)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "poll_delivery_pr: %r: find_pr_for_branch failed: %s",
            delivery.id,
            exc,
        )
        return delivery

    if pr is None:
        # No PR found — leave unchanged.
        logger.debug(
            "poll_delivery_pr: %r: no PR found for branch %r",
            delivery.id,
            work_branch,
        )
        return delivery

    pr_state = (getattr(pr, "state", "") or "").lower()

    # ------------------------------------------------------------------
    # Handle each possible PR state
    # ------------------------------------------------------------------

    if pr_state == "merged":
        return _handle_merged(store, delivery, now=now)

    if pr_state == "closed":
        return _handle_closed(store, delivery)

    # PR is open or state is unrecognised — no change.
    return delivery


# ---------------------------------------------------------------------------
# Per-state handlers
# ---------------------------------------------------------------------------


def _handle_merged(
    store: ReleaseDeliveryStore,
    delivery: ReleaseDelivery,
    *,
    now: datetime,
) -> ReleaseDelivery:
    """Transition *delivery* to ``merged`` after a confirmed PR merge.

    Args:
        store: The ledger store.
        delivery: The ``in_review`` delivery.
        now: UTC timestamp for ``completed_at``.

    Returns:
        Updated (``merged``) delivery, or the re-read merged delivery on race.
    """
    try:
        updated = store.update(
            delivery.id,
            status=AddendumStatus.MERGED,
            completed_at=now.isoformat(),
        )
        logger.info(
            "_handle_merged: delivery %r → merged (completed_at=%s)",
            delivery.id,
            now.isoformat(),
        )
        return updated
    except InvalidTransitionError:
        # Race condition: another poller already transitioned — re-read.
        logger.debug(
            "_handle_merged: %r: already merged; transition skipped",
            delivery.id,
        )
        current = store.lookup_by_id(delivery.id)
        return current if current is not None else delivery
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "_handle_merged: %r: failed to transition to merged: %s",
            delivery.id,
            exc,
        )
        return delivery


def _handle_closed(
    store: ReleaseDeliveryStore,
    delivery: ReleaseDelivery,
) -> ReleaseDelivery:
    """Update the error field when the PR was closed without merge.

    Status remains ``in_review``; no automatic replacement PR.
    Idempotent: if the error field already contains the closed marker, skip.

    Args:
        store: The ledger store.
        delivery: The ``in_review`` delivery.

    Returns:
        Updated delivery (same status, new error message) or the original
        when already marked or the write fails.
    """
    error_msg = f"{CLOSED_UNMERGED_ERROR_PREFIX} {delivery.pr_url}"

    # Idempotent: already recorded.
    if delivery.error and delivery.error.startswith(CLOSED_UNMERGED_ERROR_PREFIX):
        return delivery

    try:
        updated = store.update(
            delivery.id,
            error=error_msg,
        )
        logger.info(
            "_handle_closed: delivery %r: PR closed without merge; error recorded",
            delivery.id,
        )
        return updated
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "_handle_closed: %r: failed to update error for closed PR: %s",
            delivery.id,
            exc,
        )
        return delivery
