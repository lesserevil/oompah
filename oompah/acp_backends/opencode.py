"""OpenCode ACP backend (the third registered ACP backend).

This backend implements :class:`AcpBackend` against the OpenCode
Python SDK — a session-shaped agent framework with async streaming
support, similar in spirit to the Claude and Codex backends.

# OpenCode SDK choice

OpenCode is chosen for its:

* Session-shaped API with async ``Chat`` streaming.
* ``function_tool`` / ``@tool`` interface for tool injection.
* Streaming event model that maps cleanly to ``BackendEvent``.
* Open-source / self-hostable (reduces vendor dependency).

The SDK is lazily imported so installations that never use the
OpenCode backend don't pay the import cost. If the SDK is missing
we surface a clear install hint rather than a cryptic
``ModuleNotFound``.

# Tool bridging

The OpenCode SDK tool format uses ``@tool`` decorator (same surface
as Claude, distinct from Codex's ``@function_tool``). The
:func:`oompah.acp_tools.build_opencode_tool_catalog` function wires
the shared ``_exec_*`` helpers from :mod:`oompah.api_agent` so cd-
guard, BEADS_DIR routing, and per-command timeouts apply identically
across all three backends. The backend ignores any
``options.tool_catalog`` passed in (Claude-formatted) and rebuilds
from the workspace path.

# Permission handling

OpenCode SDK does not expose a ``can_use_tool`` callback or hard
``disallowed_tools`` denylist. The bridged catalog is the only safety
surface. ``permission_mode`` is recorded in the ``session_start``
event for audit but does not change SDK behavior.

# Cost reporting

Per-token billing: we read the ``OOMPAH_OPENCODE_BILLING`` env var
(default ``"per_token"``) to mirror the Codex pattern. ``cost_usd`` on
the terminal event is ``None`` for subscription tiers (no per-token
bill); per-token tiers surface the SDK's reported cost or leave it as
``None`` until a future billing child computes it from tokens +
model_costs.
"""

from __future__ import annotations

import contextlib
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


def _import_sdk():
    """Lazy import of the OpenCode Python SDK.

    The canonical PyPI package installs as the ``opencode`` module.
    Raises :class:`ImportError` with an install hint if the SDK is not
    available so operators see a clear action to take.
    """
    try:
        import opencode as sdk  # type: ignore
        return sdk
    except ImportError as exc:
        raise ImportError(
            "OpenCode SDK not installed. OpenCode ACP backend "
            "requires the OpenCode Python SDK. Install with: "
            "pip install opencode"
        ) from exc


@dataclass
class _OpenCodeCounters:
    """Token-usage counters scraped from SDK events.

    Mirrors the pattern from the Claude and Codex backends.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    turn_count: int = 0
    last_event: str | None = None

    def absorb_usage(self, usage: Any) -> None:
        """Pull token counts from whatever ``usage`` shape the SDK
        version exposes.

        Accepts:
        * A dict with ``input_tokens`` / ``output_tokens`` keys.
        * An OpenCode ``Usage`` object with those attributes.
        * ``None`` / unrecognized — ignored.
        """
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
            return


def _truncate(value: Any, limit: int = 1500) -> Any:
    """Shrink large tool inputs/outputs so the JSONL log stays readable.

    Same truncation policy as the Claude and Codex backends.
    """
    if isinstance(value, str):
        return value if len(value) <= limit else value[:limit] + " …[truncated]"
    if isinstance(value, dict):
        return {k: _truncate(v, limit) for k, v in value.items()}
    if isinstance(value, list):
        return [_truncate(v, limit) for v in value]
    return value


class OpenCodeAcpBackendSession(AcpBackendSession):
    """OpenCode-SDK-driven session handle.

    Mirrors :class:`CodexAcpBackendSession` / :class:`ClaudeAcpBackendSession`
    in surface and lifecycle. Drives the OpenCode ``Chat`` async
    streaming interface.
    """

    def __init__(self, options: AcpBackendOptions):
        self._options = options
        self._counters = _OpenCodeCounters()
        self._stop_requested = False
        self._session_id: str | None = None
        self._final_cost_usd: float | None = None
        self._permission_denials: list[Any] = []
        self._last_error: str | None = None
        self._status: str = "pending"
        # Runtime SDK objects. Populated lazily on first run_turn.
        self._chat: Any = None
        self._billing_model: str = self._billing_model_from_env()

    def _billing_model_from_env(self) -> str:
        """Resolve billing model from options.env.

        Mirrors the Codex backend's pattern:
        reads ``OOMPAH_OPENCODE_BILLING`` (default ``"per_token"``).
        """
        env = self._options.env or {}
        return (env.get("OOMPAH_OPENCODE_BILLING") or "per_token").strip() or "per_token"

    # ---- AcpBackendSession protocol properties ----

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
        """Request that the active session stop. Idempotent.

        Stops the OpenCode chat session if active.
        """
        self._stop_requested = True
        chat = self._chat
        if chat is not None:
            stop = getattr(chat, "stop", None)
            if stop is not None:
                with contextlib.suppress(Exception):
                    result = stop()
                    if hasattr(result, "__await__"):
                        await result

    # ---- Internal: event emission ----

    def _emit_agent_event(
        self, kind: str, *, payload: dict[str, Any] | None = None
    ) -> None:
        """Forward a translated AgentEvent to options.on_event (if any)."""
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
        """Build a BackendEvent mirroring the AgentEvent we just emitted."""
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

    # ---- Build the SDK-native tool catalog ----

    def _build_tool_catalog(self) -> list[Any]:
        """Build the OpenCode SDK-flavored tool catalog for this run.

        Ignores ``options.tool_catalog`` (Claude-formatted) and rebuilds
        from ``workspace_path`` using the same ``_exec_*`` helpers as
        the other backends so safety rails are identical.
        See :func:`oompah.acp_tools.build_opencode_tool_catalog`.
        """
        from oompah.acp_tools import build_opencode_tool_catalog

        env = self._options.env or {}
        beads_dir = env.get("BEADS_DIR")
        return build_opencode_tool_catalog(
            self._options.workspace_path,
            beads_dir=beads_dir,
        )

    # ---- run_turn ----

    async def run_turn(self) -> AsyncIterator[BackendEvent]:
        """Open an OpenCode Chat session, run the prompt, stream events,
        yield :class:`BackendEvent` objects until completion.

        After run_turn returns, ``self.status`` is one of:

        * ``"succeeded"`` — clean completion.
        * ``"failed"`` — terminal event flagged an error.
        * ``"stalled"`` — turn_timeout_s exceeded.
        * ``"interrupted"`` — caller invoked ``close()``.
        * ``"errored"`` — SDK / subprocess crashed.
        """
        if self._stop_requested:
            self._status = "interrupted"
            return

        try:
            sdk = _import_sdk()
        except ImportError as exc:
            self._last_error = str(exc)
            logger.error("OpenCode ACP backend: %s", self._last_error)
            self._status = "errored"
            return

        Chat = getattr(sdk, "Chat", None)
        if Chat is None:
            self._last_error = (
                "OpenCode SDK is missing 'Chat'; "
                "OpenCode backend requires the session-shaped Chat interface."
            )
            logger.error(self._last_error)
            self._status = "errored"
            return

        # Compose env with api_key if present.
        agent_env = dict(os.environ)
        if self._options.env:
            agent_env.update(self._options.env)
        # Allow OPENCODE_API_KEY or fall back to OPENAI_API_KEY (OpenCode
        # can proxy to OpenAI-compatible endpoints).
        api_key = (
            agent_env.get("OPENCODE_API_KEY")
            or agent_env.get("OPENAI_API_KEY")
            or agent_env.get("OOMPAH_OPENCODE_API_KEY")
        )
        if api_key:
            os.environ.setdefault("OPENCODE_API_KEY", api_key)

        # Build the tool catalog.
        try:
            tools = self._build_tool_catalog()
        except NotImplementedError as exc:
            self._last_error = f"OpenCode backend cannot bridge tools: {exc}"
            logger.warning(self._last_error)
            self._status = "errored"
            return
        except Exception as exc:
            self._last_error = f"tool catalog build failed: {exc!r}"
            logger.warning(self._last_error)
            self._status = "errored"
            return

        chat_kwargs: dict[str, Any] = {
            "model": self._options.model or "opencode",
            "tools": tools,
        }
        if api_key:
            chat_kwargs["api_key"] = api_key
        # base_url from provider (for proxy/custom endpoints).
        base_url = agent_env.get("OPENCODE_BASE_URL") or agent_env.get(
            "OOMPAH_OPENCODE_BASE_URL"
        )
        if base_url:
            chat_kwargs["base_url"] = base_url

        try:
            chat = Chat(**chat_kwargs)
        except Exception as exc:
            self._last_error = f"Chat construction failed: {exc!r}"
            logger.warning(self._last_error)
            self._status = "errored"
            return

        self._chat = chat

        # Emit session_start before any async activity.
        yield self._emit(
            "acp_session_start",
            payload={
                "model": chat_kwargs.get("model"),
                "fallback_model": self._options.fallback_model,
                "max_turns": self._options.max_turns,
                "permission_mode": self._options.permission_mode,
                "tool_policy": "opencode:bridged_catalog_only",
                "tool_catalog": [
                    getattr(t, "name", getattr(t, "__name__", str(t)))
                    for t in tools
                ],
                "billing_model": self._billing_model,
                "cwd": self._options.workspace_path,
            },
        )

        deadline = time.monotonic() + self._options.turn_timeout_s
        tool_call_stack: dict[str, Any] = {}

        try:
            async for event, data in chat.stream(self._options.prompt):
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

                async for be in self._translate_stream_event(
                    event, data, tool_call_stack
                ):
                    yield be

            # Stream ended cleanly. Emit the terminal result event.
            self._absorb_counters()
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
            logger.warning("OpenCode ACP session failed: %s", self._last_error)
            yield self._emit(
                "acp_session_error", payload={"error": self._last_error}
            )
            self._status = "errored"
        finally:
            self._chat = None

    # ---- Internal: per-event translation ----

    async def _translate_stream_event(
        self, event: str, data: Any, tool_call_stack: dict[str, Any]
    ) -> AsyncIterator[BackendEvent]:
        """Map an OpenCode Chat stream event to one or more BackendEvents.

        OpenCode Chat emits text chunks, tool calls, tool results, and
        completion events. We pattern-match on the event string since
        the concrete shapes are SDK-version dependent.
        """
        # ---- Text delta ----
        if event == "text":
            text = data if isinstance(data, str) else ""
            if text:
                self._counters.last_event = "text"
                yield self._emit("acp_text", payload={"text": text[:2000]})

        elif event == "text_done":
            # Final accumulated text — emit as a single block.
            text = data if isinstance(data, str) else ""
            if text:
                self._counters.last_event = "text"
                yield self._emit("acp_text", payload={"text": text[:2000]})

        # ---- Tool use ----
        elif event == "tool_call":
            self._counters.last_event = "tool_use"
            self._counters.turn_count += 1
            # OpenCode's tool_call data is a dict with name, args, id.
            tool_name = (
                data.get("name") if isinstance(data, dict) else getattr(data, "name", "?")
            )
            tool_args = (
                data.get("arguments", {})
                if isinstance(data, dict)
                else getattr(data, "arguments", {})
            )
            tool_id = (
                data.get("id")
                if isinstance(data, dict)
                else getattr(data, "id", None)
            )
            tool_call_stack[str(tool_id or id(data))] = tool_name
            yield self._emit(
                "acp_tool_use",
                payload={
                    "tool": str(tool_name),
                    "input": _truncate(tool_args),
                    "id": str(tool_id) if tool_id else None,
                },
            )

        # ---- Tool result ----
        elif event == "tool_result":
            result = data if isinstance(data, dict) else {}
            tool_use_id = str(result.get("tool_call_id", "")) or ""
            content = result.get("content") or ""
            is_error = bool(result.get("is_error", False))
            self._counters.last_event = "tool_result"
            yield self._emit(
                "acp_tool_result",
                payload={
                    "tool_use_id": tool_use_id,
                    "is_error": is_error,
                    "content": _truncate(content),
                },
            )

        # ---- Thinking / reasoning ----
        elif event in ("thinking", "reasoning", "thought"):
            text = data if isinstance(data, str) else ""
            if text:
                self._counters.last_event = "thinking"
                yield self._emit("acp_thinking", payload={"text": text[:2000]})

        # ---- Token usage from streaming events ----
        elif event == "usage" or event == "usage_update":
            self._counters.absorb_usage(data)

        # ---- Session ID ----
        elif event == "session_id":
            if isinstance(data, str) and not self._session_id:
                self._session_id = data

        # ---- Error ----
        elif event == "error":
            err_msg = data if isinstance(data, str) else str(data)
            self._last_error = err_msg
            yield self._emit(
                "acp_assistant_error", payload={"error": err_msg}
            )

        # else: unknown event type — silently ignore so SDK version
        # churn doesn't cause spurious errors.

    def _absorb_counters(self) -> None:
        """Read final token counts from the chat session handle."""
        chat = self._chat
        if chat is None:
            return
        for attr in ("usage", "_usage"):
            usage = getattr(chat, attr, None)
            if usage is not None:
                self._counters.absorb_usage(usage)
                break

    def _cost_payload(self) -> dict[str, Any]:
        """Build the normalized cost dict for the terminal result event.

        Mirrors the Codex backend's _cost_payload so child C can
        consume a uniform dict regardless of which backend ran.
        """
        return {
            "input_tokens": self._counters.input_tokens,
            "output_tokens": self._counters.output_tokens,
            "total_tokens": self.total_tokens,
            "cost_usd": self._final_cost_usd,
        }


# ----------------------------------------------------------------------
# Backend class
# ----------------------------------------------------------------------


class OpenCodeAcpBackend(AcpBackend):
    """OpenCode-SDK-driven ACP backend.

    Implements the pluggable :class:`AcpBackend` interface using the
    OpenCode Chat Python SDK.
    """

    @classmethod
    def name(cls) -> str:
        return "opencode"

    def start_session(self, options: AcpBackendOptions) -> AcpBackendSession:
        return OpenCodeAcpBackendSession(options)

    def validate_provider(self, provider: "ModelProvider") -> list[str]:
        """Backend-specific provider validation.

        Rules:

        * Per-token tier (default): requires ``api_key``.
        * Subscription tier: ``api_key`` optional.
        * ``base_url`` (when overridden) must be a well-formed
          ``http://`` or ``https://`` URL.

        Mirrors the Codex backend's rules since both target
        OpenAI-compatible endpoints.
        """
        errors: list[str] = []
        billing_model = (
            (getattr(provider, "billing_model", None) or "per_token")
            .strip()
            .lower()
        )
        if billing_model != "subscription":
            if not (provider.api_key or "").strip():
                errors.append(
                    "api_key required for per-token OpenCode. "
                    "Set billing_model='subscription' on the provider "
                    "for subscription billing."
                )

        base_url = (provider.base_url or "").strip()
        if base_url:
            if not (
                base_url.startswith("http://")
                or base_url.startswith("https://")
            ):
                errors.append(
                    f"base_url must start with http:// or https://; got "
                    f"{base_url!r}. Leave empty to use the default "
                    f"OpenCode endpoint."
                )

        return errors


# Register on import. ``oompah/acp_backends/__init__.py`` imports all
# backend modules so importing the package wires all backends into
# the registry.
register_backend(OpenCodeAcpBackend.name(), OpenCodeAcpBackend)