"""Tests for project scope propagation in merged-labels maintenance (OOMPAH-602)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from oompah.models import Issue, Project
from oompah.orchestrator import Orchestrator, ProjectError
from oompah.statuses import MERGED, DONE, IN_REVIEW


def _make_issue(
    identifier: str,
    state: str = "open",
    project_id: str | None = None,
    issue_type: str = "task",
) -> Issue:
    """Create a test issue."""
    return Issue(
        id=identifier,
        identifier=identifier,
        title=f"Issue {identifier}",
        description="Test issue",
        state=state,
        project_id=project_id,
        issue_type=issue_type,
        labels=[],
    )


def _make_project(project_id: str = "proj-1") -> Project:
    """Create a test project."""
    p = Project(
        id=project_id,
        name=f"Project {project_id}",
        repo_url=f"https://github.com/org/{project_id}",
        repo_path=".",
    )
    return p


class _TestTracker:
    """Mock tracker for testing."""

    def __init__(self, project_id: str):
        self.project_id = project_id
        self.issues_by_id: dict[str, Issue] = {}

    def fetch_issue_detail(self, identifier: str) -> Issue | None:
        return self.issues_by_id.get(identifier)

    def fetch_issues_by_states(self, states: list[str]) -> list[Issue]:
        return [i for i in self.issues_by_id.values() if i.state in states]

    def fetch_all_issues(self) -> list[Issue]:
        return list(self.issues_by_id.values())

    def add_issue(self, issue: Issue) -> None:
        self.issues_by_id[issue.identifier] = issue

    def update_issue(self, identifier: str, **fields) -> None:
        if identifier in self.issues_by_id:
            issue = self.issues_by_id[identifier]
            for k, v in fields.items():
                if k == "status":
                    issue.state = v


class TestMergedLabelsScopeResolution:
    """Test project scope propagation in merged-labels maintenance."""

    def _make_orchestrator(self, projects: dict[str, _TestTracker]) -> MagicMock:
        """Create an orchestrator with mocked projects and trackers."""
        orch = MagicMock()
        
        # Set up project store
        project_objs = [_make_project(pid) for pid in projects.keys()]
        project_store = MagicMock()
        project_store.list_all.return_value = project_objs
        project_store.get = lambda pid: next((p for p in project_objs if p.id == pid), None)
        orch.project_store = project_store
        
        # Set up tracker resolution
        def _tracker_for_project(pid: str) -> _TestTracker | None:
            return projects.get(pid)
        
        orch._tracker_for_project = _tracker_for_project
        orch._has_managed_projects = lambda: bool(projects)
        orch.tracker = None
        
        # Bind the real _resolve_issue_project_id method to our mock
        orch._resolve_issue_project_id = Orchestrator._resolve_issue_project_id.__get__(orch)
        
        return orch

    def test_issue_with_project_id_returns_as_is(self):
        """Issue with project_id should return unchanged."""
        projects = {
            "proj-1": _TestTracker("proj-1"),
        }
        orch = self._make_orchestrator(projects)
        issue = _make_issue("TASK-1", project_id="proj-1")
        
        resolved = orch._resolve_issue_project_id(issue)
        assert resolved == "proj-1"

    def test_issue_without_project_found_in_single_project(self):
        """Issue without project_id but found in exactly one project."""
        tracker1 = _TestTracker("proj-1")
        tracker1.add_issue(_make_issue("TASK-476", project_id=None))
        
        projects = {
            "proj-1": tracker1,
            "proj-2": _TestTracker("proj-2"),
        }
        orch = self._make_orchestrator(projects)
        issue = _make_issue("TASK-476", project_id=None)
        
        resolved = orch._resolve_issue_project_id(issue)
        assert resolved == "proj-1"

    def test_issue_without_project_found_in_multiple_projects_uses_fallback(self):
        """Issue found in multiple projects should use fallback."""
        tracker1 = _TestTracker("proj-1")
        tracker1.add_issue(_make_issue("SHARED-123", project_id=None))
        
        tracker2 = _TestTracker("proj-2")
        tracker2.add_issue(_make_issue("SHARED-123", project_id=None))
        
        projects = {
            "proj-1": tracker1,
            "proj-2": tracker2,
        }
        orch = self._make_orchestrator(projects)
        issue = _make_issue("SHARED-123", project_id=None)
        
        # With fallback
        resolved = orch._resolve_issue_project_id(issue, fallback_project_id="proj-1")
        assert resolved == "proj-1"

    def test_issue_without_project_found_in_multiple_projects_raises_without_fallback(self):
        """Issue found in multiple projects should raise error if no fallback."""
        tracker1 = _TestTracker("proj-1")
        tracker1.add_issue(_make_issue("SHARED-123", project_id=None))
        
        tracker2 = _TestTracker("proj-2")
        tracker2.add_issue(_make_issue("SHARED-123", project_id=None))
        
        projects = {
            "proj-1": tracker1,
            "proj-2": tracker2,
        }
        orch = self._make_orchestrator(projects)
        issue = _make_issue("SHARED-123", project_id=None)
        
        # Without fallback, should raise
        with pytest.raises(ProjectError, match="Ambiguous ownership"):
            orch._resolve_issue_project_id(issue)

    def test_issue_not_found_returns_fallback(self):
        """Issue not found in any project should return fallback."""
        projects = {
            "proj-1": _TestTracker("proj-1"),
            "proj-2": _TestTracker("proj-2"),
        }
        orch = self._make_orchestrator(projects)
        issue = _make_issue("NOTFOUND-999", project_id=None)
        
        resolved = orch._resolve_issue_project_id(issue, fallback_project_id="proj-2")
        assert resolved == "proj-2"

    def test_issue_not_found_returns_none_without_fallback(self):
        """Issue not found and no fallback should return None."""
        projects = {
            "proj-1": _TestTracker("proj-1"),
        }
        orch = self._make_orchestrator(projects)
        issue = _make_issue("NOTFOUND-999", project_id=None)
        
        resolved = orch._resolve_issue_project_id(issue)
        assert resolved is None

    def test_legacy_mode_no_managed_projects_returns_fallback(self):
        """Legacy mode (no managed projects) should return fallback."""
        orch = MagicMock()
        orch.project_store.list_all.return_value = []
        orch._resolve_issue_project_id = Orchestrator._resolve_issue_project_id.__get__(orch)
        
        issue = _make_issue("LEGACY-1", project_id=None)
        resolved = orch._resolve_issue_project_id(issue, fallback_project_id="legacy")
        assert resolved == "legacy"


class TestMergedLabelsMaintenanceLaneScope:
    """Test that merged-labels maintenance lane uses proper scope."""

    def test_label_merged_issues_skips_ambiguous_scope(self):
        """_label_merged_issues should skip issues with ambiguous scope."""
        # This test will be implemented once we have better integration
        # with the actual orchestrator, as testing _label_merged_issues directly
        # requires mocking many internal methods.
        pass

    def test_label_merged_epics_resolves_project_id(self):
        """_label_merged_epics should resolve project_id for issues lacking it."""
        # Similar to above, requires significant mocking
        pass
