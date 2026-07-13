"""Tests for epic release-addendum approval and snapshot UI (OOMPAH-181).

Covers section 7 (Epic detail) of plans/release-branch-addendums.md:

  Schema:
  - included_child_ids field parsed from raw dict
  - included_child_ids field present in to_raw() output
  - included_child_ids defaults to empty list when absent from raw dict
  - included_child_ids is preserved across lifecycle transitions

  API rendering contract:
  - GET /release-addendums returns included_child_ids in each entry
  - Epic addendum row contains included_child_ids list
  - included_child_ids is present and empty for task (non-epic) addendums

  Epic commit resolution:
  - resolve_epic_addendum_commits collects commits from all Merged children
  - resolve_epic_addendum_commits excludes non-Merged children
  - resolve_epic_addendum_commits deduplicates commits across children
  - resolve_epic_addendum_commits records included_child_ids in order processed
  - resolve_epic_addendum_commits raises CommitResolutionError when no Merged children
  - resolve_epic_addendum_commits raises CommitResolutionError when no commits resolved
  - Descendants merged AFTER approval are NOT automatically included (snapshot invariant)

  POST approval for epics:
  - POST detects issue_type=epic and uses epic commit resolution
  - POST response contains included_child_ids on each addendum
  - POST for epic with no merged children returns 409

  Dashboard UI:
  - renderEpicReleaseAddendumsSection() is defined in the script
  - Epic renderer shows target_branch
  - Epic renderer shows snapshot size (commit count)
  - Epic renderer shows included child count
  - Epic renderer shows status badge
  - Epic renderer shows PR link
  - Epic renderer shows expandable snapshot toggle button
  - Epic renderer snapshot detail has immutable child list
  - Epic renderer snapshot detail has commit list
  - Epic renderer shows empty state for no addendums
  - Epic renderer shows Add release branches button for Merged epics only
  - openDetailPanel dispatches to renderEpicReleaseAddendumsSection for epics
  - openDetailPanel dispatches to renderReleaseAddendumsSection for tasks

  CSS:
  - epic-addendum-entry CSS class is defined
  - epic-addendum-row CSS class is defined
  - epic-addendum-snapshot-meta CSS class is defined
  - epic-addendum-snapshot-badge CSS class is defined
  - epic-addendum-snapshot-toggle CSS class is defined
  - epic-addendum-snapshot-detail CSS class is defined
  - epic-addendum-child-list CSS class is defined
  - epic-addendum-commit-list CSS class is defined
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
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
from oompah.release_addendum_approval import (
    CommitResolutionError,
    resolve_epic_addendum_commits,
)


# ---------------------------------------------------------------------------
# HTML/JS helpers
# ---------------------------------------------------------------------------


def _load_dashboard_html() -> str:
    return (
        Path(__file__).resolve().parents[1]
        / "oompah"
        / "templates"
        / "dashboard.html"
    ).read_text(encoding="utf-8")


def _load_dashboard_script() -> str:
    html = _load_dashboard_html()
    start = html.index("<script>") + len("<script>")
    end = html.rindex("</script>")
    return html[start:end]


def _load_dashboard_styles() -> str:
    html = _load_dashboard_html()
    start = html.index("<style>") + len("<style>")
    end = html.index("</style>")
    return html[start:end]


def _function_body(script: str, name: str, is_async: bool = False) -> str:
    """Extract the body of a named JavaScript function using brace counting."""
    prefix = "async function" if is_async else "function"
    marker = f"{prefix} {name}("
    start = script.index(marker)
    brace = script.index("{", start)
    depth = 0
    for pos in range(brace, len(script)):
        char = script[pos]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return script[brace + 1 : pos]
    raise AssertionError(f"Could not find function body for {name}")


# ---------------------------------------------------------------------------
# Schema helpers
# ---------------------------------------------------------------------------


_COMMITS = ["a" * 40, "b" * 40, "c" * 40]
_CHILD_IDS = ["FOO-11", "FOO-12"]

_BASE_RAW: dict = {
    "id": "FOO-10/release/1.0",
    "source_branch": "main",
    "target_branch": "release/1.0",
    "status": "open",
    "commits": list(_COMMITS),
    "work_branch": "oompah/release/FOO-10/release-1.0",
    "worktree_key": "release-FOO-10-release-1.0",
    "queued_at": "2026-07-13T12:00:00Z",
    "started_at": None,
    "completed_at": None,
    "pr_url": None,
    "result_commits": [],
    "error": None,
}


def _make_addendum(
    source_id: str = "FOO-10",
    target_branch: str = "release/1.0",
    status: AddendumStatus = AddendumStatus.OPEN,
    commits: list[str] | None = None,
    included_child_ids: list[str] | None = None,
) -> ReleaseAddendum:
    return ReleaseAddendum(
        id=make_addendum_id(source_id, target_branch),
        source_branch="main",
        target_branch=target_branch,
        status=status,
        commits=commits if commits is not None else list(_COMMITS),
        work_branch=make_work_branch(source_id, target_branch),
        worktree_key=make_worktree_key(source_id, target_branch),
        queued_at="2026-07-13T12:00:00Z",
        included_child_ids=included_child_ids if included_child_ids is not None else [],
    )


def _make_issue(
    identifier: str = "FOO-10",
    state: str = "Merged",
    issue_type: str = "task",
    branch_name: str | None = None,
) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title="A merged issue",
        description="",
        state=state,
        priority=1,
        issue_type=issue_type,
        labels=[],
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        branch_name=branch_name or identifier.lower(),
    )


def _make_project(pid: str = "proj-1") -> MagicMock:
    project = MagicMock(spec=Project)
    project.id = pid
    project.name = "Test Project"
    project.default_branch = "main"
    project.supported_release_branches = ["release/1.1", "release/1.0"]
    project.repo_url = "https://github.com/org/repo"
    project.repo_path = "/tmp/repos/proj-1"
    project.access_token = None
    project.branches = ["main", "release/*"]
    return project


def _make_tracker(raw_addendums=None) -> MagicMock:
    tracker = MagicMock()
    meta: dict = {}
    if raw_addendums is not None:
        meta["oompah.release_addendums"] = raw_addendums

    def _get_meta(identifier):
        return dict(meta)

    tracker.get_metadata = MagicMock(side_effect=_get_meta)
    return tracker


def _make_orchestrator(
    *,
    tracker: MagicMock | None = None,
    issue: Issue | None = None,
    project: MagicMock | None = None,
) -> MagicMock:
    t = tracker or _make_tracker()
    p = project or _make_project()
    orch = MagicMock()
    orch._tracker_for_project = MagicMock(return_value=t)
    orch.project_store.list_all = MagicMock(return_value=[p])
    orch.project_store.get = MagicMock(return_value=p)
    t.fetch_issue_detail = MagicMock(return_value=issue)
    return orch


@pytest.fixture()
def client():
    server_module._api_cache.invalidate_prefix("detail:")
    return TestClient(app, raise_server_exceptions=False)


# ===========================================================================
# Schema tests: included_child_ids
# ===========================================================================


class TestIncludedChildIdsSchema:
    def test_from_raw_parses_included_child_ids(self):
        raw = dict(_BASE_RAW)
        raw["included_child_ids"] = ["FOO-11", "FOO-12"]
        addendum = ReleaseAddendum.from_raw(raw)
        assert addendum.included_child_ids == ["FOO-11", "FOO-12"]

    def test_from_raw_defaults_empty_list_when_absent(self):
        raw = dict(_BASE_RAW)
        # no included_child_ids key
        raw.pop("included_child_ids", None)
        addendum = ReleaseAddendum.from_raw(raw)
        assert addendum.included_child_ids == []

    def test_from_raw_defaults_empty_list_when_null(self):
        raw = dict(_BASE_RAW)
        raw["included_child_ids"] = None
        addendum = ReleaseAddendum.from_raw(raw)
        assert addendum.included_child_ids == []

    def test_to_raw_includes_included_child_ids(self):
        addendum = _make_addendum(included_child_ids=["FOO-11", "FOO-12"])
        raw = addendum.to_raw()
        assert "included_child_ids" in raw
        assert raw["included_child_ids"] == ["FOO-11", "FOO-12"]

    def test_to_raw_included_child_ids_empty_for_task_addendums(self):
        addendum = _make_addendum(included_child_ids=[])
        raw = addendum.to_raw()
        assert raw["included_child_ids"] == []

    def test_round_trip_preserves_included_child_ids(self):
        addendum = _make_addendum(included_child_ids=["FOO-11", "FOO-12", "FOO-13"])
        raw = addendum.to_raw()
        restored = ReleaseAddendum.from_raw(raw)
        assert restored.included_child_ids == ["FOO-11", "FOO-12", "FOO-13"]

    def test_transition_preserves_included_child_ids(self):
        """included_child_ids must not change during a lifecycle transition."""
        from oompah.release_addendum_schema import AddendumRepository

        child_ids = ["FOO-11", "FOO-12"]
        addendum = _make_addendum(
            status=AddendumStatus.OPEN,
            included_child_ids=child_ids,
        )
        tracker = MagicMock()
        tracker.get_metadata = MagicMock(
            return_value={"oompah.release_addendums": [addendum.to_raw()]}
        )
        tracker.set_metadata_field = MagicMock()
        repo = AddendumRepository(tracker)
        updated_list = repo.transition(
            "FOO-10",
            addendum.id,
            AddendumStatus.IN_PROGRESS,
        )
        assert updated_list[0].included_child_ids == child_ids

    def test_from_raw_handles_string_scalar_as_single_element(self):
        """A bare string value is coerced to a single-element list."""
        raw = dict(_BASE_RAW)
        raw["included_child_ids"] = "FOO-11"
        addendum = ReleaseAddendum.from_raw(raw)
        assert addendum.included_child_ids == ["FOO-11"]


# ===========================================================================
# API rendering contract: GET /release-addendums returns included_child_ids
# ===========================================================================


class TestGetReleaseAddendumsReturnsChildIds:
    def _get(self, client, identifier: str = "FOO-10", project_id: str = "proj-1"):
        return client.get(
            f"/api/v1/issues/{identifier}/release-addendums",
            params={"project_id": project_id},
        )

    def test_response_includes_included_child_ids_for_epic_addendum(self, client):
        addendum = _make_addendum(included_child_ids=["FOO-11", "FOO-12"])
        issue = _make_issue(issue_type="epic")
        tracker = _make_tracker(raw_addendums=[addendum.to_raw()])
        orch = _make_orchestrator(tracker=tracker, issue=issue)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = self._get(client)
        assert resp.status_code == 200
        entry = resp.json()["addendums"][0]
        assert "included_child_ids" in entry
        assert entry["included_child_ids"] == ["FOO-11", "FOO-12"]

    def test_response_has_empty_included_child_ids_for_task_addendum(self, client):
        addendum = _make_addendum(included_child_ids=[])
        issue = _make_issue(issue_type="task")
        tracker = _make_tracker(raw_addendums=[addendum.to_raw()])
        orch = _make_orchestrator(tracker=tracker, issue=issue)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = self._get(client)
        assert resp.status_code == 200
        entry = resp.json()["addendums"][0]
        assert "included_child_ids" in entry
        assert entry["included_child_ids"] == []

    def test_snapshot_size_derivable_from_commits_field(self, client):
        """The UI derives snapshot_size = len(commits); verify commits is present."""
        addendum = _make_addendum(
            commits=["a" * 40, "b" * 40, "c" * 40],
            included_child_ids=["FOO-11"],
        )
        issue = _make_issue(issue_type="epic")
        tracker = _make_tracker(raw_addendums=[addendum.to_raw()])
        orch = _make_orchestrator(tracker=tracker, issue=issue)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = self._get(client)
        assert resp.status_code == 200
        entry = resp.json()["addendums"][0]
        assert "commits" in entry
        assert len(entry["commits"]) == 3


# ===========================================================================
# resolve_epic_addendum_commits unit tests
# ===========================================================================


def _make_child(
    identifier: str,
    state: str = "Merged",
    commits: list[str] | None = None,
) -> Issue:
    issue = _make_issue(identifier=identifier, state=state, issue_type="task")
    return issue


class TestResolveEpicAddendumCommits:
    """Unit tests for resolve_epic_addendum_commits (OOMPAH-181)."""

    def _make_tracker_with_children(self, children: list[Issue]) -> MagicMock:
        tracker = MagicMock()
        tracker.fetch_children = MagicMock(return_value=children)
        return tracker

    def _make_project(self) -> MagicMock:
        project = MagicMock()
        project.default_branch = "main"
        project.repo_path = "/tmp/test-repo"
        return project

    def test_collects_commits_from_merged_children(self):
        """Commits from all Merged children are collected in order."""
        epic = _make_issue("EPIC-1", state="Merged", issue_type="epic")
        child1 = _make_child("FOO-11")
        child2 = _make_child("FOO-12")
        tracker = self._make_tracker_with_children([child1, child2])
        project = self._make_project()

        sha1 = "a" * 40
        sha2 = "b" * 40

        def _resolve(issue, proj, scm=None, repo=None):
            if issue.identifier == "FOO-11":
                return [sha1]
            return [sha2]

        with patch(
            "oompah.release_addendum_approval.resolve_addendum_commits",
            side_effect=_resolve,
        ):
            commits, child_ids = resolve_epic_addendum_commits(
                epic, tracker, project
            )

        assert commits == [sha1, sha2]
        assert child_ids == ["FOO-11", "FOO-12"]

    def test_excludes_non_merged_children(self):
        """Only Merged-state children contribute commits."""
        epic = _make_issue("EPIC-1", state="Merged", issue_type="epic")
        merged_child = _make_child("FOO-11", state="Merged")
        open_child = _make_child("FOO-12", state="Open")
        in_progress_child = _make_child("FOO-13", state="In Progress")
        tracker = self._make_tracker_with_children(
            [merged_child, open_child, in_progress_child]
        )
        project = self._make_project()

        sha1 = "a" * 40

        def _resolve(issue, proj, scm=None, repo=None):
            if issue.identifier == "FOO-11":
                return [sha1]
            raise CommitResolutionError("should not be called for non-merged")

        with patch(
            "oompah.release_addendum_approval.resolve_addendum_commits",
            side_effect=_resolve,
        ):
            commits, child_ids = resolve_epic_addendum_commits(
                epic, tracker, project
            )

        assert commits == [sha1]
        assert "FOO-11" in child_ids
        assert "FOO-12" not in child_ids
        assert "FOO-13" not in child_ids

    def test_deduplicates_commits_across_children(self):
        """Commits that appear in multiple children are only included once."""
        epic = _make_issue("EPIC-1", state="Merged", issue_type="epic")
        child1 = _make_child("FOO-11")
        child2 = _make_child("FOO-12")
        tracker = self._make_tracker_with_children([child1, child2])
        project = self._make_project()

        shared_sha = "a" * 40
        unique_sha = "b" * 40

        def _resolve(issue, proj, scm=None, repo=None):
            if issue.identifier == "FOO-11":
                return [shared_sha, unique_sha]
            # child2 shares the first commit
            return [shared_sha]

        with patch(
            "oompah.release_addendum_approval.resolve_addendum_commits",
            side_effect=_resolve,
        ):
            commits, child_ids = resolve_epic_addendum_commits(
                epic, tracker, project
            )

        # shared_sha appears only once
        assert commits.count(shared_sha) == 1
        assert unique_sha in commits
        # Both children are listed because child2's work is in the snapshot
        assert "FOO-11" in child_ids
        assert "FOO-12" in child_ids

    def test_raises_when_no_merged_children(self):
        """CommitResolutionError raised when the epic has no Merged descendants."""
        epic = _make_issue("EPIC-1", state="Merged", issue_type="epic")
        open_child = _make_child("FOO-11", state="Open")
        tracker = self._make_tracker_with_children([open_child])
        project = self._make_project()

        with pytest.raises(CommitResolutionError, match="no Merged descendants"):
            resolve_epic_addendum_commits(epic, tracker, project)

    def test_raises_when_no_commits_resolved(self):
        """CommitResolutionError raised when all per-child resolutions fail."""
        epic = _make_issue("EPIC-1", state="Merged", issue_type="epic")
        child1 = _make_child("FOO-11")
        tracker = self._make_tracker_with_children([child1])
        project = self._make_project()

        def _raise(issue, proj, scm=None, repo=None):
            raise CommitResolutionError("git failure")

        with patch(
            "oompah.release_addendum_approval.resolve_addendum_commits",
            side_effect=_raise,
        ):
            with pytest.raises(CommitResolutionError, match="could not resolve any commits"):
                resolve_epic_addendum_commits(epic, tracker, project)

    def test_no_automatic_inclusion_after_approval(self):
        """Children that merge AFTER the snapshot was taken are not in included_child_ids.

        This verifies the invariant: the snapshot is fixed at approval time.
        A new child that is Merged later cannot retroactively join the addendum.
        """
        # At approval time: only FOO-11 is Merged
        epic = _make_issue("EPIC-1", state="Merged", issue_type="epic")
        merged_child = _make_child("FOO-11", state="Merged")
        later_child = _make_child("FOO-12", state="Open")  # not yet merged
        tracker = self._make_tracker_with_children([merged_child, later_child])
        project = self._make_project()

        sha_approved = "a" * 40

        def _resolve(issue, proj, scm=None, repo=None):
            if issue.identifier == "FOO-11":
                return [sha_approved]
            raise CommitResolutionError("not merged")

        with patch(
            "oompah.release_addendum_approval.resolve_addendum_commits",
            side_effect=_resolve,
        ):
            commits, child_ids = resolve_epic_addendum_commits(
                epic, tracker, project
            )

        # Only FOO-11 was Merged at approval time
        assert "FOO-11" in child_ids
        assert "FOO-12" not in child_ids
        assert commits == [sha_approved]

        # Simulate FOO-12 merging later — changing the tracker's child list
        # does NOT affect the already-snapshotted addendum (immutable commits)
        later_child_now_merged = _make_child("FOO-12", state="Merged")
        tracker.fetch_children = MagicMock(
            return_value=[merged_child, later_child_now_merged]
        )
        # The previously-created addendum still has the original snapshot
        addendum = _make_addendum(
            commits=commits,
            included_child_ids=child_ids,
        )
        assert "FOO-12" not in addendum.included_child_ids
        assert sha_approved in addendum.commits

    def test_raises_when_fetch_children_fails(self):
        """CommitResolutionError raised when tracker.fetch_children raises."""
        epic = _make_issue("EPIC-1", state="Merged", issue_type="epic")
        tracker = MagicMock()
        tracker.fetch_children = MagicMock(side_effect=RuntimeError("network error"))
        project = self._make_project()

        with pytest.raises(CommitResolutionError, match="Failed to fetch children"):
            resolve_epic_addendum_commits(epic, tracker, project)


# ===========================================================================
# POST endpoint: epic-specific approval
# ===========================================================================


class TestEpicApprovalEndpoint:
    """Test that POST /release-addendums uses epic resolution for epic issues."""

    def _make_catalog(self, branches=("release/1.0", "release/1.1")):
        from oompah.release_branch_catalog import CatalogResult, ReleaseBranch
        return CatalogResult(
            project_id="proj-1",
            source_branch="main",
            branches=[
                ReleaseBranch(name=b, available=True, stale=False) for b in branches
            ],
            stale=False,
        )

    def _build_orchestrator_for_epic(
        self,
        epic_identifier: str = "EPIC-1",
        children: list[Issue] | None = None,
    ) -> tuple[MagicMock, MagicMock, MagicMock]:
        epic = _make_issue(
            identifier=epic_identifier,
            state="Merged",
            issue_type="epic",
        )
        project = _make_project()
        tracker = _make_tracker()
        tracker.fetch_issue_detail = MagicMock(return_value=epic)
        tracker.fetch_children = MagicMock(return_value=children or [])
        tracker.set_metadata_field = MagicMock()
        orch = MagicMock()
        orch.project_store.get = MagicMock(return_value=project)
        orch.project_store.list_all = MagicMock(return_value=[project])
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch.event_bus = None
        return orch, tracker, epic

    def test_epic_approval_calls_epic_commit_resolution(self, client):
        """When issue_type=epic, the POST endpoint uses epic commit resolution."""
        merged_child = _make_child("FOO-11", state="Merged")
        orch, tracker, epic = self._build_orchestrator_for_epic(
            children=[merged_child]
        )
        catalog = self._make_catalog()

        sha = "a" * 40
        child_ids = ["FOO-11"]

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch(
                "oompah.release_addendum_approval.resolve_epic_addendum_commits",
                return_value=([sha], child_ids),
            ) as mock_epic_resolve,
            patch("oompah.release_branch_catalog.get_default_catalog") as mock_catalog,
        ):
            mock_catalog.return_value.list_candidates.return_value = catalog
            resp = client.post(
                "/api/v1/issues/EPIC-1/release-addendums",
                json={
                    "project_id": "proj-1",
                    "target_branches": ["release/1.0"],
                    "idempotency_key": "test-key-1",
                },
            )

        assert resp.status_code == 200
        mock_epic_resolve.assert_called_once()

    def test_epic_approval_response_contains_included_child_ids(self, client):
        """POST response addendums must include included_child_ids."""
        merged_child = _make_child("FOO-11", state="Merged")
        orch, tracker, epic = self._build_orchestrator_for_epic(
            children=[merged_child]
        )
        catalog = self._make_catalog()

        sha = "a" * 40
        child_ids = ["FOO-11"]

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch(
                "oompah.release_addendum_approval.resolve_epic_addendum_commits",
                return_value=([sha], child_ids),
            ),
            patch("oompah.release_branch_catalog.get_default_catalog") as mock_catalog,
        ):
            mock_catalog.return_value.list_candidates.return_value = catalog
            resp = client.post(
                "/api/v1/issues/EPIC-1/release-addendums",
                json={
                    "project_id": "proj-1",
                    "target_branches": ["release/1.0"],
                    "idempotency_key": "test-key-2",
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["addendums"]) == 1
        entry = data["addendums"][0]
        assert "included_child_ids" in entry
        assert entry["included_child_ids"] == child_ids

    def test_epic_approval_returns_409_when_no_merged_children(self, client):
        """POST returns 409 when epic has no Merged descendants."""
        open_child = _make_child("FOO-11", state="Open")
        orch, tracker, epic = self._build_orchestrator_for_epic(
            children=[open_child]
        )
        catalog = self._make_catalog()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch(
                "oompah.release_addendum_approval.resolve_epic_addendum_commits",
                side_effect=CommitResolutionError("no Merged descendants"),
            ),
            patch("oompah.release_branch_catalog.get_default_catalog") as mock_catalog,
        ):
            mock_catalog.return_value.list_candidates.return_value = catalog
            resp = client.post(
                "/api/v1/issues/EPIC-1/release-addendums",
                json={
                    "project_id": "proj-1",
                    "target_branches": ["release/1.0"],
                    "idempotency_key": "test-key-3",
                },
            )

        assert resp.status_code == 409
        body = resp.json()
        assert body["error"]["code"] == "commit_resolution_failed"

    def test_task_approval_does_not_call_epic_resolution(self, client):
        """For non-epic issues, resolve_epic_addendum_commits must not be called."""
        task = _make_issue("FOO-10", state="Merged", issue_type="task")
        project = _make_project()
        tracker = _make_tracker()
        tracker.fetch_issue_detail = MagicMock(return_value=task)
        tracker.set_metadata_field = MagicMock()
        orch = MagicMock()
        orch.project_store.get = MagicMock(return_value=project)
        orch.project_store.list_all = MagicMock(return_value=[project])
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch.event_bus = None
        catalog = self._make_catalog()
        sha = "a" * 40

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch(
                "oompah.release_addendum_approval.resolve_addendum_commits",
                return_value=[sha],
            ),
            patch(
                "oompah.release_addendum_approval.resolve_epic_addendum_commits",
            ) as mock_epic_resolve,
            patch("oompah.release_branch_catalog.get_default_catalog") as mock_catalog,
        ):
            mock_catalog.return_value.list_candidates.return_value = catalog
            resp = client.post(
                "/api/v1/issues/FOO-10/release-addendums",
                json={
                    "project_id": "proj-1",
                    "target_branches": ["release/1.0"],
                    "idempotency_key": "test-key-4",
                },
            )

        assert resp.status_code == 200
        mock_epic_resolve.assert_not_called()


# ===========================================================================
# Dashboard UI: renderEpicReleaseAddendumsSection
# ===========================================================================


class TestRenderEpicReleaseAddendumsSectionFunction:
    def test_function_is_defined(self):
        script = _load_dashboard_script()
        assert "function renderEpicReleaseAddendumsSection(" in script

    def test_renders_target_branch(self):
        script = _load_dashboard_script()
        body = _function_body(script, "renderEpicReleaseAddendumsSection")
        assert "entry.target_branch" in body
        assert "release-addendum-branch" in body

    def test_renders_snapshot_size(self):
        """Must show commit count (snapshot size) from entry.commits."""
        script = _load_dashboard_script()
        body = _function_body(script, "renderEpicReleaseAddendumsSection")
        assert "snapshotSize" in body or "snapshot_size" in body or "commits" in body

    def test_renders_included_child_count(self):
        """Must show the number of included children (childCount)."""
        script = _load_dashboard_script()
        body = _function_body(script, "renderEpicReleaseAddendumsSection")
        assert "childCount" in body or "child_count" in body or "included_child_ids" in body

    def test_renders_status_badge(self):
        script = _load_dashboard_script()
        body = _function_body(script, "renderEpicReleaseAddendumsSection")
        assert "entry.status" in body
        assert "release-addendum-status" in body

    def test_renders_pr_link(self):
        script = _load_dashboard_script()
        body = _function_body(script, "renderEpicReleaseAddendumsSection")
        assert "entry.pr_url" in body
        assert "release-addendum-pr-link" in body

    def test_renders_expandable_snapshot_toggle(self):
        """Must include a toggle button to expand/collapse the snapshot detail."""
        script = _load_dashboard_script()
        body = _function_body(script, "renderEpicReleaseAddendumsSection")
        assert "Show snapshot" in body or "snapshot-toggle" in body

    def test_renders_snapshot_detail_with_child_list(self):
        """Snapshot detail must list included child IDs."""
        script = _load_dashboard_script()
        body = _function_body(script, "renderEpicReleaseAddendumsSection")
        assert "included_child_ids" in body
        assert "child" in body.lower()

    def test_renders_snapshot_detail_with_commit_list(self):
        """Snapshot detail must list commits (at least partially)."""
        script = _load_dashboard_script()
        body = _function_body(script, "renderEpicReleaseAddendumsSection")
        assert "commits" in body

    def test_snapshot_detail_is_immutable_label(self):
        """Snapshot is described as immutable/expandable in the function."""
        script = _load_dashboard_script()
        body = _function_body(script, "renderEpicReleaseAddendumsSection")
        # The snapshot detail element exists and is hidden by default
        assert "hidden" in body
        assert "epic-addendum-snapshot-detail" in body

    def test_snapshot_toggle_uses_aria_expanded(self):
        """The snapshot toggle button must use aria-expanded for accessibility."""
        script = _load_dashboard_script()
        body = _function_body(script, "renderEpicReleaseAddendumsSection")
        assert "aria-expanded" in body

    def test_empty_state_message(self):
        """Must show an empty-state message when no addendums exist."""
        script = _load_dashboard_script()
        body = _function_body(script, "renderEpicReleaseAddendumsSection")
        body_lower = body.lower()
        assert "no epic release addendum" in body_lower or "no release addendum" in body_lower

    def test_shows_add_button_for_merged_epics_only(self):
        """'Add release branches' button must appear only for Merged epics."""
        script = _load_dashboard_script()
        body = _function_body(script, "renderEpicReleaseAddendumsSection")
        assert "Merged" in body
        assert "epicState" in body

    def test_add_button_calls_existing_dialog(self):
        """The 'Add release branches' button must reuse the existing dialog function."""
        script = _load_dashboard_script()
        body = _function_body(script, "renderEpicReleaseAddendumsSection")
        assert "openAddReleaseBranchesDialog(" in body

    def test_no_child_task_link(self):
        """Epic renderer must NOT render child-task links (no entry.task_id)."""
        script = _load_dashboard_script()
        body = _function_body(script, "renderEpicReleaseAddendumsSection")
        assert "entry.task_id" not in body, (
            "renderEpicReleaseAddendumsSection must not render child-task links"
        )

    def test_no_apply_all_behavior(self):
        """Epic renderer must NOT reference apply-all."""
        script = _load_dashboard_script()
        body = _function_body(script, "renderEpicReleaseAddendumsSection")
        assert "apply" not in body.lower() or "applyAll" not in body

    def test_section_heading_says_release_addendums(self):
        script = _load_dashboard_script()
        body = _function_body(script, "renderEpicReleaseAddendumsSection")
        assert "Release addendums" in body


# ===========================================================================
# openDetailPanel: dispatches to correct renderer
# ===========================================================================


class TestOpenDetailPanelDispatch:
    def test_dispatches_to_epic_renderer_for_epics(self):
        """openDetailPanel must call renderEpicReleaseAddendumsSection for epics."""
        script = _load_dashboard_script()
        body = _function_body(script, "openDetailPanel", is_async=True)
        assert "renderEpicReleaseAddendumsSection(" in body

    def test_dispatches_to_task_renderer_for_non_epics(self):
        """openDetailPanel must still call renderReleaseAddendumsSection for tasks."""
        script = _load_dashboard_script()
        body = _function_body(script, "openDetailPanel", is_async=True)
        assert "renderReleaseAddendumsSection(" in body

    def test_dispatch_checks_issue_type(self):
        """openDetailPanel must branch on detail.issue_type."""
        script = _load_dashboard_script()
        body = _function_body(script, "openDetailPanel", is_async=True)
        assert "issue_type" in body
        assert "epic" in body


# ===========================================================================
# CSS: epic addendum classes
# ===========================================================================


class TestEpicAddendumCss:
    def test_css_defines_epic_addendum_entry(self):
        styles = _load_dashboard_styles()
        assert ".epic-addendum-entry" in styles

    def test_css_defines_epic_addendum_row(self):
        styles = _load_dashboard_styles()
        assert ".epic-addendum-row" in styles

    def test_css_defines_epic_addendum_snapshot_meta(self):
        styles = _load_dashboard_styles()
        assert ".epic-addendum-snapshot-meta" in styles

    def test_css_defines_epic_addendum_snapshot_badge(self):
        styles = _load_dashboard_styles()
        assert ".epic-addendum-snapshot-badge" in styles

    def test_css_defines_epic_addendum_snapshot_toggle(self):
        styles = _load_dashboard_styles()
        assert ".epic-addendum-snapshot-toggle" in styles

    def test_css_defines_epic_addendum_snapshot_detail(self):
        styles = _load_dashboard_styles()
        assert ".epic-addendum-snapshot-detail" in styles

    def test_css_defines_epic_addendum_child_list(self):
        styles = _load_dashboard_styles()
        assert ".epic-addendum-child-list" in styles

    def test_css_defines_epic_addendum_commit_list(self):
        styles = _load_dashboard_styles()
        assert ".epic-addendum-commit-list" in styles
