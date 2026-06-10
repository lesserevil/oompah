"""Tests for legacy Backlog dual-read and dispatch flags (TASK-464.2).

Covers:
- Project model: legacy_backlog_enabled and legacy_backlog_dispatch defaults,
  serialization, and round-trip through to_dict / from_dict.
- ProjectStore.UPDATABLE_FIELDS includes the new flags.
- ProjectStore.update() can set and persist both flags.
- Orchestrator._should_dispatch():
  * GitHub-backed project + Backlog issue + legacy_backlog_dispatch=False
    → rejected with reason "legacy_backlog_not_dispatchable".
  * GitHub-backed project + Backlog issue + legacy_backlog_dispatch=True
    → allowed (assuming all other gates pass).
  * GitHub-backed project + GitHub issue (tracker_kind='github_issues')
    → always allowed regardless of legacy_backlog_dispatch.
  * Non-GitHub-backed project → unaffected by the flags.
  * Issue with no project_id → unaffected.
- _fetch_all_candidates():
  * GitHub-backed project + legacy_backlog_enabled=False → Backlog issues
    excluded from candidates.
  * GitHub-backed project + legacy_backlog_enabled=True → Backlog issues
    included and tagged tracker_kind='backlog_md'.
  * Non-GitHub-backed project → issues passed through unchanged.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oompah.config import ServiceConfig
from oompah.models import Issue, Project
from oompah.orchestrator import Orchestrator
from oompah.projects import ProjectStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config() -> ServiceConfig:
    return ServiceConfig()


def _make_issue(
    identifier: str,
    state: str = "open",
    issue_type: str = "task",
    priority: int = 2,
    project_id: str | None = None,
    description: str = "Non-empty description for dispatch gate.",
    tracker_kind: str | None = None,
) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=f"Issue {identifier}",
        description=description,
        state=state,
        issue_type=issue_type,
        priority=priority,
        project_id=project_id,
        labels=[],
        tracker_kind=tracker_kind,
    )


def _make_project_mock(
    project_id: str,
    tracker_kind: str | None = None,
    legacy_backlog_enabled: bool = False,
    legacy_backlog_dispatch: bool = False,
    paused: bool = False,
    max_in_flight_prs: int = 1,
    name: str = "myrepo",
) -> MagicMock:
    p = MagicMock(spec=Project)
    p.id = project_id
    p.name = name
    p.repo_url = "https://github.com/org/repo"
    p.yolo = False
    p.paused = paused
    p.max_in_flight_prs = max_in_flight_prs
    p.last_webhook_received_at = None
    p.tracker_kind = tracker_kind
    p.legacy_backlog_enabled = legacy_backlog_enabled
    p.legacy_backlog_dispatch = legacy_backlog_dispatch
    return p


def _make_orchestrator(tmp_path, projects=None) -> Orchestrator:
    all_projects = list(projects or [])
    project_store = MagicMock()
    project_store.list_all.return_value = all_projects
    project_store.get.side_effect = lambda pid: next(
        (p for p in all_projects if p.id == pid), None
    )
    orch = Orchestrator(
        config=_make_config(),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
    )
    # Avoid being gated by the open-review cap.
    orch._reviews_cache = {}
    return orch


# ---------------------------------------------------------------------------
# Project model: field defaults
# ---------------------------------------------------------------------------


class TestLegacyBacklogModelDefaults:
    def test_legacy_backlog_enabled_defaults_to_false(self):
        p = Project(id="p", name="n", repo_url="u", repo_path="/tmp/x")
        assert p.legacy_backlog_enabled is False

    def test_legacy_backlog_dispatch_defaults_to_false(self):
        p = Project(id="p", name="n", repo_url="u", repo_path="/tmp/x")
        assert p.legacy_backlog_dispatch is False

    def test_can_set_legacy_backlog_enabled_true(self):
        p = Project(
            id="p", name="n", repo_url="u", repo_path="/tmp/x",
            legacy_backlog_enabled=True,
        )
        assert p.legacy_backlog_enabled is True

    def test_can_set_legacy_backlog_dispatch_true(self):
        p = Project(
            id="p", name="n", repo_url="u", repo_path="/tmp/x",
            legacy_backlog_dispatch=True,
        )
        assert p.legacy_backlog_dispatch is True


# ---------------------------------------------------------------------------
# Project model: to_dict serialisation
# ---------------------------------------------------------------------------


class TestLegacyBacklogSerialisation:
    def test_to_dict_includes_enabled_when_false(self):
        """Dashboard/API consumers can rely on explicit default False values."""
        p = Project(id="p", name="n", repo_url="u", repo_path="/tmp/x")
        d = p.to_dict()
        assert d["legacy_backlog_enabled"] is False

    def test_to_dict_includes_dispatch_when_false(self):
        p = Project(id="p", name="n", repo_url="u", repo_path="/tmp/x")
        d = p.to_dict()
        assert d["legacy_backlog_dispatch"] is False

    def test_to_dict_includes_enabled_when_true(self):
        p = Project(
            id="p", name="n", repo_url="u", repo_path="/tmp/x",
            legacy_backlog_enabled=True,
        )
        assert p.to_dict()["legacy_backlog_enabled"] is True

    def test_to_dict_includes_dispatch_when_true(self):
        p = Project(
            id="p", name="n", repo_url="u", repo_path="/tmp/x",
            legacy_backlog_dispatch=True,
        )
        assert p.to_dict()["legacy_backlog_dispatch"] is True

    def test_from_dict_round_trip_both_true(self):
        p = Project(
            id="p", name="n", repo_url="u", repo_path="/tmp/x",
            legacy_backlog_enabled=True,
            legacy_backlog_dispatch=True,
        )
        p2 = Project.from_dict(p.to_dict())
        assert p2.legacy_backlog_enabled is True
        assert p2.legacy_backlog_dispatch is True

    def test_from_dict_round_trip_both_false(self):
        p = Project(
            id="p", name="n", repo_url="u", repo_path="/tmp/x",
            legacy_backlog_enabled=False,
            legacy_backlog_dispatch=False,
        )
        p2 = Project.from_dict(p.to_dict())
        assert p2.legacy_backlog_enabled is False
        assert p2.legacy_backlog_dispatch is False

    def test_from_dict_missing_fields_default_to_false(self):
        """Old project records without the fields round-trip to False."""
        p = Project.from_dict(
            {"id": "x", "name": "y", "repo_url": "z", "repo_path": "/a"}
        )
        assert p.legacy_backlog_enabled is False
        assert p.legacy_backlog_dispatch is False

    def test_from_dict_enabled_only(self):
        """legacy_backlog_enabled=True without dispatch still gives dispatch=False."""
        p = Project.from_dict({
            "id": "x", "name": "y", "repo_url": "z", "repo_path": "/a",
            "legacy_backlog_enabled": True,
        })
        assert p.legacy_backlog_enabled is True
        assert p.legacy_backlog_dispatch is False


# ---------------------------------------------------------------------------
# ProjectStore: UPDATABLE_FIELDS and update()
# ---------------------------------------------------------------------------


class TestLegacyBacklogProjectStore:
    def test_legacy_backlog_enabled_in_updatable_fields(self):
        assert "legacy_backlog_enabled" in ProjectStore.UPDATABLE_FIELDS

    def test_legacy_backlog_dispatch_in_updatable_fields(self):
        assert "legacy_backlog_dispatch" in ProjectStore.UPDATABLE_FIELDS

    @pytest.fixture(autouse=True)
    def store(self, tmp_path):
        path = str(tmp_path / "projects.json")
        self.store = ProjectStore(
            path=path,
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        p = Project(
            id="proj-lb",
            name="legacy-backlog-test",
            repo_url="https://github.com/org/lb-test.git",
            repo_path=str(tmp_path / "repos" / "lb-test"),
            branch="main",
        )
        self.store._projects[p.id] = p
        self.store._save()

    def test_update_sets_legacy_backlog_enabled(self):
        updated = self.store.update("proj-lb", legacy_backlog_enabled=True)
        assert updated.legacy_backlog_enabled is True

    def test_update_sets_legacy_backlog_dispatch(self):
        updated = self.store.update("proj-lb", legacy_backlog_dispatch=True)
        assert updated.legacy_backlog_dispatch is True

    def test_update_persists_legacy_backlog_enabled(self, tmp_path):
        self.store.update("proj-lb", legacy_backlog_enabled=True)
        store2 = ProjectStore(
            path=self.store.path,
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        assert store2.get("proj-lb").legacy_backlog_enabled is True

    def test_update_persists_legacy_backlog_dispatch(self, tmp_path):
        self.store.update("proj-lb", legacy_backlog_dispatch=True)
        store2 = ProjectStore(
            path=self.store.path,
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        assert store2.get("proj-lb").legacy_backlog_dispatch is True

    def test_update_clears_legacy_backlog_enabled(self, tmp_path):
        self.store.update("proj-lb", legacy_backlog_enabled=True)
        self.store.update("proj-lb", legacy_backlog_enabled=False)
        store2 = ProjectStore(
            path=self.store.path,
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        assert store2.get("proj-lb").legacy_backlog_enabled is False


# ---------------------------------------------------------------------------
# Orchestrator._should_dispatch(): legacy Backlog dispatch gate
# ---------------------------------------------------------------------------


class TestShouldDispatchLegacyBacklogGate:
    """_should_dispatch rejects legacy Backlog issues in GitHub-backed projects
    when legacy_backlog_dispatch=False, and allows them when True."""

    def test_backlog_issue_in_github_project_no_dispatch_flag_is_rejected(
        self, tmp_path
    ):
        """Default: GitHub-backed project, Backlog issue, dispatch=False → reject."""
        proj = _make_project_mock(
            "proj-gh",
            tracker_kind="github_issues",
            legacy_backlog_enabled=True,
            legacy_backlog_dispatch=False,
        )
        orch = _make_orchestrator(tmp_path, projects=[proj])
        # tracker_kind=None → Backlog issue
        issue = _make_issue("lb-1", project_id="proj-gh", tracker_kind=None)
        assert orch._should_dispatch(issue) is False

    def test_reject_reason_is_legacy_backlog_not_dispatchable(self, tmp_path):
        proj = _make_project_mock(
            "proj-gh",
            tracker_kind="github_issues",
            legacy_backlog_enabled=True,
            legacy_backlog_dispatch=False,
        )
        orch = _make_orchestrator(tmp_path, projects=[proj])
        issue = _make_issue("lb-1", project_id="proj-gh", tracker_kind=None)
        orch._should_dispatch(issue)
        reason, _ = orch.state.reject_streak.get("lb-1", ("", 0))
        assert reason == "legacy_backlog_not_dispatchable"

    def test_backlog_issue_in_github_project_with_dispatch_flag_is_allowed(
        self, tmp_path
    ):
        """GitHub-backed project + legacy_backlog_dispatch=True → allowed."""
        proj = _make_project_mock(
            "proj-gh",
            tracker_kind="github_issues",
            legacy_backlog_enabled=True,
            legacy_backlog_dispatch=True,
        )
        orch = _make_orchestrator(tmp_path, projects=[proj])
        issue = _make_issue("lb-2", project_id="proj-gh", tracker_kind=None)
        assert orch._should_dispatch(issue) is True

    def test_github_issue_in_github_project_allowed_regardless_of_dispatch_flag(
        self, tmp_path
    ):
        """GitHub-native issues bypass the legacy dispatch gate entirely."""
        proj = _make_project_mock(
            "proj-gh",
            tracker_kind="github_issues",
            legacy_backlog_enabled=False,
            legacy_backlog_dispatch=False,
        )
        orch = _make_orchestrator(tmp_path, projects=[proj])
        # tracker_kind='github_issues' → not a legacy issue
        issue = _make_issue(
            "gh-1", project_id="proj-gh", tracker_kind="github_issues"
        )
        assert orch._should_dispatch(issue) is True

    def test_backlog_issue_in_non_github_project_unaffected(self, tmp_path):
        """Non-GitHub-backed projects are not gated by the legacy flags."""
        proj = _make_project_mock(
            "proj-backlog",
            tracker_kind=None,  # pure Backlog.md project
            legacy_backlog_enabled=False,
            legacy_backlog_dispatch=False,
        )
        orch = _make_orchestrator(tmp_path, projects=[proj])
        issue = _make_issue("task-1", project_id="proj-backlog", tracker_kind=None)
        assert orch._should_dispatch(issue) is True

    def test_issue_with_no_project_id_unaffected(self, tmp_path):
        """Issues without a project_id bypass the legacy gate."""
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue("task-noproj", project_id=None, tracker_kind=None)
        assert orch._should_dispatch(issue) is True

    def test_backlog_md_tagged_issue_is_rejected(self, tmp_path):
        """An issue explicitly tagged tracker_kind='backlog_md' is still rejected."""
        proj = _make_project_mock(
            "proj-gh",
            tracker_kind="github_issues",
            legacy_backlog_enabled=True,
            legacy_backlog_dispatch=False,
        )
        orch = _make_orchestrator(tmp_path, projects=[proj])
        issue = _make_issue("lb-3", project_id="proj-gh", tracker_kind="backlog_md")
        assert orch._should_dispatch(issue) is False

    def test_github_hyphenated_tracker_kind_allowed(self, tmp_path):
        """Issues with tracker_kind='github-issues' (hyphenated) pass the gate."""
        proj = _make_project_mock(
            "proj-gh",
            tracker_kind="github_issues",
            legacy_backlog_enabled=False,
            legacy_backlog_dispatch=False,
        )
        orch = _make_orchestrator(tmp_path, projects=[proj])
        issue = _make_issue(
            "gh-2", project_id="proj-gh", tracker_kind="github-issues"
        )
        assert orch._should_dispatch(issue) is True

    def test_gate_does_not_affect_other_projects(self, tmp_path):
        """Rejecting legacy issues in proj-a must not affect proj-b."""
        proj_a = _make_project_mock(
            "proj-a",
            tracker_kind="github_issues",
            legacy_backlog_enabled=True,
            legacy_backlog_dispatch=False,
        )
        proj_b = _make_project_mock(
            "proj-b",
            tracker_kind=None,  # pure Backlog project
        )
        orch = _make_orchestrator(tmp_path, projects=[proj_a, proj_b])
        issue_a = _make_issue("a-1", project_id="proj-a", tracker_kind=None)
        issue_b = _make_issue("b-1", project_id="proj-b", tracker_kind=None)
        assert orch._should_dispatch(issue_a) is False
        assert orch._should_dispatch(issue_b) is True


# ---------------------------------------------------------------------------
# _fetch_all_candidates(): dual-read and legacy_backlog_enabled filter
# ---------------------------------------------------------------------------


class TestFetchAllCandidatesLegacyBacklog:
    """_fetch_all_candidates filters / tags Backlog issues based on
    legacy_backlog_enabled when the project is GitHub-backed."""

    def _make_backlog_issue(self, identifier, project_id):
        return Issue(
            id=identifier,
            identifier=identifier,
            title=f"Backlog task {identifier}",
            description="desc",
            state="open",
            project_id=project_id,
            labels=[],
            tracker_kind=None,  # Backlog issues have no tracker_kind set
        )

    def _make_github_issue(self, identifier, project_id):
        return Issue(
            id=identifier,
            identifier=identifier,
            title=f"GitHub issue {identifier}",
            description="desc",
            state="open",
            project_id=project_id,
            labels=[],
            tracker_kind="github_issues",
        )

    def test_github_backed_no_legacy_enabled_excludes_backlog_issues(
        self, tmp_path
    ):
        """With legacy_backlog_enabled=False, Backlog issues are hidden."""
        proj = _make_project_mock(
            "proj-gh",
            tracker_kind="github_issues",
            legacy_backlog_enabled=False,
            legacy_backlog_dispatch=False,
        )
        backlog_issue = self._make_backlog_issue("lb-task-1", "proj-gh")
        orch = _make_orchestrator(tmp_path, projects=[proj])
        orch._run_bounded_refresh = AsyncMock(
            return_value=([backlog_issue], None)
        )

        candidates = orch._fetch_all_candidates()
        assert not any(c.id == "lb-task-1" for c in candidates)

    def test_github_backed_legacy_enabled_includes_and_tags_backlog_issues(
        self, tmp_path
    ):
        """With legacy_backlog_enabled=True, Backlog issues are included and tagged."""
        proj = _make_project_mock(
            "proj-gh",
            tracker_kind="github_issues",
            legacy_backlog_enabled=True,
            legacy_backlog_dispatch=False,
        )
        backlog_issue = self._make_backlog_issue("lb-task-2", "proj-gh")
        orch = _make_orchestrator(tmp_path, projects=[proj])
        orch._run_bounded_refresh = AsyncMock(
            return_value=([backlog_issue], None)
        )

        candidates = orch._fetch_all_candidates()
        tagged = [c for c in candidates if c.id == "lb-task-2"]
        assert len(tagged) == 1
        assert tagged[0].tracker_kind == "backlog_md"

    def test_github_backed_legacy_enabled_github_issues_pass_through_untagged(
        self, tmp_path
    ):
        """GitHub-native issues are never re-tagged regardless of legacy flags."""
        proj = _make_project_mock(
            "proj-gh",
            tracker_kind="github_issues",
            legacy_backlog_enabled=True,
            legacy_backlog_dispatch=True,
        )
        gh_issue = self._make_github_issue("gh-task-1", "proj-gh")
        orch = _make_orchestrator(tmp_path, projects=[proj])
        orch._run_bounded_refresh = AsyncMock(
            return_value=([gh_issue], None)
        )

        candidates = orch._fetch_all_candidates()
        gh_candidates = [c for c in candidates if c.id == "gh-task-1"]
        assert len(gh_candidates) == 1
        assert gh_candidates[0].tracker_kind == "github_issues"

    def test_non_github_project_issues_pass_through_unchanged(self, tmp_path):
        """Non-GitHub-backed projects are not affected by the filter."""
        proj = _make_project_mock(
            "proj-backlog",
            tracker_kind=None,
            legacy_backlog_enabled=False,
            legacy_backlog_dispatch=False,
        )
        backlog_issue = self._make_backlog_issue("task-123", "proj-backlog")
        orch = _make_orchestrator(tmp_path, projects=[proj])
        orch._run_bounded_refresh = AsyncMock(
            return_value=([backlog_issue], None)
        )

        candidates = orch._fetch_all_candidates()
        found = [c for c in candidates if c.id == "task-123"]
        assert len(found) == 1
        # tracker_kind remains None for non-GitHub projects
        assert found[0].tracker_kind is None
