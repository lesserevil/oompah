"""Tests for ``oompah.console_format``.

Acceptance criteria from oompah-zlz_2-hoop:

* ``to_dict`` / ``from_dict`` round-trip every NORMALIZED_KINDS value
* Malformed dicts are handled (don't raise on missing/extra/bad keys)
* Schema round-trips preserve all set fields
"""

from __future__ import annotations

import pytest

from oompah.console_format import (
    NORMALIZED_KINDS,
    ConsoleEvent,
    make_error,
    make_operator_input,
)


# ---------------------------------------------------------------------------
# Schema constants
# ---------------------------------------------------------------------------


class TestNormalizedKinds:
    def test_has_eight_kinds(self):
        assert len(NORMALIZED_KINDS) == 8

    def test_contains_expected_kinds(self):
        expected = {
            "operator_input",
            "agent_text",
            "agent_thinking",
            "tool_call",
            "tool_result",
            "permission",
            "session_meta",
            "error",
        }
        assert set(NORMALIZED_KINDS) == expected

    def test_is_known_kind_predicate(self):
        for kind in NORMALIZED_KINDS:
            ev = ConsoleEvent(ts="t", kind=kind)
            assert ev.is_known_kind()
        assert not ConsoleEvent(ts="t", kind="bogus").is_known_kind()


# ---------------------------------------------------------------------------
# to_dict / from_dict round-trip for every NORMALIZED_KIND
# ---------------------------------------------------------------------------


def _sample_event(kind: str) -> ConsoleEvent:
    """Build a representative event for every kind with the fields
    that kind would realistically carry.

    Used by the round-trip parametrize below.
    """
    base = dict(ts="2026-05-13T19:00:00.000000Z", kind=kind, backend="claude")
    if kind == "operator_input":
        return ConsoleEvent(
            **base, text="please run the tests", attachments=["/tmp/a.png", "/tmp/b.txt"]
        )
    if kind == "agent_text":
        return ConsoleEvent(
            **base,
            model="claude-sonnet-4",
            text="here is what I see",
            usage={"input_tokens": 100, "output_tokens": 50},
        )
    if kind == "agent_thinking":
        return ConsoleEvent(**base, model="claude-sonnet-4", text="hmm, let me think")
    if kind == "tool_call":
        return ConsoleEvent(
            **base,
            tool="read_file",
            args={"path": "README.md", "_tool_use_id": "tu_42"},
        )
    if kind == "tool_result":
        return ConsoleEvent(
            **base,
            result={"tool_use_id": "tu_42", "content": "file content"},
            is_error=False,
        )
    if kind == "permission":
        return ConsoleEvent(
            **base,
            tool="run_command",
            args={"command": "ls"},
            is_error=True,
            raw_event_kind="acp_permission_deny",
        )
    if kind == "session_meta":
        return ConsoleEvent(
            **base,
            model="claude-sonnet-4",
            args={"subtype": "success", "num_turns": 3},
            usage={"input_tokens": 200, "output_tokens": 100},
            raw_event_kind="acp_result",
        )
    if kind == "error":
        return ConsoleEvent(
            **base,
            text="turn timeout after 3600s",
            is_error=True,
            raw_event_kind="acp_turn_timeout",
        )
    raise AssertionError(f"unhandled kind: {kind}")


@pytest.mark.parametrize("kind", NORMALIZED_KINDS)
def test_round_trip_every_kind(kind):
    original = _sample_event(kind)
    as_dict = original.to_dict()
    restored = ConsoleEvent.from_dict(as_dict)
    assert restored == original, f"round trip failed for kind={kind}"


# ---------------------------------------------------------------------------
# to_dict semantics
# ---------------------------------------------------------------------------


class TestToDict:
    def test_minimal_event_only_has_required_keys(self):
        ev = ConsoleEvent(ts="t", kind="agent_text")
        out = ev.to_dict()
        # Required.
        assert out["ts"] == "t"
        assert out["kind"] == "agent_text"
        # Optional fields with default values are omitted.
        for k in (
            "backend",
            "model",
            "text",
            "tool",
            "args",
            "result",
            "is_error",
            "usage",
            "raw_event_kind",
            "attachments",
        ):
            assert k not in out, f"unexpected key {k!r} in minimal to_dict"

    def test_is_error_false_omitted_true_included(self):
        assert "is_error" not in ConsoleEvent(ts="t", kind="error").to_dict()
        assert (
            ConsoleEvent(ts="t", kind="error", is_error=True).to_dict()["is_error"]
            is True
        )

    def test_empty_string_text_kept(self):
        ev = ConsoleEvent(ts="t", kind="agent_text", text="")
        # An empty-string text is meaningful — keep it. None would mean
        # "no text"; "" means "the model emitted an empty token". Both
        # cases must be distinguishable on the dashboard.
        assert ev.to_dict()["text"] == ""

    def test_attachments_round_trip_with_copy(self):
        attachments = ["/tmp/x", "/tmp/y"]
        ev = ConsoleEvent(ts="t", kind="operator_input", text="hi", attachments=attachments)
        out = ev.to_dict()
        assert out["attachments"] == attachments
        # to_dict should produce a *copy* so mutations don't leak.
        out["attachments"].append("/tmp/z")
        assert ev.attachments == ["/tmp/x", "/tmp/y"]


# ---------------------------------------------------------------------------
# from_dict permissiveness on malformed inputs
# ---------------------------------------------------------------------------


class TestFromDictMalformed:
    def test_missing_kind_falls_through_to_session_meta(self):
        ev = ConsoleEvent.from_dict({"ts": "t"})
        assert ev.kind == "session_meta"
        assert ev.ts == "t"

    def test_non_string_kind_preserved_in_raw(self):
        ev = ConsoleEvent.from_dict({"ts": "t", "kind": 42})
        # Don't drop the original. Surface it via raw_event_kind so the
        # caller can recover.
        assert ev.kind == "session_meta"
        assert ev.raw_event_kind == "42"

    def test_missing_ts_becomes_empty_string(self):
        ev = ConsoleEvent.from_dict({"kind": "agent_text"})
        assert ev.ts == ""
        assert ev.kind == "agent_text"

    def test_extra_keys_are_ignored(self):
        ev = ConsoleEvent.from_dict(
            {"ts": "t", "kind": "agent_text", "bogus_field": "ignored"}
        )
        assert ev.kind == "agent_text"

    def test_garbage_args_type_is_dropped(self):
        ev = ConsoleEvent.from_dict({"ts": "t", "kind": "tool_call", "args": "not a dict"})
        # Best-effort: drop bad shapes rather than crash.
        assert ev.args is None

    def test_garbage_attachments_type_is_dropped(self):
        ev = ConsoleEvent.from_dict(
            {"ts": "t", "kind": "operator_input", "attachments": "single string"}
        )
        assert ev.attachments is None

    def test_is_error_coerced_to_bool(self):
        ev = ConsoleEvent.from_dict({"ts": "t", "kind": "error", "is_error": 1})
        assert ev.is_error is True
        ev2 = ConsoleEvent.from_dict({"ts": "t", "kind": "error", "is_error": 0})
        assert ev2.is_error is False
        ev3 = ConsoleEvent.from_dict({"ts": "t", "kind": "error"})
        assert ev3.is_error is False

    def test_from_dict_on_non_dict_raises_type_error(self):
        with pytest.raises(TypeError):
            ConsoleEvent.from_dict("not a dict")  # type: ignore[arg-type]
        with pytest.raises(TypeError):
            ConsoleEvent.from_dict(None)  # type: ignore[arg-type]
        with pytest.raises(TypeError):
            ConsoleEvent.from_dict(["list"])  # type: ignore[arg-type]

    def test_args_dict_is_copied_not_aliased(self):
        original = {"key": "value"}
        ev = ConsoleEvent.from_dict({"ts": "t", "kind": "tool_call", "args": original})
        assert ev.args == original
        # Mutating the source after parse must not affect the parsed
        # event (would cause spooky-action-at-a-distance bugs in the
        # JSONL reader).
        original["key"] = "mutated"
        assert ev.args == {"key": "value"}


# ---------------------------------------------------------------------------
# Module-level constructors
# ---------------------------------------------------------------------------


class TestMakeOperatorInput:
    def test_text_only(self):
        ev = make_operator_input("t", "hello")
        assert ev.kind == "operator_input"
        assert ev.text == "hello"
        assert ev.attachments is None

    def test_with_attachments(self):
        ev = make_operator_input("t", "hello", attachments=["a", "b"])
        assert ev.attachments == ["a", "b"]

    def test_with_backend(self):
        ev = make_operator_input("t", "hello", backend="claude")
        assert ev.backend == "claude"

    def test_round_trip(self):
        ev = make_operator_input(
            "t", "hello", attachments=["a", "b"], backend="claude"
        )
        assert ConsoleEvent.from_dict(ev.to_dict()) == ev


class TestMakeError:
    def test_default(self):
        ev = make_error("t", "boom")
        assert ev.kind == "error"
        assert ev.text == "boom"
        assert ev.is_error is True

    def test_preserves_raw_event_kind(self):
        ev = make_error("t", "session crashed", raw_event_kind="acp_session_error")
        assert ev.raw_event_kind == "acp_session_error"

    def test_round_trip(self):
        ev = make_error("t", "boom", backend="claude", raw_event_kind="acp_session_error")
        assert ConsoleEvent.from_dict(ev.to_dict()) == ev


# ---------------------------------------------------------------------------
# Multi-round JSON robustness
# ---------------------------------------------------------------------------


class TestJSONStability:
    def test_to_dict_is_json_serializable(self):
        import json

        for kind in NORMALIZED_KINDS:
            ev = _sample_event(kind)
            payload = json.dumps(ev.to_dict())
            # Round-trip back through json + from_dict; equality must
            # hold.
            assert ConsoleEvent.from_dict(json.loads(payload)) == ev
