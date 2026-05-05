"""ACP-mode agent execution path.

Drives the bundled `claude` CLI (via the Claude Agent SDK) as a subprocess
so the per-token cost is billed against the operator's Pro/Max
subscription rather than the per-token API meter that the api_agent path
incurs. See ``docs/acp-agent.md`` and bead ``oompah-zlz_2-bcl``.

The class shape mirrors :class:`oompah.api_agent.ApiAgentSession` so
``_run_acp_worker`` in the orchestrator can be a thin variant of
``_run_api_worker``: same observable surface (token counters, run_task
return shape, terminate semantics, JSONL event stream).

Key architectural decisions (locked in via the bead's Q&A in
docs/acp-agent.md):

* **Tool bridging (Q2 = B).** The SDK's ``ClaudeAgentOptions.mcp_servers``
  takes an in-process MCP server. We declare oompah's existing tool
  catalog (read_file / edit_file / write_file / run_command /
  search_files / list_files / bd_*) as ``@tool``-decorated functions
  and intercept their execution. That keeps the cd-out-of-worktree
  guard, shell-as-tool-name redirect, and BEADS_DIR routing in force —
  none of those exist in claude's native tools.
* **Permissions (Q4).** Auto-accept everything via
  ``ClaudeAgentOptions.permission_mode='bypassPermissions'`` (the SDK's
  equivalent of ``--dangerously-skip-permissions``). Each agent's
  per-issue JSONL log records the bypass at session start so the
  agent_watcher (planned in docs/agent-watcher.md) has a paper trail.
* **Budget tracking (Q3).** Token usage IS reported by the SDK in
  ``AssistantMessage.usage`` and ``ResultMessage.total_cost_usd``, so
  we DO populate the session counters. Whether the orchestrator's
  budget gate ENFORCES against ACP profiles is a separate decision
  upstream (see ``_run_acp_worker``); the session itself reports
  honestly.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from oompah.agent import AgentEvent, AgentError

logger = logging.getLogger(__name__)


# Hard cap on how long a single ACP turn can run before we yank the
# subprocess. Mirrors api_agent's stall watchdog cadence — the SDK's
# own timeout is much longer.
_DEFAULT_TURN_TIMEOUT_S = 3600.0


@dataclass
class _SessionCounters:
    """Token-usage counters scraped from SDK messages.

    The SDK reports usage in two places:

    * Each ``AssistantMessage`` has a ``usage`` dict (per-message tokens).
    * The terminal ``ResultMessage`` has ``usage`` and ``total_cost_usd``
      with the rolled-up session totals.

    We accumulate from AssistantMessage so live monitoring works, and
    cross-check against ResultMessage at end-of-turn.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    last_reported_input_tokens: int = 0
    last_reported_output_tokens: int = 0
    last_reported_total_tokens: int = 0
    turn_count: int = 0
    last_event: str | None = None

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def absorb_assistant_usage(self, usage: dict[str, Any] | None) -> None:
        if not isinstance(usage, dict):
            return
        # The SDK forwards Anthropic's usage shape: input_tokens /
        # output_tokens / cache_creation_input_tokens /
        # cache_read_input_tokens. Sum everything we see.
        self.input_tokens += int(usage.get("input_tokens", 0) or 0)
        self.output_tokens += int(usage.get("output_tokens", 0) or 0)
        self.cache_creation_input_tokens += int(
            usage.get("cache_creation_input_tokens", 0) or 0
        )
        self.cache_read_input_tokens += int(
            usage.get("cache_read_input_tokens", 0) or 0
        )


class AcpAgentSession:
    """Run one issue's worth of work via the Claude Agent SDK.

    Public surface intentionally mirrors :class:`ApiAgentSession`:

        * ``run_task(prompt, on_event=...)`` returns a status string
        * ``terminate()`` stops the subprocess
        * ``input_tokens`` / ``output_tokens`` / ``total_tokens``

    The SDK manages the subprocess lifecycle for us. We layer our own
    tool dispatch, JSONL logging, and stall detection on top.
    """

    def __init__(
        self,
        workspace_path: str,
        prompt: str,
        *,
        model: str | None = None,
        fallback_model: str | None = None,
        max_turns: int | None = None,
        env: dict[str, str] | None = None,
        tool_catalog: list[Any] | None = None,
        on_event: Callable[[AgentEvent], None] | None = None,
        turn_timeout_s: float = _DEFAULT_TURN_TIMEOUT_S,
    ):
        self.workspace_path = workspace_path
        self.prompt = prompt
        self.model = model
        self.fallback_model = fallback_model
        self.max_turns = max_turns
        self.env = env or {}
        self.tool_catalog = tool_catalog or []
        self.on_event = on_event
        self.turn_timeout_s = turn_timeout_s

        self._counters = _SessionCounters()
        self._client: Any = None  # claude_agent_sdk.ClaudeSDKClient
        self._stop_requested = False
        self._session_id: str | None = None
        self._final_cost_usd: float | None = None
        # Permission denials are tracked by the SDK's ResultMessage; we
        # keep them here so callers can report on them.
        self.permission_denials: list[Any] = []
        # Last error string, if the session ended in an error.
        self.last_error: str | None = None

    # ------------------------------------------------------------------
    # Public properties expected by orchestrator (mirrors api_agent)
    # ------------------------------------------------------------------

    @property
    def input_tokens(self) -> int:
        return self._counters.input_tokens

    @property
    def output_tokens(self) -> int:
        return self._counters.output_tokens

    @property
    def total_tokens(self) -> int:
        return self._counters.total_tokens

    @property
    def session_id(self) -> str | None:
        return self._session_id

    @property
    def turn_count(self) -> int:
        return self._counters.turn_count

    @property
    def total_cost_usd(self) -> float | None:
        """Whatever the SDK's ResultMessage reported (subscription-billed
        runs typically report 0 here; pay-as-you-go reports the real
        amount). Available only after the turn completes."""
        return self._final_cost_usd

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def run_task(self) -> str:
        """Open a session, send the prompt, drive the message stream,
        return when the SDK signals completion. Returns one of:

            * ``"succeeded"`` — terminal ResultMessage with no error
            * ``"failed"`` — terminal ResultMessage with an error
            * ``"stalled"`` — turn_timeout_s exceeded; subprocess killed
            * ``"interrupted"`` — orchestrator called ``terminate()``
            * ``"errored"`` — SDK / subprocess crashed unexpectedly

        ``on_event`` (if set) is called with :class:`AgentEvent` for
        every interesting message — assistant text, tool use, tool
        result, permission grant. Mirrors the api_agent observation
        surface so per-agent JSONL logging plugs in unchanged.
        """
        try:
            # Lazy import: keep the SDK out of the import path of
            # modules that don't actually use ACP.
            from claude_agent_sdk import (
                ClaudeAgentOptions,
                ClaudeSDKClient,
                AssistantMessage,
                ResultMessage,
                UserMessage,
                TextBlock,
                ToolUseBlock,
                ToolResultBlock,
                ThinkingBlock,
            )
        except ImportError as exc:
            self.last_error = f"claude_agent_sdk not installed: {exc}"
            logger.error(self.last_error)
            return "errored"

        # Compose the env we want claude to see. The orchestrator already
        # sets BEADS_DIR for the current process; we forward it explicitly
        # so claude's run_command tool inherits the right value.
        agent_env = dict(os.environ)
        agent_env.update(self.env)

        # Permission mode: NOT "bypassPermissions". That mode bypasses
        # the can_use_tool callback entirely, which is exactly the
        # mechanism we use to force claude through our MCP-bridged
        # catalog (vs its native Bash/Read/Write/etc.). With "default"
        # mode every tool call routes through can_use_tool, which
        # auto-allows ``mcp__oompah__*`` and auto-denies everything
        # else. No human-in-the-loop prompts because the callback
        # always returns a definitive decision. See
        # docs/acp-agent.md and oompah-zlz_2-bcl.6.
        from claude_agent_sdk import (
            PermissionResultAllow,
            PermissionResultDeny,
        )

        async def _can_use_tool(
            tool_name: str,
            tool_input: dict[str, Any],
            context: Any,
        ) -> Any:
            """Strict allowlist: only oompah's MCP-bridged catalog is
            permitted. Claude's native built-ins (Bash, Read, Write,
            Edit, Glob, Grep, WebFetch, ...) are denied so cd-guard,
            BEADS_DIR routing, and shell-redirect stay in force.

            Every grant and deny is emitted to per-agent JSONL so the
            agent_watcher (planned in docs/agent-watcher.md) can audit
            the tool surface after the fact.
            """
            allowed = tool_name.startswith("mcp__oompah__")
            event_kind = (
                "acp_permission_grant" if allowed else "acp_permission_deny"
            )
            try:
                self._emit(
                    event_kind,
                    payload={
                        "tool": tool_name,
                        "input": _truncate_for_log(tool_input),
                    },
                )
            except Exception:
                pass
            if allowed:
                return PermissionResultAllow()
            return PermissionResultDeny(
                message=(
                    f"Tool {tool_name!r} is not in oompah's allowed catalog. "
                    f"Use one of mcp__oompah__* (read_file, write_file, "
                    f"edit_file, list_files, search_files, run_command) "
                    f"so safety rails (cd-guard, BEADS_DIR routing) apply."
                ),
                interrupt=False,
            )

        # Hard-block claude's native built-in tools at the SDK config
        # layer. We tried doing this via can_use_tool alone — turns out
        # the callback only intercepts MCP-bridged tool calls; native
        # built-ins (Bash, Read, Write, Edit, Glob, Grep, WebFetch, ...)
        # are auto-allowed by the SDK without consulting the callback.
        # disallowed_tools is the exhaustive denylist that DOES gate
        # them. Keep this in sync with claude's built-in surface; new
        # tools Anthropic adds will need explicit entries here OR an
        # opt-in via a future profile field.
        _CLAUDE_NATIVE_BUILTINS = [
            "Bash",
            "BashOutput",
            "Edit",
            "Glob",
            "Grep",
            "KillShell",
            "ListMcpResourcesTool",
            "NotebookEdit",
            "Read",
            "ReadMcpResourceTool",
            "SlashCommand",
            "Task",
            "TodoWrite",
            "WebFetch",
            "WebSearch",
            "Write",
        ]

        options_kwargs: dict[str, Any] = {
            "system_prompt": self.prompt,
            "cwd": self.workspace_path,
            "env": agent_env,
            "permission_mode": "default",
            "can_use_tool": _can_use_tool,
            # Force tool dispatch through oompah's MCP catalog by hard-
            # blocking everything claude ships natively. The
            # can_use_tool callback above is the audit/log layer for
            # the MCP-bridged calls that ARE allowed.
            "disallowed_tools": _CLAUDE_NATIVE_BUILTINS,
        }
        if self.model:
            options_kwargs["model"] = self.model
        if self.fallback_model:
            options_kwargs["fallback_model"] = self.fallback_model
        if self.max_turns:
            options_kwargs["max_turns"] = int(self.max_turns)
        if self.tool_catalog:
            # tool_catalog is a list of mcp.SdkMcpTool produced by the
            # SDK's @tool decorator. Wrap in a server config so claude
            # can call them — but the actual gate is can_use_tool above.
            from claude_agent_sdk import create_sdk_mcp_server

            server = create_sdk_mcp_server(
                name="oompah-tools",
                version="0.1.0",
                tools=self.tool_catalog,
            )
            options_kwargs["mcp_servers"] = {"oompah": server}

        options = ClaudeAgentOptions(**options_kwargs)

        # Emit a one-time "ACP session starting" event so the JSONL log
        # records the permission policy and the model selection.
        # agent_watcher will use this as the session anchor.
        self._emit(
            "acp_session_start",
            payload={
                "model": self.model,
                "fallback_model": self.fallback_model,
                "max_turns": self.max_turns,
                "permission_mode": "default",
                "tool_policy": "strict_allowlist:mcp__oompah__*",
                "tool_catalog": [
                    getattr(t, "name", str(t)) for t in self.tool_catalog
                ],
                "disallowed_native_tools": list(_CLAUDE_NATIVE_BUILTINS),
                "cwd": self.workspace_path,
            },
        )

        try:
            async with ClaudeSDKClient(options=options) as client:
                self._client = client

                # Send the prompt that drives the run.
                await client.query(self.prompt)

                deadline = time.monotonic() + self.turn_timeout_s
                async for msg in client.receive_response():
                    if self._stop_requested:
                        return "interrupted"
                    if time.monotonic() > deadline:
                        # Stalled — let the orchestrator escalate / retry.
                        self._emit(
                            "acp_turn_timeout",
                            payload={"timeout_s": self.turn_timeout_s},
                        )
                        return "stalled"

                    # ---- Assistant: text, thinking, tool use ----
                    if isinstance(msg, AssistantMessage):
                        self._counters.turn_count += 1
                        self._counters.absorb_assistant_usage(msg.usage)
                        if msg.error:
                            self.last_error = str(msg.error)
                            self._emit(
                                "acp_assistant_error",
                                payload={"error": msg.error},
                            )
                        for block in msg.content or []:
                            if isinstance(block, TextBlock):
                                self._counters.last_event = "text"
                                self._emit(
                                    "acp_text",
                                    payload={"text": (block.text or "")[:2000]},
                                )
                            elif isinstance(block, ThinkingBlock):
                                self._counters.last_event = "thinking"
                                self._emit(
                                    "acp_thinking",
                                    payload={
                                        "text": (
                                            getattr(block, "thinking", "") or ""
                                        )[:2000]
                                    },
                                )
                            elif isinstance(block, ToolUseBlock):
                                self._counters.last_event = "tool_use"
                                self._emit(
                                    "acp_tool_use",
                                    payload={
                                        "tool": block.name,
                                        "input": _truncate_for_log(block.input),
                                        "id": block.id,
                                    },
                                )

                    # ---- User-side tool results (echoes from the SDK) ----
                    elif isinstance(msg, UserMessage):
                        if isinstance(msg.content, list):
                            for block in msg.content:
                                if isinstance(block, ToolResultBlock):
                                    self._counters.last_event = "tool_result"
                                    self._emit(
                                        "acp_tool_result",
                                        payload={
                                            "tool_use_id": block.tool_use_id,
                                            "is_error": bool(block.is_error),
                                            "content": _truncate_for_log(
                                                block.content
                                            ),
                                        },
                                    )

                    # ---- Terminal ----
                    elif isinstance(msg, ResultMessage):
                        self._session_id = msg.session_id
                        self._final_cost_usd = msg.total_cost_usd
                        if msg.permission_denials:
                            self.permission_denials = list(msg.permission_denials)
                        if msg.usage:
                            # ResultMessage.usage may correct for prefix-cache
                            # reads etc. Trust it as the final word.
                            try:
                                self._counters.input_tokens = int(
                                    msg.usage.get(
                                        "input_tokens", self._counters.input_tokens
                                    )
                                )
                                self._counters.output_tokens = int(
                                    msg.usage.get(
                                        "output_tokens", self._counters.output_tokens
                                    )
                                )
                            except (TypeError, ValueError):
                                pass
                        self._emit(
                            "acp_result",
                            payload={
                                "subtype": msg.subtype,
                                "is_error": msg.is_error,
                                "stop_reason": msg.stop_reason,
                                "duration_ms": msg.duration_ms,
                                "num_turns": msg.num_turns,
                                "total_cost_usd": msg.total_cost_usd,
                                "errors": msg.errors,
                            },
                        )
                        if msg.is_error:
                            self.last_error = (
                                "; ".join(msg.errors) if msg.errors else "errored"
                            )
                            return "failed"
                        return "succeeded"

                # Stream ended without a ResultMessage — treat as error.
                self.last_error = "stream ended without ResultMessage"
                return "errored"
        except Exception as exc:
            # SDK / subprocess failure. Don't crash the worker — log
            # and let the orchestrator retry.
            self.last_error = f"{type(exc).__name__}: {exc}"
            logger.warning("ACP session failed: %s", self.last_error)
            self._emit("acp_session_error", payload={"error": self.last_error})
            return "errored"
        finally:
            self._client = None

    async def terminate(self) -> None:
        """Request that the active session stop. Safe to call multiple
        times. The SDK's context manager cleans up the subprocess on
        exit; this just signals the receive_response loop to break."""
        self._stop_requested = True
        client = self._client
        if client is not None:
            with contextlib.suppress(Exception):
                await client.interrupt()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _emit(self, kind: str, *, payload: dict[str, Any] | None = None) -> None:
        """Emit one structured AgentEvent to the registered callback (if any).
        Mirrors api_agent's hooks so per-agent JSONL logging works
        unchanged."""
        if self.on_event is None:
            return
        ev = AgentEvent(
            event=kind,
            timestamp=time.time(),
            agent_pid=None,
            usage={
                "input_tokens": self._counters.input_tokens,
                "output_tokens": self._counters.output_tokens,
                "total_tokens": self._counters.total_tokens,
            },
            payload=payload or {},
        )
        try:
            self.on_event(ev)
        except Exception as exc:  # pragma: no cover — observer's bug
            logger.debug("on_event observer raised: %s", exc)


def _truncate_for_log(value: Any, limit: int = 1500) -> Any:
    """Shrink large tool inputs/outputs before they hit the JSONL log so
    a 10 MB shell-pipe doesn't bloat the log file. Preserves shape for
    dicts/lists; truncates string leaves with an ellipsis."""
    if isinstance(value, str):
        return value if len(value) <= limit else (value[:limit] + " …[truncated]")
    if isinstance(value, dict):
        return {k: _truncate_for_log(v, limit) for k, v in value.items()}
    if isinstance(value, list):
        return [_truncate_for_log(v, limit) for v in value]
    return value
