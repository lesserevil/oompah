"""Tracker-neutral task command-line wrapper for oompah agents.

Provides the ``oompah task`` subcommand surface so agents can manage tasks
through the active oompah tracker.

All operations call the local oompah server API.  If the server is unavailable
the commands exit with an actionable error message (acceptance criterion #2).

Usage::

    oompah task view <identifier> [--project <project-id>]
    oompah task comment <identifier> --message "..." [--author oompah]
    oompah task create --project <project-id> --title "..." [--source <source-id>]
    oompah task child-create <parent-id> --title "..." [--project <id>]
    oompah task set-status <identifier> <status> [--summary "..."]
        [--audit-override --override-reason "..."]
    oompah task add-label <identifier> <label>
    oompah task remove-label <identifier> <label>
    oompah task set-dependency <identifier> --depends-on <dep-id> [--hard-start]
    oompah task remove-dependency <identifier> --depends-on <dep-id> [--hard-start]
    oompah task submit <identifier> --summary "..."
    oompah task set-source <identifier> <source-id> [--project <id>]
    oompah task remove-source <identifier> [--project <id>]
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path
from typing import Any

try:
    import httpx as _httpx
except ImportError:  # pragma: no cover
    _httpx = None  # type: ignore[assignment]

from oompah.client_auth import (
    ClientCredentials,
    CredentialError,
    format_auth_error,
    load_client_environment,
    resolve_client_credentials,
    sanitize_server_url,
)
from oompah.git_credentials import git_credential_environment, redact_git_output
from oompah.task_handoff import (
    TASK_HANDOFF_HEADER,
    TASK_HANDOFF_PROJECT_ENV,
    TASK_HANDOFF_TASK_ENV,
    TASK_HANDOFF_TOKEN_ENV,
)

__all__ = ["main", "build_parser"]


_DEFAULT_HTTP_TIMEOUT_SECONDS = 600.0
_HTTP_TIMEOUT_ENV = "OOMPAH_TASK_CLI_TIMEOUT_SECONDS"

# Module-level auth slot: set by main() before dispatching to subcommands.
# None means unauthenticated (backward-compatible).  This is a CLI tool that
# runs in a single thread, so a module-level variable is safe.
_session_auth: ClientCredentials | None = None


def _task_handoff_token() -> str | None:
    """Return the spawned-worker capability, if this is a handoff session."""
    token = os.environ.get(TASK_HANDOFF_TOKEN_ENV, "").strip()
    return token or None


def _task_handoff_project(payload: dict[str, Any]) -> str | None:
    """Fill the non-secret project scope supplied to spawned subprocesses."""
    project_id = str(payload.get("project_id") or "").strip()
    if project_id:
        return project_id
    project_id = os.environ.get(TASK_HANDOFF_PROJECT_ENV, "").strip()
    return project_id or None


# ---------------------------------------------------------------------------
# Actor reconciliation (OOMPAH-624)
# ---------------------------------------------------------------------------


def _reconcile_actor_with_session(actor: str | None, *, flag: str = "--actor") -> str | None:
    """Return an actor value safe to send to the server.

    OOMPAH-624: when the CLI has resolved HTTP Basic credentials, the
    server binds the authorization actor to the authenticated principal.
    Passing an explicit ``--actor`` is:

    * **Redundant** when it matches the authenticated username — we drop
      it from the request body and print a stderr warning so the operator
      knows the flag is no longer required.
    * **Rejected** when it differs from the authenticated username — we
      short-circuit before the network call to avoid mutating state or
      surfacing an unhelpful 403 from the server.  The server would
      reject the mismatch anyway; failing early gives a clearer message.

    When no session auth is configured (backward-compatible
    unauthenticated deployments) the caller-supplied *actor* is returned
    unchanged.
    """

    if not actor:
        return actor
    session = _session_auth
    if session is None:
        return actor
    session_username = str(session.username or "").strip()
    if not session_username:
        return actor
    if actor.strip().lower() == session_username.lower():
        # Silent no-op when explicitly opted out via env var; some CI
        # scripts still pass --actor for legacy reasons.
        if not os.environ.get("OOMPAH_ACTOR_DEPRECATION_SILENCE"):
            print(
                f"warning: {flag} is redundant when HTTP Basic credentials "
                f"are configured; the server binds the actor to the "
                f"authenticated principal ({session_username}).",
                file=sys.stderr,
            )
        return None
    print(
        f"error: {flag}={actor!r} conflicts with the authenticated "
        f"principal {session_username!r}.  The server would reject this "
        "request with actor_mismatch (403).  Omit the flag to use the "
        "authenticated identity, or authenticate as the intended actor.",
        file=sys.stderr,
    )
    sys.exit(2)


# ---------------------------------------------------------------------------
# Server URL resolution
# ---------------------------------------------------------------------------


def _resolve_server_url(
    server_override: str | None,
    port_override: int | None,
) -> str:
    """Return the base URL for the local oompah server.

    Priority: explicit --server flag > --port flag > OOMPAH_SERVER_URL env
    variable > default ``http://127.0.0.1:8080``.

    The selected URL is passed through :func:`~oompah.client_auth.sanitize_server_url`
    to reject URLs that embed credentials in the userinfo component.
    """
    if server_override:
        raw = server_override
    elif port_override is not None:
        return f"http://127.0.0.1:{port_override}"
    else:
        raw = os.environ.get("OOMPAH_SERVER_URL", "").strip()
        if not raw:
            return "http://127.0.0.1:8080"

    try:
        return sanitize_server_url(raw)
    except CredentialError as exc:
        sys.exit(f"ERROR: {exc}")


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------


def _resolve_http_timeout() -> float:
    """Return the timeout for local oompah API calls."""
    raw = os.environ.get(_HTTP_TIMEOUT_ENV, "").strip()
    if not raw:
        return _DEFAULT_HTTP_TIMEOUT_SECONDS
    try:
        timeout = float(raw)
    except ValueError:
        return _DEFAULT_HTTP_TIMEOUT_SECONDS
    if not math.isfinite(timeout) or timeout <= 0:
        return _DEFAULT_HTTP_TIMEOUT_SECONDS
    return timeout


def _http(
    method: str,
    url: str,
    *,
    data: dict[str, Any] | None = None,
    params: dict[str, str] | None = None,
    auth: ClientCredentials | None = None,
    task_capability: str | None = None,
) -> dict[str, Any]:
    """Make an HTTP request to the oompah API and return the JSON body.

    Exits with an actionable error message when the server is unreachable
    (connection refused, DNS failure, timeout) or returns a non-2xx status.
    A 401 response produces a distinct remediation message that never echoes
    credential values or Authorization header content.

    Never raises — callers can rely on the return value being a valid dict.

    Args:
        method: HTTP method (GET, POST, PATCH, DELETE).
        url:    Full request URL.
        data:   JSON-serializable request body for POST/PATCH.
        params: URL query parameters.
        auth:   Optional :class:`~oompah.client_auth.ClientCredentials` to
                send as HTTP Basic auth.  When *None*, no Authorization
                header is sent (backward-compatible unauthenticated mode).
    """
    if _httpx is None:
        sys.exit(
            "ERROR: httpx is required for oompah task commands.\n"
            "Install it with: pip install httpx"
        )

    # Sanitize at the request boundary as well as when resolving the base URL.
    # This keeps internal callers from accidentally putting userinfo into a
    # request and ensures connection errors cannot echo a plaintext password.
    try:
        url = sanitize_server_url(url)
    except CredentialError as exc:
        sys.exit(f"ERROR: {exc}")

    # Derive base URL for error messages (strip everything after /api/).
    # Never include the auth object in error output.
    base_url = url.split("/api/")[0] if "/api/" in url else url

    # Use explicit auth if provided; fall back to the session-level auth set
    # by main().  Tests that patch _http directly bypass this entirely.
    # A spawned handoff capability is deliberately the only credential on
    # the request. Never combine it with an inherited operator Basic secret.
    effective_auth = None if task_capability else (
        auth if auth is not None else _session_auth
    )
    httpx_auth = (
        _httpx.BasicAuth(username=effective_auth.username, password=effective_auth.password)
        if effective_auth is not None
        else None
    )
    headers = {TASK_HANDOFF_HEADER: task_capability} if task_capability else None

    try:
        client_kwargs: dict[str, Any] = {
            "timeout": _resolve_http_timeout(),
            "auth": httpx_auth,
        }
        if headers is not None:
            client_kwargs["headers"] = headers
        with _httpx.Client(**client_kwargs) as client:
            if method == "GET":
                resp = client.get(url, params=params)
            elif method == "POST":
                resp = client.post(url, json=data, params=params)
            elif method == "PATCH":
                resp = client.patch(url, json=data, params=params)
            elif method == "DELETE":
                resp = client.delete(url, params=params)
            else:  # pragma: no cover
                raise ValueError(f"Unsupported HTTP method: {method}")
    except _httpx.ConnectError:
        sys.exit(
            f"ERROR: Cannot connect to oompah server at {base_url}.\n"
            "Is the server running?  Start it with: make start\n"
            "Override the server with --server, --port, or OOMPAH_SERVER_URL."
        )
    except _httpx.TimeoutException:
        sys.exit(
            f"ERROR: Request to oompah server timed out at {base_url}.\n"
            "The server may be busy or overloaded."
        )

    try:
        body: dict[str, Any] = resp.json()
    except Exception:
        body = {"_raw": resp.text}

    if not resp.is_success:
        # 401: authentication required — never echo credentials or auth data.
        if resp.status_code == 401:
            # If this is a handoff session (worker capability), provide
            # explicit diagnostics for expired/revoked tokens vs other auth
            # failures. The server sends specific error codes to help diagnose.
            if task_capability:
                err = body.get("error", {}) if isinstance(body, dict) else {}
                error_code = err.get("code", "")
                error_message = err.get("message", "")

                if "expired" in error_message.lower():
                    sys.exit(
                        f"ERROR (401): Task handoff capability expired.\n"
                        f"The worker exceeded the session lifetime.\n"
                        f"Details: {error_message}"
                    )
                elif "revoked" in error_message.lower():
                    sys.exit(
                        f"ERROR (401): Task handoff capability was revoked.\n"
                        f"The worker was terminated or restarted.\n"
                        f"Details: {error_message}"
                    )
                else:
                    sys.exit(
                        f"ERROR (401): Task handoff capability validation failed.\n"
                        f"Details: {error_message or 'Check server logs'}"
                    )
            else:
                sys.exit(format_auth_error(base_url))

        err = body.get("error", {}) if isinstance(body, dict) else {}
        msg = (
            err.get("message")
            or (body.get("detail") if isinstance(body, dict) else None)
            or resp.text
        )
        sys.exit(f"ERROR ({resp.status_code}): {msg}")

    return body


def _task_handoff_request(
    base_url: str,
    action: str,
    data: dict[str, Any],
) -> dict[str, Any] | None:
    """Use the dedicated scoped endpoint when a worker capability is present.

    ``None`` means this is an ordinary operator CLI invocation and callers
    should use the legacy tracker endpoint.  A capability is never sent to a
    general endpoint, even when a command is malformed.

    Grant renewal is handled only by the server-owned worker lease. The
    task-handoff endpoint never extends a bearer token in response to a
    request.
    """
    token = _task_handoff_token()
    if token is None:
        return None

    payload = {**data}
    if not payload.get("project_id"):
        project_id = _task_handoff_project(payload)
        if project_id:
            payload["project_id"] = project_id
    assigned_task = os.environ.get(TASK_HANDOFF_TASK_ENV, "").strip()
    if assigned_task and not payload.get("worker_task_identifier"):
        payload["worker_task_identifier"] = assigned_task
    payload["action"] = action
    return _http(
        "POST",
        f"{base_url}/api/v1/task-handoff",
        data=payload,
        task_capability=token,
    )


# ---------------------------------------------------------------------------
# Identifier encoding
# ---------------------------------------------------------------------------


_GITHUB_IDENTIFIER_RE = re.compile(r"^([^/\s]+/[^#\s]+)#(\d+)$")


def _path_identifier(identifier: str) -> str:
    """Return a route-safe placeholder for *identifier*.

    FastAPI/Starlette decodes ``%2F`` before route matching, so a GitHub issue
    identifier like ``owner/repo#42`` cannot be placed in a single path
    segment even when URL-encoded.  Use the issue number as the path segment
    and carry the full identifier in ``issue_key`` instead.
    """
    match = _GITHUB_IDENTIFIER_RE.match(identifier.strip())
    if match:
        return match.group(2)
    return identifier


def _managed_repo_from_identifier(identifier: str) -> str | None:
    """Return owner/repo for a fully-qualified GitHub issue identifier."""
    match = _GITHUB_IDENTIFIER_RE.match(identifier.strip())
    return match.group(1) if match else None


def _add_project_or_managed_repo(
    payload: dict[str, Any],
    identifier: str,
    project: str | None,
) -> None:
    if project:
        payload["project_id"] = project
    elif managed_repo := _managed_repo_from_identifier(identifier):
        payload["managed_repo"] = managed_repo


def _encode_id(identifier: str) -> str:
    """URL-encode an identifier for use in a URL path segment.

    GitHub-style identifiers such as ``owner/repo#123`` contain characters
    (``/``, ``#``) that cannot appear unencoded in URL path segments.
    """
    return urllib.parse.quote(identifier, safe="")


def _encode_path_id(identifier: str) -> str:
    """URL-encode the route-safe path identifier for API calls."""
    return _encode_id(_path_identifier(identifier))


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def _print_issue_detail(detail: dict[str, Any]) -> None:
    """Format and print issue detail for agent consumption."""
    identifier = detail.get("display_identifier") or detail.get("identifier", "?")
    title = detail.get("title", "")
    status = detail.get("state", "")
    priority = detail.get("priority", "")
    project = detail.get("project_name", "")
    labels_list: list[str] = detail.get("labels") or []
    labels = ", ".join(labels_list)
    description = (detail.get("description") or "").strip()
    url = detail.get("url", "")
    comments = detail.get("comments") or []
    children = detail.get("children") or []

    lines: list[str] = [
        f"Task {identifier} - {title}",
        "=" * 50,
        f"Status: {status}",
    ]
    if priority:
        lines.append(f"Priority: {priority}")
    if project:
        lines.append(f"Project: {project}")
    if labels:
        lines.append(f"Labels: {labels}")
    if url:
        lines.append(f"URL: {url}")
    if description:
        lines.extend(["", "Description:", description])

    if children:
        lines.append("")
        lines.append("Children:")
        for child in children:
            c_id = child.get("display_identifier") or child.get("identifier", "?")
            c_title = child.get("title", "")
            c_state = child.get("state", "")
            lines.append(f"  - {c_id}: {c_title} [{c_state}]")

    if comments:
        lines.append("")
        lines.append("Comments:")
        for comment in comments:
            author = comment.get("author", "?")
            created = comment.get("created_at", "")
            text = (comment.get("text") or "").strip()
            lines.append(f"  #{comment.get('id', '?')} - {author} - {created}")
            for line in text.splitlines():
                lines.append(f"    {line}")

    print("\n".join(lines))


# ---------------------------------------------------------------------------
# Subcommand implementations
# ---------------------------------------------------------------------------


def _cmd_view(base_url: str, args: argparse.Namespace) -> None:
    """oompah task view <identifier> [--project <id>]"""
    identifier = args.identifier
    params: dict[str, str] = {"issue_key": identifier}
    _add_project_or_managed_repo(params, identifier, getattr(args, "project", None))
    handoff = _task_handoff_request(
        base_url,
        "view",
        {
            "identifier": identifier,
            "project_id": getattr(args, "project", None),
        },
    )
    if handoff is not None:
        _print_issue_detail(handoff.get("detail") or handoff)
        return
    path = f"/api/v1/issues/{_encode_path_id(identifier)}/detail"
    result = _http("GET", f"{base_url}{path}", params=params)
    _print_issue_detail(result)


def _cmd_comment(base_url: str, args: argparse.Namespace) -> None:
    """oompah task comment <identifier> --message "..." [--author oompah]"""
    identifier = args.identifier
    data: dict[str, Any] = {
        "text": args.message,
        "author": args.author,
        "identifier": identifier,
        "issue_key": identifier,
    }
    _add_project_or_managed_repo(data, identifier, getattr(args, "project", None))
    if _task_handoff_request(base_url, "comment", data) is not None:
        print("Comment posted.")
        return
    path = f"/api/v1/issues/{_encode_path_id(identifier)}/comments"
    _http("POST", f"{base_url}{path}", data=data)
    print("Comment posted.")


def _cmd_create(base_url: str, args: argparse.Namespace) -> None:
    """oompah task create --project <id> --title "..." [...]"""
    data: dict[str, Any] = {
        "title": args.title,
        "project_id": args.project,
        "type": args.issue_type,
    }
    if getattr(args, "description", None):
        data["description"] = args.description
    if getattr(args, "priority", None):
        data["priority"] = args.priority
    if getattr(args, "labels", None):
        data["labels"] = args.labels
    # Preserve source task identity across tracker backends (AC#2).
    # When --source is given, the server prepends "Triggered by: <id>" to the
    # description so the follow-up is always traceable back to its origin.
    source_task_id = getattr(args, "source", None)
    if source_task_id:
        data["source_task_id"] = source_task_id
    result = _http("POST", f"{base_url}/api/v1/issues", data=data)
    issue = result.get("issue") or {}
    identifier = issue.get("identifier", "?")
    title = issue.get("title") or args.title
    url = issue.get("url", "")
    output = f"Created: {identifier} - {title}"
    if url:
        output += f"\nURL: {url}"
    print(output)


def _cmd_child_create(base_url: str, args: argparse.Namespace) -> None:
    """oompah task child-create <parent-id> --title "..." [--project <id>]"""
    data: dict[str, Any] = {
        "title": args.title,
        "parent_id": args.parent_id,
        "type": args.issue_type,
    }
    _add_project_or_managed_repo(data, args.parent_id, getattr(args, "project", None))
    if getattr(args, "description", None):
        data["description"] = args.description
    if getattr(args, "priority", None):
        data["priority"] = args.priority
    result = _http("POST", f"{base_url}/api/v1/issues", data=data)
    issue = result.get("issue") or {}
    identifier = issue.get("identifier", "?")
    title = issue.get("title") or args.title
    url = issue.get("url", "")
    output = f"Created: {identifier} - {title}"
    if url:
        output += f"\nURL: {url}"
    print(output)


def _cmd_set_status(base_url: str, args: argparse.Namespace) -> None:
    """Request a task status change through the project-aware API."""
    identifier = args.identifier
    data: dict[str, Any] = {
        "status": args.status,
        "issue_key": identifier,
    }
    actor_arg = getattr(args, "actor", None)
    actor = actor_arg if isinstance(actor_arg, str) and actor_arg.strip() else None
    actor = actor or os.environ.get("OOMPAH_ACTOR_LOGIN")
    # OOMPAH-624: When client credentials are configured, the server
    # binds the actor to the authenticated principal.  Explicit --actor
    # is deprecated: warn on match, hard-fail on conflict.
    actor = _reconcile_actor_with_session(actor, flag="--actor")
    if actor:
        data["actor_login"] = str(actor).strip()
    # ``is True`` keeps older programmatic callers (and Namespace-like test
    # doubles without the new field) on the backward-compatible path.
    audit_override = getattr(args, "audit_override", False) is True
    if audit_override:
        data["audit_override"] = True
        reason = getattr(args, "override_reason", None)
        if reason is not None:
            data["override_reason"] = reason
    audit_retry = getattr(args, "audit_retry", False) is True
    if audit_retry:
        data["audit_retry"] = True
        reason = getattr(args, "audit_retry_reason", None)
        if reason is not None:
            data["audit_retry_reason"] = reason
        raw_addendum = getattr(args, "audit_retry_evidence_addendum", None)
        if isinstance(raw_addendum, str) and raw_addendum.strip():
            try:
                addendum = json.loads(raw_addendum)
            except (TypeError, json.JSONDecodeError) as exc:
                raise SystemExit(
                    "--audit-retry-evidence-addendum must be valid JSON"
                ) from exc
            if not isinstance(addendum, dict):
                raise SystemExit(
                    "--audit-retry-evidence-addendum must decode to a JSON object"
                )
            data["audit_retry_evidence_addendum"] = addendum
    _add_project_or_managed_repo(data, identifier, getattr(args, "project", None))
    handoff_data = {
        "identifier": identifier,
        "project_id": getattr(args, "project", None),
        "status": args.status,
        "summary": getattr(args, "summary", None),
    }
    if actor:
        handoff_data["actor_login"] = str(actor).strip()
    if audit_override:
        handoff_data["audit_override"] = True
        if getattr(args, "override_reason", None) is not None:
            handoff_data["override_reason"] = args.override_reason
    # Audit retry is an owner/operator action, never a worker handoff.
    handoff = (
        None
        if audit_retry
        else _task_handoff_request(base_url, "set-status", handoff_data)
    )
    if handoff is not None:
        _print_status_result(handoff, args.status)
        return
    path = f"/api/v1/issues/{_encode_path_id(identifier)}"
    result = _http("PATCH", f"{base_url}{path}", data=data)

    # Post the summary as a comment when provided (tracker-neutral approach).
    summary = getattr(args, "summary", None)
    if summary:
        comment_data: dict[str, Any] = {
            "text": summary,
            "author": "oompah",
            "issue_key": identifier,
        }
        _add_project_or_managed_repo(
            comment_data,
            identifier,
            getattr(args, "project", None),
        )
        comment_path = f"/api/v1/issues/{_encode_path_id(identifier)}/comments"
        _http("POST", f"{base_url}{comment_path}", data=comment_data)

    _print_status_result(result, args.status)


def _print_status_result(result: dict[str, Any], requested_status: str) -> None:
    """Print a stable status result for API and task-handoff responses."""

    if result.get("audit_retry"):
        print(
            f"Terminal audit rearmed: {result.get('requested_target') or requested_status} "
            f"(status: {result.get('status') or 'In Validation'}, "
            f"audit ID: {result.get('audit_id') or 'pending'})"
        )
    elif (
        str(result.get("status", "")).strip().lower() == "in validation"
        and result.get("requested_target")
    ):
        audit_id = result.get("audit_id") or "pending"
        print(
            f"Terminal transition queued: {result['requested_target']} "
            f"(status: In Validation, audit ID: {audit_id})"
        )
    elif result.get("requested_target"):
        audit_id = result.get("audit_id") or "pending"
        current_status = result.get("status") or "unchanged"
        print(
            f"Terminal transition recorded: {result['requested_target']} "
            f"(status remains: {current_status}, audit ID: {audit_id})"
        )
    elif result.get("audit_override"):
        print(
            f"Status set by owner override: "
            f"{result.get('status') or requested_status} "
            f"(audit ID: {result.get('audit_id') or 'recorded'})"
        )
    else:
        print(f"Status set to: {requested_status}")


def _git_value(*args: str, cwd: str | Path | None = None) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    value = completed.stdout.strip()
    return value if completed.returncode == 0 and value else None


def _git_submission_evidence(
    *,
    cwd: str | Path | None = None,
    access_token: str | None = None,
    forge_kind: str = "github",
) -> dict[str, Any]:
    """Capture branch/head evidence from the worker's current worktree."""

    branch = _git_value("branch", "--show-current", cwd=cwd)
    head_sha = _git_value("rev-parse", "HEAD", cwd=cwd)
    try:
        status = subprocess.run(
            ["git", "status", "--porcelain=v1"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd,
        )
        worktree_clean = status.returncode == 0 and not status.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        worktree_clean = False
    remote_head_sha = None
    if branch:
        try:
            with git_credential_environment(
                forge_kind=forge_kind,
                access_token=access_token,
            ) as env:
                remote = subprocess.run(
                    ["git", "ls-remote", "--heads", "origin", branch],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=15,
                    cwd=cwd,
                    env=env,
                )
            remote.stdout = redact_git_output(
                remote.stdout, (access_token or "",)
            )
            remote.stderr = redact_git_output(
                remote.stderr, (access_token or "",)
            )
            if remote.returncode == 0 and remote.stdout.strip():
                remote_head_sha = remote.stdout.split()[0].strip()
        except (OSError, subprocess.TimeoutExpired):
            remote_head_sha = None
    changed_paths: list[str] = []
    base_sha = _git_value("merge-base", "HEAD", "origin/main", cwd=cwd)
    if base_sha:
        try:
            changed = subprocess.run(
                ["git", "diff", "--name-only", f"{base_sha}..HEAD"],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
                cwd=cwd,
            )
            if changed.returncode == 0:
                changed_paths = sorted(
                    {
                        path.strip()
                        for path in changed.stdout.splitlines()
                        if path.strip()
                    }
                )[:256]
        except (OSError, subprocess.TimeoutExpired):
            changed_paths = []
    return {
        key: value
        for key, value in {
            "task_branch": branch,
            "head_sha": head_sha,
            "remote_head_sha": remote_head_sha,
            "worktree_clean": worktree_clean,
            "changed_paths": changed_paths,
        }.items()
        if value is not None
    }


def _cmd_submit(base_url: str, args: argparse.Namespace) -> None:
    """Submit committed worker output for ordered integration."""

    identifier = args.identifier
    data: dict[str, Any] = {
        "identifier": identifier,
        "issue_key": identifier,
        "summary": getattr(args, "summary", None),
        **_git_submission_evidence(),
    }
    _add_project_or_managed_repo(data, identifier, getattr(args, "project", None))
    if _task_handoff_request(base_url, "submit", data) is not None:
        print(f"Submitted for integration: {identifier}")
        return
    path = f"/api/v1/issues/{_encode_path_id(identifier)}/submit"
    _http("POST", f"{base_url}{path}", data=data)
    print(f"Submitted for integration: {identifier}")


def _cmd_add_label(base_url: str, args: argparse.Namespace) -> None:
    """oompah task add-label <identifier> <label>"""
    identifier = args.identifier
    data: dict[str, Any] = {
        "label": args.label,
        "identifier": identifier,
        "issue_key": identifier,
    }
    actor_arg = getattr(args, "actor", None)
    actor = actor_arg if isinstance(actor_arg, str) and actor_arg.strip() else None
    actor = actor or os.environ.get("OOMPAH_ACTOR_LOGIN")
    # OOMPAH-624: same actor reconciliation as set-status.
    actor = _reconcile_actor_with_session(actor, flag="--actor")
    if actor:
        data["actor_login"] = str(actor).strip()
    _add_project_or_managed_repo(data, identifier, getattr(args, "project", None))
    if _task_handoff_request(base_url, "add-label", data) is not None:
        print(f"Label added: {args.label}")
        return
    path = f"/api/v1/issues/{_encode_path_id(identifier)}/labels"
    _http("POST", f"{base_url}{path}", data=data)
    print(f"Label added: {args.label}")


def _cmd_remove_label(base_url: str, args: argparse.Namespace) -> None:
    """oompah task remove-label <identifier> <label>"""
    identifier = args.identifier
    # URL-encode the label and pass issue_key as a query param since DELETE
    # bodies are not reliably forwarded by all HTTP intermediaries.
    encoded_label = urllib.parse.quote(args.label, safe="")
    path = f"/api/v1/issues/{_encode_path_id(identifier)}/labels/{encoded_label}"
    params: dict[str, str] = {"issue_key": identifier}
    _add_project_or_managed_repo(params, identifier, getattr(args, "project", None))
    if _task_handoff_request(
        base_url,
        "remove-label",
        {
            "identifier": identifier,
            "label": args.label,
            "project_id": getattr(args, "project", None),
        },
    ) is not None:
        print(f"Label removed: {args.label}")
        return
    _http("DELETE", f"{base_url}{path}", params=params)
    print(f"Label removed: {args.label}")


def _cmd_set_dependency(base_url: str, args: argparse.Namespace) -> None:
    """oompah task set-dependency <identifier> --depends-on <dep-id>"""
    identifier = args.identifier
    hard_start = getattr(args, "hard_start", False) is True
    data: dict[str, Any] = {
        "depends_on": args.depends_on,
        "issue_key": identifier,
        "dependency_type": "hard_start" if hard_start else "finish",
    }
    _add_project_or_managed_repo(data, identifier, getattr(args, "project", None))
    path = f"/api/v1/issues/{_encode_path_id(identifier)}/dependencies"
    _http("POST", f"{base_url}{path}", data=data)
    kind = "Hard-start dependency" if hard_start else "Dependency"
    print(f"{kind} set: {identifier} depends on {args.depends_on}")


def _cmd_remove_dependency(base_url: str, args: argparse.Namespace) -> None:
    """oompah task remove-dependency <identifier> --depends-on <dep-id>"""
    identifier = args.identifier
    hard_start = getattr(args, "hard_start", False) is True
    params: dict[str, str] = {
        "depends_on": args.depends_on,
        "issue_key": identifier,
        "dependency_type": "hard_start" if hard_start else "finish",
    }
    _add_project_or_managed_repo(
        params, identifier, getattr(args, "project", None)
    )
    path = f"/api/v1/issues/{_encode_path_id(identifier)}/dependencies"
    _http("DELETE", f"{base_url}{path}", params=params)
    kind = "Hard-start dependency" if hard_start else "Dependency"
    print(f"{kind} removed: {identifier} no longer depends on {args.depends_on}")


def _cmd_set_source(base_url: str, args: argparse.Namespace) -> None:
    """oompah task set-source <identifier> <source-id> [--project <id>]

    Sets or replaces the source-task reference on an existing task.  The
    server rewrites the "Triggered by: <id>" header in the task description
    and persists the change through the active tracker backend (native
    Markdown or GitHub Issues).

    The source reference is then visible via ``oompah task view``.
    """
    identifier = args.identifier
    source_id = args.source_id.strip() if args.source_id else ""
    if not source_id:
        sys.exit("ERROR: source-id must not be empty.")
    data: dict[str, Any] = {
        "source_task_id": source_id,
        "issue_key": identifier,
    }
    _add_project_or_managed_repo(data, identifier, getattr(args, "project", None))
    path = f"/api/v1/issues/{_encode_path_id(identifier)}"
    _http("PATCH", f"{base_url}{path}", data=data)
    print(f"Source set: {source_id}")


def _cmd_remove_source(base_url: str, args: argparse.Namespace) -> None:
    """oompah task remove-source <identifier> [--project <id>]

    Removes the source-task reference from an existing task.  The server
    strips the "Triggered by: <id>" header from the task description and
    persists the change through the active tracker backend.

    After removal, ``oompah task view`` will show no source reference.
    """
    identifier = args.identifier
    data: dict[str, Any] = {
        "clear_source": True,
        "issue_key": identifier,
    }
    _add_project_or_managed_repo(data, identifier, getattr(args, "project", None))
    path = f"/api/v1/issues/{_encode_path_id(identifier)}"
    _http("PATCH", f"{base_url}{path}", data=data)
    print("Source removed.")


def _cmd_coordinate(base_url: str, args: argparse.Namespace) -> None:
    """Read or write the durable task coordination surface."""

    identifier = args.identifier
    operation = args.coordinate_operation
    data: dict[str, Any] = {
        "identifier": identifier,
        "issue_key": identifier,
    }
    _add_project_or_managed_repo(
        data,
        identifier,
        getattr(args, "project", None),
    )
    handoff_action = f"coordination-{operation}"
    if operation == "send":
        data.update(
            {
                "recipient": args.recipient,
                "text": args.message,
                "kind": args.kind,
                "idempotency_key": args.idempotency_key,
            }
        )
    elif operation == "checkpoint":
        data.update(
            {
                **_git_submission_evidence(),
                "summary": args.summary,
                "changed_paths": args.path or None,
            }
        )
    elif operation == "inbox":
        data.update(
            {
                "unread_only": args.unread,
                "after_id": args.after,
                "limit": args.limit,
            }
        )

    scoped = _task_handoff_request(base_url, handoff_action, data)
    if scoped is not None:
        print(json.dumps(scoped, indent=2, sort_keys=True))
        return

    path = (
        f"/api/v1/issues/{_encode_path_id(identifier)}/coordination/"
        f"{operation}"
    )
    if operation in {"peers", "inbox"}:
        params = {
            key: str(value)
            for key, value in data.items()
            if key
            in {
                "issue_key",
                "project_id",
                "managed_repo",
                "after_id",
                "limit",
            }
            and value is not None
        }
        if operation == "inbox" and data.get("unread_only"):
            params["unread_only"] = "true"
        result = _http("GET", f"{base_url}{path}", params=params)
    else:
        result = _http("POST", f"{base_url}{path}", data=data)
    print(json.dumps(result, indent=2, sort_keys=True))


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser for ``oompah task``."""
    parser = argparse.ArgumentParser(
        prog="oompah task",
        description=(
            "Tracker-neutral task operations.\n\n"
            "Calls the local oompah server API and works with supported oompah "
            "trackers.  Set OOMPAH_SERVER_URL or use "
            "--server/--port to point at a non-default server.\n\n"
            "For HTTP Basic auth, credentials are resolved from (in precedence order):\n"
            "  1. CLI: --username and --password-file\n"
            "  2. Environment: OOMPAH_SERVER_USERNAME and "
            "OOMPAH_SERVER_PASSWORD_FILE (preferred) or OOMPAH_SERVER_PASSWORD\n"
            "  3. ~/.netrc file (when server URL can be resolved)\n\n"
            "Never put credentials in the server URL. "
            "There is no plaintext --password option (use --password-file or "
            "OOMPAH_SERVER_PASSWORD_FILE for unattended use)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--server",
        default=None,
        metavar="URL",
        help=(
            "oompah server base URL, e.g. http://127.0.0.1:8080. "
            "Overrides --port and OOMPAH_SERVER_URL. "
            "Must not contain embedded credentials (user:pass@host)."
        ),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        metavar="N",
        help="oompah server port on localhost (default: 8080)",
    )
    parser.add_argument(
        "--username",
        default=None,
        metavar="USER",
        help=(
            "Username for HTTP Basic auth. Overrides OOMPAH_SERVER_USERNAME. "
            "Non-secret; combine with --password-file or "
            "OOMPAH_SERVER_PASSWORD_FILE."
        ),
    )
    parser.add_argument(
        "--password-file",
        default=None,
        metavar="PATH",
        dest="password_file",
        help=(
            "Path to a file containing the client plaintext password. "
            "Overrides OOMPAH_SERVER_PASSWORD_FILE. "
            "Must be a regular (non-symlink) readable file. "
            "Preferred over OOMPAH_SERVER_PASSWORD for unattended use; "
            "no plaintext --password option exists."
        ),
    )

    sub = parser.add_subparsers(dest="subcommand", required=True)

    # --- coordinate ---
    p_coordinate = sub.add_parser(
        "coordinate",
        help="Exchange durable messages with suggested peer tasks",
    )
    coordinate_sub = p_coordinate.add_subparsers(
        dest="coordinate_operation",
        required=True,
    )

    def _coordinate_common(command):
        command.add_argument("identifier", help="Current task identifier")
        command.add_argument(
            "--project",
            "--project-id",
            dest="project",
            default=None,
        )

    p_peers = coordinate_sub.add_parser(
        "peers",
        help="List server-suggested coordination peers",
    )
    _coordinate_common(p_peers)

    p_inbox = coordinate_sub.add_parser(
        "inbox",
        help="Read durable messages addressed to this task",
    )
    _coordinate_common(p_inbox)
    p_inbox.add_argument("--unread", action="store_true")
    p_inbox.add_argument("--after", default=None)
    p_inbox.add_argument("--limit", type=int, default=100)

    p_send = coordinate_sub.add_parser(
        "send",
        help="Send a message to a server-suggested peer",
    )
    _coordinate_common(p_send)
    p_send.add_argument("--to", dest="recipient", required=True)
    p_send.add_argument("--message", "-m", required=True)
    p_send.add_argument("--kind", default="message")
    p_send.add_argument("--idempotency-key", default=None)

    p_checkpoint = coordinate_sub.add_parser(
        "checkpoint",
        help="Publish changed paths and an implementation checkpoint",
    )
    _coordinate_common(p_checkpoint)
    p_checkpoint.add_argument("--summary", required=True)
    p_checkpoint.add_argument("--path", action="append", default=[])

    # --- view ---
    p_view = sub.add_parser("view", help="Show task details")
    p_view.add_argument("identifier", help="Task identifier (e.g. TASK-123 or owner/repo#42)")
    p_view.add_argument(
        "--project", "--project-id",
        dest="project",
        default=None,
        metavar="PROJECT_ID",
        help="Restrict lookup to a specific project",
    )

    # --- comment ---
    p_comment = sub.add_parser("comment", help="Add a comment to a task")
    p_comment.add_argument("identifier", help="Task identifier")
    p_comment.add_argument("--message", "-m", required=True, help="Comment text")
    p_comment.add_argument(
        "--author",
        default="oompah",
        help="Comment author (default: oompah)",
    )
    p_comment.add_argument(
        "--project", "--project-id",
        dest="project",
        default=None,
        metavar="PROJECT_ID",
    )

    # --- create ---
    p_create = sub.add_parser("create", help="Create a new task")
    p_create.add_argument("--title", required=True, help="Task title")
    p_create.add_argument(
        "--description",
        "--desc",
        dest="description",
        required=True,
        help="Required standalone implementation description",
    )
    p_create.add_argument(
        "--project", "--project-id",
        dest="project",
        required=True,
        metavar="PROJECT_ID",
        help="Project to create the task in",
    )
    p_create.add_argument(
        "--type",
        dest="issue_type",
        default="task",
        choices=["task", "bug", "feature", "epic", "chore"],
        help="Issue type (default: task)",
    )
    p_create.add_argument(
        "--priority",
        default=None,
        choices=["high", "medium", "low"],
    )
    p_create.add_argument(
        "--label",
        action="append",
        dest="labels",
        metavar="LABEL",
        help="Add a label (can be repeated)",
    )
    p_create.add_argument(
        "--source",
        default=None,
        metavar="SOURCE_ID",
        help=(
            "Identifier of the task that triggered this follow-up "
            "(e.g. TASK-123 or owner/repo#42). "
            "Preserved in the description across all tracker backends."
        ),
    )

    # --- child-create ---
    p_child = sub.add_parser("child-create", help="Create a child task under a parent")
    p_child.add_argument("parent_id", help="Parent task identifier")
    p_child.add_argument("--title", required=True, help="Child task title")
    p_child.add_argument(
        "--description",
        "--desc",
        dest="description",
        required=True,
        help="Required standalone implementation description",
    )
    p_child.add_argument(
        "--project", "--project-id",
        dest="project",
        default=None,
        metavar="PROJECT_ID",
        help="Project to create the task in (optional; inferred from parent)",
    )
    p_child.add_argument(
        "--type",
        dest="issue_type",
        default="task",
        choices=["task", "bug", "feature", "epic", "chore"],
    )
    p_child.add_argument(
        "--priority",
        default=None,
        choices=["high", "medium", "low"],
    )

    # --- set-status ---
    p_status = sub.add_parser(
        "set-status",
        help="Update task status (terminal states are queued for validation)",
    )
    p_status.add_argument("identifier", help="Task identifier")
    p_status.add_argument("status", help="New status (e.g. Done, In Progress, Open)")
    p_status.add_argument(
        "--summary", "--final-summary",
        dest="summary",
        default=None,
        help="Summary comment to post when closing a task",
    )
    p_status.add_argument(
        "--project", "--project-id",
        dest="project",
        default=None,
        metavar="PROJECT_ID",
    )
    p_status.add_argument(
        "--actor",
        default=None,
        metavar="LOGIN",
        help="Login requesting a gated transition or owner audit override",
    )
    p_status.add_argument(
        "--audit-override",
        action="store_true",
        help="Apply a terminal status as an authorized project-owner override",
    )
    p_status.add_argument(
        "--override-reason",
        default=None,
        metavar="REASON",
        help="Required explanation when --audit-override is used",
    )
    p_status.add_argument(
        "--audit-retry",
        action="store_true",
        help="Rearm an exhausted terminal audit without reopening implementation work",
    )
    p_status.add_argument(
        "--audit-retry-reason",
        default=None,
        metavar="REASON",
        help="Required explanation when --audit-retry is used",
    )
    p_status.add_argument(
        "--audit-retry-evidence-addendum",
        default=None,
        metavar="JSON",
        help=(
            "JSON evidence addendum for an owner retry after missing evidence; "
            "must include the current evidence_fingerprint and successful checks"
        ),
    )

    # --- submit ---
    p_submit = sub.add_parser(
        "submit",
        help="Submit committed work for ordered integration",
    )
    p_submit.add_argument("identifier", help="Task identifier")
    p_submit.add_argument(
        "--summary",
        required=True,
        help="Completion summary recorded on the task",
    )
    p_submit.add_argument(
        "--project", "--project-id",
        dest="project",
        default=None,
        metavar="PROJECT_ID",
    )

    # --- add-label ---
    p_add = sub.add_parser("add-label", help="Add a label to a task")
    p_add.add_argument("identifier", help="Task identifier")
    p_add.add_argument("label", help="Label to add")
    p_add.add_argument(
        "--project", "--project-id",
        dest="project",
        default=None,
        metavar="PROJECT_ID",
    )
    p_add.add_argument(
        "--actor",
        default=None,
        metavar="LOGIN",
        help="GitHub login requesting a gated status-label transition",
    )

    # --- remove-label ---
    p_rm = sub.add_parser("remove-label", help="Remove a label from a task")
    p_rm.add_argument("identifier", help="Task identifier")
    p_rm.add_argument("label", help="Label to remove")
    p_rm.add_argument(
        "--project", "--project-id",
        dest="project",
        default=None,
        metavar="PROJECT_ID",
    )

    # --- set-dependency ---
    p_dep = sub.add_parser("set-dependency", help="Record a task dependency")
    p_dep.add_argument(
        "identifier",
        help="The task that should depend on another",
    )
    p_dep.add_argument(
        "--depends-on",
        required=True,
        dest="depends_on",
        metavar="DEP_ID",
        help="Identifier of the blocker task",
    )
    p_dep.add_argument(
        "--hard-start",
        action="store_true",
        help="Block task start until the dependency is complete",
    )
    p_dep.add_argument(
        "--project", "--project-id",
        dest="project",
        default=None,
        metavar="PROJECT_ID",
    )

    # --- remove-dependency ---
    p_rm_dep = sub.add_parser(
        "remove-dependency",
        help="Remove a task dependency",
    )
    p_rm_dep.add_argument(
        "identifier",
        help="The task whose dependency should be removed",
    )
    p_rm_dep.add_argument(
        "--depends-on",
        required=True,
        dest="depends_on",
        metavar="DEP_ID",
        help="Identifier of the blocker task to remove",
    )
    p_rm_dep.add_argument(
        "--hard-start",
        action="store_true",
        help="Remove a hard-start dependency instead of a finish-order edge",
    )
    p_rm_dep.add_argument(
        "--project", "--project-id",
        dest="project",
        default=None,
        metavar="PROJECT_ID",
    )

    # --- set-source ---
    p_set_src = sub.add_parser(
        "set-source",
        help="Set or replace a task's source reference",
        description=(
            "Sets or replaces the source-task reference on an existing task.\n\n"
            "The server rewrites the 'Triggered by: <source-id>' header in the "
            "task description and persists the change through the active tracker "
            "backend.  The new source reference is immediately visible via "
            "'oompah task view'.\n\n"
            "To remove the source reference entirely use 'oompah task remove-source'."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_set_src.add_argument("identifier", help="Task identifier (e.g. TASK-123)")
    p_set_src.add_argument(
        "source_id",
        metavar="SOURCE_ID",
        help=(
            "Identifier of the originating task (e.g. TASK-42 or owner/repo#7). "
            "Must not be empty."
        ),
    )
    p_set_src.add_argument(
        "--project", "--project-id",
        dest="project",
        default=None,
        metavar="PROJECT_ID",
        help="Restrict lookup to a specific project",
    )

    # --- remove-source ---
    p_rm_src = sub.add_parser(
        "remove-source",
        help="Remove a task's source reference",
        description=(
            "Removes the source-task reference from an existing task.\n\n"
            "The server strips the 'Triggered by: <source-id>' header from the "
            "task description and persists the change through the active tracker "
            "backend.  After removal, 'oompah task view' will show no source "
            "reference.\n\n"
            "To set or replace the source reference use 'oompah task set-source'."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_rm_src.add_argument("identifier", help="Task identifier (e.g. TASK-123)")
    p_rm_src.add_argument(
        "--project", "--project-id",
        dest="project",
        default=None,
        metavar="PROJECT_ID",
        help="Restrict lookup to a specific project",
    )

    return parser


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_DISPATCH: dict[str, Any] = {
    "coordinate": _cmd_coordinate,
    "view": _cmd_view,
    "comment": _cmd_comment,
    "create": _cmd_create,
    "child-create": _cmd_child_create,
    "set-status": _cmd_set_status,
    "submit": _cmd_submit,
    "add-label": _cmd_add_label,
    "remove-label": _cmd_remove_label,
    "set-dependency": _cmd_set_dependency,
    "remove-dependency": _cmd_remove_dependency,
    "set-source": _cmd_set_source,
    "remove-source": _cmd_remove_source,
}


def main(argv: list[str] | None = None) -> None:
    """Entry point for the ``oompah task`` subcommand surface."""
    parser = build_parser()
    args = parser.parse_args(argv)

    # Operator invocations should use the current client settings from .env
    # after an htpasswd rotation.  A spawned worker must not reload them: it
    # receives only a scoped handoff capability, never reusable Basic auth.
    if not _task_handoff_token():
        load_client_environment()

    # A spawned worker may only use the four task-handoff operations routed
    # above.  Reject broader commands before any request is made; in
    # particular, never fall back to operator Basic credentials.
    if _task_handoff_token() and args.subcommand not in {
        "view",
        "comment",
        "set-status",
        "submit",
        "coordinate",
        "add-label",
        "remove-label",
    }:
        sys.exit(
            "ERROR: this spawned worker has a task-scoped handoff capability; "
            "the requested task operation is not granted."
        )

    base_url = _resolve_server_url(
        getattr(args, "server", None),
        getattr(args, "port", None),
    )

    # Resolve client credentials (env vars + optional CLI overrides + netrc).
    # Exits with a clear error on misconfiguration (missing username,
    # conflicting sources, unreadable password file, malformed netrc, etc.).
    if _task_handoff_token():
        # The capability is the only authentication mechanism for this
        # process.  Do not even resolve inherited operator credentials.
        _auth = None
    else:
        try:
            _auth = resolve_client_credentials(
                username_override=getattr(args, "username", None),
                password_file_override=getattr(args, "password_file", None),
                server_url=base_url,
            )
        except CredentialError as exc:
            sys.exit(f"ERROR: {exc}")

    # Build dispatch at call time so module-level patches in tests take effect.
    dispatch = {
        "coordinate": _cmd_coordinate,
        "view": _cmd_view,
        "comment": _cmd_comment,
        "create": _cmd_create,
        "child-create": _cmd_child_create,
        "set-status": _cmd_set_status,
        "submit": _cmd_submit,
        "add-label": _cmd_add_label,
        "remove-label": _cmd_remove_label,
        "set-dependency": _cmd_set_dependency,
        "remove-dependency": _cmd_remove_dependency,
        "set-source": _cmd_set_source,
        "remove-source": _cmd_remove_source,
    }

    fn = dispatch.get(args.subcommand)
    if fn is None:  # pragma: no cover  – argparse already guards this
        parser.error(f"Unknown subcommand: {args.subcommand!r}")

    # Store the resolved auth in the module-level slot so _http picks it up.
    # The slot is restored on exit so tests that patch _http directly remain
    # unaffected.  This CLI is single-threaded, so the module-level variable
    # is safe; no concurrent calls share state.
    global _session_auth
    _prev_auth = _session_auth
    _session_auth = _auth
    try:
        fn(base_url, args)
    finally:
        _session_auth = _prev_auth
