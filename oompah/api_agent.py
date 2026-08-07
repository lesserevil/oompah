"""API-based agent runner: calls OpenAI-compatible chat completions endpoints.

Drop-in alternative to AgentSession (agent.py) that talks directly to any
OpenAI-compatible API instead of launching a Claude CLI subprocess.
Uses only stdlib -- no external HTTP or SDK dependencies.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import math
import os
import re
import signal
import secrets
import ssl
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from oompah.prompt import RenderedPrompt
from oompah.client_auth import agent_environment
from oompah.authority_boundary import AgentActionPolicy, check_shell_command
from oompah.git_command_validation import validate_git_command_is_noninteractive
from oompah.git_noninteractive import NONINTERACTIVE_GIT_ENV
from oompah.secrets import redact_sensitive_data, register_secret
from oompah.auditor import (
    AUDITOR_ALLOWED_TOOLS,
    AUDITOR_RESULT_TOOL_NAME,
    AUDITOR_RESULT_TOOL_SCHEMA,
    check_auditor_session_target,
    submit_auditor_result,
)
from oompah.provider_health import openai_chat_completions_url
from oompah.validation_resource_lease import (
    ValidationLeaseCancelled,
    ValidationLeaseError,
    ValidationLeaseOwner,
    ValidationResourceLease,
    is_heavyweight_validation_command,
    managed_agent_validation_owner,
)

logger = logging.getLogger(__name__)


class RetryableError(Exception):
    """Base for transient errors that ``_call_api`` should retry in-session.

    Distinguishing these from permanent failures (4xx other than 429,
    malformed payloads, etc.) lets us recover from a flaky LLM server
    without tearing down the whole worker — which would otherwise force
    the orchestrator's heavier-weight dispatch retry that rebuilds the
    full conversation from scratch.
    """


class RateLimitError(RetryableError):
    """Raised when the API returns 429 or 529 (overloaded). Honors
    Retry-After when the server provides it; otherwise the caller picks
    a backoff."""

    def __init__(self, message: str, retry_after: float = 0):
        super().__init__(message)
        self.retry_after = retry_after  # seconds; 0 means not specified


class TransientServerError(RetryableError):
    """Raised for 5xx responses, connection refused, timeouts, and other
    network-level errors that are typically resolved by waiting a few
    seconds and trying again. The wrapped HTTP code (when present) is
    available as ``status_code`` for diagnostics."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


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
    # Per-event usage snapshot for the dashboard's sticky activity-
    # summary header. Shape: {input_tokens, output_tokens, total_tokens,
    # cost_usd?}. Cumulative (running totals at the time of the event)
    # so the header can scan back-to-front for the latest non-null value.
    usage: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        out = {
            "turn": self.turn,
            "kind": self.kind,
            "summary": self.summary,
            "detail": self.detail[:2000],
            "timestamp": self.timestamp,
        }
        if self.usage is not None:
            out["usage"] = self.usage
        return out


@dataclass
class ApiAgentResult:
    status: str  # "succeeded" | "failed" | "max_turns" | "stalled" | "ask_question"
    input_tokens: int
    output_tokens: int
    total_tokens: int
    turns: int
    last_message: str
    error: str | None = None
    question: str | None = None  # set when status == "ask_question"
    activity: list[AgentActivity] = field(default_factory=list)


# Tools that indicate the agent is making progress (not just reading/exploring)
_PRODUCTIVE_TOOLS = {"write_file", "edit_file", "run_command"}

_DEFAULT_RUN_COMMAND_TIMEOUT_SECONDS = 720
_RUN_COMMAND_TIMEOUT_ENV = "OOMPAH_AGENT_COMMAND_TIMEOUT_SECONDS"

# Keep tool results below provider-side spill thresholds.  In particular, the
# Claude transport persists oversized MCP results under its own private state
# directory and tells the model to read that path.  A strict read-only auditor
# cannot (and must not) cross that authority boundary.  Chunk at Oompah's tool
# boundary instead so every continuation remains an approved workspace read.
_READ_FILE_DEFAULT_CHARS = 32_000
_TOOL_RESULT_MAX_CHARS = 64_000
_COMMAND_OUTPUT_PAGE_CHARS = 32_000
_COMMAND_OUTPUT_MAX_RECORDS = 32

_AUDITOR_FINALIZATION_PROMPT = (
    "This is the reserved audit-finalization turn. Do not continue inspecting "
    "or answer with prose. Call submit_audit_result exactly once with the "
    "structured verdict; only that coordinator submission is authoritative."
)


def _audit_result_was_accepted(result: str) -> bool:
    """Return true only for the coordinator's structured acceptance envelope."""

    if not isinstance(result, str) or result.startswith("Error"):
        return False
    try:
        payload = json.loads(result)
    except (TypeError, ValueError):
        return False
    return isinstance(payload, dict) and payload.get("accepted") is True


class CommandOutputStore:
    """Keep oversized command results behind an opaque, session-local tool.

    Provider transports are allowed to persist large MCP results in their own
    private state directories.  That is not an authority boundary an auditor
    can cross, so oversized command output must never be handed to the
    provider in the first place.  This store keeps the result in Oompah
    memory and exposes only bounded pages through the approved tool catalog.
    The random result id is intentionally not a filesystem path.
    """

    def __init__(self, *, max_records: int = _COMMAND_OUTPUT_MAX_RECORDS) -> None:
        self._max_records = max(1, int(max_records))
        self._records: dict[str, str] = {}
        self._order: list[str] = []
        self._lock = threading.Lock()

    def save(self, output: str) -> str:
        result_id = f"cmd-{secrets.token_urlsafe(18)}"
        with self._lock:
            self._records[result_id] = output
            self._order.append(result_id)
            while len(self._order) > self._max_records:
                expired = self._order.pop(0)
                self._records.pop(expired, None)
        return result_id

    def _get(self, result_id: Any) -> str | None:
        if not isinstance(result_id, str) or not result_id.strip():
            return None
        with self._lock:
            return self._records.get(result_id)

    @staticmethod
    def _bounded_limit(raw: Any) -> int | None:
        if isinstance(raw, bool) or not isinstance(raw, int) or raw < 1:
            return None
        return min(raw, _COMMAND_OUTPUT_PAGE_CHARS)

    def read(self, args: dict[str, Any]) -> str:
        result_id = args.get("result_id")
        output = self._get(result_id)
        if output is None:
            return "Error: command output result is unknown or expired"

        offset = args.get("offset", 0)
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            return "Error: offset must be a non-negative integer"
        limit = self._bounded_limit(args.get("limit", _COMMAND_OUTPUT_PAGE_CHARS))
        if limit is None:
            return "Error: limit must be a positive integer"

        pattern = args.get("pattern")
        if pattern is not None and str(pattern):
            try:
                matcher = re.compile(str(pattern))
            except re.error as exc:
                return f"Error: invalid search pattern: {exc}"
            matches: list[str] = []
            for match in matcher.finditer(output):
                start = max(0, match.start() - 120)
                end = min(len(output), match.end() + 120)
                matches.append(f"match at {match.start()}:\n{output[start:end]}")
                if len("\n\n".join(matches)) >= limit or len(matches) >= 100:
                    break
            if not matches:
                return f"No matches found for {pattern!r} in command output"
            result = "\n\n".join(matches)
            if len(result) > limit:
                result = result[:limit]
                result += "\n[search results truncated; narrow the pattern to continue]"
            return result

        if offset > len(output):
            return f"Error: offset {offset} is past end of command output ({len(output)} characters)"
        end = min(len(output), offset + limit)
        header = (
            f"[oompah read_command_output: result_id={result_id!r} "
            f"characters {offset}:{end} of {len(output)}]\n"
        )
        trailer = (
            "\n[truncated by Oompah before provider transport; continue only "
            "through the approved tool with "
            f"read_command_output(result_id={result_id!r}, offset={end}, limit={limit})]"
            if end < len(output)
            else "\n[end of command output]"
        )
        return f"{header}{output[offset:end]}{trailer}"


def _resolve_run_command_timeout(raw: str | None = None) -> int:
    value = os.environ.get(_RUN_COMMAND_TIMEOUT_ENV) if raw is None else raw
    if value is None or not value.strip():
        return _DEFAULT_RUN_COMMAND_TIMEOUT_SECONDS
    try:
        parsed = float(value)
    except ValueError:
        return _DEFAULT_RUN_COMMAND_TIMEOUT_SECONDS
    if not math.isfinite(parsed) or parsed <= 0:
        return _DEFAULT_RUN_COMMAND_TIMEOUT_SECONDS
    return max(1, int(math.ceil(parsed)))


# ---------------------------------------------------------------------------
# Tool definitions (OpenAI function-calling schema)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read a bounded portion of a file at the given path (relative to "
                "workspace root). Prefer this for focused inspection."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to workspace root.",
                    },
                    "offset": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "Optional zero-based character offset for chunked reads.",
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": _TOOL_RESULT_MAX_CHARS,
                        "description": "Optional maximum characters to return. Defaults to 32000.",
                    },
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
            "description": (
                "Run one read-only inspection or configured test command in the "
                "workspace. Use search_files for searches and separate calls "
                "instead of shell pipelines; unsupported read-only syntax returns "
                "a recoverable validation response. Returns stdout, stderr, and "
                "exit code."
            ),
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
            "name": "read_command_output",
            "description": (
                "Read or search a bounded page of oversized output from a prior "
                "run_command call. Use the opaque result_id returned by run_command; "
                "never use a provider path, grep, tail, or a shell pipeline."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "result_id": {
                        "type": "string",
                        "description": "Opaque result id returned by run_command.",
                    },
                    "offset": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "Zero-based character offset for the next page.",
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": _COMMAND_OUTPUT_PAGE_CHARS,
                        "description": "Maximum characters to return; defaults to 32000.",
                    },
                    "pattern": {
                        "type": "string",
                        "description": "Optional regular expression to search the saved output.",
                    },
                },
                "required": ["result_id"],
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
                "Search across the workspace with a Python regular expression. "
                "Optional `path` and `include` narrow the scope and results are bounded. "
                "Set `context` for surrounding source lines. "
                "Use this instead of grep pipelines for auditor searches. "
                "Returns workspace-relative matching lines with file:line: prefix."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Python regular expression applied to each line.",
                    },
                    "path": {
                        "type": "string",
                        "description": "Workspace-relative directory or file to search in. Default '.'.",
                        "default": ".",
                    },
                    "include": {
                        "type": "string",
                        "description": "Optional workspace-relative file glob.",
                        "default": "",
                    },
                    "context": {
                        "type": "integer",
                        "description": "Surrounding lines before and after each match. Default 0.",
                        "minimum": 0,
                        "maximum": 20,
                        "default": 0,
                    },
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask_question",
            "description": (
                "Ask a question to the project maintainer when you are blocked and "
                "cannot proceed without human input. The question will be posted as a "
                "comment on the issue. The agent session will then STOP and the issue "
                "will be held until a human answers.\n\n"
                "STRICT RULES — violating these wastes human time and blocks progress:\n"
                "- NEVER ask about HOW to implement something — figure it out by reading code\n"
                "- NEVER restate the issue description as a question\n"
                "- NEVER ask for confirmation of your plan — just execute it\n"
                "- NEVER ask 'how should I proceed' or 'what should I prioritize'\n"
                "- ONLY ask when the issue is genuinely ambiguous and multiple valid "
                "interpretations exist that would lead to fundamentally different implementations\n"
                "- Examples of valid questions: 'The issue says remove feature X, but feature Y "
                "depends on it — should I remove both or keep Y working?'\n"
                "- Examples of INVALID questions: 'How do I fix this bug?', 'Should I prioritize X?', "
                "'What approach should I take?'"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The question to ask the project maintainer.",
                    },
                },
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "attach_image",
            "description": (
                "Attach an image to the current issue. Use this when you have "
                "produced a diagram, annotated screenshot, or generated mock that "
                "should travel with the issue. The image is written into the "
                "issue's outputs/ directory, committed alongside your code "
                "changes, and recorded in the issue's attachment metadata. Only "
                "available when the active focus has allow_image_output=True and "
                "the resolved model has the image capability."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "issue_identifier": {
                        "type": "string",
                        "description": "The identifier of the current issue (e.g. 'oompah-9k1').",
                    },
                    "filename": {
                        "type": "string",
                        "description": "Original file name (extension matters; png/jpg/webp/gif/svg/pdf).",
                    },
                    "content_base64": {
                        "type": "string",
                        "description": "Base64-encoded image bytes.",
                    },
                    "turn": {
                        "type": "integer",
                        "description": "Optional turn number; included in the canonical filename when provided.",
                    },
                    "caption": {
                        "type": "string",
                        "description": "Optional caption — recorded in the issue's attachment metadata.",
                    },
                },
                "required": ["issue_identifier", "filename", "content_base64"],
            },
        },
    },
    AUDITOR_RESULT_TOOL_SCHEMA,
]


# ---------------------------------------------------------------------------
# Path safety
# ---------------------------------------------------------------------------


def _safe_resolve(workspace: Path, relative: str) -> Path:
    """Resolve *relative* inside *workspace*, raising ValueError on traversal."""
    resolved = (workspace / relative).resolve()
    workspace_resolved = workspace.resolve()
    if not (
        resolved == workspace_resolved
        or str(resolved).startswith(str(workspace_resolved) + os.sep)
    ):
        raise ValueError(
            f"Path traversal blocked: {relative!r} resolves outside workspace"
        )
    return resolved


# ---------------------------------------------------------------------------
# Tool execution helpers
# ---------------------------------------------------------------------------


def _exec_read_file(workspace: Path, args: dict[str, Any]) -> str:
    path = _safe_resolve(workspace, args["path"])
    if not path.is_file():
        return f"Error: file not found: {args['path']}"
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"Error reading file: {exc}"

    offset = args.get("offset", 0)
    limit = args.get("limit", _READ_FILE_DEFAULT_CHARS)
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        return "Error: offset must be a non-negative integer"
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        return "Error: limit must be a positive integer"
    # Fail safe even when a backend or model bypasses the advertised schema.
    limit = min(limit, _TOOL_RESULT_MAX_CHARS)
    total = len(content)
    if offset > total:
        return f"Error: offset {offset} is past end of file ({total} characters)"

    end = min(total, offset + limit)
    chunk = content[offset:end]
    if offset == 0 and end == total:
        # Preserve the established exact-result behavior for ordinary files.
        return chunk

    header = (
        f"[oompah read_file: {args['path']} characters {offset}:{end} "
        f"of {total}]\n"
    )
    if end < total:
        trailer = (
            "\n[truncated by Oompah before provider transport; continue only "
            "through the approved tool with "
            f"read_file(path={args['path']!r}, offset={end}, limit={limit})]"
        )
    else:
        trailer = "\n[end of file]"
    return f"{header}{chunk}{trailer}"


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
    # Validate containment in-process as well as in the worker.  The separate
    # process is intentional: Python's stdlib regex engine has no per-match
    # timeout, so an adversarial-but-valid pattern must not block the server.
    _safe_resolve(workspace, args.get("path", "."))
    worker = Path(__file__).with_name("search_files.py")
    request = json.dumps({"workspace": str(workspace.resolve()), "args": args})
    try:
        result = subprocess.run(
            [sys.executable, str(worker)],
            input=request,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            detail = (result.stderr or "search worker failed").strip()
            return f"Error searching: {detail[:1000]}"
        return result.stdout or f"No matches found for {args['pattern']!r}"
    except subprocess.TimeoutExpired:
        return "Error: search timed out"
    except Exception as exc:
        return f"Error searching: {exc}"


def _validate_command_stays_in_workspace(command: str, workspace: Path) -> str | None:
    """Return an error string if ``command`` cd's out of the agent's
    worktree, else ``None``. Catches the dominant pattern observed in
    practice: agents prefixing their shell commands with ``cd /abs/path
    && ...``, ending up in the main checkout where their edits aren't.

    This isn't airtight — `bash -c "true; cd /; ls"` or `eval` would
    bypass it — but it covers the leading-cd / leading-pushd cases
    that show up repeatedly in agent logs, with a clear error message
    that nudges the agent to use relative paths.
    """
    import re as _re

    # Match leading `cd <target>` or `(cd <target>` or `pushd <target>`,
    # tolerating leading whitespace.
    m = _re.match(
        r"""^\s*\(?\s*(cd|pushd)\s+(?:"([^"]+)"|'([^']+)'|(\S+))""",
        command,
    )
    if not m:
        return None
    target = m.group(2) or m.group(3) or m.group(4) or ""
    # Relative cd is fine — stays within workspace.
    if not target.startswith("/") and not target.startswith("~"):
        return None
    try:
        target_path = Path(os.path.expanduser(target)).resolve()
        ws = workspace.resolve()
    except OSError:
        return None
    if target_path == ws:
        return None
    # Allow descending into subdirs of the workspace.
    try:
        target_path.relative_to(ws)
    except ValueError:
        return (
            f"refusing to run: command starts with `{m.group(1)} {target}` which "
            f"leaves your worktree ({ws}). Your worktree IS the project — use "
            f"relative paths from here. If you genuinely need to inspect another "
            f"checkout, do it without `cd` (e.g. "
            f"`grep -n PATTERN /other/path/file.py`)."
        )
    return None


def _exec_run_command(
    workspace: Path,
    args: dict[str, Any],
    timeout: int | None = None,
    env_overrides: dict[str, str] | None = None,
    tool_liveness: Any = None,
    output_store: CommandOutputStore | None = None,
    validation_lease: ValidationResourceLease | None = None,
    validation_owner: ValidationLeaseOwner | None = None,
    lease_cancelled: Callable[[], bool] | None = None,
    require_validation_lease: bool = False,
    successful_validation_handler: Callable[[str, Path], object] | None = None,
    result_delivery_required: bool = False,
) -> str:
    timeout = _resolve_run_command_timeout() if timeout is None else timeout
    command = args["command"]
    cd_err = _validate_command_stays_in_workspace(command, workspace)
    if cd_err:
        return f"Error: {cd_err}"
    # Validate that git commands are noninteractive (OOMPAH-681)
    git_err = validate_git_command_is_noninteractive(command)
    if git_err:
        return f"Error: {git_err}"
    # Build env from the agent's own env, layering caller-supplied overrides
    # on top, then remove client-only Basic-auth inputs before spawning a
    # command.  This applies even when no explicit overrides are supplied,
    # because ``env=None`` would otherwise inherit the server's full env.
    inherited_env = {**os.environ, **(env_overrides or {})}
    env = agent_environment(inherited_env, workspace_path=workspace)
    
    # Apply noninteractive git environment to all commands as defense-in-depth (OOMPAH-681).
    # This prevents git from spawning editors even if the command bypasses our validation.
    if "git" in command:
        env.update(NONINTERACTIVE_GIT_ENV)

    def _terminate_process_tree(process: subprocess.Popen[str]) -> tuple[str, str]:
        if os.name == "posix":
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                # The shell may already be gone while a descendant still
                # owns one of its stdout/stderr pipes. Never fall back to an
                # unbounded communicate() in that state.
                pass
        else:
            process.terminate()
        try:
            return process.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            if os.name == "posix":
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            else:
                process.kill()
            try:
                return process.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                # The provider is being retired; retaining partial output is
                # neither useful nor safe. Closing our readers makes the
                # cancellation path bounded even when an uncooperative
                # descendant inherited the pipe.
                for stream in (process.stdout, process.stderr):
                    if stream is not None:
                        with contextlib.suppress(Exception):
                            stream.close()
                with contextlib.suppress(Exception):
                    process.wait(timeout=0.1)
                return "", ""

    validation_handle = None
    invocation_id: str | None = None
    result_pending = False

    def _mark_result_pending() -> None:
        """Keep liveness ownership until the provider sees this result."""

        nonlocal result_pending
        if invocation_id is None or not result_delivery_required:
            return
        try:
            pending = getattr(tool_liveness, "result_pending", None)
            if callable(pending):
                pending(invocation_id)
            else:
                # Older observers do not understand the bridge lifecycle;
                # their existing completion behavior remains compatible.
                return
            result_pending = True
        except Exception:
            # Liveness is supervisory telemetry. A broken observer must not
            # suppress the bounded command result.
            logger.debug("Unable to mark command result pending", exc_info=True)

    heavyweight_validation = is_heavyweight_validation_command(command)
    if require_validation_lease and heavyweight_validation and validation_owner is None:
        return (
            "Error: heavyweight validation is unavailable because trusted "
            "managed-agent ownership metadata is incomplete"
        )
    if validation_owner is not None and heavyweight_validation:
        if validation_lease is None:
            return (
                "Error: heavyweight validation is unavailable because the "
                "service validation lease is not configured"
            )
        if tool_liveness is not None:
            try:
                invocation_id = tool_liveness.start_waiting(
                    tool_name="run_command",
                    result_delivery_required=result_delivery_required,
                )
            except Exception:
                invocation_id = None
        try:
            lease_kwargs: dict[str, Any] = {"is_cancelled": lease_cancelled}
            if invocation_id is not None:
                lease_kwargs["on_wait"] = lambda: tool_liveness.heartbeat(
                    invocation_id
                )
            validation_handle = validation_lease.acquire(
                validation_owner,
                **lease_kwargs,
            )
        except ValidationLeaseCancelled as exc:
            if invocation_id is not None:
                with contextlib.suppress(Exception):
                    tool_liveness.complete(invocation_id)
            return f"Error: {exc}"
        except (OSError, sqlite3.Error, ValidationLeaseError) as exc:
            if invocation_id is not None:
                with contextlib.suppress(Exception):
                    tool_liveness.complete(invocation_id)
            return f"Error: unable to acquire heavyweight validation capacity: {exc}"

    if tool_liveness is not None:
        try:
            if invocation_id is None:
                invocation_id = tool_liveness.start(
                    tool_name="run_command",
                    timeout_s=timeout,
                    result_delivery_required=result_delivery_required,
                )
            else:
                tool_liveness.start_runtime(
                    invocation_id,
                    timeout_s=timeout,
                    result_delivery_required=result_delivery_required,
                )
        except Exception:
            # Liveness is supervisory telemetry. It must never prevent the
            # command itself from running when an observer is unavailable.
            if invocation_id is not None:
                with contextlib.suppress(Exception):
                    tool_liveness.complete(invocation_id)
            invocation_id = None

    try:
        def _authority_cancelled() -> bool:
            if lease_cancelled is None:
                return False
            try:
                return bool(lease_cancelled())
            except Exception:
                return True

        if _authority_cancelled():
            return "Error: validation authority withdrawn before command launch"
        # Runtime begins after capacity acquisition, including process setup.
        runtime_deadline = time.monotonic() + max(float(timeout), 0.0)
        popen_kwargs: dict[str, Any] = {
            "cwd": str(workspace),
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "text": True,
            "env": env,
            "start_new_session": os.name == "posix",
        }
        if validation_handle is not None and os.name == "posix":
            popen_kwargs["pass_fds"] = validation_handle.pass_fds
        if _authority_cancelled():
            return "Error: validation authority withdrawn before command launch"
        process = subprocess.Popen(["bash", "-lc", command], **popen_kwargs)
        if validation_handle is not None:
            try:
                validation_handle.attach_process(
                    process,
                    timeout_seconds=timeout,
                )
            except ValidationLeaseError:
                _terminate_process_tree(process)
                raise
        if invocation_id is not None:
            try:
                tool_liveness.attach_process(invocation_id, process)
            except Exception:
                pass
        while True:
            if _authority_cancelled():
                _terminate_process_tree(process)
                _mark_result_pending()
                return "Error: validation authority withdrawn while command was running"
            remaining = runtime_deadline - time.monotonic()
            if remaining <= 0:
                _terminate_process_tree(process)
                _mark_result_pending()
                return f"Error: command timed out after {timeout}s"
            try:
                stdout, stderr = process.communicate(timeout=min(remaining, 0.25))
                break
            except subprocess.TimeoutExpired:
                if invocation_id is not None:
                    with contextlib.suppress(Exception):
                        tool_liveness.heartbeat(invocation_id)

        # The shell may have exited while descendants still hold one of the
        # captured pipes. Mark the handoff before evidence recording and
        # output assembly so concurrent stall inspection cannot retire the
        # provider while this bounded result is being prepared.
        _mark_result_pending()

        if (
            heavyweight_validation
            and process.returncode == 0
            and callable(successful_validation_handler)
            and not _authority_cancelled()
        ):
            try:
                successful_validation_handler(command, workspace)
            except Exception as exc:  # noqa: BLE001 - evidence is an optimization
                logger.warning(
                    "Unable to record auditor validation evidence: %s",
                    exc,
                )

        parts: list[str] = []
        if stdout:
            parts.append(f"stdout:\n{stdout}")
        if stderr:
            parts.append(f"stderr:\n{stderr}")
        parts.append(f"exit_code: {process.returncode}")
        result = "\n".join(parts)
        if len(result) <= _TOOL_RESULT_MAX_CHARS:
            return result

        result_id: str | None = None
        if output_store is not None:
            try:
                result_id = output_store.save(result)
            except Exception as exc:  # noqa: BLE001 - keep provider boundary fail-closed
                logger.warning("Unable to retain oversized command output: %s", exc)

        preview = result[:_COMMAND_OUTPUT_PAGE_CHARS]
        if result_id is None:
            return (
                f"{preview}\n[command output truncated by Oompah before provider "
                "transport; no approved continuation is available]"
            )
        return (
            f"{preview}\n[command output truncated by Oompah before provider "
            f"transport; result_id={result_id!r}, total_characters={len(result)}. "
            "Continue only with the approved read_command_output tool. "
            f"Example: read_command_output(result_id={result_id!r}, offset="
            f"{_COMMAND_OUTPUT_PAGE_CHARS}, limit={_COMMAND_OUTPUT_PAGE_CHARS})]"
        )
    except Exception as exc:
        return f"Error running command: {exc}"
    finally:
        if invocation_id is not None:
            try:
                if result_delivery_required and not result_pending:
                    _mark_result_pending()
                if not result_delivery_required or not result_pending:
                    tool_liveness.complete(invocation_id)
            except Exception:
                pass
        if validation_handle is not None:
            validation_handle.release()


def _exec_read_command_output(
    output_store: CommandOutputStore | None,
    args: dict[str, Any],
) -> str:
    """Read an opaque oversized command result through the approved channel."""

    if output_store is None:
        return "Error: command output continuation is unavailable in this session"
    return output_store.read(args)


def _exec_attach_image(workspace: Path, args: dict[str, Any]) -> str:
    """Decode a base64 image into the workspace's
    .oompah/attachments/<issue>/outputs/ directory, named
    ``<turn>-<sha>-<filename>``. Returns the canonical relative path on
    success, or an error string. The orchestrator commits these on agent
    completion and writes the manifest back to tracker metadata."""
    import base64 as _b64
    import hashlib as _h
    import re as _re

    issue = str(args.get("issue_identifier") or "").strip()
    filename = str(args.get("filename") or "").strip()
    content_b64 = args.get("content_base64") or ""
    turn = args.get("turn")

    if not issue or not filename or not content_b64:
        return "Error: attach_image requires issue_identifier, filename, content_base64"
    if "/" in issue or "\\" in issue:
        return f"Error: invalid issue_identifier: {issue!r}"

    try:
        data = _b64.b64decode(content_b64, validate=True)
    except Exception as exc:
        return f"Error: content_base64 is not valid base64 ({exc})"

    # Reject anything not on the attachments allow-list.
    from oompah.attachments import (
        ALLOWED_MIME_TYPES,
        MAX_ATTACHMENT_BYTES,
    )
    import mimetypes as _mt

    mime, _ = _mt.guess_type(filename)
    if not mime or mime not in ALLOWED_MIME_TYPES:
        return (
            f"Error: filename {filename!r} has mime {mime!r}; "
            f"attach_image only accepts {sorted(ALLOWED_MIME_TYPES)}"
        )
    if len(data) > MAX_ATTACHMENT_BYTES:
        return (
            f"Error: image is {len(data)} bytes; per-attachment cap is "
            f"{MAX_ATTACHMENT_BYTES}"
        )

    safe = _re.sub(r"[^A-Za-z0-9._-]+", "_", os.path.basename(filename)) or "file"
    sha = _h.sha256(data).hexdigest()[:12]
    turn_part = (
        f"{int(turn)}-" if isinstance(turn, (int, str)) and str(turn).isdigit() else ""
    )
    fname = f"{turn_part}{sha}-{safe}"

    out_dir = workspace / ".oompah" / "attachments" / issue / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / fname
    if not dest.exists():
        dest.write_bytes(data)
    rel = f".oompah/attachments/{issue}/outputs/{fname}"
    return f"OK: wrote {len(data)} bytes to {rel}"


# Tools that require explicit opt-in. They are NOT registered with the
# model unless ``ApiAgentSession.enabled_tools`` includes them.
_OPT_IN_TOOLS: frozenset[str] = frozenset(
    {"attach_image", AUDITOR_RESULT_TOOL_NAME, "read_command_output"}
)


# Phrases that indicate a confirmation-seeking question.  When an
# ask_question call matches one of these the tool result is treated as
# an error and the agent is told to keep working instead of stopping.
_BLOCKED_QUESTION_PHRASES: tuple[str, ...] = (
    "is that ok",
    "is this ok",
    "is it ok",
    "does that look right",
    "does this look right",
    "does that look correct",
    "does this look correct",
    "do you agree",
    "am i on the right track",
    "should i proceed",
    "should i continue",
    "should i go ahead",
    "how should i proceed",
    "what should i prioritize",
    "what approach should i take",
    "how do i fix this",
    "how do i solve this",
    "how do i implement this",
    "how do i do this",
    "can you confirm",
    "please confirm",
)

_ASK_QUESTION_REJECTION: str = (
    "This question was rejected because it is confirmation-seeking or asks "
    "for implementation guidance. You are an autonomous agent — investigate "
    "and solve the problem yourself. Do not ask the human for approval of "
    "your plan. Proceed with the implementation."
)


_TOOL_DISPATCH: dict[str, Any] = {
    "read_file": _exec_read_file,
    "write_file": _exec_write_file,
    "edit_file": _exec_edit_file,
    "search_files": _exec_search_files,
    "list_files": _exec_list_files,
    "run_command": _exec_run_command,
    "attach_image": _exec_attach_image,
    # ask_question is handled specially in the agent loop, not here
}


_TOOL_REQUIRED_ARGS: dict[str, list[str]] = {
    "read_file": ["path"],
    "write_file": ["path", "content"],
    "edit_file": ["path", "old_string", "new_string"],
    "search_files": ["pattern"],
    "run_command": ["command"],
    "read_command_output": ["result_id"],
    "list_files": [],
    "ask_question": ["question"],
    "attach_image": ["issue_identifier", "filename", "content_base64"],
    AUDITOR_RESULT_TOOL_NAME: ["audit_id", "target_state", "evidence_fingerprint", "verdict", "message"],
}

_READ_ONLY_TOOL_NAMES = frozenset(
    {"read_file", "search_files", "list_files", "read_command_output"}
)


def _execute_tool(
    workspace: Path,
    name: str,
    args: dict[str, Any],
    cmd_timeout: int | None = None,
    env_overrides: dict[str, str] | None = None,
    read_only: bool = False,
    task_tracker: Any = None,
    project_id: str | None = None,
    task_identifier: str | None = None,
    action_policy: AgentActionPolicy | None = None,
    audit_target: Any = None,
    audit_result_handler: Any = None,
    tool_liveness: Any = None,
    policy_denial_handler: Any = None,
    command_output_store: CommandOutputStore | None = None,
    validation_lease: ValidationResourceLease | None = None,
    lease_cancelled: Callable[[], bool] | None = None,
    successful_validation_handler: Callable[[str, Path], object] | None = None,
) -> str:
    """Execute a tool call and return its string result.

    ``env_overrides`` is forwarded to ``run_command`` only — the file/edit
    tools don't spawn subprocesses, so it has no effect on them.
    """
    if read_only and name not in _READ_ONLY_TOOL_NAMES:
        return f"Error: tool {name!r} is unavailable in a read-only session"

    if action_policy is not None and action_policy.read_only and name not in AUDITOR_ALLOWED_TOOLS:
        return (
            "Error: auditor capability policy denied this tool. Only read-only "
            "repository/test tools and submit_audit_result are available."
        )

    if name == AUDITOR_RESULT_TOOL_NAME:
        session_denial = check_auditor_session_target(action_policy, audit_target)
        if session_denial is not None:
            return session_denial
        return submit_auditor_result(args, audit_target, audit_result_handler)

    handler = _TOOL_DISPATCH.get(name)
    if handler is None:
        # Models occasionally lift a shell command out of the WORKFLOW.md
        # cheat sheet and call it as a tool name (e.g. ``oompah task set-status``
        # with spaces, or ``git commit``). Detect that and redirect them
        # to ``run_command`` instead of leaving them to loop on the bare
        # "unknown tool" message.
        looks_like_shell = " " in name or name.startswith(
            ("oompah", "oompah_", "git", "git_", "uv ", "make")
        )
        if looks_like_shell:
            return (
                f"Error: {name!r} is not a tool — it looks like a shell "
                f"command. Use the run_command tool instead, e.g. "
                f"run_command(command={name!r} + ' ARGS_HERE'). "
                f"Available tools: {', '.join(_TOOL_DISPATCH)}"
            )
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
        if name == "read_command_output":
            return _exec_read_command_output(command_output_store, args)
        if name == "run_command":
            shell_denial = check_shell_command(
                action_policy, str(args.get("command") or "")
            )
            if shell_denial is not None:
                # Unsupported read-only shell syntax is a tool-validation
                # response. It must be returned to the model so it can split
                # the inspection into search/read calls, but it is not a
                # repeated forbidden mutation and must not retire the audit.
                from oompah.auditor import is_recoverable_auditor_command_denial

                if (
                    callable(policy_denial_handler)
                    and not is_recoverable_auditor_command_denial(shell_denial)
                ):
                    try:
                        policy_denial_handler(shell_denial)
                    except Exception:  # noqa: BLE001 - denial stays fail-closed
                        logger.exception("Policy-denial observer failed")
                return shell_denial
            # API workers execute inside the oompah process. Route their task
            # handoff command through the active tracker instead of allowing
            # the CLI to synchronously HTTP-call its own server.
            from oompah.acp_tools import _exec_oompah_task_command

            direct = _exec_oompah_task_command(
                args.get("command", ""),
                task_tracker,
                project_id,
                action_policy,
                task_identifier,
                workspace_path=workspace,
            )
            if direct is not None:
                return direct
            command_kwargs = {
                "timeout": cmd_timeout,
                "env_overrides": env_overrides,
            }
            if tool_liveness is not None:
                command_kwargs["tool_liveness"] = tool_liveness
            if command_output_store is not None:
                command_kwargs["output_store"] = command_output_store
            validation_owner = managed_agent_validation_owner(
                action_policy,
                audit_target,
                project_id=project_id,
                task_id=task_identifier,
            )
            if validation_owner is not None:
                command_kwargs["validation_owner"] = validation_owner
                command_kwargs["validation_lease"] = validation_lease
                command_kwargs["lease_cancelled"] = lease_cancelled
            if (
                validation_lease is not None
                or getattr(action_policy, "auditor_session", False) is True
            ):
                command_kwargs["require_validation_lease"] = True
            if successful_validation_handler is not None:
                command_kwargs["successful_validation_handler"] = (
                    successful_validation_handler
                )
            if tool_liveness is not None:
                command_kwargs["result_delivery_required"] = True
            return handler(workspace, args, **command_kwargs)
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


# Timeout for individual HTTP requests to the chat completions endpoint.
# 600 seconds (10 minutes) accommodates slow deep-reasoning model inference.
_HTTP_TIMEOUT = 600


def _http_post(
    url: str, headers: dict[str, str], body: bytes, ssl_ctx: ssl.SSLContext
) -> dict[str, Any]:
    """Blocking HTTP POST that returns parsed JSON.

    Raises a typed exception so the caller can decide whether to retry:
    - :class:`RateLimitError` for 429/529 (honors Retry-After).
    - :class:`TransientServerError` for 5xx and network-level failures.
    - :class:`RuntimeError` for permanent failures (4xx other than 429),
      malformed JSON, or anything else not worth retrying.
    """
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(
            req, context=ssl_ctx, timeout=_HTTP_TIMEOUT
        ) as resp:
            data = resp.read()
            return json.loads(data)
    except urllib.error.HTTPError as exc:
        error_body = ""
        try:
            error_body = exc.read().decode("utf-8", errors="replace")[:2000]
        except Exception:
            pass
        if exc.code in (429, 529):
            retry_after = 0.0
            ra_header = exc.headers.get("Retry-After", "") if exc.headers else ""
            if ra_header:
                try:
                    retry_after = float(ra_header)
                except ValueError:
                    pass
            raise RateLimitError(
                f"HTTP {exc.code} from {url}: {error_body}",
                retry_after=retry_after,
            ) from exc
        # 5xx: server-side problem — typically transient. Worth retrying
        # the same call rather than tearing down the whole worker.
        if 500 <= exc.code < 600:
            raise TransientServerError(
                f"HTTP {exc.code} from {url}: {error_body}",
                status_code=exc.code,
            ) from exc
        # 401: authentication failure. Treat as retryable — the token
        # may have expired and will be renewed by the operator, or the
        # server may have had a brief identity-service hiccup. Unlike
        # other 4xx errors (bad request, not found, etc.), a 401 never
        # indicates a problem with the request payload itself.
        if exc.code == 401:
            raise TransientServerError(
                f"HTTP {exc.code} from {url}: {error_body}",
                status_code=exc.code,
            ) from exc
        # 404 from litellm's model router: "litellm.NotFoundError ...
        # Received Model Group=..." means the model is not (yet)
        # registered in the routing table.  This can happen transiently
        # during model deployment or planned maintenance.  Treat as
        # transient so the in-session retry loop can recover, and so
        # run_task logs at WARNING instead of ERROR (avoiding spurious
        # error_watcher bug tasks for infrastructure blips).
        if exc.code == 404 and _is_litellm_not_found_error(error_body):
            raise TransientServerError(
                f"HTTP {exc.code} from {url}: {error_body}",
                status_code=exc.code,
            ) from exc
        # All other 4xx: permanent client failure — do not retry.
        raise RuntimeError(f"HTTP {exc.code} from {url}: {error_body}") from exc
    except urllib.error.URLError as exc:
        # Connection refused, timeouts, DNS failures, name not resolved,
        # etc. — almost always transient (server restarting, brief network
        # blip). Treat as retryable.
        raise TransientServerError(
            f"URL error for {url}: {exc.reason}",
            status_code=None,
        ) from exc
    except OSError as exc:
        # Raw socket-level errors that leak through urllib unwrapped —
        # most commonly during ``resp.read()`` after ``urlopen`` has
        # already returned. macOS reports ENOTCONN (errno 57, "Socket is
        # not connected") when the remote tears down the TLS connection
        # mid-stream; Linux equivalents include ECONNRESET (104) and
        # EPIPE (32). These are transient — the next request opens a
        # fresh socket — so retry rather than failing the whole task.
        # Note: ``urllib.error.URLError`` is a subclass of ``OSError``,
        # so this handler runs only for plain OSErrors that escaped the
        # URLError wrapping (the more-specific branch above wins first).
        raise TransientServerError(
            f"Socket error for {url}: [Errno {exc.errno}] {exc.strerror or exc}",
            status_code=None,
        ) from exc


# ---------------------------------------------------------------------------
# Context-window budgeting
# ---------------------------------------------------------------------------

# Default output reservation when no per-call budget is computed.
_DEFAULT_MAX_OUTPUT_TOKENS = 32768
# Floor for ``max_tokens`` after pruning, so the model can always reply.
_MIN_MAX_OUTPUT_TOKENS = 1024
# Padding for our 4-chars-per-token approximation drift.
_TOKENIZER_SAFETY_MARGIN = 1024


def _estimate_tokens(payload: object) -> int:
    """Approximate token count for an arbitrary JSON-serializable object.

    Uses the well-known 4-chars-per-token rule of thumb, which is close
    for English-heavy content typical of agent transcripts. The caller
    pads the result with :data:`_TOKENIZER_SAFETY_MARGIN` when budgeting.
    """
    try:
        s = json.dumps(payload, ensure_ascii=False)
    except (TypeError, ValueError):
        s = str(payload)
    return max(1, len(s) // 4)


_CONTEXT_WINDOW_RE = re.compile(
    r"(?:maximum context length is|context length is only) (\d+) tokens",
)

# Phrases that unambiguously indicate a context-window-exceeded error.
# The second entry covers the ``litellm.BadRequestError`` variant emitted
# by the NVIDIA inference API when input + output tokens exceed the model's
# context window (as opposed to the ``ContextWindowExceededError`` variant
# that litellm raises via its own fallback path).
_CONTEXT_WINDOW_INDICATORS: tuple[str, ...] = (
    "ContextWindowExceededError",
    "context length is only",  # NVIDIA BadRequestError: "the model's context length is only N tokens"
)


def _extract_context_window_limit(error_body: str) -> int | None:
    """Extract the context-window limit (tokens) from a context-window error body.

    Handles two litellm-wrapped formats seen at
    ``https://inference-api.nvidia.com/v1/chat/completions``:

    1. ``ContextWindowExceededError`` variant::

        {"error":{"message":"... ContextWindowExceededError: ...
            \"maximum context length is 131072 tokens.\"..."}}

    2. ``BadRequestError`` variant (NVIDIA, token-count mismatch)::

        {"error":{"message":"litellm.BadRequestError: OpenAIException -
            {\"error\":{\"message\":\"You passed 98305 input tokens and requested
            32768 output tokens. However, the model's context length is only
            131072 tokens, resulting in a maximum input length of 98304 tokens.
            ...\"}}..."}}

    Returns the integer limit, or ``None`` if the pattern cannot be matched.
    """
    try:
        body = json.loads(error_body)
        msg = (body.get("error") or {}).get("message") or ""
    except (json.JSONDecodeError, TypeError, AttributeError):
        msg = error_body
    m = _CONTEXT_WINDOW_RE.search(msg)
    if m:
        return int(m.group(1))
    return None


def _is_context_window_error(error_body: str) -> bool:
    """Return True when *error_body* describes a context-window-exceeded error.

    Detects both the ``ContextWindowExceededError`` variant and the
    ``litellm.BadRequestError`` variant (NVIDIA) where the model rejects
    the request because ``input_tokens + max_tokens > context_window``.
    """
    return any(phrase in error_body for phrase in _CONTEXT_WINDOW_INDICATORS)


# Phrases that together uniquely identify a litellm model-router "not found"
# response.  Both must be present.  These appear in the JSON error body when
# the model group is not registered in litellm's routing table, which can
# happen transiently during model deployment or maintenance:
#
#   {"error":{"message":"litellm.NotFoundError: NotFoundError: OpenAIException
#       - . Received Model Group=nvidia/nvidia/nemotron-3-ultra\n
#       Available Model Group Fallbacks=None","code":"404"}}
#
# TASK-471
_LITELLM_NOT_FOUND_INDICATORS: tuple[str, ...] = (
    "litellm.NotFoundError",
    "Received Model Group=",
)


def _is_litellm_not_found_error(error_body: str) -> bool:
    """Return True when *error_body* describes a litellm model-router not-found error.

    HTTP 404 responses from the NVIDIA inference API that contain both
    ``"litellm.NotFoundError"`` and ``"Received Model Group="`` mean that
    the model is not (yet) registered in litellm's routing table.  This
    can happen transiently during model deployment or maintenance, so these
    should be retried rather than treated as permanent failures.
    """
    return all(phrase in error_body for phrase in _LITELLM_NOT_FOUND_INDICATORS)


def _prune_messages_to_fit(
    messages: list[dict[str, Any]],
    tool_definitions: list[dict[str, Any]],
    max_input_tokens: int,
) -> int:
    """Prune oldest assistant/tool round-trips from ``messages`` in place
    until the estimated outgoing payload fits in ``max_input_tokens``.

    Always preserves ``messages[0]`` (system) and ``messages[1]`` (the
    initial user prompt), since dropping those would erase the task.

    Removes message groups, where a group is one assistant message
    plus any immediately-following tool messages that respond to its
    tool_calls. Dropping an assistant without its tool responses (or
    vice versa) would leave dangling ``tool_call_id`` references that
    OpenAI-compatible endpoints reject with 400. Returns the number of
    messages removed.
    """
    if max_input_tokens <= 0:
        return 0
    # Anchor the head — never drop these.
    head_count = min(2, len(messages))
    removed = 0
    while True:
        est = _estimate_tokens(
            {
                "messages": messages,
                "tools": tool_definitions,
            }
        )
        if est <= max_input_tokens:
            return removed
        # Find the first assistant message after the head.
        cut_start = None
        for i in range(head_count, len(messages)):
            if messages[i].get("role") == "assistant":
                cut_start = i
                break
        if cut_start is None:
            # Nothing left to drop without breaking the head.
            return removed
        # Walk forward to absorb tool responses to this assistant's calls.
        cut_end = cut_start + 1
        while cut_end < len(messages) and messages[cut_end].get("role") == "tool":
            cut_end += 1
        # If the assistant had no tool_calls and no tool followers, this
        # is just a plain assistant reply — fine to drop alone.
        del messages[cut_start:cut_end]
        removed += cut_end - cut_start
        if cut_start >= len(messages):
            # Only head remains.
            return removed


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
        command_timeout: int | None = None,
        enabled_tools: set[str] | None = None,
        read_only: bool = False,
        model_max_context: int | None = None,
        log_path: str | None = None,
        task_tracker: Any = None,
        project_id: str | None = None,
        task_identifier: str | None = None,
        action_policy: AgentActionPolicy | None = None,
        audit_target: Any = None,
        audit_result_handler: Any = None,
        tool_liveness: Any = None,
        policy_denial_handler: Any = None,
        validation_lease: ValidationResourceLease | None = None,
        successful_validation_handler: Callable[[str, Path], object] | None = None,
    ):
        # Validate before joining.  In particular, an absent base must never
        # turn into the relative path ``/chat/completions``.  This constructor
        # is also the last guard for runtime provider mutations after
        # candidate selection.
        self.base_url = base_url.strip().rstrip("/") if isinstance(base_url, str) else base_url
        self._url = openai_chat_completions_url(self.base_url)
        self._api_key = api_key
        # Provider credentials can appear later in an otherwise innocuous
        # response/detail string.  Register the value at session creation so
        # every API-agent sink is protected by literal replacement too.
        register_secret(api_key)
        self.model = model
        self.workspace = Path(workspace_path).resolve()
        self.max_turns = max_turns
        self.stall_turns = stall_turns
        self.system_prompt = system_prompt
        self.command_timeout = (
            _resolve_run_command_timeout()
            if command_timeout is None
            else command_timeout
        )
        # Names of tools to expose to the model. ``None`` means "all
        # tools except those that require explicit opt-in" — currently
        # ``attach_image`` is the only opt-in tool, so it's filtered out
        # by default. The orchestrator passes an explicit set when the
        # active focus opts in and the resolved model has the image
        # capability.
        if action_policy is not None and action_policy.read_only:
            # A capability policy is server authority, not merely a prompt
            # hint. Intersect caller input with the canonical allowlist so a
            # malformed dispatch cannot even advertise a mutation tool to the
            # model; _execute_tool repeats this check at execution time.
            requested_tools = (
                set(AUDITOR_ALLOWED_TOOLS)
                if enabled_tools is None
                else set(enabled_tools)
            )
            self.enabled_tools = requested_tools & set(AUDITOR_ALLOWED_TOOLS)
        else:
            self.enabled_tools = enabled_tools
        self.read_only = bool(read_only)
        # Total context window for ``model`` (input + output, in tokens).
        # When set, _call_api budgets each request: prunes the oldest
        # assistant/tool round-trips if the prompt would overflow, and
        # clamps max_tokens to fit within the remaining headroom. When
        # None, behaviour falls back to the legacy fixed max_tokens.
        self.model_max_context = model_max_context
        # Path to a JSONL file recording every request, response, and
        # activity event for this dispatch. None disables file logging.
        self.log_path = log_path
        self.task_tracker = task_tracker
        self.project_id = project_id
        self.task_identifier = task_identifier
        self.action_policy = action_policy
        self.audit_target = audit_target
        self.audit_result_handler = audit_result_handler
        self.tool_liveness = tool_liveness
        self.policy_denial_handler = policy_denial_handler
        self.validation_lease = validation_lease
        self.successful_validation_handler = successful_validation_handler
        self._force_audit_finalization = False
        # Auditor command output continuations are session-local and stay in
        # the approved tool channel. Normal workers do not need a continuation
        # capability, so they receive a bounded preview only.
        self.command_output_store = (
            CommandOutputStore()
            if action_policy is not None and action_policy.read_only
            else None
        )
        self._ssl_ctx = _build_ssl_context()

    def _log_event(self, kind: str, **fields: Any) -> None:
        """Append one JSONL record to ``self.log_path`` (best-effort).

        Each record is a single-line JSON object with ``ts`` (UTC ISO),
        ``kind`` (e.g. "session_start", "request", "response",
        "activity", "session_end"), and any extra fields the caller
        passes. Failures are swallowed so logging never disrupts a
        running agent. ``api_key`` and HTTP headers are never written.

        SECURITY: All ``fields`` are recursively scanned by
        :func:`oompah.secrets.redact_sensitive_data` before serialization.
        Request payloads carry full ``messages``/``tools``, response
        bodies carry tool outputs, and error events carry exception
        text — any of which could embed a bearer token, HTTP Basic
        password, or URL with userinfo returned by a downstream API.
        """
        if not self.log_path:
            return
        try:
            # Redact sensitive fields recursively before persistence.
            # The redaction runs *before* JSON encoding so that both the
            # values we know about (strings, dicts, lists) and any
            # unknown-typed values that would otherwise be stringified
            # via default=str are scanned.
            safe_fields = {k: redact_sensitive_data(v) for k, v in fields.items()}
            record = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "kind": kind,
                **safe_fields,
            }
            os.makedirs(os.path.dirname(self.log_path) or ".", exist_ok=True)
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False, default=str))
                f.write("\n")
        except (OSError, TypeError, ValueError):
            # Logging is best-effort: any error here must not break the agent.
            pass

    @property
    def _tool_definitions(self) -> list[dict[str, Any]]:
        """Tool schemas to send to the API for this session."""
        def available(name: str) -> bool:
            return name != "read_command_output" or self.command_output_store is not None

        if self.enabled_tools is None:
            return [
                t
                for t in TOOL_DEFINITIONS
                if t["function"]["name"] not in _OPT_IN_TOOLS
                and available(t["function"]["name"])
                and (
                    not self.read_only
                    or t["function"]["name"] in _READ_ONLY_TOOL_NAMES
                )
            ]
        return [
            t
            for t in TOOL_DEFINITIONS
            if t["function"]["name"] in self.enabled_tools
            and available(t["function"]["name"])
            and (
                not self.read_only
                or t["function"]["name"] in _READ_ONLY_TOOL_NAMES
            )
        ]

    # -- public interface ---------------------------------------------------

    async def run_task(
        self,
        prompt: "str | RenderedPrompt",
        on_activity: Callable[[AgentActivity], None] | None = None,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> ApiAgentResult:
        """Run the agent on a task prompt. Returns result with token counts.

        ``prompt`` accepts either a plain string (single text user message)
        or a :class:`RenderedPrompt`. When ``RenderedPrompt.parts`` is set,
        the first user message uses an OpenAI-style content array so
        multimodal models receive image/audio inline. Subsequent turns
        (tool results) remain text.
        """
        messages: list[dict[str, Any]] = []
        activity: list[AgentActivity] = []

        # One-time header recording the dispatch parameters. After this
        # the log captures every request/response and every activity
        # event so the full conversation can be reconstructed.
        self._log_event(
            "session_start",
            model=self.model,
            base_url=self.base_url,
            workspace=str(self.workspace),
            max_turns=self.max_turns,
            stall_turns=self.stall_turns,
            system_prompt=self.system_prompt,
            tools=[t.get("function", {}).get("name") for t in self._tool_definitions],
            model_max_context=self.model_max_context,
        )

        def _emit(turn: int, kind: str, summary: str, detail: str = "") -> None:
            # Attach the running token totals so the dashboard's
            # sticky activity summary header can scan back-to-front
            # for the latest usage snapshot. ``total_input`` and
            # friends live in the enclosing scope below.
            usage_snap: dict[str, Any] | None = None
            try:
                if total_input or total_output or total_tokens:
                    usage_snap = {
                        "input_tokens": total_input,
                        "output_tokens": total_output,
                        "total_tokens": total_tokens,
                    }
            except NameError:
                pass  # _emit called before counters initialized

            # SECURITY: summary and detail may be built from tool args,
            # tool results, or exception text — any of which can carry
            # a bearer token, HTTP Basic password, or URL with userinfo.
            # Redact before we store the activity, hand it to the
            # callback, or record it in the JSONL log.
            _summary_r = redact_sensitive_data(summary)
            _summary = _summary_r if isinstance(_summary_r, str) else str(_summary_r)
            _detail_r = redact_sensitive_data(detail)
            _detail = _detail_r if isinstance(_detail_r, str) else str(_detail_r)

            entry = AgentActivity(
                turn=turn,
                kind=kind,
                summary=_summary,
                detail=_detail,
                timestamp=time.time(),
                usage=usage_snap,
            )
            activity.append(entry)
            if on_activity:
                on_activity(entry)
            self._log_event(
                "activity",
                turn=turn,
                event_kind=kind,
                summary=_summary,
                detail=_detail,
            )
            if kind == "tool_result":
                mark_delivered = getattr(
                    self.tool_liveness,
                    "result_delivered",
                    None,
                )
                if callable(mark_delivered):
                    try:
                        # Activity callback and JSONL persistence have both
                        # completed, so the bounded result is durably
                        # deliverable to the API provider.
                        mark_delivered()
                    except Exception:  # pragma: no cover - observer path
                        logger.debug(
                            "Unable to acknowledge API tool result",
                            exc_info=True,
                        )

        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})

        # Build the first user message. If a RenderedPrompt was passed and
        # it carries content parts, send the array form; otherwise fall
        # back to a plain text content (preserves the legacy contract).
        if isinstance(prompt, RenderedPrompt):
            if prompt.parts:
                messages.append({"role": "user", "content": prompt.parts})
            else:
                messages.append({"role": "user", "content": prompt.text})
        else:
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
                requires_audit_result = bool(
                    self.action_policy is not None
                    and getattr(self.action_policy, "auditor_session", False)
                    and self.audit_target is not None
                    and callable(self.audit_result_handler)
                )
                self._force_audit_finalization = bool(
                    requires_audit_result and turn == self.max_turns
                )
                if self._force_audit_finalization:
                    messages.append(
                        {"role": "user", "content": _AUDITOR_FINALIZATION_PROMPT}
                    )
                # Capture the last user/tool messages being sent this turn
                recent_msgs = []
                for m in reversed(messages):
                    if m.get("role") in ("user", "tool"):
                        recent_msgs.insert(0, m)
                    else:
                        break
                prompt_preview = (
                    "\n".join(
                        f"[{m.get('role')}] {(m.get('content') or '')[:500]}"
                        for m in recent_msgs
                    )
                    if recent_msgs
                    else "(system prompt + history)"
                )
                _emit(
                    turn,
                    "thinking",
                    f"Turn {turn}: calling {self.model}...",
                    prompt_preview,
                )

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
                        tc_name = fn.get("name", "?")
                        try:
                            parsed = json.loads(fn.get("arguments", "{}"))
                        except json.JSONDecodeError:
                            _emit(
                                turn,
                                "warning",
                                f"Dropping truncated tool call: {tc_name}",
                            )
                            continue
                        # Also drop if required args are missing (truncation mid-JSON)
                        required = _TOOL_REQUIRED_ARGS.get(tc_name, [])
                        missing = [a for a in required if a not in parsed]
                        if missing:
                            _emit(
                                turn,
                                "warning",
                                f"Dropping truncated tool call: {tc_name} (missing {', '.join(missing)})",
                            )
                            continue
                        valid_tcs.append(tc)
                    assistant_msg["tool_calls"] = valid_tcs or None

                messages.append(assistant_msg)

                content = assistant_msg.get("content") or ""
                if content:
                    last_message = content
                    _emit(turn, "message", content[:200], content)

                tool_calls = assistant_msg.get("tool_calls")
                if not tool_calls:
                    if requires_audit_result:
                        _emit(
                            turn,
                            "warning",
                            "Auditor stopped without committing a structured result",
                            (
                                "Continuing to the reserved finalization turn."
                                if turn < self.max_turns
                                else "Reserved finalization turn was exhausted."
                            ),
                        )
                        continue
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

                    # Handle ask_question specially — stop the agent loop
                    if tool_name == "ask_question":
                        question_text = tool_args.get("question", "")
                        if not question_text:
                            result_str = "Error: question text is required"
                            _emit(
                                turn,
                                "tool_result",
                                f"{tool_name} → {result_str}",
                                result_str,
                            )
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tc.get("id", ""),
                                    "content": result_str,
                                }
                            )
                            continue
                        # Guardrail: reject confirmation-seeking questions
                        lowered = question_text.lower()
                        if any(
                            phrase in lowered for phrase in _BLOCKED_QUESTION_PHRASES
                        ):
                            result_str = _ASK_QUESTION_REJECTION
                            _emit(
                                turn,
                                "tool_result",
                                "ask_question → Rejected (confirmation-seeking)",
                                result_str,
                            )
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tc.get("id", ""),
                                    "content": result_str,
                                }
                            )
                            continue
                        _emit(
                            turn,
                            "tool_result",
                            f"ask_question → Question posted, stopping agent",
                            f"Question: {question_text}",
                        )
                        return ApiAgentResult(
                            status="ask_question",
                            input_tokens=total_input,
                            output_tokens=total_output,
                            total_tokens=total_tokens,
                            turns=turns,
                            last_message=question_text,
                            question=question_text,
                            activity=activity,
                        )

                    # If JSON parsing failed, give the model a clear error
                    if not tool_args and raw_args not in ("{}", ""):
                        result_str = (
                            f"Error: malformed JSON in tool arguments for {tool_name}. "
                            f"Received: {raw_args[:200]}. "
                            f"Please provide valid JSON with the required arguments."
                        )
                    else:
                        env_overrides = (
                            None
                        )
                        result_str = await asyncio.to_thread(
                            _execute_tool,
                            self.workspace,
                            tool_name,
                            tool_args,
                            self.command_timeout,
                            env_overrides,
                            self.read_only,
                            self.task_tracker,
                            self.project_id,
                            self.task_identifier,
                            self.action_policy,
                            self.audit_target,
                            self.audit_result_handler,
                            self.tool_liveness,
                            self.policy_denial_handler,
                            self.command_output_store,
                            self.validation_lease,
                            is_cancelled,
                            self.successful_validation_handler,
                        )

                    tool_failed = result_str.startswith("Error")
                    _emit(
                        turn,
                        "tool_result",
                        f"{tool_name} → {result_str[:150]}",
                        result_str,
                    )

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.get("id", ""),
                            "content": result_str,
                        }
                    )

                    # Once the coordinator has accepted the structured
                    # verdict, the durable terminal boundary is complete.
                    # Do not spend another provider turn that could produce a
                    # second prose verdict or hit the ordinary ceiling before
                    # the result is acknowledged.
                    if (
                        tool_name == AUDITOR_RESULT_TOOL_NAME
                        and _audit_result_was_accepted(result_str)
                    ):
                        _emit(
                            turn,
                            "message",
                            "Auditor result committed; stopping session",
                            result_str,
                        )
                        return ApiAgentResult(
                            status="succeeded",
                            input_tokens=total_input,
                            output_tokens=total_output,
                            total_tokens=total_tokens,
                            turns=turns,
                            last_message=result_str,
                            activity=activity,
                        )

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
                    _emit(
                        turn,
                        "message",
                        f"Agent stalled: {turns_since_productive} turns with no writes or commands",
                    )
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

        except RateLimitError as exc:
            _emit(turns, "error", f"Rate limited: {exc}")
            logger.warning("ApiAgentSession.run_task rate limited: %s", exc)
            return ApiAgentResult(
                status="rate_limited",
                input_tokens=total_input,
                output_tokens=total_output,
                total_tokens=total_tokens,
                turns=turns,
                last_message=last_message,
                error=str(exc),
                activity=activity,
            )
        except TransientServerError as exc:
            # _call_api's 5-attempt retry loop exhausted on a transient
            # 5xx / network-level failure (ENOTCONN/ECONNRESET/EPIPE
            # wrapped by _http_post, connection refused, DNS blip, etc.)
            # or a 401 authentication error (expired/revoked token).
            #
            # Log at WARNING — not ERROR — so the error_watcher does not
            # auto-file duplicate bug tasks for transient errors the
            # orchestrator already handles by re-dispatching the worker.
            # Mirrors the RateLimitError handler above and the
            # TrackerTimeoutError WARNING pattern in oompah/tracker.py.
            #
            # oompah-zlz_2-e6t5: 401 auth errors are a subset of
            # TransientServerError — distinguish them for operator
            # ergonomics. A 401 on the first attempt is almost always an
            # invalid API key (operator misconfiguration), not a server
            # blip, so emit a slightly more specific log name so the
            # operator can grep for "auth_error" to find these quickly.
            auth_err = exc.status_code == 401
            if auth_err:
                _emit(turns, "error", f"auth_error: {exc}")
                logger.warning(
                    "ApiAgentSession.run_task auth_error (401): %s",
                    exc,
                )
            else:
                _emit(turns, "error", str(exc))
                logger.warning(
                    "ApiAgentSession.run_task transient_error: %s",
                    exc,
                )
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
        except OSError as exc:
            # Defense-in-depth (oompah-zlz_2-bpa): the canonical fix for
            # raw socket errors lives in ``_http_post`` (ovt: ENOTCONN /
            # ECONNRESET / EPIPE wrapped as TransientServerError so the
            # 5-retry loop in ``_call_api`` can recover). If a raw OSError
            # ever leaks past those retries — either because retries are
            # exhausted on a sustained outage or because some new code
            # path bypasses ``_http_post`` — keep the bare ``[Errno N]``
            # repr out of the log line so error_watcher fingerprints
            # cleanly into a single "transport_error" task instead of
            # duplicating the historic '[Errno 57] Socket is not
            # connected' title pattern that ovt already fixed at the
            # source.
            #
            # hp2 cleanup (oompah-zlz_2-hp2): split the user-facing
            # ``msg`` (which keeps the ``transport_error:`` prefix so
            # ``result.error`` and the activity panel are descriptive)
            # from the log args (which carry only ``[Errno N] strerror``
            # so the format string's existing ``transport_error:`` prefix
            # doesn't render twice — matching the rate_limited /
            # transient_error log patterns above).
            detail = f"[Errno {exc.errno}] {exc.strerror or exc}"
            msg = f"transport_error: {detail}"
            _emit(turns, "error", msg)
            logger.error(
                "ApiAgentSession.run_task transport_error: %s",
                detail,
            )
            return ApiAgentResult(
                status="failed",
                input_tokens=total_input,
                output_tokens=total_output,
                total_tokens=total_tokens,
                turns=turns,
                last_message=last_message,
                error=msg,
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
        """Make one chat completions call with automatic rate-limit retry.

        When :attr:`model_max_context` is set, prunes the oldest
        assistant/tool round-trips out of ``messages`` (in place) until
        the estimated outgoing payload fits, then sets ``max_tokens``
        to the remaining headroom (clamped to a sensible floor).
        """
        tool_defs = self._tool_definitions
        tool_choice: str | dict[str, Any] = "auto"
        if self._force_audit_finalization:
            tool_defs = [
                tool
                for tool in tool_defs
                if tool.get("function", {}).get("name") == AUDITOR_RESULT_TOOL_NAME
            ]
            tool_choice = {
                "type": "function",
                "function": {"name": AUDITOR_RESULT_TOOL_NAME},
            }
        max_tokens = _DEFAULT_MAX_OUTPUT_TOKENS
        if self.model_max_context:
            # Reserve at least the floor for output, plus the safety margin.
            max_input = (
                self.model_max_context
                - _MIN_MAX_OUTPUT_TOKENS
                - _TOKENIZER_SAFETY_MARGIN
            )
            removed = _prune_messages_to_fit(messages, tool_defs, max_input)
            if removed:
                logger.warning(
                    "ApiAgentSession: pruned %d oldest message(s) to fit %d-token context window",
                    removed,
                    self.model_max_context,
                )
            est_input = _estimate_tokens({"messages": messages, "tools": tool_defs})
            headroom = self.model_max_context - est_input - _TOKENIZER_SAFETY_MARGIN
            max_tokens = max(
                _MIN_MAX_OUTPUT_TOKENS, min(_DEFAULT_MAX_OUTPUT_TOKENS, headroom)
            )
        payload = {
            "model": self.model,
            "messages": messages,
            "tools": tool_defs,
            "tool_choice": tool_choice,
            "max_tokens": max_tokens,
        }
        # Log the full outgoing payload (without auth headers) so the
        # exact prompt the model receives is recoverable from disk.
        self._log_event("request", payload=payload)
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "oompah/0.1",
        }
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        max_retries = 5
        for attempt in range(max_retries):
            try:
                response = await asyncio.to_thread(
                    _http_post, self._url, headers, body, self._ssl_ctx
                )
                # Mirror of the "request" log above so each turn has a
                # complete sent/received pair on disk.
                self._log_event(
                    "response",
                    attempt=attempt,
                    body=response,
                )
                return response
            except RateLimitError as exc:
                self._log_event(
                    "rate_limit",
                    attempt=attempt,
                    retry_after=exc.retry_after,
                    error=str(exc),
                )
                if attempt >= max_retries - 1:
                    raise
                # Use Retry-After if provided, otherwise exponential backoff
                delay = (
                    exc.retry_after if exc.retry_after > 0 else min(2**attempt * 5, 120)
                )
                logger.warning(
                    "Rate limited (attempt %d/%d), retrying in %.0fs: %s",
                    attempt + 1,
                    max_retries,
                    delay,
                    exc,
                )
                await asyncio.sleep(delay)
            except TransientServerError as exc:
                # 5xx, connection refused, network blip — retry with
                # exponential backoff. Cheaper than failing back up to
                # the orchestrator (which rebuilds the whole conversation
                # on retry); preserves the agent's in-progress context.
                self._log_event(
                    "transient_error",
                    attempt=attempt,
                    status_code=exc.status_code,
                    error=str(exc),
                )
                if attempt >= max_retries - 1:
                    raise
                # 1s, 2s, 4s, 8s, capped at 30s. Faster ramp than rate
                # limits since 5xx/network blips usually clear quickly.
                delay = min(2**attempt, 30)
                logger.warning(
                    "Transient server error (attempt %d/%d), retrying in %.0fs: %s",
                    attempt + 1,
                    max_retries,
                    delay,
                    exc,
                )
                await asyncio.sleep(delay)
            except RuntimeError as exc:
                # oompah-zlz_2-vwrp: a 400 caused by an oversized prompt
                # carries the model's actual context window in the error
                # body. Extract it, enable session budgeting, prune the
                # messages, and retry once — all within the same worker
                # turn so the orchestrator never sees a failure.
                # If this is not a context-window error, propagate
                # immediately (permanent client failure).
                error_body = str(exc)
                self._log_event(
                    "context_window_error",
                    attempt=attempt,
                    error=error_body,
                )
                if not _is_context_window_error(error_body):
                    raise
                if attempt >= 1:
                    # Already retried once; don't loop.
                    raise
                ctx_limit = _extract_context_window_limit(error_body)
                if ctx_limit is None:
                    logger.warning(
                        "ApiAgentSession: context-window 400 but limit not in error body; "
                        "retrying with conservative fallback (128 k tokens)",
                    )
                    ctx_limit = 131072
                if self.model_max_context is None:
                    logger.warning(
                        "ApiAgentSession: learned context-window limit %d from error "
                        "response; enabling pruning on this session",
                        ctx_limit,
                    )
                    self.model_max_context = ctx_limit
                # Budget with the discovered limit.
                max_input = ctx_limit - _MIN_MAX_OUTPUT_TOKENS - _TOKENIZER_SAFETY_MARGIN
                removed = _prune_messages_to_fit(messages, tool_defs, max_input)
                logger.warning(
                    "ApiAgentSession: pruned %d message(s) to fit %d-token context window "
                    "(learned from 400 response)",
                    removed,
                    ctx_limit,
                )
                est_input = _estimate_tokens({"messages": messages, "tools": tool_defs})
                headroom = ctx_limit - est_input - _TOKENIZER_SAFETY_MARGIN
                max_tokens = max(
                    _MIN_MAX_OUTPUT_TOKENS, min(_DEFAULT_MAX_OUTPUT_TOKENS, headroom)
                )
                payload["max_tokens"] = max_tokens
                self._log_event(
                    "context_window_retry",
                    pruned=removed,
                    max_tokens=max_tokens,
                    remaining_messages=len(messages),
                )
                body = json.dumps(payload).encode("utf-8")
                continue
