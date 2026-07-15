"""Claude Agent SDK backend (the historical default).

Wraps the bundled ``claude`` CLI via the Claude Agent SDK so per-token
costs bill against the operator's Pro/Max subscription rather than
the per-token API meter that the api_agent path incurs. This file
contains ALL of the SDK-specific code that previously lived inline in
``oompah/acp_agent.py``; the latter is now a backend-agnostic facade
that looks the backend up through the registry.

See ``plans/acp-agent.md`` and task ``oompah-zlz_2-bcl`` for the
architectural decisions that locked in the strict-allowlist tool
policy and the can_use_tool / disallowed_tools dual-gating mechanism.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import tempfile
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator, TYPE_CHECKING

from oompah.acp_backends.base import (
    AcpBackend,
    AcpBackendOptions,
    AcpBackendSession,
    BackendEvent,
)
from oompah.acp_backends.registry import register_backend
from oompah.agent import AgentEvent

if TYPE_CHECKING:
    from oompah.models import ModelProvider

logger = logging.getLogger(__name__)


# Hard-block claude's native built-in tools at the SDK config layer. We
# tried doing this via can_use_tool alone — turns out the callback only
# intercepts MCP-bridged tool calls; native built-ins (Bash, Read,
# Write, Edit, Glob, Grep, WebFetch, ...) are auto-allowed by the SDK
# without consulting the callback. disallowed_tools is the exhaustive
# denylist that DOES gate them. Keep this in sync with claude's
# built-in surface; new tools Anthropic adds will need explicit entries
# here OR an opt-in via a future profile field.
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
    "ToolSearch",
    "WebFetch",
    "WebSearch",
    "Write",
]


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


class ClaudeAcpBackendSession(AcpBackendSession):
    """Claude-SDK-driven session handle.

    Implements the :class:`AcpBackendSession` protocol. Internally
    drives ``claude_agent_sdk.ClaudeSDKClient`` with our strict-
    allowlist permission policy and yields :class:`BackendEvent`
    objects from :meth:`run_turn`. Also calls ``options.on_event``
    (when set) with translated :class:`AgentEvent` objects for
    back-compat with the orchestrator's JSONL-logging path.
    """

    def __init__(self, options: AcpBackendOptions):
        self._options = options
        self._counters = _SessionCounters()
        self._client: Any = None  # claude_agent_sdk.ClaudeSDKClient
        # Temp file holding the (potentially large) system prompt, passed
        # to the CLI as --system-prompt-file to avoid the OS arg limit.
        # Removed in run_turn's finally.
        self._sysprompt_file: str | None = None
        self._stop_requested = False
        # Mid-run comment injection queue (OOMPAH-211). Populated by
        # inject_message() and drained at each ResultMessage boundary in
        # run_turn(). None = injection not configured for this session.
        self._comment_queue: asyncio.Queue | None = options.comment_queue
        self._session_id: str | None = None
        self._final_cost_usd: float | None = None
        self._permission_denials: list[Any] = []
        self._last_error: str | None = None
        # Terminal status set by run_turn; the AcpBackendSession
        # protocol guarantees this is one of:
        # succeeded | failed | stalled | interrupted | errored.
        # "pending" is the pre-run sentinel — protocol consumers should
        # only read ``status`` AFTER run_turn() has returned.
        self._status: str = "pending"

    # ---- AcpBackendSession protocol property accessors ----

    @property
    def status(self) -> str:
        return self._status

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
        return self._final_cost_usd

    @property
    def last_error(self) -> str | None:
        return self._last_error

    @property
    def permission_denials(self) -> list[Any]:
        return list(self._permission_denials)

    # ---- Lifecycle ----

    async def close(self) -> None:
        """Request that the active session stop. Idempotent."""
        self._stop_requested = True
        client = self._client
        if client is not None:
            with contextlib.suppress(Exception):
                await client.interrupt()

    # ---- Mid-run comment injection (OOMPAH-211) ----

    def _dequeue_comment(self) -> str | None:
        """Try to dequeue one pending injected comment. Returns None if
        the queue is absent or empty. Safe to call from the event loop."""
        if self._comment_queue is None:
            return None
        try:
            return self._comment_queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def inject_message(self, text: str) -> None:
        """Enqueue *text* for delivery as a new agent turn at the next
        ResultMessage boundary. No-op when the session has no queue."""
        if self._comment_queue is not None:
            await self._comment_queue.put(text)

    # ---- Internal: AgentEvent emission for back-compat on_event ----

    def _emit_agent_event(
        self, kind: str, *, payload: dict[str, Any] | None = None
    ) -> None:
        """Forward a translated AgentEvent to options.on_event (if any).

        The AgentEvent kind uses the historical ``acp_*`` prefix so the
        orchestrator's _run_acp_worker kind_map (and any external JSONL
        consumers) keep working unchanged.
        """
        on_event = self._options.on_event
        if on_event is None:
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
            on_event(ev)
        except Exception as exc:  # pragma: no cover — observer's bug
            logger.debug("on_event observer raised: %s", exc)

    def _make_backend_event(
        self, kind: str, payload: dict[str, Any]
    ) -> BackendEvent:
        """Build a BackendEvent mirroring the AgentEvent we just emitted.

        BackendEvent.kind drops the ``acp_`` prefix that AgentEvent uses
        — the protocol consumer (oompah/acp_agent.py:AcpAgentSession or
        a future direct caller) can re-prefix if it wants the legacy
        kind names. Keeps the backend protocol clean.
        """
        prefix = "acp_"
        clean_kind = kind[len(prefix):] if kind.startswith(prefix) else kind
        return BackendEvent(
            kind=clean_kind,
            payload=dict(payload or {}),
            timestamp=time.time(),
            usage={
                "input_tokens": self._counters.input_tokens,
                "output_tokens": self._counters.output_tokens,
                "total_tokens": self._counters.total_tokens,
            },
        )

    def _emit(
        self, kind: str, *, payload: dict[str, Any] | None = None
    ) -> BackendEvent:
        """Dual-emit: forward an AgentEvent to on_event AND return a
        BackendEvent the caller can yield from run_turn."""
        self._emit_agent_event(kind, payload=payload)
        return self._make_backend_event(kind, payload or {})

    # ---- run_turn: the actual SDK drive loop ----

    async def run_turn(self) -> AsyncIterator[BackendEvent]:
        """Open a session, send the prompt, drive the message stream,
        yield BackendEvent objects until completion.

        After run_turn returns, ``self.status`` is one of:

        * ``"succeeded"`` — terminal ResultMessage with no error
        * ``"failed"`` — terminal ResultMessage with an error
        * ``"stalled"`` — turn_timeout_s exceeded; subprocess killed
        * ``"interrupted"`` — caller invoked ``close()``
        * ``"errored"`` — SDK / subprocess crashed unexpectedly
        """
        # If close() was called before run_turn started, honor it.
        if self._stop_requested:
            self._status = "interrupted"
            return

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
            self._last_error = (
                f"claude_agent_sdk not installed: {exc}. "
                "Install with: uv pip install 'oompah[claude]'"
            )
            logger.error(self._last_error)
            self._status = "errored"
            return

        # Permission mode: NOT "bypassPermissions". That mode bypasses
        # the can_use_tool callback entirely, which is exactly the
        # mechanism we use to force claude through our MCP-bridged
        # catalog (vs its native Bash/Read/Write/etc.). With "default"
        # mode every tool call routes through can_use_tool, which
        # auto-allows ``mcp__oompah__*`` and auto-denies everything
        # else. No human-in-the-loop prompts because the callback
        # always returns a definitive decision. See
        # plans/acp-agent.md and oompah-zlz_2-bcl.6.
        try:
            from claude_agent_sdk import (
                PermissionResultAllow,
                PermissionResultDeny,
            )
        except ImportError as exc:
            self._last_error = (
                f"claude_agent_sdk missing PermissionResultAllow/Deny: {exc}. "
                "Install with: uv pip install 'oompah[claude]'"
            )
            logger.error(self._last_error)
            self._status = "errored"
            return

        # Compose the env we want claude to see.
        agent_env = dict(os.environ)
        if self._options.env:
            agent_env.update(self._options.env)

        async def _can_use_tool(
            tool_name: str,
            tool_input: dict[str, Any],
            context: Any,
        ) -> Any:
            """Strict allowlist: only oompah's MCP-bridged catalog is
            permitted. Claude's native built-ins (Bash, Read, Write,
            Edit, Glob, Grep, WebFetch, ...) are denied so cd-guard
            and shell-redirect stay in force."""
            allowed = tool_name.startswith("mcp__oompah__")
            event_kind = (
                "acp_permission_grant" if allowed else "acp_permission_deny"
            )
            try:
                self._emit_agent_event(
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
                    f"so safety rails (cd-guard and shell-redirect) apply."
                ),
                interrupt=False,
            )

        options_kwargs: dict[str, Any] = {
            "system_prompt": self._options.prompt,
            "cwd": self._options.workspace_path,
            "env": agent_env,
            "permission_mode": self._options.permission_mode,
            "can_use_tool": _can_use_tool,
            "disallowed_tools": _CLAUDE_NATIVE_BUILTINS,
        }
        if self._options.model:
            options_kwargs["model"] = self._options.model
        if self._options.fallback_model:
            options_kwargs["fallback_model"] = self._options.fallback_model
        if self._options.max_turns:
            options_kwargs["max_turns"] = int(self._options.max_turns)
        if self._options.tool_catalog:
            try:
                from claude_agent_sdk import create_sdk_mcp_server
            except ImportError as exc:
                self._last_error = (
                    f"claude_agent_sdk missing create_sdk_mcp_server: {exc}. "
                    "Install with: uv pip install 'oompah[claude]'"
                )
                logger.error(self._last_error)
                self._status = "errored"
                return

            server = create_sdk_mcp_server(
                name="oompah-tools",
                version="0.1.0",
                tools=self._options.tool_catalog,
            )
            options_kwargs["mcp_servers"] = {"oompah": server}

        # Transport the (often large) rendered prompt to the CLI via a
        # file rather than a --system-prompt argument. A big string there
        # makes the SDK exec the bundled `claude` binary with an argv that
        # exceeds the OS limit (E2BIG: "[Errno 7] Argument list too long"),
        # which crashed every dispatch for large-context tasks. The same
        # prompt is also delivered as the user query() below, so this is
        # purely a transport fix. Falls back to the inline string if the
        # temp file can't be written.
        try:
            fd, self._sysprompt_file = tempfile.mkstemp(
                prefix="oompah-sysprompt-", suffix=".md"
            )
            with os.fdopen(fd, "w", encoding="utf-8") as pf:
                pf.write(self._options.prompt or "")
            options_kwargs["system_prompt"] = {
                "type": "file",
                "path": self._sysprompt_file,
            }
        except OSError as exc:
            logger.warning(
                "Could not write system-prompt temp file (%s); falling back "
                "to inline --system-prompt (may hit arg-size limits)",
                exc,
            )
            self._sysprompt_file = None

        options = ClaudeAgentOptions(**options_kwargs)

        # Emit the session-start event before we open the client. Gives
        # consumers a chance to wire up loggers before the SDK starts
        # streaming.
        start_event = self._emit(
            "acp_session_start",
            payload={
                "model": self._options.model,
                "fallback_model": self._options.fallback_model,
                "max_turns": self._options.max_turns,
                "permission_mode": self._options.permission_mode,
                "tool_policy": "strict_allowlist:mcp__oompah__*",
                "tool_catalog": [
                    getattr(t, "name", str(t))
                    for t in (self._options.tool_catalog or [])
                ],
                "disallowed_native_tools": list(_CLAUDE_NATIVE_BUILTINS),
                "cwd": self._options.workspace_path,
            },
        )
        yield start_event

        try:
            async with ClaudeSDKClient(options=options) as client:
                self._client = client

                await client.query(self._options.prompt)

                # --- Multi-turn injection loop (OOMPAH-211) ---
                # Each iteration consumes one response from the SDK. When a
                # ResultMessage arrives, we check the comment_queue for any
                # pending human comments and inject them as a new agent turn
                # without restarting the session. This loop runs at most once
                # for sessions with no comment_queue (the common case).
                while True:
                    deadline = time.monotonic() + self._options.turn_timeout_s
                    _got_result = False  # set True when ResultMessage arrives

                    async for msg in client.receive_response():
                        if self._stop_requested:
                            self._status = "interrupted"
                            return
                        if time.monotonic() > deadline:
                            yield self._emit(
                                "acp_turn_timeout",
                                payload={"timeout_s": self._options.turn_timeout_s},
                            )
                            self._status = "stalled"
                            return

                        # ---- Assistant: text, thinking, tool use ----
                        if isinstance(msg, AssistantMessage):
                            self._counters.turn_count += 1
                            self._counters.absorb_assistant_usage(msg.usage)
                            if msg.error:
                                self._last_error = str(msg.error)
                                yield self._emit(
                                    "acp_assistant_error",
                                    payload={"error": msg.error},
                                )
                            for block in msg.content or []:
                                if isinstance(block, TextBlock):
                                    self._counters.last_event = "text"
                                    yield self._emit(
                                        "acp_text",
                                        payload={"text": (block.text or "")[:2000]},
                                    )
                                elif isinstance(block, ThinkingBlock):
                                    self._counters.last_event = "thinking"
                                    yield self._emit(
                                        "acp_thinking",
                                        payload={
                                            "text": (
                                                getattr(block, "thinking", "") or ""
                                            )[:2000]
                                        },
                                    )
                                elif isinstance(block, ToolUseBlock):
                                    self._counters.last_event = "tool_use"
                                    yield self._emit(
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
                                        yield self._emit(
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
                            _got_result = True
                            self._session_id = msg.session_id
                            self._final_cost_usd = msg.total_cost_usd
                            if msg.permission_denials:
                                self._permission_denials = list(msg.permission_denials)
                            if msg.usage:
                                # ResultMessage.usage may correct for prefix-
                                # cache reads etc. Trust it as the final word.
                                try:
                                    self._counters.input_tokens = int(
                                        msg.usage.get(
                                            "input_tokens",
                                            self._counters.input_tokens,
                                        )
                                    )
                                    self._counters.output_tokens = int(
                                        msg.usage.get(
                                            "output_tokens",
                                            self._counters.output_tokens,
                                        )
                                    )
                                except (TypeError, ValueError):
                                    pass
                            yield self._emit(
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
                                self._last_error = (
                                    "; ".join(msg.errors) if msg.errors else "errored"
                                )
                                self._status = "failed"
                                return

                            self._status = "succeeded"

                            # --- Comment injection (OOMPAH-211) ---
                            # If a human posted a comment while we were running,
                            # deliver it as a new agent turn before returning.
                            _injected = self._dequeue_comment()
                            if _injected is not None:
                                logger.info(
                                    "Injecting mid-run comment (%d chars) as new agent turn",
                                    len(_injected),
                                )
                                yield self._emit(
                                    "acp_injected_comment",
                                    payload={
                                        "text": _injected[:200],
                                        "full_length": len(_injected),
                                    },
                                )
                                await client.query(_injected)
                                # Reset status; outer while will start next
                                # receive_response() cycle.
                                self._status = "pending"
                                break  # break inner for → restart receive loop
                            # No injected comment → we are done.
                            return

                    # Inner async-for completed.
                    if not _got_result:
                        # Stream ended without a ResultMessage — treat as error.
                        self._last_error = "stream ended without ResultMessage"
                        self._status = "errored"
                        return
                    # _got_result=True means we injected a comment and broke
                    # the inner loop. Continue outer while for the next turn.
        except Exception as exc:
            # SDK / subprocess failure. Don't crash the worker — log
            # and let the orchestrator retry.
            self._last_error = f"{type(exc).__name__}: {exc}"
            logger.warning("ACP session failed: %s", self._last_error)
            yield self._emit(
                "acp_session_error", payload={"error": self._last_error},
            )
            self._status = "errored"
        finally:
            self._client = None
            if self._sysprompt_file:
                with contextlib.suppress(OSError):
                    os.remove(self._sysprompt_file)
                self._sysprompt_file = None


class ClaudeAcpBackend(AcpBackend):
    """The historical default ACP backend.

    Drives the bundled ``claude`` CLI via the Claude Agent SDK. Bills
    against the operator's Pro/Max subscription rather than per-token
    API meter.
    """

    @classmethod
    def name(cls) -> str:
        return "claude"

    def start_session(self, options: AcpBackendOptions) -> AcpBackendSession:
        return ClaudeAcpBackendSession(options)

    def validate_provider(self, provider: "ModelProvider") -> list[str]:
        """The Claude SDK relies on the operator's subscription auth —
        no api_key required at the provider level. Always passes.

        A future backend that DOES need an api_key (e.g. a hypothetical
        Codex-via-API path) should override this to return errors for
        missing fields.
        """
        return []


# Register on import. ``oompah/acp_backends/__init__.py`` imports this
# module so importing the package is sufficient to make ``claude``
# resolvable through the registry.
register_backend(ClaudeAcpBackend.name(), ClaudeAcpBackend)
