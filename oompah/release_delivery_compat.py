"""Compatibility layer: task/epic release-addendum API paths over the ledger.

Adapts the existing task/epic release-addendum read, approval, retry, and
archive paths to use the project-owned delivery ledger while preserving the
documented task-detail API request shapes during the compatibility window
(OOMPAH-196).

Key responsibilities
---------------------

1. :func:`delivery_to_compat_raw` — convert a
   :class:`~oompah.release_delivery_store.ReleaseDelivery` to the
   backward-compatible dict shape that the existing task-detail UI expects
   (same fields as :meth:`~oompah.release_addendum_schema.ReleaseAddendum.to_raw`
   plus additional ledger fields).

2. :func:`make_delivery_store` — construct a
   :class:`~oompah.release_delivery_store.ReleaseDeliveryStore` for a project.

3. :func:`make_delivery_adapter` — construct a
   :class:`~oompah.release_delivery_adapter.DualReadDeliveryAdapter` that
   combines ledger entries with legacy task-metadata addendums.

4. :func:`approve_release_addendums_via_ledger` — async approval function that
   writes :class:`~oompah.release_delivery_store.ReleaseDelivery` records to
   the ledger; does **not** write ``oompah.release_addendums`` task metadata or
   create child backport tasks.

Compatibility window
---------------------

During the compatibility window the read, retry, and archive paths use both
the ledger and legacy addendum metadata:

* Reads go through :class:`~oompah.release_delivery_adapter.DualReadDeliveryAdapter`.
* Retry/archive look up the target delivery in the ledger first; if not found
  there they fall back to legacy addendum metadata (shim).

Once the window has elapsed, the shim paths can be removed and the adapter
replaced by direct ledger reads.

Plan reference
--------------

plans/release-delivery-commit-inventory.md sections 3.2 and 4.2.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from oompah.release_addendum_schema import AddendumStatus
from oompah.release_delivery_adapter import DualReadDeliveryAdapter
from oompah.release_delivery_store import (
    ReleaseDelivery,
    ReleaseDeliveryStore,
    SourceKind,
    make_delivery_work_branch,
    make_delivery_worktree_key,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Per-source asyncio locks (module singleton)
# ---------------------------------------------------------------------------

#: Keyed by source task identifier; lazily created in the event loop.
_source_locks: dict[str, asyncio.Lock] = {}


def _get_source_lock(identifier: str) -> asyncio.Lock:
    """Return the per-source :class:`asyncio.Lock` for *identifier*.

    The lock is created lazily the first time it is requested.  Since
    FastAPI uses a single event loop, this is safe to call from any async
    request handler.

    Args:
        identifier: Source task or epic identifier (e.g. ``"FOO-10"``).

    Returns:
        The :class:`asyncio.Lock` for *identifier*.
    """
    if identifier not in _source_locks:
        _source_locks[identifier] = asyncio.Lock()
    return _source_locks[identifier]


# ---------------------------------------------------------------------------
# Delivery ID factory
# ---------------------------------------------------------------------------


def _make_delivery_id() -> str:
    """Return a fresh unique delivery ID of the form ``rd_<uuid-hex>``.

    Returns:
        New delivery ID string.
    """
    return f"rd_{uuid.uuid4().hex}"


# ---------------------------------------------------------------------------
# Compatibility serialisation
# ---------------------------------------------------------------------------


def delivery_to_compat_raw(
    delivery: ReleaseDelivery,
    *,
    included_child_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Serialise *delivery* to a backward-compatible dict.

    The resulting dict is a superset of the shape returned by
    :meth:`~oompah.release_addendum_schema.ReleaseAddendum.to_raw`:

    * ``commits`` maps to ``source_commits`` so the UI receives the same
      field name as the legacy addendum format.
    * ``worktree_key`` is computed via
      :func:`~oompah.release_delivery_store.make_delivery_worktree_key`.
    * All ledger-only fields (``source_kind``, ``source_identifier``,
      ``pr_number``, ``migrated_from``, ``delivery_id``) are included as
      additional fields; older clients ignore unknown keys.
    * ``included_child_ids`` defaults to an empty list.  Pass the caller-
      supplied value explicitly for epic approvals so the UI receives the
      list of included child task identifiers.

    Args:
        delivery: Ledger delivery record to serialise.
        included_child_ids: Optional list of epic child task identifiers
            included in this delivery.  When provided, overrides the default
            empty list.  Use this for newly-created epic-source deliveries
            where the caller knows the included descendants.

    Returns:
        Dict suitable for the task-detail addendum API response.
    """
    worktree_key = make_delivery_worktree_key(delivery)

    out: dict[str, Any] = {
        # Legacy-compatible fields
        "id": delivery.id,
        "source_branch": delivery.source_branch,
        "target_branch": delivery.target_branch,
        "status": delivery.status.value,
        "commits": list(delivery.source_commits),
        "work_branch": delivery.work_branch,
        "worktree_key": worktree_key,
        "queued_at": delivery.queued_at,
        "started_at": delivery.started_at,
        "completed_at": delivery.completed_at,
        "pr_url": delivery.pr_url,
        "result_commits": list(delivery.result_commits),
        "error": delivery.error,
        "included_child_ids": list(included_child_ids) if included_child_ids else [],
        # Additional ledger fields (additive; older clients ignore unknown keys)
        "delivery_id": delivery.id,
        "source_kind": delivery.source_kind.value,
        "source_identifier": delivery.source_identifier,
        "pr_number": delivery.pr_number,
        "migrated_from": delivery.migrated_from,
    }
    if delivery.claimed_by is not None:
        out["claimed_by"] = delivery.claimed_by
    if delivery.lease_expires_at is not None:
        out["lease_expires_at"] = delivery.lease_expires_at
    return out


# ---------------------------------------------------------------------------
# Store / adapter factories
# ---------------------------------------------------------------------------


def make_delivery_store(
    project: Any,
    git_writer: Any | None = None,
) -> ReleaseDeliveryStore:
    """Construct a :class:`~oompah.release_delivery_store.ReleaseDeliveryStore`
    for *project*.

    Args:
        project: Project providing ``repo_path`` and ``id``.
        git_writer: Optional tracker for git-backed writes.  When ``None``,
            the store writes to the filesystem only (useful in tests and for
            read-only callers).

    Returns:
        :class:`~oompah.release_delivery_store.ReleaseDeliveryStore`.

    Raises:
        ValueError: When ``project.repo_path`` is empty.
    """
    repo_path: str = getattr(project, "repo_path", "") or ""
    if not repo_path:
        raise ValueError(
            f"Project {getattr(project, 'id', '?')!r} has no repo_path; "
            "cannot access the release delivery ledger"
        )
    return ReleaseDeliveryStore(
        project_root=repo_path,
        project_id=str(project.id),
        git_writer=git_writer,
    )


def make_delivery_adapter(
    project: Any,
    tracker: Any,
    git_writer: Any | None = None,
) -> DualReadDeliveryAdapter:
    """Construct a :class:`~oompah.release_delivery_adapter.DualReadDeliveryAdapter`
    for *project*.

    Args:
        project: Project providing ``repo_path`` and ``id``.
        tracker: Tracker implementation used for legacy addendum reads.
        git_writer: Optional tracker for git-backed writes (passed to the store).

    Returns:
        :class:`~oompah.release_delivery_adapter.DualReadDeliveryAdapter`.

    Raises:
        ValueError: When ``project.repo_path`` is empty.
    """
    store = make_delivery_store(project, git_writer=git_writer)
    return DualReadDeliveryAdapter(store, tracker, str(project.id))


# ---------------------------------------------------------------------------
# Approval result
# ---------------------------------------------------------------------------


@dataclass
class LedgerApprovalResult:
    """Result returned by :func:`approve_release_addendums_via_ledger`.

    Attributes:
        deliveries: Full updated delivery list for the source task after this
            approval.  Includes both newly-created and previously-active ledger
            entries as seen by the :class:`~oompah.release_delivery_adapter.DualReadDeliveryAdapter`.
        newly_created_ids: Delivery IDs that were created in this call.
            Empty when all requested branches already had active deliveries
            (idempotent duplicate).
        event_failures: Delivery IDs for which event publication failed.
            These rows are durably ``open`` but were not immediately woken up;
            the periodic queue scanner will recover them.
    """

    deliveries: list[ReleaseDelivery] = field(default_factory=list)
    newly_created_ids: list[str] = field(default_factory=list)
    event_failures: list[str] = field(default_factory=list)

    @property
    def queued(self) -> bool:
        """True when all newly-created deliveries were successfully enqueued."""
        if not self.newly_created_ids:
            # Idempotent — nothing new was created
            return True
        return len(self.event_failures) == 0


# ---------------------------------------------------------------------------
# Core ledger approval
# ---------------------------------------------------------------------------


async def approve_release_addendums_via_ledger(
    store: ReleaseDeliveryStore,
    adapter: DualReadDeliveryAdapter,
    source_task: Any,
    project: Any,
    target_branches: list[str],
    commits: list[str],
    *,
    included_child_ids: list[str] | None = None,
    event_bus: Any | None = None,
) -> LedgerApprovalResult:
    """Atomically create open ledger deliveries for each missing target branch.

    This is the ledger-backed replacement for
    :func:`~oompah.release_addendum_approval.approve_release_addendums`.
    It writes :class:`~oompah.release_delivery_store.ReleaseDelivery` records
    to the project-owned ledger instead of ``oompah.release_addendums`` task
    metadata.  It never creates child backport tasks.

    Idempotency
    -----------

    The approval is serialised per source identifier via an
    :class:`asyncio.Lock`.  If an active (non-archived) delivery already
    exists for a ``(source_identifier, target_branch)`` pair it is returned
    unchanged and no new record is written.

    Event-failure recovery
    ----------------------

    If event publication fails after persistence the delivery remains ``open``
    and the function returns ``queued=False`` for that delivery.  The periodic
    queue scanner must pick it up.  The approval is *never* rolled back because
    an in-memory wake-up failed.

    Args:
        store: Ledger store backed by the project's ledger file.
        adapter: Dual-read adapter used to read back the full delivery list
            (including any legacy records) after writes.
        source_task: Source :class:`~oompah.models.Issue` (already validated
            as ``Merged`` on the default branch).
        project: Project providing ``default_branch`` and ``id``.
        target_branches: Deduplicated, validated target branch names.
        commits: Ordered, non-empty commit SHA list to snapshot.
        included_child_ids: For epic approvals, the ordered list of
            descendant task identifiers whose commits are included.
            ``None`` or empty for per-task approvals.
        event_bus: Optional :class:`~oompah.events.EventBus` for publishing
            ``release_addendum_ready`` events to wake the queue.

    Returns:
        :class:`LedgerApprovalResult` with the full updated delivery list,
        newly created IDs, and any event-publication failures.
    """
    from oompah.events import EventType

    identifier = source_task.identifier
    source_branch: str = getattr(project, "default_branch", "main") or "main"
    is_epic = getattr(source_task, "issue_type", "task") == "epic"
    source_kind = SourceKind.EPIC if is_epic else SourceKind.TASK
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    lock = _get_source_lock(identifier)
    newly_created_ids: list[str] = []
    newly_created_deliveries: list[ReleaseDelivery] = []

    async with lock:
        # Read current ledger deliveries for this source.
        # Active = any non-archived delivery for the same target branch.
        existing = store.lookup_by_source_identifier(identifier)
        active_by_branch: dict[str, str] = {
            d.target_branch: d.id
            for d in existing
            if d.status is not AddendumStatus.ARCHIVED
        }

        for target_branch in target_branches:
            if target_branch in active_by_branch:
                logger.debug(
                    "approve_via_ledger: %s → %s already has active delivery %s, skipping",
                    identifier,
                    target_branch,
                    active_by_branch[target_branch],
                )
                continue

            delivery_id = _make_delivery_id()
            # Build initial delivery to derive work_branch deterministically
            _draft = ReleaseDelivery(
                id=delivery_id,
                project_id=str(project.id),
                source_branch=source_branch,
                source_kind=source_kind,
                source_identifier=identifier,
                source_commits=list(commits),
                target_branch=target_branch,
                status=AddendumStatus.OPEN,
                queued_at=now,
            )
            work_branch = make_delivery_work_branch(_draft)

            delivery = ReleaseDelivery(
                id=delivery_id,
                project_id=str(project.id),
                source_branch=source_branch,
                source_kind=source_kind,
                source_identifier=identifier,
                source_commits=list(commits),
                target_branch=target_branch,
                status=AddendumStatus.OPEN,
                queued_at=now,
                work_branch=work_branch,
            )
            store.append(delivery)
            newly_created_ids.append(delivery_id)
            newly_created_deliveries.append(delivery)
            active_by_branch[target_branch] = delivery_id
            logger.info(
                "approve_via_ledger: created delivery %s for %s → %s",
                delivery_id,
                identifier,
                target_branch,
            )

    # Build the combined return list.
    #
    # We combine in-memory state (existing ledger entries + newly-created
    # deliveries) with legacy addendums from the tracker, rather than
    # re-reading from disk.  This avoids a race between the write (which
    # may go through a git_writer that does not immediately update the
    # on-disk file) and the subsequent read.
    #
    # De-duplication: ledger entries whose migrated_from matches a legacy
    # addendum ID shadow that legacy addendum (same logic as the adapter).
    try:
        from oompah.release_delivery_adapter import _addendum_to_delivery

        # Collect migrated_from IDs from both existing and newly-created entries.
        migrated_from_set: set[str] = {
            d.migrated_from
            for d in (list(existing) + newly_created_deliveries)
            if d.migrated_from
        }

        # Fetch legacy addendums from the adapter's tracker helper.
        legacy_addendums = adapter._fetch_legacy_addendums(identifier)  # noqa: SLF001
        synthetic: list[ReleaseDelivery] = []
        for addendum in legacy_addendums:
            if addendum.id in migrated_from_set:
                continue
            synthetic.append(
                _addendum_to_delivery(
                    addendum,
                    identifier,
                    source_kind,
                    str(project.id),
                )
            )
        deliveries: list[ReleaseDelivery] = list(existing) + newly_created_deliveries + synthetic
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "approve_via_ledger: failed to build combined delivery list for %s: %s",
            identifier,
            exc,
        )
        deliveries = list(existing) + newly_created_deliveries

    # Publish events outside the lock (failure must not roll back persistence).
    event_failures: list[str] = []
    if event_bus is not None and newly_created_ids:
        for delivery_id in newly_created_ids:
            try:
                event_bus.emit(
                    EventType.RELEASE_ADDENDUM_READY,
                    {
                        "delivery_id": delivery_id,
                        "source_identifier": identifier,
                        "project_id": str(project.id),
                    },
                )
                logger.debug(
                    "approve_via_ledger: emitted RELEASE_ADDENDUM_READY for %s",
                    delivery_id,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "approve_via_ledger: event publication failed for %s: %s",
                    delivery_id,
                    exc,
                )
                event_failures.append(delivery_id)

    return LedgerApprovalResult(
        deliveries=deliveries,
        newly_created_ids=newly_created_ids,
        event_failures=event_failures,
    )


# ---------------------------------------------------------------------------
# Ledger-backed retry helper
# ---------------------------------------------------------------------------


def retry_ledger_delivery(
    store: ReleaseDeliveryStore,
    delivery_id: str,
) -> ReleaseDelivery:
    """Transition a ledger delivery from ``blocked`` or ``in_review`` to ``open``.

    Clears the lease and error fields.

    Args:
        store: Ledger store for the project.
        delivery_id: ID of the delivery to retry.

    Returns:
        The updated :class:`~oompah.release_delivery_store.ReleaseDelivery`.

    Raises:
        :class:`~oompah.release_delivery_store.DeliveryNotFoundError`: When
            *delivery_id* is not in the ledger.
        :class:`~oompah.release_addendum_schema.InvalidTransitionError`: When
            the current status does not permit a retry transition.
        :class:`~oompah.release_delivery_store.LedgerParseError`: When the
            ledger file is malformed.
    """
    return store.update(
        delivery_id,
        status=AddendumStatus.OPEN,
        claimed_by=None,
        lease_expires_at=None,
        error=None,
        conflict_agent_task_id=None,
    )


# ---------------------------------------------------------------------------
# Ledger-backed archive helper
# ---------------------------------------------------------------------------


def archive_ledger_delivery(
    store: ReleaseDeliveryStore,
    delivery_id: str,
) -> ReleaseDelivery:
    """Transition a ledger delivery from ``open`` or ``blocked`` to ``archived``.

    Args:
        store: Ledger store for the project.
        delivery_id: ID of the delivery to archive.

    Returns:
        The updated :class:`~oompah.release_delivery_store.ReleaseDelivery`.

    Raises:
        :class:`~oompah.release_delivery_store.DeliveryNotFoundError`: When
            *delivery_id* is not in the ledger.
        :class:`~oompah.release_addendum_schema.InvalidTransitionError`: When
            the current status does not permit an archive transition.
        :class:`~oompah.release_delivery_store.LedgerParseError`: When the
            ledger file is malformed.
    """
    return store.update(
        delivery_id,
        status=AddendumStatus.ARCHIVED,
    )
