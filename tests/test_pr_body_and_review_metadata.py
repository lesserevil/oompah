"""Tests for _build_pr_body and _write_review_metadata (TASK-462.2).

Covers:
- _build_pr_body: hub issue link generation, closing keyword safety checks
- _write_review_metadata: best-effort metadata field writes
- _mark_task_in_review: delegates to both update_issue and _write_review_metadata
- _ensure_review_exists: passes description to provider.create_review
- Epic PR creation: includes hub link in description and writes metadata
"""

from __future__ import annotations

import fnmatch
from unittest.mock import MagicMock, call, patch

import pytest

from oompah.config import ServiceConfig
from oompah.models import Issue, RunningEntry
from oompah.orchestrator import Orchestrator
from oompah.statuses import IN_REVIEW


# ------------------------------------------------------------------ helpers


def _make_orchestrator(tmp_path, projects=None):
    project_store = MagicMock()
    project_store.list_all.return_value = projects or []
    project_store.get.side_effect = lambda pid: next(
        (p for p in (projects or []) if p.id == pid), None
    )
    project_store.epic_branch_name.side_effect = lambda epic_id: (
        f"epic-{epic_id.replace('/', '_')}"
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
    default_branch: str = "main",
    epic_strategy: str = "flat",
) -> MagicMock:
    p = MagicMock()
    p.id = project_id
    p.name = "test-project"
    p.repo_url = repo_url
    p.repo_path = "/tmp/repo"
    p.branch = default_branch
    p.default_branch = default_branch
    p.branches = [default_branch]
    p.matches_branch = lambda b: fnmatch.fnmatch(b, default_branch)
    p.paused = False
    p.epic_strategy = epic_strategy
    p.max_in_flight_prs = 5
    p.access_token = None
    return p


def _make_github_issue(
    identifier: str = "org/repo#42",
    title: str = "Test issue",
    description: str = "body",
    url: str = "https://github.com/org/repo/issues/42",
    tracker_owner: str = "org",
    tracker_repo: str = "repo",
    issue_number: str = "42",
    display_identifier: str = "org/repo#42",
    target_branch: str | None = None,
    project_id: str | None = "proj-1",
) -> Issue:
    return Issue(
        id=issue_number,
        identifier=identifier,
        title=title,
        description=description,
        state="open",
        url=url,
        tracker_owner=tracker_owner,
        tracker_repo=tracker_repo,
        issue_number=issue_number,
        display_identifier=display_identifier,
        tracker_kind="github_issues",
        target_branch=target_branch,
        project_id=project_id,
    )


def _make_entry(issue: Issue) -> RunningEntry:
    return RunningEntry(
        worker_task=MagicMock(),
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=MagicMock(),
        agent_profile_name="default",
    )


# ------------------------------------------------------------------ _build_pr_body


class TestBuildPrBody:
    def test_returns_empty_for_no_issue(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        result = orch._build_pr_body(None, "main", "org/repo", "main")
        assert result == ""

    def test_returns_empty_for_issue_without_url(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        issue = Issue(
            id="1", identifier="TASK-1", title="T", url=None, tracker_kind="github_issues"
        )
        result = orch._build_pr_body(issue, "main", "org/repo", "main")
        assert result == ""

    def test_non_github_tracker_uses_plain_link(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        issue = Issue(
            id="1",
            identifier="TASK-1",
            title="T",
            url="https://example.com/task/1",
            tracker_kind="backlog",
        )
        result = orch._build_pr_body(issue, "main", "org/repo", "main")
        assert "Relates to:" in result
        assert "https://example.com/task/1" in result
        assert "Fixes" not in result

    def test_github_same_repo_default_branch_uses_closing_keyword(self, tmp_path):
        """Same repo + default branch target → Fixes #N closing keyword."""
        orch = _make_orchestrator(tmp_path)
        issue = _make_github_issue(
            tracker_owner="org", tracker_repo="repo", issue_number="42",
            url="https://github.com/org/repo/issues/42",
        )
        result = orch._build_pr_body(issue, "main", "org/repo", "main")
        assert "Fixes #42" in result
        # Also includes a stable link
        assert "https://github.com/org/repo/issues/42" in result

    def test_github_same_repo_non_default_branch_no_closing_keyword(self, tmp_path):
        """Same repo + non-default branch → plain link, no closing keyword."""
        orch = _make_orchestrator(tmp_path)
        issue = _make_github_issue(
            tracker_owner="org", tracker_repo="repo", issue_number="42",
            url="https://github.com/org/repo/issues/42",
        )
        result = orch._build_pr_body(issue, "release/1.2", "org/repo", "main")
        assert "Fixes" not in result
        assert "Relates to:" in result
        assert "https://github.com/org/repo/issues/42" in result

    def test_github_different_repo_no_closing_keyword(self, tmp_path):
        """Cross-repo (hub repo != PR repo) → plain link, no closing keyword."""
        orch = _make_orchestrator(tmp_path)
        # Issue is in org/oompah-tasks, PR is in org/repo
        issue = _make_github_issue(
            identifier="org/oompah-tasks#42",
            tracker_owner="org",
            tracker_repo="oompah-tasks",
            issue_number="42",
            url="https://github.com/org/oompah-tasks/issues/42",
        )
        result = orch._build_pr_body(issue, "main", "org/repo", "main")
        assert "Fixes" not in result
        assert "Relates to:" in result
        assert "https://github.com/org/oompah-tasks/issues/42" in result

    def test_github_case_insensitive_slug_comparison(self, tmp_path):
        """Slug comparison is case-insensitive."""
        orch = _make_orchestrator(tmp_path)
        issue = _make_github_issue(
            tracker_owner="Org", tracker_repo="Repo", issue_number="7",
            url="https://github.com/Org/Repo/issues/7",
        )
        result = orch._build_pr_body(issue, "main", "org/repo", "main")
        assert "Fixes #7" in result

    def test_github_no_issue_number_falls_back_to_plain_link(self, tmp_path):
        """GitHub issue without issue_number → plain link even if same repo + default branch."""
        orch = _make_orchestrator(tmp_path)
        issue = Issue(
            id="42",
            identifier="org/repo#42",
            title="T",
            url="https://github.com/org/repo/issues/42",
            tracker_owner="org",
            tracker_repo="repo",
            issue_number=None,
            tracker_kind="github_issues",
        )
        result = orch._build_pr_body(issue, "main", "org/repo", "main")
        assert "Fixes" not in result
        assert "Relates to:" in result


# ------------------------------------------------------------------ _write_review_metadata


class TestWriteReviewMetadata:
    def test_writes_review_url_and_number(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        orch._write_review_metadata(
            tracker,
            "org/repo#42",
            review_id="99",
            review_url="https://github.com/org/repo/pull/99",
        )
        calls = {c.args[1]: c.args[2] for c in tracker.set_metadata_field.call_args_list}
        assert calls.get("oompah.review_url") == "https://github.com/org/repo/pull/99"
        assert calls.get("oompah.review_number") == "99"

    def test_writes_source_and_target_branches(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        orch._write_review_metadata(
            tracker,
            "org/repo#42",
            review_id="3",
            review_url="https://github.com/org/repo/pull/3",
            source_branch="oompah/proj/gh-42",
            target_branch="main",
        )
        calls = {c.args[1]: c.args[2] for c in tracker.set_metadata_field.call_args_list}
        assert calls.get("oompah.work_branch") == "oompah/proj/gh-42"
        assert calls.get("oompah.target_branch") == "main"

    def test_skips_none_fields(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        orch._write_review_metadata(
            tracker,
            "org/repo#42",
            review_id=None,
            review_url=None,
        )
        tracker.set_metadata_field.assert_not_called()

    def test_failures_are_best_effort_not_raised(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        tracker.set_metadata_field.side_effect = Exception("tracker error")
        # Should not raise
        orch._write_review_metadata(
            tracker,
            "org/repo#42",
            review_id="5",
            review_url="https://github.com/org/repo/pull/5",
        )


# ------------------------------------------------------------------ _mark_task_in_review


class TestMarkTaskInReview:
    def test_writes_review_metadata_after_status_update(self, tmp_path):
        proj = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[proj])

        tracker = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=tracker)

        review = MagicMock()
        review.id = "77"
        review.url = "https://github.com/org/repo/pull/77"
        review.source_branch = "oompah/proj/gh-42"
        review.target_branch = "main"

        issue = _make_github_issue()
        entry = _make_entry(issue)

        orch._mark_task_in_review(entry, "proj-1", review)

        tracker.update_issue.assert_called_once_with(issue.identifier, status=IN_REVIEW)
        meta_calls = {c.args[1]: c.args[2] for c in tracker.set_metadata_field.call_args_list}
        assert meta_calls.get("oompah.review_url") == "https://github.com/org/repo/pull/77"
        assert meta_calls.get("oompah.review_number") == "77"
        assert meta_calls.get("oompah.work_branch") == "oompah/proj/gh-42"
        assert meta_calls.get("oompah.target_branch") == "main"

    def test_noop_when_no_project_id(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=tracker)

        review = MagicMock()
        issue = _make_github_issue()
        entry = _make_entry(issue)

        orch._mark_task_in_review(entry, None, review)

        tracker.update_issue.assert_not_called()
        tracker.set_metadata_field.assert_not_called()

    def test_exception_in_tracker_is_caught(self, tmp_path):
        proj = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[proj])
        tracker = MagicMock()
        tracker.update_issue.side_effect = Exception("tracker unavailable")
        orch._tracker_for_project = MagicMock(return_value=tracker)

        review = MagicMock()
        issue = _make_github_issue()
        entry = _make_entry(issue)

        # Should not raise
        orch._mark_task_in_review(entry, "proj-1", review)


# ------------------------------------------------------------------ _ensure_review_exists


class TestEnsureReviewExistsPassesDescription:
    def test_github_issue_description_passed_to_create_review(self, tmp_path):
        """create_review receives a non-empty description with the hub link."""
        proj = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[proj])
        orch._reviews_cache = {"proj-1": []}

        provider = MagicMock()
        provider.create_review.return_value = MagicMock(
            id="10", url="https://github.com/org/repo/pull/10",
            source_branch="org/repo#42", target_branch="main",
        )
        tracker = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=tracker)

        issue = _make_github_issue()
        entry = _make_entry(issue)

        with (
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
        ):
            result = orch._ensure_review_exists(entry, "proj-1")

        assert result is True
        call_kwargs = provider.create_review.call_args.kwargs
        description = call_kwargs.get("description", "")
        assert "https://github.com/org/repo/issues/42" in description

    def test_cross_repo_hub_issue_no_closing_keyword(self, tmp_path):
        """Cross-repo hub issue → plain link, no 'Fixes' keyword in PR body."""
        proj = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[proj])
        orch._reviews_cache = {"proj-1": []}

        provider = MagicMock()
        provider.create_review.return_value = MagicMock(
            id="20", url="https://github.com/org/repo/pull/20",
            source_branch="org/hub-repo#42", target_branch="main",
        )
        tracker = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=tracker)

        # Issue is in a different repo (hub)
        issue = _make_github_issue(
            identifier="org/oompah-tasks#42",
            tracker_owner="org",
            tracker_repo="oompah-tasks",
            issue_number="42",
            url="https://github.com/org/oompah-tasks/issues/42",
        )
        entry = _make_entry(issue)

        with (
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
        ):
            orch._ensure_review_exists(entry, "proj-1")

        call_kwargs = provider.create_review.call_args.kwargs
        description = call_kwargs.get("description", "")
        assert "Fixes" not in description
        assert "https://github.com/org/oompah-tasks/issues/42" in description

    def test_release_branch_no_closing_keyword(self, tmp_path):
        """PR targeting a release branch → no 'Fixes' keyword even if same repo."""
        proj = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[proj])
        orch._reviews_cache = {"proj-1": []}

        provider = MagicMock()
        provider.create_review.return_value = MagicMock(
            id="30", url="https://github.com/org/repo/pull/30",
            source_branch="org/repo#42", target_branch="release/1.2",
        )
        tracker = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=tracker)

        issue = _make_github_issue(target_branch="release/1.2")
        entry = _make_entry(issue)

        with (
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
        ):
            orch._ensure_review_exists(entry, "proj-1")

        call_kwargs = provider.create_review.call_args.kwargs
        description = call_kwargs.get("description", "")
        assert "Fixes" not in description
        assert "https://github.com/org/repo/issues/42" in description

    def test_same_repo_default_branch_uses_closing_keyword(self, tmp_path):
        """Same repo + default branch → 'Fixes #N' in PR body."""
        proj = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[proj])
        orch._reviews_cache = {"proj-1": []}

        provider = MagicMock()
        provider.create_review.return_value = MagicMock(
            id="40", url="https://github.com/org/repo/pull/40",
            source_branch="org/repo#42", target_branch="main",
        )
        tracker = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=tracker)

        # Issue is in the same repo as the PR and targets main
        issue = _make_github_issue(
            tracker_owner="org", tracker_repo="repo", issue_number="42",
            url="https://github.com/org/repo/issues/42",
        )
        entry = _make_entry(issue)

        with (
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
        ):
            orch._ensure_review_exists(entry, "proj-1")

        call_kwargs = provider.create_review.call_args.kwargs
        description = call_kwargs.get("description", "")
        assert "Fixes #42" in description

    def test_backlog_issue_no_url_empty_description(self, tmp_path):
        """Backlog issue without URL → empty description (no hub link)."""
        proj = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[proj])
        orch._reviews_cache = {"proj-1": []}

        provider = MagicMock()
        provider.create_review.return_value = MagicMock(
            id="50", url="https://github.com/org/repo/pull/50",
            source_branch="TASK-99", target_branch="main",
        )
        tracker = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=tracker)

        issue = Issue(
            id="TASK-99",
            identifier="TASK-99",
            title="Backlog task",
            url=None,
            tracker_kind=None,
            project_id="proj-1",
        )
        entry = _make_entry(issue)

        with (
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
        ):
            orch._ensure_review_exists(entry, "proj-1")

        call_kwargs = provider.create_review.call_args.kwargs
        assert call_kwargs.get("description") == ""
