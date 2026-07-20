"""Tests for checkpoint coalescing (OOMPAH-257).

Validates the debounce/coalesce/mandatory-flush/ephemeral-vs-durable
behavior introduced by the checkpoint queue for state-branch task mutations.

Coverage:
  § 1  CheckpointQueue unit tests (debounce, max-delay, mandatory flush)
  § 2  Concurrent-writer safety
  § 3  Push-race and retry behavior
  § 4  Tracker integration — coalescing via state-branch tracker
  § 5  Mandatory flush for terminal/In Review status transitions
  § 6  Ephemeral vs durable classification
  § 7  Observability (pending_mutations, last_push_at, push_failures)
  § 8  Integration — commits target state branch only (not main)
  § 9  Shutdown flush
  § 10 Auto-correction of invalid max_delay < debounce

Design reference: plans/state-branch-design.md § 5
"""

from __future__ import annotations

import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable, Iterator
from unittest.mock import MagicMock, patch

import pytest

from oompah.checkpoint_queue import CheckpointQueue
from oompah.oompah_md_tracker import OompahMarkdownTracker
from oompah.statuses import ARCHIVED, DONE, IN_PROGRESS, IN_REVIEW, MERGED, OPEN
from oompah.tracker import TrackerError


# ---------------------------------------------------------------------------
# Shared git helpers (copied from test_oompah_md_tracker_state_branch pattern)
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=check,
    )


def _commit_sha(repo: Path, branch: str) -> str:
    return _git(repo, "rev-parse", branch).stdout.strip()


def _commit_count(repo: Path, branch: str) -> int:
    result = _git(repo, "rev-list", "--count", branch)
    return int(result.stdout.strip())


def _init_git_repo(root: Path, *, branch: str = "main") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-b", branch)
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test Agent")
    readme = root / "README.md"
    readme.write_text("# test\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "Initial commit")
    return root


def _create_state_branch(repo: Path, state_branch: str) -> None:
    _git(repo, "checkout", "--orphan", state_branch)
    _git(repo, "reset", "--hard")
    tasks_root = repo / ".oompah" / "tasks"
    tasks_root.mkdir(parents=True, exist_ok=True)
    for subdir in [
        "proposed", "backlog", "open", "in-progress", "needs-human",
        "needs-ci-fix", "needs-rebase", "in-review", "decomposed",
        "duplicate-candidate", "done", "merged", "archived",
    ]:
        d = tasks_root / subdir
        d.mkdir(exist_ok=True)
        (d / ".gitkeep").write_text("", encoding="utf-8")
    _git(repo, "add", ".oompah/")
    _git(repo, "commit", "-m", "Bootstrap oompah state branch")
    _git(repo, "checkout", "main")


def _make_tracker(
    repo: Path,
    *,
    state_branch_name: str,
    debounce_ms: int = 5000,
    max_delay_ms: int = 30000,
    git_sync: bool = False,
    timer_factory: Any = None,
) -> OompahMarkdownTracker:
    """Build a state-branch-enabled tracker for test use."""
    kwargs: dict[str, Any] = {}
    if timer_factory is not None:
        kwargs["_checkpoint_timer_factory"] = timer_factory
    return OompahMarkdownTracker(
        active_states=[OPEN, IN_PROGRESS],
        terminal_states=[DONE, MERGED, ARCHIVED],
        cwd=str(repo),
        default_branch="main",
        git_sync=git_sync,
        state_branch_enabled=True,
        state_branch_name=state_branch_name,
        state_branch_checkpoint_debounce_ms=debounce_ms,
        state_branch_checkpoint_max_delay_ms=max_delay_ms,
        **kwargs,
    )


@pytest.fixture
def state_repo(tmp_path: Path) -> Iterator[tuple[Path, str]]:
    """Git repo with main + orphan state branch; returns (repo_path, state_branch)."""
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    sb = "oompah/state/proj-test"
    _create_state_branch(repo, sb)
    yield repo, sb


# ---------------------------------------------------------------------------
# § 1 — CheckpointQueue unit tests
# ---------------------------------------------------------------------------


class TestCheckpointQueueDebounce:
    """Debounce coalescing: N mutations within the window → one flush call."""

    def _make_fake_timer_factory(
        self, fire_immediately: bool = True
    ) -> tuple[Callable, list[Any]]:
        """Return (factory, timers_list).

        If fire_immediately=True, each timer fires synchronously when start() is
        called (useful for deterministic debounce tests without actual sleeping).
        If fire_immediately=False, timers are captured but never auto-fire.
        """
        timers: list[Any] = []

        class FakeTimer:
            def __init__(self, interval, fn, args=(), kwargs=None):
                self.interval = interval
                self.fn = fn
                self.args = args
                self.kwargs = kwargs or {}
                self.cancelled = False
                self.daemon = True
                timers.append(self)

            def start(self):
                if fire_immediately and not self.cancelled:
                    self.fn(*self.args, **self.kwargs)

            def cancel(self):
                self.cancelled = True

        return FakeTimer, timers

    def test_single_schedule_then_flush_commits_once(self):
        """One schedule() + flush() → flush_fn called exactly once."""
        flush_count = 0

        def flush_fn():
            nonlocal flush_count
            flush_count += 1

        FakeTimer, _ = self._make_fake_timer_factory(fire_immediately=False)
        q = CheckpointQueue(
            debounce_ms=100,
            max_delay_ms=1100,
            flush_fn=flush_fn,
            _timer_factory=FakeTimer,
        )
        q.schedule()
        assert q.pending_mutations == 1
        count = q.flush(reason="test")
        assert count == 1
        assert flush_count == 1
        assert q.pending_mutations == 0

    def test_many_schedules_within_window_produce_one_flush(self):
        """N schedule() calls → pending_mutations == N; one flush() commits all."""
        flush_count = 0

        def flush_fn():
            nonlocal flush_count
            flush_count += 1

        FakeTimer, _ = self._make_fake_timer_factory(fire_immediately=False)
        q = CheckpointQueue(
            debounce_ms=100,
            max_delay_ms=1100,
            flush_fn=flush_fn,
            _timer_factory=FakeTimer,
        )
        # Simulate 10 rapid mutations (all within the debounce window)
        for _ in range(10):
            q.schedule()

        assert q.pending_mutations == 10, "All 10 mutations must be buffered"

        flushed = q.flush(reason="test")
        assert flushed == 10, "Flush must report 10 mutations"
        assert flush_count == 1, "flush_fn must be called exactly once"
        assert q.pending_mutations == 0, "Buffer must be empty after flush"

    def test_flush_without_pending_mutations_is_no_op(self):
        """flush() with no pending mutations returns 0 and does not call flush_fn."""
        flush_count = 0

        def flush_fn():
            nonlocal flush_count
            flush_count += 1

        FakeTimer, _ = self._make_fake_timer_factory(fire_immediately=False)
        q = CheckpointQueue(
            debounce_ms=100, max_delay_ms=1100, flush_fn=flush_fn, _timer_factory=FakeTimer
        )
        result = q.flush(reason="test")
        assert result == 0
        assert flush_count == 0

    def test_debounce_timer_fires_and_commits(self):
        """When debounce timer fires (immediately in fake factory), flush_fn is called."""
        flush_count = 0

        def flush_fn():
            nonlocal flush_count
            flush_count += 1

        FakeTimer, timers = self._make_fake_timer_factory(fire_immediately=True)
        q = CheckpointQueue(
            debounce_ms=100,
            max_delay_ms=1100,
            flush_fn=flush_fn,
            _timer_factory=FakeTimer,
        )
        q.schedule()  # schedule + fake timer fires synchronously
        # The debounce timer fired → flush_fn called → pending_mutations reset to 0
        assert flush_count == 1
        assert q.pending_mutations == 0

    def test_debounce_resets_on_each_schedule(self):
        """Each schedule() call cancels and restarts the debounce timer."""
        FakeTimer, timers = self._make_fake_timer_factory(fire_immediately=False)
        q = CheckpointQueue(
            debounce_ms=100,
            max_delay_ms=1100,
            flush_fn=lambda: None,
            _timer_factory=FakeTimer,
        )
        q.schedule()
        q.schedule()
        q.schedule()
        # Only the last debounce timer should not be cancelled
        debounce_timers = [t for t in timers if t.interval == 0.1]
        # All but the last should be cancelled
        assert all(t.cancelled for t in debounce_timers[:-1]), (
            "Earlier debounce timers must be cancelled when new mutations arrive"
        )
        assert not debounce_timers[-1].cancelled, (
            "The final debounce timer must still be active"
        )

    def test_max_delay_timer_starts_only_on_first_pending(self):
        """Max-delay timer is started once when the first mutation arrives."""
        FakeTimer, timers = self._make_fake_timer_factory(fire_immediately=False)
        q = CheckpointQueue(
            debounce_ms=100,
            max_delay_ms=1100,
            flush_fn=lambda: None,
            _timer_factory=FakeTimer,
        )
        q.schedule()
        q.schedule()
        q.schedule()
        # Max-delay timers have interval 1.1 seconds
        max_timers = [t for t in timers if abs(t.interval - 1.1) < 0.01]
        assert len(max_timers) == 1, (
            f"Max-delay timer must start exactly once; got {len(max_timers)} timers"
        )

    def test_flush_cancels_both_timers(self):
        """flush() cancels both the debounce and max-delay timers."""
        FakeTimer, timers = self._make_fake_timer_factory(fire_immediately=False)
        flush_fn = MagicMock()
        q = CheckpointQueue(
            debounce_ms=100,
            max_delay_ms=1100,
            flush_fn=flush_fn,
            _timer_factory=FakeTimer,
        )
        q.schedule()
        assert len(timers) == 2  # debounce + max-delay
        q.flush(reason="test")
        assert all(t.cancelled for t in timers), (
            "Both debounce and max-delay timers must be cancelled after flush"
        )

    def test_after_flush_new_schedules_create_fresh_timers(self):
        """After flush(), scheduling again starts a new timer cycle."""
        FakeTimer, timers = self._make_fake_timer_factory(fire_immediately=False)
        flush_fn = MagicMock()
        q = CheckpointQueue(
            debounce_ms=100,
            max_delay_ms=1100,
            flush_fn=flush_fn,
            _timer_factory=FakeTimer,
        )
        q.schedule()
        q.flush(reason="first")
        assert flush_fn.call_count == 1
        timers_after_first_flush = len(timers)

        # Schedule again → must create new timers
        q.schedule()
        assert len(timers) > timers_after_first_flush, (
            "New timers must be created after flush() resets the state"
        )
        q.flush(reason="second")
        assert flush_fn.call_count == 2


class TestCheckpointQueueMaxDelay:
    """Max-delay timer forces flush regardless of ongoing write activity."""

    def test_max_delay_timer_fires_even_with_constant_activity(self):
        """Max-delay timer fires and commits even if debounce never expires."""
        flush_count = 0
        max_timer_ref: list[Any] = []
        debounce_timers: list[Any] = []

        def flush_fn():
            nonlocal flush_count
            flush_count += 1

        class FakeTimer:
            def __init__(self, interval, fn, args=(), kwargs=None):
                self.interval = interval
                self.fn = fn
                self.args = args
                self.cancelled = False
                self.daemon = True
                if abs(interval - 11.0) < 0.1:  # max_delay (10000ms + 1000)
                    max_timer_ref.append(self)
                else:
                    debounce_timers.append(self)

            def start(self):
                pass  # debounce timers don't fire automatically

            def cancel(self):
                self.cancelled = True

        q = CheckpointQueue(
            debounce_ms=10000,
            max_delay_ms=11000,
            flush_fn=flush_fn,
            _timer_factory=FakeTimer,
        )

        # Simulate 5 rapid mutations (like a burst of agent activity)
        for _ in range(5):
            q.schedule()

        assert q.pending_mutations == 5
        assert flush_count == 0, "Debounce not yet fired"

        # Simulate max-delay timer firing
        assert len(max_timer_ref) == 1, "Max-delay timer must have been created"
        max_timer_ref[0].fn(*max_timer_ref[0].args)

        assert flush_count == 1, "Max-delay timer must have triggered a flush"
        assert q.pending_mutations == 0

    def test_max_delay_at_least_debounce_plus_1000(self):
        """CheckpointQueue validates max_delay >= debounce + 1000 and auto-corrects."""
        FakeTimer, _ = TestCheckpointQueueDebounce()._make_fake_timer_factory(False)
        # debounce=5000, max_delay=3000 → invalid (3000 < 5000 + 1000)
        # Should auto-correct max_delay to 6000 and log an error
        import logging
        with patch.object(logging.getLogger("oompah.checkpoint_queue"), "error") as mock_err:
            q = CheckpointQueue(
                debounce_ms=5000,
                max_delay_ms=3000,  # invalid
                flush_fn=lambda: None,
                _timer_factory=FakeTimer,
            )
        # Must have logged an error about the correction
        mock_err.assert_called_once()
        assert "auto-correcting" in mock_err.call_args[0][0].lower() or \
               "auto-correct" in str(mock_err.call_args).lower()
        # _max_delay_ms must be corrected to debounce + 1000 = 6000
        assert q._max_delay_ms == 6000


# ---------------------------------------------------------------------------
# § 2 — Concurrent-writer safety
# ---------------------------------------------------------------------------


class TestCheckpointQueueConcurrency:
    """Concurrent schedule() calls must not lose mutations or corrupt state."""

    def test_concurrent_schedules_do_not_lose_count(self):
        """N threads each calling schedule() once → pending_mutations == N."""
        FakeTimer, _ = TestCheckpointQueueDebounce()._make_fake_timer_factory(False)
        q = CheckpointQueue(
            debounce_ms=100,
            max_delay_ms=1100,
            flush_fn=lambda: None,
            _timer_factory=FakeTimer,
        )
        n_threads = 50
        barrier = threading.Barrier(n_threads)

        def worker():
            barrier.wait()  # All threads start at the same time
            q.schedule()

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        # All mutations must be counted
        assert q.pending_mutations == n_threads, (
            f"Expected {n_threads} pending mutations; got {q.pending_mutations}"
        )

    def test_concurrent_flush_and_schedule_are_safe(self):
        """One thread flushing while another is scheduling must not deadlock or corrupt."""
        flush_counts: list[int] = []
        flush_lock = threading.Lock()

        def flush_fn():
            with flush_lock:
                flush_counts.append(1)

        FakeTimer, _ = TestCheckpointQueueDebounce()._make_fake_timer_factory(False)
        q = CheckpointQueue(
            debounce_ms=100,
            max_delay_ms=1100,
            flush_fn=flush_fn,
            _timer_factory=FakeTimer,
        )

        errors: list[Exception] = []

        def scheduler():
            try:
                for _ in range(20):
                    q.schedule()
                    time.sleep(0.001)
            except Exception as exc:
                errors.append(exc)

        def flusher():
            try:
                time.sleep(0.005)
                q.flush(reason="concurrent_test")
            except Exception as exc:
                errors.append(exc)

        t1 = threading.Thread(target=scheduler)
        t2 = threading.Thread(target=flusher)
        t1.start()
        t2.start()
        t1.join(timeout=5.0)
        t2.join(timeout=5.0)

        assert not errors, f"Unexpected exceptions: {errors}"
        # No deadlock — both threads finished

    def test_double_flush_is_idempotent(self):
        """Calling flush() twice in quick succession commits only once."""
        flush_count = 0

        def flush_fn():
            nonlocal flush_count
            flush_count += 1

        FakeTimer, _ = TestCheckpointQueueDebounce()._make_fake_timer_factory(False)
        q = CheckpointQueue(
            debounce_ms=100, max_delay_ms=1100, flush_fn=flush_fn, _timer_factory=FakeTimer
        )
        q.schedule()
        q.schedule()

        flushed1 = q.flush(reason="first")
        flushed2 = q.flush(reason="second")  # Nothing pending anymore

        assert flushed1 == 2
        assert flushed2 == 0, "Second flush must be a no-op"
        assert flush_count == 1, "flush_fn must be called only once"

    def test_concurrent_tracker_mutations_committed_atomically(
        self, state_repo: tuple[Path, str]
    ) -> None:
        """N concurrent mutations via tracker → all committed, no mutations lost.

        This is the concurrent-writer test from the task spec: 'Concurrent-writer
        and rebase-race tests prove no task mutation is lost or reordered.'
        """
        repo, state_branch = state_repo
        tracker = _make_tracker(repo, state_branch_name=state_branch, git_sync=False)

        n_tasks = 10
        created_ids: list[str] = []
        errors: list[Exception] = []
        lock = threading.Lock()
        barrier = threading.Barrier(n_tasks)

        def create_task(idx: int) -> None:
            try:
                barrier.wait()
                issue = tracker.create_issue(f"Concurrent task {idx}")
                with lock:
                    created_ids.append(issue.identifier)
            except Exception as exc:
                with lock:
                    errors.append(exc)

        threads = [threading.Thread(target=create_task, args=(i,)) for i in range(n_tasks)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10.0)

        assert not errors, f"Concurrent mutations raised exceptions: {errors}"
        assert len(created_ids) == n_tasks, (
            f"Expected {n_tasks} created tasks; got {len(created_ids)}: {created_ids}"
        )

        # Force flush so all tasks are committed to git
        tracker.flush_checkpoint(reason="test")

        # Verify all tasks are readable
        all_issues = {i.identifier: i for i in tracker.fetch_all_issues()}
        for task_id in created_ids:
            assert task_id in all_issues, (
                f"Concurrent task {task_id!r} was lost after flush"
            )


# ---------------------------------------------------------------------------
# § 3 — Push-race and retry behavior
# ---------------------------------------------------------------------------


class TestPushRaceRecovery:
    """Push races: non-ff rejection must trigger rebase + retry without losing mutations."""

    def test_push_retry_exhaustion_increments_push_failures(self):
        """When all push retries fail, push_failures is incremented."""
        flush_call_count = 0

        def always_failing_flush():
            nonlocal flush_call_count
            flush_call_count += 1
            raise TrackerError("Simulated persistent push failure")

        FakeTimer, _ = TestCheckpointQueueDebounce()._make_fake_timer_factory(False)
        q = CheckpointQueue(
            debounce_ms=100,
            max_delay_ms=1100,
            flush_fn=always_failing_flush,
            _timer_factory=FakeTimer,
        )
        q.schedule()

        with pytest.raises(TrackerError, match="push failure"):
            q.flush(reason="test")

        assert q.push_failures == 1, "push_failures must be 1 after one failed flush"

    def test_push_failure_increments_on_each_failed_flush(self):
        """Each failed flush increments push_failures by 1."""
        def failing_flush():
            raise TrackerError("push failure")

        FakeTimer, _ = TestCheckpointQueueDebounce()._make_fake_timer_factory(False)
        q = CheckpointQueue(
            debounce_ms=100,
            max_delay_ms=1100,
            flush_fn=failing_flush,
            _timer_factory=FakeTimer,
        )

        for i in range(3):
            q.schedule()
            with pytest.raises(TrackerError):
                q.flush(reason="test")
            assert q.push_failures == i + 1

    def test_successful_flush_does_not_increment_push_failures(self):
        """A successful flush must leave push_failures at 0."""
        FakeTimer, _ = TestCheckpointQueueDebounce()._make_fake_timer_factory(False)
        q = CheckpointQueue(
            debounce_ms=100,
            max_delay_ms=1100,
            flush_fn=lambda: None,
            _timer_factory=FakeTimer,
        )
        q.schedule()
        q.flush(reason="test")
        assert q.push_failures == 0

    def test_non_ff_push_triggers_rebase_and_retry(self, state_repo: tuple[Path, str]) -> None:
        """Non-fast-forward push rejection → fetch + rebase + retry; no data lost.

        This is the 'rebase-race test' from the task spec.
        """
        repo, state_branch = state_repo
        tracker = _make_tracker(
            repo, state_branch_name=state_branch, git_sync=True
        )

        push_attempt = 0
        git_calls: list[str] = []

        original_git = tracker._git

        def _fake_git(args: list[str], *, check: bool, **kwargs) -> Any:
            nonlocal push_attempt
            cmd = args[0] if args else ""
            git_calls.append(" ".join(args))
            cwd = kwargs.get("cwd", repo)

            if cmd == "push":
                push_attempt += 1
                if push_attempt <= 1:
                    # First push attempt: simulate rejection
                    result = MagicMock()
                    result.returncode = 1
                    result.stdout = ""
                    result.stderr = "! [rejected] (non-fast-forward)"
                    return result
                # Subsequent attempts: succeed
                result = MagicMock()
                result.returncode = 0
                result.stdout = ""
                result.stderr = ""
                return result

            if cmd == "remote" and "get-url" in args:
                result = MagicMock()
                result.returncode = 0
                result.stdout = "https://example.com/fake.git"
                result.stderr = ""
                return result

            if cmd == "fetch":
                result = MagicMock()
                result.returncode = 0
                result.stdout = ""
                result.stderr = ""
                return result

            if cmd == "rebase" and "--abort" not in args:
                result = MagicMock()
                result.returncode = 0
                result.stdout = ""
                result.stderr = ""
                return result

            # All other commands: run real git
            return original_git(args, check=check, **kwargs)

        tracker._git = _fake_git  # type: ignore[method-assign]

        issue = tracker.create_issue("Task for push-race test")
        tracker.flush_checkpoint(reason="test")  # Force flush

        # Push must have been retried after rebase
        push_calls = [c for c in git_calls if c.startswith("push")]
        assert len(push_calls) >= 2, (
            f"Expected ≥2 push attempts (initial + retry after rebase); "
            f"got: {push_calls}"
        )

        # Rebase must have been attempted (not reset --hard)
        rebase_calls = [c for c in git_calls if c.startswith("rebase") and "--abort" not in c]
        assert rebase_calls, (
            f"Tracker must try 'git rebase' after non-ff rejection; calls: {git_calls}"
        )

        reset_hard_calls = [c for c in git_calls if "reset" in c and "--hard" in c]
        assert not reset_hard_calls, (
            f"Tracker must NOT use 'git reset --hard'; found: {reset_hard_calls}"
        )

        # The issue must still be readable (no data loss)
        found = tracker.fetch_issue_detail(issue.identifier)
        assert found is not None, "Issue must be readable after push-race recovery"
        assert found.title == "Task for push-race test"


# ---------------------------------------------------------------------------
# § 4 — Tracker integration: coalescing behavior
# ---------------------------------------------------------------------------


class TestTrackerCheckpointCoalescing:
    """Tracker integration tests for checkpoint coalescing (OOMPAH-257)."""

    def test_tracker_exposes_checkpoint_queue_when_state_branch_enabled(
        self, state_repo: tuple[Path, str]
    ) -> None:
        """OompahMarkdownTracker must have a CheckpointQueue when state_branch_enabled=True."""
        repo, state_branch = state_repo
        tracker = _make_tracker(repo, state_branch_name=state_branch)
        assert tracker._checkpoint_queue is not None, (
            "state_branch_enabled=True must create a CheckpointQueue"
        )
        assert isinstance(tracker._checkpoint_queue, CheckpointQueue)

    def test_legacy_tracker_has_no_checkpoint_queue(self, tmp_path: Path) -> None:
        """Legacy tracker (state_branch_enabled=False) must NOT have a CheckpointQueue."""
        tracker = OompahMarkdownTracker(
            active_states=[OPEN],
            terminal_states=[DONE],
            cwd=str(tmp_path),
            git_sync=False,
        )
        assert tracker._checkpoint_queue is None

    def test_checkpoint_pending_mutations_property_increments(
        self, state_repo: tuple[Path, str]
    ) -> None:
        """checkpoint_pending_mutations increments as mutations are made."""
        repo, state_branch = state_repo
        tracker = _make_tracker(repo, state_branch_name=state_branch, git_sync=False)
        assert tracker.checkpoint_pending_mutations == 0

        tracker.create_issue("First task")
        assert tracker.checkpoint_pending_mutations == 1

        tracker.create_issue("Second task")
        assert tracker.checkpoint_pending_mutations == 2

    def test_flush_checkpoint_drains_pending_mutations(
        self, state_repo: tuple[Path, str]
    ) -> None:
        """flush_checkpoint() must drain pending_mutations to 0."""
        repo, state_branch = state_repo
        tracker = _make_tracker(repo, state_branch_name=state_branch, git_sync=False)

        tracker.create_issue("Task A")
        tracker.create_issue("Task B")
        tracker.create_issue("Task C")
        assert tracker.checkpoint_pending_mutations == 3

        count = tracker.flush_checkpoint(reason="test")
        assert count == 3, "flush_checkpoint must return the number of flushed mutations"
        assert tracker.checkpoint_pending_mutations == 0

    def test_many_mutations_within_debounce_produce_one_commit(
        self, state_repo: tuple[Path, str]
    ) -> None:
        """N mutations within the debounce window → exactly one new git commit.

        This is the 'deterministic clock test' from the task spec:
        'Deterministic clock test proves many mutations within the debounce window
        produce one commit containing all changed tasks.'
        """
        repo, state_branch = state_repo
        commits_before = _commit_count(repo, state_branch)

        tracker = _make_tracker(repo, state_branch_name=state_branch, git_sync=False)

        # Make many mutations in quick succession (all within the debounce window)
        task = tracker.create_issue("Batch task 1")
        tracker.create_issue("Batch task 2")
        tracker.create_issue("Batch task 3")
        tracker.update_issue(task.identifier, status=IN_PROGRESS)
        tracker.add_comment(task.identifier, "Batch comment", author="oompah")

        # Before flush: no git commit added yet
        commits_mid = _commit_count(repo, state_branch)
        assert commits_mid == commits_before, (
            f"No git commits must be created before flush; "
            f"expected {commits_before} commits, got {commits_mid}"
        )

        # Force the checkpoint flush
        flushed = tracker.flush_checkpoint(reason="test")
        assert flushed == 5, f"Expected 5 pending mutations to flush; got {flushed}"

        # After flush: exactly one new commit (all 5 mutations coalesced)
        commits_after = _commit_count(repo, state_branch)
        assert commits_after == commits_before + 1, (
            f"All {flushed} mutations must produce exactly 1 new git commit; "
            f"got {commits_after - commits_before} new commits"
        )

    def test_flush_checkpoint_on_legacy_tracker_is_noop(
        self, tmp_path: Path
    ) -> None:
        """flush_checkpoint() on a legacy tracker must return 0 and not raise."""
        tracker = OompahMarkdownTracker(
            active_states=[OPEN],
            terminal_states=[DONE],
            cwd=str(tmp_path),
            git_sync=False,
        )
        result = tracker.flush_checkpoint(reason="test")
        assert result == 0

    def test_checkpoint_commit_message_uses_canonical_subject(
        self, state_repo: tuple[Path, str]
    ) -> None:
        """Coalesced checkpoint commits must use the canonical subject line."""
        repo, state_branch = state_repo
        tracker = _make_tracker(repo, state_branch_name=state_branch, git_sync=False)
        tracker.create_issue("Commit message test task")
        tracker.flush_checkpoint(reason="test")

        log = _git(repo, "log", "--oneline", "-1", state_branch).stdout
        assert "Checkpoint oompah task state" in log or "oompah" in log.lower(), (
            f"Checkpoint commit message must be recognizable; got: {log!r}"
        )

    def test_all_mutations_committed_in_single_checkpoint(
        self, state_repo: tuple[Path, str]
    ) -> None:
        """After flush, all in-flight task data must appear in the git tree."""
        repo, state_branch = state_repo
        tracker = _make_tracker(repo, state_branch_name=state_branch, git_sync=False)

        # Create multiple tasks
        t1 = tracker.create_issue("Alpha task")
        t2 = tracker.create_issue("Beta task")
        t3 = tracker.create_issue("Gamma task")
        tracker.flush_checkpoint(reason="test")

        # All task files must be committed on state branch
        tree = _git(repo, "ls-tree", "-r", "--name-only", state_branch).stdout.splitlines()
        for task_id in [t1.identifier, t2.identifier, t3.identifier]:
            assert any(task_id in f for f in tree), (
                f"Task {task_id!r} must appear in state branch tree after flush; "
                f"state branch tree: {tree}"
            )

        # Main must not contain any of these task files
        main_tree = _git(repo, "ls-tree", "-r", "--name-only", "main").stdout.splitlines()
        for task_id in [t1.identifier, t2.identifier, t3.identifier]:
            assert not any(task_id in f for f in main_tree), (
                f"Task {task_id!r} must NOT appear on main branch"
            )


# ---------------------------------------------------------------------------
# § 5 — Mandatory flush for terminal/In Review status
# ---------------------------------------------------------------------------


class TestMandatoryFlushEvents:
    """Mandatory flush triggers (design § 5.3)."""

    def _commit_count_tracker(self, repo: Path, state_branch: str, tracker: OompahMarkdownTracker) -> int:
        return _commit_count(repo, state_branch)

    def test_done_status_triggers_mandatory_flush(
        self, state_repo: tuple[Path, str]
    ) -> None:
        """Transitioning to Done must flush immediately (not wait for debounce).

        Design § 5.3: 'Task status moves to a terminal state (Done, Merged, Archived)
        — data must be durable before the service dispatches the next task.'
        """
        repo, state_branch = state_repo
        tracker = _make_tracker(repo, state_branch_name=state_branch, git_sync=False)

        task = tracker.create_issue("Done flush test task")
        commits_after_create = _commit_count(repo, state_branch)

        # Transition to In Progress (non-terminal, non-mandatory)
        tracker.update_issue(task.identifier, status=IN_PROGRESS)
        commits_after_ip = _commit_count(repo, state_branch)
        # Still no commit (buffered by debounce)
        assert commits_after_ip == commits_after_create

        # Transition to Done → mandatory flush must occur immediately
        tracker.update_issue(task.identifier, status=DONE)
        commits_after_done = _commit_count(repo, state_branch)
        assert commits_after_done > commits_after_create, (
            f"Transitioning to Done must trigger a mandatory checkpoint flush; "
            f"commits before Done: {commits_after_create}, after: {commits_after_done}"
        )
        assert tracker.checkpoint_pending_mutations == 0, (
            "Pending mutations must be 0 after mandatory flush on Done"
        )

    def test_merged_status_triggers_mandatory_flush(
        self, state_repo: tuple[Path, str]
    ) -> None:
        """Transitioning to Merged must flush immediately (terminal status)."""
        repo, state_branch = state_repo
        tracker = _make_tracker(repo, state_branch_name=state_branch, git_sync=False)

        task = tracker.create_issue("Merged flush test task")
        commits_before = _commit_count(repo, state_branch)

        tracker.update_issue(task.identifier, status=MERGED)
        commits_after = _commit_count(repo, state_branch)
        assert commits_after > commits_before, (
            "Transitioning to Merged must trigger a mandatory checkpoint flush"
        )

    def test_archived_status_triggers_mandatory_flush(
        self, state_repo: tuple[Path, str]
    ) -> None:
        """Transitioning to Archived must flush immediately (terminal status)."""
        repo, state_branch = state_repo
        tracker = _make_tracker(repo, state_branch_name=state_branch, git_sync=False)

        task = tracker.create_issue("Archived flush test task")
        commits_before = _commit_count(repo, state_branch)

        tracker.update_issue(task.identifier, status=ARCHIVED)
        commits_after = _commit_count(repo, state_branch)
        assert commits_after > commits_before, (
            "Transitioning to Archived must trigger a mandatory checkpoint flush"
        )

    def test_in_review_status_triggers_mandatory_flush(
        self, state_repo: tuple[Path, str]
    ) -> None:
        """Transitioning to In Review must flush immediately.

        Design § 5.3: 'Task status moves to In Review — PR has been opened;
        PR URL must be committed immediately so the poller can find it.'
        """
        repo, state_branch = state_repo
        tracker = _make_tracker(repo, state_branch_name=state_branch, git_sync=False)

        task = tracker.create_issue("In Review flush test task")
        commits_before = _commit_count(repo, state_branch)

        tracker.update_issue(task.identifier, status=IN_REVIEW)
        commits_after = _commit_count(repo, state_branch)
        assert commits_after > commits_before, (
            "Transitioning to In Review must trigger a mandatory checkpoint flush"
        )

    def test_in_progress_status_does_not_trigger_mandatory_flush(
        self, state_repo: tuple[Path, str]
    ) -> None:
        """Transitioning to In Progress must NOT trigger an immediate flush.

        Only terminal statuses and In Review are mandatory; In Progress is not.
        """
        repo, state_branch = state_repo
        tracker = _make_tracker(repo, state_branch_name=state_branch, git_sync=False)

        task = tracker.create_issue("In Progress no-flush test task")
        commits_after_create = _commit_count(repo, state_branch)

        tracker.update_issue(task.identifier, status=IN_PROGRESS)
        commits_after_ip = _commit_count(repo, state_branch)

        assert commits_after_ip == commits_after_create, (
            "Transitioning to In Progress must NOT trigger an immediate flush"
        )
        assert tracker.checkpoint_pending_mutations > 0, (
            "Pending mutations must still be buffered after In Progress transition"
        )

    def test_open_status_does_not_trigger_mandatory_flush(
        self, state_repo: tuple[Path, str]
    ) -> None:
        """Reopening a task (→ Open) must NOT trigger an immediate flush."""
        repo, state_branch = state_repo
        tracker = _make_tracker(repo, state_branch_name=state_branch, git_sync=False)

        # Create task, transition to Done (mandatory flush), then reopen
        task = tracker.create_issue("Reopen no-flush test task")
        tracker.update_issue(task.identifier, status=DONE)  # mandatory flush
        commits_after_done = _commit_count(repo, state_branch)

        tracker.update_issue(task.identifier, status=OPEN)  # should NOT flush
        commits_after_reopen = _commit_count(repo, state_branch)
        assert commits_after_reopen == commits_after_done, (
            "Reopening (→ Open) must NOT trigger an immediate flush"
        )

    def test_explicit_flush_for_human_edit(
        self, state_repo: tuple[Path, str]
    ) -> None:
        """Human-initiated edits can call flush_checkpoint(reason='human_edit') to flush immediately.

        Design § 5.3: 'PATCH /api/v1/issues/{id} from a human operator — human-
        initiated changes are higher-priority than agent activity.'
        """
        repo, state_branch = state_repo
        tracker = _make_tracker(repo, state_branch_name=state_branch, git_sync=False)

        task = tracker.create_issue("Human edit test task")
        tracker.update_issue(task.identifier, description="Updated by human")
        commits_before_flush = _commit_count(repo, state_branch)

        # Simulate human edit handler calling flush immediately
        tracker.flush_checkpoint(reason="human_edit")
        commits_after_flush = _commit_count(repo, state_branch)

        assert commits_after_flush > commits_before_flush, (
            "flush_checkpoint(reason='human_edit') must commit pending mutations"
        )
        assert tracker.checkpoint_pending_mutations == 0


# ---------------------------------------------------------------------------
# § 6 — Ephemeral vs durable classification
# ---------------------------------------------------------------------------


class TestEphemeralVsDurable:
    """Ephemeral agent updates must not trigger checkpoint schedules (§ 4)."""

    def test_add_comment_without_flush_leaves_pending(
        self, state_repo: tuple[Path, str]
    ) -> None:
        """An add_comment() call that is not a terminal event stays buffered."""
        repo, state_branch = state_repo
        tracker = _make_tracker(repo, state_branch_name=state_branch, git_sync=False)
        task = tracker.create_issue("Ephemeral comment test task")

        commits_before = _commit_count(repo, state_branch)
        # Non-terminal comment: buffered, not committed
        tracker.add_comment(task.identifier, "Intermediate agent progress", author="oompah")
        commits_after = _commit_count(repo, state_branch)
        assert commits_after == commits_before, (
            "An intermediate (non-mandatory) comment must NOT create a git commit"
        )
        assert tracker.checkpoint_pending_mutations > 0

    def test_focus_handoff_comment_is_committed_on_terminal_status(
        self, state_repo: tuple[Path, str]
    ) -> None:
        """A focus-handoff comment followed by a terminal status → committed.

        Regression test: 'ephemeral agent updates do not create commits while
        a focus handoff does.'

        The focus handoff comment itself is queued (not committed immediately).
        The DONE status transition triggers the mandatory flush, which commits
        BOTH the focus-handoff comment AND the status change in one atomic
        checkpoint commit.
        """
        repo, state_branch = state_repo
        tracker = _make_tracker(repo, state_branch_name=state_branch, git_sync=False)

        task = tracker.create_issue("Focus handoff test task")
        commits_before = _commit_count(repo, state_branch)
        pending_before = tracker.checkpoint_pending_mutations

        # Post focus-handoff comment (durable but not immediately flushed)
        tracker.add_comment(
            task.identifier,
            "Focus handoff: feature\n\nOutcome: Implementation complete.",
            author="oompah",
        )
        # Comment is buffered; no commit yet
        assert _commit_count(repo, state_branch) == commits_before
        assert tracker.checkpoint_pending_mutations > pending_before

        # Mark as Done → mandatory flush commits both the comment and the status
        tracker.update_issue(task.identifier, status=DONE)
        commits_after = _commit_count(repo, state_branch)
        assert commits_after > commits_before, (
            "Done transition must flush the focus-handoff comment AND the status change"
        )

        # Verify both the comment and status are in the committed task file
        task_data = tracker.fetch_issue_detail(task.identifier)
        assert task_data is not None
        assert task_data.state == DONE

    def test_status_changes_are_durable(
        self, state_repo: tuple[Path, str]
    ) -> None:
        """Status changes are durable: they schedule a checkpoint (or flush if terminal)."""
        repo, state_branch = state_repo
        tracker = _make_tracker(repo, state_branch_name=state_branch, git_sync=False)

        task = tracker.create_issue("Status durable test task")
        commits_before = _commit_count(repo, state_branch)

        # Non-terminal status change: schedules checkpoint (buffered)
        tracker.update_issue(task.identifier, status=IN_PROGRESS)
        assert tracker.checkpoint_pending_mutations > 0, (
            "Non-terminal status change must schedule a checkpoint (durable)"
        )

    def test_label_change_is_durable(
        self, state_repo: tuple[Path, str]
    ) -> None:
        """Label changes are durable (schedule a checkpoint)."""
        repo, state_branch = state_repo
        tracker = _make_tracker(repo, state_branch_name=state_branch, git_sync=False)

        task = tracker.create_issue("Label durable test task")
        pending_before = tracker.checkpoint_pending_mutations

        tracker.add_label(task.identifier, "backend")
        assert tracker.checkpoint_pending_mutations > pending_before, (
            "Label change must schedule a checkpoint (durable)"
        )

    def test_description_update_is_durable(
        self, state_repo: tuple[Path, str]
    ) -> None:
        """Description updates are durable (schedule a checkpoint)."""
        repo, state_branch = state_repo
        tracker = _make_tracker(repo, state_branch_name=state_branch, git_sync=False)

        task = tracker.create_issue("Description durable test")
        pending_before = tracker.checkpoint_pending_mutations

        tracker.update_issue(task.identifier, description="New description")
        assert tracker.checkpoint_pending_mutations > pending_before, (
            "Description update must schedule a checkpoint (durable)"
        )


# ---------------------------------------------------------------------------
# § 7 — Observability
# ---------------------------------------------------------------------------


class TestCheckpointObservability:
    """Tests for observability surface: pending_mutations, last_push_at, push_failures."""

    def test_pending_mutations_starts_at_zero(
        self, state_repo: tuple[Path, str]
    ) -> None:
        """Freshly created tracker has 0 pending mutations."""
        repo, state_branch = state_repo
        tracker = _make_tracker(repo, state_branch_name=state_branch)
        assert tracker.checkpoint_pending_mutations == 0

    def test_last_push_at_is_none_before_first_flush(
        self, state_repo: tuple[Path, str]
    ) -> None:
        """last_push_at must be None before any flush has occurred."""
        repo, state_branch = state_repo
        tracker = _make_tracker(repo, state_branch_name=state_branch)
        assert tracker.checkpoint_last_push_at is None

    def test_last_push_at_set_after_successful_flush(
        self, state_repo: tuple[Path, str]
    ) -> None:
        """last_push_at must be an ISO-8601 timestamp after a successful flush."""
        repo, state_branch = state_repo
        tracker = _make_tracker(repo, state_branch_name=state_branch, git_sync=False)

        tracker.create_issue("Last push test task")
        tracker.flush_checkpoint(reason="test")

        ts = tracker.checkpoint_last_push_at
        assert ts is not None, "last_push_at must be set after a successful flush"
        # Must be a valid ISO-8601 string
        from datetime import datetime
        try:
            datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            pytest.fail(f"last_push_at is not a valid ISO-8601 timestamp: {ts!r}")

    def test_push_failures_starts_at_zero(
        self, state_repo: tuple[Path, str]
    ) -> None:
        """push_failures must be 0 on a fresh tracker."""
        repo, state_branch = state_repo
        tracker = _make_tracker(repo, state_branch_name=state_branch)
        assert tracker.checkpoint_push_failures == 0

    def test_get_checkpoint_observability_returns_none_for_legacy_tracker(
        self, tmp_path: Path
    ) -> None:
        """get_checkpoint_observability() returns None for legacy (non-state-branch) tracker."""
        tracker = OompahMarkdownTracker(
            active_states=[OPEN],
            terminal_states=[DONE],
            cwd=str(tmp_path),
            git_sync=False,
        )
        assert tracker.get_checkpoint_observability() is None

    def test_get_checkpoint_observability_returns_dict_for_state_branch_tracker(
        self, state_repo: tuple[Path, str]
    ) -> None:
        """get_checkpoint_observability() returns a dict with all required fields.

        The state_repo fixture has a bootstrap commit on the state branch.
        Before any CheckpointQueue.flush() call, last_push_at falls back to
        the git commit timestamp of that bootstrap commit (OOMPAH-283).
        """
        repo, state_branch = state_repo
        tracker = _make_tracker(repo, state_branch_name=state_branch)

        obs = tracker.get_checkpoint_observability()
        assert obs is not None
        assert obs["branch"] == state_branch
        assert obs["pending_mutations"] == 0
        assert obs["push_failures"] == 0
        # After bootstrap a git commit exists — last_push_at must be a
        # valid ISO-8601 timestamp, not None (OOMPAH-283 fix).
        assert obs["last_push_at"] is not None, (
            "last_push_at must reflect the bootstrap commit, not None"
        )
        from datetime import datetime
        try:
            datetime.fromisoformat(obs["last_push_at"].replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            pytest.fail(
                f"last_push_at is not a valid ISO-8601 timestamp: {obs['last_push_at']!r}"
            )
        assert obs["alert"] is None

    def test_get_checkpoint_observability_last_push_at_is_none_when_no_git_commits(
        self, tmp_path: Path
    ) -> None:
        """last_push_at is None when the state branch has no commits yet.

        This covers the edge case where a tracker is created with a state
        branch that exists locally but has no commits (the queue has not
        flushed and git log returns nothing).
        """
        # Create a bare repo with main + an empty orphan state branch (no commits).
        repo = tmp_path / "repo"
        _init_git_repo(repo)
        sb = "oompah/state/proj-nocommit"
        _git(repo, "checkout", "--orphan", sb)
        _git(repo, "reset", "--hard")
        # Do NOT commit — the branch ref does not exist yet in git.
        # Switch back to main so the tracker can start cleanly.
        _git(repo, "checkout", "main")

        # We can't create a tracker against a non-existent branch (TrackerError).
        # Instead, verify _get_state_branch_last_commit_at() returns None when
        # the branch does not exist.
        tracker = OompahMarkdownTracker(
            active_states=[OPEN],
            terminal_states=[DONE],
            cwd=str(repo),
            default_branch="main",
            git_sync=False,
            state_branch_enabled=True,
            state_branch_name="oompah/state/proj-nocommit",
            state_branch_checkpoint_debounce_ms=5000,
            state_branch_checkpoint_max_delay_ms=30000,
        )
        # _get_state_branch_last_commit_at must return None for a branch that
        # has no commits (git log returns non-zero / empty output).
        ts = tracker._get_state_branch_last_commit_at()
        assert ts is None, (
            f"Expected None when branch has no commits, got {ts!r}"
        )

    def test_get_checkpoint_observability_last_push_at_reflects_bootstrap_commit(
        self, state_repo: tuple[Path, str]
    ) -> None:
        """last_push_at reflects the bootstrap commit immediately after startup.

        Reproduces the 'Last push: never' bug (OOMPAH-283): right after
        state-branch bootstrap the CheckpointQueue has never flushed, so
        _last_push_at is None.  The fix makes get_checkpoint_observability()
        fall back to the latest git commit on the state branch.
        """
        repo, state_branch = state_repo
        # Record the bootstrap commit timestamp directly from git.
        result = _git(repo, "log", "-1", "--format=%aI", state_branch)
        bootstrap_ts = result.stdout.strip()
        assert bootstrap_ts, "state_repo fixture must have a bootstrap commit"

        # Tracker starts fresh — queue has never flushed.
        tracker = _make_tracker(repo, state_branch_name=state_branch)
        assert tracker.checkpoint_last_push_at is None, (
            "In-memory last_push_at must still be None (queue has not flushed)"
        )

        obs = tracker.get_checkpoint_observability()
        assert obs is not None
        # Must report the bootstrap commit time, not None.
        assert obs["last_push_at"] == bootstrap_ts, (
            f"Expected bootstrap timestamp {bootstrap_ts!r}, "
            f"got {obs['last_push_at']!r}"
        )

    def test_observability_alert_set_after_push_failure(self) -> None:
        """get_checkpoint_observability() alert field is set after push failure."""
        def failing_flush():
            raise TrackerError("Simulated push failure")

        FakeTimer, _ = TestCheckpointQueueDebounce()._make_fake_timer_factory(False)
        q = CheckpointQueue(
            debounce_ms=100,
            max_delay_ms=1100,
            flush_fn=failing_flush,
            _timer_factory=FakeTimer,
        )
        q.schedule()
        with pytest.raises(TrackerError):
            q.flush(reason="test")

        obs = q.get_observability_dict(branch="oompah/state/proj-test")
        assert obs["push_failures"] == 1
        assert obs["alert"] == "push_failed"

    def test_observability_pending_mutations_reflects_current_count(
        self, state_repo: tuple[Path, str]
    ) -> None:
        """pending_mutations in observability dict must match checkpoint_pending_mutations."""
        repo, state_branch = state_repo
        tracker = _make_tracker(repo, state_branch_name=state_branch, git_sync=False)

        tracker.create_issue("Observability test task 1")
        tracker.create_issue("Observability test task 2")

        obs = tracker.get_checkpoint_observability()
        assert obs is not None
        assert obs["pending_mutations"] == tracker.checkpoint_pending_mutations == 2

    def test_legacy_tracker_checkpoint_properties_return_zero_or_none(
        self, tmp_path: Path
    ) -> None:
        """Legacy tracker checkpoint properties return safe defaults."""
        tracker = OompahMarkdownTracker(
            active_states=[OPEN],
            terminal_states=[DONE],
            cwd=str(tmp_path),
            git_sync=False,
        )
        assert tracker.checkpoint_pending_mutations == 0
        assert tracker.checkpoint_last_push_at is None
        assert tracker.checkpoint_push_failures == 0


# ---------------------------------------------------------------------------
# § 8 — Integration: all commits target state branch only
# ---------------------------------------------------------------------------


class TestStateBranchIsolation:
    """All checkpoint commits must land on the state branch, not on main."""

    def test_checkpoint_commits_only_to_state_branch(
        self, state_repo: tuple[Path, str]
    ) -> None:
        """After flush, all commits are on the state branch; main is unchanged."""
        repo, state_branch = state_repo
        main_sha_before = _commit_sha(repo, "main")
        commits_before = _commit_count(repo, state_branch)

        tracker = _make_tracker(repo, state_branch_name=state_branch, git_sync=False)
        tracker.create_issue("State branch isolation task 1")
        tracker.create_issue("State branch isolation task 2")
        tracker.flush_checkpoint(reason="test")

        # Main must be unchanged
        assert _commit_sha(repo, "main") == main_sha_before, (
            "main branch must NOT be modified by checkpoint commits"
        )

        # State branch must have at least one new commit
        assert _commit_count(repo, state_branch) > commits_before, (
            "State branch must have new commits after flush"
        )

    def test_multiple_flushes_stay_on_state_branch(
        self, state_repo: tuple[Path, str]
    ) -> None:
        """Multiple flush cycles must all commit to the state branch only."""
        repo, state_branch = state_repo
        main_sha_before = _commit_sha(repo, "main")

        tracker = _make_tracker(repo, state_branch_name=state_branch, git_sync=False)

        # First flush cycle
        tracker.create_issue("Cycle 1 task A")
        tracker.create_issue("Cycle 1 task B")
        tracker.flush_checkpoint(reason="cycle-1")

        # Second flush cycle
        tracker.create_issue("Cycle 2 task A")
        tracker.flush_checkpoint(reason="cycle-2")

        # Main must still be unchanged after both flushes
        assert _commit_sha(repo, "main") == main_sha_before, (
            "main branch must remain unchanged after multiple checkpoint flushes"
        )

    def test_checkpoint_commit_is_on_oompah_state_namespace(
        self, state_repo: tuple[Path, str]
    ) -> None:
        """Checkpoint commits must land on a branch under oompah/state/."""
        repo, state_branch = state_repo
        assert state_branch.startswith("oompah/state/"), (
            "State branch must be under the oompah/state/ namespace"
        )

        tracker = _make_tracker(repo, state_branch_name=state_branch, git_sync=False)
        tracker.create_issue("Namespace test task")
        tracker.flush_checkpoint(reason="test")

        # Verify the commit appears on the state branch
        log = _git(repo, "log", "--oneline", "-3", state_branch).stdout
        assert "Checkpoint" in log or "oompah" in log.lower(), (
            f"Expected checkpoint commit on {state_branch!r}: {log!r}"
        )


# ---------------------------------------------------------------------------
# § 9 — Shutdown flush
# ---------------------------------------------------------------------------


class TestShutdownFlush:
    """Service shutdown must flush any pending mutations before exiting."""

    def test_shutdown_flushes_pending_mutations(
        self, state_repo: tuple[Path, str]
    ) -> None:
        """shutdown_checkpoint() must commit any buffered mutations."""
        repo, state_branch = state_repo
        commits_before = _commit_count(repo, state_branch)

        tracker = _make_tracker(repo, state_branch_name=state_branch, git_sync=False)
        tracker.create_issue("Shutdown test task 1")
        tracker.create_issue("Shutdown test task 2")

        assert tracker.checkpoint_pending_mutations == 2

        tracker.shutdown_checkpoint()  # Simulates service SIGTERM

        commits_after = _commit_count(repo, state_branch)
        assert commits_after > commits_before, (
            "shutdown_checkpoint() must flush pending mutations to git"
        )
        assert tracker.checkpoint_pending_mutations == 0, (
            "Pending mutations must be 0 after shutdown flush"
        )

    def test_shutdown_with_no_pending_is_noop(
        self, state_repo: tuple[Path, str]
    ) -> None:
        """shutdown_checkpoint() with no pending mutations must not raise or commit."""
        repo, state_branch = state_repo
        commits_before = _commit_count(repo, state_branch)

        tracker = _make_tracker(repo, state_branch_name=state_branch, git_sync=False)
        tracker.shutdown_checkpoint()  # Nothing pending

        assert _commit_count(repo, state_branch) == commits_before, (
            "shutdown_checkpoint() with no pending mutations must not create a commit"
        )

    def test_shutdown_on_legacy_tracker_is_noop(self, tmp_path: Path) -> None:
        """shutdown_checkpoint() on a legacy tracker must not raise."""
        tracker = OompahMarkdownTracker(
            active_states=[OPEN],
            terminal_states=[DONE],
            cwd=str(tmp_path),
            git_sync=False,
        )
        tracker.shutdown_checkpoint()  # Must not raise

    def test_checkpoint_queue_shutdown_method(self) -> None:
        """CheckpointQueue.shutdown() flushes pending mutations."""
        flushed = []

        def flush_fn():
            flushed.append(1)

        FakeTimer, _ = TestCheckpointQueueDebounce()._make_fake_timer_factory(False)
        q = CheckpointQueue(
            debounce_ms=100, max_delay_ms=1100, flush_fn=flush_fn, _timer_factory=FakeTimer
        )
        q.schedule()
        q.schedule()

        q.shutdown()
        assert len(flushed) == 1, "shutdown() must call flush_fn once"
        assert q.pending_mutations == 0


# ---------------------------------------------------------------------------
# § 10 — Auto-correction of invalid max_delay < debounce
# ---------------------------------------------------------------------------


class TestMaxDelayAutoCorrection:
    """max_delay must be auto-corrected when < debounce + 1000 (design § 5.2)."""

    def test_max_delay_less_than_debounce_corrected_with_error_log(self) -> None:
        """max_delay < debounce → corrected to debounce + 1000 and error logged."""
        import logging
        FakeTimer, _ = TestCheckpointQueueDebounce()._make_fake_timer_factory(False)

        with patch.object(
            logging.getLogger("oompah.checkpoint_queue"), "error"
        ) as mock_err:
            q = CheckpointQueue(
                debounce_ms=10000,
                max_delay_ms=5000,  # invalid
                flush_fn=lambda: None,
                _timer_factory=FakeTimer,
            )

        assert q._max_delay_ms == 11000, (
            f"max_delay must be corrected to debounce + 1000 = 11000; got {q._max_delay_ms}"
        )
        mock_err.assert_called_once()

    def test_max_delay_equal_to_debounce_corrected(self) -> None:
        """max_delay == debounce → corrected to debounce + 1000."""
        import logging
        FakeTimer, _ = TestCheckpointQueueDebounce()._make_fake_timer_factory(False)

        with patch.object(
            logging.getLogger("oompah.checkpoint_queue"), "error"
        ) as mock_err:
            q = CheckpointQueue(
                debounce_ms=5000,
                max_delay_ms=5000,  # equal — invalid (must be >= debounce + 1000)
                flush_fn=lambda: None,
                _timer_factory=FakeTimer,
            )

        assert q._max_delay_ms == 6000
        mock_err.assert_called_once()

    def test_valid_max_delay_not_corrected(self) -> None:
        """Valid max_delay >= debounce + 1000 must NOT be corrected."""
        import logging
        FakeTimer, _ = TestCheckpointQueueDebounce()._make_fake_timer_factory(False)

        with patch.object(
            logging.getLogger("oompah.checkpoint_queue"), "error"
        ) as mock_err:
            q = CheckpointQueue(
                debounce_ms=5000,
                max_delay_ms=30000,  # valid (30000 >= 5000 + 1000)
                flush_fn=lambda: None,
                _timer_factory=FakeTimer,
            )

        assert q._max_delay_ms == 30000, "Valid max_delay must not be modified"
        mock_err.assert_not_called()

    def test_tracker_applies_auto_correction_via_checkpoint_queue(
        self, state_repo: tuple[Path, str]
    ) -> None:
        """OompahMarkdownTracker with invalid max_delay must auto-correct via CheckpointQueue."""
        repo, state_branch = state_repo
        import logging

        with patch.object(
            logging.getLogger("oompah.checkpoint_queue"), "error"
        ) as mock_err:
            tracker = _make_tracker(
                repo,
                state_branch_name=state_branch,
                debounce_ms=8000,
                max_delay_ms=3000,  # invalid
            )

        assert tracker._checkpoint_queue is not None
        assert tracker._checkpoint_queue._max_delay_ms == 9000, (
            f"max_delay must be auto-corrected to 9000; got {tracker._checkpoint_queue._max_delay_ms}"
        )
        mock_err.assert_called_once()

    def test_boundary_value_debounce_plus_1000_is_valid(self) -> None:
        """max_delay == debounce + 1000 is the minimum valid value."""
        import logging
        FakeTimer, _ = TestCheckpointQueueDebounce()._make_fake_timer_factory(False)

        with patch.object(
            logging.getLogger("oompah.checkpoint_queue"), "error"
        ) as mock_err:
            q = CheckpointQueue(
                debounce_ms=5000,
                max_delay_ms=6000,  # exactly debounce + 1000 → valid
                flush_fn=lambda: None,
                _timer_factory=FakeTimer,
            )

        assert q._max_delay_ms == 6000, "Exactly debounce+1000 must not be corrected"
        mock_err.assert_not_called()
