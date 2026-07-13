"""Durable claiming and recovery for release deliveries (OOMPAH-195).

Release deliveries are project-owned ledger records in
``.oompah/release-deliveries.yml``.  This module provides a queue that
scans the ledger for ``open`` entries, claims one atomically with a finite
lease, and recovers expired leases — all keyed by immutable delivery ID.

The queue identity is the ``delivery_id`` (not a ``(source, branch)`` tuple),
so claiming, retry, and worktree cleanup are all keyed by a single stable ID
that survives a service restart.

Design differences from :mod:`oompah.release_addendum_queue`
-------------------------------------------------------------

- Lock is per-project (not per-source-task): the ledger is one file per
  project, so contention is at the project level.
- Scan reads from :class:`~oompah.release_delivery_store.ReleaseDeliveryStore`
  rather than iterating task metadata.
- Items carry the full :class:`~oompah.release_delivery_store.ReleaseDelivery`
  record so the executor has access to the immutable ``source_commits``
  snapshot without a second read.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from oompah.events import EventBus, EventType
from oompah.release_addendum_schema import AddendumStatus
from oompah.release_delivery_store import (
    ReleaseDelivery,
    ReleaseDeliveryStore,
    _delivery_lock,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Queue item
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReleaseDeliveryQueueItem:
    """A claimable or claimed ledger delivery.

    Attributes:
        delivery_id: Immutable delivery identifier (``rd_01J...``).
        project_id: Project that owns the delivery.
        delivery: The full :class:`~oompah.release_delivery_store.ReleaseDelivery`
            record at claim time (snapshot; not auto-updated).
    """

    delivery_id: str
    project_id: str
    delivery: ReleaseDelivery

    @property
    def key(self) -> tuple[str, str]:
        """Stable sort key: ``(project_id, delivery_id)``."""
        return (self.project_id, self.delivery_id)


# ---------------------------------------------------------------------------
# Timestamp helper
# ---------------------------------------------------------------------------


def _parse_timestamp(value: str | None) -> datetime | None:
    """Parse an ISO-8601 timestamp string to a timezone-aware datetime, or None."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Queue class
# ---------------------------------------------------------------------------


class ReleaseDeliveryQueue:
    """Scan, claim, and recover durable release-delivery ledger records.

    All mutating operations (claim, lease recovery) are serialised under the
    per-project delivery lock from
    :func:`~oompah.release_delivery_store._delivery_lock`.

    Args:
        project_id: Project that this queue services.
        store: The :class:`~oompah.release_delivery_store.ReleaseDeliveryStore`
            for reading/writing the project ledger.
        worker_id: Stable identifier for this queue worker (written to
            ``claimed_by`` on the delivery).
        lease_duration: How long a single claim is valid before the recovery
            pass returns it to ``open``.
        event_bus: Optional :class:`~oompah.events.EventBus`; subscribes to
            :attr:`~oompah.events.EventType.RELEASE_ADDENDUM_READY` for
            wake-up signals when a new delivery is queued.
        now: Optional callable that returns the current UTC datetime; used in
            tests to control the clock.
    """

    def __init__(
        self,
        project_id: str,
        store: ReleaseDeliveryStore,
        *,
        worker_id: str,
        lease_duration: timedelta = timedelta(minutes=15),
        event_bus: EventBus | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.project_id = project_id
        self._store = store
        self.worker_id = worker_id
        self.lease_duration = lease_duration
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._wake_event = asyncio.Event()
        self._event_bus = event_bus
        # Store the bound method reference so that close() can use the same
        # object for unsubscribe (Python bound methods are not identical across
        # attribute accesses, so identity-based unsubscribe requires a stored ref).
        self._ready_handler = self._on_ready
        if event_bus is not None:
            event_bus.subscribe(EventType.RELEASE_ADDENDUM_READY, self._ready_handler)

    def close(self) -> None:
        """Detach this queue from its event bus when it is discarded."""
        if self._event_bus is not None:
            self._event_bus.unsubscribe(EventType.RELEASE_ADDENDUM_READY, self._ready_handler)
            self._event_bus = None

    def _on_ready(self, _event_type: EventType | str, payload: dict[str, Any]) -> None:
        """Wake the queue when a new delivery is added for this project."""
        if payload.get("project_id") == self.project_id:
            self._wake_event.set()

    async def wait_for_work(self, timeout: float | None = None) -> bool:
        """Wait for a wake-up event; callers still use :meth:`scan` for recovery.

        Args:
            timeout: Maximum seconds to wait; ``None`` waits indefinitely.

        Returns:
            ``True`` when woken by a ready event; ``False`` on timeout.
        """
        try:
            if timeout is None:
                await self._wake_event.wait()
            else:
                await asyncio.wait_for(self._wake_event.wait(), timeout)
        except asyncio.TimeoutError:
            return False
        self._wake_event.clear()
        return True

    def scan(self) -> list[ReleaseDeliveryQueueItem]:
        """Return all ``open`` deliveries for this project in stable key order.

        This is read-only and idempotent.  Deliveries in terminal states
        (``merged``, ``archived``) are excluded.

        Returns:
            Sorted list of :class:`ReleaseDeliveryQueueItem` objects.
        """
        try:
            ledger = self._store.read_ledger()
        except Exception:  # noqa: BLE001
            logger.exception(
                "ReleaseDeliveryQueue.scan: failed to read ledger for project %r",
                self.project_id,
            )
            return []

        items: list[ReleaseDeliveryQueueItem] = []
        for delivery in ledger.deliveries:
            if delivery.project_id != self.project_id:
                continue
            if delivery.status is AddendumStatus.OPEN:
                items.append(
                    ReleaseDeliveryQueueItem(
                        delivery_id=delivery.id,
                        project_id=self.project_id,
                        delivery=delivery,
                    )
                )
        return sorted(items, key=lambda item: item.key)

    def recover_expired_leases(self) -> list[ReleaseDeliveryQueueItem]:
        """Return expired ``in_progress`` leases to ``open`` exactly once.

        Reads the ledger under the project lock, identifies any delivery
        whose ``lease_expires_at`` has elapsed while still ``in_progress``,
        and transitions each back to ``open`` with ``claimed_by`` and
        ``lease_expires_at`` cleared.

        Returns:
            List of :class:`ReleaseDeliveryQueueItem` objects for re-opened
            deliveries (now ``open`` again).
        """
        now = self._now()
        recovered: list[ReleaseDeliveryQueueItem] = []

        with _delivery_lock(self.project_id):
            try:
                ledger = self._store.read_ledger()
            except Exception:  # noqa: BLE001
                logger.exception(
                    "recover_expired_leases: failed to read ledger for project %r",
                    self.project_id,
                )
                return []

            for delivery in ledger.deliveries:
                if delivery.project_id != self.project_id:
                    continue
                if delivery.status is not AddendumStatus.IN_PROGRESS:
                    continue
                expiry = _parse_timestamp(delivery.lease_expires_at)
                if expiry is None or expiry > now:
                    continue

                # Lease has expired — reset to open
                try:
                    updated = self._store.update(
                        delivery.id,
                        status=AddendumStatus.OPEN,
                        claimed_by=None,
                        lease_expires_at=None,
                    )
                    recovered.append(
                        ReleaseDeliveryQueueItem(
                            delivery_id=updated.id,
                            project_id=self.project_id,
                            delivery=updated,
                        )
                    )
                    logger.info(
                        "recover_expired_leases: returned expired lease for delivery %r"
                        " (was claimed by %r, expired at %s)",
                        delivery.id,
                        delivery.claimed_by,
                        delivery.lease_expires_at,
                    )
                except Exception:  # noqa: BLE001
                    logger.exception(
                        "recover_expired_leases: failed to reset delivery %r",
                        delivery.id,
                    )

        return recovered

    def claim_one(self) -> ReleaseDeliveryQueueItem | None:
        """Atomically claim one ``open`` delivery with a finite lease.

        Recovers expired leases first, then scans for ``open`` entries and
        tries to claim each in stable key order.  A delivery that was
        concurrently claimed between scan and update is skipped.

        Returns:
            A :class:`ReleaseDeliveryQueueItem` with the claimed
            :class:`~oompah.release_delivery_store.ReleaseDelivery`
            (status ``in_progress``), or ``None`` when nothing is claimable.
        """
        self.recover_expired_leases()

        for item in self.scan():
            with _delivery_lock(self.project_id):
                # Re-read the specific delivery under the lock to guard
                # against concurrent claims that happened after the scan.
                current = self._store.lookup_by_id(item.delivery_id)
                if current is None or current.status is not AddendumStatus.OPEN:
                    continue  # concurrently claimed or state changed

                now = self._now()
                try:
                    claimed = self._store.update(
                        item.delivery_id,
                        status=AddendumStatus.IN_PROGRESS,
                        claimed_by=self.worker_id,
                        lease_expires_at=(now + self.lease_duration).isoformat(),
                        started_at=now.isoformat(),
                    )
                    logger.info(
                        "ReleaseDeliveryQueue.claim_one: claimed delivery %r"
                        " for project %r (worker=%r)",
                        item.delivery_id,
                        self.project_id,
                        self.worker_id,
                    )
                    return ReleaseDeliveryQueueItem(
                        delivery_id=claimed.id,
                        project_id=self.project_id,
                        delivery=claimed,
                    )
                except Exception:  # noqa: BLE001
                    logger.exception(
                        "claim_one: failed to claim delivery %r",
                        item.delivery_id,
                    )
                    continue

        return None
