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
            forge_kind="gitlab",
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

    def test_push_hook_without_project_is_ignored(self, client_gitlab):
        """Push Hook payload with no project field (cannot determine repo_slug) is ignored."""
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

    def test_no_secret_configured_is_rejected(self):
        """A public GitLab hook must fail closed without a configured secret."""
        from oompah.server import app, _api_cache

        projects = [
            Project(
                id="proj-gl2",
                name="gitlab-no-secret",
                repo_url="https://gitlab.com/group/project.git",
                repo_path="/tmp/repos/project",
                webhook_secret=None,  # No secret!
                forge_kind="gitlab",
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
            assert resp.status_code == 401
            assert "secret is not configured" in resp.json()["error"]
            orch.request_refresh.assert_not_called()

    def test_unmatched_repo_is_silently_ignored(self, client_gitlab):
        """GitLab webhook for an unregistered repo must NOT trigger event-bus emission."""
        client, orch = client_gitlab
        # Subscribe to detect any spurious event-bus emissions
        received = []
        orch.event_bus.subscribe(
            EventType.FORGE_WEBHOOK_RECEIVED,
            lambda et, p: received.append(p),
        )
        # Payload uses a different repo slug not registered in client_gitlab
        payload = _gitlab_mr_payload(repo="unknown-group/unknown-project")
        resp = client.post(
            "/api/v1/webhooks/gitlab",
            content=json.dumps(payload),
            headers={
                "X-Gitlab-Event": "Merge Request Hook",
                "X-Gitlab-Token": "any-token-does-not-matter",
                "Content-Type": "application/json",
            },
        )
        # Must return 200 OK (ignored) — not process the event
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True
        assert data.get("action") == "ignored"
        # No refresh triggered and no event emitted for an unknown repo
        orch.request_refresh.assert_not_called()
        assert received == [], (
            "GitLab webhook from unregistered repo must not emit FORGE_WEBHOOK_RECEIVED"
        )

    # ------------------------------------------------------------------
    # Push Hook tests
    # ------------------------------------------------------------------

    def test_push_hook_with_project_processed(self, client_gitlab):
        """Push Hook with a valid project payload should be processed, not ignored."""
        client, orch = client_gitlab
        payload = {
            "ref": "refs/heads/main",
            "user_username": "tanuki",
            "project": {"path_with_namespace": "group/project"},
        }
        resp = client.post(
            "/api/v1/webhooks/gitlab",
            content=json.dumps(payload),
            headers={
                "X-Gitlab-Event": "Push Hook",
                "X-Gitlab-Token": "gl-secret",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["action"] == "processed"
        assert data["event_type"] == "Push Hook"

    def test_push_hook_without_project_ignored(self, client_gitlab):
        """Push Hook missing the project field returns 'ignored'."""
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

    # ------------------------------------------------------------------
    # Issue Hook tests
    # ------------------------------------------------------------------

    def test_issue_hook_open_processed(self, client_gitlab):
        """Issue Hook with valid payload should be processed."""
        client, orch = client_gitlab
        payload = {
            "object_attributes": {
                "iid": 5,
                "title": "New bug",
                "action": "open",
                "state": "opened",
            },
            "user": {"username": "tanuki"},
            "project": {"path_with_namespace": "group/project"},
        }
        resp = client.post(
            "/api/v1/webhooks/gitlab",
            content=json.dumps(payload),
            headers={
                "X-Gitlab-Event": "Issue Hook",
                "X-Gitlab-Token": "gl-secret",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["action"] == "processed"
        assert data["event_type"] == "Issue Hook"

    def test_issue_hook_missing_project_ignored(self, client_gitlab):
        """Issue Hook without a project field is ignored."""
        client, orch = client_gitlab
        payload = {
            "object_attributes": {"iid": 1, "title": "t", "action": "open"},
        }
        resp = client.post(
            "/api/v1/webhooks/gitlab",
            content=json.dumps(payload),
            headers={
                "X-Gitlab-Event": "Issue Hook",
                "X-Gitlab-Token": "gl-secret",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["action"] == "ignored"

    # ------------------------------------------------------------------
    # Note Hook tests
    # ------------------------------------------------------------------

    def test_note_hook_processed(self, client_gitlab):
        """Note Hook with valid payload should be processed."""
        client, orch = client_gitlab
        payload = {
            "object_attributes": {
                "id": 301,
                "note": "LGTM",
                "noteable_type": "MergeRequest",
                "action": "create",
            },
            "user": {"username": "reviewer"},
            "project": {"path_with_namespace": "group/project"},
            "merge_request": {"iid": 7},
        }
        resp = client.post(
            "/api/v1/webhooks/gitlab",
            content=json.dumps(payload),
            headers={
                "X-Gitlab-Event": "Note Hook",
                "X-Gitlab-Token": "gl-secret",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["action"] == "processed"
        assert data["event_type"] == "Note Hook"

    def test_note_hook_triggers_refresh(self, client_gitlab):
        """Note Hook should trigger an orchestrator refresh (like issue_comment)."""
        client, orch = client_gitlab
        payload = {
            "object_attributes": {
                "id": 1,
                "note": "lgtm",
                "noteable_type": "Issue",
                "action": "create",
            },
            "user": {"username": "tanuki"},
            "project": {"path_with_namespace": "group/project"},
            "issue": {"iid": 3},
        }
        resp = client.post(
            "/api/v1/webhooks/gitlab",
            content=json.dumps(payload),
            headers={
                "X-Gitlab-Event": "Note Hook",
                "X-Gitlab-Token": "gl-secret",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200
        orch.request_refresh.assert_called_once()

    # ------------------------------------------------------------------
    # Pipeline Hook tests
    # ------------------------------------------------------------------

    def test_pipeline_hook_processed(self, client_gitlab):
        """Pipeline Hook with valid payload should be processed."""
        client, orch = client_gitlab
        payload = {
            "object_attributes": {
                "id": 31,
                "ref": "main",
                "status": "success",
            },
            "user": {"username": "ci-bot"},
            "project": {"path_with_namespace": "group/project"},
        }
        resp = client.post(
            "/api/v1/webhooks/gitlab",
            content=json.dumps(payload),
            headers={
                "X-Gitlab-Event": "Pipeline Hook",
                "X-Gitlab-Token": "gl-secret",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["action"] == "processed"
        assert data["event_type"] == "Pipeline Hook"

    def test_pipeline_hook_no_refresh(self, client_gitlab):
        """Pipeline Hook events do not trigger an orchestrator refresh."""
        client, orch = client_gitlab
        payload = {
            "object_attributes": {"id": 1, "ref": "main", "status": "running"},
            "user": {"username": "ci"},
            "project": {"path_with_namespace": "group/project"},
        }
        resp = client.post(
            "/api/v1/webhooks/gitlab",
            content=json.dumps(payload),
            headers={
                "X-Gitlab-Event": "Pipeline Hook",
                "X-Gitlab-Token": "gl-secret",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200
        orch.request_refresh.assert_not_called()

    # ------------------------------------------------------------------
    # Job Hook tests
    # ------------------------------------------------------------------

    def test_job_hook_processed(self, client_gitlab):
        """Job Hook with valid payload should be processed."""
        client, orch = client_gitlab
        payload = {
            "build_id": 1977,
            "build_name": "test",
            "build_status": "success",
            "ref": "main",
            "user": {"name": "Tanuki"},
            "repository": {"homepage": "https://gitlab.com/group/project"},
        }
        resp = client.post(
            "/api/v1/webhooks/gitlab",
            content=json.dumps(payload),
            headers={
                "X-Gitlab-Event": "Job Hook",
                "X-Gitlab-Token": "gl-secret",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["action"] == "processed"
        assert data["event_type"] == "Job Hook"

    def test_job_hook_missing_homepage_ignored(self, client_gitlab):
        """Job Hook without repository homepage is ignored."""
        client, orch = client_gitlab
        payload = {
            "build_id": 1,
            "build_status": "success",
            "repository": {},
        }
        resp = client.post(
            "/api/v1/webhooks/gitlab",
            content=json.dumps(payload),
            headers={
                "X-Gitlab-Event": "Job Hook",
                "X-Gitlab-Token": "gl-secret",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["action"] == "ignored"

    # ------------------------------------------------------------------
    # Unknown hook type
    # ------------------------------------------------------------------

    def test_unknown_hook_ignored(self, client_gitlab):
        """Unrecognised GitLab hook types are ignored."""
        client, orch = client_gitlab
        resp = client.post(
            "/api/v1/webhooks/gitlab",
            content=json.dumps({"foo": "bar"}),
            headers={
                "X-Gitlab-Event": "Confidential Issue Hook",
                "X-Gitlab-Token": "gl-secret",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["action"] == "ignored"
        orch.request_refresh.assert_not_called()


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

    # ------------------------------------------------------------------
    # GitLab-specific event types
    # ------------------------------------------------------------------

    def test_gitlab_mr_hook_always_refreshes(self):
        from oompah.server import _webhook_should_request_refresh
        assert _webhook_should_request_refresh(
            self._event("Merge Request Hook", action="open"), project=None
        ) is True

    def test_gitlab_note_hook_always_refreshes(self):
        from oompah.server import _webhook_should_request_refresh
        assert _webhook_should_request_refresh(
            self._event("Note Hook", action="create"), project=None
        ) is True

    def test_gitlab_issue_hook_open_refreshes(self):
        from oompah.server import _webhook_should_request_refresh
        assert _webhook_should_request_refresh(
            self._event("Issue Hook", action="open"), project=None
        ) is True

    def test_gitlab_issue_hook_close_refreshes(self):
        from oompah.server import _webhook_should_request_refresh
        assert _webhook_should_request_refresh(
            self._event("Issue Hook", action="close"), project=None
        ) is True

    def test_gitlab_issue_hook_reopen_refreshes(self):
        from oompah.server import _webhook_should_request_refresh
        assert _webhook_should_request_refresh(
            self._event("Issue Hook", action="reopen"), project=None
        ) is True

    def test_gitlab_issue_hook_update_refreshes(self):
        from oompah.server import _webhook_should_request_refresh
        assert _webhook_should_request_refresh(
            self._event("Issue Hook", action="update"), project=None
        ) is True

    def test_gitlab_pipeline_hook_does_not_refresh(self):
        from oompah.server import _webhook_should_request_refresh
        assert _webhook_should_request_refresh(
            self._event("Pipeline Hook", action="success"), project=None
        ) is False

    def test_gitlab_job_hook_does_not_refresh(self):
        from oompah.server import _webhook_should_request_refresh
        assert _webhook_should_request_refresh(
            self._event("Job Hook", action="success"), project=None
        ) is False

    def test_gitlab_push_hook_to_tracked_branch_refreshes(self):
        from oompah.server import _webhook_should_request_refresh
        event = self._event("Push Hook", target_branch="main")
        event = type(event)(
            provider="gitlab",
            event_type="Push Hook",
            action="pushed",
            repo_slug="group/project",
            target_branch="main",
        )
        project = self._project(tracked_branch="main")
        assert _webhook_should_request_refresh(event, project=project) is True

    def test_gitlab_push_hook_to_non_tracked_branch_does_not_refresh(self):
        from oompah.server import _webhook_should_request_refresh
        from oompah.webhooks import WebhookEvent
        event = WebhookEvent(
            provider="gitlab",
            event_type="Push Hook",
            action="pushed",
            repo_slug="group/project",
            target_branch="feature-x",
        )
        project = self._project(tracked_branch="main")
        assert _webhook_should_request_refresh(event, project=project) is False


# Webhook-driven task state reconciliation
# ---------------------------------------------------------------------------


class TestWebhookInReviewReconciliation:
    """PR opened/reopened webhook marks task In Review."""

    def _make_orch_with_task(self, source_branch: str, task_state: str = "In Progress"):
        """Build a mock orchestrator with a tracker that returns one task."""
        from unittest.mock import MagicMock
        orch = MagicMock()
        orch.event_bus = EventBus()
        orch.request_refresh = MagicMock()
        orch.invalidate_merged_branches = MagicMock()
        orch.project_store = MagicMock()

        projects = [
            Project(
                id="proj-gh1",
                name="github-proj",
                repo_url="https://github.com/org/repo.git",
                repo_path="/tmp/repos/repo",
                webhook_secret=None,
            ),
        ]
        orch.project_store.list_all.return_value = projects
        orch.project_store.update = MagicMock()

        from oompah.models import Issue

        mock_issue = MagicMock(spec=Issue)
        mock_issue.identifier = source_branch
        mock_issue.state = task_state

        mock_tracker = MagicMock()
        mock_tracker.fetch_issue_detail.return_value = mock_issue
        mock_tracker.update_issue = MagicMock()
        mock_tracker.set_metadata_field = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=mock_tracker)
        # _resolve_task_for_branch is used by the updated webhook handlers
        # to support both Backlog and GitHub-backed task lookup.
        orch._resolve_task_for_branch = MagicMock(return_value=mock_issue)

        return orch, mock_tracker, mock_issue

    def test_pr_opened_marks_task_in_review(self):
        """A pull_request opened event triggers In Review marking."""
        import time
        from oompah.server import app, _api_cache

        orch, mock_tracker, mock_issue = self._make_orch_with_task(
            "feat-branch", "In Progress"
        )
        with patch("oompah.server._orchestrator", orch):
            _api_cache.invalidate("reviews:all")
            _api_cache.invalidate("issues:all")
            client = TestClient(app)
            payload = _github_pr_payload(
                action="opened", source="feat-branch", number=77
            )
            resp = client.post(
                "/api/v1/webhooks/github",
                content=json.dumps(payload),
                headers={
                    "X-GitHub-Event": "pull_request",
                    "Content-Type": "application/json",
                },
            )

        assert resp.status_code == 200
        # Give the background thread a moment to run
        for _ in range(50):
            if mock_tracker.update_issue.called:
                break
            time.sleep(0.02)

        from oompah.statuses import IN_REVIEW
        mock_tracker.update_issue.assert_called_once_with(
            "feat-branch", status=IN_REVIEW
        )

    def test_pr_reopened_marks_task_in_review(self):
        """A pull_request reopened event triggers In Review marking."""
        import time
        from oompah.server import app, _api_cache

        orch, mock_tracker, mock_issue = self._make_orch_with_task(
            "feat-branch", "Open"
        )
        with patch("oompah.server._orchestrator", orch):
            _api_cache.invalidate("reviews:all")
            _api_cache.invalidate("issues:all")
            client = TestClient(app)
            payload = _github_pr_payload(action="reopened", source="feat-branch")
            resp = client.post(
                "/api/v1/webhooks/github",
                content=json.dumps(payload),
                headers={
                    "X-GitHub-Event": "pull_request",
                    "Content-Type": "application/json",
                },
            )

        assert resp.status_code == 200
        for _ in range(50):
            if mock_tracker.update_issue.called:
                break
            time.sleep(0.02)

        from oompah.statuses import IN_REVIEW
        mock_tracker.update_issue.assert_called_once_with(
            "feat-branch", status=IN_REVIEW
        )

    def test_pr_closed_unmerged_does_not_mark_in_review(self):
        """A closed (unmerged) PR does not trigger In Review marking."""
        import time
        from oompah.server import app, _api_cache

        orch, mock_tracker, mock_issue = self._make_orch_with_task(
            "feat-branch", "In Review"
        )
        with patch("oompah.server._orchestrator", orch):
            _api_cache.invalidate("reviews:all")
            _api_cache.invalidate("issues:all")
            client = TestClient(app)
            payload = _github_pr_payload(
                action="closed", source="feat-branch", merged=False
            )
            resp = client.post(
                "/api/v1/webhooks/github",
                content=json.dumps(payload),
                headers={
                    "X-GitHub-Event": "pull_request",
                    "Content-Type": "application/json",
                },
            )

        assert resp.status_code == 200
        time.sleep(0.1)
        # No In Review update — closed without merge should not re-open
        for call in mock_tracker.update_issue.call_args_list:
            from oompah.statuses import IN_REVIEW
            assert call.kwargs.get("status") != IN_REVIEW

    def test_pr_opened_already_in_review_skips_status_update_but_writes_metadata(self):
        """PR opened for a task already In Review skips status update but still writes metadata."""
        import time
        from oompah.server import app, _api_cache
        from unittest.mock import patch as _patch

        orch, mock_tracker, mock_issue = self._make_orch_with_task(
            "feat-branch", "In Review"
        )

        with _patch("oompah.server._orchestrator", orch):
            _api_cache.invalidate("reviews:all")
            _api_cache.invalidate("issues:all")
            client = TestClient(app)
            payload = _github_pr_payload(action="opened", source="feat-branch", number=99)
            resp = client.post(
                "/api/v1/webhooks/github",
                content=json.dumps(payload),
                headers={
                    "X-GitHub-Event": "pull_request",
                    "Content-Type": "application/json",
                },
            )

        assert resp.status_code == 200
        time.sleep(0.1)
        # Status update must NOT be called (already In Review)
        mock_tracker.update_issue.assert_not_called()
        # Metadata writes ARE still expected
        assert mock_tracker.set_metadata_field.called


class TestWebhookMergedReconciliation:
    """PR closed+merged webhook marks task Merged."""

    def _make_orch_with_task(self, source_branch: str, task_state: str = "In Review"):
        from unittest.mock import MagicMock
        orch = MagicMock()
        orch.event_bus = EventBus()
        orch.request_refresh = MagicMock()
        orch.invalidate_merged_branches = MagicMock()
        orch.project_store = MagicMock()

        projects = [
            Project(
                id="proj-gh1",
                name="github-proj",
                repo_url="https://github.com/org/repo.git",
                repo_path="/tmp/repos/repo",
                webhook_secret=None,
            ),
        ]
        orch.project_store.list_all.return_value = projects
        orch.project_store.update = MagicMock()

        from oompah.models import Issue

        mock_issue = MagicMock(spec=Issue)
        mock_issue.identifier = source_branch
        mock_issue.state = task_state

        mock_tracker = MagicMock()
        mock_tracker.fetch_issue_detail.return_value = mock_issue
        mock_tracker.update_issue = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=mock_tracker)
        # _resolve_task_for_branch is used by the updated webhook handlers
        # to support both Backlog and GitHub-backed task lookup.
        orch._resolve_task_for_branch = MagicMock(return_value=mock_issue)

        return orch, mock_tracker

    def test_pr_merged_marks_task_merged(self):
        """A pull_request closed+merged event marks the task Merged."""
        import time
        from oompah.server import app, _api_cache

        orch, mock_tracker = self._make_orch_with_task("feat-branch", "In Review")
        with patch("oompah.server._orchestrator", orch):
            _api_cache.invalidate("reviews:all")
            _api_cache.invalidate("issues:all")
            client = TestClient(app)
            payload = _github_pr_payload(
                action="closed", source="feat-branch", merged=True
            )
            resp = client.post(
                "/api/v1/webhooks/github",
                content=json.dumps(payload),
                headers={
                    "X-GitHub-Event": "pull_request",
                    "Content-Type": "application/json",
                },
            )

        assert resp.status_code == 200
        for _ in range(50):
            if mock_tracker.update_issue.called:
                break
            time.sleep(0.02)

        from oompah.statuses import MERGED
        mock_tracker.update_issue.assert_called_once_with("feat-branch", status=MERGED)

    def test_pr_already_merged_skips_update(self):
        """PR merged webhook for an already-Merged task is a no-op."""
        import time
        from oompah.server import app, _api_cache

        orch, mock_tracker = self._make_orch_with_task("feat-branch", "Merged")
        with patch("oompah.server._orchestrator", orch):
            _api_cache.invalidate("reviews:all")
            _api_cache.invalidate("issues:all")
            client = TestClient(app)
            payload = _github_pr_payload(
                action="closed", source="feat-branch", merged=True
            )
            resp = client.post(
                "/api/v1/webhooks/github",
                content=json.dumps(payload),
                headers={
                    "X-GitHub-Event": "pull_request",
                    "Content-Type": "application/json",
                },
            )

        assert resp.status_code == 200
        time.sleep(0.1)
        mock_tracker.update_issue.assert_not_called()

    def test_pr_closed_without_merge_does_not_mark_merged(self):
        """PR closed without merge does not trigger a Merged update."""
        import time
        from oompah.server import app, _api_cache

        orch, mock_tracker = self._make_orch_with_task("feat-branch", "In Review")
        with patch("oompah.server._orchestrator", orch):
            _api_cache.invalidate("reviews:all")
            _api_cache.invalidate("issues:all")
            client = TestClient(app)
            payload = _github_pr_payload(
                action="closed", source="feat-branch", merged=False
            )
            resp = client.post(
                "/api/v1/webhooks/github",
                content=json.dumps(payload),
                headers={
                    "X-GitHub-Event": "pull_request",
                    "Content-Type": "application/json",
                },
            )

        assert resp.status_code == 200
        time.sleep(0.1)
        from oompah.statuses import MERGED
        for call in mock_tracker.update_issue.call_args_list:
            assert call.kwargs.get("status") != MERGED


# ---------------------------------------------------------------------------
# Status-label authorization tests
# ---------------------------------------------------------------------------


def _github_labeled_payload(
    action: str = "labeled",
    number: int = 42,
    issue_author: str = "issue-creator",
    label_name: str = "oompah:status:open",
    sender_login: str = "unauthorized-user",
    repo: str = "org/repo",
) -> dict:
    """Build a GitHub issues.labeled / issues.unlabeled payload."""
    return {
        "action": action,
        "issue": {
            "number": number,
            "title": "Test issue",
            "user": {"login": issue_author},
        },
        "label": {
            "name": label_name,
            "color": "e4e669",
        },
        "repository": {"full_name": repo},
        "sender": {"login": sender_login},
    }


def _make_orch_with_tracker(projects=None, mock_tracker=None):
    """Build a mock orchestrator with a tracker attached."""
    if projects is None:
        projects = [
            Project(
                id="proj-gh1",
                name="github-proj",
                repo_url="https://github.com/org/repo.git",
                repo_path="/tmp/repos/repo",
                webhook_secret=None,
                status_label_authorized_logins=[],
            ),
        ]
    orch = _make_mock_orchestrator(projects=projects)
    if mock_tracker is not None:
        orch._tracker_for_project = MagicMock(return_value=mock_tracker)
    return orch


class TestStatusLabelActorWebhookPayload:
    """The server event payload includes label_actor for issues.labeled events."""

    def test_labeled_event_includes_label_actor_in_payload(self):
        """label_actor from sender is included in the emitted event payload."""
        from oompah.server import app, _api_cache
        from oompah.events import EventType

        received_payloads = []
        orch = _make_orch_with_tracker()
        orch.event_bus.subscribe(
            EventType.FORGE_WEBHOOK_RECEIVED,
            lambda et, p: received_payloads.append(p),
        )

        with patch("oompah.server._orchestrator", orch):
            _api_cache.invalidate("issues:all")
            client = TestClient(app)
            payload = _github_labeled_payload(
                action="labeled",
                sender_login="alice",
                label_name="oompah:status:open",
            )
            resp = client.post(
                "/api/v1/webhooks/github",
                content=json.dumps(payload),
                headers={
                    "X-GitHub-Event": "issues",
                    "Content-Type": "application/json",
                },
            )

        assert resp.status_code == 200
        assert len(received_payloads) == 1
        ep = received_payloads[0]
        assert ep["label_actor"] == "alice"
        assert ep["label_name"] == "oompah:status:open"

    def test_non_labeled_event_omits_label_actor(self):
        """Non-labeled issues events do not include label_actor in the payload."""
        from oompah.server import app, _api_cache
        from oompah.events import EventType

        received_payloads = []
        orch = _make_orch_with_tracker()
        orch.event_bus.subscribe(
            EventType.FORGE_WEBHOOK_RECEIVED,
            lambda et, p: received_payloads.append(p),
        )

        with patch("oompah.server._orchestrator", orch):
            _api_cache.invalidate("issues:all")
            client = TestClient(app)
            payload = _github_issues_payload(action="opened")
            resp = client.post(
                "/api/v1/webhooks/github",
                content=json.dumps(payload),
                headers={
                    "X-GitHub-Event": "issues",
                    "Content-Type": "application/json",
                },
            )

        assert resp.status_code == 200
        assert len(received_payloads) == 1
        ep = received_payloads[0]
        assert "label_actor" not in ep


class TestUnauthorizedStatusLabelRevert:
    """Unauthorized oompah:status:* label changes trigger revert + comment."""

    def _make_orch_with_tracker_for_revert(self, authorized_logins=None):
        """Build orch with a tracker that supports revert operations."""
        from unittest.mock import MagicMock

        project = Project(
            id="proj-gh1",
            name="github-proj",
            repo_url="https://github.com/org/repo.git",
            repo_path="/tmp/repos/repo",
            webhook_secret=None,
            tracker_kind="github_issues",
            status_label_authorized_logins=authorized_logins or [],
            tracker_owner="org",
            tracker_repo="repo",
        )
        mock_tracker = MagicMock()
        mock_tracker._set_status_label = MagicMock()
        mock_tracker.add_comment = MagicMock()
        mock_tracker._trusted_status_ledger = {}
        mock_tracker._untrusted_status_issues = set()
        mock_tracker.record_untrusted_status_label_change = MagicMock()
        mock_tracker.record_trusted_status = MagicMock()
        mock_tracker.remove_label = MagicMock()
        mock_tracker.identifier_for_number = MagicMock(
            side_effect=lambda number: f"org/repo#{number}"
        )

        orch = _make_mock_orchestrator(projects=[project])
        orch._tracker_for_project = MagicMock(return_value=mock_tracker)
        return orch, mock_tracker, project

    def test_unauthorized_labeled_triggers_revert(self):
        """An unauthorized actor applying oompah:status:open triggers a revert."""
        import time
        from oompah.server import app, _api_cache
        from unittest.mock import patch as mpatch

        orch, mock_tracker, project = self._make_orch_with_tracker_for_revert(
            authorized_logins=[]
        )

        with mpatch("oompah.server._orchestrator", orch):
            with mpatch.dict("os.environ", {"OOMPAH_BOT_LOGIN": "oompah"}):
                _api_cache.invalidate("issues:all")
                client = TestClient(app)
                payload = _github_labeled_payload(
                    action="labeled",
                    number=42,
                    sender_login="unauthorized-user",  # not bot, not in allowlist
                    label_name="oompah:status:open",
                )
                resp = client.post(
                    "/api/v1/webhooks/github",
                    content=json.dumps(payload),
                    headers={
                        "X-GitHub-Event": "issues",
                        "Content-Type": "application/json",
                    },
                )

        assert resp.status_code == 200
        # Wait for background thread to complete
        for _ in range(100):
            if (
                mock_tracker._set_status_label.called
                or mock_tracker.add_comment.called
            ):
                break
            time.sleep(0.02)

        # The revert thread should have attempted to set status back or add comment
        assert (
            mock_tracker._set_status_label.called
            or mock_tracker.add_comment.called
        ), "Revert or comment should have been called"
        # Comment explaining the unauthorized change should have been posted
        assert mock_tracker.add_comment.called
        comment_call_args = mock_tracker.add_comment.call_args
        comment_body = comment_call_args[0][1]
        assert "unauthorized" in comment_body.lower() or "Unauthorized" in comment_body

    def test_authorized_bot_labeled_does_not_trigger_revert(self):
        """The oompah bot applying a status label is authorized — no revert."""
        import time
        from oompah.server import app, _api_cache
        from unittest.mock import patch as mpatch

        orch, mock_tracker, project = self._make_orch_with_tracker_for_revert(
            authorized_logins=[]
        )

        with mpatch("oompah.server._orchestrator", orch):
            with mpatch.dict("os.environ", {"OOMPAH_BOT_LOGIN": "oompah"}):
                _api_cache.invalidate("issues:all")
                client = TestClient(app)
                payload = _github_labeled_payload(
                    action="labeled",
                    number=42,
                    sender_login="oompah",  # the bot — authorized
                    label_name="oompah:status:open",
                )
                resp = client.post(
                    "/api/v1/webhooks/github",
                    content=json.dumps(payload),
                    headers={
                        "X-GitHub-Event": "issues",
                        "Content-Type": "application/json",
                    },
                )

        assert resp.status_code == 200
        # Give enough time for any (incorrect) background thread to run
        time.sleep(0.15)
        # No revert should have been triggered
        mock_tracker._set_status_label.assert_not_called()
        mock_tracker.add_comment.assert_not_called()

    def test_authorized_owner_in_allowlist_does_not_trigger_revert(self):
        """A project owner in the allowlist applying a status label is authorized."""
        import time
        from oompah.server import app, _api_cache
        from unittest.mock import patch as mpatch

        orch, mock_tracker, project = self._make_orch_with_tracker_for_revert(
            authorized_logins=["alice"]
        )

        with mpatch("oompah.server._orchestrator", orch):
            with mpatch.dict("os.environ", {"OOMPAH_BOT_LOGIN": "oompah"}):
                _api_cache.invalidate("issues:all")
                client = TestClient(app)
                payload = _github_labeled_payload(
                    action="labeled",
                    number=42,
                    sender_login="alice",  # in allowlist
                    label_name="oompah:status:open",
                )
                resp = client.post(
                    "/api/v1/webhooks/github",
                    content=json.dumps(payload),
                    headers={
                        "X-GitHub-Event": "issues",
                        "Content-Type": "application/json",
                    },
                )

        assert resp.status_code == 200
        time.sleep(0.15)
        mock_tracker._set_status_label.assert_not_called()
        mock_tracker.add_comment.assert_not_called()

    def test_tracker_owner_labeled_records_trusted_status_without_revert(self):
        """The tracker owner can apply status labels and updates the trusted ledger."""
        import time
        from oompah.server import app, _api_cache
        from unittest.mock import patch as mpatch

        orch, mock_tracker, project = self._make_orch_with_tracker_for_revert(
            authorized_logins=[]
        )

        with mpatch("oompah.server._orchestrator", orch):
            with mpatch.dict("os.environ", {"OOMPAH_BOT_LOGIN": "oompah"}):
                _api_cache.invalidate("issues:all")
                client = TestClient(app)
                payload = _github_labeled_payload(
                    action="labeled",
                    number=42,
                    sender_login="org",
                    label_name="oompah:status:open",
                )
                resp = client.post(
                    "/api/v1/webhooks/github",
                    content=json.dumps(payload),
                    headers={
                        "X-GitHub-Event": "issues",
                        "Content-Type": "application/json",
                    },
                )

        assert resp.status_code == 200
        time.sleep(0.15)
        mock_tracker._set_status_label.assert_not_called()
        mock_tracker.add_comment.assert_not_called()
        mock_tracker.record_trusted_status.assert_called_once_with(42, "Open")

    @pytest.mark.parametrize(
        ("label_name", "status"),
        [
            ("oompah:status:proposed", "Proposed"),
            ("oompah:status:backlog", "Backlog"),
            ("oompah:status:archived", "Archived"),
        ],
    )
    def test_oompah_owned_backfill_label_event_does_not_trigger_revert(
        self, label_name, status
    ):
        """Known oompah-owned backfill events bypass unauthorized handling."""
        import time
        from oompah.server import app, _api_cache
        from unittest.mock import patch as mpatch

        orch, mock_tracker, project = self._make_orch_with_tracker_for_revert(
            authorized_logins=[]
        )
        mock_tracker._trusted_status_ledger[42] = status

        with mpatch("oompah.server._orchestrator", orch):
            with mpatch.dict("os.environ", {"OOMPAH_BOT_LOGIN": "oompah"}):
                _api_cache.invalidate("issues:all")
                client = TestClient(app)
                payload = _github_labeled_payload(
                    action="labeled",
                    number=42,
                    sender_login="unexpected-app-actor",
                    label_name=label_name,
                )
                resp = client.post(
                    "/api/v1/webhooks/github",
                    content=json.dumps(payload),
                    headers={
                        "X-GitHub-Event": "issues",
                        "Content-Type": "application/json",
                    },
                )

        assert resp.status_code == 200
        time.sleep(0.15)
        mock_tracker._set_status_label.assert_not_called()
        mock_tracker.add_comment.assert_not_called()
        mock_tracker.record_untrusted_status_label_change.assert_not_called()
        mock_tracker.record_trusted_status.assert_called_once_with(42, status)

    def test_oompah_owned_backfill_label_event_is_idempotent(self):
        """Repeated delivery of a correlated webhook stays quiet."""
        import time
        from oompah.server import app, _api_cache
        from unittest.mock import patch as mpatch

        orch, mock_tracker, project = self._make_orch_with_tracker_for_revert(
            authorized_logins=[]
        )
        mock_tracker._trusted_status_ledger[42] = "Proposed"

        with mpatch("oompah.server._orchestrator", orch):
            with mpatch.dict("os.environ", {"OOMPAH_BOT_LOGIN": "oompah"}):
                _api_cache.invalidate("issues:all")
                client = TestClient(app)
                payload = _github_labeled_payload(
                    action="labeled",
                    number=42,
                    sender_login="unexpected-app-actor",
                    label_name="oompah:status:proposed",
                )
                for _ in range(2):
                    resp = client.post(
                        "/api/v1/webhooks/github",
                        content=json.dumps(payload),
                        headers={
                            "X-GitHub-Event": "issues",
                            "Content-Type": "application/json",
                        },
                    )
                    assert resp.status_code == 200

        time.sleep(0.15)
        mock_tracker._set_status_label.assert_not_called()
        mock_tracker.add_comment.assert_not_called()
        mock_tracker.record_untrusted_status_label_change.assert_not_called()
        assert mock_tracker.record_trusted_status.call_count == 2

    def test_external_status_label_mismatch_still_triggers_revert(self):
        """A different status than the ledger remains an unauthorized edit."""
        import time
        from oompah.server import app, _api_cache
        from unittest.mock import patch as mpatch

        orch, mock_tracker, project = self._make_orch_with_tracker_for_revert(
            authorized_logins=[]
        )
        mock_tracker._trusted_status_ledger[42] = "Backlog"

        with mpatch("oompah.server._orchestrator", orch):
            with mpatch.dict("os.environ", {"OOMPAH_BOT_LOGIN": "oompah"}):
                _api_cache.invalidate("issues:all")
                client = TestClient(app)
                payload = _github_labeled_payload(
                    action="labeled",
                    number=42,
                    sender_login="attacker",
                    label_name="oompah:status:open",
                )
                resp = client.post(
                    "/api/v1/webhooks/github",
                    content=json.dumps(payload),
                    headers={
                        "X-GitHub-Event": "issues",
                        "Content-Type": "application/json",
                    },
                )

        assert resp.status_code == 200
        for _ in range(100):
            if mock_tracker.add_comment.called:
                break
            time.sleep(0.02)

        assert mock_tracker.add_comment.called
        mock_tracker.record_untrusted_status_label_change.assert_called_once_with(
            42,
            "oompah:status:open",
            "attacker",
            "labeled",
        )
        mock_tracker.record_trusted_status.assert_not_called()

    def test_non_status_label_does_not_trigger_revert(self):
        """Non-oompah:status:* label changes do not trigger authorization checks."""
        import time
        from oompah.server import app, _api_cache
        from unittest.mock import patch as mpatch

        orch, mock_tracker, project = self._make_orch_with_tracker_for_revert()

        with mpatch("oompah.server._orchestrator", orch):
            _api_cache.invalidate("issues:all")
            client = TestClient(app)
            payload = _github_labeled_payload(
                action="labeled",
                number=42,
                sender_login="anyone",
                label_name="bug",  # not a status label
            )
            resp = client.post(
                "/api/v1/webhooks/github",
                content=json.dumps(payload),
                headers={
                    "X-GitHub-Event": "issues",
                    "Content-Type": "application/json",
                },
            )

        assert resp.status_code == 200
        time.sleep(0.15)
        mock_tracker._set_status_label.assert_not_called()
        mock_tracker.add_comment.assert_not_called()

    def test_unlabeled_unauthorized_triggers_revert(self):
        """Unauthorized removal of oompah:status:* label triggers revert."""
        import time
        from oompah.server import app, _api_cache
        from unittest.mock import patch as mpatch

        orch, mock_tracker, project = self._make_orch_with_tracker_for_revert(
            authorized_logins=[]
        )

        with mpatch("oompah.server._orchestrator", orch):
            with mpatch.dict("os.environ", {"OOMPAH_BOT_LOGIN": "oompah"}):
                _api_cache.invalidate("issues:all")
                client = TestClient(app)
                payload = _github_labeled_payload(
                    action="unlabeled",
                    number=99,
                    sender_login="attacker",
                    label_name="oompah:status:open",
                )
                resp = client.post(
                    "/api/v1/webhooks/github",
                    content=json.dumps(payload),
                    headers={
                        "X-GitHub-Event": "issues",
                        "Content-Type": "application/json",
                    },
                )

        assert resp.status_code == 200
        for _ in range(100):
            if mock_tracker.add_comment.called:
                break
            time.sleep(0.02)

        assert mock_tracker.add_comment.called

    def test_unauthorized_comment_is_rate_limited_per_issue_actor(self):
        """Repeated unauthorized label events do not post repeated comments."""
        from oompah.server import (
            _revert_unauthorized_status_label_change,
            _unauthorized_status_comment_last_post,
        )
        from oompah.webhooks import WebhookEvent

        orch, mock_tracker, project = self._make_orch_with_tracker_for_revert(
            authorized_logins=[]
        )
        event = WebhookEvent(
            provider="github",
            event_type="issues",
            action="labeled",
            repo_slug="org/repo",
            issue_number="42",
            label_name="oompah:status:open",
            label_actor="attacker",
        )

        _unauthorized_status_comment_last_post.clear()
        try:
            _revert_unauthorized_status_label_change(orch, event, project)
            _revert_unauthorized_status_label_change(orch, event, project)
        finally:
            _unauthorized_status_comment_last_post.clear()

        assert mock_tracker.add_comment.call_count == 1

    def test_labeled_without_trusted_ledger_removes_label(self):
        """A no-ledger labeled revert removes only the untrusted label."""
        from oompah.server import _do_revert_status_label

        _orch, mock_tracker, _project = self._make_orch_with_tracker_for_revert(
            authorized_logins=[]
        )

        _do_revert_status_label(
            mock_tracker,
            "42",
            "oompah:status:open",
            "labeled",
        )

        mock_tracker._set_status_label.assert_not_called()
        mock_tracker.remove_label.assert_called_once_with(
            "org/repo#42",
            "oompah:status:open",
        )


class TestPollingStatusLabelValidation:
    """fetch_candidate_issues skips issues with untrusted status labels."""

    def _make_tracker(self):
        from oompah.github_tracker import GitHubIssueTracker, GitHubAuth
        auth = MagicMock(spec=GitHubAuth)
        auth.get_token.return_value = "fake-token"
        tracker = GitHubIssueTracker(
            owner="org",
            repo="repo",
            active_states=["Open"],
            terminal_states=["Done", "Archived"],
            auth=auth,
        )
        return tracker

    def _make_gh_issue(self, number: int, status_label: str = "oompah:status:open") -> dict:
        return {
            "number": number,
            "title": f"Issue #{number}",
            "body": "",
            "state": "open",
            "labels": [
                {"name": status_label, "color": "e4e669"}
            ],
            "user": {"login": "creator"},
            "assignees": [],
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "html_url": f"https://github.com/org/repo/issues/{number}",
            "pull_request": None,
        }

    def test_untrusted_issue_excluded_from_candidates(self):
        """Issues in _untrusted_status_issues are excluded from fetch_candidate_issues."""
        import httpx
        tracker = self._make_tracker()

        gh_issues = [
            self._make_gh_issue(1),
            self._make_gh_issue(2),
        ]

        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.is_success = True
        mock_resp.headers = httpx.Headers({})
        mock_resp.json.return_value = gh_issues
        mock_resp.request = MagicMock()

        # Mark issue #2 as untrusted
        tracker._untrusted_status_issues.add(2)

        with patch.object(tracker._client._http, "request", return_value=mock_resp):
            # Also patch _ensure_status_label to avoid API calls
            with patch.object(tracker, "_ensure_status_label", side_effect=lambda x: x):
                candidates = tracker.fetch_candidate_issues()

        numbers = [int(c.identifier.rsplit("#", 1)[-1]) for c in candidates]
        assert 2 not in numbers, "Issue #2 should be excluded (untrusted)"
        assert 1 in numbers, "Issue #1 should be included (trusted)"

    def test_trusted_issue_is_included(self):
        """Issues NOT in _untrusted_status_issues are included normally."""
        import httpx
        tracker = self._make_tracker()

        gh_issues = [self._make_gh_issue(3)]

        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.is_success = True
        mock_resp.headers = httpx.Headers({})
        mock_resp.json.return_value = gh_issues
        mock_resp.request = MagicMock()

        # No untrusted issues
        with patch.object(tracker._client._http, "request", return_value=mock_resp):
            with patch.object(tracker, "_ensure_status_label", side_effect=lambda x: x):
                candidates = tracker.fetch_candidate_issues()

        assert len(candidates) == 1

    def test_record_trusted_status_updates_ledger(self):
        """record_trusted_status stores the status in the ledger."""
        tracker = self._make_tracker()
        tracker.record_trusted_status(42, "Open")
        assert tracker._trusted_status_ledger[42] == "Open"
        assert 42 not in tracker._untrusted_status_issues

    def test_record_trusted_status_clears_untrusted_set(self):
        """record_trusted_status removes issue from untrusted set."""
        tracker = self._make_tracker()
        tracker._untrusted_status_issues.add(42)
        tracker.record_trusted_status(42, "Open")
        assert 42 not in tracker._untrusted_status_issues

    def test_record_untrusted_status_label_change_adds_to_set(self):
        """record_untrusted_status_label_change marks issue as untrusted."""
        tracker = self._make_tracker()
        tracker._trusted_status_ledger[5] = "Backlog"
        tracker.record_untrusted_status_label_change(5, "oompah:status:open", "attacker", "labeled")
        assert 5 in tracker._untrusted_status_issues
        # Ledger entry should be removed
        assert 5 not in tracker._trusted_status_ledger

    def test_set_status_label_records_trusted_status(self):
        """_set_status_label records the new status in the trusted ledger."""
        import httpx
        tracker = self._make_tracker()

        # Mock the label operations
        mock_labels_resp = MagicMock(spec=httpx.Response)
        mock_labels_resp.status_code = 200
        mock_labels_resp.is_success = True
        mock_labels_resp.headers = httpx.Headers({})
        mock_labels_resp.json.return_value = []
        mock_labels_resp.request = MagicMock()

        mock_post_resp = MagicMock(spec=httpx.Response)
        mock_post_resp.status_code = 200
        mock_post_resp.is_success = True
        mock_post_resp.headers = httpx.Headers({})
        mock_post_resp.json.return_value = {}
        mock_post_resp.request = MagicMock()

        with patch.object(tracker._client._http, "request", return_value=mock_labels_resp):
            tracker._set_status_label(7, "Open")

        assert tracker._trusted_status_ledger.get(7) == "Open"
        assert 7 not in tracker._untrusted_status_issues


class TestValidateStatusLabelActor:
    """Tests for GitHubIssueTracker.validate_status_label_actor()."""

    def _make_tracker(self):
        from oompah.github_tracker import GitHubIssueTracker, GitHubAuth
        auth = MagicMock(spec=GitHubAuth)
        auth.get_token.return_value = "fake-token"
        return GitHubIssueTracker(
            owner="org",
            repo="repo",
            active_states=["Open"],
            terminal_states=["Done", "Archived"],
            auth=auth,
        )

    def _make_mock_events_response(self, events_data, headers=None):
        import httpx
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.is_success = True
        mock_resp.headers = httpx.Headers(headers or {})
        mock_resp.json.return_value = events_data
        mock_resp.request = MagicMock()
        return mock_resp

    def test_authorized_actor_returns_true(self):
        """When the most recent labeled event was by an authorized actor, returns True."""
        tracker = self._make_tracker()
        events = [
            {
                "event": "labeled",
                "label": {"name": "oompah:status:open"},
                "actor": {"login": "oompah"},
                "created_at": "2024-01-01T00:00:00Z",
            }
        ]
        mock_resp = self._make_mock_events_response(events)
        with patch.object(tracker._client._http, "request", return_value=mock_resp):
            result = tracker.validate_status_label_actor(
                42, "Open", frozenset({"oompah"})
            )
        assert result is True

    def test_unauthorized_actor_returns_false(self):
        """When the most recent labeled event was by an unauthorized actor, returns False."""
        tracker = self._make_tracker()
        events = [
            {
                "event": "labeled",
                "label": {"name": "oompah:status:open"},
                "actor": {"login": "attacker"},
                "created_at": "2024-01-01T00:00:00Z",
            }
        ]
        mock_resp = self._make_mock_events_response(events)
        with patch.object(tracker._client._http, "request", return_value=mock_resp):
            result = tracker.validate_status_label_actor(
                42, "Open", frozenset({"oompah"})
            )
        assert result is False

    def test_no_labeled_events_returns_true(self):
        """When there are no labeled events, treat as trusted (can't verify)."""
        tracker = self._make_tracker()
        events = []  # No labeled events at all
        mock_resp = self._make_mock_events_response(events)
        with patch.object(tracker._client._http, "request", return_value=mock_resp):
            result = tracker.validate_status_label_actor(
                42, "Open", frozenset({"oompah"})
            )
        assert result is True

    def test_api_failure_returns_true(self):
        """API failure to fetch events treats the issue as trusted (don't block dispatch)."""
        from oompah.tracker import TrackerError
        tracker = self._make_tracker()
        with patch.object(
            tracker._client,
            "request_paginated",
            side_effect=TrackerError("API unavailable"),
        ):
            result = tracker.validate_status_label_actor(
                42, "Open", frozenset({"oompah"})
            )
        assert result is True

    def test_most_recent_labeled_event_is_checked(self):
        """Multiple labeled events: only the most recent one is authoritative."""
        tracker = self._make_tracker()
        events = [
            {
                "event": "labeled",
                "label": {"name": "oompah:status:open"},
                "actor": {"login": "oompah"},  # authorized, but older
                "created_at": "2024-01-01T00:00:00Z",
            },
            {
                "event": "labeled",
                "label": {"name": "oompah:status:open"},
                "actor": {"login": "attacker"},  # unauthorized, but more recent
                "created_at": "2024-01-02T00:00:00Z",
            },
        ]
        mock_resp = self._make_mock_events_response(events)
        with patch.object(tracker._client._http, "request", return_value=mock_resp):
            result = tracker.validate_status_label_actor(
                42, "Open", frozenset({"oompah"})
            )
        # The most recent event was by "attacker" — unauthorized
        assert result is False

    def test_authorized_set_includes_project_owners(self):
        """Project owners in authorized set are treated as trusted."""
        tracker = self._make_tracker()
        events = [
            {
                "event": "labeled",
                "label": {"name": "oompah:status:open"},
                "actor": {"login": "alice"},
                "created_at": "2024-01-01T00:00:00Z",
            }
        ]
        mock_resp = self._make_mock_events_response(events)
        with patch.object(tracker._client._http, "request", return_value=mock_resp):
            result = tracker.validate_status_label_actor(
                42, "Open", frozenset({"oompah", "alice"})  # alice is authorized
            )
        assert result is True


# ---------------------------------------------------------------------------
# GitLab webhook: deduplication
# ---------------------------------------------------------------------------


class TestGitLabWebhookDedup:
    """Tests for event deduplication in POST /api/v1/webhooks/gitlab."""

    def _mr_payload(self, iid=1, action="open", state="opened"):
        return {
            "object_attributes": {
                "iid": iid,
                "title": "MR title",
                "action": action,
                "state": state,
                "source_branch": "feat",
                "target_branch": "main",
            },
            "user": {"username": "dev"},
            "project": {"path_with_namespace": "group/project"},
        }

    def _post(self, client, payload, event_uuid=None):
        headers = {
            "X-Gitlab-Event": "Merge Request Hook",
            "X-Gitlab-Token": "gl-secret",
            "Content-Type": "application/json",
        }
        if event_uuid:
            headers["X-Gitlab-Event-UUID"] = event_uuid
        return client.post(
            "/api/v1/webhooks/gitlab",
            content=json.dumps(payload),
            headers=headers,
        )

    def test_duplicate_uuid_suppressed(self, client_gitlab):
        """Second delivery with same X-Gitlab-Event-UUID returns 'deduplicated'."""
        from oompah.webhooks import GitLabEventDedup
        from oompah.server import set_gitlab_hook_manager

        client, orch = client_gitlab
        dedup = GitLabEventDedup()
        with patch("oompah.server._gitlab_event_dedup", dedup):
            payload = self._mr_payload()
            resp1 = self._post(client, payload, event_uuid="uuid-abc-1")
            assert resp1.status_code == 200
            assert resp1.json()["action"] == "processed"

            resp2 = self._post(client, payload, event_uuid="uuid-abc-1")
            assert resp2.status_code == 200
            assert resp2.json()["action"] == "deduplicated"

    def test_different_uuids_both_processed(self, client_gitlab):
        """Two deliveries with different UUIDs are both processed."""
        from oompah.webhooks import GitLabEventDedup
        client, orch = client_gitlab
        dedup = GitLabEventDedup()
        with patch("oompah.server._gitlab_event_dedup", dedup):
            payload = self._mr_payload()
            resp1 = self._post(client, payload, event_uuid="uuid-1")
            resp2 = self._post(client, payload, event_uuid="uuid-2")
            assert resp1.json()["action"] == "processed"
            assert resp2.json()["action"] == "processed"

    def test_no_dedup_when_dedup_disabled(self, client_gitlab):
        """When _gitlab_event_dedup is None, all events pass through."""
        client, orch = client_gitlab
        with patch("oompah.server._gitlab_event_dedup", None):
            payload = self._mr_payload()
            for _ in range(3):
                resp = self._post(client, payload)
                assert resp.json()["action"] == "processed"

    def test_fingerprint_dedup_without_uuid(self, client_gitlab):
        """Without X-Gitlab-Event-UUID, fingerprint dedup suppresses duplicate."""
        from oompah.webhooks import GitLabEventDedup
        client, orch = client_gitlab
        dedup = GitLabEventDedup()
        with patch("oompah.server._gitlab_event_dedup", dedup):
            payload = self._mr_payload(iid=5, action="open")
            resp1 = self._post(client, payload)  # no UUID header
            assert resp1.json()["action"] == "processed"

            resp2 = self._post(client, payload)  # same payload, no UUID
            assert resp2.json()["action"] == "deduplicated"


# ---------------------------------------------------------------------------
# GET /api/v1/webhooks/gitlab/status
# ---------------------------------------------------------------------------


class TestGitLabWebhookStatusEndpoint:
    """Tests for GET /api/v1/webhooks/gitlab/status."""

    def test_returns_200_when_manager_not_set(self, client_gitlab):
        """When manager is not initialised, endpoint returns running=false."""
        client, _orch = client_gitlab
        with patch("oompah.server._gitlab_hook_manager", None):
            resp = client.get("/api/v1/webhooks/gitlab/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["running"] is False
        assert data["configured"] is False

    def test_returns_manager_status(self, client_gitlab):
        """When manager is set, endpoint returns its status snapshot."""
        from unittest.mock import MagicMock
        client, _orch = client_gitlab

        fake_manager = MagicMock()
        fake_manager.status = {
            "running": True,
            "configured": True,
            "detail": "",
            "webhook_url": "https://oompah.example.com/api/v1/webhooks/gitlab",
            "projects": {
                "p1": {
                    "name": "my-proj",
                    "hook_id": 7,
                    "healthy": True,
                    "last_error": "",
                }
            },
        }
        with patch("oompah.server._gitlab_hook_manager", fake_manager):
            resp = client.get("/api/v1/webhooks/gitlab/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["running"] is True
        assert data["configured"] is True
        assert data["projects"]["p1"]["healthy"] is True


# ---------------------------------------------------------------------------
# attach_gitlab_hook_alerts (bootstrap)
# ---------------------------------------------------------------------------


class TestAttachGitlabHookAlerts:
    """Tests for attach_gitlab_hook_alerts() in oompah.bootstrap."""

    def test_callback_updates_orchestrator_alerts(self):
        from unittest.mock import MagicMock
        from oompah.bootstrap import attach_gitlab_hook_alerts
        from oompah.webhooks import GitLabHookManager

        orch = MagicMock()
        orch._alerts = []
        manager = GitLabHookManager()
        attach_gitlab_hook_alerts(orch, manager)

        # Simulate reconcile with an unhealthy project
        status = {
            "configured": True,
            "projects": {
                "p1": {"name": "gl-proj", "healthy": False, "last_error": "connection refused"}
            },
        }
        manager._status_callback(status)

        assert len(orch._alerts) == 1
        assert orch._alerts[0]["source"] == "gitlab_hook_manager:p1"

    def test_callback_clears_stale_alerts_on_recovery(self):
        from unittest.mock import MagicMock
        from oompah.bootstrap import attach_gitlab_hook_alerts
        from oompah.webhooks import GitLabHookManager

        orch = MagicMock()
        orch._alerts = []
        manager = GitLabHookManager()
        attach_gitlab_hook_alerts(orch, manager)

        # First: unhealthy → alert appears
        bad_status = {
            "configured": True,
            "projects": {
                "p1": {"name": "gl-proj", "healthy": False, "last_error": "err"}
            },
        }
        manager._status_callback(bad_status)
        assert len(orch._alerts) == 1

        # Then: healthy → alert is cleared
        good_status = {
            "configured": True,
            "projects": {
                "p1": {"name": "gl-proj", "healthy": True, "last_error": ""}
            },
        }
        manager._status_callback(good_status)
        assert orch._alerts == []
