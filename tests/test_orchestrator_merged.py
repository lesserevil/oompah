"""Tests for orchestrator merged-issue labeling and dispatch gating."""

from unittest.mock import MagicMock, patch, call

import pytest

from oompah.config import ServiceConfig
from oompah.models import BlockerRef, Issue
from oompah.orchestrator import Orchestrator
from oompah.scm import ReviewRequest


def _make_config() -> ServiceConfig:
    return ServiceConfig()


def _make_issue(identifier: str, state: str = "closed", labels: list | None = None,
                branch_name: str | None = None) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=f"Issue {identifier}",
        state=state,
        labels=labels or [],
        branch_name=branch_name,
    )


def _make_project(project_id: str = "proj-1", repo_url: str = "https://github.com/org/repo"):
    p = MagicMock()
    p.id = project_id
    p.repo_url = repo_url
    p.name = "test-project"
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

        mock_tracker.add_label.assert_called_once_with("feat-branch", "merged")

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

        mock_tracker.add_label.assert_not_called()

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

        mock_tracker.add_label.assert_not_called()

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

        mock_tracker.add_label.assert_not_called()

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

        mock_tracker.add_label.assert_called_once_with("issue-123", "merged")

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

    def test_add_label_error_does_not_crash(self, tmp_path):
        from oompah.tracker import TrackerError

        project = _make_project()
        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._merged_branches = {"feat-branch"}

        mock_tracker = MagicMock()
        mock_tracker.fetch_issues_by_states.return_value = [
            _make_issue("feat-branch", state="closed"),
        ]
        mock_tracker.add_label.side_effect = TrackerError("bd failed")
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

        mock_tracker.update_issue.assert_called_once_with("feat-1", status="open")

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

        issue = _make_issue("feat-1", state="in_progress")
        issue.project_id = project.id
        orch.state.retry_attempts["feat-1"] = MagicMock()
        orch._reset_orphaned_in_progress([issue])

        mock_tracker.update_issue.assert_not_called()

    def test_skips_open_issues(self, tmp_path):
        project = _make_project()
        orch = self._make_orchestrator(tmp_path, projects=[project])
        mock_tracker = MagicMock()
        orch._project_trackers[project.id] = mock_tracker

        issue = _make_issue("feat-1", state="open")
        issue.project_id = project.id
        orch._reset_orphaned_in_progress([issue])

        mock_tracker.update_issue.assert_not_called()


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
        issue = _make_issue("feat-1", state="in_progress")
        assert orch._should_dispatch(issue) is True


def _make_review(
    review_id: str,
    source_branch: str = "feat-branch",
    ci_status: str = "passed",
    has_conflicts: bool = False,
    needs_rebase: bool = False,
    draft: bool = False,
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
        """When multiple PRs have conflicts, each gets a conflict notification (no serialization)."""
        project = _make_project()
        project.yolo = True

        provider = MagicMock()
        # _yolo_notify_conflict calls provider.get_review() which returns a review object
        mock_review = MagicMock()
        mock_review.source_branch = "feat-1"
        mock_review.target_branch = "main"
        provider.get_review.return_value = mock_review
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = self._make_orchestrator(tmp_path, projects=[project])

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

        # Both conflict reviews should trigger get_review (conflict notification, not rebase)
        assert provider.get_review.call_count == 2
        # rebase_review should NOT be called (conflicts use notify, not rebase)
        assert provider.rebase_review.call_count == 0

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_only_one_ci_retry_per_project_per_tick(
        self, mock_slug, mock_detect, tmp_path
    ):
        """When multiple PRs have failed CI, only retry the first one per tick."""
        project = _make_project()
        project.yolo = True

        provider = MagicMock()
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = self._make_orchestrator(tmp_path, projects=[project])

        reviews = [
            _make_review("1", source_branch="feat-1", ci_status="failed"),
            _make_review("2", source_branch="feat-2", ci_status="failed"),
        ]
        orch._reviews_cache = {project.id: reviews}

        # _yolo_retry_ci talks to the tracker; mock it out
        orch._yolo_retry_ci = MagicMock()

        orch._yolo_review_actions_sync()

        # Only one CI retry should have been attempted
        assert orch._yolo_retry_ci.call_count == 1
        assert orch._yolo_retry_ci.call_args[0][1].id == "1"

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
                                          state="in_progress", priority=0)
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
            state="open",
            project_id=None,
        )
        orch._reviews_cache = {
            "proj-1": [_make_review("1", "feat-1", ci_status="passed")]
        }
        assert orch._should_dispatch(issue) is True
