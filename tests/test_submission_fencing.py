"""Submission fencing against post-handoff worktree mutation (OOMPAH-724).

Tests that verify accepted submissions are protected from late changes
that occur between acceptance and worker retirement, preventing the
EXOCOMP-172 scenario where integration fails due to stale worktree state.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import tempfile
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from oompah.config import ServiceConfig
from oompah.integration import IntegrationRecord
from oompah.models import Issue, RunningEntry
from oompah.orchestrator import Orchestrator
from oompah.projects import RecoveryPublicationError
from oompah.statuses import OPEN, READY_TO_INTEGRATE
from oompah.task_transition_service import issue_authority_version


def _issue(
    *,
    issue_id: str = "task-1",
    identifier: str = "TASK-1",
    project_id: str = "project-a",
    state: str = "Ready to Integrate",
    work_branch: str = "task/TASK-1",
    head_sha: str = "a" * 40,
) -> Issue:
    return Issue(
        id=issue_id,
        identifier=identifier,
        title="Submission fencing test",
        state=state,
        project_id=project_id,
        work_branch=work_branch,
        assignment_id="assignment-1",
        updated_at=datetime.now(timezone.utc),
        integration=(
            IntegrationRecord(
                state="ready",
                head_sha=head_sha,
            )
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


def _create_test_worktree(tmp_path: Path, head_sha: str = "a" * 40) -> str:
    """Create a minimal git worktree for testing."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    
    # Initialize git repo
    subprocess.run(
        ["git", "init"],
        cwd=repo_dir,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_dir,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_dir,
        capture_output=True,
        check=True,
    )
    
    # Create initial commit
    test_file = repo_dir / "test.txt"
    test_file.write_text("test")
    subprocess.run(
        ["git", "add", "test.txt"],
        cwd=repo_dir,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo_dir,
        capture_output=True,
        check=True,
    )
    
    return str(repo_dir)


@pytest.mark.asyncio
async def test_late_tracked_changes_after_submission_acceptance_are_detected(tmp_path):
    """Reproduce EXOCOMP-172: late formatter changes after submission acceptance."""
    orch = _orchestrator(tmp_path)
    issue = _issue()
    
    # Create a test worktree
    workspace = _create_test_worktree(tmp_path)
    
    # Create a running entry with submission
    entry = RunningEntry(
        worker_task=None,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        assignment_id="assignment-1",
        workspace_path=workspace,
    )
    
    # Record the initial HEAD
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=True,
    )
    initial_head = result.stdout.strip()
    
    # Simulate submission acceptance: set the record
    submission_record = IntegrationRecord(
        state="ready",
        head_sha=initial_head,
    )
    entry.accepted_submission_record = submission_record
    
    # Simulate late formatter changes: create a new commit after submission
    test_file = Path(workspace) / "formatted.txt"
    test_file.write_text("formatted content")
    subprocess.run(
        ["git", "add", "formatted.txt"],
        cwd=workspace,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "Late formatter change"],
        cwd=workspace,
        capture_output=True,
        check=True,
    )
    
    # Get the new HEAD after late changes
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=True,
    )
    final_head = result.stdout.strip()
    
    # Verify we actually made a change
    assert initial_head != final_head, "Test setup failed: no change was made"
    
    # Now simulate the revoked submission exit handler
    # Mock the tracker and project_store
    tracker_mock = MagicMock()
    current_issue = _issue(state=READY_TO_INTEGRATE)
    tracker_mock.fetch_issue_detail.return_value = current_issue
    tracker_mock.update_issue.return_value = None
    
    project_store_mock = MagicMock()
    project_store_mock.preserve_worktree_changes.return_value = {
        "version": "1",
        "project_id": issue.project_id,
        "issue_identifier": issue.identifier,
        "recovery_ref": f"refs/oompah/recovery/TASK-1-deadbeef",
        "snapshot_head": final_head,
    }
    
    with patch.object(orch, "_tracker_for_project", return_value=tracker_mock):
        with patch.object(orch, "project_store", project_store_mock):
            # Set up the running state
            orch.state.running[issue.id] = entry
            orch.state.claimed.add(issue.id)
            orch.state.completed.add(issue.id)
            
            # Call the handler - it should detect late changes
            await orch._handle_revoked_submission_exit(
                entry,
                issue.id,
                issue.project_id,
                submission_record,
            )
    
    # Verify the behavior
    # 1. Entry should be removed from running/claimed
    assert issue.id not in orch.state.running
    assert issue.id not in orch.state.claimed
    
    # 2. Task should be reopened (not left in Ready to Integrate)
    tracker_mock.update_issue.assert_called()
    call_args = tracker_mock.update_issue.call_args
    assert call_args[1]["status"] == OPEN, "Late changes should reopen task to Open"
    
    # 3. Should be removed from completed state
    assert issue.id not in orch.state.completed
    
    # 4. A comment should be posted with recovery context
    # (We can't easily verify this without mocking _post_comment, but the
    # logic is there)


@pytest.mark.asyncio
async def test_clean_submission_with_no_late_changes_proceeds_to_integration(tmp_path):
    """Verify clean submissions without late changes proceed to integration."""
    orch = _orchestrator(tmp_path)
    issue = _issue()
    
    # Create a test worktree
    workspace = _create_test_worktree(tmp_path)
    
    # Get the initial HEAD
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=True,
    )
    clean_head = result.stdout.strip()
    
    # Create a running entry
    entry = RunningEntry(
        worker_task=None,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        assignment_id="assignment-1",
        workspace_path=workspace,
    )
    
    # Set submission record matching the current HEAD
    submission_record = IntegrationRecord(
        state="ready",
        head_sha=clean_head,
    )
    entry.accepted_submission_record = submission_record
    
    # Mock the tracker
    tracker_mock = MagicMock()
    current_issue = _issue(state=READY_TO_INTEGRATE)
    tracker_mock.fetch_issue_detail.return_value = current_issue
    tracker_mock.update_issue.return_value = None
    
    # Mock project_store to return no late changes
    project_store_mock = MagicMock()
    project_store_mock.preserve_worktree_changes.return_value = None
    
    with patch.object(orch, "_tracker_for_project", return_value=tracker_mock):
        with patch.object(orch, "project_store", project_store_mock):
            # Set up the running state
            orch.state.running[issue.id] = entry
            orch.state.claimed.add(issue.id)
            orch.state.completed.add(issue.id)
            
            # Call the handler
            await orch._handle_revoked_submission_exit(
                entry,
                issue.id,
                issue.project_id,
                submission_record,
            )
    
    # Verify the behavior
    # 1. Entry should be removed from running/claimed
    assert issue.id not in orch.state.running
    assert issue.id not in orch.state.claimed
    
    # 2. Task should stay in Ready to Integrate (or be updated to it)
    tracker_mock.update_issue.assert_called()
    call_args = tracker_mock.update_issue.call_args
    assert call_args[1]["status"] == READY_TO_INTEGRATE, "Clean submission should be Ready to Integrate"
    
    # 3. Should remain in completed state for integration queue
    assert issue.id in orch.state.completed


@pytest.mark.asyncio
async def test_durable_clean_submission_leaves_status_to_transition_service(tmp_path):
    """The validation job, not retirement cleanup, owns the Ready write."""

    orch = _orchestrator(tmp_path)
    orch.workflow_runtime = SimpleNamespace(enforce=True)
    issue = _issue(state="In Progress")
    workspace = _create_test_worktree(tmp_path)
    clean_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    record = IntegrationRecord(state="ready", head_sha=clean_head)
    issue.integration = record
    entry = RunningEntry(
        worker_task=None,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        assignment_id="assignment-1",
        workspace_path=workspace,
        accepted_submission_record=record,
        authority_revoked=True,
    )
    tracker = MagicMock()
    tracker.fetch_issue_detail.return_value = issue
    project_store = MagicMock()
    project_store.preserve_worktree_changes.return_value = None
    orch.state.running[issue.id] = entry
    orch._notify_observers = MagicMock()

    with (
        patch.object(orch, "_tracker_for_project", return_value=tracker),
        patch.object(orch, "project_store", project_store),
        patch.object(orch, "_schedule_implementation_workflow_event") as schedule,
    ):
        await orch._handle_revoked_submission_exit(
            entry, issue.id, issue.project_id, record
        )

    tracker.update_issue.assert_not_called()
    schedule.assert_not_called()


@pytest.mark.asyncio
async def test_revoked_submission_preserves_against_accepted_branch_when_projection_is_stale(
    tmp_path,
):
    """Late-exit recovery uses accepted evidence, not a stale hierarchy branch."""

    stale_branch = "epic-OOMPAH-763--task-OOMPAH-814"
    accepted_branch = "OOMPAH-814"
    issue = _issue(
        issue_id="OOMPAH-814",
        identifier="OOMPAH-814",
        work_branch=stale_branch,
        head_sha="",
    )
    workspace = _create_test_worktree(tmp_path)
    accepted_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    record = IntegrationRecord(
        state="ready",
        task_branch=accepted_branch,
        head_sha=accepted_head,
    )
    entry = RunningEntry(
        worker_task=None,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        workspace_path=workspace,
        accepted_submission_record=record,
        authority_revoked=True,
    )
    tracker = MagicMock()
    tracker.fetch_issue_detail.return_value = issue
    store = MagicMock()
    store.preserve_worktree_changes.return_value = None
    orch = _orchestrator(tmp_path)
    orch.state.running[issue.id] = entry

    with (
        patch.object(orch, "_tracker_for_project", return_value=tracker),
        patch.object(orch, "project_store", store),
    ):
        await orch._handle_revoked_submission_exit(
            entry,
            issue.id,
            issue.project_id,
            record,
        )

    store.preserve_worktree_changes.assert_called_once_with(
        issue.project_id,
        issue.identifier,
        workspace,
        accepted_branch,
    )
    tracker.update_issue.assert_called_once_with(
        issue.identifier,
        status=READY_TO_INTEGRATE,
    )


@pytest.mark.asyncio
async def test_consumed_prior_checkpoint_does_not_reopen_successor_submission(tmp_path):
    """A checkpoint already contained by the accepted head is historical."""

    orch = _orchestrator(tmp_path)
    issue = _issue(state=READY_TO_INTEGRATE)
    workspace = _create_test_worktree(tmp_path)
    submitted_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    record = IntegrationRecord(
        state="ready",
        task_branch=issue.work_branch,
        head_sha=submitted_head,
    )
    entry = RunningEntry(
        worker_task=None,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        assignment_id="assignment-1",
        workspace_path=workspace,
    )
    tracker = MagicMock()
    tracker.fetch_issue_detail.return_value = issue
    store = MagicMock()
    store.preserve_worktree_changes.return_value = {
        "snapshot_head": "b" * 40,
        "recovery_ref": "refs/oompah/recovery/TASK-1",
        "publication_state": "published",
    }
    store.consume_worktree_recovery_if_incorporated.return_value = "consumed"
    orch.state.running[issue.id] = entry
    orch.state.claimed.add(issue.id)
    orch.state.completed.add(issue.id)

    with (
        patch.object(orch, "_tracker_for_project", return_value=tracker),
        patch.object(orch, "project_store", store),
    ):
        await orch._handle_revoked_submission_exit(
            entry,
            issue.id,
            issue.project_id,
            record,
        )

    store.consume_worktree_recovery_if_incorporated.assert_called_once()
    tracker.update_issue.assert_called_once_with(
        issue.identifier,
        status=READY_TO_INTEGRATE,
    )
    assert issue.id in orch.state.completed


@pytest.mark.parametrize(
    ("relationship", "expected_status", "expected_reopened"),
    [
        ("consumed", None, 0),
        ("current", OPEN, 1),
    ],
)
def test_restart_reconciliation_distinguishes_consumed_and_current_recovery(
    tmp_path,
    relationship,
    expected_status,
    expected_reopened,
):
    issue = _issue(state=READY_TO_INTEGRATE, head_sha="a" * 40)
    issue.integration = IntegrationRecord(
        state="ready",
        task_branch=issue.work_branch,
        head_sha="a" * 40,
    )
    context = {
        "project_id": issue.project_id,
        "issue_identifier": issue.identifier,
        "snapshot_head": "b" * 40,
        "recovery_ref": "refs/oompah/recovery/TASK-1",
        "worktree_path": str(tmp_path / "missing-checkout"),
        "publication_state": "published",
    }
    store = MagicMock()
    store.pending_worktree_recoveries.return_value = [context]
    store.preserve_worktree_changes.return_value = context
    store.consume_worktree_recovery_if_incorporated.return_value = relationship
    orch = Orchestrator(
        config=ServiceConfig(),
        workflow_path="WORKFLOW.md",
        project_store=store,
        state_path=str(tmp_path / "restart-state.json"),
    )
    tracker = MagicMock()
    tracker.fetch_issue_detail.return_value = issue
    orch._project_trackers[issue.project_id] = tracker
    orch._post_comment = MagicMock()

    result = orch._reconcile_pending_recovery_publications(discover=True)

    assert result["reopened"] == expected_reopened
    assert result["pending"] == 0
    if expected_status is None:
        tracker.update_issue.assert_not_called()
    else:
        tracker.update_issue.assert_called_once_with(
            issue.identifier,
            status=expected_status,
        )


def test_restart_recovery_preserves_against_accepted_branch_when_projection_is_stale(
    tmp_path,
):
    stale_branch = "epic-OOMPAH-763--task-OOMPAH-814"
    accepted_branch = "OOMPAH-814"
    accepted_head = "a" * 40
    issue = _issue(
        issue_id="OOMPAH-814",
        identifier="OOMPAH-814",
        work_branch=stale_branch,
        head_sha="",
    )
    issue.integration = IntegrationRecord(
        state="ready",
        task_branch=accepted_branch,
        head_sha=accepted_head,
    )
    context = {
        "project_id": issue.project_id,
        "issue_identifier": issue.identifier,
        "snapshot_head": "b" * 40,
        "recovery_ref": "refs/oompah/recovery/OOMPAH-814",
        "worktree_path": str(tmp_path / "accepted-checkout"),
        "publication_state": "published",
    }
    store = MagicMock()
    store.pending_worktree_recoveries.return_value = [context]
    store.preserve_worktree_changes.return_value = context
    store.consume_worktree_recovery_if_incorporated.return_value = "consumed"
    orch = Orchestrator(
        config=ServiceConfig(),
        workflow_path="WORKFLOW.md",
        project_store=store,
        state_path=str(tmp_path / "restart-state.json"),
    )
    tracker = MagicMock()
    tracker.fetch_issue_detail.return_value = issue
    orch._project_trackers[issue.project_id] = tracker

    result = orch._reconcile_pending_recovery_publications(discover=True)

    store.preserve_worktree_changes.assert_called_once_with(
        issue.project_id,
        issue.identifier,
        context["worktree_path"],
        accepted_branch,
    )
    consume_call = store.consume_worktree_recovery_if_incorporated.call_args
    assert consume_call.args[:3] == (
        issue.project_id,
        issue.identifier,
        accepted_head,
    )
    assert consume_call.kwargs["accepted_branch"] == accepted_branch
    assert result["manual"] == 0
    assert result["pending"] == 0


@pytest.mark.asyncio
async def test_unpublished_active_operation_checkpoint_blocks_integration(tmp_path):
    """commit-tree recovery can leave HEAD unchanged and still fence Ready."""

    orch = _orchestrator(tmp_path)
    issue = _issue(state="In Progress")
    workspace = _create_test_worktree(tmp_path)
    submitted_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    record = IntegrationRecord(state="ready", head_sha=submitted_head)
    entry = RunningEntry(
        worker_task=None,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        assignment_id="assignment-1",
        workspace_path=workspace,
    )
    context = {
        "project_id": issue.project_id,
        "issue_identifier": issue.identifier,
        "snapshot_head": "b" * 40,
        "pending_ref": "refs/oompah/recovery-pending/TASK-1",
        "recovery_ref": "refs/oompah/recovery/TASK-1",
    }
    tracker = MagicMock()
    tracker.fetch_issue_detail.return_value = issue
    store = MagicMock()
    store.preserve_worktree_changes.side_effect = RecoveryPublicationError(
        "transfer interrupted",
        context=context,
    )
    orch.state.running[issue.id] = entry
    orch.state.claimed.add(issue.id)
    orch.state.completed.add(issue.id)
    orch._post_comment = MagicMock()

    with (
        patch.object(orch, "_tracker_for_project", return_value=tracker),
        patch.object(orch, "project_store", store),
    ):
        await orch._handle_revoked_submission_exit(
            entry,
            issue.id,
            issue.project_id,
            record,
        )

    tracker.update_issue.assert_called_once_with(issue.identifier, status=OPEN)
    assert not any(
        call.kwargs.get("status") == READY_TO_INTEGRATE
        for call in tracker.update_issue.call_args_list
    )
    assert (issue.project_id, issue.identifier) in orch._pending_recovery_publications
    assert issue.id not in orch.state.completed


@pytest.mark.asyncio
async def test_published_commit_tree_checkpoint_with_unchanged_head_reopens(tmp_path):
    orch = _orchestrator(tmp_path)
    issue = _issue(state="In Progress")
    workspace = _create_test_worktree(tmp_path)
    submitted_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    record = IntegrationRecord(state="ready", head_sha=submitted_head)
    entry = RunningEntry(
        worker_task=None,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        assignment_id="assignment-1",
        workspace_path=workspace,
    )
    tracker = MagicMock()
    tracker.fetch_issue_detail.return_value = issue
    store = MagicMock()
    store.preserve_worktree_changes.return_value = {
        "snapshot_head": "c" * 40,
        "recovery_ref": "refs/oompah/recovery/TASK-1",
        "publication_state": "published",
    }
    orch.state.running[issue.id] = entry
    orch.state.completed.add(issue.id)
    orch._post_comment = MagicMock()

    with (
        patch.object(orch, "_tracker_for_project", return_value=tracker),
        patch.object(orch, "project_store", store),
    ):
        await orch._handle_revoked_submission_exit(
            entry,
            issue.id,
            issue.project_id,
            record,
        )

    tracker.update_issue.assert_called_once_with(issue.identifier, status=OPEN)
    assert issue.id not in orch.state.completed


@pytest.mark.asyncio
async def test_durable_submission_fences_after_assignment_clear(tmp_path):
    """The validation event uses post-clear authority, never the stale claim."""
    from oompah.server import _accept_worker_submission

    issue = _issue(state="In Progress")
    issue.integration = None
    stale_revision = issue_authority_version(issue)
    tracker = MagicMock()
    tracker.fetch_issue_detail.return_value = issue
    tracker.get_metadata.return_value = {
        "oompah.agent_run_id": "assignment-1"
    }
    entry = SimpleNamespace(
        issue=issue,
        identifier=issue.identifier,
        run_id="run-1",
        authority_generation="generation-1",
    )
    orch = MagicMock()
    orch.project_store = None
    orch.config.parallel_epic_children_enabled = False
    orch.workflow_runtime = SimpleNamespace(enforce=True)
    orch.issue_transition_lock.return_value = asyncio.Lock()
    orch._current_running_entry.return_value = entry
    orch._schedule_implementation_workflow_event.return_value = SimpleNamespace(
        job_id="validation-job"
    )
    orch.coordination_checkpoint.return_value = {"peers": []}

    accepted = await _accept_worker_submission(
        orch,
        tracker,
        issue.identifier,
        issue.project_id,
        {
            "summary": "Completed and tested",
            "task_branch": issue.work_branch,
            "head_sha": "a" * 40,
            "remote_head_sha": "a" * 40,
            "worktree_clean": True,
        },
        initial_issue=issue,
    )

    tracker.set_metadata_field.assert_any_call(
        issue.identifier, "oompah.agent_run_id", None
    )
    assert accepted.issue.assignment_id is None
    scheduled = orch._schedule_implementation_workflow_event.call_args.kwargs
    assert scheduled["payload"]["assignment_id"] == ""
    assert scheduled["payload"]["prior_generation"] == "generation-1"
    assert scheduled["payload"]["run_id"] == "run-1"
    assert scheduled["expected_evidence_revision"] == issue_authority_version(
        accepted.issue
    )
    assert scheduled["expected_evidence_revision"] != stale_revision


@pytest.mark.asyncio
async def test_submission_rejects_tracker_row_from_another_project():
    from oompah.server import _accept_worker_submission

    issue = _issue(state="In Progress")
    issue.project_id = "project-b"
    tracker = MagicMock()
    tracker.fetch_issue_detail.return_value = issue
    orch = MagicMock()
    orch.issue_transition_lock.return_value = asyncio.Lock()

    with pytest.raises(ValueError, match="authenticated project"):
        await _accept_worker_submission(
            orch,
            tracker,
            issue.identifier,
            "project-a",
            {
                "summary": "must not cross scope",
                "task_branch": issue.work_branch,
                "head_sha": "a" * 40,
            },
            initial_issue=issue,
        )

    tracker.set_metadata_field.assert_not_called()


def test_submission_runtime_lookup_is_exact_project_scoped():
    from oompah.server import _exact_implementation_running_entry

    issue = _issue(state="In Progress")
    foreign_issue = replace(issue, project_id="project-b")
    orch = MagicMock()
    orch._current_running_entry.return_value = SimpleNamespace(
        issue=foreign_issue,
        identifier=foreign_issue.identifier,
        run_id="foreign-run",
        authority_generation="foreign-generation",
    )

    assert _exact_implementation_running_entry(orch, issue, "project-a") is None


@pytest.mark.asyncio
async def test_submission_acceptance_revokes_worker_authority(tmp_path):
    """Verify that accepting a submission immediately revokes worker authority."""
    orch = _orchestrator(tmp_path)
    issue = _issue(state="Ready to Integrate")
    
    # Create a running entry
    entry = RunningEntry(
        worker_task=None,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        assignment_id="assignment-1",
        authority_generation="gen-123",
    )
    orch.state.running[issue.id] = entry
    orch.state.claimed.add(issue.id)
    
    # Mock the tracker and gates
    tracker_mock = MagicMock()
    tracker_mock.set_metadata_field.return_value = None
    tracker_mock.update_issue.return_value = None
    tracker_mock.fetch_issue_detail.return_value = issue
    
    with patch.object(orch, "_tracker_for_project", return_value=tracker_mock):
        with patch.object(orch, "_run_unpushed_gate", return_value=True):
            with patch.object(orch, "_run_completion_verifier") as verifier_mock:
                verifier_mock.return_value.passed = True
                with patch.object(orch, "_capture_worker_submission_record") as capture_mock:
                    capture_mock.return_value = IntegrationRecord(
                        state="ready",
                        head_sha="a" * 40,
                    )
                    with patch.object(orch, "_cancel_retry_for_issue") as cancel_mock:
                        # Call the method
                        result = orch._accept_worker_submission(entry, issue, issue.project_id)
                        
                        # Verify submission was accepted
                        assert result is True
                        
                        # Verify authority cancellation was called
                        cancel_mock.assert_called_once()
                        call_args = cancel_mock.call_args
                        assert call_args[1]["reason"] == "task submitted for integration"
                        
                        # Verify the submission record was set on the entry
                        assert entry.accepted_submission_record is not None
                        assert entry.accepted_submission_record.state == "ready"


@pytest.mark.asyncio
async def test_worker_exit_routes_revoked_submission_to_normalized_exact_project(
    tmp_path,
):
    orch = _orchestrator(tmp_path)
    issue = _issue(project_id="  project-a  ")
    record = IntegrationRecord(state="ready", head_sha="a" * 40)
    entry = RunningEntry(
        worker_task=asyncio.create_task(asyncio.sleep(0)),
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        assignment_id="assignment-1",
        authority_generation="generation-1",
        authority_revoked=True,
        accepted_submission_record=record,
    )
    orch.state.running[issue.id] = entry

    with patch.object(
        orch, "_handle_revoked_submission_exit", new_callable=AsyncMock
    ) as handler:
        await orch._on_worker_exit(
            issue.id,
            "normal",
            None,
            run_id=entry.run_id,
        )
    await entry.worker_task

    handler.assert_awaited_once_with(
        entry,
        issue.id,
        "project-a",
        record,
    )


@pytest.mark.asyncio
async def test_revoked_submission_rejects_cross_project_tracker_record(tmp_path):
    orch = _orchestrator(tmp_path)
    issue = _issue(project_id="project-a")
    foreign = _issue(project_id="project-b")
    record = IntegrationRecord(state="ready", head_sha="a" * 40)
    entry = RunningEntry(
        worker_task=asyncio.create_task(asyncio.sleep(0)),
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        assignment_id="assignment-1",
        authority_revoked=True,
        accepted_submission_record=record,
    )
    orch.state.running[issue.id] = entry
    orch.state.claimed.add(issue.id)
    orch.state.completed.add(issue.id)
    tracker = MagicMock()
    tracker.fetch_issue_detail.return_value = foreign

    with patch.object(
        orch, "_tracker_for_project", return_value=tracker
    ) as tracker_for_project:
        await orch._handle_revoked_submission_exit(
            entry,
            issue.id,
            "project-a",
            record,
        )
    await entry.worker_task

    tracker_for_project.assert_called_once_with("project-a")
    tracker.update_issue.assert_not_called()
    assert issue.id not in orch.state.running
    assert issue.id not in orch.state.completed


@pytest.mark.asyncio
async def test_revoked_submission_preserves_replacement_installed_during_recovery(
    tmp_path,
):
    orch = _orchestrator(tmp_path)
    issue = _issue(project_id="project-a")
    replacement_issue = _issue(project_id="project-a", state=OPEN)
    record = IntegrationRecord(state="ready", head_sha="a" * 40)
    entry = RunningEntry(
        worker_task=asyncio.create_task(asyncio.sleep(0)),
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        assignment_id="assignment-1",
        workspace_path=str(tmp_path),
        authority_revoked=True,
        accepted_submission_record=record,
    )
    replacement = RunningEntry(
        worker_task=asyncio.create_task(asyncio.sleep(0)),
        identifier=replacement_issue.identifier,
        issue=replacement_issue,
        session=None,
        retry_attempt=1,
        started_at=datetime.now(timezone.utc),
        assignment_id="assignment-2",
    )
    assert replacement.run_id != entry.run_id
    orch.state.running[issue.id] = entry
    orch.state.claimed.add(issue.id)
    orch.state.claimed_issues[issue.id] = issue

    project_store = MagicMock()

    def install_replacement(*_args):
        orch._register_running_entry(issue.id, replacement)
        orch.state.claimed.add(issue.id)
        orch.state.claimed_issues[issue.id] = replacement_issue
        return None

    project_store.preserve_worktree_changes.side_effect = install_replacement
    tracker = MagicMock()
    tracker.fetch_issue_detail.return_value = issue

    with (
        patch.object(orch, "project_store", project_store),
        patch.object(orch, "_tracker_for_project", return_value=tracker),
    ):
        await orch._handle_revoked_submission_exit(
            entry,
            issue.id,
            issue.project_id,
            record,
        )
    await entry.worker_task
    await replacement.worker_task

    assert orch.state.running[issue.id] is replacement
    assert issue.id in orch.state.claimed
    assert orch.state.claimed_issues[issue.id] is replacement_issue
    tracker.fetch_issue_detail.assert_not_called()
    tracker.update_issue.assert_not_called()


@pytest.mark.asyncio
async def test_non_revoked_submission_exit_keeps_ordinary_retry_path(tmp_path):
    orch = _orchestrator(tmp_path)
    issue = _issue(project_id="  project-a  ")
    record = IntegrationRecord(state="ready", head_sha="a" * 40)
    entry = RunningEntry(
        worker_task=asyncio.create_task(asyncio.sleep(0)),
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        assignment_id="assignment-1",
        authority_generation="generation-1",
        accepted_submission_record=record,
    )
    orch.state.running[issue.id] = entry

    with (
        patch.object(
            orch, "_handle_revoked_submission_exit", new_callable=AsyncMock
        ) as handler,
        patch.object(orch, "_post_comment"),
        patch.object(orch, "_schedule_retry") as schedule_retry,
        patch.object(orch, "_fire_task_cost_record"),
        patch.object(orch, "_fire_telemetry_comment"),
    ):
        await orch._on_worker_exit(
            issue.id,
            "abnormal",
            "provider failed",
            run_id=entry.run_id,
        )
    await entry.worker_task

    handler.assert_not_awaited()
    assert schedule_retry.call_args.kwargs["project_id"] == "project-a"
    assert issue.id not in orch.state.running
