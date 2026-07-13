"""Durable claiming and recovery for release addendums.

Release addendums are metadata records on their original source task or epic,
not tracker work items.  This adapter deliberately exposes only those records
to the release executor: it never creates an :class:`Issue` or a child task.
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from oompah.events import EventBus, EventType
from oompah.release_addendum_schema import (
    AddendumRepository,
    AddendumStatus,
    ReleaseAddendum,
)


@dataclass(frozen=True)
class ReleaseAddendumQueueItem:
    """A claimed or discoverable addendum, addressed without a tracker task."""

    project_id: str
    source_identifier: str
    target_branch: str
    addendum: ReleaseAddendum

    @property
    def key(self) -> tuple[str, str, str]:
        """Stable queue key: project, source identifier, and target branch."""
        return (self.project_id, self.source_identifier, self.target_branch)


_source_locks: dict[tuple[str, str], threading.RLock] = {}
_source_locks_guard = threading.Lock()


def _source_lock(project_id: str, source_identifier: str) -> threading.RLock:
    """Return the process-local write lock for a source metadata record."""
    key = (project_id, source_identifier)
    with _source_locks_guard:
        return _source_locks.setdefault(key, threading.RLock())


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class ReleaseAddendumQueue:
    """Scan, claim, and recover durable release-addendum metadata.

    Claiming is serialized per ``(project_id, source_identifier)`` because all
    addendums for a source share one metadata field.  The public item key adds
    ``target_branch`` and is therefore safe to hand to execution code.
    """

    def __init__(
        self,
        project_id: str,
        tracker: Any,
        *,
        worker_id: str,
        lease_duration: timedelta = timedelta(minutes=15),
        event_bus: EventBus | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.project_id = project_id
        self.tracker = tracker
        self.worker_id = worker_id
        self.lease_duration = lease_duration
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._wake_event = asyncio.Event()
        self._event_bus = event_bus
        if event_bus is not None:
            event_bus.subscribe(EventType.RELEASE_ADDENDUM_READY, self._on_ready)

    def close(self) -> None:
        """Detach this queue from its event bus when it is discarded."""
        if self._event_bus is not None:
            self._event_bus.unsubscribe(EventType.RELEASE_ADDENDUM_READY, self._on_ready)
            self._event_bus = None

    def _on_ready(self, _event_type: EventType | str, payload: dict[str, Any]) -> None:
        if payload.get("project_id") == self.project_id:
            self._wake_event.set()

    async def wait_for_work(self, timeout: float | None = None) -> bool:
        """Wait for a ready event; callers still use :meth:`scan` for recovery."""
        try:
            if timeout is None:
                await self._wake_event.wait()
            else:
                await asyncio.wait_for(self._wake_event.wait(), timeout)
        except asyncio.TimeoutError:
            return False
        self._wake_event.clear()
        return True

    def scan(self) -> list[ReleaseAddendumQueueItem]:
        """Return all durable ``open`` rows in stable queue-key order.

        This is read-only and idempotent.  It intentionally scans every source
        task state so an addendum remains dispatchable after its source merges.
        """
        items: list[ReleaseAddendumQueueItem] = []
        for source in self.tracker.fetch_all_issues():
            identifier = getattr(source, "identifier", None) or getattr(source, "id", None)
            if not identifier:
                continue
            for addendum in AddendumRepository(self.tracker).read(str(identifier)):
                if addendum.status is AddendumStatus.OPEN:
                    items.append(
                        ReleaseAddendumQueueItem(
                            self.project_id, str(identifier), addendum.target_branch, addendum
                        )
                    )
        return sorted(items, key=lambda item: item.key)

    def recover_expired_leases(self) -> list[ReleaseAddendumQueueItem]:
        """Return expired in-progress leases to ``open`` exactly once."""
        now = self._now()
        recovered: list[ReleaseAddendumQueueItem] = []
        for source in self.tracker.fetch_all_issues():
            identifier = getattr(source, "identifier", None) or getattr(source, "id", None)
            if not identifier:
                continue
            identifier = str(identifier)
            with _source_lock(self.project_id, identifier):
                repo = AddendumRepository(self.tracker)
                addendums = repo.read(identifier)
                for addendum in addendums:
                    expiry = _parse_timestamp(addendum.lease_expires_at)
                    if addendum.status is not AddendumStatus.IN_PROGRESS or expiry is None or expiry > now:
                        continue
                    updated = repo.transition(
                        identifier,
                        addendum.id,
                        AddendumStatus.OPEN,
                        existing=addendums,
                        claimed_by=None,
                        lease_expires_at=None,
                    )
                    addendums = updated
                    reopened = next(a for a in updated if a.id == addendum.id)
                    recovered.append(
                        ReleaseAddendumQueueItem(
                            self.project_id, identifier, reopened.target_branch, reopened
                        )
                    )
        return recovered

    def claim_one(self) -> ReleaseAddendumQueueItem | None:
        """Atomically claim one durable open addendum with a finite lease."""
        self.recover_expired_leases()
        for item in self.scan():
            with _source_lock(self.project_id, item.source_identifier):
                repo = AddendumRepository(self.tracker)
                current = repo.read(item.source_identifier)
                addendum = next((a for a in current if a.id == item.addendum.id), None)
                if addendum is None or addendum.status is not AddendumStatus.OPEN:
                    continue
                now = self._now()
                updated = repo.transition(
                    item.source_identifier,
                    addendum.id,
                    AddendumStatus.IN_PROGRESS,
                    existing=current,
                    claimed_by=self.worker_id,
                    lease_expires_at=(now + self.lease_duration).isoformat(),
                    started_at=now.isoformat(),
                )
                claimed = next(a for a in updated if a.id == addendum.id)
                return ReleaseAddendumQueueItem(
                    self.project_id, item.source_identifier, claimed.target_branch, claimed
                )
        return None
