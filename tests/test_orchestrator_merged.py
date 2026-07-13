"""Tests for orchestrator merged-issue labeling and dispatch gating."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from oompah.config import ServiceConfig
from oompah.models import BlockerRef, Issue, RunningEntry
from oompah.orchestrator import Orchestrator
from oompah.projects import github_work_branch_name
from oompah.scm import ReviewRequest
from oompah.statuses import (
    DONE,
    IN_PROGRESS,
    IN_REVIEW,
    MERGED,
    NEEDS_CI_FIX,
    NEEDS_REBASE,
)


def _make_config() -> ServiceConfig:
    return ServiceConfig()


def _make_issue(identifier: str, state: str = "closed", labels: list | None = None,
                branch_name: str | None = None,
                description: str | None = "Issue body — exists so the empty-description gate passes.",
                issue_type: str = "task",
                parent_id: str | None = None,
                project_id: str | None = None) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=f"Issue {identifier}",
        description=description,
        state=state,
        issue_type=issue_type,
        parent_id=parent_id,
        project_id=project_id,
        labels=labels or [],
        branch_name=branch_name,
    )


def _make_project(project_id: str = "proj-1", repo_url: str = "https://github.com/org/repo",
                 churn_magnet_gate_enabled: bool = False,
                 churn_magnet_top_n: int = 10,
                 epic_strategy: str = "flat"):
    p = MagicMock()
    p.id = project_id
    p.repo_url = repo_url
    p.name = "test-project"
    p.repo_path = "/tmp/repo"
    p.default_branch = "main"
    p.access_token = None
    p.merge_queue_enabled = False  # default: direct-merge mode
    p.paused = False  # default: not paused
    p.churn_magnet_gate_enabled = churn_magnet_gate_enabled
    p.churn_magnet_top_n = churn_magnet_top_n
    p.epic_strategy = epic_strategy
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
        # The sweep still checks projects because provider fallback can
        # reconcile landed PRs when the merged-branch cache is empty.
        orch.project_store.list_all.assert_called_once()

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

    def test_skips_matching_merged_branch_when_current_tip_is_ahead(self, tmp_path):
        project = _make_project()
        project.repo_path = str(tmp_path)
        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._merged_branches = {"TASK-737"}
        orch._managed_branch_ref_exists = MagicMock(return_value=True)
        orch._count_review_branch_ahead = MagicMock(
            return_value=(3, ["0e6fd90 TASK-737: Close task as Done"], "")
        )

        mock_tracker = MagicMock()
        mock_tracker.fetch_issues_by_states.return_value = [
            _make_issue("TASK-737", state=DONE, project_id=project.id),
        ]
        orch._project_trackers[project.id] = mock_tracker

        orch._label_merged_issues()

        mock_tracker.update_issue.assert_not_called()
        orch._count_review_branch_ahead.assert_called_once_with(
            project,
            "main",
            "TASK-737",
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

    @patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo")
    @patch("oompah.orchestrator.detect_provider")
    def test_done_ci_fix_helper_marked_merged_when_review_branch_landed(
        self,
        mock_detect,
        _mock_slug,
        tmp_path,
    ):
        project = _make_project()
        project.repo_path = str(tmp_path)
        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._merged_branches = set()
        landed_branch = "oompah/proj/gh-269"

        provider = MagicMock()

        def find_pr_for_branch(_slug, branch):
            if branch != landed_branch:
                return None
            return ReviewRequest(
                id="270",
                title="PR #270",
                url="https://github.com/org/repo/pull/270",
                author="alice",
                state="merged",
                source_branch=landed_branch,
                target_branch="main",
                created_at="2026-01-01",
                updated_at="2026-01-02",
            )

        provider.find_pr_for_branch.side_effect = find_pr_for_branch
        mock_detect.return_value = provider

        helper = _make_issue(
            "example-org/oompah#271",
            state=DONE,
            branch_name="oompah/proj/gh-271",
            project_id=project.id,
        )
        helper.title = f"CI fix: PR #270 on branch {landed_branch}"
        mock_tracker = MagicMock()
        mock_tracker.fetch_issues_by_states.return_value = [helper]
        orch._project_trackers[project.id] = mock_tracker

        orch._label_merged_issues()

        assert provider.find_pr_for_branch.call_args_list[-1] == call(
            "org/repo",
            landed_branch,
        )
        mock_tracker.update_issue.assert_called_once_with(
            helper.identifier,
            status=MERGED,
        )

    def test_done_issue_with_open_review_is_not_closed_from_stale_merged_ref(
        self,
        tmp_path,
    ):
        project = _make_project()
        project.repo_path = str(tmp_path)
        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._merged_branches = {"feat-branch"}
        orch._reviews_cache = {
            project.id: [
                ReviewRequest(
                    id="271",
                    title="PR #271",
                    url="https://github.com/org/repo/pull/271",
                    author="alice",
                    state="open",
                    source_branch="feat-branch",
                    target_branch="main",
                    created_at="2026-01-01",
                    updated_at="2026-01-02",
                )
            ]
        }

        mock_tracker = MagicMock()
        mock_tracker.fetch_issues_by_states.return_value = [
            _make_issue("feat-branch", state=DONE, project_id=project.id),
        ]
        orch._project_trackers[project.id] = mock_tracker

        orch._label_merged_issues()

        mock_tracker.update_issue.assert_not_called()

    def test_shared_epic_child_not_marked_merged_from_child_branch(self, tmp_path):
        project = _make_project(epic_strategy="shared")
        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._merged_branches = {"TASK-1"}

        parent = _make_issue(
            "EPIC-1",
            issue_type="epic",
            project_id=project.id,
        )
        child = _make_issue(
            "TASK-1",
            state="In Review",
            parent_id="EPIC-1",
            project_id=project.id,
        )
        mock_tracker = MagicMock()
        mock_tracker.fetch_issues_by_states.return_value = [child]
        mock_tracker.fetch_issue_detail.return_value = parent
        orch._project_trackers[project.id] = mock_tracker

        orch._label_merged_issues()

        mock_tracker.update_issue.assert_not_called()

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


class TestReconcileStaleInReviewTasks:
    """Tests for _reconcile_stale_in_review_tasks."""

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

    def test_keeps_task_in_review_when_open_review_is_cached(self, tmp_path):
        project = _make_project()
        project.repo_path = str(tmp_path)
        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {
            project.id: [
                ReviewRequest(
                    id="10",
                    title="PR #10",
                    url="https://github.com/org/repo/pull/10",
                    author="alice",
                    state="open",
                    source_branch="TASK-1",
                    target_branch="main",
                    created_at="2026-01-01",
                    updated_at="2026-01-01",
                )
            ]
        }
        orch._merged_branches = set()

        mock_tracker = MagicMock()
        mock_tracker.fetch_issues_by_states.return_value = [
            _make_issue("TASK-1", state="In Review"),
        ]
        orch._project_trackers[project.id] = mock_tracker

        orch._reconcile_stale_in_review_tasks()

        mock_tracker.update_issue.assert_not_called()
        mock_tracker.add_comment.assert_not_called()

    def test_repairs_merged_task_with_open_unmerged_review(self, tmp_path):
        project = _make_project()
        project.repo_path = str(tmp_path)
        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {
            project.id: [
                ReviewRequest(
                    id="222",
                    title="PR #222",
                    url="https://github.com/org/repo/pull/222",
                    author="alice",
                    state="open",
                    source_branch="TASK-730",
                    target_branch="main",
                    created_at="2026-01-01",
                    updated_at="2026-01-01",
                )
            ]
        }
        orch._count_review_branch_ahead = MagicMock(
            return_value=(2, ["abc123 TASK-730: fix"], "")
        )

        mock_tracker = MagicMock()
        mock_tracker.fetch_issues_by_states.return_value = [
            _make_issue("TASK-730", state=MERGED, project_id=project.id),
        ]
        orch._project_trackers[project.id] = mock_tracker

        orch._reconcile_terminal_open_reviews()

        mock_tracker.fetch_issues_by_states.assert_called_once_with([MERGED])
        mock_tracker.update_issue.assert_called_once_with(
            "TASK-730", status=IN_REVIEW
        )
        orch._count_review_branch_ahead.assert_called_once_with(
            project,
            "main",
            "TASK-730",
        )

    def test_repairs_merged_conflicted_review_to_needs_rebase(self, tmp_path):
        project = _make_project()
        project.repo_path = str(tmp_path)
        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {
            project.id: [
                ReviewRequest(
                    id="224",
                    title="PR #224",
                    url="https://github.com/org/repo/pull/224",
                    author="alice",
                    state="open",
                    source_branch="TASK-733",
                    target_branch="main",
                    created_at="2026-01-01",
                    updated_at="2026-01-01",
                    has_conflicts=True,
                )
            ]
        }
        orch._count_review_branch_ahead = MagicMock(return_value=(4, [], ""))

        mock_tracker = MagicMock()
        mock_tracker.fetch_issues_by_states.return_value = [
            _make_issue("TASK-733", state=MERGED, project_id=project.id),
        ]
        orch._project_trackers[project.id] = mock_tracker

        orch._reconcile_terminal_open_reviews()

        mock_tracker.update_issue.assert_called_once_with(
            "TASK-733", status=NEEDS_REBASE
        )

    def test_repairs_github_work_branch_merged_state(self, tmp_path):
        project = _make_project()
        project.repo_path = str(tmp_path)
        orch = self._make_orchestrator(tmp_path, projects=[project])
        work_branch = "oompah/proj/gh-42"
        orch._reviews_cache = {
            project.id: [
                ReviewRequest(
                    id="42",
                    title="PR #42",
                    url="https://github.com/org/repo/pull/42",
                    author="alice",
                    state="open",
                    source_branch=work_branch,
                    target_branch="main",
                    created_at="2026-01-01",
                    updated_at="2026-01-01",
                )
            ]
        }
        orch._count_review_branch_ahead = MagicMock(return_value=(1, [], ""))

        issue = _make_issue("org/repo#42", state=MERGED, project_id=project.id)
        issue.work_branch = work_branch
        mock_tracker = MagicMock()
        mock_tracker.fetch_issues_by_states.return_value = [issue]
        orch._project_trackers[project.id] = mock_tracker

        orch._reconcile_terminal_open_reviews()

        mock_tracker.update_issue.assert_called_once_with(
            "org/repo#42", status=IN_REVIEW
        )
        orch._count_review_branch_ahead.assert_called_once_with(
            project,
            "main",
            work_branch,
        )

    @patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo")
    @patch("oompah.orchestrator.detect_provider")
    def test_false_merged_repair_skips_stale_cached_open_review(
        self,
        mock_detect,
        _mock_slug,
        tmp_path,
    ):
        project = _make_project()
        project.repo_path = str(tmp_path)
        project.access_token = "token"
        orch = self._make_orchestrator(tmp_path, projects=[project])
        work_branch = "epic-imported-branch"
        orch._reviews_cache = {
            project.id: [
                ReviewRequest(
                    id="195",
                    title="PR #195",
                    url="https://github.com/org/repo/pull/195",
                    author="alice",
                    state="open",
                    source_branch=work_branch,
                    target_branch="main",
                    created_at="2026-01-01",
                    updated_at="2026-01-01",
                )
            ]
        }
        provider = MagicMock()
        provider.find_pr_for_branch.return_value = ReviewRequest(
            id="195",
            title="PR #195",
            url="https://github.com/org/repo/pull/195",
            author="alice",
            state="merged",
            source_branch=work_branch,
            target_branch="main",
            created_at="2026-01-01",
            updated_at="2026-01-02",
        )
        mock_detect.return_value = provider
        orch._count_review_branch_ahead = MagicMock(return_value=(11, [], ""))

        issue = _make_issue("OVA-1", state=MERGED, project_id=project.id)
        issue.work_branch = work_branch
        mock_tracker = MagicMock()
        mock_tracker.fetch_issues_by_states.return_value = [issue]
        orch._project_trackers[project.id] = mock_tracker

        orch._reconcile_terminal_open_reviews()

        provider.find_pr_for_branch.assert_called_once_with("org/repo", work_branch)
        orch._count_review_branch_ahead.assert_not_called()
        mock_tracker.update_issue.assert_not_called()

    def test_keeps_merged_when_open_review_branch_is_not_ahead(self, tmp_path):
        project = _make_project()
        project.repo_path = str(tmp_path)
        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {
            project.id: [
                ReviewRequest(
                    id="10",
                    title="PR #10",
                    url="https://github.com/org/repo/pull/10",
                    author="alice",
                    state="open",
                    source_branch="TASK-1",
                    target_branch="main",
                    created_at="2026-01-01",
                    updated_at="2026-01-01",
                )
            ]
        }
        orch._count_review_branch_ahead = MagicMock(return_value=(0, [], ""))

        mock_tracker = MagicMock()
        mock_tracker.fetch_issues_by_states.return_value = [
            _make_issue("TASK-1", state=MERGED, project_id=project.id),
        ]
        orch._project_trackers[project.id] = mock_tracker

        orch._reconcile_terminal_open_reviews()

        mock_tracker.update_issue.assert_not_called()

    def test_marks_in_review_task_merged_when_branch_is_merged(self, tmp_path):
        project = _make_project()
        project.repo_path = str(tmp_path)
        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {project.id: []}
        orch._merged_branches = {"TASK-1"}

        mock_tracker = MagicMock()
        mock_tracker.fetch_issues_by_states.return_value = [
            _make_issue("TASK-1", state="In Review"),
        ]
        orch._project_trackers[project.id] = mock_tracker

        orch._reconcile_stale_in_review_tasks()

        mock_tracker.update_issue.assert_called_once_with("TASK-1", status="Merged")
        mock_tracker.add_comment.assert_not_called()

    @patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo")
    @patch("oompah.orchestrator.detect_provider")
    def test_stale_github_in_review_uses_generated_branch_before_needs_human(
        self,
        mock_detect,
        _mock_slug,
        tmp_path,
    ):
        project = _make_project()
        project.name = "oompah"
        project.repo_path = str(tmp_path)
        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {project.id: []}
        orch._merged_branches = set()

        expected_branch = github_work_branch_name(project.name, "269")
        provider = MagicMock()
        provider.find_pr_for_branch.return_value = ReviewRequest(
            id="290",
            title="PR #290",
            url="https://github.com/org/repo/pull/290",
            author="alice",
            state="merged",
            source_branch=expected_branch,
            target_branch="main",
            created_at="2026-01-01",
            updated_at="2026-01-02",
        )
        mock_detect.return_value = provider

        issue = _make_issue(
            "example-org/oompah#269",
            state=IN_REVIEW,
            project_id=project.id,
        )
        issue.tracker_kind = "github_issues"
        issue.issue_number = "269"

        mock_tracker = MagicMock()
        mock_tracker.fetch_issues_by_states.return_value = [issue]
        orch._project_trackers[project.id] = mock_tracker

        orch._reconcile_stale_in_review_tasks()

        provider.find_pr_for_branch.assert_called_once_with(
            "org/repo",
            expected_branch,
        )
        mock_tracker.update_issue.assert_called_once_with(
            issue.identifier,
            status=MERGED,
        )
        mock_tracker.add_comment.assert_not_called()

    @patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo")
    @patch("oompah.orchestrator.detect_provider")
    def test_shared_epic_stale_review_uses_explicit_work_branch(
        self,
        mock_detect,
        _mock_slug,
        tmp_path,
    ):
        project = _make_project(epic_strategy="shared")
        project.repo_path = str(tmp_path)
        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch.project_store.epic_branch_name.side_effect = (
            lambda ident: f"epic-{ident}"
        )
        orch._reviews_cache = {project.id: []}
        orch._merged_branches = set()

        work_branch = "epic-NVIDIA-dev_ova_3"
        provider = MagicMock()
        provider.find_pr_for_branch.return_value = ReviewRequest(
            id="195",
            title="OVA-1",
            url="https://github.com/org/repo/pull/195",
            author="alice",
            state="merged",
            source_branch=work_branch,
            target_branch="main",
            created_at="2026-01-01",
            updated_at="2026-01-02",
        )
        mock_detect.return_value = provider

        issue = _make_issue(
            "OVA-1",
            state=IN_REVIEW,
            issue_type="epic",
            project_id=project.id,
        )
        issue.work_branch = work_branch
        mock_tracker = MagicMock()
        mock_tracker.fetch_issues_by_states.return_value = [issue]
        orch._project_trackers[project.id] = mock_tracker

        orch._reconcile_stale_in_review_tasks()

        provider.find_pr_for_branch.assert_called_once_with("org/repo", work_branch)
        mock_tracker.update_issue.assert_called_once_with("OVA-1", status=MERGED)
        mock_tracker.add_comment.assert_not_called()

    @patch("oompah.orchestrator.detect_provider", return_value=None)
    def test_reopens_when_merged_branch_name_is_stale(
        self,
        _mock_detect,
        tmp_path,
    ):
        project = _make_project()
        project.repo_path = str(tmp_path)
        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {project.id: []}
        orch._merged_branches = {"TASK-737"}
        orch._managed_branch_ref_exists = MagicMock(return_value=True)
        orch._count_review_branch_ahead = MagicMock(
            return_value=(3, ["0e6fd90 TASK-737: Close task as Done"], "")
        )

        mock_tracker = MagicMock()
        mock_tracker.fetch_issues_by_states.return_value = [
            _make_issue("TASK-737", state="In Review", project_id=project.id),
        ]
        orch._project_trackers[project.id] = mock_tracker

        orch._reconcile_stale_in_review_tasks()

        mock_tracker.update_issue.assert_called_once_with("TASK-737", status="Open")
        comment = mock_tracker.add_comment.call_args.args[1]
        assert "Unmerged commits: 3 commits" in comment
        assert "0e6fd90 TASK-737: Close task as Done" in comment
        assert orch._count_review_branch_ahead.call_count == 2

    def test_shared_epic_child_without_child_pr_becomes_done_when_on_epic_branch(
        self,
        tmp_path,
    ):
        project = _make_project(epic_strategy="shared")
        project.repo_path = str(tmp_path)
        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch.project_store.epic_branch_name.side_effect = (
            lambda ident: f"epic-{ident}"
        )
        orch._reviews_cache = {project.id: []}
        orch._merged_branches = set()

        parent = _make_issue(
            "EPIC-1",
            issue_type="epic",
            project_id=project.id,
        )
        child = _make_issue(
            "TASK-1",
            state="In Review",
            parent_id="EPIC-1",
            project_id=project.id,
        )
        mock_tracker = MagicMock()
        mock_tracker.fetch_issues_by_states.return_value = [child]
        mock_tracker.fetch_issue_detail.return_value = parent
        orch._project_trackers[project.id] = mock_tracker

        with patch.object(
            orch,
            "_done_review_child_has_epic_branch_work",
            return_value=True,
        ) as has_epic_branch_work:
            orch._reconcile_stale_in_review_tasks()

        has_epic_branch_work.assert_called_once_with(
            project,
            "epic-EPIC-1",
            child,
        )
        mock_tracker.update_issue.assert_called_once_with("TASK-1", status=DONE)
        mock_tracker.add_comment.assert_not_called()

    @patch("oompah.close_gate._count_commits_ahead")
    def test_shared_epic_uses_epic_branch_for_cached_review(
        self,
        mock_count,
        tmp_path,
    ):
        project = _make_project(epic_strategy="shared")
        project.repo_path = str(tmp_path)
        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch.project_store.epic_branch_name.side_effect = (
            lambda ident: f"epic-{ident}"
        )
        orch._reviews_cache = {
            project.id: [
                ReviewRequest(
                    id="260",
                    title="TASK-459",
                    url="https://github.com/org/repo/pull/260",
                    author="alice",
                    state="open",
                    source_branch="epic-TASK-459",
                    target_branch="main",
                    created_at="2026-01-01",
                    updated_at="2026-01-02",
                )
            ]
        }
        orch._merged_branches = set()

        mock_tracker = MagicMock()
        mock_tracker.fetch_issues_by_states.return_value = [
            _make_issue(
                "TASK-459",
                state="In Review",
                issue_type="epic",
                project_id=project.id,
            ),
        ]
        orch._project_trackers[project.id] = mock_tracker

        orch._reconcile_stale_in_review_tasks()

        mock_count.assert_not_called()
        mock_tracker.update_issue.assert_not_called()
        mock_tracker.add_comment.assert_not_called()

    @patch("oompah.close_gate._count_commits_ahead")
    @patch("oompah.orchestrator.extract_repo_slug")
    @patch("oompah.orchestrator.detect_provider")
    def test_shared_epic_uses_epic_branch_for_provider_lookup(
        self,
        mock_detect,
        mock_slug,
        mock_count,
        tmp_path,
    ):
        project = _make_project(epic_strategy="shared")
        project.repo_path = str(tmp_path)
        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch.project_store.epic_branch_name.side_effect = (
            lambda ident: f"epic-{ident}"
        )
        orch._reviews_cache = {project.id: []}
        orch._merged_branches = set()

        provider = MagicMock()

        def find_pr_for_branch(_slug, branch):
            if branch == "epic-TASK-459":
                return ReviewRequest(
                    id="260",
                    title="TASK-459",
                    url="https://github.com/org/repo/pull/260",
                    author="alice",
                    state="open",
                    source_branch="epic-TASK-459",
                    target_branch="main",
                    created_at="2026-01-01",
                    updated_at="2026-01-02",
                )
            return None

        provider.find_pr_for_branch.side_effect = find_pr_for_branch
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"
        mock_count.return_value = (0, [], "origin/TASK-459 missing")

        mock_tracker = MagicMock()
        mock_tracker.fetch_issues_by_states.return_value = [
            _make_issue(
                "TASK-459",
                state="In Review",
                issue_type="epic",
                project_id=project.id,
            ),
        ]
        orch._project_trackers[project.id] = mock_tracker

        orch._reconcile_stale_in_review_tasks()

        provider.find_pr_for_branch.assert_called_once_with(
            "org/repo",
            "epic-TASK-459",
        )
        mock_count.assert_not_called()
        mock_tracker.update_issue.assert_not_called()
        mock_tracker.add_comment.assert_not_called()

    @patch("oompah.close_gate._count_commits_ahead")
    @patch("oompah.orchestrator.extract_repo_slug")
    @patch("oompah.orchestrator.detect_provider")
    def test_reopens_closed_unmerged_review_with_commits_ahead(
        self,
        mock_detect,
        mock_slug,
        mock_count,
        tmp_path,
    ):
        project = _make_project()
        project.repo_path = str(tmp_path)
        project.default_branch = "main"
        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {project.id: []}
        orch._merged_branches = set()

        provider = MagicMock()
        provider.find_pr_for_branch.return_value = ReviewRequest(
            id="205",
            title="TASK-1",
            url="https://github.com/org/repo/pull/205",
            author="alice",
            state="closed",
            source_branch="TASK-1",
            target_branch="main",
            created_at="2026-01-01",
            updated_at="2026-01-02",
        )
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"
        mock_count.return_value = (2, ["abc123 fix one", "def456 fix two"], "")

        mock_tracker = MagicMock()
        mock_tracker.fetch_issues_by_states.return_value = [
            _make_issue("TASK-1", state="In Review"),
        ]
        orch._project_trackers[project.id] = mock_tracker

        orch._reconcile_stale_in_review_tasks()

        provider.find_pr_for_branch.assert_called_once_with("org/repo", "TASK-1")
        mock_count.assert_called_once_with(str(tmp_path), "main", "TASK-1")
        mock_tracker.update_issue.assert_called_once_with("TASK-1", status="Open")
        comment = mock_tracker.add_comment.call_args.args[1]
        assert "review #205 was closed without merge" in comment
        assert "Unmerged commits: 2 commits" in comment

    @patch("oompah.close_gate._count_commits_ahead")
    @patch("oompah.orchestrator.extract_repo_slug")
    @patch("oompah.orchestrator.detect_provider")
    def test_marks_missing_review_merged_when_branch_has_no_commits_ahead(
        self,
        mock_detect,
        mock_slug,
        mock_count,
        tmp_path,
    ):
        project = _make_project()
        project.repo_path = str(tmp_path)
        project.default_branch = "main"
        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {project.id: []}
        orch._merged_branches = set()

        provider = MagicMock()
        provider.find_pr_for_branch.return_value = None
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"
        mock_count.return_value = (0, [], "")

        mock_tracker = MagicMock()
        mock_tracker.fetch_issues_by_states.return_value = [
            _make_issue("TASK-1", state="In Review"),
        ]
        orch._project_trackers[project.id] = mock_tracker

        orch._reconcile_stale_in_review_tasks()

        mock_tracker.update_issue.assert_called_once_with("TASK-1", status="Merged")
        mock_tracker.add_comment.assert_not_called()

    @patch("oompah.orchestrator.extract_repo_slug")
    @patch("oompah.orchestrator.detect_provider")
    def test_provider_open_review_prevents_reopen_when_cache_is_stale(
        self,
        mock_detect,
        mock_slug,
        tmp_path,
    ):
        project = _make_project()
        project.repo_path = str(tmp_path)
        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {project.id: []}
        orch._merged_branches = set()

        provider = MagicMock()
        provider.find_pr_for_branch.return_value = ReviewRequest(
            id="10",
            title="TASK-1",
            url="https://github.com/org/repo/pull/10",
            author="alice",
            state="open",
            source_branch="TASK-1",
            target_branch="main",
            created_at="2026-01-01",
            updated_at="2026-01-02",
        )
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        mock_tracker = MagicMock()
        mock_tracker.fetch_issues_by_states.return_value = [
            _make_issue("TASK-1", state="In Review"),
        ]
        orch._project_trackers[project.id] = mock_tracker

        orch._reconcile_stale_in_review_tasks()

        mock_tracker.update_issue.assert_not_called()
        mock_tracker.add_comment.assert_not_called()


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

    def test_skips_epic_rollup_in_progress(self, tmp_path):
        """An epic can be In Progress from child rollup without an attached agent."""
        project = _make_project()
        orch = self._make_orchestrator(tmp_path, projects=[project])
        mock_tracker = MagicMock()
        orch._project_trackers[project.id] = mock_tracker

        issue = _make_issue("epic-1", state="In Progress", issue_type="epic")
        issue.project_id = project.id
        child = _make_issue("child-1", state="Open", parent_id=issue.identifier)
        with patch.object(orch, "_fetch_epic_children", return_value=[child]):
            orch._reset_orphaned_in_progress([issue])

        mock_tracker.update_issue.assert_not_called()
        assert issue.id not in orch._orphan_reset_counts

    def test_resets_orphaned_epic_review_repair_to_needs_ci_fix(self, tmp_path):
        project = _make_project(epic_strategy="shared")
        orch = self._make_orchestrator(tmp_path, projects=[project])
        mock_tracker = MagicMock()
        orch._project_trackers[project.id] = mock_tracker

        issue = _make_issue(
            "TRICKLE-1",
            state="In Progress",
            labels=["ci-fix"],
            issue_type="epic",
        )
        issue.project_id = project.id
        issue.work_branch = "epic-TRICKLE-1"
        children = [
            _make_issue("TRICKLE-2", state=IN_REVIEW, parent_id=issue.identifier),
            _make_issue("TRICKLE-3", state=MERGED, parent_id=issue.identifier),
        ]

        with patch.object(orch, "_fetch_epic_children", return_value=children):
            orch._reset_orphaned_in_progress([issue])

        mock_tracker.update_issue.assert_called_once_with(
            "TRICKLE-1",
            status=NEEDS_CI_FIX,
            priority="0",
        )

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

    def test_preserves_completed_marker_orphaned_in_progress_as_done(self, tmp_path):
        project = _make_project()
        orch = self._make_orchestrator(tmp_path, projects=[project])
        mock_tracker = MagicMock()
        orch._project_trackers[project.id] = mock_tracker

        issue = _make_issue("feat-1", state="In Progress")
        issue.project_id = project.id
        orch.state.completed.add(issue.id)

        orch._reset_orphaned_in_progress([issue])

        mock_tracker.update_issue.assert_called_once_with("feat-1", status=DONE)
        assert issue.id in orch.state.completed

    def test_completed_branch_ahead_orphan_is_marked_done_not_open(self, tmp_path):
        project = _make_project()
        orch = self._make_orchestrator(tmp_path, projects=[project])
        mock_tracker = MagicMock()
        orch._project_trackers[project.id] = mock_tracker

        issue = _make_issue("feat-1", state="In Progress")
        issue.project_id = project.id
        orch.state.completed.add(issue.id)
        orch._done_issue_has_unmerged_review_work = MagicMock(return_value=True)

        orch._reset_orphaned_in_progress([issue])

        mock_tracker.update_issue.assert_called_once_with("feat-1", status=DONE)
        assert issue.id in orch.state.completed

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
    """Tests for tracker status spelling used by the task lifecycle."""

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

    def test_reconcile_preserves_running_epic_repair_read_as_review(self, tmp_path):
        orch = self._make_orchestrator(tmp_path)
        issue = _make_issue(
            "TRICKLE-1",
            state=IN_PROGRESS,
            labels=["ci-fix"],
            issue_type="epic",
            project_id="proj-trickle",
        )
        fresh = _make_issue(
            "TRICKLE-1",
            state=IN_REVIEW,
            labels=["ci-fix"],
            issue_type="epic",
            project_id="proj-trickle",
        )
        child = _make_issue(
            "TRICKLE-2",
            state=IN_REVIEW,
            parent_id=issue.identifier,
            project_id="proj-trickle",
        )
        tracker = MagicMock()
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
        orch._fetch_epic_children = MagicMock(return_value=[child])
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch._terminate_running = AsyncMock()

        asyncio.run(orch._reconcile())

        orch._terminate_running.assert_not_called()
        tracker.update_issue.assert_called_once_with("TRICKLE-1", status=IN_PROGRESS)
        assert orch.state.running[issue.id].issue.state == IN_PROGRESS


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
        """A task with no description body must not be dispatched.
        Title-only tasks are placeholders (e.g. ad-hoc CLI tests) and
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
    """Tests for _yolo_retry_ci epic review repair routing."""

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

    def test_mature_epic_with_children_marks_epic_for_ci_fix(self, tmp_path):
        """PR matched against a mature epic → the epic itself is repaired."""
        project = _make_project()
        project.yolo = True
        orch = self._make_orchestrator(tmp_path, projects=[project])

        epic = Issue(
            id="trickle-rl5",
            identifier="trickle-rl5",
            title="CI-Speed plan",
            description="Make CI faster",
            state=IN_REVIEW,
            issue_type="epic",
            labels=[],
            branch_name="epic-trickle-rl5",
        )
        children = [
            _make_issue("trickle-c1", state=IN_REVIEW),
            _make_issue("trickle-c2", state=MERGED),
            _make_issue("trickle-c3", state=DONE),
        ]
        tracker = self._attach_tracker(orch, project, epic, children=children)

        review = _make_review("23", source_branch="epic-trickle-rl5", ci_status="failed")

        orch._yolo_retry_ci(project, review)

        tracker.create_issue.assert_not_called()
        tracker.update_issue.assert_called_once_with(
            "trickle-rl5",
            status=NEEDS_CI_FIX,
            priority="0",
            **{"add-label": "ci-fix"},
        )
        tracker.add_comment.assert_called_once()
        tracker.set_metadata_field.assert_any_call(
            "trickle-rl5", "oompah.work_branch", "epic-trickle-rl5"
        )

    def test_immature_epic_with_children_creates_ci_fix_helper(self, tmp_path):
        """A parent with unfinished children still uses the helper fallback."""
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
        children = [_make_issue(f"trickle-c{i}", state="open") for i in range(2)]
        tracker = self._attach_tracker(orch, project, epic, children=children)

        review = _make_review("23", source_branch="trickle-rl5", ci_status="failed")

        orch._yolo_retry_ci(project, review)

        tracker.update_issue.assert_not_called()
        tracker.add_comment.assert_not_called()
        tracker.create_issue.assert_called_once()
        kwargs = tracker.create_issue.call_args.kwargs
        assert kwargs["issue_type"] == "task"
        assert kwargs["priority"] == 0
        assert kwargs["parent"] == "trickle-rl5"
        assert kwargs["initial_status"] == NEEDS_CI_FIX
        assert kwargs["labels"] == ["ci-fix"]

    def test_existing_in_progress_ci_fix_sibling_title_is_idempotent(
        self, tmp_path
    ):
        """An already-claimed sibling may have lost Needs CI Fix status.

        Sibling CI-fix tasks are claimed by agents and move to In Progress.
        Older siblings did not carry the ci-fix label, so the PR/branch title
        is also an idempotency signal. Without this, each YOLO pass filed
        another sibling for the same failed PR.
        """
        project = _make_project()
        project.yolo = True
        orch = self._make_orchestrator(tmp_path, projects=[project])

        epic = Issue(
            id="example-org/oompah#272",
            identifier="example-org/oompah#272",
            title="Epic",
            description="Epic body",
            state="In Review",
            issue_type="epic",
            labels=[],
            branch_name="epic-example-org_oompah_272",
        )
        sibling = _make_issue(
            "example-org/oompah#292",
            state="In Progress",
            labels=[],
            parent_id=epic.identifier,
        )
        sibling.title = "CI fix: PR #291 on branch epic-example-org_oompah_272"
        children = [sibling, _make_issue("example-org/oompah#276", state="Done")]
        tracker = self._attach_tracker(orch, project, epic, children=children)

        review = _make_review(
            "291",
            source_branch="epic-example-org_oompah_272",
            ci_status="failed",
        )

        orch._yolo_retry_ci(project, review)

        tracker.create_issue.assert_not_called()
        tracker.update_issue.assert_not_called()
        tracker.add_comment.assert_not_called()

    def test_non_epic_task_keeps_relabel_behavior(self, tmp_path):
        """PR matched against a non-epic task → existing behavior preserved
        (relabel + reopen, no sibling created)."""
        project = _make_project()
        project.yolo = True
        orch = self._make_orchestrator(tmp_path, projects=[project])

        task = Issue(
            id="proj-task1",
            identifier="proj-task1",
            title="Task",
            description="A task with a body so the dispatcher accepts it.",
            state="closed",  # closed so we exercise the reopen path
            issue_type="task",
            labels=[],
            branch_name="feat-task1",
        )
        tracker = self._attach_tracker(orch, project, task, children=[])

        review = _make_review("42", source_branch="feat-task1", ci_status="failed")

        orch._yolo_retry_ci(project, review)

        # Existing relabel path fires: status=Needs CI Fix, priority=0, label=ci-fix
        tracker.update_issue.assert_called_once()
        update_kwargs = tracker.update_issue.call_args.kwargs
        assert update_kwargs.get("status") == "Needs CI Fix"
        assert update_kwargs.get("priority") == "0"
        assert update_kwargs.get("add-label") == "ci-fix"
        # Comment is added to the existing task
        tracker.add_comment.assert_called_once()
        # NO sibling task is created
        tracker.create_issue.assert_not_called()

    def test_childless_epic_keeps_relabel_behavior(self, tmp_path):
        """PR matched against a childless epic → existing behavior preserved
        (relabel — epic-planner can pick it up). No sibling task."""
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
        # NO sibling task is created
        tracker.create_issue.assert_not_called()

    def test_already_labeled_mature_epic_with_children_is_moved_to_needs_ci_fix(
        self, tmp_path
    ):
        """Legacy ci-fix residue on an epic should not strand the failed PR."""
        project = _make_project()
        project.yolo = True
        orch = self._make_orchestrator(tmp_path, projects=[project])

        epic = Issue(
            id="trickle-rl5",
            identifier="trickle-rl5",
            title="CI-Speed plan",
            description="Make CI faster",
            state=IN_PROGRESS,
            issue_type="epic",
            labels=["ci-fix"],  # already labeled — pre-existing bug residue
            branch_name="epic-trickle-rl5",
        )
        children = [_make_issue("trickle-c1", state=IN_REVIEW)]
        tracker = self._attach_tracker(orch, project, epic, children=children)

        review = _make_review("23", source_branch="epic-trickle-rl5", ci_status="failed")

        orch._yolo_retry_ci(project, review)

        tracker.add_comment.assert_not_called()
        tracker.create_issue.assert_not_called()
        tracker.update_issue.assert_called_once_with(
            "trickle-rl5",
            status=NEEDS_CI_FIX,
            priority="0",
            **{"add-label": "ci-fix"},
        )


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
        """When YOLO merges a PR whose task carries merge-conflict, the label
        is removed so the task doesn't stay stale."""
        project = _make_project()
        project.yolo = True
        provider = MagicMock()
        provider.merge_review.return_value = (True, "merged")
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = self._make_orchestrator(tmp_path, projects=[project])

        mock_tracker = MagicMock()
        # Task with merge-conflict label
        mock_task = MagicMock()
        mock_task.labels = ["bug", "merge-conflict"]
        mock_task.id = "task-001"
        mock_task.identifier = "oompah-zlz_2-001"
        mock_tracker.fetch_issue_detail.return_value = mock_task
        orch._project_trackers[project.id] = mock_tracker

        reviews = [
            _make_review("1", source_branch="task-001", ci_status="passed"),
        ]
        orch._reviews_cache = {project.id: reviews}

        orch._yolo_review_actions_sync()

        # merge_review called (PR merged)
        provider.merge_review.assert_called_once_with("org/repo", "1")
        # merge-conflict label removed from the matching task
        assert any(
            call.kwargs.get("remove-label") == "merge-conflict"
            for call in mock_tracker.update_issue.call_args_list
        )

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_successful_enqueue_clears_merge_conflict_label(
        self, mock_slug, mock_detect, tmp_path,
    ):
        """When YOLO enqueues a PR (merge queue mode) whose task carries
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
        mock_task = MagicMock()
        mock_task.labels = ["merge-conflict", "tech-debt"]
        mock_task.id = "task-002"
        mock_task.identifier = "oompah-zlz_2-002"
        mock_tracker.fetch_issue_detail.return_value = mock_task
        orch._project_trackers[project.id] = mock_tracker

        reviews = [
            _make_review("2", source_branch="task-002", ci_status="passed"),
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
        mock_task = MagicMock()
        mock_task.labels = ["merge-conflict"]  # stale label
        mock_task.id = "task-003"
        mock_task.identifier = "oompah-zlz_2-003"
        mock_tracker.fetch_issue_detail.return_value = mock_task
        orch._project_trackers[project.id] = mock_tracker

        # CI is still running; has_conflicts=False (externally rebased)
        reviews = [
            _make_review("3", source_branch="task-003",
                         ci_status="running", has_conflicts=False),
        ]
        orch._reviews_cache = {project.id: reviews}

        orch._yolo_review_actions_sync()

        # No merge/enqueue attempted (CI still running)
        provider.merge_review.assert_not_called()
        provider.enable_auto_merge.assert_not_called()
        # But the stale merge-conflict label on the matching task was cleared
        tracker_call_kwargs = mock_tracker.update_issue.call_args
        assert tracker_call_kwargs is not None
        assert tracker_call_kwargs[1].get("remove-label") == "merge-conflict"

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_noop_when_task_has_no_merge_conflict_label(
        self, mock_slug, mock_detect, tmp_path,
    ):
        """When a merged PR matches a task that does NOT have merge-conflict
        label, no tracker update is issued (reduces API chatter)."""
        project = _make_project()
        project.yolo = True
        provider = MagicMock()
        provider.merge_review.return_value = (True, "merged")
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = self._make_orchestrator(tmp_path, projects=[project])

        mock_tracker = MagicMock()
        mock_task = MagicMock()
        mock_task.labels = ["bug"]  # no merge-conflict
        mock_task.id = "task-004"
        mock_task.identifier = "oompah-zlz_2-004"
        mock_tracker.fetch_issue_detail.return_value = mock_task
        orch._project_trackers[project.id] = mock_tracker

        reviews = [
            _make_review("4", source_branch="task-004", ci_status="passed"),
        ]
        orch._reviews_cache = {project.id: reviews}

        orch._yolo_review_actions_sync()

        provider.merge_review.assert_called()
        assert not any(
            call.kwargs.get("remove-label") == "merge-conflict"
            for call in mock_tracker.update_issue.call_args_list
        )

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_noop_when_no_matching_task(
        self, mock_slug, mock_detect, tmp_path,
    ):
        """When a PR is merged and has no matching task (orphan branch), the
        clear-label step is a silent no-op and does not crash."""
        project = _make_project()
        project.yolo = True
        provider = MagicMock()
        provider.merge_review.return_value = (True, "merged")
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = self._make_orchestrator(tmp_path, projects=[project])

        mock_tracker = MagicMock()
        mock_tracker.fetch_issue_detail.return_value = None  # no matching task
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
    """Tests that open reviews no longer serialize agent dispatch."""

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

    def test_dispatch_allowed_when_project_has_open_review(self, tmp_path):
        """An issue in a project with an open review can still be dispatched."""
        orch = self._make_orchestrator(tmp_path)
        issue = self._make_project_issue("feat-2", state="open", priority=2)
        # Project already has an open non-draft review
        orch._reviews_cache = {"proj-1": [_make_review("10")]}

        assert orch._should_dispatch(issue) is True

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

    def test_p0_issue_dispatches_with_open_review(self, tmp_path):
        """P0 issues dispatch when a project has an open review."""
        orch = self._make_orchestrator(tmp_path)
        issue = self._make_project_issue("feat-crit", state="open", priority=0)
        # Project has an open review, but dispatch is no longer capped by it.
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
        """Issues without a project_id are never at review capacity."""
        orch = self._make_orchestrator(tmp_path)
        orch._reviews_cache = {"proj-1": [_make_review("1", "feat-1", ci_status="passed")]}
        assert orch._project_has_open_review(None) is False

    def test_no_reviews_cache_returns_false(self, tmp_path):
        """If the reviews cache is absent, capacity is not full."""
        orch = self._make_orchestrator(tmp_path)
        # _reviews_cache not set — should fall back gracefully
        assert orch._project_has_open_review("proj-1") is False

    def test_empty_project_reviews_returns_false(self, tmp_path):
        """A project with no open reviews is below capacity."""
        orch = self._make_orchestrator(tmp_path)
        orch._reviews_cache = {"proj-1": []}
        assert orch._project_has_open_review("proj-1") is False

    def test_unknown_project_returns_false(self, tmp_path):
        """A project not in the reviews cache is below capacity."""
        orch = self._make_orchestrator(tmp_path)
        orch._reviews_cache = {"proj-2": [_make_review("1", "feat-1", ci_status="passed")]}
        assert orch._project_has_open_review("proj-1") is False

    def test_one_open_review_returns_true(self, tmp_path):
        """A project with one open non-draft review is at the default cap."""
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
    """Tests that open reviews no longer gate new work dispatch."""

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

    def test_open_review_allows_dispatch(self, tmp_path):
        """When a project has an open PR, new issues still dispatch."""
        orch = self._make_orchestrator(tmp_path)
        issue = self._make_project_issue("feat-2", project_id="proj-1", state="open")
        orch._reviews_cache = {
            "proj-1": [_make_review("1", "feat-1", ci_status="passed")]
        }
        assert orch._should_dispatch(issue) is True

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

    def test_p0_issue_dispatches_with_open_review(self, tmp_path):
        """P0 issues dispatch when a project has an open review."""
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


class TestResetOrphanedInProgressSweep:
    """_reset_orphaned_in_progress also sweeps In Progress tasks (TASK-409).

    In Progress tasks are never in the candidates list (only Open/active tasks
    are candidates).  The fix adds a separate fetch of In Progress tasks so
    orphans left behind after retry-claim release are still reset.
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

    def test_resets_in_progress_issue_not_in_candidates(self, tmp_path):
        """An In Progress task with no agent is reset even when not in candidates."""
        project = _make_project()
        orch = self._make_orchestrator(tmp_path, projects=[project])
        mock_tracker = MagicMock()
        orch._project_trackers[project.id] = mock_tracker

        # Issue is In Progress but was NOT passed in candidates (typical post-retry-release)
        ip_issue = _make_issue("feat-orphan", state="In Progress")
        ip_issue.project_id = project.id

        # Stub _fetch_all_in_progress_issues to return the orphaned issue
        orch._fetch_all_in_progress_issues = MagicMock(return_value=[ip_issue])

        # candidates are empty (In Progress tasks never appear here)
        orch._reset_orphaned_in_progress([])

        mock_tracker.update_issue.assert_called_once_with("feat-orphan", status="Open")

    def test_preserves_completed_in_progress_issue_as_done(self, tmp_path):
        """A completed task must not be reopened by the orphan sweep."""
        project = _make_project()
        orch = self._make_orchestrator(tmp_path, projects=[project])
        mock_tracker = MagicMock()
        orch._project_trackers[project.id] = mock_tracker

        ip_issue = _make_issue("feat-done", state="In Progress")
        ip_issue.project_id = project.id
        orch.state.completed.add(ip_issue.id)
        orch._fetch_all_in_progress_issues = MagicMock(return_value=[ip_issue])
        orch._done_issue_has_unmerged_review_work = MagicMock(return_value=False)

        orch._reset_orphaned_in_progress([])

        mock_tracker.update_issue.assert_called_once_with("feat-done", status=DONE)
        orch._done_issue_has_unmerged_review_work.assert_not_called()
        assert ip_issue.id in orch.state.completed
        assert ip_issue.id not in orch._orphan_reset_counts

    def test_skips_in_progress_issue_with_running_agent(self, tmp_path):
        """A running agent protects an In Progress task from orphan reset."""
        project = _make_project()
        orch = self._make_orchestrator(tmp_path, projects=[project])
        mock_tracker = MagicMock()
        orch._project_trackers[project.id] = mock_tracker

        ip_issue = _make_issue("feat-active", state="In Progress")
        ip_issue.project_id = project.id
        orch.state.running["feat-active"] = MagicMock()
        orch._fetch_all_in_progress_issues = MagicMock(return_value=[ip_issue])

        orch._reset_orphaned_in_progress([])

        mock_tracker.update_issue.assert_not_called()

    def test_skips_in_progress_issue_with_pending_retry(self, tmp_path):
        """A pending retry protects an In Progress task from orphan reset."""
        project = _make_project()
        orch = self._make_orchestrator(tmp_path, projects=[project])
        mock_tracker = MagicMock()
        orch._project_trackers[project.id] = mock_tracker

        ip_issue = _make_issue("feat-retrying", state="In Progress")
        ip_issue.project_id = project.id
        orch.state.retry_attempts["feat-retrying"] = MagicMock()
        orch._fetch_all_in_progress_issues = MagicMock(return_value=[ip_issue])

        orch._reset_orphaned_in_progress([])

        mock_tracker.update_issue.assert_not_called()

    def test_deduplicates_issue_appearing_in_both_candidates_and_in_progress(self, tmp_path):
        """An issue in both candidates and the In Progress sweep is only reset once."""
        project = _make_project()
        orch = self._make_orchestrator(tmp_path, projects=[project])
        mock_tracker = MagicMock()
        orch._project_trackers[project.id] = mock_tracker

        # Edge case: same issue appears in both lists (e.g. custom active_states)
        ip_issue = _make_issue("feat-dup", state="In Progress")
        ip_issue.project_id = project.id
        orch._fetch_all_in_progress_issues = MagicMock(return_value=[ip_issue])

        orch._reset_orphaned_in_progress([ip_issue])

        # Should only update once
        assert mock_tracker.update_issue.call_count == 1

    def test_fetch_in_progress_error_does_not_abort_candidates(self, tmp_path):
        """If fetching In Progress issues fails, candidate sweep still runs."""
        project = _make_project()
        orch = self._make_orchestrator(tmp_path, projects=[project])
        mock_tracker = MagicMock()
        orch._project_trackers[project.id] = mock_tracker

        # Orphaned Open issue in candidates (simulates old-style scenario)
        open_issue = _make_issue("feat-open-orphan", state="In Progress")
        open_issue.project_id = project.id
        # In-progress fetch raises an exception
        orch._fetch_all_in_progress_issues = MagicMock(side_effect=RuntimeError("boom"))

        # Pass the orphan as a candidate directly
        orch._reset_orphaned_in_progress([open_issue])

        # Candidate sweep still ran
        mock_tracker.update_issue.assert_called_once_with("feat-open-orphan", status="Open")


class TestFetchIssueAcrossTrackers:
    """Tests for _fetch_issue_across_trackers."""

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

    def test_returns_none_when_not_found_anywhere(self, tmp_path):
        project = _make_project()
        orch = self._make_orchestrator(tmp_path, projects=[project])
        mock_tracker = MagicMock()
        mock_tracker.fetch_issue_detail.return_value = None
        orch._project_trackers[project.id] = mock_tracker
        orch.tracker = MagicMock()
        orch.tracker.fetch_issue_detail.return_value = None

        result = orch._fetch_issue_across_trackers("TASK-999")

        assert result is None

    def test_finds_issue_in_project_tracker(self, tmp_path):
        project = _make_project()
        orch = self._make_orchestrator(tmp_path, projects=[project])
        issue = _make_issue("TASK-42", state="In Progress")
        mock_tracker = MagicMock()
        mock_tracker.fetch_issue_detail.return_value = issue
        orch._project_trackers[project.id] = mock_tracker

        result = orch._fetch_issue_across_trackers("TASK-42")

        assert result is not None
        assert result.identifier == "TASK-42"
        assert result.project_id == project.id

    def test_falls_back_to_default_tracker_when_no_projects(self, tmp_path):
        orch = self._make_orchestrator(tmp_path, projects=[])
        issue = _make_issue("TASK-99", state="In Progress")
        orch.tracker = MagicMock()
        orch.tracker.fetch_issue_detail.return_value = issue

        result = orch._fetch_issue_across_trackers("TASK-99")

        assert result is not None
        assert result.identifier == "TASK-99"
        # No project_id set when found via legacy tracker
        assert result.project_id is None

    def test_skips_failed_project_tracker_and_continues(self, tmp_path):
        from oompah.tracker import TrackerError

        proj1 = _make_project("proj-1")
        proj2 = _make_project("proj-2")
        orch = self._make_orchestrator(tmp_path, projects=[proj1, proj2])

        bad_tracker = MagicMock()
        bad_tracker.fetch_issue_detail.side_effect = TrackerError("oops")
        good_tracker = MagicMock()
        issue = _make_issue("TASK-77", state="In Progress")
        good_tracker.fetch_issue_detail.return_value = issue
        orch._project_trackers["proj-1"] = bad_tracker
        orch._project_trackers["proj-2"] = good_tracker

        result = orch._fetch_issue_across_trackers("TASK-77")

        assert result is not None
        assert result.project_id == "proj-2"


class TestReconcileInReviewPrOutcomes:
    """Tests for _reconcile_in_review_pr_outcomes."""

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

    def _make_review(
        self,
        branch: str,
        ci_status: str = "",
        has_conflicts: bool = False,
        state: str = "open",
    ) -> ReviewRequest:
        return ReviewRequest(
            id="10",
            title=f"PR for {branch}",
            url="https://github.com/org/repo/pull/10",
            author="alice",
            state=state,
            source_branch=branch,
            target_branch="main",
            created_at="2026-01-01",
            updated_at="2026-01-01",
            ci_status=ci_status,
            has_conflicts=has_conflicts,
        )

    def test_marks_needs_ci_fix_when_pr_ci_failed(self, tmp_path):
        """In Review task with a failed-CI PR is marked Needs CI Fix."""
        project = _make_project()
        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {
            project.id: [self._make_review("TASK-1", ci_status="failed")]
        }

        mock_tracker = MagicMock()
        mock_tracker.fetch_issues_by_states.return_value = [
            _make_issue("TASK-1", state=IN_REVIEW),
        ]
        orch._project_trackers[project.id] = mock_tracker

        orch._reconcile_in_review_pr_outcomes()

        mock_tracker.update_issue.assert_called_once_with(
            "TASK-1", status=NEEDS_CI_FIX
        )

    def test_marks_needs_rebase_when_pr_has_conflicts(self, tmp_path):
        """In Review task with a conflicted PR is marked Needs Rebase."""
        project = _make_project()
        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {
            project.id: [
                self._make_review("TASK-1", has_conflicts=True, ci_status="passed")
            ]
        }

        mock_tracker = MagicMock()
        mock_tracker.fetch_issues_by_states.return_value = [
            _make_issue("TASK-1", state=IN_REVIEW),
        ]
        orch._project_trackers[project.id] = mock_tracker

        orch._reconcile_in_review_pr_outcomes()

        mock_tracker.update_issue.assert_called_once_with(
            "TASK-1", status=NEEDS_REBASE
        )

    def test_ci_failure_takes_priority_over_conflicts(self, tmp_path):
        """When CI fails AND conflicts exist, Needs CI Fix takes priority."""
        project = _make_project()
        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {
            project.id: [
                self._make_review(
                    "TASK-1", ci_status="failed", has_conflicts=True
                )
            ]
        }

        mock_tracker = MagicMock()
        mock_tracker.fetch_issues_by_states.return_value = [
            _make_issue("TASK-1", state=IN_REVIEW),
        ]
        orch._project_trackers[project.id] = mock_tracker

        orch._reconcile_in_review_pr_outcomes()

        mock_tracker.update_issue.assert_called_once_with(
            "TASK-1", status=NEEDS_CI_FIX
        )

    def test_skips_in_review_task_with_healthy_open_pr(self, tmp_path):
        """In Review task with a passing-CI, no-conflict PR is left alone."""
        project = _make_project()
        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {
            project.id: [
                self._make_review("TASK-1", ci_status="passed", has_conflicts=False)
            ]
        }

        mock_tracker = MagicMock()
        mock_tracker.fetch_issues_by_states.return_value = [
            _make_issue("TASK-1", state=IN_REVIEW),
        ]
        orch._project_trackers[project.id] = mock_tracker

        orch._reconcile_in_review_pr_outcomes()

        mock_tracker.update_issue.assert_not_called()

    def test_skips_task_with_no_matching_pr_in_cache(self, tmp_path):
        """In Review task whose branch is not in the cache is left alone."""
        project = _make_project()
        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {
            project.id: [
                self._make_review("OTHER-BRANCH", ci_status="failed")
            ]
        }

        mock_tracker = MagicMock()
        mock_tracker.fetch_issues_by_states.return_value = [
            _make_issue("TASK-1", state=IN_REVIEW),
        ]
        orch._project_trackers[project.id] = mock_tracker

        orch._reconcile_in_review_pr_outcomes()

        mock_tracker.update_issue.assert_not_called()

    def test_handles_empty_reviews_cache(self, tmp_path):
        """Empty reviews cache is a no-op."""
        project = _make_project()
        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {}

        mock_tracker = MagicMock()
        mock_tracker.fetch_issues_by_states.return_value = [
            _make_issue("TASK-1", state=IN_REVIEW),
        ]
        orch._project_trackers[project.id] = mock_tracker

        orch._reconcile_in_review_pr_outcomes()

        mock_tracker.fetch_issues_by_states.assert_not_called()
        mock_tracker.update_issue.assert_not_called()

    def test_uses_branch_name_field_over_identifier(self, tmp_path):
        """When branch_name is set, it is used to match against the PR."""
        project = _make_project()
        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {
            project.id: [
                self._make_review(
                    "my-feature-branch", ci_status="failed"
                )
            ]
        }

        mock_tracker = MagicMock()
        mock_tracker.fetch_issues_by_states.return_value = [
            _make_issue(
                "TASK-5",
                state=IN_REVIEW,
                branch_name="my-feature-branch",
            ),
        ]
        orch._project_trackers[project.id] = mock_tracker

        orch._reconcile_in_review_pr_outcomes()

        mock_tracker.update_issue.assert_called_once_with(
            "TASK-5", status=NEEDS_CI_FIX
        )

    def test_tracker_error_does_not_crash(self, tmp_path):
        """TrackerError during issue fetch is silently swallowed."""
        from oompah.tracker import TrackerError

        project = _make_project()
        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {
            project.id: [self._make_review("TASK-1", ci_status="failed")]
        }

        mock_tracker = MagicMock()
        mock_tracker.fetch_issues_by_states.side_effect = TrackerError("boom")
        orch._project_trackers[project.id] = mock_tracker

        # Should not raise
        orch._reconcile_in_review_pr_outcomes()
        mock_tracker.update_issue.assert_not_called()

    def test_update_error_does_not_crash(self, tmp_path):
        """TrackerError during status update is silently swallowed."""
        from oompah.tracker import TrackerError

        project = _make_project()
        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {
            project.id: [self._make_review("TASK-1", ci_status="failed")]
        }

        mock_tracker = MagicMock()
        mock_tracker.fetch_issues_by_states.return_value = [
            _make_issue("TASK-1", state=IN_REVIEW),
        ]
        mock_tracker.update_issue.side_effect = TrackerError("write fail")
        orch._project_trackers[project.id] = mock_tracker

        # Should not raise
        orch._reconcile_in_review_pr_outcomes()
        mock_tracker.update_issue.assert_called_once()

    def test_pending_ci_does_not_change_state(self, tmp_path):
        """In Review task with pending CI (not yet passed or failed) is left alone."""
        project = _make_project()
        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {
            project.id: [
                self._make_review("TASK-1", ci_status="pending")
            ]
        }

        mock_tracker = MagicMock()
        mock_tracker.fetch_issues_by_states.return_value = [
            _make_issue("TASK-1", state=IN_REVIEW),
        ]
        orch._project_trackers[project.id] = mock_tracker

        orch._reconcile_in_review_pr_outcomes()

        mock_tracker.update_issue.assert_not_called()
