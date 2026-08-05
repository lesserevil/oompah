from concurrent.futures import ThreadPoolExecutor

from oompah.integration_queue import (
    STANDALONE_RECLASSIFICATION_REASON,
    IntegrationQueueStore,
)


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


def test_sqlite_memory_dsn_is_not_converted_to_a_workspace_file():
    store = IntegrationQueueStore(":memory:")
    try:
        assert store.path == ":memory:"
        assert _enqueue(store, "A").task_id == "A"
    finally:
        store.close()


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


def test_same_head_with_new_recorded_target_is_a_new_authority(tmp_path):
    store = IntegrationQueueStore(str(tmp_path / "queue.sqlite3"))
    first = store.enqueue(
        project_id="p1",
        epic_id="OOMPAH-804",
        task_id="OOMPAH-834",
        task_branch="epic-OOMPAH-804--task-OOMPAH-834",
        head_sha="a" * 40,
        base_branch="epic-OOMPAH-804",
    )
    corrected = store.enqueue(
        project_id="p1",
        epic_id="OOMPAH-804",
        task_id="OOMPAH-834",
        task_branch=first.task_branch,
        head_sha=first.head_sha,
        base_branch="epic-OOMPAH-768--task-OOMPAH-804",
    )

    assert corrected.base_branch == "epic-OOMPAH-768--task-OOMPAH-804"
    assert corrected.updated_at >= first.updated_at


def test_same_head_with_new_base_sha_is_a_new_authority(tmp_path):
    store = IntegrationQueueStore(str(tmp_path / "queue.sqlite3"))
    first = store.enqueue(
        project_id="p1",
        epic_id="OOMPAH-804",
        task_id="OOMPAH-834",
        task_branch="epic-OOMPAH-804--task-OOMPAH-834",
        head_sha="a" * 40,
        base_branch="epic-OOMPAH-768--task-OOMPAH-804",
        base_sha="b" * 40,
    )
    claimed = store.claim_next(
        project_id="p1",
        epic_id="OOMPAH-804",
        lease_owner="old-base-generation",
        dependency_map={"OOMPAH-834": ()},
        satisfied=set(),
    )
    assert claimed is not None
    corrected = store.enqueue(
        project_id="p1",
        epic_id="OOMPAH-804",
        task_id="OOMPAH-834",
        task_branch=first.task_branch,
        head_sha=first.head_sha,
        base_branch=first.base_branch,
        base_sha="c" * 40,
    )

    assert corrected.base_sha == "c" * 40
    assert corrected.state == "ready"
    assert corrected.lease_owner is None
    assert corrected.updated_at >= first.updated_at


def test_candidate_generation_survives_restart_and_lease_recovery(tmp_path):
    path = tmp_path / "queue.sqlite3"
    store = IntegrationQueueStore(str(path))
    store.enqueue(
        project_id="p1",
        epic_id="OOMPAH-804",
        task_id="OOMPAH-834",
        task_branch="epic-OOMPAH-804--task-OOMPAH-834",
        head_sha="a" * 40,
        base_branch="epic-OOMPAH-768--task-OOMPAH-804",
    )
    claimed = store.claim_next(
        project_id="p1",
        epic_id="OOMPAH-804",
        lease_owner="dead-instance",
        dependency_map={"OOMPAH-834": ()},
        satisfied=set(),
    )
    assert claimed is not None
    candidate = store.record_candidate(
        project_id="p1",
        task_id="OOMPAH-834",
        lease_owner="dead-instance",
        expected_head_sha="a" * 40,
        expected_candidate_head_sha=None,
        candidate_head_sha="b" * 40,
        candidate_base_sha="c" * 40,
    )
    assert candidate is not None
    generation = candidate.authority_generation()
    store.close()

    reopened = IntegrationQueueStore(str(path))
    durable = reopened.get("p1", "OOMPAH-834")
    assert durable is not None
    assert durable.base_branch == "epic-OOMPAH-768--task-OOMPAH-804"
    assert durable.candidate_head_sha == "b" * 40
    assert durable.candidate_base_sha == "c" * 40
    assert durable.authority_generation() == generation
    assert reopened.recover_abandoned() == 1
    recovered = reopened.claim_next(
        project_id="p1",
        epic_id="OOMPAH-804",
        lease_owner="replacement",
        dependency_map={"OOMPAH-834": ()},
        satisfied=set(),
    )
    assert recovered is not None
    assert recovered.candidate_head_sha == "b" * 40
    reopened.close()


def test_compare_and_swap_cancel_preserves_new_head(tmp_path):
    store = IntegrationQueueStore(str(tmp_path / "queue.sqlite3"))
    queued = _enqueue(store, "A")
    replacement = store.enqueue(
        project_id="p1",
        epic_id="E-1",
        task_id="A",
        task_branch=queued.task_branch,
        head_sha="new-head",
    )

    assert not store.cancel(
        "p1",
        "A",
        reason="stale cycle snapshot",
        expected_head_sha=queued.head_sha,
        expected_state="ready",
    )
    current = store.items(project_id="p1", epic_id="E-1")[0]
    assert current == replacement
    assert current.state == "ready"


def test_restore_cancelled_requires_exact_branch_and_head(tmp_path):
    store = IntegrationQueueStore(str(tmp_path / "queue.sqlite3"))
    queued = _enqueue(store, "A")
    assert store.cancel(
        "p1",
        "A",
        reason="container dependency cycle requires authorized repair",
        expected_head_sha=queued.head_sha,
        expected_state="ready",
    )

    assert store.restore_cancelled(
        "p1",
        "A",
        expected_head_sha=queued.head_sha,
        expected_task_branch=queued.task_branch,
        expected_epic_id=queued.epic_id,
    )
    restored = store.items(project_id="p1", epic_id="E-1")[0]
    assert restored.state == "ready"
    assert restored.head_sha == queued.head_sha
    assert not store.restore_cancelled(
        "p1",
        "A",
        expected_head_sha="different",
        expected_task_branch=queued.task_branch,
        expected_epic_id=queued.epic_id,
    )


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


def test_task_scoped_recovery_requires_exact_expired_generation(tmp_path):
    store = IntegrationQueueStore(str(tmp_path / "queue.sqlite3"))
    _enqueue(store, "A")
    claimed = store.claim_next(
        project_id="p1",
        epic_id="E-1",
        lease_owner="legacy-owner",
        dependency_map={"A": []},
        satisfied=set(),
        lease_seconds=5,
        now=10,
    )
    assert claimed is not None

    assert store.recover_task_generation(
        "p1",
        "A",
        expected_generation=claimed.authority_generation(),
        now=14,
    ) is None
    recovered = store.recover_task_generation(
        "p1",
        "A",
        expected_generation=claimed.authority_generation(),
        now=16,
    )

    assert recovered is not None
    assert recovered.state == "ready"
    assert recovered.lease_owner is None


def test_workflow_finish_generation_fences_replacement_and_live_lease(tmp_path):
    store = IntegrationQueueStore(str(tmp_path / "queue.sqlite3"))
    original = _enqueue(store, "A")
    replacement = store.enqueue(
        project_id="p1",
        epic_id="E-1",
        task_id="A",
        task_branch=original.task_branch,
        head_sha="replacement-head",
        explicit_retry=True,
    )

    assert store.finish_task_generation(
        "p1",
        "A",
        expected_generation=original.authority_generation(),
        state="integrated",
    ) is None
    claimed = store.claim_next(
        project_id="p1",
        epic_id="E-1",
        lease_owner="legacy-owner",
        dependency_map={"A": []},
        satisfied=set(),
    )
    assert claimed is not None
    assert store.finish_task_generation(
        "p1",
        "A",
        expected_generation=claimed.authority_generation(),
        state="integrated",
    ) is None
    assert store.get("p1", "A").head_sha == replacement.head_sha


def test_workflow_finish_generation_is_one_exact_idempotency_checkpoint(tmp_path):
    store = IntegrationQueueStore(str(tmp_path / "queue.sqlite3"))
    queued = _enqueue(store, "A")

    finished = store.finish_task_generation(
        "p1",
        "A",
        expected_generation=queued.authority_generation(),
        state="blocked",
        error="ci_failure:failed exact combined-tree gate",
    )

    assert finished is not None
    assert finished.state == "blocked"
    assert finished.attempts == 1
    assert store.finish_task_generation(
        "p1",
        "A",
        expected_generation=queued.authority_generation(),
        state="blocked",
    ) is None
    assert store.get("p1", "A") == finished


def test_workflow_finish_consumes_durable_retry_without_legacy_claim(tmp_path):
    store = IntegrationQueueStore(str(tmp_path / "queue.sqlite3"))
    queued = _enqueue(store, "A")
    blocked = store.finish_task_generation(
        "p1",
        "A",
        expected_generation=queued.authority_generation(),
        state="blocked",
        error="ci_failure:first attempt",
    )
    assert blocked is not None
    retried = store.enqueue(
        project_id="p1",
        epic_id="E-1",
        task_id="A",
        task_branch=blocked.task_branch,
        head_sha=blocked.head_sha,
        explicit_retry=True,
        preserve_attempts=True,
    )
    assert retried.retry_forced

    integrated = store.finish_task_generation(
        "p1",
        "A",
        expected_generation=retried.authority_generation(),
        state="integrated",
    )

    assert integrated is not None
    assert not integrated.retry_forced


def test_integrated_history_scan_is_bounded_and_resumes_after_restart(tmp_path):
    path = tmp_path / "queue.sqlite3"
    store = IntegrationQueueStore(str(path))
    for index in range(5):
        task_id = f"HIST-{index}"
        _enqueue(store, task_id, priority=index)
        claimed = store.claim_next(
            project_id="p1",
            epic_id="E-1",
            lease_owner=f"worker-{index}",
            dependency_map={task_id: ()},
            satisfied=set(),
        )
        assert claimed is not None
        assert store.complete("p1", task_id, lease_owner=f"worker-{index}")

    first_batch = store.items(states=("integrated",), limit=2)
    assert [item.task_id for item in first_batch] == ["HIST-0", "HIST-1"]
    cursor = store.cursor_for(first_batch[-1])
    assert [item.task_id for item in store.items(states=("ready",))] == []
    store.close()

    reopened = IntegrationQueueStore(str(path))
    resumed = reopened.items(states=("integrated",), limit=2, after=cursor)
    assert [item.task_id for item in resumed] == ["HIST-2", "HIST-3"]
    assert reopened.get("p1", "HIST-2") == resumed[0]
    reopened.close()


def test_legacy_integration_checkpoint_is_queue_first_and_exact(tmp_path):
    store = IntegrationQueueStore(str(tmp_path / "queue.sqlite3"))
    queued = _enqueue(store, "A")
    claimed = store.claim_next(
        project_id="p1",
        epic_id="E-1",
        lease_owner="legacy-owner",
        dependency_map={"A": ()},
        satisfied=set(),
    )
    assert claimed is not None

    checkpoint = store.checkpoint_legacy_integration(
        "p1",
        "A",
        lease_owner="legacy-owner",
        expected_task_branch=queued.task_branch,
        expected_head_sha=queued.head_sha,
        rebased_head_sha="rebased-head",
        integrated_sha="landed-head",
        base_sha="epic-base",
    )

    assert checkpoint is not None
    assert checkpoint.state == "integrated"
    assert checkpoint.head_sha == "rebased-head"
    assert checkpoint.rebased_from_head_sha == queued.head_sha
    assert checkpoint.integrated_sha == "landed-head"
    assert checkpoint.history_sequence > 0
    assert store.checkpoint_legacy_integration(
        "p1",
        "A",
        lease_owner="legacy-owner",
        expected_task_branch=queued.task_branch,
        expected_head_sha=queued.head_sha,
        rebased_head_sha="different-head",
        integrated_sha="different-landing",
    ) is None


def test_tracker_first_checkpoint_normalization_rejects_replaced_generation(tmp_path):
    store = IntegrationQueueStore(str(tmp_path / "queue.sqlite3"))
    original = _enqueue(store, "A")
    replacement = store.enqueue(
        project_id="p1",
        epic_id="E-1",
        task_id="A",
        task_branch=original.task_branch,
        head_sha="replacement-submission",
    )

    assert store.normalize_legacy_tracker_checkpoint(
        "p1",
        "A",
        expected_generation=original.authority_generation(),
        task_branch=original.task_branch,
        head_sha="rebased-head",
        integrated_sha="landed-head",
    ) is None

    normalized = store.normalize_legacy_tracker_checkpoint(
        "p1",
        "A",
        expected_generation=replacement.authority_generation(),
        task_branch=replacement.task_branch,
        head_sha="rebased-head",
        integrated_sha="landed-head",
    )
    assert normalized is not None
    assert normalized.state == "integrated"
    assert normalized.rebased_from_head_sha == replacement.head_sha
    assert normalized.head_sha == "rebased-head"
    assert normalized.integrated_sha == "landed-head"
    assert normalized.history_sequence > 0


def test_history_sequence_never_reuses_cursor_after_rearm_and_restart(tmp_path):
    path = tmp_path / "queue.sqlite3"
    store = IntegrationQueueStore(str(path))
    queued = _enqueue(store, "A")
    claimed = store.claim_next(
        project_id="p1",
        epic_id="E-1",
        lease_owner="first-worker",
        dependency_map={"A": ()},
        satisfied=set(),
    )
    assert claimed is not None
    assert store.complete("p1", "A", lease_owner="first-worker")
    first = store.get("p1", "A")
    first_cursor = store.cursor_for(first)
    rearmed = store.enqueue(
        project_id="p1",
        epic_id="E-1",
        task_id="A",
        task_branch=queued.task_branch,
        head_sha=queued.head_sha,
        explicit_retry=True,
        rearm_integrated=True,
    )
    assert rearmed.history_sequence == 0
    store.close()

    reopened = IntegrationQueueStore(str(path))
    claimed = reopened.claim_next(
        project_id="p1",
        epic_id="E-1",
        lease_owner="second-worker",
        dependency_map={"A": ()},
        satisfied=set(),
    )
    assert claimed is not None
    assert reopened.complete("p1", "A", lease_owner="second-worker")
    second = reopened.get("p1", "A")

    assert second.history_sequence > first.history_sequence
    assert reopened.items(states=("integrated",), after=first_cursor) == [second]


def test_tracker_normalization_moves_repaired_landing_after_old_cursor(tmp_path):
    store = IntegrationQueueStore(str(tmp_path / "queue.sqlite3"))
    queued = _enqueue(store, "A")
    claimed = store.claim_next(
        project_id="p1",
        epic_id="E-1",
        lease_owner="legacy-worker",
        dependency_map={"A": ()},
        satisfied=set(),
    )
    assert claimed is not None
    assert store.complete("p1", "A", lease_owner="legacy-worker")
    legacy = store.get("p1", "A")
    legacy_cursor = store.cursor_for(legacy)

    normalized = store.normalize_legacy_tracker_checkpoint(
        "p1",
        "A",
        expected_generation=legacy.authority_generation(),
        task_branch=queued.task_branch,
        head_sha="rebased-head",
        integrated_sha="landed-head",
    )

    assert normalized is not None
    assert normalized.history_sequence > legacy.history_sequence
    assert store.items(states=("integrated",), after=legacy_cursor) == [normalized]


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


def test_preflight_block_preserves_retry_forced_until_gate_claim(tmp_path):
    store = IntegrationQueueStore(str(tmp_path / "queue.sqlite3"))
    original = store.enqueue(
        project_id="p1",
        epic_id="E-1",
        task_id="A",
        task_branch="task-a",
        head_sha="a" * 40,
    )
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
        error="old target failure",
    )
    queued = store.enqueue(
        project_id="p1",
        epic_id="E-1",
        task_id="A",
        task_branch=original.task_branch,
        head_sha=original.head_sha,
        explicit_retry=True,
    )
    assert queued.retry_forced is True

    assert store.block_preflight(
        "p1",
        "A",
        reason="terminal parent target unavailable",
        expected_head_sha="a" * 40,
    )
    blocked = store.get("p1", "A")
    assert blocked is not None
    assert blocked.state == "blocked"
    assert blocked.retry_forced is True
    assert blocked.last_error == "terminal parent target unavailable"


def test_retry_forced_is_returned_once_and_consumed_by_claim(tmp_path):
    """A claim returns cache-bypass authority without leaving it pending."""
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

    # Claim must carry the force bit to its executor while atomically clearing
    # the durable pending flag.  Returning only the post-update row loses the
    # explicit retry; retaining the flag durably can loop after a crash.
    claimed_again = store.claim_next(
        project_id="p1",
        epic_id="E-1",
        lease_owner="worker-2",
        dependency_map={"A": []},
        satisfied=set(),
    )
    assert claimed_again is not None
    assert claimed_again.retry_forced is False
    assert claimed_again.claimed_retry_forced is True
    integrating = store.get("p1", "A")
    assert integrating is not None
    assert integrating.state == "integrating"
    assert integrating.retry_forced is False
    assert integrating.claimed_retry_forced is False

    # The row remains unforced after the attempt records its outcome.
    assert store.complete("p1", "A", lease_owner="worker-2")
    completed = store.get("p1", "A")
    assert completed is not None
    assert completed.retry_forced is False


def test_retry_forced_does_not_repeat_after_lease_recovery(tmp_path):
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
        error="cached transient failure",
        retryable=False,
    )
    retried = store.enqueue(
        project_id="p1",
        epic_id="E-1",
        task_id="A",
        task_branch=original.task_branch,
        head_sha=original.head_sha,
        explicit_retry=True,
    )
    assert retried.retry_forced is True

    retry_claim = store.claim_next(
        project_id="p1",
        epic_id="E-1",
        lease_owner="worker-2",
        dependency_map={"A": []},
        satisfied=set(),
        lease_seconds=1,
        now=100.0,
    )
    assert retry_claim is not None
    assert retry_claim.retry_forced is False
    assert retry_claim.claimed_retry_forced is True

    integrating = store.get("p1", "A")
    assert integrating is not None
    assert integrating.retry_forced is False

    # The first claim consumed the one-shot retry.  If that executor crashes,
    # lease recovery must not force the gate again indefinitely.
    assert store.recover_expired(now=102.0) == 1
    recovered = store.claim_next(
        project_id="p1",
        epic_id="E-1",
        lease_owner="worker-3",
        dependency_map={"A": []},
        satisfied=set(),
        now=102.0,
    )
    assert recovered is not None
    assert recovered.retry_forced is False
    assert recovered.claimed_retry_forced is False
    assert store.fail(
        "p1",
        "A",
        lease_owner="worker-3",
        error="fresh gate failed",
        retryable=False,
    )
    failed = store.get("p1", "A")
    assert failed is not None
    assert failed.retry_forced is False


def test_claim_returns_exact_generation_when_another_connection_cancels(tmp_path):
    """The claim snapshot is read inside the same SQLite write fence."""

    path = tmp_path / "queue.sqlite3"
    store = IntegrationQueueStore(str(path))
    observer = IntegrationQueueStore(str(path))
    original = _enqueue(store, "A")
    first = store.claim_next(
        project_id="p1",
        epic_id="E-1",
        lease_owner="worker-1",
        dependency_map={"A": []},
        satisfied=set(),
    )
    assert first is not None
    assert store.fail(
        "p1",
        "A",
        lease_owner="worker-1",
        error="cached failure",
        retryable=False,
    )
    store.enqueue(
        project_id="p1",
        epic_id="E-1",
        task_id="A",
        task_branch=original.task_branch,
        head_sha=original.head_sha,
        explicit_retry=True,
    )

    real_connection = store._conn

    class CancelAfterCommit:
        def __init__(self):
            self.cancelled = False

        def execute(self, *args, **kwargs):
            return real_connection.execute(*args, **kwargs)

        def commit(self):
            real_connection.commit()
            if not self.cancelled:
                self.cancelled = True
                assert observer.cancel(
                    "p1",
                    "A",
                    reason="newer controller decision",
                    expected_head_sha=original.head_sha,
                    expected_state="integrating",
                )

        def rollback(self):
            return real_connection.rollback()

    store._conn = CancelAfterCommit()
    claimed = store.claim_next(
        project_id="p1",
        epic_id="E-1",
        lease_owner="worker-2",
        dependency_map={"A": []},
        satisfied=set(),
    )

    assert claimed is not None
    assert claimed.state == "integrating"
    assert claimed.lease_owner == "worker-2"
    assert claimed.head_sha == original.head_sha
    assert claimed.retry_forced is False
    assert claimed.claimed_retry_forced is True
    assert observer.get("p1", "A").state == "cancelled"


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


def test_durable_workflow_consumes_forced_retry_once_across_restart(tmp_path):
    path = tmp_path / "queue.sqlite3"
    store = IntegrationQueueStore(str(path))
    original = _enqueue(store, "A")
    claimed = store.claim_next(
        project_id="p1",
        epic_id="E-1",
        lease_owner="worker-1",
        dependency_map={"A": ()},
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
    retried = store.enqueue(
        project_id="p1",
        epic_id="E-1",
        task_id="A",
        task_branch=original.task_branch,
        head_sha=original.head_sha,
        explicit_retry=True,
    )

    consumed, forced = store.consume_retry_generation(
        "p1",
        "A",
        expected_generation=retried.authority_generation(),
    )

    assert consumed is not None
    assert forced is True
    assert consumed.retry_forced is False
    store.close()
    restarted = IntegrationQueueStore(str(path))
    durable = restarted.get("p1", "A")
    assert durable is not None
    second, forced_again = restarted.consume_retry_generation(
        "p1",
        "A",
        expected_generation=durable.authority_generation(),
    )
    assert second == durable
    assert forced_again is False


def test_authority_generation_survives_restart_and_changes_with_row(tmp_path):
    path = tmp_path / "queue.sqlite3"
    store = IntegrationQueueStore(str(path))
    queued = _enqueue(store, "A")
    generation = queued.authority_generation()
    store.close()

    restarted = IntegrationQueueStore(str(path))
    assert restarted.get("p1", "A").authority_generation() == generation
    claimed = restarted.claim_next(
        project_id="p1",
        epic_id="E-1",
        lease_owner="gate",
        dependency_map={"A": []},
        satisfied=set(),
    )
    assert claimed is not None
    assert claimed.authority_generation() != generation


def test_run_if_generation_rejects_row_changed_before_action(tmp_path):
    store = IntegrationQueueStore(str(tmp_path / "queue.sqlite3"))
    queued = _enqueue(store, "A")
    generation = queued.authority_generation()
    replacement = store.enqueue(
        project_id="p1",
        epic_id="E-1",
        task_id="A",
        task_branch=queued.task_branch,
        head_sha="replacement-head",
    )
    calls = []

    assert not store.run_if_generation(
        "p1",
        "A",
        expected_generation=generation,
        action=lambda row: calls.append(row) or True,
    )
    assert calls == []
    assert store.get("p1", "A") == replacement


def test_workflow_rebase_checkpoint_advances_exact_unleased_generation(tmp_path):
    store = IntegrationQueueStore(str(tmp_path / "queue.sqlite3"))
    queued = _enqueue(store, "A")
    blocked = store.finish_task_generation(
        "p1",
        "A",
        expected_generation=queued.authority_generation(),
        state="blocked",
        error="ci_failure:cached failure",
    )
    assert blocked is not None
    retried = store.enqueue(
        project_id="p1",
        epic_id="E-1",
        task_id="A",
        task_branch=queued.task_branch,
        head_sha=queued.head_sha,
        explicit_retry=True,
        preserve_attempts=True,
    )
    assert retried.retry_forced

    advanced = store.advance_task_generation(
        "p1",
        "A",
        expected_generation=retried.authority_generation(),
        head_sha="feedbeef",
        base_sha="base-new",
    )

    assert advanced is not None
    assert advanced.state == "ready"
    assert advanced.head_sha == "feedbeef"
    assert advanced.base_sha == "base-new"
    assert advanced.rebased_from_head_sha == queued.head_sha
    assert advanced.rebased_publication_pending is True
    assert advanced.retry_forced == retried.retry_forced
    assert advanced.attempts == retried.attempts
    assert store.finish_task_generation(
        "p1",
        "A",
        expected_generation=advanced.authority_generation(),
        state="blocked",
        error="ci_failure:not yet published",
    ) is None
    published = store.complete_task_publication(
        "p1",
        "A",
        expected_generation=advanced.authority_generation(),
        head_sha=advanced.head_sha,
    )
    assert published is not None
    assert published.rebased_publication_pending is False


def test_rebase_intent_is_durable_before_publication_and_survives_restart(tmp_path):
    path = tmp_path / "integration.sqlite3"
    store = IntegrationQueueStore(str(path))
    queued = store.enqueue(
        project_id="p1",
        epic_id="E-1",
        task_id="A",
        task_branch="task-A",
        head_sha="a" * 40,
    )

    intent = store.prepare_task_rebase(
        "p1",
        "A",
        expected_generation=queued.authority_generation(),
        base_sha="b" * 40,
    )

    assert intent is not None
    assert intent.head_sha == queued.head_sha
    assert intent.rebased_from_head_sha == queued.head_sha
    assert intent.rebase_intent_pending is True
    assert intent.rebased_publication_pending is False
    store.close()

    restarted = IntegrationQueueStore(str(path))
    recovered = restarted.get("p1", "A")
    assert recovered == intent
    prepared = restarted.prepare_task_publication(
        "p1",
        "A",
        expected_generation=recovered.authority_generation(),
        head_sha="c" * 40,
        base_sha="b" * 40,
    )
    assert prepared is not None
    assert prepared.rebase_intent_pending is False
    assert prepared.rebased_publication_pending is True
    assert prepared.rebased_from_head_sha == queued.head_sha


def test_exact_queue_identity_rehomes_same_head_to_current_parent(tmp_path):
    store = IntegrationQueueStore(str(tmp_path / "integration.sqlite3"))
    original = store.enqueue(
        project_id="p1",
        epic_id="E-OLD",
        task_id="A",
        task_branch="task-A",
        head_sha="a" * 40,
    )

    replacement = store.replace_task_identity(
        "p1",
        "A",
        expected_generation=original.authority_generation(),
        epic_id="E-NEW",
        task_branch=original.task_branch,
        head_sha=original.head_sha,
    )

    assert replacement is not None
    assert replacement.epic_id == "E-NEW"
    assert replacement.authority_generation() != original.authority_generation()
    assert store.replace_task_identity(
        "p1",
        "A",
        expected_generation=original.authority_generation(),
        epic_id="E-THIRD",
        task_branch=original.task_branch,
        head_sha=original.head_sha,
    ) is None


def test_exact_queue_generation_retires_durably_for_standalone_reclassification(
    tmp_path,
):
    path = tmp_path / "integration.sqlite3"
    store = IntegrationQueueStore(str(path))
    original = store.enqueue(
        project_id="p1",
        epic_id="E-OLD",
        task_id="A",
        task_branch="task-A",
        head_sha="a" * 40,
    )
    callback_rows = []

    retired = store.retire_task_generation(
        "p1",
        "A",
        expected_generation=original.authority_generation(),
        reason=STANDALONE_RECLASSIFICATION_REASON,
        action=lambda row: callback_rows.append(row) or True,
    )

    assert callback_rows == [original]
    assert retired is not None
    assert retired.state == "cancelled"
    assert retired.last_error == STANDALONE_RECLASSIFICATION_REASON
    assert store.retire_task_generation(
        "p1",
        "A",
        expected_generation=original.authority_generation(),
        reason=STANDALONE_RECLASSIFICATION_REASON,
    ) is None
    store.close()

    restarted = IntegrationQueueStore(str(path))
    assert restarted.get("p1", "A") == retired


def test_workflow_rebase_checkpoint_fences_replacement_and_live_lease(tmp_path):
    store = IntegrationQueueStore(str(tmp_path / "queue.sqlite3"))
    queued = _enqueue(store, "A")
    replacement = store.enqueue(
        project_id="p1",
        epic_id="E-1",
        task_id="A",
        task_branch=queued.task_branch,
        head_sha="new-user-head",
    )

    assert store.advance_task_generation(
        "p1",
        "A",
        expected_generation=queued.authority_generation(),
        head_sha="late-workflow-head",
    ) is None
    claimed = store.claim_next(
        project_id="p1",
        epic_id="E-1",
        lease_owner="legacy-owner",
        dependency_map={"A": ()},
        satisfied=set(),
    )
    assert claimed is not None
    assert store.advance_task_generation(
        "p1",
        "A",
        expected_generation=claimed.authority_generation(),
        head_sha="late-workflow-head",
    ) is None
    assert store.get("p1", "A").head_sha == replacement.head_sha


def test_run_if_generation_executes_inside_exact_row_fence(tmp_path):
    store = IntegrationQueueStore(str(tmp_path / "queue.sqlite3"))
    queued = _enqueue(store, "A")
    observed = []

    assert store.run_if_generation(
        "p1",
        "A",
        expected_generation=queued.authority_generation(),
        action=lambda row: observed.append(row.to_dict()) or True,
    )
    assert observed == [queued.to_dict()]
    assert store.get("p1", "A") == queued


def test_run_if_absent_rejects_existing_row_before_action(tmp_path):
    store = IntegrationQueueStore(str(tmp_path / "queue.sqlite3"))
    queued = _enqueue(store, "A")
    calls = []

    assert not store.run_if_absent(
        "p1",
        "A",
        action=lambda: calls.append("reopen") or True,
    )
    assert calls == []
    assert store.get("p1", "A") == queued


def test_run_if_absent_executes_inside_absence_fence(tmp_path):
    store = IntegrationQueueStore(str(tmp_path / "queue.sqlite3"))
    calls = []

    assert store.run_if_absent(
        "p1",
        "legacy-task",
        action=lambda: calls.append("reopen") or True,
    )
    assert calls == ["reopen"]
    assert store.get("p1", "legacy-task") is None
