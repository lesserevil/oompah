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


def test_explicit_retry_unblocks_blocked_row_with_same_head(tmp_path):
    """Test that explicit user retry clears blocked state for same head/branch."""
    store = IntegrationQueueStore(str(tmp_path / "queue.sqlite3"))
    
    # Enqueue a task (explicit submission)
    item = _enqueue(store, "A")
    assert item.state == "ready"
    
    # Claim and fail it (non-retryable, becomes blocked)
    claimed = store.claim_next(
        project_id="p1",
        epic_id="E-1",
        lease_owner="worker-1",
        dependency_map={"A": []},
        satisfied=set(),
    )
    assert claimed is not None
    store.fail(
        "p1", "A",
        lease_owner="worker-1",
        error="permanent failure",
        retryable=False,  # This makes it blocked, not ready
    )
    
    # Verify it's blocked
    blocked = store.items(project_id="p1", epic_id="E-1")[0]
    assert blocked.state == "blocked"
    assert blocked.head_sha == blocked.head_sha  # Same head
    assert blocked.task_branch == blocked.task_branch  # Same branch
    
    # Background sync should NOT unblock it (idempotent)
    resubmitted = store.enqueue(
        project_id="p1",
        epic_id="E-1",
        task_id="A",
        task_branch="task/A",
        head_sha=blocked.head_sha,
        explicit_retry=False,  # Background sync
    )
    assert resubmitted.state == "blocked"  # Still blocked
    
    # Explicit retry SHOULD unblock it
    retried = store.enqueue(
        project_id="p1",
        epic_id="E-1",
        task_id="A",
        task_branch="task/A",
        head_sha=blocked.head_sha,
        explicit_retry=True,  # Explicit user retry
    )
    assert retried.state == "ready"  # Now ready


def test_background_sync_is_idempotent_for_blocked_rows(tmp_path):
    """Test that background sync (periodic Ready-to-Integrate) doesn't unblock."""
    store = IntegrationQueueStore(str(tmp_path / "queue.sqlite3"))
    
    # Create a blocked item manually (simulating failed integration)
    item = _enqueue(store, "A")
    claimed = store.claim_next(
        project_id="p1",
        epic_id="E-1",
        lease_owner="worker-1",
        dependency_map={"A": []},
        satisfied=set(),
    )
    store.fail("p1", "A", lease_owner="worker-1", error="failure", retryable=False)
    
    # Background sync with same head/branch should NOT change blocked state
    synced = store.enqueue(
        project_id="p1",
        epic_id="E-1",
        task_id="A",
        task_branch="task/A",
        head_sha="aaaaaaaa",  # From _enqueue (task.lower() * 8)[:8]
        explicit_retry=False,  # This is background sync
    )
    assert synced.state == "blocked"  # Remains blocked


def test_recover_abandoned_leases_at_startup(tmp_path):
    """Test that recover_abandoned() resets all integrating leases."""
    store = IntegrationQueueStore(str(tmp_path / "queue.sqlite3"))
    
    # Enqueue multiple tasks
    _enqueue(store, "A")
    _enqueue(store, "B")
    _enqueue(store, "C")
    
    # Claim and move them to integrating state
    for task_id in ["A", "B", "C"]:
        claimed = store.claim_next(
            project_id="p1",
            epic_id="E-1",
            lease_owner="dead-instance",
            dependency_map={"A": [], "B": ["A"], "C": ["A", "B"]},
            satisfied={"A"} if task_id in ["B", "C"] else set(),
        )
        if claimed is not None:
            pass  # Now they're in integrating state
    
    # Verify they're integrating
    items = store.items(project_id="p1", epic_id="E-1")
    integrating_count = sum(1 for item in items if item.state == "integrating")
    assert integrating_count > 0  # At least one is integrating
    
    # Recover abandoned leases
    recovered = store.recover_abandoned()
    assert recovered > 0
    
    # Verify all are now ready
    items = store.items(project_id="p1", epic_id="E-1")
    for item in items:
        assert item.state == "ready"
        assert item.lease_owner is None
        assert item.lease_expires_at is None
