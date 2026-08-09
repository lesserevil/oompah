"""Durable review-capacity reservation coverage for OOMPAH-646."""

from __future__ import annotations

import multiprocessing
import sqlite3
import time

import pytest

from oompah.review_capacity import ReviewCapacityStore


class _CoordinatedReviewCapacityStore(ReviewCapacityStore):
    """Hold spawned contenders at the exact migration boundary."""

    def __init__(self, path, ready, release):
        self._migration_ready = ready
        self._migration_release = release
        super().__init__(path)

    def _migrate_schema(self):
        self._migration_ready.set()
        if not self._migration_release.wait(timeout=60):
            raise TimeoutError("parent did not release coordinated schema migration")
        super()._migrate_schema()


def _open_capacity_store_concurrently(path, ready, release, results):
    """Open one store after every migration contender is ready."""

    try:
        store = _CoordinatedReviewCapacityStore(path, ready, release)
        columns = {
            row[1]
            for row in store._conn.execute(  # noqa: SLF001 - migration assertion
                "PRAGMA table_info(review_capacity_reservations)"
            )
        }
        store.close()
        results.put(("ok", columns))
    except BaseException as exc:  # pragma: no cover - reported in parent
        results.put(("error", f"{type(exc).__name__}: {exc}"))


def _wait_for_migration_contender(process, ready, results, *, deadline, label):
    """Observe one spawned contender without hiding an early child exit."""

    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AssertionError(f"{label} did not reach the migration boundary")
        if ready.wait(timeout=min(remaining, 0.1)):
            return
        if process.exitcode is not None:
            try:
                outcome = results.get(timeout=1)
            except Exception as exc:  # pragma: no cover - assertion detail
                outcome = f"result unavailable: {type(exc).__name__}: {exc}"
            raise AssertionError(
                f"{label} exited with {process.exitcode} before migration readiness: "
                f"{outcome}"
            )


def _acquire(store: ReviewCapacityStore, *, project: str, task: str, rid: str):
    return store.acquire(
        project_id=project,
        task_id=task,
        source_branch=f"branch-{task}",
        target_branch="main",
        limit=1,
        open_review_ids=[],
        reservation_id=rid,
    )


def test_compare_and_swap_serializes_project_capacity(tmp_path):
    store = ReviewCapacityStore(str(tmp_path / "review-capacity.sqlite3"))

    first = _acquire(store, project="proj-1", task="TASK-1", rid="res-1")
    second = _acquire(store, project="proj-1", task="TASK-2", rid="res-2")

    assert first is not None
    assert second is None


def test_committed_reservation_survives_restart_and_deduplicates_live_review(
    tmp_path,
):
    path = str(tmp_path / "review-capacity.sqlite3")
    store = ReviewCapacityStore(path)
    reservation = _acquire(store, project="proj-1", task="TASK-1", rid="res-1")
    assert reservation is not None
    assert store.commit("res-1", "101") is True
    store.close()

    restarted = ReviewCapacityStore(path)
    assert restarted.count("proj-1", []) == 1
    # The durable reservation and the forge listing describe the same PR.
    assert restarted.count("proj-1", ["101"]) == 1
    assert _acquire(
        restarted,
        project="proj-1",
        task="TASK-2",
        rid="res-2",
    ) is None


def test_release_on_close_or_merge_frees_slot(tmp_path):
    store = ReviewCapacityStore(str(tmp_path / "review-capacity.sqlite3"))
    reservation = _acquire(store, project="proj-1", task="TASK-1", rid="res-1")
    assert reservation is not None
    store.commit("res-1", "101")

    assert store.release(project_id="proj-1", review_id="101") == 1
    assert _acquire(
        store,
        project="proj-1",
        task="TASK-2",
        rid="res-2",
    ) is not None


def test_live_empty_listing_preserves_recent_commit_until_propagation_grace(
    tmp_path,
    monkeypatch,
):
    clock = [100.0]
    monkeypatch.setattr("oompah.review_capacity.time.time", lambda: clock[0])
    store = ReviewCapacityStore(str(tmp_path / "review-capacity.sqlite3"))
    reservation = store.adopt(
        project_id="proj-1",
        task_id="TASK-1",
        source_branch="branch-1",
        target_branch="main",
        review_id="101",
        reservation_id="res-1",
    )

    assert store.reconcile_open_reviews(
        "proj-1",
        [],
        minimum_committed_age_seconds=60,
    ) == 0
    assert store.active("proj-1") == [reservation]

    clock[0] = 161.0
    assert store.reconcile_open_reviews(
        "proj-1",
        [],
        minimum_committed_age_seconds=60,
    ) == 1
    assert store.active("proj-1") == []


def test_projects_do_not_share_review_capacity(tmp_path):
    store = ReviewCapacityStore(str(tmp_path / "review-capacity.sqlite3"))
    assert _acquire(store, project="proj-1", task="TASK-1", rid="res-1")
    assert _acquire(store, project="proj-2", task="TASK-2", rid="res-2")


def test_create_failure_release_is_retryable(tmp_path):
    store = ReviewCapacityStore(str(tmp_path / "review-capacity.sqlite3"))
    reservation = _acquire(store, project="proj-1", task="TASK-1", rid="res-1")
    assert reservation is not None

    assert store.release(project_id="proj-1", reservation_id="res-1") == 1
    assert _acquire(
        store,
        project="proj-1",
        task="TASK-2",
        rid="res-2",
    ) is not None


def test_uncommitted_lease_expires_without_stranding_capacity(tmp_path, monkeypatch):
    store = ReviewCapacityStore(str(tmp_path / "review-capacity.sqlite3"))
    clock = [100.0]
    monkeypatch.setattr("oompah.review_capacity.time.time", lambda: clock[0])
    reservation = store.acquire(
        project_id="proj-1",
        task_id="TASK-1",
        source_branch="branch-1",
        target_branch="main",
        limit=1,
        open_review_ids=[],
        reservation_id="res-1",
        lease_ttl_seconds=10,
    )
    assert reservation is not None

    clock[0] = 111.0
    assert _acquire(store, project="proj-1", task="TASK-2", rid="res-2")


def test_exact_delivery_authority_survives_restart(tmp_path):
    path = str(tmp_path / "review-capacity.sqlite3")
    store = ReviewCapacityStore(path)
    reservation = store.acquire(
        project_id="proj-1",
        task_id="TASK-1",
        source_branch="branch-TASK-1",
        target_branch="main",
        limit=1,
        open_review_ids=[],
        reservation_id="res-exact",
        authority_generation="delivery-generation",
        head_sha="ABC123",
    )
    assert reservation is not None
    store.close()

    restarted = ReviewCapacityStore(path)
    assert restarted.active("proj-1") == [
        reservation.__class__(
            reservation_id="res-exact",
            project_id="proj-1",
            task_id="TASK-1",
            source_branch="branch-TASK-1",
            target_branch="main",
            review_id=None,
            acquired_at=reservation.acquired_at,
            lease_expires_at=reservation.lease_expires_at,
            authority_generation="delivery-generation",
            head_sha="abc123",
        )
    ]


def test_schema_one_database_migrates_exact_authority_columns(tmp_path):
    path = tmp_path / "review-capacity.sqlite3"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        INSERT INTO schema_meta(key, value) VALUES('version', '1');
        CREATE TABLE review_capacity_reservations (
            reservation_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            source_branch TEXT NOT NULL,
            target_branch TEXT NOT NULL,
            review_id TEXT,
            acquired_at REAL NOT NULL,
            lease_expires_at REAL,
            released_at REAL
        );
        INSERT INTO review_capacity_reservations VALUES(
            'legacy', 'proj-1', 'TASK-1', 'branch-TASK-1', 'main',
            NULL, 100.0, 99999999999.0, NULL
        );
        """
    )
    connection.commit()
    connection.close()

    store = ReviewCapacityStore(str(path))
    [reservation] = store.active("proj-1")
    assert reservation.reservation_id == "legacy"
    assert reservation.authority_generation is None
    assert reservation.head_sha is None
    with sqlite3.connect(path) as migrated:
        columns = {
            row[1]
            for row in migrated.execute(
                "PRAGMA table_info(review_capacity_reservations)"
            )
        }
        version = migrated.execute(
            "SELECT value FROM schema_meta WHERE key = 'version'"
        ).fetchone()[0]
    assert {"authority_generation", "head_sha"} <= columns
    assert version == "2"


@pytest.mark.timeout(90)
def test_schema_one_concurrent_process_initialization_is_serialized(tmp_path):
    path = tmp_path / "review-capacity.sqlite3"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        INSERT INTO schema_meta(key, value) VALUES('version', '1');
        CREATE TABLE review_capacity_reservations (
            reservation_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            source_branch TEXT NOT NULL,
            target_branch TEXT NOT NULL,
            review_id TEXT,
            acquired_at REAL NOT NULL,
            lease_expires_at REAL,
            released_at REAL
        );
        """
    )
    connection.commit()
    connection.close()

    context = multiprocessing.get_context("spawn")
    # Each child explicitly publishes readiness immediately before BEGIN
    # IMMEDIATE, then waits for one parent-controlled release.  This preserves
    # simultaneous contention without requiring every spawned interpreter to
    # finish imports inside a fragile Barrier timeout under a saturated gate.
    ready_events = [context.Event() for _ in range(2)]
    migration_release = context.Event()
    result_queues = [context.Queue() for _ in range(2)]
    processes = [
        context.Process(
            target=_open_capacity_store_concurrently,
            args=(str(path), ready, migration_release, results),
        )
        for ready, results in zip(ready_events, result_queues)
    ]
    observed = []
    try:
        for process in processes:
            process.start()
        deadline = time.monotonic() + 60
        for index, (process, ready, results) in enumerate(
            zip(processes, ready_events, result_queues)
        ):
            _wait_for_migration_contender(
                process,
                ready,
                results,
                deadline=deadline,
                label=f"migration contender {index}",
            )
        migration_release.set()
        observed = [
            results.get(timeout=max(deadline - time.monotonic(), 0.1))
            for results in result_queues
        ]
        for process in processes:
            process.join(timeout=max(deadline - time.monotonic(), 0.1))
            assert process.exitcode == 0
    finally:
        migration_release.set()
        for process in processes:
            if process.is_alive():
                process.terminate()
        for process in processes:
            process.join(timeout=5)
        for results in result_queues:
            results.close()
            results.join_thread()

    assert [status for status, _payload in observed] == ["ok", "ok"]
    for _status, columns in observed:
        assert {"authority_generation", "head_sha"} <= set(columns)
    with sqlite3.connect(path) as migrated:
        version = migrated.execute(
            "SELECT value FROM schema_meta WHERE key = 'version'"
        ).fetchone()[0]
    assert version == "2"
