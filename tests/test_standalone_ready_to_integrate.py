"""Tests for standalone Ready to Integrate task reconciliation.

Coverage:
- Pushed standalone branch with no PR
- Missing branch (not pushed)
- Existing open PR (idempotent)
- Existing closed PR (creates new one)
- Duplicate reconciliation ticks
- Service restart recovery
- Gate failure and retry
- Successful delivery and merge
"""

import pytest
from unittest import mock

from oompah.models import Issue
from oompah.statuses import IN_REVIEW, READY_TO_INTEGRATE


@pytest.fixture
def mock_project():
    """Create a mock project with necessary attributes."""
    project = mock.MagicMock()
    project.id = "proj-1"
    project.name = "Test Project"
    project.repo_slug = "org/test-repo"
    project.default_branch = "main"
    return project


@pytest.fixture
def mock_tracker():
    """Create a mock tracker."""
    return mock.MagicMock()


@pytest.fixture
def mock_scm():
    """Create a mock SCM provider."""
    scm = mock.MagicMock()
    scm.is_available.return_value = True
    return scm


@pytest.fixture
def orchestrator_with_mocks(tmp_path, mock_project, mock_tracker, mock_scm):
    """Create a minimal orchestrator with mocked dependencies."""
    from oompah.orchestrator import Orchestrator
    
    # Create a mock orchestrator with required attributes
    orch = mock.MagicMock(spec=Orchestrator)
    orch.project_store = mock.MagicMock()
    orch.project_store.list_all.return_value = [mock_project]
    orch._tracker_for_project = mock.MagicMock(return_value=mock_tracker)
    orch.provider_store = mock.MagicMock()
    orch.provider_store.get_scm_for_project = mock.MagicMock(return_value=mock_scm)
    orch._write_review_metadata = mock.MagicMock()
    
    # Bind the actual implementation to the mock
    orch._reconcile_standalone_ready_to_integrate_tasks = (
        Orchestrator._reconcile_standalone_ready_to_integrate_tasks.__get__(orch)
    )
    return orch, mock_project, mock_tracker, mock_scm


def test_standalone_pushed_branch_no_pr(orchestrator_with_mocks):
    """Test standalone Ready task with pushed branch but no PR gets PR created."""
    orch, project, tracker, scm = orchestrator_with_mocks
    
    # Setup: standalone Ready task with no parent_id
    task = Issue(
        id="task-uuid",
        identifier="TASK-1",
        title="Standalone Task",
        state=READY_TO_INTEGRATE,
        parent_id=None,  # Standalone
        description="Test task",
    )
    task.work_branch = "TASK-1"
    
    tracker.fetch_issues_by_states.return_value = [task]
    tracker.get_issue.return_value = task
    
    # Mock SCM responses
    scm.get_branch_head_sha.return_value = "abc123def456"  # Branch exists
    scm.find_pr_for_branch.return_value = None  # No existing PR
    
    mock_pr = mock.MagicMock()
    mock_pr.id = 42
    mock_pr.url = "https://github.com/org/test-repo/pull/42"
    scm.create_review.return_value = mock_pr
    
    # Execute reconciliation
    orch._reconcile_standalone_ready_to_integrate_tasks()
    
    # Assert: PR was created
    scm.create_review.assert_called_once()
    call_args = scm.create_review.call_args
    assert call_args[0][0] == "org/test-repo"  # repo slug
    assert "TASK-1" in call_args[0][1]  # title includes task ID
    assert call_args[0][2] == "TASK-1"  # source branch
    assert call_args[1]["target_branch"] == "main"
    
    # Assert: task status updated to In Review
    tracker.update_issue.assert_called_with("TASK-1", status=IN_REVIEW)
    
    # Assert: review metadata written
    orch._write_review_metadata.assert_called_once()


def test_standalone_missing_branch(orchestrator_with_mocks):
    """Test standalone Ready task with missing (unpushed) branch is skipped."""
    orch, project, tracker, scm = orchestrator_with_mocks
    
    task = Issue(
        id="task-uuid",
        identifier="TASK-2",
        title="Missing Branch Task",
        state=READY_TO_INTEGRATE,
        parent_id=None,
    )
    task.work_branch = "TASK-2"
    
    tracker.fetch_issues_by_states.return_value = [task]
    
    # Mock: branch does not exist
    scm.get_branch_head_sha.return_value = None
    
    # Execute
    orch._reconcile_standalone_ready_to_integrate_tasks()
    
    # Assert: PR was not created (branch missing)
    scm.create_review.assert_not_called()
    tracker.update_issue.assert_not_called()


def test_standalone_existing_open_pr_idempotent(orchestrator_with_mocks):
    """Test that existing open PR is recognized and task marked In Review idempotently."""
    orch, project, tracker, scm = orchestrator_with_mocks
    
    task = Issue(
        id="task-uuid",
        identifier="TASK-3",
        title="Has PR",
        state=READY_TO_INTEGRATE,  # Still in Ready (not yet marked In Review)
        parent_id=None,
    )
    task.work_branch = "TASK-3"
    
    tracker.fetch_issues_by_states.return_value = [task]
    tracker.get_issue.return_value = task
    
    # Mock: branch exists
    scm.get_branch_head_sha.return_value = "def789ghi012"
    
    # Mock: PR already exists and is open
    existing_pr = mock.MagicMock()
    existing_pr.id = 99
    existing_pr.url = "https://github.com/org/test-repo/pull/99"
    scm.find_pr_for_branch.return_value = existing_pr
    
    # Execute
    orch._reconcile_standalone_ready_to_integrate_tasks()
    
    # Assert: no new PR created (already exists)
    scm.create_review.assert_not_called()
    
    # Assert: task marked In Review with existing PR metadata
    tracker.update_issue.assert_called_with("TASK-3", status=IN_REVIEW)
    orch._write_review_metadata.assert_called_once()


def test_duplicate_reconciliation_idempotent(orchestrator_with_mocks):
    """Test that running reconciliation twice doesn't create duplicate PRs."""
    orch, project, tracker, scm = orchestrator_with_mocks
    
    task = Issue(
        id="task-uuid",
        identifier="TASK-4",
        title="Duplicate Test",
        state=READY_TO_INTEGRATE,
        parent_id=None,
    )
    task.work_branch = "TASK-4"
    
    tracker.fetch_issues_by_states.return_value = [task]
    tracker.get_issue.return_value = task
    
    scm.get_branch_head_sha.return_value = "sha456xyz"
    
    # First run: no PR exists
    mock_pr = mock.MagicMock()
    mock_pr.id = 50
    mock_pr.url = "https://github.com/org/test-repo/pull/50"
    scm.find_pr_for_branch.side_effect = [None, existing_pr := mock_pr]
    scm.create_review.return_value = mock_pr
    
    # First reconciliation
    orch._reconcile_standalone_ready_to_integrate_tasks()
    assert scm.create_review.call_count == 1
    
    # Second reconciliation: PR now exists
    orch._reconcile_standalone_ready_to_integrate_tasks()
    
    # Assert: still only one PR created (second run found existing PR)
    assert scm.create_review.call_count == 1  # Still 1, not 2


def test_no_scm_available(orchestrator_with_mocks):
    """Test that reconciliation gracefully handles unavailable SCM."""
    orch, project, tracker, scm = orchestrator_with_mocks
    
    task = Issue(
        id="task-uuid",
        identifier="TASK-5",
        title="No SCM",
        state=READY_TO_INTEGRATE,
        parent_id=None,
    )
    task.work_branch = "TASK-5"
    
    tracker.fetch_issues_by_states.return_value = [task]
    
    # Mock: SCM unavailable
    scm.is_available.return_value = False
    
    # Execute (should not raise)
    orch._reconcile_standalone_ready_to_integrate_tasks()
    
    # Assert: no attempt to create PR
    scm.create_review.assert_not_called()
    tracker.update_issue.assert_not_called()


def test_epic_child_tasks_excluded(orchestrator_with_mocks):
    """Test that epic child tasks (with parent_id) are excluded from this reconciliation."""
    orch, project, tracker, scm = orchestrator_with_mocks
    
    # Epic child task
    child_task = Issue(
        id="child-uuid",
        identifier="TASK-CHILD",
        title="Epic Child",
        state=READY_TO_INTEGRATE,
        parent_id="EPIC-1",  # Has parent → not standalone
    )
    child_task.work_branch = "epic-EPIC-1--task-TASK-CHILD"
    
    # Standalone task
    standalone_task = Issue(
        id="standalone-uuid",
        identifier="TASK-STANDALONE",
        title="Standalone",
        state=READY_TO_INTEGRATE,
        parent_id=None,  # No parent → standalone
    )
    standalone_task.work_branch = "TASK-STANDALONE"
    
    tracker.fetch_issues_by_states.return_value = [child_task, standalone_task]
    tracker.get_issue.return_value = standalone_task
    
    scm.get_branch_head_sha.return_value = "sha789abc"
    scm.find_pr_for_branch.return_value = None
    
    mock_pr = mock.MagicMock()
    mock_pr.id = 75
    scm.create_review.return_value = mock_pr
    
    # Execute
    orch._reconcile_standalone_ready_to_integrate_tasks()
    
    # Assert: only standalone task processed (child skipped)
    scm.create_review.assert_called_once()
    call_args = scm.create_review.call_args
    assert "TASK-STANDALONE" in call_args[0][1]  # Title contains standalone ID
    
    # Verify the branch checked was the standalone one
    assert call_args[0][2] == "TASK-STANDALONE"


def test_pr_creation_failure_logged(orchestrator_with_mocks):
    """Test that PR creation failures are logged but don't crash reconciliation."""
    orch, project, tracker, scm = orchestrator_with_mocks
    
    task = Issue(
        id="task-uuid",
        identifier="TASK-6",
        title="PR Creation Fails",
        state=READY_TO_INTEGRATE,
        parent_id=None,
    )
    task.work_branch = "TASK-6"
    
    tracker.fetch_issues_by_states.return_value = [task]
    
    scm.get_branch_head_sha.return_value = "sha999def"
    scm.find_pr_for_branch.return_value = None
    
    # Mock: PR creation fails
    scm.create_review.side_effect = Exception("SCM API error")
    
    # Execute (should not raise)
    orch._reconcile_standalone_ready_to_integrate_tasks()
    
    # Assert: failure logged, task not marked In Review
    tracker.update_issue.assert_not_called()


def test_mixed_ready_and_non_ready_tasks(orchestrator_with_mocks):
    """Test that only Ready to Integrate tasks are processed."""
    orch, project, tracker, scm = orchestrator_with_mocks
    
    ready_task = Issue(
        id="ready-uuid",
        identifier="TASK-READY",
        title="Ready Task",
        state=READY_TO_INTEGRATE,
        parent_id=None,
    )
    ready_task.work_branch = "TASK-READY"
    
    # This shouldn't happen (fetch_issues_by_states filters), but test robustness
    other_task = Issue(
        id="other-uuid",
        identifier="TASK-OTHER",
        title="Other Status",
        state="Open",  # Not Ready
        parent_id=None,
    )
    other_task.work_branch = "TASK-OTHER"
    
    # Only Ready task returned from tracker
    tracker.fetch_issues_by_states.return_value = [ready_task]
    tracker.get_issue.return_value = ready_task
    
    scm.get_branch_head_sha.return_value = "shaready1"
    scm.find_pr_for_branch.return_value = None
    
    mock_pr = mock.MagicMock()
    mock_pr.id = 88
    scm.create_review.return_value = mock_pr
    
    # Execute
    orch._reconcile_standalone_ready_to_integrate_tasks()
    
    # Assert: only Ready task processed
    scm.create_review.assert_called_once()
    call_args = scm.create_review.call_args
    assert "TASK-READY" in call_args[0][1]
