"""Durable review-capacity reservation coverage for OOMPAH-646."""

from __future__ import annotations

import multiprocessing
import sqlite3

from oompah.review_capacity import ReviewCapacityStore


class _BarrierReviewCapacityStore(ReviewCapacityStore):
    """Hold spawned contenders at the exact migration boundary."""

    def __init__(self, path, migration_barrier):
        self._migration_barrier = migration_barrier
        super().__init__(path)

    def _migrate_schema(self):
        self._migration_barrier.wait(timeout=10)
        super()._migrate_schema()


def _open_capacity_store_concurrently(path, migration_barrier, results):
    """Open one store after every migration contender is ready."""

    try:
        store = _BarrierReviewCapacityStore(path, migration_barrier)
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
    # Two children plus the parent rendezvous after each spawned interpreter
    # has completed imports/schema setup and immediately before BEGIN
    # IMMEDIATE.  Neither contender can finish migration before the other is
    # actually ready to contend.
    migration_barrier = context.Barrier(3)
    results = context.Queue()
    processes = [
        context.Process(
            target=_open_capacity_store_concurrently,
            args=(str(path), migration_barrier, results),
        )
        for _ in range(2)
    ]
    observed = []
    try:
        for process in processes:
            process.start()
        migration_barrier.wait(timeout=15)
        observed = [results.get(timeout=15) for _ in processes]
        for process in processes:
            process.join(timeout=15)
            assert process.exitcode == 0
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
        for process in processes:
            process.join(timeout=5)
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
