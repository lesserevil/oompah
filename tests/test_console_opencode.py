"""Tests for the OpenCode-backend console translator
(oompah-zlz_2-recu).

Parallels :mod:`tests.test_console_translator_codex` — same per-kind
mapping coverage plus SDK-history shape assertions adapted for opencode.
"""

from __future__ import annotations

import json

import pytest

from oompah.agent import AgentEvent
from oompah.console_format import ConsoleEvent, make_operator_input
from oompah.console_translators import (
    acp_to_normalized as dispatch_acp_to_normalized,
    normalized_to_sdk_history as dispatch_normalized_to_sdk_history,
    get_translator,
    known_backends,
)
from oompah.console_translators.opencode import (
    acp_to_normalized,
    normalized_to_sdk_history,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ev(event: str, payload: dict | None = None, usage: dict | None = None) -> AgentEvent:
    """Build an AgentEvent matching what the OpenCode ACP backend emits."""
    return AgentEvent(
        event=event,
        timestamp=1700000000.0,
        agent_pid=None,
        usage=usage,
        payload=payload or {},
    )


# ---------------------------------------------------------------------------
# Per-kind mapping
# ---------------------------------------------------------------------------


class TestKindMapping:
    """Every acp_* event from the OpenCode backend should produce a
    backend='opencode' stamped ConsoleEvent of the right kind."""

    def test_acp_session_start_to_session_meta(self):
        ev = _ev(
            "acp_session_start",
            {
                "model": "opencode-model",
                "max_turns": 50,
                "permission_mode": "acceptedits",
                "cwd": "/workspace",
            },
        )
        norm = acp_to_normalized(ev)
        assert norm.kind == "session_meta"
        assert norm.backend == "opencode"
        assert norm.model == "opencode-model"
        assert norm.raw_event_kind == "acp_session_start"
        assert norm.args["permission_mode"] == "acceptedits"

    def test_acp_text_to_agent_text(self):
        ev = _ev(
            "acp_text",
            {"text": "hi from opencode"},
            usage={"input_tokens": 5, "output_tokens": 3, "total_tokens": 8},
        )
        norm = acp_to_normalized(ev)
        assert norm.kind == "agent_text"
        assert norm.backend == "opencode"
        assert norm.text == "hi from opencode"
        assert norm.usage == {"input_tokens": 5, "output_tokens": 3, "total_tokens": 8}

    def test_acp_thinking_to_agent_thinking(self):
        ev = _ev("acp_thinking", {"text": "reasoning about it..."})
        norm = acp_to_normalized(ev)
        assert norm.kind == "agent_thinking"
        assert norm.backend == "opencode"
        assert norm.text == "reasoning about it..."

    def test_acp_tool_use_to_tool_call(self):
        ev = _ev(
            "acp_tool_use",
            {"tool": "read_file", "input": {"path": "README.md"}, "id": "tu_42"},
        )
        norm = acp_to_normalized(ev)
        assert norm.kind == "tool_call"
        assert norm.backend == "opencode"
        assert norm.tool == "read_file"
        assert norm.args == {"path": "README.md", "_tool_use_id": "tu_42"}

    def test_acp_tool_use_with_string_input(self):
        ev = _ev(
            "acp_tool_use",
            {"tool": "run_command", "input": "<truncated repr>", "id": "tu_x"},
        )
        norm = acp_to_normalized(ev)
        assert norm.kind == "tool_call"
        assert norm.args == {"_raw_input": "<truncated repr>", "_tool_use_id": "tu_x"}

    def test_acp_tool_result_to_tool_result(self):
        ev = _ev(
            "acp_tool_result",
            {"tool_use_id": "tu_42", "is_error": False, "content": "file contents"},
        )
        norm = acp_to_normalized(ev)
        assert norm.kind == "tool_result"
        assert norm.backend == "opencode"
        assert norm.is_error is False
        assert norm.result == {"tool_use_id": "tu_42", "content": "file contents"}

    def test_acp_tool_result_error(self):
        ev = _ev(
            "acp_tool_result",
            {"tool_use_id": "tu_42", "is_error": True, "content": "ENOENT"},
        )
        norm = acp_to_normalized(ev)
        assert norm.is_error is True
        assert norm.result["content"] == "ENOENT"

    def test_acp_permission_grant_to_permission(self):
        ev = _ev(
            "acp_permission_grant",
            {"tool": "mcp__oompah__read_file", "input": {"path": "x"}},
        )
        norm = acp_to_normalized(ev)
        assert norm.kind == "permission"
        assert norm.backend == "opencode"
        assert norm.is_error is False
        assert norm.raw_event_kind == "acp_permission_grant"

    def test_acp_permission_deny_is_error(self):
        ev = _ev(
            "acp_permission_deny",
            {"tool": "Bash", "input": {"command": "rm -rf /"}},
        )
        norm = acp_to_normalized(ev)
        assert norm.kind == "permission"
        assert norm.backend == "opencode"
        assert norm.is_error is True
        assert norm.raw_event_kind == "acp_permission_deny"

    def test_acp_assistant_error_to_error(self):
        ev = _ev("acp_assistant_error", {"error": "rate limit"})
        norm = acp_to_normalized(ev)
        assert norm.kind == "error"
        assert norm.backend == "opencode"
        assert norm.text == "rate limit"
        assert norm.is_error is True

    def test_acp_session_error_to_error(self):
        ev = _ev("acp_session_error", {"error": "connection reset"})
        norm = acp_to_normalized(ev)
        assert norm.kind == "error"
        assert norm.backend == "opencode"
        assert norm.text == "connection reset"
        assert norm.is_error is True

    def test_acp_turn_timeout_to_error(self):
        ev = _ev("acp_turn_timeout", {"timeout_s": 3600.0})
        norm = acp_to_normalized(ev)
        assert norm.kind == "error"
        assert norm.backend == "opencode"
        assert "3600" in (norm.text or "")
        assert norm.is_error is True

    def test_acp_result_to_session_meta(self):
        ev = _ev(
            "acp_result",
            {
                "subtype": "success",
                "is_error": False,
                "stop_reason": "end_turn",
                "num_turns": 3,
                "total_cost_usd": 0.001,
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "total_tokens": 150,
                    "cost_usd": 0.001,
                },
            },
            usage={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
        )
        norm = acp_to_normalized(ev)
        assert norm.kind == "session_meta"
        assert norm.raw_event_kind == "acp_result"
        assert norm.args["subtype"] == "success"
        assert norm.is_error is False

    def test_acp_result_with_error(self):
        ev = _ev("acp_result", {"is_error": True, "errors": ["something broke"]})
        norm = acp_to_normalized(ev)
        assert norm.kind == "session_meta"
        assert norm.is_error is True

    def test_unknown_event_falls_into_session_meta(self):
        ev = _ev("acp_brand_new_event", {"foo": "bar"})
        norm = acp_to_normalized(ev)
        assert norm.kind == "session_meta"
        assert norm.backend == "opencode"
        assert norm.raw_event_kind == "acp_brand_new_event"
        assert norm.args == {"foo": "bar"}


class TestBackendStamp:
    """Every translated OpenCode event must stamp backend='opencode'."""

    def test_every_kind_has_backend_stamp(self):
        kinds = [
            ("acp_session_start", {"model": "m"}),
            ("acp_text", {"text": "hi"}),
            ("acp_thinking", {"text": "hi"}),
            ("acp_tool_use", {"tool": "t", "input": {}, "id": "tu"}),
            ("acp_tool_result", {"tool_use_id": "tu", "content": "x"}),
            ("acp_permission_grant", {"tool": "t", "input": {}}),
            ("acp_permission_deny", {"tool": "t", "input": {}}),
            ("acp_assistant_error", {"error": "x"}),
            ("acp_session_error", {"error": "x"}),
            ("acp_turn_timeout", {"timeout_s": 1.0}),
            ("acp_result", {"is_error": False}),
            ("acp_made_up", {}),
        ]
        for evt_name, payload in kinds:
            norm = acp_to_normalized(_ev(evt_name, payload))
            assert norm.backend == "opencode", f"missing opencode stamp for {evt_name}"


# ---------------------------------------------------------------------------
# Timestamp formatting
# ---------------------------------------------------------------------------


class TestTimestamp:
    def test_float_timestamp_becomes_iso_z(self):
        ev = _ev("acp_text", {"text": "x"})
        ev.timestamp = 1700000000.0
        norm = acp_to_normalized(ev)
        assert norm.ts.startswith("2023-11-14T22:13:20")
        assert norm.ts.endswith("Z")

    def test_none_timestamp_becomes_empty_string(self):
        ev = _ev("acp_text", {"text": "x"})
        ev.timestamp = None  # type: ignore[assignment]
        norm = acp_to_normalized(ev)
        assert norm.ts == ""


# ---------------------------------------------------------------------------
# normalized_to_sdk_history
# ---------------------------------------------------------------------------


class TestSdkHistory:
    """The opencode history shape is a list of openai-agents input items:
    plain ``{role, content}`` for messages, ``{type:function_call,...}``
    and ``{type:function_call_output,...}`` for tool turns."""

    def test_empty_input_returns_empty_list(self):
        assert normalized_to_sdk_history([]) == []

    def test_operator_input_becomes_user_message(self):
        op = make_operator_input("t1", "hello world")
        history = normalized_to_sdk_history([op])
        assert history == [{"role": "user", "content": "hello world"}]

    def test_operator_input_empty_text_no_attachments_skipped(self):
        op = make_operator_input("t1", "")
        history = normalized_to_sdk_history([op])
        assert history == []

    def test_operator_input_with_attachments_inlines_paths(self):
        op = make_operator_input(
            "t", "look at these", attachments=["/tmp/a.png", "/tmp/b.txt"]
        )
        history = normalized_to_sdk_history([op])
        assert len(history) == 1
        item = history[0]
        assert item["role"] == "user"
        assert "look at these" in item["content"]
        assert "[attachment: /tmp/a.png]" in item["content"]
        assert "[attachment: /tmp/b.txt]" in item["content"]

    def test_agent_text_becomes_assistant_message(self):
        events = [
            make_operator_input("t1", "go"),
            ConsoleEvent(ts="t2", kind="agent_text", backend="opencode", text="here you go"),
        ]
        history = normalized_to_sdk_history(events)
        assert history == [
            {"role": "user", "content": "go"},
            {"role": "assistant", "content": "here you go"},
        ]

    def test_empty_agent_text_produces_no_item(self):
        events = [
            make_operator_input("t1", "go"),
            ConsoleEvent(ts="t2", kind="agent_text", backend="opencode", text=""),
        ]
        history = normalized_to_sdk_history(events)
        assert history == [{"role": "user", "content": "go"}]

    def test_tool_call_becomes_function_call_item(self):
        events = [
            make_operator_input("t1", "read README"),
            ConsoleEvent(
                ts="t2",
                kind="tool_call",
                backend="opencode",
                tool="read_file",
                args={"path": "README.md", "_tool_use_id": "tu_1"},
            ),
        ]
        history = normalized_to_sdk_history(events)
        assert history[0] == {"role": "user", "content": "read README"}
        call = history[1]
        assert call["type"] == "function_call"
        assert call["name"] == "read_file"
        assert call["call_id"] == "tu_1"
        # Arguments must be a JSON-encoded string.
        assert isinstance(call["arguments"], str)
        assert json.loads(call["arguments"]) == {"path": "README.md"}

    def test_tool_call_arguments_are_json_encoded_strings_not_dicts(self):
        """Arguments field must be a JSON-encoded string per the SDK spec."""
        events = [
            ConsoleEvent(
                ts="t2",
                kind="tool_call",
                backend="opencode",
                tool="run_command",
                args={"command": "ls -la", "_tool_use_id": "tu_x"},
            ),
        ]
        history = normalized_to_sdk_history(events)
        arg = history[0]["arguments"]
        assert isinstance(arg, str)
        # Should be parseable as JSON.
        assert json.loads(arg) == {"command": "ls -la"}

    def test_tool_call_with_raw_input_string(self):
        """A truncated string ``_raw_input`` is passed through verbatim."""
        events = [
            ConsoleEvent(
                ts="t2",
                kind="tool_call",
                backend="opencode",
                tool="run_command",
                args={"_raw_input": "<truncated>", "_tool_use_id": "tu_x"},
            ),
        ]
        history = normalized_to_sdk_history(events)
        assert history[0]["arguments"] == "<truncated>"
        assert history[0]["call_id"] == "tu_x"

    def test_tool_result_becomes_function_call_output(self):
        events = [
            make_operator_input("t1", "go"),
            ConsoleEvent(
                ts="t2",
                kind="tool_call",
                backend="opencode",
                tool="read_file",
                args={"path": "x", "_tool_use_id": "tu_1"},
            ),
            ConsoleEvent(
                ts="t3",
                kind="tool_result",
                backend="opencode",
                result={"tool_use_id": "tu_1", "content": "file body"},
            ),
        ]
        history = normalized_to_sdk_history(events)
        kinds = [item.get("type") or item.get("role") for item in history]
        assert kinds == ["user", "function_call", "function_call_output"]
        assert history[-1] == {
            "type": "function_call_output",
            "call_id": "tu_1",
            "output": "file body",
        }

    def test_tool_result_with_is_error_prefixes_output(self):
        events = [
            ConsoleEvent(
                ts="t3",
                kind="tool_result",
                backend="opencode",
                result={"tool_use_id": "tu_1", "content": "ENOENT"},
                is_error=True,
            ),
        ]
        history = normalized_to_sdk_history(events)
        assert history[0]["output"].startswith("[ERROR]")
        assert "ENOENT" in history[0]["output"]

    def test_tool_result_dict_content_json_encoded(self):
        events = [
            ConsoleEvent(
                ts="t3",
                kind="tool_result",
                backend="opencode",
                result={"tool_use_id": "tu_1", "content": {"k": "v"}},
            ),
        ]
        history = normalized_to_sdk_history(events)
        assert history[0]["output"] == '{"k": "v"}'

    def test_thinking_permission_session_meta_error_skipped(self):
        events = [
            make_operator_input("t1", "go"),
            ConsoleEvent(ts="t2", kind="agent_thinking", text="thinking..."),
            ConsoleEvent(ts="t3", kind="permission", tool="read_file"),
            ConsoleEvent(ts="t4", kind="session_meta", model="opencode-model"),
            ConsoleEvent(ts="t5", kind="error", text="boom", is_error=True),
            ConsoleEvent(ts="t6", kind="agent_text", text="visible reply"),
        ]
        history = normalized_to_sdk_history(events)
        assert history == [
            {"role": "user", "content": "go"},
            {"role": "assistant", "content": "visible reply"},
        ]

    def test_tool_call_missing_id_dropped(self):
        events = [
            make_operator_input("t1", "go"),
            ConsoleEvent(
                ts="t2",
                kind="tool_call",
                tool="read_file",
                args={"path": "x"},  # no _tool_use_id!
            ),
            ConsoleEvent(ts="t3", kind="agent_text", text="done"),
        ]
        history = normalized_to_sdk_history(events)
        # function_call dropped; user + assistant remain.
        assert history == [
            {"role": "user", "content": "go"},
            {"role": "assistant", "content": "done"},
        ]

    def test_tool_result_missing_id_dropped(self):
        events = [
            ConsoleEvent(
                ts="t3",
                kind="tool_result",
                result={"content": "data"},  # no tool_use_id!
            ),
        ]
        history = normalized_to_sdk_history(events)
        assert history == []

    def test_alternating_roles_allowed(self):
        """openai-agents accepts adjacent same-role messages."""
        events = [
            make_operator_input("t1", "go"),
            ConsoleEvent(ts="t2", kind="agent_text", text="part 1"),
            ConsoleEvent(ts="t3", kind="agent_text", text="part 2"),
        ]
        history = normalized_to_sdk_history(events)
        assert [m.get("role") or m.get("type") for m in history] == [
            "user", "assistant", "assistant"
        ]

    def test_round_trip_full_conversation(self):
        """End-to-end: synthetic AgentEvent stream → normalized →
        SDK history produces an input-item list the openai-agents SDK
        can consume verbatim."""
        events_in = [
            _ev("acp_session_start", {"model": "opencode-model"}),
            _ev("acp_text", {"text": "Hello operator"}),
            _ev(
                "acp_tool_use",
                {"tool": "read_file", "input": {"path": "README.md"}, "id": "tu_123"},
            ),
            _ev(
                "acp_tool_result",
                {"tool_use_id": "tu_123", "is_error": False, "content": "contents"},
            ),
            _ev("acp_text", {"text": "I have read the file"}),
            _ev("acp_result", {"subtype": "success", "is_error": False}),
        ]
        normalized = [acp_to_normalized(e) for e in events_in]
        op = make_operator_input("t0", "please read the README")
        history = normalized_to_sdk_history([op] + normalized)

        for item in history:
            assert isinstance(item, dict)
            assert ("role" in item) ^ ("type" in item), item
            if "role" in item:
                assert item["role"] in ("user", "assistant", "system")
                assert "content" in item
                assert isinstance(item["content"], str)
            else:
                assert item["type"] in ("function_call", "function_call_output")
                if item["type"] == "function_call":
                    assert "arguments" in item and isinstance(item["arguments"], str)
                    assert "call_id" in item
                    assert "name" in item
                else:
                    assert "call_id" in item
                    assert "output" in item

        # All four "model-input" turns should be present (session events excluded).
        assert len(history) == 5


# ---------------------------------------------------------------------------
# Dispatch wrapper sanity
# ---------------------------------------------------------------------------


class TestDispatch:
    def test_opencode_in_known_backends(self):
        assert "opencode" in known_backends()

    def test_get_translator_opencode(self):
        assert get_translator("opencode").backend == "opencode"

    def test_explicit_opencode_dispatch_matches_direct(self):
        ev = _ev("acp_text", {"text": "x"})
        direct = acp_to_normalized(ev)
        dispatched = dispatch_acp_to_normalized(ev, backend="opencode")
        assert direct == dispatched

    def test_history_dispatch_matches_direct(self):
        events = [
            make_operator_input("t1", "hi"),
            ConsoleEvent(ts="t2", kind="agent_text", text="hello"),
        ]
        direct = normalized_to_sdk_history(events)
        dispatched = dispatch_normalized_to_sdk_history(events, backend="opencode")
        assert direct == dispatched


# ---------------------------------------------------------------------------
# Normalized round-trip via to_dict / from_dict
# ---------------------------------------------------------------------------


class TestNormalizedRoundTripViaJson:
    """Every opencode event kind round-trips cleanly through dict form."""

    @pytest.mark.parametrize(
        "evt_name,payload",
        [
            ("acp_session_start", {"model": "m", "cwd": "/"}),
            ("acp_text", {"text": "x"}),
            ("acp_thinking", {"text": "x"}),
            ("acp_tool_use", {"tool": "t", "input": {"a": 1}, "id": "tu"}),
            ("acp_tool_result", {"tool_use_id": "tu", "content": "x", "is_error": False}),
            ("acp_permission_grant", {"tool": "t", "input": {"a": 1}}),
            ("acp_permission_deny", {"tool": "t", "input": {"a": 1}}),
            ("acp_assistant_error", {"error": "boom"}),
            ("acp_session_error", {"error": "boom"}),
            ("acp_turn_timeout", {"timeout_s": 60.0}),
            ("acp_result", {"is_error": False, "subtype": "success"}),
            ("acp_unknown", {"foo": "bar"}),
        ],
    )
    def test_kind_round_trip(self, evt_name, payload):
        ev = _ev(evt_name, payload)
        norm = acp_to_normalized(ev)
        assert ConsoleEvent.from_dict(norm.to_dict()) == norm