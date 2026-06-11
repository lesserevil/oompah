"""Tests for GitHub-safe work branch generation and metadata persistence
before worktree creation (TASK-461.3).

Covers:
- AC#1: Branch names never rely on bare task numbers — GitHub-backed tasks
  get ``oompah/<project-slug>/gh-<number>`` branches via
  ``_create_workspace_for_issue()``.
- AC#2: Review reconciliation can find the task from Work Branch metadata —
  ``oompah.work_branch`` is persisted to the GitHub issue before the worktree
  is created; ``oompah.target_branch`` is also persisted when set.
"""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from oompah.config import ServiceConfig
from oompah.models import Issue, Project
from oompah.orchestrator import Orchestrator
from oompah.projects import github_work_branch_name


def _make_config() -> ServiceConfig:
    return ServiceConfig()


def _make_orchestrator(tmp_path) -> Orchestrator:
    return Orchestrator(
        config=_make_config(),
        workflow_path="WORKFLOW.md",
        state_path=str(tmp_path / "service_state.json"),
    )


def _github_issue(**overrides) -> Issue:
    defaults = dict(
        id="gh-node-1234",
        identifier="owner/oompah-tasks#1234",
        title="Test GitHub issue",
        state="in_progress",
        priority=2,
        issue_type="task",
        labels=[],
        tracker_kind="github_issues",
        tracker_owner="owner",
        tracker_repo="oompah-tasks",
        issue_number="1234",
        project_id="proj-gh",
    )
    defaults.update(overrides)
    return Issue(**defaults)


def _backlog_issue(**overrides) -> Issue:
    defaults = dict(
        id="TASK-999",
        identifier="TASK-999",
        title="Backlog issue",
        state="in_progress",
        priority=2,
        issue_type="task",
        labels=[],
        tracker_kind="backlog_md",
        project_id="proj-bl",
    )
    defaults.update(overrides)
    return Issue(**defaults)


def _make_project(project_id: str = "proj-gh", name: str = "myproj") -> Project:
    return Project(
        id=project_id,
        name=name,
        repo_url="https://example.com/myproj.git",
        repo_path="/tmp/fake-repo",
        branch="main",
        default_branch="main",
        branches=["main", "release/*"],
    )


class TestGitHubWorkBranchGeneration:
    """_create_workspace_for_issue uses a GitHub-safe branch name for
    GitHub-backed tasks (TASK-461.3 AC#1)."""

    def test_github_issue_gets_github_safe_branch_name(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        issue = _github_issue()
        project = _make_project()
        expected_branch = github_work_branch_name(project.name, issue.issue_number)

        mock_store = MagicMock()
        mock_store.get.return_value = project
        mock_store.create_worktree.return_value = "/fake/wt"
        orch.project_store = mock_store

        mock_tracker = MagicMock()
        orch._project_trackers["proj-gh"] = mock_tracker

        with patch.object(orch, "_project_epic_strategy", return_value="flat"), \
             patch.object(orch, "_resolve_parent_epic", return_value=None), \
             patch.object(orch, "_sync_issue_task_file_to_workspace"):
            orch._create_workspace_for_issue(issue)

        mock_store.create_worktree.assert_called_once_with(
            issue.project_id,
            issue.identifier,
            base_branch=issue.target_branch,
            branch_name=expected_branch,
        )
        assert issue.work_branch == expected_branch
        assert issue.branch_name == expected_branch

    def test_backlog_issue_uses_no_explicit_branch_name(self, tmp_path):
        """Backlog-backed tasks must not get a GitHub-style branch — the
        ``branch_name`` kwarg must remain ``None`` (default behaviour)."""
        orch = _make_orchestrator(tmp_path)
        issue = _backlog_issue()
        project = _make_project(project_id="proj-bl")

        mock_store = MagicMock()
        mock_store.get.return_value = project
        mock_store.create_worktree.return_value = "/fake/wt"
        orch.project_store = mock_store

        with patch.object(orch, "_project_epic_strategy", return_value="flat"), \
             patch.object(orch, "_resolve_parent_epic", return_value=None), \
             patch.object(orch, "_sync_issue_task_file_to_workspace"):
            orch._create_workspace_for_issue(issue)

        mock_store.create_worktree.assert_called_once_with(
            issue.project_id,
            issue.identifier,
            base_branch=issue.target_branch,
            branch_name=None,
        )

    def test_github_issue_without_issue_number_uses_no_branch_name(self, tmp_path):
        """If issue_number is missing, we cannot generate a safe branch name —
        fall back to None (create_worktree will use sanitized identifier)."""
        orch = _make_orchestrator(tmp_path)
        issue = _github_issue(issue_number=None)

        mock_store = MagicMock()
        mock_store.get.return_value = _make_project()
        mock_store.create_worktree.return_value = "/fake/wt"
        orch.project_store = mock_store

        with patch.object(orch, "_project_epic_strategy", return_value="flat"), \
             patch.object(orch, "_resolve_parent_epic", return_value=None), \
             patch.object(orch, "_sync_issue_task_file_to_workspace"):
            orch._create_workspace_for_issue(issue)

        _, kwargs = mock_store.create_worktree.call_args
        assert kwargs.get("branch_name") is None

    def test_branch_name_uses_project_slug_not_identifier(self, tmp_path):
        """Branch name must encode the project name slug, not the raw issue
        identifier — so it does not contain bare numbers or ``#`` characters."""
        orch = _make_orchestrator(tmp_path)
        issue = _github_issue(issue_number="42")
        project = _make_project(name="trickle")

        mock_store = MagicMock()
        mock_store.get.return_value = project
        mock_store.create_worktree.return_value = "/fake/wt"
        orch.project_store = mock_store

        mock_tracker = MagicMock()
        orch._project_trackers["proj-gh"] = mock_tracker

        with patch.object(orch, "_project_epic_strategy", return_value="flat"), \
             patch.object(orch, "_resolve_parent_epic", return_value=None), \
             patch.object(orch, "_sync_issue_task_file_to_workspace"):
            orch._create_workspace_for_issue(issue)

        _, kwargs = mock_store.create_worktree.call_args
        branch = kwargs.get("branch_name")
        assert branch == "oompah/trickle/gh-42"
        assert "#" not in branch
        assert branch != "42"


class TestGitHubWorkBranchMetadataPersistence:
    """work_branch and target_branch are persisted to the GitHub issue before
    the worktree is created (TASK-461.3 AC#2)."""

    def test_work_branch_metadata_written_before_worktree_create(self, tmp_path):
        """set_metadata_field('oompah.work_branch', ...) must be called before
        create_worktree() so the metadata is available even if worktree
        creation fails."""
        orch = _make_orchestrator(tmp_path)
        project = _make_project()
        issue = _github_issue()

        call_order = []
        mock_store = MagicMock()
        mock_store.get.return_value = project

        def record_create_worktree(*a, **kw):
            call_order.append("create_worktree")
            return "/fake/wt"

        mock_store.create_worktree.side_effect = record_create_worktree

        mock_tracker = MagicMock()

        def record_set_metadata(identifier, key, value):
            call_order.append(f"set_metadata:{key}={value}")

        mock_tracker.set_metadata_field.side_effect = record_set_metadata
        orch._project_trackers["proj-gh"] = mock_tracker
        orch.project_store = mock_store

        with patch.object(orch, "_project_epic_strategy", return_value="flat"), \
             patch.object(orch, "_resolve_parent_epic", return_value=None), \
             patch.object(orch, "_sync_issue_task_file_to_workspace"):
            orch._create_workspace_for_issue(issue)

        expected_branch = github_work_branch_name(project.name, issue.issue_number)
        assert f"set_metadata:oompah.work_branch={expected_branch}" in call_order
        # Metadata write must precede worktree creation
        meta_idx = call_order.index(f"set_metadata:oompah.work_branch={expected_branch}")
        create_idx = call_order.index("create_worktree")
        assert meta_idx < create_idx, (
            "oompah.work_branch must be persisted BEFORE create_worktree is called"
        )

    def test_target_branch_metadata_written_when_set(self, tmp_path):
        """When issue.target_branch is set, it must also be persisted."""
        orch = _make_orchestrator(tmp_path)
        project = _make_project()
        issue = _github_issue(target_branch="release/1.2")

        mock_store = MagicMock()
        mock_store.get.return_value = project
        mock_store.create_worktree.return_value = "/fake/wt"
        orch.project_store = mock_store

        mock_tracker = MagicMock()
        orch._project_trackers["proj-gh"] = mock_tracker

        with patch.object(orch, "_project_epic_strategy", return_value="flat"), \
             patch.object(orch, "_resolve_parent_epic", return_value=None), \
             patch.object(orch, "_sync_issue_task_file_to_workspace"):
            orch._create_workspace_for_issue(issue)

        calls = mock_tracker.set_metadata_field.call_args_list
        target_calls = [
            c for c in calls if c.args[1] == "oompah.target_branch"
        ]
        assert target_calls, "oompah.target_branch should be persisted"
        assert target_calls[0].args[2] == "release/1.2"

    def test_target_branch_not_written_when_none(self, tmp_path):
        """When issue.target_branch is None, skip the target_branch metadata
        write (do not write None or empty string)."""
        orch = _make_orchestrator(tmp_path)
        project = _make_project()
        issue = _github_issue(target_branch=None)

        mock_store = MagicMock()
        mock_store.get.return_value = project
        mock_store.create_worktree.return_value = "/fake/wt"
        orch.project_store = mock_store

        mock_tracker = MagicMock()
        orch._project_trackers["proj-gh"] = mock_tracker

        with patch.object(orch, "_project_epic_strategy", return_value="flat"), \
             patch.object(orch, "_resolve_parent_epic", return_value=None), \
             patch.object(orch, "_sync_issue_task_file_to_workspace"):
            orch._create_workspace_for_issue(issue)

        calls = mock_tracker.set_metadata_field.call_args_list
        target_calls = [
            c for c in calls if c.args[1] == "oompah.target_branch"
        ]
        assert not target_calls, (
            "oompah.target_branch must NOT be written when issue.target_branch is None"
        )

    def test_metadata_failure_does_not_abort_worktree_creation(self, tmp_path):
        """A failed set_metadata_field must not prevent worktree creation —
        the error is logged and silently swallowed."""
        orch = _make_orchestrator(tmp_path)
        project = _make_project()
        issue = _github_issue()

        mock_store = MagicMock()
        mock_store.get.return_value = project
        mock_store.create_worktree.return_value = "/fake/wt"
        orch.project_store = mock_store

        mock_tracker = MagicMock()
        mock_tracker.set_metadata_field.side_effect = RuntimeError("API down")
        orch._project_trackers["proj-gh"] = mock_tracker

        with patch.object(orch, "_project_epic_strategy", return_value="flat"), \
             patch.object(orch, "_resolve_parent_epic", return_value=None), \
             patch.object(orch, "_sync_issue_task_file_to_workspace"):
            # Must NOT raise even though set_metadata_field raised.
            wp, _epic = orch._create_workspace_for_issue(issue)

        assert wp == "/fake/wt"
        mock_store.create_worktree.assert_called_once()

    def test_backlog_issue_does_not_write_metadata(self, tmp_path):
        """Backlog-backed tasks must not attempt to write GitHub metadata."""
        orch = _make_orchestrator(tmp_path)
        issue = _backlog_issue()
        project = _make_project(project_id="proj-bl")

        mock_store = MagicMock()
        mock_store.get.return_value = project
        mock_store.create_worktree.return_value = "/fake/wt"
        orch.project_store = mock_store

        mock_tracker = MagicMock()
        orch._project_trackers["proj-bl"] = mock_tracker

        with patch.object(orch, "_project_epic_strategy", return_value="flat"), \
             patch.object(orch, "_resolve_parent_epic", return_value=None), \
             patch.object(orch, "_sync_issue_task_file_to_workspace"):
            orch._create_workspace_for_issue(issue)

        mock_tracker.set_metadata_field.assert_not_called()
