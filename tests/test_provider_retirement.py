"""Regressions for authoritative provider retirement (OOMPAH-701)."""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import subprocess
import threading
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oompah.agent import ProcessIdentity
from oompah.api_agent import _execute_tool
from oompah.authority_boundary import auditor_policy
from oompah.config import ServiceConfig
from oompah.models import Issue, RunningEntry
from oompah.orchestrator import Orchestrator
from oompah.statuses import IN_PROGRESS, IN_VALIDATION


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
    )


def test_read_only_awk_and_sed_validation_does_not_rotate_auditor(
    tmp_path,
) -> None:
    orch = _orchestrator(tmp_path)
    entry = _entry(state=IN_VALIDATION, auditor=True)
    orch.state.running[entry.issue.id] = entry
    orch._schedule_running_termination = MagicMock()
    commands = (
        "awk 'NR>=7790 && NR<=7900' oompah/orchestrator.py",
        "sed -n '7790,7900p' oompah/orchestrator.py",
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
