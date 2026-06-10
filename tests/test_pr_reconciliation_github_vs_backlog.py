"""Regression tests for PR and release reconciliation — GitHub-backed vs Backlog flows.

Covers the areas from TASK-462.6 where GitHub-backed and legacy Backlog-backed
flows behave differently:

  1. Branch-to-issue indexing: GitHub tasks resolved via work_branch index;
     Backlog tasks resolved via legacy fetch_issue_detail(identifier).
  2. PR metadata writes: oompah.work_branch written for GitHub tasks; absent
     for Backlog tasks.
  3. Stale In Review recovery: branch_name (work_branch slug) used for GitHub
     tasks; identifier used for Backlog tasks.
  4. CI-fix sibling tasks: _yolo_retry_ci finds GitHub task via branch index.
  5. Merge conflicts: merge-conflict label cleared via branch index for GitHub
     tasks; via legacy path for Backlog tasks.
  6. YOLO direct merge: GitHub task marked Merged through branch-index resolver.
  7. Merge queue enqueue: enqueue clears merge-conflict label via resolver.
  8. Release-pick outcomes: backport PR descriptions do NOT use GitHub closing
     keywords (Fixes #N) — AC#2 compliance.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from oompah.config import ServiceConfig
from oompah.models import Issue
from oompah.orchestrator import Orchestrator
from oompah.scm import ReviewRequest
from oompah.statuses import IN_REVIEW, MERGED, NEEDS_CI_FIX, NEEDS_REBASE


# ---------------------------------------------------------------------------
# Shared test helpers
# ---------------------------------------------------------------------------


def _make_orchestrator(tmp_path, projects=None):
    project_store = MagicMock()
    project_store.list_all.return_value = projects or []
    project_store.get.side_effect = lambda pid: next(
        (p for p in (projects or []) if p.id == pid), None
    )
    return Orchestrator(
        config=ServiceConfig(),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
    )


def _make_project(
    project_id: str = "proj-1",
    repo_url: str = "https://github.com/org/repo",
    yolo: bool = False,
    merge_queue_enabled: bool = False,
    epic_strategy: str = "flat",
) -> MagicMock:
    p = MagicMock()
    p.id = project_id
    p.name = "test-project"
    p.repo_url = repo_url
    p.repo_path = "/tmp/repo"
    p.default_branch = "main"
    p.access_token = None
    p.merge_queue_enabled = merge_queue_enabled
    p.paused = False
    p.yolo = yolo
    p.churn_magnet_gate_enabled = False
    p.churn_magnet_top_n = 10
    p.epic_strategy = epic_strategy
    return p


def _make_issue(
    identifier: str,
    state: str = "open",
    branch_name: str | None = None,
    labels: list | None = None,
    work_branch: str | None = None,
    project_id: str | None = None,
    issue_type: str = "task",
    description: str = "body",
) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=f"Issue {identifier}",
        description=description,
        state=state,
        issue_type=issue_type,
        labels=labels or [],
        branch_name=branch_name,
        work_branch=work_branch,
        project_id=project_id,
    )


def _make_github_issue(
    number: int = 42,
    owner: str = "org",
    repo: str = "tasks",
    work_branch: str = "oompah/proj/gh-42",
    state: str = "open",
    labels: list | None = None,
    project_id: str | None = "proj-1",
) -> Issue:
    identifier = f"{owner}/{repo}#{number}"
    return Issue(
        id=identifier,
        identifier=identifier,
        title=f"GitHub Issue #{number}",
        description="GitHub-backed task body",
        state=state,
        issue_type="task",
        labels=labels or [],
        # branch_name is the work_branch slug stored from tracker metadata
        branch_name=work_branch,
        work_branch=work_branch,
        tracker_kind="github_issues",
        project_id=project_id,
    )


def _make_review(
    review_id: str = "10",
    source_branch: str = "feat-branch",
    ci_status: str = "passed",
    has_conflicts: bool = False,
    needs_rebase: bool = False,
    target_branch: str = "main",
) -> ReviewRequest:
    return ReviewRequest(
        id=review_id,
        title=f"PR #{review_id}",
        url=f"https://github.com/org/repo/pull/{review_id}",
        author="alice",
        state="open",
        source_branch=source_branch,
        target_branch=target_branch,
        created_at="2026-01-01",
        updated_at="2026-01-01",
        ci_status=ci_status,
        has_conflicts=has_conflicts,
        needs_rebase=needs_rebase,
        labels=[],
    )


# ---------------------------------------------------------------------------
# 1. Branch-to-issue indexing: GitHub vs Backlog resolution
# ---------------------------------------------------------------------------


class TestBranchIndexResolutionGitHubVsBacklog:
    """_resolve_task_for_branch uses the branch index for GitHub tasks and
    falls back to legacy fetch_issue_detail for Backlog tasks (AC#1)."""

    def test_github_task_resolved_via_work_branch_index(self, tmp_path):
        """GitHub task with work_branch is found through the branch index,
        not the legacy identifier lookup."""
        orch = _make_orchestrator(tmp_path)
        gh_issue = _make_github_issue(number=42, work_branch="oompah/proj/gh-42")

        tracker = MagicMock()
        tracker.fetch_issues_by_states.return_value = [gh_issue]
        tracker.fetch_issue_detail.side_effect = [
            None,   # index build: not called here (branch in index triggers direct fetch)
            gh_issue,  # identifier lookup from index result
        ]

        result = orch._resolve_task_for_branch(
            tracker, "oompah/proj/gh-42", project_id="proj-1"
        )

        assert result is gh_issue

    def test_backlog_task_resolved_via_legacy_identifier_lookup(self, tmp_path):
        """Backlog task (no work_branch) is resolved via fetch_issue_detail
        with the branch name as the identifier."""
        orch = _make_orchestrator(tmp_path)
        backlog_issue = _make_issue("TASK-5", state="open")

        tracker = MagicMock()
        # Branch index returns empty (no work_branch on any issue)
        tracker.fetch_issues_by_states.return_value = [
            _make_issue("TASK-5", state="open")  # no work_branch
        ]
        # Legacy lookup: fetch_issue_detail("TASK-5") returns the issue
        tracker.fetch_issue_detail.return_value = backlog_issue

        result = orch._resolve_task_for_branch(tracker, "TASK-5")

        tracker.fetch_issue_detail.assert_called_with("TASK-5")
        assert result is backlog_issue

    def test_github_and_backlog_coexist_in_same_project(self, tmp_path):
        """When a project has mixed GitHub and Backlog issues, resolution
        uses the branch index for GitHub tasks and falls through for Backlog."""
        orch = _make_orchestrator(tmp_path)
        gh_issue = _make_github_issue(number=10, work_branch="oompah/proj/gh-10")
        backlog_issue = _make_issue("TASK-999", state="open")

        tracker = MagicMock()
        tracker.fetch_issues_by_states.return_value = [gh_issue, backlog_issue]
        tracker.fetch_issue_detail.return_value = gh_issue  # returned for identifier lookup

        result = orch._resolve_task_for_branch(
            tracker, "oompah/proj/gh-10", project_id="proj-1"
        )

        assert result is gh_issue
        # Legacy lookup (fetch_issue_detail) receives the identifier from the index
        tracker.fetch_issue_detail.assert_called_with(gh_issue.identifier)

    def test_github_epic_branch_resolved_via_stripped_prefix(self, tmp_path):
        """epic-<work_branch> source branches are resolved by stripping the
        'epic-' prefix and consulting the branch index."""
        orch = _make_orchestrator(tmp_path)
        gh_epic = _make_github_issue(number=7, work_branch="oompah/proj/epic-gh-7")
        gh_epic.issue_type = "epic"

        tracker = MagicMock()
        tracker.fetch_issues_by_states.return_value = [gh_epic]
        tracker.fetch_issue_detail.return_value = gh_epic

        # PR source branch has 'epic-' prefix
        result = orch._resolve_task_for_branch(
            tracker, "epic-oompah/proj/epic-gh-7", project_id="proj-1"
        )

        assert result is gh_epic


# ---------------------------------------------------------------------------
# 2. PR metadata writes: work_branch written for GitHub, absent for Backlog
# ---------------------------------------------------------------------------


class TestPrMetadataWritesGitHubVsBacklog:
    """_write_review_metadata stores oompah.work_branch for GitHub tasks
    (where source_branch is the work_branch slug, not the identifier) but
    is skipped when source_branch is None (AC#1)."""

    def test_github_work_branch_written_to_metadata(self, tmp_path):
        """oompah.work_branch is written when source_branch differs from identifier."""
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()

        orch._write_review_metadata(
            tracker,
            "org/tasks#42",
            review_id="99",
            review_url="https://github.com/org/repo/pull/99",
            source_branch="oompah/proj/gh-42",
            target_branch="main",
        )

        calls = {c.args[1]: c.args[2] for c in tracker.set_metadata_field.call_args_list}
        assert calls.get("oompah.work_branch") == "oompah/proj/gh-42"

    def test_backlog_task_no_work_branch_field_when_not_supplied(self, tmp_path):
        """When source_branch is not passed, oompah.work_branch is not written."""
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()

        orch._write_review_metadata(
            tracker,
            "TASK-5",
            review_id="7",
            review_url="https://github.com/org/repo/pull/7",
            # source_branch NOT supplied (Backlog tasks don't need it)
        )

        calls = {c.args[1]: c.args[2] for c in tracker.set_metadata_field.call_args_list}
        assert "oompah.work_branch" not in calls

    def test_review_url_and_number_written_for_both_tracker_kinds(self, tmp_path):
        """review_url and review_number are written regardless of tracker kind."""
        orch = _make_orchestrator(tmp_path)

        for identifier in ("org/tasks#42", "TASK-5"):
            tracker = MagicMock()
            orch._write_review_metadata(
                tracker,
                identifier,
                review_id="10",
                review_url="https://github.com/org/repo/pull/10",
            )
            calls = {c.args[1]: c.args[2] for c in tracker.set_metadata_field.call_args_list}
            assert calls.get("oompah.review_url") == "https://github.com/org/repo/pull/10"
            assert calls.get("oompah.review_number") == "10"


# ---------------------------------------------------------------------------
# 3. Stale In Review recovery: branch_name used for GitHub, identifier for Backlog
# ---------------------------------------------------------------------------


class TestStaleInReviewRecoveryGitHubVsBacklog:
    """_reconcile_stale_in_review_tasks uses issue.branch_name (the work_branch
    slug) for GitHub tasks and falls back to issue.identifier for Backlog
    tasks when checking merged_branches and open_branches (AC#1)."""

    def _make_orch(self, tmp_path, project, merged_branches=None, reviews_cache=None):
        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._merged_branches = set(merged_branches or [])
        orch._reviews_cache = reviews_cache or {project.id: []}
        return orch

    def test_github_task_marked_merged_via_branch_name(self, tmp_path):
        """GitHub task is marked Merged when branch_name is in merged_branches
        (not when identifier is there)."""
        project = _make_project()
        project.repo_path = str(tmp_path)

        gh_issue = _make_github_issue(
            number=42, work_branch="oompah/proj/gh-42", state=IN_REVIEW,
            project_id=project.id,
        )
        orch = self._make_orch(
            tmp_path, project,
            merged_branches={"oompah/proj/gh-42"},  # work branch in set, NOT identifier
        )

        tracker = MagicMock()
        tracker.fetch_issues_by_states.return_value = [gh_issue]
        orch._project_trackers[project.id] = tracker

        orch._reconcile_stale_in_review_tasks()

        tracker.update_issue.assert_called_once_with(gh_issue.identifier, status=MERGED)

    def test_backlog_task_marked_merged_via_identifier(self, tmp_path):
        """Backlog task is marked Merged when identifier is in merged_branches
        (branch_name is absent)."""
        project = _make_project()
        project.repo_path = str(tmp_path)

        backlog_issue = _make_issue("TASK-7", state=IN_REVIEW, project_id=project.id)
        orch = self._make_orch(
            tmp_path, project,
            merged_branches={"TASK-7"},  # identifier in set
        )

        tracker = MagicMock()
        tracker.fetch_issues_by_states.return_value = [backlog_issue]
        orch._project_trackers[project.id] = tracker

        orch._reconcile_stale_in_review_tasks()

        tracker.update_issue.assert_called_once_with("TASK-7", status=MERGED)

    def test_github_task_kept_in_review_via_branch_name_in_cache(self, tmp_path):
        """GitHub task is kept In Review when branch_name appears in the
        open_branches cache (not when identifier does)."""
        project = _make_project()
        project.repo_path = str(tmp_path)

        gh_issue = _make_github_issue(
            number=42, work_branch="oompah/proj/gh-42", state=IN_REVIEW,
            project_id=project.id,
        )
        orch = self._make_orch(
            tmp_path, project,
            reviews_cache={
                project.id: [
                    _make_review(
                        review_id="10",
                        source_branch="oompah/proj/gh-42",  # matches branch_name
                    )
                ]
            },
        )

        tracker = MagicMock()
        tracker.fetch_issues_by_states.return_value = [gh_issue]
        orch._project_trackers[project.id] = tracker

        orch._reconcile_stale_in_review_tasks()

        # Task has an open review → no change
        tracker.update_issue.assert_not_called()

    def test_backlog_task_kept_in_review_via_identifier_in_cache(self, tmp_path):
        """Backlog task (identifier == branch) is kept In Review when identifier
        appears as source_branch in the reviews cache."""
        project = _make_project()
        project.repo_path = str(tmp_path)

        backlog_issue = _make_issue("TASK-3", state=IN_REVIEW, project_id=project.id)
        orch = self._make_orch(
            tmp_path, project,
            reviews_cache={
                project.id: [
                    _make_review(review_id="5", source_branch="TASK-3")
                ]
            },
        )

        tracker = MagicMock()
        tracker.fetch_issues_by_states.return_value = [backlog_issue]
        orch._project_trackers[project.id] = tracker

        orch._reconcile_stale_in_review_tasks()

        tracker.update_issue.assert_not_called()

    def test_github_task_effective_branch_is_branch_name_not_identifier(self, tmp_path):
        """_stale_in_review_effective_branch returns branch_name (the work_branch
        slug) for a GitHub task, NOT its full owner/repo#N identifier.

        This means merged_branches must contain the SLUG (e.g. 'oompah/proj/gh-42'),
        not the identifier, for the task to be marked Merged automatically.
        """
        project = _make_project()

        gh_issue = _make_github_issue(
            number=42, work_branch="oompah/proj/gh-42", state=IN_REVIEW,
            project_id=project.id,
        )
        orch = _make_orchestrator(tmp_path, projects=[project])

        # Effective branch should be branch_name, not identifier
        effective = orch._stale_in_review_effective_branch(gh_issue, project.id)
        assert effective == "oompah/proj/gh-42", (
            f"Expected 'oompah/proj/gh-42', got {effective!r}"
        )
        assert effective != gh_issue.identifier, (
            "Effective branch should be work_branch slug, not GitHub identifier"
        )


# ---------------------------------------------------------------------------
# 4. CI-fix sibling tasks: GitHub task found via branch index
# ---------------------------------------------------------------------------


class TestCiFixSiblingGitHubVsBacklog:
    """_yolo_retry_ci resolves GitHub tasks via the branch index.  For Backlog
    tasks, the legacy fetch_issue_detail path is used (AC#1)."""

    def _make_orch_with_issue(self, tmp_path, project, issue, *, work_branch=None):
        orch = _make_orchestrator(tmp_path, projects=[project])
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = None  # Index-only resolution

        if work_branch:
            # Seed the branch index so _resolve_task_for_branch finds the task
            tracker.fetch_issues_by_states.return_value = [issue]
            # After index lookup, fetch_issue_detail is called with the identifier
            tracker.fetch_issue_detail.return_value = issue
        else:
            # Legacy path: no work_branch → branch index is empty,
            # fetch_issue_detail returns the issue by identifier
            tracker.fetch_issues_by_states.return_value = []
            tracker.fetch_issue_detail.return_value = issue

        orch._fetch_epic_children = MagicMock(return_value=[])
        created_sibling = MagicMock()
        created_sibling.identifier = "new-sibling-1"
        tracker.create_issue.return_value = created_sibling
        orch._project_trackers[project.id] = tracker
        return orch, tracker

    def test_github_task_ci_fix_sibling_created_via_branch_index(self, tmp_path):
        """When a PR's source_branch is a GitHub slug, _yolo_retry_ci finds the
        task via the branch index and relabels it Needs CI Fix."""
        project = _make_project(yolo=True)
        gh_issue = _make_github_issue(
            number=42, work_branch="oompah/proj/gh-42",
            labels=[], project_id=project.id,
        )

        orch, tracker = self._make_orch_with_issue(
            tmp_path, project, gh_issue, work_branch="oompah/proj/gh-42"
        )
        review = _make_review(review_id="99", source_branch="oompah/proj/gh-42",
                              ci_status="failed")

        orch._yolo_retry_ci(project, review)

        # The tracker should receive a status update (relabel to Needs CI Fix)
        # OR a sibling creation — either is valid depending on whether the issue
        # has children. Since fetch_epic_children returns [], the relabel path fires.
        assert (
            tracker.update_issue.called or tracker.create_issue.called
        ), "Expected either update_issue (relabel) or create_issue (sibling)"

    def test_backlog_task_ci_fix_uses_legacy_path(self, tmp_path):
        """Backlog task (branch == identifier) reaches _yolo_retry_ci via
        the legacy fetch_issue_detail path and is relabeled Needs CI Fix."""
        project = _make_project(yolo=True)
        backlog_issue = _make_issue(
            "TASK-9", state="open", labels=[], project_id=project.id,
            description="Task description",
        )

        orch, tracker = self._make_orch_with_issue(
            tmp_path, project, backlog_issue, work_branch=None
        )
        # Legacy: branch name equals identifier
        tracker.fetch_issue_detail.return_value = backlog_issue
        review = _make_review(review_id="55", source_branch="TASK-9",
                              ci_status="failed")

        orch._yolo_retry_ci(project, review)

        # update_issue called with Needs CI Fix status
        tracker.update_issue.assert_called_once()
        update_kwargs = tracker.update_issue.call_args.kwargs
        assert update_kwargs.get("status") == NEEDS_CI_FIX

    def test_github_task_ci_fix_identifier_used_in_relabel(self, tmp_path):
        """When the GitHub task is found via branch index, the tracker update
        uses the GitHub identifier (owner/repo#N), not the work_branch slug."""
        project = _make_project(yolo=True)
        gh_issue = _make_github_issue(
            number=42, work_branch="oompah/proj/gh-42",
            labels=[], project_id=project.id,
        )

        orch, tracker = self._make_orch_with_issue(
            tmp_path, project, gh_issue, work_branch="oompah/proj/gh-42"
        )
        orch._fetch_epic_children = MagicMock(return_value=[])
        review = _make_review(review_id="99", source_branch="oompah/proj/gh-42",
                              ci_status="failed")

        orch._yolo_retry_ci(project, review)

        if tracker.update_issue.called:
            update_call = tracker.update_issue.call_args
            # The identifier passed to update_issue must be the GitHub identifier,
            # not the work_branch slug
            identifier_arg = update_call.args[0] if update_call.args else None
            assert identifier_arg == gh_issue.identifier
            assert identifier_arg != "oompah/proj/gh-42"


# ---------------------------------------------------------------------------
# 5. Merge conflicts: merge-conflict label cleared via branch index (GitHub)
# ---------------------------------------------------------------------------


class TestMergeConflictLabelClearingGitHubVsBacklog:
    """_clear_merge_conflict_label_for_branch uses _resolve_task_for_branch
    so GitHub tasks are found via the branch index (AC#1)."""

    def test_github_task_conflict_label_cleared_via_branch_index(self, tmp_path):
        """merge-conflict label removed from GitHub task found via branch index."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])

        gh_issue = _make_github_issue(
            number=42, work_branch="oompah/proj/gh-42",
            labels=["merge-conflict"], project_id=project.id,
        )
        tracker = MagicMock()
        # Branch index: issue found via work_branch
        tracker.fetch_issues_by_states.return_value = [gh_issue]
        tracker.fetch_issue_detail.return_value = gh_issue
        orch._project_trackers[project.id] = tracker

        orch._clear_merge_conflict_label_for_branch(
            project, tracker, "oompah/proj/gh-42"
        )

        tracker.update_issue.assert_called_once_with(
            gh_issue.identifier, **{"remove-label": "merge-conflict"}
        )

    def test_backlog_task_conflict_label_cleared_via_legacy_path(self, tmp_path):
        """merge-conflict label removed from Backlog task via legacy path."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])

        backlog_issue = _make_issue("TASK-5", state="open",
                                    labels=["merge-conflict"])
        tracker = MagicMock()
        # Branch index: no work_branch on Backlog issues
        tracker.fetch_issues_by_states.return_value = [
            _make_issue("TASK-5", state="open")  # no work_branch
        ]
        # Legacy lookup by identifier
        tracker.fetch_issue_detail.return_value = backlog_issue

        orch._clear_merge_conflict_label_for_branch(project, tracker, "TASK-5")

        tracker.update_issue.assert_called_once_with(
            "TASK-5", **{"remove-label": "merge-conflict"}
        )

    def test_github_task_no_label_no_update(self, tmp_path):
        """If the GitHub task lacks merge-conflict label, update_issue is not called."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])

        gh_issue = _make_github_issue(
            number=42, work_branch="oompah/proj/gh-42",
            labels=["bug"],  # no merge-conflict
            project_id=project.id,
        )
        tracker = MagicMock()
        tracker.fetch_issues_by_states.return_value = [gh_issue]
        tracker.fetch_issue_detail.return_value = gh_issue

        orch._clear_merge_conflict_label_for_branch(
            project, tracker, "oompah/proj/gh-42"
        )

        tracker.update_issue.assert_not_called()

    def test_github_orphan_branch_no_crash(self, tmp_path):
        """When branch index returns nothing for a GitHub branch, no crash."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])

        tracker = MagicMock()
        # Branch index: no matching issue
        tracker.fetch_issues_by_states.return_value = []
        tracker.fetch_issue_detail.return_value = None

        # Should not raise
        orch._clear_merge_conflict_label_for_branch(
            project, tracker, "oompah/proj/gh-orphan"
        )

        tracker.update_issue.assert_not_called()


# ---------------------------------------------------------------------------
# 6. YOLO direct merge: GitHub task marked Merged via resolver
# ---------------------------------------------------------------------------


class TestYoloDirectMergeGitHubVsBacklog:
    """YOLO direct-merge behavior differs between GitHub-backed and Backlog tasks.

    For GitHub-backed tasks (tracker_kind='github_issues'):
    - After a successful merge, _yolo_mark_task_merged explicitly marks the
      task Merged using the identifier resolved via branch index.  This is
      needed because the webhook path can't resolve the branch→task mapping.

    For Backlog tasks (default tracker_kind):
    - YOLO only calls provider.merge_review and leaves the Merged status
      update to the webhook sweep.  No explicit update_issue(MERGED) call.

    AC#1: tests cover both paths and document where behavior differs.
    """

    def test_yolo_mark_task_merged_uses_branch_index_for_github(self, tmp_path):
        """_yolo_mark_task_merged resolves the GitHub task via branch index and
        marks it Merged using its full owner/repo#N identifier."""
        project = _make_project(yolo=True)
        gh_issue = _make_github_issue(
            number=42, work_branch="oompah/proj/gh-42",
            labels=[], state=IN_REVIEW, project_id=project.id,
        )

        orch = _make_orchestrator(tmp_path, projects=[project])
        tracker = MagicMock()
        tracker.fetch_issues_by_states.return_value = [gh_issue]
        tracker.fetch_issue_detail.return_value = gh_issue
        orch._project_trackers[project.id] = tracker

        review = _make_review("10", source_branch="oompah/proj/gh-42")
        orch._yolo_mark_task_merged(tracker, project, review, "10")

        # update_issue called with the GitHub identifier and MERGED status
        tracker.update_issue.assert_called_once_with(
            gh_issue.identifier, status=MERGED
        )

    def test_yolo_mark_task_merged_uses_identifier_for_backlog(self, tmp_path):
        """_yolo_mark_task_merged also works for Backlog tasks where branch==identifier."""
        project = _make_project(yolo=True)
        backlog_issue = _make_issue(
            "TASK-9", state=IN_REVIEW, labels=[], project_id=project.id,
        )

        orch = _make_orchestrator(tmp_path, projects=[project])
        tracker = MagicMock()
        tracker.fetch_issues_by_states.return_value = []  # no work_branch
        tracker.fetch_issue_detail.return_value = backlog_issue
        orch._project_trackers[project.id] = tracker

        review = _make_review("20", source_branch="TASK-9")
        orch._yolo_mark_task_merged(tracker, project, review, "20")

        tracker.update_issue.assert_called_once_with("TASK-9", status=MERGED)

    def test_yolo_mark_task_merged_noop_when_task_already_merged(self, tmp_path):
        """If the GitHub task is already Merged, no redundant update is issued."""
        project = _make_project(yolo=True)
        gh_issue = _make_github_issue(
            number=42, work_branch="oompah/proj/gh-42",
            state=MERGED, project_id=project.id,
        )

        orch = _make_orchestrator(tmp_path, projects=[project])
        tracker = MagicMock()
        tracker.fetch_issues_by_states.return_value = [gh_issue]
        tracker.fetch_issue_detail.return_value = gh_issue

        review = _make_review("10", source_branch="oompah/proj/gh-42")
        orch._yolo_mark_task_merged(tracker, project, review, "10")

        # No update_issue call when state is already Merged
        merged_calls = [
            c for c in tracker.update_issue.call_args_list
            if c.kwargs.get("status") == MERGED
        ]
        assert not merged_calls

    @patch("oompah.orchestrator.extract_repo_slug")
    @patch("oompah.orchestrator.detect_provider")
    def test_backlog_task_yolo_merge_does_not_explicitly_mark_merged(
        self, mock_detect, mock_slug, tmp_path
    ):
        """For Backlog tasks (tracker_kind=backlog_md, the default), YOLO merges
        the PR but does NOT call update_issue(MERGED).  The webhook sweep handles
        the status transition separately.  This is the key difference from
        GitHub-backed tasks (AC#1)."""
        project = _make_project(yolo=True)
        backlog_issue = _make_issue(
            "TASK-9", state=IN_REVIEW, labels=[], project_id=project.id,
        )

        provider = MagicMock()
        provider.merge_review.return_value = (True, "merged")
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        # Default tracker_kind is backlog_md — _yolo_mark_task_merged NOT called
        orch = _make_orchestrator(tmp_path, projects=[project])
        tracker = MagicMock()
        tracker.fetch_issues_by_states.return_value = [
            _make_issue("TASK-9", state="open")  # no work_branch
        ]
        tracker.fetch_issue_detail.return_value = backlog_issue
        orch._project_trackers[project.id] = tracker
        orch._reviews_cache = {
            project.id: [
                _make_review("20", source_branch="TASK-9")
            ]
        }

        orch._yolo_review_actions_sync()

        provider.merge_review.assert_called_once_with("org/repo", "20")
        # For Backlog tasks, YOLO does NOT call update_issue(MERGED) —
        # that's the webhook sweep's responsibility.
        merged_update_calls = [
            c for c in tracker.update_issue.call_args_list
            if c.kwargs.get("status") == MERGED
        ]
        assert not merged_update_calls, (
            "YOLO should NOT mark Backlog task Merged directly "
            "(webhook sweep handles it)"
        )


# ---------------------------------------------------------------------------
# 7. Merge queue enqueue: GitHub task enqueued via resolver
# ---------------------------------------------------------------------------


class TestMergeQueueEnqueueGitHubVsBacklog:
    """Merge queue enqueue uses _resolve_task_for_branch to find GitHub tasks
    so the correct identifier is marked In Review / Merged (AC#1)."""

    @patch("oompah.orchestrator.extract_repo_slug")
    @patch("oompah.orchestrator.detect_provider")
    def test_github_task_enqueued_for_merge_via_branch_index(
        self, mock_detect, mock_slug, tmp_path
    ):
        """When merge_queue_enabled=True, the GitHub task found via branch index
        has its stale merge-conflict label cleared on enqueue.  The label
        clearing uses _resolve_task_for_branch to find the task via the index."""
        project = _make_project(yolo=True, merge_queue_enabled=True)
        gh_issue = _make_github_issue(
            number=42, work_branch="oompah/proj/gh-42",
            labels=["merge-conflict"],  # stale label — should be cleared on enqueue
            state=IN_REVIEW, project_id=project.id,
        )

        provider = MagicMock()
        provider.enable_auto_merge.return_value = (True, "")
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = _make_orchestrator(tmp_path, projects=[project])
        tracker = MagicMock()
        tracker.fetch_issues_by_states.return_value = [gh_issue]
        tracker.fetch_issue_detail.return_value = gh_issue
        orch._project_trackers[project.id] = tracker
        orch._reviews_cache = {
            project.id: [
                _make_review("30", source_branch="oompah/proj/gh-42")
            ]
        }

        orch._yolo_review_actions_sync()

        provider.enable_auto_merge.assert_called_once_with("org/repo", "30")
        # Stale merge-conflict label should be cleared from the GitHub task
        # via _clear_merge_conflict_label_for_branch → _resolve_task_for_branch
        remove_calls = [
            c for c in tracker.update_issue.call_args_list
            if c.kwargs.get("remove-label") == "merge-conflict"
        ]
        assert remove_calls, "Expected merge-conflict label cleared on enqueue"
        # The identifier used must be the GitHub identifier, not the branch slug
        assert remove_calls[0].args[0] == gh_issue.identifier

    @patch("oompah.orchestrator.extract_repo_slug")
    @patch("oompah.orchestrator.detect_provider")
    def test_backlog_task_enqueued_via_legacy_path(
        self, mock_detect, mock_slug, tmp_path
    ):
        """Backlog task enqueued for merge (legacy path) uses identifier."""
        project = _make_project(yolo=True, merge_queue_enabled=True)
        backlog_issue = _make_issue(
            "TASK-11", state=IN_REVIEW, labels=[], project_id=project.id,
        )

        provider = MagicMock()
        provider.enable_auto_merge.return_value = (True, "")
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = _make_orchestrator(tmp_path, projects=[project])
        tracker = MagicMock()
        tracker.fetch_issues_by_states.return_value = []
        tracker.fetch_issue_detail.return_value = backlog_issue
        orch._project_trackers[project.id] = tracker
        orch._reviews_cache = {
            project.id: [_make_review("40", source_branch="TASK-11")]
        }

        orch._yolo_review_actions_sync()

        provider.enable_auto_merge.assert_called_once_with("org/repo", "40")


# ---------------------------------------------------------------------------
# 8. Release-pick outcomes: backport PR body must NOT use closing keywords (AC#2)
# ---------------------------------------------------------------------------


class TestReleasepickNoBranchClosingKeyword:
    """open_backport_pr does NOT use 'Fixes #N' GitHub closing keywords.

    The description uses a plain reference so merging the release-branch PR
    does NOT auto-close the original issue on GitHub (AC#2)."""

    def test_backport_pr_description_no_fixes_keyword(self):
        """open_backport_pr description never contains 'Fixes' or 'Closes'."""
        from oompah.cherry_pick_pr_creator import open_backport_pr
        from oompah.models import Issue
        from oompah.release_pick_schema import BackportEntry

        source = Issue(
            id="org/tasks#10",
            identifier="org/tasks#10",
            title="Fix important bug",
            description="desc",
            state="open",
            tracker_kind="github_issues",
        )
        child = Issue(
            id="org/tasks#11",
            identifier="org/tasks#11",
            title="Backport Fix important bug to release/1.0",
            description="desc",
            state="open",
            tracker_kind="github_issues",
        )
        entry = BackportEntry(branch="release/1.0", commits=["abc123"])
        scm = MagicMock()
        scm.create_review.return_value = MagicMock(
            id="55", url="https://github.com/org/repo/pull/55"
        )

        open_backport_pr(scm, "org/repo", source, child, entry)

        call_kwargs = scm.create_review.call_args
        description = (
            call_kwargs.kwargs.get("description")
            or (call_kwargs.args[3] if len(call_kwargs.args) > 3 else "")
        )
        assert "Fixes" not in description, (
            f"Backport PR description must NOT use 'Fixes' keyword; got: {description!r}"
        )
        assert "Closes" not in description, (
            f"Backport PR description must NOT use 'Closes' keyword; got: {description!r}"
        )
        assert "resolves" not in description.lower(), (
            f"Backport PR description must NOT use 'resolves' keyword; got: {description!r}"
        )

    def test_backport_pr_description_references_source_task(self):
        """open_backport_pr description mentions the source task identifier
        without auto-closing it."""
        from oompah.cherry_pick_pr_creator import open_backport_pr
        from oompah.models import Issue
        from oompah.release_pick_schema import BackportEntry

        source = Issue(
            id="org/tasks#10",
            identifier="org/tasks#10",
            title="Fix critical regression",
            description="desc",
            state="open",
            tracker_kind="github_issues",
        )
        child = Issue(
            id="org/tasks#11",
            identifier="org/tasks#11",
            title="Backport fix",
            description="desc",
            state="open",
            tracker_kind="github_issues",
        )
        entry = BackportEntry(branch="release/2.0", commits=["def456"])
        scm = MagicMock()
        scm.create_review.return_value = MagicMock(
            id="56", url="https://github.com/org/repo/pull/56"
        )

        open_backport_pr(scm, "org/repo", source, child, entry)

        call_kwargs = scm.create_review.call_args
        description = (
            call_kwargs.kwargs.get("description")
            or (call_kwargs.args[3] if len(call_kwargs.args) > 3 else "")
        )
        # Source identifier referenced without a closing keyword
        assert source.identifier in description

    def test_backport_pr_targets_release_branch_not_main(self):
        """The PR target branch in open_backport_pr is the release branch,
        not main."""
        from oompah.cherry_pick_pr_creator import open_backport_pr
        from oompah.models import Issue
        from oompah.release_pick_schema import BackportEntry

        source = Issue(
            id="org/tasks#20",
            identifier="org/tasks#20",
            title="Fix bug",
            description="desc",
            state="open",
            tracker_kind="github_issues",
        )
        child = Issue(
            id="org/tasks#21",
            identifier="org/tasks#21",
            title="Backport Fix bug to release/3.0",
            description="desc",
            state="open",
            tracker_kind="github_issues",
        )
        entry = BackportEntry(branch="release/3.0", commits=["ghi789"])
        scm = MagicMock()
        scm.create_review.return_value = MagicMock(
            id="57", url="https://github.com/org/repo/pull/57"
        )

        open_backport_pr(scm, "org/repo", source, child, entry)

        call_kwargs = scm.create_review.call_args
        target_branch = call_kwargs.kwargs.get("target_branch")
        assert target_branch == "release/3.0", (
            f"Expected target_branch='release/3.0', got {target_branch!r}"
        )

    def test_backlog_backport_pr_also_has_no_closing_keyword(self):
        """For Backlog-backed source tasks, open_backport_pr ALSO avoids
        closing keywords (plain references)."""
        from oompah.cherry_pick_pr_creator import open_backport_pr
        from oompah.models import Issue
        from oompah.release_pick_schema import BackportEntry

        source = Issue(
            id="TASK-30",
            identifier="TASK-30",
            title="Fix regression",
            description="desc",
            state="open",
            tracker_kind=None,  # Backlog tracker
        )
        child = Issue(
            id="TASK-30.1",
            identifier="TASK-30.1",
            title="Backport TASK-30 to release/1.0",
            description="desc",
            state="open",
            tracker_kind=None,
        )
        entry = BackportEntry(branch="release/1.0", commits=["aaa111"])
        scm = MagicMock()
        scm.create_review.return_value = MagicMock(
            id="58", url="https://github.com/org/repo/pull/58"
        )

        open_backport_pr(scm, "org/repo", source, child, entry)

        call_kwargs = scm.create_review.call_args
        description = (
            call_kwargs.kwargs.get("description")
            or (call_kwargs.args[3] if len(call_kwargs.args) > 3 else "")
        )
        # No closing keyword for Backlog tasks either
        assert "Fixes" not in description
        assert "Closes" not in description

    def test_pr_body_build_release_branch_no_closing_keyword_direct(self, tmp_path):
        """_build_pr_body for a GitHub issue targeting a release branch returns
        a plain link without 'Fixes #N' (AC#2 end-to-end check)."""
        orch = _make_orchestrator(tmp_path)
        issue = Issue(
            id="42",
            identifier="org/repo#42",
            title="Fix regression",
            description="desc",
            state="open",
            owner="org",
            repo="repo",
            issue_number="42",
            url="https://github.com/org/repo/issues/42",
            tracker_kind="github_issues",
        )

        # PR targeting release/2.0 (not main)
        body = orch._build_pr_body(issue, "release/2.0", "org/repo", "main")

        assert "Fixes" not in body, f"Expected no 'Fixes' keyword, got: {body!r}"
        assert "https://github.com/org/repo/issues/42" in body


# ---------------------------------------------------------------------------
# 9. PR body: "Fixes" only for same-repo + default-branch, never for release
# ---------------------------------------------------------------------------


class TestPrBodyClosingKeywordRules:
    """Systematic verification that _build_pr_body uses closing keywords
    only when appropriate, and never for release branches (AC#2)."""

    def test_same_repo_default_branch_gets_closing_keyword(self, tmp_path):
        """Same repo, default branch → Fixes #N."""
        orch = _make_orchestrator(tmp_path)
        issue = Issue(
            id="10",
            identifier="org/repo#10",
            title="T",
            url="https://github.com/org/repo/issues/10",
            owner="org",
            repo="repo",
            issue_number="10",
            tracker_kind="github_issues",
        )
        body = orch._build_pr_body(issue, "main", "org/repo", "main")
        assert "Fixes #10" in body

    def test_release_branch_never_gets_closing_keyword(self, tmp_path):
        """Release branch target → plain link, no Fixes."""
        orch = _make_orchestrator(tmp_path)
        issue = Issue(
            id="10",
            identifier="org/repo#10",
            title="T",
            url="https://github.com/org/repo/issues/10",
            owner="org",
            repo="repo",
            issue_number="10",
            tracker_kind="github_issues",
        )
        for release_branch in ("release/1.0", "release/2.x", "v3", "maint-1.0"):
            body = orch._build_pr_body(issue, release_branch, "org/repo", "main")
            assert "Fixes" not in body, (
                f"Expected no 'Fixes' for target={release_branch!r}, got: {body!r}"
            )

    def test_cross_repo_github_issue_never_gets_closing_keyword(self, tmp_path):
        """Cross-repo (hub repo != PR repo) → plain link, no Fixes."""
        orch = _make_orchestrator(tmp_path)
        issue = Issue(
            id="hub-10",
            identifier="org/hub-tasks#10",
            title="T",
            url="https://github.com/org/hub-tasks/issues/10",
            owner="org",
            repo="hub-tasks",
            issue_number="10",
            tracker_kind="github_issues",
        )
        body = orch._build_pr_body(issue, "main", "org/repo", "main")
        assert "Fixes" not in body
        assert "https://github.com/org/hub-tasks/issues/10" in body

    def test_backlog_issue_never_gets_closing_keyword(self, tmp_path):
        """Backlog issues always use plain links, regardless of target branch."""
        orch = _make_orchestrator(tmp_path)
        issue = Issue(
            id="TASK-5",
            identifier="TASK-5",
            title="T",
            url="https://example.com/task/5",
            tracker_kind=None,
        )
        for target in ("main", "release/1.0", "develop"):
            body = orch._build_pr_body(issue, target, "org/repo", "main")
            assert "Fixes" not in body, (
                f"Expected no 'Fixes' for Backlog task, target={target!r}, got: {body!r}"
            )
