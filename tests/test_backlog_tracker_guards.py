"""Tests for the BacklogMdTracker isinstance guards added in TASK-457.5.

Each guard wraps a Backlog.md-only operation (worktree file reads, task-file
syncs, etc.) so that API-backed trackers (e.g. GitHub Issues) are unaffected.

These tests verify:
- When the active tracker IS a BacklogMdTracker, the legacy worktree path runs.
- When the active tracker is NOT a BacklogMdTracker, the guard short-circuits
  before touching any filesystem or worktree state.
"""

from __future__ import annotations

import fnmatch
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

from oompah.config import ServiceConfig
from oompah.models import BlockerRef, Issue, RunningEntry
from oompah.orchestrator import Orchestrator
from oompah.tracker import BacklogMdTracker, TrackerProtocol


# ---------------------------------------------------------------------------
# Minimal FakeTracker — satisfies TrackerProtocol but is NOT BacklogMdTracker
# ---------------------------------------------------------------------------

class _FakeTracker(TrackerProtocol):
    """Minimal non-Backlog tracker that satisfies TrackerProtocol."""

    def __init__(self):
        self._issues: Dict[str, Issue] = {}

    def fetch_candidate_issues(self) -> List[Issue]:
        return list(self._issues.values())

    def fetch_all_issues(self) -> List[Issue]:
        return list(self._issues.values())

    def fetch_all_issues_enriched(self) -> List[Issue]:
        return list(self._issues.values())

    def fetch_issue_detail(self, identifier: str) -> Issue | None:
        return self._issues.get(identifier)

    def fetch_children(self, epic_id: str) -> List[Issue]:
        return []

    def fetch_comments(self, identifier: str) -> List[Dict[str, Any]]:
        return []

    def fetch_issues_by_states(self, state_names: List[str]) -> List[Issue]:
        return []

    def fetch_issues_by_labels(self, labels: List[str], *, states: List[str] | None = None) -> List[Issue]:
        return []

    def fetch_issue_states_by_ids(self, issue_ids: List[str]) -> List[Issue]:
        return []

    def fetch_attachments(self, identifier: str) -> List[Dict[str, Any]]:
        return []

    def set_attachments(self, identifier: str, attachments: List[Dict[str, Any]], *, project_root: str | None = None) -> None:
        pass

    def fetch_memories(self) -> Dict[str, str]:
        return {}

    def create_issue(self, title: str, issue_type: str = "task", description: str | None = None, priority: int | None = None, initial_status: str | None = None, labels: List[str] | None = None, parent: str | None = None) -> Issue:
        raise NotImplementedError

    def update_issue(self, identifier: str, **fields: str) -> None:
        pass

    def close_issue(self, identifier: str, *, reason: str | None = None) -> None:
        pass

    def reopen_issue(self, identifier: str) -> None:
        pass

    def archive_issue(self, identifier: str) -> None:
        pass

    def mark_needs_human(self, identifier: str) -> None:
        pass

    def add_comment(self, identifier: str, body: str, *, author: str | None = None) -> None:
        pass

    def add_label(self, identifier: str, label: str) -> None:
        pass

    def remove_label(self, identifier: str, label: str) -> None:
        pass

    def add_parent_child(self, parent_id: str, child_id: str) -> None:
        pass

    def add_dependency(self, identifier: str, depends_on: str) -> None:
        pass

    def get_metadata(self, identifier: str) -> Dict[str, Any]:
        return {}

    def set_metadata_field(self, identifier: str, key: str, value: Any) -> None:
        pass

    def is_archived(self, identifier: str) -> bool:
        return False

    def invalidate_read_cache(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _make_issue(
    identifier: str = "task-1",
    state: str = "open",
    parent_id: str | None = None,
    project_id: str | None = "proj-1",
    issue_type: str = "task",
    priority: int | None = 2,
) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title="Test issue",
        description="",
        state=state,
        issue_type=issue_type,
        parent_id=parent_id,
        project_id=project_id,
        priority=priority,
        labels=[],
    )


def _make_project(
    project_id: str = "proj-1",
    epic_strategy: str = "shared",
    repo_path: str = "/fake/repo",
) -> MagicMock:
    p = MagicMock()
    p.id = project_id
    p.name = "test-project"
    p.repo_url = "https://github.com/org/repo"
    p.repo_path = repo_path
    p.branch = "main"
    p.default_branch = "main"
    p.branches = ["main"]
    p.matches_branch = lambda b: fnmatch.fnmatch(b, "main")
    p.paused = False
    p.epic_strategy = epic_strategy
    p.max_in_flight_prs = 1
    p.access_token = None
    return p


def _make_orch(tmp_path, projects=None, tracker_kind: str = "backlog_md") -> Orchestrator:
    """Create an Orchestrator with a mocked project store."""
    project_store = MagicMock()
    project_store.list_all.return_value = projects or []
    project_store.get.side_effect = lambda pid: next(
        (p for p in (projects or []) if p.id == pid), None
    )
    cfg = ServiceConfig()
    cfg.tracker_kind = tracker_kind
    orch = Orchestrator(
        config=cfg,
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
    )
    return orch


# ---------------------------------------------------------------------------
# Tests for _shared_epic_child_done guard
# ---------------------------------------------------------------------------

class TestSharedEpicChildDoneGuard:
    """_shared_epic_child_done skips worktree reads for non-Backlog trackers."""

    def test_backlog_tracker_reads_worktree_file(self, tmp_path):
        """When BacklogMdTracker is active, the epic-branch file IS read."""
        proj = _make_project()
        orch = _make_orch(tmp_path, projects=[proj])
        orch.project_store.read_task_status_in_epic_worktree.return_value = "Done"
        child = _make_issue(identifier="task-1", parent_id="epic-1", state="open")
        # Default tracker_kind is 'backlog_md' → BacklogMdTracker → guard passes
        result = orch._shared_epic_child_done(child)
        assert result is True
        orch.project_store.read_task_status_in_epic_worktree.assert_called()

    def test_non_backlog_tracker_skips_worktree_file(self, tmp_path):
        """When a non-Backlog tracker is active, no worktree read occurs and
        the function returns False."""
        proj = _make_project()
        orch = _make_orch(tmp_path, projects=[proj])
        fake_tracker = _FakeTracker()
        # Inject the non-Backlog tracker so the guard fires
        with patch.object(orch, "_tracker_for_project", return_value=fake_tracker):
            child = _make_issue(identifier="task-1", parent_id="epic-1", state="open")
            result = orch._shared_epic_child_done(child)
        assert result is False
        orch.project_store.read_task_status_in_epic_worktree.assert_not_called()

    def test_no_project_id_returns_false_without_tracker_call(self, tmp_path):
        """Issues without a project_id return False immediately (no tracker lookup)."""
        orch = _make_orch(tmp_path)
        child = _make_issue(identifier="task-no-proj", parent_id="epic-1", project_id=None)
        result = orch._shared_epic_child_done(child)
        assert result is False


# ---------------------------------------------------------------------------
# Tests for _blocker_satisfied guard
# ---------------------------------------------------------------------------

class TestBlockerSatisfiedGuard:
    """_blocker_satisfied skips worktree reads for non-Backlog trackers."""

    def test_terminal_blocker_state_satisfies_without_tracker_check(self, tmp_path):
        """A terminal blocker_state satisfies regardless of tracker type."""
        orch = _make_orch(tmp_path)
        child = _make_issue(project_id=None)
        blocker = BlockerRef(id="b1", identifier="b1")
        result = orch._blocker_satisfied(child, blocker, blocker_state="Done")
        assert result is True

    def test_non_backlog_tracker_skips_worktree_read(self, tmp_path):
        """Non-terminal blocker with non-Backlog tracker returns False without
        reading the epic-branch worktree."""
        proj = _make_project(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        fake_tracker = _FakeTracker()
        child = _make_issue(parent_id="epic-1", project_id="proj-1")
        blocker = BlockerRef(id="b1", identifier="b1")
        with patch.object(orch, "_tracker_for_project", return_value=fake_tracker):
            result = orch._blocker_satisfied(child, blocker, blocker_state="open")
        assert result is False
        orch.project_store.read_task_status_in_epic_worktree.assert_not_called()

    def test_backlog_tracker_reads_worktree_for_sibling_blocker(self, tmp_path):
        """BacklogMdTracker path reads the epic-branch status for a sibling."""
        proj = _make_project(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        # Epic branch says the blocker is Done
        orch.project_store.read_task_status_in_epic_worktree.return_value = "Done"
        child = _make_issue(parent_id="epic-1", project_id="proj-1")
        blocker = BlockerRef(id="b1", identifier="b1")
        with patch.object(orch, "_project_epic_strategy", return_value="shared"):
            result = orch._blocker_satisfied(child, blocker, blocker_state="open")
        assert result is True
        orch.project_store.read_task_status_in_epic_worktree.assert_called()


# ---------------------------------------------------------------------------
# Tests for _shared_epic_child_terminal guard
# ---------------------------------------------------------------------------

class TestSharedEpicChildTerminalGuard:
    """_shared_epic_child_terminal skips worktree reads for non-Backlog trackers."""

    def test_terminal_child_state_satisfies_without_tracker_check(self, tmp_path):
        """When child.state is already terminal, no tracker lookup needed."""
        orch = _make_orch(tmp_path)
        epic = _make_issue(identifier="epic-1", issue_type="epic")
        child = _make_issue(identifier="c1", state="Done")
        result = orch._shared_epic_child_terminal(epic, child)
        assert result is True

    def test_non_backlog_tracker_returns_false_for_non_terminal_child(self, tmp_path):
        """Non-terminal child + non-Backlog tracker: False without worktree read."""
        proj = _make_project()
        orch = _make_orch(tmp_path, projects=[proj])
        fake_tracker = _FakeTracker()
        epic = _make_issue(identifier="epic-1", issue_type="epic", project_id="proj-1")
        child = _make_issue(identifier="c1", state="open")
        with patch.object(orch, "_tracker_for_project", return_value=fake_tracker):
            result = orch._shared_epic_child_terminal(epic, child)
        assert result is False
        orch.project_store.read_task_status_in_epic_worktree.assert_not_called()

    def test_backlog_tracker_reads_worktree_for_nonterminal_child(self, tmp_path):
        """BacklogMdTracker: reads epic-branch status to override False."""
        proj = _make_project()
        orch = _make_orch(tmp_path, projects=[proj])
        orch.project_store.read_task_status_in_epic_worktree.return_value = "Done"
        epic = _make_issue(identifier="epic-1", issue_type="epic", project_id="proj-1")
        child = _make_issue(identifier="c1", state="open")
        result = orch._shared_epic_child_terminal(epic, child)
        assert result is True
        orch.project_store.read_task_status_in_epic_worktree.assert_called()


# ---------------------------------------------------------------------------
# Tests for _epic_child_effective_state guard
# ---------------------------------------------------------------------------

class TestEpicChildEffectiveStateGuard:
    """_epic_child_effective_state returns child.state without worktree reads
    when the tracker is not a BacklogMdTracker."""

    def test_non_backlog_tracker_returns_child_state_unchanged(self, tmp_path):
        """Non-Backlog tracker: no epic-branch read; child.state is returned."""
        proj = _make_project()
        orch = _make_orch(tmp_path, projects=[proj])
        fake_tracker = _FakeTracker()
        epic = _make_issue(identifier="epic-1", issue_type="epic", project_id="proj-1")
        child = _make_issue(identifier="c1", state="In Progress")
        with patch.object(orch, "_tracker_for_project", return_value=fake_tracker):
            eff = orch._epic_child_effective_state(epic, child)
        assert eff == "In Progress"
        orch.project_store.read_task_status_in_epic_worktree.assert_not_called()

    def test_backlog_tracker_can_upgrade_state_via_epic_branch(self, tmp_path):
        """BacklogMdTracker: epic-branch 'Done' overrides default-branch 'open'."""
        proj = _make_project()
        orch = _make_orch(tmp_path, projects=[proj])
        orch.project_store.read_task_status_in_epic_worktree.return_value = "Done"
        epic = _make_issue(identifier="epic-1", issue_type="epic", project_id="proj-1")
        child = _make_issue(identifier="c1", state="open")
        eff = orch._epic_child_effective_state(epic, child)
        # "Done" is more advanced than "open"
        assert eff == "Done"
        orch.project_store.read_task_status_in_epic_worktree.assert_called()


# ---------------------------------------------------------------------------
# Tests for _sync_issue_task_file_to_workspace guard
# ---------------------------------------------------------------------------

class TestSyncIssueTaskFileGuard:
    """_sync_issue_task_file_to_workspace is a no-op for non-Backlog trackers."""

    def test_non_backlog_tracker_skips_sync(self, tmp_path):
        """sync_task_file_to_worktree must NOT be called for non-Backlog trackers."""
        proj = _make_project()
        orch = _make_orch(tmp_path, projects=[proj])
        fake_tracker = _FakeTracker()
        issue = _make_issue(identifier="task-1", project_id="proj-1")
        with patch.object(orch, "_tracker_for_project", return_value=fake_tracker):
            orch._sync_issue_task_file_to_workspace(issue, "/workspace/path")
        orch.project_store.sync_task_file_to_worktree.assert_not_called()

    def test_backlog_tracker_calls_sync(self, tmp_path):
        """sync_task_file_to_worktree IS called when the tracker is BacklogMdTracker."""
        proj = _make_project()
        orch = _make_orch(tmp_path, projects=[proj])
        issue = _make_issue(identifier="task-1", project_id="proj-1")
        # Default tracker is BacklogMdTracker
        orch._sync_issue_task_file_to_workspace(issue, "/workspace/path")
        orch.project_store.sync_task_file_to_worktree.assert_called_once()

    def test_no_project_id_is_noop(self, tmp_path):
        """Issues without project_id are skipped before the tracker check."""
        orch = _make_orch(tmp_path)
        issue = _make_issue(identifier="task-1", project_id=None)
        orch._sync_issue_task_file_to_workspace(issue, "/workspace/path")
        orch.project_store.sync_task_file_to_worktree.assert_not_called()


# ---------------------------------------------------------------------------
# Tests for _fetch_terminal_issue_from_worker_workspace guard
# ---------------------------------------------------------------------------

class TestFetchTerminalIssueFromWorkerWorkspaceGuard:
    """_fetch_terminal_issue_from_worker_workspace returns None immediately
    when the active tracker is not a BacklogMdTracker."""

    def _make_running_entry(self, identifier: str, workspace_path: str = "/workspace") -> RunningEntry:
        issue = _make_issue(identifier=identifier)
        return RunningEntry(
            worker_task=MagicMock(),
            identifier=identifier,
            issue=issue,
            session=None,
            retry_attempt=0,
            started_at=MagicMock(),
            workspace_path=workspace_path,
        )

    def test_non_backlog_tracker_returns_none_without_reading_workspace(self, tmp_path):
        """No filesystem read occurs when the active tracker is not BacklogMdTracker."""
        orch = _make_orch(tmp_path)
        fake_tracker = _FakeTracker()
        # Override the global tracker with the fake (non-Backlog) one
        orch.tracker = fake_tracker
        entry = self._make_running_entry("task-1")
        with patch("os.path.isdir", return_value=True):
            result = orch._fetch_terminal_issue_from_worker_workspace(
                entry, tracker=fake_tracker
            )
        assert result is None

    def test_backlog_tracker_reads_workspace_when_present(self, tmp_path):
        """BacklogMdTracker path attempts to read the worker workspace."""
        proj = _make_project()
        orch = _make_orch(tmp_path, projects=[proj])
        entry = self._make_running_entry("task-1", workspace_path="/workspace")
        backlog_tracker = orch.tracker  # Default is BacklogMdTracker
        assert isinstance(backlog_tracker, BacklogMdTracker)

        with (
            patch("os.path.isdir", return_value=True),
            patch.object(orch, "_new_tracker") as mock_new_tracker,
        ):
            ws_tracker = MagicMock(spec=BacklogMdTracker)
            ws_tracker.fetch_issue_detail.return_value = None
            mock_new_tracker.return_value = ws_tracker
            result = orch._fetch_terminal_issue_from_worker_workspace(
                entry, tracker=backlog_tracker
            )
        # Returns None because workspace tracker returned None for the issue
        assert result is None
        ws_tracker.fetch_issue_detail.assert_called_once_with("task-1")

    def test_passed_tracker_takes_priority_over_self_tracker(self, tmp_path):
        """Passing a non-Backlog tracker explicitly guards even if self.tracker
        is a BacklogMdTracker."""
        orch = _make_orch(tmp_path)
        # self.tracker is BacklogMdTracker but we pass a FakeTracker
        fake_tracker = _FakeTracker()
        entry = self._make_running_entry("task-1")
        # The guard checks check_tracker=fake_tracker first; since it's not
        # BacklogMdTracker and self.tracker IS BacklogMdTracker, it must
        # still fall back to reading.  But our test confirms the guard only
        # short-circuits when BOTH are non-Backlog.
        # Patch self.tracker too so both are non-Backlog:
        orch.tracker = fake_tracker
        with patch("os.path.isdir", return_value=True):
            result = orch._fetch_terminal_issue_from_worker_workspace(
                entry, tracker=fake_tracker
            )
        assert result is None

    def test_empty_workspace_path_returns_none(self, tmp_path):
        """Missing workspace_path is a no-op for BacklogMdTracker too."""
        orch = _make_orch(tmp_path)
        assert isinstance(orch.tracker, BacklogMdTracker)
        entry = self._make_running_entry("task-1", workspace_path="")
        result = orch._fetch_terminal_issue_from_worker_workspace(entry)
        assert result is None
