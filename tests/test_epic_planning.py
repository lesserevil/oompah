"""Tests for epic planning: _should_dispatch_epic, _fetch_epic_children, _plan_open_epics."""

import asyncio
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
) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=title or f"Issue {identifier}",
        state=state,
        issue_type=issue_type,
        priority=priority,
        labels=labels or [],
        project_id=project_id,
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
        config.max_concurrent_agents = 0
        project_store = MagicMock()
        project_store.list_all.return_value = []
        orch = Orchestrator(
            config=config,
            workflow_path="WORKFLOW.md",
            project_store=project_store,
            state_path=str(tmp_path / "state.json"),
        )
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
        mock_tracker.fetch_children.side_effect = TrackerError("bd failed")
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
        mock_tracker.fetch_children.side_effect = TrackerError("bd failed")
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
        config.max_concurrent_agents = 0
        project_store = MagicMock()
        project_store.list_all.return_value = [project]
        project_store.get.side_effect = lambda pid: project if pid == project.id else None
        orch = Orchestrator(
            config=config,
            workflow_path="WORKFLOW.md",
            project_store=project_store,
            state_path=str(tmp_path / "state.json"),
        )

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


class TestEpicPlannerFocusSelection:
    """Tests that the epic_planner focus is selected for epic issues."""

    def test_epic_gets_epic_planner_focus(self):
        """When an epic is dispatched, select_focus should return epic_planner."""
        from oompah.focus import select_focus

        epic = _make_epic(title="Build new payment system")
        focus = select_focus(epic)
        assert focus.name == "epic_planner"
        assert focus.role == "Epic Planner"

    def test_epic_planner_must_do_includes_bd_create(self):
        """The epic_planner focus should tell the agent to use bd create."""
        from oompah.focus import select_focus

        epic = _make_epic()
        focus = select_focus(epic)
        assert any("bd create" in rule for rule in focus.must_do)

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
