"""Backlog.md task-change webhook installation for managed projects.

Installs a ``post-commit`` git hook into each managed project's cloned
repository so that oompah is notified via HTTP POST whenever a commit
touches backlog task files (``backlog/tasks/*.md`` or
``backlog/completed/*.md``).

The hook is installed idempotently: re-running installation on a repo
that already has the hook with the same configuration is a no-op (the
hook file and git config values are only written when they differ from
what is on disk).

On receipt, the webhook handler in ``oompah/server.py`` invalidates
issue caches, triggers a ``git pull`` sync of the project, and requests
an orchestrator UI refresh — so changes made by agents or direct commits
appear in the dashboard without waiting for the next full-sync cycle.

Usage::

    from oompah.backlog_webhooks import (
        validate_backlog_webhook_signature,
        install_backlog_webhook_hook,
        ensure_backlog_webhooks,
    )

    # Validate an incoming webhook:
    valid = validate_backlog_webhook_signature(body_bytes, sig_header, secret)

    # Install the hook for one project:
    ok = install_backlog_webhook_hook(repo_path, webhook_url, project_id, secret)

    # Install hooks for all managed projects (called at startup):
    results = ensure_backlog_webhooks(project_store, server_base_url="http://localhost:8080")
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import subprocess
from typing import Any

from oompah.git_hooks import hook_path as _bundled_hook_path

logger = logging.getLogger(__name__)

# Git config keys written into each managed repo.
_GIT_CONFIG_URL_KEY = "oompah.backlog-webhook-url"
_GIT_CONFIG_SECRET_KEY = "oompah.backlog-webhook-secret"
_GIT_CONFIG_PROJECT_ID_KEY = "oompah.project-id"

# Default oompah server base URL if none is configured.
_DEFAULT_SERVER_BASE_URL = "http://localhost:8080"
_BACKLOG_WEBHOOK_PATH = "/api/v1/webhooks/backlog"

# Sentinel string embedded in the installed hook script to identify it
# as oompah-managed (enables idempotency checks).
_OOMPAH_HOOK_MARKER = "# oompah-backlog-webhook-hook"

# Git hook name installed into managed repos.
_HOOK_NAME = "post-commit"


# ---------------------------------------------------------------------------
# Signature validation (server side)
# ---------------------------------------------------------------------------


def validate_backlog_webhook_signature(
    payload_body: bytes,
    signature_header: str,
    secret: str,
) -> bool:
    """Validate an oompah Backlog webhook HMAC-SHA256 signature.

    The hook script signs the POST body with the project's shared secret
    and sends the signature in the ``X-Oompah-Signature`` header as
    ``sha256=<hex_digest>``.

    Args:
        payload_body: Raw request body bytes.
        signature_header: Value of the ``X-Oompah-Signature`` header.
        secret: The shared webhook secret string.

    Returns:
        ``True`` if the signature is valid, ``False`` otherwise.
    """
    if not signature_header or not secret:
        return False
    prefix = "sha256="
    if not signature_header.startswith(prefix):
        return False
    expected = signature_header[len(prefix):]
    mac = hmac.new(secret.encode("utf-8"), msg=payload_body, digestmod=hashlib.sha256)
    return hmac.compare_digest(mac.hexdigest(), expected)


# ---------------------------------------------------------------------------
# Hook installation (idempotent)
# ---------------------------------------------------------------------------


def _git_config_get(repo_path: str, key: str) -> str:
    """Read a git local config value from repo_path."""
    try:
        result = subprocess.run(
            ["git", "config", "--local", key],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def _git_config_set(repo_path: str, key: str, value: str) -> bool:
    """Write a git local config value in repo_path. Returns True on success."""
    try:
        result = subprocess.run(
            ["git", "config", "--local", key, value],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def install_backlog_webhook_hook(
    repo_path: str,
    webhook_url: str,
    project_id: str,
    secret: str,
) -> bool:
    """Install or update the post-commit hook in a managed repo.

    Idempotent: if the hook file is already present with an oompah marker
    AND the git config entries already match the supplied values, the
    function returns ``True`` without writing anything.

    The hook is symlinked (or copied, on platforms that do not support
    symlinks) to the bundled ``oompah/git_hooks/post-commit`` script, then
    the three git config keys are set so the script knows where to POST.

    Args:
        repo_path: Absolute path to the cloned project repo.
        webhook_url: Full URL of the oompah backlog webhook endpoint.
        project_id: The oompah project identifier.
        secret: HMAC-SHA256 shared secret for signing payloads. May be
                empty string if no authentication is required.

    Returns:
        ``True`` if the hook is configured (after installation), ``False``
        if installation failed for any reason.
    """
    if not repo_path or not os.path.isdir(os.path.join(repo_path, ".git")):
        logger.debug(
            "install_backlog_webhook_hook: skipping %s (not a git repo)",
            repo_path,
        )
        return False

    hook_src = _bundled_hook_path(_HOOK_NAME)
    if not os.path.isfile(hook_src):
        logger.warning(
            "install_backlog_webhook_hook: bundled %s not found at %s",
            _HOOK_NAME,
            hook_src,
        )
        return False

    hooks_dir = os.path.join(repo_path, ".git", "hooks")
    os.makedirs(hooks_dir, exist_ok=True)
    hook_dst = os.path.join(hooks_dir, _HOOK_NAME)

    # Determine whether the hook already points at our bundled script.
    hook_already_installed = _is_oompah_hook(hook_dst)

    if not hook_already_installed:
        # Install or replace the hook.
        _remove_path_if_exists(hook_dst)
        installed = _symlink_or_copy(hook_src, hook_dst)
        if not installed:
            return False
    else:
        # Hook file is present; make sure it is executable.
        _ensure_executable(hook_dst)

    # Write git config entries (idempotent — only writes when changed).
    config_ok = True
    config_entries = [
        (_GIT_CONFIG_URL_KEY, webhook_url),
        (_GIT_CONFIG_PROJECT_ID_KEY, project_id),
    ]
    # Only write the secret key when a secret is configured; leave it absent
    # (not empty-string) when there is no secret to avoid leaking placeholder
    # values into git config and to work around git not round-tripping empty
    # string values reliably.
    if secret:
        config_entries.append((_GIT_CONFIG_SECRET_KEY, secret))
    for key, value in config_entries:
        current = _git_config_get(repo_path, key)
        if current != value:
            if not _git_config_set(repo_path, key, value):
                logger.warning(
                    "install_backlog_webhook_hook: could not set %s for %s",
                    key,
                    repo_path,
                )
                config_ok = False

    if not hook_already_installed:
        logger.info(
            "Installed Backlog webhook hook for %s (url=%s)",
            repo_path,
            webhook_url,
        )
    else:
        logger.debug(
            "Backlog webhook hook already installed for %s; config updated",
            repo_path,
        )

    return config_ok


def _is_oompah_hook(hook_path: str) -> bool:
    """Return True if the file at hook_path is an oompah-managed hook."""
    if not os.path.exists(hook_path):
        return False
    try:
        # Read the actual file content (resolving symlinks).
        real = os.path.realpath(hook_path)
        with open(real, encoding="utf-8", errors="replace") as fh:
            content = fh.read(512)
        return _OOMPAH_HOOK_MARKER in content
    except OSError:
        return False


def _remove_path_if_exists(path: str) -> None:
    """Remove a file or symlink if it exists."""
    try:
        if os.path.islink(path) or os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def _symlink_or_copy(src: str, dst: str) -> bool:
    """Symlink src → dst; fall back to a file copy. Returns True on success."""
    try:
        os.symlink(src, dst)
        _ensure_executable(dst)
        return True
    except (OSError, NotImplementedError):
        pass
    # Symlink failed — copy instead.
    try:
        with open(src, "rb") as rf, open(dst, "wb") as wf:
            wf.write(rf.read())
        _ensure_executable(dst)
        return True
    except OSError as exc:
        logger.warning(
            "install_backlog_webhook_hook: failed to install hook at %s: %s",
            dst,
            exc,
        )
        return False


def _ensure_executable(path: str) -> None:
    """chmod +x the file at path (only for real files, not symlinks)."""
    if os.path.islink(path):
        return
    try:
        os.chmod(path, 0o755)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Bulk install (startup / project add-update)
# ---------------------------------------------------------------------------


def ensure_backlog_webhooks(
    project_store: Any,
    server_base_url: str | None = None,
) -> dict[str, str]:
    """Install or update the Backlog webhook hook for every managed project.

    Called at startup (after source sync) and whenever a project is
    added or updated so that new repos immediately get the hook.

    Args:
        project_store: A ``ProjectStore`` instance (or any object with a
                       ``list_all() -> list[Project]`` method).
        server_base_url: Base URL of the oompah server (e.g.
                         ``"http://localhost:8080"``). When ``None``,
                         reads ``OOMPAH_SERVER_URL`` from the environment,
                         then falls back to ``http://localhost:8080``.

    Returns:
        Mapping of ``project_id → "ok"|"skipped: <reason>"|"failed: <reason>"``.
        Never raises.
    """
    import os as _os

    base_url = (
        server_base_url
        or _os.environ.get("OOMPAH_SERVER_URL")
        or _DEFAULT_SERVER_BASE_URL
    ).rstrip("/")
    webhook_url = base_url + _BACKLOG_WEBHOOK_PATH

    projects = project_store.list_all() if project_store else []
    results: dict[str, str] = {}

    for project in projects:
        pid = project.id
        repo_path = getattr(project, "repo_path", None) or ""
        secret = getattr(project, "webhook_secret", None) or ""

        # External/native task trackers do not use Backlog post-commit hooks.
        tracker_kind = str(getattr(project, "tracker_kind", None) or "").strip().lower()
        if tracker_kind in {"github_issues", "github-issues", "oompah_md", "oompah.md", "oompah"}:
            logger.debug(
                "ensure_backlog_webhooks: skipping %s project %s",
                tracker_kind,
                pid,
            )
            results[pid] = f"skipped: {tracker_kind} tracker"
            continue

        if not repo_path or not os.path.isdir(os.path.join(repo_path, ".git")):
            results[pid] = "skipped: no .git directory"
            continue

        try:
            ok = install_backlog_webhook_hook(
                repo_path=repo_path,
                webhook_url=webhook_url,
                project_id=pid,
                secret=secret,
            )
            results[pid] = "ok" if ok else "failed: hook installation error"
        except Exception as exc:
            logger.warning(
                "ensure_backlog_webhooks: error for project %s: %s",
                pid,
                exc,
            )
            results[pid] = f"failed: {exc}"

    return results
