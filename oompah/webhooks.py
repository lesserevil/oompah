"""Forge webhook receiver for GitHub and GitLab.

Parses webhook payloads, validates HMAC signatures (GitHub) or secret
tokens (GitLab), and extracts PR/MR event information for the EventBus.

Usage::

    from oompah.webhooks import (
        validate_github_signature,
        validate_gitlab_token,
        parse_github_webhook,
        parse_gitlab_webhook,
        WebhookEvent,
    )
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class WebhookEvent:
    """Normalized event extracted from a forge webhook payload.

    Attributes:
        provider: ``"github"`` or ``"gitlab"``.
        event_type: The webhook event type header value
                    (e.g. ``"pull_request"``, ``"Merge Request Hook"``).
        action: The action within the event (e.g. ``"opened"``, ``"closed"``).
        repo_slug: ``"owner/repo"`` or ``"group/project"``.
        review_id: The PR/MR number as a string.
        source_branch: The head/source branch name.
        target_branch: The base/target branch name.
        author: The login/username of the PR/MR author.
        title: The PR/MR title.
        merged: Whether the PR/MR was merged.
        raw: The full raw payload dict for downstream consumers.
    """

    provider: str
    event_type: str
    action: str
    repo_slug: str = ""
    review_id: str = ""
    source_branch: str = ""
    target_branch: str = ""
    author: str = ""
    title: str = ""
    merged: bool = False
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


# ---------------------------------------------------------------------------
# GitHub
# ---------------------------------------------------------------------------


def validate_github_signature(
    payload_body: bytes, signature_header: str, secret: str
) -> bool:
    """Validate a GitHub webhook HMAC-SHA256 signature.

    GitHub sends the signature in the ``X-Hub-Signature-256`` header as
    ``sha256=<hex_digest>``.

    Args:
        payload_body: Raw request body bytes.
        signature_header: Value of the ``X-Hub-Signature-256`` header.
        secret: The shared webhook secret string.

    Returns:
        ``True`` if the signature is valid, ``False`` otherwise.
    """
    if not signature_header or not secret:
        return False

    prefix = "sha256="
    if not signature_header.startswith(prefix):
        return False

    expected_sig = signature_header[len(prefix):]

    mac = hmac.new(
        secret.encode("utf-8"),
        msg=payload_body,
        digestmod=hashlib.sha256,
    )
    computed = mac.hexdigest()

    return hmac.compare_digest(computed, expected_sig)


def parse_github_webhook(
    event_type: str, payload: dict[str, Any]
) -> WebhookEvent | None:
    """Parse a GitHub webhook payload into a WebhookEvent.

    Only PR-related events are parsed (``pull_request``). Other event
    types return ``None``.

    Args:
        event_type: Value of the ``X-GitHub-Event`` header.
        payload: Parsed JSON body.

    Returns:
        A ``WebhookEvent`` for PR events, or ``None`` for non-PR events.
    """
    if event_type != "pull_request":
        logger.debug("Ignoring non-PR GitHub event: %s", event_type)
        return None

    action = payload.get("action", "")
    pr = payload.get("pull_request", {})
    if not pr:
        return None

    repo = payload.get("repository", {})
    repo_slug = repo.get("full_name", "")

    head = pr.get("head", {})
    base = pr.get("base", {})
    user = pr.get("user", {})

    return WebhookEvent(
        provider="github",
        event_type=event_type,
        action=action,
        repo_slug=repo_slug,
        review_id=str(pr.get("number", "")),
        source_branch=head.get("ref", ""),
        target_branch=base.get("ref", ""),
        author=user.get("login", ""),
        title=pr.get("title", ""),
        merged=bool(pr.get("merged", False)),
        raw=payload,
    )


# ---------------------------------------------------------------------------
# GitLab
# ---------------------------------------------------------------------------


def validate_gitlab_token(
    token_header: str, secret: str
) -> bool:
    """Validate a GitLab webhook secret token.

    GitLab sends the secret in the ``X-Gitlab-Token`` header as a plain
    string that must match the configured secret exactly.

    Args:
        token_header: Value of the ``X-Gitlab-Token`` header.
        secret: The shared webhook secret string.

    Returns:
        ``True`` if the token matches, ``False`` otherwise.
    """
    if not token_header or not secret:
        return False
    return hmac.compare_digest(token_header, secret)


def parse_gitlab_webhook(
    event_type: str, payload: dict[str, Any]
) -> WebhookEvent | None:
    """Parse a GitLab webhook payload into a WebhookEvent.

    Only MR-related events are parsed (``Merge Request Hook``). Other
    event types return ``None``.

    Args:
        event_type: Value of the ``X-Gitlab-Event`` header.
        payload: Parsed JSON body.

    Returns:
        A ``WebhookEvent`` for MR events, or ``None`` for non-MR events.
    """
    if event_type != "Merge Request Hook":
        logger.debug("Ignoring non-MR GitLab event: %s", event_type)
        return None

    attrs = payload.get("object_attributes", {})
    if not attrs:
        return None

    project = payload.get("project", {})
    repo_slug = project.get("path_with_namespace", "")

    user = payload.get("user", {})

    action = attrs.get("action", "")
    state = attrs.get("state", "")
    merged = state == "merged"

    return WebhookEvent(
        provider="gitlab",
        event_type=event_type,
        action=action,
        repo_slug=repo_slug,
        review_id=str(attrs.get("iid", "")),
        source_branch=attrs.get("source_branch", ""),
        target_branch=attrs.get("target_branch", ""),
        author=user.get("username", ""),
        title=attrs.get("title", ""),
        merged=merged,
        raw=payload,
    )


# ---------------------------------------------------------------------------
# Matching helpers
# ---------------------------------------------------------------------------


def match_project_by_repo(
    projects: list, repo_slug: str, provider: str
) -> Any | None:
    """Find the project whose repo_url matches the webhook's repo slug.

    Uses the same slug extraction logic as the SCM module so that
    ``"owner/repo"`` matches ``"https://github.com/owner/repo.git"``.

    Args:
        projects: List of ``Project`` objects.
        repo_slug: The ``"owner/repo"`` slug from the webhook.
        provider: ``"github"`` or ``"gitlab"``.

    Returns:
        The matching ``Project``, or ``None``.
    """
    from oompah.scm import extract_repo_slug

    for project in projects:
        slug = extract_repo_slug(project.repo_url)
        if slug == repo_slug:
            return project
    return None
