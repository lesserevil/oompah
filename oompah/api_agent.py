"""API-based agent runner: calls OpenAI-compatible chat completions endpoints.

Drop-in alternative to AgentSession (agent.py) that talks directly to any
OpenAI-compatible API instead of launching a Claude CLI subprocess.
Uses only stdlib -- no external HTTP or SDK dependencies.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import ssl
import subprocess
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class AgentActivity:
    """One activity entry in the agent's log."""
    turn: int
    kind: str  # "thinking" | "tool_call" | "tool_result" | "message" | "error"
    summary: str
    detail: str = ""
    timestamp: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "turn": self.turn,
            "kind": self.kind,
            "summary": self.summary,
            "detail": self.detail[:2000],
            "timestamp": self.timestamp,
        }


@dataclass
class ApiAgentResult:
    status: str  # "succeeded" | "failed" | "max_turns" | "stalled"
    input_tokens: int
    output_tokens: int
    total_tokens: int
    turns: int
    last_message: str
    error: str | None = None
    activity: list[AgentActivity] = field(default_factory=list)


# Tools that indicate the agent is making progress (not just reading/exploring)
_PRODUCTIVE_TOOLS = {"write_file", "edit_file", "run_command"}


# ---------------------------------------------------------------------------
# Tool definitions (OpenAI function-calling schema)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file at the given path (relative to workspace root).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to workspace root.",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file at the given path (relative to workspace root). Creates parent directories as needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to workspace root.",
                    },
                    "content": {
                        "type": "string",
                        "description": "The full content to write to the file.",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run a shell command in the workspace directory. Returns stdout, stderr, and exit code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute.",
                    }
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories at the given path (relative to workspace root).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path relative to workspace root. Use '.' for the workspace root.",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": (
                "Edit a file by replacing an exact string match with new content. "
                "More efficient than write_file for targeted changes — only send the "
                "changed parts, not the entire file. The old_string must match exactly "
                "one location in the file (including whitespace and indentation). "
                "Use replace_all=true to replace every occurrence."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to workspace root.",
                    },
                    "old_string": {
                        "type": "string",
                        "description": "The exact text to find in the file. Must match uniquely unless replace_all is true.",
                    },
                    "new_string": {
                        "type": "string",
                        "description": "The replacement text.",
                    },
                    "replace_all": {
                        "type": "boolean",
                        "description": "If true, replace all occurrences. Default false.",
                    },
                },
                "required": ["path", "old_string", "new_string"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": (
                "Search for a pattern across files in the workspace. "
                "Returns matching lines with file paths and line numbers. "
                "Useful for finding where functions, variables, or strings are used."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Search pattern (plain text or regex).",
                    },
                    "path": {
                        "type": "string",
                        "description": "Directory or file to search in (relative to workspace root). Default '.'.",
                    },
                    "include": {
                        "type": "string",
                        "description": "Glob pattern to filter files, e.g. '*.go' or '*.py'.",
                    },
                },
                "required": ["pattern"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Path safety
# ---------------------------------------------------------------------------

def _safe_resolve(workspace: Path, relative: str) -> Path:
    """Resolve *relative* inside *workspace*, raising ValueError on traversal."""
    resolved = (workspace / relative).resolve()
    workspace_resolved = workspace.resolve()
    if not (resolved == workspace_resolved or str(resolved).startswith(str(workspace_resolved) + os.sep)):
        raise ValueError(f"Path traversal blocked: {relative!r} resolves outside workspace")
    return resolved


# ---------------------------------------------------------------------------
# Tool execution helpers
# ---------------------------------------------------------------------------

def _exec_read_file(workspace: Path, args: dict[str, Any]) -> str:
    path = _safe_resolve(workspace, args["path"])
    if not path.is_file():
        return f"Error: file not found: {args['path']}"
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"Error reading file: {exc}"


def _exec_write_file(workspace: Path, args: dict[str, Any]) -> str:
    path = _safe_resolve(workspace, args["path"])
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(args["content"], encoding="utf-8")
        return f"OK: wrote {len(args['content'])} bytes to {args['path']}"
    except Exception as exc:
        return f"Error writing file: {exc}"


def _exec_list_files(workspace: Path, args: dict[str, Any]) -> str:
    path = _safe_resolve(workspace, args.get("path", "."))
    if not path.is_dir():
        return f"Error: not a directory: {args.get('path', '.')}"
    try:
        entries = sorted(p.name + ("/" if p.is_dir() else "") for p in path.iterdir())
        return "\n".join(entries) if entries else "(empty directory)"
    except Exception as exc:
        return f"Error listing directory: {exc}"


def _exec_edit_file(workspace: Path, args: dict[str, Any]) -> str:
    path = _safe_resolve(workspace, args["path"])
    if not path.is_file():
        return f"Error: file not found: {args['path']}"
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as exc:
        return f"Error reading file: {exc}"

    old_string = args["old_string"]
    new_string = args["new_string"]
    replace_all = args.get("replace_all", False)

    if not old_string:
        return "Error: old_string must not be empty"
    if old_string == new_string:
        return "Error: old_string and new_string are identical"

    count = content.count(old_string)
    if count == 0:
        # Show a snippet of the file to help the model find the right text
        lines = content.splitlines()
        preview = "\n".join(lines[:30])
        return (
            f"Error: old_string not found in {args['path']}. "
            f"File has {len(lines)} lines. First 30 lines:\n{preview}"
        )
    if count > 1 and not replace_all:
        return (
            f"Error: old_string matches {count} locations in {args['path']}. "
            f"Provide more context to make it unique, or set replace_all=true."
        )

    if replace_all:
        new_content = content.replace(old_string, new_string)
    else:
        new_content = content.replace(old_string, new_string, 1)

    try:
        path.write_text(new_content, encoding="utf-8")
        replacements = count if replace_all else 1
        return f"OK: replaced {replacements} occurrence(s) in {args['path']}"
    except Exception as exc:
        return f"Error writing file: {exc}"


def _exec_search_files(workspace: Path, args: dict[str, Any]) -> str:
    search_path = _safe_resolve(workspace, args.get("path", "."))
    pattern = args["pattern"]
    include = args.get("include", "")

    cmd = ["grep", "-rn", "--include", include, pattern, str(search_path)] if include else \
          ["grep", "-rn", pattern, str(search_path)]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=15,
            cwd=str(workspace),
        )
        output = result.stdout
        if not output:
            return f"No matches found for {pattern!r}"
        # Make paths relative to workspace
        ws_prefix = str(workspace.resolve()) + os.sep
        lines = output.splitlines()
        rel_lines = [l.replace(ws_prefix, "") for l in lines]
        if len(rel_lines) > 100:
            rel_lines = rel_lines[:100]
            rel_lines.append(f"... ({len(lines) - 100} more matches)")
        return "\n".join(rel_lines)
    except subprocess.TimeoutExpired:
        return "Error: search timed out"
    except Exception as exc:
        return f"Error searching: {exc}"


def _exec_run_command(workspace: Path, args: dict[str, Any], timeout: int = 60) -> str:
    command = args["command"]
    try:
        result = subprocess.run(
            ["bash", "-lc", command],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        parts: list[str] = []
        if result.stdout:
            parts.append(f"stdout:\n{result.stdout}")
        if result.stderr:
            parts.append(f"stderr:\n{result.stderr}")
        parts.append(f"exit_code: {result.returncode}")
        return "\n".join(parts)
    except subprocess.TimeoutExpired:
        return f"Error: command timed out after {timeout}s"
    except Exception as exc:
        return f"Error running command: {exc}"


_TOOL_DISPATCH: dict[str, Any] = {
    "read_file": _exec_read_file,
    "write_file": _exec_write_file,
    "edit_file": _exec_edit_file,
    "search_files": _exec_search_files,
    "list_files": _exec_list_files,
    "run_command": _exec_run_command,
}


_TOOL_REQUIRED_ARGS: dict[str, list[str]] = {
    "read_file": ["path"],
    "write_file": ["path", "content"],
    "edit_file": ["path", "old_string", "new_string"],
    "search_files": ["pattern"],
    "run_command": ["command"],
    "list_files": [],
}


def _execute_tool(workspace: Path, name: str, args: dict[str, Any], cmd_timeout: int = 60) -> str:
    """Execute a tool call and return its string result."""
    handler = _TOOL_DISPATCH.get(name)
    if handler is None:
        return f"Error: unknown tool {name!r}. Available tools: {', '.join(_TOOL_DISPATCH)}"

    # Validate required arguments upfront with clear error messages
    required = _TOOL_REQUIRED_ARGS.get(name, [])
    missing = [arg for arg in required if arg not in args]
    if missing:
        return (
            f"Error: {name} requires the following arguments: {', '.join(required)}. "
            f"Missing: {', '.join(missing)}. "
            f"Received: {', '.join(args.keys()) if args else '(none)'}"
        )

    try:
        if name == "run_command":
            return handler(workspace, args, timeout=cmd_timeout)
        return handler(workspace, args)
    except ValueError as exc:
        # path traversal
        return str(exc)
    except Exception as exc:
        return f"Error executing {name}: {exc}"


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _build_ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    return ctx


def _http_post(url: str, headers: dict[str, str], body: bytes, ssl_ctx: ssl.SSLContext) -> dict[str, Any]:
    """Blocking HTTP POST that returns parsed JSON. Raises on HTTP/network errors."""
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=300) as resp:
            data = resp.read()
            return json.loads(data)
    except urllib.error.HTTPError as exc:
        error_body = ""
        try:
            error_body = exc.read().decode("utf-8", errors="replace")[:2000]
        except Exception:
            pass
        raise RuntimeError(
            f"HTTP {exc.code} from {url}: {error_body}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"URL error for {url}: {exc.reason}") from exc


# ---------------------------------------------------------------------------
# ApiAgentSession
# ---------------------------------------------------------------------------

class ApiAgentSession:
    """Agent session that calls an OpenAI-compatible chat completions API."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        workspace_path: str,
        max_turns: int = 200,
        stall_turns: int = 5,
        system_prompt: str = "",
        command_timeout: int = 60,
    ):
        # Strip trailing slash for clean URL joining
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self.model = model
        self.workspace = Path(workspace_path).resolve()
        self.max_turns = max_turns
        self.stall_turns = stall_turns
        self.system_prompt = system_prompt
        self.command_timeout = command_timeout

        self._ssl_ctx = _build_ssl_context()
        self._url = f"{self.base_url}/chat/completions"

    # -- public interface ---------------------------------------------------

    async def run_task(
        self,
        prompt: str,
        on_activity: Callable[[AgentActivity], None] | None = None,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> ApiAgentResult:
        """Run the agent on a task prompt. Returns result with token counts."""
        messages: list[dict[str, Any]] = []
        activity: list[AgentActivity] = []

        def _emit(turn: int, kind: str, summary: str, detail: str = "") -> None:
            entry = AgentActivity(
                turn=turn, kind=kind, summary=summary,
                detail=detail, timestamp=time.time(),
            )
            activity.append(entry)
            if on_activity:
                on_activity(entry)

        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})

        messages.append({"role": "user", "content": prompt})

        total_input = 0
        total_output = 0
        total_tokens = 0
        last_message = ""
        turns = 0
        turns_since_productive = 0  # stall detection
        consecutive_errors = 0  # track repeated tool errors
        last_error_signature = ""  # detect identical repeated errors
        _MAX_CONSECUTIVE_ERRORS = 3  # bail after this many identical errors

        try:
            for turn in range(1, self.max_turns + 1):
                turns = turn
                # Capture the last user/tool messages being sent this turn
                recent_msgs = []
                for m in reversed(messages):
                    if m.get("role") in ("user", "tool"):
                        recent_msgs.insert(0, m)
                    else:
                        break
                prompt_preview = "\n".join(
                    f"[{m.get('role')}] {(m.get('content') or '')[:500]}"
                    for m in recent_msgs
                ) if recent_msgs else "(system prompt + history)"
                _emit(turn, "thinking", f"Turn {turn}: calling {self.model}...", prompt_preview)

                response = await self._call_api(messages)

                # Accumulate usage
                usage = response.get("usage", {})
                total_input += usage.get("prompt_tokens", 0)
                total_output += usage.get("completion_tokens", 0)
                total_tokens += usage.get("total_tokens", 0)

                choices = response.get("choices", [])
                if not choices:
                    _emit(turn, "error", "Empty choices in API response")
                    return ApiAgentResult(
                        status="failed",
                        input_tokens=total_input,
                        output_tokens=total_output,
                        total_tokens=total_tokens,
                        turns=turns,
                        last_message=last_message,
                        error="Empty choices in API response",
                        activity=activity,
                    )

                finish_reason = choices[0].get("finish_reason", "")
                assistant_msg = choices[0].get("message", {})

                # If the response was truncated due to max_tokens, warn and
                # strip any incomplete tool calls to avoid missing-arg errors.
                if finish_reason == "length":
                    _emit(turn, "warning", "Response truncated (max_tokens reached)")
                    tool_calls_raw = assistant_msg.get("tool_calls") or []
                    valid_tcs = []
                    for tc in tool_calls_raw:
                        fn = tc.get("function", {})
                        try:
                            json.loads(fn.get("arguments", "{}"))
                            valid_tcs.append(tc)
                        except json.JSONDecodeError:
                            _emit(turn, "warning",
                                  f"Dropping truncated tool call: {fn.get('name', '?')}")
                    assistant_msg["tool_calls"] = valid_tcs or None

                messages.append(assistant_msg)

                content = assistant_msg.get("content") or ""
                if content:
                    last_message = content
                    _emit(turn, "message", content[:200], content)

                tool_calls = assistant_msg.get("tool_calls")
                if not tool_calls:
                    _emit(turn, "message", "Agent finished (no more tool calls)")
                    return ApiAgentResult(
                        status="succeeded",
                        input_tokens=total_input,
                        output_tokens=total_output,
                        total_tokens=total_tokens,
                        turns=turns,
                        last_message=last_message,
                        activity=activity,
                    )

                turn_had_productive = False
                for tc in tool_calls:
                    fn = tc.get("function", {})
                    tool_name = fn.get("name", "")
                    raw_args = fn.get("arguments", "{}")
                    try:
                        tool_args = json.loads(raw_args)
                    except json.JSONDecodeError:
                        tool_args = {}

                    args_summary = ", ".join(
                        f"{k}={v!r}" for k, v in tool_args.items()
                    )[:150]
                    _emit(turn, "tool_call", f"{tool_name}({args_summary})")

                    # If JSON parsing failed, give the model a clear error
                    if not tool_args and raw_args not in ("{}", ""):
                        result_str = (
                            f"Error: malformed JSON in tool arguments for {tool_name}. "
                            f"Received: {raw_args[:200]}. "
                            f"Please provide valid JSON with the required arguments."
                        )
                    else:
                        result_str = await asyncio.to_thread(
                            _execute_tool, self.workspace, tool_name, tool_args, self.command_timeout
                        )

                    tool_failed = result_str.startswith("Error")
                    _emit(turn, "tool_result", f"{tool_name} → {result_str[:150]}", result_str)

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", ""),
                        "content": result_str,
                    })

                    if tool_name in _PRODUCTIVE_TOOLS and not tool_failed:
                        turn_had_productive = True

                    # Track repeated identical errors
                    if tool_failed:
                        error_sig = f"{tool_name}:{result_str[:200]}"
                        if error_sig == last_error_signature:
                            consecutive_errors += 1
                        else:
                            consecutive_errors = 1
                            last_error_signature = error_sig
                    else:
                        consecutive_errors = 0
                        last_error_signature = ""

                # Repeated error detection — stop wasting turns on the same error
                if consecutive_errors >= _MAX_CONSECUTIVE_ERRORS:
                    error_msg = (
                        f"Stalled after {consecutive_errors} identical tool errors: "
                        f"{last_error_signature[:150]}"
                    )
                    _emit(turn, "message", error_msg)
                    return ApiAgentResult(
                        status="stalled",
                        input_tokens=total_input,
                        output_tokens=total_output,
                        total_tokens=total_tokens,
                        turns=turns,
                        last_message=error_msg,
                        error=error_msg,
                        activity=activity,
                    )

                # Stall detection
                if turn_had_productive:
                    turns_since_productive = 0
                else:
                    turns_since_productive += 1

                # Check if the task was cancelled (e.g. issue closed externally)
                if is_cancelled and await asyncio.to_thread(is_cancelled):
                    _emit(turn, "message", "Task cancelled (issue no longer active)")
                    return ApiAgentResult(
                        status="succeeded",
                        input_tokens=total_input,
                        output_tokens=total_output,
                        total_tokens=total_tokens,
                        turns=turns,
                        last_message="Task cancelled",
                        activity=activity,
                    )

                if turns_since_productive >= self.stall_turns:
                    _emit(turn, "message",
                          f"Agent stalled: {turns_since_productive} turns with no writes or commands")
                    return ApiAgentResult(
                        status="stalled",
                        input_tokens=total_input,
                        output_tokens=total_output,
                        total_tokens=total_tokens,
                        turns=turns,
                        last_message=last_message,
                        error=f"Stalled after {turns_since_productive} turns without productive action",
                        activity=activity,
                    )

            _emit(turns, "message", f"Reached max turns ({self.max_turns})")
            return ApiAgentResult(
                status="max_turns",
                input_tokens=total_input,
                output_tokens=total_output,
                total_tokens=total_tokens,
                turns=turns,
                last_message=last_message,
                activity=activity,
            )

        except Exception as exc:
            _emit(turns, "error", str(exc))
            logger.error("ApiAgentSession.run_task failed: %s", exc)
            return ApiAgentResult(
                status="failed",
                input_tokens=total_input,
                output_tokens=total_output,
                total_tokens=total_tokens,
                turns=turns,
                last_message=last_message,
                error=str(exc),
                activity=activity,
            )

    # -- private helpers ----------------------------------------------------

    async def _call_api(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        """Make one chat completions call (blocking HTTP wrapped in to_thread)."""
        payload = {
            "model": self.model,
            "messages": messages,
            "tools": TOOL_DEFINITIONS,
            "tool_choice": "auto",
            "max_tokens": 16384,
        }
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
            "User-Agent": "oompah/0.1",
        }

        return await asyncio.to_thread(
            _http_post, self._url, headers, body, self._ssl_ctx
        )
