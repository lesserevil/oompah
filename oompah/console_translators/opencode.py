"""OpenCode ACP backend console event translator (oompah-zlz_2-recu).

Translates between the :class:`AgentEvent` stream produced by the
OpenCode ACP backend (``acp_*`` kinds — identical vocabulary to the
Claude and Codex backends) and the normalized
:class:`ConsoleEvent` form, and reconstructs an openai-agents-SDK-
compatible ``input`` list for replay.

Mapping table (acp_event.event → ConsoleEvent.kind):

============================  =================  =======================
acp_event.event               ConsoleEvent.kind  Notes
============================  =================  =======================
``acp_text``                   ``agent_text``     text from payload["text"]
``acp_thinking``              ``agent_thinking`` text from payload["text"]
``acp_tool_use``              ``tool_call``       tool name + args from payload
``acp_tool_result``           ``tool_result``     result content from payload
``acp_permission_grant``      ``permission``      is_error=False
``acp_permission_deny``       ``permission``      is_error=True
``acp_assistant_error``       ``error``          is_error=True
``acp_session_error``         ``error``          is_error=True
``acp_turn_timeout``          ``error``          is_error=True, text="turn
                                                     timeout after Xs"
``acp_session_start``         ``session_meta`` model + args from payload
``acp_result``                ``session_meta`` is_error from payload
*anything else*               ``session_meta`` raw_event_kind preserved
============================  =================  =======================

SDK history shape (openai-agents input items):

* ``operator_input`` → ``{"role": "user", "content": "..."}``
* ``agent_text`` → ``{"role": "assistant", "content": "..."}``
* ``tool_call`` → ``{"type": "function_call", "name": "...",
  "arguments": "...", "call_id": "..."}``
* ``tool_result`` → ``{"type": "function_call_output",
  "call_id": "...", "output": "..."}``
* ``agent_thinking``, ``permission``, ``session_meta``, ``error``:
  skipped silently.

Arguments in ``function_call`` items must be a JSON-encoded string,
NOT a dict — per the OpenAI Responses API spec.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
from typing import Any

from oompah.console_format import ConsoleEvent
from oompah.console_translators import Translator, register_translator

logger = logging.getLogger(__name__)


_BACKEND_NAME = "opencode"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_ts(timestamp: float | int | None) -> str:
    """Convert a unix-epoch timestamp to ISO-8601 UTC with microsecond
    precision (suffix ``Z``). Mirrors the codex translator helper."""
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
    """Translate one OpenCode-backend :class:`AgentEvent` to a
    :class:`ConsoleEvent`.

    See the module docstring for the mapping table. Stamps
    ``backend="opencode"`` on every output.
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

    # --- agent thinking ---
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

    Returns ``None`` for empty input so the SDK doesn't see a
    degenerate empty user message.
    """
    parts: list[str] = []
    if event.text:
        parts.append(event.text)
    if event.attachments:
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
    ``function_call`` input item.

    Returns ``None`` when the event lacks the required ``_tool_use_id``
    link — the SDK rejects unanchored function calls.

    Arguments are JSON-encoded as a string per the Responses API spec.
    """
    args = dict(event.args or {})
    tool_use_id = args.pop("_tool_use_id", None)
    if not tool_use_id:
        return None
    raw_input = args.pop("_raw_input", None)
    if raw_input is not None and not args:
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
            arguments_str = json.dumps({})
    return {
        "type": "function_call",
        "name": event.tool or "",
        "arguments": arguments_str,
        "call_id": str(tool_use_id),
    }


def _tool_result_to_input_item(event: ConsoleEvent) -> dict[str, Any] | None:
    """Convert a normalized tool_result event into an openai-agents
    ``function_call_output`` input item.

    Returns ``None`` if no ``tool_use_id`` link is present.
    """
    result = dict(event.result or {})
    tool_use_id = result.get("tool_use_id")
    if not tool_use_id:
        return None
    content = result.get("content", "")
    if not isinstance(content, str):
        try:
            content = json.dumps(content)
        except (TypeError, ValueError):
            content = str(content)
    out: dict[str, Any] = {
        "type": "function_call_output",
        "call_id": str(tool_use_id),
        "output": content,
    }
    if event.is_error:
        out["output"] = f"[ERROR] {content}"
    return out


def normalized_to_sdk_history(events: list[ConsoleEvent]) -> list[dict]:
    """Build an openai-agents ``Runner.run_streamed(input=...)``-compatible
    list of input items from a sequence of normalized ConsoleEvents.

    Rules:

    * ``operator_input`` → ``{"role": "user", "content": "..."}``
    * ``agent_text`` → ``{"role": "assistant", "content": "..."}``
    * ``tool_call`` → ``{"type": "function_call", ...}``
    * ``tool_result`` → ``{"type": "function_call_output", ...}``
    * ``agent_thinking``, ``permission``, ``session_meta``, ``error``:
      skipped silently
    * Empty ``agent_text`` events produce no input item.
    * Tool calls / results missing their id link are silently dropped.
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