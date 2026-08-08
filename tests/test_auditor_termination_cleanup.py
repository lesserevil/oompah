"""Regressions for forced completion-auditor termination cleanup."""

from __future__ import annotations

import asyncio
import threading
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import oompah.task_handoff as task_handoff_module
from oompah.config import ServiceConfig
from oompah.models import Issue, RunningEntry
from oompah.orchestrator import (
    Orchestrator,
    RuntimeTerminationCoordinator,
    RuntimeTerminationPublicationTimeout,
)
from oompah.statuses import IN_VALIDATION, READY_TO_INTEGRATE
from oompah.task_handoff import (
    TASK_HANDOFF_HEADER,
    acquire_task_handoff_permit,
    issue_task_handoff_token,
    revoke_task_handoff_token,
    validate_task_handoff_token,
)
from oompah.terminal_audit import (
    AuditAttempt,
    FailureClassification,
    RequestState,
    TargetState,
    TerminalAuditRecord,
    Verdict,
    compute_evidence_fingerprint,
)


def _orchestrator(tmp_path) -> Orchestrator:
    project_store = MagicMock()
    project_store.list_all.return_value = []
    return Orchestrator(
        config=ServiceConfig(duplicate_preflight_max_agents=0),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
    )


def _entry(attempt_id: str = "attempt-1") -> RunningEntry:
    issue = Issue(
        id="issue-1",
        identifier="OOMPAH-591",
        title="Audit termination cleanup regression",
        description="Prove forced termination releases only its own branch fence.",
        state=IN_VALIDATION,
        project_id="project-1",
        branch_name="task-branch",
    )
    task = MagicMock()
    task.done.return_value = True
    return RunningEntry(
        worker_task=task,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        is_auditor=True,
        audit_id="audit-1",
        audit_attempt_id=attempt_id,
        branch_key="task-branch",
        # These cleanup regressions exercise a live auditor. A provider that
        # never crossed admission is now rolled back instead of finalized.
        provider_started=True,
    )


def test_schedule_running_termination_reports_admission(tmp_path) -> None:
    """Callers can distinguish a created retry task from rejected admission."""

    async def scenario() -> None:
        orch = _orchestrator(tmp_path)
        entry = _entry()
        orch.state.running[entry.issue.id] = entry
        terminate = AsyncMock(return_value=True)
        with patch.object(orch, "_terminate_running", terminate):
            assert orch._schedule_running_termination(
                entry.issue.id,
                expected_entry=entry,
            ) is True
            await asyncio.sleep(0)
            await asyncio.sleep(0)
        terminate.assert_awaited_once_with(
            entry.issue.id,
            False,
            expected_entry=entry,
        )

    asyncio.run(scenario())


def test_schedule_running_termination_reports_rejected_authority(tmp_path) -> None:
    """A stale generation or closed scheduler cannot imply retry ownership."""

    async def scenario() -> None:
        orch = _orchestrator(tmp_path)
        entry = _entry()
        assert orch._schedule_running_termination(
            entry.issue.id,
            expected_entry=entry,
        ) is False
        orch.state.running[entry.issue.id] = entry
        orch._termination_scheduling_closed = True
        assert orch._schedule_running_termination(
            entry.issue.id,
            expected_entry=entry,
        ) is False

    asyncio.run(scenario())


def _terminate(orch: Orchestrator) -> bool:
    with (
        patch.object(orch, "_fire_task_cost_record"),
        patch.object(orch, "_fire_telemetry_comment"),
    ):
        return asyncio.run(
            orch._terminate_running("issue-1", cleanup_workspace=False)
        )


def test_forced_auditor_termination_releases_all_runtime_claims(tmp_path) -> None:
    orch = _orchestrator(tmp_path)
    entry = _entry()
    orch.state.running[entry.issue.id] = entry
    orch.state.claimed.add(entry.issue.id)
    orch.state.claimed_issues[entry.issue.id] = entry.issue
    orch._audit_branch_claims[entry.branch_key] = entry.audit_attempt_id

    assert _terminate(orch) is True

    assert entry.issue.id not in orch.state.running
    assert entry.issue.id not in orch.state.claimed
    assert entry.issue.id not in orch.state.claimed_issues
    assert entry.branch_key not in orch._audit_branch_claims
    assert not orch._audit_branch_busy(entry.issue, entry.branch_key)


def test_forced_termination_does_not_release_replacement_auditor_claim(
    tmp_path,
) -> None:
    orch = _orchestrator(tmp_path)
    stale = _entry("attempt-old")
    orch.state.running[stale.issue.id] = stale
    orch.state.claimed.add(stale.issue.id)
    orch.state.claimed_issues[stale.issue.id] = stale.issue
    orch._audit_branch_claims[stale.branch_key] = "attempt-new"

    assert _terminate(orch) is True

    assert orch._audit_branch_claims[stale.branch_key] == "attempt-new"


def test_failed_termination_child_creation_preserves_exact_token_and_fence(
    tmp_path,
) -> None:
    """A pre-start failure must restore the runtime instead of revoking it."""

    orch = _orchestrator(tmp_path)
    entry = _entry()
    entry.task_handoff_token = issue_task_handoff_token(
        project_id="project-1",
        task_identifier=entry.identifier,
        allowed_actions={"comment"},
        ttl_seconds=60,
    )
    orch.state.running[entry.issue.id] = entry

    async def terminate_with_rejected_child() -> None:
        rejected_loop = MagicMock()

        def reject_after_concurrent_admission(_coroutine, **_kwargs):
            # This is the exact retirement-linearization window: the runtime
            # is marked pending but child creation has not succeeded yet.
            # An API permit must already be fenced, then failure rolls back
            # the exact capability for the still-running worker.
            valid, _reason = validate_task_handoff_token(
                entry.task_handoff_token,
                project_id="project-1",
                task_identifier=entry.identifier,
                action="comment",
            )
            assert valid is False
            raise RuntimeError("task creation failed")

        rejected_loop.create_task.side_effect = reject_after_concurrent_admission
        with patch(
            "oompah.orchestrator.asyncio.get_running_loop",
            return_value=rejected_loop,
        ):
            try:
                await orch._terminate_running(entry.issue.id, cleanup_workspace=False)
            except RuntimeError as exc:
                assert str(exc) == "task creation failed"
            else:  # pragma: no cover - documents the required failure path
                raise AssertionError(
                    "termination child creation unexpectedly succeeded"
                )

    asyncio.run(terminate_with_rejected_child())

    # The child never owned cleanup, so the parent restores the exact
    # callback-fence baseline and leaves the still-running worker capable of
    # completing its scoped handoff.
    assert entry.retirement_pending is False
    assert orch.state.running[entry.issue.id] is entry
    assert not orch._terminating_worker_owners
    valid, reason = validate_task_handoff_token(
        entry.task_handoff_token,
        project_id="project-1",
        task_identifier=entry.identifier,
        action="comment",
    )
    assert valid is True, reason
    revoke_task_handoff_token(entry.task_handoff_token)


def test_suspended_request_then_child_failure_restore_does_not_hold_worker_exit(
    tmp_path,
) -> None:
    """A reversible retirement denial cannot poison the restored runtime."""

    from fastapi.testclient import TestClient

    import oompah.server as server
    from oompah.server import app

    orch = _orchestrator(tmp_path)
    entry = _entry()
    entry.is_auditor = False
    entry.issue.state = READY_TO_INTEGRATE
    entry.task_handoff_token = issue_task_handoff_token(
        project_id="project-1",
        task_identifier=entry.identifier,
        allowed_actions={"comment"},
        ttl_seconds=60,
    )
    orch.state.running[entry.issue.id] = entry
    tracker = MagicMock()
    tracker.fetch_issue_detail.return_value = entry.issue
    tracker.fetch_comments.return_value = []
    orch._tracker_for_project = MagicMock(return_value=tracker)
    orch._accept_worker_submission = MagicMock(return_value=True)
    orch._fire_task_cost_record = MagicMock()
    orch._fire_telemetry_comment = MagicMock()
    orch._fire_work_contributor_record = MagicMock()
    orch._post_comment = MagicMock()
    orch._post_event = MagicMock()
    orch._notify_observers = MagicMock()
    responses = []

    old_orch = server._orchestrator
    old_creds = server._http_credentials
    old_broadcast = server.broadcast_issues
    server._orchestrator = orch
    server._http_credentials = None
    server.broadcast_issues = MagicMock()

    async def terminate_with_rejected_child() -> None:
        owner_loop = asyncio.get_running_loop()

        def reject_after_suspended_request(_coroutine, **_kwargs):
            with TestClient(app, raise_server_exceptions=False) as client:
                responses.append(
                    client.post(
                        "/api/v1/task-handoff",
                        headers={
                            TASK_HANDOFF_HEADER: entry.task_handoff_token,
                        },
                        json={
                            "action": "comment",
                            "project_id": "project-1",
                            "identifier": entry.identifier,
                            "message": "request raced reversible retirement",
                        },
                    )
                )
            raise RuntimeError("task creation failed")

        with patch.object(
            owner_loop,
            "create_task",
            side_effect=reject_after_suspended_request,
        ):
            with pytest.raises(RuntimeError, match="task creation failed"):
                await orch._terminate_running(
                    entry.issue.id,
                    cleanup_workspace=False,
                )

    try:
        asyncio.run(terminate_with_rejected_child())
        assert len(responses) == 1
        assert responses[0].status_code == 401
        assert responses[0].json()["error"]["code"] == "handoff_revoked"

        valid, reason = validate_task_handoff_token(
            entry.task_handoff_token,
            project_id="project-1",
            task_identifier=entry.identifier,
            action="comment",
        )
        assert valid is True, reason
        token_digest = task_handoff_module._default_store._digest(
            entry.task_handoff_token
        )
        assert token_digest not in task_handoff_module._default_store._failures

        # Without consuming any registry state, prove the ordinary success path
        # owns the runtime rather than the task-handoff failure hold.
        awaitable = orch._on_worker_exit(entry.issue.id, "normal", None)
        asyncio.run(awaitable)
    finally:
        server._orchestrator = old_orch
        server._http_credentials = old_creds
        server.broadcast_issues = old_broadcast
        revoke_task_handoff_token(entry.task_handoff_token)

    orch._accept_worker_submission.assert_called_once()
    tracker.mark_needs_human.assert_not_called()


def test_concurrent_child_creation_failures_keep_handoff_fenced_until_last_parent(
    tmp_path,
) -> None:
    """One failed parent cannot reopen a capability needed by its peer.

    Both parents target the same exact runtime.  The first child publication
    fails only after the second parent has acquired the shared retirement
    fence; the second parent observes that the bearer is still denied before
    it too fails and the final owner rolls the capability back.
    """

    async def scenario() -> None:
        orch = _orchestrator(tmp_path)
        entry = _entry()
        entry.task_handoff_token = issue_task_handoff_token(
            project_id="project-1",
            task_identifier=entry.identifier,
            allowed_actions={"comment"},
            ttl_seconds=60,
        )
        orch.state.running[entry.issue.id] = entry
        publication_started = asyncio.Event()
        release_failure = asyncio.Event()
        publish_calls = 0

        async def fail_publication(
            _issue_id,
            coordinator,
            **_kwargs,
        ):
            nonlocal publish_calls
            publish_calls += 1
            publication_started.set()
            await release_failure.wait()
            with orch._provider_admission_lock:
                coordinator.error = RuntimeError("first child creation failed")
                coordinator.completed = True
                coordinator.starting = False
                coordinator.completion_event.set()
            return False

        with patch.object(
            orch,
            "_publish_termination_child",
            side_effect=fail_publication,
        ):
            first = asyncio.create_task(
                orch._terminate_running(
                    entry.issue.id,
                    cleanup_workspace=False,
                )
            )
            await publication_started.wait()
            second = asyncio.create_task(
                orch._terminate_running(
                    entry.issue.id,
                    cleanup_workspace=False,
                )
            )
            owner_key = orch._termination_owner_key(entry.issue.id, entry)
            for _ in range(100):
                if len(orch._terminating_worker_owners.get(owner_key, set())) == 2:
                    break
                await asyncio.sleep(0)
            else:  # pragma: no cover - deterministic scheduling guard
                raise AssertionError("peer did not join shared retirement")

            valid, _reason = validate_task_handoff_token(
                entry.task_handoff_token,
                project_id="project-1",
                task_identifier=entry.identifier,
                action="comment",
            )
            assert valid is False
            release_failure.set()
            results = await asyncio.gather(first, second, return_exceptions=True)

        assert [str(result) for result in results] == [
            "first child creation failed",
            "first child creation failed",
        ]
        assert all(isinstance(result, RuntimeError) for result in results)
        assert publish_calls == 1
        assert entry.retirement_pending is False
        assert not orch._terminating_worker_owners
        assert not orch._termination_handoff_fences
        valid, reason = validate_task_handoff_token(
            entry.task_handoff_token,
            project_id="project-1",
            task_identifier=entry.identifier,
            action="comment",
        )
        assert valid is True, reason
        revoke_task_handoff_token(entry.task_handoff_token)

    asyncio.run(scenario())


def test_concurrent_successful_parents_union_cleanup_and_retry_requirements(
    tmp_path,
) -> None:
    """One exact child satisfies the strongest request made by either parent."""

    async def scenario() -> None:
        orch = _orchestrator(tmp_path)
        entry = _entry()
        orch.state.running[entry.issue.id] = entry
        child_started = asyncio.Event()
        release_child = asyncio.Event()
        child_calls = 0

        async def retire_once(
            issue_id,
            _cleanup_workspace,
            *,
            expected_entry,
            coordinator=None,
            **_kwargs,
        ) -> bool:
            nonlocal child_calls
            child_calls += 1
            assert expected_entry is entry
            child_started.set()
            await release_child.wait()
            with orch._provider_admission_lock:
                with orch._retry_authority_lock:
                    assert orch.state.running.get(issue_id) is entry
                    orch.state.running.pop(issue_id)
            return True

        orch._terminate_running_once = retire_once
        weak = asyncio.create_task(
            orch._terminate_running(entry.issue.id, cleanup_workspace=False)
        )
        await child_started.wait()
        strong = asyncio.create_task(
            orch._terminate_running(
                entry.issue.id,
                cleanup_workspace=True,
                expected_entry=entry,
                post_retirement_retry=True,
            )
        )
        await asyncio.sleep(0)
        release_child.set()

        assert await weak is True
        assert await strong is True
        assert child_calls == 1
        orch.project_store.remove_worktree.assert_called_once_with(
            "project-1",
            orch._audit_workspace_identifier(
                entry.identifier,
                entry.audit_attempt_id,
            ),
        )
        assert orch._post_retirement_retry_token_for(entry.issue.id, entry)

    asyncio.run(scenario())


def test_late_stronger_parent_upgrades_completed_exact_retirement(tmp_path) -> None:
    """Removal cannot make a captured stronger request report false success."""

    async def scenario() -> None:
        orch = _orchestrator(tmp_path)
        entry = _entry()
        orch.state.running[entry.issue.id] = entry
        child_calls = 0

        async def retire_once(
            issue_id,
            _cleanup_workspace,
            *,
            expected_entry,
            coordinator=None,
            **_kwargs,
        ) -> bool:
            nonlocal child_calls
            child_calls += 1
            assert expected_entry is entry
            with orch._provider_admission_lock:
                with orch._retry_authority_lock:
                    orch.state.running.pop(issue_id)
            return True

        orch._terminate_running_once = retire_once
        assert await orch._terminate_running(
            entry.issue.id,
            cleanup_workspace=False,
        )
        assert entry.issue.id not in orch.state.running

        assert await orch._terminate_running(
            entry.issue.id,
            cleanup_workspace=True,
            expected_entry=entry,
            post_retirement_retry=True,
        )
        assert child_calls == 1
        orch.project_store.remove_worktree.assert_called_once_with(
            "project-1",
            orch._audit_workspace_identifier(
                entry.identifier,
                entry.audit_attempt_id,
            ),
        )
        assert orch._post_retirement_retry_token_for(entry.issue.id, entry)

    asyncio.run(scenario())


def test_late_stronger_parent_cannot_clean_replacement_generation(tmp_path) -> None:
    """A retained coordinator never applies old requirements to a new owner."""

    async def scenario() -> None:
        orch = _orchestrator(tmp_path)
        entry = _entry()
        orch.state.running[entry.issue.id] = entry

        async def retire_once(
            issue_id,
            _cleanup_workspace,
            *,
            expected_entry,
            coordinator=None,
            **_kwargs,
        ) -> bool:
            assert expected_entry is entry
            with orch._provider_admission_lock:
                with orch._retry_authority_lock:
                    orch.state.running.pop(issue_id)
            return True

        orch._terminate_running_once = retire_once
        assert await orch._terminate_running(
            entry.issue.id,
            cleanup_workspace=False,
        )
        replacement = _entry("replacement-attempt")
        replacement.run_id = "replacement-run"
        orch.state.running[entry.issue.id] = replacement

        assert not await orch._terminate_running(
            entry.issue.id,
            cleanup_workspace=True,
            expected_entry=entry,
            post_retirement_retry=True,
        )
        orch.project_store.remove_worktree.assert_not_called()
        assert orch._post_retirement_retry_token_for(entry.issue.id, entry) is None
        assert orch.state.running[entry.issue.id] is replacement

    asyncio.run(scenario())


def test_successful_termination_fences_handoff_before_child_can_run(tmp_path) -> None:
    """A successful child publication leaves no bearer-admission interval."""
    orch = _orchestrator(tmp_path)
    entry = _entry()
    entry.task_handoff_token = issue_task_handoff_token(
        project_id="project-1",
        task_identifier=entry.identifier,
        allowed_actions={"comment"},
        ttl_seconds=60,
    )
    orch.state.running[entry.issue.id] = entry
    import oompah.orchestrator as orchestrator_module

    original_revoke = orchestrator_module.revoke_task_handoff_token

    def verify_fence_then_revoke(token):
        valid, _reason = validate_task_handoff_token(
            token,
            project_id="project-1",
            task_identifier=entry.identifier,
            action="comment",
        )
        assert valid is False
        original_revoke(token)

    with patch.object(
        orchestrator_module,
        "revoke_task_handoff_token",
        side_effect=verify_fence_then_revoke,
    ):
        assert _terminate(orch) is True

    valid, _reason = validate_task_handoff_token(
        entry.task_handoff_token,
        project_id="project-1",
        task_identifier=entry.identifier,
        action="comment",
    )
    assert valid is False


def test_retirement_drains_admitted_handoff_observer_before_inspection(
    tmp_path,
) -> None:
    """A mutation ordered before suspension completes before retirement."""

    async def scenario() -> None:
        orch = _orchestrator(tmp_path)
        entry = _entry()
        entry.is_auditor = False
        entry.task_handoff_token = issue_task_handoff_token(
            project_id="project-1",
            task_identifier=entry.identifier,
            allowed_actions={"comment"},
            ttl_seconds=60,
        )
        orch.state.running[entry.issue.id] = entry
        permit = acquire_task_handoff_permit(
            entry.task_handoff_token,
            project_id="project-1",
            task_identifier=entry.identifier,
            action="comment",
        )
        assert permit is not None
        admitted = asyncio.Event()
        release_mutation = asyncio.Event()
        retirement_entered = asyncio.Event()

        async def mutation_with_observer() -> None:
            async with permit:
                admitted.set()
                await release_mutation.wait()
                # The real endpoint invokes its observer before leaving the
                # permit context.  Model that exact ordering deterministically.
                entry.handoff_pending = True

        async def retire_once(
            issue_id,
            _cleanup_workspace,
            *,
            expected_entry,
            **_kwargs,
        ) -> bool:
            assert expected_entry is entry
            assert entry.handoff_pending is True
            retirement_entered.set()
            orch._remove_running_entry(issue_id, entry)
            return True

        mutation = asyncio.create_task(mutation_with_observer())
        await admitted.wait()
        with patch.object(orch, "_terminate_running_once", side_effect=retire_once):
            termination = asyncio.create_task(
                orch._terminate_running(entry.issue.id, cleanup_workspace=False)
            )
            while not entry.retirement_pending:
                await asyncio.sleep(0)
            await asyncio.sleep(0)
            assert retirement_entered.is_set() is False
            release_mutation.set()
            await mutation
            assert await termination is True
        assert retirement_entered.is_set() is True

    asyncio.run(scenario())


@pytest.mark.parametrize("invalidation", ["revoked", "expired"])
def test_retirement_drains_invalidated_handoff_through_adapter_and_observer(
    tmp_path,
    invalidation,
) -> None:
    """Invalidating a grant cannot hide its already-admitted mutation."""

    async def scenario() -> None:
        clock = [100.0]
        with patch.object(
            task_handoff_module._default_store,
            "_now",
            new=lambda: clock[0],
        ):
            orch = _orchestrator(tmp_path)
            entry = _entry()
            entry.is_auditor = False
            entry.task_handoff_token = issue_task_handoff_token(
                project_id="project-1",
                task_identifier=entry.identifier,
                allowed_actions={"comment"},
                ttl_seconds=1,
            )
            orch.state.running[entry.issue.id] = entry
            permit = acquire_task_handoff_permit(
                entry.task_handoff_token,
                project_id="project-1",
                task_identifier=entry.identifier,
                action="comment",
            )
            assert permit is not None
            admitted = asyncio.Event()
            release_adapter = asyncio.Event()
            adapter_finished = asyncio.Event()
            release_observer = asyncio.Event()
            observer_finished = asyncio.Event()
            retirement_entered = asyncio.Event()

            async def mutation_with_observer() -> None:
                async with permit:
                    admitted.set()
                    await release_adapter.wait()
                    adapter_finished.set()
                    await release_observer.wait()
                    entry.handoff_pending = True
                    observer_finished.set()

            async def retire_once(
                issue_id,
                _cleanup_workspace,
                *,
                expected_entry,
                **_kwargs,
            ) -> bool:
                assert expected_entry is entry
                assert adapter_finished.is_set()
                assert observer_finished.is_set()
                assert entry.handoff_pending is True
                retirement_entered.set()
                orch._remove_running_entry(issue_id, entry)
                return True

            mutation = asyncio.create_task(mutation_with_observer())
            await admitted.wait()
            if invalidation == "revoked":
                revoke_task_handoff_token(entry.task_handoff_token)
            else:
                clock[0] = 102.0
                valid, _reason = validate_task_handoff_token(
                    entry.task_handoff_token,
                    project_id="project-1",
                    task_identifier=entry.identifier,
                    action="comment",
                )
                assert valid is False
                assert (
                    task_handoff_module._default_store._digest(
                        entry.task_handoff_token
                    )
                    not in task_handoff_module._default_store._grants
                )

            with patch.object(
                orch,
                "_terminate_running_once",
                side_effect=retire_once,
            ):
                termination = asyncio.create_task(
                    orch._terminate_running(
                        entry.issue.id,
                        cleanup_workspace=False,
                    )
                )
                while not entry.retirement_pending:
                    await asyncio.sleep(0)
                await asyncio.sleep(0)
                assert retirement_entered.is_set() is False

                release_adapter.set()
                await adapter_finished.wait()
                await asyncio.sleep(0)
                assert retirement_entered.is_set() is False

                release_observer.set()
                await mutation
                assert await termination is True

            assert retirement_entered.is_set()

    asyncio.run(scenario())


@pytest.mark.parametrize("invalidation", ["revoked", "expired"])
def test_invalidated_handoff_drain_timeout_retains_exact_runtime_and_claims(
    tmp_path,
    invalidation,
) -> None:
    """A wedged admitted mutation keeps its runtime and scheduler ownership."""

    async def scenario() -> None:
        clock = [200.0]
        with patch.object(
            task_handoff_module._default_store,
            "_now",
            new=lambda: clock[0],
        ):
            orch = _orchestrator(tmp_path)
            entry = _entry()
            entry.is_auditor = False
            entry.task_handoff_token = issue_task_handoff_token(
                project_id="project-1",
                task_identifier=entry.identifier,
                allowed_actions={"comment"},
                ttl_seconds=1,
            )
            orch.state.running[entry.issue.id] = entry
            orch.state.claimed.add(entry.issue.id)
            orch.state.claimed_issues[entry.issue.id] = entry.issue
            permit = acquire_task_handoff_permit(
                entry.task_handoff_token,
                project_id="project-1",
                task_identifier=entry.identifier,
                action="comment",
            )
            assert permit is not None
            admitted = asyncio.Event()
            release_mutation = asyncio.Event()

            async def wedged_mutation() -> None:
                async with permit:
                    admitted.set()
                    await release_mutation.wait()

            mutation = asyncio.create_task(wedged_mutation())
            await admitted.wait()
            if invalidation == "revoked":
                revoke_task_handoff_token(entry.task_handoff_token)
            else:
                clock[0] = 202.0
                valid, _reason = validate_task_handoff_token(
                    entry.task_handoff_token,
                    project_id="project-1",
                    task_identifier=entry.identifier,
                    action="comment",
                )
                assert valid is False

            observed_fences = []

            def immediate_timeout(fence, *, timeout_seconds):
                assert timeout_seconds >= 1.0
                assert fence is not None
                assert fence.restore_allowed is False
                observed_fences.append(fence)
                return task_handoff_module._default_store.wait_for_operations(
                    fence,
                    timeout_seconds=0,
                )

            import oompah.orchestrator as orchestrator_module

            with patch.object(
                orchestrator_module,
                "wait_for_task_handoff_operations",
                side_effect=immediate_timeout,
            ):
                assert await orch._terminate_running(
                    entry.issue.id,
                    cleanup_workspace=False,
                ) is False

            assert len(observed_fences) == 1
            assert orch.state.running == {entry.issue.id: entry}
            assert orch.state.claimed == {entry.issue.id}
            assert orch.state.claimed_issues == {entry.issue.id: entry.issue}
            assert entry.retirement_pending is True

            release_mutation.set()
            await mutation

    asyncio.run(scenario())


def test_http_owner_retirement_runs_child_on_scheduler_worker_loop(tmp_path) -> None:
    """An HTTP-loop caller never cancels or awaits a scheduler-loop Task."""

    from oompah.server import _retire_scheduler_for_owner_claim

    orch = _orchestrator(tmp_path)
    entry = _entry()
    entry.is_auditor = False
    owner_ready = threading.Event()
    worker_started = threading.Event()
    owner_stopped = threading.Event()
    observed: dict[str, object] = {}

    def run_scheduler_loop() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def live_worker() -> None:
            observed["worker_thread"] = threading.get_ident()
            worker_started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                observed["cancelled_thread"] = threading.get_ident()
                raise

        worker_task = loop.create_task(live_worker(), name="scheduler-owned-worker")
        entry.worker_task = worker_task
        orch._dispatch_loop = loop
        orch.state.running[entry.issue.id] = entry
        orch.state.claimed.add(entry.issue.id)
        orch.state.claimed_issues[entry.issue.id] = entry.issue
        observed["loop"] = loop
        observed["task"] = worker_task
        owner_ready.set()
        try:
            loop.run_forever()
        finally:
            orch._dispatch_loop = None
            loop.close()
            owner_stopped.set()

    owner_thread = threading.Thread(
        target=run_scheduler_loop,
        name="oompah-test-scheduler",
    )
    owner_thread.start()
    assert owner_ready.wait(timeout=3)
    assert worker_started.wait(timeout=3)
    owner_loop = observed["loop"]

    async def http_owner_claim() -> tuple[bool, str]:
        # This asyncio.run loop models the server's HTTP loop. The production
        # service owns its scheduler in a separate dedicated thread.
        assert asyncio.get_running_loop() is not owner_loop
        return await _retire_scheduler_for_owner_claim(
            orch,
            entry.issue,
            entry.issue.project_id or "project-1",
        )

    try:
        with (
            patch.object(orch, "_fire_task_cost_record"),
            patch.object(orch, "_fire_telemetry_comment"),
        ):
            retired, reason = asyncio.run(http_owner_claim())
        assert retired is True, reason
        assert entry.issue.id not in orch.state.running
        assert observed["cancelled_thread"] == owner_thread.ident
        coordinator = getattr(entry, "_termination_coordinator")
        assert coordinator.owner_loop is owner_loop
        assert coordinator.task is not None
        assert coordinator.task.get_loop() is owner_loop
    finally:
        owner_loop.call_soon_threadsafe(owner_loop.stop)
        assert owner_stopped.wait(timeout=3)
        owner_thread.join(timeout=3)
        assert not owner_thread.is_alive()


def test_stale_termination_child_callback_cannot_poison_reopened_generation(
    tmp_path,
) -> None:
    """A delayed done callback publishes only for its exact child."""

    orch = _orchestrator(tmp_path)
    entry = _entry()
    old_child = MagicMock()
    old_child.cancelled.return_value = True
    replacement_child = MagicMock()
    coordinator = RuntimeTerminationCoordinator(
        entry=entry,
        starting=True,
        child_created=True,
        task=replacement_child,
    )

    orch._termination_child_finished(coordinator, old_child)

    assert coordinator.task is replacement_child
    assert coordinator.completed is False
    assert coordinator.error is None


def test_foreign_retirement_fails_closed_when_owner_stops_before_callback(
    tmp_path,
) -> None:
    """Callback acceptance cannot strand a parent on a stopped owner loop."""

    orch = _orchestrator(tmp_path)
    entry = _entry()
    orch.state.running[entry.issue.id] = entry
    owner_loop = asyncio.new_event_loop()
    blocker_entered = threading.Event()
    stop_owner = threading.Event()
    owner_stopped = threading.Event()
    publication_queued = threading.Event()

    def block_then_stop() -> None:
        blocker_entered.set()
        assert stop_owner.wait(timeout=3)
        owner_loop.stop()

    owner_loop.call_soon(block_then_stop)

    def run_owner_loop() -> None:
        asyncio.set_event_loop(owner_loop)
        orch._dispatch_loop = owner_loop
        try:
            owner_loop.run_forever()
        finally:
            orch._dispatch_loop = None
            owner_loop.close()
            owner_stopped.set()

    owner_thread = threading.Thread(target=run_owner_loop)
    owner_thread.start()
    assert blocker_entered.wait(timeout=3)
    original_call_soon_threadsafe = owner_loop.call_soon_threadsafe

    def record_publication(callback, *args):
        handle = original_call_soon_threadsafe(callback, *args)
        publication_queued.set()
        return handle

    async def request_retirement() -> None:
        with patch.object(
            owner_loop,
            "call_soon_threadsafe",
            side_effect=record_publication,
        ):
            retirement = asyncio.create_task(
                orch._terminate_running(
                    entry.issue.id,
                    cleanup_workspace=False,
                )
            )
            assert await asyncio.to_thread(publication_queued.wait, 3)
            stop_owner.set()
            with pytest.raises(
                RuntimeTerminationPublicationTimeout,
                match="did not acknowledge retirement child publication",
            ):
                await asyncio.wait_for(retirement, timeout=3)

    try:
        asyncio.run(request_retirement())
    finally:
        stop_owner.set()
        assert owner_stopped.wait(timeout=3)
        owner_thread.join(timeout=3)
        assert not owner_thread.is_alive()

    assert orch.state.running[entry.issue.id] is entry
    assert entry.retirement_pending is False
    assert orch._terminating_worker_owners == {}


def test_publication_timeout_cannot_restore_fence_during_child_creation(
    tmp_path,
) -> None:
    """The timeout observer cannot detach an owner-loop retirement child."""

    orch = _orchestrator(tmp_path)
    entry = _entry()
    entry.is_auditor = False
    entry.task_handoff_token = issue_task_handoff_token(
        project_id="project-1",
        task_identifier=entry.identifier,
        allowed_actions={"comment"},
        ttl_seconds=60,
    )
    owner_ready = threading.Event()
    worker_started = threading.Event()
    owner_stopped = threading.Event()
    child_creation_entered = threading.Event()
    release_child_creation = threading.Event()
    fence_observations: list[bool] = []
    observed: dict[str, object] = {}

    def run_owner_loop() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def live_worker() -> None:
            worker_started.set()
            await asyncio.Event().wait()

        worker_task = loop.create_task(live_worker())
        entry.worker_task = worker_task
        orch._dispatch_loop = loop
        orch.state.running[entry.issue.id] = entry
        observed["loop"] = loop
        owner_ready.set()
        try:
            loop.run_forever()
        finally:
            orch._dispatch_loop = None
            loop.close()
            owner_stopped.set()

    owner_thread = threading.Thread(target=run_owner_loop)
    owner_thread.start()
    assert owner_ready.wait(timeout=3)
    assert worker_started.wait(timeout=3)
    owner_loop = observed["loop"]
    original_create_task = owner_loop.create_task

    def delay_retirement_child(coroutine, **kwargs):
        child_creation_entered.set()
        assert release_child_creation.wait(timeout=3)
        valid, _reason = validate_task_handoff_token(
            entry.task_handoff_token,
            project_id="project-1",
            task_identifier=entry.identifier,
            action="comment",
        )
        fence_observations.append(valid)
        return original_create_task(coroutine, **kwargs)

    def release_after_publication_timeout() -> None:
        assert child_creation_entered.wait(timeout=3)
        time.sleep(1.2)
        valid, _reason = validate_task_handoff_token(
            entry.task_handoff_token,
            project_id="project-1",
            task_identifier=entry.identifier,
            action="comment",
        )
        fence_observations.append(valid)
        release_child_creation.set()

    release_thread = threading.Thread(target=release_after_publication_timeout)
    release_thread.start()
    try:
        with (
            patch.object(
                owner_loop,
                "create_task",
                side_effect=delay_retirement_child,
            ),
            patch.object(orch, "_fire_task_cost_record"),
            patch.object(orch, "_fire_telemetry_comment"),
        ):
            assert asyncio.run(
                orch._terminate_running(
                    entry.issue.id,
                    cleanup_workspace=False,
                )
            )
    finally:
        release_child_creation.set()
        release_thread.join(timeout=3)
        if not owner_stopped.is_set():
            owner_loop.call_soon_threadsafe(owner_loop.stop)
        assert owner_stopped.wait(timeout=3)
        owner_thread.join(timeout=3)

    assert not release_thread.is_alive()
    assert not owner_thread.is_alive()
    assert fence_observations == [False, False]
    assert entry.issue.id not in orch.state.running
    assert orch._terminating_worker_owners == {}


def test_cancelled_foreign_retirement_waits_for_queued_owner_publication(
    tmp_path,
) -> None:
    """Cancellation cannot detach a callback that the owner may still run."""

    orch = _orchestrator(tmp_path)
    entry = _entry()
    orch.state.running[entry.issue.id] = entry
    owner_loop = asyncio.new_event_loop()
    blocker_entered = threading.Event()
    release_owner = threading.Event()
    owner_stopped = threading.Event()
    publication_queued = threading.Event()

    def block_owner() -> None:
        blocker_entered.set()
        assert release_owner.wait(timeout=3)

    owner_loop.call_soon(block_owner)

    def run_owner_loop() -> None:
        asyncio.set_event_loop(owner_loop)
        orch._dispatch_loop = owner_loop
        try:
            owner_loop.run_forever()
        finally:
            orch._dispatch_loop = None
            owner_loop.close()
            owner_stopped.set()

    owner_thread = threading.Thread(target=run_owner_loop)
    owner_thread.start()
    assert blocker_entered.wait(timeout=3)
    original_call_soon_threadsafe = owner_loop.call_soon_threadsafe

    def record_publication(callback, *args):
        handle = original_call_soon_threadsafe(callback, *args)
        publication_queued.set()
        return handle

    async def request_retirement() -> None:
        with patch.object(
            owner_loop,
            "call_soon_threadsafe",
            side_effect=record_publication,
        ):
            retirement = asyncio.create_task(
                orch._terminate_running(
                    entry.issue.id,
                    cleanup_workspace=False,
                )
            )
            assert await asyncio.to_thread(publication_queued.wait, 3)
            retirement.cancel()
            await asyncio.sleep(0.05)
            assert retirement.done() is False
            release_owner.set()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(retirement, timeout=3)

    try:
        asyncio.run(request_retirement())
    finally:
        release_owner.set()
        if not owner_stopped.is_set():
            owner_loop.call_soon_threadsafe(owner_loop.stop)
        assert owner_stopped.wait(timeout=3)
        owner_thread.join(timeout=3)
        assert not owner_thread.is_alive()

    assert entry.issue.id not in orch.state.running
    assert orch._terminating_worker_owners == {}


def test_cancelled_leader_keeps_follower_bounded_when_owner_loop_stops(
    tmp_path,
) -> None:
    """The leader retains the publication timeout after caller cancellation."""

    orch = _orchestrator(tmp_path)
    entry = _entry()
    orch.state.running[entry.issue.id] = entry
    owner_loop = asyncio.new_event_loop()
    blocker_entered = threading.Event()
    stop_owner = threading.Event()
    owner_stopped = threading.Event()
    publication_queued = threading.Event()

    def block_then_stop() -> None:
        blocker_entered.set()
        assert stop_owner.wait(timeout=3)
        owner_loop.stop()

    owner_loop.call_soon(block_then_stop)

    def run_owner_loop() -> None:
        asyncio.set_event_loop(owner_loop)
        orch._dispatch_loop = owner_loop
        try:
            owner_loop.run_forever()
        finally:
            orch._dispatch_loop = None
            owner_loop.close()
            owner_stopped.set()

    owner_thread = threading.Thread(target=run_owner_loop)
    owner_thread.start()
    assert blocker_entered.wait(timeout=3)
    original_call_soon_threadsafe = owner_loop.call_soon_threadsafe

    def record_publication(callback, *args):
        handle = original_call_soon_threadsafe(callback, *args)
        publication_queued.set()
        return handle

    async def request_retirements() -> list[BaseException | bool]:
        with patch.object(
            owner_loop,
            "call_soon_threadsafe",
            side_effect=record_publication,
        ):
            leader = asyncio.create_task(
                orch._terminate_running(
                    entry.issue.id,
                    cleanup_workspace=False,
                )
            )
            assert await asyncio.to_thread(publication_queued.wait, 3)
            follower = asyncio.create_task(
                orch._terminate_running(
                    entry.issue.id,
                    cleanup_workspace=False,
                    expected_entry=entry,
                )
            )
            owner_key = orch._termination_owner_key(entry.issue.id, entry)
            deadline = asyncio.get_running_loop().time() + 3
            while len(orch._terminating_worker_owners.get(owner_key, set())) < 2:
                assert asyncio.get_running_loop().time() < deadline
                await asyncio.sleep(0.001)
            leader.cancel()
            await asyncio.sleep(0.05)
            assert leader.done() is False
            stop_owner.set()
            return await asyncio.wait_for(
                asyncio.gather(leader, follower, return_exceptions=True),
                timeout=3,
            )

    try:
        results = asyncio.run(request_retirements())
    finally:
        stop_owner.set()
        assert owner_stopped.wait(timeout=3)
        owner_thread.join(timeout=3)
        assert not owner_thread.is_alive()

    assert len(results) == 2
    assert all(
        isinstance(result, RuntimeTerminationPublicationTimeout)
        and "did not acknowledge retirement child publication" in str(result)
        for result in results
    )
    assert orch.state.running[entry.issue.id] is entry
    assert entry.retirement_pending is False
    assert orch._terminating_worker_owners == {}


@pytest.mark.parametrize("first_outcome", ["false", "error", "cancelled"])
def test_later_owner_retries_failed_exact_runtime_coordinator(
    tmp_path,
    first_outcome,
) -> None:
    """A transient child outcome cannot poison a retained exact runtime."""

    async def scenario() -> None:
        orch = _orchestrator(tmp_path)
        entry = _entry()
        orch.state.running[entry.issue.id] = entry
        calls = 0

        async def retire_once(
            issue_id,
            _cleanup_workspace,
            *,
            expected_entry,
            **_kwargs,
        ) -> bool:
            nonlocal calls
            calls += 1
            assert expected_entry is entry
            if calls == 1:
                if first_outcome == "false":
                    return False
                if first_outcome == "cancelled":
                    raise asyncio.CancelledError
                raise RuntimeError("transient retirement failure")
            orch._remove_running_entry(issue_id, entry)
            return True

        with patch.object(orch, "_terminate_running_once", side_effect=retire_once):
            if first_outcome == "false":
                assert not await orch._terminate_running(
                    entry.issue.id,
                    cleanup_workspace=False,
                )
            elif first_outcome == "cancelled":
                with pytest.raises(asyncio.CancelledError):
                    await orch._terminate_running(
                        entry.issue.id,
                        cleanup_workspace=False,
                    )
            else:
                with pytest.raises(RuntimeError, match="transient retirement failure"):
                    await orch._terminate_running(
                        entry.issue.id,
                        cleanup_workspace=False,
                    )

            assert orch.state.running[entry.issue.id] is entry
            assert await orch._terminate_running(
                entry.issue.id,
                cleanup_workspace=False,
            )
            assert calls == 2
            assert entry.issue.id not in orch.state.running

    asyncio.run(scenario())


def test_owner_authority_revocation_fences_live_auditor(tmp_path) -> None:
    orch = _orchestrator(tmp_path)
    entry = _entry()
    orch.state.running[entry.issue.id] = entry

    with patch.object(orch, "_schedule_running_termination") as terminate:
        orch._revoke_auditor_authority("project-1", entry.identifier)

    assert entry.authority_revoked is True
    assert entry.forced_exit_reason == "authority_revoked"
    terminate.assert_called_once_with(
        entry.issue.id,
        cleanup_workspace=False,
        task_name_prefix="retire-revoked-auditor",
        expected_entry=entry,
    )


def test_uncommitted_normal_exit_is_a_finalization_failure(tmp_path) -> None:
    orch = _orchestrator(tmp_path)
    entry = _entry()
    fingerprint = compute_evidence_fingerprint(
        "requirements",
        "project-1",
        entry.identifier,
    )
    attempt = AuditAttempt(
        attempt_id=entry.audit_attempt_id,
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        provider_id="provider-a",
        model="model-a",
        request_state=RequestState.IN_PROGRESS,
    )
    record = TerminalAuditRecord(
        audit_id=entry.audit_id,
        project_id="project-1",
        task_id=entry.identifier,
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.IN_PROGRESS,
        attempts=[attempt],
    )
    store = MagicMock()
    store.read.return_value = MagicMock(pending_chain=[record])

    with (
        patch.object(orch, "_audit_store", return_value=store),
        patch.object(orch, "_audit_update_record", return_value=True),
        patch("oompah.orchestrator.AuditorDispatchLane.finish_attempt") as finish,
    ):
        finish.return_value = record
        assert orch._finish_audit_attempt(entry, "normal", None) is True

    assert finish.call_args.kwargs["failure_classification"] == (
        FailureClassification.FINALIZATION_FAILURE
    )


def test_tool_result_delivery_timeout_is_retryable_transport_failure(tmp_path) -> None:
    orch = _orchestrator(tmp_path)
    entry = _entry()
    fingerprint = compute_evidence_fingerprint(
        "requirements",
        "project-1",
        entry.identifier,
    )
    attempt = AuditAttempt(
        attempt_id=entry.audit_attempt_id,
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        provider_id="provider-haiku",
        model="haiku",
        request_state=RequestState.IN_PROGRESS,
    )
    record = TerminalAuditRecord(
        audit_id=entry.audit_id,
        project_id="project-1",
        task_id=entry.identifier,
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.IN_PROGRESS,
        attempts=[attempt],
    )
    store = MagicMock()
    store.read.return_value = MagicMock(pending_chain=[record])

    with (
        patch.object(orch, "_audit_store", return_value=store),
        patch.object(orch, "_audit_update_record", return_value=True),
        patch("oompah.orchestrator.AuditorDispatchLane.finish_attempt") as finish,
    ):
        finish.return_value = record
        assert orch._finish_audit_attempt(
            entry,
            "auditor_tool_result_delivery_timeout",
            "run_command result delivery timed out after 30s",
        )

    assert finish.call_args.kwargs["failure_classification"] == (
        FailureClassification.INFRASTRUCTURE_ERROR
    )


def test_tool_delivery_timeout_uses_audit_retry_not_ordinary_retry(tmp_path) -> None:
    async def scenario() -> None:
        orch = _orchestrator(tmp_path)
        entry = _entry()
        orch.state.running[entry.issue.id] = entry
        orch._tool_stall_status = MagicMock(
            return_value=(False, "run_command result delivery timed out after 30s")
        )

        async def terminate(
            issue_id: str,
            cleanup_workspace: bool,
            *,
            post_retirement_retry: bool = False,
        ) -> bool:
            assert issue_id == entry.issue.id
            assert cleanup_workspace is False
            assert post_retirement_retry is True
            orch.state.running.pop(issue_id, None)
            return True

        orch._terminate_running = AsyncMock(side_effect=terminate)
        orch._schedule_retry = MagicMock()

        await orch._reconcile()

        assert entry.forced_exit_reason == "auditor_tool_result_delivery_timeout"
        assert entry.forced_exit_error == "run_command result delivery timed out after 30s"
        orch._terminate_running.assert_awaited_once_with(
            entry.issue.id,
            cleanup_workspace=False,
            post_retirement_retry=True,
        )
        orch._schedule_retry.assert_not_called()

    asyncio.run(scenario())


def test_workflow_lease_covers_substantive_and_transport_budgets(tmp_path) -> None:
    project_store = MagicMock()
    project_store.list_all.return_value = []
    orch = Orchestrator(
        config=ServiceConfig(
            duplicate_preflight_max_agents=0,
            audit_max_attempts=2,
            audit_max_transport_retries=3,
        ),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
    )

    assert orch.terminal_audit_workflow.max_attempts == 5


def test_structured_nonterminal_result_owns_attempt_classification(tmp_path) -> None:
    orch = _orchestrator(tmp_path)
    entry = _entry()
    fingerprint = compute_evidence_fingerprint(
        "requirements",
        "project-1",
        entry.identifier,
    )
    attempt = AuditAttempt(
        attempt_id=entry.audit_attempt_id,
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.IN_PROGRESS,
        verdict=Verdict.ERROR,
        failure_classification=FailureClassification.INFRASTRUCTURE_ERROR,
    )
    record = TerminalAuditRecord(
        audit_id=entry.audit_id,
        project_id="project-1",
        task_id=entry.identifier,
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.IN_PROGRESS,
        attempts=[attempt],
    )
    store = MagicMock()
    store.read.return_value = MagicMock(pending_chain=[record])

    with (
        patch.object(orch, "_audit_store", return_value=store),
        patch("oompah.orchestrator.AuditorDispatchLane.finish_attempt") as finish,
    ):
        assert orch._finish_audit_attempt(entry, "normal", None) is False

    finish.assert_not_called()
