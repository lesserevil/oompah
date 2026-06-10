"""Tool catalog bridging for ACP-mode agents.

The Claude Agent SDK takes an in-process MCP server with @tool-decorated
functions in ``ClaudeAgentOptions.mcp_servers``. We declare oompah's
existing tool catalog (read_file / write_file / edit_file / list_files /
search_files / run_command / get_project / update_project) here, routing
each one through the same ``_exec_*`` implementations the api_agent path
already uses.

Reusing those implementations is the whole point — they carry oompah's
safety rails (cd-out-of-worktree guard, tracker environment overrides,
per-command timeouts) that claude's native tools don't know about. See
``plans/acp-agent.md`` Q2 (locked decision: tool bridging via option B,
oompah's catalog wins).

This module exposes three catalog builders, one per registered ACP
backend, all wired through the same ``_exec_*`` helpers so the
safety rails are identical:

* :func:`build_tool_catalog` — Claude Agent SDK ``@tool`` format
  (the default backend).
* :func:`build_codex_tool_catalog` — OpenAI Agents SDK
  ``@function_tool`` format (second backend).
* :func:`build_opencode_tool_catalog` — OpenCode SDK ``@tool``
  format (third backend, oompah-zlz_2-p1ti).

When the operator adds a new ACP backend the convention is: add a
parallel ``build_<backend>_tool_catalog`` here so the shared
``_exec_*`` implementations remain the single source of truth for
oompah's tool semantics. The backend's :meth:`start_session` picks
which builder to call.

The ``get_project`` / ``update_project`` tools (TASK-464.8) provide a
non-HTTP path for agents running inside oompah MCP to read and update
ProjectStore tracker fields without calling back into
``http://127.0.0.1:8090``, which deadlocks the same-process server.
Both tools require ``project_store`` and ``project_id`` to be passed to
the catalog builder; if either is missing the tools return an
``error:`` message rather than raising.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared project-management helpers (TASK-464.8)
# ---------------------------------------------------------------------------

# Tracker-related fields that agents are allowed to read and update via the
# non-HTTP MCP path.  Intentionally conservative: only the fields needed for
# managed-project cutover and rollback.  Infrastructure fields (repo_path,
# lfs_available, branches, …) must go through the operator UI or API.
_PROJECT_READABLE_FIELDS = frozenset(
    {
        "id",
        "name",
        "tracker_kind",
        "tracker_owner",
        "tracker_repo",
        "github_project_node_id",
        "legacy_backlog_enabled",
        "legacy_backlog_dispatch",
        "tracker_cutover_at",
        "paused",
    }
)

_PROJECT_UPDATABLE_FIELDS = frozenset(
    {
        "tracker_kind",
        "tracker_owner",
        "tracker_repo",
        "github_project_node_id",
        "legacy_backlog_enabled",
        "legacy_backlog_dispatch",
        "tracker_cutover_at",
        "paused",
    }
)


def _exec_get_project(project_store: Any, project_id: str | None) -> str:
    """Return a JSON snapshot of the project's tracker configuration.

    This is the non-HTTP path for agents to read ProjectStore state
    without calling back into ``http://127.0.0.1:8090`` (which deadlocks
    the same-process oompah server).

    Returns a JSON object with the fields in ``_PROJECT_READABLE_FIELDS``,
    or a JSON ``{"error": "..."}`` dict on failure.
    """
    if project_store is None or not project_id:
        return json.dumps(
            {"error": "project_store or project_id not available for this worktree"}
        )
    try:
        project = project_store.get(project_id)
    except Exception as exc:  # pragma: no cover — defensive
        return json.dumps({"error": f"ProjectStore.get failed: {exc}"})

    if project is None:
        return json.dumps({"error": f"Project {project_id!r} not found"})

    cutover_at = None
    raw = getattr(project, "tracker_cutover_at", None)
    if raw is not None:
        try:
            cutover_at = raw.isoformat()
        except AttributeError:
            cutover_at = str(raw)

    result: dict[str, Any] = {
        "id": project.id,
        "name": getattr(project, "name", None),
        "tracker_kind": getattr(project, "tracker_kind", None),
        "tracker_owner": getattr(project, "tracker_owner", None),
        "tracker_repo": getattr(project, "tracker_repo", None),
        "github_project_node_id": getattr(project, "github_project_node_id", None),
        "legacy_backlog_enabled": getattr(project, "legacy_backlog_enabled", False),
        "legacy_backlog_dispatch": getattr(project, "legacy_backlog_dispatch", False),
        "tracker_cutover_at": cutover_at,
        "paused": getattr(project, "paused", False),
    }
    return json.dumps(result, indent=2)


def _exec_update_project(
    project_store: Any,
    project_id: str | None,
    fields_json: str,
) -> str:
    """Update tracker configuration fields for the managed project.

    This is the non-HTTP path for agents to mutate ProjectStore state
    without calling back into ``http://127.0.0.1:8090`` (which deadlocks
    the same-process oompah server) or editing ``.oompah/projects.json``
    directly (which bypasses validation and in-memory state).

    ``fields_json`` must be a JSON-encoded object whose keys are a subset
    of ``_PROJECT_UPDATABLE_FIELDS``.  Returns a JSON object with the
    updated tracker fields, or a plain ``error: ...`` string on failure.
    """
    if project_store is None or not project_id:
        return "error: project_store or project_id not available for this worktree"

    try:
        fields = json.loads(fields_json)
    except (json.JSONDecodeError, TypeError) as exc:
        return f"error: fields_json must be a valid JSON object string: {exc}"

    if not isinstance(fields, dict):
        return "error: fields_json must be a JSON object (dict), not a scalar or array"

    unknown = set(fields) - _PROJECT_UPDATABLE_FIELDS
    if unknown:
        allowed_str = ", ".join(sorted(_PROJECT_UPDATABLE_FIELDS))
        return (
            f"error: unknown fields: {', '.join(sorted(unknown))}. "
            f"Allowed fields are: {allowed_str}"
        )

    try:
        updated = project_store.update(project_id, **fields)
    except Exception as exc:
        return f"error: ProjectStore.update failed: {exc}"

    if updated is None:
        return f"error: Project {project_id!r} not found"

    cutover_at = None
    raw = getattr(updated, "tracker_cutover_at", None)
    if raw is not None:
        try:
            cutover_at = raw.isoformat()
        except AttributeError:
            cutover_at = str(raw)

    result: dict[str, Any] = {
        "updated": True,
        "id": updated.id,
        "tracker_kind": getattr(updated, "tracker_kind", None),
        "tracker_owner": getattr(updated, "tracker_owner", None),
        "tracker_repo": getattr(updated, "tracker_repo", None),
        "github_project_node_id": getattr(updated, "github_project_node_id", None),
        "legacy_backlog_enabled": getattr(updated, "legacy_backlog_enabled", False),
        "legacy_backlog_dispatch": getattr(updated, "legacy_backlog_dispatch", False),
        "tracker_cutover_at": cutover_at,
        "paused": getattr(updated, "paused", False),
    }
    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# Claude Agent SDK tool catalog
# ---------------------------------------------------------------------------


def build_tool_catalog(
    workspace_path: str,
    *,
    run_command_timeout_s: int = 60,
    project_store: Any = None,
    project_id: str | None = None,
) -> list[Any]:
    """Build the SDK-flavored tool list for one ACP session.

    Returns a list of ``SdkMcpTool`` instances (the @tool decorator's
    output), ready to be passed into
    :func:`claude_agent_sdk.create_sdk_mcp_server`.

    Backlog.md commands resolve from the workspace, so no tracker-specific
    environment override is needed. Mirrors the api_agent path.

    When ``project_store`` and ``project_id`` are supplied, two additional
    tools are included: ``get_project`` (read tracker fields) and
    ``update_project`` (write tracker fields).  These give agents a
    non-HTTP path to manage ProjectStore state without calling back into
    the local oompah server (which would deadlock the same-process
    request handler).
    """
    # Lazy imports: keep the SDK out of import paths that don't need it,
    # and avoid pulling api_agent's full surface (which imports _http_post
    # etc.) at module load time.
    try:
        from claude_agent_sdk import tool
    except ImportError as exc:
        raise ImportError(
            "claude-agent-sdk not installed. Claude ACP backend requires "
            "the Claude Agent SDK. Install with: "
            "uv pip install 'oompah[claude]'"
        ) from exc

    from oompah.api_agent import (
        _exec_read_file,
        _exec_write_file,
        _exec_edit_file,
        _exec_list_files,
        _exec_search_files,
        _exec_run_command,
    )

    workspace = Path(workspace_path)

    def _wrap_text(content: str) -> dict[str, Any]:
        """Package a plain-string tool result in the MCP content shape
        the SDK expects from @tool functions."""
        return {"content": [{"type": "text", "text": content}]}

    @tool(
        "read_file",
        "Read the contents of a file inside the workspace. Path is "
        "workspace-relative. Returns file contents or an error message.",
        {"path": str},
    )
    async def read_file(args: dict[str, Any]) -> dict[str, Any]:
        return _wrap_text(_exec_read_file(workspace, args))

    @tool(
        "write_file",
        "Write text content to a file inside the workspace. Creates "
        "parent directories. Overwrites existing files. Path is "
        "workspace-relative.",
        {"path": str, "content": str},
    )
    async def write_file(args: dict[str, Any]) -> dict[str, Any]:
        return _wrap_text(_exec_write_file(workspace, args))

    @tool(
        "edit_file",
        "Replace exactly one occurrence of `old_string` with "
        "`new_string` in `path`. More efficient than write_file for "
        "targeted changes. Errors if the old_string is missing or "
        "appears more than once.",
        {"path": str, "old_string": str, "new_string": str},
    )
    async def edit_file(args: dict[str, Any]) -> dict[str, Any]:
        return _wrap_text(_exec_edit_file(workspace, args))

    @tool(
        "list_files",
        "List the immediate entries of a directory in the workspace. "
        "Use path='.' for the workspace root.",
        {"path": str},
    )
    async def list_files(args: dict[str, Any]) -> dict[str, Any]:
        return _wrap_text(_exec_list_files(workspace, args))

    @tool(
        "search_files",
        "Grep-style search across the workspace. `pattern` is a Python "
        "regex. Optional `path` narrows the scope. Returns matching "
        "lines with file:line: prefix.",
        {"pattern": str, "path": str},
    )
    async def search_files(args: dict[str, Any]) -> dict[str, Any]:
        return _wrap_text(_exec_search_files(workspace, args))

    @tool(
        "run_command",
        "Run a shell command inside the workspace. Stays inside the "
        "workspace — `cd` to absolute paths outside is refused. "
        "Project-specific tracker environment overrides are applied "
        "when configured. Returns stdout, stderr, and exit code.",
        {"command": str},
    )
    async def run_command(args: dict[str, Any]) -> dict[str, Any]:
        return _wrap_text(
            _exec_run_command(
                workspace,
                args,
                timeout=run_command_timeout_s,
            )
        )

    @tool(
        "get_project",
        "Read the tracker configuration for the managed project this "
        "worktree belongs to. Returns JSON with id, name, tracker_kind, "
        "tracker_owner, tracker_repo, tracker_cutover_at, "
        "legacy_backlog_enabled, legacy_backlog_dispatch, "
        "github_project_node_id, and paused fields. "
        "Use this instead of calling http://127.0.0.1:8090 — HTTP "
        "self-calls from inside an oompah MCP tool deadlock the server. "
        "No parameters required.",
        {},
    )
    async def get_project(args: dict[str, Any]) -> dict[str, Any]:
        return _wrap_text(_exec_get_project(project_store, project_id))

    @tool(
        "update_project",
        "Update tracker configuration fields for the managed project. "
        "Pass 'fields_json' as a JSON-encoded object whose keys are a "
        "subset of: tracker_kind, tracker_owner, tracker_repo, "
        "github_project_node_id, legacy_backlog_enabled, "
        "legacy_backlog_dispatch, tracker_cutover_at, paused. "
        "Example: '{\"tracker_kind\": \"github_issues\", "
        "\"tracker_owner\": \"my-org\", \"tracker_repo\": \"my-repo\"}'. "
        "Use this instead of PATCH http://127.0.0.1:8090/api/v1/projects/<id> "
        "or editing .oompah/projects.json directly — both can deadlock or "
        "corrupt the running service.",
        {"fields_json": str},
    )
    async def update_project(args: dict[str, Any]) -> dict[str, Any]:
        return _wrap_text(
            _exec_update_project(
                project_store,
                project_id,
                args.get("fields_json", "{}"),
            )
        )

    return [
        read_file,
        write_file,
        edit_file,
        list_files,
        search_files,
        run_command,
        get_project,
        update_project,
    ]


# ----------------------------------------------------------------------
# Codex / OpenAI Agents SDK tool catalog (oompah-zlz_2-yiuy)
# ----------------------------------------------------------------------


def build_codex_tool_catalog(
    workspace_path: str,
    *,
    run_command_timeout_s: int = 60,
    project_store: Any = None,
    project_id: str | None = None,
) -> list[Any]:
    """Build the OpenAI-Agents-SDK-flavored tool list for a Codex session.

    Returns a list of decorator-wrapped functions (whatever
    ``agents.function_tool`` produces). Each wrapper routes through
    the same :func:`oompah.api_agent._exec_*` helpers used by the
    Claude backend so the safety rails (cd-out-of-worktree guard,
    tracker environment overrides, per-command timeouts) are identical between
    backends — that's the entire point of reusing this module.

    The SDK is imported lazily; callers that don't actually open a
    Codex session never pay the import cost. If the SDK is missing
    we raise ``ImportError`` with a clear install hint rather than
    silently returning ``[]``, because a missing SDK is an operator
    config error not a "no tools" condition.

    Mirrors :func:`build_tool_catalog` (the Claude-flavored builder)
    1:1 in name + behavior; only the surrounding decorator differs.

    When ``project_store`` and ``project_id`` are supplied, ``get_project``
    and ``update_project`` tools are added for non-HTTP ProjectStore access
    (see TASK-464.8).
    """
    # Lazy import: keeps the SDK out of import paths that don't need it.
    # The openai-agents PyPI package imports as ``agents``; we accept
    # the rename in case the package gets repackaged under a more
    # obvious top-level name (e.g. ``openai_agents``).
    try:
        import agents  # type: ignore
    except ImportError as exc:  # pragma: no cover — exercised only when missing
        try:
            import openai_agents as agents  # type: ignore
        except ImportError:
            raise ImportError(
                "openai-agents SDK not installed. Codex ACP backend "
                "requires the OpenAI Agents Python SDK. Install with: "
                "uv pip install 'oompah[codex]'"
            ) from exc

    function_tool = getattr(agents, "function_tool", None)
    if function_tool is None:
        raise ImportError(
            "openai-agents SDK is installed but does not expose "
            "'function_tool'. Codex ACP backend requires a "
            "session-shaped SDK with tool decoration support."
        )

    from oompah.api_agent import (
        _exec_read_file,
        _exec_write_file,
        _exec_edit_file,
        _exec_list_files,
        _exec_search_files,
        _exec_run_command,
    )

    workspace = Path(workspace_path)

    # Each @function_tool target is introspected by the SDK to build
    # a JSON Schema for the model — keep the signatures simple
    # (positional kwargs, scalar types) and the docstrings clear.

    @function_tool
    def read_file(path: str) -> str:
        """Read the contents of a file inside the workspace. Path is
        workspace-relative. Returns file contents or an error message."""
        return _exec_read_file(workspace, {"path": path})

    @function_tool
    def write_file(path: str, content: str) -> str:
        """Write text content to a file inside the workspace. Creates
        parent directories. Overwrites existing files. Path is
        workspace-relative."""
        return _exec_write_file(workspace, {"path": path, "content": content})

    @function_tool
    def edit_file(path: str, old_string: str, new_string: str) -> str:
        """Replace exactly one occurrence of ``old_string`` with
        ``new_string`` in ``path``. More efficient than write_file for
        targeted changes. Errors if ``old_string`` is missing or
        appears more than once."""
        return _exec_edit_file(
            workspace,
            {"path": path, "old_string": old_string, "new_string": new_string},
        )

    @function_tool
    def list_files(path: str) -> str:
        """List the immediate entries of a directory in the workspace.
        Use ``path='.'`` for the workspace root."""
        return _exec_list_files(workspace, {"path": path})

    @function_tool
    def search_files(pattern: str, path: str = ".") -> str:
        """Grep-style search across the workspace. ``pattern`` is a
        Python regex. Optional ``path`` narrows the scope. Returns
        matching lines with ``file:line:`` prefix."""
        return _exec_search_files(workspace, {"pattern": pattern, "path": path})

    @function_tool
    def run_command(command: str) -> str:
        """Run a shell command inside the workspace. Stays inside the
        workspace — ``cd`` to absolute paths outside is refused.
        Project-specific tracker environment overrides are applied when
        configured. Returns stdout, stderr, and exit code."""
        return _exec_run_command(
            workspace,
            {"command": command},
            timeout=run_command_timeout_s,
        )

    @function_tool
    def get_project() -> str:
        """Read the tracker configuration for the managed project this
        worktree belongs to. Returns JSON with id, name, tracker_kind,
        tracker_owner, tracker_repo, tracker_cutover_at,
        legacy_backlog_enabled, legacy_backlog_dispatch,
        github_project_node_id, and paused fields.
        Use this instead of calling http://127.0.0.1:8090 — HTTP
        self-calls from inside an oompah MCP tool deadlock the server."""
        return _exec_get_project(project_store, project_id)

    @function_tool
    def update_project(fields_json: str) -> str:
        """Update tracker configuration fields for the managed project.
        ``fields_json`` must be a JSON-encoded object whose keys are a
        subset of: tracker_kind, tracker_owner, tracker_repo,
        github_project_node_id, legacy_backlog_enabled,
        legacy_backlog_dispatch, tracker_cutover_at, paused.
        Use this instead of PATCH http://127.0.0.1:8090/api/v1/projects/<id>
        or editing .oompah/projects.json directly — both can deadlock or
        corrupt the running service."""
        return _exec_update_project(project_store, project_id, fields_json)

    return [
        read_file,
        write_file,
        edit_file,
        list_files,
        search_files,
        run_command,
        get_project,
        update_project,
    ]


# ----------------------------------------------------------------------
# OpenCode SDK tool catalog (oompah-zlz_2-p1ti)
# ----------------------------------------------------------------------


def build_opencode_tool_catalog(
    workspace_path: str,
    *,
    run_command_timeout_s: int = 60,
    project_store: Any = None,
    project_id: str | None = None,
) -> list[Any]:
    """Build the OpenCode-SDK-flavored tool list for an OpenCode session.

    Returns a list of ``@tool``-decorated async functions (OpenCode uses
    the same ``@tool`` surface as Claude, unlike Codex's
    ``@function_tool``). Each function routes through the same
    :func:`oompah.api_agent._exec_*` helpers so cd-guard, tracker
    per-command timeouts apply identically to the Claude and OpenCode backends.

    The SDK is imported lazily; callers that don't use OpenCode never
    pay the import cost. If the SDK is missing we raise
    ``ImportError`` with a clear install hint (NOT silently empty) —
    a missing SDK is an operator config error.

    When ``project_store`` and ``project_id`` are supplied, ``get_project``
    and ``update_project`` tools are added for non-HTTP ProjectStore access
    (see TASK-464.8).
    """
    # Lazy import to keep the SDK out of import paths that don't need it.
    try:
        import opencode  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "OpenCode SDK not installed. OpenCode ACP backend requires "
            "the OpenCode Python SDK. Install with: pip install opencode"
        ) from exc

    tool = getattr(opencode, "tool", None)
    if tool is None:
        raise ImportError(
            "OpenCode SDK is installed but does not expose the 'tool' "
            "decorator. The OpenCode backend requires an SDK version "
            "with tool decoration support."
        )

    from oompah.api_agent import (
        _exec_read_file,
        _exec_write_file,
        _exec_edit_file,
        _exec_list_files,
        _exec_search_files,
        _exec_run_command,
    )

    workspace = Path(workspace_path)

    def _wrap_text(content: str) -> dict[str, Any]:
        """Package a plain-string tool result in the MCP content shape
        the SDK expects from @tool functions."""
        return {"content": [{"type": "text", "text": content}]}

    @tool(
        "read_file",
        "Read the contents of a file inside the workspace. Path is "
        "workspace-relative. Returns file contents or an error message.",
        {"path": str},
    )
    async def read_file(args: dict[str, Any]) -> dict[str, Any]:
        return _wrap_text(_exec_read_file(workspace, args))

    @tool(
        "write_file",
        "Write text content to a file inside the workspace. Creates "
        "parent directories. Overwrites existing files. Path is "
        "workspace-relative.",
        {"path": str, "content": str},
    )
    async def write_file(args: dict[str, Any]) -> dict[str, Any]:
        return _wrap_text(_exec_write_file(workspace, args))

    @tool(
        "edit_file",
        "Replace exactly one occurrence of `old_string` with "
        "`new_string` in `path`. More efficient than write_file for "
        "targeted changes. Errors if the old_string is missing or "
        "appears more than once.",
        {"path": str, "old_string": str, "new_string": str},
    )
    async def edit_file(args: dict[str, Any]) -> dict[str, Any]:
        return _wrap_text(_exec_edit_file(workspace, args))

    @tool(
        "list_files",
        "List the immediate entries of a directory in the workspace. "
        "Use path='.' for the workspace root.",
        {"path": str},
    )
    async def list_files(args: dict[str, Any]) -> dict[str, Any]:
        return _wrap_text(_exec_list_files(workspace, args))

    @tool(
        "search_files",
        "Grep-style search across the workspace. `pattern` is a Python "
        "regex. Optional `path` narrows the scope. Returns matching "
        "lines with file:line: prefix.",
        {"pattern": str, "path": str},
    )
    async def search_files(args: dict[str, Any]) -> dict[str, Any]:
        return _wrap_text(_exec_search_files(workspace, args))

    @tool(
        "run_command",
        "Run a shell command inside the workspace. Stays inside the "
        "workspace — `cd` to absolute paths outside is refused. "
        "Project-specific tracker environment overrides are applied "
        "when configured. Returns stdout, stderr, and exit code.",
        {"command": str},
    )
    async def run_command(args: dict[str, Any]) -> dict[str, Any]:
        return _wrap_text(
            _exec_run_command(
                workspace,
                args,
                timeout=run_command_timeout_s,
            )
        )

    @tool(
        "get_project",
        "Read the tracker configuration for the managed project this "
        "worktree belongs to. Returns JSON with id, name, tracker_kind, "
        "tracker_owner, tracker_repo, tracker_cutover_at, "
        "legacy_backlog_enabled, legacy_backlog_dispatch, "
        "github_project_node_id, and paused fields. "
        "Use this instead of calling http://127.0.0.1:8090 — HTTP "
        "self-calls from inside an oompah MCP tool deadlock the server. "
        "No parameters required.",
        {},
    )
    async def get_project(args: dict[str, Any]) -> dict[str, Any]:
        return _wrap_text(_exec_get_project(project_store, project_id))

    @tool(
        "update_project",
        "Update tracker configuration fields for the managed project. "
        "Pass 'fields_json' as a JSON-encoded object whose keys are a "
        "subset of: tracker_kind, tracker_owner, tracker_repo, "
        "github_project_node_id, legacy_backlog_enabled, "
        "legacy_backlog_dispatch, tracker_cutover_at, paused. "
        "Example: '{\"tracker_kind\": \"github_issues\", "
        "\"tracker_owner\": \"my-org\", \"tracker_repo\": \"my-repo\"}'. "
        "Use this instead of PATCH http://127.0.0.1:8090/api/v1/projects/<id> "
        "or editing .oompah/projects.json directly — both can deadlock or "
        "corrupt the running service.",
        {"fields_json": str},
    )
    async def update_project(args: dict[str, Any]) -> dict[str, Any]:
        return _wrap_text(
            _exec_update_project(
                project_store,
                project_id,
                args.get("fields_json", "{}"),
            )
        )

    return [
        read_file,
        write_file,
        edit_file,
        list_files,
        search_files,
        run_command,
        get_project,
        update_project,
    ]
