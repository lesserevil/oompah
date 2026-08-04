"""Tests for nested epic rollup cycle fix (OOMPAH-748).

Verifies that a nested epic child can reach Merged state when its branch
lands on the immediate parent branch, without requiring the root epic
to land on main first.
"""

from unittest.mock import MagicMock, patch
import pytest

from oompah.models import Issue
from oompah.orchestrator import Orchestrator
from oompah.config import ServiceConfig
from oompah.scm import ReviewRequest
from oompah.terminal_audit import TargetState
from oompah.terminal_transition_coordinator import TransitionResult


def _make_project(project_id: str = "proj-1", branch: str = "main") -> MagicMock:
    p = MagicMock()
    p.id = project_id
    p.name = "test-project"
    p.repo_url = "https://github.com/org/repo"
    p.repo_path = "/tmp/repo"
    p.branch = branch
    p.default_branch = branch
    p.branches = [branch]
    p.paused = False
    p.epic_strategy = "shared"
    p.max_in_flight_prs = 1
    p.access_token = None
    return p


def _make_issue(
    identifier: str,
    *,
    state: str = "closed",
    issue_type: str = "task",
    parent_id: str | None = None,
    project_id: str = "proj-1",
    branch_name: str | None = None,
) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=f"Issue {identifier}",
        description="",
        state=state,
        issue_type=issue_type,
        parent_id=parent_id,
        project_id=project_id,
        branch_name=branch_name or identifier,
    )


def _make_review(
    *,
    number: int,
    state: str,
    source_branch: str,
    target_branch: str = "main",
) -> ReviewRequest:
    return ReviewRequest(
        id=str(number),
        title=f"PR #{number}",
        url=f"https://example.com/pulls/{number}",
        author="someone",
        state=state,
        source_branch=source_branch,
        target_branch=target_branch,
        created_at="",
        updated_at="",
    )


def _make_orch(tmp_path, *, project=None):
    """Build an Orchestrator with mock store/tracker/provider plumbed in."""
    from unittest.mock import AsyncMock
    
    if project is None:
        project = _make_project()

    project_store = MagicMock()
    project_store.list_all.return_value = [project]
    project_store.get.side_effect = lambda pid: project if pid == project.id else None
    project_store.epic_branch_name.side_effect = lambda i: f"epic-{i}"

    orch = Orchestrator(
        config=ServiceConfig(),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
    )
    # Mock the coordinator's request_transition to return success
    orch.terminal_transition_coordinator.request_transition = AsyncMock(
        return_value=TransitionResult(
            success=True,
            audit_id="audit-123",
            queued_targets=[TargetState.MERGED],
            coalesced=False,
            superseded_audit_id=None,
            reason=None,
        )
    )
    return orch


class TestNestedEpicCycleFix:
    """Test that nested epic cycles are broken by target-relative validation."""
    
    def test_nested_epic_auto_close_when_landed_on_parent_branch(self, tmp_path):
        """A nested epic can auto-close when landed on parent branch, 
        before the parent lands on main.
        
        Scenario:
        - Parent epic has open PR to main (not yet merged)
        - Nested child epic has merged PR to parent epic branch
        - Nested child's branch is confirmed merged to parent epic branch
        - Child should be able to auto-close without waiting for parent→main merge
        """
        project = _make_project()
        
        # Root parent epic - has children and open PR to main
        parent_epic = _make_issue(
            "epic-EXOCOMP-127",
            issue_type="epic",
            state="open",
            parent_id=None,  # No parent - this is the root
            branch_name="epic-epic-EXOCOMP-127",
        )
        
        # Nested child epic - landed on parent branch
        nested_child = _make_issue(
            "epic-EXOCOMP-128",
            issue_type="epic",
            state="open",  # Still open, waiting for auto-close
            parent_id="epic-EXOCOMP-127",  # Child of parent epic
            branch_name="epic-epic-EXOCOMP-128",
        )
        
        # One regular child task - also closed and merged
        regular_child = _make_issue(
            "task-EXOCOMP-129",
            issue_type="task",
            state="closed",
            parent_id="epic-EXOCOMP-128",  # Child of nested epic
            branch_name="task-EXOCOMP-129",
        )
        
        tracker = MagicMock()
        orch = _make_orch(tmp_path, project=project)
        orch._project_trackers[project.id] = tracker
        
        # Provider: tracks PR states
        provider = MagicMock()
        def find_pr_for_branch(slug, branch):
            if branch == "epic-epic-EXOCOMP-128":
                # Nested child PR: MERGED to parent epic branch (not main!)
                return _make_review(
                    number=21,
                    state="merged",
                    source_branch="epic-epic-EXOCOMP-128",
                    target_branch="epic-epic-EXOCOMP-127",  # <-- parent branch
                )
            elif branch == "task-EXOCOMP-129":
                # Regular child PR: merged to nested epic branch
                return _make_review(
                    number=28,
                    state="merged",
                    source_branch="task-EXOCOMP-129",
                    target_branch="epic-epic-EXOCOMP-128",
                )
            elif branch == "epic-epic-EXOCOMP-127":
                # Parent epic PR: OPEN to main (not yet merged!)
                return _make_review(
                    number=99,
                    state="open",
                    source_branch="epic-epic-EXOCOMP-127",
                    target_branch="main",
                )
            return None
        
        provider.find_pr_for_branch.side_effect = find_pr_for_branch
        provider.list_merged_reviews.return_value = []
        
        # Verify: nested child can auto-close despite parent not being on main
        with (
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
            patch.object(orch, "_fetch_epic_children", return_value=[regular_child]),
            patch.object(orch, "_tracker_for_issue", return_value=tracker),
            patch.object(orch, "_request_epic_terminal_rollup") as mock_close,
            patch.object(orch, "_resolve_parent_epic", return_value=parent_epic),
            patch.object(orch, "_epic_branch_for_issue", side_effect=lambda issue: {
                "epic-EXOCOMP-127": "epic-epic-EXOCOMP-127",
                "epic-EXOCOMP-128": "epic-epic-EXOCOMP-128",
                "task-EXOCOMP-129": "task-EXOCOMP-129",
            }.get(issue.identifier, issue.identifier)),
        ):
            # This should pass because:
            # 1. All children (just task-EXOCOMP-129) are closed ✓
            # 2. All children are merged to nested epic branch (epic-epic-EXOCOMP-128) ✓
            # 3. Nested epic's own branch is merged to PARENT branch (epic-epic-EXOCOMP-127) ✓
            #    (NOT requiring parent→main merge)
            result = orch._epic_auto_close_check(nested_child)
        
        # The nested child should close successfully
        assert result is True
        mock_close.assert_called_once()
        # Verify the request was for the nested child
        call_args = mock_close.call_args
        assert call_args.args[0].identifier == "epic-EXOCOMP-128"
        
        # Verify comment was posted
        tracker.append_comment.assert_called_once()
        reason = tracker.append_comment.call_args.args[1]
        assert "epic-EXOCOMP-128" not in reason or "merged" in reason.lower()
    
    def test_root_epic_still_requires_main_merge_for_auto_close(self, tmp_path):
        """A root-level epic still requires its branch to be merged to main
        before auto-close (not just to parent, since it has no parent).
        
        This verifies the fix doesn't break the original behavior for
        root epics.
        """
        project = _make_project()
        
        # Root epic with no parent
        root_epic = _make_issue(
            "epic-A",
            issue_type="epic",
            state="open",
            parent_id=None,  # No parent
            branch_name="epic-epic-A",
        )
        
        # Child task
        child = _make_issue(
            "task-A1",
            issue_type="task",
            state="closed",
            parent_id="epic-A",
            branch_name="task-A1",
        )
        
        tracker = MagicMock()
        orch = _make_orch(tmp_path, project=project)
        orch._project_trackers[project.id] = tracker
        
        provider = MagicMock()
        def find_pr(slug, branch):
            if branch == "task-A1":
                # Child merged to epic branch
                return _make_review(
                    number=1,
                    state="merged",
                    source_branch="task-A1",
                    target_branch="epic-epic-A",
                )
            elif branch == "epic-epic-A":
                # Epic branch NOT merged to main
                return _make_review(
                    number=99,
                    state="open",
                    source_branch="epic-epic-A",
                    target_branch="main",
                )
            return None
        
        provider.find_pr_for_branch.side_effect = find_pr
        provider.list_merged_reviews.return_value = []
        
        with (
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
            patch.object(orch, "_fetch_epic_children", return_value=[child]),
            patch.object(orch, "_tracker_for_issue", return_value=tracker),
            patch.object(orch, "_request_epic_terminal_rollup") as mock_close,
            patch.object(orch, "_epic_branch_for_issue", return_value="epic-epic-A"),
        ):
            result = orch._epic_auto_close_check(root_epic)
        
        # Root epic should NOT close because its branch isn't on main yet
        assert result is False
        mock_close.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
