"""Tests for orchestrator merged-issue labeling and dispatch gating."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from oompah.config import ServiceConfig
from oompah.models import BlockerRef, Issue, RunningEntry
from oompah.orchestrator import Orchestrator
from oompah.scm import ReviewRequest


def _make_config() -> ServiceConfig:
    return ServiceConfig()


def _make_issue(identifier: str, state: str = "closed", labels: list | None = None,
                branch_name: str | None = None,
                description: str | None = "Issue body — exists so the empty-description gate passes.") -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=f"Issue {identifier}",
        description=description,
        state=state,
        labels=labels or [],
        branch_name=branch_name,
    )


def _make_project(project_id: str = "proj-1", repo_url: str = "https://github.com/org/repo",
                 churn_magnet_gate_enabled: bool = False,
                 churn_magnet_top_n: int = 10):
    p = MagicMock()
    p.id = project_id
    p.repo_url = repo_url
    p.name = "test-project"
    p.merge_queue_enabled = False  # default: direct-merge mode
    p.paused = False  # default: not paused
    p.churn_magnet_gate_enabled = churn_magnet_gate_enabled
    p.churn_magnet_top_n = churn_magnet_top_n
    return p


class TestLabelMergedIssues:
    """Tests for _label_merged_issues."""

    def _make_orchestrator(self, tmp_path, projects=None):
        project_store = MagicMock()
        project_store.list_all.return_value = projects or []
        project_store.get.side_effect = lambda pid: next(
            (p for p in (projects or []) if p.id == pid), None
        )
        orch = Orchestrator(
            config=_make_config(),
            workflow_path="WORKFLOW.md",
            project_store=project_store,
            state_path=str(tmp_path / "state.json"),
        )
        return orch

    def test_no_merged_branches_is_noop(self, tmp_path):
        orch = self._make_orchestrator(tmp_path)
        orch._merged_branches = set()
        orch._label_merged_issues()
        # No projects queried
        orch.project_store.list_all.assert_not_called()

    def test_labels_closed_issue_with_matching_branch(self, tmp_path):
        project = _make_project()
        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._merged_branches = {"feat-branch"}

        mock_tracker = MagicMock()
        mock_tracker.fetch_issues_by_states.return_value = [
            _make_issue("feat-branch", state="closed"),
        ]
        orch._project_trackers[project.id] = mock_tracker

        orch._label_merged_issues()

        mock_tracker.update_issue.assert_called_once_with(
            "feat-branch", status="Merged"
        )

    def test_labels_in_review_issue_with_matching_branch(self, tmp_path):
        project = _make_project()
        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._merged_branches = {"feat-branch"}

        mock_tracker = MagicMock()
        mock_tracker.fetch_issues_by_states.return_value = [
            _make_issue("feat-branch", state="In Review"),
        ]
        orch._project_trackers[project.id] = mock_tracker

        orch._label_merged_issues()

        queried_states = mock_tracker.fetch_issues_by_states.call_args.args[0]
        assert "In Review" in queried_states
        assert "Needs CI Fix" in queried_states
        assert "Needs Rebase" in queried_states
        mock_tracker.update_issue.assert_called_once_with(
            "feat-branch", status="Merged"
        )

    def test_skips_already_merged_label(self, tmp_path):
        project = _make_project()
        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._merged_branches = {"feat-branch"}

        mock_tracker = MagicMock()
        mock_tracker.fetch_issues_by_states.return_value = [
            _make_issue("feat-branch", state="closed", labels=["merged"]),
        ]
        orch._project_trackers[project.id] = mock_tracker

        orch._label_merged_issues()

        mock_tracker.update_issue.assert_not_called()

    def test_skips_archived_issues(self, tmp_path):
        project = _make_project()
        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._merged_branches = {"feat-branch"}

        mock_tracker = MagicMock()
        mock_tracker.fetch_issues_by_states.return_value = [
            _make_issue("feat-branch", state="closed", labels=["archive:yes"]),
        ]
        orch._project_trackers[project.id] = mock_tracker

        orch._label_merged_issues()

        mock_tracker.update_issue.assert_not_called()

    def test_skips_issue_without_matching_branch(self, tmp_path):
        project = _make_project()
        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._merged_branches = {"some-other-branch"}

        mock_tracker = MagicMock()
        mock_tracker.fetch_issues_by_states.return_value = [
            _make_issue("feat-branch", state="closed"),
        ]
        orch._project_trackers[project.id] = mock_tracker

        orch._label_merged_issues()

        mock_tracker.update_issue.assert_not_called()

    def test_uses_branch_name_field_over_identifier(self, tmp_path):
        project = _make_project()
        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._merged_branches = {"custom-branch"}

        mock_tracker = MagicMock()
        mock_tracker.fetch_issues_by_states.return_value = [
            _make_issue("issue-123", state="closed", branch_name="custom-branch"),
        ]
        orch._project_trackers[project.id] = mock_tracker

        orch._label_merged_issues()

        mock_tracker.update_issue.assert_called_once_with(
            "issue-123", status="Merged"
        )

    def test_tracker_error_does_not_crash(self, tmp_path):
        from oompah.tracker import TrackerError

        project = _make_project()
        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._merged_branches = {"feat-branch"}

        mock_tracker = MagicMock()
        mock_tracker.fetch_issues_by_states.side_effect = TrackerError("db down")
        orch._project_trackers[project.id] = mock_tracker

        # Should not raise
        orch._label_merged_issues()

    def test_update_status_error_does_not_crash(self, tmp_path):
        from oompah.tracker import TrackerError

        project = _make_project()
        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._merged_branches = {"feat-branch"}

        mock_tracker = MagicMock()
        mock_tracker.fetch_issues_by_states.return_value = [
            _make_issue("feat-branch", state="closed"),
        ]
        mock_tracker.update_issue.side_effect = TrackerError("tracker failed")
        orch._project_trackers[project.id] = mock_tracker

        # Should not raise
        orch._label_merged_issues()


class TestFetchAllMergedBranches:
    """Tests for _fetch_all_merged_branches."""

    def test_no_projects_returns_empty(self, tmp_path):
        project_store = MagicMock()
        project_store.list_all.return_value = []
        orch = Orchestrator(
            config=_make_config(),
            workflow_path="WORKFLOW.md",
            project_store=project_store,
            state_path=str(tmp_path / "state.json"),
        )
        assert orch._fetch_all_merged_branches() == set()

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_aggregates_branches_across_projects(self, mock_slug, mock_detect, tmp_path):
        proj1 = _make_project("p1", "https://github.com/org/repo1")
        proj2 = _make_project("p2", "https://github.com/org/repo2")

        provider1 = MagicMock()
        provider1.list_merged_branches.return_value = {"branch-a", "branch-b"}
        provider2 = MagicMock()
        provider2.list_merged_branches.return_value = {"branch-c"}

        mock_detect.side_effect = [provider1, provider2]
        mock_slug.side_effect = ["org/repo1", "org/repo2"]

        project_store = MagicMock()
        project_store.list_all.return_value = [proj1, proj2]

        orch = Orchestrator(
            config=_make_config(),
            workflow_path="WORKFLOW.md",
            project_store=project_store,
            state_path=str(tmp_path / "state.json"),
        )
        result = orch._fetch_all_merged_branches()
        assert result == {"branch-a", "branch-b", "branch-c"}

    @patch("oompah.orchestrator.detect_provider")
    def test_unknown_provider_returns_empty(self, mock_detect, tmp_path):
        proj = _make_project()
        mock_detect.return_value = None

        project_store = MagicMock()
        project_store.list_all.return_value = [proj]

        orch = Orchestrator(
            config=_make_config(),
            workflow_path="WORKFLOW.md",
            project_store=project_store,
            state_path=str(tmp_path / "state.json"),
        )
        assert orch._fetch_all_merged_branches() == set()


class TestBlockerHasUnmergedPr:
    """Tests for _blocker_has_unmerged_pr dispatch gating."""

    def _make_orchestrator(self, tmp_path):
        orch = Orchestrator(
            config=_make_config(),
            workflow_path="WORKFLOW.md",
            state_path=str(tmp_path / "state.json"),
        )
        return orch

    def test_blocker_with_open_pr_is_unmerged(self, tmp_path):
        orch = self._make_orchestrator(tmp_path)
        orch._unmerged_review_branches = {"feat-branch"}
        orch._merged_branches = set()

        blocker = BlockerRef(id="feat-branch", identifier="feat-branch", state="closed")
        assert orch._blocker_has_unmerged_pr(blocker) is True

    def test_blocker_branch_merged_is_not_blocking(self, tmp_path):
        orch = self._make_orchestrator(tmp_path)
        orch._unmerged_review_branches = set()
        orch._merged_branches = {"feat-branch"}

        blocker = BlockerRef(id="feat-branch", identifier="feat-branch", state="closed")
        assert orch._blocker_has_unmerged_pr(blocker) is False

    def test_blocker_closed_no_open_pr_not_blocking(self, tmp_path):
        """Closed issue with no open PR should not block (may never have had an MR)."""
        orch = self._make_orchestrator(tmp_path)
        orch._unmerged_review_branches = set()
        orch._merged_branches = {"other-branch"}  # feat-branch NOT in merged set

        blocker = BlockerRef(id="feat-branch", identifier="feat-branch", state="closed")
        assert orch._blocker_has_unmerged_pr(blocker) is False

    def test_no_merged_data_falls_back_to_permissive(self, tmp_path):
        """If merged branch data unavailable, don't block (backwards compat)."""
        orch = self._make_orchestrator(tmp_path)
        orch._unmerged_review_branches = set()
        orch._merged_branches = None

        blocker = BlockerRef(id="feat-branch", identifier="feat-branch", state="closed")
        assert orch._blocker_has_unmerged_pr(blocker) is False

    def test_empty_blocker_id_is_not_blocking(self, tmp_path):
        orch = self._make_orchestrator(tmp_path)
        orch._unmerged_review_branches = set()
        orch._merged_branches = set()

        blocker = BlockerRef(id="", identifier="", state="closed")
        assert orch._blocker_has_unmerged_pr(blocker) is False


class TestResetOrphanedInProgress:
    """Tests for _reset_orphaned_in_progress."""

    def _make_orchestrator(self, tmp_path, projects=None):
        project_store = MagicMock()
        project_store.list_all.return_value = projects or []
        project_store.get.side_effect = lambda pid: next(
            (p for p in (projects or []) if p.id == pid), None
        )
        orch = Orchestrator(
            config=_make_config(),
            workflow_path="WORKFLOW.md",
            project_store=project_store,
            state_path=str(tmp_path / "state.json"),
        )
        return orch

    def test_resets_orphaned_in_progress_to_open(self, tmp_path):
        project = _make_project()
        orch = self._make_orchestrator(tmp_path, projects=[project])
        mock_tracker = MagicMock()
        orch._project_trackers[project.id] = mock_tracker

        issue = _make_issue("feat-1", state="in_progress")
        issue.project_id = project.id
        orch._reset_orphaned_in_progress([issue])

        mock_tracker.update_issue.assert_called_once_with("feat-1", status="Open")

    def test_resets_backlog_in_progress_to_open(self, tmp_path):
        project = _make_project()
        orch = self._make_orchestrator(tmp_path, projects=[project])
        mock_tracker = MagicMock()
        orch._project_trackers[project.id] = mock_tracker

        issue = _make_issue("feat-1", state="In Progress")
        issue.project_id = project.id
        orch._reset_orphaned_in_progress([issue])

        mock_tracker.update_issue.assert_called_once_with("feat-1", status="Open")

    def test_resets_ci_fix_orphan_to_needs_ci_fix_p0(self, tmp_path):
        project = _make_project()
        orch = self._make_orchestrator(tmp_path, projects=[project])
        mock_tracker = MagicMock()
        orch._project_trackers[project.id] = mock_tracker

        issue = _make_issue("feat-1", state="In Progress", labels=["ci-fix"])
        issue.project_id = project.id
        orch._reset_orphaned_in_progress([issue])

        mock_tracker.update_issue.assert_called_once_with(
            "feat-1",
            status="Needs CI Fix",
            priority="0",
        )

    def test_resets_merge_conflict_orphan_to_needs_rebase_p0(self, tmp_path):
        project = _make_project()
        orch = self._make_orchestrator(tmp_path, projects=[project])
        mock_tracker = MagicMock()
        orch._project_trackers[project.id] = mock_tracker

        issue = _make_issue("feat-1", state="In Progress", labels=["merge-conflict"])
        issue.project_id = project.id
        orch._reset_orphaned_in_progress([issue])

        mock_tracker.update_issue.assert_called_once_with(
            "feat-1",
            status="Needs Rebase",
            priority="0",
        )

    def test_skips_issue_with_running_agent(self, tmp_path):
        project = _make_project()
        orch = self._make_orchestrator(tmp_path, projects=[project])
        mock_tracker = MagicMock()
        orch._project_trackers[project.id] = mock_tracker

        issue = _make_issue("feat-1", state="in_progress")
        issue.project_id = project.id
        orch.state.running["feat-1"] = MagicMock()
        orch._reset_orphaned_in_progress([issue])

        mock_tracker.update_issue.assert_not_called()

    def test_skips_issue_with_pending_retry(self, tmp_path):
        project = _make_project()
        orch = self._make_orchestrator(tmp_path, projects=[project])
        mock_tracker = MagicMock()
        orch._project_trackers[project.id] = mock_tracker

        issue = _make_issue("feat-1", state="open")
        issue.project_id = project.id
        orch.state.retry_attempts["feat-1"] = MagicMock()
        orch._reset_orphaned_in_progress([issue])

        mock_tracker.update_issue.assert_not_called()

    def test_resets_completed_marker_orphaned_in_progress_to_open(self, tmp_path):
        project = _make_project()
        orch = self._make_orchestrator(tmp_path, projects=[project])
        mock_tracker = MagicMock()
        orch._project_trackers[project.id] = mock_tracker

        issue = _make_issue("feat-1", state="In Progress")
        issue.project_id = project.id
        orch.state.completed.add(issue.id)

        orch._reset_orphaned_in_progress([issue])

        mock_tracker.update_issue.assert_called_once_with("feat-1", status="Open")
        assert issue.id not in orch.state.completed

    def test_skips_open_issues(self, tmp_path):
        project = _make_project()
        orch = self._make_orchestrator(tmp_path, projects=[project])
        mock_tracker = MagicMock()
        orch._project_trackers[project.id] = mock_tracker

        issue = _make_issue("feat-1", state="open")
        issue.project_id = project.id
        orch._reset_orphaned_in_progress([issue])

        mock_tracker.update_issue.assert_not_called()


class TestFetchInProgressIssues:
    """Tests for fetching In Progress tasks independently of dispatch candidates."""

    def _make_orchestrator(self, tmp_path, projects=None):
        project_store = MagicMock()
        project_store.list_all.return_value = projects or []
        project_store.get.side_effect = lambda pid: next(
            (p for p in (projects or []) if p.id == pid), None
        )
        return Orchestrator(
            config=_make_config(),
            workflow_path="WORKFLOW.md",
            project_store=project_store,
            state_path=str(tmp_path / "state.json"),
        )

    def test_fetches_in_progress_from_project_trackers(self, tmp_path):
        project = _make_project(project_id="proj-a")
        orch = self._make_orchestrator(tmp_path, projects=[project])
        issue = _make_issue("feat-1", state="In Progress")
        mock_tracker = MagicMock()
        mock_tracker.fetch_issues_by_states.return_value = [issue]
        orch._project_trackers[project.id] = mock_tracker

        result = orch._fetch_in_progress_issues()

        mock_tracker.fetch_issues_by_states.assert_called_once_with(["In Progress"])
        assert result == [issue]
        assert result[0].project_id == project.id

    def test_fetches_in_progress_even_when_active_candidates_are_open_only(self, tmp_path):
        project = _make_project(project_id="proj-a")
        orch = self._make_orchestrator(tmp_path, projects=[project])
        open_issue = _make_issue("feat-open", state="Open")
        stuck_issue = _make_issue("feat-stuck", state="In Progress")
        mock_tracker = MagicMock()
        mock_tracker.fetch_candidate_issues.return_value = [open_issue]
        mock_tracker.fetch_issues_by_states.return_value = [stuck_issue]
        orch._project_trackers[project.id] = mock_tracker

        candidates = orch._fetch_all_candidates()
        in_progress = orch._fetch_in_progress_issues()

        assert candidates == [open_issue]
        assert in_progress == [stuck_issue]
        mock_tracker.fetch_issues_by_states.assert_called_once_with(["In Progress"])


class TestBacklogStatusReconciliation:
    """Tests for tracker status spelling used by Backlog.md."""

    def _make_orchestrator(self, tmp_path):
        config = _make_config()
        config.tracker_active_states = ["To Do", "In Progress"]
        config.tracker_terminal_states = ["Done"]
        return Orchestrator(
            config=config,
            workflow_path="WORKFLOW.md",
            state_path=str(tmp_path / "state.json"),
        )

    def test_reconcile_keeps_backlog_in_progress_agent_running(self, tmp_path):
        orch = self._make_orchestrator(tmp_path)
        issue = _make_issue("feat-1", state="To Do")
        fresh = _make_issue("feat-1", state="In Progress")
        task = MagicMock()
        task.done.return_value = True
        orch.state.running[issue.id] = RunningEntry(
            worker_task=task,
            identifier=issue.identifier,
            issue=issue,
            session=None,
            retry_attempt=0,
            started_at=datetime.now(timezone.utc),
        )
        orch._fetch_running_states = MagicMock(return_value={issue.id: fresh})
        orch._terminate_running = AsyncMock()

        asyncio.run(orch._reconcile())

        orch._terminate_running.assert_not_called()
        assert orch.state.running[issue.id].issue.state == "In Progress"


class TestShouldDispatchCompleted:
    """Tests that completed issues are not re-dispatched."""

    def _make_orchestrator(self, tmp_path, projects=None):
        project_store = MagicMock()
        project_store.list_all.return_value = projects or []
        orch = Orchestrator(
            config=_make_config(),
            workflow_path="WORKFLOW.md",
            project_store=project_store,
            state_path=str(tmp_path / "state.json"),
        )
        return orch

    def test_completed_issue_not_dispatched(self, tmp_path):
        """An issue in state.completed should not be re-dispatched."""
        orch = self._make_orchestrator(tmp_path)
        issue = _make_issue("feat-1", state="in_progress")
        orch.state.completed.add("feat-1")
        assert orch._should_dispatch(issue) is False

    def test_non_completed_issue_dispatched(self, tmp_path):
        """An issue NOT in state.completed should be dispatchable."""
        orch = self._make_orchestrator(tmp_path)
        issue = _make_issue("feat-1", state="open")
        assert orch._should_dispatch(issue) is True

    def test_empty_description_rejected(self, tmp_path):
        """A bead with no description body must not be dispatched.
        Title-only beads are placeholders (e.g. ad-hoc CLI tests) and
        agents have no useful context to work from."""
        orch = self._make_orchestrator(tmp_path)
        issue = _make_issue("feat-empty", state="open", description=None)
        assert orch._should_dispatch(issue) is False

    def test_whitespace_description_rejected(self, tmp_path):
        """Description that's only whitespace also counts as empty."""
        orch = self._make_orchestrator(tmp_path)
        issue = _make_issue("feat-ws", state="open", description="   \n  \t ")
        assert orch._should_dispatch(issue) is False

    def test_short_description_accepted(self, tmp_path):
        """Any non-blank description is enough — judgement of quality is
        the agent's job, not the dispatcher's."""
        orch = self._make_orchestrator(tmp_path)
        issue = _make_issue("feat-short", state="open", description="x")
        assert orch._should_dispatch(issue) is True


def _make_review(
    review_id: str,
    source_branch: str = "feat-branch",
    ci_status: str = "passed",
    has_conflicts: bool = False,
    needs_rebase: bool = False,
    draft: bool = False,
    labels: list[str] | None = None,
    churn_magnet: bool = False,
) -> ReviewRequest:
    return ReviewRequest(
        id=review_id,
        title=f"PR #{review_id}",
        url=f"https://github.com/org/repo/pull/{review_id}",
        author="alice",
        state="open",
        source_branch=source_branch,
        target_branch="main",
        created_at="2025-01-01",
        updated_at="2025-01-02",
        ci_status=ci_status,
        has_conflicts=has_conflicts,
        needs_rebase=needs_rebase,
        draft=draft,
        labels=labels or [],
        churn_magnet=churn_magnet,
    )


class TestYoloReviewSerializationByProject:
    """Tests that _yolo_review_actions_sync only acts on one MR/PR per project
    per tick, preventing merge conflicts from simultaneous merges."""

    def _make_orchestrator(self, tmp_path, projects=None):
        project_store = MagicMock()
        project_store.list_all.return_value = projects or []
        project_store.get.side_effect = lambda pid: next(
            (p for p in (projects or []) if p.id == pid), None
        )
        orch = Orchestrator(
            config=_make_config(),
            workflow_path="WORKFLOW.md",
            project_store=project_store,
            state_path=str(tmp_path / "state.json"),
        )
        return orch

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_only_one_merge_per_project_per_tick(self, mock_slug, mock_detect, tmp_path):
        """When multiple PRs are ready to merge, only merge the first one per tick."""
        project = _make_project()
        project.yolo = True

        provider = MagicMock()
        provider.merge_review.return_value = (True, "merged")
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = self._make_orchestrator(tmp_path, projects=[project])

        # Three PRs all with CI passed and no rebase needed
        reviews = [
            _make_review("1", source_branch="feat-1", ci_status="passed"),
            _make_review("2", source_branch="feat-2", ci_status="passed"),
            _make_review("3", source_branch="feat-3", ci_status="passed"),
        ]
        orch._reviews_cache = {project.id: reviews}

        orch._yolo_review_actions_sync()

        # Only one merge should have been attempted
        assert provider.merge_review.call_count == 1
        provider.merge_review.assert_called_once_with("org/repo", "1")

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_conflict_resolution_dispatches_notify_for_each(
        self, mock_slug, mock_detect, tmp_path
    ):
        """When multiple PRs have conflicts, each gets a conflict notification (no serialization).
        Conflicts use continue (all processed) not break, and _yolo_notify_conflict is called for all."""
        project = _make_project()
        project.yolo = True

        provider = MagicMock()
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._yolo_notify_conflict = MagicMock()

        # Mock the tracker to return an issue for fetch_issue_detail
        mock_tracker = MagicMock()
        mock_issue = MagicMock()
        mock_issue.state = "closed"
        mock_issue.labels = []
        mock_issue.identifier = "test-001"
        mock_issue.id = "test-001"
        mock_tracker.fetch_issue_detail.return_value = mock_issue
        orch._project_trackers[project.id] = mock_tracker

        reviews = [
            _make_review("1", source_branch="feat-1", has_conflicts=True),
            _make_review("2", source_branch="feat-2", has_conflicts=True),
        ]
        orch._reviews_cache = {project.id: reviews}

        orch._yolo_review_actions_sync()

        # rebase_review should NOT be called (conflicts use notify, not rebase)
        provider.rebase_review.assert_not_called()
        # Both conflict reviews should trigger _yolo_notify_conflict (continue, not break)
        assert orch._yolo_notify_conflict.call_count == 2
        calls = orch._yolo_notify_conflict.call_args_list
        assert calls[0][0][2] == "org/repo"  # slug
        assert calls[0][0][3] == "1"          # review_id
        assert calls[1][0][3] == "2"          # review_id

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_draft_prs_are_skipped_not_counted_as_action(
        self, mock_slug, mock_detect, tmp_path
    ):
        """Draft PRs are skipped; the next non-draft is acted upon."""
        project = _make_project()
        project.yolo = True

        provider = MagicMock()
        provider.merge_review.return_value = (True, "merged")
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = self._make_orchestrator(tmp_path, projects=[project])

        reviews = [
            _make_review("1", source_branch="feat-1", ci_status="passed", draft=True),
            _make_review("2", source_branch="feat-2", ci_status="passed"),
            _make_review("3", source_branch="feat-3", ci_status="passed"),
        ]
        orch._reviews_cache = {project.id: reviews}

        orch._yolo_review_actions_sync()

        # Draft PR is skipped; only PR #2 should be merged
        assert provider.merge_review.call_count == 1
        provider.merge_review.assert_called_once_with("org/repo", "2")

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_each_project_gets_one_action_independently(
        self, mock_slug, mock_detect, tmp_path
    ):
        """Each project is serialized independently — two projects each get one action."""
        proj1 = _make_project("proj-1", "https://github.com/org/repo1")
        proj1.yolo = True
        proj2 = _make_project("proj-2", "https://github.com/org/repo2")
        proj2.yolo = True

        provider = MagicMock()
        provider.merge_review.return_value = (True, "merged")
        mock_detect.return_value = provider
        mock_slug.side_effect = ["org/repo1", "org/repo2"]

        orch = self._make_orchestrator(tmp_path, projects=[proj1, proj2])

        orch._reviews_cache = {
            "proj-1": [
                _make_review("10", source_branch="p1-feat-a", ci_status="passed"),
                _make_review("11", source_branch="p1-feat-b", ci_status="passed"),
            ],
            "proj-2": [
                _make_review("20", source_branch="p2-feat-a", ci_status="passed"),
                _make_review("21", source_branch="p2-feat-b", ci_status="passed"),
            ],
        }

        orch._yolo_review_actions_sync()

        # One merge per project = 2 total, not 4
        assert provider.merge_review.call_count == 2
        calls = provider.merge_review.call_args_list
        # Each project's first PR is merged
        assert call("org/repo1", "10") in calls
        assert call("org/repo2", "20") in calls

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_non_yolo_project_is_skipped(self, mock_slug, mock_detect, tmp_path):
        """Projects without yolo=True are not acted upon."""
        project = _make_project()
        project.yolo = False

        provider = MagicMock()
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {
            project.id: [
                _make_review("1", source_branch="feat-1", ci_status="passed"),
            ]
        }

        orch._yolo_review_actions_sync()

        provider.merge_review.assert_not_called()

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_pending_ci_pr_receives_no_action(self, mock_slug, mock_detect, tmp_path):
        """PRs with pending CI are not merged, rebased, or retried."""
        project = _make_project()
        project.yolo = True

        provider = MagicMock()
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {
            project.id: [
                _make_review("1", source_branch="feat-1", ci_status="pending"),
            ]
        }
        orch._yolo_retry_ci = MagicMock()

        orch._yolo_review_actions_sync()

        provider.merge_review.assert_not_called()
        provider.rebase_review.assert_not_called()
        orch._yolo_retry_ci.assert_not_called()

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_pr_needing_rebase_not_merged(self, mock_slug, mock_detect, tmp_path):
        """A PR that needs a rebase is not merged even if CI passed."""
        project = _make_project()
        project.yolo = True

        provider = MagicMock()
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {
            project.id: [
                _make_review(
                    "1",
                    source_branch="feat-1",
                    ci_status="passed",
                    needs_rebase=True,
                ),
            ]
        }

        orch._yolo_review_actions_sync()

        provider.merge_review.assert_not_called()


class TestYoloRetryCi:
    """Tests for _yolo_retry_ci epic-with-children escalation (oompah-zlz_2-p4y).

    When a PR's source_branch matches an epic that already has children,
    relabeling the epic as ci-fix would silently strand the work — the
    dispatcher refuses to dispatch epics-with-children. The fix is to file
    a sibling task bead under the epic instead, so an agent actually runs.

    For non-epic beads (or childless epics) the existing behavior is kept.
    """

    def _make_orchestrator(self, tmp_path, projects=None):
        project_store = MagicMock()
        project_store.list_all.return_value = projects or []
        project_store.get.side_effect = lambda pid: next(
            (p for p in (projects or []) if p.id == pid), None
        )
        orch = Orchestrator(
            config=_make_config(),
            workflow_path="WORKFLOW.md",
            project_store=project_store,
            state_path=str(tmp_path / "state.json"),
        )
        return orch

    def _attach_tracker(self, orch, project, issue, children=None):
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = issue
        # Mock the orchestrator's child fetch helper directly so the test
        # doesn't need to reach into tracker.fetch_children.
        orch._fetch_epic_children = MagicMock(return_value=list(children or []))
        # Returned issue from create_issue (used only for logging)
        created = MagicMock()
        created.identifier = "proj-newchild"
        tracker.create_issue.return_value = created
        orch._project_trackers[project.id] = tracker
        return tracker

    def test_epic_with_children_creates_sibling_bead(self, tmp_path):
        """PR matched against a parent epic → new sibling bead is created
        instead of relabeling the epic."""
        project = _make_project()
        project.yolo = True
        orch = self._make_orchestrator(tmp_path, projects=[project])

        epic = Issue(
            id="trickle-rl5",
            identifier="trickle-rl5",
            title="CI-Speed plan",
            description="Make CI faster",
            state="open",
            issue_type="epic",
            labels=[],
            branch_name="trickle-rl5",
        )
        # Seven children, mirroring the live trickle PR #23 case.
        children = [_make_issue(f"trickle-c{i}", state="open") for i in range(7)]
        tracker = self._attach_tracker(orch, project, epic, children=children)

        review = _make_review("23", source_branch="trickle-rl5", ci_status="failed")

        orch._yolo_retry_ci(project, review)

        # Existing relabel path must NOT fire on the epic
        tracker.update_issue.assert_not_called()
        tracker.add_comment.assert_not_called()

        # A sibling task must be created, parented to the epic, as a P0
        # Needs CI Fix work item.
        tracker.create_issue.assert_called_once()
        kwargs = tracker.create_issue.call_args.kwargs
        assert kwargs["issue_type"] == "task"
        assert kwargs["priority"] == 0
        assert kwargs["parent"] == "trickle-rl5"
        assert kwargs["initial_status"] == "Needs CI Fix"
        assert "PR #23" in kwargs["title"]
        assert "trickle-rl5" in kwargs["title"]
        # Description should mention the parent epic and dispatch hint
        desc = kwargs["description"]
        assert "trickle-rl5" in desc
        assert "epic" in desc
        assert "Fix the failing tests" in desc

    def test_non_epic_bead_keeps_relabel_behavior(self, tmp_path):
        """PR matched against a non-epic bead → existing behavior preserved
        (relabel + reopen, no sibling created)."""
        project = _make_project()
        project.yolo = True
        orch = self._make_orchestrator(tmp_path, projects=[project])

        bead = Issue(
            id="proj-task1",
            identifier="proj-task1",
            title="Task",
            description="A task with a body so the dispatcher accepts it.",
            state="closed",  # closed so we exercise the reopen path
            issue_type="task",
            labels=[],
            branch_name="feat-task1",
        )
        tracker = self._attach_tracker(orch, project, bead, children=[])

        review = _make_review("42", source_branch="feat-task1", ci_status="failed")

        orch._yolo_retry_ci(project, review)

        # Existing relabel path fires: status=Needs CI Fix, priority=0, label=ci-fix
        tracker.update_issue.assert_called_once()
        update_kwargs = tracker.update_issue.call_args.kwargs
        assert update_kwargs.get("status") == "Needs CI Fix"
        assert update_kwargs.get("priority") == "0"
        assert update_kwargs.get("add-label") == "ci-fix"
        # Comment is added to the existing bead
        tracker.add_comment.assert_called_once()
        # NO sibling bead is created
        tracker.create_issue.assert_not_called()

    def test_childless_epic_keeps_relabel_behavior(self, tmp_path):
        """PR matched against a childless epic → existing behavior preserved
        (relabel — epic-planner can pick it up). No sibling bead."""
        project = _make_project()
        project.yolo = True
        orch = self._make_orchestrator(tmp_path, projects=[project])

        epic = Issue(
            id="proj-empty-epic",
            identifier="proj-empty-epic",
            title="Empty epic",
            description="An epic that has not been planned yet.",
            state="open",
            issue_type="epic",
            labels=[],
            branch_name="feat-empty-epic",
        )
        tracker = self._attach_tracker(orch, project, epic, children=[])

        review = _make_review("99", source_branch="feat-empty-epic",
                              ci_status="failed")

        orch._yolo_retry_ci(project, review)

        # Existing relabel path fires (epic-planner will pick it up)
        tracker.update_issue.assert_called_once()
        tracker.add_comment.assert_called_once()
        # NO sibling bead is created
        tracker.create_issue.assert_not_called()

    def test_already_labeled_ci_fix_is_noop_for_epic_with_children(self, tmp_path):
        """If the epic-with-children is already labeled ci-fix from a prior
        cycle that pre-dates this fix, we still skip relabel (idempotent
        guard runs first). New sibling beads will only be filed when the
        bead is freshly identified — the per-MR guard below test_only_one
        ensures we don't spam, and any orphaned ci-fix-labeled epics are
        a one-time manual cleanup."""
        project = _make_project()
        project.yolo = True
        orch = self._make_orchestrator(tmp_path, projects=[project])

        epic = Issue(
            id="trickle-rl5",
            identifier="trickle-rl5",
            title="CI-Speed plan",
            description="Make CI faster",
            state="open",
            issue_type="epic",
            labels=["ci-fix"],  # already labeled — pre-existing bug residue
            branch_name="trickle-rl5",
        )
        children = [_make_issue("trickle-c1", state="open")]
        tracker = self._attach_tracker(orch, project, epic, children=children)

        review = _make_review("23", source_branch="trickle-rl5", ci_status="failed")

        orch._yolo_retry_ci(project, review)

        # Idempotency guard fires first — no relabel, no sibling
        tracker.update_issue.assert_not_called()
        tracker.add_comment.assert_not_called()
        tracker.create_issue.assert_not_called()


class TestYoloMergeConflictLabelClearing:
    """Tests for stale merge-conflict label clearing (oompah-zlz_2-683l).

    The merge-conflict label is added by ``_yolo_notify_conflict`` when a PR
    has ``has_conflicts=True``. It must be removed:
    - When YOLO successfully merges / enqueues a PR (GitHub confirmed no conflicts).
    - When a PR no longer has conflicts but also no longer triggers a YOLO
      action (e.g. CI is still running; the owner rebased the branch outside
      the YOLO agent path).

    These tests verify both paths.
    """

    def _make_orchestrator(self, tmp_path, projects=None):
        project_store = MagicMock()
        project_store.list_all.return_value = projects or []
        project_store.get.side_effect = lambda pid: next(
            (p for p in (projects or []) if p.id == pid), None
        )
        orch = Orchestrator(
            config=_make_config(),
            workflow_path="WORKFLOW.md",
            project_store=project_store,
            state_path=str(tmp_path / "state.json"),
        )
        return orch

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_successful_merge_clears_merge_conflict_label(
        self, mock_slug, mock_detect, tmp_path,
    ):
        """When YOLO merges a PR whose bead carries merge-conflict, the label
        is removed so the bead doesn't stay stale."""
        project = _make_project()
        project.yolo = True
        provider = MagicMock()
        provider.merge_review.return_value = (True, "merged")
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = self._make_orchestrator(tmp_path, projects=[project])

        mock_tracker = MagicMock()
        # Bead with merge-conflict label
        mock_bead = MagicMock()
        mock_bead.labels = ["bug", "merge-conflict"]
        mock_bead.id = "bead-001"
        mock_bead.identifier = "oompah-zlz_2-001"
        mock_tracker.fetch_issue_detail.return_value = mock_bead
        orch._project_trackers[project.id] = mock_tracker

        reviews = [
            _make_review("1", source_branch="bead-001", ci_status="passed"),
        ]
        orch._reviews_cache = {project.id: reviews}

        orch._yolo_review_actions_sync()

        # merge_review called (PR merged)
        provider.merge_review.assert_called_once_with("org/repo", "1")
        # merge-conflict label removed from the matching bead
        tracker_call_kwargs = mock_tracker.update_issue.call_args
        assert tracker_call_kwargs is not None
        kwargs_dict = tracker_call_kwargs[1]
        assert kwargs_dict.get("remove-label") == "merge-conflict"

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_successful_enqueue_clears_merge_conflict_label(
        self, mock_slug, mock_detect, tmp_path,
    ):
        """When YOLO enqueues a PR (merge queue mode) whose bead carries
        merge-conflict, the label is removed."""
        project = _make_project()
        project.yolo = True
        project.merge_queue_enabled = True
        provider = MagicMock()
        provider.enable_auto_merge.return_value = (True, "")
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = self._make_orchestrator(tmp_path, projects=[project])

        mock_tracker = MagicMock()
        mock_bead = MagicMock()
        mock_bead.labels = ["merge-conflict", "tech-debt"]
        mock_bead.id = "bead-002"
        mock_bead.identifier = "oompah-zlz_2-002"
        mock_tracker.fetch_issue_detail.return_value = mock_bead
        orch._project_trackers[project.id] = mock_tracker

        reviews = [
            _make_review("2", source_branch="bead-002", ci_status="passed"),
        ]
        orch._reviews_cache = {project.id: reviews}

        orch._yolo_review_actions_sync()

        provider.enable_auto_merge.assert_called_once_with("org/repo", "2")
        tracker_call_kwargs = mock_tracker.update_issue.call_args
        assert tracker_call_kwargs is not None
        assert tracker_call_kwargs[1].get("remove-label") == "merge-conflict"

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_stale_label_cleared_when_conflicts_resolved_externally(
        self, mock_slug, mock_detect, tmp_path,
    ):
        """When a PR no longer has merge conflicts (external rebase) and CI is
        still running, the stale merge-conflict label is still cleared — the
        tick's end-of-iteration check sees has_conflicts=False and removes the
        stale label."""
        project = _make_project()
        project.yolo = True
        provider = MagicMock()
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = self._make_orchestrator(tmp_path, projects=[project])

        mock_tracker = MagicMock()
        mock_bead = MagicMock()
        mock_bead.labels = ["merge-conflict"]  # stale label
        mock_bead.id = "bead-003"
        mock_bead.identifier = "oompah-zlz_2-003"
        mock_tracker.fetch_issue_detail.return_value = mock_bead
        orch._project_trackers[project.id] = mock_tracker

        # CI is still running; has_conflicts=False (externally rebased)
        reviews = [
            _make_review("3", source_branch="bead-003",
                         ci_status="running", has_conflicts=False),
        ]
        orch._reviews_cache = {project.id: reviews}

        orch._yolo_review_actions_sync()

        # No merge/enqueue attempted (CI still running)
        provider.merge_review.assert_not_called()
        provider.enable_auto_merge.assert_not_called()
        # But the stale merge-conflict label on the matching bead was cleared
        tracker_call_kwargs = mock_tracker.update_issue.call_args
        assert tracker_call_kwargs is not None
        assert tracker_call_kwargs[1].get("remove-label") == "merge-conflict"

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_noop_when_bead_has_no_merge_conflict_label(
        self, mock_slug, mock_detect, tmp_path,
    ):
        """When a merged PR matches a bead that does NOT have merge-conflict
        label, no tracker update is issued (reduces API chatter)."""
        project = _make_project()
        project.yolo = True
        provider = MagicMock()
        provider.merge_review.return_value = (True, "merged")
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = self._make_orchestrator(tmp_path, projects=[project])

        mock_tracker = MagicMock()
        mock_bead = MagicMock()
        mock_bead.labels = ["bug"]  # no merge-conflict
        mock_bead.id = "bead-004"
        mock_bead.identifier = "oompah-zlz_2-004"
        mock_tracker.fetch_issue_detail.return_value = mock_bead
        orch._project_trackers[project.id] = mock_tracker

        reviews = [
            _make_review("4", source_branch="bead-004", ci_status="passed"),
        ]
        orch._reviews_cache = {project.id: reviews}

        orch._yolo_review_actions_sync()

        provider.merge_review.assert_called()
        mock_tracker.update_issue.assert_not_called()  # no label to remove

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_noop_when_no_matching_bead(
        self, mock_slug, mock_detect, tmp_path,
    ):
        """When a PR is merged and has no matching bead (orphan branch), the
        clear-label step is a silent no-op and does not crash."""
        project = _make_project()
        project.yolo = True
        provider = MagicMock()
        provider.merge_review.return_value = (True, "merged")
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = self._make_orchestrator(tmp_path, projects=[project])

        mock_tracker = MagicMock()
        mock_tracker.fetch_issue_detail.return_value = None  # no matching bead
        orch._project_trackers[project.id] = mock_tracker

        reviews = [
            _make_review("5", source_branch="orphan-branch", ci_status="passed"),
        ]
        orch._reviews_cache = {project.id: reviews}

        # Should not raise
        orch._yolo_review_actions_sync()
        provider.merge_review.assert_called()
        mock_tracker.update_issue.assert_not_called()


class TestProjectHasOpenReview:
    """Tests for _project_has_open_review dispatch gating."""

    def _make_orchestrator(self, tmp_path, projects=None):
        project_store = MagicMock()
        project_store.list_all.return_value = projects or []
        project_store.get.side_effect = lambda pid: next(
            (p for p in (projects or []) if p.id == pid), None
        )
        orch = Orchestrator(
            config=_make_config(),
            workflow_path="WORKFLOW.md",
            project_store=project_store,
            state_path=str(tmp_path / "state.json"),
        )
        return orch

    def test_no_project_id_always_returns_false(self, tmp_path):
        """Legacy issues without a project_id are never blocked by this check."""
        orch = self._make_orchestrator(tmp_path)
        orch._reviews_cache = {"proj-1": [_make_review("1")]}
        assert orch._project_has_open_review(None) is False

    def test_project_with_open_review_returns_true(self, tmp_path):
        orch = self._make_orchestrator(tmp_path)
        orch._reviews_cache = {"proj-1": [_make_review("1")]}
        assert orch._project_has_open_review("proj-1") is True

    def test_project_with_only_draft_reviews_returns_false(self, tmp_path):
        """Draft PRs do not count as blocking open reviews."""
        orch = self._make_orchestrator(tmp_path)
        orch._reviews_cache = {
            "proj-1": [_make_review("1", draft=True)]
        }
        assert orch._project_has_open_review("proj-1") is False

    def test_project_with_no_reviews_returns_false(self, tmp_path):
        orch = self._make_orchestrator(tmp_path)
        orch._reviews_cache = {"proj-1": []}
        assert orch._project_has_open_review("proj-1") is False

    def test_project_not_in_cache_returns_false(self, tmp_path):
        orch = self._make_orchestrator(tmp_path)
        orch._reviews_cache = {}
        assert orch._project_has_open_review("proj-1") is False

    def test_no_reviews_cache_returns_false(self, tmp_path):
        """Gracefully handles missing _reviews_cache attribute."""
        orch = self._make_orchestrator(tmp_path)
        # Don't set _reviews_cache
        assert orch._project_has_open_review("proj-1") is False

    def test_mixed_draft_and_non_draft_returns_true(self, tmp_path):
        """Even one non-draft review among drafts counts as blocking."""
        orch = self._make_orchestrator(tmp_path)
        orch._reviews_cache = {
            "proj-1": [
                _make_review("1", draft=True),
                _make_review("2", draft=False),
            ]
        }
        assert orch._project_has_open_review("proj-1") is True


class TestDispatchSerializationByProject:
    """Tests that _should_dispatch gates on open reviews to serialize per project."""

    def _make_orchestrator(self, tmp_path, projects=None):
        project_store = MagicMock()
        project_store.list_all.return_value = projects or []
        project_store.get.side_effect = lambda pid: next(
            (p for p in (projects or []) if p.id == pid), None
        )
        orch = Orchestrator(
            config=_make_config(),
            workflow_path="WORKFLOW.md",
            project_store=project_store,
            state_path=str(tmp_path / "state.json"),
        )
        return orch

    def _make_project_issue(
        self,
        identifier: str,
        state: str = "open",
        project_id: str = "proj-1",
        priority: int | None = 2,
    ) -> Issue:
        issue = _make_issue(identifier, state=state)
        issue.project_id = project_id
        issue.priority = priority
        return issue

    def test_dispatch_blocked_when_project_has_open_review(self, tmp_path):
        """An issue in a project with an open review should not be dispatched."""
        orch = self._make_orchestrator(tmp_path)
        issue = self._make_project_issue("feat-2", state="open", priority=2)
        # Project already has an open non-draft review
        orch._reviews_cache = {"proj-1": [_make_review("10")]}

        assert orch._should_dispatch(issue) is False

    def test_dispatch_allowed_when_project_has_no_open_review(self, tmp_path):
        """An issue in a project with no open reviews can be dispatched."""
        orch = self._make_orchestrator(tmp_path)
        issue = self._make_project_issue("feat-2", state="open", priority=2)
        orch._reviews_cache = {"proj-1": []}

        assert orch._should_dispatch(issue) is True

    def test_dispatch_allowed_when_only_draft_reviews_present(self, tmp_path):
        """Draft reviews do not block dispatch."""
        orch = self._make_orchestrator(tmp_path)
        issue = self._make_project_issue("feat-2", state="open", priority=2)
        orch._reviews_cache = {"proj-1": [_make_review("10", draft=True)]}

        assert orch._should_dispatch(issue) is True

    def test_p0_issue_bypasses_open_review_gate(self, tmp_path):
        """P0 issues bypass the open-review gate to ensure critical fixes are never blocked."""
        orch = self._make_orchestrator(tmp_path)
        issue = self._make_project_issue("feat-crit", state="open", priority=0)
        # Project has an open review, but P0 should bypass the check
        orch._reviews_cache = {"proj-1": [_make_review("10")]}

        assert orch._should_dispatch(issue) is True

    def test_legacy_issue_without_project_not_gated(self, tmp_path):
        """Issues without project_id are not subject to the per-project gate."""
        orch = self._make_orchestrator(tmp_path)
        issue = _make_issue("legacy-1", state="open")
        issue.priority = 2
        issue.project_id = None
        orch._reviews_cache = {"proj-1": [_make_review("10")]}

        # Legacy issue should not be blocked by project reviews
        assert orch._should_dispatch(issue) is True


class TestProjectHasOpenReview:
    """Tests for _project_has_open_review."""

    def _make_orchestrator(self, tmp_path):
        orch = Orchestrator(
            config=_make_config(),
            workflow_path="WORKFLOW.md",
            state_path=str(tmp_path / "state.json"),
        )
        return orch

    def test_no_project_id_returns_false(self, tmp_path):
        """Issues without a project_id never block on open reviews."""
        orch = self._make_orchestrator(tmp_path)
        orch._reviews_cache = {"proj-1": [_make_review("1", "feat-1", ci_status="passed")]}
        assert orch._project_has_open_review(None) is False

    def test_no_reviews_cache_returns_false(self, tmp_path):
        """If the reviews cache is absent (before first tick), don't block."""
        orch = self._make_orchestrator(tmp_path)
        # _reviews_cache not set — should fall back gracefully
        assert orch._project_has_open_review("proj-1") is False

    def test_empty_project_reviews_returns_false(self, tmp_path):
        """A project with no open reviews allows dispatch."""
        orch = self._make_orchestrator(tmp_path)
        orch._reviews_cache = {"proj-1": []}
        assert orch._project_has_open_review("proj-1") is False

    def test_unknown_project_returns_false(self, tmp_path):
        """A project not in the reviews cache allows dispatch."""
        orch = self._make_orchestrator(tmp_path)
        orch._reviews_cache = {"proj-2": [_make_review("1", "feat-1", ci_status="passed")]}
        assert orch._project_has_open_review("proj-1") is False

    def test_one_open_review_returns_true(self, tmp_path):
        """A project with one open non-draft review blocks dispatch."""
        orch = self._make_orchestrator(tmp_path)
        orch._reviews_cache = {
            "proj-1": [_make_review("1", "feat-1", ci_status="passed")]
        }
        assert orch._project_has_open_review("proj-1") is True

    def test_only_draft_reviews_returns_false(self, tmp_path):
        """Draft reviews don't count as blocking — they're not ready to merge."""
        orch = self._make_orchestrator(tmp_path)
        orch._reviews_cache = {
            "proj-1": [_make_review("1", "feat-1", ci_status="passed", draft=True)]
        }
        assert orch._project_has_open_review("proj-1") is False

    def test_mix_of_draft_and_non_draft_returns_true(self, tmp_path):
        """If any non-draft review is open, dispatch is blocked."""
        orch = self._make_orchestrator(tmp_path)
        orch._reviews_cache = {
            "proj-1": [
                _make_review("1", "feat-1", draft=True),
                _make_review("2", "feat-2", ci_status="passed"),
            ]
        }
        assert orch._project_has_open_review("proj-1") is True


class TestDispatchSerializationByProject:
    """Tests that _should_dispatch gates new work on projects with open reviews."""

    def _make_orchestrator(self, tmp_path, projects=None):
        project_store = MagicMock()
        project_store.list_all.return_value = projects or []
        project_store.get.side_effect = lambda pid: next(
            (p for p in (projects or []) if p.id == pid), None
        )
        orch = Orchestrator(
            config=_make_config(),
            workflow_path="WORKFLOW.md",
            project_store=project_store,
            state_path=str(tmp_path / "state.json"),
        )
        return orch

    def _make_project_issue(self, identifier: str, project_id: str = "proj-1",
                             state: str = "open", priority=None) -> Issue:
        return Issue(
            id=identifier,
            identifier=identifier,
            title=f"Issue {identifier}",
            description="body — passes the empty-description gate.",
            state=state,
            project_id=project_id,
            priority=priority,
        )

    def test_open_review_blocks_dispatch(self, tmp_path):
        """When a project has an open PR, new issues for that project are not dispatched."""
        orch = self._make_orchestrator(tmp_path)
        issue = self._make_project_issue("feat-2", project_id="proj-1", state="open")
        orch._reviews_cache = {
            "proj-1": [_make_review("1", "feat-1", ci_status="passed")]
        }
        assert orch._should_dispatch(issue) is False

    def test_no_reviews_allows_dispatch(self, tmp_path):
        """When a project has no open PRs, dispatch proceeds normally."""
        orch = self._make_orchestrator(tmp_path)
        issue = self._make_project_issue("feat-2", project_id="proj-1", state="open")
        orch._reviews_cache = {"proj-1": []}
        assert orch._should_dispatch(issue) is True

    def test_different_project_not_affected(self, tmp_path):
        """An open review in project A does not block dispatch for project B."""
        orch = self._make_orchestrator(tmp_path)
        issue = self._make_project_issue("feat-b", project_id="proj-2", state="open")
        orch._reviews_cache = {
            "proj-1": [_make_review("1", "feat-a", ci_status="passed")],
            "proj-2": [],
        }
        assert orch._should_dispatch(issue) is True

    def test_p0_issue_bypasses_review_gate(self, tmp_path):
        """P0 issues are never blocked by the open-review gate."""
        orch = self._make_orchestrator(tmp_path)
        issue = self._make_project_issue("feat-2", project_id="proj-1",
                                          state="open", priority=0)
        orch._reviews_cache = {
            "proj-1": [_make_review("1", "feat-1", ci_status="passed")]
        }
        assert orch._should_dispatch(issue) is True

    def test_draft_only_reviews_allow_dispatch(self, tmp_path):
        """Draft PRs don't block dispatch — the pipeline is not truly in-flight."""
        orch = self._make_orchestrator(tmp_path)
        issue = self._make_project_issue("feat-2", project_id="proj-1", state="open")
        orch._reviews_cache = {
            "proj-1": [_make_review("1", "feat-1", draft=True)]
        }
        assert orch._should_dispatch(issue) is True

    def test_legacy_issue_no_project_id_not_blocked(self, tmp_path):
        """Issues without a project_id are not affected by the review gate."""
        orch = self._make_orchestrator(tmp_path)
        issue = Issue(
            id="legacy-1",
            identifier="legacy-1",
            title="Legacy issue",
            description="legacy body",
            state="open",
            project_id=None,
        )
        orch._reviews_cache = {
            "proj-1": [_make_review("1", "feat-1", ci_status="passed")]
        }
        assert orch._should_dispatch(issue) is True


class TestBudgetWindowPersistence:
    """Tests for the rolling budget window: spend persists across restart
    inside a window, resets at rollover, and resets on window-kind change.
    Boundaries are calendar-aligned (top-of-hour, local midnight, Sunday
    00:00) — see also TestBudgetWindowCalendarBoundaries."""

    def _make_orchestrator(self, tmp_path, window: str = "day", tz: str = "UTC"):
        cfg = ServiceConfig()
        cfg.budget_limit = 10.0
        cfg.budget_window = window
        cfg.budget_timezone = tz
        project_store = MagicMock()
        project_store.list_all.return_value = []
        return Orchestrator(
            config=cfg,
            workflow_path="WORKFLOW.md",
            project_store=project_store,
            state_path=str(tmp_path / "state.json"),
        )

    def test_initial_budget_state_is_zero(self, tmp_path):
        orch = self._make_orchestrator(tmp_path)
        assert orch.state.agent_totals.estimated_cost == 0.0
        assert orch.state.budget_window_start == 0.0

    def test_first_check_initializes_window_start(self, tmp_path):
        orch = self._make_orchestrator(tmp_path)
        assert orch._check_budget() is True
        assert orch.state.budget_window_start > 0
        # Snapped to the previous calendar boundary, NOT to "now".
        assert orch.state.budget_window_start == orch._previous_budget_boundary(
            __import__("time").time()
        )

    def test_persisted_spend_restored_within_window(self, tmp_path, monkeypatch):
        # Seed state.json as if a prior run had already spent $4 with
        # window_start at the top of the current hour, in an "hour" window.
        # Use hour-window so the test is deterministic regardless of
        # time-of-day (an hour boundary is always less than 1h ago).
        import json, time
        fake_now = 1_700_000_000.0  # arbitrary fixed instant
        monkeypatch.setattr(time, "time", lambda: fake_now)
        # Top of the hour at fake_now.
        snapped_start = fake_now - (fake_now % 3600)
        state_path = tmp_path / "state.json"
        with open(state_path, "w") as f:
            json.dump({
                "estimated_cost": 4.0,
                "budget_window_start": snapped_start,
                "budget_window_kind": "hour",
            }, f)
        orch = self._make_orchestrator(tmp_path, window="hour")
        # Spend should be carried forward.
        assert orch.state.agent_totals.estimated_cost == 4.0
        assert orch.state.budget_window_kind == "hour"

    def test_persisted_spend_dropped_when_window_kind_changed(self, tmp_path):
        # Operator switched window from week → hour. Don't carry the
        # old week's spend into the new hour window.
        import json, time
        state_path = tmp_path / "state.json"
        with open(state_path, "w") as f:
            json.dump({
                "estimated_cost": 8.0,
                "budget_window_start": time.time() - 60,
                "budget_window_kind": "week",
            }, f)
        orch = self._make_orchestrator(tmp_path, window="hour")
        assert orch.state.agent_totals.estimated_cost == 0.0

    def test_persisted_spend_dropped_when_window_already_lapsed(self, tmp_path):
        # Persisted window started 2 days ago in a "day" window — should
        # NOT carry forward.
        import json, time
        state_path = tmp_path / "state.json"
        with open(state_path, "w") as f:
            json.dump({
                "estimated_cost": 8.0,
                "budget_window_start": time.time() - 2 * 86400,
                "budget_window_kind": "day",
            }, f)
        orch = self._make_orchestrator(tmp_path, window="day")
        assert orch.state.agent_totals.estimated_cost == 0.0

    def test_window_rolls_over_resets_spend(self, tmp_path):
        import time
        orch = self._make_orchestrator(tmp_path, window="hour")
        # Pretend we're 65 minutes into the hour window with $5 spent.
        # That means we crossed at least one top-of-hour boundary, so a
        # roll must fire.
        orch.state.agent_totals.estimated_cost = 5.0
        orch.state.budget_window_start = time.time() - 65 * 60
        orch.state.budget_window_kind = "hour"
        assert orch._check_budget() is True
        # Rolled — spend reset, new window snapped to most-recent boundary.
        assert orch.state.agent_totals.estimated_cost == 0.0
        # Snapped boundary is at most 1 hour in the past.
        assert (time.time() - orch.state.budget_window_start) <= 3600
        # And it equals the previous-boundary helper.
        assert orch.state.budget_window_start == orch._previous_budget_boundary(
            time.time()
        )

    def test_within_window_does_not_roll(self, tmp_path, monkeypatch):
        # Mock time so the test is deterministic regardless of where we
        # are inside the wall-clock hour.
        import time
        # Pick a fake now that is 30 min after a top-of-hour boundary so
        # there's still 30 min left in the window.
        fake_now = 1_700_000_000.0
        boundary = fake_now - (fake_now % 3600)
        fake_now = boundary + 30 * 60  # 30 min into the hour
        monkeypatch.setattr(time, "time", lambda: fake_now)
        orch = self._make_orchestrator(tmp_path, window="hour")
        start = boundary  # snapped boundary, 30 min ago
        orch.state.agent_totals.estimated_cost = 5.0
        orch.state.budget_window_start = start
        orch.state.budget_window_kind = "hour"
        assert orch._check_budget() is True
        # No rollover — spend and start preserved.
        assert orch.state.agent_totals.estimated_cost == 5.0
        assert orch.state.budget_window_start == start

    def test_zero_budget_limit_disables_check(self, tmp_path):
        orch = self._make_orchestrator(tmp_path)
        orch.config.budget_limit = 0.0
        # Even with $1000 spent, no limit means always within budget.
        orch.state.agent_totals.estimated_cost = 1000.0
        assert orch._check_budget() is True

    def test_persist_writes_estimated_cost(self, tmp_path):
        import json
        orch = self._make_orchestrator(tmp_path)
        orch.state.agent_totals.estimated_cost = 2.5
        orch.state.budget_window_start = 1000.0
        orch._persist_budget_state()
        with open(tmp_path / "state.json") as f:
            data = json.load(f)
        assert data["estimated_cost"] == 2.5
        assert data["budget_window_start"] == 1000.0
        assert data["budget_window_kind"] == "day"

    def test_window_seconds_per_kind(self, tmp_path):
        # Nominal window seconds — kept for display / dashboard purposes.
        # Actual roll boundaries are calendar-aligned, not seconds-based.
        for kind, expected in (("hour", 3600), ("day", 86400), ("week", 604800)):
            orch = self._make_orchestrator(tmp_path, window=kind)
            assert orch._budget_window_seconds() == expected


class TestBudgetWindowCalendarBoundaries:
    """Calendar-aligned budget window rolls: top-of-hour, local midnight,
    Sunday 00:00. Replaces the seconds-based rolling from the original
    windowed-budget work — operators think in calendar terms, not in
    "60 minutes after I happened to boot"."""

    def _make_orchestrator(self, tmp_path, window: str, tz: str = "UTC"):
        cfg = ServiceConfig()
        cfg.budget_limit = 10.0
        cfg.budget_window = window
        cfg.budget_timezone = tz
        project_store = MagicMock()
        project_store.list_all.return_value = []
        return Orchestrator(
            config=cfg,
            workflow_path="WORKFLOW.md",
            project_store=project_store,
            state_path=str(tmp_path / "state.json"),
        )

    def _ts(self, tz: str, year, month, day, hour=0, minute=0, second=0):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        return datetime(year, month, day, hour, minute, second,
                        tzinfo=ZoneInfo(tz)).timestamp()

    # ----- previous / next boundary correctness -----

    def test_hour_boundary_previous_is_top_of_hour(self, tmp_path):
        orch = self._make_orchestrator(tmp_path, window="hour", tz="UTC")
        ts = self._ts("UTC", 2026, 5, 5, 14, 17, 23)
        prev = orch._previous_budget_boundary(ts)
        expected = self._ts("UTC", 2026, 5, 5, 14, 0, 0)
        assert prev == expected

    def test_hour_boundary_next_is_next_top_of_hour(self, tmp_path):
        orch = self._make_orchestrator(tmp_path, window="hour", tz="UTC")
        ts = self._ts("UTC", 2026, 5, 5, 14, 17, 23)
        nxt = orch._next_budget_boundary(ts)
        expected = self._ts("UTC", 2026, 5, 5, 15, 0, 0)
        assert nxt == expected

    def test_day_boundary_previous_is_midnight(self, tmp_path):
        orch = self._make_orchestrator(tmp_path, window="day",
                                       tz="America/Los_Angeles")
        ts = self._ts("America/Los_Angeles", 2026, 5, 5, 14, 17, 23)
        prev = orch._previous_budget_boundary(ts)
        expected = self._ts("America/Los_Angeles", 2026, 5, 5, 0, 0, 0)
        assert prev == expected

    def test_day_boundary_next_is_next_midnight(self, tmp_path):
        orch = self._make_orchestrator(tmp_path, window="day",
                                       tz="America/Los_Angeles")
        ts = self._ts("America/Los_Angeles", 2026, 5, 5, 14, 17, 23)
        nxt = orch._next_budget_boundary(ts)
        expected = self._ts("America/Los_Angeles", 2026, 5, 6, 0, 0, 0)
        assert nxt == expected

    def test_week_boundary_previous_is_sunday_midnight(self, tmp_path):
        orch = self._make_orchestrator(tmp_path, window="week", tz="UTC")
        # 2026-05-05 is a Tuesday. Most recent Sunday is 2026-05-03.
        ts = self._ts("UTC", 2026, 5, 5, 14, 17, 23)
        prev = orch._previous_budget_boundary(ts)
        expected = self._ts("UTC", 2026, 5, 3, 0, 0, 0)
        assert prev == expected

    def test_week_boundary_when_today_is_sunday(self, tmp_path):
        orch = self._make_orchestrator(tmp_path, window="week", tz="UTC")
        # 2026-05-03 IS a Sunday — previous boundary is 2026-05-03 00:00,
        # not 2026-04-26.
        ts = self._ts("UTC", 2026, 5, 3, 14, 0, 0)
        prev = orch._previous_budget_boundary(ts)
        expected = self._ts("UTC", 2026, 5, 3, 0, 0, 0)
        assert prev == expected

    def test_week_boundary_when_today_is_saturday(self, tmp_path):
        orch = self._make_orchestrator(tmp_path, window="week", tz="UTC")
        # 2026-05-02 is a Saturday — previous boundary is 2026-04-26
        # (the previous Sunday).
        ts = self._ts("UTC", 2026, 5, 2, 23, 59, 0)
        prev = orch._previous_budget_boundary(ts)
        expected = self._ts("UTC", 2026, 4, 26, 0, 0, 0)
        assert prev == expected
        # Next boundary is the upcoming Sunday 2026-05-03 00:00.
        nxt = orch._next_budget_boundary(ts)
        assert nxt == self._ts("UTC", 2026, 5, 3, 0, 0, 0)

    # ----- roll behaviour at exact boundaries -----

    def test_hour_does_not_roll_just_before_boundary(self, tmp_path, monkeypatch):
        import time
        orch = self._make_orchestrator(tmp_path, window="hour", tz="UTC")
        start = self._ts("UTC", 2026, 5, 5, 14, 0, 0)
        orch.state.budget_window_start = start
        orch.state.budget_window_kind = "hour"
        orch.state.agent_totals.estimated_cost = 5.0
        # 14:59:59 — same hour, must not roll.
        monkeypatch.setattr(
            time, "time",
            lambda: self._ts("UTC", 2026, 5, 5, 14, 59, 59),
        )
        orch._roll_budget_window_if_due()
        assert orch.state.agent_totals.estimated_cost == 5.0
        assert orch.state.budget_window_start == start

    def test_hour_rolls_at_exact_boundary(self, tmp_path, monkeypatch):
        import time
        orch = self._make_orchestrator(tmp_path, window="hour", tz="UTC")
        start = self._ts("UTC", 2026, 5, 5, 14, 0, 0)
        orch.state.budget_window_start = start
        orch.state.budget_window_kind = "hour"
        orch.state.agent_totals.estimated_cost = 5.0
        # Half a second past 15:00:00 — boundary crossed.
        monkeypatch.setattr(
            time, "time",
            lambda: self._ts("UTC", 2026, 5, 5, 15, 0, 0) + 0.5,
        )
        orch._roll_budget_window_if_due()
        assert orch.state.agent_totals.estimated_cost == 0.0
        assert orch.state.budget_window_start == self._ts(
            "UTC", 2026, 5, 5, 15, 0, 0,
        )

    def test_day_rolls_at_local_midnight(self, tmp_path, monkeypatch):
        import time
        tz = "America/Los_Angeles"
        orch = self._make_orchestrator(tmp_path, window="day", tz=tz)
        start = self._ts(tz, 2026, 5, 5, 14, 17, 0)
        orch.state.budget_window_start = self._ts(tz, 2026, 5, 5, 0, 0, 0)
        orch.state.budget_window_kind = "day"
        orch.state.agent_totals.estimated_cost = 5.0
        # 1 second past local midnight — must roll.
        monkeypatch.setattr(
            time, "time",
            lambda: self._ts(tz, 2026, 5, 6, 0, 0, 1),
        )
        orch._roll_budget_window_if_due()
        assert orch.state.agent_totals.estimated_cost == 0.0
        assert orch.state.budget_window_start == self._ts(tz, 2026, 5, 6, 0, 0, 0)

    def test_week_rolls_at_sunday_midnight(self, tmp_path, monkeypatch):
        import time
        orch = self._make_orchestrator(tmp_path, window="week", tz="UTC")
        # Sunday 2026-04-26 00:00 is the previous boundary.
        orch.state.budget_window_start = self._ts("UTC", 2026, 4, 26, 0, 0, 0)
        orch.state.budget_window_kind = "week"
        orch.state.agent_totals.estimated_cost = 8.0
        # Saturday 2026-05-02 23:59 — still within the window.
        monkeypatch.setattr(
            time, "time",
            lambda: self._ts("UTC", 2026, 5, 2, 23, 59, 0),
        )
        orch._roll_budget_window_if_due()
        assert orch.state.agent_totals.estimated_cost == 8.0
        # Now Sunday 2026-05-03 00:00:01 — must roll.
        monkeypatch.setattr(
            time, "time",
            lambda: self._ts("UTC", 2026, 5, 3, 0, 0, 1),
        )
        orch._roll_budget_window_if_due()
        assert orch.state.agent_totals.estimated_cost == 0.0
        assert orch.state.budget_window_start == self._ts("UTC", 2026, 5, 3, 0, 0, 0)

    # ----- DST -----

    def test_day_boundary_handles_dst_spring_forward(self, tmp_path):
        # 2026-03-08 in America/Los_Angeles: DST spring-forward at 02:00.
        # Day boundary at 2026-03-08 00:00 PST and 2026-03-09 00:00 PDT
        # must both be wall-clock midnights, not naive UTC arithmetic.
        orch = self._make_orchestrator(tmp_path, window="day",
                                       tz="America/Los_Angeles")
        ts = self._ts("America/Los_Angeles", 2026, 3, 8, 12, 0, 0)
        prev = orch._previous_budget_boundary(ts)
        nxt = orch._next_budget_boundary(ts)
        assert prev == self._ts("America/Los_Angeles", 2026, 3, 8, 0, 0, 0)
        assert nxt == self._ts("America/Los_Angeles", 2026, 3, 9, 0, 0, 0)
        # The window is 23 wall-clock hours (in seconds: 23*3600).
        assert (nxt - prev) == 23 * 3600

    def test_day_boundary_handles_dst_fall_back(self, tmp_path):
        # 2026-11-01 in America/Los_Angeles: DST fall-back at 02:00 PDT
        # → 01:00 PST. Day boundary at 2026-11-01 00:00 PDT and
        # 2026-11-02 00:00 PST.
        orch = self._make_orchestrator(tmp_path, window="day",
                                       tz="America/Los_Angeles")
        ts = self._ts("America/Los_Angeles", 2026, 11, 1, 12, 0, 0)
        prev = orch._previous_budget_boundary(ts)
        nxt = orch._next_budget_boundary(ts)
        assert prev == self._ts("America/Los_Angeles", 2026, 11, 1, 0, 0, 0)
        assert nxt == self._ts("America/Los_Angeles", 2026, 11, 2, 0, 0, 0)
        # The window is 25 wall-clock hours.
        assert (nxt - prev) == 25 * 3600

    def test_week_boundary_spans_dst_transition(self, tmp_path):
        # Week containing the spring-forward transition (2026-03-08).
        # Sunday 2026-03-08 00:00 PST → Sunday 2026-03-15 00:00 PDT.
        # That week is 7*24 - 1 = 167 hours long.
        orch = self._make_orchestrator(tmp_path, window="week",
                                       tz="America/Los_Angeles")
        ts = self._ts("America/Los_Angeles", 2026, 3, 10, 12, 0, 0)
        prev = orch._previous_budget_boundary(ts)
        nxt = orch._next_budget_boundary(ts)
        assert prev == self._ts("America/Los_Angeles", 2026, 3, 8, 0, 0, 0)
        assert nxt == self._ts("America/Los_Angeles", 2026, 3, 15, 0, 0, 0)
        assert (nxt - prev) == 167 * 3600

    # ----- cold-start snapping -----

    def test_cold_start_snaps_to_previous_boundary(self, tmp_path, monkeypatch):
        # Boot at 14:17 with hour-window: persisted budget_window_start
        # must be 14:00, not 14:17.
        import time
        orch = self._make_orchestrator(tmp_path, window="hour", tz="UTC")
        fake_now = self._ts("UTC", 2026, 5, 5, 14, 17, 23)
        monkeypatch.setattr(time, "time", lambda: fake_now)
        orch._roll_budget_window_if_due()
        snapped = self._ts("UTC", 2026, 5, 5, 14, 0, 0)
        assert orch.state.budget_window_start == snapped
        # And the persisted state file matches.
        import json
        with open(tmp_path / "state.json") as f:
            data = json.load(f)
        assert data["budget_window_start"] == snapped

    def test_cold_start_day_snaps_to_local_midnight(self, tmp_path, monkeypatch):
        import time
        tz = "America/Los_Angeles"
        orch = self._make_orchestrator(tmp_path, window="day", tz=tz)
        fake_now = self._ts(tz, 2026, 5, 5, 14, 17, 23)
        monkeypatch.setattr(time, "time", lambda: fake_now)
        orch._roll_budget_window_if_due()
        snapped = self._ts(tz, 2026, 5, 5, 0, 0, 0)
        assert orch.state.budget_window_start == snapped

    # ----- timezone resolution -----

    def test_invalid_timezone_falls_back_to_utc_with_warning(self, tmp_path,
                                                              caplog):
        cfg = ServiceConfig()
        cfg.budget_limit = 10.0
        cfg.budget_window = "day"
        cfg.budget_timezone = "Not/A/Real/Zone"
        project_store = MagicMock()
        project_store.list_all.return_value = []
        import logging
        caplog.set_level(logging.WARNING, logger="oompah.orchestrator")
        orch = Orchestrator(
            config=cfg,
            workflow_path="WORKFLOW.md",
            project_store=project_store,
            state_path=str(tmp_path / "state.json"),
        )
        tz = orch._budget_tz()
        assert str(tz.key) == "UTC"
        assert any("Invalid OOMPAH_BUDGET_TIMEZONE" in r.message
                   for r in caplog.records)

    def test_explicit_iana_timezone_used(self, tmp_path):
        orch = self._make_orchestrator(tmp_path, window="day",
                                       tz="Europe/London")
        assert str(orch._budget_tz().key) == "Europe/London"

    # ----- snapshot integration -----

    def test_window_remaining_seconds_uses_calendar_boundary(self, tmp_path,
                                                              monkeypatch):
        import time
        orch = self._make_orchestrator(tmp_path, window="hour", tz="UTC")
        # 14:30 — 30 min until 15:00 boundary.
        monkeypatch.setattr(
            time, "time",
            lambda: self._ts("UTC", 2026, 5, 5, 14, 30, 0),
        )
        remaining = orch._budget_window_remaining_seconds()
        assert remaining == 30 * 60


class TestModelProviderFreeCheck:
    """Tests for ModelProvider.is_model_explicitly_free — distinguishes
    'not in map' from 'in map with zeros' so the budget bypass is
    conservative."""

    def test_free_when_explicit_zero_zero(self):
        from oompah.models import ModelProvider
        p = ModelProvider(
            id="p", name="t", base_url="http://x",
            model_costs={"freemodel": {"cost_per_1k_input": 0, "cost_per_1k_output": 0}},
        )
        assert p.is_model_explicitly_free("freemodel") is True

    def test_paid_when_any_nonzero(self):
        from oompah.models import ModelProvider
        p = ModelProvider(
            id="p", name="t", base_url="http://x",
            model_costs={"sonnet": {"cost_per_1k_input": 0.003, "cost_per_1k_output": 0.015}},
        )
        assert p.is_model_explicitly_free("sonnet") is False

    def test_paid_when_only_input_zero(self):
        from oompah.models import ModelProvider
        p = ModelProvider(
            id="p", name="t", base_url="http://x",
            model_costs={"weird": {"cost_per_1k_input": 0, "cost_per_1k_output": 0.001}},
        )
        # Both must be zero — output-only zero still counts as paid.
        assert p.is_model_explicitly_free("weird") is False

    def test_missing_model_treated_as_paid(self):
        from oompah.models import ModelProvider
        p = ModelProvider(
            id="p", name="t", base_url="http://x",
            model_costs={"known": {"cost_per_1k_input": 0, "cost_per_1k_output": 0}},
        )
        # Conservative — no entry means unknown pricing, not free.
        assert p.is_model_explicitly_free("unknown-model") is False

    def test_empty_model_costs_map(self):
        from oompah.models import ModelProvider
        p = ModelProvider(id="p", name="t", base_url="http://x")
        assert p.is_model_explicitly_free("any-model") is False

    def test_empty_model_string(self):
        from oompah.models import ModelProvider
        p = ModelProvider(
            id="p", name="t", base_url="http://x",
            model_costs={"x": {"cost_per_1k_input": 0, "cost_per_1k_output": 0}},
        )
        assert p.is_model_explicitly_free("") is False
        assert p.is_model_explicitly_free(None) is False  # type: ignore


class TestBudgetGateFreeTierBypass:
    """Tests for the budget cap's zero-cost-model bypass in _should_dispatch."""

    def _make_orchestrator(self, tmp_path):
        from oompah.config import ServiceConfig
        from oompah.providers import ProviderStore
        from oompah.models import ModelProvider, AgentProfile
        from unittest.mock import MagicMock

        cfg = ServiceConfig()
        cfg.budget_limit = 10.0
        cfg.agent_profiles = [
            AgentProfile(name="default", command="claude", model_role="fast"),
        ]
        # Single provider with both a free and a paid model.
        prov = ModelProvider(
            id="prov-1", name="TestProvider", base_url="http://test",
            models=["free-model", "paid-model"],
            model_roles={"fast": "free-model", "standard": "paid-model"},
            model_costs={
                "free-model": {"cost_per_1k_input": 0, "cost_per_1k_output": 0},
                "paid-model": {"cost_per_1k_input": 0.005, "cost_per_1k_output": 0.025},
            },
        )
        # Pass a path to a nonexistent file so ProviderStore doesn't
        # auto-load the real .oompah/providers.json from the cwd.
        provider_store = ProviderStore(path=str(tmp_path / "providers.json"))
        provider_store._providers = {prov.id: prov}
        project_store = MagicMock()
        project_store.list_all.return_value = []
        return Orchestrator(
            config=cfg, workflow_path="WORKFLOW.md",
            provider_store=provider_store, project_store=project_store,
            state_path=str(tmp_path / "state.json"),
        )

    def _force_over_budget(self, orch):
        orch.state.agent_totals.estimated_cost = 999.0
        orch.state.budget_window_start = __import__("time").time()
        orch.state.budget_window_kind = "day"

    def test_free_model_dispatched_when_over_budget(self, tmp_path):
        orch = self._make_orchestrator(tmp_path)
        issue = _make_issue("feat-1", state="open")
        self._force_over_budget(orch)
        assert orch._should_dispatch(issue) is True
        assert orch.state.free_tier_dispatches_this_window == 1
        assert orch.state.budget_exceeded is True

    def test_paid_model_rejected_when_over_budget(self, tmp_path):
        # Override the AgentProfile to route to a paid model.
        from oompah.models import AgentProfile
        orch = self._make_orchestrator(tmp_path)
        orch.config.agent_profiles = [AgentProfile(name="standard", command="claude", model_role="standard")]
        issue = _make_issue("feat-2", state="open")
        self._force_over_budget(orch)
        assert orch._should_dispatch(issue) is False
        assert orch.state.free_tier_dispatches_this_window == 0

    def test_under_budget_paid_model_dispatched(self, tmp_path):
        from oompah.models import AgentProfile
        orch = self._make_orchestrator(tmp_path)
        orch.config.agent_profiles = [AgentProfile(name="standard", command="claude", model_role="standard")]
        issue = _make_issue("feat-3", state="open")
        # Default state — under budget. Dispatch should pass.
        assert orch._should_dispatch(issue) is True

    def test_window_roll_resets_free_tier_counter(self, tmp_path):
        import time
        orch = self._make_orchestrator(tmp_path)
        orch.config.budget_window = "hour"
        orch.state.free_tier_dispatches_this_window = 5
        # Force window start way in the past.
        orch.state.budget_window_start = time.time() - 7200  # 2h ago
        orch.state.budget_window_kind = "hour"
        orch.state.agent_totals.estimated_cost = 999.0
        # _check_budget rolls; rollover must zero the free-tier counter.
        orch._roll_budget_window_if_due()
        assert orch.state.free_tier_dispatches_this_window == 0
        assert orch.state.agent_totals.estimated_cost == 0.0

    def test_unknown_model_costs_treated_as_paid(self, tmp_path):
        # Profile resolves to a model that's not in the provider's
        # model_costs map. Conservative: rejected.
        from oompah.models import AgentProfile
        orch = self._make_orchestrator(tmp_path)
        orch.config.agent_profiles = [
            AgentProfile(name="x", command="claude", model="model-not-in-costs"),
        ]
        # Add the model to the provider's `models` list so resolution finds it.
        prov = orch.provider_store.get("prov-1")
        prov.models.append("model-not-in-costs")
        prov.default_model = "model-not-in-costs"
        issue = _make_issue("feat-4", state="open")
        self._force_over_budget(orch)
        assert orch._should_dispatch(issue) is False


class TestYoloChurnMagnetGate:
    """Tests for the high-risk PR gate (oompah-zlz_2-rxwe.3).

    When project.churn_magnet_gate_enabled is True, the YOLO sync must
    skip merge/enqueue for PRs that have the [churn-magnet] label
    AND are stale (needs_rebase=True).  The gate is evaluated OUTSIDE
    the `ci_ok and not needs_rebase` base condition so stale PRs are
    caught regardless of CI state, and it fires even when CI is
    "passed" and mergeable.
    """

    def _make_orchestrator(self, tmp_path, projects=None):
        project_store = MagicMock()
        project_store.list_all.return_value = projects or []
        project_store.get.side_effect = lambda pid: next(
            (p for p in (projects or []) if p.id == pid), None
        )
        orch = Orchestrator(
            config=_make_config(),
            workflow_path="WORKFLOW.md",
            project_store=project_store,
            state_path=str(tmp_path / "state.json"),
        )
        return orch

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_gate_disabled_merge_succeeds(self, mock_slug, mock_detect, tmp_path):
        """Gate is off → PR merges normally (baseline sanity check)."""
        project = _make_project(churn_magnet_gate_enabled=False)
        project.yolo = True

        provider = MagicMock()
        provider.merge_review.return_value = (True, "merged")
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {
            "proj-1": [
                _make_review("1", source_branch="feat-1", ci_status="passed"),
            ]
        }

        orch._yolo_review_actions_sync()

        provider.merge_review.assert_called_once_with("org/repo", "1")

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_gate_enabled_no_Churn_magnet_label_merge_succeeds(
        self, mock_slug, mock_detect, tmp_path
    ):
        """Gate on, PR not marked churn-magnet → merges normally."""
        project = _make_project(churn_magnet_gate_enabled=True)
        project.yolo = True

        provider = MagicMock()
        provider.merge_review.return_value = (True, "merged")
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {
            "proj-1": [
                _make_review("1", source_branch="feat-1", ci_status="passed"),
            ]
        }

        orch._yolo_review_actions_sync()

        provider.merge_review.assert_called_once_with("org/repo", "1")

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_gate_enabled_churn_magnet_not_stale_merge_succeeds(
        self, mock_slug, mock_detect, tmp_path
    ):
        """Gate on, PR is churn-magnet but not stale → merges normally."""
        project = _make_project(churn_magnet_gate_enabled=True)
        project.yolo = True

        provider = MagicMock()
        provider.merge_review.return_value = (True, "merged")
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {
            "proj-1": [
                _make_review(
                    "1",
                    source_branch="feat-1",
                    ci_status="passed",
                    labels=["churn-magnet"],
                    churn_magnet=True,
                ),
            ]
        }

        orch._yolo_review_actions_sync()

        # Not skipped — merge should succeeds
        provider.merge_review.assert_called_once_with("org/repo", "1")

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_gate_enabled_churn_magnet_stale_skipped(self, mock_slug, mock_detect, tmp_path):
        """Gate on, PR is churn-magnet AND stale → SKIPPED, no merge/enqueue."""
        project = _make_project(churn_magnet_gate_enabled=True)
        project.yolo = True

        provider = MagicMock()
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {
            "proj-1": [
                _make_review(
                    "1",
                    source_branch="feat-1",
                    ci_status="passed",
                    needs_rebase=True,
                    labels=["churn-magnet"],
                    churn_magnet=True,
                ),
            ]
        }

        with patch.object(orch, "_record_yolo_action") as mock_record:
            orch._yolo_review_actions_sync()

            # Gate fires — neither merge_review nor enable_auto_merge called
            provider.merge_review.assert_not_called()
            assert not provider.enable_auto_merge.called

            # _record_yolo_action called with 'gate_blocked'
            gate_calls = [
                c for c in mock_record.call_args_list
                if c[0][2] == "gate_blocked"
            ]
            assert len(gate_calls) == 1, (
                f"Expected one gate_blocked call; got {gate_calls}"
            )

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_gate_enabled_stale_no_churn_magnet_not_merged(
        self, mock_slug, mock_detect, tmp_path
    ):
        """Gate on, PR is stale but not churn-magnet: not merged (stale PR).

        Stale PRs (needs_rebase=True) are not merged regardless of the gate.
        This test confirms the gate does NOT incorrectly merge a stale PR
        when the churn-magnet label is absent — the base condition
        `if ci_ok and not needs_rebase` already handles this case.
        """
        project = _make_project(churn_magnet_gate_enabled=True)
        project.yolo = True

        provider = MagicMock()
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = self._make_orchestrator(tmp_path, projects=[project])
        # needs_rebase=True + no churn-magnet label → base condition fails,
        # no merge, and gate does NOT fire (no churn-magnet label).
        orch._reviews_cache = {
            "proj-1": [
                _make_review(
                    "1",
                    source_branch="feat-1",
                    ci_status="passed",
                    needs_rebase=True,
                    labels=[],
                    churn_magnet=False,
                ),
            ]
        }

        with patch.object(orch, "_record_yolo_action") as mock_record:
            orch._yolo_review_actions_sync()

            # Neither merge_review nor enable_auto_merge called (stale)
            provider.merge_review.assert_not_called()
            provider.enable_auto_merge.assert_not_called()

            # No gate_blocked call (gate requires churn-magnet label)
            gate_calls = [
                c for c in mock_record.call_args_list
                if c[0][2] == "gate_blocked"
            ]
            assert len(gate_calls) == 0

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_gate_enabled_merge_queue_stale_churn_magnet_enqueued(
        self, mock_slug, mock_detect, tmp_path
    ):
        """Gate on + merge_queue: stale churn-magnet PR is skipped, not enqueued."""
        project = _make_project(churn_magnet_gate_enabled=True)
        project.yolo = True
        project.merge_queue_enabled = True

        provider = MagicMock()
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {
            "proj-1": [
                _make_review(
                    "1",
                    source_branch="feat-1",
                    ci_status="passed",
                    needs_rebase=True,
                    labels=["churn-magnet"],
                    churn_magnet=True,
                ),
            ]
        }

        with patch.object(orch, "_record_yolo_action") as mock_record:
            orch._yolo_review_actions_sync()

            # Gate fires → enable_auto_merge NOT called
            provider.enable_auto_merge.assert_not_called()
            provider.merge_review.assert_not_called()

            gate_calls = [
                c for c in mock_record.call_args_list
                if c[0][2] == "gate_blocked"
            ]
            assert len(gate_calls) == 1
