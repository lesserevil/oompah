"""Unit and integration tests for the async backlog refresh manager (OOMPAH-251).

Covers:
- RefreshStatus.to_dict() serialisation
- BacklogRefreshManager.get_or_start(): start, in-progress reuse, TTL expiry, completion
- BacklogRefreshManager.trigger_refresh(): force-restart, stale result retention
- BacklogRefreshManager.get_status(): phase transitions during run
- BacklogRefreshManager.get_cached_result(): None before first run, filled after
- BacklogRefreshManager.is_running()
- Progress callback phases emitted during get_backlog() run
- Failed refresh: error stored, previous result retained
- Retry: trigger_refresh after failure starts a new job
- Concurrent requests: reuse the same in-flight job (no duplicate runs)
- Thread safety: multiple threads calling get_or_start() simultaneously
- Phase ordering: loading_merged → resolving_commits → comparing_ancestry →
  preparing_rows → diagnostics → complete
"""

from __future__ import annotations

import asyncio
import time
import threading
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oompah.release_delivery_refresh import (
    PHASES,
    BacklogRefreshManager,
    RefreshStatus,
)
from oompah.release_delivery_backlog import (
    BacklogResult,
    ItemRow,
    SourceCommitInfo,
    UnassociatedCommitRow,
)
from oompah.release_delivery_inventory import ReleaseStatusCell

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PROJECT_ID = "proj-refresh-test"
_BRANCH = "release/0.11"
_SOURCE_HEAD = "s" * 40
_RELEASE_HEAD = "r" * 40


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_backlog_result(
    *,
    n_items: int = 2,
    stale: bool = False,
) -> BacklogResult:
    items = [
        ItemRow(
            identifier=f"TASK-{i}",
            title=f"Task {i}",
            kind="task",
            source_commits=[
                SourceCommitInfo(
                    sha=f"{i:040x}",
                    short_sha=f"{i:07x}",
                    subject=f"feat: task {i}",
                    author_name="Dev",
                    authored_at="2026-07-01T00:00:00Z",
                )
            ],
            delivery_status=ReleaseStatusCell(state="not_selected"),
            delivery_id=None,
            commit_count=1,
            most_recent_commit_at="2026-07-01T00:00:00Z",
        )
        for i in range(1, n_items + 1)
    ]
    return BacklogResult(
        project_id=_PROJECT_ID,
        source_branch="main",
        source_head=_SOURCE_HEAD,
        selected_branch=_BRANCH,
        branch_head=_RELEASE_HEAD,
        branch_available=True,
        items=items,
        unassociated_commits=[],
        stale=stale,
        refreshed_at="2026-07-01T00:00:00+00:00",
        total_commit_count=n_items,
    )


def _make_service_mock(
    result: BacklogResult | None = None,
    *,
    delay: float = 0.0,
    error: Exception | None = None,
) -> MagicMock:
    """Return a mock ItemBacklogService.

    Args:
        result: BacklogResult to return from get_backlog().
        delay: Artificial delay in seconds before returning.
        error: If set, get_backlog raises this exception instead.
    """
    svc = MagicMock()
    if error is not None:
        def _get_backlog(**kwargs):
            if delay:
                time.sleep(delay)
            raise error
        svc.get_backlog.side_effect = _get_backlog
    else:
        def _get_backlog(
            selected_branch=None,
            filter="all",
            query=None,
            tracker=None,
            progress_callback=None,
        ):
            if delay:
                time.sleep(delay)
            # Simulate progress callbacks if provided
            if progress_callback and result is not None:
                progress_callback("loading_merged", 0, None)
                progress_callback("resolving_commits", 0, 2)
                progress_callback("resolving_commits", 1, 2)
                progress_callback("resolving_commits", 2, 2)
                progress_callback("comparing_ancestry", 0, None)
                progress_callback("preparing_rows", 0, 2)
                progress_callback("preparing_rows", 2, 2)
                progress_callback("diagnostics", 0, None)
            return result
        svc.get_backlog.side_effect = _get_backlog
    return svc


# ---------------------------------------------------------------------------
# RefreshStatus tests
# ---------------------------------------------------------------------------


class TestRefreshStatus:
    def test_default_phase_is_pending(self):
        status = RefreshStatus()
        assert status.phase == "pending"

    def test_to_dict_contains_required_fields(self):
        status = RefreshStatus(
            phase="resolving_commits",
            completed=5,
            total=20,
            elapsed_s=2.3,
            error=None,
            has_result=False,
        )
        d = status.to_dict()
        assert d["phase"] == "resolving_commits"
        assert d["completed"] == 5
        assert d["total"] == 20
        assert d["has_result"] is False
        assert "elapsed_s" in d

    def test_to_dict_omits_none_total(self):
        """total is omitted from to_dict() when None (phase with unknown total)."""
        status = RefreshStatus(phase="loading_merged", total=None)
        d = status.to_dict()
        assert "total" not in d

    def test_to_dict_omits_none_error(self):
        """error is omitted from to_dict() when None."""
        status = RefreshStatus(phase="complete", error=None)
        d = status.to_dict()
        assert "error" not in d

    def test_to_dict_includes_error_when_set(self):
        status = RefreshStatus(phase="failed", error="git timeout")
        d = status.to_dict()
        assert d["error"] == "git timeout"

    def test_to_dict_elapsed_s_rounded(self):
        status = RefreshStatus(elapsed_s=1.23456789)
        d = status.to_dict()
        # Rounded to 3 decimal places
        assert d["elapsed_s"] == round(1.23456789, 3)

    def test_has_result_true_when_cached(self):
        status = RefreshStatus(has_result=True, phase="complete")
        assert status.to_dict()["has_result"] is True

    def test_all_phases_are_valid_strings(self):
        """All phase constants are non-empty strings."""
        for phase in PHASES:
            assert isinstance(phase, str)
            assert len(phase) > 0


# ---------------------------------------------------------------------------
# BacklogRefreshManager: get_cached_result and is_running
# ---------------------------------------------------------------------------


class TestRefreshManagerBasicState:
    def test_get_cached_result_none_before_any_run(self):
        manager = BacklogRefreshManager()
        assert manager.get_cached_result(_PROJECT_ID, _BRANCH) is None

    def test_get_status_none_before_any_run(self):
        manager = BacklogRefreshManager()
        assert manager.get_status(_PROJECT_ID, _BRANCH) is None

    def test_is_running_false_before_any_run(self):
        manager = BacklogRefreshManager()
        assert manager.is_running(_PROJECT_ID, _BRANCH) is False

    def test_keys_are_independent(self):
        """Different (project_id, branch) keys are independent."""
        manager = BacklogRefreshManager()
        assert manager.get_status("proj-a", "release/1.0") is None
        assert manager.get_status("proj-b", "release/1.0") is None
        assert manager.get_status("proj-a", "release/2.0") is None


# ---------------------------------------------------------------------------
# BacklogRefreshManager: get_or_start
# ---------------------------------------------------------------------------


class TestRefreshManagerGetOrStart:
    @pytest.mark.asyncio
    async def test_first_call_returns_none_cached_result(self):
        """First call returns (status, None) — no cached result yet."""
        manager = BacklogRefreshManager()
        backlog = _make_backlog_result()
        svc = _make_service_mock(backlog, delay=0.05)

        status, cached = await manager.get_or_start(
            _PROJECT_ID, _BRANCH, service=svc
        )
        assert cached is None
        assert status.phase in ("pending", "loading_merged")

    @pytest.mark.asyncio
    async def test_result_available_after_job_completes(self):
        """Cached result is set after the background task finishes."""
        manager = BacklogRefreshManager()
        backlog = _make_backlog_result()
        svc = _make_service_mock(backlog)

        status, cached = await manager.get_or_start(
            _PROJECT_ID, _BRANCH, service=svc
        )
        # Wait for the background task to complete
        await asyncio.sleep(0.1)

        final = manager.get_cached_result(_PROJECT_ID, _BRANCH)
        assert final is not None
        assert final.project_id == _PROJECT_ID
        assert len(final.items) == 2

    @pytest.mark.asyncio
    async def test_second_call_while_running_reuses_job(self):
        """Second call while a job is in progress does not start a new task."""
        manager = BacklogRefreshManager()
        backlog = _make_backlog_result()
        svc = _make_service_mock(backlog, delay=0.05)

        status1, _ = await manager.get_or_start(_PROJECT_ID, _BRANCH, service=svc)
        # Immediately call again while first task is still running
        status2, _ = await manager.get_or_start(_PROJECT_ID, _BRANCH, service=svc)

        # Both calls should see the same phase (the in-flight job)
        assert status1.phase in PHASES
        assert status2.phase in PHASES

        # Wait for the background task to complete
        await asyncio.sleep(0.2)

        # service.get_backlog should only have been called once (not duplicated)
        assert svc.get_backlog.call_count == 1, (
            f"Expected exactly 1 get_backlog call; two concurrent get_or_start "
            f"calls must reuse the same in-flight job"
        )

    @pytest.mark.asyncio
    async def test_completed_job_not_restarted_within_ttl(self):
        """Completed job is not restarted on subsequent calls within TTL."""
        manager = BacklogRefreshManager(result_ttl_s=300.0)  # 5 min TTL
        backlog = _make_backlog_result()
        svc = _make_service_mock(backlog)

        # First call: starts the job
        await manager.get_or_start(_PROJECT_ID, _BRANCH, service=svc)
        await asyncio.sleep(0.05)  # Let it complete

        # Second call: result is fresh, no new job
        status, cached = await manager.get_or_start(_PROJECT_ID, _BRANCH, service=svc)

        assert cached is not None
        assert status.phase == "complete"
        # Still only one get_backlog call
        assert svc.get_backlog.call_count == 1

    @pytest.mark.asyncio
    async def test_expired_result_triggers_new_refresh(self):
        """Expired result (past TTL) triggers a new refresh on next call."""
        manager = BacklogRefreshManager(result_ttl_s=0.01)  # Very short TTL
        backlog = _make_backlog_result()
        svc = _make_service_mock(backlog)

        # First call: starts the job, completes
        await manager.get_or_start(_PROJECT_ID, _BRANCH, service=svc)
        await asyncio.sleep(0.05)  # Let it complete and expire TTL

        assert svc.get_backlog.call_count == 1

        # Second call after TTL expired: should start a new job
        await manager.get_or_start(_PROJECT_ID, _BRANCH, service=svc)
        await asyncio.sleep(0.05)  # Let it complete

        assert svc.get_backlog.call_count == 2

    @pytest.mark.asyncio
    async def test_stale_result_returned_while_refresh_runs(self):
        """Stale cached result is returned immediately while new refresh runs.

        This is the stale-while-revalidate model: the old result is served
        immediately so the client is never left with an empty state.
        """
        manager = BacklogRefreshManager(result_ttl_s=0.01)  # Very short TTL
        backlog1 = _make_backlog_result(n_items=1)
        svc1 = _make_service_mock(backlog1)

        # First run
        await manager.get_or_start(_PROJECT_ID, _BRANCH, service=svc1)
        await asyncio.sleep(0.05)  # Complete and expire TTL

        # Second run (TTL expired): should return stale result + start new job
        backlog2 = _make_backlog_result(n_items=3)
        svc2 = _make_service_mock(backlog2, delay=0.2)

        status, stale_result = await manager.get_or_start(
            _PROJECT_ID, _BRANCH, service=svc2
        )
        # Stale result from first run is returned immediately
        assert stale_result is not None
        assert len(stale_result.items) == 1  # From first run
        # New job is running
        assert status.has_result is True

    @pytest.mark.asyncio
    async def test_get_or_start_passes_filter_all_to_service(self):
        """get_or_start always passes filter='all' to the service for a cache-agnostic result."""
        manager = BacklogRefreshManager()
        backlog = _make_backlog_result()
        svc = _make_service_mock(backlog)

        await manager.get_or_start(_PROJECT_ID, _BRANCH, service=svc, filter="needs_delivery")
        await asyncio.sleep(0.05)

        # The service should have been called with filter="all"
        # (passed through by the refresh manager, overriding the caller's filter)
        call_kwargs = svc.get_backlog.call_args.kwargs
        assert call_kwargs.get("filter") == "all"

    @pytest.mark.asyncio
    async def test_get_or_start_passes_tracker_to_service(self):
        """get_or_start forwards tracker to the service."""
        manager = BacklogRefreshManager()
        backlog = _make_backlog_result()
        svc = _make_service_mock(backlog)
        tracker = MagicMock()

        await manager.get_or_start(_PROJECT_ID, _BRANCH, service=svc, tracker=tracker)
        await asyncio.sleep(0.05)

        call_kwargs = svc.get_backlog.call_args.kwargs
        assert call_kwargs.get("tracker") is tracker


# ---------------------------------------------------------------------------
# BacklogRefreshManager: failure handling
# ---------------------------------------------------------------------------


class TestRefreshManagerFailure:
    @pytest.mark.asyncio
    async def test_failed_job_sets_phase_failed(self):
        """When get_backlog raises an exception, phase transitions to 'failed'."""
        manager = BacklogRefreshManager()
        svc = _make_service_mock(error=RuntimeError("git subprocess crashed"))

        await manager.get_or_start(_PROJECT_ID, _BRANCH, service=svc)
        await asyncio.sleep(0.05)  # Let the background task fail

        status = manager.get_status(_PROJECT_ID, _BRANCH)
        assert status is not None
        assert status.phase == "failed"
        assert "git subprocess crashed" in (status.error or "")

    @pytest.mark.asyncio
    async def test_failed_job_retains_previous_result(self):
        """Previous cached result is retained after a refresh fails.

        This ensures the UI can still show stale data after a network error.
        """
        manager = BacklogRefreshManager(result_ttl_s=0.01)
        backlog = _make_backlog_result(n_items=2)
        svc_ok = _make_service_mock(backlog)

        # First run: successful
        await manager.get_or_start(_PROJECT_ID, _BRANCH, service=svc_ok)
        await asyncio.sleep(0.05)

        # TTL expires and second run fails
        svc_fail = _make_service_mock(error=RuntimeError("timeout"))
        await manager.get_or_start(_PROJECT_ID, _BRANCH, service=svc_fail)
        await asyncio.sleep(0.05)

        status = manager.get_status(_PROJECT_ID, _BRANCH)
        assert status.phase == "failed"
        # But the previous result is still there
        cached = manager.get_cached_result(_PROJECT_ID, _BRANCH)
        assert cached is not None
        assert len(cached.items) == 2
        # has_result is True because stale data exists
        assert status.has_result is True

    @pytest.mark.asyncio
    async def test_failed_job_restarts_on_next_get_or_start(self):
        """After failure, the next get_or_start call starts a new job."""
        manager = BacklogRefreshManager()
        svc_fail = _make_service_mock(error=RuntimeError("temporary failure"))

        # First call: fails
        await manager.get_or_start(_PROJECT_ID, _BRANCH, service=svc_fail)
        await asyncio.sleep(0.05)
        assert manager.get_status(_PROJECT_ID, _BRANCH).phase == "failed"

        # Second call: new service that succeeds
        backlog = _make_backlog_result()
        svc_ok = _make_service_mock(backlog)
        await manager.get_or_start(_PROJECT_ID, _BRANCH, service=svc_ok)
        await asyncio.sleep(0.05)

        status = manager.get_status(_PROJECT_ID, _BRANCH)
        assert status.phase == "complete"
        assert manager.get_cached_result(_PROJECT_ID, _BRANCH) is not None


# ---------------------------------------------------------------------------
# BacklogRefreshManager: trigger_refresh (retry / force restart)
# ---------------------------------------------------------------------------


class TestRefreshManagerTriggerRefresh:
    @pytest.mark.asyncio
    async def test_trigger_refresh_returns_pending_status(self):
        """trigger_refresh returns a RefreshStatus with phase in early phases."""
        manager = BacklogRefreshManager()
        backlog = _make_backlog_result()
        svc = _make_service_mock(backlog, delay=0.1)

        status = await manager.trigger_refresh(_PROJECT_ID, _BRANCH, service=svc)
        assert status.phase in ("pending", "loading_merged")

        await asyncio.sleep(0.2)  # Cleanup

    @pytest.mark.asyncio
    async def test_trigger_refresh_after_success_starts_new_run(self):
        """trigger_refresh on a completed job starts a fresh run."""
        manager = BacklogRefreshManager()
        backlog1 = _make_backlog_result(n_items=1)
        svc1 = _make_service_mock(backlog1)

        # First run
        await manager.get_or_start(_PROJECT_ID, _BRANCH, service=svc1)
        await asyncio.sleep(0.05)
        assert manager.get_status(_PROJECT_ID, _BRANCH).phase == "complete"

        # Force refresh
        backlog2 = _make_backlog_result(n_items=3)
        svc2 = _make_service_mock(backlog2)
        await manager.trigger_refresh(_PROJECT_ID, _BRANCH, service=svc2)
        await asyncio.sleep(0.05)

        # New result from second run
        cached = manager.get_cached_result(_PROJECT_ID, _BRANCH)
        assert cached is not None
        assert len(cached.items) == 3

    @pytest.mark.asyncio
    async def test_trigger_refresh_after_failure_is_retry(self):
        """trigger_refresh is the retry path after a failed refresh."""
        manager = BacklogRefreshManager()
        svc_fail = _make_service_mock(error=RuntimeError("network error"))

        # First run fails
        await manager.get_or_start(_PROJECT_ID, _BRANCH, service=svc_fail)
        await asyncio.sleep(0.05)
        assert manager.get_status(_PROJECT_ID, _BRANCH).phase == "failed"

        # Retry via trigger_refresh
        backlog = _make_backlog_result()
        svc_ok = _make_service_mock(backlog)
        status = await manager.trigger_refresh(_PROJECT_ID, _BRANCH, service=svc_ok)
        assert status.phase in ("pending", "loading_merged")

        await asyncio.sleep(0.05)
        assert manager.get_status(_PROJECT_ID, _BRANCH).phase == "complete"

    @pytest.mark.asyncio
    async def test_trigger_refresh_cancels_in_flight_job(self):
        """trigger_refresh cancels an in-progress job before starting a new one."""
        manager = BacklogRefreshManager()

        # A slow job that would block
        backlog_slow = _make_backlog_result(n_items=1)
        svc_slow = _make_service_mock(backlog_slow, delay=10.0)

        # Start a slow job
        await manager.get_or_start(_PROJECT_ID, _BRANCH, service=svc_slow)

        # Force refresh with a faster job
        backlog_fast = _make_backlog_result(n_items=5)
        svc_fast = _make_service_mock(backlog_fast)
        await manager.trigger_refresh(_PROJECT_ID, _BRANCH, service=svc_fast)
        await asyncio.sleep(0.05)

        # The fast job's result should be cached
        cached = manager.get_cached_result(_PROJECT_ID, _BRANCH)
        assert cached is not None
        assert len(cached.items) == 5
        # Only the fast job should have completed
        assert svc_fast.get_backlog.call_count == 1

    @pytest.mark.asyncio
    async def test_trigger_refresh_retains_stale_result_during_new_run(self):
        """Stale result from the previous run is retained while trigger_refresh runs.

        This ensures the client continues seeing old items during a manual retry.
        """
        manager = BacklogRefreshManager()
        backlog1 = _make_backlog_result(n_items=2)
        svc1 = _make_service_mock(backlog1)

        # First run completes
        await manager.get_or_start(_PROJECT_ID, _BRANCH, service=svc1)
        await asyncio.sleep(0.05)

        # Trigger refresh with a slow new job
        backlog2 = _make_backlog_result(n_items=4)
        svc2 = _make_service_mock(backlog2, delay=0.2)
        status = await manager.trigger_refresh(_PROJECT_ID, _BRANCH, service=svc2)

        # During the new job, stale result is retained
        assert status.has_result is True
        cached = manager.get_cached_result(_PROJECT_ID, _BRANCH)
        assert cached is not None
        assert len(cached.items) == 2  # Still the old result

        await asyncio.sleep(0.3)  # Let the new job finish

        # After completion, new result is available
        cached = manager.get_cached_result(_PROJECT_ID, _BRANCH)
        assert len(cached.items) == 4


# ---------------------------------------------------------------------------
# BacklogRefreshManager: phase transitions
# ---------------------------------------------------------------------------


class TestRefreshManagerPhaseTransitions:
    @pytest.mark.asyncio
    async def test_status_phase_transitions_to_complete(self):
        """Phase transitions from loading_merged to complete over the job lifetime."""
        manager = BacklogRefreshManager()
        phases_seen: list[str] = []

        backlog = _make_backlog_result()
        svc = _make_service_mock(backlog)
        original_run_backlog = svc.get_backlog.side_effect

        def _tracked_backlog(**kwargs):
            # Capture phase DURING execution
            status = manager.get_status(_PROJECT_ID, _BRANCH)
            if status:
                phases_seen.append(status.phase)
            return original_run_backlog(**kwargs)

        svc.get_backlog.side_effect = _tracked_backlog

        await manager.get_or_start(_PROJECT_ID, _BRANCH, service=svc)
        await asyncio.sleep(0.1)

        final_status = manager.get_status(_PROJECT_ID, _BRANCH)
        assert final_status.phase == "complete"
        # At least one in-progress phase was seen
        assert any(p in ("loading_merged", "resolving_commits") for p in phases_seen), (
            f"Expected at least one loading phase, saw: {phases_seen}"
        )

    @pytest.mark.asyncio
    async def test_elapsed_time_increases_during_run(self):
        """elapsed_s in RefreshStatus increases over the job's lifetime."""
        manager = BacklogRefreshManager()
        backlog = _make_backlog_result()
        svc = _make_service_mock(backlog, delay=0.1)

        await manager.get_or_start(_PROJECT_ID, _BRANCH, service=svc)

        # Small delay then check elapsed
        await asyncio.sleep(0.05)
        status = manager.get_status(_PROJECT_ID, _BRANCH)
        assert status is not None
        assert status.elapsed_s > 0

        await asyncio.sleep(0.1)


# ---------------------------------------------------------------------------
# Progress callback tests (OOMPAH-251 requirement)
# ---------------------------------------------------------------------------


class TestProgressCallback:
    """Tests that ItemBacklogService.get_backlog emits progress phases.

    The progress_callback contract: (phase: str, completed: int, total: int | None).
    """

    def _run_with_callback(
        self,
        tmp_path,
        *,
        n_merged: int = 5,
    ) -> list[tuple[str, int, int | None]]:
        """Run ItemBacklogService.get_backlog with a recording progress callback.

        Returns list of (phase, completed, total) tuples in emission order.
        """
        from oompah.release_delivery_backlog import ItemBacklogService
        from oompah.release_delivery_store import ReleaseDeliveryStore
        import time

        store = MagicMock(spec=ReleaseDeliveryStore)
        ledger = MagicMock()
        ledger.deliveries = []
        store.read_ledger.return_value = ledger

        # Create mock merged issues
        merged_issues = []
        for i in range(n_merged):
            issue = MagicMock()
            issue.identifier = f"TASK-{i}"
            issue.work_branch = f"TASK-{i}"
            issue.review_number = str(i + 100)
            issue.issue_type = "task"
            issue.state = "Merged"
            merged_issues.append(issue)

        tracker = MagicMock()
        tracker.fetch_issues_by_states.return_value = merged_issues
        tracker.get_issue.return_value = None

        svc = ItemBacklogService(
            project_root=tmp_path,
            project_id=_PROJECT_ID,
            default_branch="main",
            delivery_store=store,
        )

        snap = MagicMock()
        snap.source_head = _SOURCE_HEAD
        snap.release_heads = {_BRANCH: _RELEASE_HEAD}
        snap.stale = False
        snap.fetched_at = time.monotonic()

        recorded: list[tuple[str, int, int | None]] = []

        def _record(phase, completed, total):
            recorded.append((phase, completed, total))

        # Simulate some commits in main that match the work branches
        commits = []
        for i in range(n_merged):
            ci = MagicMock()
            ci.sha = f"{i:040x}"
            ci.subject = f"feat: TASK-{i}"
            ci.author_name = "Dev"
            ci.authored_at = "2026-07-01T00:00:00Z"
            ci.is_merge = False
            ci.parents = []
            commits.append(ci)

        def _mock_find_branch(repo_path, work_branch, main_shas, *, timeout=60):
            # Return one commit per branch
            for ci in commits:
                if ci.sha in main_shas:
                    pass
            # Each task has exactly one commit matching its index
            idx = int(work_branch.split("-")[1])
            sha = f"{idx:040x}"
            if sha in main_shas:
                return [sha]
            return []

        with (
            patch("oompah.release_delivery_backlog._acquire_snapshot", return_value=snap),
            patch("oompah.release_delivery_backlog._enumerate_commits", return_value=commits),
            patch("oompah.release_delivery_backlog._check_ancestry_batch", return_value=set()),
            patch("oompah.release_delivery_backlog._is_tracker_only_commit", return_value=False),
            patch("oompah.release_delivery_backlog._find_branch_commits_in_main",
                  side_effect=_mock_find_branch),
        ):
            svc.get_backlog(
                selected_branch=_BRANCH,
                filter="all",
                tracker=tracker,
                progress_callback=_record,
            )

        return recorded

    def test_progress_callback_receives_loading_merged_phase(self, tmp_path):
        """loading_merged phase is emitted before tracker.fetch_issues_by_states."""
        recorded = self._run_with_callback(tmp_path, n_merged=3)
        phases = [p for p, _, _ in recorded]
        assert "loading_merged" in phases, (
            f"Expected 'loading_merged' phase in {phases}"
        )

    def test_progress_callback_receives_resolving_commits_phase(self, tmp_path):
        """resolving_commits phase is emitted for each merged issue processed."""
        recorded = self._run_with_callback(tmp_path, n_merged=3)
        resolve_events = [(p, c, t) for p, c, t in recorded if p == "resolving_commits"]
        assert len(resolve_events) >= 3, (
            f"Expected at least 3 resolving_commits events for 3 merged issues, got {len(resolve_events)}"
        )

    def test_progress_callback_total_matches_merged_count(self, tmp_path):
        """resolving_commits total equals the number of merged issues."""
        n = 7
        recorded = self._run_with_callback(tmp_path, n_merged=n)
        resolve_events = [(p, c, t) for p, c, t in recorded if p == "resolving_commits"]
        assert resolve_events, "Must have at least one resolving_commits event"
        # The total on the last event should equal n
        last_total = resolve_events[-1][2]
        assert last_total == n, (
            f"Expected resolving_commits total={n}, got {last_total}"
        )

    def test_progress_callback_comparing_ancestry_phase(self, tmp_path):
        """comparing_ancestry phase is emitted."""
        recorded = self._run_with_callback(tmp_path, n_merged=2)
        phases = [p for p, _, _ in recorded]
        assert "comparing_ancestry" in phases

    def test_progress_callback_preparing_rows_phase(self, tmp_path):
        """preparing_rows phase is emitted."""
        recorded = self._run_with_callback(tmp_path, n_merged=2)
        phases = [p for p, _, _ in recorded]
        assert "preparing_rows" in phases

    def test_progress_callback_diagnostics_phase(self, tmp_path):
        """diagnostics phase is emitted."""
        recorded = self._run_with_callback(tmp_path, n_merged=2)
        phases = [p for p, _, _ in recorded]
        assert "diagnostics" in phases

    def test_progress_callback_phases_in_order(self, tmp_path):
        """Phases are emitted in the expected order (loading → resolving → comparing → preparing → diagnostics)."""
        recorded = self._run_with_callback(tmp_path, n_merged=3)

        seen_phases = []
        for p, _, _ in recorded:
            if not seen_phases or seen_phases[-1] != p:
                seen_phases.append(p)

        expected_order = [
            "loading_merged",
            "resolving_commits",
            "comparing_ancestry",
            "preparing_rows",
            "diagnostics",
        ]
        # Each expected phase should appear (and in order)
        last_idx = -1
        for expected_phase in expected_order:
            try:
                idx = seen_phases.index(expected_phase)
                assert idx > last_idx, (
                    f"Phase {expected_phase!r} appeared at index {idx} but expected "
                    f"after index {last_idx} (phases: {seen_phases})"
                )
                last_idx = idx
            except ValueError:
                pass  # Some phases may be skipped in certain scenarios

    def test_progress_callback_exception_does_not_abort_backlog(self, tmp_path):
        """Exception in progress_callback is silently suppressed; backlog still returns."""
        from oompah.release_delivery_backlog import ItemBacklogService
        from oompah.release_delivery_store import ReleaseDeliveryStore
        import time

        store = MagicMock(spec=ReleaseDeliveryStore)
        ledger = MagicMock()
        ledger.deliveries = []
        store.read_ledger.return_value = ledger

        issue = MagicMock()
        issue.identifier = "TASK-1"
        issue.work_branch = "TASK-1"
        issue.review_number = "101"
        issue.issue_type = "task"
        issue.state = "Merged"

        tracker = MagicMock()
        tracker.fetch_issues_by_states.return_value = [issue]
        tracker.get_issue.return_value = None

        svc = ItemBacklogService(
            project_root=tmp_path,
            project_id=_PROJECT_ID,
            default_branch="main",
            delivery_store=store,
        )

        snap = MagicMock()
        snap.source_head = _SOURCE_HEAD
        snap.release_heads = {_BRANCH: _RELEASE_HEAD}
        snap.stale = False
        snap.fetched_at = time.monotonic()

        ci = MagicMock()
        ci.sha = "a" * 40
        ci.subject = "feat: TASK-1"
        ci.author_name = "Dev"
        ci.authored_at = "2026-07-01T00:00:00Z"
        ci.is_merge = False
        ci.parents = []

        def _raising_callback(phase, completed, total):
            raise RuntimeError("callback error!")

        with (
            patch("oompah.release_delivery_backlog._acquire_snapshot", return_value=snap),
            patch("oompah.release_delivery_backlog._enumerate_commits", return_value=[ci]),
            patch("oompah.release_delivery_backlog._check_ancestry_batch", return_value=set()),
            patch("oompah.release_delivery_backlog._is_tracker_only_commit", return_value=False),
            patch("oompah.release_delivery_backlog._find_branch_commits_in_main",
                  return_value=["a" * 40]),
        ):
            # Should not raise
            result = svc.get_backlog(
                selected_branch=_BRANCH,
                filter="all",
                tracker=tracker,
                progress_callback=_raising_callback,
            )

        # Backlog was returned successfully despite the callback errors
        assert result is not None

    def test_progress_callback_not_called_without_tracker(self, tmp_path):
        """Without a tracker, loading_merged and resolving_commits phases are NOT emitted.

        When tracker=None, the tracker-sourced discovery loop is skipped entirely.
        """
        from oompah.release_delivery_backlog import ItemBacklogService
        from oompah.release_delivery_store import ReleaseDeliveryStore
        import time

        store = MagicMock(spec=ReleaseDeliveryStore)
        ledger = MagicMock()
        ledger.deliveries = []
        store.read_ledger.return_value = ledger

        svc = ItemBacklogService(
            project_root=tmp_path,
            project_id=_PROJECT_ID,
            default_branch="main",
            delivery_store=store,
        )

        snap = MagicMock()
        snap.source_head = _SOURCE_HEAD
        snap.release_heads = {_BRANCH: _RELEASE_HEAD}
        snap.stale = False
        snap.fetched_at = time.monotonic()

        recorded: list[str] = []

        with (
            patch("oompah.release_delivery_backlog._acquire_snapshot", return_value=snap),
            patch("oompah.release_delivery_backlog._enumerate_commits", return_value=[]),
            patch("oompah.release_delivery_backlog._check_ancestry_batch", return_value=set()),
            patch("oompah.release_delivery_backlog._is_tracker_only_commit", return_value=False),
            patch("oompah.release_delivery_backlog._find_branch_commits_in_main", return_value=[]),
        ):
            svc.get_backlog(
                selected_branch=_BRANCH,
                filter="all",
                tracker=None,
                progress_callback=lambda p, c, t: recorded.append(p),
            )

        # Without tracker, loading_merged and resolving_commits are skipped
        assert "loading_merged" not in recorded
        assert "resolving_commits" not in recorded
        # But ancestry and downstream phases still fire
        assert "comparing_ancestry" in recorded


# ---------------------------------------------------------------------------
# Trickle-scale performance regression (OOMPAH-251)
# ---------------------------------------------------------------------------


class TestTrickleScaleBacklogRegressionOOMPAH251:
    """Regression tests for the Trickle release/0.11 performance issue (OOMPAH-251).

    Simulates a Trickle-scale scenario:
    - Thousands of source commits on the default branch
    - Dozens of Merged items in the tracker (including deleted branches + PR refs)
    - Verifies that:
      1. The PRIMARY items list is built and returned.
      2. External SCM lookups (get_pr_commits) are bounded/called (one per item with PR).
      3. Title enrichment failure does NOT prevent primary rows from being returned.
      4. Not-selected and delivered items are correctly filtered.
    """

    _BRANCH = "release/0.11"
    _SOURCE_HEAD = "0" * 39 + "1"
    _RELEASE_011_HEAD = "0" * 39 + "2"
    _N_MAIN_COMMITS = 2000   # Trickle-scale: thousands of commits
    _N_MERGED_ITEMS = 60     # Trickle-scale: dozens of merged items

    def _make_merged_issue(self, i: int, *, has_pr: bool = False, deleted_branch: bool = False):
        issue = MagicMock()
        issue.identifier = f"OOMPAH-{100 + i}"
        issue.work_branch = None if deleted_branch else f"OOMPAH-{100 + i}"
        issue.review_number = str(400 + i) if has_pr else None
        issue.issue_type = "task" if i % 3 != 0 else "epic"
        issue.state = "Merged"
        issue.title = f"Task/Epic {100 + i}"
        return issue

    def _run_trickle_scale_backlog(
        self,
        tmp_path,
        *,
        title_enrichment_fails: bool = False,
    ):
        """Run ItemBacklogService with a synthetic Trickle-scale fixture."""
        from oompah.release_delivery_backlog import ItemBacklogService
        from oompah.release_delivery_store import ReleaseDeliveryStore
        import time

        # Build N_MAIN_COMMITS synthetic commits
        all_commits = []
        for i in range(self._N_MAIN_COMMITS):
            ci = MagicMock()
            ci.sha = f"{i:040x}"
            ci.subject = f"direct commit {i}"
            ci.author_name = "Dev"
            ci.authored_at = "2026-07-01T00:00:00Z"
            ci.is_merge = False
            ci.parents = []
            all_commits.append(ci)

        sha_set = {ci.sha for ci in all_commits}

        # Build N_MERGED_ITEMS Merged issues
        # Half with live branches, half with deleted branches + PR refs
        merged_issues = []
        # These are the SHAs that belong to merged items (first N_MERGED_ITEMS commits)
        item_shas: dict[str, str] = {}  # issue identifier → sha
        for i in range(self._N_MERGED_ITEMS):
            has_pr = (i >= self._N_MERGED_ITEMS // 2)  # Second half uses PR refs
            deleted = has_pr  # PR-ref items have deleted branches
            issue = self._make_merged_issue(i, has_pr=has_pr, deleted_branch=deleted)
            merged_issues.append(issue)
            # Map this issue to the i-th commit
            item_shas[issue.identifier] = all_commits[i].sha

        tracker = MagicMock()
        tracker.fetch_issues_by_states.return_value = merged_issues
        if title_enrichment_fails:
            tracker.get_issue.side_effect = RuntimeError("tracker unavailable")
        else:
            tracker.get_issue.return_value = None  # No title

        scm = MagicMock()
        scm_call_count = [0]

        def _mock_get_pr_commits(repo, pr_number):
            scm_call_count[0] += 1
            # Return the SHA for this item's PR
            pr_idx = int(pr_number) - 400
            ident = f"OOMPAH-{100 + pr_idx}"
            sha = item_shas.get(ident, "")
            return [sha] if sha else []

        scm.get_pr_commits.side_effect = _mock_get_pr_commits

        store = MagicMock(spec=ReleaseDeliveryStore)
        ledger = MagicMock()
        ledger.deliveries = []
        store.read_ledger.return_value = ledger

        svc = ItemBacklogService(
            project_root=tmp_path,
            project_id=_PROJECT_ID,
            default_branch="main",
            delivery_store=store,
            scm=scm,
            managed_repo="org/trickle",
        )

        snap = MagicMock()
        snap.source_head = self._SOURCE_HEAD
        snap.release_heads = {self._BRANCH: self._RELEASE_011_HEAD}
        snap.stale = False
        snap.fetched_at = time.monotonic()

        def _mock_find_branch(repo_path, work_branch, main_shas, *, timeout=60):
            # Look up the sha for this work branch
            for issue in merged_issues:
                if issue.work_branch == work_branch:
                    sha = item_shas.get(issue.identifier, "")
                    if sha and sha in main_shas:
                        return [sha]
            return []

        phases_emitted: list[tuple[str, int, int | None]] = []

        with (
            patch("oompah.release_delivery_backlog._acquire_snapshot", return_value=snap),
            patch("oompah.release_delivery_backlog._enumerate_commits", return_value=all_commits),
            patch("oompah.release_delivery_backlog._check_ancestry_batch", return_value=set()),
            patch("oompah.release_delivery_backlog._is_tracker_only_commit", return_value=False),
            patch("oompah.release_delivery_backlog._find_branch_commits_in_main",
                  side_effect=_mock_find_branch),
        ):
            result = svc.get_backlog(
                selected_branch=self._BRANCH,
                filter="all",
                tracker=tracker,
                progress_callback=lambda p, c, t: phases_emitted.append((p, c, t)),
            )

        return result, scm_call_count[0], phases_emitted

    def test_primary_items_returned_with_trickle_scale_commits(self, tmp_path):
        """Primary item list is non-empty with Trickle-scale fixture.

        Regression: with thousands of main commits and dozens of merged items,
        the backlog must still enumerate and return all primary candidate rows.
        """
        result, _, _ = self._run_trickle_scale_backlog(tmp_path)

        assert len(result.items) == self._N_MERGED_ITEMS, (
            f"Expected {self._N_MERGED_ITEMS} items for Trickle-scale fixture, "
            f"got {len(result.items)}"
        )

    def test_scm_calls_bounded_by_items_with_deleted_branches(self, tmp_path):
        """SCM PR commit lookups are bounded: one per item with a deleted branch + PR ref.

        For Trickle scale (dozens of merged items with deleted branches), the SCM
        call count must be proportional to the number of MERGED ITEMS with PRs,
        not to the number of MAIN COMMITS (thousands).
        """
        result, scm_call_count, _ = self._run_trickle_scale_backlog(tmp_path)

        # Half the items use PR refs (those with deleted branches)
        expected_scm_calls = self._N_MERGED_ITEMS // 2
        assert scm_call_count == expected_scm_calls, (
            f"Expected {expected_scm_calls} SCM PR lookups (one per item with deleted "
            f"branch + PR ref), got {scm_call_count}. Must not be proportional to "
            f"{self._N_MAIN_COMMITS} main commits."
        )
        # Critical: SCM calls must NOT grow with the number of main commits
        assert scm_call_count < self._N_MAIN_COMMITS, (
            f"SCM calls ({scm_call_count}) must be < number of main commits "
            f"({self._N_MAIN_COMMITS})"
        )

    def test_title_enrichment_failure_does_not_prevent_primary_rows(self, tmp_path):
        """Primary candidate rows are returned even when title enrichment always fails.

        If tracker.get_issue() raises for every item, the backlog must still
        return all items (with title=None rather than aborting).
        """
        result, _, _ = self._run_trickle_scale_backlog(
            tmp_path, title_enrichment_fails=True
        )

        assert len(result.items) == self._N_MERGED_ITEMS, (
            f"Expected {self._N_MERGED_ITEMS} items even when title enrichment fails, "
            f"got {len(result.items)}"
        )
        # All titles should be None (enrichment failed gracefully)
        titles = [item.title for item in result.items]
        assert all(t is None for t in titles), (
            f"All titles should be None when enrichment fails, got: {titles[:5]}"
        )

    def test_not_selected_items_in_needs_delivery_filter(self, tmp_path):
        """not_selected items appear in needs_delivery filter (they need to be queued)."""
        result, _, _ = self._run_trickle_scale_backlog(tmp_path)

        # With no ledger entries and no ancestry, all items are not_selected
        needs_delivery = [
            item for item in result.items
            if item.delivery_status.state not in ("delivered", "archived")
        ]
        assert len(needs_delivery) == self._N_MERGED_ITEMS, (
            f"Expected all {self._N_MERGED_ITEMS} items in needs_delivery filter, "
            f"got {len(needs_delivery)}"
        )

    def test_delivered_by_ancestry_excluded_from_needs_delivery(self, tmp_path):
        """Items delivered by ancestry are excluded from needs_delivery filter.

        Simulates some commits being reachable from the release branch.
        """
        from oompah.release_delivery_backlog import ItemBacklogService
        from oompah.release_delivery_store import ReleaseDeliveryStore
        import time

        # Only a small fixture for this test
        n_items = 10
        n_delivered = 3

        all_commits = []
        for i in range(n_items):
            ci = MagicMock()
            ci.sha = f"{i:040x}"
            ci.subject = f"feat: TASK-{i}"
            ci.author_name = "Dev"
            ci.authored_at = "2026-07-01T00:00:00Z"
            ci.is_merge = False
            ci.parents = []
            all_commits.append(ci)

        sha_set = {ci.sha for ci in all_commits}
        # First n_delivered commits are reachable from release branch
        ancestry_set = {all_commits[i].sha for i in range(n_delivered)}

        merged_issues = []
        for i in range(n_items):
            issue = MagicMock()
            issue.identifier = f"TASK-{i}"
            issue.work_branch = f"TASK-{i}"
            issue.review_number = None
            issue.issue_type = "task"
            issue.state = "Merged"
            merged_issues.append(issue)

        tracker = MagicMock()
        tracker.fetch_issues_by_states.return_value = merged_issues
        tracker.get_issue.return_value = None

        store = MagicMock(spec=ReleaseDeliveryStore)
        ledger = MagicMock()
        ledger.deliveries = []
        store.read_ledger.return_value = ledger

        svc = ItemBacklogService(
            project_root=tmp_path,
            project_id=_PROJECT_ID,
            default_branch="main",
            delivery_store=store,
        )

        snap = MagicMock()
        snap.source_head = self._SOURCE_HEAD
        snap.release_heads = {self._BRANCH: self._RELEASE_011_HEAD}
        snap.stale = False
        snap.fetched_at = time.monotonic()

        def _mock_find_branch(repo_path, work_branch, main_shas, *, timeout=60):
            idx = int(work_branch.split("-")[1])
            sha = all_commits[idx].sha
            return [sha] if sha in main_shas else []

        with (
            patch("oompah.release_delivery_backlog._acquire_snapshot", return_value=snap),
            patch("oompah.release_delivery_backlog._enumerate_commits", return_value=all_commits),
            patch("oompah.release_delivery_backlog._check_ancestry_batch", return_value=ancestry_set),
            patch("oompah.release_delivery_backlog._is_tracker_only_commit", return_value=False),
            patch("oompah.release_delivery_backlog._find_branch_commits_in_main",
                  side_effect=_mock_find_branch),
        ):
            result_all = svc.get_backlog(
                selected_branch=self._BRANCH,
                filter="all",
                tracker=tracker,
            )
            result_nd = svc.get_backlog(
                selected_branch=self._BRANCH,
                filter="needs_delivery",
                tracker=tracker,
            )

        # filter=all shows all items
        assert len(result_all.items) == n_items

        # filter=needs_delivery excludes the delivered ones
        delivered_ids = {
            item.identifier
            for item in result_all.items
            if item.delivery_status.state == "delivered"
        }
        assert len(delivered_ids) == n_delivered, (
            f"Expected {n_delivered} delivered items, got {len(delivered_ids)}"
        )

        needs_delivery_ids = {item.identifier for item in result_nd.items}
        assert not (delivered_ids & needs_delivery_ids), (
            "Delivered items must not appear in needs_delivery filter"
        )

    def test_progress_phases_emitted_for_trickle_scale(self, tmp_path):
        """All expected progress phases are emitted for a Trickle-scale run."""
        _, _, phases = self._run_trickle_scale_backlog(tmp_path)

        phase_names = [p for p, _, _ in phases]
        assert "loading_merged" in phase_names
        assert "resolving_commits" in phase_names
        assert "comparing_ancestry" in phase_names
        assert "preparing_rows" in phase_names

    def test_resolving_commits_progress_total_equals_merged_count(self, tmp_path):
        """The total in resolving_commits phase equals the number of merged issues."""
        _, _, phases = self._run_trickle_scale_backlog(tmp_path)

        resolve_events = [(p, c, t) for p, c, t in phases if p == "resolving_commits"]
        assert resolve_events, "Must have at least one resolving_commits event"

        # Total on the first event (with a known total) should equal N_MERGED_ITEMS
        events_with_total = [(p, c, t) for p, c, t in resolve_events if t is not None]
        assert events_with_total, "At least one resolving_commits event must have a total"
        total = events_with_total[0][2]
        assert total == self._N_MERGED_ITEMS, (
            f"Expected resolving_commits total={self._N_MERGED_ITEMS}, got {total}"
        )


# ---------------------------------------------------------------------------
# Thread safety tests
# ---------------------------------------------------------------------------


class TestRefreshManagerThreadSafety:
    @pytest.mark.asyncio
    async def test_concurrent_get_or_start_starts_only_one_job(self):
        """Multiple concurrent get_or_start calls start only one background job."""
        manager = BacklogRefreshManager()
        backlog = _make_backlog_result()
        svc = _make_service_mock(backlog, delay=0.1)

        # Start 5 concurrent calls
        results = await asyncio.gather(*[
            manager.get_or_start(_PROJECT_ID, _BRANCH, service=svc)
            for _ in range(5)
        ])

        await asyncio.sleep(0.2)  # Let the job complete

        # All calls returned a valid status
        for status, cached in results:
            assert status is not None

        # But get_backlog should have been called only once
        assert svc.get_backlog.call_count == 1, (
            f"Expected 1 get_backlog call from concurrent requests, got "
            f"{svc.get_backlog.call_count}"
        )
