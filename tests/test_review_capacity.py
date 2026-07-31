"""Durable review-capacity reservation coverage for OOMPAH-646."""

from __future__ import annotations

from oompah.review_capacity import ReviewCapacityStore


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
