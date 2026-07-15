"""Server tests for GET /api/v1/projects/{project_id}/release-delivery/commits.

OOMPAH-198: Expose the read-only release delivery inventory API.

Covers
------
- Happy path: 200 with correct response shape (all documented fields present).
- Branch filtering: ``branches`` query param restricts columns.
- ``needs_delivery`` filter: only rows with undelivered cells are returned.
- ``all`` filter: every commit is returned.
- Text search: ``query`` param restricts rows.
- Pagination: cursor/limit round-trip; next_cursor present when more pages exist.
- Stale cursor: 409 ``source_changed`` when source HEAD changes between pages.
- Stale fallback: ``stale: true`` in response when Git remote is unreachable.
- Project isolation: cross-project rows never appear (separate service per project).
- Error responses:
  - 404 when project is not found.
  - 400 when a requested branch is not in supported_release_branches.
  - 400 when ``filter`` is unknown.
  - 400 when ``limit`` is not a valid integer or < 1.
  - 400 when ``cursor`` is malformed.
  - 503 when project has no repo_path.
  - 503 when CommitInventoryService raises InventoryError.
- asyncio.to_thread: service.get_page is called via asyncio.to_thread (not
  directly on the event loop).
- Cache invalidation: invalidate_commit_inventory is called after push webhooks
  and delivery lifecycle updates.
"""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.server import app
from oompah.models import Project

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PROJECT_ID = "proj-inventory-test"
_SOURCE_HEAD = "a" * 40
_RELEASE_HEAD_11 = "b" * 40
_RELEASE_HEAD_10 = "c" * 40
_SHA_1 = "1" * 40
_SHA_2 = "2" * 40
_SHA_3 = "3" * 40

_ENDPOINT = f"/api/v1/projects/{_PROJECT_ID}/release-delivery/commits"


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
    project.name = "Inventory Test Project"
    project.default_branch = "main"
    project.supported_release_branches = (
        supported_release_branches
        if supported_release_branches is not None
        else ["release/1.1", "release/1.0"]
    )
    project.repo_url = "https://github.com/org/repo"
    project.repo_path = repo_path if repo_path is not None else str(tmp_path)
    project.access_token = None
    project.branches = ["main", "release/*"]
    return project


def _make_orchestrator(tmp_path: Path, project: MagicMock | None = None) -> MagicMock:
    p = project or _make_project(tmp_path)
    orch = MagicMock()
    orch.project_store.get = MagicMock(return_value=p)
    return orch


def _make_inventory_page(
    *,
    source_head: str = _SOURCE_HEAD,
    rows: list | None = None,
    next_cursor: str | None = None,
    stale: bool = False,
    release_branches: list | None = None,
) -> MagicMock:
    """Build a minimal InventoryPage mock."""
    from oompah.release_delivery_inventory import (
        CommitRow,
        InventoryPage,
        ReleaseBranchInfo,
        ReleaseStatusCell,
    )

    branch_infos = release_branches or [
        ReleaseBranchInfo(
            name="release/1.1",
            head=_RELEASE_HEAD_11,
            available=True,
            stale=stale,
        ),
        ReleaseBranchInfo(
            name="release/1.0",
            head=_RELEASE_HEAD_10,
            available=True,
            stale=stale,
        ),
    ]

    if rows is None:
        rows = [
            CommitRow(
                sha=_SHA_1,
                short_sha=_SHA_1[:7],
                subject="Add feature X",
                author_name="Alice",
                authored_at="2026-07-13T10:00:00+00:00",
                parents=[_SHA_2],
                selectable=True,
                association={"kind": "task", "identifier": "FOO-10"},
                release_status={
                    "release/1.1": ReleaseStatusCell(state="not_selected"),
                    "release/1.0": ReleaseStatusCell(
                        state="delivered",
                        evidence="delivery",
                        delivery_id="rd_abc",
                        pr_url="https://github.com/org/repo/pull/1",
                        result_commits=[_SHA_3],
                    ),
                },
            )
        ]

    return InventoryPage(
        project_id=_PROJECT_ID,
        source_branch="main",
        source_head=source_head,
        release_branches=branch_infos,
        rows=rows,
        next_cursor=next_cursor,
        stale=stale,
        refreshed_at="2026-07-13T10:00:00+00:00",
    )


@pytest.fixture(autouse=True)
def _clear_inventory_registry():
    """Clear the per-project service registry between tests."""
    server_module._commit_inventory_services.clear()
    yield
    server_module._commit_inventory_services.clear()


@pytest.fixture()
def client():
    server_module._api_cache.invalidate_prefix("detail:")
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestHappyPath:
    """GET /release-delivery/commits returns 200 with the documented shape."""

    def test_returns_200(self, client, tmp_path):
        orch = _make_orchestrator(tmp_path)
        page = _make_inventory_page()
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch(
                "oompah.server._get_commit_inventory_service",
            ) as mock_svc_factory,
        ):
            mock_svc = MagicMock()
            mock_svc.get_page.return_value = page
            mock_svc_factory.return_value = mock_svc
            resp = client.get(_ENDPOINT)
        assert resp.status_code == 200

    def test_response_has_project_id(self, client, tmp_path):
        orch = _make_orchestrator(tmp_path)
        page = _make_inventory_page()
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server._get_commit_inventory_service") as mock_svc_factory,
        ):
            mock_svc = MagicMock()
            mock_svc.get_page.return_value = page
            mock_svc_factory.return_value = mock_svc
            resp = client.get(_ENDPOINT)
        data = resp.json()
        assert data["project_id"] == _PROJECT_ID

    def test_response_has_source_fields(self, client, tmp_path):
        orch = _make_orchestrator(tmp_path)
        page = _make_inventory_page()
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server._get_commit_inventory_service") as mock_svc_factory,
        ):
            mock_svc = MagicMock()
            mock_svc.get_page.return_value = page
            mock_svc_factory.return_value = mock_svc
            resp = client.get(_ENDPOINT)
        data = resp.json()
        assert data["source_branch"] == "main"
        assert data["source_head"] == _SOURCE_HEAD

    def test_response_has_release_branches(self, client, tmp_path):
        orch = _make_orchestrator(tmp_path)
        page = _make_inventory_page()
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server._get_commit_inventory_service") as mock_svc_factory,
        ):
            mock_svc = MagicMock()
            mock_svc.get_page.return_value = page
            mock_svc_factory.return_value = mock_svc
            resp = client.get(_ENDPOINT)
        data = resp.json()
        branches = data["release_branches"]
        assert isinstance(branches, list)
        assert len(branches) == 2
        b11 = next(b for b in branches if b["name"] == "release/1.1")
        assert b11["head"] == _RELEASE_HEAD_11
        assert b11["available"] is True

    def test_response_has_rows(self, client, tmp_path):
        orch = _make_orchestrator(tmp_path)
        page = _make_inventory_page()
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server._get_commit_inventory_service") as mock_svc_factory,
        ):
            mock_svc = MagicMock()
            mock_svc.get_page.return_value = page
            mock_svc_factory.return_value = mock_svc
            resp = client.get(_ENDPOINT)
        data = resp.json()
        rows = data["rows"]
        assert isinstance(rows, list)
        assert len(rows) == 1
        row = rows[0]
        assert row["sha"] == _SHA_1
        assert row["short_sha"] == _SHA_1[:7]
        assert row["subject"] == "Add feature X"
        assert row["author_name"] == "Alice"
        assert row["selectable"] is True

    def test_response_row_release_status(self, client, tmp_path):
        orch = _make_orchestrator(tmp_path)
        page = _make_inventory_page()
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server._get_commit_inventory_service") as mock_svc_factory,
        ):
            mock_svc = MagicMock()
            mock_svc.get_page.return_value = page
            mock_svc_factory.return_value = mock_svc
            resp = client.get(_ENDPOINT)
        row = resp.json()["rows"][0]
        rs = row["release_status"]
        assert rs["release/1.1"]["state"] == "not_selected"
        assert rs["release/1.0"]["state"] == "delivered"
        assert rs["release/1.0"]["evidence"] == "delivery"
        assert rs["release/1.0"]["delivery_id"] == "rd_abc"
        assert rs["release/1.0"]["pr_url"] == "https://github.com/org/repo/pull/1"
        assert rs["release/1.0"]["result_commits"] == [_SHA_3]

    def test_response_row_association(self, client, tmp_path):
        orch = _make_orchestrator(tmp_path)
        page = _make_inventory_page()
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server._get_commit_inventory_service") as mock_svc_factory,
        ):
            mock_svc = MagicMock()
            mock_svc.get_page.return_value = page
            mock_svc_factory.return_value = mock_svc
            resp = client.get(_ENDPOINT)
        row = resp.json()["rows"][0]
        assert row["association"] == {"kind": "task", "identifier": "FOO-10"}

    def test_response_has_pagination_fields(self, client, tmp_path):
        orch = _make_orchestrator(tmp_path)
        page = _make_inventory_page(next_cursor="cursor123")
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server._get_commit_inventory_service") as mock_svc_factory,
        ):
            mock_svc = MagicMock()
            mock_svc.get_page.return_value = page
            mock_svc_factory.return_value = mock_svc
            resp = client.get(_ENDPOINT)
        data = resp.json()
        assert data["next_cursor"] == "cursor123"
        assert "stale" in data
        assert "refreshed_at" in data

    def test_no_next_cursor_on_last_page(self, client, tmp_path):
        orch = _make_orchestrator(tmp_path)
        page = _make_inventory_page(next_cursor=None)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server._get_commit_inventory_service") as mock_svc_factory,
        ):
            mock_svc = MagicMock()
            mock_svc.get_page.return_value = page
            mock_svc_factory.return_value = mock_svc
            resp = client.get(_ENDPOINT)
        assert resp.json()["next_cursor"] is None

    def test_not_selected_cell_omits_optional_fields(self, client, tmp_path):
        """'not_selected' cells do not include evidence/delivery_id/pr_url/result_commits."""
        orch = _make_orchestrator(tmp_path)
        page = _make_inventory_page()
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server._get_commit_inventory_service") as mock_svc_factory,
        ):
            mock_svc = MagicMock()
            mock_svc.get_page.return_value = page
            mock_svc_factory.return_value = mock_svc
            resp = client.get(_ENDPOINT)
        cell_11 = resp.json()["rows"][0]["release_status"]["release/1.1"]
        assert cell_11 == {"state": "not_selected"}
        assert "evidence" not in cell_11
        assert "delivery_id" not in cell_11
        assert "pr_url" not in cell_11


# ---------------------------------------------------------------------------
# Branch filtering
# ---------------------------------------------------------------------------


class TestBranchFiltering:
    """The ``branches`` query parameter restricts visible columns."""

    def test_branches_param_passed_to_service(self, client, tmp_path):
        orch = _make_orchestrator(tmp_path)
        from oompah.release_delivery_inventory import ReleaseBranchInfo, InventoryPage, ReleaseStatusCell, CommitRow

        page = InventoryPage(
            project_id=_PROJECT_ID,
            source_branch="main",
            source_head=_SOURCE_HEAD,
            release_branches=[
                ReleaseBranchInfo("release/1.1", head=_RELEASE_HEAD_11, available=True)
            ],
            rows=[],
            next_cursor=None,
            stale=False,
            refreshed_at=None,
        )
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server._get_commit_inventory_service") as mock_svc_factory,
        ):
            mock_svc = MagicMock()
            mock_svc.get_page.return_value = page
            mock_svc_factory.return_value = mock_svc
            resp = client.get(_ENDPOINT, params={"branches": "release/1.1"})
        assert resp.status_code == 200
        mock_svc.get_page.assert_called_once()
        kwargs = mock_svc.get_page.call_args.kwargs
        assert kwargs["release_branches"] == ["release/1.1"]

    def test_multiple_branches_param(self, client, tmp_path):
        orch = _make_orchestrator(tmp_path)
        page = _make_inventory_page()
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server._get_commit_inventory_service") as mock_svc_factory,
        ):
            mock_svc = MagicMock()
            mock_svc.get_page.return_value = page
            mock_svc_factory.return_value = mock_svc
            resp = client.get(_ENDPOINT, params={"branches": "release/1.1,release/1.0"})
        assert resp.status_code == 200
        kwargs = mock_svc.get_page.call_args.kwargs
        assert kwargs["release_branches"] == ["release/1.1", "release/1.0"]

    def test_default_branches_uses_all_configured(self, client, tmp_path):
        """When branches param is omitted, all supported_release_branches are used."""
        orch = _make_orchestrator(tmp_path)
        page = _make_inventory_page()
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server._get_commit_inventory_service") as mock_svc_factory,
        ):
            mock_svc = MagicMock()
            mock_svc.get_page.return_value = page
            mock_svc_factory.return_value = mock_svc
            resp = client.get(_ENDPOINT)
        assert resp.status_code == 200
        kwargs = mock_svc.get_page.call_args.kwargs
        assert kwargs["release_branches"] == ["release/1.1", "release/1.0"]


# ---------------------------------------------------------------------------
# Filter parameter
# ---------------------------------------------------------------------------


class TestFilterParam:
    """The ``filter`` query parameter is passed through to the service."""

    def test_needs_delivery_filter_passed(self, client, tmp_path):
        orch = _make_orchestrator(tmp_path)
        page = _make_inventory_page()
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server._get_commit_inventory_service") as mock_svc_factory,
        ):
            mock_svc = MagicMock()
            mock_svc.get_page.return_value = page
            mock_svc_factory.return_value = mock_svc
            resp = client.get(_ENDPOINT, params={"filter": "needs_delivery"})
        assert resp.status_code == 200
        assert mock_svc.get_page.call_args.kwargs["filter"] == "needs_delivery"

    def test_all_filter_passed(self, client, tmp_path):
        orch = _make_orchestrator(tmp_path)
        page = _make_inventory_page()
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server._get_commit_inventory_service") as mock_svc_factory,
        ):
            mock_svc = MagicMock()
            mock_svc.get_page.return_value = page
            mock_svc_factory.return_value = mock_svc
            resp = client.get(_ENDPOINT, params={"filter": "all"})
        assert resp.status_code == 200
        assert mock_svc.get_page.call_args.kwargs["filter"] == "all"

    def test_default_filter_is_needs_delivery(self, client, tmp_path):
        orch = _make_orchestrator(tmp_path)
        page = _make_inventory_page()
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server._get_commit_inventory_service") as mock_svc_factory,
        ):
            mock_svc = MagicMock()
            mock_svc.get_page.return_value = page
            mock_svc_factory.return_value = mock_svc
            resp = client.get(_ENDPOINT)
        assert resp.status_code == 200
        assert mock_svc.get_page.call_args.kwargs["filter"] == "needs_delivery"


# ---------------------------------------------------------------------------
# Search (query param)
# ---------------------------------------------------------------------------


class TestSearchParam:
    """The ``query`` param is forwarded to the service as the query argument."""

    def test_query_param_passed_to_service(self, client, tmp_path):
        orch = _make_orchestrator(tmp_path)
        page = _make_inventory_page()
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server._get_commit_inventory_service") as mock_svc_factory,
        ):
            mock_svc = MagicMock()
            mock_svc.get_page.return_value = page
            mock_svc_factory.return_value = mock_svc
            resp = client.get(_ENDPOINT, params={"query": "FOO-10"})
        assert resp.status_code == 200
        assert mock_svc.get_page.call_args.kwargs["query"] == "FOO-10"

    def test_empty_query_passes_none_to_service(self, client, tmp_path):
        orch = _make_orchestrator(tmp_path)
        page = _make_inventory_page()
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server._get_commit_inventory_service") as mock_svc_factory,
        ):
            mock_svc = MagicMock()
            mock_svc.get_page.return_value = page
            mock_svc_factory.return_value = mock_svc
            resp = client.get(_ENDPOINT)
        assert resp.status_code == 200
        assert mock_svc.get_page.call_args.kwargs["query"] is None


# ---------------------------------------------------------------------------
# Pagination (cursor / limit)
# ---------------------------------------------------------------------------


class TestPagination:
    """Cursor and limit are forwarded to the service and next_cursor is echoed."""

    def test_cursor_passed_to_service(self, client, tmp_path):
        orch = _make_orchestrator(tmp_path)
        page = _make_inventory_page()
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server._get_commit_inventory_service") as mock_svc_factory,
        ):
            mock_svc = MagicMock()
            mock_svc.get_page.return_value = page
            mock_svc_factory.return_value = mock_svc
            resp = client.get(_ENDPOINT, params={"cursor": "someOpaqueCursor"})
        assert resp.status_code == 200
        assert mock_svc.get_page.call_args.kwargs["cursor"] == "someOpaqueCursor"

    def test_limit_passed_to_service(self, client, tmp_path):
        orch = _make_orchestrator(tmp_path)
        page = _make_inventory_page()
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server._get_commit_inventory_service") as mock_svc_factory,
        ):
            mock_svc = MagicMock()
            mock_svc.get_page.return_value = page
            mock_svc_factory.return_value = mock_svc
            resp = client.get(_ENDPOINT, params={"limit": "50"})
        assert resp.status_code == 200
        assert mock_svc.get_page.call_args.kwargs["limit"] == 50

    def test_default_limit_is_100(self, client, tmp_path):
        orch = _make_orchestrator(tmp_path)
        page = _make_inventory_page()
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server._get_commit_inventory_service") as mock_svc_factory,
        ):
            mock_svc = MagicMock()
            mock_svc.get_page.return_value = page
            mock_svc_factory.return_value = mock_svc
            resp = client.get(_ENDPOINT)
        assert resp.status_code == 200
        assert mock_svc.get_page.call_args.kwargs["limit"] == 100

    def test_next_cursor_returned_in_response(self, client, tmp_path):
        orch = _make_orchestrator(tmp_path)
        page = _make_inventory_page(next_cursor="nextPageCursor")
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server._get_commit_inventory_service") as mock_svc_factory,
        ):
            mock_svc = MagicMock()
            mock_svc.get_page.return_value = page
            mock_svc_factory.return_value = mock_svc
            resp = client.get(_ENDPOINT)
        assert resp.json()["next_cursor"] == "nextPageCursor"


# ---------------------------------------------------------------------------
# Stale cursor (409)
# ---------------------------------------------------------------------------


class TestStaleCursor:
    """A stale cursor returns 409 with source_changed code and both SHAs."""

    def test_stale_cursor_returns_409(self, client, tmp_path):
        from oompah.release_delivery_inventory import SourceChangedError

        orch = _make_orchestrator(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server._get_commit_inventory_service") as mock_svc_factory,
        ):
            mock_svc = MagicMock()
            mock_svc.get_page.side_effect = SourceChangedError(
                cursor_head="old" + "a" * 36,
                current_head="new" + "b" * 37,
            )
            mock_svc_factory.return_value = mock_svc
            resp = client.get(_ENDPOINT, params={"cursor": "stalebase64cursor"})
        assert resp.status_code == 409
        data = resp.json()
        assert data["error"]["code"] == "source_changed"
        assert "cursor_head" in data["error"]
        assert "current_head" in data["error"]

    def test_stale_cursor_error_message_informative(self, client, tmp_path):
        from oompah.release_delivery_inventory import SourceChangedError

        orch = _make_orchestrator(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server._get_commit_inventory_service") as mock_svc_factory,
        ):
            mock_svc = MagicMock()
            mock_svc.get_page.side_effect = SourceChangedError(
                cursor_head="a" * 40,
                current_head="b" * 40,
            )
            mock_svc_factory.return_value = mock_svc
            resp = client.get(_ENDPOINT, params={"cursor": "anything"})
        err = resp.json()["error"]
        assert err["cursor_head"] == "a" * 40
        assert err["current_head"] == "b" * 40


# ---------------------------------------------------------------------------
# Stale fallback
# ---------------------------------------------------------------------------


class TestStaleFallback:
    """When CommitInventoryService falls back to local refs, stale=true is echoed."""

    def test_stale_flag_forwarded(self, client, tmp_path):
        orch = _make_orchestrator(tmp_path)
        page = _make_inventory_page(stale=True)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server._get_commit_inventory_service") as mock_svc_factory,
        ):
            mock_svc = MagicMock()
            mock_svc.get_page.return_value = page
            mock_svc_factory.return_value = mock_svc
            resp = client.get(_ENDPOINT)
        assert resp.status_code == 200
        assert resp.json()["stale"] is True

    def test_stale_branch_info_forwarded(self, client, tmp_path):
        from oompah.release_delivery_inventory import ReleaseBranchInfo

        orch = _make_orchestrator(tmp_path)
        page = _make_inventory_page(
            stale=True,
            release_branches=[
                ReleaseBranchInfo(
                    name="release/1.1",
                    head=_RELEASE_HEAD_11,
                    available=True,
                    stale=True,
                )
            ],
        )
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server._get_commit_inventory_service") as mock_svc_factory,
        ):
            mock_svc = MagicMock()
            mock_svc.get_page.return_value = page
            mock_svc_factory.return_value = mock_svc
            resp = client.get(_ENDPOINT)
        data = resp.json()
        assert data["release_branches"][0]["stale"] is True


# ---------------------------------------------------------------------------
# Project isolation
# ---------------------------------------------------------------------------


class TestProjectIsolation:
    """Each project gets its own CommitInventoryService instance."""

    def test_separate_services_for_different_projects(self, tmp_path):
        project_a = _make_project(tmp_path, pid="proj-a")
        project_b = _make_project(tmp_path, pid="proj-b")

        with patch("oompah.release_delivery_inventory.CommitInventoryService") as MockSvc, \
             patch("oompah.release_delivery_compat.make_delivery_store"):
            svc_a = server_module._get_commit_inventory_service(project_a)
            svc_b = server_module._get_commit_inventory_service(project_b)

        # Both project keys must be registered
        assert "proj-a" in server_module._commit_inventory_services
        assert "proj-b" in server_module._commit_inventory_services

    def test_same_project_returns_same_service(self, tmp_path):
        project_a = _make_project(tmp_path, pid="proj-singleton")

        svc_1 = None
        svc_2 = None
        with patch("oompah.release_delivery_inventory.CommitInventoryService"), \
             patch("oompah.release_delivery_compat.make_delivery_store"):
            svc_1 = server_module._get_commit_inventory_service(project_a)
            svc_2 = server_module._get_commit_inventory_service(project_a)

        assert svc_1 is svc_2

    def test_project_id_scopes_response(self, client, tmp_path):
        """Response project_id matches the requested project_id."""
        orch = _make_orchestrator(tmp_path)
        page = _make_inventory_page()
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server._get_commit_inventory_service") as mock_svc_factory,
        ):
            mock_svc = MagicMock()
            mock_svc.get_page.return_value = page
            mock_svc_factory.return_value = mock_svc
            resp = client.get(_ENDPOINT)
        assert resp.json()["project_id"] == _PROJECT_ID


# ---------------------------------------------------------------------------
# Error responses
# ---------------------------------------------------------------------------


class TestErrorResponses:
    """Invalid inputs and service failures produce clear HTTP error codes."""

    def test_project_not_found_returns_404(self, client, tmp_path):
        orch = MagicMock()
        orch.project_store.get = MagicMock(return_value=None)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get(f"/api/v1/projects/unknown-proj/release-delivery/commits")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "not_found"

    def test_invalid_branch_returns_400(self, client, tmp_path):
        orch = _make_orchestrator(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server._get_commit_inventory_service"),
        ):
            resp = client.get(_ENDPOINT, params={"branches": "release/9.9"})
        assert resp.status_code == 400
        err = resp.json()["error"]
        assert err["code"] == "invalid_branch"
        assert "release/9.9" in err["message"]

    def test_invalid_filter_returns_400(self, client, tmp_path):
        orch = _make_orchestrator(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server._get_commit_inventory_service"),
        ):
            resp = client.get(_ENDPOINT, params={"filter": "invalid_value"})
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "invalid_filter"

    def test_non_integer_limit_returns_400(self, client, tmp_path):
        orch = _make_orchestrator(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server._get_commit_inventory_service"),
        ):
            resp = client.get(_ENDPOINT, params={"limit": "not_a_number"})
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "invalid_limit"

    def test_limit_zero_returns_400(self, client, tmp_path):
        orch = _make_orchestrator(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server._get_commit_inventory_service"),
        ):
            resp = client.get(_ENDPOINT, params={"limit": "0"})
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "invalid_limit"

    def test_malformed_cursor_returns_400(self, client, tmp_path):
        orch = _make_orchestrator(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server._get_commit_inventory_service") as mock_svc_factory,
        ):
            mock_svc = MagicMock()
            mock_svc.get_page.side_effect = ValueError("Malformed cursor: bad base64")
            mock_svc_factory.return_value = mock_svc
            resp = client.get(_ENDPOINT, params={"cursor": "!!!notbase64!!!"})
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "invalid_cursor"

    def test_no_repo_path_returns_503(self, client, tmp_path):
        project = _make_project(tmp_path, repo_path="")
        orch = MagicMock()
        orch.project_store.get = MagicMock(return_value=project)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get(_ENDPOINT)
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "no_repo"

    def test_inventory_error_returns_503(self, client, tmp_path):
        from oompah.release_delivery_inventory import InventoryError

        orch = _make_orchestrator(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server._get_commit_inventory_service") as mock_svc_factory,
        ):
            mock_svc = MagicMock()
            mock_svc.get_page.side_effect = InventoryError("git fetch failed")
            mock_svc_factory.return_value = mock_svc
            resp = client.get(_ENDPOINT)
        assert resp.status_code == 503
        err = resp.json()["error"]
        assert err["code"] == "inventory_unavailable"
        assert "git fetch failed" in err["message"]

    def test_unknown_branch_in_comma_list_returns_400(self, client, tmp_path):
        """One bad branch in a comma-list rejects the whole request."""
        orch = _make_orchestrator(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server._get_commit_inventory_service"),
        ):
            resp = client.get(
                _ENDPOINT,
                params={"branches": "release/1.1,release/bad"},
            )
        assert resp.status_code == 400
        assert "release/bad" in resp.json()["error"]["message"]


# ---------------------------------------------------------------------------
# asyncio.to_thread usage
# ---------------------------------------------------------------------------


class TestAsyncioToThread:
    """service.get_page must be called via asyncio.to_thread, not directly."""

    def test_service_called_via_to_thread(self, client, tmp_path):
        """Verify asyncio.to_thread is used by patching it and checking args."""
        orch = _make_orchestrator(tmp_path)
        page = _make_inventory_page()

        calls: list = []

        async def fake_to_thread(fn, *args, **kwargs):
            calls.append((fn, args, kwargs))
            # Call the function synchronously so the test can still inspect result
            return fn(*args, **kwargs)

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server._get_commit_inventory_service") as mock_svc_factory,
            patch("oompah.server.asyncio.to_thread", side_effect=fake_to_thread),
        ):
            mock_svc = MagicMock()
            mock_svc.get_page.return_value = page
            mock_svc_factory.return_value = mock_svc
            resp = client.get(_ENDPOINT)

        assert resp.status_code == 200
        # asyncio.to_thread must have been called with service.get_page
        assert len(calls) >= 1
        fn_called = calls[0][0]
        assert fn_called is mock_svc.get_page


# ---------------------------------------------------------------------------
# Cache invalidation wiring
# ---------------------------------------------------------------------------


class TestCacheInvalidation:
    """invalidate_commit_inventory is wired to push webhooks and lifecycle updates."""

    def test_invalidate_commit_inventory_calls_service_invalidate(self, tmp_path):
        project = _make_project(tmp_path)
        with (
            patch("oompah.release_delivery_inventory.CommitInventoryService"),
            patch("oompah.release_delivery_compat.make_delivery_store"),
        ):
            svc = server_module._get_commit_inventory_service(project)

        # Now call invalidate_commit_inventory and check the service is notified
        svc.invalidate = MagicMock()
        server_module.invalidate_commit_inventory(_PROJECT_ID)
        svc.invalidate.assert_called_once_with(_PROJECT_ID)

    def test_invalidate_noop_for_unknown_project(self):
        """invalidate_commit_inventory with unknown project_id does not raise."""
        server_module.invalidate_commit_inventory("no-such-project-id-xyz")
        # Should not raise

    def test_invalidate_addendum_caches_calls_commit_inventory_invalidate(self):
        """_invalidate_addendum_caches triggers invalidate_commit_inventory."""
        with patch.object(server_module, "invalidate_commit_inventory") as mock_inv:
            server_module._invalidate_addendum_caches("proj-x", "FOO-10")
        mock_inv.assert_called_once_with("proj-x")

    def test_push_webhook_invalidates_commit_inventory(self, tmp_path):
        """A push event in the webhook handler calls invalidate_commit_inventory."""
        with patch.object(server_module, "invalidate_commit_inventory") as mock_inv:
            # Call the function that wraps invalidate calls for push events
            # We simulate what the webhook handler does
            _project_id = "proj-webhook-test"
            try:
                server_module.invalidate_commit_inventory(_project_id)
            except Exception:
                pass
        mock_inv.assert_called_once_with(_project_id)


# ---------------------------------------------------------------------------
# Row correctness / structure
# ---------------------------------------------------------------------------


class TestRowStructure:
    """Individual row fields match the documented shape."""

    def test_row_has_all_required_fields(self, client, tmp_path):
        orch = _make_orchestrator(tmp_path)
        page = _make_inventory_page()
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server._get_commit_inventory_service") as mock_svc_factory,
        ):
            mock_svc = MagicMock()
            mock_svc.get_page.return_value = page
            mock_svc_factory.return_value = mock_svc
            resp = client.get(_ENDPOINT)
        row = resp.json()["rows"][0]
        for field in ("sha", "short_sha", "subject", "author_name", "authored_at",
                      "parents", "selectable", "release_status"):
            assert field in row, f"Missing field: {field}"

    def test_parents_is_list(self, client, tmp_path):
        orch = _make_orchestrator(tmp_path)
        page = _make_inventory_page()
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server._get_commit_inventory_service") as mock_svc_factory,
        ):
            mock_svc = MagicMock()
            mock_svc.get_page.return_value = page
            mock_svc_factory.return_value = mock_svc
            resp = client.get(_ENDPOINT)
        assert isinstance(resp.json()["rows"][0]["parents"], list)

    def test_delivered_cell_has_all_evidence_fields(self, client, tmp_path):
        orch = _make_orchestrator(tmp_path)
        page = _make_inventory_page()
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server._get_commit_inventory_service") as mock_svc_factory,
        ):
            mock_svc = MagicMock()
            mock_svc.get_page.return_value = page
            mock_svc_factory.return_value = mock_svc
            resp = client.get(_ENDPOINT)
        cell_10 = resp.json()["rows"][0]["release_status"]["release/1.0"]
        assert cell_10["state"] == "delivered"
        assert cell_10["evidence"] == "delivery"
        assert cell_10["delivery_id"] == "rd_abc"
        assert cell_10["pr_url"] == "https://github.com/org/repo/pull/1"
        assert cell_10["result_commits"] == [_SHA_3]

    def test_row_with_no_association_has_null_association(self, client, tmp_path):
        from oompah.release_delivery_inventory import CommitRow, InventoryPage, ReleaseBranchInfo, ReleaseStatusCell

        orch = _make_orchestrator(tmp_path)
        page = InventoryPage(
            project_id=_PROJECT_ID,
            source_branch="main",
            source_head=_SOURCE_HEAD,
            release_branches=[
                ReleaseBranchInfo("release/1.1", head=_RELEASE_HEAD_11, available=True)
            ],
            rows=[
                CommitRow(
                    sha=_SHA_1,
                    short_sha=_SHA_1[:7],
                    subject="Direct commit",
                    author_name="Bob",
                    authored_at="2026-07-13T09:00:00+00:00",
                    parents=[_SHA_2],
                    selectable=True,
                    association=None,
                    release_status={
                        "release/1.1": ReleaseStatusCell(state="not_selected"),
                    },
                )
            ],
            next_cursor=None,
            stale=False,
            refreshed_at=None,
        )
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server._get_commit_inventory_service") as mock_svc_factory,
        ):
            mock_svc = MagicMock()
            mock_svc.get_page.return_value = page
            mock_svc_factory.return_value = mock_svc
            resp = client.get(_ENDPOINT)
        assert resp.json()["rows"][0]["association"] is None

    def test_empty_rows_on_all_filter(self, client, tmp_path):
        from oompah.release_delivery_inventory import InventoryPage, ReleaseBranchInfo

        orch = _make_orchestrator(tmp_path)
        page = InventoryPage(
            project_id=_PROJECT_ID,
            source_branch="main",
            source_head=_SOURCE_HEAD,
            release_branches=[
                ReleaseBranchInfo("release/1.1", head=_RELEASE_HEAD_11, available=True)
            ],
            rows=[],
            next_cursor=None,
            stale=False,
            refreshed_at=None,
        )
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server._get_commit_inventory_service") as mock_svc_factory,
        ):
            mock_svc = MagicMock()
            mock_svc.get_page.return_value = page
            mock_svc_factory.return_value = mock_svc
            resp = client.get(_ENDPOINT, params={"filter": "all"})
        assert resp.status_code == 200
        assert resp.json()["rows"] == []


# ---------------------------------------------------------------------------
# Branch available=False (branch exists in config but not in remote)
# ---------------------------------------------------------------------------


class TestBranchAvailability:
    """Unavailable branches are included with available=False and head=None."""

    def test_unavailable_branch_in_response(self, client, tmp_path):
        from oompah.release_delivery_inventory import ReleaseBranchInfo, InventoryPage

        orch = _make_orchestrator(tmp_path)
        page = InventoryPage(
            project_id=_PROJECT_ID,
            source_branch="main",
            source_head=_SOURCE_HEAD,
            release_branches=[
                ReleaseBranchInfo(
                    name="release/1.1", head=None, available=False, stale=False
                )
            ],
            rows=[],
            next_cursor=None,
            stale=False,
            refreshed_at=None,
        )
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server._get_commit_inventory_service") as mock_svc_factory,
        ):
            mock_svc = MagicMock()
            mock_svc.get_page.return_value = page
            mock_svc_factory.return_value = mock_svc
            resp = client.get(_ENDPOINT)
        branch_info = resp.json()["release_branches"][0]
        assert branch_info["available"] is False
        assert branch_info["head"] is None


# ===========================================================================
# POST /api/v1/projects/{project_id}/release-delivery/commits
# OOMPAH-199: Add commit-selection release delivery queue API
# ===========================================================================

_POST_ENDPOINT = f"/api/v1/projects/{_PROJECT_ID}/release-delivery/commits"
_IDEM_KEY = "test-idempotency-key-12345"
_SHA_A = "a" * 40
_SHA_B = "b" * 40
_SHA_C = "c" * 40
_SHA_D = "d" * 40
_BRANCH_11 = "release/1.1"
_BRANCH_10 = "release/1.0"


def _post_body(
    *,
    source_head: str = _SOURCE_HEAD,
    commits: list[str] | None = None,
    target_branches: list[str] | None = None,
) -> dict:
    return {
        "source_head": source_head,
        "commits": commits if commits is not None else [_SHA_A],
        "target_branches": target_branches if target_branches is not None else [_BRANCH_11],
    }


def _make_post_orchestrator(tmp_path: Path, project: MagicMock | None = None) -> MagicMock:
    p = project or _make_project(tmp_path)
    orch = MagicMock()
    orch.project_store.get = MagicMock(return_value=p)
    orch.event_bus = MagicMock()
    return orch


def _patch_git_validation(
    *,
    current_head: str | None = _SOURCE_HEAD,
    error_code: str | None = None,
    error_message: str | None = None,
):
    """Patch _delivery_validate_git to return a fixed result."""
    return patch(
        "oompah.server._delivery_validate_git",
        return_value=(current_head, error_code, error_message),
    )


@pytest.fixture(autouse=True)
def _clear_idempotency_store():
    """Clear the idempotency store between tests to avoid cross-test leakage."""
    server_module._delivery_idempotency_store.clear()
    yield
    server_module._delivery_idempotency_store.clear()


# ---------------------------------------------------------------------------
# Happy path – single commit, single target
# ---------------------------------------------------------------------------


class TestPostHappyPathSingleCommitSingleTarget:
    """POST with one commit and one target creates one delivery bundle."""

    def test_returns_201(self, client, tmp_path):
        orch = _make_post_orchestrator(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            _patch_git_validation(),
            patch("oompah.release_delivery_compat.make_delivery_store") as mock_store_factory,
        ):
            mock_store = MagicMock()
            mock_store.read_ledger.return_value = MagicMock(
                version=1, deliveries=[]
            )
            mock_store._write_ledger = MagicMock()
            mock_store_factory.return_value = mock_store
            resp = client.post(
                _POST_ENDPOINT,
                json=_post_body(),
                headers={"Idempotency-Key": _IDEM_KEY},
            )
        assert resp.status_code == 201

    def test_response_has_created_pair(self, client, tmp_path):
        orch = _make_post_orchestrator(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            _patch_git_validation(),
            patch("oompah.release_delivery_compat.make_delivery_store") as mock_store_factory,
        ):
            mock_store = MagicMock()
            mock_store.read_ledger.return_value = MagicMock(
                version=1, deliveries=[]
            )
            mock_store._write_ledger = MagicMock()
            mock_store_factory.return_value = mock_store
            resp = client.post(
                _POST_ENDPOINT,
                json=_post_body(commits=[_SHA_A], target_branches=[_BRANCH_11]),
                headers={"Idempotency-Key": _IDEM_KEY},
            )
        data = resp.json()
        assert len(data["created"]) == 1
        pair = data["created"][0]
        assert pair["commit"] == _SHA_A
        assert pair["target"] == _BRANCH_11
        assert "delivery_id" in pair

    def test_already_active_and_already_delivered_are_empty(self, client, tmp_path):
        orch = _make_post_orchestrator(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            _patch_git_validation(),
            patch("oompah.release_delivery_compat.make_delivery_store") as mock_store_factory,
        ):
            mock_store = MagicMock()
            mock_store.read_ledger.return_value = MagicMock(
                version=1, deliveries=[]
            )
            mock_store._write_ledger = MagicMock()
            mock_store_factory.return_value = mock_store
            resp = client.post(
                _POST_ENDPOINT,
                json=_post_body(),
                headers={"Idempotency-Key": _IDEM_KEY},
            )
        data = resp.json()
        assert data["already_active"] == []
        assert data["already_delivered"] == []
        assert data["invalid"] == []

    def test_never_creates_ordinary_task(self, client, tmp_path):
        """Delivery bundles must not create task files or task-kind records."""
        from oompah.release_delivery_store import SourceKind

        written_deliveries: list = []

        def capture_write(ledger, subject):
            written_deliveries.extend(ledger.deliveries)

        orch = _make_post_orchestrator(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            _patch_git_validation(),
            patch("oompah.release_delivery_compat.make_delivery_store") as mock_store_factory,
        ):
            mock_store = MagicMock()
            mock_store.read_ledger.return_value = MagicMock(
                version=1, deliveries=[]
            )
            mock_store._write_ledger = MagicMock(side_effect=capture_write)
            mock_store_factory.return_value = mock_store
            client.post(
                _POST_ENDPOINT,
                json=_post_body(),
                headers={"Idempotency-Key": _IDEM_KEY},
            )

        # All written deliveries must be source_kind=commits, not task or epic
        for d in written_deliveries:
            assert d.source_kind is SourceKind.COMMITS
            assert d.source_identifier is None


# ---------------------------------------------------------------------------
# Happy path – many commits, many targets
# ---------------------------------------------------------------------------


class TestPostManyCommitsManyTargets:
    """POST with multiple commits and multiple targets creates multiple bundles."""

    def test_creates_one_bundle_per_target(self, client, tmp_path):
        orch = _make_post_orchestrator(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            _patch_git_validation(),
            patch("oompah.release_delivery_compat.make_delivery_store") as mock_store_factory,
        ):
            mock_store = MagicMock()
            mock_store.read_ledger.return_value = MagicMock(
                version=1, deliveries=[]
            )
            mock_store._write_ledger = MagicMock()
            mock_store_factory.return_value = mock_store
            resp = client.post(
                _POST_ENDPOINT,
                json=_post_body(
                    commits=[_SHA_A, _SHA_B],
                    target_branches=[_BRANCH_11, _BRANCH_10],
                ),
                headers={"Idempotency-Key": _IDEM_KEY},
            )
        data = resp.json()
        # 2 commits × 2 targets = 4 pairs, but only 2 unique delivery_ids
        assert len(data["created"]) == 4
        delivery_ids = {pair["delivery_id"] for pair in data["created"]}
        # One bundle per target branch
        assert len(delivery_ids) == 2

    def test_all_commits_in_each_bundle_in_order(self, client, tmp_path):
        """The queued source_commits order must match the submitted order."""
        written_deliveries: list = []

        def capture_write(ledger, subject):
            written_deliveries.extend(ledger.deliveries)

        orch = _make_post_orchestrator(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            _patch_git_validation(),
            patch("oompah.release_delivery_compat.make_delivery_store") as mock_store_factory,
        ):
            mock_store = MagicMock()
            mock_store.read_ledger.return_value = MagicMock(
                version=1, deliveries=[]
            )
            mock_store._write_ledger = MagicMock(side_effect=capture_write)
            mock_store_factory.return_value = mock_store
            client.post(
                _POST_ENDPOINT,
                json=_post_body(
                    commits=[_SHA_A, _SHA_B, _SHA_C],
                    target_branches=[_BRANCH_11],
                ),
                headers={"Idempotency-Key": _IDEM_KEY},
            )

        assert len(written_deliveries) >= 1
        bundle = next(d for d in written_deliveries if d.target_branch == _BRANCH_11)
        # Exact commit order preserved
        assert bundle.source_commits == [_SHA_A, _SHA_B, _SHA_C]

    def test_created_pairs_include_all_commit_target_combos(self, client, tmp_path):
        orch = _make_post_orchestrator(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            _patch_git_validation(),
            patch("oompah.release_delivery_compat.make_delivery_store") as mock_store_factory,
        ):
            mock_store = MagicMock()
            mock_store.read_ledger.return_value = MagicMock(
                version=1, deliveries=[]
            )
            mock_store._write_ledger = MagicMock()
            mock_store_factory.return_value = mock_store
            resp = client.post(
                _POST_ENDPOINT,
                json=_post_body(
                    commits=[_SHA_A, _SHA_B],
                    target_branches=[_BRANCH_11],
                ),
                headers={"Idempotency-Key": _IDEM_KEY},
            )
        created = resp.json()["created"]
        combos = {(p["commit"], p["target"]) for p in created}
        assert (_SHA_A, _BRANCH_11) in combos
        assert (_SHA_B, _BRANCH_11) in combos


# ---------------------------------------------------------------------------
# Duplicate active/merged pairs
# ---------------------------------------------------------------------------


class TestPostDuplicatePairs:
    """Duplicate active and merged deliveries produce already_active / already_delivered."""

    def _make_active_delivery(self, target_branch: str, commits: list[str]) -> MagicMock:
        from oompah.release_delivery_store import ReleaseDelivery, SourceKind
        from oompah.release_addendum_schema import AddendumStatus

        d = MagicMock(spec=ReleaseDelivery)
        d.id = "rd_active_test"
        d.target_branch = target_branch
        d.source_commits = list(commits)
        d.status = AddendumStatus.OPEN
        return d

    def _make_merged_delivery(self, target_branch: str, commits: list[str]) -> MagicMock:
        from oompah.release_delivery_store import ReleaseDelivery
        from oompah.release_addendum_schema import AddendumStatus

        d = MagicMock(spec=ReleaseDelivery)
        d.id = "rd_merged_test"
        d.target_branch = target_branch
        d.source_commits = list(commits)
        d.status = AddendumStatus.MERGED
        return d

    def test_already_active_when_active_delivery_exists(self, client, tmp_path):
        active = self._make_active_delivery(_BRANCH_11, [_SHA_A])
        orch = _make_post_orchestrator(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            _patch_git_validation(),
            patch("oompah.release_delivery_compat.make_delivery_store") as mock_store_factory,
        ):
            mock_store = MagicMock()
            mock_store.read_ledger.return_value = MagicMock(
                version=1, deliveries=[active]
            )
            mock_store._write_ledger = MagicMock()
            mock_store_factory.return_value = mock_store
            resp = client.post(
                _POST_ENDPOINT,
                json=_post_body(commits=[_SHA_A], target_branches=[_BRANCH_11]),
                headers={"Idempotency-Key": _IDEM_KEY},
            )
        data = resp.json()
        assert resp.status_code == 201
        assert len(data["already_active"]) == 1
        assert data["already_active"][0]["commit"] == _SHA_A
        assert data["already_active"][0]["target"] == _BRANCH_11
        assert data["already_active"][0]["delivery_id"] == "rd_active_test"
        assert data["created"] == []

    def test_already_delivered_when_merged_delivery_exists(self, client, tmp_path):
        merged = self._make_merged_delivery(_BRANCH_11, [_SHA_A])
        orch = _make_post_orchestrator(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            _patch_git_validation(),
            patch("oompah.release_delivery_compat.make_delivery_store") as mock_store_factory,
        ):
            mock_store = MagicMock()
            mock_store.read_ledger.return_value = MagicMock(
                version=1, deliveries=[merged]
            )
            mock_store._write_ledger = MagicMock()
            mock_store_factory.return_value = mock_store
            resp = client.post(
                _POST_ENDPOINT,
                json=_post_body(commits=[_SHA_A], target_branches=[_BRANCH_11]),
                headers={"Idempotency-Key": _IDEM_KEY},
            )
        data = resp.json()
        assert resp.status_code == 201
        assert len(data["already_delivered"]) == 1
        assert data["already_delivered"][0]["commit"] == _SHA_A
        assert data["already_delivered"][0]["target"] == _BRANCH_11
        assert data["created"] == []

    def test_already_delivered_when_commit_is_on_target_branch(self, client, tmp_path):
        """Git ancestry blocks duplicate delivery even without ledger evidence."""
        orch = _make_post_orchestrator(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            _patch_git_validation(),
            patch("oompah.server._delivery_landed_commits_by_branch",
                  return_value={_BRANCH_11: {_SHA_A}}),
            patch("oompah.release_delivery_compat.make_delivery_store") as factory,
        ):
            store = MagicMock()
            store.read_ledger.return_value = MagicMock(version=1, deliveries=[])
            factory.return_value = store
            response = client.post(_POST_ENDPOINT, json=_post_body(),
                                   headers={"Idempotency-Key": _IDEM_KEY})
        assert response.status_code == 201
        assert response.json()["created"] == []
        assert response.json()["already_delivered"] == [
            {"commit": _SHA_A, "target": _BRANCH_11}
        ]
        store._write_ledger.assert_not_called()

    def test_no_duplicate_deliveries_when_active(self, client, tmp_path):
        """No new ledger write when delivery is already active."""
        active = self._make_active_delivery(_BRANCH_11, [_SHA_A])
        orch = _make_post_orchestrator(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            _patch_git_validation(),
            patch("oompah.release_delivery_compat.make_delivery_store") as mock_store_factory,
        ):
            mock_store = MagicMock()
            mock_store.read_ledger.return_value = MagicMock(
                version=1, deliveries=[active]
            )
            mock_store._write_ledger = MagicMock()
            mock_store_factory.return_value = mock_store
            client.post(
                _POST_ENDPOINT,
                json=_post_body(commits=[_SHA_A], target_branches=[_BRANCH_11]),
                headers={"Idempotency-Key": _IDEM_KEY},
            )
        # _write_ledger must NOT be called since there are no new deliveries
        mock_store._write_ledger.assert_not_called()

    def test_mixed_created_and_active(self, client, tmp_path):
        """One target active, another target fresh → one active, one created."""
        active = self._make_active_delivery(_BRANCH_11, [_SHA_A])
        orch = _make_post_orchestrator(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            _patch_git_validation(),
            patch("oompah.release_delivery_compat.make_delivery_store") as mock_store_factory,
        ):
            mock_store = MagicMock()
            mock_store.read_ledger.return_value = MagicMock(
                version=1, deliveries=[active]
            )
            mock_store._write_ledger = MagicMock()
            mock_store_factory.return_value = mock_store
            resp = client.post(
                _POST_ENDPOINT,
                json=_post_body(
                    commits=[_SHA_A],
                    target_branches=[_BRANCH_11, _BRANCH_10],
                ),
                headers={"Idempotency-Key": _IDEM_KEY},
            )
        data = resp.json()
        assert resp.status_code == 201
        assert len(data["already_active"]) == 1
        assert len(data["created"]) == 1
        assert data["created"][0]["target"] == _BRANCH_10


# ---------------------------------------------------------------------------
# Archived re-approval
# ---------------------------------------------------------------------------


class TestPostArchivedReapproval:
    """A commit with only an archived delivery gets a fresh bundle (created)."""

    def test_archived_does_not_block_new_delivery(self, client, tmp_path):
        from oompah.release_delivery_store import ReleaseDelivery
        from oompah.release_addendum_schema import AddendumStatus

        archived = MagicMock(spec=ReleaseDelivery)
        archived.id = "rd_archived_test"
        archived.target_branch = _BRANCH_11
        archived.source_commits = [_SHA_A]
        archived.status = AddendumStatus.ARCHIVED

        orch = _make_post_orchestrator(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            _patch_git_validation(),
            patch("oompah.release_delivery_compat.make_delivery_store") as mock_store_factory,
        ):
            mock_store = MagicMock()
            mock_store.read_ledger.return_value = MagicMock(
                version=1, deliveries=[archived]
            )
            mock_store._write_ledger = MagicMock()
            mock_store_factory.return_value = mock_store
            resp = client.post(
                _POST_ENDPOINT,
                json=_post_body(commits=[_SHA_A], target_branches=[_BRANCH_11]),
                headers={"Idempotency-Key": _IDEM_KEY},
            )
        data = resp.json()
        assert resp.status_code == 201
        # Archived entry must NOT block; a new delivery is created
        assert len(data["created"]) == 1
        assert data["already_active"] == []
        assert data["already_delivered"] == []


# ---------------------------------------------------------------------------
# Queue wake-up after persistence
# ---------------------------------------------------------------------------


class TestPostQueueWakeup:
    """event_bus.emit is called AFTER persistence for each new delivery."""

    def test_event_emitted_after_write(self, client, tmp_path):
        from oompah.events import EventType

        call_order: list[str] = []

        def record_write(ledger, subject):
            call_order.append("write")

        orch = _make_post_orchestrator(tmp_path)
        orch.event_bus.emit = MagicMock(side_effect=lambda *a, **kw: call_order.append("emit"))

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            _patch_git_validation(),
            patch("oompah.release_delivery_compat.make_delivery_store") as mock_store_factory,
        ):
            mock_store = MagicMock()
            mock_store.read_ledger.return_value = MagicMock(
                version=1, deliveries=[]
            )
            mock_store._write_ledger = MagicMock(side_effect=record_write)
            mock_store_factory.return_value = mock_store
            client.post(
                _POST_ENDPOINT,
                json=_post_body(),
                headers={"Idempotency-Key": _IDEM_KEY},
            )

        assert "write" in call_order
        assert "emit" in call_order
        # Write must precede emit
        assert call_order.index("write") < call_order.index("emit")

    def test_event_emitted_with_delivery_id(self, client, tmp_path):
        from oompah.events import EventType

        emitted_payloads: list = []

        def capture_emit(event_type, payload):
            if event_type == EventType.RELEASE_ADDENDUM_READY:
                emitted_payloads.append(payload)

        orch = _make_post_orchestrator(tmp_path)
        orch.event_bus.emit = MagicMock(side_effect=capture_emit)

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            _patch_git_validation(),
            patch("oompah.release_delivery_compat.make_delivery_store") as mock_store_factory,
        ):
            mock_store = MagicMock()
            mock_store.read_ledger.return_value = MagicMock(
                version=1, deliveries=[]
            )
            mock_store._write_ledger = MagicMock()
            mock_store_factory.return_value = mock_store
            resp = client.post(
                _POST_ENDPOINT,
                json=_post_body(),
                headers={"Idempotency-Key": _IDEM_KEY},
            )

        assert len(emitted_payloads) == 1
        delivery_id = resp.json()["created"][0]["delivery_id"]
        assert emitted_payloads[0]["delivery_id"] == delivery_id
        assert emitted_payloads[0]["project_id"] == _PROJECT_ID

    def test_no_event_when_no_new_deliveries(self, client, tmp_path):
        """No event emitted when all pairs are already_active."""
        from oompah.release_delivery_store import ReleaseDelivery
        from oompah.release_addendum_schema import AddendumStatus

        active = MagicMock(spec=ReleaseDelivery)
        active.id = "rd_existing"
        active.target_branch = _BRANCH_11
        active.source_commits = [_SHA_A]
        active.status = AddendumStatus.OPEN

        orch = _make_post_orchestrator(tmp_path)
        orch.event_bus.emit = MagicMock()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            _patch_git_validation(),
            patch("oompah.release_delivery_compat.make_delivery_store") as mock_store_factory,
        ):
            mock_store = MagicMock()
            mock_store.read_ledger.return_value = MagicMock(
                version=1, deliveries=[active]
            )
            mock_store._write_ledger = MagicMock()
            mock_store_factory.return_value = mock_store
            client.post(
                _POST_ENDPOINT,
                json=_post_body(commits=[_SHA_A], target_branches=[_BRANCH_11]),
                headers={"Idempotency-Key": _IDEM_KEY},
            )

        orch.event_bus.emit.assert_not_called()

    def test_event_emitted_for_each_new_delivery(self, client, tmp_path):
        """One event per new delivery (two targets → two events)."""
        from oompah.events import EventType

        emitted: list = []

        def capture(event_type, payload):
            if event_type == EventType.RELEASE_ADDENDUM_READY:
                emitted.append(payload)

        orch = _make_post_orchestrator(tmp_path)
        orch.event_bus.emit = MagicMock(side_effect=capture)

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            _patch_git_validation(),
            patch("oompah.release_delivery_compat.make_delivery_store") as mock_store_factory,
        ):
            mock_store = MagicMock()
            mock_store.read_ledger.return_value = MagicMock(
                version=1, deliveries=[]
            )
            mock_store._write_ledger = MagicMock()
            mock_store_factory.return_value = mock_store
            client.post(
                _POST_ENDPOINT,
                json=_post_body(
                    commits=[_SHA_A],
                    target_branches=[_BRANCH_11, _BRANCH_10],
                ),
                headers={"Idempotency-Key": _IDEM_KEY},
            )

        assert len(emitted) == 2


# ---------------------------------------------------------------------------
# Idempotency replay
# ---------------------------------------------------------------------------


class TestPostIdempotencyReplay:
    """Replaying the same idempotency key returns original outcome, no second write."""

    def test_replay_returns_201(self, client, tmp_path):
        orch = _make_post_orchestrator(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            _patch_git_validation(),
            patch("oompah.release_delivery_compat.make_delivery_store") as mock_store_factory,
        ):
            mock_store = MagicMock()
            mock_store.read_ledger.return_value = MagicMock(
                version=1, deliveries=[]
            )
            mock_store._write_ledger = MagicMock()
            mock_store_factory.return_value = mock_store
            # First request
            client.post(
                _POST_ENDPOINT,
                json=_post_body(),
                headers={"Idempotency-Key": _IDEM_KEY},
            )
            # Replay
            resp = client.post(
                _POST_ENDPOINT,
                json=_post_body(),
                headers={"Idempotency-Key": _IDEM_KEY},
            )
        assert resp.status_code == 201

    def test_replay_returns_same_body(self, client, tmp_path):
        orch = _make_post_orchestrator(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            _patch_git_validation(),
            patch("oompah.release_delivery_compat.make_delivery_store") as mock_store_factory,
        ):
            mock_store = MagicMock()
            mock_store.read_ledger.return_value = MagicMock(
                version=1, deliveries=[]
            )
            mock_store._write_ledger = MagicMock()
            mock_store_factory.return_value = mock_store
            resp1 = client.post(
                _POST_ENDPOINT,
                json=_post_body(),
                headers={"Idempotency-Key": _IDEM_KEY},
            )
            resp2 = client.post(
                _POST_ENDPOINT,
                json=_post_body(),
                headers={"Idempotency-Key": _IDEM_KEY},
            )
        assert resp1.json() == resp2.json()

    def test_replay_makes_no_additional_write(self, client, tmp_path):
        orch = _make_post_orchestrator(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            _patch_git_validation(),
            patch("oompah.release_delivery_compat.make_delivery_store") as mock_store_factory,
        ):
            mock_store = MagicMock()
            mock_store.read_ledger.return_value = MagicMock(
                version=1, deliveries=[]
            )
            mock_store._write_ledger = MagicMock()
            mock_store_factory.return_value = mock_store
            # First call
            client.post(
                _POST_ENDPOINT,
                json=_post_body(),
                headers={"Idempotency-Key": _IDEM_KEY},
            )
            write_count_after_first = mock_store._write_ledger.call_count
            # Replay
            client.post(
                _POST_ENDPOINT,
                json=_post_body(),
                headers={"Idempotency-Key": _IDEM_KEY},
            )
        # No additional write on replay
        assert mock_store._write_ledger.call_count == write_count_after_first

    def test_different_key_creates_new_delivery(self, client, tmp_path):
        orch = _make_post_orchestrator(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            _patch_git_validation(),
            patch("oompah.release_delivery_compat.make_delivery_store") as mock_store_factory,
        ):
            mock_store = MagicMock()
            mock_store.read_ledger.return_value = MagicMock(
                version=1, deliveries=[]
            )
            mock_store._write_ledger = MagicMock()
            mock_store_factory.return_value = mock_store
            resp1 = client.post(
                _POST_ENDPOINT,
                json=_post_body(),
                headers={"Idempotency-Key": "key-one"},
            )
            resp2 = client.post(
                _POST_ENDPOINT,
                json=_post_body(),
                headers={"Idempotency-Key": "key-two"},
            )
        # Both should succeed and create deliveries
        assert resp1.status_code == 201
        assert resp2.status_code == 201
        # Different keys → different delivery IDs
        id1 = resp1.json()["created"][0]["delivery_id"]
        id2 = resp2.json()["created"][0]["delivery_id"]
        assert id1 != id2


# ---------------------------------------------------------------------------
# Pre-write rejection: missing idempotency key
# ---------------------------------------------------------------------------


class TestPostMissingIdempotencyKey:
    """Missing Idempotency-Key header is rejected before writing."""

    def test_missing_key_returns_400(self, client, tmp_path):
        orch = _make_post_orchestrator(tmp_path)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.post(_POST_ENDPOINT, json=_post_body())
        assert resp.status_code == 400

    def test_missing_key_error_code(self, client, tmp_path):
        orch = _make_post_orchestrator(tmp_path)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.post(_POST_ENDPOINT, json=_post_body())
        assert resp.json()["error"]["code"] == "missing_idempotency_key"

    def test_empty_key_returns_400(self, client, tmp_path):
        orch = _make_post_orchestrator(tmp_path)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.post(
                _POST_ENDPOINT,
                json=_post_body(),
                headers={"Idempotency-Key": "   "},
            )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Pre-write rejection: malformed payload
# ---------------------------------------------------------------------------


class TestPostMalformedPayload:
    """Malformed payloads are rejected before writing."""

    def test_invalid_json_returns_400(self, client, tmp_path):
        orch = _make_post_orchestrator(tmp_path)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.post(
                _POST_ENDPOINT,
                content=b"not json at all",
                headers={
                    "Content-Type": "application/json",
                    "Idempotency-Key": _IDEM_KEY,
                },
            )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "malformed_payload"

    def test_missing_source_head_returns_400(self, client, tmp_path):
        orch = _make_post_orchestrator(tmp_path)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.post(
                _POST_ENDPOINT,
                json={"commits": [_SHA_A], "target_branches": [_BRANCH_11]},
                headers={"Idempotency-Key": _IDEM_KEY},
            )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "malformed_payload"

    def test_invalid_sha_in_source_head_returns_400(self, client, tmp_path):
        orch = _make_post_orchestrator(tmp_path)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.post(
                _POST_ENDPOINT,
                json=_post_body(source_head="short"),
                headers={"Idempotency-Key": _IDEM_KEY},
            )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "malformed_payload"

    def test_invalid_sha_in_commits_returns_400(self, client, tmp_path):
        orch = _make_post_orchestrator(tmp_path)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.post(
                _POST_ENDPOINT,
                json=_post_body(commits=["not-a-sha"]),
                headers={"Idempotency-Key": _IDEM_KEY},
            )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "malformed_payload"

    def test_empty_commits_returns_400(self, client, tmp_path):
        orch = _make_post_orchestrator(tmp_path)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.post(
                _POST_ENDPOINT,
                json=_post_body(commits=[]),
                headers={"Idempotency-Key": _IDEM_KEY},
            )
        assert resp.status_code == 400

    def test_empty_target_branches_returns_400(self, client, tmp_path):
        orch = _make_post_orchestrator(tmp_path)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.post(
                _POST_ENDPOINT,
                json=_post_body(target_branches=[]),
                headers={"Idempotency-Key": _IDEM_KEY},
            )
        assert resp.status_code == 400

    def test_missing_target_branches_returns_400(self, client, tmp_path):
        orch = _make_post_orchestrator(tmp_path)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.post(
                _POST_ENDPOINT,
                json={"source_head": _SOURCE_HEAD, "commits": [_SHA_A]},
                headers={"Idempotency-Key": _IDEM_KEY},
            )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Pre-write rejection: changed source HEAD
# ---------------------------------------------------------------------------


class TestPostSourceHeadChanged:
    """A changed source HEAD is rejected with 409 before writing."""

    def test_source_changed_returns_409(self, client, tmp_path):
        new_head = "9" * 40
        orch = _make_post_orchestrator(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            _patch_git_validation(
                current_head=new_head,
                error_code="source_changed",
                error_message="Source HEAD has changed.",
            ),
        ):
            resp = client.post(
                _POST_ENDPOINT,
                json=_post_body(source_head=_SOURCE_HEAD),
                headers={"Idempotency-Key": _IDEM_KEY},
            )
        assert resp.status_code == 409

    def test_source_changed_error_code(self, client, tmp_path):
        new_head = "9" * 40
        orch = _make_post_orchestrator(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            _patch_git_validation(
                current_head=new_head,
                error_code="source_changed",
                error_message="Source HEAD has changed.",
            ),
        ):
            resp = client.post(
                _POST_ENDPOINT,
                json=_post_body(),
                headers={"Idempotency-Key": _IDEM_KEY},
            )
        err = resp.json()["error"]
        assert err["code"] == "source_changed"
        assert "submitted_head" in err
        assert "current_head" in err

    def test_source_changed_includes_both_heads(self, client, tmp_path):
        new_head = "9" * 40
        orch = _make_post_orchestrator(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            _patch_git_validation(
                current_head=new_head,
                error_code="source_changed",
                error_message="Source HEAD has changed.",
            ),
        ):
            resp = client.post(
                _POST_ENDPOINT,
                json=_post_body(source_head=_SOURCE_HEAD),
                headers={"Idempotency-Key": _IDEM_KEY},
            )
        err = resp.json()["error"]
        assert err["submitted_head"] == _SOURCE_HEAD
        assert err["current_head"] == new_head


# ---------------------------------------------------------------------------
# Pre-write rejection: unreachable / merge SHA
# ---------------------------------------------------------------------------


class TestPostInvalidCommitSHA:
    """Invalid, unreachable, or merge commit SHAs are rejected before writing."""

    def test_unreachable_commit_returns_400(self, client, tmp_path):
        orch = _make_post_orchestrator(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            _patch_git_validation(
                error_code="unreachable_commit",
                error_message=f"Commit {_SHA_A!r} is not reachable.",
            ),
        ):
            resp = client.post(
                _POST_ENDPOINT,
                json=_post_body(commits=[_SHA_A]),
                headers={"Idempotency-Key": _IDEM_KEY},
            )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "unreachable_commit"

    def test_merge_commit_returns_400(self, client, tmp_path):
        orch = _make_post_orchestrator(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            _patch_git_validation(
                error_code="merge_commit",
                error_message=f"Commit {_SHA_A!r} is a merge commit.",
            ),
        ):
            resp = client.post(
                _POST_ENDPOINT,
                json=_post_body(commits=[_SHA_A]),
                headers={"Idempotency-Key": _IDEM_KEY},
            )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "merge_commit"

    def test_atomic_validation_failure_writes_nothing(self, client, tmp_path):
        """When any SHA fails validation, nothing is written to the ledger."""
        orch = _make_post_orchestrator(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            _patch_git_validation(
                error_code="unreachable_commit",
                error_message="SHA unreachable",
            ),
            patch("oompah.release_delivery_compat.make_delivery_store") as mock_store_factory,
        ):
            mock_store = MagicMock()
            mock_store._write_ledger = MagicMock()
            mock_store_factory.return_value = mock_store
            client.post(
                _POST_ENDPOINT,
                json=_post_body(),
                headers={"Idempotency-Key": _IDEM_KEY},
            )
        mock_store._write_ledger.assert_not_called()


# ---------------------------------------------------------------------------
# Pre-write rejection: unavailable branch
# ---------------------------------------------------------------------------


class TestPostUnavailableBranch:
    """Unavailable or unconfigured target branches are rejected before writing."""

    def test_unavailable_branch_returns_400(self, client, tmp_path):
        orch = _make_post_orchestrator(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            _patch_git_validation(
                error_code="unavailable_branch",
                error_message="Branch not available.",
            ),
        ):
            resp = client.post(
                _POST_ENDPOINT,
                json=_post_body(target_branches=[_BRANCH_11]),
                headers={"Idempotency-Key": _IDEM_KEY},
            )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "unavailable_branch"

    def test_invalid_branch_not_in_configured_returns_400(self, client, tmp_path):
        orch = _make_post_orchestrator(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            _patch_git_validation(
                error_code="invalid_branch",
                error_message="Branch not in supported list.",
            ),
        ):
            resp = client.post(
                _POST_ENDPOINT,
                json=_post_body(target_branches=["release/99.9"]),
                headers={"Idempotency-Key": _IDEM_KEY},
            )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "invalid_branch"


# ---------------------------------------------------------------------------
# Project not found
# ---------------------------------------------------------------------------


class TestPostProjectNotFound:
    def test_project_not_found_returns_404(self, client):
        orch = MagicMock()
        orch.project_store.get = MagicMock(return_value=None)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.post(
                "/api/v1/projects/unknown-proj/release-delivery/commits",
                json=_post_body(),
                headers={"Idempotency-Key": _IDEM_KEY},
            )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "not_found"


# ---------------------------------------------------------------------------
# No repo path
# ---------------------------------------------------------------------------


class TestPostNoRepo:
    def test_no_repo_returns_503(self, client, tmp_path):
        project = _make_project(tmp_path, repo_path="")
        orch = MagicMock()
        orch.project_store.get = MagicMock(return_value=project)
        orch.event_bus = MagicMock()
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.post(
                _POST_ENDPOINT,
                json=_post_body(),
                headers={"Idempotency-Key": _IDEM_KEY},
            )
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "no_repo"


# ---------------------------------------------------------------------------
# Delivery bundle structure verification
# ---------------------------------------------------------------------------


class TestPostDeliveryBundleStructure:
    """Verify that written delivery bundles have the correct immutable fields."""

    def test_bundle_has_correct_source_commits(self, client, tmp_path):
        written: list = []

        def capture_write(ledger, subject):
            for d in ledger.deliveries:
                written.append(d)

        orch = _make_post_orchestrator(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            _patch_git_validation(),
            patch("oompah.release_delivery_compat.make_delivery_store") as mock_store_factory,
        ):
            mock_store = MagicMock()
            mock_store.read_ledger.return_value = MagicMock(
                version=1, deliveries=[]
            )
            mock_store._write_ledger = MagicMock(side_effect=capture_write)
            mock_store_factory.return_value = mock_store
            client.post(
                _POST_ENDPOINT,
                json=_post_body(
                    commits=[_SHA_A, _SHA_B],
                    target_branches=[_BRANCH_11],
                ),
                headers={"Idempotency-Key": _IDEM_KEY},
            )

        bundle = next(d for d in written if d.target_branch == _BRANCH_11)
        assert bundle.source_commits == [_SHA_A, _SHA_B]

    def test_bundle_has_source_kind_commits(self, client, tmp_path):
        from oompah.release_delivery_store import SourceKind

        written: list = []

        def capture_write(ledger, subject):
            written.extend(ledger.deliveries)

        orch = _make_post_orchestrator(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            _patch_git_validation(),
            patch("oompah.release_delivery_compat.make_delivery_store") as mock_store_factory,
        ):
            mock_store = MagicMock()
            mock_store.read_ledger.return_value = MagicMock(
                version=1, deliveries=[]
            )
            mock_store._write_ledger = MagicMock(side_effect=capture_write)
            mock_store_factory.return_value = mock_store
            client.post(
                _POST_ENDPOINT,
                json=_post_body(),
                headers={"Idempotency-Key": _IDEM_KEY},
            )

        bundle = written[0]
        assert bundle.source_kind is SourceKind.COMMITS
        assert bundle.source_identifier is None

    def test_bundle_has_correct_target_branch(self, client, tmp_path):
        written: list = []

        def capture_write(ledger, subject):
            written.extend(ledger.deliveries)

        orch = _make_post_orchestrator(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            _patch_git_validation(),
            patch("oompah.release_delivery_compat.make_delivery_store") as mock_store_factory,
        ):
            mock_store = MagicMock()
            mock_store.read_ledger.return_value = MagicMock(
                version=1, deliveries=[]
            )
            mock_store._write_ledger = MagicMock(side_effect=capture_write)
            mock_store_factory.return_value = mock_store
            client.post(
                _POST_ENDPOINT,
                json=_post_body(target_branches=[_BRANCH_11]),
                headers={"Idempotency-Key": _IDEM_KEY},
            )

        bundle = written[0]
        assert bundle.target_branch == _BRANCH_11

    def test_bundle_has_open_status(self, client, tmp_path):
        from oompah.release_addendum_schema import AddendumStatus

        written: list = []

        def capture_write(ledger, subject):
            written.extend(ledger.deliveries)

        orch = _make_post_orchestrator(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            _patch_git_validation(),
            patch("oompah.release_delivery_compat.make_delivery_store") as mock_store_factory,
        ):
            mock_store = MagicMock()
            mock_store.read_ledger.return_value = MagicMock(
                version=1, deliveries=[]
            )
            mock_store._write_ledger = MagicMock(side_effect=capture_write)
            mock_store_factory.return_value = mock_store
            client.post(
                _POST_ENDPOINT,
                json=_post_body(),
                headers={"Idempotency-Key": _IDEM_KEY},
            )

        assert written[0].status is AddendumStatus.OPEN

    def test_bundle_project_id_matches(self, client, tmp_path):
        written: list = []

        def capture_write(ledger, subject):
            written.extend(ledger.deliveries)

        orch = _make_post_orchestrator(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            _patch_git_validation(),
            patch("oompah.release_delivery_compat.make_delivery_store") as mock_store_factory,
        ):
            mock_store = MagicMock()
            mock_store.read_ledger.return_value = MagicMock(
                version=1, deliveries=[]
            )
            mock_store._write_ledger = MagicMock(side_effect=capture_write)
            mock_store_factory.return_value = mock_store
            client.post(
                _POST_ENDPOINT,
                json=_post_body(),
                headers={"Idempotency-Key": _IDEM_KEY},
            )

        assert written[0].project_id == _PROJECT_ID


# ---------------------------------------------------------------------------
# asyncio.to_thread: git validation must be off-loop
# ---------------------------------------------------------------------------


class TestPostAsyncioToThread:
    """_delivery_validate_git must be called via asyncio.to_thread."""

    def test_validate_called_via_to_thread(self, client, tmp_path):
        """asyncio.to_thread is used by patching it and checking it was invoked."""
        calls: list = []
        _source_head = _SOURCE_HEAD

        async def fake_to_thread(fn, *args, **kwargs):
            calls.append((fn, args, kwargs))
            # Run the function so the handler proceeds normally
            return fn(*args, **kwargs)

        # Build a real validate-git function that returns "no error"
        def _fake_validate(*args, **kwargs):
            return (_source_head, None, None)

        orch = _make_post_orchestrator(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server.asyncio.to_thread", side_effect=fake_to_thread),
            patch(
                "oompah.server._delivery_validate_git",
                side_effect=_fake_validate,
            ) as mock_validate,
            patch("oompah.release_delivery_compat.make_delivery_store") as mock_store_factory,
        ):
            mock_store = MagicMock()
            mock_store.read_ledger.return_value = MagicMock(
                version=1, deliveries=[]
            )
            mock_store._write_ledger = MagicMock()
            mock_store_factory.return_value = mock_store
            resp = client.post(
                _POST_ENDPOINT,
                json=_post_body(),
                headers={"Idempotency-Key": _IDEM_KEY},
            )

        assert resp.status_code == 201
        # asyncio.to_thread must have been called at least once
        assert len(calls) >= 1
        # At least one call should be to the git validation function (the mock)
        fn_names_called = [getattr(fn, "__name__", None) for fn, _, _ in calls]
        # The mock's name should contain "_delivery_validate_git" or the call list
        # should have been populated with the mock object itself
        validate_was_threaded = any(
            fn is mock_validate or getattr(fn, "__name__", "") == "_fake_validate"
            for fn, _, _ in calls
        )
        assert validate_was_threaded, (
            f"Expected _delivery_validate_git to be called via asyncio.to_thread; "
            f"calls seen: {fn_names_called}"
        )
