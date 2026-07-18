"""Forge webhook receiver for GitHub and GitLab, and gh webhook forwarder.

Parses webhook payloads, validates HMAC signatures (GitHub) or secret
tokens (GitLab), and extracts PR/MR event information for the EventBus.

The WebhookForwarder class manages 'gh webhook forward' subprocesses for
each project, monitoring health and restarting on failure. It depends on
the third-party ``cli/gh-webhook`` gh extension and probes for it at
startup; if the extension is missing, a single ERROR is logged and the
forwarder skips launching subprocesses (rather than silently no-op'ing
as in the original bug — see issue ``oompah-zlz_2-2g1``).

See ``docs/webhook-forwarding.md`` for setup, verification, and
troubleshooting.

Usage::

    from oompah.webhooks import (
        validate_github_signature,
        validate_gitlab_token,
        parse_github_webhook,
        parse_gitlab_webhook,
        WebhookEvent,
        WebhookForwarder,
        check_gh_webhook_available,
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
        issue_number: The GitHub issue number as a string.  Set for
                      ``issues`` and ``issue_comment`` events so
                      downstream consumers can key cache invalidations
                      without inspecting ``raw``.
        comment_id: The comment node id or numeric id as a string.  Set
                    for ``issue_comment`` events.
        label_name: The label name.  Set for ``label`` events (repository-
                    level label management) and for ``issues`` events with
                    action ``labeled`` or ``unlabeled`` where the label
                    being applied/removed is carried in ``payload.label``.
        label_actor: The GitHub login of the user who applied or removed
                     the label.  Set for ``issues`` events with action
                     ``labeled`` or ``unlabeled``.  Distinct from
                     ``author`` (the issue creator); the label actor is
                     always ``payload.sender.login``.
        project_item_id: The ``projects_v2_item`` node id.  Set for
                         ``projects_v2_item`` events.
        project_field_name: The name of the changed field.  Set for
                            ``projects_v2_item`` ``edited`` events when
                            the ``changes.field_value`` key is present.
        project_field_value: The new field value as a string.  Set for
                             ``projects_v2_item`` ``edited`` events.
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
    # Issue-specific fields
    issue_number: str = ""
    comment_id: str = ""
    # Label-specific fields
    label_name: str = ""
    # The login of the user who applied or removed a label on an issue.
    # Set only for ``issues`` events with action ``labeled``/``unlabeled``.
    # Always sourced from ``payload.sender.login``, never from the issue author.
    label_actor: str = ""
    # GitHub Projects v2 fields
    project_item_id: str = ""
    project_field_name: str = ""
    project_field_value: str = ""


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

    Handles ``pull_request``, ``push``, and ``merge_group`` events.
    ``push`` events surface direct commits to a branch (e.g. operators
    pushing chore commits to main without a PR) — the tracked-branch
    advancing is the signal that a source resync is needed.
    ``merge_group`` events fire when GitHub's merge queue processes a PR;
    a ``checks_requested`` action starts CI on the merge-group ref, and a
    ``destroyed`` action fires when the queue removes the group (either
    because it merged successfully or was ejected due to failing CI).
    Other event types return ``None``.

    Args:
        event_type: Value of the ``X-GitHub-Event`` header.
        payload: Parsed JSON body.

    Returns:
        A ``WebhookEvent`` for PR/push/merge_group events, or ``None`` for
        other events.
    """
    if event_type == "pull_request":
        return _parse_github_pr(event_type, payload)
    if event_type == "push":
        return _parse_github_push(event_type, payload)
    if event_type == "merge_group":
        return _parse_github_merge_group(event_type, payload)
    if event_type == "issues":
        return _parse_github_issues(event_type, payload)
    if event_type == "issue_comment":
        return _parse_github_issue_comment(event_type, payload)
    if event_type == "label":
        return _parse_github_label(event_type, payload)
    if event_type == "projects_v2_item":
        return _parse_github_projects_v2_item(event_type, payload)
    logger.debug("Ignoring GitHub event: %s", event_type)
    return None


def _parse_github_pr(
    event_type: str, payload: dict[str, Any]
) -> WebhookEvent | None:
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


def _parse_github_push(
    event_type: str, payload: dict[str, Any]
) -> WebhookEvent | None:
    """Parse a GitHub ``push`` event into a WebhookEvent.

    The pushed branch is recorded in ``target_branch`` (since "what branch
    the push affected" is the closest semantic match in the existing
    dataclass). Branch deletions (``deleted: true``) and tag pushes
    (``refs/tags/*``) return ``None`` — neither requires a source resync.
    """
    if payload.get("deleted"):
        return None
    ref = payload.get("ref", "") or ""
    if not ref.startswith("refs/heads/"):
        return None
    branch = ref[len("refs/heads/"):]

    repo = payload.get("repository", {})
    repo_slug = repo.get("full_name", "")

    pusher = payload.get("pusher") or {}
    sender = payload.get("sender") or {}
    author = pusher.get("name") or sender.get("login", "")

    head_commit = payload.get("head_commit") or {}
    title = (head_commit.get("message") or "").splitlines()[0] if head_commit else ""

    return WebhookEvent(
        provider="github",
        event_type=event_type,
        action="pushed",
        repo_slug=repo_slug,
        review_id="",
        source_branch="",
        target_branch=branch,
        author=author,
        title=title,
        merged=False,
        raw=payload,
    )


def _parse_github_merge_group(
    event_type: str, payload: dict[str, Any]
) -> WebhookEvent | None:
    """Parse a GitHub ``merge_group`` event into a WebhookEvent.

    GitHub fires ``merge_group`` events when the merge queue creates or
    destroys a merge group (a speculatively-stacked candidate ref).

    Actions:
      * ``checks_requested`` — CI has been triggered on the merge-group ref.
      * ``destroyed`` — the merge group was removed.  The ``reason`` field
        distinguishes success (``"merged"`` → ``merged=True``) from failure
        (``"invalidated"`` or ``"dequeued"`` → ``merged=False``).

    The ``head_ref`` of the merge group encodes the source PR branch name in
    the form ``gh-readonly-queue/<base>/<pr-identifier>``.  We surface it
    in ``source_branch`` so downstream consumers can match the task.

    Args:
        event_type: Always ``"merge_group"``.
        payload: Parsed JSON body from GitHub.

    Returns:
        A ``WebhookEvent`` or ``None`` (e.g. for unrecognised payloads).
    """
    action = payload.get("action", "")
    mg = payload.get("merge_group") or {}
    if not mg:
        logger.debug("merge_group event has no merge_group object; ignoring")
        return None

    repo = payload.get("repository") or {}
    repo_slug = repo.get("full_name", "")

    head_ref = mg.get("head_ref", "") or ""
    base_ref = mg.get("base_ref", "") or mg.get("base_sha", "")

    # ``destroyed`` with reason ``"merged"`` means the queue commit landed.
    reason = payload.get("reason", "") or ""
    merged = action == "destroyed" and reason == "merged"

    return WebhookEvent(
        provider="github",
        event_type=event_type,
        action=action,
        repo_slug=repo_slug,
        review_id="",  # merge_group events don't carry a PR number directly
        source_branch=head_ref,
        target_branch=base_ref,
        author="",
        title="",
        merged=merged,
        raw=payload,
    )


def _parse_github_issues(
    event_type: str, payload: dict[str, Any]
) -> WebhookEvent | None:
    """Parse a GitHub ``issues`` event into a WebhookEvent.

    GitHub fires ``issues`` events when an issue is opened, edited,
    deleted, closed, reopened, labeled, unlabeled, assigned, etc.

    Pull-request-backed issues (i.e. payloads whose ``issue`` object
    contains a ``pull_request`` key) are skipped — those are tracked
    through the ``pull_request`` event instead.

    For ``labeled`` and ``unlabeled`` actions, two additional fields
    are populated:

    * ``label_name`` — the name of the label being applied or removed,
      taken from ``payload.label.name`` (the label object in the
      ``issues.labeled`` / ``issues.unlabeled`` payload).
    * ``label_actor`` — the GitHub login of the user who applied or
      removed the label, always taken from ``payload.sender.login``.
      Never taken from ``issue.user.login`` (the issue creator) — the
      sender is the authoritative actor for label-change events.

    Args:
        event_type: Always ``"issues"``.
        payload: Parsed JSON body from GitHub.

    Returns:
        A ``WebhookEvent`` for issue events, or ``None`` for malformed
        or PR-backed payloads.
    """
    action = payload.get("action", "")
    issue = payload.get("issue") or {}
    if not issue:
        return None

    # Skip PR-backed issues — they are handled by the pull_request event.
    if issue.get("pull_request"):
        logger.debug("Skipping issues event for PR-backed issue #%s", issue.get("number"))
        return None

    repo = payload.get("repository") or {}
    repo_slug = repo.get("full_name", "")

    user = issue.get("user") or {}
    sender = payload.get("sender") or {}
    # ``author`` is always the issue creator (issue.user.login).
    author = user.get("login", "") or sender.get("login", "")

    issue_number = str(issue.get("number", "") or "")
    title = issue.get("title", "") or ""

    # For labeled/unlabeled events, capture the label being changed and
    # the actor who made the change.  The actor MUST be sender.login —
    # not the issue creator — because different users may label issues
    # without being the issue author.
    label_name = ""
    label_actor = ""
    if action in ("labeled", "unlabeled"):
        label_obj = payload.get("label") or {}
        label_name = label_obj.get("name", "") or ""
        # Always use sender.login as the label-change actor.
        label_actor = sender.get("login", "") or ""

    return WebhookEvent(
        provider="github",
        event_type=event_type,
        action=action,
        repo_slug=repo_slug,
        review_id=issue_number,
        author=author,
        title=title,
        merged=False,
        raw=payload,
        issue_number=issue_number,
        label_name=label_name,
        label_actor=label_actor,
    )


def _parse_github_issue_comment(
    event_type: str, payload: dict[str, Any]
) -> WebhookEvent | None:
    """Parse a GitHub ``issue_comment`` event into a WebhookEvent.

    GitHub fires ``issue_comment`` events when a comment on an issue (or
    PR) is created, edited, or deleted.

    Args:
        event_type: Always ``"issue_comment"``.
        payload: Parsed JSON body from GitHub.

    Returns:
        A ``WebhookEvent``, or ``None`` for malformed payloads.
    """
    action = payload.get("action", "")
    issue = payload.get("issue") or {}
    comment = payload.get("comment") or {}
    if not issue or not comment:
        return None

    repo = payload.get("repository") or {}
    repo_slug = repo.get("full_name", "")

    comment_user = comment.get("user") or {}
    author = comment_user.get("login", "")

    issue_number = str(issue.get("number", "") or "")
    title = issue.get("title", "") or ""
    comment_id = str(comment.get("id", "") or "")

    return WebhookEvent(
        provider="github",
        event_type=event_type,
        action=action,
        repo_slug=repo_slug,
        review_id=issue_number,
        author=author,
        title=title,
        merged=False,
        raw=payload,
        issue_number=issue_number,
        comment_id=comment_id,
    )


def _parse_github_label(
    event_type: str, payload: dict[str, Any]
) -> WebhookEvent | None:
    """Parse a GitHub ``label`` event into a WebhookEvent.

    GitHub fires ``label`` events when a label is created, edited, or
    deleted in a repository.  These events carry the label metadata but
    are not tied to a specific issue or PR.

    Args:
        event_type: Always ``"label"``.
        payload: Parsed JSON body from GitHub.

    Returns:
        A ``WebhookEvent``, or ``None`` for malformed payloads.
    """
    action = payload.get("action", "")
    label = payload.get("label") or {}
    if not label:
        return None

    repo = payload.get("repository") or {}
    repo_slug = repo.get("full_name", "")

    sender = payload.get("sender") or {}
    author = sender.get("login", "")

    label_name = label.get("name", "") or ""

    return WebhookEvent(
        provider="github",
        event_type=event_type,
        action=action,
        repo_slug=repo_slug,
        author=author,
        title=label_name,
        merged=False,
        raw=payload,
        label_name=label_name,
    )


def _parse_github_projects_v2_item(
    event_type: str, payload: dict[str, Any]
) -> WebhookEvent | None:
    """Parse a GitHub ``projects_v2_item`` event into a WebhookEvent.

    GitHub fires ``projects_v2_item`` events when a project item is
    created, edited, deleted, archived, or reordered on a GitHub
    Projects v2 board.

    For ``edited`` actions the ``changes.field_value`` key (when present)
    carries the name of the changed field and its new value.  We surface
    these in ``project_field_name`` and ``project_field_value`` so cache
    invalidation can react to status-field changes without reading
    ``raw``.

    ``projects_v2_item`` events are organisation- or user-level events
    and do not include a ``repository`` object, so ``repo_slug`` is left
    empty.

    Args:
        event_type: Always ``"projects_v2_item"``.
        payload: Parsed JSON body from GitHub.

    Returns:
        A ``WebhookEvent``, or ``None`` for malformed payloads.
    """
    action = payload.get("action", "")
    item = payload.get("projects_v2_item") or {}
    if not item:
        return None

    sender = payload.get("sender") or {}
    author = sender.get("login", "")

    project_item_id = str(item.get("node_id") or item.get("id") or "")

    # Extract field name and new value from ``changes.field_value`` (only
    # present on ``edited`` events).
    field_name = ""
    field_value = ""
    changes = payload.get("changes") or {}
    field_value_change = changes.get("field_value") or {}
    if field_value_change:
        field_name = str(field_value_change.get("field_name") or "")
        to = field_value_change.get("to") or {}
        # GitHub Projects v2 encodes the new value in a type-specific key.
        # Walk through common keys to find the human-readable value.
        for value_key in ("name", "title", "status_value", "number", "date", "text"):
            candidate = to.get(value_key)
            if candidate is not None:
                field_value = str(candidate)
                break
        if not field_value and to:
            # Fallback: use the first scalar value present.
            for v in to.values():
                if isinstance(v, (str, int, float, bool)) and v is not None:
                    field_value = str(v)
                    break

    return WebhookEvent(
        provider="github",
        event_type=event_type,
        action=action,
        repo_slug="",
        author=author,
        merged=False,
        raw=payload,
        project_item_id=project_item_id,
        project_field_name=field_name,
        project_field_value=field_value,
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


# ---------------------------------------------------------------------------
# Webhook Forwarder
# ---------------------------------------------------------------------------

import asyncio
import os
import shutil
from datetime import datetime, timezone

from oompah.scm import extract_repo_slug


_WEBHOOK_FORWARD_DEFAULT_PORT = 8080
_WEBHOOK_POLL_INTERVAL_S = 5.0  # how often to check process health
_WEBHOOK_BASE_DELAY_S = 1.0  # initial restart backoff
_WEBHOOK_MAX_DELAY_S = 60.0  # cap on restart backoff
_WEBHOOK_GH_API_TIMEOUT_S = 15.0
_GH_WEBHOOK_FORWARDER_HOOK_URL = "https://webhook-forwarder.github.com/hook"

# Default events the forwarder subscribes to.
#
# Core SCM events (always required):
#   ``push``           — source-sync after operators commit to a tracked branch.
#   ``pull_request``   — auto-merge label updates and PR-closed handling.
#
# GitHub Issues / GitHub-backed task events (required for task tracking):
#   ``issues``             — task open/edit/close in the task hub.
#   ``issue_comment``      — new comments on tasks (agent handoff, ACs).
#   ``label``              — label create/edit/delete (agent routing hints).
#
# ``projects_v2_item`` is intentionally omitted from this repo-scoped default:
# GitHub rejects it for repository webhooks created by ``gh webhook forward``.
# Oompah can still parse it when delivered through a separately configured
# organization/user-level webhook.
#
# Without ``--events``, the gh-webhook extension subscribes to nothing and
# the subprocess produces no traffic.
_WEBHOOK_DEFAULT_EVENTS = "push,pull_request,issues,issue_comment,label"

# Stderr tail size kept in memory per project (for surfacing the most
# recent error to the dashboard / logs without unbounded growth).
_WEBHOOK_STDERR_TAIL_BYTES = 4096


def _default_webhook_forward_url(server_port: int | str | None = None) -> str:
    """Return the local GitHub webhook receiver URL for the active server port."""
    raw_port = server_port
    if raw_port is None:
        raw_port = os.environ.get("OOMPAH_SERVER_PORT")
    try:
        port = int(str(raw_port).strip()) if raw_port is not None else None
    except (TypeError, ValueError):
        port = None
    if port is None:
        port = _WEBHOOK_FORWARD_DEFAULT_PORT
    return f"http://localhost:{port}/api/v1/webhooks/github"


def _short_process_error(stdout: str, stderr: str) -> str:
    """Return the first useful subprocess error line for logs."""
    for text in (stderr, stdout):
        for line in text.splitlines():
            line = line.strip()
            if line:
                return line
    return "no output"


async def check_gh_webhook_available() -> tuple[bool, str]:
    """Probe whether the ``gh webhook`` extension is installed.

    Runs ``gh webhook --help`` once and inspects the exit code. The
    ``cli/gh-webhook`` extension is a third-party gh extension; on a
    machine that does not have it installed, ``gh`` exits non-zero and
    prints ``unknown command "webhook"`` to stderr.

    Returns:
        A tuple of ``(available, detail)``. ``available`` is ``True`` if
        the extension responded successfully. ``detail`` is a short
        human-readable string explaining the failure (or ``""`` on
        success) — suitable for logging and dashboard alerts.
    """
    if shutil.which("gh") is None:
        return False, "'gh' CLI not found on PATH"

    try:
        proc = await asyncio.create_subprocess_exec(
            "gh", "webhook", "--help",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10.0)
    except asyncio.TimeoutError:
        return False, "'gh webhook --help' timed out"
    except FileNotFoundError:
        return False, "'gh' CLI not found on PATH"
    except Exception as exc:  # pragma: no cover — defensive
        return False, f"failed to probe gh webhook: {exc}"

    if proc.returncode == 0:
        return True, ""

    msg = (stderr or b"").decode("utf-8", errors="replace").strip().splitlines()
    detail = msg[0] if msg else f"gh webhook exited with code {proc.returncode}"
    return False, detail


class _ForwarderProcess:
    """Holds state for one project's webhook forward subprocess."""

    __slots__ = (
        "project_id",
        "project_name",
        "repo_path",
        "repo_slug",
        "access_token",
        "forwarding_enabled",
        "process",
        "restart_delay_s",
        "restart_attempts",
        "stderr_task",
        "last_stderr",
        "last_error",
        "last_error_at",
        "disabled",
        "disabled_reason",
    )

    def __init__(
        self,
        project_id: str,
        project_name: str,
        repo_path: str,
        repo_slug: str = "",
        access_token: str | None = None,
        forwarding_enabled: bool = True,
    ):
        self.project_id = project_id
        self.project_name = project_name
        self.repo_path = repo_path
        self.repo_slug = repo_slug
        self.access_token = access_token
        self.forwarding_enabled = forwarding_enabled
        self.process: asyncio.subprocess.Process | None = None
        self.restart_delay_s: float = _WEBHOOK_BASE_DELAY_S
        self.restart_attempts: int = 0
        # Background task that drains the subprocess's stderr into
        # ``last_stderr``. Reset on every (re)launch.
        self.stderr_task: asyncio.Task | None = None
        # Tail of the most recent stderr output (truncated to
        # _WEBHOOK_STDERR_TAIL_BYTES). Useful for surfacing auth or
        # extension-install errors when the process crashes.
        self.last_stderr: str = ""
        self.last_error: str = ""
        self.last_error_at: str = ""
        self.disabled: bool = False
        self.disabled_reason: str = ""


def _is_fatal_forwarder_error(detail: str) -> bool:
    """Return true when retrying the same gh-webhook invocation is pointless."""
    text = (detail or "").lower()
    if not text:
        return False
    if "http 404" in text or "not found" in text:
        return True
    if "http 403" in text or "permission denied" in text:
        return True
    if "could not resolve to a repository" in text:
        return True
    if "repository not found" in text:
        return True
    return False


def _truncate_error_detail(detail: str, limit: int = 500) -> str:
    """Keep alert/log details readable without storing large stderr tails."""
    text = " ".join((detail or "").strip().split())
    if len(text) <= limit:
        return text
    return text[: max(limit - 1, 0)].rstrip(" ,.;:-") + "..."


def build_webhook_forwarder_alerts(status: dict[str, Any]) -> list[dict[str, str]]:
    """Build dashboard alerts from a :class:`WebhookForwarder` status snapshot."""
    alerts: list[dict[str, str]] = []
    if not status.get("available"):
        detail = str(status.get("detail") or "gh-webhook extension unavailable")
        alerts.append({
            "level": "warning",
            "source": "webhook_forwarder",
            "message": (
                f"Webhooks degraded: {detail}. "
                "Install with `make install-gh-extensions`. "
                "Polling backup is active, but updates may be delayed."
            ),
        })

    projects = status.get("projects") or {}
    if isinstance(projects, dict):
        for project_id, project_status in projects.items():
            if not isinstance(project_status, dict):
                continue
            if project_status.get("forwarding_enabled") is False:
                continue
            error = str(project_status.get("last_error") or "").strip()
            if not error:
                continue
            name = str(project_status.get("name") or project_id)
            disabled = bool(project_status.get("disabled"))
            action = (
                "The forwarder stopped retrying for this project until the "
                "repo URL, repo path, or token changes."
                if disabled
                else "The forwarder will keep retrying with backoff."
            )
            alerts.append({
                "level": "error" if disabled else "warning",
                "source": f"webhook_forwarder:{project_id}",
                "message": (
                    f"Webhook forwarding failed for {name}: {error}. "
                    f"{action} Polling backup is active."
                ),
            })
    return alerts


class WebhookForwarder:
    """Manages 'gh webhook forward' subprocesses for each project.

    Launches and supervises a ``gh webhook forward --url <url>`` process
    per registered project. Each process runs in the project's repo_path
    directory. The forwarder monitors process health via polling, restarts
    on failure with exponential backoff, and cleans up all subprocesses on
    shutdown.

    The forwarder is a singleton — instantiate once and call :meth:`start`
    to begin the polling loop, and :meth:`stop` to shut down all processes.

    Args:
        project_store: A ``ProjectStore`` used to discover projects and
                       their ``repo_path`` values.
        webhook_url: The URL to pass to ``gh webhook forward --url``. When
                     ``None``, defaults to the ``OOMPAH_WEBHOOK_FORWARD_URL``
                     environment variable or the local receiver URL derived
                     from ``server_port``/``OOMPAH_SERVER_PORT``.
        server_port: Local oompah server port used to derive the default
                     webhook receiver URL when ``webhook_url`` and
                     ``OOMPAH_WEBHOOK_FORWARD_URL`` are unset.
        poll_interval_s: How often (in seconds) to poll process health.
                         Defaults to 5 seconds.
        events: Comma-separated list of forge event names to forward
                (passed verbatim to ``gh webhook forward --events``).
                Defaults to ``_WEBHOOK_DEFAULT_EVENTS`` — SCM events
                (``push``, ``pull_request``) plus GitHub-backed task
                tracking events (``issues``, ``issue_comment``, ``label``,
                all supported by repo-scoped GitHub webhooks). Override via
                the ``OOMPAH_WEBHOOK_EVENTS`` environment variable.
        status_callback: Optional callable invoked when the forwarder's
                         availability state changes. Called with a dict:
                         ``{"available": bool, "detail": str}`` so an
                         outer system (orchestrator, dashboard) can
                         surface a degraded-mode banner. The callback
                         runs synchronously; keep it cheap.
    """

    def __init__(
        self,
        project_store: Any = None,
        webhook_url: str | None = None,
        server_port: int | str | None = None,
        poll_interval_s: float = _WEBHOOK_POLL_INTERVAL_S,
        events: str | None = None,
        status_callback: Any = None,
    ):
        self.project_store = project_store
        self._webhook_url = (
            webhook_url
            or os.environ.get("OOMPAH_WEBHOOK_FORWARD_URL")
            or _default_webhook_forward_url(server_port)
        )
        self._events = (
            events
            or os.environ.get("OOMPAH_WEBHOOK_EVENTS")
            or _WEBHOOK_DEFAULT_EVENTS
        )
        self._poll_interval_s = poll_interval_s
        self._processes: dict[str, _ForwarderProcess] = {}  # project_id -> state
        self._stopping = False
        self._task: asyncio.Task | None = None
        self._started = False
        # Set after the first ``check_gh_webhook_available()`` probe.
        # ``None`` means "not yet probed". Once probed, downstream code
        # uses this to skip launching forwarders rather than spamming
        # the log on every restart-backoff cycle.
        self._extension_available: bool | None = None
        self._extension_detail: str = ""
        self._status_callback = status_callback

    @property
    def is_running(self) -> bool:
        """True if the forwarder polling loop is active."""
        return self._started and not self._stopping

    @property
    def extension_available(self) -> bool | None:
        """Whether the ``gh webhook`` extension was found at startup.

        ``None`` until :meth:`start` has run the probe. ``False`` means
        the extension is missing or broken — no subprocesses will be
        launched. ``True`` means forwarders are running normally.
        """
        return self._extension_available

    @property
    def status(self) -> dict[str, Any]:
        """Snapshot of the forwarder's health for the dashboard.

        Includes whether the extension is available, the most recent
        probe detail (e.g. ``"unknown command \"webhook\""``), and a
        per-project view of the latest stderr tail when a subprocess has
        been crashing.
        """
        per_project: dict[str, dict[str, Any]] = {}
        for pid, fp in self._processes.items():
            per_project[pid] = {
                "name": fp.project_name,
                "running": fp.process is not None and fp.process.returncode is None,
                "restart_attempts": fp.restart_attempts,
                "last_stderr": fp.last_stderr,
                "last_error": fp.last_error,
                "last_error_at": fp.last_error_at,
                "forwarding_enabled": fp.forwarding_enabled,
                "disabled": fp.disabled,
                "disabled_reason": fp.disabled_reason,
            }
        return {
            "running": self.is_running,
            "available": bool(self._extension_available),
            "detail": self._extension_detail,
            "extension_available": self._extension_available,
            "extension_detail": self._extension_detail,
            "events": self._events,
            "webhook_url": self._webhook_url,
            "projects": per_project,
        }

    async def start(self) -> None:
        """Start the forwarder polling loop.

        Idempotent — subsequent calls while already running are no-ops.

        Performs a one-shot ``gh webhook --help`` probe before starting
        the polling loop. If the ``cli/gh-webhook`` extension is missing,
        a single ERROR log line is emitted, the polling loop runs but
        never spawns subprocesses, and :meth:`extension_available`
        becomes ``False`` so the dashboard can show a degraded-mode
        banner.
        """
        if self._started:
            return

        available, detail = await check_gh_webhook_available()
        self._extension_available = available
        self._extension_detail = detail
        if available:
            logger.info(
                "WebhookForwarder: gh-webhook extension OK; forwarding events=%s",
                self._events,
            )
        else:
            logger.error(
                "WebhookForwarder: gh-webhook extension unavailable (%s). "
                "Install with `gh extension install cli/gh-webhook` "
                "(or run `make install-gh-extensions`). "
                "No forge webhook events will be forwarded; "
                "oompah will fall back to the periodic full-sync safety net.",
                detail or "unknown reason",
            )
        self._notify_status()

        self._started = True
        self._stopping = False
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            "WebhookForwarder started (url=%s, poll_interval=%.1fs)",
            self._webhook_url,
            self._poll_interval_s,
        )

    def _notify_status(self) -> None:
        """Invoke the status callback (if any), swallowing exceptions."""
        if self._status_callback is None:
            return
        try:
            self._status_callback(self.status)
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning("WebhookForwarder status_callback raised: %s", exc)

    def _record_project_error(
        self,
        fp: _ForwarderProcess,
        detail: str,
        *,
        fatal: bool | None = None,
        warn_only: bool = False,
    ) -> None:
        """Record and surface the latest per-project forwarder error.

        Args:
            fp: The forwarder process state to update.
            detail: Human-readable error detail string.
            fatal: When True, disable the project and log the error. When None,
                inferred from *detail* via :func:`_is_fatal_forwarder_error`.
            warn_only: When True (and *fatal* resolves to True), log at WARNING
                instead of ERROR.  Use this for configuration errors that are
                expected when the local environment doesn't have the required
                directory (e.g. ``repo_path`` not present on this host) — they
                disable forwarding, but they shouldn't trigger ``error_watcher``.
        """
        clean_detail = _truncate_error_detail(detail) or "unknown error"
        if fatal is None:
            fatal = _is_fatal_forwarder_error(clean_detail)
        fp.last_error = clean_detail
        fp.last_error_at = datetime.now(timezone.utc).isoformat()
        if fatal:
            fp.disabled = True
            fp.disabled_reason = clean_detail
            if warn_only:
                logger.warning(
                    "WebhookForwarder: disabling webhook forwarding for project %s: %s",
                    fp.project_name,
                    clean_detail,
                )
            else:
                logger.error(
                    "WebhookForwarder: disabling webhook forwarding for project %s: %s",
                    fp.project_name,
                    clean_detail,
                )
        self._notify_status()

    def _clear_project_error(self, fp: _ForwarderProcess) -> None:
        """Clear a prior project error once the configuration changes or runs."""
        if not (fp.last_error or fp.disabled or fp.disabled_reason):
            return
        fp.last_error = ""
        fp.last_error_at = ""
        fp.disabled = False
        fp.disabled_reason = ""
        self._notify_status()

    async def stop(self) -> None:
        """Stop the forwarder and terminate all subprocesses.

        Waits for the polling loop to finish, then kills all running
        ``gh webhook forward`` processes. Idempotent.
        """
        if self._stopping:
            return
        self._stopping = True

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None

        await self._kill_all()
        self._started = False
        logger.info("WebhookForwarder stopped")

    async def _run_loop(self) -> None:
        """Main polling loop that monitors and restarts processes."""
        while not self._stopping:
            try:
                await self._poll_and_restart()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("WebhookForwarder poll error: %s", exc)

            await asyncio.sleep(self._poll_interval_s)

    async def _poll_and_restart(self) -> None:
        """Check each project's process and restart any that have exited."""
        projects = (self.project_store.list_all() if self.project_store else [])
        live_ids = {p.id for p in projects}

        # Ensure a _ForwarderProcess exists for every project.
        for project in projects:
            repo_slug = extract_repo_slug(project.repo_url)
            access_token = getattr(project, "access_token", None)
            forwarding_enabled = bool(
                getattr(project, "webhook_forwarding_enabled", True)
            )
            if project.id not in self._processes:
                self._processes[project.id] = _ForwarderProcess(
                    project_id=project.id,
                    project_name=project.name,
                    repo_path=project.repo_path,
                    repo_slug=repo_slug,
                    access_token=access_token,
                    forwarding_enabled=forwarding_enabled,
                )
            else:
                fp = self._processes[project.id]
                old_config = (
                    fp.repo_path,
                    fp.repo_slug,
                    fp.access_token,
                    fp.forwarding_enabled,
                )
                new_config = (
                    project.repo_path,
                    repo_slug,
                    access_token,
                    forwarding_enabled,
                )
                fp.project_name = project.name
                fp.repo_path = project.repo_path
                fp.repo_slug = repo_slug
                fp.access_token = access_token
                fp.forwarding_enabled = forwarding_enabled
                if old_config != new_config:
                    self._clear_project_error(fp)

        # Remove stale entries for deleted projects.
        stale = set(self._processes) - live_ids
        for pid in stale:
            await self._terminate(pid)
            del self._processes[pid]

        # Poll each active project.
        for project in projects:
            fp = self._processes[project.id]
            if not fp.forwarding_enabled:
                await self._terminate(fp.project_id)
                self._clear_project_error(fp)
                continue
            await self._check_and_restart(fp)

    async def _check_and_restart(self, fp: _ForwarderProcess) -> None:
        """Check one project's process and restart it if dead."""
        if fp.disabled:
            return

        proc = fp.process

        if proc is not None:
            # Poll the process to see if it has exited.
            try:
                rc = proc.poll()
            except Exception:
                rc = None

            if rc is None:
                # Still running.
                fp.restart_delay_s = _WEBHOOK_BASE_DELAY_S
                self._clear_project_error(fp)
                return

            # Process has exited.
            exited_code = rc
            logger.info(
                "WebhookForwarder: gh webhook forward exited for project %s (code=%d), restarting in %.1fs",
                fp.project_name,
                exited_code,
                fp.restart_delay_s,
            )
            await self._terminate(fp.project_id)

            # Wait for backoff before restarting.
            await asyncio.sleep(fp.restart_delay_s)
            if self._stopping:
                return

            # Exponential backoff with cap.
            fp.restart_delay_s = min(fp.restart_delay_s * 2, _WEBHOOK_MAX_DELAY_S)
            fp.restart_attempts += 1

        else:
            fp.restart_attempts += 1

        # Launch a new process.
        await self._launch(fp)

    async def _launch(self, fp: _ForwarderProcess) -> None:
        """Launch a 'gh webhook forward' subprocess for one project.

        Skips silently (no subprocess, no log spam) when the
        ``gh webhook`` extension was found unavailable at startup —
        the single ERROR was already logged in :meth:`start`. The
        invocation always passes ``--events`` so the upstream extension
        actually subscribes to events; without it, the subprocess
        connects but no traffic is delivered.
        """
        # Don't pollute logs on every poll cycle when the extension is
        # known-missing. The single startup ERROR already told the
        # operator; the dashboard banner keeps the state visible.
        if self._extension_available is False:
            return
        if fp.disabled:
            return

        repo_path = fp.repo_path
        if not repo_path or not os.path.isdir(repo_path):
            logger.debug(
                "WebhookForwarder: skipping project %s (no repo_path or dir not found)",
                fp.project_name,
            )
            self._record_project_error(
                fp,
                "configured repo_path is missing or not a directory",
                fatal=True,
                warn_only=True,
            )
            return

        if not os.path.isdir(os.path.join(repo_path, ".git")):
            logger.debug(
                "WebhookForwarder: skipping project %s (not a git repo)",
                fp.project_name,
            )
            self._record_project_error(
                fp,
                "configured repo_path is not a Git worktree",
                fatal=True,
            )
            return

        if not fp.repo_slug:
            logger.warning(
                "WebhookForwarder: skipping project %s (could not determine repo slug)",
                fp.project_name,
            )
            self._record_project_error(
                fp,
                "could not determine GitHub repo slug from project repo_url",
                fatal=True,
            )
            return

        env = os.environ.copy()
        if fp.access_token:
            env["GH_TOKEN"] = fp.access_token

        if fp.restart_attempts > 0:
            await self._cleanup_existing_forwarder_hooks(fp, env)
            if fp.disabled:
                return

        try:
            proc = await asyncio.create_subprocess_exec(
                "gh",
                "webhook",
                "forward",
                "--repo",
                fp.repo_slug,
                "--events",
                self._events,
                "--url",
                self._webhook_url,
                cwd=repo_path,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            fp.process = proc
            self._clear_project_error(fp)
            # Reset stderr buffer for the new invocation and start the
            # background drainer. Capturing stderr is critical for
            # surfacing install/auth issues — without it, a process
            # that exits immediately leaves no diagnostic trail.
            fp.last_stderr = ""
            fp.stderr_task = asyncio.create_task(self._drain_stderr(fp))
            logger.info(
                "WebhookForwarder: started gh webhook forward for project %s "
                "(pid=%d, events=%s)",
                fp.project_name,
                proc.pid,
                self._events,
            )
        except FileNotFoundError:
            logger.warning(
                "WebhookForwarder: 'gh' CLI not found — skipping project %s",
                fp.project_name,
            )
            self._record_project_error(fp, "'gh' CLI not found on PATH", fatal=True)
            fp.process = None
        except Exception as exc:
            logger.warning(
                "WebhookForwarder: failed to start gh webhook forward for project %s: %s",
                fp.project_name,
                exc,
            )
            self._record_project_error(fp, str(exc), fatal=None)
            fp.process = None

    async def _cleanup_existing_forwarder_hooks(
        self,
        fp: _ForwarderProcess,
        env: dict[str, str],
    ) -> None:
        """Remove stale gh-webhook relay hooks before launching.

        The ``cli/gh-webhook`` extension creates a repository hook named
        ``cli`` that points at GitHub's webhook-forwarder relay. If the
        local process exits abruptly, that remote hook can remain in place;
        the next launch then fails with ``Hook already exists``. Removing
        matching hooks here makes the forwarder restartable without manual
        GitHub cleanup.
        """
        if not fp.repo_slug:
            return

        rc, stdout, stderr = await self._run_gh_api(
            fp,
            env,
            f"repos/{fp.repo_slug}/hooks",
            "--jq",
            (
                ".[] | select(.name == \"cli\" "
                f"and .config.url == \"{_GH_WEBHOOK_FORWARDER_HOOK_URL}\") | .id"
            ),
        )
        if rc != 0:
            detail = _short_process_error(stdout, stderr)
            logger.warning(
                "WebhookForwarder: could not inspect existing gh-webhook hooks "
                "for project %s: %s",
                fp.project_name,
                detail,
            )
            self._record_project_error(
                fp,
                detail,
                fatal=_is_fatal_forwarder_error(detail),
            )
            return

        hook_ids = [line.strip() for line in stdout.splitlines() if line.strip()]
        for hook_id in hook_ids:
            rc, delete_stdout, delete_stderr = await self._run_gh_api(
                fp,
                env,
                "-X",
                "DELETE",
                f"repos/{fp.repo_slug}/hooks/{hook_id}",
            )
            if rc == 0:
                logger.info(
                    "WebhookForwarder: removed stale gh-webhook hook %s for project %s",
                    hook_id,
                    fp.project_name,
                )
            else:
                detail = _short_process_error(delete_stdout, delete_stderr)
                logger.warning(
                    "WebhookForwarder: failed to remove stale gh-webhook hook %s "
                    "for project %s: %s",
                    hook_id,
                    fp.project_name,
                    detail,
                )
                self._record_project_error(
                    fp,
                    detail,
                    fatal=_is_fatal_forwarder_error(detail),
                )

    async def _run_gh_api(
        self,
        fp: _ForwarderProcess,
        env: dict[str, str],
        *args: str,
    ) -> tuple[int, str, str]:
        """Run ``gh api`` with captured output for forwarder maintenance."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "gh",
                "api",
                *args,
                cwd=fp.repo_path,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=_WEBHOOK_GH_API_TIMEOUT_S,
            )
        except asyncio.TimeoutError:
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass
            return 124, "", "gh api timed out"
        except FileNotFoundError:
            return 127, "", "'gh' CLI not found on PATH"
        except Exception as exc:  # pragma: no cover - defensive
            return 1, "", str(exc)

        return (
            proc.returncode or 0,
            stdout.decode("utf-8", errors="replace"),
            stderr.decode("utf-8", errors="replace"),
        )

    async def _drain_stderr(self, fp: _ForwarderProcess) -> None:
        """Read the subprocess's stderr into ``fp.last_stderr``.

        Keeps only the most recent ``_WEBHOOK_STDERR_TAIL_BYTES`` bytes
        so a long-running noisy forwarder doesn't grow unbounded. When
        the process exits with a non-zero return code, the captured tail
        is logged at WARNING so install/auth problems surface in
        ``oompah.log``.
        """
        proc = fp.process
        if proc is None:
            return
        stderr = getattr(proc, "stderr", None)
        if stderr is None:
            return
        buf = b""
        try:
            while True:
                chunk = await stderr.read(1024)
                if not chunk:
                    break
                buf = (buf + chunk)[-_WEBHOOK_STDERR_TAIL_BYTES:]
                fp.last_stderr = buf.decode("utf-8", errors="replace")
        except asyncio.CancelledError:
            raise
        except Exception:  # pragma: no cover — defensive
            pass
        # If stderr reached EOF, the process is normally done. Wait briefly
        # so ``returncode`` is populated, then detach this completed process
        # so the polling loop can launch a replacement on its next pass.
        rc = proc.returncode
        if rc is None:
            try:
                rc = await asyncio.wait_for(proc.wait(), timeout=1.0)
            except (asyncio.TimeoutError, TypeError):
                rc = proc.returncode
        if rc is not None and fp.process is proc:
            fp.process = None

        # If the process exited badly, log the captured tail so the
        # operator can see auth/install errors in oompah.log.
        if rc not in (None, 0) and fp.last_stderr:
            detail = _short_process_error("", fp.last_stderr)
            logger.warning(
                "WebhookForwarder: gh webhook forward stderr for project %s "
                "(exit=%d): %s",
                fp.project_name,
                rc,
                fp.last_stderr.strip(),
            )
            self._record_project_error(
                fp,
                detail,
                fatal=_is_fatal_forwarder_error(fp.last_stderr),
            )

    async def _terminate(self, project_id: str) -> None:
        """Terminate the subprocess for one project, if running."""
        fp = self._processes.get(project_id)
        if not fp:
            return
        proc = fp.process
        if proc is None:
            # No subprocess, but a stderr drainer task may still be
            # outstanding from a prior run — clean it up.
            await self._cancel_stderr_task(fp)
            return

        fp.process = None
        if proc.returncode is not None:
            await self._cancel_stderr_task(fp)
            return  # already exited

        try:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
        except (ProcessLookupError, ValueError, OSError):
            pass

        await self._cancel_stderr_task(fp)
        logger.info(
            "WebhookForwarder: terminated gh webhook forward for project %s",
            fp.project_name,
        )

    @staticmethod
    async def _cancel_stderr_task(fp: _ForwarderProcess) -> None:
        """Cancel the background stderr drainer (if any) and await it."""
        task = fp.stderr_task
        if task is None:
            return
        fp.stderr_task = None
        if task.done():
            return
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass

    async def _kill_all(self) -> None:
        """Terminate all running subprocesses."""
        for pid in list(self._processes.keys()):
            await self._terminate(pid)
        self._processes.clear()
