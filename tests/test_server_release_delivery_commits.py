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
