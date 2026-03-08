"""Tests for forge webhook receiver endpoints in oompah.server.

Covers:
- POST /api/v1/webhooks/github — PR events, signature validation, non-PR events
- POST /api/v1/webhooks/gitlab — MR events, token validation, non-MR events
- EventBus emission on webhook receipt
- Cache invalidation and refresh triggering
- Missing headers, invalid payloads
"""

from __future__ import annotations

import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from oompah.events import EventBus, EventType
from oompah.models import Project


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_mock_orchestrator(projects=None, webhook_secret=None):
    """Build a mock orchestrator with project_store, event_bus, and request_refresh."""
    orch = MagicMock()
    orch.event_bus = EventBus()
    orch.request_refresh = MagicMock()

    if projects is None:
        projects = [
            Project(
                id="proj-gh1",
                name="github-proj",
                repo_url="https://github.com/org/repo.git",
                repo_path="/tmp/repos/repo",
                webhook_secret=webhook_secret,
            ),
        ]
    orch.project_store = MagicMock()
    orch.project_store.list_all.return_value = projects
    return orch


def _github_signature(body_bytes: bytes, secret: str) -> str:
    """Compute X-Hub-Signature-256 header value."""
    return "sha256=" + hmac.new(
        secret.encode(), body_bytes, hashlib.sha256
    ).hexdigest()


def _github_pr_payload(
    action="opened", number=42, repo="org/repo",
    source="feat-branch", target="main", author="octocat",
    title="Test PR", merged=False,
):
    return {
        "action": action,
        "pull_request": {
            "number": number,
            "title": title,
            "merged": merged,
            "user": {"login": author},
            "head": {"ref": source},
            "base": {"ref": target},
        },
        "repository": {"full_name": repo},
    }


def _gitlab_mr_payload(
    action="open", iid=7, repo="group/project",
    source="fix-branch", target="main", author="tanuki",
    title="Test MR", state="opened",
):
    return {
        "object_attributes": {
            "iid": iid,
            "title": title,
            "action": action,
            "state": state,
            "source_branch": source,
            "target_branch": target,
        },
        "user": {"username": author},
        "project": {"path_with_namespace": repo},
    }


@pytest.fixture
def client_no_secret():
    """TestClient with a mock orchestrator (no webhook secret)."""
    from oompah.server import app, _api_cache

    orch = _make_mock_orchestrator(webhook_secret=None)
    with patch("oompah.server._orchestrator", orch):
        _api_cache.invalidate("reviews:all")
        _api_cache.invalidate("issues:all")
        yield TestClient(app), orch


@pytest.fixture
def client_with_secret():
    """TestClient with a mock orchestrator (webhook secret configured)."""
    from oompah.server import app, _api_cache

    orch = _make_mock_orchestrator(webhook_secret="test-secret-123")
    with patch("oompah.server._orchestrator", orch):
        _api_cache.invalidate("reviews:all")
        _api_cache.invalidate("issues:all")
        yield TestClient(app), orch


@pytest.fixture
def client_gitlab():
    """TestClient with a GitLab project configured."""
    from oompah.server import app, _api_cache

    projects = [
        Project(
            id="proj-gl1",
            name="gitlab-proj",
            repo_url="https://gitlab.com/group/project.git",
            repo_path="/tmp/repos/project",
            webhook_secret="gl-secret",
        ),
    ]
    orch = _make_mock_orchestrator(projects=projects)
    with patch("oompah.server._orchestrator", orch):
        _api_cache.invalidate("reviews:all")
        _api_cache.invalidate("issues:all")
        yield TestClient(app), orch


# ---------------------------------------------------------------------------
# GitHub webhook endpoint
# ---------------------------------------------------------------------------


class TestGitHubWebhookEndpoint:
    """Tests for POST /api/v1/webhooks/github."""

    def test_pr_opened_no_secret(self, client_no_secret):
        client, orch = client_no_secret
        payload = _github_pr_payload(action="opened")
        resp = client.post(
            "/api/v1/webhooks/github",
            content=json.dumps(payload),
            headers={
                "X-GitHub-Event": "pull_request",
                "X-GitHub-Delivery": "abc-123",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["action"] == "processed"
        assert data["review_id"] == "42"
        assert data["pr_action"] == "opened"
        orch.request_refresh.assert_called_once()

    def test_pr_merged_triggers_refresh(self, client_no_secret):
        client, orch = client_no_secret
        payload = _github_pr_payload(action="closed", merged=True)
        resp = client.post(
            "/api/v1/webhooks/github",
            content=json.dumps(payload),
            headers={
                "X-GitHub-Event": "pull_request",
                "X-GitHub-Delivery": "def-456",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200
        orch.request_refresh.assert_called_once()

    def test_valid_signature(self, client_with_secret):
        client, orch = client_with_secret
        payload = _github_pr_payload()
        body_bytes = json.dumps(payload).encode()
        sig = _github_signature(body_bytes, "test-secret-123")
        resp = client.post(
            "/api/v1/webhooks/github",
            content=body_bytes,
            headers={
                "X-GitHub-Event": "pull_request",
                "X-Hub-Signature-256": sig,
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_invalid_signature_rejected(self, client_with_secret):
        client, orch = client_with_secret
        payload = _github_pr_payload()
        resp = client.post(
            "/api/v1/webhooks/github",
            content=json.dumps(payload),
            headers={
                "X-GitHub-Event": "pull_request",
                "X-Hub-Signature-256": "sha256=badbadbadbad",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 401
        assert "Invalid signature" in resp.json().get("error", "")
        orch.request_refresh.assert_not_called()

    def test_push_event_ignored(self, client_no_secret):
        client, orch = client_no_secret
        resp = client.post(
            "/api/v1/webhooks/github",
            content=json.dumps({"ref": "refs/heads/main"}),
            headers={
                "X-GitHub-Event": "push",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "ignored"
        orch.request_refresh.assert_not_called()

    def test_ping_event_ignored(self, client_no_secret):
        client, orch = client_no_secret
        resp = client.post(
            "/api/v1/webhooks/github",
            content=json.dumps({"zen": "test"}),
            headers={
                "X-GitHub-Event": "ping",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["action"] == "ignored"

    def test_missing_event_header(self, client_no_secret):
        client, _ = client_no_secret
        resp = client.post(
            "/api/v1/webhooks/github",
            content=json.dumps({"action": "opened"}),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400
        assert "Missing" in resp.json().get("error", "")

    def test_invalid_json_body(self, client_no_secret):
        client, _ = client_no_secret
        resp = client.post(
            "/api/v1/webhooks/github",
            content=b"not json{{{",
            headers={
                "X-GitHub-Event": "pull_request",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 400
        assert "Invalid JSON" in resp.json().get("error", "")

    def test_event_bus_emission(self, client_no_secret):
        client, orch = client_no_secret
        received = []
        orch.event_bus.subscribe(
            EventType.FORGE_WEBHOOK_RECEIVED,
            lambda et, p: received.append(p),
        )
        payload = _github_pr_payload(action="opened")
        resp = client.post(
            "/api/v1/webhooks/github",
            content=json.dumps(payload),
            headers={
                "X-GitHub-Event": "pull_request",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200
        assert len(received) == 1
        assert received[0]["provider"] == "github"
        assert received[0]["action"] == "opened"
        assert received[0]["review_id"] == "42"
        assert received[0]["source_branch"] == "feat-branch"

    def test_unmatched_repo_still_processed(self, client_no_secret):
        """A webhook from an unregistered repo is still processed (no validation needed)."""
        client, orch = client_no_secret
        payload = _github_pr_payload(repo="unknown-org/unknown-repo")
        resp = client.post(
            "/api/v1/webhooks/github",
            content=json.dumps(payload),
            headers={
                "X-GitHub-Event": "pull_request",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        orch.request_refresh.assert_called_once()


# ---------------------------------------------------------------------------
# GitLab webhook endpoint
# ---------------------------------------------------------------------------


class TestGitLabWebhookEndpoint:
    """Tests for POST /api/v1/webhooks/gitlab."""

    def test_mr_opened(self, client_gitlab):
        client, orch = client_gitlab
        payload = _gitlab_mr_payload(action="open")
        resp = client.post(
            "/api/v1/webhooks/gitlab",
            content=json.dumps(payload),
            headers={
                "X-Gitlab-Event": "Merge Request Hook",
                "X-Gitlab-Token": "gl-secret",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["action"] == "processed"
        assert data["review_id"] == "7"
        assert data["mr_action"] == "open"
        orch.request_refresh.assert_called_once()

    def test_mr_merged(self, client_gitlab):
        client, orch = client_gitlab
        payload = _gitlab_mr_payload(action="merge", state="merged")
        resp = client.post(
            "/api/v1/webhooks/gitlab",
            content=json.dumps(payload),
            headers={
                "X-Gitlab-Event": "Merge Request Hook",
                "X-Gitlab-Token": "gl-secret",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200
        orch.request_refresh.assert_called_once()

    def test_invalid_token_rejected(self, client_gitlab):
        client, orch = client_gitlab
        payload = _gitlab_mr_payload()
        resp = client.post(
            "/api/v1/webhooks/gitlab",
            content=json.dumps(payload),
            headers={
                "X-Gitlab-Event": "Merge Request Hook",
                "X-Gitlab-Token": "wrong-token",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 401
        assert "Invalid token" in resp.json().get("error", "")
        orch.request_refresh.assert_not_called()

    def test_push_event_ignored(self, client_gitlab):
        client, orch = client_gitlab
        resp = client.post(
            "/api/v1/webhooks/gitlab",
            content=json.dumps({"ref": "refs/heads/main"}),
            headers={
                "X-Gitlab-Event": "Push Hook",
                "X-Gitlab-Token": "gl-secret",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["action"] == "ignored"
        orch.request_refresh.assert_not_called()

    def test_missing_event_header(self, client_gitlab):
        client, _ = client_gitlab
        resp = client.post(
            "/api/v1/webhooks/gitlab",
            content=json.dumps({}),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400
        assert "Missing" in resp.json().get("error", "")

    def test_invalid_json_body(self, client_gitlab):
        client, _ = client_gitlab
        resp = client.post(
            "/api/v1/webhooks/gitlab",
            content=b"not json",
            headers={
                "X-Gitlab-Event": "Merge Request Hook",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 400

    def test_event_bus_emission(self, client_gitlab):
        client, orch = client_gitlab
        received = []
        orch.event_bus.subscribe(
            EventType.FORGE_WEBHOOK_RECEIVED,
            lambda et, p: received.append(p),
        )
        payload = _gitlab_mr_payload(action="open")
        resp = client.post(
            "/api/v1/webhooks/gitlab",
            content=json.dumps(payload),
            headers={
                "X-Gitlab-Event": "Merge Request Hook",
                "X-Gitlab-Token": "gl-secret",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200
        assert len(received) == 1
        assert received[0]["provider"] == "gitlab"
        assert received[0]["action"] == "open"
        assert received[0]["review_id"] == "7"
        assert received[0]["project_id"] == "proj-gl1"

    def test_no_secret_configured_accepts_any(self):
        """When no webhook_secret is set, webhooks are accepted without token validation."""
        from oompah.server import app, _api_cache

        projects = [
            Project(
                id="proj-gl2",
                name="gitlab-no-secret",
                repo_url="https://gitlab.com/group/project.git",
                repo_path="/tmp/repos/project",
                webhook_secret=None,  # No secret!
            ),
        ]
        orch = _make_mock_orchestrator(projects=projects)
        with patch("oompah.server._orchestrator", orch):
            _api_cache.invalidate("reviews:all")
            _api_cache.invalidate("issues:all")
            client = TestClient(app)
            payload = _gitlab_mr_payload()
            resp = client.post(
                "/api/v1/webhooks/gitlab",
                content=json.dumps(payload),
                headers={
                    "X-Gitlab-Event": "Merge Request Hook",
                    "Content-Type": "application/json",
                },
            )
            assert resp.status_code == 200
            assert resp.json()["ok"] is True


# ---------------------------------------------------------------------------
# EventType registration
# ---------------------------------------------------------------------------


class TestForgeWebhookEventType:
    """FORGE_WEBHOOK_RECEIVED must exist in EventType."""

    def test_event_type_exists(self):
        assert hasattr(EventType, "FORGE_WEBHOOK_RECEIVED")
        assert EventType.FORGE_WEBHOOK_RECEIVED == "forge_webhook_received"

    def test_event_type_is_string(self):
        assert isinstance(EventType.FORGE_WEBHOOK_RECEIVED, str)
