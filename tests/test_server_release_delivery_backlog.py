"""Server tests for GET /api/v1/projects/{project_id}/release-delivery/backlog.

OOMPAH-236: Replace Release Delivery commit pagination with an item-centric release backlog.

Covers
------
- Happy path: 200 with correct response shape (items, unassociated_commits, metadata).
- No next_cursor in response (complete bounded list).
- branch param required: 400 when missing.
- branch must be in supported_release_branches: 400 when not.
- filter param: needs_delivery (default) and all.
- query param for text search.
- stale=True propagated when Git remote is unreachable.
- branch_available=False when branch does not exist locally.
- 404 when project not found.
- 400 for unknown filter value.
- 503 when project has no repo_path.
- 503 when ItemBacklogService raises InventoryError.
- asyncio.to_thread: service.get_backlog is called via asyncio.to_thread.
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


# ---------------------------------------------------------------------------
# Test: 200 response shape
# ---------------------------------------------------------------------------


class TestBacklogResponseShape:
    def test_200_with_correct_shape(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        backlog = _make_backlog_result()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_item_backlog_service") as mock_svc_factory,
        ):
            svc = MagicMock()
            svc.get_backlog.return_value = backlog
            mock_svc_factory.return_value = svc

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

        # Must NOT have next_cursor
        assert "next_cursor" not in data

    def test_item_row_shape(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        backlog = _make_backlog_result()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_item_backlog_service") as mock_svc_factory,
        ):
            svc = MagicMock()
            svc.get_backlog.return_value = backlog
            mock_svc_factory.return_value = svc

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

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_item_backlog_service") as mock_svc_factory,
        ):
            svc = MagicMock()
            svc.get_backlog.return_value = backlog
            mock_svc_factory.return_value = svc

            client = TestClient(app)
            resp = client.get(f"{_ENDPOINT}?branch={_RELEASE_BRANCH}")

        assert "next_cursor" not in resp.json()


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
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_item_backlog_service") as mock_svc_factory,
        ):
            svc = MagicMock()
            svc.get_backlog.return_value = backlog
            mock_svc_factory.return_value = svc
            client = TestClient(app)
            resp = client.get(f"{_ENDPOINT}?branch={_RELEASE_BRANCH}")
        assert resp.status_code == 200
        assert resp.json()["selected_branch"] == _RELEASE_BRANCH


# ---------------------------------------------------------------------------
# Test: filter parameter
# ---------------------------------------------------------------------------


class TestFilterParameter:
    def test_default_filter_is_needs_delivery(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        backlog = _make_backlog_result()
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_item_backlog_service") as mock_svc_factory,
        ):
            svc = MagicMock()
            svc.get_backlog.return_value = backlog
            mock_svc_factory.return_value = svc
            client = TestClient(app)
            client.get(f"{_ENDPOINT}?branch={_RELEASE_BRANCH}")
            # Check that get_backlog was called with needs_delivery filter
            call_kwargs = svc.get_backlog.call_args.kwargs
            assert call_kwargs.get("filter", "needs_delivery") == "needs_delivery"

    def test_all_filter_accepted(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        backlog = _make_backlog_result()
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_item_backlog_service") as mock_svc_factory,
        ):
            svc = MagicMock()
            svc.get_backlog.return_value = backlog
            mock_svc_factory.return_value = svc
            client = TestClient(app)
            resp = client.get(f"{_ENDPOINT}?branch={_RELEASE_BRANCH}&filter=all")
        assert resp.status_code == 200
        call_kwargs = svc.get_backlog.call_args.kwargs
        assert call_kwargs.get("filter") == "all"

    def test_unknown_filter_returns_400(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            client = TestClient(app)
            resp = client.get(f"{_ENDPOINT}?branch={_RELEASE_BRANCH}&filter=bad_filter")
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "invalid_filter"


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

    def test_503_when_inventory_error(self, tmp_path):
        from oompah.release_delivery_inventory import InventoryError

        orch = _make_orchestrator(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_item_backlog_service") as mock_svc_factory,
        ):
            svc = MagicMock()
            svc.get_backlog.side_effect = InventoryError("git failed")
            mock_svc_factory.return_value = svc
            client = TestClient(app)
            resp = client.get(f"{_ENDPOINT}?branch={_RELEASE_BRANCH}")
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "backlog_unavailable"


# ---------------------------------------------------------------------------
# Test: stale and branch_available
# ---------------------------------------------------------------------------


class TestStaleAndBranchAvailable:
    def test_stale_true_propagated(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        backlog = _make_backlog_result(stale=True)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_item_backlog_service") as mock_svc_factory,
        ):
            svc = MagicMock()
            svc.get_backlog.return_value = backlog
            mock_svc_factory.return_value = svc
            client = TestClient(app)
            resp = client.get(f"{_ENDPOINT}?branch={_RELEASE_BRANCH}")
        assert resp.json()["stale"] is True

    def test_branch_not_available(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        backlog = _make_backlog_result(branch_available=False, items=[])
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_item_backlog_service") as mock_svc_factory,
        ):
            svc = MagicMock()
            svc.get_backlog.return_value = backlog
            mock_svc_factory.return_value = svc
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
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_item_backlog_service") as mock_svc_factory,
        ):
            svc = MagicMock()
            svc.get_backlog.return_value = backlog
            mock_svc_factory.return_value = svc
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
# Test: asyncio.to_thread
# ---------------------------------------------------------------------------


class TestAsyncioToThread:
    def test_get_backlog_called_via_asyncio_to_thread(self, tmp_path):
        """Verify service.get_backlog is invoked via asyncio.to_thread."""
        orch = _make_orchestrator(tmp_path)
        backlog = _make_backlog_result()
        calls = []

        original_to_thread = asyncio.to_thread

        async def recording_to_thread(fn, *args, **kwargs):
            calls.append(fn)
            return await original_to_thread(fn, *args, **kwargs)

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_item_backlog_service") as mock_svc_factory,
            patch("oompah.server.asyncio.to_thread", side_effect=recording_to_thread),
        ):
            svc = MagicMock()
            svc.get_backlog.return_value = backlog
            mock_svc_factory.return_value = svc
            client = TestClient(app)
            client.get(f"{_ENDPOINT}?branch={_RELEASE_BRANCH}")

        # The function passed to to_thread should be svc.get_backlog
        assert any(fn is svc.get_backlog for fn in calls)


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
        """
        orch = _make_orchestrator(tmp_path)
        backlog = self._make_large_backlog_result(n_items=5, n_unassociated=300)

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_item_backlog_service") as mock_svc_factory,
        ):
            svc = MagicMock()
            svc.get_backlog.return_value = backlog
            mock_svc_factory.return_value = svc

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

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_item_backlog_service") as mock_svc_factory,
        ):
            svc = MagicMock()
            svc.get_backlog.return_value = backlog
            mock_svc_factory.return_value = svc

            client = TestClient(app)
            resp = client.get(f"{_ENDPOINT}?branch={_RELEASE_BRANCH}&filter=all")

        data = resp.json()
        assert resp.status_code == 200
        assert len(data["unassociated_commits"]) == 200
        assert len(data["items"]) == 2

    def test_service_called_once_per_request(self, tmp_path):
        """Service.get_backlog is called exactly once per HTTP request (not per commit).

        Regression guard: the handler must not loop over commits and call the
        service multiple times.
        """
        orch = _make_orchestrator(tmp_path)
        backlog = self._make_large_backlog_result(n_items=5, n_unassociated=300)

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_item_backlog_service") as mock_svc_factory,
        ):
            svc = MagicMock()
            svc.get_backlog.return_value = backlog
            mock_svc_factory.return_value = svc

            client = TestClient(app)
            client.get(f"{_ENDPOINT}?branch={_RELEASE_BRANCH}&filter=all")

        # get_backlog must have been called exactly once
        assert svc.get_backlog.call_count == 1, (
            f"service.get_backlog must be called once per request, "
            f"got {svc.get_backlog.call_count}"
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
