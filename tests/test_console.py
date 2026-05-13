"""Tests for the per-project ACP console (oompah-zlz_2-ebwe).

Covers:

* ConsoleStore: JSONL append/read/page, malformed-line resilience,
  oversize-event truncation, project_id sanitization.
* render_transcript_as_prompt: prompt formatting + history-cap.
* ConsoleSession: submit serializes, transcript persists, broadcast
  fan-out called for every event.
* ConsoleManager: get-or-create lifecycle, read-without-construction,
  unknown project handling.
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

# These tests cover the LEGACY umbrella implementation
# (oompah/console_legacy.py). The new modular ConsoleSession +
# ConsoleSessionManager (oompah-zlz_2-49tv) is tested in
# tests/test_console_session.py.
from oompah import console_legacy as console_mod
from oompah.console_legacy import (
    ConsoleManager,
    ConsoleSession,
    ConsoleStore,
    render_transcript_as_prompt,
)


# ----------------------------------------------------------------------
# ConsoleStore
# ----------------------------------------------------------------------


class TestConsoleStore:
    def test_append_and_read(self, tmp_path: Path) -> None:
        store = ConsoleStore("proj-A", base_dir=str(tmp_path))
        store.append("operator_input", {"text": "hello"})
        store.append("acp_text", {"text": "hi there"})
        events = store.read_all()
        assert len(events) == 2
        assert events[0]["kind"] == "operator_input"
        assert events[0]["payload"]["text"] == "hello"
        assert events[1]["kind"] == "acp_text"
        store.close()

    def test_jsonl_is_real_file(self, tmp_path: Path) -> None:
        store = ConsoleStore("proj-A", base_dir=str(tmp_path))
        store.append("operator_input", {"text": "hello"})
        store.close()
        path = tmp_path / "proj-A.jsonl"
        assert path.exists()
        lines = path.read_text().strip().splitlines()
        assert len(lines) == 1
        decoded = json.loads(lines[0])
        assert decoded["kind"] == "operator_input"

    def test_read_persists_across_instances(self, tmp_path: Path) -> None:
        s1 = ConsoleStore("proj-A", base_dir=str(tmp_path))
        s1.append("operator_input", {"text": "first"})
        s1.close()
        s2 = ConsoleStore("proj-A", base_dir=str(tmp_path))
        events = s2.read_all()
        assert len(events) == 1
        assert events[0]["payload"]["text"] == "first"
        s2.close()

    def test_malformed_line_skipped(self, tmp_path: Path) -> None:
        # Drop a malformed line manually and ensure read_all skips it.
        path = tmp_path / "proj-X.jsonl"
        path.write_text(
            json.dumps({"ts": "1970-01-01T00:00:00Z", "kind": "a"}) + "\n"
            "this is not json\n"
            + json.dumps({"ts": "1970-01-01T00:00:01Z", "kind": "b"}) + "\n"
        )
        store = ConsoleStore("proj-X", base_dir=str(tmp_path))
        events = store.read_all()
        assert [e["kind"] for e in events] == ["a", "b"]

    def test_oversize_event_truncated(self, tmp_path: Path) -> None:
        store = ConsoleStore("proj-X", base_dir=str(tmp_path))
        huge = "X" * (console_mod._MAX_EVENT_BYTES + 100)
        ev = store.append("acp_text", {"text": huge})
        # Truncation marker is set; payload no longer carries the giant string.
        assert ev["payload"].get("_truncated") is True
        store.close()

    def test_project_id_rejects_path_separator(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            ConsoleStore("../escape", base_dir=str(tmp_path))
        with pytest.raises(ValueError):
            ConsoleStore("a/b", base_dir=str(tmp_path))

    def test_project_id_rejects_empty(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            ConsoleStore("", base_dir=str(tmp_path))
        with pytest.raises(ValueError):
            ConsoleStore(".", base_dir=str(tmp_path))
        with pytest.raises(ValueError):
            ConsoleStore("..", base_dir=str(tmp_path))

    def test_read_page_default_limit(self, tmp_path: Path) -> None:
        store = ConsoleStore("proj-P", base_dir=str(tmp_path))
        for i in range(10):
            store.append("operator_input", {"text": f"msg-{i}"})
        events, total = store.read_page(limit=5)
        assert total == 10
        assert len(events) == 5
        # Default page returns the LATEST 5 events.
        assert events[-1]["payload"]["text"] == "msg-9"
        store.close()

    def test_read_page_before(self, tmp_path: Path) -> None:
        store = ConsoleStore("proj-P", base_dir=str(tmp_path))
        for i in range(10):
            store.append("operator_input", {"text": f"msg-{i}"})
        # ``before=5`` should give events at indices [0..4].
        events, total = store.read_page(limit=10, before=5)
        assert total == 10
        assert [e["payload"]["text"] for e in events] == [
            f"msg-{i}" for i in range(5)
        ]
        store.close()


# ----------------------------------------------------------------------
# render_transcript_as_prompt
# ----------------------------------------------------------------------


class TestRenderTranscript:
    def test_minimal_prompt(self) -> None:
        out = render_transcript_as_prompt(
            [],
            new_input="hello",
            project_name="oompah",
        )
        assert "Operator: hello" in out
        assert "Assistant:" in out
        # Header references the project.
        assert "oompah" in out

    def test_includes_operator_and_assistant(self) -> None:
        transcript = [
            {"kind": "operator_input", "payload": {"text": "first"}},
            {"kind": "acp_text", "payload": {"text": "first reply"}},
        ]
        out = render_transcript_as_prompt(
            transcript, new_input="next", project_name="P",
        )
        assert "Operator: first" in out
        assert "Assistant: first reply" in out
        assert "Operator: next" in out

    def test_tool_use_inlined(self) -> None:
        transcript = [
            {
                "kind": "acp_tool_use",
                "payload": {"tool": "run_command", "input": {"command": "ls"}},
            },
        ]
        out = render_transcript_as_prompt(
            transcript, new_input="ok", project_name="P",
        )
        assert "[tool-use run_command" in out

    def test_thinking_dropped(self) -> None:
        transcript = [
            {"kind": "acp_thinking", "payload": {"text": "scratch"}},
            {"kind": "acp_text", "payload": {"text": "speech"}},
        ]
        out = render_transcript_as_prompt(
            transcript, new_input="x", project_name="P",
        )
        assert "scratch" not in out
        assert "speech" in out

    def test_session_start_and_result_skipped(self) -> None:
        transcript = [
            {"kind": "acp_session_start", "payload": {"model": "claude-3-5"}},
            {"kind": "acp_text", "payload": {"text": "hi"}},
            {"kind": "acp_result", "payload": {"num_turns": 1}},
        ]
        out = render_transcript_as_prompt(
            transcript, new_input="x", project_name="P",
        )
        # session_start details should not bleed into the prompt body.
        assert "claude-3-5" not in out
        assert "hi" in out
        assert "num_turns" not in out

    def test_history_capped(self) -> None:
        # 300 events; cap is 200 so the prompt should mention elision.
        transcript = [
            {"kind": "operator_input", "payload": {"text": f"m{i}"}}
            for i in range(300)
        ]
        out = render_transcript_as_prompt(
            transcript, new_input="x", project_name="P",
            max_history_events=200,
        )
        assert "[Earlier 100 events elided" in out
        # The earliest message dropped should NOT appear.
        assert "Operator: m0" not in out
        # The 100th message (start of the kept window) should appear.
        assert "Operator: m100" in out

    def test_includes_tools_summary(self) -> None:
        out = render_transcript_as_prompt(
            [],
            new_input="x",
            project_name="P",
            tools_summary="read/write/run",
        )
        assert "Tools: read/write/run" in out


# ----------------------------------------------------------------------
# ConsoleSession — uses a stubbed AcpAgentSession
# ----------------------------------------------------------------------


@dataclass
class _StubEvent:
    event: str
    payload: dict
    timestamp: float = 0.0
    usage: dict | None = None


class _StubAcpAgentSession:
    """Drop-in for oompah.acp_agent.AcpAgentSession used by the session
    tests. Captures construction args and fires a deterministic sequence
    of on_event callbacks then returns 'succeeded'."""

    INSTANCES: list["_StubAcpAgentSession"] = []
    SCRIPTED_EVENTS: list[_StubEvent] = []
    SCRIPTED_STATUS: str = "succeeded"

    def __init__(
        self,
        workspace_path: str,
        prompt: str,
        *,
        model=None,
        env=None,
        tool_catalog=None,
        on_event=None,
        permission_mode=None,
        backend_name=None,
        **kwargs,
    ):
        self.workspace_path = workspace_path
        self.prompt = prompt
        self.model = model
        self.env = env
        self.tool_catalog = tool_catalog
        self.on_event = on_event
        self.permission_mode = permission_mode
        self.backend_name = backend_name
        self.last_error = None
        _StubAcpAgentSession.INSTANCES.append(self)

    async def run_task(self):
        for ev in _StubAcpAgentSession.SCRIPTED_EVENTS:
            if self.on_event is not None:
                self.on_event(ev)
        return _StubAcpAgentSession.SCRIPTED_STATUS


@pytest.fixture
def stub_acp(monkeypatch):
    """Patch the acp_agent module so ConsoleSession constructs the stub."""
    _StubAcpAgentSession.INSTANCES = []
    _StubAcpAgentSession.SCRIPTED_EVENTS = [
        _StubEvent(event="acp_session_start", payload={"model": "test-model"}),
        _StubEvent(event="acp_text", payload={"text": "hello operator"}),
        _StubEvent(event="acp_result", payload={
            "subtype": "completed",
            "is_error": False,
            "num_turns": 1,
            "total_cost_usd": 0.0,
        }),
    ]
    _StubAcpAgentSession.SCRIPTED_STATUS = "succeeded"
    import sys
    # Patch the symbol that ConsoleSession imports inside _handle_turn.
    # _handle_turn does ``from oompah.acp_agent import AcpAgentSession``
    # so we patch the attribute on the module.
    import oompah.acp_agent as acp_agent_mod
    monkeypatch.setattr(
        acp_agent_mod, "AcpAgentSession", _StubAcpAgentSession,
    )
    # Also patch the tool catalog builders to no-op so tests don't try
    # to import the real Claude SDK.
    import oompah.acp_tools as acp_tools_mod

    def _stub_build_tool_catalog(workspace_path, **kwargs):
        return []

    monkeypatch.setattr(
        acp_tools_mod, "build_tool_catalog", _stub_build_tool_catalog,
    )
    monkeypatch.setattr(
        acp_tools_mod, "build_codex_tool_catalog", _stub_build_tool_catalog,
    )
    return _StubAcpAgentSession


def _resolve_backend_fn(_project_id: str) -> dict:
    return {
        "backend_name": "claude",
        "model": "claude-sonnet",
        "permission_mode": "acceptEdits",
    }


class TestConsoleSession:
    def test_submit_persists_and_broadcasts(self, tmp_path, stub_acp):
        broadcasts: list[tuple[str, dict]] = []

        async def run():
            store = ConsoleStore("proj-T1", base_dir=str(tmp_path))
            session = ConsoleSession(
                project_id="proj-T1",
                workspace_path=str(tmp_path),
                project_name="testproj",
                store=store,
                resolve_backend=_resolve_backend_fn,
                broadcast=lambda pid, ev: broadcasts.append((pid, ev)),
            )
            loop = asyncio.get_event_loop()
            session.ensure_runner(loop=loop)
            fut = await session.submit("hello", wait=True)
            assert fut is not None
            await asyncio.wait_for(fut, timeout=5.0)
            await session.shutdown()
            return session

        session = asyncio.new_event_loop().run_until_complete(run())
        # Check broadcasts: operator_input + 3 scripted events = 4 minimum.
        kinds = [ev["kind"] for (_pid, ev) in broadcasts]
        assert "operator_input" in kinds
        assert "acp_text" in kinds
        assert "acp_result" in kinds
        # Transcript persisted to disk.
        store2 = ConsoleStore("proj-T1", base_dir=str(tmp_path))
        on_disk = store2.read_all()
        assert any(e["kind"] == "operator_input" for e in on_disk)
        assert any(e["kind"] == "acp_text" for e in on_disk)
        store2.close()

    def test_resolve_backend_consulted_per_turn(self, tmp_path, stub_acp):
        """Each turn calls resolve_backend so role/provider edits pick up
        on the next message without restart."""
        calls = []

        def _resolve(pid: str) -> dict:
            calls.append(pid)
            return {"backend_name": "claude", "permission_mode": "acceptEdits"}

        async def run():
            session = ConsoleSession(
                project_id="proj-T2",
                workspace_path=str(tmp_path),
                project_name="x",
                store=ConsoleStore("proj-T2", base_dir=str(tmp_path)),
                resolve_backend=_resolve,
                broadcast=lambda pid, ev: None,
            )
            loop = asyncio.get_event_loop()
            session.ensure_runner(loop=loop)
            for _ in range(2):
                fut = await session.submit("hi", wait=True)
                await asyncio.wait_for(fut, timeout=5.0)
            await session.shutdown()

        asyncio.new_event_loop().run_until_complete(run())
        # resolve_backend called once per turn (2 turns).
        assert len(calls) == 2
        assert calls[0] == "proj-T2"

    def test_concurrent_inputs_serialize(self, tmp_path, stub_acp):
        """Submitting two messages back-to-back must process them one
        after the other, not interleaved."""
        order: list[str] = []

        # Override scripted events to record processing order.
        _StubAcpAgentSession.SCRIPTED_EVENTS = [
            _StubEvent(event="acp_text", payload={"text": "marker"}),
            _StubEvent(event="acp_result", payload={"num_turns": 1}),
        ]

        async def run():
            session = ConsoleSession(
                project_id="proj-T3",
                workspace_path=str(tmp_path),
                project_name="x",
                store=ConsoleStore("proj-T3", base_dir=str(tmp_path)),
                resolve_backend=_resolve_backend_fn,
                broadcast=lambda pid, ev: order.append(ev["kind"]),
            )
            loop = asyncio.get_event_loop()
            session.ensure_runner(loop=loop)
            fut1 = await session.submit("first", wait=True)
            fut2 = await session.submit("second", wait=True)
            await asyncio.wait_for(fut1, timeout=5.0)
            await asyncio.wait_for(fut2, timeout=5.0)
            await session.shutdown()

        asyncio.new_event_loop().run_until_complete(run())
        # Both turns processed completely (operator_input + result for each).
        ops = [k for k in order if k == "operator_input"]
        results = [k for k in order if k == "acp_result"]
        assert len(ops) == 2
        assert len(results) == 2
        # Order: first operator_input, then first turn's events, then
        # second operator_input.
        first_op_idx = order.index("operator_input")
        first_result_idx = order.index("acp_result")
        second_op_idx = order.index("operator_input", first_op_idx + 1)
        assert first_result_idx < second_op_idx, (
            "second operator_input must come AFTER first turn completes"
        )

    def test_restart_replays_transcript(self, tmp_path, stub_acp):
        """Service restart simulated by closing one session and opening
        a fresh one; new session sees prior transcript in its prompt."""
        prompts_seen: list[str] = []

        # First turn: just a basic exchange.
        async def first_session():
            session = ConsoleSession(
                project_id="proj-R",
                workspace_path=str(tmp_path),
                project_name="restart-test",
                store=ConsoleStore("proj-R", base_dir=str(tmp_path)),
                resolve_backend=_resolve_backend_fn,
                broadcast=lambda pid, ev: None,
            )
            loop = asyncio.get_event_loop()
            session.ensure_runner(loop=loop)
            fut = await session.submit("hello, my name is testbot", wait=True)
            await asyncio.wait_for(fut, timeout=5.0)
            await session.shutdown()

        asyncio.new_event_loop().run_until_complete(first_session())

        # Second turn: fresh ConsoleSession. The previous transcript on
        # disk must replay into the prompt.
        async def second_session():
            session = ConsoleSession(
                project_id="proj-R",
                workspace_path=str(tmp_path),
                project_name="restart-test",
                store=ConsoleStore("proj-R", base_dir=str(tmp_path)),
                resolve_backend=_resolve_backend_fn,
                broadcast=lambda pid, ev: None,
            )
            loop = asyncio.get_event_loop()
            session.ensure_runner(loop=loop)
            fut = await session.submit("do you remember?", wait=True)
            await asyncio.wait_for(fut, timeout=5.0)
            await session.shutdown()

        asyncio.new_event_loop().run_until_complete(second_session())
        # Grab the prompt the second session built.
        # _StubAcpAgentSession.INSTANCES[1] is the second turn's session.
        second_instance = _StubAcpAgentSession.INSTANCES[-1]
        assert "hello, my name is testbot" in second_instance.prompt
        assert "do you remember?" in second_instance.prompt


# ----------------------------------------------------------------------
# ConsoleManager
# ----------------------------------------------------------------------


class TestConsoleManager:
    def test_unknown_project_raises(self, tmp_path):
        mgr = ConsoleManager(
            resolve_backend=_resolve_backend_fn,
            broadcast=lambda pid, ev: None,
            resolve_project=lambda pid: None,
            base_dir=str(tmp_path),
        )
        with pytest.raises(KeyError):
            mgr.get_or_create("missing")

    def test_get_or_create_is_idempotent(self, tmp_path):
        mgr = ConsoleManager(
            resolve_backend=_resolve_backend_fn,
            broadcast=lambda pid, ev: None,
            resolve_project=lambda pid: {
                "repo_path": str(tmp_path),
                "name": "x",
            },
            base_dir=str(tmp_path),
        )
        a = mgr.get_or_create("p")
        b = mgr.get_or_create("p")
        assert a is b

    def test_read_transcript_without_session(self, tmp_path):
        # Pre-seed disk so read_transcript has something to return.
        store = ConsoleStore("p", base_dir=str(tmp_path))
        store.append("operator_input", {"text": "preseeded"})
        store.close()
        mgr = ConsoleManager(
            resolve_backend=_resolve_backend_fn,
            broadcast=lambda pid, ev: None,
            resolve_project=lambda pid: {
                "repo_path": str(tmp_path),
                "name": "x",
            },
            base_dir=str(tmp_path),
        )
        # No session is constructed yet — manager._sessions is empty.
        assert mgr.get_session("p") is None
        events, total = mgr.read_transcript("p")
        assert total == 1
        assert events[0]["payload"]["text"] == "preseeded"

    def test_no_repo_path_raises(self, tmp_path):
        mgr = ConsoleManager(
            resolve_backend=_resolve_backend_fn,
            broadcast=lambda pid, ev: None,
            resolve_project=lambda pid: {"repo_path": "", "name": "x"},
            base_dir=str(tmp_path),
        )
        with pytest.raises(KeyError):
            mgr.get_or_create("p")
