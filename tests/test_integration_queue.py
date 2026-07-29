from concurrent.futures import ThreadPoolExecutor

from oompah.integration_queue import IntegrationQueueStore


def _enqueue(store, task, *, priority=1, submitted_at=None):
    return store.enqueue(
        project_id="p1",
        epic_id="E-1",
        task_id=task,
        task_branch=f"task/{task}",
        head_sha=(task.lower() * 8)[:8],
        priority=priority,
        submitted_at=submitted_at,
    )


def test_out_of_order_submission_waits_for_finish_dependency(tmp_path):
    store = IntegrationQueueStore(str(tmp_path / "queue.sqlite3"))
    _enqueue(store, "B", priority=0, submitted_at="2026-01-01T00:00:00Z")
    _enqueue(store, "A", priority=5, submitted_at="2026-01-02T00:00:00Z")
    dependency_map = {"B": ["A"], "A": []}

    first = store.claim_next(
        project_id="p1",
        epic_id="E-1",
        lease_owner="worker-1",
        dependency_map=dependency_map,
        satisfied=set(),
    )
    assert first is not None and first.task_id == "A"
    assert store.complete("p1", "A", lease_owner="worker-1")
    second = store.claim_next(
        project_id="p1",
        epic_id="E-1",
        lease_owner="worker-2",
        dependency_map=dependency_map,
        satisfied={"A"},
    )
    assert second is not None and second.task_id == "B"


def test_identical_resubmit_is_idempotent_and_new_head_requeues(tmp_path):
    store = IntegrationQueueStore(str(tmp_path / "queue.sqlite3"))
    first = _enqueue(store, "A")
    repeated = _enqueue(store, "A")
    assert repeated == first
    updated = store.enqueue(
        project_id="p1",
        epic_id="E-1",
        task_id="A",
        task_branch="task/A",
        head_sha="feedbeef",
    )
    assert updated.head_sha == "feedbeef"
    assert updated.state == "ready"


def test_expired_lease_recovers_after_restart(tmp_path):
    path = tmp_path / "queue.sqlite3"
    store = IntegrationQueueStore(str(path))
    _enqueue(store, "A")
    claimed = store.claim_next(
        project_id="p1",
        epic_id="E-1",
        lease_owner="dead-instance",
        dependency_map={"A": []},
        satisfied=set(),
        lease_seconds=1,
        now=10,
    )
    assert claimed is not None
    store.close()

    reopened = IntegrationQueueStore(str(path))
    assert reopened.recover_expired(now=12) == 1
    recovered = reopened.claim_next(
        project_id="p1",
        epic_id="E-1",
        lease_owner="new-instance",
        dependency_map={"A": []},
        satisfied=set(),
        now=12,
    )
    assert recovered is not None
    assert recovered.attempts == 2


def test_concurrent_claimers_only_receive_one_lease(tmp_path):
    store = IntegrationQueueStore(str(tmp_path / "queue.sqlite3"))
    _enqueue(store, "A")

    def _claim(owner):
        return store.claim_next(
            project_id="p1",
            epic_id="E-1",
            lease_owner=owner,
            dependency_map={"A": []},
            satisfied=set(),
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        claimed = list(pool.map(_claim, ["one", "two", "three", "four"]))
    assert len([item for item in claimed if item is not None]) == 1
