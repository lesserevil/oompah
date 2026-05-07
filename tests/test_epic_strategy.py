"""Tests for the per-project ``epic_strategy`` setting.

Covers Project model (default + round-trip + back-compat), ProjectStore
update validation, the new epic worktree helpers, the orchestrator
dispatch gating (shared mode), the worktree allocation helper, the PR
target selection (stacked mode), and the epic→main PR creation
(stacked + shared).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from oompah.config import ServiceConfig
from oompah.models import Issue, Project, RunningEntry
from oompah.orchestrator import Orchestrator
from oompah.projects import ProjectError, ProjectStore


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
    project_store.epic_branch_name.side_effect = (
        lambda epic_id: f"epic-{epic_id.replace('/', '_')}"
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
        p = Project(id="p", name="n", repo_url="u", repo_path="/tmp/x")
        assert p.epic_strategy == "stacked"

    def test_to_dict_includes_default(self):
        p = Project(id="p", name="n", repo_url="u", repo_path="/tmp/x")
        d = p.to_dict()
        assert d["epic_strategy"] == "stacked"

    def test_to_dict_round_trip(self):
        p = Project(
            id="p", name="n", repo_url="u", repo_path="/tmp/x",
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
            "id": "p", "name": "n", "repo_url": "u", "repo_path": "/tmp/x",
            "epic_strategy": "totally-bogus",
        }
        p = Project.from_dict(d)
        assert p.epic_strategy == "flat"

    def test_from_dict_normalizes_case(self):
        d = {
            "id": "p", "name": "n", "repo_url": "u", "repo_path": "/tmp/x",
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
            id="p1", name="n", repo_url="u", repo_path="/tmp/x",
            git_user_name="A", git_user_email="a@example.com",
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
            id="p1", name="my-project", repo_url="u", repo_path="/tmp/repo",
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
        self._set_up_running_sibling(orch, parent_id="epic-1",
                                     sibling_id="task-running")
        # Now try to dispatch another child of the same epic
        child = _make_issue(identifier="task-2", parent_id="epic-1",
                            state="open")
        # Make _count_open_reviews + per-state checks neutral
        orch._reviews_cache = {}
        assert orch._should_dispatch(child) is False
        # Confirm the rejection reason was the shared-epic-busy gate
        reason, _count = orch.state.reject_streak[child.id]
        assert "shared_epic_busy" in reason

    def test_allows_when_no_sibling_running_in_shared_mode(self, tmp_path):
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        child = _make_issue(identifier="task-only", parent_id="epic-1",
                            state="open")
        orch._reviews_cache = {}
        assert orch._should_dispatch(child) is True

    def test_flat_mode_allows_multiple_children_of_same_epic(self, tmp_path):
        """Flat mode → no per-epic serial cap, only the global PR cap applies."""
        proj = _make_project_record(epic_strategy="flat")
        # Allow multiple PRs in flight at once
        proj.max_in_flight_prs = 5
        orch = _make_orch(tmp_path, projects=[proj])
        self._set_up_running_sibling(orch, parent_id="epic-1",
                                     sibling_id="task-running")
        child = _make_issue(identifier="task-2", parent_id="epic-1",
                            state="open")
        orch._reviews_cache = {}
        # flat mode: passes
        assert orch._should_dispatch(child) is True

    def test_stacked_mode_allows_multiple_children_of_same_epic(self, tmp_path):
        """Stacked mode also allows parallel children — only shared serializes."""
        proj = _make_project_record(epic_strategy="stacked")
        proj.max_in_flight_prs = 5
        orch = _make_orch(tmp_path, projects=[proj])
        self._set_up_running_sibling(orch, parent_id="epic-1",
                                     sibling_id="task-running")
        child = _make_issue(identifier="task-2", parent_id="epic-1",
                            state="open")
        orch._reviews_cache = {}
        assert orch._should_dispatch(child) is True

    def test_shared_mode_allows_different_epics_in_parallel(self, tmp_path):
        """Multiple epics still dispatch concurrently — only same-epic siblings serialize."""
        proj = _make_project_record(epic_strategy="shared")
        proj.max_in_flight_prs = 5
        orch = _make_orch(tmp_path, projects=[proj])
        # Sibling running on epic-1
        self._set_up_running_sibling(orch, parent_id="epic-1",
                                     sibling_id="other-running")
        # Child of a *different* epic
        child = _make_issue(identifier="task-x", parent_id="epic-2",
                            state="open")
        orch._reviews_cache = {}
        assert orch._should_dispatch(child) is True

    def test_p0_bypasses_shared_gate(self, tmp_path):
        """P0 issues bypass the per-epic serial cap, matching other gate bypasses."""
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        self._set_up_running_sibling(orch, parent_id="epic-1",
                                     sibling_id="task-running")
        child = _make_issue(
            identifier="task-p0", parent_id="epic-1", state="open",
            priority=0,
        )
        orch._reviews_cache = {}
        assert orch._should_dispatch(child) is True


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
            "proj-1", "epic-1",
        )
        orch.project_store.create_worktree.assert_not_called()

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

        issue = _make_issue(identifier="task-1", parent_id="epic-1",
                            project_id="proj-1")
        entry = RunningEntry(
            worker_task=MagicMock(),
            identifier="task-1",
            issue=issue,
            session=None,
            retry_attempt=0,
            started_at=MagicMock(),
            agent_profile_name="default",
        )
        with patch("oompah.orchestrator.detect_provider", return_value=provider), \
             patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"):
            orch._ensure_review_exists(entry, "proj-1")
        # base_branch should be project.branch (main), NOT the epic branch
        call = provider.create_review.call_args
        kwargs = call.kwargs
        assert kwargs.get("target_branch") == "main"

    def test_stacked_targets_epic_branch_for_child(self, tmp_path):
        proj = _make_project_record(epic_strategy="stacked")
        orch = _make_orch(tmp_path, projects=[proj])
        orch._reviews_cache = {"proj-1": []}

        provider = MagicMock()
        provider.create_review.return_value = MagicMock(id="42")

        epic = _make_issue(identifier="epic-1", issue_type="epic")
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = epic
        issue = _make_issue(identifier="task-1", parent_id="epic-1",
                            project_id="proj-1")
        entry = RunningEntry(
            worker_task=MagicMock(),
            identifier="task-1",
            issue=issue,
            session=None,
            retry_attempt=0,
            started_at=MagicMock(),
            agent_profile_name="default",
        )
        with patch.object(orch, "_tracker_for_issue", return_value=tracker), \
             patch("oompah.orchestrator.detect_provider", return_value=provider), \
             patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"):
            orch._ensure_review_exists(entry, "proj-1")
        call = provider.create_review.call_args
        kwargs = call.kwargs
        # Branch name uses the project_store helper, which mocks return
        # f"epic-{epic_id}".  Stacked mode targets the epic branch.
        assert kwargs.get("target_branch") == "epic-epic-1"

    def test_shared_skips_per_child_pr(self, tmp_path):
        proj = _make_project_record(epic_strategy="shared")
        orch = _make_orch(tmp_path, projects=[proj])
        orch._reviews_cache = {"proj-1": []}

        provider = MagicMock()
        epic = _make_issue(identifier="epic-1", issue_type="epic")
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = epic
        issue = _make_issue(identifier="task-1", parent_id="epic-1",
                            project_id="proj-1")
        entry = RunningEntry(
            worker_task=MagicMock(),
            identifier="task-1",
            issue=issue,
            session=None,
            retry_attempt=0,
            started_at=MagicMock(),
            agent_profile_name="default",
        )
        with patch.object(orch, "_tracker_for_issue", return_value=tracker), \
             patch("oompah.orchestrator.detect_provider", return_value=provider), \
             patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"):
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

        issue = _make_issue(identifier="task-1", parent_id=None,
                            project_id="proj-1")
        entry = RunningEntry(
            worker_task=MagicMock(),
            identifier="task-1",
            issue=issue,
            session=None,
            retry_attempt=0,
            started_at=MagicMock(),
            agent_profile_name="default",
        )
        with patch("oompah.orchestrator.detect_provider", return_value=provider), \
             patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"):
            orch._ensure_review_exists(entry, "proj-1")
        call = provider.create_review.call_args
        kwargs = call.kwargs
        assert kwargs.get("target_branch") == "main"


# --------------------------------------------------- epic completion + PR open


class TestOpenEpicMainPrs:
    def _setup(self, tmp_path, *, strategy: str):
        proj = _make_project_record(epic_strategy=strategy)
        orch = _make_orch(tmp_path, projects=[proj])
        orch._reviews_cache = {}
        return orch, proj

    def test_flat_mode_is_noop(self, tmp_path):
        orch, proj = self._setup(tmp_path, strategy="flat")
        epic = _make_issue(identifier="epic-1", issue_type="epic",
                           project_id="proj-1", state="open")
        with patch.object(orch, "_fetch_epic_children",
                          return_value=[_make_issue(state="closed")]), \
             patch("oompah.orchestrator.detect_provider") as detect_p:
            opened = orch._open_epic_main_prs([epic])
        assert opened == 0
        detect_p.assert_not_called()

    def test_skips_epic_with_no_children(self, tmp_path):
        orch, proj = self._setup(tmp_path, strategy="stacked")
        epic = _make_issue(identifier="epic-1", issue_type="epic",
                           project_id="proj-1", state="open")
        provider = MagicMock()
        with patch.object(orch, "_fetch_epic_children", return_value=[]), \
             patch("oompah.orchestrator.detect_provider", return_value=provider):
            opened = orch._open_epic_main_prs([epic])
        assert opened == 0
        provider.create_review.assert_not_called()

    def test_skips_when_child_not_terminal(self, tmp_path):
        orch, proj = self._setup(tmp_path, strategy="stacked")
        epic = _make_issue(identifier="epic-1", issue_type="epic",
                           project_id="proj-1", state="open")
        child_open = _make_issue(identifier="c1", state="open")
        child_closed = _make_issue(identifier="c2", state="closed")
        provider = MagicMock()
        with patch.object(orch, "_fetch_epic_children",
                          return_value=[child_open, child_closed]), \
             patch("oompah.orchestrator.detect_provider", return_value=provider):
            opened = orch._open_epic_main_prs([epic])
        assert opened == 0
        provider.create_review.assert_not_called()

    def test_skips_when_epic_already_terminal(self, tmp_path):
        orch, proj = self._setup(tmp_path, strategy="shared")
        epic = _make_issue(identifier="epic-1", issue_type="epic",
                           project_id="proj-1", state="closed")
        provider = MagicMock()
        with patch.object(orch, "_fetch_epic_children",
                          return_value=[_make_issue(state="closed")]), \
             patch("oompah.orchestrator.detect_provider", return_value=provider):
            opened = orch._open_epic_main_prs([epic])
        assert opened == 0
        provider.create_review.assert_not_called()

    def test_creates_pr_for_stacked_when_all_children_closed(self, tmp_path):
        orch, proj = self._setup(tmp_path, strategy="stacked")
        orch.project_store.epic_branch_name.side_effect = (
            lambda i: f"epic-{i}"
        )
        epic = _make_issue(
            identifier="epic-1", issue_type="epic", project_id="proj-1",
            state="open", title="Epic feature", description="Body of epic",
        )
        child = _make_issue(identifier="c1", state="closed")
        provider = MagicMock()
        provider.create_review.return_value = MagicMock(id="99")
        with patch.object(orch, "_fetch_epic_children", return_value=[child]), \
             patch("oompah.orchestrator.detect_provider", return_value=provider), \
             patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"), \
             patch.object(orch, "_push_epic_branch") as push:
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
        orch.project_store.epic_branch_name.side_effect = (
            lambda i: f"epic-{i}"
        )
        epic = _make_issue(
            identifier="epic-1", issue_type="epic", project_id="proj-1",
            state="open", title="Shared work", description="Doc body",
        )
        child = _make_issue(identifier="c1", state="closed")
        provider = MagicMock()
        provider.create_review.return_value = MagicMock(id="100")
        with patch.object(orch, "_fetch_epic_children", return_value=[child]), \
             patch("oompah.orchestrator.detect_provider", return_value=provider), \
             patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"), \
             patch.object(orch, "_push_epic_branch"):
            opened = orch._open_epic_main_prs([epic])
        assert opened == 1

    def test_idempotent_when_pr_already_exists(self, tmp_path):
        orch, proj = self._setup(tmp_path, strategy="stacked")
        orch.project_store.epic_branch_name.side_effect = (
            lambda i: f"epic-{i}"
        )
        epic = _make_issue(identifier="epic-1", issue_type="epic",
                           project_id="proj-1", state="open")
        child = _make_issue(state="closed")
        existing_review = MagicMock()
        existing_review.source_branch = "epic-epic-1"
        existing_review.draft = False
        orch._reviews_cache = {"proj-1": [existing_review]}
        provider = MagicMock()
        with patch.object(orch, "_fetch_epic_children", return_value=[child]), \
             patch("oompah.orchestrator.detect_provider", return_value=provider), \
             patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"), \
             patch.object(orch, "_push_epic_branch") as push:
            opened = orch._open_epic_main_prs([epic])
        assert opened == 0
        provider.create_review.assert_not_called()
        push.assert_not_called()

    def test_skips_when_provider_unavailable(self, tmp_path):
        orch, proj = self._setup(tmp_path, strategy="stacked")
        epic = _make_issue(identifier="epic-1", issue_type="epic",
                           project_id="proj-1", state="open")
        child = _make_issue(state="closed")
        with patch.object(orch, "_fetch_epic_children", return_value=[child]), \
             patch("oompah.orchestrator.detect_provider", return_value=None):
            opened = orch._open_epic_main_prs([epic])
        assert opened == 0
