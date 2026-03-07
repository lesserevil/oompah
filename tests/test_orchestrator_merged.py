"""Tests for orchestrator merged-issue labeling and dispatch gating."""

from unittest.mock import MagicMock, patch, call

import pytest

from oompah.config import ServiceConfig
from oompah.models import BlockerRef, Issue
from oompah.orchestrator import Orchestrator


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
        orch._unmerged_pr_branches = {"feat-branch"}
        orch._merged_branches = set()

        blocker = BlockerRef(id="feat-branch", identifier="feat-branch", state="closed")
        assert orch._blocker_has_unmerged_pr(blocker) is True

    def test_blocker_branch_merged_is_not_blocking(self, tmp_path):
        orch = self._make_orchestrator(tmp_path)
        orch._unmerged_pr_branches = set()
        orch._merged_branches = {"feat-branch"}

        blocker = BlockerRef(id="feat-branch", identifier="feat-branch", state="closed")
        assert orch._blocker_has_unmerged_pr(blocker) is False

    def test_blocker_closed_but_not_merged_is_blocking(self, tmp_path):
        """Key test: closed issue without a merged branch should still block."""
        orch = self._make_orchestrator(tmp_path)
        orch._unmerged_pr_branches = set()
        orch._merged_branches = {"other-branch"}  # feat-branch NOT in merged set

        blocker = BlockerRef(id="feat-branch", identifier="feat-branch", state="closed")
        assert orch._blocker_has_unmerged_pr(blocker) is True

    def test_no_merged_data_falls_back_to_permissive(self, tmp_path):
        """If merged branch data unavailable, don't block (backwards compat)."""
        orch = self._make_orchestrator(tmp_path)
        orch._unmerged_pr_branches = set()
        orch._merged_branches = None

        blocker = BlockerRef(id="feat-branch", identifier="feat-branch", state="closed")
        assert orch._blocker_has_unmerged_pr(blocker) is False

    def test_empty_blocker_id_is_not_blocking(self, tmp_path):
        orch = self._make_orchestrator(tmp_path)
        orch._unmerged_pr_branches = set()
        orch._merged_branches = set()

        blocker = BlockerRef(id="", identifier="", state="closed")
        assert orch._blocker_has_unmerged_pr(blocker) is False


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
