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
import re
import ssl
import subprocess
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from oompah.prompt import RenderedPrompt

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

    cmd = (
        ["grep", "-rn", "--include", include, pattern, str(search_path)]
        if include
        else ["grep", "-rn", pattern, str(search_path)]
    )
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
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
    timeout: int = 60,
    env_overrides: dict[str, str] | None = None,
) -> str:
    command = args["command"]
    cd_err = _validate_command_stays_in_workspace(command, workspace)
    if cd_err:
        return f"Error: {cd_err}"
    # Build env from the agent's own env, layering caller-supplied overrides
    # on top. Used most importantly to set ``BEADS_DIR`` so that any ``bd``
    # commands the agent runs operate on the project's main beads database
    # rather than the worktree's forked dolt copy. Without this, agent-side
    # ``bd close`` succeeds in the worktree but is invisible to the
    # orchestrator, and dispatch storms occur.
    env = None
    if env_overrides:
        env = {**os.environ, **env_overrides}
    try:
        result = subprocess.run(
            ["bash", "-lc", command],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
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


def _exec_attach_image(workspace: Path, args: dict[str, Any]) -> str:
    """Decode a base64 image into the workspace's
    .oompah/attachments/<issue>/outputs/ directory, named
    ``<turn>-<sha>-<filename>``. Returns the canonical relative path on
    success, or an error string. The orchestrator commits these on agent
    completion (see Phase 3, oompah-e6y.3) and writes back to beads
    metadata (oompah-e6y.4)."""
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
_OPT_IN_TOOLS: frozenset[str] = frozenset({"attach_image"})


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
    "list_files": [],
    "ask_question": ["question"],
    "attach_image": ["issue_identifier", "filename", "content_base64"],
}


def _execute_tool(
    workspace: Path,
    name: str,
    args: dict[str, Any],
    cmd_timeout: int = 60,
    env_overrides: dict[str, str] | None = None,
) -> str:
    """Execute a tool call and return its string result.

    ``env_overrides`` is forwarded to ``run_command`` only — the file/edit
    tools don't spawn subprocesses, so it has no effect on them.
    """
    handler = _TOOL_DISPATCH.get(name)
    if handler is None:
        # Models occasionally lift a shell command out of the WORKFLOW.md
        # cheat sheet and call it as a tool name (e.g. ``bd comments add``
        # with spaces, or ``git commit``). Detect that and redirect them
        # to ``run_command`` instead of leaving them to loop on the bare
        # "unknown tool" message.
        looks_like_shell = " " in name or name.startswith(
            ("bd", "bd_", "git", "git_", "uv ", "make")
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
        if name == "run_command":
            return handler(
                workspace,
                args,
                timeout=cmd_timeout,
                env_overrides=env_overrides,
            )
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
# For model_max_context ≥ 131072 this is a fixed reservation; for smaller
# windows it scales proportionally so _call_api's budget never goes
# negative (guaranteeing pruning always has a meaningful budget).
_MIN_MAX_OUTPUT_TOKENS = 2048
# Extra safety margin on top of _estimate_tokens() to absorb tokenizer
# approximation drift. Scales proportionally with context size to avoid
# starving small-window budgets.
_TOKENIZER_SAFETY_MARGIN = 3072


def _estimate_tokens(payload: object) -> int:
    """Approximate token count for an arbitrary JSON-serializable object.

    Uses the well-known 3-chars-per-token rule of thumb, which is slightly
    more conservative than the common 4-char estimate and helps ensure
    pruning triggers well before the real token count exhausts the model's
    context window. The caller pads the result with
    :data:`_TOKENIZER_SAFETY_MARGIN` when budgeting.
    """
    try:
        s = json.dumps(payload, ensure_ascii=False)
    except (TypeError, ValueError):
        s = str(payload)
    return max(1, len(s) // 3)


_CONTEXT_WINDOW_RE = re.compile(
    r"maximum context length is (\d+) tokens",
)


def _extract_context_window_limit(error_body: str) -> int | None:
    """Extract the context-window limit (tokens) from a
    ``ContextWindowExceededError`` error body.

    Handles the litellm-wrapped nested-JSON format seen at
    ``https://inference-api.nvidia.com/v1/chat/completions``::

        {"error":{"message":"... ContextWindowExceededError: ...
            \"maximum context length is 131072 tokens.\"..."}}

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
    """Return True when *error_body* describes a ``ContextWindowExceededError``."""
    return "ContextWindowExceededError" in error_body


# Proportional reserve scale factor: reserve ~87.5% of context for input tokens
# when margins would otherwise consume too much on small windows.
_INPUT_TOKEN_BUDGET_RATIO = 0.875


def _context_reserves(ctx: int) -> tuple[int, int]:
    """Return (min_output_reserve, tokenizer_safety_margin) for *ctx*.

    For large contexts (≥ 131072) the fixed absolute values are used,
    keeping pruning conservative. For smaller windows the margins are
    capped proportionally so that max_input = ctx * 0.875 remains positive
    and guarantees pruning always has a meaningful budget to work with.
    """
    if ctx >= 131072:
        return (_MIN_MAX_OUTPUT_TOKENS, _TOKENIZER_SAFETY_MARGIN)
    # Proportional: guarantee max_input >= ctx * _INPUT_TOKEN_BUDGET_RATIO
    return (int(ctx * 0.016), int(ctx * 0.025))


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
        command_timeout: int = 60,
        enabled_tools: set[str] | None = None,
        model_max_context: int | None = None,
        log_path: str | None = None,
        beads_dir: str | None = None,
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
        # Names of tools to expose to the model. ``None`` means "all
        # tools except those that require explicit opt-in" — currently
        # ``attach_image`` is the only opt-in tool, so it's filtered out
        # by default. The orchestrator passes an explicit set when the
        # active focus opts in and the resolved model has the image
        # capability.
        self.enabled_tools = enabled_tools
        # Total context window for ``model`` (input + output, in tokens).
        # When set, _call_api budgets each request: prunes the oldest
        # assistant/tool round-trips if the prompt would overflow, and
        # clamps max_tokens to fit within the remaining headroom. When
        # None, behaviour falls back to the legacy fixed max_tokens.
        self.model_max_context = model_max_context
        # Path to a JSONL file recording every request, response, and
        # activity event for this dispatch. None disables file logging.
        self.log_path = log_path
        # When set, every ``bd`` command the agent runs via run_command
        # gets ``BEADS_DIR=<beads_dir>`` in its env, so writes land in
        # the orchestrator's source-of-truth DB rather than the agent's
        # worktree-forked dolt. Without this, ``bd close`` succeeds in
        # the worktree but is invisible to the orchestrator → dispatch
        # storms (oompah-zlz_2-{07h,529,etc} pattern observed).
        self.beads_dir = beads_dir

        self._ssl_ctx = _build_ssl_context()
        self._url = f"{self.base_url}/chat/completions"

    def _log_event(self, kind: str, **fields: Any) -> None:
        """Append one JSONL record to ``self.log_path`` (best-effort).

        Each record is a single-line JSON object with ``ts`` (UTC ISO),
        ``kind`` (e.g. "session_start", "request", "response",
        "activity", "session_end"), and any extra fields the caller
        passes. Failures are swallowed so logging never disrupts a
        running agent. ``api_key`` and HTTP headers are never written.
        """
        if not self.log_path:
            return
        try:
            record = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "kind": kind,
                **fields,
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
        if self.enabled_tools is None:
            return [
                t
                for t in TOOL_DEFINITIONS
                if t["function"]["name"] not in _OPT_IN_TOOLS
            ]
        return [
            t for t in TOOL_DEFINITIONS if t["function"]["name"] in self.enabled_tools
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
            entry = AgentActivity(
                turn=turn,
                kind=kind,
                summary=summary,
                detail=detail,
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
                summary=summary,
                detail=detail,
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
                            {"BEADS_DIR": self.beads_dir} if self.beads_dir else None
                        )
                        result_str = await asyncio.to_thread(
                            _execute_tool,
                            self.workspace,
                            tool_name,
                            tool_args,
                            self.command_timeout,
                            env_overrides,
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
            # auto-file duplicate bug beads for transient errors the
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
            # cleanly into a single "transport_error" bead instead of
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
        max_tokens = _DEFAULT_MAX_OUTPUT_TOKENS
        if self.model_max_context:
            # Reserve at least the floor for output, plus the safety margin.
            min_out, safety = _context_reserves(self.model_max_context)
            max_input = self.model_max_context - min_out - safety
            removed = _prune_messages_to_fit(messages, tool_defs, max_input)
            if removed:
                logger.warning(
                    "ApiAgentSession: pruned %d oldest message(s) to fit %d-token context window",
                    removed,
                    self.model_max_context,
                )
            est_input = _estimate_tokens({"messages": messages, "tools": tool_defs})
            headroom = self.model_max_context - est_input - safety
            max_tokens = max(
                _MIN_MAX_OUTPUT_TOKENS, min(_DEFAULT_MAX_OUTPUT_TOKENS, headroom)
            )
        payload = {
            "model": self.model,
            "messages": messages,
            "tools": tool_defs,
            "tool_choice": "auto",
            "max_tokens": max_tokens,
        }
        # Log the full outgoing payload (without auth headers) so the
        # exact prompt the model receives is recoverable from disk.
        self._log_event("request", payload=payload)
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
            "User-Agent": "oompah/0.1",
        }

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
                min_out, safety = _context_reserves(ctx_limit)
                max_input = ctx_limit - min_out - safety
                removed = _prune_messages_to_fit(messages, tool_defs, max_input)
                logger.warning(
                    "ApiAgentSession: pruned %d message(s) to fit %d-token context window "
                    "(learned from 400 response)",
                    removed,
                    ctx_limit,
                )
                est_input = _estimate_tokens({"messages": messages, "tools": tool_defs})
                headroom = ctx_limit - est_input - safety
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
