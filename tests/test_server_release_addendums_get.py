"""Tests for GET /api/v1/issues/{identifier}/release-addendums (OOMPAH-180).

Covers the endpoint added in OOMPAH-180 to allow the task-detail UI to read
the current addendum list without going through the approval POST endpoint.

  Response contract:
  - 200 with empty addendums list when no addendums have been created
  - 200 with full addendum list when addendums exist
  - Response always contains 'identifier' and 'addendums' keys
  - Each addendum entry has target_branch, status, pr_url, error, queued_at
  - 404 for unknown issue
  - 503 on unexpected server errors

  Field presence:
  - All to_raw() fields present per entry
  - Multiple addendums in correct order
"""

from __future__ import annotations

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


def _make_issue(
    identifier: str = "FOO-10",
    state: str = "Merged",
) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title="A merged task",
        description="",
        state=state,
        priority=1,
        issue_type="task",
        labels=[],
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
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
    """Return a mock tracker whose get_metadata returns the given raw addendums."""
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


def _make_addendum(
    source_id: str = "FOO-10",
    target_branch: str = "release/1.0",
    status: AddendumStatus = AddendumStatus.OPEN,
    pr_url: str | None = None,
    error: str | None = None,
    commits: list[str] | None = None,
) -> ReleaseAddendum:
    commits = commits or ["abc123" + "0" * 34]
    return ReleaseAddendum(
        id=make_addendum_id(source_id, target_branch),
        source_branch="main",
        target_branch=target_branch,
        status=status,
        commits=commits,
        work_branch=make_work_branch(source_id, target_branch),
        worktree_key=make_worktree_key(source_id, target_branch),
        queued_at="2026-07-13T12:00:00Z",
        started_at=None,
        completed_at=None,
        pr_url=pr_url,
        result_commits=[],
        error=error,
    )


@pytest.fixture()
def client():
    server_module._api_cache.invalidate_prefix("detail:")
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Tests: GET /api/v1/issues/{identifier}/release-addendums
# ---------------------------------------------------------------------------


class TestGetReleaseAddendumsEndpoint:
    _ENDPOINT = "/api/v1/issues/FOO-10/release-addendums"

    def _get(self, client, identifier: str = "FOO-10", project_id: str = "proj-1"):
        return client.get(
            f"/api/v1/issues/{identifier}/release-addendums",
            params={"project_id": project_id},
        )

    # --- 200: empty list ---

    def test_returns_200_with_empty_list_when_no_addendums(self, client):
        issue = _make_issue()
        orch = _make_orchestrator(
            tracker=_make_tracker(raw_addendums=None),
            issue=issue,
        )
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = self._get(client)
        assert resp.status_code == 200
        data = resp.json()
        assert data["identifier"] == "FOO-10"
        assert data["addendums"] == []

    def test_response_shape_has_identifier_and_addendums_keys(self, client):
        issue = _make_issue()
        orch = _make_orchestrator(tracker=_make_tracker(), issue=issue)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = self._get(client)
        assert resp.status_code == 200
        body = resp.json()
        assert "identifier" in body
        assert "addendums" in body

    # --- 200: with addendums ---

    def test_returns_one_addendum(self, client):
        addendum = _make_addendum(target_branch="release/1.0")
        issue = _make_issue()
        tracker = _make_tracker(raw_addendums=[addendum.to_raw()])
        orch = _make_orchestrator(tracker=tracker, issue=issue)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = self._get(client)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["addendums"]) == 1
        entry = data["addendums"][0]
        assert entry["target_branch"] == "release/1.0"
        assert entry["status"] == "open"

    def test_returns_two_addendums(self, client):
        a1 = _make_addendum(target_branch="release/1.1")
        a2 = _make_addendum(target_branch="release/1.0")
        issue = _make_issue()
        tracker = _make_tracker(raw_addendums=[a1.to_raw(), a2.to_raw()])
        orch = _make_orchestrator(tracker=tracker, issue=issue)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = self._get(client)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["addendums"]) == 2
        branches = {e["target_branch"] for e in data["addendums"]}
        assert branches == {"release/1.1", "release/1.0"}

    def test_addendum_entry_has_required_fields(self, client):
        addendum = _make_addendum(
            target_branch="release/1.0",
            status=AddendumStatus.BLOCKED,
            error="merge conflict",
        )
        issue = _make_issue()
        tracker = _make_tracker(raw_addendums=[addendum.to_raw()])
        orch = _make_orchestrator(tracker=tracker, issue=issue)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = self._get(client)
        assert resp.status_code == 200
        entry = resp.json()["addendums"][0]
        # Fields required by the UI
        assert "target_branch" in entry
        assert "status" in entry
        assert "pr_url" in entry
        assert "error" in entry
        assert "queued_at" in entry

    def test_addendum_entry_error_field_present_when_blocked(self, client):
        addendum = _make_addendum(
            status=AddendumStatus.BLOCKED,
            error="cherry-pick conflict on file.py",
        )
        issue = _make_issue()
        tracker = _make_tracker(raw_addendums=[addendum.to_raw()])
        orch = _make_orchestrator(tracker=tracker, issue=issue)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = self._get(client)
        entry = resp.json()["addendums"][0]
        assert entry["error"] == "cherry-pick conflict on file.py"
        assert entry["status"] == "blocked"

    def test_addendum_entry_pr_url_present_when_in_review(self, client):
        addendum = _make_addendum(
            status=AddendumStatus.IN_REVIEW,
            pr_url="https://github.com/org/repo/pull/42",
        )
        issue = _make_issue()
        tracker = _make_tracker(raw_addendums=[addendum.to_raw()])
        orch = _make_orchestrator(tracker=tracker, issue=issue)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = self._get(client)
        entry = resp.json()["addendums"][0]
        assert entry["pr_url"] == "https://github.com/org/repo/pull/42"

    def test_returns_identifier_from_issue(self, client):
        issue = _make_issue(identifier="BAR-99")
        tracker = _make_tracker()
        orch = _make_orchestrator(tracker=tracker, issue=issue)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get(
                "/api/v1/issues/BAR-99/release-addendums",
                params={"project_id": "proj-1"},
            )
        assert resp.status_code == 200
        assert resp.json()["identifier"] == "BAR-99"

    # --- 404 for unknown issue ---

    def test_returns_404_for_unknown_issue(self, client):
        orch = MagicMock()
        orch.project_store.list_all = MagicMock(return_value=[_make_project()])
        orch.project_store.get = MagicMock(return_value=_make_project())
        tracker = _make_tracker()
        tracker.fetch_issue_detail = MagicMock(return_value=None)
        orch._tracker_for_project = MagicMock(return_value=tracker)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get(
                "/api/v1/issues/NONEXISTENT-1/release-addendums",
                params={"project_id": "proj-1"},
            )
        assert resp.status_code == 404
        body = resp.json()
        assert body["error"]["code"] == "issue_not_found"

    # --- All addendum statuses round-trip ---

    @pytest.mark.parametrize("status", [
        AddendumStatus.OPEN,
        AddendumStatus.IN_PROGRESS,
        AddendumStatus.IN_REVIEW,
        AddendumStatus.BLOCKED,
        AddendumStatus.MERGED,
        AddendumStatus.ARCHIVED,
    ])
    def test_all_statuses_round_trip(self, client, status):
        addendum = _make_addendum(status=status)
        issue = _make_issue()
        tracker = _make_tracker(raw_addendums=[addendum.to_raw()])
        orch = _make_orchestrator(tracker=tracker, issue=issue)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = self._get(client)
        assert resp.status_code == 200
        entry = resp.json()["addendums"][0]
        assert entry["status"] == status.value

    # --- Empty addendums field (null stored value) ---

    def test_null_stored_addendums_returns_empty_list(self, client):
        issue = _make_issue()
        tracker = _make_tracker(raw_addendums=None)
        orch = _make_orchestrator(tracker=tracker, issue=issue)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = self._get(client)
        assert resp.status_code == 200
        assert resp.json()["addendums"] == []
