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


def test_backoff_skips_poisoned_row_and_advances_independent_epic(tmp_path):
    store = IntegrationQueueStore(str(tmp_path / "queue.sqlite3"))
    poisoned = store.enqueue(
        project_id="p1",
        epic_id="EPIC-POISON",
        task_id="POISON",
        task_branch="task/POISON",
        head_sha="deadbeef",
        priority=0,
    )
    independent = store.enqueue(
        project_id="p1",
        epic_id="EPIC-INDEPENDENT",
        task_id="HEALTHY",
        task_branch="task/HEALTHY",
        head_sha="cafebabe",
        priority=0,
    )
    claimed = store.claim_next(
        project_id="p1",
        epic_id=poisoned.epic_id,
        lease_owner="worker-1",
        dependency_map={"POISON": ()},
        satisfied=set(),
        now=10,
    )
    assert claimed is not None
    assert store.fail(
        "p1",
        "POISON",
        lease_owner="worker-1",
        error="untracked helper collision",
        retryable=True,
        retry_at=100,
    )

    assert (
        store.claim_next(
            project_id="p1",
            epic_id=poisoned.epic_id,
            lease_owner="worker-2",
            dependency_map={"POISON": ()},
            satisfied=set(),
            now=10,
        )
        is None
    )
    advanced = store.claim_next(
        project_id="p1",
        epic_id=independent.epic_id,
        lease_owner="worker-3",
        dependency_map={"HEALTHY": ()},
        satisfied=set(),
        now=10,
    )
    assert advanced is not None and advanced.task_id == "HEALTHY"


def test_claim_attempt_budget_bounds_repeated_failures(tmp_path):
    store = IntegrationQueueStore(str(tmp_path / "queue.sqlite3"))
    _enqueue(store, "A")
    for attempt, owner in ((1, "worker-1"), (2, "worker-2")):
        claimed = store.claim_next(
            project_id="p1",
            epic_id="E-1",
            lease_owner=owner,
            dependency_map={"A": ()},
            satisfied=set(),
            now=attempt,
            max_attempts=2,
        )
        assert claimed is not None and claimed.attempts == attempt
        assert store.fail(
            "p1",
            "A",
            lease_owner=owner,
            error=f"failure {attempt}",
            retryable=True,
            retry_at=attempt,
        )

    assert (
        store.claim_next(
            project_id="p1",
            epic_id="E-1",
            lease_owner="worker-3",
            dependency_map={"A": ()},
            satisfied=set(),
            now=3,
            max_attempts=2,
        )
        is None
    )
    row = store.items(project_id="p1", epic_id="E-1")[0]
    assert row.attempts == 2
    assert row.state == "ready"


def test_automatic_new_head_retry_preserves_attempts_and_backoff(tmp_path):
    store = IntegrationQueueStore(str(tmp_path / "queue.sqlite3"))
    original = _enqueue(store, "A")
    claimed = store.claim_next(
        project_id="p1",
        epic_id="E-1",
        lease_owner="worker-1",
        dependency_map={"A": ()},
        satisfied=set(),
        now=1,
    )
    assert claimed is not None
    assert store.fail(
        "p1",
        "A",
        lease_owner="worker-1",
        error="epic race",
        retryable=True,
        retry_at=100,
    )
    updated = store.enqueue(
        project_id="p1",
        epic_id="E-1",
        task_id="A",
        task_branch=original.task_branch,
        head_sha="new-head",
        preserve_attempts=True,
        retry_at=100,
    )
    assert updated.attempts == 1
    assert updated.next_retry_at == 100
    assert updated.state == "ready"


def test_cancel_invalidates_active_lease_and_rejects_late_finish(tmp_path):
    store = IntegrationQueueStore(str(tmp_path / "queue.sqlite3"))
    _enqueue(store, "A")
    claimed = store.claim_next(
        project_id="p1",
        epic_id="E-1",
        lease_owner="worker-1",
        dependency_map={"A": []},
        satisfied=set(),
    )
    assert claimed is not None

    assert store.cancel("p1", "A", reason="task became Done")
    retired = store.items(project_id="p1", epic_id="E-1")[0]
    assert retired.state == "cancelled"
    assert retired.lease_owner is None
    assert retired.last_error == "task became Done"
    assert not store.complete("p1", "A", lease_owner="worker-1")
    assert not store.fail(
        "p1",
        "A",
        lease_owner="worker-1",
        error="late failure",
    )
    reflowed = store.enqueue(
        project_id="p1",
        epic_id="E-1",
        task_id="A",
        task_branch=retired.task_branch,
        head_sha=retired.head_sha,
        explicit_retry=True,
    )
    assert reflowed.state == "ready"
    assert reflowed.retry_forced is True


def test_owns_active_lease_requires_exact_current_claim(tmp_path):
    store = IntegrationQueueStore(str(tmp_path / "queue.sqlite3"))
    queued = _enqueue(store, "A")

    assert not store.owns_active_lease(
        project_id=queued.project_id,
        task_id=queued.task_id,
        task_branch=queued.task_branch,
        head_sha=queued.head_sha,
        lease_owner="worker-1",
    )

    first = store.claim_next(
        project_id="p1",
        epic_id="E-1",
        lease_owner="worker-1",
        dependency_map={"A": []},
        satisfied=set(),
        lease_seconds=1,
        now=10,
    )
    assert first is not None
    assert store.owns_active_lease(
        project_id=first.project_id,
        task_id=first.task_id,
        task_branch=first.task_branch,
        head_sha=first.head_sha,
        lease_owner=first.lease_owner,
        now=10.5,
    )
    # Expiry withdraws authority even before a recovery/claim rewrites the
    # durable row.  A stale executor cannot use the interval between deadline
    # and replacement as an authorization window.
    assert not store.owns_active_lease(
        project_id=first.project_id,
        task_id=first.task_id,
        task_branch=first.task_branch,
        head_sha=first.head_sha,
        lease_owner=first.lease_owner,
        now=11,
    )
    assert not store.owns_active_lease(
        project_id=first.project_id,
        task_id=first.task_id,
        task_branch=first.task_branch,
        head_sha="different-head",
        lease_owner=first.lease_owner,
        now=10.5,
    )

    replacement = store.claim_next(
        project_id="p1",
        epic_id="E-1",
        lease_owner="worker-2",
        dependency_map={"A": []},
        satisfied=set(),
        now=12,
    )
    assert replacement is not None
    assert not store.owns_active_lease(
        project_id=first.project_id,
        task_id=first.task_id,
        task_branch=first.task_branch,
        head_sha=first.head_sha,
        lease_owner=first.lease_owner,
        now=12,
    )
    assert store.owns_active_lease(
        project_id=replacement.project_id,
        task_id=replacement.task_id,
        task_branch=replacement.task_branch,
        head_sha=replacement.head_sha,
        lease_owner=replacement.lease_owner,
        now=12,
    )


def test_explicit_retry_unblocks_blocked_row_with_same_head(tmp_path):
    store = IntegrationQueueStore(str(tmp_path / "queue.sqlite3"))
    original = _enqueue(store, "A")
    claimed = store.claim_next(
        project_id="p1",
        epic_id="E-1",
        lease_owner="worker-1",
        dependency_map={"A": []},
        satisfied=set(),
    )
    assert claimed is not None
    assert store.fail(
        "p1",
        "A",
        lease_owner="worker-1",
        error="permanent failure",
        retryable=False,
    )
    blocked = store.items(project_id="p1", epic_id="E-1")[0]
    assert blocked.state == "blocked"

    synced = store.enqueue(
        project_id="p1",
        epic_id="E-1",
        task_id="A",
        task_branch=original.task_branch,
        head_sha=original.head_sha,
    )
    assert synced.state == "blocked"

    retried = store.enqueue(
        project_id="p1",
        epic_id="E-1",
        task_id="A",
        task_branch=original.task_branch,
        head_sha=original.head_sha,
        explicit_retry=True,
    )
    assert retried.state == "ready"
    assert retried.attempts == 0
    assert retried.last_error is None


def test_explicit_retry_preserves_nonblocked_identical_rows(tmp_path):
    store = IntegrationQueueStore(str(tmp_path / "queue.sqlite3"))

    ready = _enqueue(store, "A")
    assert store.enqueue(
        project_id="p1",
        epic_id="E-1",
        task_id="A",
        task_branch=ready.task_branch,
        head_sha=ready.head_sha,
        explicit_retry=True,
    ) == ready

    claimed = store.claim_next(
        project_id="p1",
        epic_id="E-1",
        lease_owner="worker-1",
        dependency_map={"A": []},
        satisfied=set(),
    )
    assert claimed is not None
    still_integrating = store.enqueue(
        project_id="p1",
        epic_id="E-1",
        task_id="A",
        task_branch=ready.task_branch,
        head_sha=ready.head_sha,
        explicit_retry=True,
    )
    assert still_integrating.state == "integrating"
    assert still_integrating.lease_owner == "worker-1"

    assert store.complete("p1", "A", lease_owner="worker-1")
    integrated = store.items(project_id="p1", epic_id="E-1")[0]
    repeated = store.enqueue(
        project_id="p1",
        epic_id="E-1",
        task_id="A",
        task_branch=ready.task_branch,
        head_sha=ready.head_sha,
        explicit_retry=True,
    )
    assert repeated == integrated
    assert repeated.state == "integrated"


def test_explicit_ready_reflow_rearms_identical_integrated_row(tmp_path):
    store = IntegrationQueueStore(str(tmp_path / "queue.sqlite3"))
    original = _enqueue(store, "A")
    claimed = store.claim_next(
        project_id="p1",
        epic_id="E-1",
        lease_owner="worker-1",
        dependency_map={"A": []},
        satisfied=set(),
    )
    assert claimed is not None
    assert store.complete("p1", "A", lease_owner="worker-1")

    background_sync = store.enqueue(
        project_id="p1",
        epic_id="E-1",
        task_id="A",
        task_branch=original.task_branch,
        head_sha=original.head_sha,
    )
    assert background_sync.state == "integrated"

    reflowed = store.enqueue(
        project_id="p1",
        epic_id="E-1",
        task_id="A",
        task_branch=original.task_branch,
        head_sha=original.head_sha,
        explicit_retry=True,
        rearm_integrated=True,
    )
    assert reflowed.state == "ready"
    assert reflowed.attempts == 0
    assert reflowed.lease_owner is None
    assert reflowed.last_error is None


def test_explicit_ready_reflow_does_not_reset_active_row(tmp_path):
    store = IntegrationQueueStore(str(tmp_path / "queue.sqlite3"))
    original = _enqueue(store, "A")

    repeated_ready = store.enqueue(
        project_id="p1",
        epic_id="E-1",
        task_id="A",
        task_branch=original.task_branch,
        head_sha=original.head_sha,
        explicit_retry=True,
        rearm_integrated=True,
    )
    assert repeated_ready == original

    claimed = store.claim_next(
        project_id="p1",
        epic_id="E-1",
        lease_owner="worker-1",
        dependency_map={"A": []},
        satisfied=set(),
    )
    assert claimed is not None
    repeated_integrating = store.enqueue(
        project_id="p1",
        epic_id="E-1",
        task_id="A",
        task_branch=original.task_branch,
        head_sha=original.head_sha,
        explicit_retry=True,
        rearm_integrated=True,
    )
    assert repeated_integrating == claimed
    assert repeated_integrating.lease_owner == "worker-1"


def test_recover_abandoned_leases_at_startup(tmp_path):
    store = IntegrationQueueStore(str(tmp_path / "queue.sqlite3"))
    original = _enqueue(store, "A")
    claimed = store.claim_next(
        project_id="p1",
        epic_id="E-1",
        lease_owner="dead-instance",
        dependency_map={"A": []},
        satisfied=set(),
    )
    assert claimed is not None

    assert store.recover_abandoned() == 1
    recovered = store.items(project_id="p1", epic_id="E-1")[0]
    assert recovered.state == "ready"
    assert recovered.head_sha == original.head_sha
    assert recovered.attempts == 1
    assert recovered.lease_owner is None
    assert recovered.lease_expires_at is None
    assert store.recover_abandoned() == 0


def test_explicit_retry_sets_retry_forced_flag(tmp_path):
    """explicit_retry should set retry_forced flag when unblocking."""
    store = IntegrationQueueStore(str(tmp_path / "queue.sqlite3"))
    original = _enqueue(store, "A")
    claimed = store.claim_next(
        project_id="p1",
        epic_id="E-1",
        lease_owner="worker-1",
        dependency_map={"A": []},
        satisfied=set(),
    )
    assert claimed is not None
    assert store.fail(
        "p1",
        "A",
        lease_owner="worker-1",
        error="permanent failure",
        retryable=False,
    )
    blocked = store.items(project_id="p1", epic_id="E-1")[0]
    assert blocked.state == "blocked"
    assert blocked.retry_forced is False

    # explicit_retry should set retry_forced=True
    retried = store.enqueue(
        project_id="p1",
        epic_id="E-1",
        task_id="A",
        task_branch=original.task_branch,
        head_sha=original.head_sha,
        explicit_retry=True,
    )
    assert retried.state == "ready"
    assert retried.retry_forced is True


def test_retry_forced_cleared_when_claimed(tmp_path):
    """retry_forced flag should be cleared when item is claimed."""
    store = IntegrationQueueStore(str(tmp_path / "queue.sqlite3"))
    original = _enqueue(store, "A")
    claimed = store.claim_next(
        project_id="p1",
        epic_id="E-1",
        lease_owner="worker-1",
        dependency_map={"A": []},
        satisfied=set(),
    )
    assert claimed is not None
    assert store.fail(
        "p1",
        "A",
        lease_owner="worker-1",
        error="CI failed",
        retryable=False,
    )

    # Reset with explicit retry
    retried = store.enqueue(
        project_id="p1",
        epic_id="E-1",
        task_id="A",
        task_branch=original.task_branch,
        head_sha=original.head_sha,
        explicit_retry=True,
    )
    assert retried.retry_forced is True

    # Claim should clear retry_forced
    claimed_again = store.claim_next(
        project_id="p1",
        epic_id="E-1",
        lease_owner="worker-2",
        dependency_map={"A": []},
        satisfied=set(),
    )
    assert claimed_again is not None
    assert claimed_again.retry_forced is False


def test_new_head_on_explicit_retry_row_clears_retry_forced(tmp_path):
    """Regular enqueue with new head should clear retry_forced flag."""
    store = IntegrationQueueStore(str(tmp_path / "queue.sqlite3"))
    original = _enqueue(store, "A")
    claimed = store.claim_next(
        project_id="p1",
        epic_id="E-1",
        lease_owner="worker-1",
        dependency_map={"A": []},
        satisfied=set(),
    )
    assert claimed is not None
    assert store.fail(
        "p1",
        "A",
        lease_owner="worker-1",
        error="CI failed",
        retryable=False,
    )

    # Reset with explicit retry
    retried = store.enqueue(
        project_id="p1",
        epic_id="E-1",
        task_id="A",
        task_branch=original.task_branch,
        head_sha=original.head_sha,
        explicit_retry=True,
    )
    assert retried.retry_forced is True

    # New head enqueue should clear retry_forced
    new_head = store.enqueue(
        project_id="p1",
        epic_id="E-1",
        task_id="A",
        task_branch=original.task_branch,
        head_sha="newheadsha123",
    )
    assert new_head.state == "ready"
    assert new_head.retry_forced is False  # Flag is cleared for new submissions
