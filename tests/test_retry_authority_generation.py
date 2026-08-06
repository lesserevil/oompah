"""Deterministic authority fences for implementation retries (OOMPAH-661)."""

from __future__ import annotations

import asyncio
import threading
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oompah.config import ServiceConfig
from oompah.focus import BUILTIN_FOCI, select_focus
from oompah.integration import IntegrationRecord
from oompah.models import Issue, RetryEntry, RunningEntry
from oompah.orchestrator import DispatchAuthorityRevoked, Orchestrator
from oompah.server import _cancel_retry_for_authority_change


_OWNED_ORCHESTRATORS: list[
    tuple[
        Orchestrator,
        tuple[tuple[str, Any], ...],
        tuple[tuple[str, Any], ...],
    ]
] = []


async def _terminate_owned_orchestrators(
    owned: list[
        tuple[
            Orchestrator,
            tuple[tuple[str, Any], ...],
            tuple[tuple[str, Any], ...],
        ]
    ],
    cleanup_errors: list[str],
) -> None:
    """Retire runtimes before their pools are joined and stores are closed."""

    for owner_index, (orch, _pools, _stores) in enumerate(
        reversed(owned), start=1
    ):
        orch._termination_scheduling_closed = True
        for retry in list(orch.state.retry_attempts.values()):
            timer = retry.timer_handle
            if timer is not None and not timer.cancelled():
                timer.cancel()
        try:
            await orch._drain_scheduled_terminations()
        except Exception as exc:  # noqa: BLE001 - retire every orchestrator
            cleanup_errors.append(
                f"orchestrator {owner_index} termination drain failed: {exc!r}"
            )
        for issue_id, _entry in orch._running_items_snapshot():
            try:
                await orch._terminate_running(issue_id, cleanup_workspace=False)
            except Exception as exc:  # noqa: BLE001 - retire every runtime
                cleanup_errors.append(
                    f"orchestrator {owner_index} runtime {issue_id} termination "
                    f"failed: {exc!r}"
                )
        try:
            await orch._drain_scheduled_terminations()
        except Exception as exc:  # noqa: BLE001 - continue resource cleanup
            cleanup_errors.append(
                f"orchestrator {owner_index} final termination drain failed: {exc!r}"
            )
        remaining = [issue_id for issue_id, _entry in orch._running_items_snapshot()]
        if remaining:
            cleanup_errors.append(
                f"orchestrator {owner_index} retained running entries: "
                + ", ".join(sorted(remaining))
            )


def _close_owned_orchestrator_resources(
    owned: list[
        tuple[
            Orchestrator,
            tuple[tuple[str, Any], ...],
            tuple[tuple[str, Any], ...],
        ]
    ],
    cleanup_errors: list[str],
) -> None:
    """Join all submitted telemetry work and close every owned store."""

    for owner_index, (_orch, pools, stores) in enumerate(reversed(owned), start=1):
        for resource_name, pool in pools:
            try:
                pool.shutdown(wait=True, cancel_futures=False)
            except Exception as exc:  # noqa: BLE001 - close every resource
                cleanup_errors.append(
                    f"orchestrator {owner_index} {resource_name} shutdown "
                    f"failed: {exc!r}"
                )
            live_threads = [
                thread.name
                for thread in getattr(pool, "_threads", ())
                if thread.is_alive()
            ]
            if live_threads:
                cleanup_errors.append(
                    f"orchestrator {owner_index} {resource_name} retained live "
                    f"threads: {', '.join(live_threads)}"
                )
        for resource_name, store in stores:
            try:
                store.close()
            except Exception as exc:  # noqa: BLE001 - close every resource
                cleanup_errors.append(
                    f"orchestrator {owner_index} {resource_name} close "
                    f"failed: {exc!r}"
                )


def _close_owned_event_loop(
    loop: asyncio.AbstractEventLoop,
    cleanup_errors: list[str],
) -> None:
    """Cancel loop work, join the default executor, and close the loop."""

    pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
    if pending:
        for task in pending:
            task.cancel()
        try:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception as exc:  # noqa: BLE001 - continue loop cleanup
            cleanup_errors.append(f"pending task drain failed: {exc!r}")
        cleanup_errors.append(
            "event loop retained pending tasks: "
            + ", ".join(sorted(task.get_name() for task in pending))
        )

    live_timers = [
        handle
        for handle in getattr(loop, "_scheduled", ())
        if not handle.cancelled()
    ]
    for handle in live_timers:
        handle.cancel()
    if live_timers:
        cleanup_errors.append(
            f"event loop retained {len(live_timers)} scheduled timer(s)"
        )

    try:
        loop.run_until_complete(loop.shutdown_asyncgens())
    except Exception as exc:  # noqa: BLE001 - continue executor cleanup
        cleanup_errors.append(f"async-generator shutdown failed: {exc!r}")
    executor = getattr(loop, "_default_executor", None)
    try:
        loop.run_until_complete(loop.shutdown_default_executor())
    except Exception as exc:  # noqa: BLE001 - loop close must still run
        cleanup_errors.append(f"default-executor shutdown failed: {exc!r}")
    if executor is not None:
        live_threads = [
            thread.name
            for thread in getattr(executor, "_threads", ())
            if thread.is_alive()
        ]
        if live_threads:
            cleanup_errors.append(
                "default executor retained live threads: "
                + ", ".join(live_threads)
            )
    loop.close()
    asyncio.set_event_loop(None)


@pytest.fixture(autouse=True)
def _owned_event_loop():
    """Give synchronous retry scheduling one loop with strict teardown."""

    first_owned = len(_OWNED_ORCHESTRATORS)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        yield loop
    finally:
        owned = _OWNED_ORCHESTRATORS[first_owned:]
        del _OWNED_ORCHESTRATORS[first_owned:]
        cleanup_errors: list[str] = []
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                _terminate_owned_orchestrators(owned, cleanup_errors)
            )
        except Exception as exc:  # noqa: BLE001 - continue resource cleanup
            cleanup_errors.append(f"orchestrator cleanup failed: {exc!r}")
        _close_owned_orchestrator_resources(owned, cleanup_errors)
        _close_owned_event_loop(loop, cleanup_errors)
        if cleanup_errors:
            pytest.fail("owned test resource leakage: " + "; ".join(cleanup_errors))


def _issue(
    *,
    issue_id: str = "task-1",
    identifier: str = "TASK-1",
    project_id: str = "project-a",
    state: str = "In Progress",
    updated_at: str | None = "2026-07-31T12:00:00+00:00",
    head_sha: str | None = "a" * 40,
    work_branch: str = "task/TASK-1",
    assignment_id: str | None = "assignment-1",
) -> Issue:
    return Issue(
        id=issue_id,
        identifier=identifier,
        title="Retry authority test",
        state=state,
        project_id=project_id,
        assignment_id=assignment_id,
        work_branch=work_branch,
        updated_at=(
            datetime.fromisoformat(updated_at) if updated_at is not None else None
        ),
        integration=(
            IntegrationRecord(state="ready", head_sha=head_sha)
            if head_sha
            else None
        ),
    )


def _orchestrator(tmp_path) -> Orchestrator:
    orch = Orchestrator(
        config=ServiceConfig(),
        workflow_path="WORKFLOW.md",
        state_path=str(tmp_path / "service-state.json"),
    )
    stores = tuple(
        (name, store)
        for name in (
            "coordination_store",
            "integration_queue",
            "review_capacity_store",
            "workflow_job_store",
            "task_transition_journal",
        )
        if (store := getattr(orch, name, None)) is not None
    )
    _OWNED_ORCHESTRATORS.append(
        (
            orch,
            (
                ("_tick_pool", orch._tick_pool),
                ("_refresh_pool", orch._refresh_pool),
            ),
            stores,
        )
    )
    return orch


def _schedule(orch: Orchestrator, issue: Issue, *, attempt: int = 1) -> RetryEntry:
    entry = RunningEntry(
        worker_task=None,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=attempt - 1,
        started_at=datetime.now(timezone.utc),
        assignment_id="assignment-1",
        workspace_path=None,
    )
    orch._schedule_retry(
        issue.id,
        attempt=attempt,
        identifier=issue.identifier,
        delay_ms=60_000,
        error="old divergence error",
        project_id=issue.project_id,
        context_entry=entry,
    )
    return orch.state.retry_attempts[issue.id]


def test_authority_guarded_setup_mutation_rejects_revoked_generation(tmp_path):
    orch = _orchestrator(tmp_path)
    mutated: list[str] = []

    with pytest.raises(DispatchAuthorityRevoked):
        orch._authority_guarded_call(
            lambda: False,
            mutated.append,
            "stale setup",
        )

    assert mutated == []


def test_submission_authority_cancellation_is_immediate_and_history_remains(
    tmp_path,
):
    orch = _orchestrator(tmp_path)
    issue = _issue()
    retry = _schedule(orch, issue)

    assert orch.get_snapshot()["counts"]["retrying"] == 1
    orch._cancel_retry_for_issue(
        issue_id=issue.id,
        identifier=issue.identifier,
        project_id=issue.project_id,
        reason="task submitted for integration",
    )

    assert retry.cancelled is True
    assert orch.state.retry_attempts == {}
    snapshot = orch.get_snapshot()
    assert snapshot["counts"]["retrying"] == 0
    assert snapshot["retrying"] == []
    # Cancellation only withdraws live authority; the failure text remains
    # available to the caller that already recorded it in task history.
    assert retry.error == "old divergence error"


def test_submission_cancellation_clears_claim_placeholder(tmp_path):
    orch = _orchestrator(tmp_path)
    issue = _issue()
    retry = _schedule(orch, issue)
    orch.state.claimed.add(issue.id)
    orch.state.claimed_issues[issue.id] = issue

    orch._cancel_retry_for_issue(
        issue_id=issue.id,
        identifier=issue.identifier,
        project_id=issue.project_id,
        reason="task submitted for integration",
    )

    assert retry.cancelled is True
    assert issue.id not in orch.state.claimed
    assert issue.id not in orch.state.claimed_issues


def test_revoked_running_submission_is_quarantined_without_retry(tmp_path):
    async def scenario():
        orch = _orchestrator(tmp_path)
        issue = _issue()
        worker = asyncio.create_task(asyncio.sleep(60))
        entry = RunningEntry(
            worker_task=worker,
            identifier=issue.identifier,
            issue=issue,
            session=None,
            retry_attempt=1,
            started_at=datetime.now(timezone.utc),
            assignment_id="assignment-1",
            authority_generation="generation-running",
        )
        orch.state.running[issue.id] = entry
        orch.state.claimed.add(issue.id)
        orch.state.claimed_issues[issue.id] = issue

        orch._cancel_retry_for_issue(
            issue_id=issue.id,
            identifier=issue.identifier,
            project_id=issue.project_id,
            reason="task submitted for integration",
        )
        for _ in range(20):
            await asyncio.sleep(0)
            if issue.id not in orch.state.running:
                break

        await orch._drain_scheduled_terminations()
        assert entry.authority_revoked is True
        assert issue.id not in orch.state.running
        assert issue.id not in orch.state.claimed
        assert issue.id not in orch.state.claimed_issues
        assert worker.done()
        assert orch._scheduled_termination_tasks == {}
        assert not any(
            task.get_name() == f"quarantine-worker-{issue.id}"
            for task in asyncio.all_tasks()
            if task is not asyncio.current_task()
        )

    asyncio.run(scenario())


def test_stop_fences_cross_thread_termination_scheduling_and_drains_owner_task(
    tmp_path,
):
    async def scenario():
        orch = _orchestrator(tmp_path)
        issue = _issue()
        worker = asyncio.create_task(asyncio.sleep(60))
        entry = RunningEntry(
            worker_task=worker,
            identifier=issue.identifier,
            issue=issue,
            session=None,
            retry_attempt=1,
            started_at=datetime.now(timezone.utc),
            assignment_id="assignment-1",
            authority_generation="generation-running",
        )
        orch.state.running[issue.id] = entry
        orch._dispatch_loop = asyncio.get_running_loop()
        termination_started = asyncio.Event()
        allow_termination = asyncio.Event()

        async def terminate(issue_id, cleanup_workspace=False):
            assert issue_id == issue.id
            assert cleanup_workspace is False
            termination_started.set()
            await allow_termination.wait()
            orch.state.running.pop(issue_id, None)
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)
            return True

        orch._terminate_running = AsyncMock(side_effect=terminate)

        # Exercise the production call_soon_threadsafe path.  The retirement
        # remains in flight so stop() must observe and drain it.
        await asyncio.to_thread(
            orch._schedule_running_termination,
            issue.id,
            task_name_prefix="quarantine-worker",
        )
        await termination_started.wait()
        stop_task = asyncio.create_task(orch.stop())
        await asyncio.sleep(0)
        assert not stop_task.done()

        allow_termination.set()
        await stop_task
        assert orch._terminate_running.await_count == 1
        assert orch._scheduled_termination_tasks == {}
        assert not any(
            task.get_name() == f"quarantine-worker-{issue.id}"
            for task in asyncio.all_tasks()
            if task is not asyncio.current_task()
        )

        # A foreign callback arriving after the shutdown admission gate closes
        # must not create a new untracked task during loop teardown.
        orch.state.running[issue.id] = entry
        await asyncio.to_thread(
            orch._schedule_running_termination,
            issue.id,
            task_name_prefix="late-quarantine-worker",
        )
        await asyncio.sleep(0)
        assert orch._terminate_running.await_count == 1
        assert orch._scheduled_termination_tasks == {}
        orch.state.running.pop(issue.id, None)

    asyncio.run(scenario())


def test_stop_rejects_callback_queued_before_empty_termination_drain(tmp_path):
    async def scenario():
        orch = _orchestrator(tmp_path)
        issue = _issue()
        worker = asyncio.create_task(asyncio.sleep(60))
        entry = RunningEntry(
            worker_task=worker,
            identifier=issue.identifier,
            issue=issue,
            session=None,
            retry_attempt=1,
            started_at=datetime.now(timezone.utc),
            assignment_id="assignment-1",
            authority_generation="generation-running",
        )
        orch.state.running[issue.id] = entry
        queued_callbacks = []

        def hold_callback(callback, *args):
            queued_callbacks.append((callback, args))

        owner_loop = MagicMock()
        owner_loop.is_running.return_value = True
        owner_loop.call_soon_threadsafe.side_effect = hold_callback
        orch._dispatch_loop = owner_loop
        orch._terminate_running = AsyncMock(return_value=True)

        # Hold the foreign-thread callback until stop() has closed admission
        # and drained the still-empty scheduled-task map.
        await asyncio.to_thread(
            orch._schedule_running_termination,
            issue.id,
            task_name_prefix="quarantine-worker",
        )
        assert len(queued_callbacks) == 1
        held_termination_callback, held_termination_args = queued_callbacks[0]
        assert orch._scheduled_termination_tasks == {}

        await orch.stop()
        assert orch._terminate_running.await_count == 1
        held_termination_callback(*held_termination_args)
        await asyncio.sleep(0)

        assert orch._terminate_running.await_count == 1
        assert orch._scheduled_termination_tasks == {}
        assert not any(
            task.get_name() == f"quarantine-worker-{issue.id}"
            for task in asyncio.all_tasks()
            if task is not asyncio.current_task()
        )
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)
        orch.state.running.pop(issue.id, None)

    asyncio.run(scenario())


def test_dispatch_setup_cancelled_before_status_write(tmp_path):
    async def scenario():
        orch = _orchestrator(tmp_path)
        issue = _issue()
        tracker = MagicMock()
        tracker.fetch_issue_states_by_ids.return_value = [issue]
        orch._tracker_for_issue = MagicMock(return_value=tracker)
        profile = MagicMock(name="default")
        profile.name = "default"
        orch._match_agent_profile = MagicMock(return_value=profile)
        orch._run_worker = AsyncMock()
        retry = _schedule(orch, issue)
        orch._retry_dispatching[issue.id] = retry
        await orch.issue_transition_lock(issue.id).acquire()
        dispatch = asyncio.create_task(
            orch._dispatch(issue, attempt=retry.attempt, retry_entry=retry)
        )
        for _ in range(20):
            await asyncio.sleep(0)
            if issue.id in orch.state.claimed:
                break
        orch._cancel_retry_for_issue(
            issue_id=issue.id,
            identifier=issue.identifier,
            project_id=issue.project_id,
            reason="task submitted for integration",
        )
        orch.issue_transition_lock(issue.id).release()
        await dispatch

        tracker.update_issue.assert_not_called()
        orch._run_worker.assert_not_awaited()
        assert issue.id not in orch.state.claimed
        assert issue.id not in orch.state.claimed_issues

    asyncio.run(scenario())


def test_status_change_cancels_only_matching_project_and_task(tmp_path):
    orch = _orchestrator(tmp_path)
    first = _issue()
    second = _issue(
        issue_id="task-2",
        identifier="TASK-2",
        project_id="project-b",
        work_branch="task/TASK-2",
        head_sha="b" * 40,
    )
    first_retry = _schedule(orch, first)
    second_retry = _schedule(orch, second)

    orch._cancel_retry_for_issue(
        identifier=first.identifier,
        project_id=first.project_id,
        reason="status changed to Backlog",
    )

    assert first_retry.cancelled is True
    assert first.id not in orch.state.retry_attempts
    assert second.id in orch.state.retry_attempts
    assert second_retry.cancelled is False


@pytest.mark.parametrize("new_status", ["Backlog", "Open", "Needs Human", "Done"])
def test_every_operator_status_change_withdraws_retry_authority(tmp_path, new_status):
    orch = _orchestrator(tmp_path)
    issue = _issue()
    retry = _schedule(orch, issue)

    _cancel_retry_for_authority_change(
        orch,
        issue,
        issue.identifier,
        issue.project_id,
        new_status,
        None,
    )

    assert retry.cancelled is True
    assert issue.id not in orch.state.retry_attempts


def test_replacement_head_cannot_inherit_failed_retry_generation(tmp_path):
    orch = _orchestrator(tmp_path)
    original = _issue()
    retry = _schedule(orch, original)
    replacement = _issue(head_sha="b" * 40)

    assert retry.authority_generation
    assert orch._retry_entry_matches_issue(replacement, retry) is False


def test_replacement_assignment_cannot_inherit_failed_retry_generation(tmp_path):
    orch = _orchestrator(tmp_path)
    retry = _schedule(orch, _issue())

    assert orch._retry_entry_matches_issue(
        _issue(assignment_id="assignment-2"), retry
    ) is False


def test_replacement_attempt_cannot_inherit_failed_retry_generation(tmp_path):
    orch = _orchestrator(tmp_path)
    retry = _schedule(orch, _issue())
    replacement = _issue()
    replacement.retry_attempt = 1

    assert orch._retry_entry_matches_issue(replacement, retry) is False


def test_exact_generation_tampering_is_rejected(tmp_path):
    orch = _orchestrator(tmp_path)
    retry = _schedule(orch, _issue())
    retry.authority_generation = "tampered-generation"

    assert orch._retry_entry_matches_issue(_issue(), retry) is False


@pytest.mark.parametrize("source_state", ["Open", "In Progress"])
def test_retry_authorizes_its_own_in_progress_write(tmp_path, source_state):
    async def scenario():
        orch = _orchestrator(tmp_path)
        issue = _issue(state=source_state)
        retry = _schedule(orch, issue)
        orch._retry_dispatching[issue.id] = retry
        orch._match_agent_profile = MagicMock(
            return_value=MagicMock(name="default", model_role="fast")
        )
        orch._run_worker = AsyncMock()
        tracker_state = {"state": source_state}
        tracker = MagicMock()

        def fetch(_issue_ids):
            return [replace(issue, state=tracker_state["state"])]

        def update(_identifier, *, status):
            tracker_state["state"] = status

        tracker.fetch_issue_states_by_ids.side_effect = fetch
        tracker.update_issue.side_effect = update
        orch._tracker_for_issue = MagicMock(return_value=tracker)

        await orch._dispatch(issue, attempt=retry.attempt, retry_entry=retry)
        await asyncio.sleep(0)

        assert tracker_state["state"] == "In Progress"
        assert tracker.update_issue.call_args_list == [
            ((issue.identifier,), {"status": "In Progress"})
        ]
        orch._run_worker.assert_awaited_once()
        assert issue.id in orch.state.running
        assert retry.cancelled is True
        assert issue.id not in orch.state.retry_attempts

        running = orch.state.running.pop(issue.id)
        if running.worker_task is not None and not running.worker_task.done():
            running.worker_task.cancel()

    asyncio.run(scenario())


def test_ci_repair_retry_preserves_accepted_plain_branch_through_state_refresh(
    tmp_path,
):
    """A state-only repair refresh cannot revert OOMPAH-860 to hierarchy."""

    async def scenario():
        orch = _orchestrator(tmp_path)
        accepted = IntegrationRecord(
            state="blocked",
            task_branch="OOMPAH-860",
            base_branch="epic-OOMPAH-763",
            base_sha="b" * 40,
            head_sha="a" * 40,
        )
        issue = _issue(
            issue_id="oompah-860",
            identifier="OOMPAH-860",
            state="Needs CI Fix",
            work_branch="epic-OOMPAH-763--task-OOMPAH-860",
            head_sha=None,
        )
        issue.parent_id = "OOMPAH-763"
        issue.integration = accepted
        retry = _schedule(orch, issue)
        orch._retry_dispatching[issue.id] = retry
        orch._match_agent_profile = MagicMock(
            return_value=MagicMock(name="default", model_role="fast")
        )
        orch._run_worker = AsyncMock()
        tracker_state = {"state": "Needs CI Fix"}
        tracker = MagicMock()

        def fetch(_issue_ids):
            # Fast state refreshes can omit metadata.  Preserve the stale
            # hierarchy projection to prove accepted IntegrationRecord wins.
            return [
                Issue(
                    id=issue.id,
                    identifier=issue.identifier,
                    title=issue.title,
                    state=tracker_state["state"],
                    project_id=issue.project_id,
                    parent_id=issue.parent_id,
                    assignment_id=issue.assignment_id,
                    work_branch="epic-OOMPAH-763--task-OOMPAH-860",
                )
            ]

        def update(_identifier, *, status):
            tracker_state["state"] = status

        tracker.fetch_issue_states_by_ids.side_effect = fetch
        tracker.update_issue.side_effect = update
        orch._tracker_for_issue = MagicMock(return_value=tracker)

        await orch._dispatch(issue, attempt=retry.attempt, retry_entry=retry)
        await asyncio.sleep(0)

        assert retry.work_branch == "OOMPAH-860"
        assert tracker_state["state"] == "In Progress"
        orch._run_worker.assert_awaited_once()
        running = orch.state.running[issue.id]
        assert running.issue.integration is accepted
        assert orch._retry_issue_branch(running.issue) == "OOMPAH-860"

        if not running.worker_task.done():
            running.worker_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await running.worker_task

    asyncio.run(scenario())


def test_restart_rearms_ci_repair_on_accepted_plain_branch(tmp_path):
    """Persisted repair authority retains an accepted branch after restart."""

    original = _orchestrator(tmp_path)
    issue = _issue(
        issue_id="oompah-860",
        identifier="OOMPAH-860",
        state="Needs CI Fix",
        work_branch="epic-OOMPAH-763--task-OOMPAH-860",
        head_sha=None,
    )
    issue.parent_id = "OOMPAH-763"
    issue.integration = IntegrationRecord(
        state="blocked",
        task_branch="OOMPAH-860",
        base_branch="epic-OOMPAH-763",
        base_sha="b" * 40,
        head_sha="a" * 40,
    )
    retry = _schedule(original, issue)

    restarted = _orchestrator(tmp_path)
    restarted._fetch_retry_issue = MagicMock(return_value=issue)
    asyncio.run(restarted._restore_persisted_retries())

    restored = restarted.state.retry_attempts[issue.id]
    assert retry.work_branch == "OOMPAH-860"
    assert restored.work_branch == "OOMPAH-860"
    assert restarted._retry_issue_branch(issue) == "OOMPAH-860"
    restarted._cancel_retry_for_issue(issue_id=issue.id, reason="test cleanup")


def test_state_refresh_cannot_replace_a_newer_accepted_generation():
    source = _issue(
        issue_id="oompah-860",
        identifier="OOMPAH-860",
        work_branch="epic-OOMPAH-763--task-OOMPAH-860",
    )
    source.integration = IntegrationRecord(
        state="blocked",
        task_branch="OOMPAH-860",
        head_sha="b" * 40,
        submitted_at="2026-08-06T14:00:00+00:00",
    )
    stale = replace(
        source,
        integration=IntegrationRecord(
            state="blocked",
            task_branch="epic-OOMPAH-763--task-OOMPAH-860",
            head_sha="a" * 40,
            submitted_at="2026-08-06T13:00:00+00:00",
        ),
    )

    Orchestrator._preserve_accepted_submission_authority(source, stale)

    assert stale.integration is source.integration
    assert Orchestrator._retry_issue_branch(stale) == "OOMPAH-860"


def test_state_refresh_keeps_a_newer_concurrent_accepted_generation():
    source = _issue(issue_id="oompah-860", identifier="OOMPAH-860")
    source.integration = IntegrationRecord(
        state="blocked",
        task_branch="OOMPAH-860",
        head_sha="a" * 40,
        submitted_at="2026-08-06T13:00:00+00:00",
    )
    concurrent = replace(
        source,
        integration=IntegrationRecord(
            state="ready",
            task_branch="repair/OOMPAH-860",
            head_sha="b" * 40,
            submitted_at="2026-08-06T14:00:00+00:00",
        ),
    )
    accepted = concurrent.integration

    Orchestrator._preserve_accepted_submission_authority(source, concurrent)

    assert concurrent.integration is accepted
    assert Orchestrator._retry_issue_branch(concurrent) == "repair/OOMPAH-860"


def test_status_write_failure_rearms_accepted_branch_after_state_only_refresh(
    tmp_path,
):
    async def scenario():
        orch = _orchestrator(tmp_path)
        accepted = IntegrationRecord(
            state="blocked",
            task_branch="OOMPAH-860",
            base_branch="epic-OOMPAH-763",
            base_sha="b" * 40,
            head_sha="a" * 40,
            submitted_at="2026-08-06T13:00:00+00:00",
        )
        issue = _issue(
            issue_id="oompah-860",
            identifier="OOMPAH-860",
            state="Needs CI Fix",
            work_branch="epic-OOMPAH-763--task-OOMPAH-860",
            head_sha=None,
        )
        issue.integration = accepted
        retry = _schedule(orch, issue)
        orch._retry_dispatching[issue.id] = retry
        orch._match_agent_profile = MagicMock(
            return_value=MagicMock(name="default", model_role="fast")
        )
        orch._run_worker = AsyncMock()
        tracker = MagicMock()
        tracker.fetch_issue_states_by_ids.side_effect = lambda _issue_ids: [
            replace(issue, integration=None)
        ]
        tracker.update_issue.side_effect = RuntimeError("status write failed")
        orch._tracker_for_issue = MagicMock(return_value=tracker)

        await orch._dispatch(issue, attempt=retry.attempt, retry_entry=retry)

        assert orch.state.retry_attempts[issue.id] is retry
        assert retry.cancelled is False
        assert retry.work_branch == "OOMPAH-860"
        assert tracker.update_issue.call_count == 1
        orch._run_worker.assert_not_awaited()
        orch._cancel_retry_for_issue(issue_id=issue.id, reason="test cleanup")

    asyncio.run(scenario())


def test_focus_handoff_open_retry_starts_feature_developer_exactly_once(tmp_path):
    async def scenario():
        orch = _orchestrator(tmp_path)
        issue = _issue(state="In Progress")
        issue.labels = ["focus-complete:docs", "needs:feature"]
        tracker_state = {"state": "In Progress"}
        tracker = MagicMock()
        tracker.fetch_comments.return_value = [
            {
                "author": "oompah",
                "text": (
                    "Focus handoff: docs\n"
                    "Documentation review is complete; implementation remains."
                ),
            }
        ]

        def fetch(_issue_ids):
            return [replace(issue, state=tracker_state["state"])]

        def update(_identifier, *, status):
            tracker_state["state"] = status

        tracker.fetch_issue_states_by_ids.side_effect = fetch
        tracker.update_issue.side_effect = update
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch._tracker_for_issue = MagicMock(return_value=tracker)
        orch._post_comment = MagicMock()
        writer_entry = RunningEntry(
            worker_task=None,
            identifier=issue.identifier,
            issue=issue,
            session=None,
            retry_attempt=0,
            started_at=datetime.now(timezone.utc),
            agent_profile_name="deep",
            focus_name="docs",
            focus_role="Technical Writer",
            assignment_id="assignment-1",
        )

        assert orch._handoff_completed_focus(
            writer_entry,
            issue,
            issue.project_id,
        )
        assert tracker_state["state"] == "Open"
        assert select_focus(issue, foci=BUILTIN_FOCI).role == "Feature Developer"

        orch._schedule_retry(
            issue.id,
            attempt=1,
            identifier=issue.identifier,
            delay_ms=60_000,
            error="focus handoff retry",
            escalated_profile="deep",
            project_id=issue.project_id,
            context_entry=writer_entry,
            authority_issue=issue,
        )
        retry = orch.state.retry_attempts[issue.id]
        orch._retry_dispatching[issue.id] = retry
        profile = MagicMock(name="deep", model_role="deep")
        profile.name = "deep"
        orch._get_profile_by_name = MagicMock(return_value=profile)
        started_roles: list[str] = []

        async def run_worker(running_issue, *_args, **_kwargs):
            started_roles.append(
                select_focus(running_issue, foci=BUILTIN_FOCI).role
            )

        orch._run_worker = AsyncMock(side_effect=run_worker)

        await orch._dispatch(
            issue,
            attempt=retry.attempt,
            override_profile=retry.escalated_profile,
            retry_entry=retry,
        )
        for _ in range(20):
            await asyncio.sleep(0)
            if started_roles:
                break

        assert tracker_state["state"] == "In Progress"
        assert started_roles == ["Feature Developer"]
        assert orch._run_worker.await_count == 1
        assert issue.id in orch.state.running
        assert retry.cancelled is True

    asyncio.run(scenario())


def test_retry_authorizes_its_shared_tracker_assignment_claim(tmp_path):
    async def scenario():
        orch = _orchestrator(tmp_path)
        issue = _issue(state="Open")
        issue.tracker_kind = "oompah_md"
        retry = _schedule(orch, issue)
        orch._retry_dispatching[issue.id] = retry
        orch._match_agent_profile = MagicMock(
            return_value=MagicMock(name="default", model_role="fast")
        )
        orch._run_worker = AsyncMock()
        tracker_state = {
            "state": "Open",
            "assignment_id": issue.assignment_id,
        }
        tracker = MagicMock()

        def fetch(_issue_ids):
            return [
                replace(
                    issue,
                    state=tracker_state["state"],
                    assignment_id=tracker_state["assignment_id"],
                )
            ]

        def update(_identifier, *, status):
            tracker_state["state"] = status

        def set_metadata(_identifier, field, value):
            assert field == "oompah.agent_run_id"
            tracker_state["assignment_id"] = value

        tracker.fetch_issue_states_by_ids.side_effect = fetch
        tracker.update_issue.side_effect = update
        tracker.set_metadata_field.side_effect = set_metadata
        tracker.get_metadata.side_effect = lambda _identifier: {
            "oompah.agent_run_id": tracker_state["assignment_id"]
        }
        orch._tracker_for_issue = MagicMock(return_value=tracker)

        await orch._dispatch(issue, attempt=retry.attempt, retry_entry=retry)
        await asyncio.sleep(0)

        running = orch.state.running[issue.id]
        assert tracker_state["assignment_id"] != issue.assignment_id
        assert running.assignment_id == tracker_state["assignment_id"]
        assert retry.dispatch_assignment_id == tracker_state["assignment_id"]
        orch._run_worker.assert_awaited_once()

        if running.worker_task is not None and not running.worker_task.done():
            running.worker_task.cancel()

    asyncio.run(scenario())


def test_retry_status_write_failure_restores_open_and_rearms_generation(tmp_path):
    async def scenario():
        orch = _orchestrator(tmp_path)
        issue = _issue(state="Open")
        retry = _schedule(orch, issue)
        orch._retry_dispatching[issue.id] = retry
        orch._match_agent_profile = MagicMock(
            return_value=MagicMock(name="default", model_role="fast")
        )
        orch._run_worker = AsyncMock()
        tracker_state = {"state": "Open"}
        tracker = MagicMock()
        fetch_count = 0

        def fetch(_issue_ids):
            nonlocal fetch_count
            fetch_count += 1
            return [replace(issue, state=tracker_state["state"])]

        def update(_identifier, *, status):
            tracker_state["state"] = status
            if status == "In Progress":
                raise RuntimeError("tracker write response lost after commit")

        tracker.fetch_issue_states_by_ids.side_effect = fetch
        tracker.update_issue.side_effect = update
        orch._tracker_for_issue = MagicMock(return_value=tracker)

        await orch._dispatch(issue, attempt=retry.attempt, retry_entry=retry)

        assert fetch_count == 3
        assert [call.kwargs["status"] for call in tracker.update_issue.call_args_list] == [
            "In Progress",
            "Open",
        ]
        assert tracker_state["state"] == "Open"
        assert issue.id not in orch.state.running
        assert issue.id in orch.state.retry_attempts
        assert orch.state.retry_attempts[issue.id] is retry
        assert retry.timer_handle is not None
        orch._cancel_retry_for_issue(issue_id=issue.id, reason="test cleanup")
        orch._run_worker.assert_not_awaited()

    asyncio.run(scenario())


def test_regular_worker_task_creation_failure_restores_tracker_state(tmp_path):
    """A non-auditor launch failure cannot orphan an ordinary task active."""

    async def scenario():
        orch = _orchestrator(tmp_path)
        issue = _issue(state="Open", assignment_id="prior-run")
        issue.tracker_kind = "oompah_md"
        orch._match_agent_profile = MagicMock(
            return_value=MagicMock(name="default", model_role="fast")
        )
        orch._run_worker = AsyncMock()
        tracker_state = {"state": "Open"}
        metadata = {"oompah.agent_run_id": "prior-run"}
        tracker = MagicMock()
        tracker.fetch_issue_states_by_ids.side_effect = lambda _ids: [
            replace(issue, state=tracker_state["state"])
        ]
        tracker.update_issue.side_effect = (
            lambda _identifier, *, status: tracker_state.update(state=status)
        )
        tracker.get_metadata.side_effect = lambda _identifier: dict(metadata)
        tracker.set_metadata_field.side_effect = (
            lambda _identifier, key, value: metadata.update({key: value})
        )
        orch._tracker_for_issue = MagicMock(return_value=tracker)

        with patch(
            "oompah.orchestrator.asyncio.create_task",
            side_effect=RuntimeError("event loop rejected worker task"),
        ):
            admitted = await orch._dispatch(issue, attempt=None)

        assert admitted is False
        assert tracker_state["state"] == "Open"
        assert metadata["oompah.agent_run_id"] == "prior-run"
        assert [call.kwargs["status"] for call in tracker.update_issue.call_args_list] == [
            "In Progress",
            "Open",
        ]
        assert issue.id not in orch.state.running
        assert issue.id not in orch.state.claimed
        orch._run_worker.assert_not_awaited()

    asyncio.run(scenario())


def test_regular_status_commit_with_lost_response_gets_free_recovery_owner(tmp_path):
    """An uncertain initial status commit is reconciled like a retry claim."""

    async def scenario():
        orch = _orchestrator(tmp_path)
        issue = _issue(state="Open")
        orch._match_agent_profile = MagicMock(
            return_value=MagicMock(name="default", model_role="fast")
        )
        tracker_state = {"state": "Open"}
        tracker = MagicMock()
        tracker.fetch_issue_states_by_ids.side_effect = lambda _ids: [
            replace(issue, state=tracker_state["state"])
        ]

        def update(_identifier, *, status):
            tracker_state["state"] = status
            if status == "In Progress":
                raise RuntimeError("status committed but response was lost")

        tracker.update_issue.side_effect = update
        orch._tracker_for_issue = MagicMock(return_value=tracker)

        admitted = await orch._dispatch(issue, attempt=None)

        assert admitted is False
        assert tracker_state["state"] == "Open"
        assert [call.kwargs["status"] for call in tracker.update_issue.call_args_list] == [
            "In Progress",
            "Open",
        ]
        recovery = orch.state.retry_attempts[issue.id]
        assert recovery.pre_admission_recovery is True
        assert recovery.attempt == 0
        assert recovery.dispatch_status is None
        persisted = orch._load_state()["retry_attempts"][issue.id]
        assert persisted["pre_admission_recovery"] is True
        assert issue.id not in orch.state.running
        assert issue.id not in orch.state.claimed
        orch._cancel_retry_for_issue(issue_id=issue.id, reason="test cleanup")

    asyncio.run(scenario())


def test_regular_rollback_failure_persists_restart_recovery_owner(tmp_path):
    """A failed Open rollback cannot leave an ownerless active task."""

    async def scenario():
        orch = _orchestrator(tmp_path)
        issue = _issue(state="Open")
        orch._match_agent_profile = MagicMock(
            return_value=MagicMock(name="default", model_role="fast")
        )
        tracker_state = {"state": "Open"}
        tracker = MagicMock()
        tracker.fetch_issue_states_by_ids.side_effect = lambda _ids: [
            replace(issue, state=tracker_state["state"])
        ]

        def update(_identifier, *, status):
            if status == "Open":
                raise RuntimeError("temporary rollback outage")
            tracker_state["state"] = status

        tracker.update_issue.side_effect = update
        orch._tracker_for_issue = MagicMock(return_value=tracker)

        with patch(
            "oompah.orchestrator.asyncio.create_task",
            side_effect=RuntimeError("event loop rejected worker task"),
        ):
            admitted = await orch._dispatch(issue, attempt=None)

        assert admitted is False
        assert tracker_state["state"] == "In Progress"
        recovery = orch.state.retry_attempts[issue.id]
        assert recovery.pre_admission_recovery is True
        assert recovery.dispatch_status == "In Progress"
        persisted = orch._load_state()["retry_attempts"][issue.id]
        assert persisted["authority_generation"] == recovery.authority_generation
        assert persisted["dispatch_status"] == "In Progress"

        restarted = _orchestrator(tmp_path)
        restored = next(
            entry
            for entry in restarted._persisted_retry_entries
            if entry.issue_id == issue.id
        )
        assert restored.pre_admission_recovery is True
        assert restored.dispatch_status == "In Progress"
        restarted_tracker_state = {"state": "In Progress"}
        restarted._fetch_retry_issue = MagicMock(
            side_effect=lambda _retry: replace(
                issue,
                state=restarted_tracker_state["state"],
            )
        )
        restarted_tracker = MagicMock()
        restarted_tracker.fetch_issue_states_by_ids.side_effect = lambda _ids: [
            replace(issue, state=restarted_tracker_state["state"])
        ]
        restarted_tracker.update_issue.side_effect = (
            lambda _identifier, *, status: restarted_tracker_state.update(
                state=status
            )
        )
        restarted._tracker_for_issue = MagicMock(return_value=restarted_tracker)
        await restarted._restore_persisted_retries()
        assert restarted.state.retry_attempts[issue.id].timer_handle is not None
        assert restarted.state.retry_attempts[issue.id].pre_admission_recovery is True
        restarted.state.retry_attempts[issue.id].timer_handle.cancel()
        restarted._dispatch = AsyncMock(return_value=True)
        await restarted._on_retry_timer(issue.id)
        assert restarted_tracker_state["state"] == "Open"
        restarted._dispatch.assert_not_awaited()
        restarted.state.retry_attempts[issue.id].timer_handle.cancel()
        restarted.state.retry_attempts[issue.id].timer_handle = None
        await restarted._on_retry_timer(issue.id)
        assert restarted._dispatch.await_args.kwargs["attempt"] is None
        assert restarted._dispatch.await_args.kwargs["override_profile"] is None
        assert (
            restarted._dispatch.await_args.kwargs["retry_entry"]
            is restarted.state.retry_attempts[issue.id]
        )
        orch._cancel_retry_for_issue(issue_id=issue.id, reason="test cleanup")
        restarted._cancel_retry_for_issue(issue_id=issue.id, reason="test cleanup")

    asyncio.run(scenario())


def test_regular_recovery_survives_primary_journal_failure_and_restart(tmp_path):
    """The independent journal owns an uncertain claim if state save fails."""

    async def scenario():
        orch = _orchestrator(tmp_path)
        issue = _issue(state="Open")
        orch._match_agent_profile = MagicMock(
            return_value=MagicMock(name="default", model_role="fast")
        )
        tracker_state = {"state": "Open"}
        tracker = MagicMock()
        tracker.fetch_issue_states_by_ids.side_effect = lambda _ids: [
            replace(issue, state=tracker_state["state"])
        ]

        def update(_identifier, *, status):
            if status == "Open":
                raise RuntimeError("rollback unavailable")
            tracker_state["state"] = status

        tracker.update_issue.side_effect = update
        orch._tracker_for_issue = MagicMock(return_value=tracker)

        with (
            patch.object(orch, "_save_state", return_value=False),
            patch(
                "oompah.orchestrator.asyncio.create_task",
                side_effect=RuntimeError("event loop rejected worker task"),
            ),
        ):
            admitted = await orch._dispatch(issue, attempt=None)

        assert admitted is False
        recovery = orch.state.retry_attempts[issue.id]
        assert recovery.dispatch_status == "In Progress"
        assert orch._retry_persistence_failed is False
        assert orch._retry_fallback_path.endswith(
            ".implementation-retries.json"
        )

        replacement = _orchestrator(tmp_path)
        restored = next(
            entry
            for entry in replacement._persisted_retry_entries
            if entry.issue_id == issue.id
        )
        assert restored.authority_generation == recovery.authority_generation
        assert restored.pre_admission_recovery is True
        assert restored.dispatch_status == "In Progress"
        orch._cancel_retry_for_issue(issue_id=issue.id, reason="test cleanup")

    asyncio.run(scenario())


def test_both_retry_journal_failures_close_provider_admission(tmp_path):
    """A process-local owner is fail-closed when neither journal can commit."""

    async def scenario():
        orch = _orchestrator(tmp_path)
        issue = _issue(state="Open")
        with (
            patch.object(orch, "_save_retry_fallback", return_value=False),
            patch.object(orch, "_save_state", return_value=False),
        ):
            recovery = orch._install_pre_admission_recovery(
                issue,
                restore_status="Open",
                intended_active_state="In Progress",
                intended_assignment_id=issue.assignment_id,
                attempt=None,
                reason="unpersistable pre-admission claim",
            )

        assert orch._retry_persistence_failed is True
        assert orch._quiesced is True
        assert orch._dispatch_is_blocked(issue) is True
        assert orch.state.retry_attempts[issue.id] is recovery
        assert recovery.cancelled is False
        orch._cancel_retry_for_issue(issue_id=issue.id, reason="test cleanup")

    asyncio.run(scenario())


def test_unpause_repairs_retry_journal_before_reopening_admission(tmp_path):
    """Retained retry authority stays fenced until a durable write succeeds."""

    orch = _orchestrator(tmp_path)
    issue = _issue(state="Open")
    with (
        patch.object(orch, "_save_retry_fallback", return_value=False),
        patch.object(orch, "_save_state", return_value=False),
    ):
        recovery = orch._install_pre_admission_recovery(
            issue,
            restore_status="Open",
            intended_active_state="In Progress",
            intended_assignment_id=issue.assignment_id,
            attempt=None,
            reason="unpersistable pre-admission claim",
        )

    activate = MagicMock(return_value=True)
    with (
        patch.object(orch, "_activate_unpaused_dispatch", activate),
        patch.object(orch, "_save_retry_fallback", return_value=False),
        patch.object(orch, "_save_state", return_value=False),
    ):
        assert orch.unpause() is False

    assert activate.call_count == 0
    assert orch._retry_persistence_failed is True
    assert orch._quiesced is True
    assert orch._dispatch_is_blocked(issue) is True
    assert orch.state.retry_attempts[issue.id] is recovery

    observed_during_persistence: list[tuple[bool, bool, bool]] = []
    real_save_fallback = orch._save_retry_fallback

    def recovered_save(snapshot):
        observed_during_persistence.append(
            (
                orch._quiesced,
                orch._retry_persistence_failed,
                orch._dispatch_is_blocked(issue),
            )
        )
        return real_save_fallback(snapshot)

    with (
        patch.object(orch, "_activate_unpaused_dispatch", activate),
        patch.object(orch, "_save_retry_fallback", side_effect=recovered_save),
    ):
        assert orch.unpause() is True

    assert observed_during_persistence == [(True, True, True)]
    assert orch._retry_persistence_failed is False
    assert orch._quiesced is False
    assert orch._dispatch_is_blocked(issue) is False
    activate.assert_called_once_with()
    orch._cancel_retry_for_issue(issue_id=issue.id, reason="test cleanup")


def test_post_rearm_persistence_failure_suppresses_resumed_event(tmp_path):
    """Activation cannot report success after its new retry snapshot fails."""

    async def scenario():
        orch = _orchestrator(tmp_path)
        issue = _issue(state="Open")
        recovery = orch._install_pre_admission_recovery(
            issue,
            restore_status="Open",
            intended_active_state="In Progress",
            intended_assignment_id=issue.assignment_id,
            attempt=None,
            reason="suspended pre-admission recovery",
        )
        if recovery.timer_handle is not None:
            recovery.timer_handle.cancel()
            recovery.timer_handle = None
        with orch._provider_admission_lock:
            orch._paused = True
            orch._quiesced = True

        emitted: list[object] = []
        real_emit = orch.event_bus.emit

        def record_emit(event_type, payload):
            emitted.append(event_type)
            return real_emit(event_type, payload)

        with (
            patch.object(orch, "_save_retry_fallback", return_value=False),
            patch.object(orch, "_save_state", return_value=False),
            patch.object(orch.event_bus, "emit", side_effect=record_emit),
        ):
            assert orch.unpause() is False

        assert recovery.timer_handle is not None
        assert orch._retry_persistence_failed is True
        assert orch._quiesced is True
        assert orch._dispatch_is_blocked(issue) is True
        assert all(
            getattr(event_type, "value", event_type) != "orchestrator_resumed"
            for event_type in emitted
        )
        recovery.timer_handle.cancel()
        recovery.timer_handle = None
        orch._cancel_retry_for_issue(issue_id=issue.id, reason="test cleanup")

    asyncio.run(scenario())


@pytest.mark.parametrize("lifecycle_fence", ["pause", "quiesce"])
def test_lifecycle_fence_preserves_failed_pre_admission_rollback(
    tmp_path,
    lifecycle_fence,
):
    """Pause and quiesce retain the free owner until rollback succeeds."""

    async def scenario():
        orch = _orchestrator(tmp_path)
        source = _issue(state="Open")
        active = replace(source, state="In Progress")
        tracker_state = {"state": "In Progress", "fail_rollback": True}
        tracker = MagicMock()
        tracker.fetch_issue_states_by_ids.side_effect = lambda _ids: [
            replace(active, state=tracker_state["state"])
        ]

        def update(_identifier, *, status):
            if status == "Open" and tracker_state["fail_rollback"]:
                raise RuntimeError("temporary rollback outage")
            tracker_state["state"] = status

        tracker.update_issue.side_effect = update
        orch._tracker_for_issue = MagicMock(return_value=tracker)
        recovery = orch._install_pre_admission_recovery(
            source,
            restore_status="Open",
            intended_active_state="In Progress",
            intended_assignment_id=source.assignment_id,
            attempt=None,
            reason="pre-admission launch failure",
        )
        orch._fetch_retry_issue = MagicMock(
            side_effect=lambda _retry: replace(
                active,
                state=tracker_state["state"],
            )
        )
        orch._dispatch = AsyncMock(return_value=False)

        getattr(orch, lifecycle_fence)()
        assert recovery.cancelled is False
        assert orch.state.retry_attempts[source.id] is recovery
        if lifecycle_fence == "pause":
            assert recovery.timer_handle is None
        else:
            recovery.timer_handle.cancel()
            recovery.timer_handle = None
            await orch._on_retry_timer(source.id)
            assert recovery.dispatch_status == "In Progress"
            assert recovery.timer_handle is None

        assert orch.unpause() is True
        assert recovery.timer_handle is not None
        recovery.timer_handle.cancel()
        recovery.timer_handle = None
        await orch._on_retry_timer(source.id)
        assert recovery.dispatch_status == "In Progress"
        assert recovery.cancelled is False
        orch._dispatch.assert_not_awaited()

        tracker_state["fail_rollback"] = False
        recovery.timer_handle.cancel()
        recovery.timer_handle = None
        await orch._on_retry_timer(source.id)
        assert tracker_state["state"] == "Open"
        assert recovery.dispatch_status is None
        orch._dispatch.assert_not_awaited()

        recovery.timer_handle.cancel()
        recovery.timer_handle = None
        await orch._on_retry_timer(source.id)
        orch._dispatch.assert_awaited_once()
        assert orch._dispatch.await_args.kwargs["attempt"] is None
        orch._cancel_retry_for_issue(issue_id=source.id, reason="test cleanup")

    asyncio.run(scenario())


def test_retry_journal_serializes_reordered_install_and_cancel(tmp_path):
    """A delayed older writer cannot resurrect retry authority."""

    orch = _orchestrator(tmp_path)
    issue = _issue(state="Open")
    retry = _schedule(orch, issue)
    baseline_version = orch._retry_snapshot_version
    first_write_started = threading.Event()
    release_first_write = threading.Event()
    second_writer_started = threading.Event()
    written_versions: list[int] = []
    real_save_fallback = orch._save_retry_fallback

    def delayed_save(snapshot):
        version = int(snapshot["version"])
        written_versions.append(version)
        if version == baseline_version + 1:
            first_write_started.set()
            assert release_first_write.wait(timeout=3)
        return real_save_fallback(snapshot)

    def persist_old_snapshot():
        orch._persist_retry_entries()

    def cancel_and_persist_new_snapshot():
        second_writer_started.set()
        orch._cancel_retry_for_issue(issue_id=issue.id, reason="replacement owner")

    with patch.object(orch, "_save_retry_fallback", side_effect=delayed_save):
        old_writer = threading.Thread(target=persist_old_snapshot)
        new_writer = threading.Thread(target=cancel_and_persist_new_snapshot)
        old_writer.start()
        assert first_write_started.wait(timeout=3)
        new_writer.start()
        assert second_writer_started.wait(timeout=3)
        release_first_write.set()
        old_writer.join(timeout=3)
        new_writer.join(timeout=3)

    assert not old_writer.is_alive()
    assert not new_writer.is_alive()
    assert retry.cancelled is True
    assert written_versions == [baseline_version + 1, baseline_version + 2]
    state = orch._load_state()
    assert state["retry_attempts"] == {}
    assert state["retry_attempts_version"] == baseline_version + 2
    fallback_version, fallback_entries = orch._load_retry_fallback()
    assert fallback_version == baseline_version + 2
    assert fallback_entries == {}
    assert _orchestrator(tmp_path)._persisted_retry_entries == []


def test_nested_dispatch_cancellation_waits_for_admission_compensation(tmp_path):
    """Repeated cancellation cannot interrupt exact tracker rollback."""

    async def scenario():
        orch = _orchestrator(tmp_path)
        issue = _issue(state="Open")
        orch._match_agent_profile = MagicMock(
            return_value=MagicMock(name="default", model_role="fast")
        )
        tracker_state = {"state": "Open"}
        tracker = MagicMock()
        tracker.fetch_issue_states_by_ids.side_effect = lambda _ids: [
            replace(issue, state=tracker_state["state"])
        ]
        tracker.update_issue.side_effect = (
            lambda _identifier, *, status: tracker_state.update(state=status)
        )
        orch._tracker_for_issue = MagicMock(return_value=tracker)

        recovery_entered = asyncio.Event()
        release_recovery = asyncio.Event()
        recovery_finished = asyncio.Event()
        real_recover = orch._recover_aborted_retry_dispatch

        async def delayed_recover(*args, **kwargs):
            recovery_entered.set()
            await release_recovery.wait()
            await real_recover(*args, **kwargs)
            recovery_finished.set()

        orch._recover_aborted_retry_dispatch = delayed_recover
        loop = asyncio.get_running_loop()
        with patch(
            "oompah.orchestrator.asyncio.create_task",
            side_effect=RuntimeError("event loop rejected worker task"),
        ):
            dispatch_task = loop.create_task(orch._dispatch(issue, attempt=None))
            await recovery_entered.wait()
            dispatch_task.cancel()
            await asyncio.sleep(0)
            dispatch_task.cancel()
            release_recovery.set()
            with pytest.raises(asyncio.CancelledError):
                await dispatch_task

        assert recovery_finished.is_set()
        assert tracker_state["state"] == "Open"
        assert issue.id in orch.state.retry_attempts
        assert issue.id not in orch.state.running
        assert issue.id not in orch.state.claimed
        orch._cancel_retry_for_issue(issue_id=issue.id, reason="test cleanup")

    asyncio.run(scenario())


def test_retry_worker_task_creation_failure_restores_exact_retry_owner(tmp_path):
    """A retry is consumed only after worker task and RunningEntry publication."""

    async def scenario():
        orch = _orchestrator(tmp_path)
        issue = _issue(state="Open")
        issue.tracker_kind = "oompah_md"
        retry = _schedule(orch, issue)
        orch._retry_dispatching[issue.id] = retry
        orch._match_agent_profile = MagicMock(
            return_value=MagicMock(name="default", model_role="fast")
        )
        orch._run_worker = AsyncMock()
        tracker_state = {"state": "Open"}
        metadata = {"oompah.agent_run_id": issue.assignment_id}
        tracker = MagicMock()
        tracker.fetch_issue_states_by_ids.side_effect = lambda _ids: [
            replace(
                issue,
                state=tracker_state["state"],
                assignment_id=metadata["oompah.agent_run_id"],
            )
        ]
        tracker.update_issue.side_effect = (
            lambda _identifier, *, status: tracker_state.update(state=status)
        )
        tracker.get_metadata.side_effect = lambda _identifier: dict(metadata)
        tracker.set_metadata_field.side_effect = (
            lambda _identifier, key, value: metadata.update({key: value})
        )
        orch._tracker_for_issue = MagicMock(return_value=tracker)

        with patch(
            "oompah.orchestrator.asyncio.create_task",
            side_effect=RuntimeError("event loop rejected retry worker task"),
        ):
            admitted = await orch._dispatch(
                issue,
                attempt=retry.attempt,
                retry_entry=retry,
            )

        assert admitted is False
        assert tracker_state["state"] == "Open"
        assert metadata["oompah.agent_run_id"] == issue.assignment_id
        assert orch.state.retry_attempts[issue.id] is retry
        assert retry.cancelled is False
        assert retry.dispatch_status is None
        assert retry.timer_handle is not None
        assert issue.id not in orch.state.running
        assert issue.id not in orch.state.claimed
        orch._run_worker.assert_not_awaited()
        orch._cancel_retry_for_issue(issue_id=issue.id, reason="test cleanup")

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("dimension", "expected_diagnostic"),
    [
        ("branch", "branch"),
        ("assignment", "assignment"),
        ("head", "head"),
    ],
)
def test_retry_abort_after_status_write_restores_open_and_withdraws_drifted_generation(
    tmp_path,
    caplog,
    dimension,
    expected_diagnostic,
):
    async def scenario():
        caplog.set_level("INFO")
        orch = _orchestrator(tmp_path)
        issue = _issue(state="Open")
        retry = _schedule(orch, issue)
        orch._retry_dispatching[issue.id] = retry
        orch._match_agent_profile = MagicMock(
            return_value=MagicMock(name="default", model_role="fast")
        )
        orch._run_worker = AsyncMock()
        tracker_state = {"state": "Open", "drifted": False}
        tracker = MagicMock()
        fetch_count = 0

        def fetch(_issue_ids):
            nonlocal fetch_count
            fetch_count += 1
            values = {"state": tracker_state["state"]}
            if tracker_state["drifted"]:
                if dimension == "branch":
                    values["work_branch"] = "task/replacement"
                elif dimension == "assignment":
                    values["assignment_id"] = "assignment-2"
                else:
                    values["integration"] = IntegrationRecord(
                        state="ready",
                        head_sha="b" * 40,
                    )
            return [replace(issue, **values)]

        def update(_identifier, *, status):
            tracker_state["state"] = status
            if status == "In Progress":
                tracker_state["drifted"] = True

        tracker.fetch_issue_states_by_ids.side_effect = fetch
        tracker.update_issue.side_effect = update
        orch._tracker_for_issue = MagicMock(return_value=tracker)

        await orch._dispatch(issue, attempt=retry.attempt, retry_entry=retry)

        assert [call.kwargs["status"] for call in tracker.update_issue.call_args_list] == [
            "In Progress",
            "Open",
        ]
        assert tracker_state["state"] == "Open"
        assert issue.id not in orch.state.running
        assert issue.id not in orch.state.claimed
        assert issue.id not in orch.state.retry_attempts
        orch._run_worker.assert_not_awaited()
        diagnostics = [
            record.retry_authority
            for record in caplog.records
            if hasattr(record, "retry_authority")
        ]
        assert any(
            expected_diagnostic in diagnostic["dimensions"]
            for diagnostic in diagnostics
        )

    asyncio.run(scenario())


def test_operator_open_wins_after_retry_status_write(tmp_path):
    async def scenario():
        orch = _orchestrator(tmp_path)
        issue = _issue(state="Open")
        retry = _schedule(orch, issue)
        orch._retry_dispatching[issue.id] = retry
        orch._match_agent_profile = MagicMock(
            return_value=MagicMock(name="default", model_role="fast")
        )
        orch._run_worker = AsyncMock()
        tracker = MagicMock()
        tracker.fetch_issue_states_by_ids.side_effect = [
            [issue],
            [issue],
            [_issue(state="Open")],
        ]

        def update(_identifier, *, status):
            if status == "In Progress":
                orch._cancel_retry_for_issue(
                    issue_id=issue.id,
                    identifier=issue.identifier,
                    project_id=issue.project_id,
                    reason="operator moved task back to Open",
                )

        tracker.update_issue.side_effect = update
        orch._tracker_for_issue = MagicMock(return_value=tracker)

        await orch._dispatch(issue, attempt=retry.attempt, retry_entry=retry)

        assert [call.kwargs["status"] for call in tracker.update_issue.call_args_list] == [
            "In Progress",
        ]
        assert issue.id not in orch.state.running
        assert issue.id not in orch.state.retry_attempts
        assert retry.cancelled is True
        orch._run_worker.assert_not_awaited()

    asyncio.run(scenario())


def test_accepted_submission_wins_during_retry_setup(tmp_path):
    async def scenario():
        orch = _orchestrator(tmp_path)
        issue = _issue(state="Open")
        retry = _schedule(orch, issue)
        orch._retry_dispatching[issue.id] = retry
        orch._match_agent_profile = MagicMock(
            return_value=MagicMock(name="default", model_role="fast")
        )
        orch._run_worker = AsyncMock()
        tracker_state = {"state": "Open"}
        tracker = MagicMock()
        fetch_count = 0

        def fetch(_issue_ids):
            nonlocal fetch_count
            fetch_count += 1
            if fetch_count == 3:
                tracker_state["state"] = "Ready to Integrate"
                orch._cancel_retry_for_issue(
                    issue_id=issue.id,
                    identifier=issue.identifier,
                    project_id=issue.project_id,
                    reason="task submitted for integration",
                )
                return [
                    replace(
                        issue,
                        state=tracker_state["state"],
                        integration=IntegrationRecord(
                            state="ready",
                            head_sha="b" * 40,
                        ),
                    )
                ]
            return [replace(issue, state=tracker_state["state"])]

        tracker.fetch_issue_states_by_ids.side_effect = fetch
        tracker.update_issue.side_effect = (
            lambda _identifier, *, status: tracker_state.update(state=status)
        )
        orch._tracker_for_issue = MagicMock(return_value=tracker)

        await orch._dispatch(issue, attempt=retry.attempt, retry_entry=retry)

        assert tracker_state["state"] == "Ready to Integrate"
        assert [call.kwargs["status"] for call in tracker.update_issue.call_args_list] == [
            "In Progress",
        ]
        assert retry.cancelled is True
        assert issue.id not in orch.state.retry_attempts
        assert issue.id not in orch.state.running
        orch._run_worker.assert_not_awaited()

    asyncio.run(scenario())


def test_failed_status_rollback_keeps_live_retry_owner(tmp_path):
    async def scenario():
        orch = _orchestrator(tmp_path)
        issue = _issue(state="Open")
        retry = _schedule(orch, issue)
        orch._retry_dispatching[issue.id] = retry
        orch._match_agent_profile = MagicMock(
            return_value=MagicMock(name="default", model_role="fast")
        )
        orch._run_worker = AsyncMock()
        tracker_state = {
            "state": "Open",
            "branch": issue.work_branch,
        }
        tracker = MagicMock()

        def fetch(_issue_ids):
            return [
                replace(
                    issue,
                    state=tracker_state["state"],
                    work_branch=tracker_state["branch"],
                )
            ]

        def update(_identifier, *, status):
            if status == "Open":
                raise RuntimeError("temporary rollback failure")
            tracker_state["state"] = status
            tracker_state["branch"] = "task/replacement"

        tracker.fetch_issue_states_by_ids.side_effect = fetch
        tracker.update_issue.side_effect = update
        orch._tracker_for_issue = MagicMock(return_value=tracker)

        await orch._dispatch(issue, attempt=retry.attempt, retry_entry=retry)

        assert tracker_state["state"] == "In Progress"
        assert issue.id not in orch.state.running
        assert orch.state.retry_attempts[issue.id] is retry
        assert retry.cancelled is False
        assert retry.dispatch_status == "In Progress"
        assert retry.timer_handle is not None
        orch._run_worker.assert_not_awaited()
        orch._cancel_retry_for_issue(issue_id=issue.id, reason="test cleanup")

    asyncio.run(scenario())


def test_terminal_owner_fence_wins_after_retry_status_write(tmp_path):
    async def scenario():
        orch = _orchestrator(tmp_path)
        issue = _issue(state="Open")
        retry = _schedule(orch, issue)
        orch._retry_dispatching[issue.id] = retry
        orch._match_agent_profile = MagicMock(
            return_value=MagicMock(name="default", model_role="fast")
        )
        orch._run_worker = AsyncMock()
        tracker_state = {"state": "Open"}
        tracker = MagicMock()
        fetch_count = 0

        def fetch(_issue_ids):
            nonlocal fetch_count
            fetch_count += 1
            if fetch_count == 3:
                orch.state.completed.add(issue.id)
            return [replace(issue, state=tracker_state["state"])]

        tracker.fetch_issue_states_by_ids.side_effect = fetch
        tracker.update_issue.side_effect = (
            lambda _identifier, *, status: tracker_state.update(state=status)
        )
        orch._tracker_for_issue = MagicMock(return_value=tracker)

        await orch._dispatch(issue, attempt=retry.attempt, retry_entry=retry)

        assert tracker_state["state"] == "In Progress"
        assert issue.id in orch.state.completed
        assert retry.cancelled is True
        assert issue.id not in orch.state.retry_attempts
        assert issue.id not in orch.state.running
        orch._run_worker.assert_not_awaited()

    asyncio.run(scenario())


def test_due_retry_loses_to_submit_cancellation_race(tmp_path):
    async def scenario():
        orch = _orchestrator(tmp_path)
        issue = _issue()
        retry = _schedule(orch, issue)
        started = threading.Event()
        release = threading.Event()

        def fetch(_retry):
            started.set()
            assert release.wait(timeout=3)
            return _issue()

        orch._fetch_retry_issue = fetch
        orch._dispatch = AsyncMock()
        task = asyncio.create_task(orch._on_retry_timer(issue.id))
        await asyncio.to_thread(started.wait)

        # This is the same operation the submit/status API uses. It must
        # withdraw the entry even though its timer callback is awaiting I/O.
        orch._cancel_retry_for_issue(
            issue_id=issue.id,
            identifier=issue.identifier,
            project_id=issue.project_id,
            reason="task submitted for integration",
        )
        release.set()
        await task

        orch._dispatch.assert_not_awaited()
        assert retry.cancelled is True

    asyncio.run(scenario())


def test_restart_discards_persisted_retry_with_replaced_head(tmp_path):
    original = _orchestrator(tmp_path)
    retry = _schedule(original, _issue())
    restarted = _orchestrator(tmp_path)
    restarted._fetch_retry_issue = MagicMock(
        return_value=_issue(head_sha="b" * 40)
    )

    asyncio.run(restarted._restore_persisted_retries())

    assert retry.authority_generation
    assert restarted.state.retry_attempts == {}
    assert restarted._load_state().get("retry_attempts") == {}


def test_restart_discards_persisted_retry_for_missing_task(tmp_path):
    original = _orchestrator(tmp_path)
    _schedule(original, _issue())
    restarted = _orchestrator(tmp_path)
    restarted._fetch_retry_issue = MagicMock(return_value=None)

    asyncio.run(restarted._restore_persisted_retries())

    assert restarted.state.retry_attempts == {}
    assert restarted._load_state().get("retry_attempts") == {}


def test_restart_discards_legacy_persisted_retry_without_generation(tmp_path):
    original = _orchestrator(tmp_path)
    original._save_state(
        retry_attempts={
            "task-1": {
                "issue_id": "task-1",
                "identifier": "TASK-1",
                "attempt": 1,
                "project_id": "project-a",
                "due_at_epoch_ms": 0,
            }
        }
    )
    restarted = _orchestrator(tmp_path)
    restarted._fetch_retry_issue = MagicMock(return_value=_issue())

    asyncio.run(restarted._restore_persisted_retries())

    restarted._fetch_retry_issue.assert_not_called()
    assert restarted.state.retry_attempts == {}
    assert restarted._load_state().get("retry_attempts") == {}


def test_restart_repersist_valid_retry_after_rearming(tmp_path):
    original = _orchestrator(tmp_path)
    _schedule(original, _issue())
    restarted = _orchestrator(tmp_path)
    restarted._fetch_retry_issue = MagicMock(return_value=_issue())

    asyncio.run(restarted._restore_persisted_retries())

    persisted = restarted._load_state().get("retry_attempts")
    assert set(persisted) == {"task-1"}
    assert persisted["task-1"]["authority_generation"]


def test_restart_after_open_status_claim_starts_replacement_worker_once(tmp_path):
    async def scenario():
        original = _orchestrator(tmp_path)
        issue = _issue(state="Open")
        retry = _schedule(original, issue)
        # The dispatcher persists this intent before writing In Progress.  A
        # restart at this point must recognize the resulting active state as
        # self-authored and resume provider startup.
        retry.dispatch_status = "In Progress"
        retry.dispatch_assignment_id = "assignment-2"
        original._persist_retry_entries()

        restarted = _orchestrator(tmp_path)
        active_issue = replace(
            issue,
            state="In Progress",
            assignment_id="assignment-2",
        )
        restarted._fetch_retry_issue = MagicMock(return_value=active_issue)
        await restarted._restore_persisted_retries()

        restored = restarted.state.retry_attempts[issue.id]
        assert restored.dispatch_status == "In Progress"
        persisted = restarted._load_state()["retry_attempts"][issue.id]
        assert persisted["dispatch_status"] == "In Progress"
        assert persisted["dispatch_assignment_id"] == "assignment-2"

        tracker_state = {"state": "In Progress"}
        tracker = MagicMock()
        tracker.fetch_issue_states_by_ids.side_effect = lambda _ids: [
            replace(active_issue, state=tracker_state["state"])
        ]
        tracker.update_issue.side_effect = (
            lambda _identifier, *, status: tracker_state.update(state=status)
        )
        restarted._tracker_for_issue = MagicMock(return_value=tracker)
        restarted._match_agent_profile = MagicMock(
            return_value=MagicMock(name="deep", model_role="deep")
        )
        restarted._run_worker = AsyncMock()

        await restarted._on_retry_timer(issue.id)
        await asyncio.sleep(0)

        assert tracker_state["state"] == "In Progress"
        restarted._run_worker.assert_awaited_once()
        assert issue.id in restarted.state.running
        assert issue.id not in restarted.state.retry_attempts
        running = restarted.state.running.pop(issue.id)
        if running.worker_task is not None and not running.worker_task.done():
            running.worker_task.cancel()

    asyncio.run(scenario())


def test_restart_restores_dispatchable_state_when_claim_authority_drifted(tmp_path):
    async def scenario():
        original = _orchestrator(tmp_path)
        issue = _issue(state="Open")
        retry = _schedule(original, issue)
        retry.dispatch_status = "In Progress"
        original._persist_retry_entries()

        restarted = _orchestrator(tmp_path)
        tracker_state = {"state": "In Progress"}
        drifted = replace(
            issue,
            state="In Progress",
            work_branch="task/replacement",
        )
        tracker = MagicMock()
        tracker.fetch_issue_states_by_ids.side_effect = lambda _ids: [
            replace(drifted, state=tracker_state["state"])
        ]
        tracker.update_issue.side_effect = (
            lambda _identifier, *, status: tracker_state.update(state=status)
        )
        restarted._fetch_retry_issue = MagicMock(return_value=drifted)
        restarted._tracker_for_issue = MagicMock(return_value=tracker)

        await restarted._restore_persisted_retries()

        assert tracker_state["state"] == "Open"
        assert issue.id not in restarted.state.retry_attempts
        assert restarted._load_state().get("retry_attempts") == {}

    asyncio.run(scenario())


def test_workspace_head_is_revalidated_when_tracker_has_no_head(tmp_path):
    workspace = tmp_path / "worker"
    workspace.mkdir()
    orch = _orchestrator(tmp_path)
    issue = _issue(head_sha=None)
    entry = RunningEntry(
        worker_task=None,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        assignment_id="assignment-1",
        workspace_path=str(workspace),
    )
    with patch.object(Orchestrator, "_worktree_head", return_value="a" * 40):
        orch._schedule_retry(
            issue.id,
            attempt=1,
            identifier=issue.identifier,
            delay_ms=60_000,
            error="old divergence error",
            project_id=issue.project_id,
            context_entry=entry,
        )
        retry = orch.state.retry_attempts[issue.id]
        assert orch._retry_entry_matches_issue(_issue(head_sha=None), retry) is True

    with patch.object(Orchestrator, "_worktree_head", return_value="b" * 40):
        assert orch._retry_entry_matches_issue(_issue(head_sha=None), retry) is False


def test_api_status_authority_helper_ignores_noop_and_cancels_changed_status(
    tmp_path,
):
    orch = MagicMock()
    issue = _issue()

    _cancel_retry_for_authority_change(
        orch, issue, issue.identifier, issue.project_id, "In Progress", None
    )
    orch._cancel_retry_for_issue.assert_not_called()

    _cancel_retry_for_authority_change(
        orch, issue, issue.identifier, issue.project_id, "Needs Human", None
    )
    orch._cancel_retry_for_issue.assert_called_once_with(
        issue_id=issue.id,
        identifier=issue.identifier,
        project_id=issue.project_id,
        reason="task status changed",
    )


def test_legacy_retry_entries_remain_dispatchable(tmp_path):
    orch = _orchestrator(tmp_path)
    issue = _issue(state="Open", updated_at=None, head_sha=None)
    retry = RetryEntry(
        issue_id=issue.id,
        identifier=issue.identifier,
        attempt=1,
        due_at_ms=0,
        project_id=issue.project_id,
    )
    assert orch._retry_entry_matches_issue(issue, retry) is True
