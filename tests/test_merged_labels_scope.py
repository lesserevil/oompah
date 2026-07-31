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
    labels: list[str] | None = None,
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
        labels=labels or [],
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
        self.update_calls: list[tuple[str, dict]] = []

    def fetch_issue_detail(self, identifier: str) -> Issue | None:
        return self.issues_by_id.get(identifier)

    def fetch_issues_by_states(self, states: list[str]) -> list[Issue]:
        return [i for i in self.issues_by_id.values() if i.state in states]

    def fetch_all_issues(self) -> list[Issue]:
        return list(self.issues_by_id.values())

    def add_issue(self, issue: Issue) -> None:
        self.issues_by_id[issue.identifier] = issue

    def update_issue(self, identifier: str, **fields) -> None:
        self.update_calls.append((identifier, fields))
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

        # Bind the real scope helpers to our mock so these tests exercise the
        # production resolution/routing code without constructing the full
        # service.
        orch._resolve_issue_project_id = Orchestrator._resolve_issue_project_id.__get__(orch)
        orch._scope_issue_for_maintenance = (
            Orchestrator._scope_issue_for_maintenance.__get__(orch)
        )

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

    def test_issue_without_project_found_in_multiple_projects_rejects_fallback(self):
        """An identifier collision must never be resolved by loop fallback."""
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

        with pytest.raises(ProjectError, match="Ambiguous ownership"):
            orch._resolve_issue_project_id(issue, fallback_project_id="proj-1")

    def test_explicit_project_mismatch_is_rejected(self):
        """A record fetched from another project cannot be mutated here."""
        orch = self._make_orchestrator({
            "proj-a": _TestTracker("proj-a"),
            "proj-b": _TestTracker("proj-b"),
        })
        issue = _make_issue("TASK-1", project_id="proj-b")

        with pytest.raises(ProjectError, match="declares project"):
            orch._resolve_issue_project_id(issue, source_project_id="proj-a")

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

    def test_github_and_native_records_route_to_their_own_trackers(self):
        """Scope normalization selects the project tracker, not self.tracker."""
        github_tracker = _TestTracker("github-project")
        native_tracker = _TestTracker("native-project")
        orch = self._make_orchestrator({
            "github-project": github_tracker,
            "native-project": native_tracker,
        })
        github_issue = _make_issue("org/repo#476", project_id="github-project")
        native_issue = _make_issue("OOMPAH-476", project_id="native-project")

        github_scope, selected_github = orch._scope_issue_for_maintenance(
            github_issue, "github-project"
        )
        native_scope, selected_native = orch._scope_issue_for_maintenance(
            native_issue, "native-project"
        )

        assert (github_scope, selected_github) == ("github-project", github_tracker)
        assert (native_scope, selected_native) == ("native-project", native_tracker)

    def test_scope_resolution_is_restart_safe(self):
        """A fresh orchestrator can re-resolve a legacy record after restart."""
        tracker = _TestTracker("proj-14849f1b")
        tracker.add_issue(_make_issue("OOMPAH-476"))
        projects = {"proj-14849f1b": tracker}

        first = self._make_orchestrator(projects)
        first_issue = _make_issue("OOMPAH-476")
        assert first._scope_issue_for_maintenance(
            first_issue, "proj-14849f1b"
        )[0] == "proj-14849f1b"

        second = self._make_orchestrator(projects)
        second_issue = _make_issue("OOMPAH-476")
        assert second._scope_issue_for_maintenance(
            second_issue, "proj-14849f1b"
        )[0] == "proj-14849f1b"

    def test_managed_scope_never_calls_legacy_tracker(self):
        """Managed resolution must not fall back to the unscoped tracker."""
        project_tracker = _TestTracker("proj-1")
        project_tracker.add_issue(_make_issue("OOMPAH-476"))
        orch = self._make_orchestrator({"proj-1": project_tracker})
        orch.tracker = MagicMock()

        issue = _make_issue("OOMPAH-476")
        resolved, selected = orch._scope_issue_for_maintenance(issue, "proj-1")

        assert resolved == "proj-1"
        assert selected is project_tracker
        orch.tracker.assert_not_called()


class TestMergedLabelsMaintenanceLaneScope:
    """Test that merged-labels maintenance lane uses proper scope."""

    @staticmethod
    def _make_orchestrator(projects: dict[str, _TestTracker]) -> MagicMock:
        return TestMergedLabelsScopeResolution()._make_orchestrator(projects)

    def test_label_merged_issues_skips_ambiguous_scope(self):
        """_label_merged_issues should skip issues with ambiguous scope."""
        tracker_a = _TestTracker("proj-a")
        tracker_b = _TestTracker("proj-b")
        issue = _make_issue("SHARED-123", state="closed")
        tracker_a.add_issue(issue)
        tracker_b.add_issue(_make_issue("SHARED-123", state="closed"))
        orch = self._make_orchestrator({"proj-a": tracker_a, "proj-b": tracker_b})
        orch._label_merged_issues = Orchestrator._label_merged_issues.__get__(orch)
        orch._job_deadline_exceeded = lambda _job: False
        orch._merged_branches = {"SHARED-123"}
        orch._reviews_cache = {}
        orch._landed_branch_for_issue = MagicMock(return_value="SHARED-123")

        with patch("oompah.orchestrator.detect_provider", return_value=None):
            orch._label_merged_issues()

        orch._landed_branch_for_issue.assert_not_called()
        assert issue.project_id is None

    def test_all_merged_epics_skips_ambiguous_scope(self):
        """An identifier collision must not reach merged-epic mutation."""
        tracker_a = _TestTracker("proj-a")
        tracker_b = _TestTracker("proj-b")
        tracker_a.add_issue(
            _make_issue("SHARED-EPIC", state=MERGED, issue_type="epic")
        )
        tracker_b.add_issue(
            _make_issue("SHARED-EPIC", state=MERGED, issue_type="epic")
        )
        orch = self._make_orchestrator(
            {"proj-a": tracker_a, "proj-b": tracker_b}
        )
        orch._all_merged_epics = Orchestrator._all_merged_epics.__get__(orch)

        assert orch._all_merged_epics() == []

    def test_merged_epic_children_use_parent_project_tracker(self):
        """Legacy children are normalized before merged-epic writes."""
        tracker = _TestTracker("proj-1")
        epic = _make_issue(
            "EPIC-1", state=MERGED, issue_type="epic", project_id="proj-1"
        )
        child = _make_issue("CHILD-476", state=DONE, project_id=None)
        tracker.add_issue(child)
        orch = self._make_orchestrator({"proj-1": tracker})
        orch._job_deadline_exceeded = lambda _job: False
        orch._fetch_epic_children = MagicMock(return_value=[child])
        orch._request_merged_via_coordinator = MagicMock(
            return_value=MagicMock(success=True)
        )
        orch._epic_branch_for_issue = MagicMock(return_value="epic-EPIC-1")
        orch._resolve_epic_target_branch = MagicMock(return_value="main")
        orch._refresh_landing_evidence_target_refs = MagicMock(
            return_value=(True, None)
        )
        orch._refresh_landing_evidence_candidate_refs = MagicMock(
            return_value=(True, None)
        )
        orch._child_landing_evidence_block_reason = MagicMock(return_value=None)
        orch._open_review_branch_for_issue_in_cache = MagicMock(return_value="")
        orch._cleanup_landed_private_child_branch = MagicMock()
        orch._clear_stuck_epic_alert = MagicMock()
        orch._mark_epic_merged = Orchestrator._mark_epic_merged.__get__(orch)

        orch._mark_epic_merged(epic, epic_branch="epic-EPIC-1")

        assert child.project_id == "proj-1"
        assert (
            orch._request_merged_via_coordinator.call_args_list[-1].args[1]
            == "proj-1"
        )

    def test_independent_child_label_uses_parent_project_tracker(self):
        """Legacy independent children do not use the global tracker."""
        tracker = _TestTracker("proj-1")
        epic = _make_issue(
            "EPIC-1", state=MERGED, issue_type="epic", project_id="proj-1"
        )
        child = _make_issue("CHILD-476", state=MERGED, project_id=None)
        tracker.add_issue(child)
        orch = self._make_orchestrator({"proj-1": tracker})
        orch._all_non_terminal_epics = MagicMock(return_value=[])
        orch._all_merged_epics = MagicMock(return_value=[epic])
        orch._detect_independently_merged_children = MagicMock(
            return_value=[(child, epic, "epic-EPIC-1")]
        )
        orch._tracker_for_issue = lambda _issue: tracker
        orch._job_deadline_exceeded = lambda _job: False
        orch._reconcile_independently_merged_children = (
            Orchestrator._reconcile_independently_merged_children.__get__(orch)
        )

        assert orch._reconcile_independently_merged_children() == 1
        assert child.project_id == "proj-1"
        assert tracker.update_calls == [
            ("CHILD-476", {"add_label": "epic:independently-merged"})
        ]

    def test_label_merged_epics_resolves_project_id(self):
        """_label_merged_epics scopes a legacy epic before marking it."""
        tracker = _TestTracker("proj-1")
        epic = _make_issue("EPIC-476", state="Backlog", issue_type="epic")
        tracker.add_issue(epic)
        orch = self._make_orchestrator({"proj-1": tracker})
        orch._label_merged_epics = Orchestrator._label_merged_epics.__get__(orch)
        orch._all_non_terminal_epics = Orchestrator._all_non_terminal_epics.__get__(orch)
        orch._job_deadline_exceeded = lambda _job: False
        orch._epic_branch_for_issue = MagicMock(return_value="epic-EPIC-476")
        orch._resolve_epic_target_branch = MagicMock(return_value="main")
        orch._epic_branch_landed_on_target = MagicMock(return_value=True)
        orch._mark_epic_merged = MagicMock()

        with patch("oompah.orchestrator.detect_provider", return_value=MagicMock()):
            orch._label_merged_epics()

        assert epic.project_id == "proj-1"
        orch._mark_epic_merged.assert_called_once_with(
            epic, epic_branch="epic-EPIC-476"
        )

    def test_label_merged_issues_is_idempotent_for_merged_label(self):
        """Already-labelled issues are not reprocessed on later sweeps."""
        tracker = _TestTracker("proj-1")
        tracker.add_issue(_make_issue("TASK-1", state="closed", labels=["merged"]))
        orch = self._make_orchestrator({"proj-1": tracker})
        orch._label_merged_issues = Orchestrator._label_merged_issues.__get__(orch)
        orch._job_deadline_exceeded = lambda _job: False
        orch._merged_branches = {"TASK-1"}
        orch._reviews_cache = {}
        orch._landed_branch_for_issue = MagicMock()

        with patch("oompah.orchestrator.detect_provider", return_value=None):
            orch._label_merged_issues()

        orch._landed_branch_for_issue.assert_not_called()
