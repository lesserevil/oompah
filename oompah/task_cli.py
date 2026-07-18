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
    oompah task add-label <identifier> <label>
    oompah task remove-label <identifier> <label>
    oompah task set-dependency <identifier> --depends-on <dep-id>
    oompah task set-source <identifier> <source-id> [--project <id>]
    oompah task remove-source <identifier> [--project <id>]
"""

from __future__ import annotations

import argparse
import math
import os
import re
import sys
import urllib.parse
from typing import Any

try:
    import httpx as _httpx
except ImportError:  # pragma: no cover
    _httpx = None  # type: ignore[assignment]

__all__ = ["main", "build_parser"]


_DEFAULT_HTTP_TIMEOUT_SECONDS = 600.0
_HTTP_TIMEOUT_ENV = "OOMPAH_TASK_CLI_TIMEOUT_SECONDS"


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
    """
    if server_override:
        return server_override.rstrip("/")
    if port_override is not None:
        return f"http://127.0.0.1:{port_override}"
    env_url = os.environ.get("OOMPAH_SERVER_URL", "").strip()
    if env_url:
        return env_url.rstrip("/")
    return "http://127.0.0.1:8080"


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
) -> dict[str, Any]:
    """Make an HTTP request to the oompah API and return the JSON body.

    Exits with an actionable error message when the server is unreachable
    (connection refused, DNS failure, timeout) or returns a non-2xx status.
    Never raises — callers can rely on the return value being a valid dict.
    """
    if _httpx is None:
        sys.exit(
            "ERROR: httpx is required for oompah task commands.\n"
            "Install it with: pip install httpx"
        )

    # Derive base URL for error messages (strip everything after /api/).
    base_url = url.split("/api/")[0] if "/api/" in url else url

    try:
        with _httpx.Client(timeout=_resolve_http_timeout()) as client:
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
        err = body.get("error", {}) if isinstance(body, dict) else {}
        msg = (
            err.get("message")
            or (body.get("detail") if isinstance(body, dict) else None)
            or resp.text
        )
        sys.exit(f"ERROR ({resp.status_code}): {msg}")

    return body


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
    path = f"/api/v1/issues/{_encode_path_id(identifier)}/detail"
    result = _http("GET", f"{base_url}{path}", params=params)
    _print_issue_detail(result)


def _cmd_comment(base_url: str, args: argparse.Namespace) -> None:
    """oompah task comment <identifier> --message "..." [--author oompah]"""
    identifier = args.identifier
    data: dict[str, Any] = {
        "text": args.message,
        "author": args.author,
        "issue_key": identifier,
    }
    _add_project_or_managed_repo(data, identifier, getattr(args, "project", None))
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
    """oompah task set-status <identifier> <status> [--summary "..."]"""
    identifier = args.identifier
    data: dict[str, Any] = {
        "status": args.status,
        "issue_key": identifier,
    }
    actor_arg = getattr(args, "actor", None)
    actor = actor_arg if isinstance(actor_arg, str) and actor_arg.strip() else None
    actor = actor or os.environ.get("OOMPAH_ACTOR_LOGIN")
    if actor:
        data["actor_login"] = str(actor).strip()
    _add_project_or_managed_repo(data, identifier, getattr(args, "project", None))
    path = f"/api/v1/issues/{_encode_path_id(identifier)}"
    _http("PATCH", f"{base_url}{path}", data=data)

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

    print(f"Status set to: {args.status}")


def _cmd_add_label(base_url: str, args: argparse.Namespace) -> None:
    """oompah task add-label <identifier> <label>"""
    identifier = args.identifier
    data: dict[str, Any] = {
        "label": args.label,
        "issue_key": identifier,
    }
    actor_arg = getattr(args, "actor", None)
    actor = actor_arg if isinstance(actor_arg, str) and actor_arg.strip() else None
    actor = actor or os.environ.get("OOMPAH_ACTOR_LOGIN")
    if actor:
        data["actor_login"] = str(actor).strip()
    _add_project_or_managed_repo(data, identifier, getattr(args, "project", None))
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
    _http("DELETE", f"{base_url}{path}", params=params)
    print(f"Label removed: {args.label}")


def _cmd_set_dependency(base_url: str, args: argparse.Namespace) -> None:
    """oompah task set-dependency <identifier> --depends-on <dep-id>"""
    identifier = args.identifier
    data: dict[str, Any] = {
        "depends_on": args.depends_on,
        "issue_key": identifier,
    }
    _add_project_or_managed_repo(data, identifier, getattr(args, "project", None))
    path = f"/api/v1/issues/{_encode_path_id(identifier)}/dependencies"
    _http("POST", f"{base_url}{path}", data=data)
    print(f"Dependency set: {identifier} depends on {args.depends_on}")


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
            "--server/--port to point at a non-default server."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--server",
        default=None,
        metavar="URL",
        help=(
            "oompah server base URL, e.g. http://127.0.0.1:8080. "
            "Overrides --port and OOMPAH_SERVER_URL."
        ),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        metavar="N",
        help="oompah server port on localhost (default: 8080)",
    )

    sub = parser.add_subparsers(dest="subcommand", required=True)

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
    p_status = sub.add_parser("set-status", help="Update task status")
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
        help="GitHub login requesting a gated intake transition",
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
    "view": _cmd_view,
    "comment": _cmd_comment,
    "create": _cmd_create,
    "child-create": _cmd_child_create,
    "set-status": _cmd_set_status,
    "add-label": _cmd_add_label,
    "remove-label": _cmd_remove_label,
    "set-dependency": _cmd_set_dependency,
    "set-source": _cmd_set_source,
    "remove-source": _cmd_remove_source,
}


def main(argv: list[str] | None = None) -> None:
    """Entry point for the ``oompah task`` subcommand surface."""
    parser = build_parser()
    args = parser.parse_args(argv)

    base_url = _resolve_server_url(
        getattr(args, "server", None),
        getattr(args, "port", None),
    )

    # Build dispatch at call time so module-level patches in tests take effect.
    dispatch = {
        "view": _cmd_view,
        "comment": _cmd_comment,
        "create": _cmd_create,
        "child-create": _cmd_child_create,
        "set-status": _cmd_set_status,
        "add-label": _cmd_add_label,
        "remove-label": _cmd_remove_label,
        "set-dependency": _cmd_set_dependency,
        "set-source": _cmd_set_source,
        "remove-source": _cmd_remove_source,
    }

    fn = dispatch.get(args.subcommand)
    if fn is None:  # pragma: no cover  – argparse already guards this
        parser.error(f"Unknown subcommand: {args.subcommand!r}")
    fn(base_url, args)
