"""Deterministic authority fences for implementation retries (OOMPAH-661)."""

from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oompah.config import ServiceConfig
from oompah.integration import IntegrationRecord
from oompah.models import Issue, RetryEntry, RunningEntry
from oompah.orchestrator import Orchestrator
from oompah.server import _cancel_retry_for_authority_change


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
    return Orchestrator(
        config=ServiceConfig(),
        workflow_path="WORKFLOW.md",
        state_path=str(tmp_path / "service-state.json"),
    )


def _schedule(orch: Orchestrator, issue: Issue, *, attempt: int = 1) -> RetryEntry:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
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


def test_workspace_head_is_revalidated_when_tracker_has_no_head(tmp_path):
    workspace = tmp_path / "worker"
    workspace.mkdir()
    asyncio.set_event_loop(asyncio.new_event_loop())
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
