"""Codex-backend console event translator (oompah-zlz_2-elug, Console 6/6).

Translates between the AgentEvent stream produced by
:mod:`oompah.acp_backends.codex` (``acp_*`` kinds — same shape as the
Claude backend emits; the abstraction-layer normalizes both to the
identical ``AgentEvent(event=..., timestamp=..., usage=...,
payload=...)`` dataclass) and the normalized
:class:`oompah.console_format.ConsoleEvent` form, and reconstructs an
openai-agents-SDK-compatible ``input`` list (the SDK's "history" hand-
off when re-entering a previously-recorded conversation).

# Why the mapping is symmetric with the Claude translator

Both ACP backends route their underlying SDK events through
:class:`oompah.acp_backends.base.BackendEvent` → :class:`AgentEvent`
before reaching :func:`acp_to_normalized`. By the time we see an
event here it's wearing the same ``acp_*`` jersey regardless of
which SDK produced it. So the translator's responsibility is just to
(a) stamp ``backend="codex"`` on each normalized event so a replay
later knows which dialect to render under, and (b) for the SDK
history builder, emit the openai-agents `Runner.run_streamed(input=…)`
shape instead of the Anthropic Messages shape.

# SDK history shape: openai-agents "input items"

The openai-agents SDK accepts either a plain ``str`` (treated as a
single user turn) or a ``list[TResponseInputItem]`` (a sequence of
typed dicts) for the ``input=`` argument to ``Runner.run_streamed``.
That list is the "history" the test harness asserts on.

Each input item is one of:

* **Message** — text turn (user/assistant/system)::

      {"role": "user", "content": "..."}
      {"role": "assistant", "content": "..."}

* **Function call** — assistant requested a tool::

      {
        "type": "function_call",
        "name": "read_file",
        "arguments": "{\"path\":\"README.md\"}",
        "call_id": "tu_42",
      }

* **Function call output** — tool returned data::

      {
        "type": "function_call_output",
        "call_id": "tu_42",
        "output": "file body…",
      }

Tool call args MUST be a JSON-encoded string per the OpenAI Responses
API spec (``arguments``), not a dict — even though the Claude side
naturally carries them as a dict. We JSON-encode at the boundary so
the codex SDK accepts the shape without further massaging.

# Robustness contract

* Unknown ``acp_*`` event kinds fall into ``session_meta`` so the
  transcript stays readable. The original kind survives in
  ``raw_event_kind`` for future-aware viewers.
* Tool calls and tool results missing their ``id``/``tool_use_id``
  link are silently dropped from the SDK history (the SDK rejects
  unanchored function_call_output items). This matches the Claude
  translator's behavior.
* Roles in the history are NOT forced to strictly alternate the way
  the Anthropic API requires; openai-agents accepts adjacent same-
  role messages. Two consecutive ``agent_text`` events become two
  ``{"role":"assistant"}`` messages.
* Empty ``agent_text`` events produce no message (empty content is
  not a useful history entry and some SDK versions reject it).
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
from typing import Any

from oompah.console_format import ConsoleEvent
from oompah.console_translators import Translator, register_translator

logger = logging.getLogger(__name__)


_BACKEND_NAME = "codex"


# ---------------------------------------------------------------------------
# Helpers (shared shape with claude.py but kept local to avoid a cross-module
# import dance — these are simple enough that duplication is cheaper than
# coupling).
# ---------------------------------------------------------------------------


def _format_ts(timestamp: float | int | None) -> str:
    """Convert a unix-epoch timestamp to ISO-8601 UTC with microsecond
    precision (suffix ``Z``).

    Matches the format the Claude translator emits, so a mixed
    transcript (claude turns followed by codex turns) still
    chronologically string-sorts correctly when scanned by the
    on-disk store.
    """
    if timestamp is None:
        return ""
    try:
        return (
            _dt.datetime.fromtimestamp(float(timestamp), tz=_dt.timezone.utc)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        )
    except (TypeError, ValueError, OSError):
        return ""


def _extract_payload(acp_event: Any) -> dict[str, Any]:
    payload = getattr(acp_event, "payload", None)
    if isinstance(payload, dict):
        return payload
    return {}


def _extract_usage(acp_event: Any) -> dict[str, Any] | None:
    usage = getattr(acp_event, "usage", None)
    if isinstance(usage, dict) and usage:
        return dict(usage)
    return None


# ---------------------------------------------------------------------------
# AgentEvent → ConsoleEvent
# ---------------------------------------------------------------------------


def acp_to_normalized(acp_event: Any) -> ConsoleEvent:
    """Translate one codex-backend :class:`oompah.agent.AgentEvent` to
    a :class:`ConsoleEvent`.

    See the module docstring for the mapping table. Stamps
    ``backend="codex"`` on every output so a replay later can pick the
    right ``normalized_to_sdk_history`` path. The acp_* event names
    are identical to the Claude backend's; we centralize the mapping
    here so a future divergence in the codex backend's vocabulary can
    diverge here without touching the claude translator.
    """
    raw_kind = str(getattr(acp_event, "event", "") or "")
    payload = _extract_payload(acp_event)
    usage = _extract_usage(acp_event)
    ts = _format_ts(getattr(acp_event, "timestamp", None))

    # --- agent text ---
    if raw_kind == "acp_text":
        return ConsoleEvent(
            ts=ts,
            kind="agent_text",
            backend=_BACKEND_NAME,
            text=str(payload.get("text") or ""),
            usage=usage,
        )

    # --- agent thinking (reasoning_item from openai-agents) ---
    if raw_kind == "acp_thinking":
        return ConsoleEvent(
            ts=ts,
            kind="agent_thinking",
            backend=_BACKEND_NAME,
            text=str(payload.get("text") or ""),
            usage=usage,
        )

    # --- tool call (assistant → tool) ---
    if raw_kind == "acp_tool_use":
        tool_input = payload.get("input")
        args: dict[str, Any] = {}
        if isinstance(tool_input, dict):
            args.update(tool_input)
        elif tool_input is not None:
            # Truncation in the backend can produce a string; keep it
            # under a synthetic key so the round-trip is lossless.
            args["_raw_input"] = tool_input
        tool_use_id = payload.get("id")
        if tool_use_id is not None:
            args["_tool_use_id"] = str(tool_use_id)
        return ConsoleEvent(
            ts=ts,
            kind="tool_call",
            backend=_BACKEND_NAME,
            tool=str(payload.get("tool") or ""),
            args=args,
            usage=usage,
        )

    # --- tool result (tool → assistant) ---
    if raw_kind == "acp_tool_result":
        result_payload: dict[str, Any] = {}
        if "tool_use_id" in payload:
            result_payload["tool_use_id"] = str(payload["tool_use_id"])
        if "content" in payload:
            result_payload["content"] = payload["content"]
        is_error = bool(payload.get("is_error", False))
        return ConsoleEvent(
            ts=ts,
            kind="tool_result",
            backend=_BACKEND_NAME,
            result=result_payload,
            is_error=is_error,
            usage=usage,
        )

    # --- permission grant/deny ---
    # openai-agents has no native permission gate, but the codex
    # backend records permission_mode for audit and the orchestrator
    # may file these synthetically. Keep parity with claude so the
    # transcript renders uniformly.
    if raw_kind in ("acp_permission_grant", "acp_permission_deny"):
        tool_input = payload.get("input")
        args = {}
        if isinstance(tool_input, dict):
            args.update(tool_input)
        elif tool_input is not None:
            args["_raw_input"] = tool_input
        return ConsoleEvent(
            ts=ts,
            kind="permission",
            backend=_BACKEND_NAME,
            tool=str(payload.get("tool") or ""),
            args=args or None,
            is_error=(raw_kind == "acp_permission_deny"),
            raw_event_kind=raw_kind,
        )

    # --- errors ---
    if raw_kind in ("acp_assistant_error", "acp_session_error"):
        err = payload.get("error")
        text = str(err) if err is not None else ""
        return ConsoleEvent(
            ts=ts,
            kind="error",
            backend=_BACKEND_NAME,
            text=text,
            is_error=True,
            raw_event_kind=raw_kind,
            usage=usage,
        )

    if raw_kind == "acp_turn_timeout":
        timeout_s = payload.get("timeout_s")
        return ConsoleEvent(
            ts=ts,
            kind="error",
            backend=_BACKEND_NAME,
            text=f"turn timeout after {timeout_s}s",
            is_error=True,
            raw_event_kind=raw_kind,
            usage=usage,
        )

    # --- session lifecycle ---
    if raw_kind == "acp_session_start":
        model = payload.get("model")
        return ConsoleEvent(
            ts=ts,
            kind="session_meta",
            backend=_BACKEND_NAME,
            model=str(model) if model is not None else None,
            args=dict(payload) if payload else None,
            raw_event_kind=raw_kind,
            usage=usage,
        )

    if raw_kind == "acp_result":
        return ConsoleEvent(
            ts=ts,
            kind="session_meta",
            backend=_BACKEND_NAME,
            args=dict(payload) if payload else None,
            is_error=bool(payload.get("is_error", False)),
            raw_event_kind=raw_kind,
            usage=usage,
        )

    # --- unknown ---
    return ConsoleEvent(
        ts=ts,
        kind="session_meta",
        backend=_BACKEND_NAME,
        args=dict(payload) if payload else None,
        raw_event_kind=raw_kind or None,
        usage=usage,
    )


# ---------------------------------------------------------------------------
# Normalized events → openai-agents SDK input items
# ---------------------------------------------------------------------------


def _operator_input_to_message(event: ConsoleEvent) -> dict[str, Any] | None:
    """Build an openai-agents user input item from an operator_input event.

    Returns ``None`` for empty input (no text + no attachments) so the
    SDK doesn't see a degenerate empty user message.
    """
    parts: list[str] = []
    if event.text:
        parts.append(event.text)
    if event.attachments:
        # Inline the attachment path references — same back-compat
        # contract as the claude translator (the staging dir is the
        # caller's job; we just preserve the reference for replay).
        for path in event.attachments:
            parts.append(f"[attachment: {path}]")
    if not parts:
        return None
    content = "\n".join(parts) if len(parts) > 1 else parts[0]
    return {"role": "user", "content": content}


def _agent_text_to_message(event: ConsoleEvent) -> dict[str, Any] | None:
    """Build an openai-agents assistant input item from an agent_text event."""
    if not event.text:
        return None
    return {"role": "assistant", "content": event.text}


def _tool_call_to_input_item(event: ConsoleEvent) -> dict[str, Any] | None:
    """Convert a normalized tool_call event into an openai-agents
    ``function_call`` input item. Returns ``None`` when the event
    lacks the required ``_tool_use_id`` link — the SDK rejects
    unanchored function calls.

    The ``arguments`` field is a JSON-encoded string per the OpenAI
    Responses API spec, NOT a dict. We encode here at the boundary so
    the SDK accepts the input verbatim.
    """
    args = dict(event.args or {})
    tool_use_id = args.pop("_tool_use_id", None)
    if not tool_use_id:
        return None
    raw_input = args.pop("_raw_input", None)
    if raw_input is not None and not args:
        # Backend captured a truncated repr instead of a dict; pass it
        # through verbatim. JSON-encode if it's not already a string.
        if isinstance(raw_input, str):
            arguments_str = raw_input
        else:
            try:
                arguments_str = json.dumps(raw_input)
            except (TypeError, ValueError):
                arguments_str = str(raw_input)
    else:
        try:
            arguments_str = json.dumps(args, sort_keys=True)
        except (TypeError, ValueError):
            # Defensive: SDK requires a string; never raise out of the
            # history builder.
            arguments_str = json.dumps({})
    return {
        "type": "function_call",
        "name": event.tool or "",
        "arguments": arguments_str,
        "call_id": str(tool_use_id),
    }


def _tool_result_to_input_item(event: ConsoleEvent) -> dict[str, Any] | None:
    """Convert a normalized tool_result event into an openai-agents
    ``function_call_output`` input item. Returns ``None`` if no
    ``tool_use_id`` link is present (the SDK pairs outputs to calls
    by ``call_id`` — orphaned outputs are rejected)."""
    result = dict(event.result or {})
    tool_use_id = result.get("tool_use_id")
    if not tool_use_id:
        return None
    content = result.get("content", "")
    if not isinstance(content, str):
        # The SDK expects a string output; coerce dict/list to JSON,
        # everything else to repr.
        try:
            content = json.dumps(content)
        except (TypeError, ValueError):
            content = str(content)
    out: dict[str, Any] = {
        "type": "function_call_output",
        "call_id": str(tool_use_id),
        "output": content,
    }
    # The Responses API doesn't have a first-class is_error flag on
    # function_call_output. Convention: prefix with [ERROR] so the
    # model can react. Keeps the round-trip lossless for the test.
    if event.is_error:
        out["output"] = f"[ERROR] {content}"
    return out


def normalized_to_sdk_history(events: list[ConsoleEvent]) -> list[dict]:
    """Build an openai-agents ``Runner.run_streamed(input=...)``-compatible
    list of input items from a sequence of normalized console events.

    Returned shape::

        [
            {"role": "user", "content": "..."},
            {"role": "assistant", "content": "..."},
            {"type": "function_call", "name": "...", "arguments": "...",
             "call_id": "..."},
            {"type": "function_call_output", "call_id": "...", "output": "..."},
            ...
        ]

    Rules:

    * ``operator_input`` → ``{"role": "user", "content": "..."}``
    * ``agent_text`` → ``{"role": "assistant", "content": "..."}``
    * ``tool_call`` → ``{"type": "function_call", ...}``
    * ``tool_result`` → ``{"type": "function_call_output", ...}``
    * ``agent_thinking``, ``permission``, ``session_meta``, ``error``:
      skipped (no equivalent input-item shape).
    * Empty ``agent_text`` events produce no input item.
    * Tool calls / results missing their id link are silently
      dropped (the SDK rejects them).

    Unlike the Claude translator we don't enforce strict role
    alternation — openai-agents accepts adjacent same-role items.
    """
    out: list[dict[str, Any]] = []
    for event in events:
        kind = event.kind
        item: dict[str, Any] | None = None
        if kind == "operator_input":
            item = _operator_input_to_message(event)
        elif kind == "agent_text":
            item = _agent_text_to_message(event)
        elif kind == "tool_call":
            item = _tool_call_to_input_item(event)
        elif kind == "tool_result":
            item = _tool_result_to_input_item(event)
        # else: skip silently — kinds without an input-item analog
        # (thinking, permission, session_meta, error) don't belong in
        # the SDK's model-input view.
        if item is not None:
            out.append(item)
    return out


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


register_translator(
    Translator(
        backend=_BACKEND_NAME,
        acp_to_normalized=acp_to_normalized,
        normalized_to_sdk_history=normalized_to_sdk_history,
    )
)
