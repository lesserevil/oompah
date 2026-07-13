"""Tests for GET /api/v1/projects/{project_id}/release-branches/{branch}/addendums.

Section 7 Branch inspection of plans/release-branch-addendums.md (OOMPAH-182).

Covers:
  Route safety:
  - Branch name with slashes works as path segments (release/1.0)
  - Branch name percent-encoded (release%2F1.0) routes identically
  - Branch names with dots and other special chars are handled

  Grouping and ordering:
  - All six groups present in response (open, in_progress, in_review, blocked,
    merged, archived) even when empty
  - Addendums correctly bucketed by status
  - Multiple tasks with addendums for the same branch all appear
  - Tasks with addendums for a *different* branch are NOT included
  - Epic addendums (included_child_ids non-empty) are returned correctly

  Source deep links:
  - Each entry has identifier, title, type, and addendum
  - Addendum is the full to_raw() dict

  Warning behavior:
  - untracked_commits absent when no git errors and all commits tracked
  - untracked_commits present when git log finds commits not in result_commits
  - untracked_commits absent when git is unavailable (graceful degradation)
  - untracked_commits absent when no repo_path configured

  Unavailable historical branches:
  - 200 with empty groups for a branch that once existed but has no addendums
  - 200 with populated groups even for branches not in supported list (historical)

  Error and edge cases:
  - 404 for unknown project
  - 503 when tracker is unavailable
  - 200 with empty groups when branch matches no addendums
  - No crash when a task has malformed addendum metadata
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.server import app
from oompah.models import Issue, Project
from oompah.release_addendum_schema import (
    AddendumStatus,
    ReleaseAddendum,
    make_addendum_id,
    make_work_branch,
    make_worktree_key,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW = datetime(2026, 7, 13, 10, 0, 0, tzinfo=timezone.utc)

_COMMIT_A = "a" * 40
_COMMIT_B = "b" * 40
_COMMIT_C = "c" * 40
_PR_URL = "https://github.com/org/repo/pull/42"


def _make_issue(
    identifier: str = "FOO-10",
    state: str = "Merged",
    title: str = "A merged task",
    issue_type: str = "task",
) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=title,
        description="",
        state=state,
        priority=1,
        issue_type=issue_type,
        labels=[],
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )


def _make_project(
    pid: str = "proj-1",
    repo_path: str = "/tmp/repos/proj-1",
    supported_release_branches: list[str] | None = None,
) -> MagicMock:
    project = MagicMock(spec=Project)
    project.id = pid
    project.name = "Test Project"
    project.default_branch = "main"
    project.supported_release_branches = supported_release_branches or [
        "release/1.1",
        "release/1.0",
    ]
    project.repo_url = "https://github.com/org/repo"
    project.repo_path = repo_path
    project.access_token = None
    project.branches = ["main", "release/*"]
    return project


def _make_addendum(
    source_id: str = "FOO-10",
    target_branch: str = "release/1.0",
    status: AddendumStatus = AddendumStatus.OPEN,
    pr_url: str | None = None,
    error: str | None = None,
    commits: list[str] | None = None,
    result_commits: list[str] | None = None,
    included_child_ids: list[str] | None = None,
) -> ReleaseAddendum:
    commits = commits or [_COMMIT_A]
    return ReleaseAddendum(
        id=make_addendum_id(source_id, target_branch),
        source_branch="main",
        target_branch=target_branch,
        status=status,
        commits=commits,
        work_branch=make_work_branch(source_id, target_branch),
        worktree_key=make_worktree_key(source_id, target_branch),
        queued_at=NOW.isoformat(),
        started_at=NOW.isoformat() if status != AddendumStatus.OPEN else None,
        completed_at=NOW.isoformat() if status in (AddendumStatus.MERGED, AddendumStatus.ARCHIVED) else None,
        pr_url=pr_url,
        result_commits=result_commits or [],
        error=error,
        included_child_ids=included_child_ids or [],
    )


def _raw_addendum(addendum: ReleaseAddendum) -> list[dict]:
    return [addendum.to_raw()]


class _WriteableTracker:
    """Minimal tracker stub that stores addendum metadata in-memory."""

    def __init__(self, issues: list[Issue], addendums_by_id: dict[str, list[ReleaseAddendum]] | None = None):
        self._issues = issues
        self._meta: dict[str, dict] = {}
        for identifier, adm_list in (addendums_by_id or {}).items():
            self._meta[identifier] = {
                "oompah.release_addendums": [a.to_raw() for a in adm_list],
            }

    def fetch_all_issues(self) -> list[Issue]:
        return list(self._issues)

    def fetch_issue_detail(self, identifier: str) -> Issue | None:
        for issue in self._issues:
            if issue.identifier == identifier:
                return issue
        return None

    def get_metadata(self, identifier: str) -> dict:
        return dict(self._meta.get(identifier, {}))

    def set_metadata_field(self, identifier: str, key: str, value: object) -> None:
        if identifier not in self._meta:
            self._meta[identifier] = {}
        self._meta[identifier][key] = value


class _FakeProjectStore:
    def __init__(self, project: MagicMock | None):
        self._project = project

    def get(self, project_id: str) -> MagicMock | None:
        if self._project and self._project.id == project_id:
            return self._project
        return None


class _FakeOrch:
    def __init__(self, project: MagicMock | None, tracker: _WriteableTracker):
        self.project_store = _FakeProjectStore(project)
        self._tracker = tracker

    def _tracker_for_project(self, project_id: str) -> _WriteableTracker:
        return self._tracker


@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Route safety tests
# ---------------------------------------------------------------------------


class TestRouteSafety:
    """Branch names with slashes and special characters are handled correctly."""

    def _call(self, client, project_id: str, branch_url_segment: str):
        """Build and execute the request."""
        project = _make_project(pid=project_id)
        tracker = _WriteableTracker(issues=[], addendums_by_id={})
        orch = _FakeOrch(project, tracker)
        url = f"/api/v1/projects/{project_id}/release-branches/{branch_url_segment}/addendums"
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            return client.get(url)

    def test_branch_with_slash_as_path_segments(self, client):
        """release/1.0 as literal path segments is routed and decoded correctly."""
        resp = self._call(client, "proj-1", "release/1.0")
        assert resp.status_code == 200
        data = resp.json()
        assert data["branch"] == "release/1.0"

    def test_branch_percent_encoded_slash(self, client):
        """release%2F1.0 (percent-encoded) is decoded to release/1.0."""
        resp = self._call(client, "proj-1", "release%2F1.0")
        assert resp.status_code == 200
        data = resp.json()
        assert data["branch"] == "release/1.0"

    def test_branch_with_dots(self, client):
        """release/1.2.3 with dots is handled correctly."""
        resp = self._call(client, "proj-1", "release/1.2.3")
        assert resp.status_code == 200
        data = resp.json()
        assert data["branch"] == "release/1.2.3"

    def test_branch_deep_nesting(self, client):
        """releases/v2/stable (nested) is handled correctly."""
        resp = self._call(client, "proj-1", "releases/v2/stable")
        assert resp.status_code == 200
        data = resp.json()
        assert data["branch"] == "releases/v2/stable"


# ---------------------------------------------------------------------------
# Grouping and ordering tests
# ---------------------------------------------------------------------------


class TestGroupingAndOrdering:
    """Addendums are grouped by status in the correct order."""

    def _orch(self, project, issues, addendums_by_id):
        tracker = _WriteableTracker(issues, addendums_by_id)
        return _FakeOrch(project, tracker)

    def test_all_groups_present_in_empty_response(self, client):
        """All six status groups are present even when no addendums exist."""
        project = _make_project()
        orch = _FakeOrch(project, _WriteableTracker([], {}))
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get("/api/v1/projects/proj-1/release-branches/release/1.0/addendums")
        assert resp.status_code == 200
        data = resp.json()
        groups = data["groups"]
        for status in ("open", "in_progress", "in_review", "blocked", "merged", "archived"):
            assert status in groups, f"Expected group {status!r} in response"
            assert groups[status] == [], f"Expected group {status!r} to be empty list"

    def test_open_addendum_appears_in_open_group(self, client):
        issue = _make_issue("FOO-10")
        addendum = _make_addendum("FOO-10", "release/1.0", status=AddendumStatus.OPEN)
        project = _make_project()
        orch = self._orch(project, [issue], {"FOO-10": [addendum]})
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get("/api/v1/projects/proj-1/release-branches/release/1.0/addendums")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["groups"]["open"]) == 1
        assert data["groups"]["open"][0]["identifier"] == "FOO-10"

    def test_in_progress_addendum_bucketed_correctly(self, client):
        issue = _make_issue("FOO-10")
        addendum = _make_addendum("FOO-10", "release/1.0", status=AddendumStatus.IN_PROGRESS)
        project = _make_project()
        orch = self._orch(project, [issue], {"FOO-10": [addendum]})
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get("/api/v1/projects/proj-1/release-branches/release/1.0/addendums")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["groups"]["in_progress"]) == 1
        assert len(data["groups"]["open"]) == 0

    def test_in_review_addendum_bucketed_correctly(self, client):
        issue = _make_issue("FOO-10")
        addendum = _make_addendum(
            "FOO-10", "release/1.0", status=AddendumStatus.IN_REVIEW, pr_url=_PR_URL
        )
        project = _make_project()
        orch = self._orch(project, [issue], {"FOO-10": [addendum]})
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get("/api/v1/projects/proj-1/release-branches/release/1.0/addendums")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["groups"]["in_review"]) == 1
        entry = data["groups"]["in_review"][0]
        assert entry["identifier"] == "FOO-10"
        assert entry["addendum"]["pr_url"] == _PR_URL

    def test_blocked_addendum_bucketed_correctly(self, client):
        issue = _make_issue("FOO-10")
        addendum = _make_addendum(
            "FOO-10", "release/1.0", status=AddendumStatus.BLOCKED,
            error="cherry-pick conflict at file.py",
        )
        project = _make_project()
        orch = self._orch(project, [issue], {"FOO-10": [addendum]})
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get("/api/v1/projects/proj-1/release-branches/release/1.0/addendums")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["groups"]["blocked"]) == 1
        entry = data["groups"]["blocked"][0]
        assert entry["addendum"]["error"] == "cherry-pick conflict at file.py"

    def test_merged_addendum_bucketed_correctly(self, client):
        issue = _make_issue("FOO-10")
        addendum = _make_addendum(
            "FOO-10", "release/1.0", status=AddendumStatus.MERGED,
            result_commits=[_COMMIT_A],
        )
        project = _make_project()
        orch = self._orch(project, [issue], {"FOO-10": [addendum]})
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get("/api/v1/projects/proj-1/release-branches/release/1.0/addendums")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["groups"]["merged"]) == 1

    def test_archived_addendum_bucketed_correctly(self, client):
        issue = _make_issue("FOO-10")
        addendum = _make_addendum("FOO-10", "release/1.0", status=AddendumStatus.ARCHIVED)
        project = _make_project()
        orch = self._orch(project, [issue], {"FOO-10": [addendum]})
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get("/api/v1/projects/proj-1/release-branches/release/1.0/addendums")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["groups"]["archived"]) == 1

    def test_multiple_tasks_all_appear(self, client):
        """Multiple source tasks with addendums for the same branch all appear."""
        issues = [
            _make_issue("FOO-10", title="Feature A"),
            _make_issue("FOO-11", title="Feature B"),
        ]
        addendums_by_id = {
            "FOO-10": [_make_addendum("FOO-10", "release/1.0", status=AddendumStatus.OPEN)],
            "FOO-11": [_make_addendum("FOO-11", "release/1.0", status=AddendumStatus.MERGED)],
        }
        project = _make_project()
        orch = self._orch(project, issues, addendums_by_id)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get("/api/v1/projects/proj-1/release-branches/release/1.0/addendums")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["groups"]["open"]) == 1
        assert len(data["groups"]["merged"]) == 1
        assert data["groups"]["open"][0]["identifier"] == "FOO-10"
        assert data["groups"]["merged"][0]["identifier"] == "FOO-11"

    def test_addendum_for_different_branch_excluded(self, client):
        """Addendum for release/1.1 does NOT appear when querying release/1.0."""
        issue = _make_issue("FOO-10")
        addendum_10 = _make_addendum("FOO-10", "release/1.0", status=AddendumStatus.OPEN)
        addendum_11 = _make_addendum("FOO-10", "release/1.1", status=AddendumStatus.OPEN)
        project = _make_project()
        orch = self._orch(project, [issue], {"FOO-10": [addendum_10, addendum_11]})
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get("/api/v1/projects/proj-1/release-branches/release/1.0/addendums")
        assert resp.status_code == 200
        data = resp.json()
        # Only the release/1.0 addendum should appear
        total_entries = sum(len(v) for v in data["groups"].values())
        assert total_entries == 1
        assert data["groups"]["open"][0]["addendum"]["target_branch"] == "release/1.0"


# ---------------------------------------------------------------------------
# Source deep links
# ---------------------------------------------------------------------------


class TestSourceDeepLinks:
    """Each entry has identifier, title, type, and complete addendum dict."""

    def _orch(self, project, issue, addendums):
        tracker = _WriteableTracker([issue], {issue.identifier: addendums})
        return _FakeOrch(project, tracker)

    def test_entry_has_identifier(self, client):
        issue = _make_issue("FOO-42", title="My Feature")
        addendum = _make_addendum("FOO-42", "release/1.0")
        project = _make_project()
        orch = self._orch(project, issue, [addendum])
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get("/api/v1/projects/proj-1/release-branches/release/1.0/addendums")
        assert resp.status_code == 200
        entry = resp.json()["groups"]["open"][0]
        assert entry["identifier"] == "FOO-42"

    def test_entry_has_title(self, client):
        issue = _make_issue("FOO-42", title="My Important Feature")
        addendum = _make_addendum("FOO-42", "release/1.0")
        project = _make_project()
        orch = self._orch(project, issue, [addendum])
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get("/api/v1/projects/proj-1/release-branches/release/1.0/addendums")
        assert resp.status_code == 200
        entry = resp.json()["groups"]["open"][0]
        assert entry["title"] == "My Important Feature"

    def test_entry_has_type_task(self, client):
        issue = _make_issue("FOO-42", issue_type="task")
        addendum = _make_addendum("FOO-42", "release/1.0")
        project = _make_project()
        orch = self._orch(project, issue, [addendum])
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get("/api/v1/projects/proj-1/release-branches/release/1.0/addendums")
        assert resp.status_code == 200
        entry = resp.json()["groups"]["open"][0]
        assert entry["type"] == "task"

    def test_entry_has_type_epic(self, client):
        issue = _make_issue("FOO-20", issue_type="epic")
        addendum = _make_addendum(
            "FOO-20", "release/1.0", included_child_ids=["FOO-10", "FOO-11"]
        )
        project = _make_project()
        orch = self._orch(project, issue, [addendum])
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get("/api/v1/projects/proj-1/release-branches/release/1.0/addendums")
        assert resp.status_code == 200
        entry = resp.json()["groups"]["open"][0]
        assert entry["type"] == "epic"

    def test_addendum_is_full_to_raw_dict(self, client):
        """The addendum field contains the full to_raw() output."""
        issue = _make_issue("FOO-42")
        addendum = _make_addendum(
            "FOO-42", "release/1.0",
            status=AddendumStatus.IN_REVIEW,
            pr_url=_PR_URL,
            commits=[_COMMIT_A, _COMMIT_B],
        )
        project = _make_project()
        orch = self._orch(project, issue, [addendum])
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get("/api/v1/projects/proj-1/release-branches/release/1.0/addendums")
        assert resp.status_code == 200
        entry = resp.json()["groups"]["in_review"][0]
        adm = entry["addendum"]
        assert adm["id"] == f"FOO-42/release/1.0"
        assert adm["target_branch"] == "release/1.0"
        assert adm["source_branch"] == "main"
        assert adm["status"] == "in_review"
        assert adm["pr_url"] == _PR_URL
        assert adm["commits"] == [_COMMIT_A, _COMMIT_B]
        assert "work_branch" in adm
        assert "worktree_key" in adm
        assert "queued_at" in adm

    def test_epic_addendum_included_child_ids_present(self, client):
        """Epic addendums include included_child_ids for snapshot detail."""
        issue = _make_issue("EPIC-1", issue_type="epic")
        addendum = _make_addendum(
            "EPIC-1", "release/1.0",
            included_child_ids=["FOO-10", "FOO-11", "FOO-12"],
        )
        project = _make_project()
        orch = self._orch(project, issue, [addendum])
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get("/api/v1/projects/proj-1/release-branches/release/1.0/addendums")
        assert resp.status_code == 200
        entry = resp.json()["groups"]["open"][0]
        assert entry["addendum"]["included_child_ids"] == ["FOO-10", "FOO-11", "FOO-12"]


# ---------------------------------------------------------------------------
# Unavailable historical branches
# ---------------------------------------------------------------------------


class TestHistoricalBranches:
    """A branch not in supported_release_branches still returns its addendums."""

    def test_branch_not_in_supported_list_returns_200(self, client):
        """Even if the branch is historical (not in supported_release_branches),
        existing addendums are still returned."""
        # No supported_release_branches contains "release/0.9"
        project = _make_project(supported_release_branches=["release/1.0"])
        issue = _make_issue("FOO-5")
        addendum = _make_addendum(
            "FOO-5", "release/0.9", status=AddendumStatus.MERGED
        )
        tracker = _WriteableTracker([issue], {"FOO-5": [addendum]})
        orch = _FakeOrch(project, tracker)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get("/api/v1/projects/proj-1/release-branches/release/0.9/addendums")
        assert resp.status_code == 200
        data = resp.json()
        assert data["branch"] == "release/0.9"
        assert len(data["groups"]["merged"]) == 1

    def test_querying_nonexistent_branch_returns_empty_groups(self, client):
        """Querying a branch with no addendums returns 200 with empty groups."""
        project = _make_project()
        tracker = _WriteableTracker([], {})
        orch = _FakeOrch(project, tracker)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get("/api/v1/projects/proj-1/release-branches/release/99.9/addendums")
        assert resp.status_code == 200
        data = resp.json()
        total = sum(len(v) for v in data["groups"].values())
        assert total == 0


# ---------------------------------------------------------------------------
# Warning behavior (untracked_commits)
# ---------------------------------------------------------------------------


class TestUntrackedCommitsWarning:
    """untracked_commits warning is informational and based on git log."""

    def _orch(self, project, issues=None, addendums_by_id=None):
        tracker = _WriteableTracker(issues or [], addendums_by_id or {})
        return _FakeOrch(project, tracker)

    def test_untracked_commits_absent_when_no_repo_path(self, client):
        """When project has no repo_path, untracked_commits is absent."""
        project = _make_project(repo_path="")
        orch = self._orch(project)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get("/api/v1/projects/proj-1/release-branches/release/1.0/addendums")
        assert resp.status_code == 200
        assert "untracked_commits" not in resp.json()

    def test_untracked_commits_absent_when_git_fails(self, client):
        """When git log fails, untracked_commits is absent (graceful degradation)."""
        project = _make_project(repo_path="/tmp/repos/proj-1")
        orch = self._orch(project)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            with patch("subprocess.run", side_effect=OSError("git not found")):
                resp = client.get(
                    "/api/v1/projects/proj-1/release-branches/release/1.0/addendums"
                )
        assert resp.status_code == 200
        assert "untracked_commits" not in resp.json()

    def test_untracked_commits_absent_when_all_commits_tracked(self, client):
        """When all branch commits appear in result_commits, no warning."""
        project = _make_project(repo_path="/tmp/repos/proj-1")
        issue = _make_issue("FOO-10")
        addendum = _make_addendum(
            "FOO-10", "release/1.0",
            status=AddendumStatus.MERGED,
            result_commits=[_COMMIT_A, _COMMIT_B],
        )
        orch = self._orch(project, [issue], {"FOO-10": [addendum]})
        # git log returns exactly the two known commits
        mock_run = MagicMock(return_value=MagicMock(
            returncode=0,
            stdout=f"{_COMMIT_A}\n{_COMMIT_B}\n",
        ))
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            with patch("subprocess.run", mock_run):
                resp = client.get(
                    "/api/v1/projects/proj-1/release-branches/release/1.0/addendums"
                )
        assert resp.status_code == 200
        assert "untracked_commits" not in resp.json()

    def test_untracked_commits_present_for_direct_commits(self, client):
        """When git finds commits not in any result_commits, warning is shown."""
        project = _make_project(repo_path="/tmp/repos/proj-1")
        issue = _make_issue("FOO-10")
        addendum = _make_addendum(
            "FOO-10", "release/1.0",
            status=AddendumStatus.MERGED,
            result_commits=[_COMMIT_A],
        )
        orch = self._orch(project, [issue], {"FOO-10": [addendum]})
        # git log returns three commits; only COMMIT_A is tracked
        untracked_sha = _COMMIT_C
        mock_run = MagicMock(return_value=MagicMock(
            returncode=0,
            stdout=f"{_COMMIT_A}\n{untracked_sha}\n",
        ))
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            with patch("subprocess.run", mock_run):
                resp = client.get(
                    "/api/v1/projects/proj-1/release-branches/release/1.0/addendums"
                )
        assert resp.status_code == 200
        data = resp.json()
        assert "untracked_commits" in data
        warn = data["untracked_commits"]
        assert warn["count"] == 1
        assert untracked_sha in warn["commits"]
        assert "warning" in warn
        assert "release/1.0" in warn["warning"]

    def test_untracked_commits_does_not_represent_raw_commit_as_feature(self, client):
        """The warning section is informational; it does not have a type or task link."""
        project = _make_project(repo_path="/tmp/repos/proj-1")
        orch = self._orch(project)
        mock_run = MagicMock(return_value=MagicMock(
            returncode=0,
            stdout=f"{_COMMIT_C}\n",
        ))
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            with patch("subprocess.run", mock_run):
                resp = client.get(
                    "/api/v1/projects/proj-1/release-branches/release/1.0/addendums"
                )
        assert resp.status_code == 200
        data = resp.json()
        assert "untracked_commits" in data
        warn = data["untracked_commits"]
        # No "identifier", "title", or "type" — it's not a task
        assert "identifier" not in warn
        assert "title" not in warn
        assert "type" not in warn

    def test_untracked_commits_limited_to_50(self, client):
        """Large numbers of untracked commits are capped at 50 in the response."""
        project = _make_project(repo_path="/tmp/repos/proj-1")
        orch = self._orch(project)
        many_commits = [("d" * 39 + str(i % 10)) for i in range(80)]
        mock_run = MagicMock(return_value=MagicMock(
            returncode=0,
            stdout="\n".join(many_commits) + "\n",
        ))
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            with patch("subprocess.run", mock_run):
                resp = client.get(
                    "/api/v1/projects/proj-1/release-branches/release/1.0/addendums"
                )
        assert resp.status_code == 200
        warn = resp.json().get("untracked_commits", {})
        assert warn.get("count") == 80
        assert len(warn.get("commits", [])) <= 50


# ---------------------------------------------------------------------------
# Error and edge cases
# ---------------------------------------------------------------------------


class TestErrorCases:
    """404, 503, and malformed data cases."""

    def test_unknown_project_returns_404(self, client):
        project = _make_project(pid="proj-real")
        tracker = _WriteableTracker([], {})
        orch = _FakeOrch(project, tracker)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get(
                "/api/v1/projects/proj-NONEXISTENT/release-branches/release/1.0/addendums"
            )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "not_found"

    def test_tracker_unavailable_returns_503(self, client):
        project = _make_project()

        class _FailOrch:
            project_store = _FakeProjectStore(project)

            def _tracker_for_project(self, pid):
                raise RuntimeError("tracker connection failed")

        with patch.object(server_module, "_get_orchestrator", return_value=_FailOrch()):
            resp = client.get(
                "/api/v1/projects/proj-1/release-branches/release/1.0/addendums"
            )
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "tracker_unavailable"

    def test_fetch_all_issues_failure_returns_503(self, client):
        project = _make_project()

        class _FailTracker:
            def fetch_all_issues(self):
                raise RuntimeError("storage error")

            def get_metadata(self, *a):
                return {}

        class _FailOrch:
            project_store = _FakeProjectStore(project)

            def _tracker_for_project(self, pid):
                return _FailTracker()

        with patch.object(server_module, "_get_orchestrator", return_value=_FailOrch()):
            resp = client.get(
                "/api/v1/projects/proj-1/release-branches/release/1.0/addendums"
            )
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "list_failed"

    def test_malformed_addendum_metadata_skipped_gracefully(self, client):
        """A task with corrupt metadata does not crash the endpoint."""
        issue = _make_issue("FOO-10")
        good_issue = _make_issue("FOO-11")
        good_addendum = _make_addendum("FOO-11", "release/1.0", status=AddendumStatus.OPEN)

        class _MixedTracker:
            def fetch_all_issues(self):
                return [issue, good_issue]

            def get_metadata(self, identifier):
                if identifier == "FOO-10":
                    return {"oompah.release_addendums": "not-a-list"}
                if identifier == "FOO-11":
                    return {"oompah.release_addendums": [good_addendum.to_raw()]}
                return {}

            def set_metadata_field(self, *a):
                pass

        project = _make_project()

        class _MixedOrch:
            project_store = _FakeProjectStore(project)

            def _tracker_for_project(self, pid):
                return _MixedTracker()

        with patch.object(server_module, "_get_orchestrator", return_value=_MixedOrch()):
            resp = client.get(
                "/api/v1/projects/proj-1/release-branches/release/1.0/addendums"
            )
        assert resp.status_code == 200
        data = resp.json()
        # Good addendum is returned; malformed is silently skipped
        assert len(data["groups"]["open"]) == 1
        assert data["groups"]["open"][0]["identifier"] == "FOO-11"

    def test_response_has_project_id_and_branch(self, client):
        """Response always contains project_id and branch keys."""
        project = _make_project()
        tracker = _WriteableTracker([], {})
        orch = _FakeOrch(project, tracker)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get(
                "/api/v1/projects/proj-1/release-branches/release/1.0/addendums"
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_id"] == "proj-1"
        assert data["branch"] == "release/1.0"


# ---------------------------------------------------------------------------
# _compute_untracked_commits unit tests
# ---------------------------------------------------------------------------


class TestComputeUntrackedCommits:
    """Unit tests for _compute_untracked_commits helper."""

    def test_returns_empty_when_no_repo_path(self):
        from oompah.server import _compute_untracked_commits
        result = _compute_untracked_commits("", "release/1.0", frozenset())
        assert result == {}

    def test_returns_empty_on_git_oserror(self):
        from oompah.server import _compute_untracked_commits
        with patch("subprocess.run", side_effect=OSError("no git")):
            result = _compute_untracked_commits("/repo", "release/1.0", frozenset())
        assert result == {}

    def test_returns_empty_on_nonzero_returncode(self):
        from oompah.server import _compute_untracked_commits
        with patch("subprocess.run", return_value=MagicMock(returncode=1, stdout="")):
            result = _compute_untracked_commits("/repo", "release/1.0", frozenset())
        assert result == {}

    def test_returns_empty_when_all_commits_tracked(self):
        from oompah.server import _compute_untracked_commits
        tracked = frozenset([_COMMIT_A, _COMMIT_B])
        with patch("subprocess.run", return_value=MagicMock(
            returncode=0,
            stdout=f"{_COMMIT_A}\n{_COMMIT_B}\n",
        )):
            result = _compute_untracked_commits("/repo", "release/1.0", tracked)
        assert result == {}

    def test_returns_warning_for_untracked_commits(self):
        from oompah.server import _compute_untracked_commits
        tracked = frozenset([_COMMIT_A])
        with patch("subprocess.run", return_value=MagicMock(
            returncode=0,
            stdout=f"{_COMMIT_A}\n{_COMMIT_B}\n{_COMMIT_C}\n",
        )):
            result = _compute_untracked_commits("/repo", "release/1.0", tracked)
        assert result["count"] == 2
        assert _COMMIT_B in result["commits"]
        assert _COMMIT_C in result["commits"]
        assert "release/1.0" in result["warning"]

    def test_caps_commits_at_50(self):
        from oompah.server import _compute_untracked_commits
        many = [("x" * 39 + str(i)[-1]) for i in range(80)]
        with patch("subprocess.run", return_value=MagicMock(
            returncode=0,
            stdout="\n".join(many) + "\n",
        )):
            result = _compute_untracked_commits("/repo", "release/1.0", frozenset())
        assert result["count"] == 80
        assert len(result["commits"]) == 50

    def test_uses_correct_git_command(self):
        from oompah.server import _compute_untracked_commits
        with patch("subprocess.run", return_value=MagicMock(
            returncode=0, stdout=""
        )) as mock_run:
            _compute_untracked_commits("/my/repo", "release/1.0", frozenset())
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert cmd[0] == "git"
        assert "log" in cmd
        assert "origin/release/1.0" in cmd
        assert call_args[1].get("cwd") == "/my/repo"


# ---------------------------------------------------------------------------
# Deprecation and 410 tests (OOMPAH-201)
# ---------------------------------------------------------------------------


class TestDeprecationCompatibilityResponse:
    """The endpoint returns a documented compatibility/deprecation response.

    OOMPAH-201: Document and deprecate the old release-branch inspector.
    The endpoint continues to function during the v1.0→v1.1 transition window
    but adds deprecation markers so API consumers can migrate.
    """

    def _call_endpoint(self, client, branch: str = "release/1.0") -> object:
        project = _make_project(pid="proj-depr")
        tracker = _WriteableTracker(issues=[], addendums_by_id={})
        orch = _FakeOrch(project=project, tracker=tracker)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            with patch.object(server_module, "_LEGACY_BRANCH_INSPECTION_REMOVED", False):
                return client.get(
                    f"/api/v1/projects/proj-depr/release-branches/{branch}/addendums"
                )

    def test_returns_200_during_transition_window(self, client):
        resp = self._call_endpoint(client)
        assert resp.status_code == 200

    def test_response_body_has_deprecated_true(self, client):
        resp = self._call_endpoint(client)
        data = resp.json()
        assert data.get("deprecated") is True

    def test_response_body_has_message_field(self, client):
        resp = self._call_endpoint(client)
        data = resp.json()
        assert "message" in data
        assert "deprecated" in data["message"].lower() or "removed" in data["message"].lower()

    def test_response_body_has_replacement_path(self, client):
        resp = self._call_endpoint(client, branch="release/1.0")
        data = resp.json()
        assert "replacement" in data
        replacement = data["replacement"]
        assert "release-delivery/commits" in replacement
        assert "proj-depr" in replacement

    def test_replacement_path_includes_branch_filter(self, client):
        resp = self._call_endpoint(client, branch="release/1.1")
        data = resp.json()
        assert "release/1.1" in data.get("replacement", "")

    def test_response_has_deprecation_header(self, client):
        resp = self._call_endpoint(client)
        assert resp.headers.get("Deprecation") == "true"

    def test_response_has_sunset_header(self, client):
        resp = self._call_endpoint(client)
        assert "Sunset" in resp.headers

    def test_response_has_link_header_with_successor(self, client):
        resp = self._call_endpoint(client)
        link = resp.headers.get("Link", "")
        assert "release-delivery/commits" in link
        assert 'rel="successor-version"' in link

    def test_response_still_includes_groups_during_transition(self, client):
        """The compatibility response continues to return addendum groups."""
        resp = self._call_endpoint(client)
        data = resp.json()
        assert "groups" in data
        groups = data["groups"]
        for key in ("open", "in_progress", "in_review", "blocked", "merged", "archived"):
            assert key in groups

    def test_response_still_includes_project_id_and_branch(self, client):
        resp = self._call_endpoint(client, branch="release/1.0")
        data = resp.json()
        assert data["project_id"] == "proj-depr"
        assert data["branch"] == "release/1.0"

    def test_404_still_returned_for_unknown_project(self, client):
        orch = _FakeOrch(project=None, tracker=_WriteableTracker(issues=[], addendums_by_id={}))
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            with patch.object(server_module, "_LEGACY_BRANCH_INSPECTION_REMOVED", False):
                resp = client.get(
                    "/api/v1/projects/proj-unknown/release-branches/release/1.0/addendums"
                )
        assert resp.status_code == 404


class TestLegacyEndpointRemoved410:
    """When _LEGACY_BRANCH_INSPECTION_REMOVED is True the endpoint returns 410 Gone.

    OOMPAH-201: The removal is scheduled for after the v1.0→v1.1 upgrade window.
    Tests here exercise the 410 code path by patching the removal flag.
    """

    def _call_removed(self, client, project_id: str = "proj-1", branch: str = "release/1.0"):
        project = _make_project(pid=project_id)
        tracker = _WriteableTracker(issues=[], addendums_by_id={})
        orch = _FakeOrch(project=project, tracker=tracker)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            with patch.object(server_module, "_LEGACY_BRANCH_INSPECTION_REMOVED", True):
                return client.get(
                    f"/api/v1/projects/{project_id}/release-branches/{branch}/addendums"
                )

    def test_returns_410_gone(self, client):
        resp = self._call_removed(client)
        assert resp.status_code == 410

    def test_410_body_has_error_code_gone(self, client):
        resp = self._call_removed(client)
        data = resp.json()
        assert "error" in data
        assert data["error"]["code"] == "gone"

    def test_410_body_has_message(self, client):
        resp = self._call_removed(client)
        data = resp.json()
        assert "message" in data["error"]
        assert "removed" in data["error"]["message"].lower()

    def test_410_body_has_replacement_path(self, client):
        resp = self._call_removed(client, project_id="proj-abc", branch="release/2.0")
        data = resp.json()
        replacement = data["error"].get("replacement", "")
        assert "release-delivery/commits" in replacement
        assert "proj-abc" in replacement

    def test_410_replacement_encodes_branch(self, client):
        resp = self._call_removed(client, branch="release/1.5")
        data = resp.json()
        replacement = data["error"].get("replacement", "")
        assert "release/1.5" in replacement

    def test_410_returned_without_calling_tracker(self, client):
        """The 410 path returns before hitting the tracker/DB."""
        tracker = _WriteableTracker(issues=[], addendums_by_id={})
        project = _make_project()
        orch = _FakeOrch(project=project, tracker=tracker)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            with patch.object(server_module, "_LEGACY_BRANCH_INSPECTION_REMOVED", True):
                with patch.object(tracker, "fetch_all_issues", side_effect=RuntimeError("should not be called")) as mock_fetch:
                    resp = client.get(
                        "/api/v1/projects/proj-1/release-branches/release/1.0/addendums"
                    )
        assert resp.status_code == 410
        mock_fetch.assert_not_called()

    def test_410_for_unknown_project_returns_410_not_404(self, client):
        """When removed, 410 is returned before the project lookup."""
        orch = _FakeOrch(project=None, tracker=_WriteableTracker(issues=[], addendums_by_id={}))
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            with patch.object(server_module, "_LEGACY_BRANCH_INSPECTION_REMOVED", True):
                resp = client.get(
                    "/api/v1/projects/proj-unknown/release-branches/release/1.0/addendums"
                )
        assert resp.status_code == 410
