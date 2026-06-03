"""Tests for the Backlog webhook endpoint POST /api/v1/webhooks/backlog.

Covers:
- Valid webhook receipt: cache invalidation, sync trigger, refresh
- Signature validation (HMAC-SHA256)
- Missing / invalid JSON body
- Unmatched project_id
- Idempotent webhook receipt (multiple posts for same project)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from oompah.models import Project


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_orchestrator(project: Project | None = None):
    """Build a minimal mock orchestrator for server endpoint tests."""
    orch = MagicMock()
    orch.request_refresh = MagicMock()
    orch.project_store = MagicMock()
    orch.project_store.get = MagicMock(return_value=project)
    orch.project_store.sync_project_sources = MagicMock(
        return_value={"git": "ok", "backlog": "ok"}
    )
    return orch


def _backlog_payload(project_id="proj-1", event="task_changed", files=None):
    return {
        "project_id": project_id,
        "event": event,
        "files": files or ["backlog/tasks/task-1 - Test.md"],
    }


def _backlog_signature(body_bytes: bytes, secret: str) -> str:
    mac = hmac.new(secret.encode(), body_bytes, hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client_no_project():
    """TestClient with no matching project (project_id lookup returns None)."""
    from oompah.server import app, _api_cache

    orch = _make_mock_orchestrator(project=None)
    with patch("oompah.server._orchestrator", orch):
        _api_cache.invalidate("issues:all")
        yield TestClient(app), orch


@pytest.fixture
def client_project_no_secret():
    """TestClient with a project that has no webhook_secret."""
    from oompah.server import app, _api_cache

    project = Project(
        id="proj-1",
        name="test-repo",
        repo_url="https://github.com/org/repo.git",
        repo_path="/tmp/repos/test",
        webhook_secret=None,
    )
    orch = _make_mock_orchestrator(project=project)
    with patch("oompah.server._orchestrator", orch):
        _api_cache.invalidate("issues:all")
        yield TestClient(app), orch


@pytest.fixture
def client_project_with_secret():
    """TestClient with a project that has a webhook_secret configured."""
    from oompah.server import app, _api_cache

    project = Project(
        id="proj-1",
        name="test-repo",
        repo_url="https://github.com/org/repo.git",
        repo_path="/tmp/repos/test",
        webhook_secret="test-secret-xyz",
    )
    orch = _make_mock_orchestrator(project=project)
    with patch("oompah.server._orchestrator", orch):
        _api_cache.invalidate("issues:all")
        yield TestClient(app), orch


# ---------------------------------------------------------------------------
# Basic receipt tests
# ---------------------------------------------------------------------------


class TestBacklogWebhookEndpoint:
    """Tests for POST /api/v1/webhooks/backlog."""

    def test_valid_webhook_accepted(self, client_project_no_secret):
        client, orch = client_project_no_secret
        payload = _backlog_payload()
        resp = client.post(
            "/api/v1/webhooks/backlog",
            content=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["action"] == "processed"
        assert data["project_id"] == "proj-1"
        assert data["event"] == "task_changed"
        assert data["files_changed"] == 1

    def test_request_refresh_called(self, client_project_no_secret):
        """Webhook receipt triggers orchestrator.request_refresh()."""
        client, orch = client_project_no_secret
        resp = client.post(
            "/api/v1/webhooks/backlog",
            content=json.dumps(_backlog_payload()),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200
        orch.request_refresh.assert_called_once()

    def test_project_sync_triggered_in_background(self, client_project_no_secret):
        """Webhook receipt triggers sync_project_sources in a background thread."""
        client, orch = client_project_no_secret
        resp = client.post(
            "/api/v1/webhooks/backlog",
            content=json.dumps(_backlog_payload()),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200
        # Wait briefly for the background thread to run
        for _ in range(50):
            if orch.project_store.sync_project_sources.called:
                break
            time.sleep(0.02)
        orch.project_store.sync_project_sources.assert_called_once_with("proj-1")

    def test_issue_cache_invalidated(self, client_project_no_secret):
        """Webhook receipt invalidates the issue list cache."""
        from oompah.server import _api_cache

        # Pre-populate cache
        _api_cache.set("issues:all", [{"id": "t1"}], ttl_ms=60000)

        client, _ = client_project_no_secret
        client.post(
            "/api/v1/webhooks/backlog",
            content=json.dumps(_backlog_payload()),
            headers={"Content-Type": "application/json"},
        )

        # Cache should be invalidated after webhook
        assert _api_cache.get("issues:all") is None

    def test_unmatched_project_still_returns_200(self, client_no_project):
        """When project_id does not match any project, webhook is accepted."""
        client, orch = client_no_project
        resp = client.post(
            "/api/v1/webhooks/backlog",
            content=json.dumps(_backlog_payload(project_id="unknown-proj")),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        # Still triggers refresh
        orch.request_refresh.assert_called_once()
        # But no project sync (no project found)
        time.sleep(0.05)
        orch.project_store.sync_project_sources.assert_not_called()

    def test_idempotent_multiple_posts(self, client_project_no_secret):
        """Multiple webhook posts for the same project all succeed."""
        client, orch = client_project_no_secret
        for i in range(3):
            resp = client.post(
                "/api/v1/webhooks/backlog",
                content=json.dumps(_backlog_payload()),
                headers={"Content-Type": "application/json"},
            )
            assert resp.status_code == 200
        assert orch.request_refresh.call_count == 3


# ---------------------------------------------------------------------------
# Signature validation tests
# ---------------------------------------------------------------------------


class TestBacklogWebhookSignatureValidation:
    """Tests for HMAC-SHA256 signature validation on POST /api/v1/webhooks/backlog."""

    def test_valid_signature_accepted(self, client_project_with_secret):
        client, orch = client_project_with_secret
        payload = json.dumps(_backlog_payload()).encode()
        sig = _backlog_signature(payload, "test-secret-xyz")
        resp = client.post(
            "/api/v1/webhooks/backlog",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-Oompah-Signature": sig,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_invalid_signature_rejected(self, client_project_with_secret):
        client, orch = client_project_with_secret
        payload = json.dumps(_backlog_payload()).encode()
        resp = client.post(
            "/api/v1/webhooks/backlog",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-Oompah-Signature": "sha256=badbadbadbad",
            },
        )
        assert resp.status_code == 401
        data = resp.json()
        assert "Invalid signature" in data.get("error", "")
        orch.request_refresh.assert_not_called()

    def test_no_signature_with_secret_accepted(self, client_project_with_secret):
        """When the project has a secret but the hook sends no signature, accept anyway.

        This handles the case where the hook was installed before the secret
        was set, or the git config hasn't propagated yet.
        """
        client, orch = client_project_with_secret
        resp = client.post(
            "/api/v1/webhooks/backlog",
            content=json.dumps(_backlog_payload()),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200

    def test_no_secret_no_signature_accepted(self, client_project_no_secret):
        """When neither project secret nor signature, webhook is accepted."""
        client, orch = client_project_no_secret
        resp = client.post(
            "/api/v1/webhooks/backlog",
            content=json.dumps(_backlog_payload()),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------


class TestBacklogWebhookErrors:
    """Error handling for POST /api/v1/webhooks/backlog."""

    def test_empty_body_returns_400(self, client_no_project):
        client, _ = client_no_project
        resp = client.post(
            "/api/v1/webhooks/backlog",
            content=b"",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400

    def test_invalid_json_returns_400(self, client_no_project):
        client, _ = client_no_project
        resp = client.post(
            "/api/v1/webhooks/backlog",
            content=b"not json{{{{",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400

    def test_non_object_json_returns_400(self, client_no_project):
        client, _ = client_no_project
        resp = client.post(
            "/api/v1/webhooks/backlog",
            content=json.dumps(["not", "an", "object"]),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400

    def test_missing_project_id_accepted_gracefully(self, client_no_project):
        """Webhook without project_id is accepted (empty project_id → no project found)."""
        client, orch = client_no_project
        resp = client.post(
            "/api/v1/webhooks/backlog",
            content=json.dumps({"event": "task_changed"}),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        orch.request_refresh.assert_called_once()


# ---------------------------------------------------------------------------
# Webhook triggering sync (integration-style)
# ---------------------------------------------------------------------------


class TestBacklogWebhookTriggerSync:
    """Verify the webhook handler triggers the correct project sync."""

    def test_sync_uses_correct_project_id(self, client_project_no_secret):
        """sync_project_sources is called with the project's ID."""
        client, orch = client_project_no_secret
        resp = client.post(
            "/api/v1/webhooks/backlog",
            content=json.dumps(_backlog_payload(project_id="proj-1")),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200
        # Wait for background thread
        for _ in range(50):
            if orch.project_store.sync_project_sources.called:
                break
            time.sleep(0.02)
        args = orch.project_store.sync_project_sources.call_args
        assert args[0][0] == "proj-1"

    def test_files_changed_count_in_response(self, client_project_no_secret):
        """Response includes count of changed files."""
        client, _ = client_project_no_secret
        files = [
            "backlog/tasks/task-1 - Test.md",
            "backlog/tasks/task-2 - Other.md",
        ]
        resp = client.post(
            "/api/v1/webhooks/backlog",
            content=json.dumps(_backlog_payload(files=files)),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200
        assert resp.json()["files_changed"] == 2
