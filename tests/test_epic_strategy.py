"""Tests for the per-project ``epic_strategy`` setting.

Covers Project model (default + round-trip + back-compat), ProjectStore
update validation, the new epic worktree helpers, the orchestrator
dispatch gating (shared mode), the worktree allocation helper, the PR
target selection (stacked mode), and the epic→main PR creation
(stacked + shared).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import fnmatch

import pytest

from oompah.config import ServiceConfig
from oompah.models import Issue, Project, RunningEntry
from oompah.orchestrator import Orchestrator
from oompah.projects import ProjectError, ProjectStore
from oompah.statuses import IN_REVIEW, OPEN


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
    p.matches_branch = lambda b: fnmatch.fnmatch(b, "main")
    p.paused = paused
    p.epic_strategy = epic_strategy
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
        config=ServiceConfig(),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
    )
    return orch


# ----------------------------------------------------- Project model + storage


class TestProjectEpicStrategyField:
    def test_default_is_stacked(self):
        # Default for newly-created Project objects is "stacked"
        # (changed from "flat" so new projects get merge-train semantics
        # out of the box; pre-existing projects on disk retain their value
        # and from_dict still falls back to "flat" when the field is entirely
        # missing from a pre-amd projects.json — see test_from_dict_back_compat_when_missing).
        p = Project(id="p", name="n", repo_url="u", repo_path="/tmp/x")
        assert p.epic_strategy == "stacked"

    def test_to_dict_includes_default(self):
        p = Project(id="p", name="n", repo_url="u", repo_path="/tmp/x")
        d = p.to_dict()
        assert d["epic_strategy"] == "stacked"

    def test_to_dict_round_trip(self):
        p = Project(
            id="p",
            name="n",
            repo_url="u",
            repo_path="/tmp/x",
            epic_strategy="stacked",
        )
        d = p.to_dict()
        assert d["epic_strategy"] == "stacked"
        p2 = Project.from_dict(d)
        assert p2.epic_strategy == "stacked"

    def test_from_dict_back_compat_when_missing(self):
        # Existing projects.json without the field → defaults to flat
        d = {"id": "p", "name": "n", "repo_url": "u", "repo_path": "/tmp/x"}
        p = Project.from_dict(d)
        assert p.epic_strategy == "flat"

    def test_from_dict_unknown_value_falls_back_to_flat(self):
        d = {
            "id": "p",
            "name": "n",
            "repo_url": "u",
            "repo_path": "/tmp/x",
            "epic_strategy": "totally-bogus",
        }
        p = Project.from_dict(d)
        assert p.epic_strategy == "flat"

    def test_from_dict_normalizes_case(self):
        d = {
            "id": "p",
            "name": "n",
            "repo_url": "u",
            "repo_path": "/tmp/x",
            "epic_strategy": "SHARED",
        }
        p = Project.from_dict(d)
        assert p.epic_strategy == "shared"


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

    def test_update_to_stacked(self, tmp_path):
        store = self._store(tmp_path)
        self._seed(store)
        p = store.update("p1", epic_strategy="stacked")
        assert p is not None
        assert p.epic_strategy == "stacked"

    def test_update_to_shared(self, tmp_path):
        store = self._store(tmp_path)
        self._seed(store)
        p = store.update("p1", epic_strategy="shared")
        assert p is not None
        assert p.epic_strategy == "shared"

    def test_update_normalizes_case(self, tmp_path):
        store = self._store(tmp_path)
        self._seed(store)
        p = store.update("p1", epic_strategy="STACKED")
        assert p is not None
        assert p.epic_strategy == "stacked"

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

    def test_update_none_resets_to_flat(self, tmp_path):
        store = self._store(tmp_path)
        self._seed(store, epic_strategy="stacked")
        p = store.update("p1", epic_strategy=None)
        assert p is not None
        assert p.epic_strategy == "flat"


class TestUpdatableFieldsIncludesEpicStrategy:
    def test_field_in_allow_list(self):
        assert "epic_strategy" in ProjectStore.UPDATABLE_FIELDS


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
    def test_default_when_no_project(self, tmp_path):
        orch = _make_orch(tmp_path)
        assert orch._project_epic_strategy(None) == "flat"
        assert orch._project_epic_strategy("missing") == "flat"

    def test_returns_configured_value(self, tmp_path):
        proj = _make_project_record(epic_strategy="stacked")
        orch = _make_orch(tmp_path, projects=[proj])
        assert orch._project_epic_strategy("proj-1") == "stacked"

    def test_falls_back_on_invalid_value(self, tmp_path):
        proj = _make_project_record(epic_strategy="weird")
        orch = _make_orch(tmp_path, projects=[proj])
        assert orch._project_epic_strategy("proj-1") == "flat"


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

    def test_rejects_when_child_done_on_epic_branch(self, tmp_path):
        """A shared-epic child already terminal on its epic branch must not
        be re-dispatched, even though main still shows it active. This is
        the fix for the infinite re-dispatch loop."""
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        child = _make_issue(identifier="task-only", parent_id="epic-1", state="open")
        orch._reviews_cache = {}
        with patch.object(
            orch.project_store,
            "read_task_status_in_epic_worktree",
            return_value="Done",
        ):
            assert orch._should_dispatch(child) is False
        reason, _count = orch.state.reject_streak[child.id]
        assert "epic_branch_done" in reason

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

    def test_shared_child_dispatches_when_blocker_done_on_epic_branch(self, tmp_path):
        """A shared-epic child whose sibling blocker is Done on the EPIC
        BRANCH (but still Open on the default branch) must dispatch — the
        dependency is satisfied. This breaks the 706.7-style deadlock."""
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
            assert orch._should_dispatch(child) is True

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

    def test_p0_child_done_on_epic_branch_still_rejected(self, tmp_path):
        """The epic-branch-done gate applies even to P0 — a completed
        child must never be re-dispatched regardless of priority."""
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
            assert orch._should_dispatch(child) is False
        reason, _count = orch.state.reject_streak[child.id]
        assert "epic_branch_done" in reason

    def test_flat_mode_allows_multiple_children_of_same_epic(self, tmp_path):
        """Flat mode → no per-epic serial cap, only the global PR cap applies."""
        proj = _make_project_record(epic_strategy="flat")
        # Allow multiple PRs in flight at once
        proj.max_in_flight_prs = 5
        orch = _make_orch(tmp_path, projects=[proj])
        self._set_up_running_sibling(
            orch, parent_id="epic-1", sibling_id="task-running"
        )
        child = _make_issue(identifier="task-2", parent_id="epic-1", state="open")
        orch._reviews_cache = {}
        # flat mode: passes
        assert orch._should_dispatch(child) is True

    def test_stacked_mode_allows_multiple_children_of_same_epic(self, tmp_path):
        """Stacked mode also allows parallel children — only shared serializes."""
        proj = _make_project_record(epic_strategy="stacked")
        proj.max_in_flight_prs = 5
        orch = _make_orch(tmp_path, projects=[proj])
        self._set_up_running_sibling(
            orch, parent_id="epic-1", sibling_id="task-running"
        )
        child = _make_issue(identifier="task-2", parent_id="epic-1", state="open")
        orch._reviews_cache = {}
        assert orch._should_dispatch(child) is True

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

    @pytest.mark.parametrize("strategy", ["flat", "stacked"])
    def test_select_dispatchable_only_serializes_shared_strategy(
        self, tmp_path, strategy
    ):
        proj = _make_project_record(epic_strategy=strategy)
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

        assert [issue.identifier for issue in ready] == ["task-a", "task-b"]

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


# ------------------------------------------------------- workspace allocation


class TestWorkspaceAllocation:
    """_create_workspace_for_issue picks per-bead vs shared epic worktree."""

    def test_flat_mode_uses_per_bead_worktree(self, tmp_path):
        proj = _make_project_record(epic_strategy="flat")
        orch = _make_orch(tmp_path, projects=[proj])
        orch.project_store.create_worktree.return_value = "/wt/per-bead"
        orch.project_store.create_epic_worktree.return_value = "/wt/epic"

        issue = _make_issue(parent_id="epic-1", project_id="proj-1")
        wp, epic = orch._create_workspace_for_issue(issue)
        assert wp == "/wt/per-bead"
        assert epic is None
        orch.project_store.create_worktree.assert_called_once()
        orch.project_store.create_epic_worktree.assert_not_called()

    def test_per_bead_worktree_syncs_task_file(self, tmp_path):
        proj = _make_project_record(epic_strategy="flat")
        orch = _make_orch(tmp_path, projects=[proj])
        orch.project_store.create_worktree.return_value = "/wt/per-bead"

        issue = _make_issue(identifier="TASK-389", project_id="proj-1")
        wp, epic = orch._create_workspace_for_issue(issue)

        assert wp == "/wt/per-bead"
        assert epic is None
        orch.project_store.sync_task_file_to_worktree.assert_called_once_with(
            "proj-1",
            "TASK-389",
            "/wt/per-bead",
            preserve_statuses=frozenset(orch.config.tracker_terminal_states),
        )

    def test_stacked_mode_uses_per_bead_worktree(self, tmp_path):
        proj = _make_project_record(epic_strategy="stacked")
        orch = _make_orch(tmp_path, projects=[proj])
        orch.project_store.create_worktree.return_value = "/wt/per-bead"
        issue = _make_issue(parent_id="epic-1", project_id="proj-1")
        wp, epic = orch._create_workspace_for_issue(issue)
        assert wp == "/wt/per-bead"
        assert epic is None  # stacked still uses per-bead worktree
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

    def test_shared_epic_worktree_syncs_child_task_file(self, tmp_path):
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
        orch.project_store.sync_task_file_to_worktree.assert_called_once_with(
            "proj-1",
            "TASK-389",
            "/wt/epic-1",
            preserve_statuses=frozenset(orch.config.tracker_terminal_states),
        )

    def test_shared_mode_top_level_issue_uses_per_bead(self, tmp_path):
        """Top-level issues (no parent) under shared mode get a per-bead worktree."""
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        orch.project_store.create_worktree.return_value = "/wt/per-bead"
        issue = _make_issue(parent_id=None, project_id="proj-1")
        wp, epic = orch._create_workspace_for_issue(issue)
        assert wp == "/wt/per-bead"
        assert epic is None
        orch.project_store.create_worktree.assert_called_once()


# ------------------------------------------------------------- PR target test


class TestEnsureReviewExistsRespectsEpicStrategy:
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

    def test_stacked_targets_epic_branch_for_child(self, tmp_path):
        proj = _make_project_record(epic_strategy="stacked")
        orch = _make_orch(tmp_path, projects=[proj])
        orch._reviews_cache = {"proj-1": []}

        provider = MagicMock()
        provider.create_review.return_value = MagicMock(id="42")

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
        call = provider.create_review.call_args
        kwargs = call.kwargs
        # Branch name uses the project_store helper, which mocks return
        # f"epic-{epic_id}".  Stacked mode targets the epic branch.
        assert kwargs.get("target_branch") == "epic-epic-1"

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

    def test_stacked_top_level_targets_main(self, tmp_path):
        """Top-level beads in stacked mode (no parent_id) still target main."""
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

    def test_stacked_child_with_target_branch_still_uses_epic_branch(self, tmp_path):
        """In stacked mode, a child's target_branch does NOT override the epic branch."""
        proj = _make_project_record(epic_strategy="stacked")
        orch = _make_orch(tmp_path, projects=[proj])
        orch._reviews_cache = {"proj-1": []}

        provider = MagicMock()
        provider.create_review.return_value = MagicMock(id="42")

        epic = _make_issue(identifier="epic-1", issue_type="epic")
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = epic

        # Child has a target_branch set — stacked mode should still win
        issue = Issue(
            id="task-1",
            identifier="task-1",
            title="child task",
            description="body",
            state="open",
            issue_type="task",
            parent_id="epic-1",
            project_id="proj-1",
            target_branch="release/3.0",
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

        call = provider.create_review.call_args
        kwargs = call.kwargs
        # Stacked child always targets the epic branch, not issue.target_branch
        assert kwargs.get("target_branch") == "epic-epic-1"


# --------------------------------------------------- epic completion + PR open


class TestOpenEpicMainPrs:
    def _setup(self, tmp_path, *, strategy: str):
        proj = _make_project_record(epic_strategy=strategy)
        orch = _make_orch(tmp_path, projects=[proj])
        orch._reviews_cache = {}
        return orch, proj

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
            identifier="epic-1", issue_type="epic", project_id="proj-1", state="closed"
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
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
            patch.object(orch, "_push_epic_branch"),
        ):
            opened = orch._open_epic_main_prs([epic])
        assert opened == 1

    def test_shared_lands_when_children_done_on_epic_branch_only(self, tmp_path):
        """The fix: shared-epic children that are Done on the EPIC BRANCH
        but still Open on the default branch must satisfy the landing gate
        (otherwise the epic→main PR never opens — the deadlock)."""
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
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
            patch.object(orch, "_push_epic_branch") as push,
        ):
            opened = orch._open_epic_main_prs([epic])
        assert opened == 1
        push.assert_called_once_with(proj, "epic-1")
        provider.create_review.assert_called_once()

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

    def test_shared_merged_child_does_not_block_landing(self, tmp_path):
        """A child merged via its own path (Merged on default branch, stale
        on the epic branch) counts as complete and must NOT block an
        otherwise-done epic — mirrors epic-706 (706.6 Merged, rest Done)."""
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
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
            patch.object(orch, "_push_epic_branch"),
        ):
            opened = orch._open_epic_main_prs([epic])
        assert opened == 1

    def test_all_non_terminal_epics_includes_backlog_epics(self, tmp_path):
        """The landing-gate pool must include epics in non-dispatch states
        like Backlog (otherwise their completed work never lands)."""
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        backlog_epic = _make_issue(identifier="e1", issue_type="epic", state="Backlog")
        open_epic = _make_issue(identifier="e2", issue_type="epic", state="Open")
        done_epic = _make_issue(identifier="e3", issue_type="epic", state="Done")
        task = _make_issue(identifier="t1", issue_type="task", state="Backlog")
        tracker = MagicMock()
        tracker.fetch_all_issues.return_value = [backlog_epic, open_epic, done_epic, task]
        with patch.object(orch, "_tracker_for_project", return_value=tracker):
            epics = orch._all_non_terminal_epics()
        idents = {e.identifier for e in epics}
        # Backlog + Open epics included; terminal (Done) epic and non-epic excluded.
        assert idents == {"e1", "e2"}

    def test_shared_all_children_already_merged_opens_no_pr(self, tmp_path):
        """If every child is already Merged (whole epic landed), the rollup is
        Merged, not Done — no epic→main PR should be opened."""
        orch, proj = self._setup(tmp_path, strategy="shared")
        orch.project_store.epic_branch_name.side_effect = lambda i: f"epic-{i}"
        orch.project_store.read_task_status_in_epic_worktree.return_value = None
        epic = _make_issue(
            identifier="epic-1", issue_type="epic", project_id="proj-1", state="open",
        )
        c1 = _make_issue(identifier="c1", state="merged")
        c2 = _make_issue(identifier="c2", state="merged")
        provider = MagicMock()
        with (
            patch.object(orch, "_fetch_epic_children", return_value=[c1, c2]),
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
            patch.object(orch, "_push_epic_branch") as push,
        ):
            opened = orch._open_epic_main_prs([epic])
        assert opened == 0
        push.assert_not_called()

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
        # Forge reports the epic branch among recently-merged head refs even
        # though a newer redundant PR may still be open (the loop artifact).
        provider.list_merged_branches.return_value = {"epic-epic-1"}
        tracker = MagicMock()
        with (
            patch.object(orch, "_fetch_epic_children", return_value=[child]),
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
        provider.list_merged_branches.assert_called_once_with("org/repo")
        # Epic (and its child) marked Merged instead.
        marked = {
            call.args[0]: call.kwargs.get("status")
            for call in tracker.update_issue.call_args_list
        }
        assert marked.get("epic-1") == "Merged"
        assert marked.get("c1") == "Merged"

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
            patch("oompah.orchestrator.detect_provider", return_value=provider),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
            patch.object(orch, "_push_epic_branch"),
        ):
            opened = orch._open_epic_main_prs([epic])
        assert opened == 1
        provider.create_review.assert_called_once()


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

    def test_stacked_mode_ignores_parent_epic_always_targets_project_branch(
        self, tmp_path
    ):
        """Stacked mode: _resolve_epic_target_branch always returns project.branch.

        In stacked mode, child task PRs already target the parent epic's branch
        directly (per _ensure_review_exists). The epic 'completion PR' is not
        part of the nested stacked-mode chain — stacked nests naturally.
        """
        proj = _make_project_record(epic_strategy="stacked")
        orch = _make_orch(tmp_path, projects=[proj])
        parent_epic = _make_issue(
            identifier="epic-A", issue_type="epic", project_id="proj-1"
        )
        child_epic = _make_issue(
            identifier="epic-B",
            issue_type="epic",
            parent_id="epic-A",
            project_id="proj-1",
        )
        # Even if there is a parent epic, stacked mode doesn't use the chain
        with patch.object(orch, "_resolve_parent_epic", return_value=parent_epic):
            target = orch._resolve_epic_target_branch(child_epic, proj)
        assert target == "main"

    def test_flat_mode_ignores_parent_epic_always_targets_project_branch(
        self, tmp_path
    ):
        """Flat mode: _resolve_epic_target_branch always returns project.branch."""
        proj = _make_project_record(epic_strategy="flat")
        orch = _make_orch(tmp_path, projects=[proj])
        parent_epic = _make_issue(
            identifier="epic-A", issue_type="epic", project_id="proj-1"
        )
        child_epic = _make_issue(
            identifier="epic-B",
            issue_type="epic",
            parent_id="epic-A",
            project_id="proj-1",
        )
        with patch.object(orch, "_resolve_parent_epic", return_value=parent_epic):
            target = orch._resolve_epic_target_branch(child_epic, proj)
        assert target == "main"

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
        tracker = MagicMock()
        with (
            patch.object(orch, "_all_non_terminal_epics", return_value=[epic]),
            patch.object(orch, "_fetch_epic_children", return_value=[c1, c2]),
            patch.object(orch, "_tracker_for_issue", return_value=tracker),
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
        ):
            orch._label_merged_epics()
        tracker.update_issue.assert_not_called()

    def test_noop_when_no_merged_branches(self, tmp_path):
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        orch._merged_branches = set()
        with patch.object(orch, "_all_non_terminal_epics") as fetch:
            orch._label_merged_epics()
        fetch.assert_not_called()  # early-out before any work


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

    def test_flat_mode_child_epic_still_targets_main(self, tmp_path):
        """flat mode: child epic's PR targets main regardless of nesting."""
        proj = _make_project_record(epic_strategy="flat")
        orch = _make_orch(tmp_path, projects=[proj])
        orch._reviews_cache = {}
        orch.project_store.epic_branch_name.side_effect = lambda i: f"epic-{i}"
        # Flat mode should never reach _open_epic_main_prs for PRs because
        # the strategy check skips flat — but we verify the target resolver
        # still returns main even if called directly.
        child_epic = _make_issue(
            identifier="epic-B",
            issue_type="epic",
            parent_id="epic-A",
            project_id="proj-1",
            state="open",
        )
        parent_epic = _make_issue(
            identifier="epic-A", issue_type="epic", project_id="proj-1"
        )
        with patch.object(orch, "_resolve_parent_epic", return_value=parent_epic):
            target = orch._resolve_epic_target_branch(child_epic, proj)
        assert target == "main"

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
