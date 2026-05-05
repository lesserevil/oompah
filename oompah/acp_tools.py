"""Tool catalog bridging for ACP-mode agents.

The Claude Agent SDK takes an in-process MCP server with @tool-decorated
functions in ``ClaudeAgentOptions.mcp_servers``. We declare oompah's
existing tool catalog (read_file / write_file / edit_file / list_files /
search_files / run_command) here, routing each one through the same
``_exec_*`` implementations the api_agent path already uses.

Reusing those implementations is the whole point — they carry oompah's
safety rails (cd-out-of-worktree guard, BEADS_DIR routing, per-command
timeouts) that claude's native tools don't know about. See
``docs/acp-agent.md`` Q2 (locked decision: tool bridging via option B,
oompah's catalog wins).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def build_tool_catalog(
    workspace_path: str,
    *,
    beads_dir: str | None = None,
    run_command_timeout_s: int = 60,
) -> list[Any]:
    """Build the SDK-flavored tool list for one ACP session.

    Returns a list of ``SdkMcpTool`` instances (the @tool decorator's
    output), ready to be passed into
    :func:`claude_agent_sdk.create_sdk_mcp_server`.

    ``beads_dir`` is forwarded into ``run_command`` as the
    ``BEADS_DIR`` env override so that any ``bd`` calls the agent
    issues land in the project's main beads DB, not a per-worktree
    forked dolt. Mirrors the api_agent path.
    """
    # Lazy imports: keep the SDK out of import paths that don't need it,
    # and avoid pulling api_agent's full surface (which imports _http_post
    # etc.) at module load time.
    from claude_agent_sdk import tool

    from oompah.api_agent import (
        _exec_read_file,
        _exec_write_file,
        _exec_edit_file,
        _exec_list_files,
        _exec_search_files,
        _exec_run_command,
    )

    workspace = Path(workspace_path)
    env_overrides: dict[str, str] = {}
    if beads_dir:
        env_overrides["BEADS_DIR"] = beads_dir

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
        "workspace — `cd` to absolute paths outside is refused. `bd` "
        "commands automatically route to the project's main beads "
        "database via BEADS_DIR. Returns stdout, stderr, and exit code.",
        {"command": str},
    )
    async def run_command(args: dict[str, Any]) -> dict[str, Any]:
        return _wrap_text(
            _exec_run_command(
                workspace,
                args,
                timeout=run_command_timeout_s,
                env_overrides=env_overrides or None,
            )
        )

    return [
        read_file,
        write_file,
        edit_file,
        list_files,
        search_files,
        run_command,
    ]
