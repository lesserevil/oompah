"""Tests for :mod:`oompah.release_delivery_queue`.

Covers:
- scan() returns only open deliveries for the matching project.
- claim_one() atomically claims a delivery (concurrent claimants: exactly one wins).
- claim_one() returns None when no open deliveries exist.
- recover_expired_leases() resets expired in_progress deliveries to open.
- recover_expired_leases() does not reset non-expired or non-in-progress deliveries.
- wait_for_work() returns True on RELEASE_ADDENDUM_READY event; False on timeout.
- Restart recovery: a fresh queue reads the persisted ledger and can reclaim.
- Multiple deliveries claimed in stable key order.
- close() detaches the event bus subscription.
"""

from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from oompah.events import EventBus, EventType
from oompah.release_addendum_schema import AddendumStatus
from oompah.release_delivery_queue import (
    ReleaseDeliveryQueue,
    ReleaseDeliveryQueueItem,
)
from oompah.release_delivery_store import (
    ReleaseDelivery,
    ReleaseDeliveryStore,
    SourceKind,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

NOW = datetime(2026, 7, 13, 12, 0, 0, tzinfo=timezone.utc)
PROJECT_ID = "proj-abc"


def _sha(c: str) -> str:
    return c * 40


def _delivery(
    delivery_id: str = "rd_0001",
    *,
    status: AddendumStatus = AddendumStatus.OPEN,
    target: str = "release/1.0",
    lease_expires_at: str | None = None,
    claimed_by: str | None = None,
    project_id: str = PROJECT_ID,
) -> ReleaseDelivery:
    return ReleaseDelivery(
        id=delivery_id,
        project_id=project_id,
        source_branch="main",
        source_kind=SourceKind.TASK,
        source_identifier="FOO-10",
        source_commits=[_sha("a")],
        target_branch=target,
        status=status,
        queued_at=NOW.isoformat(),
        claimed_by=claimed_by,
        lease_expires_at=lease_expires_at,
    )


class _FakeStore:
    """In-memory store that mirrors ReleaseDeliveryStore's interface for testing."""

    def __init__(self, deliveries: list[ReleaseDelivery]) -> None:
        self._lock = threading.Lock()
        self._deliveries: list[ReleaseDelivery] = list(deliveries)
        self.update_calls: list[dict[str, Any]] = []

    def read_ledger(self) -> Any:
        from oompah.release_delivery_store import ReleaseDeliveryLedger
        with self._lock:
            return ReleaseDeliveryLedger(version=1, deliveries=list(self._deliveries))

    def lookup_by_id(self, delivery_id: str) -> ReleaseDelivery | None:
        with self._lock:
            return next((d for d in self._deliveries if d.id == delivery_id), None)

    def update(self, delivery_id: str, **fields: Any) -> ReleaseDelivery:
        from oompah.release_addendum_schema import AddendumStatus as AS, is_valid_transition
        from oompah.release_delivery_store import ImmutableFieldError, DeliveryNotFoundError, _IMMUTABLE_FIELDS, _MUTABLE_FIELDS
        from oompah.release_addendum_schema import InvalidTransitionError

        self.update_calls.append({"delivery_id": delivery_id, **fields})

        immutable_attempts = set(fields) & _IMMUTABLE_FIELDS
        if immutable_attempts:
            raise ImmutableFieldError(f"Cannot change: {immutable_attempts}")
        unknown = set(fields) - _MUTABLE_FIELDS
        if unknown:
            raise ValueError(f"Unknown fields: {unknown}")

        with self._lock:
            idx = next(
                (i for i, d in enumerate(self._deliveries) if d.id == delivery_id), None
            )
            if idx is None:
                raise DeliveryNotFoundError(f"Not found: {delivery_id}")
            current = self._deliveries[idx]

            # validate status transition
            new_status = current.status
            if "status" in fields:
                raw = fields["status"]
                new_status = raw if isinstance(raw, AS) else AS.from_raw(raw)
                if not is_valid_transition(current.status, new_status):
                    from oompah.release_addendum_schema import InvalidTransitionError
                    raise InvalidTransitionError(
                        f"Invalid transition {current.status} → {new_status}"
                    )

            # Build updated delivery
            from dataclasses import replace
            updated = replace(
                current,
                status=new_status,
                claimed_by=fields.get("claimed_by", current.claimed_by),
                lease_expires_at=fields.get("lease_expires_at", current.lease_expires_at),
                started_at=fields.get("started_at", current.started_at),
                work_branch=fields.get("work_branch", current.work_branch),
                pr_url=fields.get("pr_url", current.pr_url),
                pr_number=fields.get("pr_number", current.pr_number),
                result_commits=fields.get("result_commits", current.result_commits),
                error=fields.get("error", current.error),
                completed_at=fields.get("completed_at", current.completed_at),
            )
            self._deliveries[idx] = updated
            return updated


def _queue(
    store: _FakeStore,
    *,
    worker_id: str = "worker-a",
    project_id: str = PROJECT_ID,
    event_bus: EventBus | None = None,
    now: datetime = NOW,
) -> ReleaseDeliveryQueue:
    return ReleaseDeliveryQueue(
        project_id,
        store,
        worker_id=worker_id,
        event_bus=event_bus,
        now=lambda: now,
    )


# ---------------------------------------------------------------------------
# scan() tests
# ---------------------------------------------------------------------------


def test_scan_returns_open_deliveries():
    store = _FakeStore([_delivery(status=AddendumStatus.OPEN)])
    q = _queue(store)
    items = q.scan()
    assert len(items) == 1
    assert items[0].delivery_id == "rd_0001"


def test_scan_excludes_non_open_statuses():
    deliveries = [
        _delivery("rd_1", status=AddendumStatus.IN_PROGRESS),
        _delivery("rd_2", status=AddendumStatus.IN_REVIEW),
        _delivery("rd_3", status=AddendumStatus.BLOCKED),
        _delivery("rd_4", status=AddendumStatus.MERGED),
        _delivery("rd_5", status=AddendumStatus.ARCHIVED),
    ]
    store = _FakeStore(deliveries)
    q = _queue(store)
    assert q.scan() == []


def test_scan_filters_by_project_id():
    store = _FakeStore([
        _delivery("rd_mine", project_id=PROJECT_ID),
        _delivery("rd_other", project_id="proj-other"),
    ])
    q = _queue(store)
    items = q.scan()
    assert len(items) == 1
    assert items[0].delivery_id == "rd_mine"


def test_scan_returns_items_in_stable_key_order():
    store = _FakeStore([
        _delivery("rd_z", target="release/1.0"),
        _delivery("rd_a", target="release/2.0"),
    ])
    q = _queue(store)
    items = q.scan()
    ids = [i.delivery_id for i in items]
    assert ids == sorted(ids)


def test_scan_returns_empty_on_ledger_error():
    broken_store = MagicMock()
    broken_store.read_ledger.side_effect = RuntimeError("ledger corrupt")
    q = ReleaseDeliveryQueue(PROJECT_ID, broken_store, worker_id="w")
    assert q.scan() == []


# ---------------------------------------------------------------------------
# claim_one() tests
# ---------------------------------------------------------------------------


def test_claim_one_returns_none_when_no_open():
    store = _FakeStore([_delivery(status=AddendumStatus.IN_PROGRESS)])
    q = _queue(store)
    assert q.claim_one() is None


def test_claim_one_transitions_to_in_progress():
    store = _FakeStore([_delivery()])
    q = _queue(store)
    item = q.claim_one()
    assert item is not None
    assert item.delivery.status is AddendumStatus.IN_PROGRESS
    assert item.delivery.claimed_by == "worker-a"
    assert item.delivery.lease_expires_at is not None
    assert item.delivery.started_at is not None


def test_claim_one_sets_lease_expiry_from_duration():
    store = _FakeStore([_delivery()])
    q = ReleaseDeliveryQueue(
        PROJECT_ID,
        store,
        worker_id="w",
        lease_duration=timedelta(minutes=10),
        now=lambda: NOW,
    )
    item = q.claim_one()
    assert item is not None
    expected_expiry = (NOW + timedelta(minutes=10)).isoformat()
    assert item.delivery.lease_expires_at == expected_expiry


def test_only_one_concurrent_claimant_wins():
    """Two concurrent workers competing for the same delivery: exactly one wins."""
    store = _FakeStore([_delivery()])
    queues = [_queue(store, worker_id=f"worker-{i}") for i in range(2)]
    barrier = threading.Barrier(2)
    claims = []

    def claim(q: ReleaseDeliveryQueue) -> None:
        barrier.wait()
        claims.append(q.claim_one())

    threads = [threading.Thread(target=claim, args=(q,)) for q in queues]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    claimed = [c for c in claims if c is not None]
    assert len(claimed) == 1
    assert claimed[0].delivery.status is AddendumStatus.IN_PROGRESS


def test_claim_one_skips_already_claimed():
    """A second claim attempt on the same delivery returns None."""
    store = _FakeStore([_delivery()])
    q = _queue(store, worker_id="w1")
    first = q.claim_one()
    assert first is not None

    q2 = _queue(store, worker_id="w2")
    second = q2.claim_one()
    assert second is None


def test_claim_one_claims_first_in_sorted_order():
    """When multiple open deliveries exist, the first (sorted key) is claimed."""
    store = _FakeStore([
        _delivery("rd_zz"),
        _delivery("rd_aa"),
    ])
    q = _queue(store)
    item = q.claim_one()
    assert item is not None
    assert item.delivery_id == "rd_aa"  # sorted first


# ---------------------------------------------------------------------------
# recover_expired_leases() tests
# ---------------------------------------------------------------------------


def test_recover_expired_lease_returns_to_open():
    expired_at = (NOW - timedelta(minutes=1)).isoformat()
    store = _FakeStore([
        _delivery(
            status=AddendumStatus.IN_PROGRESS,
            lease_expires_at=expired_at,
            claimed_by="old-worker",
        )
    ])
    q = _queue(store)
    recovered = q.recover_expired_leases()
    assert len(recovered) == 1
    assert recovered[0].delivery.status is AddendumStatus.OPEN
    assert recovered[0].delivery.claimed_by is None
    assert recovered[0].delivery.lease_expires_at is None


def test_recover_non_expired_lease_is_not_touched():
    future = (NOW + timedelta(minutes=10)).isoformat()
    store = _FakeStore([
        _delivery(
            status=AddendumStatus.IN_PROGRESS,
            lease_expires_at=future,
            claimed_by="active-worker",
        )
    ])
    q = _queue(store)
    recovered = q.recover_expired_leases()
    assert recovered == []


def test_recover_skips_non_in_progress():
    """Open and blocked deliveries are not touched by lease recovery."""
    store = _FakeStore([
        _delivery("rd_open", status=AddendumStatus.OPEN),
        _delivery("rd_blocked", status=AddendumStatus.BLOCKED),
    ])
    q = _queue(store)
    assert q.recover_expired_leases() == []


def test_recover_expired_lease_enables_reclaim():
    """After lease recovery, claim_one() can re-claim the delivery."""
    expired_at = (NOW - timedelta(minutes=1)).isoformat()
    store = _FakeStore([
        _delivery(
            status=AddendumStatus.IN_PROGRESS,
            lease_expires_at=expired_at,
            claimed_by="old-worker",
        )
    ])
    q = _queue(store, worker_id="new-worker")
    q.recover_expired_leases()
    item = q.claim_one()
    assert item is not None
    assert item.delivery.claimed_by == "new-worker"


def test_recover_lease_with_null_expires_at_is_not_touched():
    """In-progress with no lease_expires_at is left alone by recovery."""
    store = _FakeStore([
        _delivery(
            status=AddendumStatus.IN_PROGRESS,
            lease_expires_at=None,
            claimed_by="worker",
        )
    ])
    q = _queue(store)
    assert q.recover_expired_leases() == []


# ---------------------------------------------------------------------------
# Restart-recovery test
# ---------------------------------------------------------------------------


def test_restart_recovery_reads_persisted_open_deliveries(tmp_path: Path):
    """A fresh queue backed by a real store can claim persisted open deliveries."""
    from oompah.release_delivery_store import (
        ReleaseDeliveryStore,
        ReleaseDelivery,
        SourceKind,
    )

    store = ReleaseDeliveryStore(tmp_path, PROJECT_ID)
    delivery = _delivery()
    store.append(delivery)

    # Simulate restart: create a brand-new queue pointing at the same ledger
    new_store = ReleaseDeliveryStore(tmp_path, PROJECT_ID)
    q = ReleaseDeliveryQueue(PROJECT_ID, new_store, worker_id="restarted-worker", now=lambda: NOW)
    item = q.claim_one()
    assert item is not None
    assert item.delivery_id == delivery.id
    assert item.delivery.status is AddendumStatus.IN_PROGRESS
    assert item.delivery.claimed_by == "restarted-worker"


# ---------------------------------------------------------------------------
# wait_for_work() tests
# ---------------------------------------------------------------------------


def test_wait_for_work_times_out_with_no_event():
    bus = EventBus()
    q = _queue(_FakeStore([]), event_bus=bus)
    result = asyncio.run(q.wait_for_work(timeout=0.001))
    assert result is False


def test_wait_for_work_woken_by_matching_project():
    bus = EventBus()
    q = _queue(_FakeStore([]), event_bus=bus)
    bus.emit(EventType.RELEASE_ADDENDUM_READY, {"project_id": PROJECT_ID})
    result = asyncio.run(q.wait_for_work(timeout=0.5))
    assert result is True


def test_wait_for_work_not_woken_by_different_project():
    bus = EventBus()
    q = _queue(_FakeStore([]), event_bus=bus)
    bus.emit(EventType.RELEASE_ADDENDUM_READY, {"project_id": "other-proj"})
    result = asyncio.run(q.wait_for_work(timeout=0.001))
    assert result is False


def test_close_detaches_event_bus():
    bus = EventBus()
    q = _queue(_FakeStore([]), event_bus=bus)
    q.close()
    # Emitting an event after close should not wake the queue (no subscription)
    bus.emit(EventType.RELEASE_ADDENDUM_READY, {"project_id": PROJECT_ID})
    result = asyncio.run(q.wait_for_work(timeout=0.001))
    assert result is False


# ---------------------------------------------------------------------------
# Queue item properties
# ---------------------------------------------------------------------------


def test_queue_item_key_is_project_id_and_delivery_id():
    d = _delivery("rd_xyz")
    item = ReleaseDeliveryQueueItem(
        delivery_id="rd_xyz",
        project_id=PROJECT_ID,
        delivery=d,
    )
    assert item.key == (PROJECT_ID, "rd_xyz")


# ---------------------------------------------------------------------------
# Archive / multiple statuses not scanned
# ---------------------------------------------------------------------------


def test_archived_delivery_not_scanned():
    store = _FakeStore([_delivery(status=AddendumStatus.ARCHIVED)])
    q = _queue(store)
    assert q.scan() == []


def test_merged_delivery_not_scanned():
    store = _FakeStore([_delivery(status=AddendumStatus.MERGED)])
    q = _queue(store)
    assert q.scan() == []
