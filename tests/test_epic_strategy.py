"""Tests for the shared-only epic workflow.

Covers Project model (default + round-trip + legacy migration to shared),
ProjectStore update validation, the epic worktree helpers, the orchestrator
dispatch gating (shared mode), the worktree allocation helper, and the
epic→default-branch rollup PR creation.
"""

from __future__ import annotations

import fnmatch
import subprocess
from unittest.mock import MagicMock, patch, call

import pytest

from oompah.config import ServiceConfig
from oompah.models import BlockerRef, Issue, Project, RunningEntry
from oompah.orchestrator import Orchestrator
from oompah.projects import ProjectError, ProjectStore
from oompah.scm import ReviewRequest
from oompah.statuses import (
    DONE,
    IN_PROGRESS,
    IN_REVIEW,
    MERGED,
    NEEDS_CI_FIX,
    NEEDS_HUMAN,
    NEEDS_REBASE,
    OPEN,
)


# --------------------------------------------------------------------- helpers


def _make_issue(
    identifier: str = "task-1",
    title: str = "test issue",
    description: str = "body",
    state: str = "open",
    issue_type: str = "task",
    parent_id: str | None = None,
    project_id: str | None = "proj-1",
    priority: int | None = 2,
    labels: list[str] | None = None,
    work_branch: str | None = None,
    review_url: str | None = None,
    review_number: str | None = None,
) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=title,
        description=description,
        state=state,
        issue_type=issue_type,
        parent_id=parent_id,
        project_id=project_id,
        priority=priority,
        labels=labels or [],
        work_branch=work_branch,
        review_url=review_url,
        review_number=review_number,
    )


def _make_project_record(
    project_id: str = "proj-1",
    epic_strategy: str = "flat",
    paused: bool = False,
    name: str = "test-project",
) -> MagicMock:
    p = MagicMock()
    p.id = project_id
    p.name = name
    p.repo_url = "https://github.com/org/repo"
    p.repo_path = "/tmp/repo"
    p.branch = "main"
    p.default_branch = "main"
    p.branches = ["main"]
    p.tracker_kind = "oompah_md"
    p.matches_branch = lambda b: fnmatch.fnmatch(b, "main")
    p.paused = paused
    p.epic_strategy = epic_strategy
    p.require_epic_for_tasks = False
    p.max_in_flight_prs = 1
    p.access_token = None
    return p


def _make_orch(tmp_path, projects=None):
    project_store = MagicMock()
    project_store.list_all.return_value = projects or []
    project_store.get.side_effect = lambda pid: next(
        (p for p in (projects or []) if p.id == pid), None
    )
    project_store.epic_branch_name.side_effect = lambda epic_id: (
        f"epic-{epic_id.replace('/', '_')}"
    )
    orch = Orchestrator(
        config=ServiceConfig(tracker_kind="oompah_md"),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
    )
    return orch


# ----------------------------------------------------- Project model + storage


class TestProjectEpicStrategyField:
    def test_default_is_shared(self):
        # Default for newly-constructed Project objects is "shared" — the only
        # supported epic strategy.  "flat" and "stacked" have been removed.
        p = Project(id="p", name="n", repo_url="u", repo_path="/tmp/x")
        assert p.epic_strategy == "shared"

    def test_to_dict_includes_default(self):
        p = Project(id="p", name="n", repo_url="u", repo_path="/tmp/x")
        d = p.to_dict()
        assert d["epic_strategy"] == "shared"
        assert d["require_epic_for_tasks"] is False

    def test_to_dict_round_trip(self):
        p = Project(
            id="p",
            name="n",
            repo_url="u",
            repo_path="/tmp/x",
            epic_strategy="shared",
            require_epic_for_tasks=True,
        )
        d = p.to_dict()
        assert d["epic_strategy"] == "shared"
        assert d["require_epic_for_tasks"] is True
        p2 = Project.from_dict(d)
        assert p2.epic_strategy == "shared"
        assert p2.require_epic_for_tasks is True

    def test_from_dict_back_compat_when_missing(self):
        # Existing projects.json without the field → defaults to "shared"
        # (migration: field was absent on pre-strategy projects).
        d = {"id": "p", "name": "n", "repo_url": "u", "repo_path": "/tmp/x"}
        p = Project.from_dict(d)
        assert p.epic_strategy == "shared"
        assert p.require_epic_for_tasks is False

    def test_from_dict_legacy_flat_migrates_to_shared(self):
        # Load migration: persisted "flat" is normalized to "shared".
        d = {
            "id": "p",
            "name": "n",
            "repo_url": "u",
            "repo_path": "/tmp/x",
            "epic_strategy": "flat",
        }
        p = Project.from_dict(d)
        assert p.epic_strategy == "shared"

    def test_from_dict_legacy_stacked_migrates_to_shared(self):
        # Load migration: persisted "stacked" is normalized to "shared".
        d = {
            "id": "p",
            "name": "n",
            "repo_url": "u",
            "repo_path": "/tmp/x",
            "epic_strategy": "stacked",
        }
        p = Project.from_dict(d)
        assert p.epic_strategy == "shared"

    def test_from_dict_unknown_value_normalizes_to_shared(self):
        # Unknown/invalid persisted values are normalized to "shared".
        d = {
            "id": "p",
            "name": "n",
            "repo_url": "u",
            "repo_path": "/tmp/x",
            "epic_strategy": "totally-bogus",
        }
        p = Project.from_dict(d)
        assert p.epic_strategy == "shared"

    def test_from_dict_shared_round_trips(self):
        # "shared" is accepted as-is.
        d = {
            "id": "p",
            "name": "n",
            "repo_url": "u",
            "repo_path": "/tmp/x",
            "epic_strategy": "shared",
        }
        p = Project.from_dict(d)
        assert p.epic_strategy == "shared"

    def test_to_dict_after_migration_writes_shared(self):
        # After a legacy record is loaded (flat→shared), to_dict() emits
        # "shared" so the next safe save overwrites the persisted value.
        d_legacy = {
            "id": "p",
            "name": "n",
            "repo_url": "u",
            "repo_path": "/tmp/x",
            "epic_strategy": "stacked",
        }
        p = Project.from_dict(d_legacy)
        d_serialized = p.to_dict()
        assert d_serialized["epic_strategy"] == "shared"


class TestProjectStoreUpdateEpicStrategy:
    def _store(self, tmp_path) -> ProjectStore:
        return ProjectStore(
            path=str(tmp_path / "projects.json"),
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "worktrees"),
        )

    def _seed(self, store: ProjectStore, **kwargs) -> Project:
        p = Project(
            id="p1",
            name="n",
            repo_url="u",
            repo_path="/tmp/x",
            git_user_name="A",
            git_user_email="a@example.com",
            **kwargs,
        )
        store._projects[p.id] = p
        store._save()
        return p

    def test_update_to_stacked_is_rejected(self, tmp_path):
        # "stacked" is no longer a valid epic strategy.
        store = self._store(tmp_path)
        self._seed(store)
        with pytest.raises(ProjectError):
            store.update("p1", epic_strategy="stacked")

    def test_update_to_flat_is_rejected(self, tmp_path):
        # "flat" is no longer a valid epic strategy.
        store = self._store(tmp_path)
        self._seed(store)
        with pytest.raises(ProjectError):
            store.update("p1", epic_strategy="flat")

    def test_update_to_shared(self, tmp_path):
        store = self._store(tmp_path)
        self._seed(store)
        p = store.update("p1", epic_strategy="shared")
        assert p is not None
        assert p.epic_strategy == "shared"

    def test_update_normalizes_case_shared(self, tmp_path):
        # "SHARED" (uppercase) is accepted and normalized.
        store = self._store(tmp_path)
        self._seed(store)
        p = store.update("p1", epic_strategy="SHARED")
        assert p is not None
        assert p.epic_strategy == "shared"

    def test_update_rejects_invalid_string(self, tmp_path):
        store = self._store(tmp_path)
        self._seed(store)
        with pytest.raises(ProjectError):
            store.update("p1", epic_strategy="sideways")

    def test_update_rejects_non_string(self, tmp_path):
        store = self._store(tmp_path)
        self._seed(store)
        with pytest.raises(ProjectError):
            store.update("p1", epic_strategy=42)

    def test_update_none_resets_to_shared(self, tmp_path):
        # None is normalized to "shared" (the only valid value).
        store = self._store(tmp_path)
        self._seed(store, epic_strategy="shared")
        p = store.update("p1", epic_strategy=None)
        assert p is not None
        assert p.epic_strategy == "shared"

    def test_update_require_epic_for_tasks(self, tmp_path):
        store = self._store(tmp_path)
        self._seed(store)
        p = store.update("p1", require_epic_for_tasks=True)
        assert p is not None
        assert p.require_epic_for_tasks is True

    def test_update_require_epic_for_tasks_rejects_non_bool(self, tmp_path):
        store = self._store(tmp_path)
        self._seed(store)
        with pytest.raises(ProjectError):
            store.update("p1", require_epic_for_tasks="true")


class TestUpdatableFieldsIncludesEpicStrategy:
    def test_field_in_allow_list(self):
        assert "epic_strategy" in ProjectStore.UPDATABLE_FIELDS
        assert "require_epic_for_tasks" in ProjectStore.UPDATABLE_FIELDS


class TestEpicWorktreeHelpers:
    def _store(self, tmp_path) -> ProjectStore:
        store = ProjectStore(
            path=str(tmp_path / "projects.json"),
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "worktrees"),
        )
        p = Project(
            id="p1",
            name="my-project",
            repo_url="u",
            repo_path="/tmp/repo",
        )
        store._projects[p.id] = p
        return store

    def test_epic_worktree_path_for_uses_epic_prefix(self, tmp_path):
        store = self._store(tmp_path)
        path = store.epic_worktree_path_for("p1", "epic-007")
        assert path.endswith("/my-project/epic-epic-007")

    def test_epic_branch_name_uses_epic_prefix(self, tmp_path):
        store = self._store(tmp_path)
        assert store.epic_branch_name("epic-007") == "epic-epic-007"

    def test_epic_worktree_path_for_unknown_project_raises(self, tmp_path):
        store = self._store(tmp_path)
        with pytest.raises(ProjectError):
            store.epic_worktree_path_for("nope", "epic-1")


# ---------------------------------------------------------------- orchestrator


class TestProjectEpicStrategyResolution:
    """_project_epic_strategy always returns 'shared' — the only supported mode."""

    def test_default_when_no_project(self, tmp_path):
        orch = _make_orch(tmp_path)
        assert orch._project_epic_strategy(None) == "shared"
        assert orch._project_epic_strategy("missing") == "shared"

    def test_returns_shared_regardless_of_project_field(self, tmp_path):
        # The epic_strategy project field is ignored at the orchestrator layer;
        # only 'shared' mode is supported after OOMPAH-167/168.
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        assert orch._project_epic_strategy("proj-1") == "shared"

    def test_always_returns_shared(self, tmp_path):
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        assert orch._project_epic_strategy("proj-1") == "shared"


class TestResolveParentEpic:
    def test_returns_none_when_no_parent(self, tmp_path):
        orch = _make_orch(tmp_path)
        issue = _make_issue(parent_id=None)
        assert orch._resolve_parent_epic(issue) is None

    def test_returns_none_when_parent_not_epic(self, tmp_path):
        proj = _make_project_record()
        orch = _make_orch(tmp_path, projects=[proj])
        parent = _make_issue(identifier="parent-task", issue_type="task")
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = parent
        with patch.object(orch, "_tracker_for_issue", return_value=tracker):
            child = _make_issue(parent_id="parent-task")
            assert orch._resolve_parent_epic(child) is None

    def test_returns_parent_with_children_in_rollup_project(self, tmp_path):
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        parent = _make_issue(identifier="TASK-738", issue_type="task")
        child = _make_issue(identifier="TASK-738.1", parent_id="TASK-738")
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = parent
        tracker.fetch_children.return_value = [child]
        with patch.object(orch, "_tracker_for_issue", return_value=tracker):
            result = orch._resolve_parent_epic(child)
        assert result is not None
        assert result.identifier == "TASK-738"

    def test_returns_epic_when_parent_is_epic(self, tmp_path):
        proj = _make_project_record()
        orch = _make_orch(tmp_path, projects=[proj])
        epic = _make_issue(identifier="epic-1", issue_type="epic")
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = epic
        with patch.object(orch, "_tracker_for_issue", return_value=tracker):
            child = _make_issue(parent_id="epic-1")
            result = orch._resolve_parent_epic(child)
            assert result is not None
            assert result.identifier == "epic-1"

    def test_returns_none_on_tracker_error(self, tmp_path):
        proj = _make_project_record()
        orch = _make_orch(tmp_path, projects=[proj])
        tracker = MagicMock()
        tracker.fetch_issue_detail.side_effect = Exception("boom")
        with patch.object(orch, "_tracker_for_issue", return_value=tracker):
            child = _make_issue(parent_id="epic-1")
            assert orch._resolve_parent_epic(child) is None


class TestEpicRollupChildStrategy:
    """_epic_rollup_child_strategy: always returns 'shared' for epic children."""

    def test_returns_none_for_non_child_issue(self, tmp_path):
        """Standalone issues (no parent) return None — no rollup strategy."""
        orch = _make_orch(tmp_path)
        issue = _make_issue(identifier="task-1", parent_id=None)
        assert orch._epic_rollup_child_strategy(issue, "proj-1") is None

    def test_returns_none_for_epic_issue_type(self, tmp_path):
        """Epics are rollup parents, not rollup children — they return None."""
        orch = _make_orch(tmp_path)
        issue = _make_issue(identifier="epic-1", issue_type="epic", parent_id="epic-root")
        assert orch._epic_rollup_child_strategy(issue, "proj-1") is None

    def test_returns_shared_for_child_of_epic(self, tmp_path):
        """Any task with a parent epic returns 'shared'."""
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        epic = _make_issue(identifier="epic-1", issue_type="epic")
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = epic
        with patch.object(orch, "_tracker_for_issue", return_value=tracker):
            child = _make_issue(identifier="task-1", parent_id="epic-1", project_id="proj-1")
            result = orch._epic_rollup_child_strategy(child, "proj-1")
        assert result == "shared"

    def test_returns_shared_for_inferred_epic_parent(self, tmp_path):
        """A task with a non-epic parent that has children also returns 'shared'."""
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        parent = _make_issue(identifier="TASK-parent", issue_type="task")
        sibling = _make_issue(identifier="TASK-child", parent_id="TASK-parent")
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = parent
        tracker.fetch_children.return_value = [sibling]
        with patch.object(orch, "_tracker_for_issue", return_value=tracker):
            child = _make_issue(identifier="task-2", parent_id="TASK-parent", project_id="proj-1")
            result = orch._epic_rollup_child_strategy(child, "proj-1")
        assert result == "shared"

    def test_returns_none_when_parent_has_no_children(self, tmp_path):
        """A task whose parent is not an epic and has no children returns None."""
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        parent = _make_issue(identifier="TASK-parent", issue_type="task")
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = parent
        tracker.fetch_children.return_value = []
        with patch.object(orch, "_tracker_for_issue", return_value=tracker):
            child = _make_issue(identifier="task-2", parent_id="TASK-parent", project_id="proj-1")
            result = orch._epic_rollup_child_strategy(child, "proj-1")
        assert result is None


class TestResolveBlockerState:
    def test_prefers_fully_qualified_identifier(self, tmp_path):
        proj = _make_project_record()
        orch = _make_orch(tmp_path, projects=[proj])
        issue = _make_issue(identifier="org/repo#273")
        blocker = BlockerRef(id="272", identifier="org/repo#272")
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = _make_issue(
            identifier="org/repo#272",
            state="Merged",
        )

        with patch.object(orch, "_tracker_for_issue", return_value=tracker):
            state = orch._resolve_blocker_state(blocker, issue)

        assert state == "merged"
        tracker.fetch_issue_detail.assert_called_once_with("org/repo#272")


# --------------------------------------------------------------- dispatch gate


class TestSharedModeDispatchGating:
    """epic_strategy='shared' must allow only 1 in-flight child per epic."""

    def _set_up_running_sibling(self, orch, parent_id: str, sibling_id: str):
        sibling = _make_issue(identifier=sibling_id, parent_id=parent_id)
        entry = RunningEntry(
            worker_task=MagicMock(),
            identifier=sibling_id,
            issue=sibling,
            session=None,
            retry_attempt=0,
            started_at=MagicMock(),
            agent_profile_name="default",
        )
        orch.state.running[sibling.id] = entry

    def test_rejects_rollup_parent_missing_epic_label(self, tmp_path):
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        parent = _make_issue(
            identifier="TASK-738",
            issue_type="task",
            parent_id=None,
            state="open",
            project_id="proj-1",
        )
        child = _make_issue(identifier="TASK-738.1", parent_id="TASK-738")
        with patch.object(orch, "_fetch_epic_children", return_value=[child]):
            assert orch._should_dispatch(parent) is False
        reason, _count = orch.state.reject_streak[parent.id]
        assert reason == "epic_rollup_parent"

    def test_allows_mature_epic_needs_ci_fix_repair(self, tmp_path):
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        epic = _make_issue(
            identifier="TASK-738",
            issue_type="epic",
            state=NEEDS_CI_FIX,
            labels=["ci-fix"],
            work_branch="epic-TASK-738",
        )
        children = [
            _make_issue(identifier="TASK-738.1", state=IN_REVIEW),
            _make_issue(identifier="TASK-738.2", state=MERGED),
        ]

        with patch.object(orch, "_fetch_epic_children", return_value=children):
            assert orch._should_dispatch(epic) is True

    def test_rejects_epic_repair_when_children_not_review_ready(self, tmp_path):
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        epic = _make_issue(
            identifier="TASK-738",
            issue_type="epic",
            state=NEEDS_CI_FIX,
            labels=["ci-fix"],
            work_branch="epic-TASK-738",
        )
        child = _make_issue(identifier="TASK-738.1", state=OPEN)

        with patch.object(orch, "_fetch_epic_children", return_value=[child]):
            assert orch._should_dispatch(epic) is False
        reason, _count = orch.state.reject_streak[epic.id]
        assert reason == "epic"

    def test_allows_mature_inferred_rollup_parent_needs_rebase(self, tmp_path):
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        parent = _make_issue(
            identifier="TASK-738",
            issue_type="feature",
            state=NEEDS_REBASE,
            labels=["merge-conflict"],
            work_branch="epic-TASK-738",
        )
        children = [
            _make_issue(identifier="TASK-738.1", state=IN_REVIEW),
            _make_issue(identifier="TASK-738.2", state=DONE),
        ]

        with patch.object(orch, "_fetch_epic_children", return_value=children):
            assert orch._should_dispatch(parent) is True

    def test_rejects_when_sibling_running_in_shared_mode(self, tmp_path):
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        # Sibling already running on the same epic
        self._set_up_running_sibling(
            orch, parent_id="epic-1", sibling_id="task-running"
        )
        # Now try to dispatch another child of the same epic
        child = _make_issue(identifier="task-2", parent_id="epic-1", state="open")
        # Make _count_open_reviews + per-state checks neutral
        orch._reviews_cache = {}
        assert orch._should_dispatch(child) is False
        # Confirm the rejection reason was the shared-epic-busy gate
        reason, _count = orch.state.reject_streak[child.id]
        assert "shared_epic_busy" in reason

    def test_allows_when_no_sibling_running_in_shared_mode(self, tmp_path):
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        child = _make_issue(identifier="task-only", parent_id="epic-1", state="open")
        orch._reviews_cache = {}
        assert orch._should_dispatch(child) is True

    def test_rejects_top_level_task_when_project_requires_epic_parent(
        self, tmp_path
    ):
        proj = _make_project_record(epic_strategy="shared")
        proj.require_epic_for_tasks = True
        orch = _make_orch(tmp_path, projects=[proj])
        task = _make_issue(identifier="task-only", parent_id=None, state="open")
        orch._reviews_cache = {}
        with patch.object(orch, "_mark_issue_needs_epic_parent") as mark_needs_human:
            assert orch._should_dispatch(task) is False
        mark_needs_human.assert_called_once_with(task, task.project_id)
        reason, _count = orch.state.reject_streak[task.id]
        assert reason == "missing_parent_epic"

    def test_does_not_recomment_when_required_parent_task_already_needs_human(
        self, tmp_path
    ):
        proj = _make_project_record(epic_strategy="shared")
        proj.require_epic_for_tasks = True
        orch = _make_orch(tmp_path, projects=[proj])
        task = _make_issue(identifier="task-only", parent_id=None, state=NEEDS_HUMAN)
        orch._reviews_cache = {}
        with patch.object(orch, "_mark_issue_needs_epic_parent") as mark_needs_human:
            assert orch._should_dispatch(task) is False
        mark_needs_human.assert_not_called()
        reason, _count = orch.state.reject_streak[task.id]
        assert reason == "missing_parent_epic"

    def test_allows_child_task_when_project_requires_epic_parent(self, tmp_path):
        proj = _make_project_record(epic_strategy="shared")
        proj.require_epic_for_tasks = True
        orch = _make_orch(tmp_path, projects=[proj])
        child = _make_issue(identifier="task-only", parent_id="epic-1", state="open")
        epic = _make_issue(identifier="epic-1", issue_type="epic")
        orch._reviews_cache = {}
        with (
            patch.object(orch, "_resolve_parent_epic", return_value=epic),
            patch.object(
                orch.project_store,
                "read_task_status_in_epic_worktree",
                return_value=None,
            ),
        ):
            assert orch._should_dispatch(child) is True

    def test_rejects_child_task_when_required_parent_is_not_epic_rollup(
        self, tmp_path
    ):
        proj = _make_project_record(epic_strategy="shared")
        proj.require_epic_for_tasks = True
        orch = _make_orch(tmp_path, projects=[proj])
        child = _make_issue(identifier="task-only", parent_id="task-parent", state="open")
        orch._reviews_cache = {}
        with (
            patch.object(orch, "_resolve_parent_epic", return_value=None),
            patch.object(orch, "_mark_issue_needs_epic_parent") as mark_needs_human,
        ):
            assert orch._should_dispatch(child) is False
        mark_needs_human.assert_called_once_with(child, child.project_id)
        reason, _count = orch.state.reject_streak[child.id]
        assert reason == "missing_parent_epic"

    def test_removed_epic_branch_status_gate_does_not_block_dispatch(self, tmp_path):
        """Shared-epic dispatch no longer reads task status from epic worktrees."""
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        child = _make_issue(identifier="task-only", parent_id="epic-1", state="open")
        orch._reviews_cache = {}
        with patch.object(
            orch.project_store,
            "read_task_status_in_epic_worktree",
            return_value="Done",
        ):
            assert orch._should_dispatch(child) is True

    def test_allows_when_child_not_done_on_epic_branch(self, tmp_path):
        """A non-terminal (or absent) epic-branch status falls through to
        normal dispatch."""
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        child = _make_issue(identifier="task-only", parent_id="epic-1", state="open")
        orch._reviews_cache = {}
        with patch.object(
            orch.project_store,
            "read_task_status_in_epic_worktree",
            return_value=None,
        ):
            assert orch._should_dispatch(child) is True

    def test_shared_child_stays_blocked_when_default_branch_blocker_open(self, tmp_path):
        """Shared-epic blocker checks use the canonical tracker state."""
        from oompah.models import BlockerRef

        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        orch._reviews_cache = {}
        child = _make_issue(identifier="c2", parent_id="epic-1", state="open")
        child.blocked_by = [BlockerRef(id="c1", identifier="c1")]
        # Epic branch: blocker c1 Done; the child c2 itself not yet done.
        def _epic_status(project_id, epic_id, child_id):
            return "Done" if child_id == "c1" else None
        orch.project_store.read_task_status_in_epic_worktree.side_effect = _epic_status
        with (
            patch.object(orch, "_resolve_blocker_state", return_value="open"),
            patch.object(orch, "_blocker_has_unmerged_pr", return_value=False),
        ):
            assert orch._should_dispatch(child) is False
        reason, _count = orch.state.reject_streak[child.id]
        assert "blocker" in reason

    def test_shared_child_blocked_when_blocker_not_done_on_either_branch(self, tmp_path):
        """If the sibling blocker is non-terminal on BOTH branches, the
        child stays blocked."""
        from oompah.models import BlockerRef

        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        orch._reviews_cache = {}
        child = _make_issue(identifier="c2", parent_id="epic-1", state="open")
        child.blocked_by = [BlockerRef(id="c1", identifier="c1")]
        def _epic_status(project_id, epic_id, child_id):
            return "In Progress" if child_id == "c1" else None
        orch.project_store.read_task_status_in_epic_worktree.side_effect = _epic_status
        with patch.object(orch, "_resolve_blocker_state", return_value="open"):
            assert orch._should_dispatch(child) is False
        reason, _count = orch.state.reject_streak[child.id]
        assert "blocker" in reason

    def test_p0_child_ignores_removed_epic_branch_status_gate(self, tmp_path):
        """The removed epic-branch status gate does not block P0 dispatch."""
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        child = _make_issue(
            identifier="task-p0", parent_id="epic-1", state="open", priority=0
        )
        orch._reviews_cache = {}
        with patch.object(
            orch.project_store,
            "read_task_status_in_epic_worktree",
            return_value="Merged",
        ):
            assert orch._should_dispatch(child) is True

    # Tests for flat/stacked mode dispatch removed — those modes are no longer
    # supported (OOMPAH-168). Only shared mode is active.

    def test_shared_mode_allows_different_epics_in_parallel(self, tmp_path):
        """Multiple epics still dispatch concurrently — only same-epic siblings serialize."""
        proj = _make_project_record(epic_strategy="shared")
        proj.max_in_flight_prs = 5
        orch = _make_orch(tmp_path, projects=[proj])
        # Sibling running on epic-1
        self._set_up_running_sibling(
            orch, parent_id="epic-1", sibling_id="other-running"
        )
        # Child of a *different* epic
        child = _make_issue(identifier="task-x", parent_id="epic-2", state="open")
        orch._reviews_cache = {}
        assert orch._should_dispatch(child) is True

    def test_p0_bypasses_shared_gate(self, tmp_path):
        """P0 issues bypass the per-epic serial cap, matching other gate bypasses."""
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        self._set_up_running_sibling(
            orch, parent_id="epic-1", sibling_id="task-running"
        )
        child = _make_issue(
            identifier="task-p0",
            parent_id="epic-1",
            state="open",
            priority=0,
        )
        orch._reviews_cache = {}
        assert orch._should_dispatch(child) is True

    def test_p0_rebase_task_does_not_bypass_shared_gate(self, tmp_path):
        """Only one rebase worker may touch a shared epic branch at a time."""
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        self._set_up_running_sibling(
            orch, parent_id="TASK-462", sibling_id="TASK-462.7"
        )
        child = _make_issue(
            identifier="TASK-462.8",
            title="Rebase epic-TASK-462 onto main",
            parent_id="TASK-462",
            state="Needs Rebase",
            priority=0,
        )
        orch._reviews_cache = {}

        assert orch._should_dispatch(child) is False
        reason, _count = orch.state.reject_streak[child.id]
        assert "shared_epic_busy=TASK-462" in reason

    def test_select_dispatchable_serializes_shared_siblings_in_same_batch(
        self, tmp_path
    ):
        """Selection must reserve a shared epic before agents start running.

        _should_dispatch() can only see already-running/claimed siblings. When
        _select_dispatchable() builds a ready batch, newly accepted candidates
        are not running yet, so same-epic siblings need a batch-local gate too.
        """
        proj = _make_project_record(epic_strategy="shared")
        proj.max_in_flight_prs = 5
        orch = _make_orch(tmp_path, projects=[proj])
        orch._reviews_cache = {}
        children = [
            _make_issue(
                identifier="task-a",
                title="alpha work",
                parent_id="epic-1",
                state="open",
            ),
            _make_issue(
                identifier="task-b",
                title="beta work",
                parent_id="epic-1",
                state="open",
            ),
        ]

        ready = orch._select_dispatchable(children)

        assert [issue.identifier for issue in ready] == ["task-a"]

    def test_select_dispatchable_allows_different_shared_epics_in_same_batch(
        self, tmp_path
    ):
        proj = _make_project_record(epic_strategy="shared")
        proj.max_in_flight_prs = 5
        orch = _make_orch(tmp_path, projects=[proj])
        orch._reviews_cache = {}
        children = [
            _make_issue(
                identifier="task-a",
                title="alpha work",
                parent_id="epic-1",
                state="open",
            ),
            _make_issue(
                identifier="task-b",
                title="beta work",
                parent_id="epic-2",
                state="open",
            ),
        ]

        ready = orch._select_dispatchable(children)

        assert [issue.identifier for issue in ready] == ["task-a", "task-b"]

    def test_select_dispatchable_serializes_shared_strategy(
        self, tmp_path
    ):
        """Shared mode serializes same-epic siblings — only the first is dispatched."""
        proj = _make_project_record(epic_strategy="shared")
        proj.max_in_flight_prs = 5
        orch = _make_orch(tmp_path, projects=[proj])
        orch._reviews_cache = {}
        children = [
            _make_issue(
                identifier="task-a",
                title="alpha work",
                parent_id="epic-1",
                state="open",
            ),
            _make_issue(
                identifier="task-b",
                title="beta work",
                parent_id="epic-1",
                state="open",
            ),
        ]

        ready = orch._select_dispatchable(children)

        # Only the first sibling is selected; the second is serialized out.
        assert [issue.identifier for issue in ready] == ["task-a"]

    def test_select_dispatchable_keeps_p0_shared_sibling_bypass(self, tmp_path):
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        orch._reviews_cache = {}
        children = [
            _make_issue(
                identifier="task-a",
                title="alpha work",
                parent_id="epic-1",
                state="open",
                priority=0,
            ),
            _make_issue(
                identifier="task-b",
                title="beta work",
                parent_id="epic-1",
                state="open",
                priority=0,
            ),
        ]

        ready = orch._select_dispatchable(children)

        assert [issue.identifier for issue in ready] == ["task-a", "task-b"]

    def test_select_dispatchable_serializes_p0_rebase_siblings(self, tmp_path):
        proj = _make_project_record(epic_strategy="shared")
        proj.max_in_flight_prs = 5
        orch = _make_orch(tmp_path, projects=[proj])
        orch._reviews_cache = {}
        children = [
            _make_issue(
                identifier="TASK-462.7",
                title="Rebase epic-TASK-462 onto main",
                parent_id="TASK-462",
                state="Needs Rebase",
                priority=0,
            ),
            _make_issue(
                identifier="TASK-462.8",
                title="Rebase epic-TASK-462 onto main",
                parent_id="TASK-462",
                state="Needs Rebase",
                priority=0,
            ),
        ]

        ready = orch._select_dispatchable(children)

        assert [issue.identifier for issue in ready] == ["TASK-462.7"]


# ------------------------------------------------------- workspace allocation


class TestWorkspaceAllocation:
    """_create_workspace_for_issue picks per-task vs shared epic worktree."""

    def test_flat_mode_uses_per_task_worktree(self, tmp_path):
        proj = _make_project_record(epic_strategy="flat")
        orch = _make_orch(tmp_path, projects=[proj])
        orch.project_store.create_worktree.return_value = "/wt/per-task"
        orch.project_store.create_epic_worktree.return_value = "/wt/epic"

        issue = _make_issue(parent_id="epic-1", project_id="proj-1")
        wp, epic = orch._create_workspace_for_issue(issue)
        assert wp == "/wt/per-task"
        assert epic is None
        orch.project_store.create_worktree.assert_called_once()
        orch.project_store.create_epic_worktree.assert_not_called()

    def test_per_task_worktree_does_not_sync_task_file(self, tmp_path):
        proj = _make_project_record(epic_strategy="flat")
        orch = _make_orch(tmp_path, projects=[proj])
        orch.project_store.create_worktree.return_value = "/wt/per-task"

        issue = _make_issue(identifier="TASK-389", project_id="proj-1")
        wp, epic = orch._create_workspace_for_issue(issue)

        assert wp == "/wt/per-task"
        assert epic is None
        orch.project_store.sync_task_file_to_worktree.assert_not_called()

    def test_stacked_mode_uses_per_task_worktree(self, tmp_path):
        proj = _make_project_record(epic_strategy="stacked")
        orch = _make_orch(tmp_path, projects=[proj])
        orch.project_store.create_worktree.return_value = "/wt/per-task"
        issue = _make_issue(parent_id="epic-1", project_id="proj-1")
        wp, epic = orch._create_workspace_for_issue(issue)
        assert wp == "/wt/per-task"
        assert epic is None  # stacked still uses per-task worktree
        orch.project_store.create_worktree.assert_called_once()

    def test_shared_mode_uses_shared_epic_worktree(self, tmp_path):
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        orch.project_store.create_epic_worktree.return_value = "/wt/epic-1"
        epic = _make_issue(identifier="epic-1", issue_type="epic")
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = epic
        with patch.object(orch, "_tracker_for_issue", return_value=tracker):
            issue = _make_issue(parent_id="epic-1", project_id="proj-1")
            wp, epic_ret = orch._create_workspace_for_issue(issue)
        assert wp == "/wt/epic-1"
        assert epic_ret is not None
        assert epic_ret.identifier == "epic-1"
        orch.project_store.create_epic_worktree.assert_called_once_with(
            "proj-1",
            "epic-1",
        )
        orch.project_store.create_worktree.assert_not_called()

    def test_shared_mode_uses_shared_worktree_for_parent_with_missing_epic_label(
        self, tmp_path
    ):
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        orch.project_store.create_epic_worktree.return_value = "/wt/epic-TASK-738"
        parent = _make_issue(identifier="TASK-738", issue_type="task")
        child = _make_issue(
            identifier="TASK-738.1",
            parent_id="TASK-738",
            project_id="proj-1",
        )
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = parent
        tracker.fetch_children.return_value = [child]

        with patch.object(orch, "_tracker_for_issue", return_value=tracker):
            wp, epic_ret = orch._create_workspace_for_issue(child)

        assert wp == "/wt/epic-TASK-738"
        assert epic_ret is not None
        assert epic_ret.identifier == "TASK-738"
        orch.project_store.create_epic_worktree.assert_called_once_with(
            "proj-1",
            "TASK-738",
        )
        orch.project_store.create_worktree.assert_not_called()

    def test_shared_epic_worktree_does_not_sync_child_task_file(self, tmp_path):
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        orch.project_store.create_epic_worktree.return_value = "/wt/epic-1"
        epic = _make_issue(identifier="epic-1", issue_type="epic")
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = epic

        with patch.object(orch, "_tracker_for_issue", return_value=tracker):
            issue = _make_issue(
                identifier="TASK-389",
                parent_id="epic-1",
                project_id="proj-1",
            )
            wp, epic_ret = orch._create_workspace_for_issue(issue)

        assert wp == "/wt/epic-1"
        assert epic_ret is not None
        orch.project_store.sync_task_file_to_worktree.assert_not_called()

    def test_shared_mode_top_level_issue_uses_per_task_worktree(self, tmp_path):
        """Top-level issues (no parent) under shared mode get a per-task worktree."""
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        orch.project_store.create_worktree.return_value = "/wt/per-task"
        issue = _make_issue(parent_id=None, project_id="proj-1")
        wp, epic = orch._create_workspace_for_issue(issue)
        assert wp == "/wt/per-task"
        assert epic is None
        orch.project_store.create_worktree.assert_called_once()

    def test_mature_epic_repair_uses_epic_worktree(self, tmp_path):
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        orch.project_store.create_epic_worktree.return_value = "/wt/epic-TASK-738"
        issue = _make_issue(
            identifier="TASK-738",
            issue_type="epic",
            state=NEEDS_CI_FIX,
            labels=["ci-fix"],
            work_branch="epic-TASK-738",
            project_id="proj-1",
        )
        children = [_make_issue(identifier="TASK-738.1", state=IN_REVIEW)]

        with patch.object(orch, "_fetch_epic_children", return_value=children):
            wp, epic = orch._create_workspace_for_issue(issue)

        assert wp == "/wt/epic-TASK-738"
        assert epic is issue
        orch.project_store.create_epic_worktree.assert_called_once_with(
            "proj-1",
            "TASK-738",
        )
        orch.project_store.create_worktree.assert_not_called()


# ------------------------------------------------------------- PR target test


class TestEnsureReviewExistsRespectsEpicStrategy:
    def test_require_epic_parent_blocks_top_level_task_review(self, tmp_path):
        proj = _make_project_record(epic_strategy="shared")
        proj.require_epic_for_tasks = True
        orch = _make_orch(tmp_path, projects=[proj])
        orch._reviews_cache = {"proj-1": []}

        tracker = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=tracker)
        issue = _make_issue(identifier="task-1", parent_id=None, project_id="proj-1")
        entry = RunningEntry(
            worker_task=MagicMock(),
            identifier="task-1",
            issue=issue,
            session=None,
            retry_attempt=0,
            started_at=MagicMock(),
            agent_profile_name="default",
        )

        result = orch._ensure_review_exists(entry, "proj-1")

        assert result is False
        tracker.update_issue.assert_called_once_with("task-1", status=NEEDS_HUMAN)
        tracker.add_comment.assert_called_once()

    def test_require_epic_parent_blocks_unresolved_parent_review(self, tmp_path):
        proj = _make_project_record(epic_strategy="shared")
        proj.require_epic_for_tasks = True
        orch = _make_orch(tmp_path, projects=[proj])
        orch._reviews_cache = {"proj-1": []}

        tracker = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=tracker)
        issue = _make_issue(
            identifier="task-1",
            parent_id="task-parent",
            project_id="proj-1",
        )
        entry = RunningEntry(
            worker_task=MagicMock(),
            identifier="task-1",
            issue=issue,
            session=None,
            retry_attempt=0,
            started_at=MagicMock(),
            agent_profile_name="default",
        )

        with patch.object(orch, "_resolve_parent_epic", return_value=None):
            result = orch._ensure_review_exists(entry, "proj-1")

        assert result is False
        tracker.update_issue.assert_called_once_with("task-1", status=NEEDS_HUMAN)
        tracker.add_comment.assert_called_once()

    def test_flat_creates_pr_targeting_main(self, tmp_path):
        proj = _make_project_record(epic_strategy="flat")
        orch = _make_orch(tmp_path, projects=[proj])
        orch._reviews_cache = {"proj-1": []}

        provider = MagicMock()
        provider.create_review.return_value = MagicMock(id="42")
        tracker = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=tracker)

        issue = _make_issue(
            identifier="task-1", parent_id="epic-1", project_id="proj-1"
        )
        entry = RunningEntry(
            worker_task=MagicMock(),
            identifier="task-1",
            issue=issue,
            session=None,
            retry_attempt=0,
            started_at=MagicMock(),
            agent_profile_name="default",
        )
        with (
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
        ):
            result = orch._ensure_review_exists(entry, "proj-1")
        # base_branch should be project.branch (main), NOT the epic branch
        call = provider.create_review.call_args
        kwargs = call.kwargs
        assert kwargs.get("target_branch") == "main"
        assert result is True
        tracker.update_issue.assert_called_once_with("task-1", status=IN_REVIEW)

    def test_reopens_when_review_creation_fails_for_unmerged_branch(self, tmp_path):
        proj = _make_project_record(epic_strategy="flat")
        orch = _make_orch(tmp_path, projects=[proj])
        orch._reviews_cache = {"proj-1": []}

        provider = MagicMock()
        provider.create_review.return_value = None
        tracker = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch._post_comment = MagicMock()

        issue = _make_issue(identifier="task-1", project_id="proj-1")
        entry = RunningEntry(
            worker_task=MagicMock(),
            identifier="task-1",
            issue=issue,
            session=None,
            retry_attempt=0,
            started_at=MagicMock(),
            agent_profile_name="default",
        )

        with (
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
            patch(
                "oompah.close_gate._count_commits_ahead",
                return_value=(2, ["abc123 feature"], ""),
            ),
        ):
            result = orch._ensure_review_exists(entry, "proj-1")

        assert result is False
        tracker.update_issue.assert_called_once_with("task-1", status=OPEN)
        orch._post_comment.assert_called_once()
        comment = orch._post_comment.call_args.args[1]
        assert "Review handoff failed" in comment
        assert "Unmerged commits: 2 commits" in comment

    def test_defers_review_creation_when_project_at_review_cap(self, tmp_path):
        proj = _make_project_record(epic_strategy="flat")
        proj.max_in_flight_prs = 1
        orch = _make_orch(tmp_path, projects=[proj])
        existing_review = MagicMock()
        existing_review.source_branch = "other-task"
        existing_review.draft = False
        orch._reviews_cache = {"proj-1": [existing_review]}

        provider = MagicMock()
        tracker = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch._post_comment = MagicMock()

        issue = _make_issue(identifier="task-1", project_id="proj-1")
        entry = RunningEntry(
            worker_task=MagicMock(),
            identifier="task-1",
            issue=issue,
            session=None,
            retry_attempt=0,
            started_at=MagicMock(),
            agent_profile_name="default",
        )

        with (
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
            patch(
                "oompah.close_gate._count_commits_ahead",
                return_value=(2, ["abc123 feature"], ""),
            ),
        ):
            result = orch._ensure_review_exists(entry, "proj-1")

        assert result is True
        provider.create_review.assert_not_called()
        tracker.update_issue.assert_called_once_with("task-1", status=DONE)
        orch._post_comment.assert_called_once()
        comment = orch._post_comment.call_args.args[1]
        assert "Review handoff deferred" in comment
        assert "Open reviews: 1/1" in comment

    def test_existing_review_marks_task_in_review(self, tmp_path):
        proj = _make_project_record(epic_strategy="flat")
        orch = _make_orch(tmp_path, projects=[proj])
        review = MagicMock()
        review.source_branch = "task-1"
        review.id = "99"
        orch._reviews_cache = {"proj-1": [review]}
        tracker = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=tracker)

        issue = _make_issue(identifier="task-1", project_id="proj-1")
        entry = RunningEntry(
            worker_task=MagicMock(),
            identifier="task-1",
            issue=issue,
            session=None,
            retry_attempt=0,
            started_at=MagicMock(),
            agent_profile_name="default",
        )

        result = orch._ensure_review_exists(entry, "proj-1")

        assert result is True
        tracker.update_issue.assert_called_once_with("task-1", status=IN_REVIEW)

    def test_shared_skips_per_child_pr(self, tmp_path):
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        orch._reviews_cache = {"proj-1": []}

        provider = MagicMock()
        epic = _make_issue(identifier="epic-1", issue_type="epic")
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = epic
        issue = _make_issue(
            identifier="task-1", parent_id="epic-1", project_id="proj-1"
        )
        entry = RunningEntry(
            worker_task=MagicMock(),
            identifier="task-1",
            issue=issue,
            session=None,
            retry_attempt=0,
            started_at=MagicMock(),
            agent_profile_name="default",
        )
        with (
            patch.object(orch, "_tracker_for_issue", return_value=tracker),
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
        ):
            orch._ensure_review_exists(entry, "proj-1")
        # No per-child PR is created — the epic→main PR is the only one
        provider.create_review.assert_not_called()

    def test_shared_parent_with_children_skips_per_child_pr(self, tmp_path):
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        orch._reviews_cache = {"proj-1": []}

        provider = MagicMock()
        parent = _make_issue(identifier="TASK-738", issue_type="task")
        child = _make_issue(
            identifier="TASK-738.1",
            parent_id="TASK-738",
            project_id="proj-1",
        )
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = parent
        tracker.fetch_children.return_value = [child]
        entry = RunningEntry(
            worker_task=MagicMock(),
            identifier="TASK-738.1",
            issue=child,
            session=None,
            retry_attempt=0,
            started_at=MagicMock(),
            agent_profile_name="default",
        )
        with (
            patch.object(orch, "_tracker_for_issue", return_value=tracker),
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
        ):
            orch._ensure_review_exists(entry, "proj-1")
        provider.create_review.assert_not_called()

    def test_shared_non_epic_parent_creates_per_task_pr(self, tmp_path):
        """Shared mode creates child PRs only when the parent cannot be resolved."""
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        orch._reviews_cache = {"proj-1": []}

        provider = MagicMock()
        provider.create_review.return_value = MagicMock(id="42")
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = None
        orch._tracker_for_project = MagicMock(return_value=tracker)
        issue = _make_issue(
            identifier="task-1", parent_id="epic-1", project_id="proj-1"
        )
        entry = RunningEntry(
            worker_task=MagicMock(),
            identifier="task-1",
            issue=issue,
            session=None,
            retry_attempt=0,
            started_at=MagicMock(),
            agent_profile_name="default",
        )

        with (
            patch.object(orch, "_tracker_for_issue", return_value=tracker),
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
            patch(
                "oompah.close_gate._count_commits_ahead",
                return_value=(2, ["abc123 feature"], ""),
            ),
        ):
            result = orch._ensure_review_exists(entry, "proj-1")

        assert result is True
        tracker.fetch_issue_detail.assert_called_once_with("epic-1")
        provider.create_review.assert_called_once()
        kwargs = provider.create_review.call_args.kwargs
        assert kwargs.get("target_branch") == "main"
        tracker.update_issue.assert_called_once_with("task-1", status=IN_REVIEW)

    def test_stacked_top_level_targets_main(self, tmp_path):
        """Top-level tasks in stacked mode (no parent_id) still target main."""
        proj = _make_project_record(epic_strategy="stacked")
        orch = _make_orch(tmp_path, projects=[proj])
        orch._reviews_cache = {"proj-1": []}

        provider = MagicMock()
        provider.create_review.return_value = MagicMock(id="42")

        issue = _make_issue(identifier="task-1", parent_id=None, project_id="proj-1")
        entry = RunningEntry(
            worker_task=MagicMock(),
            identifier="task-1",
            issue=issue,
            session=None,
            retry_attempt=0,
            started_at=MagicMock(),
            agent_profile_name="default",
        )
        with (
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
        ):
            orch._ensure_review_exists(entry, "proj-1")
        call = provider.create_review.call_args
        kwargs = call.kwargs
        assert kwargs.get("target_branch") == "main"

    def test_task_target_branch_used_when_set(self, tmp_path):
        """Normal task with Issue.target_branch set opens PR into that branch."""
        proj = _make_project_record(epic_strategy="flat")
        orch = _make_orch(tmp_path, projects=[proj])
        orch._reviews_cache = {"proj-1": []}

        provider = MagicMock()
        provider.create_review.return_value = MagicMock(id="42")
        tracker = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=tracker)

        issue = Issue(
            id="task-1",
            identifier="task-1",
            title="My release task",
            description="body",
            state="open",
            issue_type="task",
            project_id="proj-1",
            target_branch="release/1.2",
        )
        entry = RunningEntry(
            worker_task=MagicMock(),
            identifier="task-1",
            issue=issue,
            session=None,
            retry_attempt=0,
            started_at=MagicMock(),
            agent_profile_name="default",
        )
        with (
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
        ):
            result = orch._ensure_review_exists(entry, "proj-1")

        assert result is True
        call = provider.create_review.call_args
        kwargs = call.kwargs
        assert kwargs.get("target_branch") == "release/1.2"

    def test_task_without_target_branch_falls_back_to_project_default(self, tmp_path):
        """Task with no target_branch set falls back to the project default branch."""
        proj = _make_project_record(epic_strategy="flat")
        proj.default_branch = "develop"
        orch = _make_orch(tmp_path, projects=[proj])
        orch._reviews_cache = {"proj-1": []}

        provider = MagicMock()
        provider.create_review.return_value = MagicMock(id="55")
        tracker = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=tracker)

        issue = Issue(
            id="task-2",
            identifier="task-2",
            title="Normal task",
            description="body",
            state="open",
            issue_type="task",
            project_id="proj-1",
            target_branch=None,
        )
        entry = RunningEntry(
            worker_task=MagicMock(),
            identifier="task-2",
            issue=issue,
            session=None,
            retry_attempt=0,
            started_at=MagicMock(),
            agent_profile_name="default",
        )
        with (
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
        ):
            result = orch._ensure_review_exists(entry, "proj-1")

        assert result is True
        call = provider.create_review.call_args
        kwargs = call.kwargs
        assert kwargs.get("target_branch") == "develop"

    def test_release_task_opens_pr_into_release_branch(self, tmp_path):
        """Release tasks (with target_branch=release/X) open PRs into that release branch."""
        proj = _make_project_record(epic_strategy="flat")
        orch = _make_orch(tmp_path, projects=[proj])
        orch._reviews_cache = {"proj-1": []}

        provider = MagicMock()
        provider.create_review.return_value = MagicMock(id="77")
        tracker = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=tracker)

        release_issue = Issue(
            id="TASK-123",
            identifier="TASK-123",
            title="Backport fix for 2.3",
            description="cherry-pick of fix onto 2.3 branch",
            state="open",
            issue_type="task",
            project_id="proj-1",
            target_branch="release/2.3",
        )
        entry = RunningEntry(
            worker_task=MagicMock(),
            identifier="TASK-123",
            issue=release_issue,
            session=None,
            retry_attempt=0,
            started_at=MagicMock(),
            agent_profile_name="default",
        )
        with (
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
        ):
            result = orch._ensure_review_exists(entry, "proj-1")

        assert result is True
        call = provider.create_review.call_args
        kwargs = call.kwargs
        # PR must target the release branch, not main
        assert kwargs.get("target_branch") == "release/2.3"
        assert kwargs.get("target_branch") != "main"


# --------------------------------------------------- epic completion + PR open


class TestOpenEpicMainPrs:
    def _setup(self, tmp_path, *, strategy: str):
        proj = _make_project_record(epic_strategy=strategy)
        orch = _make_orch(tmp_path, projects=[proj])
        orch._reviews_cache = {}
        return orch, proj

    def test_has_epic_landing_ref_uses_shared_worktree(self, tmp_path):
        orch, proj = self._setup(tmp_path, strategy="shared")
        worktree = tmp_path / "epic-worktree"
        worktree.mkdir()
        orch.project_store.epic_branch_name.return_value = "epic-TASK-738"
        orch.project_store.epic_worktree_path_for.return_value = str(worktree)

        assert orch._has_epic_landing_ref(proj, "TASK-738") is True

    def test_has_epic_landing_ref_uses_local_branch(self, tmp_path):
        orch, proj = self._setup(tmp_path, strategy="stacked")
        repo = tmp_path / "repo"
        repo.mkdir()
        proj.repo_path = str(repo)
        orch.project_store.epic_branch_name.return_value = "epic-TASK-738"
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=oompah",
                "-c",
                "user.email=example-org@users.noreply.github.com",
                "commit",
                "--allow-empty",
                "-m",
                "init",
            ],
            cwd=repo,
            check=True,
        )
        subprocess.run(["git", "branch", "epic-TASK-738"], cwd=repo, check=True)

        assert orch._has_epic_landing_ref(proj, "TASK-738") is True

    def test_has_epic_landing_ref_returns_false_without_branch_or_worktree(
        self,
        tmp_path,
    ):
        orch, proj = self._setup(tmp_path, strategy="stacked")
        repo = tmp_path / "repo"
        repo.mkdir()
        proj.repo_path = str(repo)
        orch.project_store.epic_branch_name.return_value = "epic-TASK-738"
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)

        assert orch._has_epic_landing_ref(proj, "TASK-738") is False

    def test_declared_epic_without_landing_ref_opens_no_pr(self, tmp_path):
        orch, proj = self._setup(tmp_path, strategy="shared")
        orch.project_store.epic_branch_name.side_effect = lambda i: f"epic-{i}"
        orch.project_store.read_task_status_in_epic_worktree.return_value = None
        epic = _make_issue(
            identifier="TASK-258",
            issue_type="epic",
            project_id="proj-1",
            state="Backlog",
            title="Legacy epic",
        )
        child = _make_issue(identifier="TASK-258.1", state="Done")
        provider = MagicMock()
        with (
            patch.object(orch, "_fetch_epic_children", return_value=[child]),
            patch.object(orch, "_has_epic_landing_ref", return_value=False),
            patch("oompah.orchestrator.detect_provider", return_value=provider) as detect,
            patch.object(orch, "_push_epic_branch") as push,
        ):
            opened = orch._open_epic_main_prs([epic])
        assert opened == 0
        detect.assert_not_called()
        push.assert_not_called()
        provider.create_review.assert_not_called()

    def test_flat_mode_is_noop(self, tmp_path):
        orch, proj = self._setup(tmp_path, strategy="flat")
        epic = _make_issue(
            identifier="epic-1", issue_type="epic", project_id="proj-1", state="open"
        )
        with (
            patch.object(
                orch, "_fetch_epic_children", return_value=[_make_issue(state="closed")]
            ),
            patch("oompah.orchestrator.detect_provider") as detect_p,
        ):
            opened = orch._open_epic_main_prs([epic])
        assert opened == 0
        detect_p.assert_not_called()

    def test_skips_epic_with_no_children(self, tmp_path):
        orch, proj = self._setup(tmp_path, strategy="stacked")
        epic = _make_issue(
            identifier="epic-1", issue_type="epic", project_id="proj-1", state="open"
        )
        provider = MagicMock()
        with (
            patch.object(orch, "_fetch_epic_children", return_value=[]),
            patch("oompah.orchestrator.detect_provider", return_value=provider),
        ):
            opened = orch._open_epic_main_prs([epic])
        assert opened == 0
        provider.create_review.assert_not_called()

    def test_skips_when_child_not_terminal(self, tmp_path):
        orch, proj = self._setup(tmp_path, strategy="stacked")
        epic = _make_issue(
            identifier="epic-1", issue_type="epic", project_id="proj-1", state="open"
        )
        child_open = _make_issue(identifier="c1", state="open")
        child_closed = _make_issue(identifier="c2", state="closed")
        provider = MagicMock()
        with (
            patch.object(
                orch, "_fetch_epic_children", return_value=[child_open, child_closed]
            ),
            patch("oompah.orchestrator.detect_provider", return_value=provider),
        ):
            opened = orch._open_epic_main_prs([epic])
        assert opened == 0
        provider.create_review.assert_not_called()

    def test_skips_when_epic_already_terminal(self, tmp_path):
        orch, proj = self._setup(tmp_path, strategy="shared")
        epic = _make_issue(
            identifier="epic-1", issue_type="epic", project_id="proj-1", state="Merged"
        )
        provider = MagicMock()
        with (
            patch.object(
                orch, "_fetch_epic_children", return_value=[_make_issue(state="closed")]
            ),
            patch("oompah.orchestrator.detect_provider", return_value=provider),
        ):
            opened = orch._open_epic_main_prs([epic])
        assert opened == 0
        provider.create_review.assert_not_called()

    def test_creates_pr_for_stacked_when_all_children_closed(self, tmp_path):
        orch, proj = self._setup(tmp_path, strategy="stacked")
        orch.project_store.epic_branch_name.side_effect = lambda i: f"epic-{i}"
        epic = _make_issue(
            identifier="epic-1",
            issue_type="epic",
            project_id="proj-1",
            state="open",
            title="Epic feature",
            description="Body of epic",
        )
        child = _make_issue(identifier="c1", state="closed")
        provider = MagicMock()
        provider.create_review.return_value = MagicMock(id="99")
        with (
            patch.object(orch, "_fetch_epic_children", return_value=[child]),
            patch.object(orch, "_has_epic_landing_ref", return_value=True),
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
            patch.object(orch, "_push_epic_branch") as push,
        ):
            opened = orch._open_epic_main_prs([epic])
        assert opened == 1
        push.assert_called_once_with(proj, "epic-1")
        provider.create_review.assert_called_once()
        kwargs = provider.create_review.call_args.kwargs
        assert kwargs.get("target_branch") == "main"
        # source branch was the epic-N branch
        args = provider.create_review.call_args.args
        # signature: (slug, title, source_branch, target_branch=, description=)
        assert args[2] == "epic-epic-1"
        assert "Epic feature" in args[1]

    def test_creates_pr_for_shared_when_all_children_closed(self, tmp_path):
        orch, proj = self._setup(tmp_path, strategy="shared")
        orch.project_store.epic_branch_name.side_effect = lambda i: f"epic-{i}"
        # No epic-branch override → fall back to the child's default-branch
        # state (which is terminal here).
        orch.project_store.read_task_status_in_epic_worktree.return_value = None
        epic = _make_issue(
            identifier="epic-1",
            issue_type="epic",
            project_id="proj-1",
            state="open",
            title="Shared work",
            description="Doc body",
        )
        child = _make_issue(identifier="c1", state="closed")
        provider = MagicMock()
        provider.create_review.return_value = MagicMock(id="100")
        with (
            patch.object(orch, "_fetch_epic_children", return_value=[child]),
            patch.object(orch, "_has_epic_landing_ref", return_value=True),
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
            patch.object(orch, "_push_epic_branch"),
        ):
            opened = orch._open_epic_main_prs([epic])
        assert opened == 1

    def test_epic_pr_uses_explicit_work_branch(self, tmp_path):
        orch, proj = self._setup(tmp_path, strategy="shared")
        orch.project_store.epic_branch_name.side_effect = lambda i: f"epic-{i}"
        orch.project_store.read_task_status_in_epic_worktree.return_value = None
        epic = _make_issue(
            identifier="OVA-1",
            issue_type="epic",
            project_id="proj-1",
            state="open",
            title="Imported epic",
            description="Doc body",
        )
        epic.work_branch = "epic-NVIDIA-dev_ova_3"
        child = _make_issue(identifier="OVA-5", state="closed")
        provider = MagicMock()
        provider.list_merged_branches.return_value = set()
        provider.create_review.return_value = MagicMock(id="100")

        with (
            patch.object(orch, "_fetch_epic_children", return_value=[child]),
            patch.object(orch, "_has_epic_landing_ref", return_value=True),
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
            patch.object(orch, "_push_epic_branch") as push,
        ):
            opened = orch._open_epic_main_prs([epic])

        assert opened == 1
        push.assert_called_once_with(
            proj,
            "OVA-1",
            epic_branch="epic-NVIDIA-dev_ova_3",
        )
        args = provider.create_review.call_args.args
        assert args[2] == "epic-NVIDIA-dev_ova_3"

    def test_shared_waits_when_children_open_on_default_branch(self, tmp_path):
        """Shared epic landing waits for canonical child states."""
        orch, proj = self._setup(tmp_path, strategy="shared")
        orch.project_store.epic_branch_name.side_effect = lambda i: f"epic-{i}"
        # Epic branch says Done for every child...
        orch.project_store.read_task_status_in_epic_worktree.return_value = "Done"
        epic = _make_issue(
            identifier="epic-1", issue_type="epic", project_id="proj-1",
            state="open", title="Shared work", description="Doc body",
        )
        # ...even though the default-branch copies still look Open.
        c1 = _make_issue(identifier="c1", state="open")
        c2 = _make_issue(identifier="c2", state="open")
        provider = MagicMock()
        provider.create_review.return_value = MagicMock(id="101")
        with (
            patch.object(orch, "_fetch_epic_children", return_value=[c1, c2]),
            patch.object(orch, "_has_epic_landing_ref", return_value=True),
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
            patch.object(orch, "_push_epic_branch") as push,
        ):
            opened = orch._open_epic_main_prs([epic])
        assert opened == 0
        push.assert_not_called()
        provider.create_review.assert_not_called()

    def test_shared_waits_when_a_child_not_done_on_either_branch(self, tmp_path):
        """The gate waits when a child is non-terminal on BOTH the default
        branch and the epic branch (genuinely unfinished)."""
        orch, proj = self._setup(tmp_path, strategy="shared")
        orch.project_store.epic_branch_name.side_effect = lambda i: f"epic-{i}"
        # c1 done on the epic branch, c2 still in progress there.
        def _epic_status(project_id, epic_id, child_id):
            return "Done" if child_id == "c1" else "In Progress"
        orch.project_store.read_task_status_in_epic_worktree.side_effect = _epic_status
        epic = _make_issue(
            identifier="epic-1", issue_type="epic", project_id="proj-1", state="open",
        )
        # Both still Open on the default branch; c2 also non-terminal on epic.
        c1 = _make_issue(identifier="c1", state="open")
        c2 = _make_issue(identifier="c2", state="open")
        provider = MagicMock()
        with (
            patch.object(orch, "_fetch_epic_children", return_value=[c1, c2]),
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
            patch.object(orch, "_push_epic_branch") as push,
        ):
            opened = orch._open_epic_main_prs([epic])
        assert opened == 0
        provider.create_review.assert_not_called()
        push.assert_not_called()

    def test_shared_open_child_blocks_landing_even_when_sibling_merged(self, tmp_path):
        """A still-open canonical child blocks shared epic landing."""
        orch, proj = self._setup(tmp_path, strategy="shared")
        orch.project_store.epic_branch_name.side_effect = lambda i: f"epic-{i}"
        # c1: Done on the epic branch (Open on default); c2: Merged on the
        # default branch but stale Backlog on the epic branch.
        def _epic_status(project_id, epic_id, child_id):
            return "Done" if child_id == "c1" else "Backlog"
        orch.project_store.read_task_status_in_epic_worktree.side_effect = _epic_status
        epic = _make_issue(
            identifier="epic-1", issue_type="epic", project_id="proj-1",
            state="open", title="E", description="D",
        )
        c1 = _make_issue(identifier="c1", state="open")
        c2 = _make_issue(identifier="c2", state="merged")
        provider = MagicMock()
        provider.create_review.return_value = MagicMock(id="102")
        with (
            patch.object(orch, "_fetch_epic_children", return_value=[c1, c2]),
            patch.object(orch, "_has_epic_landing_ref", return_value=True),
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
            patch.object(orch, "_push_epic_branch"),
        ):
            opened = orch._open_epic_main_prs([epic])
        assert opened == 0
        provider.create_review.assert_not_called()

    def test_all_non_terminal_epics_includes_backlog_epics(self, tmp_path):
        """The landing-gate pool must include epics in non-dispatch states
        like Backlog and Done (otherwise completed work never lands)."""
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        backlog_epic = _make_issue(identifier="e1", issue_type="epic", state="Backlog")
        open_epic = _make_issue(identifier="e2", issue_type="epic", state="Open")
        done_epic = _make_issue(identifier="e3", issue_type="epic", state="Done")
        merged_epic = _make_issue(identifier="e4", issue_type="epic", state="Merged")
        archived_epic = _make_issue(identifier="e5", issue_type="epic", state="Archived")
        task = _make_issue(identifier="t1", issue_type="task", state="Backlog")
        tracker = MagicMock()
        tracker.fetch_all_issues.return_value = [
            backlog_epic,
            open_epic,
            done_epic,
            merged_epic,
            archived_epic,
            task,
        ]
        with patch.object(orch, "_tracker_for_project", return_value=tracker):
            epics = orch._all_non_terminal_epics()
        idents = {e.identifier for e in epics}
        # Done epics are still waiting for rollup/merge reconciliation.
        assert idents == {"e1", "e2", "e3"}

    def test_all_non_terminal_epics_includes_parent_with_missing_epic_label(
        self, tmp_path
    ):
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        parent = _make_issue(
            identifier="TASK-738",
            issue_type="task",
            state="Backlog",
            project_id="proj-1",
        )
        child = _make_issue(
            identifier="TASK-738.1",
            parent_id="TASK-738",
            state="Done",
            project_id="proj-1",
        )
        unrelated = _make_issue(
            identifier="TASK-999",
            issue_type="task",
            state="Backlog",
            project_id="proj-1",
        )
        tracker = MagicMock()
        tracker.fetch_all_issues.return_value = [parent, child, unrelated]
        with patch.object(orch, "_tracker_for_project", return_value=tracker):
            epics = orch._all_non_terminal_epics()
        assert [issue.identifier for issue in epics] == ["TASK-738"]

    def test_opens_pr_for_parent_with_missing_epic_label(self, tmp_path):
        orch, proj = self._setup(tmp_path, strategy="shared")
        orch.project_store.epic_branch_name.side_effect = lambda i: f"epic-{i}"
        orch.project_store.read_task_status_in_epic_worktree.return_value = "Done"
        parent = _make_issue(
            identifier="TASK-738",
            issue_type="task",
            project_id="proj-1",
            state="Backlog",
            title="Ubuntu package support",
            description="Body",
        )
        child = _make_issue(identifier="TASK-738.1", parent_id="TASK-738", state="Done")
        provider = MagicMock()
        provider.create_review.return_value = MagicMock(id="215")
        with (
            patch.object(orch, "_fetch_epic_children", return_value=[child]),
            patch.object(orch, "_has_epic_landing_ref", return_value=True),
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
            patch.object(orch, "_push_epic_branch") as push,
        ):
            opened = orch._open_epic_main_prs([parent])
        assert opened == 1
        push.assert_called_once_with(proj, "TASK-738")
        args = provider.create_review.call_args.args
        assert args[2] == "epic-TASK-738"

    def test_inferred_parent_without_epic_landing_ref_opens_no_pr(self, tmp_path):
        orch, proj = self._setup(tmp_path, strategy="shared")
        orch.project_store.epic_branch_name.side_effect = lambda i: f"epic-{i}"
        orch.project_store.read_task_status_in_epic_worktree.return_value = "Done"
        parent = _make_issue(
            identifier="TASK-329",
            issue_type="task",
            project_id="proj-1",
            state="Backlog",
            title="Old decomposed feature",
        )
        child = _make_issue(identifier="TASK-351", parent_id="TASK-329", state="Open")
        provider = MagicMock()
        with (
            patch.object(orch, "_fetch_epic_children", return_value=[child]),
            patch.object(orch, "_has_epic_landing_ref", return_value=False),
            patch("oompah.orchestrator.detect_provider", return_value=provider) as detect,
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
            patch.object(orch, "_push_epic_branch") as push,
        ):
            opened = orch._open_epic_main_prs([parent])
        assert opened == 0
        detect.assert_not_called()
        push.assert_not_called()
        provider.create_review.assert_not_called()

    def test_shared_all_children_already_merged_opens_pr(self, tmp_path):
        """Merged children can mean they landed into this epic branch.

        The parent itself is only Merged once its own branch lands into the
        resolved target.
        """
        orch, proj = self._setup(tmp_path, strategy="shared")
        orch.project_store.epic_branch_name.side_effect = lambda i: f"epic-{i}"
        orch.project_store.read_task_status_in_epic_worktree.return_value = None
        epic = _make_issue(
            identifier="epic-1", issue_type="epic", project_id="proj-1", state="open",
        )
        c1 = _make_issue(identifier="c1", state="merged")
        c2 = _make_issue(identifier="c2", state="merged")
        provider = MagicMock()
        provider.list_merged_reviews.return_value = []
        provider.find_pr_for_branch.return_value = None
        provider.create_review.return_value = MagicMock(id="205")
        tracker = MagicMock()
        with (
            patch.object(orch, "_fetch_epic_children", return_value=[c1, c2]),
            patch.object(orch, "_has_epic_landing_ref", return_value=True),
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
            patch.object(orch, "_push_epic_branch") as push,
            patch.object(orch, "_tracker_for_project", return_value=tracker),
            patch.object(orch, "_sync_epic_review_child_states"),
        ):
            opened = orch._open_epic_main_prs([epic])
        assert opened == 1
        provider.create_review.assert_called_once()
        push.assert_called_once()

    def test_idempotent_when_pr_already_exists(self, tmp_path):
        orch, proj = self._setup(tmp_path, strategy="stacked")
        orch.project_store.epic_branch_name.side_effect = lambda i: f"epic-{i}"
        epic = _make_issue(
            identifier="epic-1", issue_type="epic", project_id="proj-1", state="open"
        )
        child = _make_issue(state="closed")
        existing_review = MagicMock()
        existing_review.source_branch = "epic-epic-1"
        existing_review.draft = False
        orch._reviews_cache = {"proj-1": [existing_review]}
        provider = MagicMock()
        with (
            patch.object(orch, "_fetch_epic_children", return_value=[child]),
            patch.object(orch, "_has_epic_landing_ref", return_value=True),
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
            patch.object(orch, "_push_epic_branch") as push,
        ):
            opened = orch._open_epic_main_prs([epic])
        assert opened == 0
        provider.create_review.assert_not_called()
        push.assert_not_called()

    def test_idempotent_when_existing_pr_is_missing_from_cache(self, tmp_path):
        orch, proj = self._setup(tmp_path, strategy="stacked")
        orch.project_store.epic_branch_name.side_effect = lambda i: f"epic-{i}"
        epic = _make_issue(
            identifier="epic-1",
            issue_type="epic",
            project_id="proj-1",
            state=IN_REVIEW,
        )
        child = _make_issue(state="closed")
        existing_review = MagicMock()
        existing_review.id = "254"
        existing_review.url = "https://github.com/org/repo/pull/254"
        existing_review.source_branch = "epic-epic-1"
        existing_review.target_branch = "main"
        existing_review.state = "open"
        provider = MagicMock()
        provider.list_merged_branches.return_value = set()
        provider.find_pr_for_branch.return_value = existing_review
        tracker = MagicMock()
        with (
            patch.object(orch, "_fetch_epic_children", return_value=[child]),
            patch.object(orch, "_has_epic_landing_ref", return_value=True),
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
            patch.object(orch, "_push_epic_branch") as push,
            patch.object(orch, "_tracker_for_project", return_value=tracker),
            patch.object(orch, "_sync_epic_review_child_states") as sync_children,
        ):
            opened = orch._open_epic_main_prs([epic])
        assert opened == 0
        provider.find_pr_for_branch.assert_any_call("org/repo", "epic-epic-1")
        provider.create_review.assert_not_called()
        tracker.update_issue.assert_not_called()
        tracker.set_metadata_field.assert_any_call(
            "epic-1",
            "oompah.review_url",
            "https://github.com/org/repo/pull/254",
        )
        tracker.set_metadata_field.assert_any_call(
            "epic-1",
            "oompah.review_number",
            "254",
        )
        sync_children.assert_called_once_with("proj-1", epic, "epic-epic-1")
        push.assert_not_called()

    def test_existing_pr_missing_from_cache_advances_epic_to_in_review(
        self,
        tmp_path,
    ):
        orch, proj = self._setup(tmp_path, strategy="stacked")
        orch.project_store.epic_branch_name.side_effect = lambda i: f"epic-{i}"
        epic = _make_issue(
            identifier="epic-1",
            issue_type="epic",
            project_id="proj-1",
            state=DONE,
        )
        child = _make_issue(state="closed")
        existing_review = MagicMock()
        existing_review.id = "254"
        existing_review.url = "https://github.com/org/repo/pull/254"
        existing_review.source_branch = "epic-epic-1"
        existing_review.target_branch = "main"
        existing_review.state = "open"
        provider = MagicMock()
        provider.list_merged_branches.return_value = set()
        provider.find_pr_for_branch.return_value = existing_review
        tracker = MagicMock()
        with (
            patch.object(orch, "_fetch_epic_children", return_value=[child]),
            patch.object(orch, "_has_epic_landing_ref", return_value=True),
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
            patch.object(orch, "_push_epic_branch") as push,
            patch.object(orch, "_tracker_for_project", return_value=tracker),
            patch.object(orch, "_sync_epic_review_child_states") as sync_children,
        ):
            opened = orch._open_epic_main_prs([epic])
        assert opened == 0
        tracker.update_issue.assert_called_once_with("epic-1", status=IN_REVIEW)
        tracker.set_metadata_field.assert_any_call(
            "epic-1",
            "oompah.review_url",
            "https://github.com/org/repo/pull/254",
        )
        tracker.set_metadata_field.assert_any_call(
            "epic-1",
            "oompah.review_number",
            "254",
        )
        tracker.set_metadata_field.assert_any_call(
            "epic-1",
            "oompah.work_branch",
            "epic-epic-1",
        )
        tracker.set_metadata_field.assert_any_call(
            "epic-1",
            "oompah.target_branch",
            "main",
        )
        sync_children.assert_called_once_with("proj-1", epic, "epic-epic-1")
        provider.create_review.assert_not_called()
        push.assert_not_called()

    def test_existing_epic_pr_leaves_shared_children_done(self, tmp_path):
        orch, proj = self._setup(tmp_path, strategy="shared")
        epic = _make_issue(
            identifier="TRICKLE-1",
            issue_type="epic",
            project_id="proj-1",
            state=IN_REVIEW,
        )
        implemented = _make_issue(
            identifier="TRICKLE-2",
            state=DONE,
            parent_id=epic.identifier,
        )
        missing = _make_issue(
            identifier="TRICKLE-5",
            state=DONE,
            parent_id=epic.identifier,
        )
        rebase = _make_issue(
            identifier="TRICKLE-7",
            title="Rebase epic-TRICKLE-1 onto main",
            state=DONE,
            parent_id=epic.identifier,
        )
        already_open = _make_issue(
            identifier="TRICKLE-8",
            state=OPEN,
            parent_id=epic.identifier,
        )
        tracker = MagicMock()
        with (
            patch.object(orch, "_tracker_for_project", return_value=tracker),
            patch.object(
                orch,
                "_fetch_epic_children",
                return_value=[implemented, missing, rebase, already_open],
            ),
            patch.object(
                orch,
                "_done_review_child_has_epic_branch_work",
                side_effect=[True, False],
            ) as has_branch_work,
        ):
            orch._sync_epic_review_child_states(
                "proj-1",
                epic,
                "epic-TRICKLE-1",
            )

        assert has_branch_work.call_count == 2
        assert (
            call("TRICKLE-2", status=IN_REVIEW)
            not in tracker.update_issue.call_args_list
        )
        tracker.update_issue.assert_any_call("TRICKLE-5", status=OPEN)
        tracker.update_issue.assert_any_call("TRICKLE-7", status=MERGED)
        assert tracker.update_issue.call_count == 2

    def test_done_review_child_has_epic_branch_commit(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=oompah",
                "-c",
                "user.email=lesserevil@users.noreply.github.com",
                "commit",
                "--allow-empty",
                "-m",
                "initial",
            ],
            cwd=repo,
            check=True,
        )
        subprocess.run(["git", "branch", "-m", "main"], cwd=repo, check=True)
        subprocess.run(
            ["git", "checkout", "-q", "-b", "epic-TRICKLE-1"],
            cwd=repo,
            check=True,
        )
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=oompah",
                "-c",
                "user.email=lesserevil@users.noreply.github.com",
                "commit",
                "--allow-empty",
                "-m",
                "TRICKLE-2: Implement session resolver",
            ],
            cwd=repo,
            check=True,
        )

        orch, proj = self._setup(tmp_path, strategy="shared")
        proj.repo_path = str(repo)
        proj.default_branch = "main"

        assert orch._done_review_child_has_epic_branch_work(
            proj,
            "epic-TRICKLE-1",
            _make_issue(identifier="TRICKLE-2"),
        )
        assert not orch._done_review_child_has_epic_branch_work(
            proj,
            "epic-TRICKLE-1",
            _make_issue(identifier="TRICKLE-5"),
        )

    def test_defers_epic_pr_when_project_at_review_cap(self, tmp_path):
        orch, proj = self._setup(tmp_path, strategy="stacked")
        orch.project_store.epic_branch_name.side_effect = lambda i: f"epic-{i}"
        existing_review = MagicMock()
        existing_review.source_branch = "other-task"
        existing_review.draft = False
        orch._reviews_cache = {"proj-1": [existing_review]}
        epic = _make_issue(
            identifier="epic-1", issue_type="epic", project_id="proj-1", state="open"
        )
        child = _make_issue(state="closed")
        provider = MagicMock()
        provider.list_merged_branches.return_value = set()
        with (
            patch.object(orch, "_fetch_epic_children", return_value=[child]),
            patch.object(orch, "_has_epic_landing_ref", return_value=True),
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
            patch.object(orch, "_push_epic_branch") as push,
        ):
            opened = orch._open_epic_main_prs([epic])
        assert opened == 0
        provider.create_review.assert_not_called()
        push.assert_not_called()

    def test_skips_when_provider_unavailable(self, tmp_path):
        orch, proj = self._setup(tmp_path, strategy="stacked")
        epic = _make_issue(
            identifier="epic-1", issue_type="epic", project_id="proj-1", state="open"
        )
        child = _make_issue(state="closed")
        with (
            patch.object(orch, "_fetch_epic_children", return_value=[child]),
            patch.object(orch, "_has_epic_landing_ref", return_value=True),
            patch("oompah.orchestrator.detect_provider", return_value=None),
        ):
            opened = orch._open_epic_main_prs([epic])
        assert opened == 0

    def test_marks_merged_instead_of_reopening_when_epic_already_landed(
        self, tmp_path
    ):
        """Loop fix: a squash-merged epic branch is never an ancestor of main,
        so it always looks "ahead" and the async _merged_branches set is
        skipped for webhook-healthy projects. Without the authoritative
        find_pr_for_branch check the gate re-opens/re-merges the same epic PR
        every tick. When the forge reports the epic PR already merged, mark the
        epic Merged and open NOTHING."""
        orch, proj = self._setup(tmp_path, strategy="shared")
        orch.project_store.epic_branch_name.side_effect = lambda i: f"epic-{i}"
        orch.project_store.read_task_status_in_epic_worktree.return_value = None
        epic = _make_issue(
            identifier="epic-1",
            issue_type="epic",
            project_id="proj-1",
            state="open",
            title="Already landed",
        )
        child = _make_issue(identifier="c1", state="closed")
        provider = MagicMock()
        # Forge reports the epic branch merged into its resolved target even
        # though a newer redundant PR may still be open (the loop artifact).
        provider.list_merged_reviews.return_value = [
            ReviewRequest(
                id="200",
                title="epic-1",
                url="https://github.com/org/repo/pull/200",
                author="alice",
                state="merged",
                source_branch="epic-epic-1",
                target_branch="main",
                created_at="",
                updated_at="",
            )
        ]
        tracker = MagicMock()
        with (
            patch.object(orch, "_fetch_epic_children", return_value=[child]),
            patch.object(orch, "_has_epic_landing_ref", return_value=True),
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
            patch.object(orch, "_tracker_for_issue", return_value=tracker),
            patch.object(orch, "_push_epic_branch") as push,
        ):
            opened = orch._open_epic_main_prs([epic])
        # No new PR opened, branch not even pushed.
        assert opened == 0
        provider.create_review.assert_not_called()
        push.assert_not_called()
        provider.list_merged_reviews.assert_called_once_with("org/repo")
        # Epic (and its child) marked Merged instead.
        marked = {
            call.args[0]: call.kwargs.get("status")
            for call in tracker.update_issue.call_args_list
        }
        assert marked.get("epic-1") == "Merged"
        assert marked.get("c1") == "Merged"

    def test_target_mismatch_does_not_mark_epic_merged(self, tmp_path):
        orch, proj = self._setup(tmp_path, strategy="shared")
        orch.project_store.epic_branch_name.side_effect = lambda i: f"epic-{i}"
        orch.project_store.read_task_status_in_epic_worktree.return_value = None
        epic = _make_issue(
            identifier="epic-1",
            issue_type="epic",
            project_id="proj-1",
            state=DONE,
            title="Parent epic",
        )
        child = _make_issue(identifier="c1", state=DONE)
        merged_to_parent = ReviewRequest(
            id="199",
            title="child landing",
            url="https://github.com/org/repo/pull/199",
            author="alice",
            state="merged",
            source_branch="epic-epic-1",
            target_branch="epic-parent",
            created_at="",
            updated_at="",
        )
        provider = MagicMock()
        provider.list_merged_reviews.return_value = [merged_to_parent]
        provider.find_pr_for_branch.return_value = merged_to_parent
        provider.create_review.return_value = MagicMock(id="201")
        tracker = MagicMock()
        with (
            patch.object(orch, "_fetch_epic_children", return_value=[child]),
            patch.object(orch, "_has_epic_landing_ref", return_value=True),
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
            patch.object(orch, "_tracker_for_project", return_value=tracker),
            patch.object(orch, "_tracker_for_issue") as tracker_for_issue,
            patch.object(orch, "_push_epic_branch") as push,
            patch.object(orch, "_sync_epic_review_child_states"),
        ):
            opened = orch._open_epic_main_prs([epic])

        assert opened == 1
        push.assert_called_once()
        tracker_for_issue.assert_not_called()
        provider.create_review.assert_called_once()
        assert provider.create_review.call_args.kwargs["target_branch"] == "main"
        tracker.update_issue.assert_any_call("epic-1", status=IN_REVIEW)

    def test_parent_shared_epic_opens_when_child_epics_already_merged(
        self,
        tmp_path,
    ):
        orch, proj = self._setup(tmp_path, strategy="shared")
        orch.project_store.epic_branch_name.side_effect = lambda i: f"epic-{i}"
        orch.project_store.read_task_status_in_epic_worktree.return_value = None
        parent = _make_issue(
            identifier="epic-1",
            issue_type="epic",
            project_id="proj-1",
            state=DONE,
            title="Top level",
        )
        child_epic = _make_issue(
            identifier="epic-2",
            issue_type="epic",
            project_id="proj-1",
            state=MERGED,
            parent_id=parent.identifier,
        )
        provider = MagicMock()
        provider.list_merged_reviews.return_value = []
        provider.find_pr_for_branch.return_value = None
        provider.create_review.return_value = MagicMock(id="202")
        tracker = MagicMock()
        with (
            patch.object(orch, "_fetch_epic_children", return_value=[child_epic]),
            patch.object(orch, "_has_epic_landing_ref", return_value=True),
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
            patch.object(orch, "_tracker_for_project", return_value=tracker),
            patch.object(orch, "_push_epic_branch"),
            patch.object(orch, "_sync_epic_review_child_states"),
        ):
            opened = orch._open_epic_main_prs([parent])

        assert opened == 1
        provider.create_review.assert_called_once()
        assert provider.create_review.call_args.args[2] == "epic-epic-1"
        assert provider.create_review.call_args.kwargs["target_branch"] == "main"

    def test_still_opens_when_no_prior_merged_pr(self, tmp_path):
        """Guard: an unmerged (open/None) find_pr_for_branch result must NOT
        suppress the normal first-time epic PR."""
        orch, proj = self._setup(tmp_path, strategy="shared")
        orch.project_store.epic_branch_name.side_effect = lambda i: f"epic-{i}"
        orch.project_store.read_task_status_in_epic_worktree.return_value = None
        epic = _make_issue(
            identifier="epic-1", issue_type="epic", project_id="proj-1", state="open"
        )
        child = _make_issue(identifier="c1", state="closed")
        provider = MagicMock()
        provider.list_merged_branches.return_value = set()
        provider.create_review.return_value = MagicMock(id="201")
        with (
            patch.object(orch, "_fetch_epic_children", return_value=[child]),
            patch.object(orch, "_has_epic_landing_ref", return_value=True),
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
            patch.object(orch, "_push_epic_branch"),
        ):
            opened = orch._open_epic_main_prs([epic])
        assert opened == 1
        provider.create_review.assert_called_once()

    def test_uses_existing_remote_epic_branch_when_shared_push_blocked(
        self, tmp_path
    ):
        orch, proj = self._setup(tmp_path, strategy="shared")
        orch.project_store.epic_branch_name.side_effect = lambda i: f"epic-{i}"
        orch.project_store.read_task_status_in_epic_worktree.return_value = None
        epic = _make_issue(
            identifier="epic-1", issue_type="epic", project_id="proj-1", state="Done"
        )
        child = _make_issue(identifier="c1", state="Done")
        provider = MagicMock()
        provider.list_merged_branches.return_value = set()
        provider.create_review.return_value = MagicMock(id="301")
        tracker = MagicMock()

        with (
            patch.object(orch, "_fetch_epic_children", return_value=[child]),
            patch.object(orch, "_has_epic_landing_ref", return_value=True),
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
            patch.object(orch, "_tracker_for_project", return_value=tracker),
            patch.object(
                orch,
                "_push_epic_branch",
                side_effect=ProjectError("dirty shared worktree"),
            ),
            patch.object(
                orch,
                "_remote_epic_branch_has_unmerged_work",
                return_value=True,
            ) as remote_has_work,
        ):
            opened = orch._open_epic_main_prs([epic])

        assert opened == 1
        remote_has_work.assert_called_once_with(proj, "main", "epic-epic-1")
        provider.create_review.assert_called_once()
        assert provider.create_review.call_args.args[2] == "epic-epic-1"
        tracker.update_issue.assert_any_call("epic-1", status=IN_REVIEW)
        tracker.update_issue.assert_any_call("c1", status=OPEN)
        assert tracker.update_issue.call_count == 2

    def test_push_failure_without_remote_work_opens_no_epic_pr(self, tmp_path):
        orch, _proj = self._setup(tmp_path, strategy="shared")
        orch.project_store.epic_branch_name.side_effect = lambda i: f"epic-{i}"
        orch.project_store.read_task_status_in_epic_worktree.return_value = None
        epic = _make_issue(
            identifier="epic-1", issue_type="epic", project_id="proj-1", state="Done"
        )
        child = _make_issue(identifier="c1", state="Done")
        provider = MagicMock()
        provider.list_merged_branches.return_value = set()

        with (
            patch.object(orch, "_fetch_epic_children", return_value=[child]),
            patch.object(orch, "_has_epic_landing_ref", return_value=True),
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
            patch.object(
                orch,
                "_push_epic_branch",
                side_effect=ProjectError("dirty shared worktree"),
            ),
            patch.object(
                orch,
                "_remote_epic_branch_has_unmerged_work",
                return_value=False,
            ),
        ):
            opened = orch._open_epic_main_prs([epic])

        assert opened == 0
        provider.create_review.assert_not_called()

    def test_reserves_project_review_capacity_within_epic_sweep(self, tmp_path):
        orch, _proj = self._setup(tmp_path, strategy="shared")
        orch.project_store.epic_branch_name.side_effect = lambda i: f"epic-{i}"
        orch.project_store.read_task_status_in_epic_worktree.return_value = None
        epics = [
            _make_issue(
                identifier="epic-1",
                issue_type="epic",
                project_id="proj-1",
                state="Done",
            ),
            _make_issue(
                identifier="epic-2",
                issue_type="epic",
                project_id="proj-1",
                state="Done",
            ),
        ]
        child = _make_issue(identifier="c1", state="Done")
        provider = MagicMock()
        provider.list_merged_branches.return_value = set()
        provider.create_review.return_value = MagicMock(id="302")

        with (
            patch.object(orch, "_fetch_epic_children", return_value=[child]),
            patch.object(orch, "_has_epic_landing_ref", return_value=True),
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
            patch.object(orch, "_push_epic_branch"),
        ):
            opened = orch._open_epic_main_prs(epics)

        assert opened == 1
        provider.create_review.assert_called_once()

    def test_epic_rollup_waits_for_blocker_to_land(self, tmp_path):
        orch, _proj = self._setup(tmp_path, strategy="shared")
        orch.project_store.epic_branch_name.side_effect = lambda i: f"epic-{i}"
        orch.project_store.read_task_status_in_epic_worktree.return_value = None
        epic = _make_issue(
            identifier="epic-2",
            issue_type="epic",
            project_id="proj-1",
            state="Done",
        )
        epic.blocked_by = [
            BlockerRef(id="1", identifier="org/repo#1", state="Done")
        ]
        child = _make_issue(identifier="c1", state="Done")
        provider = MagicMock()

        with (
            patch.object(orch, "_fetch_epic_children", return_value=[child]),
            patch("oompah.orchestrator.detect_provider", return_value=provider),
        ):
            opened = orch._open_epic_main_prs([epic])

        assert opened == 0
        provider.create_review.assert_not_called()

    def test_epic_rollup_allows_merged_blocker(self, tmp_path):
        orch, _proj = self._setup(tmp_path, strategy="shared")
        orch.project_store.epic_branch_name.side_effect = lambda i: f"epic-{i}"
        orch.project_store.read_task_status_in_epic_worktree.return_value = None
        epic = _make_issue(
            identifier="epic-2",
            issue_type="epic",
            project_id="proj-1",
            state="Done",
        )
        epic.blocked_by = [
            BlockerRef(id="1", identifier="org/repo#1", state="Merged")
        ]
        child = _make_issue(identifier="c1", state="Done")
        provider = MagicMock()
        provider.list_merged_branches.return_value = set()
        provider.create_review.return_value = MagicMock(id="303")

        with (
            patch.object(orch, "_fetch_epic_children", return_value=[child]),
            patch.object(orch, "_has_epic_landing_ref", return_value=True),
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
            patch.object(orch, "_push_epic_branch"),
        ):
            opened = orch._open_epic_main_prs([epic])

        assert opened == 1
        provider.create_review.assert_called_once()


class TestDeferredDoneReviews:
    def test_done_task_review_handoff_retried_when_capacity_available(self, tmp_path):
        proj = _make_project_record(epic_strategy="flat")
        orch = _make_orch(tmp_path, projects=[proj])
        orch._reviews_cache = {"proj-1": []}
        issue = _make_issue(identifier="task-1", state=DONE, project_id=None)
        tracker = MagicMock()
        tracker.fetch_issues_by_states.return_value = [issue]
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch._ensure_review_exists = MagicMock(return_value=True)

        with patch(
            "oompah.close_gate._count_commits_ahead",
            return_value=(1, ["abc123 feature"], ""),
        ):
            orch._open_deferred_done_reviews()

        tracker.fetch_issues_by_states.assert_called_once_with([DONE])
        orch._ensure_review_exists.assert_called_once()
        entry, project_id = orch._ensure_review_exists.call_args.args
        assert project_id == "proj-1"
        assert entry.identifier == "task-1"
        assert entry.issue.project_id == "proj-1"
        assert entry.agent_profile_name == "maintenance"

    def test_done_task_review_handoff_not_skipped_by_stale_merged_branch(
        self,
        tmp_path,
    ):
        proj = _make_project_record(epic_strategy="flat")
        orch = _make_orch(tmp_path, projects=[proj])
        orch._reviews_cache = {"proj-1": []}
        orch._merged_branches = {"task-1"}
        issue = _make_issue(identifier="task-1", state=DONE, project_id="proj-1")
        tracker = MagicMock()
        tracker.fetch_issues_by_states.return_value = [issue]
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch._merged_branch_tip_landed = MagicMock(return_value=False)
        orch._done_issue_has_unmerged_review_work = MagicMock(return_value=True)
        orch._ensure_review_exists = MagicMock(return_value=True)

        orch._open_deferred_done_reviews()

        orch._merged_branch_tip_landed.assert_called_once_with(
            proj,
            issue,
            "proj-1",
            "task-1",
            rollup_strategy=None,
        )
        orch._done_issue_has_unmerged_review_work.assert_called_once_with(
            issue,
            proj,
            "proj-1",
        )
        orch._ensure_review_exists.assert_called_once()

    def test_done_task_with_confirmed_merged_branch_is_marked_merged(self, tmp_path):
        proj = _make_project_record(epic_strategy="flat")
        orch = _make_orch(tmp_path, projects=[proj])
        orch._reviews_cache = {"proj-1": []}
        orch._merged_branches = {"task-1"}
        issue = _make_issue(identifier="task-1", state=DONE, project_id="proj-1")
        tracker = MagicMock()
        tracker.fetch_issues_by_states.return_value = [issue]
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch._merged_branch_tip_landed = MagicMock(return_value=True)
        orch._ensure_review_exists = MagicMock(return_value=True)

        orch._open_deferred_done_reviews()

        tracker.update_issue.assert_called_once_with("task-1", status=MERGED)
        orch._ensure_review_exists.assert_not_called()

    def test_shared_done_child_with_merged_branch_skips_all_checks(self, tmp_path):
        """Shared epic child with merged branch skips all individual promotion checks.

        In shared mode, a Done child with parent_id hits the early ``continue``
        at the ``rollup_strategy == 'shared'`` guard — neither
        ``_merged_branch_tip_landed`` nor ``_ensure_review_exists`` is called.
        The child stays Done; the epic rollup PR is the only path to Merged.
        """
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        orch._reviews_cache = {"proj-1": []}
        orch._merged_branches = {"task-1"}
        issue = _make_issue(
            identifier="task-1",
            state=DONE,
            parent_id="epic-1",
            project_id="proj-1",
        )
        parent = _make_issue(identifier="epic-1", issue_type="epic")
        tracker = MagicMock()
        tracker.fetch_issues_by_states.return_value = [issue]
        tracker.fetch_issue_detail.return_value = parent
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch._merged_branch_tip_landed = MagicMock(return_value=True)
        orch._done_issue_branch_tip_landed = MagicMock(return_value=True)
        orch._ensure_review_exists = MagicMock(return_value=True)

        orch._open_deferred_done_reviews()

        # Child stays Done — no tracker update, no review creation.
        tracker.update_issue.assert_not_called()
        orch._ensure_review_exists.assert_not_called()
        orch._done_issue_branch_tip_landed.assert_not_called()
        # The early continue fires before _merged_branch_tip_landed is reached.
        orch._merged_branch_tip_landed.assert_not_called()

    def test_done_task_review_handoff_skips_project_at_capacity(self, tmp_path):
        proj = _make_project_record(epic_strategy="flat")
        proj.max_in_flight_prs = 1
        orch = _make_orch(tmp_path, projects=[proj])
        existing_review = MagicMock()
        existing_review.draft = False
        orch._reviews_cache = {"proj-1": [existing_review]}
        tracker = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch._ensure_review_exists = MagicMock(return_value=True)

        orch._open_deferred_done_reviews()

        tracker.fetch_issues_by_states.assert_not_called()
        orch._ensure_review_exists.assert_not_called()

    def test_done_task_review_handoff_skips_shared_epic_child(self, tmp_path):
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        orch._reviews_cache = {"proj-1": []}
        issue = _make_issue(
            identifier="task-1",
            state=DONE,
            parent_id="epic-1",
            project_id="proj-1",
        )
        tracker = MagicMock()
        tracker.fetch_issues_by_states.return_value = [issue]
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch._ensure_review_exists = MagicMock(return_value=True)

        with patch.object(orch, "_epic_rollup_child_strategy", return_value="shared"):
            orch._open_deferred_done_reviews()

        orch._ensure_review_exists.assert_not_called()

    def test_done_task_review_handoff_skips_when_branch_check_fails(self, tmp_path):
        proj = _make_project_record(epic_strategy="flat")
        orch = _make_orch(tmp_path, projects=[proj])
        orch._reviews_cache = {"proj-1": []}
        issue = _make_issue(identifier="task-1", state=DONE, project_id="proj-1")
        tracker = MagicMock()
        tracker.fetch_issues_by_states.return_value = [issue]
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch._ensure_review_exists = MagicMock(return_value=True)

        with patch(
            "oompah.close_gate._count_commits_ahead",
            return_value=(0, [], "unknown revision"),
        ):
            orch._open_deferred_done_reviews()

        orch._ensure_review_exists.assert_not_called()

    def test_done_task_with_landed_branch_is_marked_merged(self, tmp_path):
        proj = _make_project_record(epic_strategy="flat")
        orch = _make_orch(tmp_path, projects=[proj])
        orch._reviews_cache = {"proj-1": []}
        issue = _make_issue(identifier="task-1", state=DONE, project_id="proj-1")
        tracker = MagicMock()
        tracker.fetch_issues_by_states.return_value = [issue]
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch._ensure_review_exists = MagicMock(return_value=True)

        with (
            patch.object(orch, "_managed_branch_ref_exists", return_value=True),
            patch.object(
                orch,
                "_count_review_branch_ahead",
                return_value=(0, [], ""),
            ),
        ):
            orch._open_deferred_done_reviews()

        tracker.update_issue.assert_called_once_with("task-1", status=MERGED)
        orch._ensure_review_exists.assert_not_called()


class TestEpicRollupStatusReconciliation:
    def _orch_with_tracker(self, tmp_path):
        proj = _make_project_record(epic_strategy="flat")
        orch = _make_orch(tmp_path, projects=[proj])
        tracker = MagicMock()
        return orch, tracker

    def test_backlog_epic_with_open_child_is_persisted_open(self, tmp_path):
        orch, tracker = self._orch_with_tracker(tmp_path)
        epic = _make_issue(
            identifier="epic-1",
            issue_type="epic",
            state="Backlog",
        )
        child = _make_issue(
            identifier="child-1",
            state=OPEN,
            parent_id=epic.identifier,
        )
        tracker.fetch_children.return_value = [child]

        with patch.object(orch, "_tracker_for_issue", return_value=tracker):
            updated = orch._reconcile_epic_rollup_statuses([epic])

        assert updated == 1
        tracker.update_issue.assert_called_once_with(epic.identifier, status=OPEN)
        assert epic.state == OPEN

    def test_backlog_epic_with_in_progress_child_is_persisted_in_progress(
        self, tmp_path
    ):
        orch, tracker = self._orch_with_tracker(tmp_path)
        epic = _make_issue(
            identifier="epic-1",
            issue_type="epic",
            state="Backlog",
        )
        tracker.fetch_children.return_value = [
            _make_issue(identifier="child-1", state=OPEN, parent_id=epic.identifier),
            _make_issue(
                identifier="child-2",
                state=IN_PROGRESS,
                parent_id=epic.identifier,
            ),
        ]

        with patch.object(orch, "_tracker_for_issue", return_value=tracker):
            updated = orch._reconcile_epic_rollup_statuses([epic])

        assert updated == 1
        tracker.update_issue.assert_called_once_with(
            epic.identifier,
            status=IN_PROGRESS,
        )
        assert epic.state == IN_PROGRESS

    def test_backlog_epic_with_all_done_children_is_persisted_done(self, tmp_path):
        orch, tracker = self._orch_with_tracker(tmp_path)
        epic = _make_issue(
            identifier="epic-1",
            issue_type="epic",
            state="Backlog",
        )
        tracker.fetch_children.return_value = [
            _make_issue(identifier="child-1", state=DONE, parent_id=epic.identifier),
            _make_issue(identifier="child-2", state=DONE, parent_id=epic.identifier),
        ]

        with patch.object(orch, "_tracker_for_issue", return_value=tracker):
            updated = orch._reconcile_epic_rollup_statuses([epic])

        assert updated == 1
        tracker.update_issue.assert_called_once_with(epic.identifier, status=DONE)
        assert epic.state == DONE

    def test_shared_done_epic_with_all_merged_children_stays_done(self, tmp_path):
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        tracker = MagicMock()
        epic = _make_issue(
            identifier="epic-1",
            issue_type="epic",
            state=DONE,
        )
        tracker.fetch_children.return_value = [
            _make_issue(identifier="child-1", state=MERGED, parent_id=epic.identifier),
            _make_issue(identifier="child-2", state=MERGED, parent_id=epic.identifier),
        ]

        with patch.object(orch, "_tracker_for_issue", return_value=tracker):
            updated = orch._reconcile_epic_rollup_statuses([epic])

        assert updated == 0
        tracker.update_issue.assert_not_called()
        assert epic.state == DONE

    def test_decomposed_children_do_not_keep_epic_in_progress(self, tmp_path):
        orch, tracker = self._orch_with_tracker(tmp_path)
        epic = _make_issue(
            identifier="epic-1",
            issue_type="epic",
            state="Backlog",
        )
        tracker.fetch_children.return_value = [
            _make_issue(identifier="child-1", state=DONE, parent_id=epic.identifier),
            _make_issue(
                identifier="child-2",
                state="Decomposed",
                parent_id=epic.identifier,
            ),
        ]

        with patch.object(orch, "_tracker_for_issue", return_value=tracker):
            updated = orch._reconcile_epic_rollup_statuses([epic])

        assert updated == 1
        tracker.update_issue.assert_called_once_with(epic.identifier, status=DONE)
        assert epic.state == DONE

    def test_in_review_epic_with_done_children_is_not_downgraded(self, tmp_path):
        """In shared mode, Done children with epic-branch work STAY Done.

        The epic stays IN_REVIEW (not downgraded) and no child transition is
        needed — Done is review-ready in shared mode.
        """
        orch, tracker = self._orch_with_tracker(tmp_path)
        epic = _make_issue(
            identifier="epic-1",
            issue_type="epic",
            state=IN_REVIEW,
            work_branch="epic-epic-1",
        )
        tracker.fetch_children.return_value = [
            _make_issue(identifier="child-1", state=DONE, parent_id=epic.identifier),
        ]

        with (
            patch.object(orch, "_tracker_for_issue", return_value=tracker),
            patch.object(orch, "_tracker_for_project", return_value=tracker),
            patch.object(
                orch,
                "_done_review_child_has_epic_branch_work",
                return_value=True,
            ),
        ):
            updated = orch._reconcile_epic_rollup_statuses([epic])

        assert updated == 0
        # Shared mode: Done child stays Done — no tracker update required.
        tracker.update_issue.assert_not_called()
        assert epic.state == IN_REVIEW

    def test_in_review_epic_with_new_open_child_rolls_back_to_in_progress(
        self, tmp_path
    ):
        orch, tracker = self._orch_with_tracker(tmp_path)
        epic = _make_issue(
            identifier="epic-1",
            issue_type="epic",
            state=IN_REVIEW,
            work_branch="epic-epic-1",
            review_url="https://github.com/org/repo/pull/23",
        )
        tracker.fetch_children.return_value = [
            _make_issue(
                identifier="child-reviewed",
                state=IN_REVIEW,
                parent_id=epic.identifier,
            ),
            _make_issue(
                identifier="child-new",
                state=OPEN,
                parent_id=epic.identifier,
            ),
        ]

        with patch.object(orch, "_tracker_for_issue", return_value=tracker):
            updated = orch._reconcile_epic_rollup_statuses([epic])

        assert updated == 1
        tracker.update_issue.assert_called_once_with(
            epic.identifier,
            status=IN_PROGRESS,
        )
        assert epic.state == IN_PROGRESS

    def test_rebasing_label_does_not_reopen_done_children(self, tmp_path):
        orch, tracker = self._orch_with_tracker(tmp_path)
        epic = _make_issue(
            identifier="epic-1",
            issue_type="epic",
            state=IN_PROGRESS,
            labels=["epic:rebasing"],
        )
        tracker.fetch_children.return_value = [
            _make_issue(identifier="child-1", state=DONE, parent_id=epic.identifier),
        ]

        with (
            patch.object(orch, "_tracker_for_issue", return_value=tracker),
            patch.object(
                orch,
                "_sync_epic_review_child_states",
            ) as sync_children,
        ):
            updated = orch._reconcile_epic_rollup_statuses([epic])

        assert updated == 1
        sync_children.assert_not_called()
        tracker.update_issue.assert_called_once_with(epic.identifier, status=DONE)
        assert epic.state == DONE

    def test_ci_fix_epic_with_done_children_is_not_downgraded(self, tmp_path):
        """In shared mode, Done children with epic-branch work STAY Done.

        The epic stays NEEDS_CI_FIX (not downgraded) and no child transition
        is needed — Done is review-ready in shared mode.
        """
        orch, tracker = self._orch_with_tracker(tmp_path)
        epic = _make_issue(
            identifier="epic-1",
            issue_type="epic",
            state=NEEDS_CI_FIX,
            work_branch="epic-epic-1",
        )
        tracker.fetch_children.return_value = [
            _make_issue(identifier="child-1", state=DONE, parent_id=epic.identifier),
        ]

        with (
            patch.object(orch, "_tracker_for_issue", return_value=tracker),
            patch.object(orch, "_tracker_for_project", return_value=tracker),
            patch.object(
                orch,
                "_done_review_child_has_epic_branch_work",
                return_value=True,
            ),
        ):
            updated = orch._reconcile_epic_rollup_statuses([epic])

        assert updated == 0
        # Shared mode: Done child stays Done — no tracker update required.
        tracker.update_issue.assert_not_called()
        assert epic.state == NEEDS_CI_FIX

    def test_existing_review_epic_syncs_late_done_child_and_promotes_epic(
        self, tmp_path
    ):
        orch, tracker = self._orch_with_tracker(tmp_path)
        epic = _make_issue(
            identifier="TRICKLE-1",
            issue_type="epic",
            state=IN_PROGRESS,
            work_branch="epic-TRICKLE-1",
            review_url="https://github.com/org/repo/pull/267",
        )
        reviewed = _make_issue(
            identifier="TRICKLE-2",
            state=IN_REVIEW,
            parent_id=epic.identifier,
        )
        late_done = _make_issue(
            identifier="TRICKLE-5",
            state=DONE,
            parent_id=epic.identifier,
        )
        tracker.fetch_children.return_value = [reviewed, late_done]

        with (
            patch.object(orch, "_tracker_for_issue", return_value=tracker),
            patch.object(orch, "_tracker_for_project", return_value=tracker),
            patch.object(
                orch,
                "_done_review_child_has_epic_branch_work",
                return_value=True,
            ) as has_branch_work,
        ):
            updated = orch._reconcile_epic_rollup_statuses([epic])

        assert updated == 1
        has_branch_work.assert_called_once()
        # Shared mode: Done children with epic-branch work STAY Done.
        # Only the epic itself is promoted to IN_REVIEW.
        assert tracker.update_issue.call_args_list == [
            call("TRICKLE-1", status=IN_REVIEW),
        ]
        assert late_done.state == DONE  # unchanged in shared mode
        assert epic.state == IN_REVIEW

    def test_existing_review_epic_with_review_ready_children_promotes_to_review(
        self, tmp_path
    ):
        orch, tracker = self._orch_with_tracker(tmp_path)
        epic = _make_issue(
            identifier="TRICKLE-1",
            issue_type="epic",
            state=IN_PROGRESS,
            work_branch="epic-TRICKLE-1",
            review_url="https://github.com/org/repo/pull/267",
        )
        tracker.fetch_children.return_value = [
            _make_issue(
                identifier="TRICKLE-2",
                state=IN_REVIEW,
                parent_id=epic.identifier,
            ),
            _make_issue(
                identifier="TRICKLE-7",
                state=MERGED,
                parent_id=epic.identifier,
            ),
        ]

        with patch.object(orch, "_tracker_for_issue", return_value=tracker):
            updated = orch._reconcile_epic_rollup_statuses([epic])

        assert updated == 1
        tracker.update_issue.assert_called_once_with("TRICKLE-1", status=IN_REVIEW)
        assert epic.state == IN_REVIEW

    def test_stale_rollup_snapshot_does_not_overwrite_active_epic_repair(
        self, tmp_path
    ):
        orch, tracker = self._orch_with_tracker(tmp_path)
        stale_epic = _make_issue(
            identifier="TRICKLE-1",
            issue_type="epic",
            state=IN_PROGRESS,
            work_branch="epic-TRICKLE-1",
            review_url="https://github.com/org/repo/pull/267",
        )
        current_epic = _make_issue(
            identifier="TRICKLE-1",
            issue_type="epic",
            state=IN_PROGRESS,
            labels=["ci-fix"],
            work_branch="epic-TRICKLE-1",
            review_url="https://github.com/org/repo/pull/267",
        )
        tracker.fetch_children.return_value = [
            _make_issue(
                identifier="TRICKLE-2",
                state=IN_REVIEW,
                parent_id=stale_epic.identifier,
            ),
            _make_issue(
                identifier="TRICKLE-3",
                state=MERGED,
                parent_id=stale_epic.identifier,
            ),
        ]
        tracker.fetch_issue_detail.return_value = current_epic

        with patch.object(orch, "_tracker_for_issue", return_value=tracker):
            updated = orch._reconcile_epic_rollup_statuses([stale_epic])

        assert updated == 0
        tracker.update_issue.assert_not_called()
        assert stale_epic.state == IN_PROGRESS

    def test_matching_rollup_status_is_not_rewritten(self, tmp_path):
        orch, tracker = self._orch_with_tracker(tmp_path)
        epic = _make_issue(identifier="epic-1", issue_type="epic", state=OPEN)
        tracker.fetch_children.return_value = [
            _make_issue(identifier="child-1", state=OPEN, parent_id=epic.identifier),
        ]

        with patch.object(orch, "_tracker_for_issue", return_value=tracker):
            updated = orch._reconcile_epic_rollup_statuses([epic])

        assert updated == 0
        tracker.update_issue.assert_not_called()

    def test_epic_with_no_children_is_not_rewritten(self, tmp_path):
        orch, tracker = self._orch_with_tracker(tmp_path)
        epic = _make_issue(
            identifier="epic-1",
            issue_type="epic",
            state="Backlog",
        )
        tracker.fetch_children.return_value = []

        with patch.object(orch, "_tracker_for_issue", return_value=tracker):
            updated = orch._reconcile_epic_rollup_statuses([epic])

        assert updated == 0
        tracker.update_issue.assert_not_called()


class TestEpicReviewRepairCompletion:
    def test_finished_ci_repair_returns_epic_to_review(self, tmp_path):
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        tracker = MagicMock()
        epic = _make_issue(
            identifier="TASK-738",
            issue_type="epic",
            state=IN_PROGRESS,
            labels=["ci-fix"],
            work_branch="epic-TASK-738",
            project_id="proj-1",
        )
        entry = RunningEntry(
            worker_task=MagicMock(),
            identifier=epic.identifier,
            issue=epic,
            session=None,
            retry_attempt=0,
            started_at=MagicMock(),
            agent_profile_name="default",
        )
        children = [_make_issue(identifier="TASK-738.1", state=IN_REVIEW)]
        orch._ensure_review_exists = MagicMock(return_value=True)

        with patch.object(orch, "_fetch_epic_children", return_value=children):
            result = orch._finish_epic_review_repair(
                tracker,
                entry,
                epic,
                "proj-1",
            )

        assert result is True
        assert tracker.update_issue.call_args_list == [
            call("TASK-738", **{"remove-label": "ci-fix"}),
            call("TASK-738", status=IN_REVIEW),
        ]
        assert epic.state == IN_REVIEW


class TestPushEpicBranch:
    def test_shared_mode_skips_fast_forward_for_dirty_worktree(self, tmp_path):
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        wt_path = tmp_path / "worktree"
        (wt_path / ".oompah" / "tasks").mkdir(parents=True)

        proj = _make_project_record(epic_strategy="shared")
        proj.repo_path = str(repo_path)
        orch = _make_orch(tmp_path, projects=[proj])
        orch.project_store.epic_worktree_path_for.return_value = str(wt_path)

        calls = []

        def fake_run(cmd, **kwargs):
            calls.append((cmd, kwargs))
            if cmd == ["git", "status", "--porcelain"]:
                return subprocess.CompletedProcess(
                    cmd,
                    0,
                    stdout=" M .oompah/tasks/task-1.md\n",
                    stderr="",
                )
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        with patch("oompah.orchestrator.subprocess.run", side_effect=fake_run):
            orch._push_epic_branch(proj, "epic-1")

        commands = [cmd for cmd, _kwargs in calls]
        assert commands == [
            ["git", "fetch", "origin", "epic-epic-1"],
            ["git", "status", "--porcelain"],
            ["git", "push", "origin", "HEAD:epic-epic-1"],
        ]
        assert calls[-1][1]["cwd"] == str(wt_path)

    def test_shared_mode_fast_forwards_clean_worktree_before_push(self, tmp_path):
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        wt_path = tmp_path / "worktree"
        wt_path.mkdir()

        proj = _make_project_record(epic_strategy="shared")
        proj.repo_path = str(repo_path)
        orch = _make_orch(tmp_path, projects=[proj])
        orch.project_store.epic_worktree_path_for.return_value = str(wt_path)

        calls = []

        def fake_run(cmd, **kwargs):
            calls.append((cmd, kwargs))
            if cmd == ["git", "status", "--porcelain"]:
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
            if cmd == [
                "git",
                "rev-list",
                "--left-right",
                "--count",
                "HEAD...FETCH_HEAD",
            ]:
                return subprocess.CompletedProcess(cmd, 0, stdout="0\t3\n", stderr="")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        with patch("oompah.orchestrator.subprocess.run", side_effect=fake_run):
            orch._push_epic_branch(proj, "epic-1")

        commands = [cmd for cmd, _kwargs in calls]
        assert commands == [
            ["git", "fetch", "origin", "epic-epic-1"],
            ["git", "status", "--porcelain"],
            ["git", "rev-list", "--left-right", "--count", "HEAD...FETCH_HEAD"],
            ["git", "merge", "--ff-only", "FETCH_HEAD"],
            ["git", "push", "origin", "HEAD:epic-epic-1"],
        ]
        assert calls[3][1]["cwd"] == str(wt_path)
        assert calls[-1][1]["cwd"] == str(wt_path)

    def test_shared_mode_skips_fast_forward_for_dirty_worktree(self, tmp_path):
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        wt_path = tmp_path / "worktree"
        wt_path.mkdir()

        proj = _make_project_record(epic_strategy="shared")
        proj.repo_path = str(repo_path)
        orch = _make_orch(tmp_path, projects=[proj])
        orch.project_store.epic_worktree_path_for.return_value = str(wt_path)

        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            if cmd == ["git", "status", "--porcelain"]:
                return subprocess.CompletedProcess(
                    cmd,
                    0,
                    stdout=" M src/server.py\n",
                    stderr="",
                )
            if cmd == ["git", "diff", "--cached", "--quiet"]:
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        with patch("oompah.orchestrator.subprocess.run", side_effect=fake_run):
            orch._push_epic_branch(proj, "epic-1")

        assert ["git", "commit", "-m"] not in [cmd[:3] for cmd in calls]
        assert ["git", "merge", "--ff-only", "FETCH_HEAD"] not in calls
        assert ["git", "push", "origin", "HEAD:epic-epic-1"] in calls


# --------------------------------- resolve_epic_target_branch (nested epics)


class TestResolveEpicTargetBranch:
    """_resolve_epic_target_branch: shared-mode nested epics target parent's branch."""

    def test_top_level_epic_shared_mode_targets_project_branch(self, tmp_path):
        """Top-level epic (no parent) in shared mode → project.branch (main)."""
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        # Epic has no parent
        top_epic = _make_issue(
            identifier="epic-A", issue_type="epic", parent_id=None, project_id="proj-1"
        )
        with patch.object(orch, "_resolve_parent_epic", return_value=None):
            target = orch._resolve_epic_target_branch(top_epic, proj)
        assert target == "main"

    def test_nested_epic_shared_mode_targets_parent_epic_branch(self, tmp_path):
        """Nested epic B (child of A) in shared mode → A's branch."""
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        orch.project_store.epic_branch_name.side_effect = lambda i: f"epic-{i}"
        # Epic A is the parent
        parent_epic = _make_issue(
            identifier="epic-A", issue_type="epic", parent_id=None, project_id="proj-1"
        )
        # Epic B is a child of A
        child_epic = _make_issue(
            identifier="epic-B",
            issue_type="epic",
            parent_id="epic-A",
            project_id="proj-1",
        )
        with patch.object(orch, "_resolve_parent_epic", return_value=parent_epic):
            target = orch._resolve_epic_target_branch(child_epic, proj)
        assert target == "epic-epic-A"

    def test_nested_epic_shared_parent_tracker_error_returns_project_branch(
        self, tmp_path
    ):
        """If _resolve_parent_epic returns None (tracker error), fall back to project.branch."""
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        child_epic = _make_issue(
            identifier="epic-B",
            issue_type="epic",
            parent_id="epic-A",
            project_id="proj-1",
        )
        # Simulate tracker error — resolve_parent_epic returns None
        with patch.object(orch, "_resolve_parent_epic", return_value=None):
            target = orch._resolve_epic_target_branch(child_epic, proj)
        assert target == "main"


# ------------------------------- nested epic PR target in _open_epic_main_prs


class TestLabelMergedEpics:
    """When an epic→main PR merges, the epic and all its children become
    Merged."""

    def test_marks_epic_and_children_merged(self, tmp_path):
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        epic = _make_issue(identifier="epic-1", issue_type="epic", state="Backlog")
        c1 = _make_issue(identifier="c1", state="Done")
        c2 = _make_issue(identifier="c2", state="Merged")  # already merged → skip
        # epic_branch_name(epic-1) == "epic-epic-1" per the _make_orch stub.
        orch._merged_branches = {"epic-epic-1"}
        provider = MagicMock()
        provider.list_merged_reviews.return_value = [
            ReviewRequest(
                id="12",
                title="epic-1",
                url="https://github.com/org/repo/pull/12",
                author="alice",
                state="merged",
                source_branch="epic-epic-1",
                target_branch="main",
                created_at="",
                updated_at="",
            )
        ]
        tracker = MagicMock()
        with (
            patch.object(orch, "_all_non_terminal_epics", return_value=[epic]),
            patch.object(orch, "_fetch_epic_children", return_value=[c1, c2]),
            patch.object(orch, "_tracker_for_issue", return_value=tracker),
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
        ):
            orch._label_merged_epics()
        marked = [call.args[0] for call in tracker.update_issue.call_args_list]
        assert "epic-1" in marked          # the epic itself
        assert "c1" in marked              # not-yet-merged child
        assert "c2" not in marked          # already Merged → skipped
        for call in tracker.update_issue.call_args_list:
            assert call.kwargs.get("status") == "Merged"

    def test_noop_when_epic_branch_not_merged(self, tmp_path):
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        epic = _make_issue(identifier="epic-1", issue_type="epic", state="Backlog")
        orch._merged_branches = {"some-other-branch"}
        tracker = MagicMock()
        with (
            patch.object(orch, "_all_non_terminal_epics", return_value=[epic]),
            patch.object(orch, "_fetch_epic_children", return_value=[]),
            patch.object(orch, "_tracker_for_issue", return_value=tracker),
            patch("oompah.orchestrator.detect_provider", return_value=None),
        ):
            orch._label_merged_epics()
        tracker.update_issue.assert_not_called()

    def test_done_epic_is_marked_merged_after_rollup_pr_lands(self, tmp_path):
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        epic = _make_issue(identifier="epic-1", issue_type="epic", state="Done")
        c1 = _make_issue(identifier="c1", state="Done", parent_id="epic-1")
        tracker = MagicMock()
        tracker.fetch_all_issues.return_value = [epic, c1]
        orch._merged_branches = {"epic-epic-1"}
        provider = MagicMock()
        provider.list_merged_reviews.return_value = [
            ReviewRequest(
                id="13",
                title="epic-1",
                url="https://github.com/org/repo/pull/13",
                author="alice",
                state="merged",
                source_branch="epic-epic-1",
                target_branch="main",
                created_at="",
                updated_at="",
            )
        ]

        with (
            patch.object(orch, "_tracker_for_project", return_value=tracker),
            patch.object(orch, "_tracker_for_issue", return_value=tracker),
            patch.object(orch, "_fetch_epic_children", return_value=[c1]),
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
        ):
            orch._label_merged_epics()

        marked = {
            call.args[0]: call.kwargs.get("status")
            for call in tracker.update_issue.call_args_list
        }
        assert marked == {"epic-1": "Merged", "c1": "Merged"}

    def test_merged_epic_reconciles_children_still_done(self, tmp_path):
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        epic = _make_issue(identifier="epic-1", issue_type="epic", state="Merged")
        c1 = _make_issue(identifier="c1", state="Done", parent_id="epic-1")
        c2 = _make_issue(identifier="c2", state="Archived", parent_id="epic-1")
        tracker = MagicMock()
        tracker.fetch_all_issues.return_value = [epic, c1, c2]

        with (
            patch.object(orch, "_tracker_for_project", return_value=tracker),
            patch.object(orch, "_tracker_for_issue", return_value=tracker),
            patch.object(orch, "_fetch_epic_children", return_value=[c1, c2]),
        ):
            orch._reconcile_merged_epic_children()

        marked = {
            call.args[0]: call.kwargs.get("status")
            for call in tracker.update_issue.call_args_list
        }
        assert marked == {"epic-1": "Merged", "c1": "Merged"}

    @patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo")
    @patch("oompah.orchestrator.detect_provider")
    def test_provider_landed_epic_marks_children_and_helper_tasks(
        self,
        mock_detect,
        _mock_slug,
        tmp_path,
    ):
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        orch.project_store.epic_branch_name.side_effect = (
            lambda epic_id: f"epic-{epic_id.replace('/', '_').replace('#', '_')}"
        )
        epic = _make_issue(
            identifier="example-org/oompah#272",
            issue_type="epic",
            state="Done",
        )
        child = _make_issue(
            identifier="example-org/oompah#275",
            state="Done",
            parent_id=epic.identifier,
        )
        ci_helper = _make_issue(
            identifier="example-org/oompah#296",
            title="CI fix: PR #291 on branch epic-example-org_oompah_272",
            state="Done",
            parent_id=epic.identifier,
        )
        rebase_helper = _make_issue(
            identifier="example-org/oompah#298",
            title="Rebase epic-example-org_oompah_272 onto main",
            state="Done",
            parent_id=epic.identifier,
        )
        orch._merged_branches = set()
        provider = MagicMock()
        provider.list_merged_reviews.return_value = [
            ReviewRequest(
                id="291",
                title="example-org/oompah#272",
                url="https://github.com/org/repo/pull/291",
                author="alice",
                state="merged",
                source_branch="epic-example-org_oompah_272",
                target_branch="main",
                created_at="",
                updated_at="",
            )
        ]
        mock_detect.return_value = provider

        tracker = MagicMock()
        with (
            patch.object(orch, "_all_non_terminal_epics", return_value=[epic]),
            patch.object(
                orch,
                "_fetch_epic_children",
                return_value=[child, ci_helper, rebase_helper],
            ),
            patch.object(orch, "_tracker_for_issue", return_value=tracker),
        ):
            orch._label_merged_epics()

        marked = {
            call.args[0]: call.kwargs.get("status")
            for call in tracker.update_issue.call_args_list
        }
        assert marked == {
            epic.identifier: "Merged",
            child.identifier: "Merged",
            ci_helper.identifier: "Merged",
            rebase_helper.identifier: "Merged",
        }

    @patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo")
    @patch("oompah.orchestrator.detect_provider")
    def test_provider_landed_epic_target_mismatch_is_not_marked(
        self,
        mock_detect,
        _mock_slug,
        tmp_path,
    ):
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        orch.project_store.epic_branch_name.side_effect = (
            lambda epic_id: f"epic-{epic_id}"
        )
        epic = _make_issue(identifier="epic-1", issue_type="epic", state="Done")
        child = _make_issue(identifier="c1", state="Done", parent_id=epic.identifier)
        merged_to_parent = ReviewRequest(
            id="291",
            title="nested epic landing",
            url="https://github.com/org/repo/pull/291",
            author="alice",
            state="merged",
            source_branch="epic-epic-1",
            target_branch="epic-parent",
            created_at="",
            updated_at="",
        )
        orch._merged_branches = {"epic-epic-1"}
        provider = MagicMock()
        provider.list_merged_reviews.return_value = [merged_to_parent]
        provider.find_pr_for_branch.return_value = merged_to_parent
        mock_detect.return_value = provider

        tracker = MagicMock()
        with (
            patch.object(orch, "_all_non_terminal_epics", return_value=[epic]),
            patch.object(orch, "_fetch_epic_children", return_value=[child]),
            patch.object(orch, "_tracker_for_issue", return_value=tracker),
        ):
            orch._label_merged_epics()

        tracker.update_issue.assert_not_called()

    def test_noop_when_no_landed_epics(self, tmp_path):
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        orch._merged_branches = set()
        with patch.object(orch, "_all_non_terminal_epics") as fetch:
            fetch.return_value = []
            orch._label_merged_epics()
        fetch.assert_called_once()


class TestNestedEpicMergeChain:
    """Multi-level epic merge chain: B→A's branch, A→main in shared mode."""

    def _setup_nested(self, tmp_path):
        """Set up a 2-level nested epic: A (top) → B (child epic)."""
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        orch._reviews_cache = {}
        orch.project_store.epic_branch_name.side_effect = lambda i: f"epic-{i}"
        # No epic-branch status override → the shared landing gate falls
        # back to each child's default-branch state (what these tests set).
        orch.project_store.read_task_status_in_epic_worktree.return_value = None
        return orch, proj

    def test_child_epic_pr_targets_parent_epic_branch_not_main(self, tmp_path):
        """B's completion PR targets A's branch (epic-epic-A), NOT main."""
        orch, proj = self._setup_nested(tmp_path)
        parent_epic = _make_issue(
            identifier="epic-A",
            issue_type="epic",
            parent_id=None,
            project_id="proj-1",
            state="open",
        )
        child_epic = _make_issue(
            identifier="epic-B",
            issue_type="epic",
            parent_id="epic-A",
            project_id="proj-1",
            state="open",
            title="Child epic B",
        )
        task = _make_issue(identifier="task-1", state="closed")
        provider = MagicMock()
        provider.create_review.return_value = MagicMock(id="55")
        # _fetch_epic_children returns a task (all closed) when called for B
        # _resolve_parent_epic returns parent_epic when called for B
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = parent_epic
        with (
            patch.object(orch, "_fetch_epic_children", return_value=[task]),
            patch.object(orch, "_tracker_for_issue", return_value=tracker),
            patch.object(orch, "_has_epic_landing_ref", return_value=True),
            patch.object(
                orch,
                "_ensure_review_target_branch_exists",
                return_value=True,
            ) as ensure_target,
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
            patch.object(orch, "_push_epic_branch"),
        ):
            opened = orch._open_epic_main_prs([child_epic])
        assert opened == 1
        provider.create_review.assert_called_once()
        kwargs = provider.create_review.call_args.kwargs
        # Child epic B's PR must target A's branch, not main
        assert kwargs.get("target_branch") == "epic-epic-A"
        ensure_target.assert_called_once_with(proj, "epic-epic-A")

    def test_child_epic_pr_defers_when_parent_branch_unavailable(self, tmp_path):
        """B's completion PR waits when A's target branch cannot be created."""
        orch, proj = self._setup_nested(tmp_path)
        parent_epic = _make_issue(
            identifier="epic-A",
            issue_type="epic",
            parent_id=None,
            project_id="proj-1",
            state="open",
        )
        child_epic = _make_issue(
            identifier="epic-B",
            issue_type="epic",
            parent_id="epic-A",
            project_id="proj-1",
            state="open",
            title="Child epic B",
        )
        task = _make_issue(identifier="task-1", state="closed")
        provider = MagicMock()
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = parent_epic

        with (
            patch.object(orch, "_fetch_epic_children", return_value=[task]),
            patch.object(orch, "_tracker_for_issue", return_value=tracker),
            patch.object(orch, "_has_epic_landing_ref", return_value=True),
            patch.object(
                orch,
                "_ensure_review_target_branch_exists",
                return_value=False,
            ) as ensure_target,
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
            patch.object(orch, "_push_epic_branch") as push_epic_branch,
        ):
            opened = orch._open_epic_main_prs([child_epic])

        assert opened == 0
        ensure_target.assert_called_once_with(proj, "epic-epic-A")
        push_epic_branch.assert_not_called()
        provider.create_review.assert_not_called()

    def test_ensure_review_target_branch_exists_creates_missing_origin_branch(
        self,
        tmp_path,
    ):
        """Missing parent epic target branches are created from origin/main."""
        orch, proj = self._setup_nested(tmp_path)
        remote = tmp_path / "remote.git"
        repo = tmp_path / "repo"
        subprocess.run(
            ["git", "init", "-q", "--bare", "--initial-branch=main", str(remote)],
            check=True,
        )
        subprocess.run(["git", "clone", "-q", str(remote), str(repo)], check=True)
        (repo / "README.md").write_text("initial\n")
        subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=oompah",
                "-c",
                "user.email=lesserevil@users.noreply.github.com",
                "commit",
                "-m",
                "init",
            ],
            cwd=repo,
            check=True,
        )
        subprocess.run(["git", "push", "origin", "main"], cwd=repo, check=True)
        proj.repo_path = str(repo)
        proj.default_branch = "main"
        proj.branch = "main"

        assert orch._ensure_review_target_branch_exists(proj, "epic-epic-A")

        result = subprocess.run(
            ["git", "ls-remote", "--heads", "origin", "epic-epic-A"],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        assert "refs/heads/epic-epic-A" in result.stdout

    def test_top_level_epic_pr_still_targets_main(self, tmp_path):
        """A's completion PR targets project.branch (main), not any parent branch."""
        orch, proj = self._setup_nested(tmp_path)
        top_epic = _make_issue(
            identifier="epic-A",
            issue_type="epic",
            parent_id=None,
            project_id="proj-1",
            state="open",
            title="Top epic A",
        )
        child_epic_B = _make_issue(
            identifier="epic-B", issue_type="epic", state="closed"
        )
        provider = MagicMock()
        provider.create_review.return_value = MagicMock(id="66")
        # No parent for A: _resolve_parent_epic returns None
        with (
            patch.object(orch, "_fetch_epic_children", return_value=[child_epic_B]),
            patch.object(orch, "_resolve_parent_epic", return_value=None),
            patch.object(orch, "_has_epic_landing_ref", return_value=True),
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
            patch.object(orch, "_push_epic_branch"),
        ):
            opened = orch._open_epic_main_prs([top_epic])
        assert opened == 1
        provider.create_review.assert_called_once()
        kwargs = provider.create_review.call_args.kwargs
        assert kwargs.get("target_branch") == "main"

    def test_three_level_nesting_c_targets_b_branch(self, tmp_path):
        """Three-level nesting A→B→C: C's PR targets B's branch."""
        orch, proj = self._setup_nested(tmp_path)
        epic_B = _make_issue(
            identifier="epic-B",
            issue_type="epic",
            parent_id="epic-A",
            project_id="proj-1",
            state="open",
        )
        epic_C = _make_issue(
            identifier="epic-C",
            issue_type="epic",
            parent_id="epic-B",
            project_id="proj-1",
            state="open",
            title="Grandchild epic C",
        )
        task = _make_issue(identifier="task-1", state="closed")
        provider = MagicMock()
        provider.create_review.return_value = MagicMock(id="77")
        # Return epic_B as the parent when fetching C's parent
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = epic_B
        with (
            patch.object(orch, "_fetch_epic_children", return_value=[task]),
            patch.object(orch, "_tracker_for_issue", return_value=tracker),
            patch.object(orch, "_has_epic_landing_ref", return_value=True),
            patch.object(
                orch,
                "_ensure_review_target_branch_exists",
                return_value=True,
            ) as ensure_target,
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
            patch.object(orch, "_push_epic_branch"),
        ):
            opened = orch._open_epic_main_prs([epic_C])
        assert opened == 1
        provider.create_review.assert_called_once()
        kwargs = provider.create_review.call_args.kwargs
        # C's PR must target B's branch
        assert kwargs.get("target_branch") == "epic-epic-B"
        ensure_target.assert_called_once_with(proj, "epic-epic-B")

    def test_shared_mode_child_epic_waits_for_all_direct_children_terminal(
        self, tmp_path
    ):
        """A's completion only fires when ALL direct children (including B) are terminal.

        This verifies the existing completion-detection logic isn't broken
        by the new target-branch logic: if child epic B is still open,
        parent epic A should NOT open its PR yet.
        """
        orch, proj = self._setup_nested(tmp_path)
        top_epic = _make_issue(
            identifier="epic-A",
            issue_type="epic",
            parent_id=None,
            project_id="proj-1",
            state="open",
        )
        # Sub-epic B is still open (not terminal)
        child_epic_B = _make_issue(identifier="epic-B", issue_type="epic", state="open")
        # Direct task under A is closed
        direct_task = _make_issue(identifier="task-direct", state="closed")
        provider = MagicMock()
        with (
            patch.object(
                orch, "_fetch_epic_children", return_value=[child_epic_B, direct_task]
            ),
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
        ):
            opened = orch._open_epic_main_prs([top_epic])
        # B is still open → A's PR must NOT be opened yet
        assert opened == 0
        provider.create_review.assert_not_called()
