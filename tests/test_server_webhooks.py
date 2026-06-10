"""Tests for forge webhook receiver endpoints in oompah.server.

Covers:
- POST /api/v1/webhooks/github — PR events, signature validation, non-PR events
- POST /api/v1/webhooks/gitlab — MR events, token validation, non-MR events
- EventBus emission on webhook receipt
- Cache invalidation and refresh triggering (targeted per event type)
- Selective orchestrator refresh (_webhook_should_request_refresh)
- Branch-to-issue tracker cache invalidation
- Missing headers, invalid payloads
- last_webhook_received_at timestamp tracking per project
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
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
    # Mock project_store.update so tests can assert on last_webhook_received_at
    orch.project_store = MagicMock()
    orch.project_store.update = MagicMock()

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

    def test_pr_merged_to_tracked_branch_triggers_sync(self, client_no_secret):
        """A merged PR whose base is the project's tracked branch should
        trigger source sync — the merge advanced origin/main."""
        client, orch = client_no_secret
        payload = _github_pr_payload(action="closed", merged=True, target="main")
        resp = client.post(
            "/api/v1/webhooks/github",
            content=json.dumps(payload),
            headers={
                "X-GitHub-Event": "pull_request",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200
        import time
        for _ in range(50):
            if orch.project_store.sync_project_sources.called:
                break
            time.sleep(0.02)
        orch.project_store.sync_project_sources.assert_called_once_with("proj-gh1")

    def test_pr_opened_does_not_trigger_sync(self, client_no_secret):
        """An opened PR doesn't change origin/main yet — no sync needed."""
        client, orch = client_no_secret
        payload = _github_pr_payload(action="opened", merged=False)
        resp = client.post(
            "/api/v1/webhooks/github",
            content=json.dumps(payload),
            headers={
                "X-GitHub-Event": "pull_request",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200
        import time
        time.sleep(0.1)
        orch.project_store.sync_project_sources.assert_not_called()

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

    def test_push_event_to_tracked_branch_triggers_sync(self, client_no_secret):
        """Push to project's tracked branch (main) should fire a project-scoped
        source sync — that's the whole point of the webhook integration."""
        client, orch = client_no_secret
        resp = client.post(
            "/api/v1/webhooks/github",
            content=json.dumps({
                "ref": "refs/heads/main",
                "repository": {"full_name": "org/repo"},
                "pusher": {"name": "alice"},
                "head_commit": {"message": "chore: bump deps"},
            }),
            headers={
                "X-GitHub-Event": "push",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200
        # Refresh fires regardless of branch.
        orch.request_refresh.assert_called()
        # Sync starts in a thread; poll briefly for it to land.
        import time
        for _ in range(50):
            if orch.project_store.sync_project_sources.called:
                break
            time.sleep(0.02)
        orch.project_store.sync_project_sources.assert_called_once_with("proj-gh1")

    def test_push_event_to_other_branch_no_sync(self, client_no_secret):
        client, orch = client_no_secret
        resp = client.post(
            "/api/v1/webhooks/github",
            content=json.dumps({
                "ref": "refs/heads/feature-x",
                "repository": {"full_name": "org/repo"},
                "pusher": {"name": "alice"},
            }),
            headers={
                "X-GitHub-Event": "push",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200
        # Give any spawned thread a moment to run, then assert it didn't.
        import time
        time.sleep(0.1)
        orch.project_store.sync_project_sources.assert_not_called()

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

    def test_last_webhook_received_at_updated_on_pr(self, client_no_secret):
        """Webhook receipt for a matched project updates last_webhook_received_at."""
        client, orch = client_no_secret
        payload = _github_pr_payload(action="opened")
        resp = client.post(
            "/api/v1/webhooks/github",
            content=json.dumps(payload),
            headers={
                "X-GitHub-Event": "pull_request",
                "X-GitHub-Delivery": "test-delivery-123",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200
        # project_store.update should have been called with last_webhook_received_at.
        orch.project_store.update.assert_called()
        call_kwargs = orch.project_store.update.call_args[1]
        assert "last_webhook_received_at" in call_kwargs
        assert isinstance(call_kwargs["last_webhook_received_at"], datetime)


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


# ---------------------------------------------------------------------------
# Payload helpers for new event types
# ---------------------------------------------------------------------------


def _github_issues_payload(
    action="opened",
    number=101,
    repo="org/repo",
    title="Fix the bug",
    author="octocat",
):
    """Build a minimal GitHub ``issues`` webhook payload."""
    return {
        "action": action,
        "issue": {
            "number": number,
            "title": title,
            "user": {"login": author},
            "pull_request": None,  # not a PR
        },
        "repository": {"full_name": repo},
        "sender": {"login": author},
    }


def _github_issue_comment_payload(
    action="created",
    issue_number=101,
    comment_id=9001,
    repo="org/repo",
    author="octocat",
):
    """Build a minimal GitHub ``issue_comment`` webhook payload."""
    return {
        "action": action,
        "issue": {
            "number": issue_number,
            "pull_request": None,
        },
        "comment": {
            "id": comment_id,
            "body": "LGTM",
            "user": {"login": author},
        },
        "repository": {"full_name": repo},
        "sender": {"login": author},
    }


def _github_label_payload(
    action="created",
    label_name="priority:high",
    repo="org/repo",
    author="octocat",
):
    """Build a minimal GitHub ``label`` webhook payload."""
    return {
        "action": action,
        "label": {
            "name": label_name,
            "color": "ff0000",
        },
        "repository": {"full_name": repo},
        "sender": {"login": author},
    }


def _github_projects_v2_item_payload(
    action="edited",
    item_node_id="PVI_kwDOA123",
    field_name="Status",
    field_value="In Progress",
    author="octocat",
):
    """Build a minimal GitHub ``projects_v2_item`` webhook payload."""
    payload = {
        "action": action,
        "projects_v2_item": {
            "node_id": item_node_id,
            "content_type": "Issue",
        },
        "sender": {"login": author},
    }
    if field_name:
        payload["changes"] = {
            "field_value": {
                "field_name": field_name,
                "to": {"name": field_value},
            }
        }
    return payload


# ---------------------------------------------------------------------------
# Targeted cache invalidation tests
# ---------------------------------------------------------------------------


class TestWebhookCacheInvalidation:
    """Cache invalidation is targeted per event type (AC#1).

    PR / merge_group → reviews:all + issues:all
    issues          → issues:all + detail:{project_id}:{issue_number}
    issue_comment   → issues:all + comments:… + detail:…
    projects_v2_item → issues:all
    label           → nothing (repository-level label, not task data)
    push            → nothing in _api_cache (handled by source-sync thread)
    """

    def test_pr_invalidates_reviews_and_issues(self, client_no_secret):
        """PR events invalidate both reviews:all and issues:all."""
        from oompah.server import _api_cache

        # Pre-populate both caches.
        _api_cache.set("reviews:all", {"data": "stale"}, ttl_ms=60_000)
        _api_cache.set("issues:all", {"data": "stale"}, ttl_ms=60_000)
        client, orch = client_no_secret
        client.post(
            "/api/v1/webhooks/github",
            content=json.dumps(_github_pr_payload(action="opened")),
            headers={"X-GitHub-Event": "pull_request", "Content-Type": "application/json"},
        )
        assert _api_cache.get("reviews:all") is None
        assert _api_cache.get("issues:all") is None

    def test_issues_event_invalidates_issues_and_detail(self, client_no_secret):
        """``issues`` events drop the list cache and the per-issue detail cache."""
        from oompah.server import _api_cache

        _api_cache.set("issues:all", {"data": "stale"}, ttl_ms=60_000)
        _api_cache.set("detail:proj-gh1:101:v1", {"data": "stale"}, ttl_ms=60_000)
        # reviews:all should NOT be dropped.
        _api_cache.set("reviews:all", {"data": "fresh"}, ttl_ms=60_000)

        client, orch = client_no_secret
        client.post(
            "/api/v1/webhooks/github",
            content=json.dumps(_github_issues_payload(action="opened", number=101)),
            headers={"X-GitHub-Event": "issues", "Content-Type": "application/json"},
        )
        assert _api_cache.get("issues:all") is None
        assert _api_cache.get("detail:proj-gh1:101:v1") is None
        # reviews:all stays intact — issues events don't touch it.
        assert _api_cache.get("reviews:all") is not None

    def test_issue_comment_invalidates_comment_and_detail_caches(self, client_no_secret):
        """``issue_comment`` events invalidate issues, comments, and detail caches."""
        from oompah.server import _api_cache

        _api_cache.set("issues:all", {"data": "stale"}, ttl_ms=60_000)
        _api_cache.set("comments:proj-gh1:101", {"data": "stale"}, ttl_ms=60_000)
        _api_cache.set("detail:proj-gh1:101:v1", {"data": "stale"}, ttl_ms=60_000)
        _api_cache.set("reviews:all", {"data": "fresh"}, ttl_ms=60_000)

        client, orch = client_no_secret
        client.post(
            "/api/v1/webhooks/github",
            content=json.dumps(
                _github_issue_comment_payload(action="created", issue_number=101)
            ),
            headers={"X-GitHub-Event": "issue_comment", "Content-Type": "application/json"},
        )
        assert _api_cache.get("issues:all") is None
        assert _api_cache.get("comments:proj-gh1:101") is None
        assert _api_cache.get("detail:proj-gh1:101:v1") is None
        # reviews:all is not affected by comment events.
        assert _api_cache.get("reviews:all") is not None

    def test_label_event_does_not_invalidate_any_cache(self, client_no_secret):
        """Repository-level label events carry no task-relevant state change."""
        from oompah.server import _api_cache

        _api_cache.set("issues:all", {"data": "fresh"}, ttl_ms=60_000)
        _api_cache.set("reviews:all", {"data": "fresh"}, ttl_ms=60_000)

        client, orch = client_no_secret
        client.post(
            "/api/v1/webhooks/github",
            content=json.dumps(_github_label_payload(action="created")),
            headers={"X-GitHub-Event": "label", "Content-Type": "application/json"},
        )
        # Neither cache should have been touched.
        assert _api_cache.get("issues:all") is not None
        assert _api_cache.get("reviews:all") is not None

    def test_projects_v2_item_invalidates_issues_not_reviews(self, client_no_secret):
        """``projects_v2_item`` events drop the issue list cache only."""
        from oompah.server import _api_cache

        _api_cache.set("issues:all", {"data": "stale"}, ttl_ms=60_000)
        _api_cache.set("reviews:all", {"data": "fresh"}, ttl_ms=60_000)

        client, orch = client_no_secret
        client.post(
            "/api/v1/webhooks/github",
            content=json.dumps(
                _github_projects_v2_item_payload(action="edited", field_name="Status")
            ),
            headers={"X-GitHub-Event": "projects_v2_item", "Content-Type": "application/json"},
        )
        assert _api_cache.get("issues:all") is None
        # reviews:all is unaffected by project-field events.
        assert _api_cache.get("reviews:all") is not None

    def test_push_to_non_tracked_branch_does_not_invalidate_caches(self, client_no_secret):
        """Push events to non-tracked branches leave API caches intact."""
        from oompah.server import _api_cache

        _api_cache.set("issues:all", {"data": "fresh"}, ttl_ms=60_000)
        _api_cache.set("reviews:all", {"data": "fresh"}, ttl_ms=60_000)

        client, orch = client_no_secret
        client.post(
            "/api/v1/webhooks/github",
            content=json.dumps({
                "ref": "refs/heads/feature-xyz",
                "repository": {"full_name": "org/repo"},
                "pusher": {"name": "alice"},
                "head_commit": {"message": "wip"},
            }),
            headers={"X-GitHub-Event": "push", "Content-Type": "application/json"},
        )
        assert _api_cache.get("issues:all") is not None
        assert _api_cache.get("reviews:all") is not None

    def test_issue_comment_only_invalidates_matching_issue_caches(self, client_no_secret):
        """Comment events on issue #101 must not drop caches for issue #202."""
        from oompah.server import _api_cache

        _api_cache.set("comments:proj-gh1:202", {"data": "fresh"}, ttl_ms=60_000)
        _api_cache.set("detail:proj-gh1:202:v1", {"data": "fresh"}, ttl_ms=60_000)

        client, orch = client_no_secret
        client.post(
            "/api/v1/webhooks/github",
            content=json.dumps(
                _github_issue_comment_payload(action="created", issue_number=101)
            ),
            headers={"X-GitHub-Event": "issue_comment", "Content-Type": "application/json"},
        )
        # Other issue's caches must remain intact.
        assert _api_cache.get("comments:proj-gh1:202") is not None
        assert _api_cache.get("detail:proj-gh1:202:v1") is not None


# ---------------------------------------------------------------------------
# Selective orchestrator refresh tests
# ---------------------------------------------------------------------------


class TestWebhookSelectiveRefresh:
    """orchestrator.request_refresh() is called only for dispatch-relevant events (AC#2)."""

    def test_label_event_does_not_trigger_refresh(self, client_no_secret):
        """Repository-level label events must not wake the dispatch loop."""
        client, orch = client_no_secret
        client.post(
            "/api/v1/webhooks/github",
            content=json.dumps(_github_label_payload(action="created")),
            headers={"X-GitHub-Event": "label", "Content-Type": "application/json"},
        )
        orch.request_refresh.assert_not_called()

    def test_push_to_non_tracked_branch_does_not_trigger_refresh(self, client_no_secret):
        """Push to a branch the project doesn't track must not wake the dispatch loop."""
        client, orch = client_no_secret
        client.post(
            "/api/v1/webhooks/github",
            content=json.dumps({
                "ref": "refs/heads/dependabot/npm/lodash",
                "repository": {"full_name": "org/repo"},
                "pusher": {"name": "bot"},
                "head_commit": {"message": "bump lodash"},
            }),
            headers={"X-GitHub-Event": "push", "Content-Type": "application/json"},
        )
        orch.request_refresh.assert_not_called()

    def test_issues_opened_triggers_refresh(self, client_no_secret):
        """``issues`` opened → dispatch-relevant → refresh expected."""
        client, orch = client_no_secret
        client.post(
            "/api/v1/webhooks/github",
            content=json.dumps(_github_issues_payload(action="opened")),
            headers={"X-GitHub-Event": "issues", "Content-Type": "application/json"},
        )
        orch.request_refresh.assert_called_once()

    def test_issues_closed_triggers_refresh(self, client_no_secret):
        client, orch = client_no_secret
        client.post(
            "/api/v1/webhooks/github",
            content=json.dumps(_github_issues_payload(action="closed")),
            headers={"X-GitHub-Event": "issues", "Content-Type": "application/json"},
        )
        orch.request_refresh.assert_called_once()

    def test_issues_labeled_triggers_refresh(self, client_no_secret):
        client, orch = client_no_secret
        client.post(
            "/api/v1/webhooks/github",
            content=json.dumps(_github_issues_payload(action="labeled")),
            headers={"X-GitHub-Event": "issues", "Content-Type": "application/json"},
        )
        orch.request_refresh.assert_called_once()

    def test_issues_locked_does_not_trigger_refresh(self, client_no_secret):
        """``issues`` locked is not dispatch-relevant — no refresh expected."""
        client, orch = client_no_secret
        client.post(
            "/api/v1/webhooks/github",
            content=json.dumps(_github_issues_payload(action="locked")),
            headers={"X-GitHub-Event": "issues", "Content-Type": "application/json"},
        )
        orch.request_refresh.assert_not_called()

    def test_issues_pinned_does_not_trigger_refresh(self, client_no_secret):
        """``issues`` pinned is cosmetic — no refresh expected."""
        client, orch = client_no_secret
        client.post(
            "/api/v1/webhooks/github",
            content=json.dumps(_github_issues_payload(action="pinned")),
            headers={"X-GitHub-Event": "issues", "Content-Type": "application/json"},
        )
        orch.request_refresh.assert_not_called()

    def test_issue_comment_created_triggers_refresh(self, client_no_secret):
        """Comments affect agent context and may carry status directives."""
        client, orch = client_no_secret
        client.post(
            "/api/v1/webhooks/github",
            content=json.dumps(_github_issue_comment_payload(action="created")),
            headers={"X-GitHub-Event": "issue_comment", "Content-Type": "application/json"},
        )
        orch.request_refresh.assert_called_once()

    def test_issue_comment_edited_triggers_refresh(self, client_no_secret):
        client, orch = client_no_secret
        client.post(
            "/api/v1/webhooks/github",
            content=json.dumps(_github_issue_comment_payload(action="edited")),
            headers={"X-GitHub-Event": "issue_comment", "Content-Type": "application/json"},
        )
        orch.request_refresh.assert_called_once()

    def test_projects_v2_item_edited_with_field_triggers_refresh(self, client_no_secret):
        """A project field change (e.g. Status → In Progress) must trigger refresh."""
        client, orch = client_no_secret
        client.post(
            "/api/v1/webhooks/github",
            content=json.dumps(
                _github_projects_v2_item_payload(action="edited", field_name="Status")
            ),
            headers={"X-GitHub-Event": "projects_v2_item", "Content-Type": "application/json"},
        )
        orch.request_refresh.assert_called_once()

    def test_projects_v2_item_reordered_does_not_trigger_refresh(self, client_no_secret):
        """Reordering a project item is cosmetic and must not wake the dispatch loop."""
        client, orch = client_no_secret
        client.post(
            "/api/v1/webhooks/github",
            content=json.dumps(
                _github_projects_v2_item_payload(action="reordered", field_name="")
            ),
            headers={"X-GitHub-Event": "projects_v2_item", "Content-Type": "application/json"},
        )
        orch.request_refresh.assert_not_called()

    def test_push_to_tracked_main_triggers_refresh(self, client_no_secret):
        """Push to the project's tracked branch must trigger a refresh."""
        client, orch = client_no_secret
        client.post(
            "/api/v1/webhooks/github",
            content=json.dumps({
                "ref": "refs/heads/main",
                "repository": {"full_name": "org/repo"},
                "pusher": {"name": "alice"},
                "head_commit": {"message": "add feature"},
            }),
            headers={"X-GitHub-Event": "push", "Content-Type": "application/json"},
        )
        orch.request_refresh.assert_called()


# ---------------------------------------------------------------------------
# Branch-to-issue tracker cache invalidation tests
# ---------------------------------------------------------------------------


class TestWebhookBranchToIssueCacheInvalidation:
    """The tracker's read cache (ETag / branch-to-issue index) is invalidated for
    events that can update branch metadata or PR-to-issue mappings.

    Affected event types: issues, pull_request, push (when project matches).
    Unaffected: issue_comment, label, projects_v2_item.
    """

    def _tracker_invalidate_call_count(self, orch) -> int:
        """Return how many times invalidate_read_cache() was called on any tracker."""
        mock_tracker = orch._tracker_for_project.return_value
        return mock_tracker.invalidate_read_cache.call_count

    def test_issues_event_invalidates_tracker_cache(self, client_no_secret):
        """``issues`` events may change work-branch metadata → invalidate tracker read cache."""
        client, orch = client_no_secret
        client.post(
            "/api/v1/webhooks/github",
            content=json.dumps(_github_issues_payload(action="opened")),
            headers={"X-GitHub-Event": "issues", "Content-Type": "application/json"},
        )
        orch._tracker_for_project.assert_called_with("proj-gh1")
        assert self._tracker_invalidate_call_count(orch) >= 1

    def test_pull_request_event_invalidates_tracker_cache(self, client_no_secret):
        """``pull_request`` events update PR-to-issue mappings → invalidate tracker read cache."""
        client, orch = client_no_secret
        client.post(
            "/api/v1/webhooks/github",
            content=json.dumps(_github_pr_payload(action="opened")),
            headers={"X-GitHub-Event": "pull_request", "Content-Type": "application/json"},
        )
        orch._tracker_for_project.assert_called_with("proj-gh1")
        assert self._tracker_invalidate_call_count(orch) >= 1

    def test_push_event_invalidates_tracker_cache(self, client_no_secret):
        """``push`` events may introduce new branches → invalidate tracker read cache."""
        client, orch = client_no_secret
        client.post(
            "/api/v1/webhooks/github",
            content=json.dumps({
                "ref": "refs/heads/main",
                "repository": {"full_name": "org/repo"},
                "pusher": {"name": "alice"},
                "head_commit": {"message": "chore"},
            }),
            headers={"X-GitHub-Event": "push", "Content-Type": "application/json"},
        )
        orch._tracker_for_project.assert_called_with("proj-gh1")
        assert self._tracker_invalidate_call_count(orch) >= 1

    def test_issue_comment_does_not_invalidate_tracker_cache(self, client_no_secret):
        """Comment events don't change branch metadata → tracker cache stays intact."""
        client, orch = client_no_secret
        client.post(
            "/api/v1/webhooks/github",
            content=json.dumps(_github_issue_comment_payload(action="created")),
            headers={"X-GitHub-Event": "issue_comment", "Content-Type": "application/json"},
        )
        # _tracker_for_project must NOT have been called for branch-to-issue invalidation.
        # (It may be called for other reasons via MagicMock attribute access, so we check
        # specifically that invalidate_read_cache was NOT called.)
        mock_tracker = orch._tracker_for_project.return_value
        mock_tracker.invalidate_read_cache.assert_not_called()

    def test_label_event_does_not_invalidate_tracker_cache(self, client_no_secret):
        """Repository-level label events don't touch the tracker read cache."""
        client, orch = client_no_secret
        client.post(
            "/api/v1/webhooks/github",
            content=json.dumps(_github_label_payload(action="created")),
            headers={"X-GitHub-Event": "label", "Content-Type": "application/json"},
        )
        mock_tracker = orch._tracker_for_project.return_value
        mock_tracker.invalidate_read_cache.assert_not_called()

    def test_unmatched_repo_does_not_invalidate_tracker_cache(self, client_no_secret):
        """Unmatched repos have no project → no tracker to invalidate."""
        client, orch = client_no_secret
        client.post(
            "/api/v1/webhooks/github",
            content=json.dumps(_github_issues_payload(repo="unknown-org/unknown-repo")),
            headers={"X-GitHub-Event": "issues", "Content-Type": "application/json"},
        )
        # _tracker_for_project must NOT be called when project is None.
        # (project is None for unmatched repos; the branch-to-issue guard checks project)
        mock_tracker = orch._tracker_for_project.return_value
        mock_tracker.invalidate_read_cache.assert_not_called()


# ---------------------------------------------------------------------------
# _webhook_should_request_refresh unit tests
# ---------------------------------------------------------------------------


class TestWebhookShouldRequestRefresh:
    """Unit tests for _webhook_should_request_refresh(event, project)."""

    def _event(self, event_type, action="", merged=False, target_branch="main",
                source_branch="", issue_number="", project_field_name=""):
        """Build a minimal WebhookEvent-like object for testing."""
        from oompah.webhooks import WebhookEvent
        return WebhookEvent(
            provider="github",
            event_type=event_type,
            action=action,
            repo_slug="org/repo",
            merged=merged,
            target_branch=target_branch,
            source_branch=source_branch,
            issue_number=issue_number,
            project_field_name=project_field_name,
        )

    def _project(self, tracked_branch="main"):
        """Build a minimal project-like mock."""
        project = MagicMock()
        project.matches_branch = lambda branch: branch == tracked_branch
        return project

    def test_pull_request_always_refreshes(self):
        from oompah.server import _webhook_should_request_refresh
        assert _webhook_should_request_refresh(
            self._event("pull_request", action="opened"), project=None
        ) is True

    def test_merge_group_always_refreshes(self):
        from oompah.server import _webhook_should_request_refresh
        assert _webhook_should_request_refresh(
            self._event("merge_group", merged=True), project=None
        ) is True

    def test_issue_comment_always_refreshes(self):
        from oompah.server import _webhook_should_request_refresh
        assert _webhook_should_request_refresh(
            self._event("issue_comment", action="created"), project=None
        ) is True

    def test_issues_opened_refreshes(self):
        from oompah.server import _webhook_should_request_refresh
        assert _webhook_should_request_refresh(
            self._event("issues", action="opened"), project=None
        ) is True

    def test_issues_closed_refreshes(self):
        from oompah.server import _webhook_should_request_refresh
        assert _webhook_should_request_refresh(
            self._event("issues", action="closed"), project=None
        ) is True

    def test_issues_labeled_refreshes(self):
        from oompah.server import _webhook_should_request_refresh
        assert _webhook_should_request_refresh(
            self._event("issues", action="labeled"), project=None
        ) is True

    def test_issues_locked_does_not_refresh(self):
        from oompah.server import _webhook_should_request_refresh
        assert _webhook_should_request_refresh(
            self._event("issues", action="locked"), project=None
        ) is False

    def test_issues_pinned_does_not_refresh(self):
        from oompah.server import _webhook_should_request_refresh
        assert _webhook_should_request_refresh(
            self._event("issues", action="pinned"), project=None
        ) is False

    def test_label_event_does_not_refresh(self):
        from oompah.server import _webhook_should_request_refresh
        assert _webhook_should_request_refresh(
            self._event("label", action="created"), project=None
        ) is False

    def test_projects_v2_item_edited_refreshes(self):
        from oompah.server import _webhook_should_request_refresh
        assert _webhook_should_request_refresh(
            self._event("projects_v2_item", action="edited"), project=None
        ) is True

    def test_projects_v2_item_created_refreshes(self):
        from oompah.server import _webhook_should_request_refresh
        assert _webhook_should_request_refresh(
            self._event("projects_v2_item", action="created"), project=None
        ) is True

    def test_projects_v2_item_reordered_does_not_refresh(self):
        from oompah.server import _webhook_should_request_refresh
        assert _webhook_should_request_refresh(
            self._event("projects_v2_item", action="reordered"), project=None
        ) is False

    def test_push_to_tracked_branch_refreshes(self):
        from oompah.server import _webhook_should_request_refresh
        project = self._project(tracked_branch="main")
        assert _webhook_should_request_refresh(
            self._event("push", target_branch="main"), project=project
        ) is True

    def test_push_to_non_tracked_branch_does_not_refresh(self):
        from oompah.server import _webhook_should_request_refresh
        project = self._project(tracked_branch="main")
        assert _webhook_should_request_refresh(
            self._event("push", target_branch="feature-x"), project=project
        ) is False

    def test_push_without_project_does_not_refresh(self):
        """Push events with no matched project are never dispatch-relevant."""
        from oompah.server import _webhook_should_request_refresh
        assert _webhook_should_request_refresh(
            self._event("push", target_branch="main"), project=None
        ) is False
