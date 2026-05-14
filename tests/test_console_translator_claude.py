"""Tests for the Claude-backend console translator.

Acceptance criteria from oompah-zlz_2-hoop:

* Each acp_event kind → normalized kind mapping
* Tool-call event with args / tool-result event with output
* normalized_to_sdk_history produces alternating roles
* Unknown acp_event kind falls into session_meta with raw_event_kind set
* An operator_input event with attachments materializes as a `user` message
* Round-trip: synthetic AgentEvent stream → normalized → SDK history
  produces a shape the Claude SDK accepts (mocked)
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from oompah.agent import AgentEvent
from oompah.console_format import (
    NORMALIZED_KINDS,
    ConsoleEvent,
    make_operator_input,
)
from oompah.console_translators import (
    acp_to_normalized as dispatch_acp_to_normalized,
    get_translator,
    known_backends,
    normalized_to_sdk_history as dispatch_normalized_to_sdk_history,
)
from oompah.console_translators.claude import (
    acp_to_normalized,
    normalized_to_sdk_history,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ev(event: str, payload: dict | None = None, usage: dict | None = None) -> AgentEvent:
    """Build an AgentEvent matching what claude.py emits."""
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
    def test_acp_session_start_to_session_meta(self):
        ev = _ev(
            "acp_session_start",
            {
                "model": "claude-sonnet-4",
                "fallback_model": None,
                "max_turns": 50,
                "tool_policy": "strict_allowlist:mcp__oompah__*",
                "cwd": "/workspace",
            },
        )
        norm = acp_to_normalized(ev)
        assert norm.kind == "session_meta"
        assert norm.backend == "claude"
        assert norm.model == "claude-sonnet-4"
        assert norm.raw_event_kind == "acp_session_start"
        assert norm.args["cwd"] == "/workspace"

    def test_acp_text_to_agent_text(self):
        ev = _ev("acp_text", {"text": "hello"}, usage={"input_tokens": 5, "output_tokens": 3, "total_tokens": 8})
        norm = acp_to_normalized(ev)
        assert norm.kind == "agent_text"
        assert norm.text == "hello"
        assert norm.usage == {"input_tokens": 5, "output_tokens": 3, "total_tokens": 8}

    def test_acp_thinking_to_agent_thinking(self):
        ev = _ev("acp_thinking", {"text": "thinking..."})
        norm = acp_to_normalized(ev)
        assert norm.kind == "agent_thinking"
        assert norm.text == "thinking..."

    def test_acp_tool_use_to_tool_call_with_args(self):
        ev = _ev(
            "acp_tool_use",
            {"tool": "read_file", "input": {"path": "README.md"}, "id": "tu_42"},
        )
        norm = acp_to_normalized(ev)
        assert norm.kind == "tool_call"
        assert norm.tool == "read_file"
        # Original tool input fields preserved, plus a synthetic
        # _tool_use_id link for SDK-history reconstruction.
        assert norm.args == {"path": "README.md", "_tool_use_id": "tu_42"}

    def test_acp_tool_use_with_string_input_kept_under_raw_input_key(self):
        # When the SDK truncates large inputs into a string repr, the
        # translator should keep it under a synthetic key so the
        # round-trip is lossless.
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
            {
                "tool_use_id": "tu_42",
                "is_error": False,
                "content": "file contents...",
            },
        )
        norm = acp_to_normalized(ev)
        assert norm.kind == "tool_result"
        assert norm.is_error is False
        assert norm.result == {"tool_use_id": "tu_42", "content": "file contents..."}

    def test_acp_tool_result_error(self):
        ev = _ev(
            "acp_tool_result",
            {"tool_use_id": "tu_42", "is_error": True, "content": "ENOENT"},
        )
        norm = acp_to_normalized(ev)
        assert norm.kind == "tool_result"
        assert norm.is_error is True
        assert norm.result["content"] == "ENOENT"

    def test_acp_permission_grant_to_permission(self):
        ev = _ev(
            "acp_permission_grant",
            {"tool": "mcp__oompah__read_file", "input": {"path": "x"}},
        )
        norm = acp_to_normalized(ev)
        assert norm.kind == "permission"
        assert norm.tool == "mcp__oompah__read_file"
        assert norm.args == {"path": "x"}
        assert norm.is_error is False
        assert norm.raw_event_kind == "acp_permission_grant"

    def test_acp_permission_deny_to_permission_is_error_true(self):
        ev = _ev(
            "acp_permission_deny",
            {"tool": "Bash", "input": {"command": "rm -rf /"}},
        )
        norm = acp_to_normalized(ev)
        assert norm.kind == "permission"
        assert norm.tool == "Bash"
        assert norm.is_error is True
        assert norm.raw_event_kind == "acp_permission_deny"

    def test_acp_assistant_error_to_error(self):
        ev = _ev("acp_assistant_error", {"error": "rate limit hit"})
        norm = acp_to_normalized(ev)
        assert norm.kind == "error"
        assert norm.text == "rate limit hit"
        assert norm.is_error is True
        assert norm.raw_event_kind == "acp_assistant_error"

    def test_acp_session_error_to_error(self):
        ev = _ev("acp_session_error", {"error": "connection reset"})
        norm = acp_to_normalized(ev)
        assert norm.kind == "error"
        assert norm.text == "connection reset"
        assert norm.is_error is True
        assert norm.raw_event_kind == "acp_session_error"

    def test_acp_turn_timeout_to_error(self):
        ev = _ev("acp_turn_timeout", {"timeout_s": 3600.0})
        norm = acp_to_normalized(ev)
        assert norm.kind == "error"
        assert "3600" in (norm.text or "")
        assert norm.is_error is True
        assert norm.raw_event_kind == "acp_turn_timeout"

    def test_acp_result_to_session_meta(self):
        ev = _ev(
            "acp_result",
            {
                "subtype": "success",
                "is_error": False,
                "stop_reason": "end_turn",
                "duration_ms": 5000,
                "num_turns": 3,
                "total_cost_usd": 0.001,
            },
            usage={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
        )
        norm = acp_to_normalized(ev)
        assert norm.kind == "session_meta"
        assert norm.raw_event_kind == "acp_result"
        assert norm.args["subtype"] == "success"
        assert norm.args["total_cost_usd"] == 0.001
        assert norm.usage == {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}
        assert norm.is_error is False

    def test_acp_result_with_error(self):
        ev = _ev("acp_result", {"is_error": True, "errors": ["something broke"]})
        norm = acp_to_normalized(ev)
        assert norm.kind == "session_meta"
        assert norm.is_error is True


class TestUnknownKind:
    def test_unknown_event_falls_into_session_meta(self):
        ev = _ev("acp_brand_new_event", {"foo": "bar"})
        norm = acp_to_normalized(ev)
        assert norm.kind == "session_meta"
        assert norm.raw_event_kind == "acp_brand_new_event"
        assert norm.args == {"foo": "bar"}

    def test_empty_event_name_falls_into_session_meta(self):
        ev = _ev("", {"foo": "bar"})
        norm = acp_to_normalized(ev)
        assert norm.kind == "session_meta"
        assert norm.raw_event_kind is None

    def test_unknown_event_with_no_payload(self):
        ev = _ev("acp_mystery")
        norm = acp_to_normalized(ev)
        assert norm.kind == "session_meta"
        assert norm.raw_event_kind == "acp_mystery"
        assert norm.args is None


class TestBackendStamp:
    """Every translated event must record backend='claude' so the
    transcript can be replayed via the right translator later."""

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
            assert norm.backend == "claude", f"missing backend stamp for {evt_name}"


# ---------------------------------------------------------------------------
# Timestamp formatting
# ---------------------------------------------------------------------------


class TestTimestamp:
    def test_float_timestamp_becomes_iso_z(self):
        # 1700000000.0 == 2023-11-14T22:13:20+00:00
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

    def test_garbage_timestamp_becomes_empty_string(self):
        ev = _ev("acp_text", {"text": "x"})
        ev.timestamp = "not a number"  # type: ignore[assignment]
        norm = acp_to_normalized(ev)
        assert norm.ts == ""


# ---------------------------------------------------------------------------
# normalized_to_sdk_history
# ---------------------------------------------------------------------------


class TestSdkHistory:
    def test_empty_input_returns_empty_list(self):
        assert normalized_to_sdk_history([]) == []

    def test_operator_input_becomes_user_message_with_text_block(self):
        op = make_operator_input("t", "hello world")
        history = normalized_to_sdk_history([op])
        assert history == [
            {"role": "user", "content": [{"type": "text", "text": "hello world"}]}
        ]

    def test_operator_input_with_attachments_appends_attachment_blocks(self):
        op = make_operator_input(
            "t", "look at these", attachments=["/tmp/a.png", "/tmp/b.txt"]
        )
        history = normalized_to_sdk_history([op])
        blocks = history[0]["content"]
        # Text comes first, then one block per attachment.
        assert blocks[0] == {"type": "text", "text": "look at these"}
        assert blocks[1]["text"] == "[attachment: /tmp/a.png]"
        assert blocks[2]["text"] == "[attachment: /tmp/b.txt]"

    def test_agent_text_becomes_assistant_text_block(self):
        events = [
            make_operator_input("t1", "go"),
            ConsoleEvent(ts="t2", kind="agent_text", text="here you go", backend="claude"),
        ]
        history = normalized_to_sdk_history(events)
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1] == {
            "role": "assistant",
            "content": [{"type": "text", "text": "here you go"}],
        }

    def test_tool_call_becomes_assistant_tool_use_block(self):
        events = [
            make_operator_input("t1", "read README"),
            ConsoleEvent(
                ts="t2",
                kind="tool_call",
                tool="read_file",
                args={"path": "README.md", "_tool_use_id": "tu_1"},
                backend="claude",
            ),
        ]
        history = normalized_to_sdk_history(events)
        assert history[1]["role"] == "assistant"
        block = history[1]["content"][0]
        assert block == {
            "type": "tool_use",
            "id": "tu_1",
            "name": "read_file",
            "input": {"path": "README.md"},
        }

    def test_tool_result_becomes_user_tool_result_block(self):
        events = [
            make_operator_input("t1", "go"),
            ConsoleEvent(
                ts="t2",
                kind="tool_call",
                tool="read_file",
                args={"path": "x", "_tool_use_id": "tu_1"},
                backend="claude",
            ),
            ConsoleEvent(
                ts="t3",
                kind="tool_result",
                result={"tool_use_id": "tu_1", "content": "file body"},
                backend="claude",
            ),
        ]
        history = normalized_to_sdk_history(events)
        # user input → assistant tool_use → user tool_result
        assert [m["role"] for m in history] == ["user", "assistant", "user"]
        last = history[-1]["content"][0]
        assert last == {
            "type": "tool_result",
            "tool_use_id": "tu_1",
            "content": "file body",
        }

    def test_tool_result_with_is_error_marks_block(self):
        events = [
            make_operator_input("t1", "go"),
            ConsoleEvent(
                ts="t2",
                kind="tool_call",
                tool="run_command",
                args={"command": "ls", "_tool_use_id": "tu_1"},
            ),
            ConsoleEvent(
                ts="t3",
                kind="tool_result",
                result={"tool_use_id": "tu_1", "content": "ENOENT"},
                is_error=True,
            ),
        ]
        history = normalized_to_sdk_history(events)
        assert history[-1]["content"][0]["is_error"] is True

    def test_alternating_roles_strict(self):
        """The Anthropic API requires strict role alternation. After a
        flush, we must never emit two adjacent same-role messages."""
        events = [
            make_operator_input("t1", "step 1"),
            ConsoleEvent(ts="t2", kind="agent_text", text="ok"),
            ConsoleEvent(
                ts="t3",
                kind="tool_call",
                tool="read_file",
                args={"path": "x", "_tool_use_id": "tu_1"},
            ),
            ConsoleEvent(
                ts="t4",
                kind="tool_result",
                result={"tool_use_id": "tu_1", "content": "data"},
            ),
            ConsoleEvent(ts="t5", kind="agent_text", text="done"),
            make_operator_input("t6", "step 2"),
            ConsoleEvent(ts="t7", kind="agent_text", text="done again"),
        ]
        history = normalized_to_sdk_history(events)
        roles = [m["role"] for m in history]
        for i in range(1, len(roles)):
            assert roles[i] != roles[i - 1], (
                f"two adjacent {roles[i]} messages at index {i}: {roles}"
            )

    def test_text_and_tool_use_coalesce_into_one_assistant_message(self):
        events = [
            make_operator_input("t1", "go"),
            ConsoleEvent(ts="t2", kind="agent_text", text="I'll read it"),
            ConsoleEvent(
                ts="t3",
                kind="tool_call",
                tool="read_file",
                args={"path": "x", "_tool_use_id": "tu_1"},
            ),
        ]
        history = normalized_to_sdk_history(events)
        # All assistant blocks should sit in ONE assistant message,
        # not two — that's what the API expects when a turn has both
        # text and a tool_use.
        assistant_msgs = [m for m in history if m["role"] == "assistant"]
        assert len(assistant_msgs) == 1
        assert len(assistant_msgs[0]["content"]) == 2

    def test_thinking_permission_session_meta_error_are_skipped(self):
        events = [
            make_operator_input("t1", "go"),
            ConsoleEvent(ts="t2", kind="agent_thinking", text="thinking..."),
            ConsoleEvent(ts="t3", kind="permission", tool="read_file"),
            ConsoleEvent(ts="t4", kind="session_meta", model="claude-sonnet-4"),
            ConsoleEvent(ts="t5", kind="error", text="some error", is_error=True),
            ConsoleEvent(ts="t6", kind="agent_text", text="visible reply"),
        ]
        history = normalized_to_sdk_history(events)
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1] == {
            "role": "assistant",
            "content": [{"type": "text", "text": "visible reply"}],
        }

    def test_tool_call_missing_tool_use_id_is_dropped(self):
        """The Anthropic API rejects a tool_use without an id. Drop
        the entry rather than emit something the API will refuse."""
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
        # Should have one user + one assistant (text only — no
        # orphan tool_use block).
        assert [m["role"] for m in history] == ["user", "assistant"]
        assistant_content = history[1]["content"]
        assert len(assistant_content) == 1
        assert assistant_content[0]["type"] == "text"

    def test_tool_result_missing_tool_use_id_is_dropped(self):
        events = [
            make_operator_input("t1", "go"),
            ConsoleEvent(ts="t2", kind="agent_text", text="ok"),
            ConsoleEvent(
                ts="t3",
                kind="tool_result",
                result={"content": "data"},  # no tool_use_id!
            ),
        ]
        history = normalized_to_sdk_history(events)
        assert [m["role"] for m in history] == ["user", "assistant"]

    def test_round_trip_synthetic_stream_produces_sdk_acceptable_shape(self):
        """End-to-end round-trip: synthetic AgentEvent stream →
        normalized list → SDK history.

        The "SDK acceptable shape" check is verified by handing the
        result to a mocked ClaudeAgentOptions-shaped consumer; if the
        shape is wrong we'd raise.
        """
        events_in = [
            _ev("acp_session_start", {"model": "claude-sonnet-4"}),
            _ev("acp_text", {"text": "Hello operator"}),
            _ev(
                "acp_tool_use",
                {"tool": "read_file", "input": {"path": "README.md"}, "id": "tu_123"},
            ),
            _ev(
                "acp_tool_result",
                {
                    "tool_use_id": "tu_123",
                    "is_error": False,
                    "content": "file contents...",
                },
            ),
            _ev("acp_text", {"text": "I have read the file"}),
            _ev(
                "acp_result",
                {
                    "subtype": "success",
                    "is_error": False,
                    "num_turns": 2,
                    "total_cost_usd": 0.001,
                },
            ),
        ]
        normalized = [acp_to_normalized(e) for e in events_in]
        op = make_operator_input("2026-05-13T19:00:00Z", "please read the README")
        history = normalized_to_sdk_history([op] + normalized)

        # Mock SDK that asserts the standard Anthropic Messages API
        # shape: strict role alternation, content blocks with required
        # type tags, tool_use needs id/name/input, tool_result needs
        # tool_use_id.
        def _mock_sdk_accept(messages: list[dict]) -> None:
            assert isinstance(messages, list)
            assert all(isinstance(m, dict) for m in messages)
            prev_role = None
            for m in messages:
                assert m["role"] in ("user", "assistant")
                assert m["role"] != prev_role, "API requires strict alternation"
                prev_role = m["role"]
                assert isinstance(m["content"], list)
                for block in m["content"]:
                    assert "type" in block
                    if block["type"] == "text":
                        assert "text" in block
                    elif block["type"] == "tool_use":
                        assert "id" in block and "name" in block and "input" in block
                    elif block["type"] == "tool_result":
                        assert "tool_use_id" in block
                    else:
                        # No other block types should be emitted.
                        raise AssertionError(f"unexpected block type: {block['type']}")

        with patch("oompah.console_translators.claude.logger"):
            _mock_sdk_accept(history)


# ---------------------------------------------------------------------------
# Dispatch wrapper sanity
# ---------------------------------------------------------------------------


class TestDispatch:
    def test_known_backends_includes_claude_and_codex(self):
        assert "claude" in known_backends()
        assert "codex" in known_backends()

    def test_default_dispatch_picks_claude(self):
        assert get_translator(None).backend == "claude"
        assert get_translator("claude").backend == "claude"

    def test_explicit_claude_dispatch_matches_direct_call(self):
        ev = _ev("acp_text", {"text": "x"})
        direct = acp_to_normalized(ev)
        dispatched = dispatch_acp_to_normalized(ev, backend="claude")
        assert direct == dispatched

    def test_unknown_backend_raises_keyerror(self):
        with pytest.raises(KeyError):
            get_translator("bogus")

    def test_history_dispatch_matches_direct_call(self):
        events = [
            make_operator_input("t1", "hi"),
            ConsoleEvent(ts="t2", kind="agent_text", text="hello"),
        ]
        direct = normalized_to_sdk_history(events)
        dispatched = dispatch_normalized_to_sdk_history(events, backend="claude")
        assert direct == dispatched


class TestCodexTranslatorRegistered:
    """The codex translator was finalized in oompah-zlz_2-elug. Its full
    semantics are exercised in :mod:`tests.test_console_translator_codex`
    and :mod:`tests.test_console_crossagent`. Here we just sanity-check
    that the codex backend is registered and the dispatch path doesn't
    raise NotImplementedError anymore — guards the elug regression where
    the codex.py stub was reintroduced accidentally."""

    def test_codex_acp_to_normalized_does_not_raise_not_implemented(self):
        from oompah.console_translators import codex as codex_mod

        norm = codex_mod.acp_to_normalized(_ev("acp_text", {"text": "hi"}))
        assert norm.kind == "agent_text"
        assert norm.backend == "codex"

    def test_codex_normalized_to_sdk_history_returns_list(self):
        from oompah.console_translators import codex as codex_mod

        # Empty input → empty list, never raise.
        assert codex_mod.normalized_to_sdk_history([]) == []

    def test_codex_dispatch_returns_console_event(self):
        norm = dispatch_acp_to_normalized(
            _ev("acp_text", {"text": "hi"}), backend="codex"
        )
        assert norm.kind == "agent_text"
        assert norm.backend == "codex"


# ---------------------------------------------------------------------------
# Normalized round-trip via to_dict / from_dict
# ---------------------------------------------------------------------------


class TestNormalizedRoundTripViaJson:
    """End-to-end: every AgentEvent kind → normalized → dict → from_dict
    must produce an equal ConsoleEvent. Catches translator drift."""

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
