"""Forge webhook receiver for GitHub and GitLab, and gh webhook forwarder.

Parses webhook payloads, validates HMAC signatures (GitHub) or secret
tokens (GitLab), and extracts PR/MR event information for the EventBus.

The WebhookForwarder class manages 'gh webhook forward' subprocesses for
each project, monitoring health and restarting on failure.

Usage::

    from oompah.webhooks import (
        validate_github_signature,
        validate_gitlab_token,
        parse_github_webhook,
        parse_gitlab_webhook,
        WebhookEvent,
        WebhookForwarder,
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


# ---------------------------------------------------------------------------
# Webhook Forwarder
# ---------------------------------------------------------------------------

import asyncio
import os


_WEBHOOK_FORWARD_URL_DEFAULT = "http://localhost:8080/api/v1/webhooks/github"
_WEBHOOK_POLL_INTERVAL_S = 5.0  # how often to check process health
_WEBHOOK_BASE_DELAY_S = 1.0  # initial restart backoff
_WEBHOOK_MAX_DELAY_S = 60.0  # cap on restart backoff


class _ForwarderProcess:
    """Holds state for one project's webhook forward subprocess."""

    __slots__ = ("project_id", "project_name", "repo_path", "process", "restart_delay_s", "restart_attempts")

    def __init__(self, project_id: str, project_name: str, repo_path: str):
        self.project_id = project_id
        self.project_name = project_name
        self.repo_path = repo_path
        self.process: asyncio.subprocess.Process | None = None
        self.restart_delay_s: float = _WEBHOOK_BASE_DELAY_S
        self.restart_attempts: int = 0


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
                     environment variable or ``http://localhost:8080/api/v1/webhooks/github``.
        poll_interval_s: How often (in seconds) to poll process health.
                         Defaults to 5 seconds.
    """

    def __init__(
        self,
        project_store: Any = None,
        webhook_url: str | None = None,
        poll_interval_s: float = _WEBHOOK_POLL_INTERVAL_S,
    ):
        self.project_store = project_store
        self._webhook_url = (
            webhook_url
            or os.environ.get("OOMPAH_WEBHOOK_FORWARD_URL")
            or _WEBHOOK_FORWARD_URL_DEFAULT
        )
        self._poll_interval_s = poll_interval_s
        self._processes: dict[str, _ForwarderProcess] = {}  # project_id -> state
        self._stopping = False
        self._task: asyncio.Task | None = None
        self._started = False

    @property
    def is_running(self) -> bool:
        """True if the forwarder polling loop is active."""
        return self._started and not self._stopping

    async def start(self) -> None:
        """Start the forwarder polling loop.

        Idempotent — subsequent calls while already running are no-ops.
        """
        if self._started:
            return
        self._started = True
        self._stopping = False
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            "WebhookForwarder started (url=%s, poll_interval=%.1fs)",
            self._webhook_url,
            self._poll_interval_s,
        )

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
            if project.id not in self._processes:
                self._processes[project.id] = _ForwarderProcess(
                    project_id=project.id,
                    project_name=project.name,
                    repo_path=project.repo_path,
                )

        # Remove stale entries for deleted projects.
        stale = set(self._processes) - live_ids
        for pid in stale:
            await self._terminate(pid)
            del self._processes[pid]

        # Poll each active project.
        for project in projects:
            fp = self._processes[project.id]
            await self._check_and_restart(fp)

    async def _check_and_restart(self, fp: _ForwarderProcess) -> None:
        """Check one project's process and restart it if dead."""
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
        """Launch a 'gh webhook forward' subprocess for one project."""
        repo_path = fp.repo_path
        if not repo_path or not os.path.isdir(repo_path):
            logger.debug(
                "WebhookForwarder: skipping project %s (no repo_path or dir not found)",
                fp.project_name,
            )
            return

        if not os.path.isdir(os.path.join(repo_path, ".git")):
            logger.debug(
                "WebhookForwarder: skipping project %s (not a git repo)",
                fp.project_name,
            )
            return

        try:
            proc = await asyncio.create_subprocess_exec(
                "gh",
                "webhook",
                "forward",
                "--url",
                self._webhook_url,
                cwd=repo_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            fp.process = proc
            logger.info(
                "WebhookForwarder: started gh webhook forward for project %s (pid=%d)",
                fp.project_name,
                proc.pid,
            )
        except FileNotFoundError:
            logger.warning(
                "WebhookForwarder: 'gh' CLI not found — skipping project %s",
                fp.project_name,
            )
            fp.process = None
        except Exception as exc:
            logger.warning(
                "WebhookForwarder: failed to start gh webhook forward for project %s: %s",
                fp.project_name,
                exc,
            )
            fp.process = None

    async def _terminate(self, project_id: str) -> None:
        """Terminate the subprocess for one project, if running."""
        fp = self._processes.get(project_id)
        if not fp:
            return
        proc = fp.process
        if proc is None:
            return

        fp.process = None
        if proc.returncode is not None:
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

        logger.info(
            "WebhookForwarder: terminated gh webhook forward for project %s",
            fp.project_name,
        )

    async def _kill_all(self) -> None:
        """Terminate all running subprocesses."""
        for pid in list(self._processes.keys()):
            await self._terminate(pid)
        self._processes.clear()
