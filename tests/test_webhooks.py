"""Tests for oompah.webhooks — forge webhook parsing and validation.

Covers:
- GitHub HMAC-SHA256 signature validation
- GitLab secret token validation
- GitHub pull_request payload parsing
- GitLab Merge Request Hook payload parsing
- Non-PR/MR event rejection
- Project matching by repo slug
- WebhookEvent dataclass fields
"""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from oompah.webhooks import (
    WebhookEvent,
    match_project_by_repo,
    parse_github_webhook,
    parse_gitlab_webhook,
    validate_github_signature,
    validate_gitlab_token,
)
from oompah.models import Project


# ---------------------------------------------------------------------------
# Fixtures — sample payloads
# ---------------------------------------------------------------------------


def _github_pr_payload(
    action: str = "opened",
    number: int = 42,
    repo_full_name: str = "org/repo",
    source_branch: str = "feature-branch",
    target_branch: str = "main",
    author: str = "octocat",
    title: str = "Add new feature",
    merged: bool = False,
) -> dict:
    """Build a minimal GitHub pull_request webhook payload."""
    return {
        "action": action,
        "pull_request": {
            "number": number,
            "title": title,
            "merged": merged,
            "user": {"login": author},
            "head": {"ref": source_branch},
            "base": {"ref": target_branch},
        },
        "repository": {
            "full_name": repo_full_name,
        },
    }


def _gitlab_mr_payload(
    action: str = "open",
    iid: int = 7,
    repo_path: str = "group/project",
    source_branch: str = "fix-branch",
    target_branch: str = "main",
    author: str = "tanuki",
    title: str = "Fix the thing",
    state: str = "opened",
) -> dict:
    """Build a minimal GitLab Merge Request Hook webhook payload."""
    return {
        "object_attributes": {
            "iid": iid,
            "title": title,
            "action": action,
            "state": state,
            "source_branch": source_branch,
            "target_branch": target_branch,
        },
        "user": {"username": author},
        "project": {"path_with_namespace": repo_path},
    }


def _make_project(
    repo_url: str = "https://github.com/org/repo.git",
    project_id: str = "proj-test1",
    name: str = "test-project",
    webhook_secret: str | None = None,
) -> Project:
    return Project(
        id=project_id,
        name=name,
        repo_url=repo_url,
        repo_path="/tmp/repos/test",
        webhook_secret=webhook_secret,
    )


# ---------------------------------------------------------------------------
# GitHub signature validation
# ---------------------------------------------------------------------------


class TestValidateGitHubSignature:
    """Tests for validate_github_signature()."""

    def test_valid_signature(self):
        secret = "my-webhook-secret"
        body = b'{"action":"opened"}'
        sig = "sha256=" + hmac.new(
            secret.encode(), body, hashlib.sha256
        ).hexdigest()
        assert validate_github_signature(body, sig, secret) is True

    def test_invalid_signature(self):
        secret = "my-webhook-secret"
        body = b'{"action":"opened"}'
        assert validate_github_signature(body, "sha256=deadbeef", secret) is False

    def test_wrong_secret(self):
        secret = "correct-secret"
        wrong = "wrong-secret"
        body = b'{"action":"opened"}'
        sig = "sha256=" + hmac.new(
            wrong.encode(), body, hashlib.sha256
        ).hexdigest()
        assert validate_github_signature(body, sig, secret) is False

    def test_missing_prefix(self):
        secret = "my-secret"
        body = b"hello"
        # No sha256= prefix
        sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        assert validate_github_signature(body, sig, secret) is False

    def test_empty_signature_header(self):
        assert validate_github_signature(b"body", "", "secret") is False

    def test_empty_secret(self):
        assert validate_github_signature(b"body", "sha256=abc", "") is False

    def test_empty_both(self):
        assert validate_github_signature(b"body", "", "") is False

    def test_large_payload(self):
        """Signature validation works on large payloads."""
        secret = "big-secret"
        body = b"x" * 100_000
        sig = "sha256=" + hmac.new(
            secret.encode(), body, hashlib.sha256
        ).hexdigest()
        assert validate_github_signature(body, sig, secret) is True


# ---------------------------------------------------------------------------
# GitLab token validation
# ---------------------------------------------------------------------------


class TestValidateGitLabToken:
    """Tests for validate_gitlab_token()."""

    def test_valid_token(self):
        secret = "gitlab-secret-token"
        assert validate_gitlab_token(secret, secret) is True

    def test_invalid_token(self):
        assert validate_gitlab_token("wrong", "correct") is False

    def test_empty_token(self):
        assert validate_gitlab_token("", "secret") is False

    def test_empty_secret(self):
        assert validate_gitlab_token("token", "") is False

    def test_empty_both(self):
        assert validate_gitlab_token("", "") is False

    def test_timing_safe_comparison(self):
        """Ensure comparison is constant-time (uses hmac.compare_digest)."""
        # We can't directly test timing, but we verify the function
        # still works with long strings
        long_a = "a" * 1000
        long_b = "a" * 1000
        assert validate_gitlab_token(long_a, long_b) is True
        assert validate_gitlab_token(long_a, long_a[:-1] + "b") is False


# ---------------------------------------------------------------------------
# GitHub payload parsing
# ---------------------------------------------------------------------------


class TestParseGitHubWebhook:
    """Tests for parse_github_webhook()."""

    def test_pr_opened(self):
        payload = _github_pr_payload(action="opened")
        event = parse_github_webhook("pull_request", payload)
        assert event is not None
        assert event.provider == "github"
        assert event.event_type == "pull_request"
        assert event.action == "opened"
        assert event.repo_slug == "org/repo"
        assert event.review_id == "42"
        assert event.source_branch == "feature-branch"
        assert event.target_branch == "main"
        assert event.author == "octocat"
        assert event.title == "Add new feature"
        assert event.merged is False

    def test_pr_closed_merged(self):
        payload = _github_pr_payload(action="closed", merged=True)
        event = parse_github_webhook("pull_request", payload)
        assert event is not None
        assert event.action == "closed"
        assert event.merged is True

    def test_pr_closed_not_merged(self):
        payload = _github_pr_payload(action="closed", merged=False)
        event = parse_github_webhook("pull_request", payload)
        assert event is not None
        assert event.merged is False

    def test_pr_synchronize(self):
        payload = _github_pr_payload(action="synchronize")
        event = parse_github_webhook("pull_request", payload)
        assert event is not None
        assert event.action == "synchronize"

    def test_pr_review_requested(self):
        payload = _github_pr_payload(action="review_requested")
        event = parse_github_webhook("pull_request", payload)
        assert event is not None
        assert event.action == "review_requested"

    def test_non_pr_event_returns_none(self):
        assert parse_github_webhook("push", {"ref": "refs/heads/main"}) is None

    def test_ping_event_returns_none(self):
        assert parse_github_webhook("ping", {"zen": "test"}) is None

    def test_issues_event_returns_none(self):
        assert parse_github_webhook("issues", {"action": "opened"}) is None

    def test_missing_pull_request_key_returns_none(self):
        """If the payload is pull_request type but missing the PR object."""
        assert parse_github_webhook("pull_request", {"action": "opened"}) is None

    def test_raw_payload_preserved(self):
        payload = _github_pr_payload()
        event = parse_github_webhook("pull_request", payload)
        assert event is not None
        assert event.raw is payload

    def test_different_repo(self):
        payload = _github_pr_payload(repo_full_name="other-org/other-repo")
        event = parse_github_webhook("pull_request", payload)
        assert event is not None
        assert event.repo_slug == "other-org/other-repo"


# ---------------------------------------------------------------------------
# GitLab payload parsing
# ---------------------------------------------------------------------------


class TestParseGitLabWebhook:
    """Tests for parse_gitlab_webhook()."""

    def test_mr_open(self):
        payload = _gitlab_mr_payload(action="open")
        event = parse_gitlab_webhook("Merge Request Hook", payload)
        assert event is not None
        assert event.provider == "gitlab"
        assert event.event_type == "Merge Request Hook"
        assert event.action == "open"
        assert event.repo_slug == "group/project"
        assert event.review_id == "7"
        assert event.source_branch == "fix-branch"
        assert event.target_branch == "main"
        assert event.author == "tanuki"
        assert event.title == "Fix the thing"
        assert event.merged is False

    def test_mr_merged(self):
        payload = _gitlab_mr_payload(action="merge", state="merged")
        event = parse_gitlab_webhook("Merge Request Hook", payload)
        assert event is not None
        assert event.action == "merge"
        assert event.merged is True

    def test_mr_close(self):
        payload = _gitlab_mr_payload(action="close", state="closed")
        event = parse_gitlab_webhook("Merge Request Hook", payload)
        assert event is not None
        assert event.action == "close"
        assert event.merged is False

    def test_mr_update(self):
        payload = _gitlab_mr_payload(action="update")
        event = parse_gitlab_webhook("Merge Request Hook", payload)
        assert event is not None
        assert event.action == "update"

    def test_non_mr_event_returns_none(self):
        assert parse_gitlab_webhook("Push Hook", {"ref": "refs/heads/main"}) is None

    def test_pipeline_event_returns_none(self):
        assert parse_gitlab_webhook("Pipeline Hook", {}) is None

    def test_missing_object_attributes_returns_none(self):
        assert parse_gitlab_webhook("Merge Request Hook", {"user": {}}) is None

    def test_raw_payload_preserved(self):
        payload = _gitlab_mr_payload()
        event = parse_gitlab_webhook("Merge Request Hook", payload)
        assert event is not None
        assert event.raw is payload


# ---------------------------------------------------------------------------
# Project matching
# ---------------------------------------------------------------------------


class TestMatchProjectByRepo:
    """Tests for match_project_by_repo()."""

    def test_match_github_https(self):
        projects = [_make_project(repo_url="https://github.com/org/repo.git")]
        matched = match_project_by_repo(projects, "org/repo", "github")
        assert matched is not None
        assert matched.id == "proj-test1"

    def test_match_github_ssh(self):
        projects = [_make_project(repo_url="git@github.com:org/repo.git")]
        matched = match_project_by_repo(projects, "org/repo", "github")
        assert matched is not None

    def test_match_gitlab(self):
        projects = [_make_project(
            repo_url="https://gitlab.com/group/project.git",
            project_id="proj-gl1",
        )]
        matched = match_project_by_repo(projects, "group/project", "gitlab")
        assert matched is not None
        assert matched.id == "proj-gl1"

    def test_no_match(self):
        projects = [_make_project(repo_url="https://github.com/org/other.git")]
        matched = match_project_by_repo(projects, "org/repo", "github")
        assert matched is None

    def test_empty_projects(self):
        matched = match_project_by_repo([], "org/repo", "github")
        assert matched is None

    def test_multiple_projects_returns_first_match(self):
        projects = [
            _make_project(repo_url="https://github.com/org/other.git", project_id="p1"),
            _make_project(repo_url="https://github.com/org/repo.git", project_id="p2"),
        ]
        matched = match_project_by_repo(projects, "org/repo", "github")
        assert matched is not None
        assert matched.id == "p2"


# ---------------------------------------------------------------------------
# WebhookEvent dataclass
# ---------------------------------------------------------------------------


class TestWebhookEvent:
    """Tests for WebhookEvent dataclass."""

    def test_default_values(self):
        event = WebhookEvent(provider="github", event_type="pull_request", action="opened")
        assert event.repo_slug == ""
        assert event.review_id == ""
        assert event.source_branch == ""
        assert event.target_branch == ""
        assert event.author == ""
        assert event.title == ""
        assert event.merged is False
        assert event.raw == {}

    def test_all_fields(self):
        raw = {"key": "value"}
        event = WebhookEvent(
            provider="gitlab",
            event_type="Merge Request Hook",
            action="merge",
            repo_slug="group/proj",
            review_id="10",
            source_branch="feat",
            target_branch="main",
            author="dev",
            title="My MR",
            merged=True,
            raw=raw,
        )
        assert event.provider == "gitlab"
        assert event.merged is True
        assert event.raw is raw
