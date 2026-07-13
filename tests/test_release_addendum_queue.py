"""Durability and claiming tests for :mod:`oompah.release_addendum_queue`."""

from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from oompah.events import EventBus, EventType
from oompah.config import ServiceConfig
from oompah.orchestrator import DispatchEventType, Orchestrator
from oompah.release_addendum_queue import ReleaseAddendumQueue
from oompah.release_addendum_schema import AddendumStatus, ReleaseAddendum


NOW = datetime(2026, 7, 13, tzinfo=timezone.utc)


def _addendum(
    status: AddendumStatus = AddendumStatus.OPEN,
    *,
    target: str = "release/1.0",
    lease_expires_at: str | None = None,
) -> ReleaseAddendum:
    return ReleaseAddendum(
        id=f"FOO-10/{target}",
        source_branch="main",
        target_branch=target,
        status=status,
        commits=["a" * 40],
        work_branch="oompah/release/FOO-10/release-1.0",
        worktree_key="release-FOO-10-release-1.0",
        queued_at=NOW.isoformat(),
        claimed_by="old-worker" if status is AddendumStatus.IN_PROGRESS else None,
        lease_expires_at=lease_expires_at,
    )


class _Tracker:
    def __init__(self, addendums: list[ReleaseAddendum]) -> None:
        self._lock = threading.Lock()
        self._metadata = {"oompah.release_addendums": [a.to_raw() for a in addendums]}
        self.issues = [SimpleNamespace(identifier="FOO-10", state="Merged")]
        self.writes = 0

    def fetch_all_issues(self):
        return list(self.issues)

    def get_metadata(self, _identifier):
        with self._lock:
            return {key: list(value) if isinstance(value, list) else value for key, value in self._metadata.items()}

    def set_metadata_field(self, _identifier, key, value):
        with self._lock:
            self._metadata[key] = value
            self.writes += 1


def _queue(tracker: _Tracker, worker_id: str = "worker-a", **kwargs) -> ReleaseAddendumQueue:
    return ReleaseAddendumQueue("proj-1", tracker, worker_id=worker_id, now=lambda: NOW, **kwargs)


def test_only_one_concurrent_claimant_wins():
    tracker = _Tracker([_addendum()])
    queues = [_queue(tracker, f"worker-{index}") for index in range(2)]
    barrier = threading.Barrier(2)
    claims = []

    def claim(queue):
        barrier.wait()
        claims.append(queue.claim_one())

    threads = [threading.Thread(target=claim, args=(queue,)) for queue in queues]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    claimed = [claim for claim in claims if claim is not None]
    assert len(claimed) == 1
    assert claimed[0].key == ("proj-1", "FOO-10", "release/1.0")
    assert claimed[0].addendum.status is AddendumStatus.IN_PROGRESS


def test_ready_event_wakes_matching_project_queue():
    bus = EventBus()
    queue = _queue(_Tracker([]), event_bus=bus)

    bus.emit(EventType.RELEASE_ADDENDUM_READY, {"project_id": "other"})
    assert asyncio.run(queue.wait_for_work(timeout=0.001)) is False

    bus.emit(EventType.RELEASE_ADDENDUM_READY, {"project_id": "proj-1"})
    assert asyncio.run(queue.wait_for_work(timeout=0.1)) is True


def test_ready_event_wakes_orchestrator_dispatch_loop(tmp_path):
    orch = Orchestrator(
        config=ServiceConfig(tracker_kind="oompah_md"),
        workflow_path="WORKFLOW.md",
        state_path=str(tmp_path / "state.json"),
    )

    orch.event_bus.emit(
        EventType.RELEASE_ADDENDUM_READY,
        {"project_id": "proj-1", "source_identifier": "FOO-10"},
    )

    event = orch._dispatch_queue.get_nowait()
    assert event.event_type is DispatchEventType.REFRESH_REQUESTED
    assert event.payload["release_addendum_ready"]["source_identifier"] == "FOO-10"


def test_restart_scan_discovers_persisted_open_row_without_source_state_change():
    tracker = _Tracker([_addendum()])
    restarted_queue = _queue(tracker, "worker-after-restart")

    discovered = restarted_queue.scan()

    assert [item.key for item in discovered] == [("proj-1", "FOO-10", "release/1.0")]
    assert tracker.issues[0].state == "Merged"


def test_expired_lease_returns_to_open_and_is_claimable_again():
    tracker = _Tracker([
        _addendum(
            AddendumStatus.IN_PROGRESS,
            lease_expires_at=(NOW - timedelta(seconds=1)).isoformat(),
        )
    ])
    queue = _queue(tracker, "recovery-worker")

    recovered = queue.recover_expired_leases()
    claim = queue.claim_one()

    assert len(recovered) == 1
    assert recovered[0].addendum.status is AddendumStatus.OPEN
    assert recovered[0].addendum.claimed_by is None
    assert claim is not None
    assert claim.addendum.claimed_by == "recovery-worker"


def test_non_open_lifecycle_rows_are_never_claimed():
    tracker = _Tracker([
        _addendum(AddendumStatus.BLOCKED, target="release/1.0"),
        _addendum(AddendumStatus.MERGED, target="release/1.1"),
        _addendum(AddendumStatus.ARCHIVED, target="release/1.2"),
    ])

    assert _queue(tracker).scan() == []
    assert _queue(tracker).claim_one() is None


def test_repeated_scans_and_recovery_are_idempotent():
    tracker = _Tracker([_addendum()])
    queue = _queue(tracker)

    first = queue.scan()
    second = queue.scan()
    recovered_first = queue.recover_expired_leases()
    recovered_second = queue.recover_expired_leases()

    assert [item.key for item in first] == [item.key for item in second]
    assert recovered_first == recovered_second == []
    assert tracker.writes == 0
