"""Server tests for GET /api/v1/projects/{project_id}/release-delivery/backlog.

OOMPAH-236: Replace Release Delivery commit pagination with an item-centric release backlog.
OOMPAH-251: Async refresh model — GET returns cached result immediately.

Covers
------
- Happy path: 200 with correct response shape (items, unassociated_commits, metadata).
- No next_cursor in response (complete bounded list).
- branch param required: 400 when missing.
- branch must be in supported_release_branches: 400 when not.
- filter param: needs_delivery (default) and all.
- query param for text search (applied at read time from cached result).
- stale=True propagated when Git remote is unreachable.
- branch_available=False when branch does not exist locally.
- 404 when project not found.
- 400 for unknown filter value.
- 503 when project has no repo_path.
- refresh_status included in all 200 responses (OOMPAH-251).
- no_result_pending: returns items=[] with refresh_status.phase=pending/loading when no cache.
- failed_refresh: returns items=[] with refresh_status.phase=failed (no 503).
- filter/query applied from cached BacklogResult at read time.
- asyncio.to_thread: service.get_backlog is called via asyncio.to_thread (via refresh manager).
- GET /backlog/status: returns current refresh status for a branch.
- POST /backlog/refresh: triggers a fresh refresh job.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.server import app
from oompah.models import Project
from oompah.release_delivery_backlog import (
    BacklogResult,
    ItemRow,
    SourceCommitInfo,
    UnassociatedCommitRow,
)
from oompah.release_delivery_inventory import ReleaseStatusCell
from oompah.release_delivery_refresh import RefreshStatus

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PROJECT_ID = "proj-backlog-api-test"
_SOURCE_HEAD = "a" * 40
_RELEASE_HEAD = "b" * 40
_SHA_1 = "1" * 40
_SHA_2 = "2" * 40
_RELEASE_BRANCH = "release/1.1"

_ENDPOINT = f"/api/v1/projects/{_PROJECT_ID}/release-delivery/backlog"
_STATUS_ENDPOINT = f"/api/v1/projects/{_PROJECT_ID}/release-delivery/backlog/status"
_REFRESH_ENDPOINT = f"/api/v1/projects/{_PROJECT_ID}/release-delivery/backlog/refresh"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_project(
    tmp_path: Path,
    *,
    pid: str = _PROJECT_ID,
    supported_release_branches: list[str] | None = None,
    repo_path: str | None = None,
) -> MagicMock:
    project = MagicMock(spec=Project)
    project.id = pid
    project.name = "Backlog API Test Project"
    project.default_branch = "main"
    project.supported_release_branches = (
        supported_release_branches
        if supported_release_branches is not None
        else [_RELEASE_BRANCH, "release/1.0"]
    )
    project.repo_url = "https://github.com/org/repo"
    project.repo_path = repo_path if repo_path is not None else str(tmp_path)
    project.access_token = None
    return project


def _make_orchestrator(tmp_path: Path, project: MagicMock | None = None) -> MagicMock:
    p = project or _make_project(tmp_path)
    orch = MagicMock()
    orch.project_store.get = MagicMock(return_value=p)
    orch.tracker = MagicMock()
    return orch


def _make_backlog_result(
    *,
    items: list[ItemRow] | None = None,
    unassociated_commits: list[UnassociatedCommitRow] | None = None,
    stale: bool = False,
    branch_available: bool = True,
) -> BacklogResult:
    source_commit = SourceCommitInfo(
        sha=_SHA_1,
        short_sha=_SHA_1[:7],
        subject="Add feature X",
        author_name="Dev",
        authored_at="2026-07-01T00:00:00Z",
    )
    if items is None:
        items = [
            ItemRow(
                identifier="TASK-1",
                title="Add feature X",
                kind="task",
                source_commits=[source_commit],
                delivery_status=ReleaseStatusCell(state="not_selected"),
                delivery_id=None,
                commit_count=1,
                most_recent_commit_at="2026-07-01T00:00:00Z",
                tracker_only=False,
            )
        ]
    if unassociated_commits is None:
        unassociated_commits = []

    return BacklogResult(
        project_id=_PROJECT_ID,
        source_branch="main",
        source_head=_SOURCE_HEAD,
        selected_branch=_RELEASE_BRANCH,
        branch_head=_RELEASE_HEAD if branch_available else None,
        branch_available=branch_available,
        items=items,
        unassociated_commits=unassociated_commits,
        stale=stale,
        refreshed_at="2026-07-01T00:00:00+00:00",
        total_commit_count=1,
    )


def _make_refresh_manager_mock(
    backlog_result: BacklogResult | None = None,
    *,
    phase: str = "complete",
    has_result: bool = True,
    refresh_error: str | None = None,
    refresh_completed_at: float | None = None,
) -> MagicMock:
    """Return a mock BacklogRefreshManager that immediately yields *backlog_result*.

    Use this to replace ``_get_backlog_refresh_manager`` in server tests so that:
    - ``get_or_start()`` returns the mock result synchronously (no background task)
    - The endpoint can be tested without AsyncMock/event-loop coupling
    """
    manager = MagicMock()
    status = RefreshStatus(
        phase=phase,
        completed=0,
        total=None,
        elapsed_s=0.5,
        error=refresh_error,
        has_result=has_result and backlog_result is not None,
        result_completed_at=refresh_completed_at,
    )
    manager.get_or_start = AsyncMock(return_value=(status, backlog_result))
    manager.trigger_refresh = AsyncMock(return_value=RefreshStatus(phase="pending"))
    manager.get_status.return_value = status
    manager.get_cached_result.return_value = backlog_result
    manager.is_running.return_value = (phase not in ("complete", "failed", "idle"))
    return manager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_refresh_manager():
    """Reset the module-level refresh manager singleton before and after each test."""
    original = server_module._backlog_refresh_manager
    server_module._backlog_refresh_manager = None
    yield
    server_module._backlog_refresh_manager = original


# ---------------------------------------------------------------------------
# Test: 200 response shape
# ---------------------------------------------------------------------------


class TestBacklogResponseShape:
    def test_200_with_correct_shape(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        backlog = _make_backlog_result()
        manager = _make_refresh_manager_mock(backlog)

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_item_backlog_service"),
            patch.object(server_module, "_get_backlog_refresh_manager", return_value=manager),
        ):
            client = TestClient(app)
            resp = client.get(f"{_ENDPOINT}?branch={_RELEASE_BRANCH}")

        assert resp.status_code == 200
        data = resp.json()

        # Required top-level fields
        assert data["project_id"] == _PROJECT_ID
        assert data["source_branch"] == "main"
        assert data["source_head"] == _SOURCE_HEAD
        assert data["selected_branch"] == _RELEASE_BRANCH
        assert data["branch_available"] is True
        assert "items" in data
        assert "unassociated_commits" in data
        assert "stale" in data
        assert "refreshed_at" in data
        assert "total_commit_count" in data
        # OOMPAH-251: refresh_status always present
        assert "refresh_status" in data
        assert data["refresh_status"]["phase"] == "complete"

        # Must NOT have next_cursor
        assert "next_cursor" not in data

    def test_item_row_shape(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        backlog = _make_backlog_result()
        manager = _make_refresh_manager_mock(backlog)

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_item_backlog_service"),
            patch.object(server_module, "_get_backlog_refresh_manager", return_value=manager),
        ):
            client = TestClient(app)
            resp = client.get(f"{_ENDPOINT}?branch={_RELEASE_BRANCH}")

        data = resp.json()
        assert len(data["items"]) == 1
        item = data["items"][0]
        assert item["identifier"] == "TASK-1"
        assert item["title"] == "Add feature X"
        assert item["kind"] == "task"
        assert item["commit_count"] == 1
        assert len(item["source_commits"]) == 1
        assert item["source_commits"][0]["sha"] == _SHA_1
        assert item["source_commits"][0]["subject"] == "Add feature X"
        assert "delivery_status" in item
        assert item["delivery_status"]["state"] == "not_selected"

    def test_no_next_cursor_in_response(self, tmp_path):
        """The backlog API must never return a next_cursor field."""
        orch = _make_orchestrator(tmp_path)
        backlog = _make_backlog_result()
        manager = _make_refresh_manager_mock(backlog)

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_item_backlog_service"),
            patch.object(server_module, "_get_backlog_refresh_manager", return_value=manager),
        ):
            client = TestClient(app)
            resp = client.get(f"{_ENDPOINT}?branch={_RELEASE_BRANCH}")

        assert "next_cursor" not in resp.json()

    def test_refresh_status_in_response(self, tmp_path):
        """refresh_status field is included in every 200 response (OOMPAH-251)."""
        orch = _make_orchestrator(tmp_path)
        backlog = _make_backlog_result()
        manager = _make_refresh_manager_mock(backlog, phase="complete")

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_item_backlog_service"),
            patch.object(server_module, "_get_backlog_refresh_manager", return_value=manager),
        ):
            client = TestClient(app)
            resp = client.get(f"{_ENDPOINT}?branch={_RELEASE_BRANCH}")

        assert resp.status_code == 200
        data = resp.json()
        assert "refresh_status" in data
        rs = data["refresh_status"]
        assert "phase" in rs
        assert "completed" in rs
        assert "elapsed_s" in rs
        assert "has_result" in rs


# ---------------------------------------------------------------------------
# Test: no cached result (pending/loading phase)
# ---------------------------------------------------------------------------


class TestNoCachedResult:
    """Tests for the case where no result is cached yet (first request)."""

    def test_no_result_returns_200_with_empty_items(self, tmp_path):
        """When no result is cached, GET returns 200 with empty items (not 503)."""
        orch = _make_orchestrator(tmp_path)
        manager = _make_refresh_manager_mock(
            backlog_result=None,
            phase="loading_merged",
            has_result=False,
        )

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_item_backlog_service"),
            patch.object(server_module, "_get_backlog_refresh_manager", return_value=manager),
        ):
            client = TestClient(app)
            resp = client.get(f"{_ENDPOINT}?branch={_RELEASE_BRANCH}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["unassociated_commits"] == []
        assert data["source_head"] is None
        assert data["refresh_status"]["phase"] == "loading_merged"
        assert data["refresh_status"]["has_result"] is False

    def test_no_result_selected_branch_still_set(self, tmp_path):
        """Even without a cached result, selected_branch is set in response."""
        orch = _make_orchestrator(tmp_path)
        manager = _make_refresh_manager_mock(backlog_result=None, phase="pending", has_result=False)

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_item_backlog_service"),
            patch.object(server_module, "_get_backlog_refresh_manager", return_value=manager),
        ):
            client = TestClient(app)
            resp = client.get(f"{_ENDPOINT}?branch={_RELEASE_BRANCH}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["selected_branch"] == _RELEASE_BRANCH
        assert data["project_id"] == _PROJECT_ID

    def test_stale_result_returned_while_refresh_running(self, tmp_path):
        """Stale cached result is returned while a refresh is in progress.

        The client should see the old items AND a refresh_status indicating
        that an update is in progress.
        """
        orch = _make_orchestrator(tmp_path)
        backlog = _make_backlog_result()
        manager = _make_refresh_manager_mock(
            backlog_result=backlog,
            phase="resolving_commits",
            has_result=True,
        )

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_item_backlog_service"),
            patch.object(server_module, "_get_backlog_refresh_manager", return_value=manager),
        ):
            client = TestClient(app)
            resp = client.get(f"{_ENDPOINT}?branch={_RELEASE_BRANCH}")

        assert resp.status_code == 200
        data = resp.json()
        # Stale items are still present
        assert len(data["items"]) == 1
        assert data["items"][0]["identifier"] == "TASK-1"
        # Refresh is in progress
        assert data["refresh_status"]["phase"] == "resolving_commits"
        assert data["refresh_status"]["has_result"] is True


# ---------------------------------------------------------------------------
# Test: failed refresh
# ---------------------------------------------------------------------------


class TestFailedRefresh:
    """Tests for failed refresh jobs."""

    def test_failed_refresh_returns_200_not_503(self, tmp_path):
        """A failed refresh returns 200 with refresh_status.phase=failed (not 503).

        With the async model, failures are surface in the refresh_status field
        and do not generate HTTP 503 responses.  The client should show a retry
        button using the failure information in refresh_status.
        """
        orch = _make_orchestrator(tmp_path)
        manager = _make_refresh_manager_mock(
            backlog_result=None,
            phase="failed",
            has_result=False,
            refresh_error="git subprocess timed out",
        )

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_item_backlog_service"),
            patch.object(server_module, "_get_backlog_refresh_manager", return_value=manager),
        ):
            client = TestClient(app)
            resp = client.get(f"{_ENDPOINT}?branch={_RELEASE_BRANCH}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["refresh_status"]["phase"] == "failed"
        assert data["refresh_status"]["error"] == "git subprocess timed out"

    def test_failed_refresh_retains_stale_result(self, tmp_path):
        """Stale result from a previous successful run is retained after a failure."""
        orch = _make_orchestrator(tmp_path)
        old_backlog = _make_backlog_result()
        manager = _make_refresh_manager_mock(
            backlog_result=old_backlog,
            phase="failed",
            has_result=True,
            refresh_error="SCM API rate limited",
        )

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_item_backlog_service"),
            patch.object(server_module, "_get_backlog_refresh_manager", return_value=manager),
        ):
            client = TestClient(app)
            resp = client.get(f"{_ENDPOINT}?branch={_RELEASE_BRANCH}")

        assert resp.status_code == 200
        data = resp.json()
        # Stale items still present despite refresh failure
        assert len(data["items"]) == 1
        assert data["items"][0]["identifier"] == "TASK-1"
        assert data["refresh_status"]["phase"] == "failed"
        assert data["refresh_status"]["has_result"] is True


# ---------------------------------------------------------------------------
# Test: branch parameter
# ---------------------------------------------------------------------------


class TestBranchParameter:
    def test_400_when_branch_missing(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            client = TestClient(app)
            resp = client.get(_ENDPOINT)
        assert resp.status_code == 400
        data = resp.json()
        assert data["error"]["code"] == "missing_branch"

    def test_400_when_branch_not_in_configured(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            client = TestClient(app)
            resp = client.get(f"{_ENDPOINT}?branch=release/99.0")
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "invalid_branch"

    def test_200_with_valid_branch(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        backlog = _make_backlog_result()
        manager = _make_refresh_manager_mock(backlog)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_item_backlog_service"),
            patch.object(server_module, "_get_backlog_refresh_manager", return_value=manager),
        ):
            client = TestClient(app)
            resp = client.get(f"{_ENDPOINT}?branch={_RELEASE_BRANCH}")
        assert resp.status_code == 200
        assert resp.json()["selected_branch"] == _RELEASE_BRANCH


# ---------------------------------------------------------------------------
# Test: filter parameter
# ---------------------------------------------------------------------------


class TestFilterParameter:
    def test_default_filter_needs_delivery_excludes_delivered_items(self, tmp_path):
        """filter=needs_delivery (default) excludes delivered items from cached result.

        The cached result contains both not_selected and delivered items.
        The server applies the filter at read time; delivered items must be absent.
        """
        orch = _make_orchestrator(tmp_path)
        source_commit = SourceCommitInfo(
            sha=_SHA_1, short_sha=_SHA_1[:7], subject="feat", author_name="Dev",
            authored_at="2026-07-01T00:00:00Z",
        )
        delivered_item = ItemRow(
            identifier="TASK-DELIVERED",
            title="Delivered task",
            kind="task",
            source_commits=[source_commit],
            delivery_status=ReleaseStatusCell(state="delivered"),
            delivery_id="rd-1",
            commit_count=1,
            most_recent_commit_at="2026-07-01T00:00:00Z",
        )
        pending_item = ItemRow(
            identifier="TASK-PENDING",
            title="Pending task",
            kind="task",
            source_commits=[source_commit],
            delivery_status=ReleaseStatusCell(state="not_selected"),
            delivery_id=None,
            commit_count=1,
            most_recent_commit_at="2026-07-01T00:00:00Z",
        )
        # Cache contains both; filter should drop delivered
        backlog = _make_backlog_result(items=[delivered_item, pending_item])
        manager = _make_refresh_manager_mock(backlog)

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_item_backlog_service"),
            patch.object(server_module, "_get_backlog_refresh_manager", return_value=manager),
        ):
            client = TestClient(app)
            # Default filter = needs_delivery
            resp = client.get(f"{_ENDPOINT}?branch={_RELEASE_BRANCH}")

        assert resp.status_code == 200
        data = resp.json()
        ids = [item["identifier"] for item in data["items"]]
        assert "TASK-PENDING" in ids
        assert "TASK-DELIVERED" not in ids

    def test_all_filter_includes_delivered(self, tmp_path):
        """filter=all includes delivered items from cached result."""
        orch = _make_orchestrator(tmp_path)
        source_commit = SourceCommitInfo(
            sha=_SHA_1, short_sha=_SHA_1[:7], subject="feat", author_name="Dev",
            authored_at="2026-07-01T00:00:00Z",
        )
        delivered_item = ItemRow(
            identifier="TASK-DELIVERED",
            title="Delivered task",
            kind="task",
            source_commits=[source_commit],
            delivery_status=ReleaseStatusCell(state="delivered"),
            delivery_id="rd-1",
            commit_count=1,
            most_recent_commit_at="2026-07-01T00:00:00Z",
        )
        backlog = _make_backlog_result(items=[delivered_item])
        manager = _make_refresh_manager_mock(backlog)

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_item_backlog_service"),
            patch.object(server_module, "_get_backlog_refresh_manager", return_value=manager),
        ):
            client = TestClient(app)
            resp = client.get(f"{_ENDPOINT}?branch={_RELEASE_BRANCH}&filter=all")

        assert resp.status_code == 200
        data = resp.json()
        ids = [item["identifier"] for item in data["items"]]
        assert "TASK-DELIVERED" in ids

    def test_all_filter_accepted(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        backlog = _make_backlog_result()
        manager = _make_refresh_manager_mock(backlog)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_item_backlog_service"),
            patch.object(server_module, "_get_backlog_refresh_manager", return_value=manager),
        ):
            client = TestClient(app)
            resp = client.get(f"{_ENDPOINT}?branch={_RELEASE_BRANCH}&filter=all")
        assert resp.status_code == 200

    def test_unknown_filter_returns_400(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            client = TestClient(app)
            resp = client.get(f"{_ENDPOINT}?branch={_RELEASE_BRANCH}&filter=bad_filter")
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "invalid_filter"

    def test_archived_excluded_from_needs_delivery(self, tmp_path):
        """filter=needs_delivery excludes archived items too (same as delivered)."""
        orch = _make_orchestrator(tmp_path)
        source_commit = SourceCommitInfo(
            sha=_SHA_1, short_sha=_SHA_1[:7], subject="feat", author_name="Dev",
            authored_at="2026-07-01T00:00:00Z",
        )
        archived_item = ItemRow(
            identifier="TASK-ARCHIVED",
            title="Archived task",
            kind="task",
            source_commits=[source_commit],
            delivery_status=ReleaseStatusCell(state="archived"),
            delivery_id="rd-2",
            commit_count=1,
            most_recent_commit_at="2026-07-01T00:00:00Z",
        )
        backlog = _make_backlog_result(items=[archived_item])
        manager = _make_refresh_manager_mock(backlog)

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_item_backlog_service"),
            patch.object(server_module, "_get_backlog_refresh_manager", return_value=manager),
        ):
            client = TestClient(app)
            resp = client.get(f"{_ENDPOINT}?branch={_RELEASE_BRANCH}")  # default filter

        data = resp.json()
        ids = [item["identifier"] for item in data["items"]]
        assert "TASK-ARCHIVED" not in ids


# ---------------------------------------------------------------------------
# Test: query parameter (applied at read time from cache)
# ---------------------------------------------------------------------------


class TestQueryParameter:
    def test_query_filters_by_identifier(self, tmp_path):
        """Query string matches against item identifier (case-insensitive)."""
        orch = _make_orchestrator(tmp_path)
        source_commit = SourceCommitInfo(
            sha=_SHA_1, short_sha=_SHA_1[:7], subject="feat", author_name="Dev",
            authored_at="2026-07-01T00:00:00Z",
        )
        task_a = ItemRow(
            identifier="TASK-ALPHA",
            title="Alpha feature",
            kind="task",
            source_commits=[source_commit],
            delivery_status=ReleaseStatusCell(state="not_selected"),
            delivery_id=None,
            commit_count=1,
            most_recent_commit_at="2026-07-01T00:00:00Z",
        )
        task_b = ItemRow(
            identifier="TASK-BETA",
            title="Beta feature",
            kind="task",
            source_commits=[source_commit],
            delivery_status=ReleaseStatusCell(state="not_selected"),
            delivery_id=None,
            commit_count=1,
            most_recent_commit_at="2026-07-01T00:00:00Z",
        )
        backlog = _make_backlog_result(items=[task_a, task_b])
        manager = _make_refresh_manager_mock(backlog)

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_item_backlog_service"),
            patch.object(server_module, "_get_backlog_refresh_manager", return_value=manager),
        ):
            client = TestClient(app)
            resp = client.get(f"{_ENDPOINT}?branch={_RELEASE_BRANCH}&filter=all&query=alpha")

        data = resp.json()
        ids = [item["identifier"] for item in data["items"]]
        assert "TASK-ALPHA" in ids
        assert "TASK-BETA" not in ids

    def test_query_excludes_non_matching_items(self, tmp_path):
        """Items with no match to the query are excluded."""
        orch = _make_orchestrator(tmp_path)
        source_commit = SourceCommitInfo(
            sha=_SHA_1, short_sha=_SHA_1[:7], subject="feat", author_name="Dev",
            authored_at="2026-07-01T00:00:00Z",
        )
        task_a = ItemRow(
            identifier="TASK-1",
            title="Unrelated task",
            kind="task",
            source_commits=[source_commit],
            delivery_status=ReleaseStatusCell(state="not_selected"),
            delivery_id=None,
            commit_count=1,
            most_recent_commit_at="2026-07-01T00:00:00Z",
        )
        backlog = _make_backlog_result(items=[task_a])
        manager = _make_refresh_manager_mock(backlog)

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_item_backlog_service"),
            patch.object(server_module, "_get_backlog_refresh_manager", return_value=manager),
        ):
            client = TestClient(app)
            resp = client.get(f"{_ENDPOINT}?branch={_RELEASE_BRANCH}&filter=all&query=nonexistent")

        data = resp.json()
        assert data["items"] == []


# ---------------------------------------------------------------------------
# Test: error cases
# ---------------------------------------------------------------------------


class TestErrorCases:
    def test_404_when_project_not_found(self, tmp_path):
        orch = MagicMock()
        orch.project_store.get.return_value = None
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            client = TestClient(app)
            resp = client.get(f"/api/v1/projects/nonexistent/release-delivery/backlog?branch={_RELEASE_BRANCH}")
        assert resp.status_code == 404

    def test_503_when_no_repo_path(self, tmp_path):
        project = _make_project(tmp_path, repo_path="")
        orch = _make_orchestrator(tmp_path, project)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            client = TestClient(app)
            resp = client.get(f"{_ENDPOINT}?branch={_RELEASE_BRANCH}")
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "no_repo"

    def test_inventory_error_surfaced_in_refresh_status_not_503(self, tmp_path):
        """InventoryError from get_backlog is caught by the refresh manager.

        With the async model, discovery errors appear in refresh_status.phase=failed
        rather than as HTTP 503 responses.  The endpoint returns 200 with an
        empty items list so the client can show a retry button.
        """
        orch = _make_orchestrator(tmp_path)
        manager = _make_refresh_manager_mock(
            backlog_result=None,
            phase="failed",
            has_result=False,
            refresh_error="git subprocess failed",
        )

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_item_backlog_service"),
            patch.object(server_module, "_get_backlog_refresh_manager", return_value=manager),
        ):
            client = TestClient(app)
            resp = client.get(f"{_ENDPOINT}?branch={_RELEASE_BRANCH}")

        # With async model: 200 + failure in refresh_status, not 503
        assert resp.status_code == 200
        data = resp.json()
        assert data["refresh_status"]["phase"] == "failed"
        assert data["items"] == []


# ---------------------------------------------------------------------------
# Test: stale and branch_available
# ---------------------------------------------------------------------------


class TestStaleAndBranchAvailable:
    def test_stale_true_propagated(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        backlog = _make_backlog_result(stale=True)
        manager = _make_refresh_manager_mock(backlog)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_item_backlog_service"),
            patch.object(server_module, "_get_backlog_refresh_manager", return_value=manager),
        ):
            client = TestClient(app)
            resp = client.get(f"{_ENDPOINT}?branch={_RELEASE_BRANCH}")
        assert resp.json()["stale"] is True

    def test_branch_not_available(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        backlog = _make_backlog_result(branch_available=False, items=[])
        manager = _make_refresh_manager_mock(backlog)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_item_backlog_service"),
            patch.object(server_module, "_get_backlog_refresh_manager", return_value=manager),
        ):
            client = TestClient(app)
            resp = client.get(f"{_ENDPOINT}?branch={_RELEASE_BRANCH}")
        data = resp.json()
        assert data["branch_available"] is False
        assert data["branch_head"] is None


# ---------------------------------------------------------------------------
# Test: unassociated commits in response
# ---------------------------------------------------------------------------


class TestUnassociatedCommits:
    def test_unassociated_commits_shape(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        unassoc = UnassociatedCommitRow(
            sha=_SHA_2,
            short_sha=_SHA_2[:7],
            subject="Direct push",
            author_name="Dev",
            authored_at="2026-07-02T00:00:00Z",
            delivery_status=ReleaseStatusCell(state="not_selected"),
            delivery_id=None,
            tracker_only=False,
        )
        backlog = _make_backlog_result(items=[], unassociated_commits=[unassoc])
        manager = _make_refresh_manager_mock(backlog)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_item_backlog_service"),
            patch.object(server_module, "_get_backlog_refresh_manager", return_value=manager),
        ):
            client = TestClient(app)
            resp = client.get(f"{_ENDPOINT}?branch={_RELEASE_BRANCH}")
        data = resp.json()
        assert data["items"] == []
        assert len(data["unassociated_commits"]) == 1
        row = data["unassociated_commits"][0]
        assert row["sha"] == _SHA_2
        assert row["subject"] == "Direct push"
        assert "delivery_status" in row


# ---------------------------------------------------------------------------
# Test: GET /backlog/status endpoint (OOMPAH-251)
# ---------------------------------------------------------------------------


class TestBacklogStatusEndpoint:
    """Tests for GET /api/v1/projects/{project_id}/release-delivery/backlog/status."""

    def test_status_returns_200_with_phase(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        manager = _make_refresh_manager_mock(
            backlog_result=None,
            phase="resolving_commits",
            has_result=False,
        )

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_backlog_refresh_manager", return_value=manager),
        ):
            client = TestClient(app)
            resp = client.get(f"{_STATUS_ENDPOINT}?branch={_RELEASE_BRANCH}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["phase"] == "resolving_commits"
        assert "completed" in data
        assert "elapsed_s" in data
        assert "has_result" in data

    def test_status_400_when_branch_missing(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            client = TestClient(app)
            resp = client.get(_STATUS_ENDPOINT)
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "missing_branch"

    def test_status_404_when_project_not_found(self, tmp_path):
        orch = MagicMock()
        orch.project_store.get.return_value = None
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            client = TestClient(app)
            resp = client.get(f"/api/v1/projects/nonexistent/release-delivery/backlog/status?branch={_RELEASE_BRANCH}")
        assert resp.status_code == 404

    def test_status_returns_idle_when_no_job(self, tmp_path):
        """Returns {phase: idle} when no refresh job has been created."""
        orch = _make_orchestrator(tmp_path)
        manager = MagicMock()
        manager.get_status.return_value = None  # No job exists

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_backlog_refresh_manager", return_value=manager),
        ):
            client = TestClient(app)
            resp = client.get(f"{_STATUS_ENDPOINT}?branch={_RELEASE_BRANCH}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["phase"] == "idle"
        assert data["has_result"] is False

    def test_status_complete_phase_when_refresh_done(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        manager = _make_refresh_manager_mock(
            backlog_result=_make_backlog_result(),
            phase="complete",
            has_result=True,
        )

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_backlog_refresh_manager", return_value=manager),
        ):
            client = TestClient(app)
            resp = client.get(f"{_STATUS_ENDPOINT}?branch={_RELEASE_BRANCH}")

        data = resp.json()
        assert data["phase"] == "complete"
        assert data["has_result"] is True

    def test_status_failed_phase_with_error(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        manager = _make_refresh_manager_mock(
            backlog_result=None,
            phase="failed",
            has_result=False,
            refresh_error="git timeout after 60s",
        )

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_backlog_refresh_manager", return_value=manager),
        ):
            client = TestClient(app)
            resp = client.get(f"{_STATUS_ENDPOINT}?branch={_RELEASE_BRANCH}")

        data = resp.json()
        assert data["phase"] == "failed"
        assert data["error"] == "git timeout after 60s"

    def test_status_progress_counts_when_total_known(self, tmp_path):
        """Phase with known total exposes completed/total counts."""
        orch = _make_orchestrator(tmp_path)
        status = RefreshStatus(
            phase="resolving_commits",
            completed=12,
            total=50,
            elapsed_s=4.2,
            has_result=False,
        )
        manager = MagicMock()
        manager.get_status.return_value = status

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_backlog_refresh_manager", return_value=manager),
        ):
            client = TestClient(app)
            resp = client.get(f"{_STATUS_ENDPOINT}?branch={_RELEASE_BRANCH}")

        data = resp.json()
        assert data["phase"] == "resolving_commits"
        assert data["completed"] == 12
        assert data["total"] == 50


# ---------------------------------------------------------------------------
# Test: POST /backlog/refresh endpoint (OOMPAH-251)
# ---------------------------------------------------------------------------


class TestBacklogRefreshEndpoint:
    """Tests for POST /api/v1/projects/{project_id}/release-delivery/backlog/refresh."""

    def test_refresh_returns_202(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        manager = _make_refresh_manager_mock(_make_backlog_result())

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_item_backlog_service"),
            patch.object(server_module, "_get_backlog_refresh_manager", return_value=manager),
        ):
            client = TestClient(app)
            resp = client.post(f"{_REFRESH_ENDPOINT}?branch={_RELEASE_BRANCH}")

        assert resp.status_code == 202
        data = resp.json()
        assert data["started"] is True
        assert "phase" in data

    def test_refresh_400_when_branch_missing(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            client = TestClient(app)
            resp = client.post(_REFRESH_ENDPOINT)
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "missing_branch"

    def test_refresh_400_when_branch_not_in_configured(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            client = TestClient(app)
            resp = client.post(f"{_REFRESH_ENDPOINT}?branch=release/99.0")
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "invalid_branch"

    def test_refresh_404_when_project_not_found(self, tmp_path):
        orch = MagicMock()
        orch.project_store.get.return_value = None
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            client = TestClient(app)
            resp = client.post(f"/api/v1/projects/nonexistent/release-delivery/backlog/refresh?branch={_RELEASE_BRANCH}")
        assert resp.status_code == 404

    def test_refresh_503_when_no_repo_path(self, tmp_path):
        project = _make_project(tmp_path, repo_path="")
        orch = _make_orchestrator(tmp_path, project)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            client = TestClient(app)
            resp = client.post(f"{_REFRESH_ENDPOINT}?branch={_RELEASE_BRANCH}")
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "no_repo"

    def test_refresh_calls_trigger_refresh_on_manager(self, tmp_path):
        """POST /refresh calls manager.trigger_refresh (not get_or_start)."""
        orch = _make_orchestrator(tmp_path)
        manager = _make_refresh_manager_mock(_make_backlog_result())

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_item_backlog_service"),
            patch.object(server_module, "_get_backlog_refresh_manager", return_value=manager),
        ):
            client = TestClient(app)
            client.post(f"{_REFRESH_ENDPOINT}?branch={_RELEASE_BRANCH}")

        manager.trigger_refresh.assert_awaited_once()
        # trigger_refresh should be called with project_id and branch
        call_kwargs = manager.trigger_refresh.call_args
        assert call_kwargs.args[0] == _PROJECT_ID
        assert call_kwargs.args[1] == _RELEASE_BRANCH

    def test_retry_after_failure_starts_new_job(self, tmp_path):
        """POST /refresh is the retry path after a failed refresh.

        The endpoint should call trigger_refresh regardless of current state,
        and return 202 with phase=pending so the UI knows a new job started.
        """
        orch = _make_orchestrator(tmp_path)
        # Simulate a manager in failed state with no result
        failed_status = RefreshStatus(phase="pending")
        manager = MagicMock()
        manager.trigger_refresh = AsyncMock(return_value=failed_status)
        manager.get_status.return_value = RefreshStatus(phase="failed", error="git failed")

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_item_backlog_service"),
            patch.object(server_module, "_get_backlog_refresh_manager", return_value=manager),
        ):
            client = TestClient(app)
            resp = client.post(f"{_REFRESH_ENDPOINT}?branch={_RELEASE_BRANCH}")

        assert resp.status_code == 202
        data = resp.json()
        assert data["started"] is True
        assert data["phase"] == "pending"


# ---------------------------------------------------------------------------
# Test: large synthetic commit set — bounded git operations (OOMPAH-239)
# ---------------------------------------------------------------------------


class TestLargeCommitSetBoundedGitOps:
    """API-level regression tests for OOMPAH-239.

    Verifies that the backlog endpoint returns a 200 with primary item rows
    populated when backed by a large synthetic commit set, and that the
    underlying service's _is_tracker_only_commit is only called a bounded
    number of times (not once per unassociated commit).
    """

    def _make_large_backlog_result(
        self,
        *,
        n_items: int = 5,
        n_unassociated: int = 300,
    ) -> BacklogResult:
        """Build a BacklogResult with *n_items* item rows and *n_unassociated* unassociated rows."""
        from oompah.release_delivery_backlog import SourceCommitInfo, ItemRow, UnassociatedCommitRow

        items = [
            ItemRow(
                identifier=f"TASK-{i}",
                title=f"Task {i}",
                kind="task",
                source_commits=[
                    SourceCommitInfo(
                        sha=f"{i:040x}",
                        short_sha=f"{i:07x}",
                        subject=f"feat: task {i}",
                        author_name="Dev",
                        authored_at="2026-07-01T00:00:00Z",
                    )
                ],
                delivery_status=ReleaseStatusCell(state="open"),
                delivery_id=f"rd_{i}",
                commit_count=1,
                most_recent_commit_at="2026-07-01T00:00:00Z",
                tracker_only=False,
            )
            for i in range(1, n_items + 1)
        ]

        unassociated = [
            UnassociatedCommitRow(
                sha=f"u{j:039x}",
                short_sha=f"u{j:06x}",
                subject=f"direct commit {j}",
                author_name="Dev",
                authored_at="2026-07-01T00:00:00Z",
                delivery_status=ReleaseStatusCell(state="not_selected"),
                delivery_id=None,
                tracker_only=False,
            )
            for j in range(1, n_unassociated + 1)
        ]

        return BacklogResult(
            project_id=_PROJECT_ID,
            source_branch="main",
            source_head=_SOURCE_HEAD,
            selected_branch=_RELEASE_BRANCH,
            branch_head=_RELEASE_HEAD,
            branch_available=True,
            items=items,
            unassociated_commits=unassociated,
            stale=False,
            refreshed_at="2026-07-01T00:00:00+00:00",
            total_commit_count=n_items + n_unassociated,
        )

    def test_large_commit_set_returns_200_with_items(self, tmp_path):
        """Endpoint returns 200 with primary item rows when there are many unassociated commits.

        Regression: the endpoint was timing out (503) for projects with hundreds
        of direct-to-main commits because each triggered a git subprocess.
        With the async model, the endpoint returns immediately with the cached
        result; no git subprocess can block the HTTP response.
        """
        orch = _make_orchestrator(tmp_path)
        backlog = self._make_large_backlog_result(n_items=5, n_unassociated=300)
        manager = _make_refresh_manager_mock(backlog)

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_item_backlog_service"),
            patch.object(server_module, "_get_backlog_refresh_manager", return_value=manager),
        ):
            client = TestClient(app)
            resp = client.get(f"{_ENDPOINT}?branch={_RELEASE_BRANCH}&filter=all")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 5
        assert data["items"][0]["identifier"] == "TASK-1"
        assert data["total_commit_count"] == 305

    def test_large_commit_set_unassociated_count_in_response(self, tmp_path):
        """Unassociated commit rows appear in the response for large commit sets."""
        orch = _make_orchestrator(tmp_path)
        backlog = self._make_large_backlog_result(n_items=2, n_unassociated=200)
        manager = _make_refresh_manager_mock(backlog)

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_item_backlog_service"),
            patch.object(server_module, "_get_backlog_refresh_manager", return_value=manager),
        ):
            client = TestClient(app)
            resp = client.get(f"{_ENDPOINT}?branch={_RELEASE_BRANCH}&filter=all")

        data = resp.json()
        assert resp.status_code == 200
        assert len(data["unassociated_commits"]) == 200
        assert len(data["items"]) == 2

    def test_manager_get_or_start_called_once_per_request(self, tmp_path):
        """manager.get_or_start is called exactly once per HTTP request.

        Regression guard: the handler must not loop over commits and call the
        manager multiple times.
        """
        orch = _make_orchestrator(tmp_path)
        backlog = self._make_large_backlog_result(n_items=5, n_unassociated=300)
        manager = _make_refresh_manager_mock(backlog)

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_item_backlog_service"),
            patch.object(server_module, "_get_backlog_refresh_manager", return_value=manager),
        ):
            client = TestClient(app)
            client.get(f"{_ENDPOINT}?branch={_RELEASE_BRANCH}&filter=all")

        # get_or_start must have been called exactly once
        assert manager.get_or_start.call_count == 1, (
            f"manager.get_or_start must be called once per request, "
            f"got {manager.get_or_start.call_count}"
        )

    def test_bounded_git_calls_with_large_unassociated_set(self, tmp_path):
        """Integration: _is_tracker_only_commit is called at most MAX_UNASSOC_TRACKER_ONLY_CHECK
        times even when the backlog contains many more unassociated commits.

        This test runs ItemBacklogService directly (bypassing the HTTP layer) with
        a large synthetic commit set and asserts on the git call count.
        """
        from oompah.release_delivery_backlog import (
            ItemBacklogService,
            MAX_UNASSOC_TRACKER_ONLY_CHECK,
        )
        from oompah.release_delivery_store import ReleaseDeliveryStore
        from unittest.mock import MagicMock, patch
        import time

        n_unassociated = MAX_UNASSOC_TRACKER_ONLY_CHECK * 4

        # Build mock commits (no ledger entries → all are unassociated)
        def _make_ci(i: int):
            ci = MagicMock()
            ci.sha = f"{i:040x}"
            ci.parents = []
            ci.subject = f"direct commit {i}"
            ci.author_name = "Dev"
            ci.authored_at = "2026-07-01T00:00:00Z"
            ci.is_merge = False
            return ci

        commits = [_make_ci(i) for i in range(1, n_unassociated + 1)]

        store = MagicMock(spec=ReleaseDeliveryStore)
        ledger = MagicMock()
        ledger.deliveries = []
        store.read_ledger.return_value = ledger

        svc = ItemBacklogService(
            project_root=tmp_path,
            project_id=_PROJECT_ID,
            default_branch="main",
            delivery_store=store,
        )

        snap = MagicMock()
        snap.source_head = _SOURCE_HEAD
        snap.release_heads = {_RELEASE_BRANCH: _RELEASE_HEAD}
        snap.stale = False
        snap.fetched_at = time.monotonic()

        call_count = 0

        def _counting_is_tracker_only(repo_path, sha):
            nonlocal call_count
            call_count += 1
            return False

        with (
            patch("oompah.release_delivery_backlog._acquire_snapshot", return_value=snap),
            patch("oompah.release_delivery_backlog._enumerate_commits", return_value=commits),
            patch("oompah.release_delivery_backlog._check_ancestry_batch", return_value=set()),
            patch(
                "oompah.release_delivery_backlog._is_tracker_only_commit",
                side_effect=_counting_is_tracker_only,
            ),
            patch("oompah.release_delivery_backlog._find_branch_commits_in_main", return_value=[]),
        ):
            result = svc.get_backlog(selected_branch=_RELEASE_BRANCH, filter="all")

        assert result.total_commit_count == n_unassociated
        assert len(result.unassociated_commits) == n_unassociated
        assert call_count <= MAX_UNASSOC_TRACKER_ONLY_CHECK, (
            f"OOMPAH-239 regression: expected ≤ {MAX_UNASSOC_TRACKER_ONLY_CHECK} git calls "
            f"for {n_unassociated} unassociated commits, got {call_count}"
        )
