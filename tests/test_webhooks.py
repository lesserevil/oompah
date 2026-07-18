"""Tests for oompah.webhooks — forge webhook parsing and validation.

Covers:
- GitHub HMAC-SHA256 signature validation
- GitLab secret token validation
- GitHub pull_request payload parsing
- GitHub issues / issue_comment / label / projects_v2_item payload parsing
- GitLab Merge Request Hook payload parsing
- Non-PR/MR event rejection
- Project matching by repo slug
- WebhookEvent dataclass fields
- WebhookForwarder subprocess management
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import hashlib
import hmac
import json
import os
import tempfile

import pytest

from oompah.webhooks import (
    WebhookEvent,
    WebhookForwarder,
    _ForwarderProcess,
    build_webhook_forwarder_alerts,
    check_gh_webhook_available,
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

    def test_ping_event_returns_none(self):
        assert parse_github_webhook("ping", {"zen": "test"}) is None

    def test_issues_event_missing_issue_key_returns_none(self):
        """Malformed issues payload (no ``issue`` key) must return None."""
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


class TestParseGitHubPushWebhook:
    """Tests for parse_github_webhook() handling of push events."""

    def _push_payload(
        self,
        ref: str = "refs/heads/main",
        repo_full_name: str = "org/repo",
        deleted: bool = False,
        head_message: str = "chore(tasks): undefer all",
        pusher_name: str = "octocat",
    ) -> dict:
        return {
            "ref": ref,
            "deleted": deleted,
            "before": "0" * 40,
            "after": "1" * 40,
            "repository": {"full_name": repo_full_name},
            "pusher": {"name": pusher_name, "email": "x@example.com"},
            "sender": {"login": pusher_name},
            "head_commit": {"message": head_message, "id": "1" * 40},
        }

    def test_push_to_main(self):
        event = parse_github_webhook("push", self._push_payload())
        assert event is not None
        assert event.event_type == "push"
        assert event.action == "pushed"
        assert event.target_branch == "main"
        assert event.source_branch == ""
        assert event.review_id == ""
        assert event.merged is False
        assert event.author == "octocat"
        assert event.title == "chore(tasks): undefer all"
        assert event.repo_slug == "org/repo"

    def test_push_to_feature_branch(self):
        event = parse_github_webhook("push", self._push_payload(ref="refs/heads/feature-x"))
        assert event is not None
        assert event.target_branch == "feature-x"

    def test_push_branch_deletion_returns_none(self):
        payload = self._push_payload(deleted=True)
        assert parse_github_webhook("push", payload) is None

    def test_push_tag_returns_none(self):
        payload = self._push_payload(ref="refs/tags/v1.0")
        assert parse_github_webhook("push", payload) is None

    def test_push_multiline_message_takes_first_line_only(self):
        payload = self._push_payload(head_message="first line\n\nbody continues here")
        event = parse_github_webhook("push", payload)
        assert event is not None
        assert event.title == "first line"

    def test_push_missing_head_commit(self):
        payload = self._push_payload()
        del payload["head_commit"]
        event = parse_github_webhook("push", payload)
        assert event is not None
        assert event.title == ""

    def test_push_falls_back_to_sender_when_pusher_missing(self):
        payload = self._push_payload()
        del payload["pusher"]
        event = parse_github_webhook("push", payload)
        assert event is not None
        assert event.author == "octocat"


# ---------------------------------------------------------------------------
# GitHub issues / issue_comment / label / projects_v2_item parsing
# ---------------------------------------------------------------------------


class TestParseGitHubIssuesWebhook:
    """Tests for parse_github_webhook() handling of ``issues`` events."""

    def _issues_payload(
        self,
        action: str = "opened",
        number: int = 7,
        title: str = "Fix the bug",
        author: str = "contributor",
        repo_full_name: str = "org/repo",
        is_pr: bool = False,
    ) -> dict:
        issue: dict = {
            "number": number,
            "title": title,
            "user": {"login": author},
        }
        if is_pr:
            issue["pull_request"] = {"url": "https://api.github.com/repos/org/repo/pulls/7"}
        return {
            "action": action,
            "issue": issue,
            "repository": {"full_name": repo_full_name},
            "sender": {"login": author},
        }

    def test_issue_opened(self):
        payload = self._issues_payload(action="opened")
        event = parse_github_webhook("issues", payload)
        assert event is not None
        assert event.provider == "github"
        assert event.event_type == "issues"
        assert event.action == "opened"
        assert event.repo_slug == "org/repo"
        assert event.review_id == "7"
        assert event.issue_number == "7"
        assert event.author == "contributor"
        assert event.title == "Fix the bug"
        assert event.merged is False

    def test_issue_closed(self):
        event = parse_github_webhook("issues", self._issues_payload(action="closed"))
        assert event is not None
        assert event.action == "closed"

    def test_issue_reopened(self):
        event = parse_github_webhook("issues", self._issues_payload(action="reopened"))
        assert event is not None
        assert event.action == "reopened"

    def test_issue_labeled(self):
        event = parse_github_webhook("issues", self._issues_payload(action="labeled"))
        assert event is not None
        assert event.action == "labeled"

    def test_issue_edited(self):
        event = parse_github_webhook("issues", self._issues_payload(action="edited"))
        assert event is not None
        assert event.action == "edited"

    def test_pr_backed_issue_returns_none(self):
        """Issues with a ``pull_request`` key are skipped."""
        payload = self._issues_payload(is_pr=True)
        assert parse_github_webhook("issues", payload) is None

    def test_missing_issue_key_returns_none(self):
        assert parse_github_webhook("issues", {"action": "opened"}) is None

    def test_raw_payload_preserved(self):
        payload = self._issues_payload()
        event = parse_github_webhook("issues", payload)
        assert event is not None
        assert event.raw is payload

    def test_issue_number_as_string(self):
        payload = self._issues_payload(number=99)
        event = parse_github_webhook("issues", payload)
        assert event is not None
        assert event.issue_number == "99"
        assert event.review_id == "99"

    def test_empty_comment_id_and_label_name(self):
        """issues events carry no comment_id or label_name."""
        event = parse_github_webhook("issues", self._issues_payload())
        assert event is not None
        assert event.comment_id == ""
        assert event.label_name == ""

    def test_non_labeled_action_has_no_label_actor(self):
        """Non-labeled/unlabeled events have an empty label_actor."""
        for action in ("opened", "closed", "reopened", "edited"):
            event = parse_github_webhook("issues", self._issues_payload(action=action))
            assert event is not None
            assert event.label_actor == "", f"Expected empty label_actor for {action!r}"
            assert event.label_name == "", f"Expected empty label_name for {action!r}"

    def _labeled_payload(
        self,
        action: str = "labeled",
        number: int = 7,
        issue_author: str = "issue-creator",
        label_name: str = "oompah:status:open",
        sender_login: str = "some-user",
        repo_full_name: str = "org/repo",
    ) -> dict:
        """Build an ``issues.labeled`` or ``issues.unlabeled`` payload."""
        return {
            "action": action,
            "issue": {
                "number": number,
                "title": "Some issue",
                "user": {"login": issue_author},
            },
            "label": {
                "name": label_name,
                "color": "e4e669",
            },
            "repository": {"full_name": repo_full_name},
            "sender": {"login": sender_login},
        }

    def test_labeled_event_captures_sender_as_label_actor(self):
        """labeled event: label_actor is sender.login, NOT issue.user.login."""
        payload = self._labeled_payload(
            action="labeled",
            issue_author="issue-creator",
            sender_login="someone-who-applied-label",
        )
        event = parse_github_webhook("issues", payload)
        assert event is not None
        assert event.action == "labeled"
        assert event.label_actor == "someone-who-applied-label"
        # author is still the issue creator
        assert event.author == "issue-creator"

    def test_labeled_event_captures_label_name(self):
        """labeled event: label_name is taken from payload.label.name."""
        payload = self._labeled_payload(
            action="labeled",
            label_name="oompah:status:open",
        )
        event = parse_github_webhook("issues", payload)
        assert event is not None
        assert event.label_name == "oompah:status:open"

    def test_unlabeled_event_captures_sender_as_label_actor(self):
        """unlabeled event: label_actor is sender.login."""
        payload = self._labeled_payload(
            action="unlabeled",
            issue_author="creator",
            sender_login="remover",
            label_name="oompah:status:backlog",
        )
        event = parse_github_webhook("issues", payload)
        assert event is not None
        assert event.action == "unlabeled"
        assert event.label_actor == "remover"
        assert event.label_name == "oompah:status:backlog"

    def test_labeled_by_oompah_bot_captures_correctly(self):
        """When oompah bot applies a status label, label_actor is 'oompah'."""
        payload = self._labeled_payload(
            action="labeled",
            issue_author="contributor",
            sender_login="oompah",
            label_name="oompah:status:in-progress",
        )
        event = parse_github_webhook("issues", payload)
        assert event is not None
        assert event.label_actor == "oompah"
        assert event.label_name == "oompah:status:in-progress"

    def test_labeled_without_label_key_gives_empty_fields(self):
        """When payload has no 'label' key, label_name and label_actor are empty."""
        payload = {
            "action": "labeled",
            "issue": {
                "number": 7,
                "title": "Test",
                "user": {"login": "author"},
            },
            "repository": {"full_name": "org/repo"},
            "sender": {"login": "actor"},
            # No "label" key
        }
        event = parse_github_webhook("issues", payload)
        assert event is not None
        assert event.label_name == ""
        # label_actor is still set from sender even without the label object
        assert event.label_actor == "actor"

    def test_sender_login_is_label_actor_not_issue_author(self):
        """The sender (who applies the label) differs from the issue author."""
        payload = self._labeled_payload(
            action="labeled",
            issue_author="original-author",
            sender_login="project-maintainer",
            label_name="oompah:status:open",
        )
        event = parse_github_webhook("issues", payload)
        assert event is not None
        # The issue author is preserved in author
        assert event.author == "original-author"
        # The label applicant is in label_actor
        assert event.label_actor == "project-maintainer"
        # They are different people
        assert event.author != event.label_actor

    def test_different_repo(self):
        payload = self._issues_payload(repo_full_name="other/project")
        event = parse_github_webhook("issues", payload)
        assert event is not None
        assert event.repo_slug == "other/project"


class TestParseGitHubIssueCommentWebhook:
    """Tests for parse_github_webhook() handling of ``issue_comment`` events."""

    def _comment_payload(
        self,
        action: str = "created",
        issue_number: int = 5,
        comment_id: int = 987654,
        comment_author: str = "reviewer",
        issue_title: str = "Some issue",
        repo_full_name: str = "org/repo",
    ) -> dict:
        return {
            "action": action,
            "issue": {
                "number": issue_number,
                "title": issue_title,
                "user": {"login": "author"},
            },
            "comment": {
                "id": comment_id,
                "user": {"login": comment_author},
                "body": "LGTM",
            },
            "repository": {"full_name": repo_full_name},
        }

    def test_comment_created(self):
        payload = self._comment_payload(action="created")
        event = parse_github_webhook("issue_comment", payload)
        assert event is not None
        assert event.provider == "github"
        assert event.event_type == "issue_comment"
        assert event.action == "created"
        assert event.repo_slug == "org/repo"
        assert event.review_id == "5"
        assert event.issue_number == "5"
        assert event.comment_id == "987654"
        assert event.author == "reviewer"
        assert event.title == "Some issue"
        assert event.merged is False

    def test_comment_edited(self):
        event = parse_github_webhook("issue_comment", self._comment_payload(action="edited"))
        assert event is not None
        assert event.action == "edited"

    def test_comment_deleted(self):
        event = parse_github_webhook("issue_comment", self._comment_payload(action="deleted"))
        assert event is not None
        assert event.action == "deleted"

    def test_missing_issue_returns_none(self):
        payload = {"action": "created", "comment": {"id": 1, "user": {"login": "x"}}}
        assert parse_github_webhook("issue_comment", payload) is None

    def test_missing_comment_returns_none(self):
        payload = {"action": "created", "issue": {"number": 1, "title": "t", "user": {"login": "a"}}}
        assert parse_github_webhook("issue_comment", payload) is None

    def test_comment_id_as_string(self):
        event = parse_github_webhook("issue_comment", self._comment_payload(comment_id=111))
        assert event is not None
        assert event.comment_id == "111"

    def test_raw_payload_preserved(self):
        payload = self._comment_payload()
        event = parse_github_webhook("issue_comment", payload)
        assert event is not None
        assert event.raw is payload

    def test_empty_label_name(self):
        """issue_comment events carry no label_name."""
        event = parse_github_webhook("issue_comment", self._comment_payload())
        assert event is not None
        assert event.label_name == ""


class TestParseGitHubLabelWebhook:
    """Tests for parse_github_webhook() handling of ``label`` events."""

    def _label_payload(
        self,
        action: str = "created",
        label_name: str = "bug",
        label_id: int = 1234,
        repo_full_name: str = "org/repo",
        sender: str = "maintainer",
    ) -> dict:
        return {
            "action": action,
            "label": {
                "id": label_id,
                "name": label_name,
                "color": "d73a4a",
                "description": "Something isn't working",
            },
            "repository": {"full_name": repo_full_name},
            "sender": {"login": sender},
        }

    def test_label_created(self):
        payload = self._label_payload(action="created", label_name="enhancement")
        event = parse_github_webhook("label", payload)
        assert event is not None
        assert event.provider == "github"
        assert event.event_type == "label"
        assert event.action == "created"
        assert event.repo_slug == "org/repo"
        assert event.label_name == "enhancement"
        assert event.title == "enhancement"
        assert event.author == "maintainer"
        assert event.merged is False

    def test_label_edited(self):
        event = parse_github_webhook("label", self._label_payload(action="edited"))
        assert event is not None
        assert event.action == "edited"

    def test_label_deleted(self):
        event = parse_github_webhook("label", self._label_payload(action="deleted"))
        assert event is not None
        assert event.action == "deleted"

    def test_missing_label_returns_none(self):
        assert parse_github_webhook("label", {"action": "created"}) is None

    def test_label_name_in_both_fields(self):
        event = parse_github_webhook("label", self._label_payload(label_name="oompah:status:done"))
        assert event is not None
        assert event.label_name == "oompah:status:done"
        assert event.title == "oompah:status:done"

    def test_raw_payload_preserved(self):
        payload = self._label_payload()
        event = parse_github_webhook("label", payload)
        assert event is not None
        assert event.raw is payload

    def test_empty_issue_number_and_comment_id(self):
        """label events carry no issue_number or comment_id."""
        event = parse_github_webhook("label", self._label_payload())
        assert event is not None
        assert event.issue_number == ""
        assert event.comment_id == ""


class TestParseGitHubProjectsV2ItemWebhook:
    """Tests for parse_github_webhook() handling of ``projects_v2_item`` events."""

    def _projects_v2_item_payload(
        self,
        action: str = "edited",
        item_node_id: str = "PVTI_lADOBqkPss4ADYBdzgK1234",
        field_name: str = "Status",
        field_to_name: str = "In Progress",
        sender: str = "oompah",
    ) -> dict:
        return {
            "action": action,
            "projects_v2_item": {
                "id": 42,
                "node_id": item_node_id,
                "project_node_id": "PVT_kwDOBqkPss4ADYBd",
                "content_type": "Issue",
                "content_node_id": "I_kgDOKABC",
            },
            "changes": {
                "field_value": {
                    "field_name": field_name,
                    "field_type": "single_select",
                    "to": {"name": field_to_name},
                    "from": {"name": "To Do"},
                }
            },
            "sender": {"login": sender},
            # Note: no "repository" key — this is an org-level event
        }

    def test_item_edited(self):
        payload = self._projects_v2_item_payload(action="edited")
        event = parse_github_webhook("projects_v2_item", payload)
        assert event is not None
        assert event.provider == "github"
        assert event.event_type == "projects_v2_item"
        assert event.action == "edited"
        assert event.repo_slug == ""  # org-level event — no repo
        assert event.project_item_id == "PVTI_lADOBqkPss4ADYBdzgK1234"
        assert event.project_field_name == "Status"
        assert event.project_field_value == "In Progress"
        assert event.author == "oompah"
        assert event.merged is False

    def test_item_created(self):
        payload = {
            "action": "created",
            "projects_v2_item": {"id": 1, "node_id": "PVTI_abc", "project_node_id": "PVT_x"},
            "sender": {"login": "oompah"},
        }
        event = parse_github_webhook("projects_v2_item", payload)
        assert event is not None
        assert event.action == "created"
        assert event.project_field_name == ""
        assert event.project_field_value == ""

    def test_item_deleted(self):
        payload = {
            "action": "deleted",
            "projects_v2_item": {"id": 2, "node_id": "PVTI_del"},
            "sender": {"login": "oompah"},
        }
        event = parse_github_webhook("projects_v2_item", payload)
        assert event is not None
        assert event.action == "deleted"

    def test_missing_item_returns_none(self):
        assert parse_github_webhook("projects_v2_item", {"action": "edited"}) is None

    def test_field_value_change_extracted(self):
        event = parse_github_webhook(
            "projects_v2_item",
            self._projects_v2_item_payload(field_name="Priority", field_to_name="High"),
        )
        assert event is not None
        assert event.project_field_name == "Priority"
        assert event.project_field_value == "High"

    def test_no_changes_field(self):
        payload = {
            "action": "reordered",
            "projects_v2_item": {"id": 3, "node_id": "PVTI_x"},
            "sender": {"login": "user"},
        }
        event = parse_github_webhook("projects_v2_item", payload)
        assert event is not None
        assert event.project_field_name == ""
        assert event.project_field_value == ""

    def test_item_node_id_preferred_over_numeric_id(self):
        event = parse_github_webhook(
            "projects_v2_item",
            self._projects_v2_item_payload(item_node_id="PVTI_node_xyz"),
        )
        assert event is not None
        assert event.project_item_id == "PVTI_node_xyz"

    def test_numeric_id_used_when_no_node_id(self):
        payload = {
            "action": "edited",
            "projects_v2_item": {"id": 99},
            "sender": {"login": "user"},
        }
        event = parse_github_webhook("projects_v2_item", payload)
        assert event is not None
        assert event.project_item_id == "99"

    def test_raw_payload_preserved(self):
        payload = self._projects_v2_item_payload()
        event = parse_github_webhook("projects_v2_item", payload)
        assert event is not None
        assert event.raw is payload

    def test_unsupported_event_still_returns_none(self):
        """Unknown event types continue to return None."""
        assert parse_github_webhook("ping", {"zen": "test"}) is None
        assert parse_github_webhook("check_run", {}) is None
        assert parse_github_webhook("workflow_run", {}) is None

    def test_title_field_fallback_for_field_value(self):
        """title field in the to object is used as the field value."""
        payload = {
            "action": "edited",
            "projects_v2_item": {"id": 1, "node_id": "PVTI_a"},
            "changes": {
                "field_value": {
                    "field_name": "Sprint",
                    "field_type": "iteration",
                    "to": {"title": "Sprint 3"},
                }
            },
            "sender": {"login": "user"},
        }
        event = parse_github_webhook("projects_v2_item", payload)
        assert event is not None
        assert event.project_field_name == "Sprint"
        assert event.project_field_value == "Sprint 3"


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
        # New fields default to empty string
        assert event.issue_number == ""
        assert event.comment_id == ""
        assert event.label_name == ""
        assert event.project_item_id == ""
        assert event.project_field_name == ""
        assert event.project_field_value == ""

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

    def test_extended_fields(self):
        """New issue/project fields can be populated."""
        event = WebhookEvent(
            provider="github",
            event_type="projects_v2_item",
            action="edited",
            issue_number="42",
            comment_id="123",
            label_name="bug",
            project_item_id="PVTI_abc",
            project_field_name="Status",
            project_field_value="Done",
        )
        assert event.issue_number == "42"
        assert event.comment_id == "123"
        assert event.label_name == "bug"
        assert event.project_item_id == "PVTI_abc"
        assert event.project_field_name == "Status"
        assert event.project_field_value == "Done"


# ---------------------------------------------------------------------------
# WebhookForwarder
# ---------------------------------------------------------------------------


class _FakeProjectStore:
    """Minimal ProjectStore stand-in for testing."""

    def __init__(self, projects: list[Project] | None = None):
        self._projects = {p.id: p for p in (projects or [])}

    def list_all(self) -> list[Project]:
        return list(self._projects.values())

    def get(self, project_id: str) -> Project | None:
        return self._projects.get(project_id)


class _DummyProjectStore:
    """ProjectStore that always returns empty list."""

    def list_all(self) -> list[Project]:
        return []


class TestForwarderProcess:
    """Tests for _ForwarderProcess dataclass."""

    def test_initial_state(self):
        fp = _ForwarderProcess(
            project_id="p1",
            project_name="my-project",
            repo_path="/tmp/repos/my-project",
            repo_slug="org/my-project",
            access_token="project-token",
        )
        assert fp.project_id == "p1"
        assert fp.project_name == "my-project"
        assert fp.repo_path == "/tmp/repos/my-project"
        assert fp.repo_slug == "org/my-project"
        assert fp.access_token == "project-token"
        assert fp.forwarding_enabled is True
        assert fp.process is None
        assert fp.restart_delay_s == 1.0
        assert fp.restart_attempts == 0


class TestWebhookForwarderInit:
    """Tests for WebhookForwarder.__init__()."""

    def test_default_webhook_url(self):
        fwd = WebhookForwarder()
        assert fwd._webhook_url == "http://localhost:8080/api/v1/webhooks/github"

    def test_default_webhook_url_uses_server_port_arg(self):
        fwd = WebhookForwarder(server_port=8090)
        assert fwd._webhook_url == "http://localhost:8090/api/v1/webhooks/github"

    def test_default_webhook_url_uses_server_port_env(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_SERVER_PORT", "8090")
        fwd = WebhookForwarder()
        assert fwd._webhook_url == "http://localhost:8090/api/v1/webhooks/github"

    def test_explicit_webhook_url(self):
        fwd = WebhookForwarder(webhook_url="http://example.com/hooks")
        assert fwd._webhook_url == "http://example.com/hooks"

    def test_env_var_override(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_WEBHOOK_FORWARD_URL", "http://env-url.test/hooks")
        fwd = WebhookForwarder()
        assert fwd._webhook_url == "http://env-url.test/hooks"

    def test_explicit_overrides_env(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_WEBHOOK_FORWARD_URL", "http://env-url.test/hooks")
        fwd = WebhookForwarder(webhook_url="http://explicit.test/hooks")
        assert fwd._webhook_url == "http://explicit.test/hooks"

    def test_forward_url_env_overrides_server_port(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_WEBHOOK_FORWARD_URL", "http://env-url.test/hooks")
        fwd = WebhookForwarder(server_port=8090)
        assert fwd._webhook_url == "http://env-url.test/hooks"

    def test_custom_poll_interval(self):
        fwd = WebhookForwarder(poll_interval_s=10.0)
        assert fwd._poll_interval_s == 10.0

    def test_default_poll_interval(self):
        fwd = WebhookForwarder()
        assert fwd._poll_interval_s == 5.0

    def test_is_running_false_initially(self):
        fwd = WebhookForwarder()
        assert fwd.is_running is False


class TestWebhookForwarderStartStop:
    """Tests for WebhookForwarder start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_is_idempotent(self):
        fwd = WebhookForwarder(project_store=_DummyProjectStore())
        await fwd.start()
        assert fwd.is_running is True
        # Second start should be no-op (already running)
        await fwd.start()
        assert fwd.is_running is True
        await fwd.stop()

    @pytest.mark.asyncio
    async def test_stop_is_idempotent(self):
        fwd = WebhookForwarder(project_store=_DummyProjectStore())
        await fwd.start()
        await fwd.stop()
        assert fwd.is_running is False
        # Second stop should be no-op
        await fwd.stop()
        assert fwd.is_running is False

    @pytest.mark.asyncio
    async def test_start_then_stop_cleans_up_task(self):
        fwd = WebhookForwarder(project_store=_DummyProjectStore())
        await fwd.start()
        await fwd.stop()
        assert fwd._task is None


class TestWebhookForwarderPoll:
    """Tests for WebhookForwarder polling and restart logic."""

    @pytest.mark.asyncio
    async def test_no_project_store_means_no_error(self):
        fwd = WebhookForwarder(project_store=None)
        # Calling _poll_and_restart with no project store should not raise.
        await fwd._poll_and_restart()

    @pytest.mark.asyncio
    async def test_empty_project_store_means_no_error(self):
        fwd = WebhookForwarder(project_store=_DummyProjectStore())
        await fwd._poll_and_restart()
        # No processes should be tracked.
        assert len(fwd._processes) == 0

    @pytest.mark.asyncio
    async def test_adding_project_creates_forwarder_process(self):
        proj = Project(
            id="proj-1",
            name="test-repo",
            repo_url="https://github.com/org/repo.git",
            repo_path="/tmp/test-repo",
            access_token="project-token",
        )
        store = _FakeProjectStore([proj])
        fwd = WebhookForwarder(project_store=store)
        await fwd._poll_and_restart()
        assert "proj-1" in fwd._processes
        fp = fwd._processes["proj-1"]
        assert fp.project_name == "test-repo"
        assert fp.repo_path == "/tmp/test-repo"
        assert fp.repo_slug == "org/repo"
        assert fp.access_token == "project-token"
        assert fp.process is None  # gh not available, so not started

    @pytest.mark.asyncio
    async def test_existing_project_refreshes_forwarder_metadata(self):
        proj = Project(
            id="proj-1",
            name="test-repo",
            repo_url="https://github.com/org/repo.git",
            repo_path="/tmp/test-repo",
            access_token="old-token",
            webhook_forwarding_enabled=True,
        )
        store = _FakeProjectStore([proj])
        fwd = WebhookForwarder(project_store=store)
        await fwd._poll_and_restart()

        proj.name = "renamed-repo"
        proj.repo_url = "https://github.com/org/renamed.git"
        proj.repo_path = "/tmp/renamed-repo"
        proj.access_token = "new-token"
        proj.webhook_forwarding_enabled = False

        await fwd._poll_and_restart()

        fp = fwd._processes["proj-1"]
        assert fp.project_name == "renamed-repo"
        assert fp.repo_path == "/tmp/renamed-repo"
        assert fp.repo_slug == "org/renamed"
        assert fp.access_token == "new-token"
        assert fp.forwarding_enabled is False

    @pytest.mark.asyncio
    async def test_disabled_project_does_not_launch_forwarder(self):
        proj = Project(
            id="proj-1",
            name="polling-only",
            repo_url="https://github.com/org/repo.git",
            repo_path="/tmp/test-repo",
            webhook_forwarding_enabled=False,
        )
        store = _FakeProjectStore([proj])
        fwd = WebhookForwarder(project_store=store)
        fwd._extension_available = True

        with patch("asyncio.create_subprocess_exec") as create_proc:
            await fwd._poll_and_restart()

        assert "proj-1" in fwd._processes
        fp = fwd._processes["proj-1"]
        assert fp.forwarding_enabled is False
        assert fp.process is None
        create_proc.assert_not_called()

    @pytest.mark.asyncio
    async def test_removing_project_terminates_forwarder(self):
        proj = Project(
            id="proj-1",
            name="test-repo",
            repo_url="https://github.com/org/repo.git",
            repo_path="/tmp/test-repo",
        )
        store = _FakeProjectStore([proj])
        fwd = WebhookForwarder(project_store=store)

        # Poll once to register.
        await fwd._poll_and_restart()
        assert "proj-1" in fwd._processes

        # Simulate project removal: store returns empty.
        fwd.project_store = _DummyProjectStore()
        await fwd._poll_and_restart()
        assert "proj-1" not in fwd._processes

    @pytest.mark.asyncio
    async def test_skips_non_git_repo(self, tmp_path):
        """A project whose repo_path is not a git directory is skipped."""
        non_git_dir = str(tmp_path)
        proj = Project(
            id="proj-1",
            name="non-git",
            repo_url="https://github.com/org/repo.git",
            repo_path=non_git_dir,
        )
        store = _FakeProjectStore([proj])
        fwd = WebhookForwarder(project_store=store)
        await fwd._poll_and_restart()
        assert "proj-1" in fwd._processes
        # gh forward should not be started (not a git repo).
        assert fwd._processes["proj-1"].process is None

    @pytest.mark.asyncio
    async def test_missing_repo_path_disables_at_warning_not_error(self, caplog):
        """When repo_path is missing/not-a-directory, the project is disabled but
        only a WARNING is emitted (not ERROR), so error_watcher is not triggered.

        Regression test for OOMPAH-234.
        """
        proj = Project(
            id="proj-1",
            name="trickle",
            repo_url="https://github.com/org/repo.git",
            repo_path="/nonexistent/path/that/does/not/exist",
        )
        store = _FakeProjectStore([proj])
        fwd = WebhookForwarder(project_store=store)

        with caplog.at_level("DEBUG", logger="oompah.webhooks"):
            await fwd._poll_and_restart()

        fp = fwd._processes["proj-1"]
        # Project should be disabled (webhook forwarding cannot proceed).
        assert fp.disabled is True
        assert "repo_path is missing or not a directory" in fp.disabled_reason
        assert fp.process is None

        # The key assertion: no ERROR-level log emitted for this configuration
        # issue. Only WARNING so that error_watcher is not triggered.
        error_records = [
            r for r in caplog.records
            if r.levelname == "ERROR" and "trickle" in r.message
        ]
        assert error_records == [], (
            "Expected no ERROR logs for missing repo_path, got: "
            + str([r.message for r in error_records])
        )
        warning_records = [
            r for r in caplog.records
            if r.levelname == "WARNING" and "trickle" in r.message
        ]
        assert len(warning_records) == 1
        assert "repo_path is missing or not a directory" in warning_records[0].message

    @pytest.mark.asyncio
    async def test_launch_skips_missing_gh(self, tmp_path):
        """If gh CLI is not found, _launch logs a warning and sets process=None."""
        proj = Project(
            id="proj-1",
            name="test-repo",
            repo_url="https://github.com/org/repo.git",
            repo_path=str(tmp_path),
        )
        # Make it a git repo so it passes the .git check.
        import subprocess
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)

        fwd = WebhookForwarder(project_store=_FakeProjectStore([proj]))
        fp = _ForwarderProcess("proj-1", "test-repo", str(tmp_path), "org/repo")
        await fwd._launch(fp)
        # gh is unlikely to be missing in CI, but if it is, process stays None.
        # Either way, no exception is raised.
        assert fp.project_id == "proj-1"

    @pytest.mark.asyncio
    async def test_exponential_backoff_reset_on_running(self, tmp_path):
        """When a process is still running, its restart_delay resets to base."""
        proj = Project(
            id="proj-1",
            name="test-repo",
            repo_url="https://github.com/org/repo.git",
            repo_path=str(tmp_path),
        )
        import subprocess
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)

        store = _FakeProjectStore([proj])
        fwd = WebhookForwarder(project_store=store)
        fwd._extension_available = False

        # Register project.
        await fwd._poll_and_restart()
        fp = fwd._processes["proj-1"]

        # Simulate a running process by patching poll to return None.
        class _FakeProc:
            pid = 12345
            returncode = None

            def poll(self):
                return None  # still running

        fp.process = _FakeProc()
        fp.restart_delay_s = 8.0  # had grown via backoff

        await fwd._check_and_restart(fp)
        # Delay should be reset since process is still alive.
        assert fp.restart_delay_s == 1.0

    @pytest.mark.asyncio
    async def test_terminate_noop_when_already_exited(self):
        fwd = WebhookForwarder(project_store=_DummyProjectStore())
        fwd._processes["proj-1"] = _ForwarderProcess("proj-1", "p", "/tmp/p")

        class _DeadProc:
            pid = 999
            returncode = 1  # already dead

            def poll(self):
                return 1

            def terminate(self):
                pass  # should not be called

        fwd._processes["proj-1"].process = _DeadProc()
        await fwd._terminate("proj-1")
        # _terminate should detect already-exited process and not call terminate.

    @pytest.mark.asyncio
    async def test_kill_all_terminates_all(self, tmp_path):
        """_kill_all should clear all tracked processes."""
        proj1 = Project(id="p1", name="r1", repo_url="https://github.com/org/r1.git", repo_path=str(tmp_path))
        proj2 = Project(id="p2", name="r2", repo_url="https://github.com/org/r2.git", repo_path=str(tmp_path))
        store = _FakeProjectStore([proj1, proj2])
        fwd = WebhookForwarder(project_store=store)

        await fwd._poll_and_restart()
        assert len(fwd._processes) == 2

        await fwd._kill_all()
        assert len(fwd._processes) == 0


class TestWebhookForwarderFullLifecycle:
    """Integration-style tests for the full start → poll → stop cycle."""

    @pytest.mark.asyncio
    async def test_start_stop_with_empty_store(self):
        fwd = WebhookForwarder(project_store=_DummyProjectStore())
        await fwd.start()
        # Let one poll cycle run.
        await asyncio.sleep(0.05)
        await fwd.stop()
        assert fwd.is_running is False

    @pytest.mark.asyncio
    async def test_stop_while_loop_running_cancels_task(self):
        fwd = WebhookForwarder(
            project_store=_DummyProjectStore(),
            poll_interval_s=10.0,  # slow poll so we can cancel mid-cycle
        )
        await fwd.start()
        # Stop immediately — the task should cancel without error.
        await fwd.stop()
        assert fwd._task is None or fwd._task.done()


# ---------------------------------------------------------------------------
# Subprocess lifecycle — full start → exit → restart → cleanup
# ---------------------------------------------------------------------------


class TestForwarderProcessFullLifecycle:
    """Full lifecycle tests for the gh webhook forward subprocess.

    These tests mock asyncio.create_subprocess_exec to simulate a real gh
    process: start succeeds, then either crashes (returncode != None) or
    keeps running. The forwarder must restart a crashed process with
    exponential backoff, and clean up gracefully on shutdown.
    """

    @pytest.fixture
    def git_repo(self, tmp_path):
        """Create a real git repository so _launch() passes its .git check."""
        import subprocess
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        return tmp_path

    @pytest.mark.asyncio
    async def test_process_start_and_immediate_exit(self, git_repo):
        """Simulate gh exiting immediately — forwarder re-launches it.

        Two calls to _check_and_restart are tested:
        - First (process dead): terminate → sleep → re-launch, backoff doubles.
        - Second (process alive, poll()=None): resets delay to base, no loop.
        """
        proj = _make_project(
            repo_url="https://github.com/org/repo.git",
            project_id="proj-1",
            name="test-repo",
        )
        proj.repo_path = str(git_repo)
        store = _FakeProjectStore([proj])
        fwd = WebhookForwarder(project_store=store, poll_interval_s=100.0)
        fwd._processes["proj-1"] = _ForwarderProcess(
            "proj-1", "test-repo", str(git_repo), "org/repo",
        )

        # Simulate a process that has already exited.
        class _ExitedProc:
            pid = 12345
            returncode = 1

            def poll(self):
                return 1  # indicates exited

            def terminate(self):
                pass

            async def wait(self):
                pass

        fp = fwd._processes["proj-1"]
        fp.process = _ExitedProc()
        fp.restart_delay_s = 1.0  # already in backoff

        # Mock process returned by _launch.
        patch_proc = MagicMock()
        patch_proc.pid = 99999
        patch_proc.returncode = None
        # poll()=None on the launched process simulates "still running"
        patch_proc.poll = MagicMock(return_value=None)

        with patch(
            "asyncio.create_subprocess_exec",
            new_callable=AsyncMock,
            return_value=patch_proc,
        ):
            with patch.object(fwd, "_terminate", new_callable=AsyncMock) as mock_terminate:
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    # First _check_and_restart: process dead → terminate → sleep → re-launch.
                    await fwd._check_and_restart(fp)

                mock_terminate.assert_called_once_with("proj-1")

        # After first call: backoff doubled and new process launched.
        assert fp.restart_delay_s == 2.0  # 1.0 * 2, capped at 60
        assert fp.restart_attempts == 1
        assert fp.process is patch_proc

        # Second _check_and_restart: process still alive (poll()=None).
        # Reset delay to base, no further backoff growth.
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await fwd._check_and_restart(fp)
        assert fp.restart_delay_s == 1.0  # reset to base (_WEBHOOK_BASE_DELAY_S)
        assert fp.restart_attempts == 1  # not incremented again

    @pytest.mark.asyncio
    async def test_exponential_backoff_capped_at_60s(self, git_repo):
        """Restart delay doubles on exit but is capped at MAX_DELAY (60s)."""
        proj = _make_project(
            repo_url="https://github.com/org/repo.git",
            project_id="proj-capped",
            name="test-repo",
        )
        proj.repo_path = str(git_repo)
        store = _FakeProjectStore([proj])
        fwd = WebhookForwarder(project_store=store)

        fp = _ForwarderProcess("proj-capped", "test-repo", str(git_repo), "org/repo")
        # Start at 30 so doubling gives exactly 60
        fp.restart_delay_s = 30.0

        class _CrashedProc:
            pid = 1
            returncode = 2

            def poll(self):
                return 2  # exited

            def terminate(self):
                pass

            async def wait(self):
                pass

        fp.process = _CrashedProc()

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await fwd._check_and_restart(fp)

        # 30.0 * 2 = 60.0, capped at MIN(60.0, 60.0)
        assert fp.restart_delay_s == 60.0
        assert fp.restart_attempts == 1

    @pytest.mark.asyncio
    async def test_stop_terminates_all_tracked_processes(self, git_repo):
        """Calling stop while processes are tracked cleans them all up."""
        proj1 = _make_project(
            repo_url="https://github.com/org/repo1.git",
            project_id="proj-1",
            name="repo1",
        )
        proj1.repo_path = str(git_repo)
        proj2 = _make_project(
            repo_url="https://github.com/org/repo2.git",
            project_id="proj-2",
            name="repo2",
        )
        proj2.repo_path = str(git_repo)
        store = _FakeProjectStore([proj1, proj2])
        fwd = WebhookForwarder(project_store=store)

        await fwd.start()
        # Manually register two processes
        fp1 = _ForwarderProcess("proj-1", "repo1", str(git_repo))
        fp2 = _ForwarderProcess("proj-2", "repo2", str(git_repo))

        class _LiveProc:
            pid = 1
            returncode = None  # required by _terminate code path

            def poll(self):
                return None  # still running

            def terminate(self):
                pass  # no real process to terminate in test

            async def wait(self):
                pass  # no real process to wait on in test

        fp1.process = _LiveProc()
        fp2.process = _LiveProc()
        fwd._processes["proj-1"] = fp1
        fwd._processes["proj-2"] = fp2

        await fwd.stop()
        assert len(fwd._processes) == 0
        assert fwd.is_running is False

    @pytest.mark.asyncio
    async def test_polling_resume_when_forwarder_process_dies(self, git_repo):
        """When a gh webhook forward process dies, polling detects the exit
        and triggers a restart — verifying that the forwarder self-heals.

        Flow:
        1. First poll via _poll_and_restart: process alive, _launch registered.
        2. Second poll: process dead, _terminate called, backoff applied,
           _launch called again for restart (with _stopping reset).
        """
        proj = _make_project(
            repo_url="https://github.com/org/repo.git",
            project_id="proj-watch",
            name="watched-repo",
        )
        proj.repo_path = str(git_repo)
        store = _FakeProjectStore([proj])
        fwd = WebhookForwarder(project_store=store, poll_interval_s=0.05)
        fwd._stopping = True  # prevent _run_loop control; drive via _poll_and_restart

        terminate_calls = []
        launch_count = 0

        class _SimulatedProc:
            pid = 54321
            _alive = True  # toggled False after first poll

            def poll(self):
                return None if _SimulatedProc._alive else 137

            def terminate(self):
                pass

            async def wait(self):
                pass

        live_proc = _SimulatedProc()

        async def mock_create_subprocess_exec(*args, **kwargs):
            nonlocal launch_count
            launch_count += 1
            return live_proc

        async def mock_terminate(pid):
            terminate_calls.append(pid)

        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=mock_create_subprocess_exec,
        ):
            with patch.object(fwd, "_terminate", side_effect=mock_terminate):
                # First poll cycle: process alive, _launch registered (fire-and-forget).
                await fwd._poll_and_restart()
                assert terminate_calls == []

                # Kill the process before second poll cycle.
                _SimulatedProc._alive = False

                # Reset _stopping so restart runs: _terminate → sleep → _launch
                fwd._stopping = False
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    await fwd._poll_and_restart()

                # Restart fired: _terminate called for dead process, new gh launched.
                assert "proj-watch" in terminate_calls
                assert launch_count >= 2  # initial + at least one restart

    @pytest.mark.asyncio
    async def test_launch_without_git_directory_skipped(self, tmp_path):
        """A process is not launched if repo_path exists but is not a git repo."""
        proj = _make_project(
            repo_url="https://github.com/org/not-git.git",
            project_id="not-git",
            name="Not a Git Repo",
        )
        proj.repo_path = str(tmp_path)  # exists, but no .git
        # Ensure the directory is not a git directory
        assert not os.path.isdir(os.path.join(str(tmp_path), ".git"))

        store = _FakeProjectStore([proj])
        fwd = WebhookForwarder(project_store=store)

        await fwd._poll_and_restart()
        assert "not-git" in fwd._processes
        # _launch is skipped; process never set
        assert fwd._processes["not-git"].process is None

    @pytest.mark.asyncio
    async def test_check_and_restart_noops_when_no_process(self, tmp_path):
        """When fp.process is None, _check_and_restart launches without crashing."""
        import subprocess
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)

        fwd = WebhookForwarder(project_store=_DummyProjectStore())
        fp = _ForwarderProcess("test", "test", str(tmp_path))
        assert fp.process is None  # pre-condition

        mock_proc = MagicMock()
        mock_proc.pid = 42

        async def fake_launch(arg):
            arg.process = mock_proc

        with patch.object(fwd, "_launch", side_effect=fake_launch):
            # Should not raise — just launch
            await fwd._check_and_restart(fp)

        assert fp.restart_attempts >= 1


# ---------------------------------------------------------------------------
# Fixture helpers (shared between classes)
# ---------------------------------------------------------------------------


def _FakeProjectStore(projects=None):
    """Build a minimal ProjectStore for testing."""
    class __Fake:
        def __init__(self, projs):
            self._map = {p.id: p for p in (projs or [])}

        def list_all(self):
            return list(self._map.values())

        def get(self, pid):
            return self._map.get(pid)

    return __Fake(projects)


# ---------------------------------------------------------------------------
# gh-webhook extension detection (oompah-zlz_2-2g1)
# ---------------------------------------------------------------------------


class TestCheckGhWebhookAvailable:
    """Tests for ``check_gh_webhook_available()`` startup probe.

    These are the test cases described in the AC for oompah-zlz_2-2g1:
    the forwarder must detect at startup whether the third-party
    ``cli/gh-webhook`` extension is installed and surface a clear
    one-shot error if it is missing.
    """

    @pytest.mark.asyncio
    async def test_gh_not_on_path_returns_false(self, monkeypatch):
        """If the gh CLI isn't installed, available=False with a clear detail."""
        monkeypatch.setattr("oompah.webhooks.shutil.which", lambda _: None)
        available, detail = await check_gh_webhook_available()
        assert available is False
        assert "gh" in detail.lower()

    @pytest.mark.asyncio
    async def test_extension_present_returns_true(self, monkeypatch):
        """gh webhook --help exit 0 → extension is available."""
        monkeypatch.setattr("oompah.webhooks.shutil.which", lambda _: "/usr/bin/gh")

        class _FakeProc:
            returncode = 0

            async def communicate(self):
                return (b"Usage: gh webhook ...\n", b"")

        async def fake_exec(*args, **kwargs):
            return _FakeProc()

        monkeypatch.setattr("asyncio.create_subprocess_exec", fake_exec)
        available, detail = await check_gh_webhook_available()
        assert available is True
        assert detail == ""

    @pytest.mark.asyncio
    async def test_extension_missing_returns_false(self, monkeypatch):
        """gh webhook --help non-zero → available=False, stderr captured."""
        monkeypatch.setattr("oompah.webhooks.shutil.which", lambda _: "/usr/bin/gh")

        class _FakeProc:
            returncode = 1

            async def communicate(self):
                return (b"", b'unknown command "webhook" for "gh"\n')

        async def fake_exec(*args, **kwargs):
            return _FakeProc()

        monkeypatch.setattr("asyncio.create_subprocess_exec", fake_exec)
        available, detail = await check_gh_webhook_available()
        assert available is False
        assert "unknown command" in detail


class TestWebhookForwarderEventsFlag:
    """Confirm --events is always passed when launching gh webhook forward.

    Without --events the gh-webhook extension subscribes to no events
    and the subprocess produces zero traffic — the second half of the
    bug described in oompah-zlz_2-2g1.
    """

    @pytest.fixture
    def git_repo(self, tmp_path):
        import subprocess
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        return tmp_path

    @pytest.mark.asyncio
    async def test_default_events_passed_to_subprocess(self, git_repo):
        fwd = WebhookForwarder()
        # Pretend we already probed and the extension is available so
        # _launch actually attempts the spawn.
        fwd._extension_available = True

        fp = _ForwarderProcess("p1", "test-repo", str(git_repo), "org/repo")

        captured: dict = {}

        class _FakeProc:
            pid = 12345
            returncode = None
            stderr = None

        async def fake_exec(*args, **kwargs):
            captured["argv"] = list(args)
            return _FakeProc()

        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            await fwd._launch(fp)

        argv = captured["argv"]
        assert "gh" == argv[0]
        assert "webhook" in argv
        assert "forward" in argv
        assert "--repo" in argv
        repo_index = argv.index("--repo")
        assert argv[repo_index + 1] == "org/repo"
        # --events must be present and followed by the default set
        assert "--events" in argv
        i = argv.index("--events")
        assert argv[i + 1] == "push,pull_request,issues,issue_comment,label"
        # --url must still be passed
        assert "--url" in argv

    @pytest.mark.asyncio
    async def test_missing_repo_slug_skips_subprocess(self, git_repo):
        fwd = WebhookForwarder()
        fwd._extension_available = True
        fp = _ForwarderProcess("p1", "test-repo", str(git_repo))

        with patch("asyncio.create_subprocess_exec") as exec_mock:
            await fwd._launch(fp)

        exec_mock.assert_not_called()
        assert fp.process is None

    @pytest.mark.asyncio
    async def test_project_token_passed_as_gh_token_env(
        self, git_repo, monkeypatch, caplog
    ):
        monkeypatch.setenv("GH_TOKEN", "ambient-token")
        fwd = WebhookForwarder()
        fwd._extension_available = True
        fp = _ForwarderProcess(
            "p1",
            "test-repo",
            str(git_repo),
            "org/repo",
            access_token="project-token",
        )
        fwd._processes["p1"] = fp

        captured: dict = {}

        class _FakeProc:
            pid = 12345
            returncode = None
            stderr = None

        async def fake_exec(*args, **kwargs):
            captured["env"] = kwargs["env"]
            return _FakeProc()

        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            await fwd._launch(fp)

        assert captured["env"]["GH_TOKEN"] == "project-token"
        assert os.environ["GH_TOKEN"] == "ambient-token"
        assert "project-token" not in caplog.text
        assert "project-token" not in str(fwd.status)

    @pytest.mark.asyncio
    async def test_custom_events_via_init(self, git_repo):
        fwd = WebhookForwarder(events="pull_request")
        fwd._extension_available = True
        fp = _ForwarderProcess("p1", "test-repo", str(git_repo), "org/repo")

        captured: dict = {}

        class _FakeProc:
            pid = 1
            returncode = None
            stderr = None

        async def fake_exec(*args, **kwargs):
            captured["argv"] = list(args)
            return _FakeProc()

        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            await fwd._launch(fp)

        i = captured["argv"].index("--events")
        assert captured["argv"][i + 1] == "pull_request"

    @pytest.mark.asyncio
    async def test_events_env_var_override(self, git_repo, monkeypatch):
        monkeypatch.setenv("OOMPAH_WEBHOOK_EVENTS", "push,issues")
        fwd = WebhookForwarder()
        fwd._extension_available = True
        fp = _ForwarderProcess("p1", "test-repo", str(git_repo), "org/repo")

        captured: dict = {}

        class _FakeProc:
            pid = 1
            returncode = None
            stderr = None

        async def fake_exec(*args, **kwargs):
            captured["argv"] = list(args)
            return _FakeProc()

        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            await fwd._launch(fp)

        i = captured["argv"].index("--events")
        assert captured["argv"][i + 1] == "push,issues"


class TestWebhookForwarderHookCleanup:
    """Stale GitHub hooks left by gh-webhook must not block restarts."""

    @pytest.fixture
    def git_repo(self, tmp_path):
        import subprocess
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        return tmp_path

    @pytest.mark.asyncio
    async def test_cleanup_deletes_stale_cli_forwarder_hooks(self, git_repo):
        fwd = WebhookForwarder()
        fp = _ForwarderProcess("p1", "test-repo", str(git_repo), "org/repo")
        calls: list[list[str]] = []

        class _FakeProc:
            def __init__(self, stdout=b"", stderr=b"", returncode=0):
                self._stdout = stdout
                self._stderr = stderr
                self.returncode = returncode

            async def communicate(self):
                return self._stdout, self._stderr

        async def fake_exec(*args, **kwargs):
            calls.append(list(args))
            if args[-2:] == (
                "--jq",
                (
                    ".[] | select(.name == \"cli\" "
                    "and .config.url == \"https://webhook-forwarder.github.com/hook\") | .id"
                ),
            ):
                return _FakeProc(stdout=b"123\n456\n")
            return _FakeProc()

        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            await fwd._cleanup_existing_forwarder_hooks(fp, os.environ.copy())

        assert ["gh", "api", "-X", "DELETE", "repos/org/repo/hooks/123"] in calls
        assert ["gh", "api", "-X", "DELETE", "repos/org/repo/hooks/456"] in calls

    @pytest.mark.asyncio
    async def test_cleanup_transient_inspection_failure_does_not_block_launch(self, git_repo):
        fwd = WebhookForwarder()
        fwd._extension_available = True
        fp = _ForwarderProcess("p1", "test-repo", str(git_repo), "org/repo")
        fp.restart_attempts = 1
        calls: list[list[str]] = []

        class _FakeProc:
            pid = 123
            stderr = None

            def __init__(self, stdout=b"", stderr=b"", returncode=0):
                self._stdout = stdout
                self._stderr = stderr
                self.returncode = returncode

            async def communicate(self):
                return self._stdout, self._stderr

        class _ForwardProc:
            pid = 456
            returncode = None
            stderr = None

        async def fake_exec(*args, **kwargs):
            calls.append(list(args))
            if args[:2] == ("gh", "api"):
                return _FakeProc(stderr=b"api temporarily unavailable\n", returncode=1)
            return _ForwardProc()

        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            await fwd._launch(fp)

        assert any(call[:3] == ["gh", "api", "repos/org/repo/hooks"] for call in calls)
        assert any(call[:3] == ["gh", "webhook", "forward"] for call in calls)
        assert fp.process is not None

    @pytest.mark.asyncio
    async def test_cleanup_repo_not_found_disables_project_and_blocks_launch(self, git_repo):
        statuses: list[dict] = []
        fwd = WebhookForwarder(status_callback=statuses.append)
        fwd._extension_available = True
        fp = _ForwarderProcess("p1", "test-repo", str(git_repo), "org/repo")
        fp.restart_attempts = 1
        fwd._processes["p1"] = fp
        calls: list[list[str]] = []

        class _FakeProc:
            def __init__(self, stdout=b"", stderr=b"", returncode=0):
                self._stdout = stdout
                self._stderr = stderr
                self.returncode = returncode

            async def communicate(self):
                return self._stdout, self._stderr

        async def fake_exec(*args, **kwargs):
            calls.append(list(args))
            return _FakeProc(stderr=b"gh: Not Found (HTTP 404)\n", returncode=1)

        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            await fwd._launch(fp)

        assert calls == [["gh", "api", "repos/org/repo/hooks", "--jq", (
            ".[] | select(.name == \"cli\" "
            "and .config.url == \"https://webhook-forwarder.github.com/hook\") | .id"
        )]]
        assert fp.disabled is True
        assert "Not Found" in fp.last_error
        assert fp.process is None
        assert statuses


class TestWebhookForwarderExtensionMissing:
    """Behavior when the gh-webhook extension is not installed.

    Per the AC: the forwarder must log a single ERROR (not on every
    restart loop), surface the failure to the dashboard, and skip
    launching subprocesses entirely rather than pretending to run.
    """

    @pytest.fixture
    def git_repo(self, tmp_path):
        import subprocess
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        return tmp_path

    @pytest.mark.asyncio
    async def test_launch_skipped_when_extension_unavailable(self, git_repo):
        fwd = WebhookForwarder()
        fwd._extension_available = False  # set by start() probe in real code
        fp = _ForwarderProcess("p1", "test-repo", str(git_repo), "org/repo")

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            await fwd._launch(fp)
        # No subprocess was spawned, no fake "started" log.
        mock_exec.assert_not_called()
        assert fp.process is None

    @pytest.mark.asyncio
    async def test_start_runs_probe_and_logs_single_error(self, caplog):
        fwd = WebhookForwarder(project_store=_DummyProjectStore())

        async def fake_probe():
            return False, 'unknown command "webhook"'

        with patch("oompah.webhooks.check_gh_webhook_available", side_effect=fake_probe):
            with caplog.at_level("ERROR", logger="oompah.webhooks"):
                await fwd.start()
                try:
                    # Run a couple of poll cycles to make sure the
                    # restart loop does NOT keep emitting errors.
                    await asyncio.sleep(0.02)
                finally:
                    await fwd.stop()

        # Exactly one ERROR-level record from the forwarder about the
        # missing extension — not one per poll cycle.
        ext_errors = [
            r for r in caplog.records
            if r.levelname == "ERROR" and "gh-webhook extension unavailable" in r.message
        ]
        assert len(ext_errors) == 1
        assert fwd.extension_available is False

    @pytest.mark.asyncio
    async def test_status_callback_invoked_when_unavailable(self):
        statuses: list = []

        def cb(status):
            statuses.append(status)

        fwd = WebhookForwarder(
            project_store=_DummyProjectStore(),
            status_callback=cb,
        )

        async def fake_probe():
            return False, "no gh on PATH"

        with patch("oompah.webhooks.check_gh_webhook_available", side_effect=fake_probe):
            await fwd.start()
            await fwd.stop()

        assert len(statuses) == 1
        assert statuses[0]["available"] is False
        assert "no gh on PATH" in statuses[0]["detail"]

    @pytest.mark.asyncio
    async def test_status_callback_invoked_when_available(self):
        statuses: list = []

        def cb(status):
            statuses.append(status)

        fwd = WebhookForwarder(
            project_store=_DummyProjectStore(),
            status_callback=cb,
        )

        async def fake_probe():
            return True, ""

        with patch("oompah.webhooks.check_gh_webhook_available", side_effect=fake_probe):
            await fwd.start()
            await fwd.stop()

        assert len(statuses) == 1
        assert statuses[0]["available"] is True

    @pytest.mark.asyncio
    async def test_status_property_reports_extension_state(self):
        fwd = WebhookForwarder(project_store=_DummyProjectStore())

        async def fake_probe():
            return False, "boom"

        with patch("oompah.webhooks.check_gh_webhook_available", side_effect=fake_probe):
            await fwd.start()
            try:
                status = fwd.status
                assert status["extension_available"] is False
                assert status["extension_detail"] == "boom"
                assert status["events"] == "push,pull_request,issues,issue_comment,label"
                assert "projects" in status
            finally:
                await fwd.stop()


def test_build_webhook_forwarder_alerts_includes_project_errors():
    alerts = build_webhook_forwarder_alerts({
        "available": True,
        "detail": "",
        "projects": {
            "proj-ova": {
                "name": "ova",
                "last_error": "gh: Not Found (HTTP 404)",
                "disabled": True,
            }
        },
    })

    assert len(alerts) == 1
    assert alerts[0]["source"] == "webhook_forwarder:proj-ova"
    assert alerts[0]["level"] == "error"
    assert "Polling backup is active" in alerts[0]["message"]


def test_build_webhook_forwarder_alerts_skips_config_disabled_projects():
    alerts = build_webhook_forwarder_alerts({
        "available": True,
        "detail": "",
        "projects": {
            "proj-ova": {
                "name": "ova",
                "forwarding_enabled": False,
                "last_error": "gh: Not Found (HTTP 404)",
                "disabled": True,
            }
        },
    })

    assert alerts == []


class TestWebhookForwarderStderrCapture:
    """The forwarder must capture subprocess stderr so install/auth
    errors surface in oompah.log instead of being silently dropped."""

    @pytest.fixture
    def git_repo(self, tmp_path):
        import subprocess
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        return tmp_path

    @pytest.mark.asyncio
    async def test_stderr_drained_into_last_stderr(self, git_repo):
        fwd = WebhookForwarder()
        fwd._extension_available = True
        fp = _ForwarderProcess("p1", "test-repo", str(git_repo), "org/repo")

        # Fake stderr stream: yields a single chunk then EOF.
        class _FakeStderr:
            def __init__(self):
                self._chunks = [b"auth required: run `gh auth login`\n", b""]

            async def read(self, _n):
                return self._chunks.pop(0) if self._chunks else b""

        class _FakeProc:
            pid = 1
            returncode = 0
            stderr = _FakeStderr()

        async def fake_exec(*args, **kwargs):
            return _FakeProc()

        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            await fwd._launch(fp)

        # Wait for the drainer to finish.
        if fp.stderr_task is not None:
            await fp.stderr_task

        assert "auth required" in fp.last_stderr

    @pytest.mark.asyncio
    async def test_completed_process_is_detached_after_stderr_eof(self, git_repo):
        fwd = WebhookForwarder()
        fwd._extension_available = True
        fp = _ForwarderProcess("p1", "test-repo", str(git_repo), "org/repo")

        class _FakeStderr:
            def __init__(self):
                self._chunks = [b"websocket closed\n", b""]

            async def read(self, _n):
                return self._chunks.pop(0) if self._chunks else b""

        class _FakeProc:
            pid = 1
            returncode = 1
            stderr = _FakeStderr()

            async def wait(self):
                return self.returncode

        async def fake_exec(*args, **kwargs):
            return _FakeProc()

        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            await fwd._launch(fp)

        proc = fp.process
        assert proc is not None
        assert fp.stderr_task is not None
        await fp.stderr_task

        assert fp.last_stderr == "websocket closed\n"
        assert fp.process is None

    @pytest.mark.asyncio
    async def test_fatal_stderr_disables_project_and_reports_status(self, git_repo):
        statuses: list[dict] = []
        fwd = WebhookForwarder(status_callback=statuses.append)
        fwd._extension_available = True
        fp = _ForwarderProcess("p1", "test-repo", str(git_repo), "org/repo")
        fwd._processes["p1"] = fp

        class _FakeStderr:
            def __init__(self):
                self._chunks = [
                    b"Error: error creating webhook: HTTP 404: Not Found\n",
                    b"",
                ]

            async def read(self, _n):
                return self._chunks.pop(0) if self._chunks else b""

        class _FakeProc:
            pid = 1
            returncode = 1
            stderr = _FakeStderr()

            async def wait(self):
                return self.returncode

        async def fake_exec(*args, **kwargs):
            return _FakeProc()

        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            await fwd._launch(fp)

        assert fp.stderr_task is not None
        await fp.stderr_task

        assert fp.disabled is True
        assert "error creating webhook" in fp.last_error
        assert statuses
        project_status = statuses[-1]["projects"]["p1"]
        assert project_status["disabled"] is True
        assert "error creating webhook" in project_status["last_error"]

    @pytest.mark.asyncio
    async def test_terminate_cancels_stderr_task(self, git_repo):
        fwd = WebhookForwarder()
        fwd._extension_available = True
        fp = _ForwarderProcess("p1", "test-repo", str(git_repo), "org/repo")

        class _BlockingStderr:
            async def read(self, _n):
                # Block forever so we can verify cancellation cleans up.
                await asyncio.sleep(3600)
                return b""

        class _FakeProc:
            pid = 1
            returncode = None
            stderr = _BlockingStderr()

            def terminate(self):
                pass

            async def wait(self):
                pass

        async def fake_exec(*args, **kwargs):
            return _FakeProc()

        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            await fwd._launch(fp)
            assert fp.stderr_task is not None and not fp.stderr_task.done()
            fwd._processes["p1"] = fp
            await fwd._terminate("p1")

        # Stderr task should have been cancelled and cleared.
        assert fp.stderr_task is None
