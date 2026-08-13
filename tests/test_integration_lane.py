"""Shared-epic integration lane scheduling regressions (OOMPAH-875)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest import mock

from oompah.config import ServiceConfig
from oompah.integration import IntegrationRecord
from oompah.models import Issue
from oompah.orchestrator import DispatchEvent, DispatchEventType, Orchestrator
from tests.tick_test_support import tick_dispatch_mock


def _make_orchestrator(tmp_path) -> Orchestrator:
    return Orchestrator(
        config=ServiceConfig(
            parallel_epic_children_enabled=True,
            full_sync_interval_ms=600_000,
        ),
        workflow_path=str(tmp_path / "WORKFLOW.md"),
        project_store=mock.MagicMock(),
        state_path=str(tmp_path / "service-state.json"),
    )


def _close(orchestrator: Orchestrator) -> None:
    if orchestrator._integration_pool is not None:
        orchestrator._integration_pool.shutdown(wait=True, cancel_futures=True)
    orchestrator.integration_queue.close()
    orchestrator.coordination_store.close()
    orchestrator.review_capacity_store.close()
    orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
    orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)


def test_refresh_claim_runs_before_slow_dispatch_lane_finishes(tmp_path) -> None:
    """A Ready wakeup claims independently of an already-slow dispatch tick."""

    orchestrator = _make_orchestrator(tmp_path)
    calls = 0
    first_pass_complete = asyncio.Event()
    slow_dispatch_started = asyncio.Event()
    release_dispatch = asyncio.Event()
    claim_started = asyncio.Event()

    async def process_integration() -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            first_pass_complete.set()
            return
        claim_started.set()

    async def slow_dispatch() -> dict[str, float]:
        await first_pass_complete.wait()
        slow_dispatch_started.set()
        await release_dispatch.wait()
        return {}

    orchestrator._process_integration_queues = process_integration
    orchestrator._handle_reconcile = mock.AsyncMock()
    orchestrator._handle_review_check = mock.AsyncMock()
    orchestrator._handle_dispatch_needed = tick_dispatch_mock(on_call=slow_dispatch)
    orchestrator._handle_yolo_review = mock.AsyncMock(return_value=0.0)
    orchestrator._handle_auto_update = mock.AsyncMock()
    orchestrator._notify_observers = mock.MagicMock()
    orchestrator._maybe_run_watchdog = mock.MagicMock()
    orchestrator._recover_release_addendum_leases = mock.MagicMock(return_value=0)
    orchestrator._run_step5b_maintenance = mock.MagicMock()
    orchestrator._run_step5c_epic_maintenance = mock.MagicMock()
    orchestrator._schedule_terminal_lifecycle_reconciliation = mock.MagicMock()

    async def scenario() -> None:
        with mock.patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
            # Production ``run`` binds the scheduler loop before the first
            # tick; preserve that contract while exercising thread-safe wakes.
            orchestrator._dispatch_loop = asyncio.get_running_loop()
            tick = asyncio.create_task(orchestrator._tick())
            await asyncio.wait_for(slow_dispatch_started.wait(), timeout=1)

            # This mirrors a submission/cutover refresh arriving while an
            # unrelated dispatch or terminal-audit lane is still blocked.
            await asyncio.to_thread(orchestrator.request_refresh)
            await asyncio.wait_for(claim_started.wait(), timeout=1)
            assert not tick.done()

            release_dispatch.set()
            await tick
            assert orchestrator._integration_future is not None
            await orchestrator._integration_future

    try:
        asyncio.run(scenario())
        assert calls == 2
    finally:
        _close(orchestrator)


def test_startup_preexisting_ready_work_starts_one_integration_pass(tmp_path) -> None:
    """Restart starts exactly one independent shared-epic reconciliation pass."""

    orchestrator = _make_orchestrator(tmp_path)
    pass_started = asyncio.Event()
    calls = 0

    async def process_integration() -> None:
        nonlocal calls
        calls += 1
        pass_started.set()

    orchestrator._process_integration_queues = process_integration
    orchestrator._tick = mock.AsyncMock()
    orchestrator._run_terminal_audit_enforcement = mock.MagicMock()
    orchestrator.startup_cleanup = mock.AsyncMock()
    orchestrator._recover_restart_issues = mock.AsyncMock()
    orchestrator._restore_persisted_retries = mock.AsyncMock()

    async def scenario() -> None:
        async def stop_after_start() -> None:
            await asyncio.wait_for(pass_started.wait(), timeout=1)
            orchestrator._stopping = True
            orchestrator._post_event(
                DispatchEvent(event_type=DispatchEventType.SHUTDOWN)
            )

        await asyncio.gather(orchestrator.run(), stop_after_start())

    asyncio.run(scenario())
    assert calls == 1


def test_idle_integration_pass_does_not_self_rearm_dispatch_loop(tmp_path) -> None:
    """Startup and tick scans settle without manufacturing refreshes."""

    orchestrator = _make_orchestrator(tmp_path)
    orchestrator.project_store.list_all.return_value = []
    post_refresh = mock.MagicMock(wraps=orchestrator._post_dispatch_refresh)
    orchestrator._post_dispatch_refresh = post_refresh
    pass_count = 0
    tick_count = 0
    first_pass_complete = asyncio.Event()
    second_pass_complete = asyncio.Event()
    first_tick_complete = asyncio.Event()
    original_process = orchestrator._process_integration_queues

    async def record_process() -> None:
        nonlocal pass_count
        pass_count += 1
        await original_process()
        first_pass_complete.set()
        if pass_count >= 2:
            second_pass_complete.set()

    async def integration_probe_tick() -> None:
        nonlocal tick_count
        tick_count += 1
        orchestrator._ensure_integration_lane()
        first_tick_complete.set()

    orchestrator._process_integration_queues = record_process
    orchestrator._tick = integration_probe_tick
    orchestrator._run_terminal_audit_enforcement = mock.MagicMock()
    orchestrator.startup_cleanup = mock.AsyncMock()
    orchestrator._recover_restart_issues = mock.AsyncMock()
    orchestrator._restore_persisted_retries = mock.AsyncMock()

    async def scenario() -> tuple[int, int]:
        run = asyncio.create_task(orchestrator.run())
        await asyncio.wait_for(first_pass_complete.wait(), timeout=1)
        # OOMPAH-768 performs its duplicate-resolution startup fence before
        # the ordinary tick.  Observe that required tick explicitly rather
        # than assuming it always wins the race with the isolated lane.
        await asyncio.wait_for(first_tick_complete.wait(), timeout=1)
        # The tick intentionally schedules one scan in addition to the
        # independently started integration lane.  Once both authorized
        # passes settle, an idle lane must not create a third pass.
        await asyncio.wait_for(second_pass_complete.wait(), timeout=1)
        # Give a mistakenly self-posted REFRESH_REQUESTED event enough loop
        # turns to be dequeued and start another integration pass.
        for _ in range(10):
            await asyncio.sleep(0)
        observed = (pass_count, tick_count)

        orchestrator._stopping = True
        orchestrator._post_event(
            DispatchEvent(event_type=DispatchEventType.SHUTDOWN)
        )
        await asyncio.wait_for(run, timeout=1)
        return observed

    observed_passes, observed_ticks = asyncio.run(scenario())
    assert observed_passes == 2
    assert observed_ticks == 1
    post_refresh.assert_not_called()


def test_direct_epic_recovery_posts_refresh_without_worker_exit(tmp_path) -> None:
    """A recovered direct epic publication wakes ordinary reconciliation."""

    orchestrator = _make_orchestrator(tmp_path)
    project = mock.MagicMock(id="project-1", name="Test project")
    issue = mock.MagicMock(
        identifier="DIRECT-1",
        state="Ready to Integrate",
        integration=mock.MagicMock(state="ready"),
    )
    tracker = mock.MagicMock()
    tracker.fetch_all_issues.return_value = [issue]
    orchestrator.project_store.list_all.return_value = [project]
    orchestrator._project_trackers[project.id] = tracker
    orchestrator._sync_ready_integration_submissions = mock.MagicMock()
    orchestrator._retire_inactive_integration_rows = mock.MagicMock()
    orchestrator._audit_container_dependency_cycles = mock.MagicMock()
    orchestrator.complete_direct_epic_maintenance_submission = mock.AsyncMock(
        return_value=(True, "published and staged", mock.MagicMock())
    )
    post_refresh = mock.MagicMock()
    orchestrator._post_dispatch_refresh = post_refresh

    try:
        with mock.patch(
            "oompah.orchestrator.is_direct_epic_maintenance_issue",
            return_value=True,
        ):
            asyncio.run(orchestrator._process_integration_queues())

        orchestrator.complete_direct_epic_maintenance_submission.assert_awaited_once_with(
            issue,
            issue.integration,
            project.id,
        )
        post_refresh.assert_called_once_with()
    finally:
        _close(orchestrator)


def test_direct_epic_recovery_repairs_audited_done_with_stale_ready_record(
    tmp_path,
) -> None:
    """A PASS that raced old classification still re-enters direct recovery."""

    orchestrator = _make_orchestrator(tmp_path)
    project = SimpleNamespace(id="proj-1", name="test")
    helper = Issue(
        id="REBASE-1",
        identifier="REBASE-1",
        title="Rebase epic-EPIC-1 onto main",
        state="Done",
        parent_id="EPIC-1",
        project_id=None,
        integration=IntegrationRecord(
            state="ready",
            mode="queue",
            task_branch="epic-EPIC-1",
            base_branch="main",
            head_sha="a" * 40,
        ),
    )
    tracker = mock.MagicMock()
    tracker.fetch_all_issues.return_value = [helper]
    orchestrator.project_store.list_all.return_value = [project]
    orchestrator._tracker_for_project = mock.MagicMock(return_value=tracker)
    orchestrator.complete_direct_epic_maintenance_submission = mock.AsyncMock(
        return_value=(True, "recovered", helper.integration)
    )
    orchestrator._sync_ready_integration_submissions = mock.MagicMock()
    orchestrator._reconcile_terminal_parent_integration_rows = mock.MagicMock()
    orchestrator._retire_inactive_integration_rows = mock.MagicMock()
    orchestrator._audit_container_dependency_cycles = mock.MagicMock(return_value=[])
    orchestrator.integration_queue.items = mock.MagicMock(return_value=[])

    try:
        asyncio.run(orchestrator._process_integration_queues())

        (
            orchestrator.complete_direct_epic_maintenance_submission
            .assert_awaited_once_with(helper, helper.integration, project.id)
        )
        assert helper.project_id == project.id
    finally:
        _close(orchestrator)


def test_direct_epic_recovery_repairs_stale_label_after_integrated_checkpoint(
    tmp_path,
) -> None:
    """A crash after integration persistence still re-enters label repair."""

    orchestrator = _make_orchestrator(tmp_path)
    project = SimpleNamespace(id="proj-1", name="test")
    helper = Issue(
        id="REBASE-1",
        identifier="REBASE-1",
        title="Rebase epic-EPIC-1 onto main",
        state="Done",
        parent_id="EPIC-1",
        project_id="proj-1",
        work_branch="epic-EPIC-1",
        head_sha="a" * 40,
        integration=IntegrationRecord(
            state="integrated",
            mode="queue",
            task_branch="epic-EPIC-1",
            base_branch="epic-EPIC-1",
            head_sha="a" * 40,
            integrated_sha="a" * 40,
            maintenance_publication_proven=True,
        ),
    )
    parent = Issue(
        id="EPIC-1",
        identifier="EPIC-1",
        title="parent",
        state="Open",
        labels=["epic:rebasing"],
        project_id="proj-1",
    )
    tracker = mock.MagicMock()
    tracker.fetch_all_issues.return_value = [helper]
    orchestrator.project_store.list_all.return_value = [project]
    orchestrator._tracker_for_project = mock.MagicMock(return_value=tracker)
    orchestrator._resolve_parent_epic = mock.MagicMock(return_value=parent)
    orchestrator.complete_direct_epic_maintenance_submission = mock.AsyncMock(
        return_value=(True, "recovered labels", helper.integration)
    )
    orchestrator._sync_ready_integration_submissions = mock.MagicMock()
    orchestrator._reconcile_terminal_parent_integration_rows = mock.MagicMock()
    orchestrator._retire_inactive_integration_rows = mock.MagicMock()
    orchestrator._audit_container_dependency_cycles = mock.MagicMock(return_value=[])
    orchestrator.integration_queue.items = mock.MagicMock(return_value=[])

    try:
        asyncio.run(orchestrator._process_integration_queues())

        (
            orchestrator.complete_direct_epic_maintenance_submission
            .assert_awaited_once_with(helper, helper.integration, project.id)
        )
    finally:
        _close(orchestrator)


def test_concurrent_refreshes_coalesce_to_one_followup_integration_pass(tmp_path) -> None:
    """Refresh bursts preserve one active owner and never double-claim."""

    orchestrator = _make_orchestrator(tmp_path)
    calls = 0
    first_pass_started = asyncio.Event()
    release_first_pass = asyncio.Event()

    async def process_integration() -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            first_pass_started.set()
            await release_first_pass.wait()

    orchestrator._process_integration_queues = process_integration

    async def scenario() -> None:
        orchestrator._dispatch_loop = asyncio.get_running_loop()
        assert orchestrator._ensure_integration_lane() is True
        await asyncio.wait_for(first_pass_started.wait(), timeout=1)

        for _ in range(8):
            orchestrator.request_refresh()
        release_first_pass.set()

        assert orchestrator._integration_future is not None
        await orchestrator._integration_future

    try:
        asyncio.run(scenario())
        assert calls == 2
    finally:
        _close(orchestrator)


def test_lane_progress_exposes_run_and_claim_latency(tmp_path) -> None:
    """State exposes the independent lane's latest run and claim delay."""

    orchestrator = _make_orchestrator(tmp_path)
    try:
        orchestrator._record_integration_queue_progress(
            queue_items=[],
            eligible_ready_count=0,
            oldest_eligible_submitted_at=None,
            claimed_count=1,
            audit_progress={"batch_size": 32, "replayed": 0},
            run_started_at="2026-08-07T08:33:01+00:00",
            run_duration_ms=125.25,
            last_claim_latency_seconds=2.75,
        )

        progress = orchestrator.get_snapshot()["maintenance"]["integration_queue"]
        assert progress["last_run_started_at"] == "2026-08-07T08:33:01+00:00"
        assert progress["last_run_duration_ms"] == 125.2
        assert progress["last_claim_latency_seconds"] == 2.8
    finally:
        _close(orchestrator)


def test_shutdown_drains_slow_integration_audit_future(tmp_path) -> None:
    """Lifecycle shutdown retains ownership until durable audit replay exits."""

    orchestrator = _make_orchestrator(tmp_path)
    audit_started = asyncio.Event()
    release_audit = asyncio.Event()

    async def slow_audit_replay(**_kwargs):
        audit_started.set()
        await release_audit.wait()
        return {
            "batch_size": 32,
            "replayed": 1,
            "deferred": False,
            "cursor": None,
            "error": None,
        }

    orchestrator._replay_integrated_audit_batch = slow_audit_replay
    orchestrator._process_integration_queues = mock.AsyncMock()
    orchestrator._tick = mock.AsyncMock()
    orchestrator._run_terminal_audit_enforcement = mock.MagicMock(
        side_effect=lambda: setattr(orchestrator, "_terminal_audit_started", True)
    )
    orchestrator.startup_cleanup = mock.AsyncMock()
    orchestrator._recover_restart_issues = mock.AsyncMock()
    orchestrator._restore_persisted_retries = mock.AsyncMock()

    async def scenario() -> None:
        run = asyncio.create_task(orchestrator.run())
        await asyncio.wait_for(audit_started.wait(), timeout=1)

        orchestrator._stopping = True
        orchestrator._post_event(
            DispatchEvent(event_type=DispatchEventType.SHUTDOWN)
        )
        await asyncio.sleep(0)
        assert not run.done()

        release_audit.set()
        await asyncio.wait_for(run, timeout=1)

    asyncio.run(scenario())


def test_integration_audit_wakes_coalesce_to_one_followup_pass(tmp_path) -> None:
    """Durable audit wake bursts retain one owner and one pending replay."""

    orchestrator = _make_orchestrator(tmp_path)
    first_replay_started = asyncio.Event()
    release_first_replay = asyncio.Event()
    calls = 0

    async def replay(**_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            first_replay_started.set()
            await release_first_replay.wait()
        return {
            "batch_size": 32,
            "replayed": 1,
            "deferred": False,
            "cursor": None,
            "error": None,
        }

    orchestrator._replay_integrated_audit_batch = replay
    orchestrator._terminal_audit_started = True

    async def scenario() -> None:
        assert orchestrator._ensure_integration_audit_lane() is True
        await asyncio.wait_for(first_replay_started.wait(), timeout=1)

        for _ in range(8):
            assert (
                orchestrator._ensure_integration_audit_lane(
                    recheck_active=True
                )
                is False
            )
        release_first_replay.set()

        assert orchestrator._integration_audit_future is not None
        await asyncio.wait_for(orchestrator._integration_audit_future, timeout=1)

    try:
        asyncio.run(scenario())
        assert calls == 2
    finally:
        _close(orchestrator)
