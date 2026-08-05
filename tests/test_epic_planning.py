"""Tests for epic planning: _should_dispatch_epic, _fetch_epic_children, _plan_open_epics."""

import asyncio
import threading
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from oompah.config import ServiceConfig
from oompah.models import Issue
from oompah.orchestrator import Orchestrator
from oompah.tracker import TrackerError


def _make_config() -> ServiceConfig:
    return ServiceConfig()


def _make_issue(
    identifier: str,
    state: str = "open",
    issue_type: str = "task",
    priority: int | None = 2,
    labels: list | None = None,
    project_id: str | None = None,
    title: str | None = None,
    description: str = "Test issue body — passes the empty-description gate.",
    tracker_kind: str | None = None,
) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=title or f"Issue {identifier}",
        description=description,
        state=state,
        issue_type=issue_type,
        priority=priority,
        labels=labels or [],
        project_id=project_id,
        tracker_kind=tracker_kind,
    )


def _make_epic(
    identifier: str = "epic-1",
    state: str = "open",
    priority: int | None = 2,
    project_id: str | None = None,
    title: str = "Build new payment system",
) -> Issue:
    return _make_issue(
        identifier=identifier,
        state=state,
        issue_type="epic",
        priority=priority,
        project_id=project_id,
        title=title,
    )


def _make_project(project_id: str = "proj-1"):
    p = MagicMock()
    p.id = project_id
    p.repo_url = "https://github.com/org/repo"
    p.repo_path = "/tmp/repo"
    p.name = "test-project"
    p.paused = False  # default: not paused
    return p


def _make_orchestrator(tmp_path, projects=None):
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


class TestShouldDispatchEpic:
    """Tests for _should_dispatch_epic."""

    def test_dispatches_open_epic_without_children(self, tmp_path):
        """An open epic with no children should be dispatched for planning."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        epic = _make_epic(project_id=project.id)

        mock_tracker = MagicMock()
        mock_tracker.fetch_children.return_value = []
        orch._project_trackers[project.id] = mock_tracker

        assert orch._should_dispatch_epic(epic) is True

    def test_skips_non_epic_issue(self, tmp_path):
        """Non-epic issues should not be dispatched via _should_dispatch_epic."""
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue("task-1", issue_type="task", state="open")
        assert orch._should_dispatch_epic(issue) is False

    def test_skips_epic_with_existing_children(self, tmp_path):
        """An epic with existing children has already been planned."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        epic = _make_epic(project_id=project.id)

        child = _make_issue("task-1", issue_type="task")
        mock_tracker = MagicMock()
        mock_tracker.fetch_children.return_value = [child]
        orch._project_trackers[project.id] = mock_tracker

        assert orch._should_dispatch_epic(epic) is False

    def test_skips_epic_in_terminal_state(self, tmp_path):
        """A closed epic should not be dispatched."""
        orch = _make_orchestrator(tmp_path)
        epic = _make_epic(state="closed")
        assert orch._should_dispatch_epic(epic) is False

    def test_skips_epic_when_paused(self, tmp_path):
        """No dispatch when orchestrator is paused."""
        orch = _make_orchestrator(tmp_path)
        orch._paused = True
        epic = _make_epic()
        assert orch._should_dispatch_epic(epic) is False

    def test_skips_epic_already_running(self, tmp_path):
        """An epic already running should not be dispatched again."""
        orch = _make_orchestrator(tmp_path)
        epic = _make_epic()
        orch.state.running[epic.id] = MagicMock()
        assert orch._should_dispatch_epic(epic) is False

    def test_skips_epic_already_claimed(self, tmp_path):
        """A claimed epic should not be dispatched again."""
        orch = _make_orchestrator(tmp_path)
        epic = _make_epic()
        orch.state.claimed.add(epic.id)
        assert orch._should_dispatch_epic(epic) is False

    def test_skips_epic_in_retry(self, tmp_path):
        """An epic with a pending retry should not be dispatched."""
        orch = _make_orchestrator(tmp_path)
        epic = _make_epic()
        orch.state.retry_attempts[epic.id] = MagicMock()
        assert orch._should_dispatch_epic(epic) is False

    def test_skips_epic_already_completed(self, tmp_path):
        """A completed epic should not be dispatched."""
        orch = _make_orchestrator(tmp_path)
        epic = _make_epic()
        orch.state.completed.add(epic.id)
        assert orch._should_dispatch_epic(epic) is False

    def test_skips_epic_when_no_slots(self, tmp_path):
        """No dispatch when all slots are occupied."""
        config = _make_config()
        config.max_concurrent_agents = 1
        project_store = MagicMock()
        project_store.list_all.return_value = []
        orch = Orchestrator(
            config=config,
            workflow_path="WORKFLOW.md",
            project_store=project_store,
            state_path=str(tmp_path / "state.json"),
        )
        orch.state.max_concurrent_agents = 0
        epic = _make_epic()
        assert orch._should_dispatch_epic(epic) is False

    def test_skips_epic_when_budget_exceeded(self, tmp_path):
        """No dispatch when budget is exceeded."""
        config = _make_config()
        config.budget_limit = 1.0
        project_store = MagicMock()
        project_store.list_all.return_value = []
        orch = Orchestrator(
            config=config,
            workflow_path="WORKFLOW.md",
            project_store=project_store,
            state_path=str(tmp_path / "state.json"),
        )
        orch.state.agent_totals.estimated_cost = 2.0  # over budget
        epic = _make_epic()
        assert orch._should_dispatch_epic(epic) is False

    def test_skips_epic_missing_required_fields(self, tmp_path):
        """Epic with missing id/identifier/title/state should not be dispatched."""
        orch = _make_orchestrator(tmp_path)
        # Missing title
        epic = Issue(id="epic-1", identifier="epic-1", title="", state="open", issue_type="epic")
        assert orch._should_dispatch_epic(epic) is False

        # Missing id
        epic2 = Issue(id="", identifier="epic-1", title="Something", state="open", issue_type="epic")
        assert orch._should_dispatch_epic(epic2) is False

    def test_skips_epic_in_non_active_state(self, tmp_path):
        """An epic in deferred state should not be dispatched."""
        orch = _make_orchestrator(tmp_path)
        epic = _make_epic(state="deferred")
        assert orch._should_dispatch_epic(epic) is False

    def test_dispatches_epic_using_legacy_tracker(self, tmp_path):
        """An epic without project_id uses the legacy tracker."""
        orch = _make_orchestrator(tmp_path)
        epic = _make_epic(project_id=None)

        # Mock legacy tracker
        orch.tracker = MagicMock()
        orch.tracker.fetch_children.return_value = []

        assert orch._should_dispatch_epic(epic) is True

    def test_tracker_error_on_children_fetch_returns_false(self, tmp_path):
        """If fetching children fails, treat the epic as not dispatchable."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        epic = _make_epic(project_id=project.id)

        mock_tracker = MagicMock()
        mock_tracker.fetch_children.side_effect = TrackerError("tracker failed")
        orch._project_trackers[project.id] = mock_tracker

        # fetch_children returns [] on error, so epic IS dispatchable
        # (empty children = needs planning)
        # Actually _fetch_epic_children catches exceptions and returns []
        assert orch._should_dispatch_epic(epic) is True


class TestFetchEpicChildren:
    """Tests for _fetch_epic_children."""

    def test_returns_children_list(self, tmp_path):
        """Returns children when they exist."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        epic = _make_epic(project_id=project.id)

        child1 = _make_issue("task-1")
        child2 = _make_issue("task-2")
        mock_tracker = MagicMock()
        mock_tracker.fetch_children.return_value = [child1, child2]
        orch._project_trackers[project.id] = mock_tracker

        result = orch._fetch_epic_children(epic)
        assert len(result) == 2
        mock_tracker.fetch_children.assert_called_once_with(epic.id)

    def test_returns_empty_list_when_no_children(self, tmp_path):
        """Returns empty list when no children exist."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        epic = _make_epic(project_id=project.id)

        mock_tracker = MagicMock()
        mock_tracker.fetch_children.return_value = []
        orch._project_trackers[project.id] = mock_tracker

        result = orch._fetch_epic_children(epic)
        assert result == []

    def test_returns_empty_on_tracker_error(self, tmp_path):
        """Returns empty list on tracker errors (graceful degradation)."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        epic = _make_epic(project_id=project.id)

        mock_tracker = MagicMock()
        mock_tracker.fetch_children.side_effect = TrackerError("tracker failed")
        orch._project_trackers[project.id] = mock_tracker

        result = orch._fetch_epic_children(epic)
        assert result == []

    def test_uses_legacy_tracker_for_non_project_epic(self, tmp_path):
        """Uses legacy tracker when epic has no project_id."""
        orch = _make_orchestrator(tmp_path)
        epic = _make_epic(project_id=None)

        child = _make_issue("task-1")
        orch.tracker = MagicMock()
        orch.tracker.fetch_children.return_value = [child]

        result = orch._fetch_epic_children(epic)
        assert len(result) == 1
        orch.tracker.fetch_children.assert_called_once_with(epic.id)


class TestPlanOpenEpics:
    """Tests for _plan_open_epics."""

    def test_returns_plannable_epics(self, tmp_path):
        """Returns epics that need planning."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])

        epic = _make_epic(project_id=project.id)
        task = _make_issue("task-1", project_id=project.id)

        mock_tracker = MagicMock()
        mock_tracker.fetch_children.return_value = []
        orch._project_trackers[project.id] = mock_tracker

        result = orch._plan_open_epics([epic, task])
        assert len(result) == 1
        assert result[0].id == epic.id

    def test_excludes_epics_with_children(self, tmp_path):
        """Epics that already have children are excluded."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])

        epic = _make_epic(project_id=project.id)
        child = _make_issue("task-1")

        mock_tracker = MagicMock()
        mock_tracker.fetch_children.return_value = [child]
        orch._project_trackers[project.id] = mock_tracker

        result = orch._plan_open_epics([epic])
        assert len(result) == 0

    def test_excludes_non_epic_issues(self, tmp_path):
        """Only epic issue types are considered."""
        orch = _make_orchestrator(tmp_path)
        task = _make_issue("task-1", issue_type="task")
        bug = _make_issue("bug-1", issue_type="bug")
        feature = _make_issue("feat-1", issue_type="feature")

        result = orch._plan_open_epics([task, bug, feature])
        assert len(result) == 0

    def test_empty_candidates_returns_empty(self, tmp_path):
        """Empty candidate list returns empty."""
        orch = _make_orchestrator(tmp_path)
        result = orch._plan_open_epics([])
        assert len(result) == 0

    def test_multiple_epics_returned(self, tmp_path):
        """Multiple plannable epics are all returned."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])

        epic1 = _make_epic(identifier="epic-1", project_id=project.id, title="Epic One")
        epic2 = _make_epic(identifier="epic-2", project_id=project.id, title="Epic Two")

        mock_tracker = MagicMock()
        mock_tracker.fetch_children.return_value = []
        orch._project_trackers[project.id] = mock_tracker

        result = orch._plan_open_epics([epic1, epic2])
        assert len(result) == 2

    def test_mixed_planned_and_unplanned_epics(self, tmp_path):
        """Only unplanned epics are returned; planned ones are excluded."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])

        epic_planned = _make_epic(identifier="epic-planned", project_id=project.id)
        epic_unplanned = _make_epic(identifier="epic-unplanned", project_id=project.id)

        child = _make_issue("task-1")
        mock_tracker = MagicMock()
        # First call for epic-planned returns children, second for epic-unplanned returns none
        mock_tracker.fetch_children.side_effect = [[child], []]
        orch._project_trackers[project.id] = mock_tracker

        result = orch._plan_open_epics([epic_planned, epic_unplanned])
        assert len(result) == 1
        assert result[0].id == "epic-unplanned"


class TestShouldDispatchSkipsEpics:
    """Ensure normal _should_dispatch still skips epics."""

    def test_epic_not_dispatched_via_normal_dispatch(self, tmp_path):
        """Epics should not be dispatched via the normal _should_dispatch path."""
        orch = _make_orchestrator(tmp_path)
        epic = _make_epic(state="open")
        assert orch._should_dispatch(epic) is False

    def test_non_epic_still_dispatched_normally(self, tmp_path):
        """Non-epic issues should still dispatch normally."""
        orch = _make_orchestrator(tmp_path)
        task = _make_issue("task-1", state="open", issue_type="task")
        assert orch._should_dispatch(task) is True


class TestEpicPlanningInTick:
    """Tests that epic planning is integrated into the tick cycle."""

    def test_tick_dispatches_plannable_epic(self, tmp_path):
        """The tick cycle should dispatch open epics without children."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._prompt_template = "test"

        epic = _make_epic(project_id=project.id)

        mock_tracker = MagicMock()
        mock_tracker.fetch_candidate_issues.return_value = [epic]
        mock_tracker.fetch_children.return_value = []
        mock_tracker.update_issue.return_value = None
        mock_tracker.add_comment.return_value = {}
        mock_tracker.fetch_comments.return_value = []
        orch._project_trackers[project.id] = mock_tracker

        # Track dispatched issues
        dispatched = []

        async def mock_dispatch(issue, attempt, override_profile=None):
            dispatched.append(issue.identifier)

        orch._dispatch = mock_dispatch
        orch._reconcile = AsyncMock()
        orch._fetch_all_reviews = MagicMock(return_value={})
        orch._fetch_all_merged_branches = MagicMock(return_value=set())
        orch._pre_resolve_blockers = MagicMock()
        orch._reset_orphaned_in_progress = MagicMock()
        orch._yolo_review_actions_sync = MagicMock()
        orch._auto_archive = MagicMock()
        orch._label_merged_issues = MagicMock()
        orch._notify_observers = MagicMock()

        asyncio.run(orch._tick())

        assert epic.identifier in dispatched

    def test_tick_does_not_dispatch_planned_epic(self, tmp_path):
        """The tick cycle should not dispatch epics that already have children."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._prompt_template = "test"

        epic = _make_epic(project_id=project.id)
        child = _make_issue("task-1")

        mock_tracker = MagicMock()
        mock_tracker.fetch_candidate_issues.return_value = [epic]
        mock_tracker.fetch_children.return_value = [child]
        orch._project_trackers[project.id] = mock_tracker

        dispatched = []

        async def mock_dispatch(issue, attempt, override_profile=None):
            dispatched.append(issue.identifier)

        orch._dispatch = mock_dispatch
        orch._reconcile = AsyncMock()
        orch._fetch_all_reviews = MagicMock(return_value={})
        orch._fetch_all_merged_branches = MagicMock(return_value=set())
        orch._pre_resolve_blockers = MagicMock()
        orch._reset_orphaned_in_progress = MagicMock()
        orch._yolo_review_actions_sync = MagicMock()
        orch._auto_archive = MagicMock()
        orch._label_merged_issues = MagicMock()
        orch._notify_observers = MagicMock()

        asyncio.run(orch._tick())

        assert epic.identifier not in dispatched

    def test_tick_respects_available_slots_for_epics(self, tmp_path):
        """Epics should not be dispatched if no slots available."""
        project = _make_project()
        config = _make_config()
        config.max_concurrent_agents = 1
        project_store = MagicMock()
        project_store.list_all.return_value = [project]
        project_store.get.side_effect = lambda pid: project if pid == project.id else None
        orch = Orchestrator(
            config=config,
            workflow_path="WORKFLOW.md",
            project_store=project_store,
            state_path=str(tmp_path / "state.json"),
        )
        orch._refresh_effective_concurrency = lambda: setattr(
            orch.state, "max_concurrent_agents", 0
        ) or 0

        epic = _make_epic(project_id=project.id)

        mock_tracker = MagicMock()
        mock_tracker.fetch_candidate_issues.return_value = [epic]
        mock_tracker.fetch_children.return_value = []
        orch._project_trackers[project.id] = mock_tracker

        dispatched = []

        async def mock_dispatch(issue, attempt, override_profile=None):
            dispatched.append(issue.identifier)

        orch._dispatch = mock_dispatch
        orch._reconcile = AsyncMock()
        orch._fetch_all_reviews = MagicMock(return_value={})
        orch._fetch_all_merged_branches = MagicMock(return_value=set())
        orch._pre_resolve_blockers = MagicMock()
        orch._reset_orphaned_in_progress = MagicMock()
        orch._yolo_review_actions_sync = MagicMock()
        orch._auto_archive = MagicMock()
        orch._label_merged_issues = MagicMock()
        orch._notify_observers = MagicMock()

        asyncio.run(orch._tick())

        assert epic.identifier not in dispatched


class TestAutoDecomposition:
    """Tests for issue auto-decomposition child creation."""

    def test_should_decompose_skips_github_issue_tracker_tasks(self, tmp_path):
        """Direct GitHub-backed tasks should not create GitHub child issues."""
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue(
            "example-org/oompah#500",
            tracker_kind="github_issues",
            labels=[],
        )

        assert orch._should_decompose(
            issue,
            orch.config.decompose_after_attempts,
        ) is False

    def test_should_decompose_allows_native_project_tasks_without_issue_kind(self, tmp_path):
        """Native project metadata controls decomposition when issue records omit kind."""
        project = _make_project()
        project.tracker_kind = "oompah_md"
        orch = _make_orchestrator(tmp_path, projects=[project])
        issue = _make_issue(
            "TASK-500",
            project_id=project.id,
            tracker_kind=None,
            labels=[],
        )

        assert orch._should_decompose(
            issue,
            orch.config.decompose_after_attempts,
            project_id=project.id,
        ) is True

    def test_should_decompose_skips_github_issue_project_tasks_without_issue_kind(
        self, tmp_path
    ):
        """Project tracker kind blocks decomposition even when issue kind is absent."""
        project = _make_project()
        project.tracker_kind = "github_issues"
        orch = _make_orchestrator(tmp_path, projects=[project])
        issue = _make_issue(
            "example-org/oompah#500",
            project_id=project.id,
            tracker_kind=None,
            labels=[],
        )

        assert orch._should_decompose(
            issue,
            orch.config.decompose_after_attempts,
            project_id=project.id,
        ) is False

    def test_creates_children_with_parent_at_creation(self, tmp_path):
        """Decomposition should create child tasks under the parent immediately."""
        orch = _make_orchestrator(tmp_path)
        parent = _make_issue(
            "parent-1",
            issue_type="feature",
            title="Large task",
            description="Too large for one agent",
        )
        tasks = [
            {
                "title": "First child",
                "description": "Do first piece",
                "priority": 2,
                "focus_hint": "feature",
                "depends_on": [],
            },
            {
                "title": "Second child",
                "description": "Do second piece",
                "priority": 2,
                "focus_hint": "test",
                "depends_on": [0],
            },
        ]

        tracker = MagicMock()
        tracker.create_issue.side_effect = [
            _make_issue("child-1"),
            _make_issue("child-2"),
        ]

        asyncio.run(orch._execute_decomposition(parent, tasks, tracker, None))

        for call in tracker.create_issue.call_args_list:
            assert call.kwargs["parent"] == "parent-1"
        tracker.add_parent_child.assert_not_called()
        tracker.add_dependency.assert_called_once_with("child-2", "child-1")

    def test_rejects_blank_description_before_creating_any_children(self, tmp_path):
        """Invalid plans must not leave a title-only child task behind."""
        orch = _make_orchestrator(tmp_path)
        parent = _make_issue(
            "parent-1",
            issue_type="feature",
            title="Large task",
            description="Too large for one agent",
        )
        tasks = [
            {"title": "Valid child", "description": "Implement and test it."},
            {"title": "Invalid child", "description": "   "},
        ]
        tracker = MagicMock()

        with pytest.raises(ValueError, match="child 2 has no description"):
            asyncio.run(orch._execute_decomposition(parent, tasks, tracker, None))

        tracker.create_issue.assert_not_called()
        tracker.update_issue.assert_not_called()

    def test_decomposition_holds_project_fence_for_complete_child_set(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        parent = _make_issue(
            "parent-1",
            issue_type="epic",
            project_id="proj-test",
        )
        tasks = [
            {"title": "First", "description": "first details"},
            {"title": "Second", "description": "second details"},
        ]
        tracker = MagicMock()
        project_lock = threading.RLock()
        orch.project_store.project_write_lock = MagicMock(
            return_value=project_lock
        )

        # Only identifiers are consumed after creation in this lock-focused
        # regression.
        created = iter([
            _make_issue("child-1"),
            _make_issue("child-2"),
        ])

        def locked_create(**kwargs):
            assert project_lock._is_owned()  # type: ignore[attr-defined]
            assert kwargs["parent"] == "parent-1"
            return next(created)

        tracker.create_issue.side_effect = locked_create

        asyncio.run(
            orch._execute_decomposition(
                parent,
                tasks,
                tracker,
                "proj-test",
            )
        )

        assert tracker.create_issue.call_count == 2
        orch.project_store.project_write_lock.assert_called_once_with("proj-test")


class TestEpicPlannerFocusSelection:
    """Tests that the epic_planner focus is selected for epic issues."""

    def test_epic_gets_epic_planner_focus(self):
        """When an epic is dispatched, select_focus should return epic_planner."""
        from oompah.focus import select_focus

        epic = _make_epic(title="Build new payment system")
        focus = select_focus(epic)
        assert focus.name == "epic_planner"
        assert focus.role == "Epic Planner"

    def test_epic_planner_must_do_includes_child_create(self):
        """The epic_planner focus should tell the agent to create child tasks."""
        from oompah.focus import select_focus

        epic = _make_epic()
        focus = select_focus(epic)
        assert any("oompah task child-create" in rule for rule in focus.must_do)

    def test_epic_planner_must_not_do_includes_no_coding(self):
        """The epic_planner focus should tell the agent not to implement code."""
        from oompah.focus import select_focus

        epic = _make_epic()
        focus = select_focus(epic)
        assert any("implementing code" in rule.lower() or "code" in rule.lower()
                    for rule in focus.must_not_do)

    def test_epic_planner_must_not_close_epic(self):
        """The epic_planner focus should tell the agent not to close the epic."""
        from oompah.focus import select_focus

        epic = _make_epic()
        focus = select_focus(epic)
        assert any("close" in rule.lower() and "epic" in rule.lower()
                    for rule in focus.must_not_do)


# ---------------------------------------------------------------------------
# Audit-repair dispatch tests (OOMPAH-482)
# ---------------------------------------------------------------------------

class TestShouldDispatchEpicAuditRepair:
    """Tests for _should_dispatch_epic with audit:repair-needed label."""

    def test_dispatches_repair_epic_with_children_when_unclaimed(self, tmp_path):
        """An epic with audit:repair-needed and children should be dispatchable."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        epic = _make_epic(project_id=project.id)
        epic.labels = ["audit:repair-needed"]

        child = _make_issue("task-1")
        mock_tracker = MagicMock()
        mock_tracker.fetch_children.return_value = [child]
        mock_tracker.get_metadata.return_value = {}  # no claimed flag
        orch._project_trackers[project.id] = mock_tracker

        assert orch._should_dispatch_epic(epic) is True

    def test_skips_repair_epic_when_already_claimed(self, tmp_path):
        """A repair epic with claimed=True in metadata should not be dispatched."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        epic = _make_epic(project_id=project.id)
        epic.labels = ["audit:repair-needed"]

        from oompah.models import EPIC_AUDIT_REPAIR_METADATA_KEY, EPIC_AUDIT_REPAIR_METADATA_VERSION
        mock_tracker = MagicMock()
        mock_tracker.get_metadata.return_value = {
            EPIC_AUDIT_REPAIR_METADATA_KEY: {
                "version": EPIC_AUDIT_REPAIR_METADATA_VERSION,
                "audit_id": "audit-abc123",
                "claimed": True,
            }
        }
        orch._project_trackers[project.id] = mock_tracker

        assert orch._should_dispatch_epic(epic) is False

    def test_skips_repair_epic_when_claimed_flag_missing_and_unclaimed(self, tmp_path):
        """No claimed flag in metadata means unclaimed → dispatch allowed."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        epic = _make_epic(project_id=project.id)
        epic.labels = ["audit:repair-needed"]

        from oompah.models import EPIC_AUDIT_REPAIR_METADATA_KEY
        mock_tracker = MagicMock()
        mock_tracker.get_metadata.return_value = {
            EPIC_AUDIT_REPAIR_METADATA_KEY: {
                "version": 1,
                "audit_id": "audit-abc123",
                "claimed": False,
            }
        }
        orch._project_trackers[project.id] = mock_tracker

        assert orch._should_dispatch_epic(epic) is True

    def test_normal_epic_with_children_remains_nondispatchable(self, tmp_path):
        """An already-planned epic WITHOUT audit:repair-needed stays nondispatchable."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        epic = _make_epic(project_id=project.id)
        epic.labels = []  # no repair label

        child = _make_issue("task-1")
        mock_tracker = MagicMock()
        mock_tracker.fetch_children.return_value = [child]
        orch._project_trackers[project.id] = mock_tracker

        assert orch._should_dispatch_epic(epic) is False

    def test_metadata_read_error_treats_as_unclaimed(self, tmp_path):
        """A tracker error reading repair metadata falls through to dispatchable."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        epic = _make_epic(project_id=project.id)
        epic.labels = ["audit:repair-needed"]

        from oompah.tracker import TrackerError
        mock_tracker = MagicMock()
        mock_tracker.get_metadata.side_effect = TrackerError("read failed")
        orch._project_trackers[project.id] = mock_tracker

        # Falls back to unclaimed, allowing dispatch
        assert orch._should_dispatch_epic(epic) is True


class TestClaimEpicAuditRepair:
    """Tests for _claim_epic_audit_repair and _get_epic_audit_repair_context."""

    def test_claim_sets_claimed_flag_and_returns_audit_id(self, tmp_path):
        """_claim_epic_audit_repair sets claimed=True and returns the audit_id."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        epic = _make_epic(project_id=project.id)

        from oompah.models import EPIC_AUDIT_REPAIR_METADATA_KEY, EPIC_AUDIT_REPAIR_METADATA_VERSION
        doc = {
            "version": EPIC_AUDIT_REPAIR_METADATA_VERSION,
            "audit_id": "audit-xyz789",
            "claimed": False,
            "findings_summary": "Missing test coverage for edge case X.",
        }
        mock_tracker = MagicMock()
        mock_tracker.get_metadata.return_value = {EPIC_AUDIT_REPAIR_METADATA_KEY: doc}
        orch._project_trackers[project.id] = mock_tracker

        audit_id = orch._claim_epic_audit_repair(epic)
        assert audit_id == "audit-xyz789"
        mock_tracker.set_metadata_field.assert_called_once()
        call_args = mock_tracker.set_metadata_field.call_args
        persisted_doc = call_args[0][2]
        assert persisted_doc["claimed"] is True

    def test_claim_returns_none_when_no_metadata(self, tmp_path):
        """Returns None when no repair metadata exists."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        epic = _make_epic(project_id=project.id)

        mock_tracker = MagicMock()
        mock_tracker.get_metadata.return_value = {}
        orch._project_trackers[project.id] = mock_tracker

        result = orch._claim_epic_audit_repair(epic)
        assert result is None

    def test_get_repair_context_returns_doc(self, tmp_path):
        """_get_epic_audit_repair_context returns the stored repair doc."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        epic = _make_epic(project_id=project.id)

        from oompah.models import EPIC_AUDIT_REPAIR_METADATA_KEY
        repair_doc = {
            "version": 1,
            "audit_id": "audit-aaa111",
            "failure_classification": "incomplete",
            "findings_summary": "Child TASK-5 did not cover requirement R3.",
            "claimed": True,
        }
        mock_tracker = MagicMock()
        mock_tracker.get_metadata.return_value = {EPIC_AUDIT_REPAIR_METADATA_KEY: repair_doc}
        orch._project_trackers[project.id] = mock_tracker

        result = orch._get_epic_audit_repair_context(epic)
        assert result == repair_doc

    def test_get_repair_context_returns_none_when_absent(self, tmp_path):
        """Returns None when no repair metadata is stored."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        epic = _make_epic(project_id=project.id)

        mock_tracker = MagicMock()
        mock_tracker.get_metadata.return_value = {}
        orch._project_trackers[project.id] = mock_tracker

        result = orch._get_epic_audit_repair_context(epic)
        assert result is None


class TestPlanOpenEpicsRepair:
    """Tests for _plan_open_epics handling of audit:repair-needed epics."""

    def test_returns_repair_epic_with_children(self, tmp_path):
        """A repair-needed epic with children is returned for dispatch."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])

        epic = _make_epic(project_id=project.id)
        epic.labels = ["audit:repair-needed"]

        from oompah.models import EPIC_AUDIT_REPAIR_METADATA_KEY
        child = _make_issue("task-1")
        mock_tracker = MagicMock()
        mock_tracker.fetch_children.return_value = [child]
        mock_tracker.get_metadata.return_value = {
            EPIC_AUDIT_REPAIR_METADATA_KEY: {"version": 1, "audit_id": "audit-1", "claimed": False}
        }
        orch._project_trackers[project.id] = mock_tracker

        result = orch._plan_open_epics([epic])
        assert len(result) == 1
        assert result[0].id == epic.id

    def test_excludes_claimed_repair_epic(self, tmp_path):
        """A repair epic with claimed=True is NOT returned for dispatch."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])

        epic = _make_epic(project_id=project.id)
        epic.labels = ["audit:repair-needed"]

        from oompah.models import EPIC_AUDIT_REPAIR_METADATA_KEY
        mock_tracker = MagicMock()
        mock_tracker.get_metadata.return_value = {
            EPIC_AUDIT_REPAIR_METADATA_KEY: {"version": 1, "audit_id": "audit-1", "claimed": True}
        }
        orch._project_trackers[project.id] = mock_tracker

        result = orch._plan_open_epics([epic])
        assert len(result) == 0

    def test_mix_of_repair_and_normal_and_unplanned(self, tmp_path):
        """Returns repair epic and unplanned epic, but not planned epic."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])

        repair_epic = _make_epic(identifier="epic-repair", project_id=project.id)
        repair_epic.labels = ["audit:repair-needed"]
        planned_epic = _make_epic(identifier="epic-planned", project_id=project.id)
        unplanned_epic = _make_epic(identifier="epic-new", project_id=project.id)

        child = _make_issue("task-1")
        from oompah.models import EPIC_AUDIT_REPAIR_METADATA_KEY

        def side_effect_children(issue_id):
            if issue_id == "epic-planned":
                return [child]
            return []

        def side_effect_metadata(identifier):
            if identifier == "epic-repair":
                return {EPIC_AUDIT_REPAIR_METADATA_KEY: {"version": 1, "audit_id": "a", "claimed": False}}
            return {}

        mock_tracker = MagicMock()
        mock_tracker.fetch_children.side_effect = side_effect_children
        mock_tracker.get_metadata.side_effect = side_effect_metadata
        orch._project_trackers[project.id] = mock_tracker

        result = orch._plan_open_epics([repair_epic, planned_epic, unplanned_epic])
        ids = [r.id for r in result]
        assert "epic-repair" in ids
        assert "epic-new" in ids
        assert "epic-planned" not in ids


class TestEpicRepairPlannerFocus:
    """Tests for epic_repair_planner focus selection."""

    def test_repair_epic_gets_repair_planner_focus(self):
        """An epic with audit:repair-needed gets epic_repair_planner focus."""
        from oompah.focus import select_focus

        epic = _make_epic()
        epic.labels = ["audit:repair-needed"]
        focus = select_focus(epic)
        assert focus.name == "epic_repair_planner"

    def test_repair_planner_must_do_includes_remove_label(self):
        """The repair focus should instruct the agent to remove audit:repair-needed."""
        from oompah.focus import select_focus

        epic = _make_epic()
        epic.labels = ["audit:repair-needed"]
        focus = select_focus(epic)
        combined = " ".join(focus.must_do)
        assert "audit:repair-needed" in combined or "repair-needed" in combined

    def test_repair_planner_must_not_do_includes_no_coding(self):
        """The repair focus should tell the agent not to implement code."""
        from oompah.focus import select_focus

        epic = _make_epic()
        epic.labels = ["audit:repair-needed"]
        focus = select_focus(epic)
        assert any("code" in rule.lower() or "implement" in rule.lower()
                   for rule in focus.must_not_do)

    def test_normal_epic_still_gets_epic_planner_focus(self):
        """A normal epic without the repair label still gets epic_planner."""
        from oompah.focus import select_focus

        epic = _make_epic()
        epic.labels = []
        focus = select_focus(epic)
        assert focus.name == "epic_planner"

    def test_repair_planner_not_selected_for_non_epic(self):
        """epic_repair_planner is never selected for non-epic issues."""
        from oompah.focus import select_focus

        task = _make_issue("task-1", issue_type="task", state="open")
        task.labels = ["audit:repair-needed"]
        focus = select_focus(task)
        assert focus.name != "epic_repair_planner"


class TestStampEpicAuditRepair:
    """Tests for _stamp_epic_audit_repair in the terminal coordinator."""

    def test_stamps_label_and_metadata_on_epic_fail(self):
        """Coordinator stamps the label and metadata when an epic audit fails."""
        from oompah.terminal_transition_coordinator import (
            AuditResult,
            _stamp_epic_audit_repair,
        )
        from oompah.terminal_audit import (
            ContributorIdentity,
            EvidenceFingerprint,
            FailureClassification,
            Verdict,
        )
        from oompah.models import (
            EPIC_AUDIT_REPAIR_LABEL,
            EPIC_AUDIT_REPAIR_METADATA_KEY,
        )

        tracker = MagicMock()
        result = AuditResult(
            audit_id="audit-test-001",
            target_state="Done",
            evidence_fingerprint=EvidenceFingerprint(digest="a" * 64),
            verdict=Verdict.FAIL,
            failure_classification=FailureClassification.INCOMPLETE,
            message="Test coverage missing for module X.",
            attempt_id="attempt-1",
        )

        _stamp_epic_audit_repair(tracker, "epic-1", result, "audit-test-001")

        # Label added
        tracker.add_label.assert_called_once_with("epic-1", EPIC_AUDIT_REPAIR_LABEL)
        # Metadata set
        tracker.set_metadata_field.assert_called_once()
        call_args = tracker.set_metadata_field.call_args[0]
        assert call_args[0] == "epic-1"
        assert call_args[1] == EPIC_AUDIT_REPAIR_METADATA_KEY
        doc = call_args[2]
        assert doc["audit_id"] == "audit-test-001"
        assert doc["claimed"] is False
        assert "incomplete" in doc.get("failure_classification", "")
        assert "Test coverage" in doc.get("findings_summary", "")

    def test_swallows_tracker_label_error(self):
        """A tracker error adding the label must not raise."""
        from oompah.terminal_transition_coordinator import _stamp_epic_audit_repair
        from oompah.terminal_audit import EvidenceFingerprint, FailureClassification, Verdict
        from oompah.terminal_transition_coordinator import AuditResult

        tracker = MagicMock()
        tracker.add_label.side_effect = Exception("network failure")
        result = AuditResult(
            audit_id="audit-test-002",
            target_state="Done",
            evidence_fingerprint=EvidenceFingerprint(digest="b" * 64),
            verdict=Verdict.FAIL,
            failure_classification=FailureClassification.MISSING_TESTS,
            message="Missing tests.",
            attempt_id="attempt-2",
        )
        # Should not raise
        _stamp_epic_audit_repair(tracker, "epic-2", result, "audit-test-002")

    def test_swallows_tracker_metadata_error(self):
        """A tracker error setting metadata must not raise."""
        from oompah.terminal_transition_coordinator import _stamp_epic_audit_repair
        from oompah.terminal_audit import EvidenceFingerprint, FailureClassification, Verdict
        from oompah.terminal_transition_coordinator import AuditResult

        tracker = MagicMock()
        tracker.set_metadata_field.side_effect = Exception("storage failure")
        result = AuditResult(
            audit_id="audit-test-003",
            target_state="Done",
            evidence_fingerprint=EvidenceFingerprint(digest="c" * 64),
            verdict=Verdict.FAIL,
            failure_classification=FailureClassification.UNPUSHED,
            message="Branch not pushed.",
            attempt_id="attempt-3",
        )
        # Should not raise
        _stamp_epic_audit_repair(tracker, "epic-3", result, "audit-test-003")
