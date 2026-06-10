"""Opencode CLI backend (child C of the multi-backend ACP epic).

This backend drives the ``opencode serve`` CLI subprocess, communicating
via JSON-lines over stdin/stdout. It is similar in spirit to the Claude
backend (subprocess-driven, async generator run_turn()) but uses the
opencode binary instead of the claude CLI.

Design decisions:

* Subscription auth (empty api_key OK at provider level) — the opencode
  CLI handles its own OAuth flow, same as the Codex backend.
* base_url validation mirrors the Codex pattern: must be http(s):// when
  overridden from the default endpoint.
* The subprocess is spawned lazily on the first ``run_turn`` call, so
  ``start_session`` errors don't poison the registry.
* Tool bridging: oompah's MCP catalog round-trips through the same
  ``_exec_*`` helpers from ``oompah/acp_tools.py`` so cd-guard /
  tool-routing semantics are identical between backends.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
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


@dataclass
class _OpencodeCounters:
    """Token-usage counters scraped from opencode JSON messages.

    Mirrors the pattern used by ClaudeAcpBackendSession._SessionCounters
    and CodexAcpBackendSession._CodexCounters.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    turn_count: int = 0
    last_event: str | None = None

    def absorb_usage(self, usage: dict[str, Any] | None) -> None:
        """Pull token counts from a usage dict as emitted by opencode
        serve in its session_start or result messages."""
        if usage is None:
            return
        if isinstance(usage, dict):
            in_t = usage.get("input_tokens")
            out_t = usage.get("output_tokens")
            tot_t = usage.get("total_tokens")
        else:
            in_t = getattr(usage, "input_tokens", None)
            out_t = getattr(usage, "output_tokens", None)
            tot_t = getattr(usage, "total_tokens", None)
        try:
            if in_t is not None:
                self.input_tokens = int(in_t)
            if out_t is not None:
                self.output_tokens = int(out_t)
            if tot_t is not None:
                self.total_tokens = int(tot_t)
            elif in_t is not None or out_t is not None:
                self.total_tokens = self.input_tokens + self.output_tokens
        except (TypeError, ValueError):
            pass


def _truncate(value: Any, limit: int = 1500) -> Any:
    """Same truncation policy as the other backends — keeps the JSONL
    log readable when tool inputs/outputs are huge."""
    if isinstance(value, str):
        return value if len(value) <= limit else value[:limit] + " …[truncated]"
    if isinstance(value, dict):
        return {k: _truncate(v, limit) for k, v in value.items()}
    if isinstance(value, list):
        return [_truncate(v, limit) for v in value]
    return value


class OpencodeAcpBackendSession(AcpBackendSession):
    """Opencode-serve-driven session handle.

    Mirrors the lifecycle of :class:`ClaudeAcpBackendSession` and
    :class:`CodexAcpBackendSession` but drives the ``opencode serve``
    subprocess via JSON-lines over stdin/stdout.
    """

    def __init__(self, options: AcpBackendOptions):
        self._options = options
        self._counters = _OpencodeCounters()
        self._stop_requested = False
        self._session_id: str | None = None
        self._final_cost_usd: float | None = None
        self._permission_denials: list[Any] = []
        self._last_error: str | None = None
        self._status: str = "pending"
        # Tracks whether close() killed the subprocess so run_turn()
        # can distinguish "user cancelled" from "process crashed".
        self._killed_by_close: bool = False
        # The subprocess handle. Populated lazily on first run_turn.
        self._proc: Any = None

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
        return self._counters.total_tokens or (
            self._counters.input_tokens + self._counters.output_tokens
        )

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
        """Request that the active subprocess stop. Idempotent.  When called
        before the subprocess is spawned (``_proc is None``) the session
        is marked ``interrupted`` so that a subsequent ``run_turn`` exits
        immediately without attempting to start the opencode binary."""
        self._stop_requested = True
        proc = self._proc
        if proc is not None:
            self._killed_by_close = True
            try:
                proc.terminate()
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        else:
            # No subprocess yet — mark interrupted so run_turn bails out.
            self._status = "interrupted"

    # ---- Internal: event emission ----

    def _emit_agent_event(
        self, kind: str, *, payload: dict[str, Any] | None = None
    ) -> None:
        """Forward a translated AgentEvent to options.on_event (if any).
        Keeps the ``acp_`` prefix for back-compat with the orchestrator's
        JSONL-logging path."""
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
                "total_tokens": self.total_tokens,
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

        BackendEvent.kind drops the ``acp_`` prefix while AgentEvent uses
        it — keeps this side clean.
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
                "total_tokens": self.total_tokens,
            },
        )

    def _emit(
        self, kind: str, *, payload: dict[str, Any] | None = None
    ) -> BackendEvent:
        """Dual-emit: forward an AgentEvent to on_event AND return a
        BackendEvent the caller can yield from run_turn."""
        self._emit_agent_event(kind, payload=payload)
        return self._make_backend_event(kind, payload or {})

    # ---- Cost payload for terminal result ----

    def _cost_payload(self) -> dict[str, Any]:
        """Normalized cost dict for the terminal result event.

        Mirrors the Codex backend's _cost_payload so child C can read
        a uniform shape from any backend.
        """
        return {
            "input_tokens": self._counters.input_tokens,
            "output_tokens": self._counters.output_tokens,
            "total_tokens": self.total_tokens,
            "cost_usd": self._final_cost_usd,
        }

    # ---- Internal: build the tool catalog ----

    def _build_tool_catalog(self) -> list[Any]:
        """Build the opencode tool catalog for this run.

        Rebuilds from workspace_path so the underlying ``_exec_*``
        helpers (cd-guard and shell-redirect) apply identically to
        other backends. See :func:`oompah.acp_tools.build_tool_catalog`
        (same helper for all subprocess backends; opencode uses the
        same @tool-decorated format as the claude backend).
        """
        # Opencode uses the same @tool-decorated catalog as Claude
        # (openai-agents uses @function_tool which is different).
        from oompah.acp_tools import build_tool_catalog

        return build_tool_catalog(
            self._options.workspace_path,
            project_store=self._options.project_store,
            project_id=self._options.project_id,
        )

    # ---- run_turn: drive the opencode serve subprocess ----

    async def run_turn(self) -> AsyncIterator[BackendEvent]:
        """Spawn ``opencode serve``, send the prompt as JSON on stdin,
        stream JSON-lines from stdout, yield :class:`BackendEvent`
        objects until completion.

        After run_turn returns, ``self.status`` is one of:

        * ``"succeeded"`` — subprocess exited 0 with no error
        * ``"failed"`` — subprocess exited non-zero
        * ``"stalled"`` — turn_timeout_s exceeded; killed
        * ``"interrupted"`` — caller invoked ``close()``
        * ``"errored"`` — unexpected exception
        """
        if self._stop_requested:
            self._status = "interrupted"
            return

        # Build the tool catalog before spawning so we can surface
        # NotImplementedError early rather than mid-stream.
        try:
            tools = self._build_tool_catalog()
        except NotImplementedError as exc:
            self._last_error = (
                f"Opencode backend cannot bridge required tools: {exc}"
            )
            logger.warning(self._last_error)
            self._status = "errored"
            return
        except Exception as exc:
            self._last_error = f"tool catalog build failed: {exc!r}"
            logger.warning(self._last_error)
            self._status = "errored"
            return

        # Compose env. opencode serve reads OPENAI_API_KEY from the
        # process env; if the provider configured a custom api_key it
        # will already be in options.env.
        agent_env = dict(os.environ)
        if self._options.env:
            agent_env.update(self._options.env)
        # Forward api_key into the process env if present.
        api_key = agent_env.get("OOMPAH_OPENCODE_API_KEY")
        if api_key:
            os.environ.setdefault("OPENAI_API_KEY", api_key)

        # Build the tool catalog names for the session_start event payload.
        tool_names = [
            getattr(t, "name", getattr(t, "__name__", str(t)))
            for t in tools
        ]

        # Emit session_start before spawning so consumers can wire up
        # loggers before the subprocess starts streaming.
        yield self._emit(
            "acp_session_start",
            payload={
                "model": self._options.model,
                "fallback_model": self._options.fallback_model,
                "max_turns": self._options.max_turns,
                "permission_mode": self._options.permission_mode,
                "tool_policy": "opencode:tool_catalog",
                "tool_catalog": tool_names,
                "billing_model": "subscription",
                "cwd": self._options.workspace_path,
            },
        )

        # Spawn the opencode serve subprocess.
        cmd = ["opencode", "serve"]
        try:
            self._proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=agent_env,
                cwd=self._options.workspace_path,
            )
        except FileNotFoundError as exc:
            self._last_error = (
                "opencode binary not found in PATH. Opencode ACP backend "
                "requires the opencode CLI to be installed and in PATH. "
                f"Original error: {exc}"
            )
            logger.error(self._last_error)
            self._status = "errored"
            yield self._emit(
                "acp_session_error", payload={"error": self._last_error},
            )
            return
        except Exception as exc:
            self._last_error = f"failed to spawn opencode serve: {exc!r}"
            logger.warning(self._last_error)
            self._status = "errored"
            yield self._emit(
                "acp_session_error", payload={"error": self._last_error},
            )
            return

        # Send the initial prompt as a JSON message on stdin.
        init_msg = {
            "type": "init",
            "prompt": self._options.prompt,
            "model": self._options.model,
            "tools": tool_names,
        }
        try:
            stdin = self._proc.stdin
            stdin.write((json.dumps(init_msg) + "\n").encode())
            await stdin.drain()
        except Exception as exc:
            self._last_error = f"failed to send init message: {exc!r}"
            logger.warning(self._last_error)
            self._status = "errored"
            yield self._emit(
                "acp_session_error", payload={"error": self._last_error},
            )
            return

        deadline = time.monotonic() + self._options.turn_timeout_s

        try:
            # Read JSON-lines from stdout.
            stdout = self._proc.stdout
            async for line in stdout:
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

                line_text = line.decode("utf-8").strip()
                if not line_text:
                    continue

                try:
                    msg = json.loads(line_text)
                except json.JSONDecodeError:
                    logger.debug("skipping unparseable line: %s", line_text)
                    continue

                async for be in self._translate_message(msg):
                    yield be

                # After a result message, stop streaming.
                msg_type = msg.get("type", "")
                if msg_type == "result":
                    break

            # Stream exhausted. If close() was called during iteration,
            # _stop_requested will be True and the stream ended because
            # of that — treat as interrupted, not succeeded.  We detect
            # this by checking _stop_requested BEFORE calling wait()
            # (wait() would return 0 even for an interrupted session).
            if self._stop_requested:
                self._status = "interrupted"
                return

            # subprocess has closed its stdout — wait for it to finish.
            return_code = await self._proc.wait()
            if return_code != 0:
                # Distinguish "user closed the session" from "crash":
                # _killed_by_close is set by close() → terminate/kill.
                if self._killed_by_close:
                    self._status = "interrupted"
                    return
                stderr_lines = []
                if self._proc.stderr:
                    try:
                        stderr_data = await asyncio.wait_for(
                            self._proc.stderr.read(), timeout=2.0
                        )
                        stderr_lines = stderr_data.decode(
                            "utf-8", errors="replace"
                        ).splitlines()
                    except Exception:
                        pass
                self._last_error = (
                    f"opencode serve exited with code {return_code}. "
                    f"stderr: {'; '.join(stderr_lines[-5:])}"
                )
                logger.warning("Opencode ACP session failed: %s", self._last_error)
                yield self._emit(
                    "acp_session_error", payload={"error": self._last_error},
                )
                self._status = "errored"
                return

            # Clean exit: emit the terminal result.
            yield self._emit(
                "acp_result",
                payload={
                    "subtype": "success",
                    "is_error": False,
                    "stop_reason": "end_turn",
                    "num_turns": self._counters.turn_count,
                    "total_cost_usd": self._final_cost_usd,
                    "usage": self._cost_payload(),
                    "errors": None,
                },
            )
            self._status = "succeeded"
        except Exception as exc:
            self._last_error = f"{type(exc).__name__}: {exc}"
            logger.warning("Opencode ACP session failed: %s", self._last_error)
            yield self._emit(
                "acp_session_error", payload={"error": self._last_error},
            )
            self._status = "errored"
        finally:
            if self._proc is not None:
                with __import__("contextlib").suppress(Exception):
                    self._proc.terminate()
                self._proc = None

    # ---- Internal: message translation ----

    async def _translate_message(
        self, msg: dict[str, Any]
    ) -> AsyncIterator[BackendEvent]:
        """Map a single opencode serve JSON message to one or more
        :class:`BackendEvent` instances.

        Expected message types from opencode serve:

        * ``session_start`` — metadata; may carry session_id + usage.
        * ``text`` — assistant text delta.
        * ``tool_use`` — a tool call request.
        * ``tool_result`` — result of a tool call.
        * ``result`` — terminal success / failure.
        * ``error`` — error message.
        """
        msg_type = msg.get("type", "")

        if msg_type == "session_start":
            # Capture session_id for the protocol consumer.
            sid = msg.get("session_id")
            if isinstance(sid, str) and self._session_id is None:
                self._session_id = sid
            # Absorb any usage data.
            usage = msg.get("usage")
            if usage:
                self._counters.absorb_usage(usage)

        elif msg_type == "text":
            text = msg.get("text", "")
            if text:
                self._counters.last_event = "text"
                yield self._emit(
                    "acp_text", payload={"text": str(text)[:2000]}
                )

        elif msg_type == "tool_use":
            self._counters.last_event = "tool_use"
            self._counters.turn_count += 1
            tool_name = msg.get("tool", "?")
            tool_input = _truncate(msg.get("input", {}))
            tool_id = msg.get("id")
            yield self._emit(
                "acp_tool_use",
                payload={
                    "tool": tool_name,
                    "input": tool_input,
                    "id": tool_id,
                },
            )

        elif msg_type == "tool_result":
            self._counters.last_event = "tool_result"
            yield self._emit(
                "acp_tool_result",
                payload={
                    "tool_use_id": msg.get("tool_use_id"),
                    "is_error": bool(msg.get("is_error", False)),
                    "content": _truncate(msg.get("content", "")),
                },
            )

        elif msg_type in ("result", "error"):
            # Terminal messages. Don't yield a BackendEvent here —
            # run_turn itself emits the final result/error after the
            # loop. Just absorb usage if present.
            usage = msg.get("usage")
            if usage:
                self._counters.absorb_usage(usage)
            cost = msg.get("total_cost_usd") or msg.get("cost_usd")
            if isinstance(cost, (int, float)):
                self._final_cost_usd = float(cost)
            if msg_type == "error":
                self._last_error = msg.get("error", "unknown error")


# ----------------------------------------------------------------------
# Backend class
# ----------------------------------------------------------------------


class OpencodeAcpBackend(AcpBackend):
    """Opencode-serve-driven ACP backend.

    Validates the multi-backend abstraction by implementing a third
    concrete :class:`AcpBackend` against the opencode CLI.
    """

    @classmethod
    def name(cls) -> str:
        return "opencode"

    def start_session(self, options: AcpBackendOptions) -> AcpBackendSession:
        return OpencodeAcpBackendSession(options)

    def validate_provider(self, provider: "ModelProvider") -> list[str]:
        """Opencode uses subscription auth at the CLI level (the opencode
        binary handles OAuth) — no api_key required at the provider level.

        base_url is optional but must be a well-formed http(s) URL when
        overridden from the default opencode endpoint.
        """
        errors: list[str] = []

        base_url = (provider.base_url or "").strip()
        if base_url:
            if not (
                base_url.startswith("http://")
                or base_url.startswith("https://")
            ):
                errors.append(
                    f"base_url must start with http:// or https://; got "
                    f"{base_url!r}. Leave empty to use the default opencode "
                    f"endpoint."
                )

        return errors


# Register on import.
register_backend(OpencodeAcpBackend.name(), OpencodeAcpBackend)
