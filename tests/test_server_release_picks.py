"""Tests for the release-picks REST API endpoints in server.py (TASK-456.1).

Covers:
  GET /api/v1/issues/{identifier}/release-picks
    - Returns 200 with normalised release-pick data
    - Returns 404 when issue not found
    - Returns 503 on unexpected errors
    - Passes project to enable validation when project_id supplied

  PATCH /api/v1/issues/{identifier}/release-picks
    - Returns 400 on missing project_id
    - Returns 400 on invalid JSON
    - Returns 400 when neither 'branch' nor 'backports' supplied
    - Returns 400 on branch validation failure
    - Returns 200 with updated data on single-entry update
    - Returns 200 with updated data on bulk update
    - Returns 404 when project not found
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.server import app
from oompah.models import Issue, Project


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_issue(identifier: str = "TASK-1") -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title="A task",
        description="",
        state="open",
        priority=2,
        issue_type="task",
        labels=[],
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )


def _make_tracker(meta: dict | None = None) -> MagicMock:
    tracker = MagicMock()
    tracker.get_metadata = MagicMock(return_value=meta or {})
    tracker.set_metadata_field = MagicMock()
    tracker.fetch_issue_detail = MagicMock(return_value=None)
    return tracker


def _make_project(pid: str = "proj-1") -> MagicMock:
    project = MagicMock(spec=Project)
    project.id = pid
    project.name = "Test Project"
    project.branches = ["release/*", "main"]
    project.default_branch = "main"
    project.matches_branch = MagicMock(side_effect=lambda b: b.startswith("release/") or b == "main")
    return project


def _make_orchestrator(
    *,
    tracker: MagicMock | None = None,
    issue: Issue | None = None,
    project: MagicMock | None = None,
    project_id: str = "proj-1",
) -> MagicMock:
    t = tracker or _make_tracker()
    p = project or _make_project(project_id)
    orch = MagicMock()
    orch._tracker_for_project = MagicMock(return_value=t)
    orch.project_store.list_all = MagicMock(return_value=[p])
    orch.project_store.get = MagicMock(return_value=p)
    # Wire fetch_issue_detail so _find_tracker_for_issue works
    t.fetch_issue_detail = MagicMock(return_value=issue)
    return orch, t, p


@pytest.fixture()
def client():
    server_module._api_cache.invalidate_prefix("detail:")
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# GET /api/v1/issues/{identifier}/release-picks
# ---------------------------------------------------------------------------


class TestGetReleasePicksEndpoint:
    def test_returns_200_with_empty_picks(self, client):
        issue = _make_issue("TASK-1")
        orch, tracker, project = _make_orchestrator(issue=issue)

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get(
                "/api/v1/issues/TASK-1/release-picks",
                params={"project_id": "proj-1"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["identifier"] == "TASK-1"
        assert data["backports"] == []
        assert data["backport_of"] is None

    def test_returns_normalised_backports(self, client):
        meta = {
            "oompah.backports": [
                {
                    "branch": "release/1.0",
                    "status": "pr_open",
                    "task_id": "TASK-1.1",
                    "pr_url": "https://github.com/org/repo/pull/42",
                }
            ]
        }
        issue = _make_issue("TASK-1")
        orch, tracker, project = _make_orchestrator(issue=issue)
        tracker.get_metadata = MagicMock(return_value=meta)

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get(
                "/api/v1/issues/TASK-1/release-picks",
                params={"project_id": "proj-1"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["backports"]) == 1
        entry = data["backports"][0]
        assert entry["branch"] == "release/1.0"
        assert entry["status"] == "pr_open"
        assert entry["task_id"] == "TASK-1.1"
        assert entry["pr_url"] == "https://github.com/org/repo/pull/42"
        assert entry["pr_id"] == "42"
        assert entry["is_valid"] is True

    def test_returns_backport_of(self, client):
        meta = {"oompah.backport_of": "TASK-100"}
        issue = _make_issue("TASK-100.1")
        orch, tracker, project = _make_orchestrator(issue=issue)
        tracker.get_metadata = MagicMock(return_value=meta)

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get(
                "/api/v1/issues/TASK-100.1/release-picks",
                params={"project_id": "proj-1"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["backport_of"]["source"] == "TASK-100"
        assert data["backport_of"]["status"] == "waiting"

    def test_returns_404_when_issue_not_found(self, client):
        orch, tracker, project = _make_orchestrator(issue=None)

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get(
                "/api/v1/issues/TASK-MISSING/release-picks",
                params={"project_id": "proj-1"},
            )

        assert resp.status_code == 404
        data = resp.json()
        assert data["error"]["code"] == "issue_not_found"

    def test_returns_503_on_unexpected_error(self, client):
        with patch.object(server_module, "_get_orchestrator", side_effect=RuntimeError("boom")):
            resp = client.get("/api/v1/issues/TASK-1/release-picks")

        assert resp.status_code == 503

    def test_works_without_project_id(self, client):
        """Should search all projects when project_id is omitted."""
        issue = _make_issue("TASK-2")
        orch, tracker, project = _make_orchestrator(issue=issue)

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get("/api/v1/issues/TASK-2/release-picks")

        assert resp.status_code == 200
        data = resp.json()
        assert data["identifier"] == "TASK-2"

    def test_issue_key_query_overrides_path_identifier(self, client):
        issue = _make_issue("acme/tasks#227")
        orch, tracker, project = _make_orchestrator(issue=issue)

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get(
                "/api/v1/issues/227/release-picks",
                params={
                    "project_id": "proj-1",
                    "issue_key": "acme/tasks#227",
                },
            )

        assert resp.status_code == 200
        tracker.get_metadata.assert_called_with("acme/tasks#227")

    def test_validation_marks_invalid_branch(self, client):
        meta = {"oompah.backports": ["bad-branch"]}
        issue = _make_issue("TASK-3")
        orch, tracker, project = _make_orchestrator(issue=issue)
        tracker.get_metadata = MagicMock(return_value=meta)
        # Project only matches "release/*"
        project.matches_branch = MagicMock(side_effect=lambda b: b.startswith("release/"))

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get(
                "/api/v1/issues/TASK-3/release-picks",
                params={"project_id": "proj-1"},
            )

        assert resp.status_code == 200
        entry = resp.json()["backports"][0]
        assert entry["is_valid"] is False
        assert entry["validation_error"] is not None


# ---------------------------------------------------------------------------
# PATCH /api/v1/issues/{identifier}/release-picks
# ---------------------------------------------------------------------------


class TestPatchReleasePicksEndpoint:
    def test_returns_400_when_no_project_id(self, client):
        resp = client.patch(
            "/api/v1/issues/TASK-1/release-picks",
            json={"branch": "release/1.0"},
        )
        assert resp.status_code == 400
        data = resp.json()
        assert "project_id" in data["error"]["message"]

    def test_returns_400_on_invalid_json(self, client):
        resp = client.patch(
            "/api/v1/issues/TASK-1/release-picks",
            data="not-json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400

    def test_returns_400_when_no_branch_or_backports(self, client):
        orch, tracker, project = _make_orchestrator(issue=_make_issue("TASK-1"))

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.patch(
                "/api/v1/issues/TASK-1/release-picks",
                json={"project_id": "proj-1", "status": "waiting"},
            )

        assert resp.status_code == 400
        assert "branch" in resp.json()["error"]["message"]

    def test_single_entry_update_returns_200(self, client):
        issue = _make_issue("TASK-5")
        orch, tracker, project = _make_orchestrator(issue=issue)

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.patch(
                "/api/v1/issues/TASK-5/release-picks",
                json={
                    "project_id": "proj-1",
                    "branch": "release/1.0",
                    "status": "waiting",
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["identifier"] == "TASK-5"
        assert len(data["backports"]) == 1
        assert data["backports"][0]["branch"] == "release/1.0"

    def test_single_entry_with_all_fields(self, client):
        issue = _make_issue("TASK-6")
        orch, tracker, project = _make_orchestrator(issue=issue)

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.patch(
                "/api/v1/issues/TASK-6/release-picks",
                json={
                    "project_id": "proj-1",
                    "branch": "release/2.0",
                    "status": "pr_open",
                    "task_id": "TASK-6.1",
                    "pr_url": "https://github.com/org/repo/pull/88",
                },
            )

        assert resp.status_code == 200
        entry = resp.json()["backports"][0]
        assert entry["status"] == "pr_open"
        assert entry["task_id"] == "TASK-6.1"
        assert entry["pr_url"] == "https://github.com/org/repo/pull/88"
        assert entry["pr_id"] == "88"

    def test_bulk_update_returns_200(self, client):
        issue = _make_issue("TASK-7")
        orch, tracker, project = _make_orchestrator(issue=issue)

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.patch(
                "/api/v1/issues/TASK-7/release-picks",
                json={
                    "project_id": "proj-1",
                    "backports": [
                        {"branch": "release/1.0", "status": "waiting"},
                        {"branch": "release/2.0", "status": "task_created"},
                    ],
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["backports"]) == 2

    def test_bulk_update_returns_400_when_not_list(self, client):
        orch, tracker, project = _make_orchestrator(issue=_make_issue("TASK-8"))

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.patch(
                "/api/v1/issues/TASK-8/release-picks",
                json={"project_id": "proj-1", "backports": "not-a-list"},
            )

        assert resp.status_code == 400
        assert "backports" in resp.json()["error"]["message"]

    def test_single_entry_validation_failure_returns_400(self, client):
        issue = _make_issue("TASK-9")
        orch, tracker, project = _make_orchestrator(issue=issue)
        # Project only allows "release/*"
        project.matches_branch = MagicMock(side_effect=lambda b: b.startswith("release/"))

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.patch(
                "/api/v1/issues/TASK-9/release-picks",
                json={"project_id": "proj-1", "branch": "bad-branch"},
            )

        assert resp.status_code == 400
        data = resp.json()
        assert data["error"]["code"] == "validation"

    def test_bulk_validation_failure_returns_400(self, client):
        issue = _make_issue("TASK-10")
        orch, tracker, project = _make_orchestrator(issue=issue)
        project.matches_branch = MagicMock(side_effect=lambda b: b.startswith("release/"))

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.patch(
                "/api/v1/issues/TASK-10/release-picks",
                json={
                    "project_id": "proj-1",
                    "backports": [
                        {"branch": "release/1.0"},
                        {"branch": "bad-branch"},
                    ],
                },
            )

        assert resp.status_code == 400

    def test_returns_404_when_project_not_found(self, client):
        orch = MagicMock()
        orch._tracker_for_project = MagicMock(side_effect=Exception("Unknown project"))
        orch.project_store.get = MagicMock(return_value=None)

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.patch(
                "/api/v1/issues/TASK-11/release-picks",
                json={"project_id": "nonexistent", "branch": "release/1.0"},
            )

        assert resp.status_code == 404

    def test_set_metadata_field_called_on_write(self, client):
        issue = _make_issue("TASK-12")
        orch, tracker, project = _make_orchestrator(issue=issue)

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.patch(
                "/api/v1/issues/TASK-12/release-picks",
                json={"project_id": "proj-1", "branch": "release/3.0"},
            )

        assert resp.status_code == 200
        tracker.set_metadata_field.assert_called_once()
        call_args = tracker.set_metadata_field.call_args
        assert call_args[0][1] == "oompah.backports"

    def test_issue_key_body_overrides_path_identifier_on_write(self, client):
        issue = _make_issue("acme/tasks#227")
        orch, tracker, project = _make_orchestrator(issue=issue)

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.patch(
                "/api/v1/issues/227/release-picks",
                json={
                    "project_id": "proj-1",
                    "issue_key": "acme/tasks#227",
                    "branch": "release/3.0",
                },
            )

        assert resp.status_code == 200
        tracker.set_metadata_field.assert_called_once()
        assert tracker.set_metadata_field.call_args[0][0] == "acme/tasks#227"


# ---------------------------------------------------------------------------
# Helpers for epic matrix endpoint tests
# ---------------------------------------------------------------------------


def _make_child_issue(identifier: str, title: str = "Child", state: str = "open") -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=title,
        state=state,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )


def _make_epic_orchestrator(
    *,
    tracker: MagicMock | None = None,
    project: MagicMock | None = None,
    epic: Issue | None = None,
    children: list | None = None,
    meta_by_id: dict | None = None,
    project_id: str = "proj-1",
) -> tuple:
    t = tracker or MagicMock()
    p = project or _make_project(project_id)

    epic_issue = epic or _make_issue("TASK-456")
    all_children = children or []
    meta_map = meta_by_id or {}

    t.fetch_issue_detail = MagicMock(return_value=epic_issue)
    t.fetch_children = MagicMock(return_value=all_children)
    t.get_metadata = MagicMock(side_effect=lambda ident: meta_map.get(ident, {}))
    t.set_metadata_field = MagicMock()

    orch = MagicMock()
    orch._tracker_for_project = MagicMock(return_value=t)
    orch.project_store.list_all = MagicMock(return_value=[p])
    orch.project_store.get = MagicMock(return_value=p)
    return orch, t, p


# ---------------------------------------------------------------------------
# GET /api/v1/issues/{identifier}/release-picks/matrix
# ---------------------------------------------------------------------------


class TestGetEpicReleasePicksMatrix:
    def test_returns_200_with_empty_matrix(self, client):
        orch, tracker, project = _make_epic_orchestrator()
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get(
                "/api/v1/issues/TASK-456/release-picks/matrix",
                params={"project_id": "proj-1"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["epic_identifier"] == "TASK-456"
        assert data["branches"] == []
        assert data["rows"] == []

    def test_returns_matrix_with_children(self, client):
        child1 = _make_child_issue("TASK-456.1", title="Sub 1", state="done")
        child2 = _make_child_issue("TASK-456.2", title="Sub 2", state="open")
        meta = {
            "TASK-456.1": {
                "oompah.backports": [{"branch": "release/1.0", "status": "merged"}]
            },
            "TASK-456.2": {
                "oompah.backports": [
                    {"branch": "release/1.0", "status": "waiting"},
                    {"branch": "release/2.0", "status": "waiting"},
                ]
            },
        }
        orch, tracker, project = _make_epic_orchestrator(
            children=[child1, child2], meta_by_id=meta
        )
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get(
                "/api/v1/issues/TASK-456/release-picks/matrix",
                params={"project_id": "proj-1"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["branches"] == ["release/1.0", "release/2.0"]
        assert len(data["rows"]) == 2
        rows_by_id = {r["identifier"]: r for r in data["rows"]}
        # child1 has no entry for release/2.0 → None
        assert rows_by_id["TASK-456.1"]["entries"]["release/2.0"] is None
        assert rows_by_id["TASK-456.1"]["entries"]["release/1.0"]["status"] == "merged"

    def test_returns_404_when_epic_not_found(self, client):
        # _find_tracker_for_issue returns (None, None, None) when all projects
        # have been searched and none found the issue.
        fake_project = _make_project("proj-1")
        tracker_no_issue = MagicMock()
        tracker_no_issue.fetch_issue_detail = MagicMock(return_value=None)
        orch = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=tracker_no_issue)
        orch.project_store.list_all = MagicMock(return_value=[fake_project])
        orch.project_store.get = MagicMock(return_value=fake_project)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get("/api/v1/issues/TASK-MISSING/release-picks/matrix")
        assert resp.status_code == 404

    def test_returns_503_on_unexpected_error(self, client):
        with patch.object(
            server_module, "_get_orchestrator", side_effect=RuntimeError("crash")
        ):
            resp = client.get("/api/v1/issues/TASK-456/release-picks/matrix")
        assert resp.status_code == 503

    def test_works_without_project_id(self, client):
        orch, tracker, project = _make_epic_orchestrator()
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get("/api/v1/issues/TASK-456/release-picks/matrix")
        assert resp.status_code == 200

    def test_row_includes_title_and_state(self, client):
        child = _make_child_issue("TASK-456.1", title="My child", state="done")
        meta = {"TASK-456.1": {"oompah.backports": "release/1.0"}}
        orch, tracker, project = _make_epic_orchestrator(
            children=[child], meta_by_id=meta
        )
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get(
                "/api/v1/issues/TASK-456/release-picks/matrix",
                params={"project_id": "proj-1"},
            )
        assert resp.status_code == 200
        row = resp.json()["rows"][0]
        assert row["title"] == "My child"
        assert row["state"] == "done"


# ---------------------------------------------------------------------------
# POST /api/v1/issues/{identifier}/release-picks/apply-all
# ---------------------------------------------------------------------------


class TestPostApplyReleasePicksToAllChildren:
    def test_returns_400_when_no_project_id(self, client):
        resp = client.post(
            "/api/v1/issues/TASK-456/release-picks/apply-all",
            json={"branches": ["release/1.0"]},
        )
        assert resp.status_code == 400
        assert "project_id" in resp.json()["error"]["message"]

    def test_returns_400_when_no_branches(self, client):
        orch, tracker, project = _make_epic_orchestrator()
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.post(
                "/api/v1/issues/TASK-456/release-picks/apply-all",
                json={"project_id": "proj-1"},
            )
        assert resp.status_code == 400
        assert "branches" in resp.json()["error"]["message"]

    def test_returns_400_when_branches_not_list(self, client):
        orch, tracker, project = _make_epic_orchestrator()
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.post(
                "/api/v1/issues/TASK-456/release-picks/apply-all",
                json={"project_id": "proj-1", "branches": "release/1.0"},
            )
        assert resp.status_code == 400

    def test_returns_400_on_invalid_json(self, client):
        resp = client.post(
            "/api/v1/issues/TASK-456/release-picks/apply-all",
            data="not-json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400

    def test_returns_200_with_matrix_result(self, client):
        child = _make_child_issue("TASK-456.1")
        orch, tracker, project = _make_epic_orchestrator(children=[child])
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.post(
                "/api/v1/issues/TASK-456/release-picks/apply-all",
                json={"project_id": "proj-1", "branches": ["release/1.0"]},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["epic_identifier"] == "TASK-456"
        assert "branches" in data
        assert "rows" in data

    def test_skip_children_accepted(self, client):
        child1 = _make_child_issue("TASK-456.1")
        child2 = _make_child_issue("TASK-456.2")
        orch, tracker, project = _make_epic_orchestrator(
            children=[child1, child2]
        )
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.post(
                "/api/v1/issues/TASK-456/release-picks/apply-all",
                json={
                    "project_id": "proj-1",
                    "branches": ["release/1.0"],
                    "skip_children": ["TASK-456.2"],
                },
            )
        assert resp.status_code == 200
        # Check that TASK-456.2 had its branch set to skipped
        calls = tracker.set_metadata_field.call_args_list
        child2_calls = [c for c in calls if c[0][0] == "TASK-456.2"]
        assert child2_calls, "Expected set_metadata_field call for skipped child"
        written = child2_calls[0][0][2]
        entry = written[0]
        if isinstance(entry, dict):
            assert entry["status"] == "skipped"

    def test_branch_validation_failure_returns_400(self, client):
        child = _make_child_issue("TASK-456.1")
        orch, tracker, project = _make_epic_orchestrator(children=[child])
        project.matches_branch = MagicMock(
            side_effect=lambda b: b.startswith("release/")
        )
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.post(
                "/api/v1/issues/TASK-456/release-picks/apply-all",
                json={"project_id": "proj-1", "branches": ["bad-branch"]},
            )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "validation"

    def test_returns_404_when_project_not_found(self, client):
        orch = MagicMock()
        orch._tracker_for_project = MagicMock(
            side_effect=Exception("Unknown project")
        )
        orch.project_store.get = MagicMock(return_value=None)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.post(
                "/api/v1/issues/TASK-456/release-picks/apply-all",
                json={"project_id": "nonexistent", "branches": ["release/1.0"]},
            )
        assert resp.status_code == 404

    def test_returns_400_when_skip_children_not_list(self, client):
        orch, tracker, project = _make_epic_orchestrator()
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.post(
                "/api/v1/issues/TASK-456/release-picks/apply-all",
                json={
                    "project_id": "proj-1",
                    "branches": ["release/1.0"],
                    "skip_children": "TASK-456.2",
                },
            )
        assert resp.status_code == 400
        assert "skip_children" in resp.json()["error"]["message"]

    def test_set_metadata_field_called_per_child(self, client):
        child1 = _make_child_issue("TASK-456.1")
        child2 = _make_child_issue("TASK-456.2")
        orch, tracker, project = _make_epic_orchestrator(
            children=[child1, child2]
        )
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.post(
                "/api/v1/issues/TASK-456/release-picks/apply-all",
                json={"project_id": "proj-1", "branches": ["release/1.0"]},
            )
        assert resp.status_code == 200
        assert tracker.set_metadata_field.call_count == 2
