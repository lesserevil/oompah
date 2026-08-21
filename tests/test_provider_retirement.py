"""Regressions for authoritative provider retirement (OOMPAH-701)."""

from __future__ import annotations

import asyncio
import copy
import contextlib
import os
import signal
import subprocess
import threading
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oompah.agent import ProcessIdentity
from oompah.api_agent import _execute_tool
from oompah.authority_boundary import auditor_policy
from oompah.config import ServiceConfig
from oompah.implementation_workflow_adapter import OrchestratorImplementationEffects
from oompah.models import AgentProfile, Issue, RunningEntry
from oompah.orchestrator import Orchestrator
from oompah.projects import ProjectStore
from oompah.server import _submission_authority_lock
from oompah.statuses import IN_PROGRESS, IN_VALIDATION
from oompah.work_contributors import WorkContributor, load_contributors


def _orchestrator(tmp_path) -> Orchestrator:
    project_store = MagicMock()
    project_store.list_all.return_value = []
    return Orchestrator(
        config=ServiceConfig(
            workspace_root=str(tmp_path / "workspaces"),
            worker_termination_timeout_ms=100,
            duplicate_preflight_max_agents=0,
        ),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
    )


def _entry(
    *,
    state: str = IN_PROGRESS,
    auditor: bool = False,
    worker_task=None,
) -> RunningEntry:
    issue = Issue(
        id="issue-1",
        identifier="OOMPAH-701",
        title="Provider retirement",
        state=state,
        project_id="project-1",
    )
    if worker_task is None:
        worker_task = MagicMock()
        worker_task.done.return_value = True
    return RunningEntry(
        worker_task=worker_task,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        is_auditor=auditor,
        audit_id="audit-1" if auditor else None,
        audit_attempt_id="attempt-1" if auditor else None,
        branch_key="branch-1" if auditor else None,
        run_id="run-1",
        authority_generation="generation-1",
    )


def test_authority_revocation_from_api_thread_terminates_on_dispatch_loop(
    tmp_path,
) -> None:
    async def scenario() -> None:
        orch = _orchestrator(tmp_path)
        orch._dispatch_loop = asyncio.get_running_loop()
        worker = asyncio.create_task(asyncio.sleep(60))
        entry = _entry(worker_task=worker)
        orch.state.running[entry.issue.id] = entry
        orch.state.claimed.add(entry.issue.id)
        orch.state.claimed_issues[entry.issue.id] = entry.issue

        with (
            patch.object(orch, "_fire_task_cost_record"),
            patch.object(orch, "_fire_telemetry_comment"),
        ):
            await asyncio.to_thread(
                orch._cancel_retry_for_issue,
                issue_id=entry.issue.id,
                identifier=entry.identifier,
                project_id=entry.issue.project_id,
                reason="owner claimed task",
            )
            for _ in range(100):
                if entry.issue.id not in orch.state.running:
                    break
                await asyncio.sleep(0.01)

        assert worker.done()
        assert entry.issue.id not in orch.state.running
        assert entry.issue.id not in orch.state.claimed
        assert entry.issue.id not in orch.state.claimed_issues

    asyncio.run(scenario())


def test_running_snapshot_fences_concurrent_provider_exit_mutation(tmp_path) -> None:
    """Runtime snapshots finish before a provider-exit removal can mutate them."""

    orch = _orchestrator(tmp_path)
    implementation = _entry()
    implementation.issue.id = "implementation-1"
    auditor = _entry(state=IN_VALIDATION, auditor=True)
    auditor.issue.id = "auditor-1"

    snapshot_started = threading.Event()
    removal_attempted = threading.Event()
    release_snapshot = threading.Event()

    class _BlockingItemsDict(dict):
        def items(self):
            iterator = iter(super().items())
            first = next(iterator)
            yield first
            snapshot_started.set()
            assert release_snapshot.wait(timeout=2)
            yield from iterator

    running = _BlockingItemsDict(
        {
            implementation.issue.id: implementation,
            auditor.issue.id: auditor,
        }
    )
    orch.state.running = running

    def provider_exit() -> None:
        snapshot_started.wait(timeout=2)
        removal_attempted.set()
        orch._remove_running_entry(auditor.issue.id, auditor)

    snapshot_holder: dict[str, tuple[tuple[str, RunningEntry], ...]] = {}

    def take_snapshot() -> None:
        snapshot_holder["value"] = orch._running_items_snapshot()

    snapshotter = threading.Thread(target=take_snapshot)
    remover = threading.Thread(target=provider_exit)
    snapshotter.start()
    remover.start()
    try:
        snapshot_started.wait(timeout=2)
        assert removal_attempted.wait(timeout=2)
        # The provider-exit callback is blocked by the authority boundary while
        # the live dict iterator is being consumed.
        assert auditor.issue.id in running
        release_snapshot.set()
    finally:
        release_snapshot.set()
        snapshotter.join(timeout=2)
        remover.join(timeout=2)

    snapshot = snapshot_holder["value"]
    assert {issue_id for issue_id, _ in snapshot} == {
        implementation.issue.id,
        auditor.issue.id,
    }
    assert auditor.issue.id not in running


@pytest.mark.skipif(os.name != "posix", reason="requires Linux/POSIX process signals")
def test_revoked_run_stays_visible_until_provider_process_exits(tmp_path) -> None:
    async def scenario() -> None:
        orch = _orchestrator(tmp_path)
        workspace = tmp_path / "workspaces" / "OOMPAH-701"
        workspace.mkdir(parents=True)
        provider = subprocess.Popen(
            ["sh", "-c", "exec sleep 60"],
            cwd=workspace,
            start_new_session=True,
        )
        entry = _entry()
        entry.workspace_path = str(workspace)
        entry.authority_revoked = True
        orch.state.running[entry.issue.id] = entry
        orch.state.claimed.add(entry.issue.id)
        orch.state.claimed_issues[entry.issue.id] = entry.issue

        try:
            observed_visible = False

            def _terminate(captured, *, timeout_s):
                nonlocal observed_visible
                observed_visible = orch.state.running.get(entry.issue.id) is entry
                from oompah.agent import terminate_captured_processes

                return terminate_captured_processes(captured, timeout_s=timeout_s)

            with patch(
                "oompah.orchestrator.terminate_captured_processes",
                side_effect=_terminate,
            ):
                await orch._on_worker_exit(
                    entry.issue.id,
                    "authority_revoked",
                    None,
                    run_id=entry.run_id,
                )

            assert observed_visible is True
            assert provider.wait(timeout=2) < 0
            assert entry.issue.id not in orch.state.running
            assert entry.issue.id not in orch.state.claimed
        finally:
            if provider.poll() is None:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(provider.pid, signal.SIGKILL)
                provider.wait(timeout=2)

    asyncio.run(scenario())


@pytest.mark.asyncio
async def test_revoked_worker_capacity_release_rearms_exact_audit_without_event(
    tmp_path,
) -> None:
    """The revoked fast-exit path releases capacity through the CAS primitive."""

    orch = _orchestrator(tmp_path)
    orch._dispatch_loop = asyncio.get_running_loop()
    orch.state.max_concurrent_agents = 1
    entry = _entry()
    entry.authority_revoked = True
    orch.state.running[entry.issue.id] = entry
    orch.state.claimed.add(entry.issue.id)
    orch.state.claimed_issues[entry.issue.id] = entry.issue
    orch._record_terminal_audit_stage_wake(
        project_id="project-1",
        task_id="AUDIT-WAKE",
        audit_id="audit-successor",
    )
    dispatched = asyncio.Event()

    async def _scan(**_kwargs) -> dict[str, float]:
        if orch._available_slots() > 0:
            orch._retire_terminal_audit_stage_wake(
                project_id="project-1",
                task_id="AUDIT-WAKE",
                expected_audit_id="audit-successor",
                reason="test_dispatch",
            )
            dispatched.set()
        return {}

    with (
        patch.object(orch, "_dispatch_audit_lane", side_effect=_scan) as scan,
        patch.object(orch, "_managed_processes", return_value={}),
        patch.object(orch, "_notify_observers"),
    ):
        orch._wake_terminal_audit_continuation_lane_on_loop()
        first_owner = orch._terminal_audit_continuation_future
        assert first_owner is not None
        await asyncio.wait_for(first_owner, timeout=1)
        assert scan.await_count == 1
        assert not dispatched.is_set()

        await orch._on_worker_exit(
            entry.issue.id,
            "authority_revoked",
            None,
            run_id=entry.run_id,
        )
        await asyncio.wait_for(dispatched.wait(), timeout=1)
        await asyncio.sleep(0)

    assert entry.issue.id not in orch.state.running
    assert scan.await_count == 2
    assert orch._terminal_audit_stage_wakes_snapshot() == {}


def test_surviving_process_keeps_agent_and_audit_metrics_visible(tmp_path) -> None:
    async def scenario() -> None:
        orch = _orchestrator(tmp_path)
        try:
            entry = _entry(state=IN_VALIDATION, auditor=True)
            entry.workspace_path = str(tmp_path)
            entry.managed_processes = {
                12345: ProcessIdentity(12345, 99, 12345, 12345, str(tmp_path))
            }
            orch.state.running[entry.issue.id] = entry
            orch.state.claimed.add(entry.issue.id)
            orch._schedule_running_termination = MagicMock()

            with (
                patch(
                    "oompah.orchestrator.capture_workspace_processes",
                    return_value={},
                ),
                patch(
                    "oompah.orchestrator.terminate_captured_processes",
                    return_value={12345},
                ),
            ):
                await orch._on_worker_exit(
                    entry.issue.id,
                    "normal",
                    None,
                    run_id=entry.run_id,
                )

            snapshot = orch.get_snapshot()
            rows = {
                row["issue_id"]: row
                for row in snapshot["running"]
            }
            assert orch.state.running[entry.issue.id] is entry
            assert entry.issue.id in orch.state.claimed
            assert rows[entry.issue.id]["retiring"] is True
            assert rows[entry.issue.id]["managed_process_count"] == 1
            assert snapshot["terminal_audit"]["running"] == 1
            orch._schedule_running_termination.assert_called_once()
        finally:
            await orch._drain_background_work()
            orch.integration_queue.close()
            orch.coordination_store.close()

    asyncio.run(scenario())


def test_reconcile_retries_retirement_before_stall_handling(tmp_path) -> None:
    async def scenario() -> None:
        orch = _orchestrator(tmp_path)
        entry = _entry()
        entry.retirement_pending = True
        orch.state.running[entry.issue.id] = entry
        orch._reconcile_retry_authority = AsyncMock()
        orch._terminate_running = AsyncMock(return_value=True)

        await orch._reconcile()

        orch._terminate_running.assert_awaited_once_with(
            entry.issue.id,
            cleanup_workspace=False,
        )

    asyncio.run(scenario())


def test_startup_reaps_inherited_workspace_children_and_persists_evidence(
    tmp_path,
) -> None:
    orch = _orchestrator(tmp_path)
    captured = {
        12345: ProcessIdentity(12345, 99, 12345, 12345, str(tmp_path))
    }

    with (
        patch(
            "oompah.orchestrator.capture_workspace_processes",
            return_value=captured,
        ) as capture,
        patch(
            "oompah.orchestrator.terminate_captured_processes",
            return_value=set(),
        ) as terminate,
    ):
        asyncio.run(orch.startup_cleanup())

    capture.assert_called_once_with(orch.config.workspace_root)
    terminate.assert_called_once()
    recovery = orch._load_state()["orphan_process_recovery"]
    assert recovery["captured_count"] == 1
    assert recovery["survivor_pids"] == []
    assert (
        orch._maintenance_status["startup_cleanup"]["orphan_process_recovery"]
        == recovery
    )


def test_lifecycle_gate_prevents_launch_and_persists_exactly_one_recovery(
    tmp_path,
) -> None:
    orch = _orchestrator(tmp_path)
    entry = _entry()
    orch.state.running[entry.issue.id] = entry
    orch._quiesced = True

    assert orch._provider_launch_blocked(entry.issue, entry.run_id) is True
    assert orch._provider_launch_blocked(entry.issue, entry.run_id) is True

    assert entry.provider_started is False
    assert entry.authority_revoked is True
    assert entry.retirement_pending is True
    restart_issues = orch._load_state()["restart_issues"]
    assert restart_issues == [
        {
            "issue_id": entry.issue.id,
            "identifier": entry.identifier,
            "project_id": entry.issue.project_id,
        }
    ]


def test_pre_provider_evidence_timeout_releases_task_authority(tmp_path) -> None:
    async def scenario() -> None:
        orch = _orchestrator(tmp_path)
        orch.config.terminal_control_lock_timeout_seconds = 0.1
        orch.config.contributor_evidence_persist_timeout_seconds = 0.1
        entry = _entry()
        orch.state.running[entry.issue.id] = entry
        orch.provider_store.get = MagicMock(return_value=None)
        orch._reserve_auditor_for_contributor = AsyncMock(return_value=([], None))
        orch._release_audit_budget_reservation = MagicMock(return_value=True)
        persistence_started = threading.Event()
        release_persistence = threading.Event()

        def blocked_persistence(*_args, **_kwargs) -> None:
            persistence_started.set()
            release_persistence.wait(timeout=2)

        orch._persist_work_contributor = blocked_persistence
        staging = asyncio.create_task(
            orch._stage_work_contributor_launch(
                entry.issue,
                run_id=entry.run_id,
                provider_id="acp",
                provider_name="acp",
                model="sdk-managed",
            )
        )
        assert await asyncio.to_thread(persistence_started.wait, 0.5)
        submission_lane = asyncio.create_task(
            orch.issue_transition_lock(entry.issue.id).acquire(
                timeout_seconds=0.2
            )
        )
        error = await staging
        assert "bounded task-authority deadline" in str(error)
        assert await submission_lane
        orch.issue_transition_lock(entry.issue.id).release()
        assert entry.provider_started is False
        assert entry.session is None
        orch._release_audit_budget_reservation.assert_called_once()
        release_persistence.set()
        await asyncio.sleep(0)

    asyncio.run(scenario())


def test_contributor_evidence_takes_project_lock_before_policy_lock(tmp_path) -> None:
    """Contributor publication cannot invert ProjectStore.update lock order."""

    from oompah.auditor_policy_authority import AUDITOR_POLICY_AUTHORITY

    orch = _orchestrator(tmp_path)
    entry = _entry()
    project_lock = threading.RLock()
    orch.project_store.project_write_lock.return_value = project_lock
    metadata: dict[str, object] = {}
    tracker = MagicMock()
    tracker.get_metadata.side_effect = lambda _identifier: copy.deepcopy(metadata)
    tracker.set_metadata_field.side_effect = (
        lambda _identifier, key, value: metadata.__setitem__(key, copy.deepcopy(value))
    )
    orch._tracker_for_issue = MagicMock(return_value=tracker)
    policy_entries: list[bool] = []

    @contextlib.contextmanager
    def assert_project_lock_owned():
        # CPython's RLock ownership probe is exactly what matters here: the
        # inverse order deadlocked the live contributor writer against a
        # concurrent ProjectStore.update and wedged the scheduling API.
        policy_entries.append(project_lock._is_owned())
        assert project_lock._is_owned()
        yield

    contributor = WorkContributor(
        run_id="run-lock-order",
        provider_id="provider-1",
        provider_name="Provider One",
        model_id="model-1",
        focus="implementation",
        source_branch="OOMPAH-1202",
        source_sha=None,
        completed_at="",
    )
    with patch.object(
        AUDITOR_POLICY_AUTHORITY,
        "mutation",
        new=assert_project_lock_owned,
    ):
        orch._persist_work_contributor(entry.issue, contributor)

    assert policy_entries == [True]
    assert load_contributors(metadata) == [contributor]


def test_contributor_evidence_and_project_update_do_not_deadlock(tmp_path) -> None:
    """Exercise the production project -> policy order from both writers."""

    from oompah.models import Project
    from oompah.provenance_suppression import ProvenanceGuardedTracker

    store = ProjectStore(path=str(tmp_path / "projects.json"))
    project = Project(
        id="project-1",
        name="test-project",
        repo_url="https://github.com/example/project.git",
        repo_path=str(tmp_path / "repo"),
    )
    store._projects[project.id] = project
    orch = Orchestrator(
        config=ServiceConfig(
            workspace_root=str(tmp_path / "workspaces"),
            worker_termination_timeout_ms=100,
            duplicate_preflight_max_agents=0,
        ),
        workflow_path="WORKFLOW.md",
        project_store=store,
        state_path=str(tmp_path / "state.json"),
    )
    issue = _entry().issue
    issue.project_id = project.id
    metadata: dict[str, object] = {}
    raw_tracker = MagicMock()
    raw_tracker.get_metadata.side_effect = lambda _identifier: copy.deepcopy(metadata)
    raw_tracker.set_metadata_field.side_effect = (
        lambda _identifier, key, value: metadata.__setitem__(key, copy.deepcopy(value))
    )
    tracker = ProvenanceGuardedTracker(
        raw_tracker,
        project_store=store,
        project_id=project.id,
    )
    orch._project_trackers[project.id] = tracker
    contributor = WorkContributor(
        run_id="run-concurrent",
        provider_id="provider-1",
        provider_name="Provider One",
        model_id="model-1",
        focus="implementation",
        source_branch="OOMPAH-1202",
        source_sha=None,
        completed_at="",
    )
    project_lock_held = threading.Event()
    release_update = threading.Event()
    original_update = store._update_unlocked

    def blocked_update(*args, **kwargs):
        project_lock_held.set()
        assert release_update.wait(timeout=2)
        return original_update(*args, **kwargs)

    store._update_unlocked = blocked_update
    update_thread = threading.Thread(
        target=store.update,
        args=(project.id,),
        kwargs={"paused": True},
    )
    contributor_thread = threading.Thread(
        target=orch._persist_work_contributor,
        args=(issue, contributor),
    )
    update_thread.start()
    assert project_lock_held.wait(timeout=1)
    contributor_thread.start()
    release_update.set()
    update_thread.join(timeout=2)
    contributor_thread.join(timeout=2)

    assert not update_thread.is_alive()
    assert not contributor_thread.is_alive()
    assert load_contributors(metadata) == [contributor]


def test_pre_provider_timeout_exits_without_ghost_and_authority_lanes_continue(
    tmp_path,
) -> None:
    """The complete worker path retires its row before publishing a retry."""

    async def scenario() -> None:
        orch = _orchestrator(tmp_path)
        orch.config.terminal_control_lock_timeout_seconds = 0.1
        orch.config.contributor_evidence_persist_timeout_seconds = 0.1
        orch.workflow_runtime = SimpleNamespace(enforce=True)
        entry = _entry()
        orch.state.running[entry.issue.id] = entry
        orch.state.claimed.add(entry.issue.id)
        orch.state.claimed_issues[entry.issue.id] = entry.issue
        orch.provider_store.get = MagicMock(return_value=None)
        orch._resolve_dispatch_targets = MagicMock(return_value=[])
        orch._apply_project_provider_whitelist = MagicMock(
            side_effect=lambda targets, _issue: (targets, False)
        )
        orch._reserve_auditor_for_contributor = AsyncMock(return_value=([], None))
        orch._release_audit_budget_reservation = MagicMock(return_value=True)
        orch._run_acp_worker = AsyncMock()
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = entry.issue
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch._schedule_implementation_workflow_event = MagicMock(
            return_value=SimpleNamespace(job_id="retry-job")
        )
        orch._notify_observers = MagicMock()
        persistence_started = threading.Event()
        release_persistence = threading.Event()

        def blocked_persistence(*_args, **_kwargs) -> None:
            persistence_started.set()
            assert release_persistence.wait(timeout=2)

        orch._persist_work_contributor = blocked_persistence
        profile = AgentProfile(
            name="acp-test",
            command="",
            mode="acp",
            model="sdk-managed",
        )

        with (
            patch.object(orch, "_fire_task_cost_record"),
            patch.object(orch, "_fire_telemetry_comment"),
        ):
            worker = asyncio.create_task(
                orch._run_worker(
                    entry.issue,
                    attempt=0,
                    profile=profile,
                    run_id=entry.run_id,
                )
            )
            assert await asyncio.to_thread(persistence_started.wait, 0.5)
            await asyncio.wait_for(worker, timeout=0.5)

        assert entry.issue.id not in orch.state.running
        assert entry.issue.id not in orch.state.claimed
        assert entry.issue.id not in orch.state.claimed_issues
        orch._run_acp_worker.assert_not_awaited()
        retry_calls = [
            call.kwargs
            for call in orch._schedule_implementation_workflow_event.call_args_list
            if call.kwargs.get("action") == "implementation_retry"
        ]
        assert len(retry_calls) == 1

        effects = object.__new__(OrchestratorImplementationEffects)
        effects.orchestrator = orch
        async with effects._issue_authority_lane(entry.issue):
            pass
        async with _submission_authority_lock(orch, entry.issue.id):
            pass

        release_persistence.set()
        await asyncio.sleep(0)

    asyncio.run(scenario())


def test_late_pre_provider_write_settles_before_successor_provider_contact(
    tmp_path,
) -> None:
    """Late A cannot overwrite B's contributor identity after A retires."""

    async def scenario() -> None:
        orch = _orchestrator(tmp_path)
        orch.config.terminal_control_lock_timeout_seconds = 0.1
        orch.config.contributor_evidence_persist_timeout_seconds = 0.1
        issue = _entry().issue
        entry_a = _entry()
        entry_a.run_id = "run-a"
        orch.state.running[issue.id] = entry_a
        orch.provider_store.get = MagicMock(
            side_effect=lambda provider_id: SimpleNamespace(
                id=provider_id,
                name=provider_id,
                mode="api",
            )
        )
        orch._apply_project_provider_whitelist = MagicMock(
            side_effect=lambda targets, _issue: (targets, False)
        )
        orch._reserve_auditor_for_contributor = AsyncMock(
            side_effect=lambda _issue, targets, **_kwargs: (targets, None)
        )
        orch._release_audit_budget_reservation = MagicMock(return_value=True)

        store: dict[str, dict] = {}
        store_lock = threading.Lock()
        late_a_write_started = threading.Event()
        release_late_a = threading.Event()
        late_a_write_finished = threading.Event()
        tracker = MagicMock()

        def get_metadata(identifier: str) -> dict:
            with store_lock:
                return copy.deepcopy(store.get(identifier, {}))

        def set_metadata_field(identifier: str, key: str, value: object) -> None:
            provider_ids = {
                row.get("provider_id")
                for row in value.get("runs", [])
                if isinstance(row, dict)
            }
            if provider_ids == {"provider-a"}:
                late_a_write_started.set()
                assert release_late_a.wait(timeout=2)
            with store_lock:
                store.setdefault(identifier, {})[key] = copy.deepcopy(value)
            if provider_ids == {"provider-a"}:
                late_a_write_finished.set()

        tracker.get_metadata.side_effect = get_metadata
        tracker.set_metadata_field.side_effect = set_metadata_field
        orch._project_trackers[issue.project_id] = tracker

        stage_a = asyncio.create_task(
            orch._stage_work_contributor_launch(
                issue,
                run_id="run-a",
                provider_id="provider-a",
                provider_name="Provider A",
                model="model-a",
            )
        )
        assert await asyncio.to_thread(late_a_write_started.wait, 0.5)
        error_a = await stage_a
        assert "bounded task-authority deadline" in str(error_a)

        entry_b = _entry()
        entry_b.run_id = "run-b"
        orch.state.running[issue.id] = entry_b
        error_b_while_a_is_late = await orch._stage_work_contributor_launch(
            issue,
            run_id="run-b",
            provider_id="provider-b",
            provider_name="Provider B",
            model="model-b",
        )
        assert "Prior contributor evidence is still settling" in str(
            error_b_while_a_is_late
        )
        assert tracker.set_metadata_field.call_count == 1

        release_late_a.set()
        assert await asyncio.to_thread(late_a_write_finished.wait, 0.5)
        for _ in range(50):
            if not orch._work_contributor_lock(issue.id).locked():
                break
            await asyncio.sleep(0.01)

        error_b = await orch._stage_work_contributor_launch(
            issue,
            run_id="run-b",
            provider_id="provider-b",
            provider_name="Provider B",
            model="model-b",
        )
        assert error_b is None
        contributors = load_contributors(store[issue.identifier])
        assert {contributor.provider_id for contributor in contributors} == {
            "provider-a",
            "provider-b",
        }

    asyncio.run(scenario())


@pytest.mark.parametrize("late_tracker_failure", [False, True])
def test_cancelled_pre_provider_evidence_releases_task_authority(
    tmp_path,
    late_tracker_failure,
) -> None:
    async def scenario() -> None:
        orch = _orchestrator(tmp_path)
        orch.config.terminal_control_lock_timeout_seconds = 0.1
        orch.config.contributor_evidence_persist_timeout_seconds = 0.1
        entry = _entry()
        orch.state.running[entry.issue.id] = entry
        orch.provider_store.get = MagicMock(return_value=None)
        orch._reserve_auditor_for_contributor = AsyncMock(return_value=([], None))
        persistence_started = threading.Event()
        release_persistence = threading.Event()

        def blocked_persistence(*_args, **_kwargs) -> None:
            persistence_started.set()
            release_persistence.wait(timeout=2)
            if late_tracker_failure:
                raise RuntimeError("late tracker failure")

        orch._persist_work_contributor = blocked_persistence
        staging = asyncio.create_task(
            orch._stage_work_contributor_launch(
                entry.issue,
                run_id=entry.run_id,
                provider_id="acp",
                provider_name="acp",
                model="sdk-managed",
            )
        )
        assert await asyncio.to_thread(persistence_started.wait, 0.5)
        staging.cancel()
        if late_tracker_failure:
            release_persistence.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(staging, timeout=0.3)

        lock = orch.issue_transition_lock(entry.issue.id)
        assert await lock.acquire(timeout_seconds=0.1)
        lock.release()
        assert entry.provider_started is False
        assert entry.session is None
        release_persistence.set()
        await asyncio.sleep(0)

    asyncio.run(scenario())


def test_restart_journal_failure_installs_durable_retry_and_fails_closed(
    tmp_path,
) -> None:
    """Setup retirement cannot become process-only when state save fails."""

    async def scenario() -> None:
        orch = _orchestrator(tmp_path)
        entry = _entry()
        orch.state.running[entry.issue.id] = entry
        orch._quiesced = True

        with patch.object(orch, "_save_state", return_value=False):
            blocked = orch._provider_launch_blocked(entry.issue, entry.run_id)

        assert blocked is True
        assert orch._restart_persistence_failed is True
        assert orch._quiesced is True
        assert entry.authority_revoked is True
        retry = orch.state.retry_attempts[entry.issue.id]
        assert retry.pre_admission_recovery is True
        assert retry.dispatch_status == IN_PROGRESS
        assert retry.timer_handle is None

        replacement = _orchestrator(tmp_path)
        restored = next(
            persisted
            for persisted in replacement._persisted_retry_entries
            if persisted.issue_id == entry.issue.id
        )
        assert restored.authority_generation == retry.authority_generation
        assert restored.pre_admission_recovery is True
        assert restored.dispatch_status == IN_PROGRESS
        orch._cancel_retry_for_issue(
            issue_id=entry.issue.id,
            reason="test cleanup",
        )

    asyncio.run(scenario())


def test_lifecycle_gate_does_not_persist_a_superseded_generation(tmp_path) -> None:
    orch = _orchestrator(tmp_path)
    replacement = _entry()
    replacement.run_id = "run-new"
    orch.state.running[replacement.issue.id] = replacement
    orch._quiesced = True

    assert orch._provider_launch_blocked(replacement.issue, "run-old") is True

    assert "restart_issues" not in orch._load_state()
    assert replacement.authority_revoked is False
    assert replacement.retirement_pending is False


def test_claude_tool_catalog_reports_read_only_shell_denials(tmp_path) -> None:
    pytest.importorskip("claude_agent_sdk")
    from oompah.acp_tools import build_tool_catalog

    denials: list[str] = []
    catalog = build_tool_catalog(
        str(tmp_path),
        action_policy=auditor_policy(task_identifier="OOMPAH-701"),
        auditor=True,
        policy_denial_handler=denials.append,
    )
    run_command = next(tool for tool in catalog if tool.name == "run_command")

    result = asyncio.run(
        run_command.handler({"command": "git commit -am forbidden"})
    )

    assert result["content"][0]["text"].startswith("Error:")
    assert len(denials) == 1
    assert "read-only" in denials[0]


def test_repeated_auditor_shell_denials_force_bounded_independent_retry(
    tmp_path,
) -> None:
    orch = _orchestrator(tmp_path)
    entry = _entry(state=IN_VALIDATION, auditor=True)
    orch.state.running[entry.issue.id] = entry
    orch._schedule_running_termination = MagicMock()

    for _ in range(3):
        result = _execute_tool(
            tmp_path,
            "run_command",
            {"command": "git commit -am forbidden"},
            action_policy=auditor_policy(
                task_identifier=entry.identifier,
                project_id=entry.issue.project_id,
            ),
            policy_denial_handler=lambda denial: orch._record_auditor_policy_denial(
                entry.issue.id,
                entry.run_id,
                denial,
            ),
        )
        assert result.startswith("Error:")

    assert entry.policy_denial_count == 3
    assert entry.retirement_pending is True
    assert entry.forced_exit_reason == "auditor_policy_denial_exhausted"
    orch._schedule_running_termination.assert_called_once_with(
        entry.issue.id,
        cleanup_workspace=False,
        task_name_prefix="retire-policy-loop",
        expected_entry=entry,
    )


def test_recoverable_read_only_inspection_validation_does_not_rotate_auditor(
    tmp_path,
) -> None:
    orch = _orchestrator(tmp_path)
    entry = _entry(state=IN_VALIDATION, auditor=True)
    orch.state.running[entry.issue.id] = entry
    orch._schedule_running_termination = MagicMock()
    commands = (
        "awk 'NR>=7790 && NR<=7900' oompah/orchestrator.py",
        "sed -n '7790,7900p' oompah/orchestrator.py",
        "git ls-tree -r --name-only HEAD",
        "git ls-tree HEAD -- oompah/auditor.py",
        "git ls-tree --full-tree -r HEAD oompah",
        "git ls-remote origin refs/heads/main refs/heads/task-branch",
        "git for-each-ref --format='%(refname:short)' refs/remotes/origin/",
        "wc -l oompah/projects.py",
    )

    for command in commands:
        result = _execute_tool(
            tmp_path,
            "run_command",
            {"command": command},
            action_policy=auditor_policy(
                task_identifier=entry.identifier,
                project_id=entry.issue.project_id,
            ),
            policy_denial_handler=lambda denial: orch._record_auditor_policy_denial(
                entry.issue.id,
                entry.run_id,
                denial,
            ),
        )
        assert result.startswith("Error:")

    assert entry.policy_denial_count == 0
    assert entry.retirement_pending is False
    assert entry.forced_exit_reason is None
    orch._schedule_running_termination.assert_not_called()


def test_forced_auditor_retirement_records_retry_before_releasing_claim(
    tmp_path,
) -> None:
    async def scenario() -> None:
        orch = _orchestrator(tmp_path)
        entry = _entry(state=IN_VALIDATION, auditor=True)
        # A policy denial is emitted by a provider that was already admitted;
        # it must follow the forced-attempt finalization path, not the
        # pre-provider rollback path.
        entry.provider_started = True
        entry.forced_exit_reason = "auditor_policy_denial_exhausted"
        entry.forced_exit_error = "bounded denial failure"
        orch.state.running[entry.issue.id] = entry
        orch.state.claimed.add(entry.issue.id)
        orch._audit_branch_claims[entry.branch_key] = entry.audit_attempt_id
        orch._finish_audit_attempt = MagicMock(return_value=True)

        with (
            patch.object(orch, "_fire_task_cost_record"),
            patch.object(orch, "_fire_telemetry_comment"),
            patch.object(orch, "_post_comment"),
        ):
            assert await orch._terminate_running(
                entry.issue.id,
                cleanup_workspace=False,
            )

        orch._finish_audit_attempt.assert_called_once_with(
            entry,
            "auditor_policy_denial_exhausted",
            "bounded denial failure",
        )
        assert entry.issue.id not in orch.state.running
        assert entry.issue.id not in orch.state.claimed
        assert entry.branch_key not in orch._audit_branch_claims

    asyncio.run(scenario())


def test_contributor_evidence_timeout_defaults_to_30_seconds(tmp_path) -> None:
    """Verify that when contributor_evidence_persist_timeout_seconds is not
    explicitly configured, it defaults to 30.0 seconds instead of falling back
    to the derived floor of 5.0 seconds. Regression test for OOMPAH-1318."""
    
    async def scenario() -> None:
        # Create an orchestrator without explicitly setting
        # contributor_evidence_persist_timeout_seconds
        orch = _orchestrator(tmp_path)
        
        # Verify that the config has the attribute with default value
        assert hasattr(orch.config, 'contributor_evidence_persist_timeout_seconds')
        assert orch.config.contributor_evidence_persist_timeout_seconds == 30.0
        
        # Also test with a fresh config to ensure the default is used
        from oompah.config import ServiceConfig
        config = ServiceConfig(
            workspace_root=str(tmp_path / "workspaces"),
            worker_termination_timeout_ms=100,
        )
        assert config.contributor_evidence_persist_timeout_seconds == 30.0
        
        # The timeout should not be the derived floor of 5.0
        # (which would be min(5.0, 100/2000) = min(5.0, 0.05) = 0.05,
        # then max(0.05, 0.05) = 0.05, but that's wrong - let me recalculate)
        # Actually: control=5.0, termination=100/1000=0.1
        # min(5.0, 0.1/2) = min(5.0, 0.05) = 0.05
        # max(0.05, 0.05) = 0.05
        # But in the real flow with default 10_000ms:
        # control=5.0, termination=10.0
        # min(5.0, 10.0/2) = min(5.0, 5.0) = 5.0
        # max(5.0, 0.05) = 5.0
        # So the derived floor would be 5.0 seconds
        # But with our fix, getattr defaults to 30.0, so it should be 30.0
        
    asyncio.run(scenario())
