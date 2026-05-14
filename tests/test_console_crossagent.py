"""Cross-agent backend-switch integration test (oompah-zlz_2-elug, Console 6/6).

This is the gate test for the console-session epic
(oompah-zlz_2-ebwe). It verifies that the conversation history
survives a backend switch — both the on-disk transcript AND the
SDK-shaped history kwarg the next turn hands to the freshly-spawned
AcpAgentSession.

What it covers
--------------

1. Start a :class:`oompah.console.ConsoleSession` against a mocked
   Claude SDK (no real anthropic/openai calls). Drive a multi-turn
   conversation::

       operator → agent_text → tool_call → tool_result → operator →
       agent_text

   Every turn lands in the on-disk JSONL transcript.

2. Call ``session.switch_backend("codex")`` against a mocked Codex
   SDK. Inspect the captured ``history=`` kwarg on the NEXT turn's
   AcpAgentSession and confirm it is the codex-translator's input-
   item list with EVERY prior turn replayed in alternating
   user/assistant form.

3. Send a new operator message. Verify the codex SDK saw it as turn
   N+1 with the full prior context — same assertion via the captured
   ``prompt=`` and ``history=`` kwargs.

4. Switch back to claude. Verify the new Claude SDK instance gets a
   ``history=`` list that includes the codex turns recorded earlier
   (the on-disk transcript is the source of truth; the translator
   resolves it through claude's dialect this time).

The test uses the same FakeAgentSession+factory pattern as
``tests.test_console_session`` — we don't import the real SDKs. The
test is hermetic and runs in <1s.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock

import pytest

import oompah.console as console_mod
from oompah.console import ConsoleSession
from oompah.console_format import ConsoleEvent
from oompah.console_store import ConsoleStore


# ---------------------------------------------------------------------------
# FakeAgentSession + factory plumbing (parallel to test_console_session.py
# but tracks ALL scripted events per-turn keyed by the prompt text, so we
# can drive a five-turn conversation with different scripted events per
# turn without resetting the singleton between calls).
# ---------------------------------------------------------------------------


@dataclass
class FakeBackendEvent:
    """Backend event in the shape the translators consume.

    Matches the fields acp_to_normalized reads off ``AgentEvent``:
    ``event``, ``payload``, ``timestamp``, ``usage``.
    """

    event: str
    payload: dict
    timestamp: float = 1716000000.0
    usage: dict = field(default_factory=dict)


class FakeAgentSession:
    """Drop-in stand-in for ``oompah.acp_agent.AcpAgentSession``.

    Captures all constructor kwargs to ``instances`` so tests can
    inspect each turn's prompt/history/backend_name. The next per-turn
    script of backend events is keyed by the prompt text via
    :attr:`script_by_prompt` — tests pre-populate this map so different
    turns can emit different agent_text / tool_call / tool_result
    streams.
    """

    instances: list["FakeAgentSession"] = []
    script_by_prompt: dict[str, list[FakeBackendEvent]] = {}
    wait_for: asyncio.Event | None = None

    def __init__(self, **kwargs: Any):
        self.kwargs = dict(kwargs)
        self.on_event = kwargs.get("on_event")
        self.prompt = kwargs.get("prompt")
        self.history = kwargs.get("history")
        self.backend_name = kwargs.get("backend_name")
        FakeAgentSession.instances.append(self)
        self.run_task_called = False

    async def run_task(self) -> str:
        self.run_task_called = True
        scripted = FakeAgentSession.script_by_prompt.get(self.prompt, [])
        for ev in scripted:
            if self.on_event is not None:
                self.on_event(ev)
        wait = FakeAgentSession.wait_for
        if wait is not None:
            await wait.wait()
        return "succeeded"

    @classmethod
    def reset(cls) -> None:
        cls.instances = []
        cls.script_by_prompt = {}
        cls.wait_for = None


@pytest.fixture(autouse=True)
def _reset_fake_agent_session(monkeypatch):
    FakeAgentSession.reset()

    def _factory(**kwargs):
        return FakeAgentSession(**kwargs)

    monkeypatch.setattr(console_mod, "agent_session_factory", _factory)
    yield
    FakeAgentSession.reset()


# ---------------------------------------------------------------------------
# Store / provider / role fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path) -> ConsoleStore:
    return ConsoleStore(root=str(tmp_path / "console"))


@pytest.fixture
def provider_store() -> Any:
    stub = MagicMock()
    stub.get.return_value = MagicMock(
        id="prov-X",
        default_model="claude-sonnet-4-5-test",
    )
    stub.get_default.return_value = stub.get.return_value
    return stub


@pytest.fixture
def role_store() -> Any:
    stub = MagicMock()
    role = MagicMock()
    role.provider_id = "prov-X"
    role.model = "claude-sonnet-4-5-test"
    role.name = "default"
    stub.get.return_value = role
    return stub


# ---------------------------------------------------------------------------
# Helpers for assertions
# ---------------------------------------------------------------------------


def _claude_history_text_blocks(history: list[dict]) -> list[tuple[str, str]]:
    """Extract (role, text) pairs from a Claude-API-shaped history.

    Used to assert that the rehydrated history carries every prior
    turn's text content.
    """
    out: list[tuple[str, str]] = []
    for msg in history:
        role = msg.get("role")
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                out.append((role, str(block.get("text") or "")))
            elif block.get("type") == "tool_use":
                out.append((role, f"[tool_use:{block.get('name')}]"))
            elif block.get("type") == "tool_result":
                content_val = block.get("content")
                if isinstance(content_val, str):
                    out.append((role, f"[tool_result:{content_val[:64]}]"))
                else:
                    out.append((role, f"[tool_result:{type(content_val).__name__}]"))
    return out


def _codex_history_summary(history: list[dict]) -> list[tuple[str, str]]:
    """Extract (kind, payload-summary) pairs from a codex-shaped history.

    Codex items are either message dicts ({role, content}) or
    function_call / function_call_output dicts.
    """
    out: list[tuple[str, str]] = []
    for item in history:
        if "role" in item:
            out.append((item["role"], str(item.get("content") or "")))
        elif item.get("type") == "function_call":
            out.append(("function_call", f"{item.get('name')}({item.get('arguments')})"))
        elif item.get("type") == "function_call_output":
            out.append(("function_call_output", str(item.get("output") or "")))
    return out


# ---------------------------------------------------------------------------
# 1. Drive a 5-event Claude conversation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cross_agent_backend_switch_preserves_history(
    store, provider_store, role_store,
) -> None:
    """End-to-end: claude → codex → claude, history carried across each.

    Conversation outline (each ``send()`` is one operator turn):

      Turn 1 (claude):
        operator: "what is in README.md?"
        scripted: agent_text "I'll read the README."
                  tool_call read_file(README.md) id=tu_1
                  tool_result tu_1 content="# Project"
                  agent_text "The project is named Project."

      Turn 2 (claude):
        operator: "what about CHANGELOG?"
        scripted: agent_text "The CHANGELOG is empty."

      → switch_backend("codex")

      Turn 3 (codex):
        operator: "summarize what we've discussed"
        scripted: agent_text "We read the README and noted the CHANGELOG is empty."

      → switch_backend("claude")

      Turn 4 (claude, after the codex turn):
        operator: "one more question: how many files were read?"
        scripted: agent_text "Just one — README.md."
    """
    captured_events: list[ConsoleEvent] = []
    session = ConsoleSession(
        project_id="proj-XA",
        store=store,
        provider_store=provider_store,
        role_store=role_store,
        on_event=captured_events.append,
        workspace_path="/tmp/proj-XA",
    )
    assert session.get_meta()["backend"] == "claude"

    # ------------------------------------------------------------------
    # Turn 1: multi-event claude turn (operator → text → tool_call →
    # tool_result → text)
    # ------------------------------------------------------------------
    FakeAgentSession.script_by_prompt = {
        "what is in README.md?": [
            FakeBackendEvent(
                event="acp_text",
                payload={"text": "I'll read the README."},
            ),
            FakeBackendEvent(
                event="acp_tool_use",
                payload={
                    "tool": "read_file",
                    "input": {"path": "README.md"},
                    "id": "tu_1",
                },
            ),
            FakeBackendEvent(
                event="acp_tool_result",
                payload={
                    "tool_use_id": "tu_1",
                    "is_error": False,
                    "content": "# Project",
                },
            ),
            FakeBackendEvent(
                event="acp_text",
                payload={"text": "The project is named Project."},
            ),
        ],
        "what about CHANGELOG?": [
            FakeBackendEvent(
                event="acp_text",
                payload={"text": "The CHANGELOG is empty."},
            ),
        ],
        "summarize what we've discussed": [
            FakeBackendEvent(
                event="acp_text",
                payload={
                    "text": (
                        "We read the README and noted the CHANGELOG is empty."
                    ),
                },
            ),
        ],
        "one more question: how many files were read?": [
            FakeBackendEvent(
                event="acp_text",
                payload={"text": "Just one — README.md."},
            ),
        ],
    }

    await session.send("what is in README.md?")

    # Turn 1 transcript: operator_input + 4 backend events + terminal
    # session_meta.
    rows = store.read_all("proj-XA")
    kinds = [r["kind"] for r in rows]
    assert kinds[0] == "operator_input"
    assert kinds.count("agent_text") == 2
    assert kinds.count("tool_call") == 1
    assert kinds.count("tool_result") == 1
    assert kinds[-1] == "session_meta"
    # The on_event callback fired for every persisted event.
    assert [e.kind for e in captured_events[:5]] == [
        "operator_input", "agent_text", "tool_call", "tool_result", "agent_text",
    ]

    # ------------------------------------------------------------------
    # Turn 2: simple claude follow-up
    # ------------------------------------------------------------------
    await session.send("what about CHANGELOG?")
    assert len(FakeAgentSession.instances) == 2
    # Each call constructs a fresh AcpAgentSession with the rehydrated
    # history. Turn 2's history kwarg already includes turn 1's content.
    turn2 = FakeAgentSession.instances[1]
    assert turn2.kwargs["backend_name"] == "claude"
    t2_pairs = _claude_history_text_blocks(turn2.history)
    # Turn 1's text + tool_use + tool_result + text + turn 2's operator
    # are all visible at this point.
    flat = " | ".join(text for _, text in t2_pairs)
    assert "what is in README.md?" in flat
    assert "I'll read the README." in flat
    assert "[tool_use:read_file]" in flat
    assert "The project is named Project." in flat
    assert "what about CHANGELOG?" in flat

    # ------------------------------------------------------------------
    # Switch backend to codex.
    # ------------------------------------------------------------------
    await session.switch_backend("codex", model_role="default")
    assert session.get_meta()["backend"] == "codex"
    # Meta sidecar persisted.
    meta = store.load_meta("proj-XA")
    assert meta["backend"] == "codex"

    # ------------------------------------------------------------------
    # Turn 3: codex turn — history kwarg should be the codex shape and
    # carry EVERY prior turn.
    # ------------------------------------------------------------------
    await session.send("summarize what we've discussed")
    assert len(FakeAgentSession.instances) == 3
    turn3 = FakeAgentSession.instances[2]
    assert turn3.kwargs["backend_name"] == "codex"
    history3 = turn3.history
    assert isinstance(history3, list)
    # Every entry is a codex-input-item dict (role or type, never
    # Anthropic role+content[list]).
    for item in history3:
        assert "role" in item or item.get("type") in (
            "function_call", "function_call_output"
        )
        if "role" in item:
            assert isinstance(item.get("content"), str)
    pairs3 = _codex_history_summary(history3)
    flat3 = " | ".join(f"{role}:{text}" for role, text in pairs3)
    # All four prior turns + turn 3's new operator_input are there.
    assert "user:what is in README.md?" in flat3
    assert "assistant:I'll read the README." in flat3
    assert "function_call:read_file(" in flat3
    assert "function_call_output:# Project" in flat3
    assert "assistant:The project is named Project." in flat3
    assert "user:what about CHANGELOG?" in flat3
    assert "assistant:The CHANGELOG is empty." in flat3
    # The new turn's operator_input is the LAST user message (turn N+1
    # context).
    user_msgs = [text for role, text in pairs3 if role == "user"]
    assert user_msgs[-1] == "summarize what we've discussed"
    # The codex SDK also sees this as ``prompt=`` — turn N+1 marker.
    assert turn3.prompt == "summarize what we've discussed"

    # ------------------------------------------------------------------
    # Switch back to claude. The next turn's history should once again
    # be Claude-shaped AND include the codex turn we just had.
    # ------------------------------------------------------------------
    await session.switch_backend("claude", model_role="default")
    assert session.get_meta()["backend"] == "claude"

    await session.send("one more question: how many files were read?")
    assert len(FakeAgentSession.instances) == 4
    turn4 = FakeAgentSession.instances[3]
    assert turn4.kwargs["backend_name"] == "claude"
    history4 = turn4.history
    pairs4 = _claude_history_text_blocks(history4)
    flat4 = " | ".join(text for _, text in pairs4)
    # The codex turn lives in the transcript and now feeds through the
    # claude translator. Specifically: turn 3's user + assistant text
    # both appear.
    assert "summarize what we've discussed" in flat4
    assert "We read the README and noted the CHANGELOG is empty." in flat4
    # The new operator turn is also present.
    assert "one more question: how many files were read?" in flat4

    # ------------------------------------------------------------------
    # Final state checks
    # ------------------------------------------------------------------
    final_rows = store.read_all("proj-XA")
    backends_seen = {r.get("backend") for r in final_rows if r.get("backend")}
    # Both backends contributed events to the same transcript.
    assert "claude" in backends_seen
    assert "codex" in backends_seen
    # Operator inputs are stamped with whichever backend was active at
    # send-time.
    op_rows = [r for r in final_rows if r["kind"] == "operator_input"]
    assert [r.get("backend") for r in op_rows] == [
        "claude", "claude", "codex", "claude",
    ]
    # All four operator messages survived.
    assert [r.get("text") for r in op_rows] == [
        "what is in README.md?",
        "what about CHANGELOG?",
        "summarize what we've discussed",
        "one more question: how many files were read?",
    ]

    await session.shutdown()


# ---------------------------------------------------------------------------
# 2. Codex history-shape contract guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_codex_history_contains_alternating_user_assistant(
    store, provider_store, role_store,
) -> None:
    """The codex history list must reflect the conversation in
    chronological send order — user, assistant, user, assistant ...
    even though the SDK doesn't strictly require alternation."""
    session = ConsoleSession(
        project_id="proj-ALT",
        store=store,
        provider_store=provider_store,
        role_store=role_store,
        workspace_path="/tmp/proj-ALT",
    )

    FakeAgentSession.script_by_prompt = {
        "q1": [FakeBackendEvent(event="acp_text", payload={"text": "a1"})],
        "q2": [FakeBackendEvent(event="acp_text", payload={"text": "a2"})],
        "q3": [FakeBackendEvent(event="acp_text", payload={"text": "a3"})],
    }

    await session.send("q1")
    await session.send("q2")
    await session.switch_backend("codex")
    await session.send("q3")

    # The codex turn's history reflects all prior turns + the new one.
    codex_turn = FakeAgentSession.instances[-1]
    assert codex_turn.kwargs["backend_name"] == "codex"
    history = codex_turn.history
    roles = [item.get("role") for item in history if "role" in item]
    # The model-input portion alternates: q1 / a1 / q2 / a2 / q3 (no a3 yet).
    assert roles == ["user", "assistant", "user", "assistant", "user"]

    await session.shutdown()


# ---------------------------------------------------------------------------
# 3. Tool calls survive the round-trip into codex history
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tool_calls_survive_into_codex_history(
    store, provider_store, role_store,
) -> None:
    """A tool_call / tool_result pair recorded under claude must
    appear in the codex history as a function_call / function_call_output
    pair with the call_id link preserved."""
    session = ConsoleSession(
        project_id="proj-TS",
        store=store,
        provider_store=provider_store,
        role_store=role_store,
        workspace_path="/tmp/proj-TS",
    )

    FakeAgentSession.script_by_prompt = {
        "do the thing": [
            FakeBackendEvent(
                event="acp_text",
                payload={"text": "calling the tool"},
            ),
            FakeBackendEvent(
                event="acp_tool_use",
                payload={
                    "tool": "list_files",
                    "input": {"path": "."},
                    "id": "tu_xyz",
                },
            ),
            FakeBackendEvent(
                event="acp_tool_result",
                payload={
                    "tool_use_id": "tu_xyz",
                    "is_error": False,
                    "content": "file1\nfile2\n",
                },
            ),
        ],
        "follow up": [FakeBackendEvent(event="acp_text", payload={"text": "ok"})],
    }

    await session.send("do the thing")
    await session.switch_backend("codex")
    await session.send("follow up")

    codex_turn = FakeAgentSession.instances[-1]
    history = codex_turn.history
    call = next(
        (item for item in history if item.get("type") == "function_call"),
        None,
    )
    output = next(
        (item for item in history if item.get("type") == "function_call_output"),
        None,
    )
    assert call is not None, f"no function_call in {history!r}"
    assert output is not None, f"no function_call_output in {history!r}"
    assert call["name"] == "list_files"
    assert call["call_id"] == "tu_xyz"
    assert output["call_id"] == "tu_xyz"
    # Arguments JSON-encoded.
    assert json.loads(call["arguments"]) == {"path": "."}
    # Output passed through verbatim (no [ERROR] prefix since
    # is_error=False).
    assert output["output"] == "file1\nfile2\n"

    await session.shutdown()


# ---------------------------------------------------------------------------
# 4. Empty transcript / first turn has empty history
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_turn_under_codex_has_only_new_input_in_history(
    store, provider_store, role_store,
) -> None:
    """First turn on a fresh project under codex should pass an
    operator_input-only history (one user message) — verifies that
    rehydration works on an empty transcript."""
    # Pre-flip to codex BEFORE any turn so the very first turn runs
    # under codex.
    store.save_meta("proj-FRESH", {"backend": "codex"})
    session = ConsoleSession(
        project_id="proj-FRESH",
        store=store,
        provider_store=provider_store,
        role_store=role_store,
        workspace_path="/tmp/proj-FRESH",
    )

    FakeAgentSession.script_by_prompt = {
        "hello codex": [
            FakeBackendEvent(event="acp_text", payload={"text": "hi"}),
        ],
    }
    await session.send("hello codex")

    inst = FakeAgentSession.instances[0]
    assert inst.kwargs["backend_name"] == "codex"
    history = inst.history
    # Only the freshly-recorded operator_input is in history (the
    # agent_text from this turn was emitted AFTER history was passed
    # to the constructor).
    assert isinstance(history, list)
    assert len(history) == 1
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "hello codex"

    await session.shutdown()


# ---------------------------------------------------------------------------
# 5. Switch-while-in-flight is refused (v1 policy) — exists in
# test_console_session.py too, but re-asserted here so the cross-agent
# test file documents the full backend-switch contract in one place.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_switch_backend_refused_mid_turn_smoke(
    store, provider_store, role_store,
) -> None:
    session = ConsoleSession(
        project_id="proj-MID2",
        store=store,
        provider_store=provider_store,
        role_store=role_store,
        workspace_path="/tmp/proj-MID2",
    )

    gate = asyncio.Event()
    FakeAgentSession.wait_for = gate
    FakeAgentSession.script_by_prompt = {
        "wait": [FakeBackendEvent(event="acp_text", payload={"text": "ok"})],
    }
    task = asyncio.create_task(session.send("wait"))
    for _ in range(20):
        await asyncio.sleep(0)
        if session.get_meta()["turn_active"]:
            break
    assert session.get_meta()["turn_active"] is True

    with pytest.raises(RuntimeError, match="cannot switch backend"):
        await session.switch_backend("codex")

    gate.set()
    FakeAgentSession.wait_for = None
    await asyncio.wait_for(task, timeout=5.0)
    # Original backend untouched.
    assert session.get_meta()["backend"] == "claude"

    await session.shutdown()
