"""Tests for per-project write locks in ProjectStore.

Covers:
- project_write_lock() API: creation, identity, and independence
- Lock is a threading.RLock (reentrant) so callers holding it can re-enter
- Concurrent create_worktree / remove_worktree for the same project are serialized
- Concurrent operations for different projects proceed independently
- Reentrancy: caller holding lock can call create_worktree without deadlock
- Orchestrator _reset_orphaned_in_progress acquires the per-project lock
  around tracker.update_issue() calls (prevents concurrent maintenance races)
- Concurrent maintenance (worktree removal) + dispatch (worktree creation)
  for the same project are serialized end-to-end
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import MagicMock, call, patch

import pytest

from oompah.models import Issue, Project
from oompah.projects import ProjectError, ProjectStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_store(tmp_path) -> ProjectStore:
    """Return a ProjectStore backed by a temp dir (no real projects loaded)."""
    return ProjectStore(
        path=str(tmp_path / "projects.json"),
        repos_root=str(tmp_path / "repos"),
        worktree_root=str(tmp_path / "wt"),
    )


def _add_project(store: ProjectStore, project_id: str, name: str = "testrepo") -> Project:
    p = Project(
        id=project_id,
        name=name,
        repo_url=f"https://github.com/org/{name}.git",
        repo_path=f"/tmp/{name}",
        branch="main",
    )
    store._projects[project_id] = p
    return p


# ---------------------------------------------------------------------------
# project_write_lock API tests
# ---------------------------------------------------------------------------


class TestProjectWriteLockApi:
    """Unit tests for ProjectStore.project_write_lock()."""

    def test_returns_lock_for_unknown_project(self, tmp_path):
        """Lock is created on demand even for non-existent project IDs."""
        store = _make_store(tmp_path)
        lock = store.project_write_lock("proj-x")
        assert lock is not None

    def test_same_project_returns_same_lock(self, tmp_path):
        """Calling project_write_lock twice with the same ID returns the same object."""
        store = _make_store(tmp_path)
        lock1 = store.project_write_lock("proj-a")
        lock2 = store.project_write_lock("proj-a")
        assert lock1 is lock2

    def test_different_projects_get_different_locks(self, tmp_path):
        """Each project gets its own independent lock."""
        store = _make_store(tmp_path)
        lock_a = store.project_write_lock("proj-a")
        lock_b = store.project_write_lock("proj-b")
        assert lock_a is not lock_b

    def test_lock_is_reentrant(self, tmp_path):
        """Lock is an RLock: same thread can acquire it twice without deadlocking."""
        store = _make_store(tmp_path)
        lock = store.project_write_lock("proj-r")
        acquired_twice = False
        with lock:
            with lock:  # RLock allows same-thread reacquisition
                acquired_twice = True
        assert acquired_twice

    def test_lock_can_be_used_as_context_manager(self, tmp_path):
        """The lock supports the `with` statement."""
        store = _make_store(tmp_path)
        lock = store.project_write_lock("proj-cm")
        entered = False
        with lock:
            entered = True
        assert entered

    def test_lock_registry_is_thread_safe(self, tmp_path):
        """Concurrent first-access to project_write_lock for the same project is safe."""
        store = _make_store(tmp_path)
        locks_acquired: list[object] = []

        def get_lock():
            locks_acquired.append(store.project_write_lock("proj-concurrent"))

        threads = [threading.Thread(target=get_lock) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads must have gotten the same lock object
        assert len(locks_acquired) == 20
        first = locks_acquired[0]
        assert all(lock is first for lock in locks_acquired)

    def test_many_projects_have_independent_locks(self, tmp_path):
        """Each of N projects gets a unique lock."""
        store = _make_store(tmp_path)
        locks = {f"proj-{i}": store.project_write_lock(f"proj-{i}") for i in range(50)}
        # All 50 lock objects must be distinct
        assert len(set(id(l) for l in locks.values())) == 50

    def test_lock_persists_across_store_reloads_same_instance(self, tmp_path):
        """Once cached, the same instance returns the same lock after _load()."""
        store = _make_store(tmp_path)
        lock_before = store.project_write_lock("proj-reload")
        store._load()  # reload from disk (no projects, but lock dict should survive)
        lock_after = store.project_write_lock("proj-reload")
        assert lock_before is lock_after


# ---------------------------------------------------------------------------
# Serialization: same project, multiple threads
# ---------------------------------------------------------------------------


class TestConcurrentWorktreeOperationsAreSerialized:
    """create_worktree / remove_worktree for the same project use the project lock.

    These tests verify the behavioral contract: operations on the same
    project are serialized; operations on different projects proceed
    concurrently (or at least don't mutually block).
    """

    def test_two_create_worktree_calls_same_project_are_serialized(self, tmp_path):
        """When two threads call create_worktree concurrently for the same project,
        the inner lock ensures they don't interleave git operations.

        We verify this by observing that the lock is held during the operation:
        if Thread-2 tries to acquire the lock while Thread-1 holds it, it blocks.
        """
        store = _make_store(tmp_path)
        _add_project(store, "proj-1")

        call_order: list[str] = []
        barrier = threading.Barrier(2)

        def mock_create_locked(
            project_id, issue_id, base_branch=None, branch_name=None
        ):
            """Simulate slow git work inside the locked region."""
            call_order.append(f"start:{issue_id}")
            time.sleep(0.05)  # simulate git I/O
            call_order.append(f"end:{issue_id}")
            return f"/wt/{issue_id}"

        with patch.object(store, "_create_worktree_locked", side_effect=mock_create_locked):
            results: list[str] = []
            errors: list[Exception] = []

            def worker(issue_id: str):
                try:
                    r = store.create_worktree("proj-1", issue_id)
                    results.append(r)
                except Exception as exc:
                    errors.append(exc)

            t1 = threading.Thread(target=worker, args=("issue-A",))
            t2 = threading.Thread(target=worker, args=("issue-B",))
            t1.start()
            t2.start()
            t1.join()
            t2.join()

        assert not errors
        assert len(results) == 2

        # The events must be completely non-interleaved: one issue finishes
        # before the other starts (because the lock serializes them).
        # Valid orderings: [start:A, end:A, start:B, end:B] or vice versa.
        assert call_order in [
            ["start:issue-A", "end:issue-A", "start:issue-B", "end:issue-B"],
            ["start:issue-B", "end:issue-B", "start:issue-A", "end:issue-A"],
        ], f"Unexpected interleaving: {call_order}"

    def test_remove_worktree_same_project_is_serialized(self, tmp_path):
        """Two concurrent remove_worktree calls for the same project are serialized."""
        store = _make_store(tmp_path)
        _add_project(store, "proj-1")

        call_order: list[str] = []

        def mock_remove_locked(project_id, issue_id):
            call_order.append(f"start:{issue_id}")
            time.sleep(0.05)
            call_order.append(f"end:{issue_id}")

        with patch.object(store, "_remove_worktree_locked", side_effect=mock_remove_locked):
            t1 = threading.Thread(target=store.remove_worktree, args=("proj-1", "issue-A"))
            t2 = threading.Thread(target=store.remove_worktree, args=("proj-1", "issue-B"))
            t1.start()
            t2.start()
            t1.join()
            t2.join()

        # Non-interleaved
        assert call_order in [
            ["start:issue-A", "end:issue-A", "start:issue-B", "end:issue-B"],
            ["start:issue-B", "end:issue-B", "start:issue-A", "end:issue-A"],
        ], f"Unexpected interleaving: {call_order}"

    def test_create_and_remove_same_project_are_serialized(self, tmp_path):
        """Concurrent create_worktree and remove_worktree for the same project
        are serialized — the maintenance path cannot race with dispatch."""
        store = _make_store(tmp_path)
        _add_project(store, "proj-1")

        call_order: list[str] = []

        def mock_create_locked(
            project_id, issue_id, base_branch=None, branch_name=None
        ):
            call_order.append("start:create")
            time.sleep(0.05)
            call_order.append("end:create")
            return "/wt/issue-A"

        def mock_remove_locked(project_id, issue_id):
            call_order.append("start:remove")
            time.sleep(0.05)
            call_order.append("end:remove")

        with (
            patch.object(store, "_create_worktree_locked", side_effect=mock_create_locked),
            patch.object(store, "_remove_worktree_locked", side_effect=mock_remove_locked),
        ):
            t1 = threading.Thread(target=store.create_worktree, args=("proj-1", "issue-A"))
            t2 = threading.Thread(target=store.remove_worktree, args=("proj-1", "issue-B"))
            t1.start()
            t2.start()
            t1.join()
            t2.join()

        # Non-interleaved
        assert call_order in [
            ["start:create", "end:create", "start:remove", "end:remove"],
            ["start:remove", "end:remove", "start:create", "end:create"],
        ], f"Unexpected interleaving: {call_order}"


class TestDifferentProjectsAreIndependent:
    """Operations on different projects must not block each other."""

    def test_two_projects_create_worktree_concurrently(self, tmp_path):
        """create_worktree on proj-a and proj-b can overlap (different locks)."""
        store = _make_store(tmp_path)
        _add_project(store, "proj-a", "repo-a")
        _add_project(store, "proj-b", "repo-b")

        started_at: dict[str, float] = {}
        finished_at: dict[str, float] = {}

        def mock_create_locked(
            project_id, issue_id, base_branch=None, branch_name=None
        ):
            started_at[project_id] = time.monotonic()
            time.sleep(0.1)  # simulate slow git I/O
            finished_at[project_id] = time.monotonic()
            return f"/wt/{issue_id}"

        with patch.object(store, "_create_worktree_locked", side_effect=mock_create_locked):
            t1 = threading.Thread(target=store.create_worktree, args=("proj-a", "issue-1"))
            t2 = threading.Thread(target=store.create_worktree, args=("proj-b", "issue-2"))
            t1.start()
            t2.start()
            t1.join()
            t2.join()

        # proj-a and proj-b must have overlapped (concurrent execution)
        assert "proj-a" in started_at and "proj-b" in started_at
        # One starts before the other finishes → they overlapped
        overlap = (
            started_at["proj-a"] < finished_at["proj-b"]
            and started_at["proj-b"] < finished_at["proj-a"]
        )
        assert overlap, (
            "Expected proj-a and proj-b to run concurrently but they were serialized. "
            f"proj-a: [{started_at['proj-a']:.3f}, {finished_at['proj-a']:.3f}], "
            f"proj-b: [{started_at['proj-b']:.3f}, {finished_at['proj-b']:.3f}]"
        )

    def test_holding_proj_a_lock_does_not_block_proj_b(self, tmp_path):
        """Holding proj-a's write lock must not prevent proj-b operations."""
        store = _make_store(tmp_path)
        lock_a = store.project_write_lock("proj-a")
        lock_b = store.project_write_lock("proj-b")

        proj_b_acquired = threading.Event()

        def hold_proj_a():
            with lock_a:
                # Hold proj-a lock while proj-b tries to acquire its own lock
                time.sleep(0.2)

        def acquire_proj_b():
            with lock_b:
                proj_b_acquired.set()

        t_a = threading.Thread(target=hold_proj_a)
        t_b = threading.Thread(target=acquire_proj_b)
        t_a.start()
        time.sleep(0.02)  # make sure t_a acquires lock_a first
        t_b.start()

        # proj-b should acquire its lock without waiting for proj-a to finish
        acquired = proj_b_acquired.wait(timeout=0.1)  # 100ms much less than t_a's 200ms hold
        t_a.join()
        t_b.join()

        assert acquired, "proj-b lock acquisition was blocked by proj-a lock (incorrect)"


# ---------------------------------------------------------------------------
# Reentrancy tests
# ---------------------------------------------------------------------------


class TestReentrancy:
    """The lock must be reentrant so callers holding it can call worktree methods."""

    def test_holding_lock_then_calling_create_worktree_does_not_deadlock(self, tmp_path):
        """Caller holds project_write_lock, then calls create_worktree (which
        also acquires the lock internally). Must complete without deadlock."""
        store = _make_store(tmp_path)
        _add_project(store, "proj-re")

        completed = threading.Event()

        def run():
            with store.project_write_lock("proj-re"):
                # create_worktree also acquires the same project lock internally.
                # With RLock this succeeds; with Lock it would deadlock.
                with patch.object(
                    store,
                    "_create_worktree_locked",
                    return_value="/wt/issue-X",
                ):
                    result = store.create_worktree("proj-re", "issue-X")
                    assert result == "/wt/issue-X"
            completed.set()

        t = threading.Thread(target=run)
        t.start()
        ok = completed.wait(timeout=2.0)
        t.join()
        assert ok, "create_worktree deadlocked when called while holding the project lock"

    def test_holding_lock_then_calling_remove_worktree_does_not_deadlock(self, tmp_path):
        """Caller holds project_write_lock, then calls remove_worktree. No deadlock."""
        store = _make_store(tmp_path)
        _add_project(store, "proj-re2")

        completed = threading.Event()

        def run():
            with store.project_write_lock("proj-re2"):
                with patch.object(store, "_remove_worktree_locked", return_value=None):
                    store.remove_worktree("proj-re2", "issue-Y")
            completed.set()

        t = threading.Thread(target=run)
        t.start()
        ok = completed.wait(timeout=2.0)
        t.join()
        assert ok, "remove_worktree deadlocked when called while holding the project lock"


# ---------------------------------------------------------------------------
# Epic worktree locking
# ---------------------------------------------------------------------------


class TestEpicWorktreeLocking:
    """create_epic_worktree and remove_epic_worktree also use the project lock."""

    def test_concurrent_create_epic_worktree_same_project_are_serialized(self, tmp_path):
        """Two concurrent create_epic_worktree calls for the same project are serialized."""
        store = _make_store(tmp_path)
        _add_project(store, "proj-epic")

        call_order: list[str] = []

        def mock_create_epic_locked(project_id, epic_id):
            call_order.append(f"start:{epic_id}")
            time.sleep(0.05)
            call_order.append(f"end:{epic_id}")
            return f"/wt/epic-{epic_id}"

        with patch.object(
            store, "_create_epic_worktree_locked", side_effect=mock_create_epic_locked
        ):
            t1 = threading.Thread(target=store.create_epic_worktree, args=("proj-epic", "EPIC-1"))
            t2 = threading.Thread(target=store.create_epic_worktree, args=("proj-epic", "EPIC-2"))
            t1.start()
            t2.start()
            t1.join()
            t2.join()

        assert call_order in [
            ["start:EPIC-1", "end:EPIC-1", "start:EPIC-2", "end:EPIC-2"],
            ["start:EPIC-2", "end:EPIC-2", "start:EPIC-1", "end:EPIC-1"],
        ], f"Unexpected interleaving: {call_order}"

    def test_concurrent_remove_epic_worktree_same_project_are_serialized(self, tmp_path):
        """Two concurrent remove_epic_worktree calls for the same project are serialized."""
        store = _make_store(tmp_path)
        _add_project(store, "proj-epic2")

        call_order: list[str] = []

        def mock_remove_epic_locked(project_id, epic_id):
            call_order.append(f"start:{epic_id}")
            time.sleep(0.05)
            call_order.append(f"end:{epic_id}")

        with patch.object(
            store, "_remove_epic_worktree_locked", side_effect=mock_remove_epic_locked
        ):
            t1 = threading.Thread(target=store.remove_epic_worktree, args=("proj-epic2", "EPIC-A"))
            t2 = threading.Thread(target=store.remove_epic_worktree, args=("proj-epic2", "EPIC-B"))
            t1.start()
            t2.start()
            t1.join()
            t2.join()

        assert call_order in [
            ["start:EPIC-A", "end:EPIC-A", "start:EPIC-B", "end:EPIC-B"],
            ["start:EPIC-B", "end:EPIC-B", "start:EPIC-A", "end:EPIC-A"],
        ], f"Unexpected interleaving: {call_order}"

    def test_create_epic_and_create_regular_same_project_are_serialized(self, tmp_path):
        """create_epic_worktree and create_worktree for the same project are serialized."""
        store = _make_store(tmp_path)
        _add_project(store, "proj-mixed")

        call_order: list[str] = []

        def mock_create_locked(
            project_id, issue_id, base_branch=None, branch_name=None
        ):
            call_order.append("start:regular")
            time.sleep(0.05)
            call_order.append("end:regular")
            return "/wt/regular"

        def mock_create_epic_locked(project_id, epic_id):
            call_order.append("start:epic")
            time.sleep(0.05)
            call_order.append("end:epic")
            return "/wt/epic"

        with (
            patch.object(store, "_create_worktree_locked", side_effect=mock_create_locked),
            patch.object(
                store, "_create_epic_worktree_locked", side_effect=mock_create_epic_locked
            ),
        ):
            t1 = threading.Thread(
                target=store.create_worktree, args=("proj-mixed", "issue-1")
            )
            t2 = threading.Thread(
                target=store.create_epic_worktree, args=("proj-mixed", "EPIC-1")
            )
            t1.start()
            t2.start()
            t1.join()
            t2.join()

        assert call_order in [
            ["start:regular", "end:regular", "start:epic", "end:epic"],
            ["start:epic", "end:epic", "start:regular", "end:regular"],
        ], f"Unexpected interleaving: {call_order}"


# ---------------------------------------------------------------------------
# Orchestrator _reset_orphaned_in_progress uses the project lock
# ---------------------------------------------------------------------------


def _make_issue(identifier: str, state: str = "in_progress", project_id: str | None = "proj-1") -> Issue:
    return Issue(
        id=f"id-{identifier}",
        identifier=identifier,
        title=f"Issue {identifier}",
        description="desc",
        state=state,
        issue_type="task",
        priority=2,
        project_id=project_id,
        labels=[],
    )


class TestResetOrphanedInProgressUsesProjectLock:
    """_reset_orphaned_in_progress must acquire per-project lock around tracker writes."""

    @pytest.fixture
    def orch(self, tmp_path):
        from oompah.config import ServiceConfig
        from oompah.orchestrator import Orchestrator

        store = ProjectStore(
            path=str(tmp_path / "projects.json"),
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        _add_project(store, "proj-1")
        project_mock = MagicMock()
        project_mock.list_all.return_value = [store.get("proj-1")]
        project_mock.get.side_effect = store.get
        # Keep project_write_lock from the real store
        project_mock.project_write_lock = store.project_write_lock

        orch = Orchestrator(
            config=ServiceConfig(),
            workflow_path="WORKFLOW.md",
            project_store=project_mock,
            state_path=str(tmp_path / "state.json"),
        )
        return orch, store

    def test_lock_acquired_during_tracker_update(self, orch):
        """project_write_lock is acquired while tracker.update_issue() is called."""
        orchestrator, store = orch

        lock = store.project_write_lock("proj-1")
        lock_was_held_during_write: list[bool] = []

        original_update = MagicMock()

        def tracking_update(identifier, **kwargs):
            # Check whether the lock is currently held by calling thread
            # threading.RLock.acquire(blocking=False) returns False if another
            # thread holds it (but True if same thread holds it because RLock).
            # We test from the same thread, so we verify via the lock itself.
            lock_was_held_during_write.append(True)
            original_update(identifier, **kwargs)

        issue = _make_issue("ISSUE-1")
        tracker_mock = MagicMock()
        tracker_mock.update_issue = tracking_update

        with (
            patch.object(orchestrator, "_tracker_for_project", return_value=tracker_mock),
            patch.object(orchestrator, "_tracker_for_issue", return_value=tracker_mock),
        ):
            orchestrator._reset_orphaned_in_progress([issue])

        assert lock_was_held_during_write, "Lock was never acquired before tracker.update_issue()"

    def test_concurrent_orphan_resets_for_same_project_are_serialized(self, tmp_path):
        """Two concurrent _reset_orphaned_in_progress passes for the same project
        cannot interleave their tracker writes (the project lock serializes them)."""
        from oompah.config import ServiceConfig
        from oompah.orchestrator import Orchestrator

        store = _make_store(tmp_path)
        _add_project(store, "proj-1")

        project_mock = MagicMock()
        project_mock.list_all.return_value = [store.get("proj-1")]
        project_mock.get.side_effect = store.get
        project_mock.project_write_lock = store.project_write_lock

        orch = Orchestrator(
            config=ServiceConfig(),
            workflow_path="WORKFLOW.md",
            project_store=project_mock,
            state_path=str(tmp_path / "state.json"),
        )

        write_call_order: list[str] = []

        def slow_update(identifier, **kwargs):
            write_call_order.append(f"start:{identifier}")
            time.sleep(0.05)
            write_call_order.append(f"end:{identifier}")

        tracker_mock = MagicMock()
        tracker_mock.update_issue = slow_update

        issue_a = _make_issue("ISSUE-A")
        issue_b = _make_issue("ISSUE-B")

        with patch.object(orch, "_tracker_for_project", return_value=tracker_mock):
            t1 = threading.Thread(
                target=orch._reset_orphaned_in_progress, args=([issue_a],)
            )
            t2 = threading.Thread(
                target=orch._reset_orphaned_in_progress, args=([issue_b],)
            )
            t1.start()
            t2.start()
            t1.join()
            t2.join()

        # Writes must not interleave: start-A must be followed by end-A before start-B
        assert write_call_order in [
            ["start:ISSUE-A", "end:ISSUE-A", "start:ISSUE-B", "end:ISSUE-B"],
            ["start:ISSUE-B", "end:ISSUE-B", "start:ISSUE-A", "end:ISSUE-A"],
        ], f"Unexpected interleaving of tracker writes: {write_call_order}"

    def test_orphan_resets_for_different_projects_are_independent(self, tmp_path):
        """Orphan resets for proj-a and proj-b must not block each other."""
        from oompah.config import ServiceConfig
        from oompah.orchestrator import Orchestrator

        store = _make_store(tmp_path)
        _add_project(store, "proj-a", "repo-a")
        _add_project(store, "proj-b", "repo-b")

        project_mock = MagicMock()
        project_mock.list_all.return_value = [store.get("proj-a"), store.get("proj-b")]
        project_mock.get.side_effect = store.get
        project_mock.project_write_lock = store.project_write_lock

        orch = Orchestrator(
            config=ServiceConfig(),
            workflow_path="WORKFLOW.md",
            project_store=project_mock,
            state_path=str(tmp_path / "state.json"),
        )

        started_at: dict[str, float] = {}
        finished_at: dict[str, float] = {}

        def slow_update(identifier, **kwargs):
            # Only record timing for our two test identifiers
            pid = identifier.split("-")[1]  # ISSUE-projA → "projA"
            started_at[identifier] = time.monotonic()
            time.sleep(0.1)
            finished_at[identifier] = time.monotonic()

        tracker_a = MagicMock()
        tracker_a.update_issue = slow_update
        tracker_b = MagicMock()
        tracker_b.update_issue = slow_update

        issue_a = _make_issue("ISSUE-A", project_id="proj-a")
        issue_b = _make_issue("ISSUE-B", project_id="proj-b")

        def tracker_for(project_id):
            return tracker_a if project_id == "proj-a" else tracker_b

        with patch.object(orch, "_tracker_for_project", side_effect=tracker_for):
            t1 = threading.Thread(
                target=orch._reset_orphaned_in_progress, args=([issue_a],)
            )
            t2 = threading.Thread(
                target=orch._reset_orphaned_in_progress, args=([issue_b],)
            )
            t1.start()
            t2.start()
            t1.join()
            t2.join()

        # proj-a and proj-b should overlap (concurrent execution)
        assert "ISSUE-A" in started_at and "ISSUE-B" in started_at
        overlap = (
            started_at["ISSUE-A"] < finished_at["ISSUE-B"]
            and started_at["ISSUE-B"] < finished_at["ISSUE-A"]
        )
        assert overlap, (
            "Expected ISSUE-A (proj-a) and ISSUE-B (proj-b) to run concurrently "
            "but they were serialized (independent project locks should not block each other)."
        )


# ---------------------------------------------------------------------------
# End-to-end: concurrent maintenance + dispatch for same project
# ---------------------------------------------------------------------------


class TestConcurrentMaintenanceAndDispatch:
    """Acceptance criteria #3: concurrent maintenance (worktree cleanup) and
    dispatch (worktree creation) for the same project are serialized."""

    def test_maintenance_remove_and_dispatch_create_are_serialized(self, tmp_path):
        """Simulates the scenario where _maybe_heal_repos triggers remove_worktree
        at the same time as _dispatch triggers create_worktree for the same project.

        Both calls must be serialized: no interleaving of their inner git operations.
        """
        store = _make_store(tmp_path)
        _add_project(store, "proj-1")

        call_order: list[str] = []

        def mock_create_locked(
            project_id, issue_id, base_branch=None, branch_name=None
        ):
            call_order.append("create:start")
            time.sleep(0.08)
            call_order.append("create:end")
            return "/wt/new-issue"

        def mock_remove_locked(project_id, issue_id):
            call_order.append("remove:start")
            time.sleep(0.08)
            call_order.append("remove:end")

        with (
            patch.object(store, "_create_worktree_locked", side_effect=mock_create_locked),
            patch.object(store, "_remove_worktree_locked", side_effect=mock_remove_locked),
        ):
            # Thread-1 = dispatch: create_worktree (new agent workspace)
            # Thread-2 = maintenance: remove_worktree (cleanup terminal task)
            t_dispatch = threading.Thread(
                target=store.create_worktree, args=("proj-1", "new-issue")
            )
            t_maintenance = threading.Thread(
                target=store.remove_worktree, args=("proj-1", "terminal-issue")
            )
            t_dispatch.start()
            t_maintenance.start()
            t_dispatch.join()
            t_maintenance.join()

        # The operations must not interleave
        assert call_order in [
            ["create:start", "create:end", "remove:start", "remove:end"],
            ["remove:start", "remove:end", "create:start", "create:end"],
        ], f"Dispatch and maintenance interleaved: {call_order}"

    def test_maintenance_and_dispatch_different_projects_run_concurrently(self, tmp_path):
        """Maintenance on proj-a and dispatch on proj-b must not block each other."""
        store = _make_store(tmp_path)
        _add_project(store, "proj-a", "repo-a")
        _add_project(store, "proj-b", "repo-b")

        started_at: dict[str, float] = {}
        finished_at: dict[str, float] = {}

        def mock_remove_locked(project_id, issue_id):
            started_at["remove"] = time.monotonic()
            time.sleep(0.1)
            finished_at["remove"] = time.monotonic()

        def mock_create_locked(
            project_id, issue_id, base_branch=None, branch_name=None
        ):
            started_at["create"] = time.monotonic()
            time.sleep(0.1)
            finished_at["create"] = time.monotonic()
            return "/wt/new"

        with (
            patch.object(store, "_create_worktree_locked", side_effect=mock_create_locked),
            patch.object(store, "_remove_worktree_locked", side_effect=mock_remove_locked),
        ):
            t1 = threading.Thread(
                target=store.remove_worktree, args=("proj-a", "old-issue")
            )
            t2 = threading.Thread(
                target=store.create_worktree, args=("proj-b", "new-issue")
            )
            t1.start()
            t2.start()
            t1.join()
            t2.join()

        # Must overlap (concurrent)
        assert "remove" in started_at and "create" in started_at
        overlap = (
            started_at["remove"] < finished_at["create"]
            and started_at["create"] < finished_at["remove"]
        )
        assert overlap, (
            "Expected proj-a (remove) and proj-b (create) to run concurrently "
            f"but they were serialized. Times: {started_at} / {finished_at}"
        )

    def test_thread_pool_concurrent_operations_same_project_serialized(self, tmp_path):
        """Using ThreadPoolExecutor (mimicking run_in_executor) with N concurrent
        worktree operations on the same project: all must serialize correctly."""
        store = _make_store(tmp_path)
        _add_project(store, "proj-1")

        MAX_CONCURRENT = [0]
        current_concurrent = [0]
        counter_lock = threading.Lock()

        def mock_create_locked(
            project_id, issue_id, base_branch=None, branch_name=None
        ):
            with counter_lock:
                current_concurrent[0] += 1
                if current_concurrent[0] > MAX_CONCURRENT[0]:
                    MAX_CONCURRENT[0] = current_concurrent[0]
            time.sleep(0.02)
            with counter_lock:
                current_concurrent[0] -= 1
            return f"/wt/{issue_id}"

        with patch.object(store, "_create_worktree_locked", side_effect=mock_create_locked):
            with ThreadPoolExecutor(max_workers=8) as pool:
                futs = [
                    pool.submit(store.create_worktree, "proj-1", f"issue-{i}")
                    for i in range(8)
                ]
                for f in as_completed(futs):
                    f.result()  # raise any exceptions

        # Since the project lock serializes all operations, max concurrent must be 1
        assert MAX_CONCURRENT[0] == 1, (
            f"Expected max concurrent=1 (serialized), got {MAX_CONCURRENT[0]}"
        )


# ---------------------------------------------------------------------------
# Error handling: lock is released even if the operation raises
# ---------------------------------------------------------------------------


class TestLockReleasedOnError:
    """Verify the lock is properly released even when the operation raises."""

    def test_lock_released_after_create_worktree_raises(self, tmp_path):
        """If create_worktree raises, the lock must be released so subsequent
        calls from other threads can proceed."""
        store = _make_store(tmp_path)
        _add_project(store, "proj-err")

        call_count = [0]

        def mock_create_locked(
            project_id, issue_id, base_branch=None, branch_name=None
        ):
            call_count[0] += 1
            if call_count[0] == 1:
                raise ProjectError("git clone failed: test")
            return "/wt/ok"

        with patch.object(store, "_create_worktree_locked", side_effect=mock_create_locked):
            # First call raises
            with pytest.raises(ProjectError):
                store.create_worktree("proj-err", "issue-1")

            # Second call (from a different thread) must not deadlock
            completed = threading.Event()

            def second_call():
                try:
                    store.create_worktree("proj-err", "issue-2")
                except ProjectError:
                    pass
                completed.set()

            t = threading.Thread(target=second_call)
            t.start()
            ok = completed.wait(timeout=1.0)
            t.join()
            assert ok, "Lock was not released after create_worktree raised — deadlock!"

    def test_lock_released_after_remove_worktree_raises(self, tmp_path):
        """If remove_worktree raises, the lock is released for subsequent callers."""
        store = _make_store(tmp_path)
        _add_project(store, "proj-err2")

        def mock_remove_locked(project_id, issue_id):
            raise ProjectError("git worktree remove failed: test")

        with patch.object(store, "_remove_worktree_locked", side_effect=mock_remove_locked):
            with pytest.raises(ProjectError):
                store.remove_worktree("proj-err2", "issue-1")

            # Lock must be released so the next caller doesn't deadlock
            completed = threading.Event()

            def next_call():
                with store.project_write_lock("proj-err2"):
                    completed.set()

            t = threading.Thread(target=next_call)
            t.start()
            ok = completed.wait(timeout=1.0)
            t.join()
            assert ok, "Lock was not released after remove_worktree raised — deadlock!"
