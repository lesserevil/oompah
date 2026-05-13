"""Claude-backend console event translator.

Translates between the AgentEvent stream produced by
:mod:`oompah.acp_backends.claude` (``acp_*`` kinds) and the normalized
:class:`oompah.console_format.ConsoleEvent` form, and reconstructs a
Claude-API-compatible conversation history (the ``history=`` argument
hand-off to :meth:`AcpAgentSession.start_session` in the downstream
ConsoleSession bead, oompah-zlz_2-49tv).

Mapping table (claude AgentEvent.event → ConsoleEvent.kind):

============================  =================  =======================
AgentEvent.event              ConsoleEvent.kind  Fields carried
============================  =================  =======================
``acp_session_start``         ``session_meta``   model, args (full payload)
``acp_text``                  ``agent_text``     text, model, usage
``acp_thinking``              ``agent_thinking`` text, model
``acp_tool_use``              ``tool_call``      tool, args (with
                                                  ``_tool_use_id`` link)
``acp_tool_result``           ``tool_result``    result, is_error,
                                                  ``result["tool_use_id"]``
``acp_permission_grant``      ``permission``     tool, args, is_error=False
``acp_permission_deny``       ``permission``     tool, args, is_error=True
``acp_assistant_error``       ``error``          text, is_error=True
``acp_session_error``         ``error``          text, is_error=True
``acp_turn_timeout``          ``error``          text, is_error=True
``acp_result``                ``session_meta``   usage, args (full payload)
*anything else*               ``session_meta``   raw_event_kind preserved
============================  =================  =======================

The SDK-history builder is intentionally Anthropic-API-shaped: a
``list[dict]`` of ``{"role": "user"|"assistant", "content": [...]}``
messages with interleaved tool_use / tool_result blocks. Adjacent
events that belong on the same role are coalesced into one message so
the alternating-role invariant the API requires is preserved.
"""

from __future__ import annotations

import datetime as _dt
import logging
from typing import Any

from oompah.console_format import ConsoleEvent
from oompah.console_translators import (  # noqa: F401 — circular OK at import time
    Translator,
    register_translator,
)

logger = logging.getLogger(__name__)


_BACKEND_NAME = "claude"


# ---------------------------------------------------------------------------
# AgentEvent → ConsoleEvent
# ---------------------------------------------------------------------------


def _format_ts(timestamp: float | int | None) -> str:
    """Convert a unix-epoch timestamp to ISO-8601 with second precision.

    The console JSONL uses string ISO-8601 timestamps (see
    ``oompah.console_store``). ``AgentEvent.timestamp`` is a float
    seconds-since-epoch produced by ``time.time()``. We use UTC + Z
    suffix so chronological string compare matches event order.
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


def acp_to_normalized(acp_event: Any) -> ConsoleEvent:
    """Translate one claude-backend :class:`oompah.agent.AgentEvent` to
    a :class:`ConsoleEvent`.

    See the module docstring for the mapping table.

    Unknown AgentEvent kinds map to ``"session_meta"`` with the
    original kind preserved in ``raw_event_kind`` so the console UI
    still shows them and a future-aware reader can recover the
    backend-specific shape.
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
# Normalized events → Claude-SDK history
# ---------------------------------------------------------------------------


def _operator_input_to_message(event: ConsoleEvent) -> dict[str, Any]:
    """Build a Claude-API ``user`` message from an operator input event.

    Attachments are surfaced as additional ``text`` blocks (one per
    attachment path) so they survive the round-trip. The SDK's
    multimodal block types (``image``, ``document``) are not assumed
    here — re-staging file content is the caller's job; this helper
    just preserves the *reference*. See ``plans/multimodal-
    attachments.md`` for the staging contract.
    """
    blocks: list[dict[str, Any]] = []
    if event.text:
        blocks.append({"type": "text", "text": event.text})
    if event.attachments:
        for path in event.attachments:
            blocks.append({"type": "text", "text": f"[attachment: {path}]"})
    if not blocks:
        # Empty user turn would be rejected by the API; keep a marker.
        blocks.append({"type": "text", "text": ""})
    return {"role": "user", "content": blocks}


def _tool_call_block(event: ConsoleEvent) -> dict[str, Any] | None:
    """Convert a normalized ``tool_call`` event into an assistant
    ``tool_use`` block. Returns ``None`` when the event lacks the
    required ``_tool_use_id`` link (the API rejects tool_use without
    an id, and dropping the unanchored entry preserves a usable
    history)."""
    args = dict(event.args or {})
    tool_use_id = args.pop("_tool_use_id", None)
    if not tool_use_id:
        return None
    # The reconstructed raw input the assistant *would have* sent.
    raw_input = args.pop("_raw_input", None)
    if raw_input is not None and not args:
        input_payload: Any = raw_input
    else:
        input_payload = args
    return {
        "type": "tool_use",
        "id": str(tool_use_id),
        "name": event.tool or "",
        "input": input_payload,
    }


def _tool_result_block(event: ConsoleEvent) -> dict[str, Any] | None:
    """Convert a normalized ``tool_result`` event into a user-side
    ``tool_result`` block. Returns ``None`` when the event lacks the
    backref ``tool_use_id`` — same rationale as :func:`_tool_call_block`."""
    result = dict(event.result or {})
    tool_use_id = result.get("tool_use_id")
    if not tool_use_id:
        return None
    content = result.get("content", "")
    out: dict[str, Any] = {
        "type": "tool_result",
        "tool_use_id": str(tool_use_id),
        "content": content,
    }
    if event.is_error:
        out["is_error"] = True
    return out


def normalized_to_sdk_history(events: list[ConsoleEvent]) -> list[dict]:
    """Build a Claude-API conversation history from normalized events.

    Returned shape::

        [
            {"role": "user", "content": [{"type": "text", "text": "..."}]},
            {"role": "assistant", "content": [
                {"type": "text", "text": "..."},
                {"type": "tool_use", "id": "...", "name": "...", "input": {...}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "...", "content": "..."},
            ]},
            ...
        ]

    Rules:

    * ``operator_input`` becomes a ``user`` message (one per event).
    * ``agent_text`` / ``tool_call`` accumulate into the current
      ``assistant`` message (coalesced across consecutive events).
    * ``tool_result`` accumulates into the next ``user`` message
      (since Anthropic requires tool_results in a user turn).
    * ``agent_thinking``, ``permission``, ``session_meta``, ``error``
      are skipped — they don't belong in the model-input history. A
      future iteration could surface them via system messages, but
      today they only matter for the UI.
    * Adjacent same-role messages are emitted as one message (the API
      requires strict alternation).
    * Tool_call / tool_result entries missing their ID link are
      silently dropped — the API rejects unanchored tool blocks.

    The output never has two adjacent messages with the same role.
    """
    out: list[dict[str, Any]] = []
    # Buffers for the in-progress assistant / user-tool-result message.
    pending_assistant: list[dict[str, Any]] = []
    pending_tool_results: list[dict[str, Any]] = []

    def _flush_assistant() -> None:
        if pending_assistant:
            out.append({"role": "assistant", "content": list(pending_assistant)})
            pending_assistant.clear()

    def _flush_tool_results() -> None:
        if pending_tool_results:
            # Coalesce with the trailing user message if it would be
            # adjacent; otherwise emit a fresh user message.
            if out and out[-1]["role"] == "user":
                out[-1]["content"].extend(pending_tool_results)
            else:
                out.append({"role": "user", "content": list(pending_tool_results)})
            pending_tool_results.clear()

    for event in events:
        kind = event.kind

        if kind == "operator_input":
            # User input forces a role boundary — flush any in-progress
            # assistant blocks first, then any pending tool_results
            # (they fold into the *new* user message naturally).
            _flush_assistant()
            msg = _operator_input_to_message(event)
            if pending_tool_results:
                # Place tool_result blocks BEFORE the new operator
                # text. This mirrors how the SDK actually streams: a
                # tool turn must be closed before the user's next
                # message.
                msg["content"] = list(pending_tool_results) + list(msg["content"])
                pending_tool_results.clear()
            out.append(msg)
            continue

        if kind == "agent_text":
            # Tool results pending → they must close the prior tool
            # turn (user side) before the assistant speaks again.
            _flush_tool_results()
            if event.text:
                pending_assistant.append({"type": "text", "text": event.text})
            continue

        if kind == "tool_call":
            _flush_tool_results()
            block = _tool_call_block(event)
            if block is not None:
                pending_assistant.append(block)
            continue

        if kind == "tool_result":
            # Assistant tool_use blocks must be closed before the
            # corresponding tool_result lands.
            _flush_assistant()
            block = _tool_result_block(event)
            if block is not None:
                pending_tool_results.append(block)
            continue

        # agent_thinking / permission / session_meta / error: skip
        # silently. They're useful for the console UI but not for
        # rebuilding the SDK's model-input view.
        continue

    # Drain trailing buffers in the legal order: assistant first, then
    # any orphan tool_results as a final user message.
    _flush_assistant()
    _flush_tool_results()

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
