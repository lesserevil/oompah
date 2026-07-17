"""Tests for project-scoped release delivery retry/archive API endpoints (OOMPAH-216).

Covers:
- POST /api/v1/projects/{project_id}/release-delivery/{delivery_id}/retry
  - Returns 200 with updated status "open" on success
  - Returns 404 when project not found
  - Returns 404 when delivery not found
  - Returns 409 on invalid transition (already open, merged, archived)
  - Clears conflict_agent_task_id, lease, and error fields

- POST /api/v1/projects/{project_id}/release-delivery/{delivery_id}/archive
  - Returns 200 with updated status "archived" on success
  - Returns 409 on invalid transition (in_review, merged)
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Test constants
# ---------------------------------------------------------------------------

PROJECT_ID = "proj-retry-api-test"
_SHA_A = "a" * 40
NOW = datetime(2026, 7, 17, 0, 0, 0, tzinfo=timezone.utc)


def _delivery(
    *,
    delivery_id: str = "rd_api001",
    status_val: str = "blocked",
    error: str | None = "CONFLICT: merge conflict",
    conflict_agent_task_id: str | None = "OOMPAH-214",
    pr_url: str | None = None,
    target_branch: str = "release/0.11",
):
    from oompah.release_addendum_schema import AddendumStatus
    from oompah.release_delivery_store import ReleaseDelivery, SourceKind

    return ReleaseDelivery(
        id=delivery_id,
        project_id=PROJECT_ID,
        source_branch="main",
        source_kind=SourceKind.COMMITS,
        source_identifier=None,
        source_commits=[_SHA_A],
        target_branch=target_branch,
        status=AddendumStatus(status_val),
        queued_at=NOW.isoformat(),
        error=error,
        conflict_agent_task_id=conflict_agent_task_id,
        pr_url=pr_url,
    )


def _make_client(
    project,
    store,
    delivery=None,
):
    """Set up a TestClient with mocked orchestrator for the given project/store/delivery."""
    from oompah.server import app

    if delivery is not None:
        store.append(delivery)

    mock_project_store = MagicMock()
    mock_project_store.get.side_effect = lambda pid: project if pid == PROJECT_ID else None

    mock_orch = MagicMock()
    mock_orch.project_store = mock_project_store
    mock_orch._tracker_for_project.return_value = MagicMock()

    patches = [
        patch("oompah.server._get_orchestrator", return_value=mock_orch),
        patch("oompah.release_delivery_compat.make_delivery_store", return_value=store),
    ]
    return patches


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def project(tmp_path):
    return SimpleNamespace(
        id=PROJECT_ID,
        name="retry-test-project",
        repo_url="https://github.com/org/repo",
        repo_path=str(tmp_path),
        access_token=None,
        supported_release_branches=["release/0.11"],
    )


@pytest.fixture
def store(tmp_path):
    from oompah.release_delivery_store import ReleaseDeliveryStore
    return ReleaseDeliveryStore(tmp_path, PROJECT_ID)


# ---------------------------------------------------------------------------
# Tests: retry endpoint
# ---------------------------------------------------------------------------

class TestProjectRetryEndpoint:
    """POST /api/v1/projects/{project_id}/release-delivery/{delivery_id}/retry"""

    def test_retry_blocked_delivery_returns_200(self, project, store):
        delivery = _delivery(status_val="blocked")
        patches = _make_client(project, store, delivery=delivery)
        from oompah.server import app
        with patches[0], patches[1]:
            with TestClient(app, raise_server_exceptions=False) as c:
                resp = c.post(
                    f"/api/v1/projects/{PROJECT_ID}/release-delivery/{delivery.id}/retry"
                )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "open"
        assert data["delivery_id"] == delivery.id
        assert data["project_id"] == PROJECT_ID

    def test_retry_clears_conflict_agent_and_error(self, project, store):
        delivery = _delivery(
            status_val="blocked",
            conflict_agent_task_id="OOMPAH-214",
            error="CONFLICT: merge conflict",
        )
        patches = _make_client(project, store, delivery=delivery)
        from oompah.server import app
        with patches[0], patches[1]:
            with TestClient(app, raise_server_exceptions=False) as c:
                resp = c.post(
                    f"/api/v1/projects/{PROJECT_ID}/release-delivery/{delivery.id}/retry"
                )
        assert resp.status_code == 200
        from oompah.release_addendum_schema import AddendumStatus
        updated = store.lookup_by_id(delivery.id)
        assert updated.status is AddendumStatus.OPEN
        assert updated.error is None
        assert updated.conflict_agent_task_id is None

    def test_retry_in_review_delivery_returns_200(self, project, store):
        delivery = _delivery(
            status_val="in_review",
            error=None,
            conflict_agent_task_id=None,
        )
        patches = _make_client(project, store, delivery=delivery)
        from oompah.server import app
        with patches[0], patches[1]:
            with TestClient(app, raise_server_exceptions=False) as c:
                resp = c.post(
                    f"/api/v1/projects/{PROJECT_ID}/release-delivery/{delivery.id}/retry"
                )
        assert resp.status_code == 200
        assert resp.json()["status"] == "open"

    def test_retry_project_not_found_returns_404(self, project, store):
        delivery = _delivery()
        patches = _make_client(project, store, delivery=delivery)
        from oompah.server import app
        with patches[0], patches[1]:
            with TestClient(app, raise_server_exceptions=False) as c:
                resp = c.post(
                    f"/api/v1/projects/proj-nonexistent/release-delivery/{delivery.id}/retry"
                )
        assert resp.status_code == 404

    def test_retry_delivery_not_found_returns_404(self, project, store):
        patches = _make_client(project, store)
        from oompah.server import app
        with patches[0], patches[1]:
            with TestClient(app, raise_server_exceptions=False) as c:
                resp = c.post(
                    f"/api/v1/projects/{PROJECT_ID}/release-delivery/rd_nonexistent/retry"
                )
        assert resp.status_code == 404

    def test_retry_merged_delivery_returns_409(self, project, store):
        delivery = _delivery(
            status_val="merged",
            error=None,
            conflict_agent_task_id=None,
        )
        patches = _make_client(project, store, delivery=delivery)
        from oompah.server import app
        with patches[0], patches[1]:
            with TestClient(app, raise_server_exceptions=False) as c:
                resp = c.post(
                    f"/api/v1/projects/{PROJECT_ID}/release-delivery/{delivery.id}/retry"
                )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "invalid_transition"

    def test_retry_open_delivery_returns_409(self, project, store):
        delivery = _delivery(
            status_val="open",
            error=None,
            conflict_agent_task_id=None,
        )
        patches = _make_client(project, store, delivery=delivery)
        from oompah.server import app
        with patches[0], patches[1]:
            with TestClient(app, raise_server_exceptions=False) as c:
                resp = c.post(
                    f"/api/v1/projects/{PROJECT_ID}/release-delivery/{delivery.id}/retry"
                )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "invalid_transition"

    def test_retry_archived_delivery_returns_409(self, project, store):
        delivery = _delivery(
            status_val="archived",
            error=None,
            conflict_agent_task_id=None,
        )
        patches = _make_client(project, store, delivery=delivery)
        from oompah.server import app
        with patches[0], patches[1]:
            with TestClient(app, raise_server_exceptions=False) as c:
                resp = c.post(
                    f"/api/v1/projects/{PROJECT_ID}/release-delivery/{delivery.id}/retry"
                )
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Tests: archive endpoint
# ---------------------------------------------------------------------------

class TestProjectArchiveEndpoint:
    """POST /api/v1/projects/{project_id}/release-delivery/{delivery_id}/archive"""

    def test_archive_blocked_delivery_returns_200(self, project, store):
        delivery = _delivery(status_val="blocked")
        patches = _make_client(project, store, delivery=delivery)
        from oompah.server import app
        with patches[0], patches[1]:
            with TestClient(app, raise_server_exceptions=False) as c:
                resp = c.post(
                    f"/api/v1/projects/{PROJECT_ID}/release-delivery/{delivery.id}/archive"
                )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "archived"
        assert data["delivery_id"] == delivery.id

    def test_archive_open_delivery_returns_200(self, project, store):
        delivery = _delivery(status_val="open", error=None, conflict_agent_task_id=None)
        patches = _make_client(project, store, delivery=delivery)
        from oompah.server import app
        with patches[0], patches[1]:
            with TestClient(app, raise_server_exceptions=False) as c:
                resp = c.post(
                    f"/api/v1/projects/{PROJECT_ID}/release-delivery/{delivery.id}/archive"
                )
        assert resp.status_code == 200
        assert resp.json()["status"] == "archived"

    def test_archive_in_review_returns_409(self, project, store):
        delivery = _delivery(status_val="in_review", error=None, conflict_agent_task_id=None)
        patches = _make_client(project, store, delivery=delivery)
        from oompah.server import app
        with patches[0], patches[1]:
            with TestClient(app, raise_server_exceptions=False) as c:
                resp = c.post(
                    f"/api/v1/projects/{PROJECT_ID}/release-delivery/{delivery.id}/archive"
                )
        assert resp.status_code == 409

    def test_archive_merged_returns_409(self, project, store):
        delivery = _delivery(status_val="merged", error=None, conflict_agent_task_id=None)
        patches = _make_client(project, store, delivery=delivery)
        from oompah.server import app
        with patches[0], patches[1]:
            with TestClient(app, raise_server_exceptions=False) as c:
                resp = c.post(
                    f"/api/v1/projects/{PROJECT_ID}/release-delivery/{delivery.id}/archive"
                )
        assert resp.status_code == 409

    def test_archive_project_not_found_returns_404(self, project, store):
        delivery = _delivery()
        patches = _make_client(project, store, delivery=delivery)
        from oompah.server import app
        with patches[0], patches[1]:
            with TestClient(app, raise_server_exceptions=False) as c:
                resp = c.post(
                    f"/api/v1/projects/proj-nonexistent/release-delivery/{delivery.id}/archive"
                )
        assert resp.status_code == 404

    def test_archive_delivery_not_found_returns_404(self, project, store):
        patches = _make_client(project, store)
        from oompah.server import app
        with patches[0], patches[1]:
            with TestClient(app, raise_server_exceptions=False) as c:
                resp = c.post(
                    f"/api/v1/projects/{PROJECT_ID}/release-delivery/rd_missing/archive"
                )
        assert resp.status_code == 404
