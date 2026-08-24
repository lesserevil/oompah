"""Architectural fences for the retired process-local workflow owners."""

from __future__ import annotations

import ast
import asyncio
import inspect
import textwrap
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from oompah.orchestrator import DispatchEventType, Orchestrator


_RETIRED_LIFECYCLE_CALLS = {
    "_ensure_integration_lane",
    "_ensure_integration_audit_lane",
    "_reconcile_pending_recovery_publications",
    "_reconcile_standalone_ready_to_integrate_tasks",
    "_schedule_terminal_lifecycle_reconciliation",
    "_recover_release_addendum_leases",
    "_handle_reconcile",
    "_handle_review_check",
    "_handle_dispatch_needed",
    "_handle_yolo_review",
    "_maybe_run_watchdog",
    "_run_workflow_shadow_sweep",
    "_run_workflow_controller_sweep",
    "_run_step5b_maintenance",
    "_run_step5c_epic_maintenance",
}


def _method_tree(method) -> ast.AsyncFunctionDef | ast.FunctionDef:
    tree = ast.parse(textwrap.dedent(inspect.getsource(method)))
    node = tree.body[0]
    assert isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef))
    return node


def _self_calls(method) -> set[str]:
    return {
        node.func.attr
        for node in ast.walk(_method_tree(method))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "self"
    }


def _self_attributes(method) -> set[str]:
    return {
        node.attr
        for node in ast.walk(_method_tree(method))
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    }


def test_durable_tick_cannot_call_retired_lifecycle_owners() -> None:
    calls = _self_calls(Orchestrator._run_durable_workflow_tick)
    audit_calls = _self_calls(Orchestrator._run_terminal_audit_tick_phase)
    restart_calls = _self_calls(Orchestrator._run_restart_reconstruction_tick)

    assert calls.isdisjoint(_RETIRED_LIFECYCLE_CALLS)
    assert "_run_terminal_audit_tick_phase" in calls
    assert "_run_restart_reconstruction_tick" in calls
    assert audit_calls.isdisjoint(_RETIRED_LIFECYCLE_CALLS)
    assert restart_calls.isdisjoint(_RETIRED_LIFECYCLE_CALLS)
    assert "_dispatch_audit_lane" in audit_calls
    assert "_run_non_lifecycle_housekeeping" in _self_attributes(
        Orchestrator._run_durable_workflow_tick
    )


def test_rollout_mode_is_not_a_legacy_authority_switch() -> None:
    assert "workflow_runtime.enforce" not in inspect.getsource(Orchestrator)


def test_durable_tick_has_bounded_branch_and_line_complexity() -> None:
    method = _method_tree(Orchestrator._run_durable_workflow_tick)
    branches = sum(
        isinstance(node, (ast.If, ast.IfExp, ast.For, ast.While, ast.Try))
        for node in ast.walk(method)
    )

    assert method.end_lineno is not None
    assert method.end_lineno - method.lineno + 1 <= 80
    assert branches <= 8


def test_production_ownership_boundary_precedes_legacy_fixture_harness() -> None:
    method = _method_tree(Orchestrator._tick)
    boundary = next(
        statement
        for statement in method.body
        if isinstance(statement, ast.If)
        and "self.workflow_runtime is not None" in ast.unparse(statement.test)
    )
    calls = {
        node.func.attr
        for node in ast.walk(boundary)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "self"
    }

    assert calls == {"_run_durable_workflow_tick"}
    assert any(isinstance(statement, ast.Return) for statement in boundary.body)


def test_runtime_bound_startup_cannot_arm_process_local_lifecycle_owners() -> None:
    method = _method_tree(Orchestrator._run_event_loop)
    retired_startup_calls = {
        "_wake_integration_lane",
        "_reconcile_owner_duplicate_resolution_boundaries",
        "_ensure_integration_audit_lane",
        "_schedule_terminal_lifecycle_reconciliation",
        "_reconcile_pending_recovery_publications",
        "_schedule_restart_issue_recovery_for_resume",
    }

    unguarded: set[str] = set()

    def visit(statement: ast.AST, *, legacy_guarded: bool = False) -> None:
        guarded = legacy_guarded or (
            isinstance(statement, ast.If)
            and "not runtime_bound" in ast.unparse(statement.test)
        )
        if isinstance(statement, ast.Call):
            function = statement.func
            if (
                isinstance(function, ast.Attribute)
                and isinstance(function.value, ast.Name)
                and function.value.id == "self"
                and function.attr in retired_startup_calls
                and not guarded
            ):
                unguarded.add(function.attr)
        for child in ast.iter_child_nodes(statement):
            visit(child, legacy_guarded=guarded)

    visit(method)
    assert unguarded == set()
    calls = _self_calls(Orchestrator._run_event_loop)
    assert "_recover_restart_issues" in calls
    assert "_restore_persisted_retries" in calls


def test_housekeeping_bundle_contains_only_non_lifecycle_operations() -> None:
    assert _self_calls(Orchestrator._run_non_lifecycle_housekeeping) == {
        "_maybe_heal_repos",
        "_maybe_cleanup_worktrees",
        "_maybe_cleanup_storage",
        "_run_maintenance_job",
        "_update_repo_hygiene_health",
    }


def test_runtime_housekeeping_schedules_owner_claim_retirement() -> None:
    orchestrator = object.__new__(Orchestrator)
    orchestrator._maybe_heal_repos = Mock()
    orchestrator._maybe_cleanup_worktrees = Mock()
    orchestrator._maybe_cleanup_storage = Mock()
    orchestrator._reconcile_inactive_owner_claims = Mock()
    orchestrator._archive_workflow_events = Mock()
    orchestrator._run_maintenance_job = Mock()
    orchestrator._update_repo_hygiene_health = Mock()

    orchestrator._run_non_lifecycle_housekeeping()

    orchestrator._run_maintenance_job.assert_any_call(
        "owner_claim_retirements",
        orchestrator._reconcile_inactive_owner_claims,
        min_interval_s=60.0,
    )
    orchestrator._run_maintenance_job.assert_any_call(
        "workflow_event_archival",
        orchestrator._archive_workflow_events,
        min_interval_s=300.0,
    )


@pytest.mark.parametrize("mode", ["off", "shadow", "enforce"])
def test_legacy_event_conversion_always_targets_durable_ledger(mode: str) -> None:
    scheduled = SimpleNamespace(job_id="job-1")
    controller = SimpleNamespace(schedule_event=Mock(return_value=scheduled))
    runtime = SimpleNamespace(
        mode=mode,
        project_bindings={
            "project-1": SimpleNamespace(implementation_controller=controller)
        },
    )
    orchestrator = object.__new__(Orchestrator)
    orchestrator.workflow_runtime = runtime
    orchestrator.request_refresh = Mock()

    result = orchestrator._schedule_implementation_workflow_event(
        project_id="project-1",
        identifier="TASK-1",
        action="implementation_retry",
        payload={"attempt": 2},
        expected_evidence_revision="revision-1",
        priority=20,
    )

    assert result is scheduled
    controller.schedule_event.assert_called_once_with(
        project_id="project-1",
        task_id="TASK-1",
        action="implementation_retry",
        payload={"attempt": 2},
        expected_evidence_revision="revision-1",
        expected_head_sha=None,
        priority=20,
    )
    orchestrator.request_refresh.assert_called_once_with()


def test_control_event_wakes_reserved_admission_instead_of_world_scan() -> None:
    scheduled = SimpleNamespace(
        job_id="job-control",
        action="direct_owner_claim",
    )
    controller = SimpleNamespace(schedule_event=Mock(return_value=scheduled))
    runtime = SimpleNamespace(
        mode="enforce",
        project_bindings={
            "project-1": SimpleNamespace(implementation_controller=controller)
        },
        is_control_action=Mock(return_value=True),
    )
    orchestrator = object.__new__(Orchestrator)
    orchestrator.workflow_runtime = runtime
    orchestrator.request_refresh = Mock()
    orchestrator._request_workflow_batch_continuation = Mock(return_value=True)

    result = orchestrator._schedule_implementation_workflow_event(
        project_id="project-1",
        identifier="TASK-CONTROL",
        action="direct_owner_claim",
        priority=0,
    )

    assert result is scheduled
    runtime.is_control_action.assert_called_once_with("direct_owner_claim")
    orchestrator._request_workflow_batch_continuation.assert_called_once_with(
        reason="workflow_control_event:direct_owner_claim"
    )
    orchestrator.request_refresh.assert_not_called()


@pytest.mark.parametrize("mode", ["off", "shadow", "enforce"])
def test_runtime_refresh_does_not_wake_legacy_integration_future(mode: str) -> None:
    orchestrator = object.__new__(Orchestrator)
    orchestrator.workflow_runtime = SimpleNamespace(mode=mode)
    orchestrator._post_dispatch_refresh = Mock()
    orchestrator._wake_integration_lane = Mock()

    orchestrator.request_refresh()

    orchestrator._post_dispatch_refresh.assert_called_once_with()
    orchestrator._wake_integration_lane.assert_not_called()


def test_saturated_runtime_batch_requests_one_follow_up_tick() -> None:
    runtime = SimpleNamespace(
        mode="enforce",
        started=True,
        worker=SimpleNamespace(accepting=True),
        start=AsyncMock(),
        reconcile_async=AsyncMock(
            return_value={"worker": {"processed": 32, "batch_saturated": True}}
        ),
    )
    orchestrator = object.__new__(Orchestrator)
    orchestrator.workflow_runtime = runtime
    orchestrator.config = SimpleNamespace(full_sync_interval_ms=30_000)
    orchestrator._terminal_audit_started = False
    orchestrator._terminal_audit_last_scan = 0.0
    orchestrator._monotonic_clock = Mock(side_effect=[10.0, 10.01])
    orchestrator._dispatch_audit_lane = AsyncMock(return_value={"pending": 0})
    orchestrator._request_workflow_batch_continuation = Mock(return_value=True)
    orchestrator._maintenance_future = None
    orchestrator._run_non_lifecycle_housekeeping = Mock()
    orchestrator._notify_observers = Mock()
    orchestrator._handle_auto_update = AsyncMock()
    orchestrator._tick_pool = ThreadPoolExecutor(max_workers=1)

    try:
        with patch(
            "oompah.orchestrator.validate_dispatch_config", return_value=[]
        ):
            asyncio.run(orchestrator._run_durable_workflow_tick(started_at=10.0))
    finally:
        orchestrator._tick_pool.shutdown(wait=True)

    orchestrator._request_workflow_batch_continuation.assert_called_once_with()
    assert orchestrator._last_tick_metrics["workflow_batch_saturated"] is True
    assert (
        orchestrator._last_tick_metrics[
            "workflow_batch_continuation_requested"
        ]
        is True
    )


def test_superseded_publication_requests_one_full_reconcile_tick() -> None:
    runtime = SimpleNamespace(
        mode="enforce",
        started=True,
        worker=SimpleNamespace(accepting=True),
        start=AsyncMock(),
        reconcile_async=AsyncMock(
            return_value={
                "requires_reconcile": True,
                "reconcile_reason": "publication_authority_changed",
            }
        ),
        restart_reconstruction_pending=True,
    )
    orchestrator = object.__new__(Orchestrator)
    orchestrator.workflow_runtime = runtime
    orchestrator.config = SimpleNamespace(full_sync_interval_ms=30_000)
    orchestrator._terminal_audit_started = False
    orchestrator._terminal_audit_last_scan = 0.0
    orchestrator._monotonic_clock = Mock(side_effect=[10.0, 10.01])
    orchestrator._dispatch_audit_lane = AsyncMock(return_value={"pending": 0})
    orchestrator._request_workflow_reconcile_continuation = Mock(
        return_value=True
    )
    orchestrator._request_workflow_batch_continuation = Mock(return_value=True)
    orchestrator._maintenance_future = None
    orchestrator._run_non_lifecycle_housekeeping = Mock()
    orchestrator._notify_observers = Mock()
    orchestrator._handle_auto_update = AsyncMock()
    orchestrator._tick_pool = ThreadPoolExecutor(max_workers=1)

    try:
        with patch(
            "oompah.orchestrator.validate_dispatch_config", return_value=[]
        ):
            asyncio.run(orchestrator._run_durable_workflow_tick(started_at=10.0))
    finally:
        orchestrator._tick_pool.shutdown(wait=True)

    orchestrator._request_workflow_reconcile_continuation.assert_called_once_with(
        reason="publication_authority_changed"
    )
    orchestrator._request_workflow_batch_continuation.assert_not_called()
    runtime.reconcile_async.assert_awaited_once_with(admit_workers=False)
    orchestrator._dispatch_audit_lane.assert_awaited_once_with(
        allow_new_launches=False
    )
    assert (
        orchestrator._last_tick_metrics[
            "workflow_reconcile_continuation_requested"
        ]
        is True
    )


def test_exhausted_superseded_publication_does_not_hot_loop() -> None:
    runtime = SimpleNamespace(
        restart_reconstruction_pending=True,
        reconcile_async=AsyncMock(
            return_value={
                "requires_reconcile": True,
                "reconcile_reason": "publication_authority_changed",
                "restart_deadline_exceeded": True,
                "worker": {
                    "skipped": True,
                    "reason": (
                        "workflow publication requires reconciliation before "
                        "durable admission"
                    ),
                },
            }
        ),
        continue_admission_async=AsyncMock(),
    )
    orchestrator = object.__new__(Orchestrator)
    orchestrator._run_terminal_audit_tick_phase = AsyncMock(
        return_value={"pending": 0}
    )
    orchestrator._request_workflow_reconcile_continuation = Mock(
        return_value=True
    )

    _report, _audit_metrics, continuation_requested = asyncio.run(
        orchestrator._run_restart_reconstruction_tick(runtime)
    )

    assert continuation_requested is False
    orchestrator._request_workflow_reconcile_continuation.assert_not_called()
    runtime.continue_admission_async.assert_not_awaited()


def test_incomplete_restart_reconstruction_requests_follow_up_cut() -> None:
    order: list[str] = []
    reports = iter(
        (
            {
                "projects": {
                    "project-a": {
                        "implementation": {"truncated": False},
                        "integration": {"truncated": True},
                    }
                },
                "liveness": {
                    "scan_complete": False,
                    "status": "action_required",
                },
                "worker": {
                    "skipped": True,
                    "reason": (
                        "workflow worker admission deferred until the restart "
                        "audit-priority boundary"
                    ),
                },
            },
            {
                "liveness": {"scan_complete": True, "status": "healthy"},
                "worker": {},
            },
        )
    )
    runtime = SimpleNamespace(
        worker=SimpleNamespace(accepting=True),
        restart_reconstruction_pending=True,
        continue_admission_async=AsyncMock(
            side_effect=lambda: order.append("workflow_admission")
            or {"worker": {"processed": 1}}
        ),
    )

    async def reconcile_async(*, admit_workers):
        assert admit_workers is False
        report = next(reports)
        order.append(
            "reconcile_incomplete"
            if report["liveness"]["scan_complete"] is False
            else "reconcile_complete"
        )
        runtime.restart_reconstruction_pending = not report["liveness"][
            "scan_complete"
        ]
        return report

    runtime.reconcile_async = AsyncMock(side_effect=reconcile_async)
    orchestrator = object.__new__(Orchestrator)
    orchestrator.workflow_runtime = runtime
    orchestrator._run_terminal_audit_tick_phase = AsyncMock(
        side_effect=lambda **kwargs: order.append(
            "audit_recovery"
            if kwargs["allow_new_launches"] is False
            else "audit_launch"
        )
        or {"pending": 0}
    )
    orchestrator._request_workflow_reconcile_continuation = Mock(
        return_value=True
    )

    async def scenario() -> tuple[bool, bool]:
        first = await orchestrator._run_restart_reconstruction_tick(runtime)
        second = await orchestrator._run_restart_reconstruction_tick(runtime)
        return first[2], second[2]

    first_continuation, second_continuation = asyncio.run(scenario())

    assert first_continuation is True
    assert second_continuation is False
    orchestrator._request_workflow_reconcile_continuation.assert_called_once_with(
        reason="workflow_restart_reconstruction_incomplete"
    )
    assert order == [
        "audit_recovery",
        "reconcile_incomplete",
        "audit_recovery",
        "reconcile_complete",
        "audit_launch",
        "workflow_admission",
    ]
    runtime.continue_admission_async.assert_awaited_once_with()


def test_restart_source_error_does_not_request_immediate_retry_loop() -> None:
    runtime = SimpleNamespace(
        restart_reconstruction_pending=True,
        reconcile_async=AsyncMock(
            return_value={
                "projects": {"project-a": {"error": "TimeoutError"}},
                "liveness": {
                    "scan_complete": False,
                    "status": "action_required",
                },
            }
        ),
        continue_admission_async=AsyncMock(),
    )
    orchestrator = object.__new__(Orchestrator)
    orchestrator._run_terminal_audit_tick_phase = AsyncMock(
        return_value={"pending": 0}
    )
    orchestrator._request_workflow_reconcile_continuation = Mock(
        return_value=True
    )

    _report, _audit_metrics, continuation_requested = asyncio.run(
        orchestrator._run_restart_reconstruction_tick(runtime)
    )

    assert continuation_requested is False
    orchestrator._request_workflow_reconcile_continuation.assert_not_called()
    runtime.continue_admission_async.assert_not_awaited()


def test_restart_audit_recovery_precedes_reconcile_exception() -> None:
    order: list[str] = []

    async def reconcile_async(*, admit_workers):
        assert admit_workers is False
        order.append("reconcile")
        raise RuntimeError("source scan failed")

    runtime = SimpleNamespace(
        mode="enforce",
        started=True,
        worker=SimpleNamespace(accepting=True),
        start=AsyncMock(),
        reconcile_async=AsyncMock(side_effect=reconcile_async),
        restart_reconstruction_pending=True,
    )
    orchestrator = object.__new__(Orchestrator)
    orchestrator.workflow_runtime = runtime
    orchestrator.config = SimpleNamespace(full_sync_interval_ms=30_000)
    orchestrator._terminal_audit_started = False
    orchestrator._terminal_audit_last_scan = 0.0
    orchestrator._dispatch_audit_lane = AsyncMock(
        side_effect=lambda **kwargs: order.append(
            "audit_recovery"
            if kwargs["allow_new_launches"] is False
            else "audit_launch"
        )
        or {"audit_dispatch": 0.0, "audit_scan": 0.0}
    )

    with (
        patch("oompah.orchestrator.validate_dispatch_config", return_value=[]),
        pytest.raises(RuntimeError, match="source scan failed"),
    ):
        asyncio.run(orchestrator._run_durable_workflow_tick(started_at=0.0))

    assert order == ["audit_recovery", "reconcile"]
    orchestrator._dispatch_audit_lane.assert_awaited_once_with(
        allow_new_launches=False
    )


def test_restart_reconstruction_publishes_before_auditor_tracker_write() -> None:
    """A multi-minute-equivalent first scan owns publication before launch."""

    logical_clock = {"seconds": 0.0}
    tracker_authority = {"revision": 1}
    scan_started: asyncio.Event
    writer_tasks: list[asyncio.Task[None]] = []
    order: list[str] = []
    audit_owned = {"value": False}
    runtime = SimpleNamespace(
        mode="enforce",
        started=True,
        worker=SimpleNamespace(accepting=True),
        start=AsyncMock(),
        restart_reconstruction_pending=True,
        continue_admission_async=AsyncMock(
            side_effect=lambda: order.append("workflow_admission")
            or {"worker": {}, "requires_reconcile": False}
        ),
    )

    async def reconcile_async(*, admit_workers):
        assert admit_workers is False
        order.append("reconcile_started")
        observed_revision = tracker_authority["revision"]
        scan_started.set()
        logical_clock["seconds"] = 200.0
        await asyncio.sleep(0)
        if tracker_authority["revision"] != observed_revision:
            order.append("publication_superseded")
            return {
                "requires_reconcile": True,
                "reconcile_reason": "publication_authority_changed",
            }
        runtime.restart_reconstruction_pending = False
        order.append("publication_committed")
        return {"liveness": {"status": "healthy"}, "worker": {}}

    runtime.reconcile_async = AsyncMock(side_effect=reconcile_async)
    orchestrator = object.__new__(Orchestrator)
    orchestrator.workflow_runtime = runtime
    orchestrator.config = SimpleNamespace(full_sync_interval_ms=30_000)
    orchestrator._terminal_audit_started = False
    orchestrator._terminal_audit_last_scan = 0.0
    orchestrator._monotonic_clock = lambda: logical_clock["seconds"]
    orchestrator._request_workflow_batch_continuation = Mock(return_value=True)
    orchestrator._maintenance_future = None
    orchestrator._run_non_lifecycle_housekeeping = Mock()
    orchestrator._notify_observers = Mock()
    orchestrator._handle_auto_update = AsyncMock()
    orchestrator._tick_pool = ThreadPoolExecutor(max_workers=1)

    async def audit_phase(*, allow_new_launches):
        if not allow_new_launches:
            order.append("audit_recovery")
            return {"audit_dispatch": 0.0, "audit_scan": 0.0}
        if audit_owned["value"]:
            order.append("audit_observed_running")
            return {"audit_dispatch": 0.0, "audit_scan": 0.0}
        audit_owned["value"] = True
        order.append("audit_launch")

        async def auditor_write() -> None:
            await scan_started.wait()
            tracker_authority["revision"] += 1
            order.append("auditor_tracker_write")

        writer_tasks.append(asyncio.create_task(auditor_write()))
        await asyncio.sleep(0)
        return {"audit_dispatch": 0.0, "audit_scan": 0.0}

    orchestrator._dispatch_audit_lane = AsyncMock(side_effect=audit_phase)

    async def scenario() -> None:
        nonlocal scan_started
        scan_started = asyncio.Event()
        with patch(
            "oompah.orchestrator.validate_dispatch_config", return_value=[]
        ):
            await orchestrator._run_durable_workflow_tick(started_at=0.0)
        await asyncio.gather(*writer_tasks)

    try:
        asyncio.run(scenario())
    finally:
        orchestrator._tick_pool.shutdown(wait=True)

    assert order == [
        "audit_recovery",
        "reconcile_started",
        "publication_committed",
        "audit_launch",
        "auditor_tracker_write",
        "workflow_admission",
    ]
    assert logical_clock["seconds"] < 300.0
    assert tracker_authority["revision"] == 2
    assert runtime.reconcile_async.await_count == 1
    runtime.reconcile_async.assert_awaited_once_with(admit_workers=False)
    runtime.continue_admission_async.assert_awaited_once_with()
    assert orchestrator._last_tick_metrics["workflow_runtime"]["liveness"] == {
        "status": "healthy"
    }


def test_workflow_batch_continuation_wakes_independent_admission_lane() -> None:
    orchestrator = object.__new__(Orchestrator)
    orchestrator.workflow_runtime = SimpleNamespace(
        worker=SimpleNamespace(accepting=True)
    )
    orchestrator._provider_admission_lock = threading.RLock()
    orchestrator._stopping = False
    orchestrator._quiesced = False
    orchestrator._set_refresh_requested = Mock()
    orchestrator._wake_workflow_admission_lane = Mock()

    assert orchestrator._request_workflow_batch_continuation() is True

    orchestrator._set_refresh_requested.assert_called_once_with()
    orchestrator._wake_workflow_admission_lane.assert_called_once_with()


def test_workflow_reconcile_continuation_posts_coalescible_full_scan() -> None:
    orchestrator = object.__new__(Orchestrator)
    orchestrator.workflow_runtime = SimpleNamespace(
        worker=SimpleNamespace(accepting=True)
    )
    orchestrator._provider_admission_lock = threading.RLock()
    orchestrator._stopping = False
    orchestrator._quiesced = False
    orchestrator._paused = False
    orchestrator._set_refresh_requested = Mock()
    orchestrator._post_event = Mock()

    assert (
        orchestrator._request_workflow_reconcile_continuation(
            reason="publication_authority_changed"
        )
        is True
    )

    orchestrator._set_refresh_requested.assert_called_once_with()
    event = orchestrator._post_event.call_args.args[0]
    assert event.event_type is DispatchEventType.REFRESH_REQUESTED
    assert event.payload == {"reason": "publication_authority_changed"}


@pytest.mark.parametrize(
    ("stopping", "quiesced", "paused", "accepting"),
    (
        (True, False, False, True),
        (False, True, False, True),
        (False, False, True, True),
        (False, False, False, False),
    ),
)
def test_workflow_batch_continuation_respects_shutdown_fences(
    stopping: bool,
    quiesced: bool,
    paused: bool,
    accepting: bool,
) -> None:
    orchestrator = object.__new__(Orchestrator)
    orchestrator.workflow_runtime = SimpleNamespace(
        worker=SimpleNamespace(accepting=accepting)
    )
    orchestrator._provider_admission_lock = threading.RLock()
    orchestrator._stopping = stopping
    orchestrator._quiesced = quiesced
    orchestrator._paused = paused
    orchestrator._set_refresh_requested = Mock()
    orchestrator._post_event = Mock()

    assert orchestrator._request_workflow_batch_continuation() is False
    orchestrator._set_refresh_requested.assert_not_called()
    orchestrator._post_event.assert_not_called()


@pytest.mark.parametrize(
    ("stopping", "quiesced", "paused", "accepting"),
    (
        (True, False, False, True),
        (False, True, False, True),
        (False, False, True, True),
        (False, False, False, False),
    ),
)
def test_workflow_reconcile_continuation_respects_shutdown_fences(
    stopping: bool,
    quiesced: bool,
    paused: bool,
    accepting: bool,
) -> None:
    orchestrator = object.__new__(Orchestrator)
    orchestrator.workflow_runtime = SimpleNamespace(
        worker=SimpleNamespace(accepting=accepting)
    )
    orchestrator._provider_admission_lock = threading.RLock()
    orchestrator._stopping = stopping
    orchestrator._quiesced = quiesced
    orchestrator._paused = paused
    orchestrator._set_refresh_requested = Mock()
    orchestrator._post_event = Mock()

    assert orchestrator._request_workflow_reconcile_continuation() is False
    orchestrator._set_refresh_requested.assert_not_called()
    orchestrator._post_event.assert_not_called()


@pytest.mark.parametrize("mode", ["off", "shadow", "enforce"])
def test_installed_runtime_never_transfers_authority_to_legacy_modes(mode: str) -> None:
    order: list[str] = []
    runtime = SimpleNamespace(
        mode=mode,
        started=True,
        start=AsyncMock(),
        reconcile_async=AsyncMock(
            side_effect=lambda: order.append("reconcile") or {"mode": mode}
        ),
    )
    orchestrator = object.__new__(Orchestrator)
    orchestrator.workflow_runtime = runtime
    orchestrator.config = SimpleNamespace(full_sync_interval_ms=30_000)
    orchestrator._terminal_audit_started = False
    orchestrator._terminal_audit_last_scan = 0.0
    orchestrator._monotonic_clock = Mock(side_effect=[10.0, 10.01])
    orchestrator._dispatch_audit_lane = AsyncMock(
        side_effect=lambda **_kwargs: order.append("audit") or {"pending": 0}
    )
    orchestrator._maintenance_future = None
    orchestrator._run_non_lifecycle_housekeeping = Mock()
    orchestrator._notify_observers = Mock()
    orchestrator._handle_auto_update = AsyncMock()
    orchestrator._tick_pool = ThreadPoolExecutor(max_workers=1)

    try:
        with patch(
            "oompah.orchestrator.validate_dispatch_config", return_value=[]
        ):
            asyncio.run(orchestrator._run_durable_workflow_tick(started_at=10.0))
    finally:
        orchestrator._tick_pool.shutdown(wait=True)

    runtime.start.assert_not_awaited()
    runtime.reconcile_async.assert_awaited_once_with()
    orchestrator._dispatch_audit_lane.assert_awaited_once_with(
        allow_new_launches=True
    )
    assert order == ["audit", "reconcile"]
    orchestrator._run_non_lifecycle_housekeeping.assert_called_once_with()
    orchestrator._handle_auto_update.assert_awaited_once_with()
