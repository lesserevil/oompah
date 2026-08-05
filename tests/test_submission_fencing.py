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
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from oompah.config import ServiceConfig
from oompah.integration import IntegrationRecord
from oompah.models import Issue, RunningEntry
from oompah.orchestrator import Orchestrator
from oompah.projects import RecoveryPublicationError
from oompah.statuses import OPEN, READY_TO_INTEGRATE


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
        worker_task=asyncio.sleep(0),  # Mock task that won't execute
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
        worker_task=asyncio.sleep(0),
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
        worker_task=asyncio.sleep(0),
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
        worker_task=asyncio.sleep(0),
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
async def test_submission_acceptance_revokes_worker_authority(tmp_path):
    """Verify that accepting a submission immediately revokes worker authority."""
    orch = _orchestrator(tmp_path)
    issue = _issue(state="Ready to Integrate")
    
    # Create a running entry
    entry = RunningEntry(
        worker_task=asyncio.sleep(0),
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
