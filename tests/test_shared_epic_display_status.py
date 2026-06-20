"""Tests for _effective_display_status.

The board now displays the canonical tracker state directly. It no longer
reads task files from epic-scoped worktrees.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from oompah.models import Issue
from oompah.server import _effective_display_status


def _issue(**kw) -> Issue:
    base = dict(
        id=kw.get("identifier", "TASK-1"),
        identifier=kw.get("identifier", "TASK-1"),
        title="t",
        description="d",
        state=kw.pop("state", "Open"),
        issue_type="task",
        parent_id=kw.pop("parent_id", None),
        project_id=kw.pop("project_id", "proj-1"),
    )
    base.update({k: v for k, v in kw.items() if k not in ("identifier",)})
    return Issue(**base)


def _orch(*, strategy="shared", epic_status=None, raises=False):
    orch = MagicMock()
    orch._project_epic_strategy.return_value = strategy
    if raises:
        orch.project_store.read_task_status_in_epic_worktree.side_effect = RuntimeError("boom")
    else:
        orch.project_store.read_task_status_in_epic_worktree.return_value = epic_status
    return orch


def test_done_on_epic_branch_does_not_override_tracker_state():
    issue = _issue(identifier="TASK-706.1", parent_id="TASK-706", state="Open")
    orch = _orch(epic_status="Done")
    assert _effective_display_status(orch, issue) == "Open"
    orch.project_store.read_task_status_in_epic_worktree.assert_not_called()


def test_merged_on_main_with_stale_branch_keeps_merged():
    # e.g. 706.6: Merged in the tracker, stale state on the epic branch.
    issue = _issue(identifier="TASK-706.6", parent_id="TASK-706", state="Merged")
    orch = _orch(epic_status="Backlog")
    assert _effective_display_status(orch, issue) == "Merged"
    orch.project_store.read_task_status_in_epic_worktree.assert_not_called()


def test_in_progress_on_branch_does_not_override_tracker_state():
    issue = _issue(identifier="TASK-706.7", parent_id="TASK-706", state="Open")
    orch = _orch(epic_status="In Progress")
    assert _effective_display_status(orch, issue) == "Open"
    orch.project_store.read_task_status_in_epic_worktree.assert_not_called()


def test_manual_open_not_reverted_when_epic_branch_behind():
    # Operator moved Backlog->Open in the tracker; stale branch state must
    # not mask or revert the move.
    issue = _issue(identifier="TASK-270.3", parent_id="TASK-270", state="Open")
    orch = _orch(epic_status="Backlog")
    assert _effective_display_status(orch, issue) == "Open"
    orch.project_store.read_task_status_in_epic_worktree.assert_not_called()


def test_tie_keeps_default_branch():
    issue = _issue(identifier="TASK-270.4", parent_id="TASK-270", state="In Progress")
    orch = _orch(epic_status="In Progress")
    assert _effective_display_status(orch, issue) == "In Progress"
    orch.project_store.read_task_status_in_epic_worktree.assert_not_called()


def test_non_child_issue_unchanged():
    issue = _issue(identifier="TASK-258", parent_id=None, state="Backlog")
    orch = _orch(epic_status="Done")
    assert _effective_display_status(orch, issue) == "Backlog"
    orch.project_store.read_task_status_in_epic_worktree.assert_not_called()


def test_non_shared_project_unchanged():
    issue = _issue(identifier="TASK-9.1", parent_id="TASK-9", state="Open")
    orch = _orch(strategy="flat", epic_status="Done")
    assert _effective_display_status(orch, issue) == "Open"


def test_absent_on_epic_branch_falls_back_to_main():
    issue = _issue(identifier="TASK-706.7", parent_id="TASK-706", state="Open")
    orch = _orch(epic_status=None)  # not in the epic worktree
    assert _effective_display_status(orch, issue) == "Open"
    orch.project_store.read_task_status_in_epic_worktree.assert_not_called()


def test_lookup_error_falls_back_to_main():
    issue = _issue(identifier="TASK-706.1", parent_id="TASK-706", state="Open")
    orch = _orch(raises=True)
    assert _effective_display_status(orch, issue) == "Open"
    orch.project_store.read_task_status_in_epic_worktree.assert_not_called()
