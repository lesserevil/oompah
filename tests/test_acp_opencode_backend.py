"""Tests for the Opencode ACP backend (oompah-zlz_2-4wdh).

Covers:

* :class:`OpencodeAcpBackend` registers as ``"opencode"`` at package import.
* ``validate_provider`` accepts empty api_key for subscription auth and
  rejects invalid base_url schemes.
* :class:`OpencodeAcpBackendSession` lifecycle: properties before run_turn,
  event emission via subprocess JSON-lines, error handling, and close().
* All tests use AsyncMock for subprocess mocking — no real opencode binary
  required.
"""

from __future__ import annotations

import asyncio
import json
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oompah.acp_backends import (
    BACKENDS,
    AcpBackendOptions,
    BackendEvent,
)
from oompah.acp_backends.opencode import (
    OpencodeAcpBackend,
    OpencodeAcpBackendSession,
    _OpencodeCounters,
)
from oompah.models import ModelProvider


# ----------------------------------------------------------------------
# Registration: opencode shows up in the registry
# ----------------------------------------------------------------------


class TestOpencodeRegistration:
    def test_opencode_in_registry(self):
        """Importing oompah.acp_backends populates BACKENDS['opencode']."""
        assert "opencode" in BACKENDS
        assert BACKENDS["opencode"] is OpencodeAcpBackend

    def test_opencode_name(self):
        assert OpencodeAcpBackend.name() == "opencode"

    def test_opencode_reachable_via_registry(self):
        from oompah.acp_backends.registry import get_backend, get_backend_or_raise
        assert get_backend("opencode") is OpencodeAcpBackend
        assert get_backend_or_raise("opencode") is OpencodeAcpBackend


# ----------------------------------------------------------------------
# validate_provider: subscription auth + base_url validation
# ----------------------------------------------------------------------


class TestOpencodeValidateProvider:
    def test_name_returns_opencode(self):
        """Explicit acceptance criterion: name() == 'opencode'."""
        assert OpencodeAcpBackend.name() == "opencode"

    def test_empty_api_key_ok_for_subscription(self):
        """Opencode uses subscription auth at CLI level — empty api_key
        is perfectly valid. No api_key validation error should fire."""
        backend = OpencodeAcpBackend()
        provider = ModelProvider(
            id="p", name="opencode", base_url="", api_key="",
        )
        # Simulate subscription billing model (opencode handles its own OAuth).
        provider.billing_model = "subscription"
        errors = backend.validate_provider(provider)
        assert errors == []

    def test_api_key_not_required(self):
        """Even without billing_model set, opencode should not error on
        missing api_key since the CLI handles auth differently."""
        backend = OpencodeAcpBackend()
        provider = ModelProvider(
            id="p", name="opencode", base_url="", api_key="",
        )
        errors = backend.validate_provider(provider)
        assert errors == []

    def test_base_url_default_empty_ok(self):
        """An empty base_url (operator wants the default endpoint) is fine."""
        backend = OpencodeAcpBackend()
        provider = ModelProvider(
            id="p", name="opencode", base_url="", api_key="sk-test",
        )
        assert backend.validate_provider(provider) == []

    def test_base_url_https_ok(self):
        backend = OpencodeAcpBackend()
        provider = ModelProvider(
            id="p", name="opencode",
            base_url="https://api.openai.com/v1",
            api_key="sk-x",
        )
        assert backend.validate_provider(provider) == []

    def test_base_url_http_ok(self):
        """Operators sometimes proxy via a local http:// LB — must work."""
        backend = OpencodeAcpBackend()
        provider = ModelProvider(
            id="p", name="opencode",
            base_url="http://localhost:8080",
            api_key="sk-x",
        )
        assert backend.validate_provider(provider) == []

    def test_base_url_invalid_scheme_fails(self):
        """base_url without http:// or https:// must be rejected."""
        backend = OpencodeAcpBackend()
        provider = ModelProvider(
            id="p", name="opencode",
            base_url="ftp://bogus",
            api_key="sk-x",
        )
        errors = backend.validate_provider(provider)
        assert len(errors) == 1
        assert "base_url" in errors[0]
        assert "http://" in errors[0] or "https://" in errors[0]

    def test_base_url_no_scheme_fails(self):
        backend = OpencodeAcpBackend()
        provider = ModelProvider(
            id="p", name="opencode",
            base_url="opencode.internal",
            api_key="sk-x",
        )
        errors = backend.validate_provider(provider)
        assert len(errors) == 1
        assert "base_url" in errors[0]


# ----------------------------------------------------------------------
# OpencodeAcpBackend.start_session returns a session-shaped handle
# ----------------------------------------------------------------------


class TestOpencodeStartSession:
    def test_start_session_returns_session(self):
        """start_session returns a session handle without spawning subprocess."""
        backend = OpencodeAcpBackend()
        opt = AcpBackendOptions(
            workspace_path="/tmp/ws",
            prompt="do the thing",
            model="opencode",
        )
        session = backend.start_session(opt)
        assert isinstance(session, OpencodeAcpBackendSession)
        assert session.status == "pending"

    def test_session_properties_default_before_run(self):
        """Before run_turn is called, all counters are zero and status is pending."""
        backend = OpencodeAcpBackend()
        opt = AcpBackendOptions(workspace_path="/tmp/ws", prompt="x")
        session = backend.start_session(opt)
        assert session.status == "pending"
        assert session.input_tokens == 0
        assert session.output_tokens == 0
        assert session.total_tokens == 0
        assert session.total_cost_usd is None
        assert session.session_id is None
        assert session.turn_count == 0
        assert session.last_error is None
        assert session.permission_denials == []


# ----------------------------------------------------------------------
# Mock helpers for subprocess-driven session tests
# ----------------------------------------------------------------------


class _FakeSubprocess:
    """Minimal async subprocess stand-in for the opencode serve backend.

    Set ``events`` to a list of dicts (one JSON-line per event).  The
    ``stdin``, ``stdout``, ``stderr`` fake streams are async iterables
    that yield those dicts as JSON-lines.
    """

    def __init__(self, *, events: list[dict] | None = None, exit_code: int = 0):
        self.events = events or []
        self.exit_code = exit_code
        self._stdin = _FakeStdin()
        self._stdout = _FakeStdout(events)
        self._stderr = _FakeStderr()
        self.returncode = exit_code
        self.stdin = self._stdin
        self.stdout = self._stdout
        self.stderr = self._stderr
        self.terminate_count = 0
        self.kill_count = 0

    async def wait(self):
        return self.exit_code

    def terminate(self):
        self.terminate_count += 1

    def kill(self):
        self.kill_count += 1


class _FakeStdin:
    """Async file-like object that accepts writes."""

    async def write(self, data: bytes):
        pass

    async def drain(self):
        pass


class _FakeStdout:
    """Async file-like object that yields JSON-lines from events list.

    Each __anext__() call awaits asyncio.sleep(0) first to genuinely yield
    to the event loop. This allows run_turn() to be at an async suspension
    point when close() is called — the natural "subprocess is alive" state.
    """

    def __init__(self, events: list[dict] | None):
        self._events = events or []

    def __aiter__(self):
        return self

    async def __anext__(self):
        # Genuinely yield to the event loop first — this is critical for
        # proper async interleaving so run_turn() can be at a suspension
        # point when close() is called mid-iteration.
        await asyncio.sleep(0)
        if not self._events:
            raise StopAsyncIteration
        ev = self._events.pop(0)
        return json.dumps(ev).encode("utf-8")


class _FakeStderr:
    """Async file-like object that yields nothing."""

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration

    async def read(self):
        return b""


# ----------------------------------------------------------------------
# Session lifecycle tests
# ----------------------------------------------------------------------


def _drive_session(session: OpencodeAcpBackendSession) -> tuple:
    """Run run_turn to completion and return (session, collected_events)."""
    async def _run():
        collected = []
        async for ev in session.run_turn():
            collected.append(ev)
        return session, collected

    return asyncio.run(_run())


class TestOpencodeSessionLifecycle:
    """Drive an OpencodeAcpBackendSession through the public protocol
    using a mock subprocess."""

    def _mock_subprocess_exec(self, fake_proc: _FakeSubprocess):
        """Patch asyncio.create_subprocess_exec to return the fake proc."""
        return patch(
            "asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=fake_proc),
        )

    def test_session_properties_default_before_run_turn(self):
        """Acceptance criterion: status='pending', input_tokens=0, etc."""
        backend = OpencodeAcpBackend()
        opt = AcpBackendOptions(workspace_path="/tmp/ws", prompt="x")
        session = backend.start_session(opt)
        assert session.status == "pending"
        assert session.input_tokens == 0
        assert session.output_tokens == 0
        assert session.total_tokens == 0
        assert session.total_cost_usd is None
        assert session.session_id is None
        assert session.turn_count == 0
        assert session.last_error is None

    def test_run_turn_emits_session_start(self):
        """First event from run_turn is acp_session_start with model metadata."""
        backend = OpencodeAcpBackend()
        opt = AcpBackendOptions(
            workspace_path="/tmp/ws",
            prompt="do the thing",
            model="opencode",
        )
        session = backend.start_session(opt)
        fake = _FakeSubprocess(events=[{"type": "result", "status": "success"}])
        with self._mock_subprocess_exec(fake):
            _sess, events = _drive_session(session)

        assert len(events) >= 1
        assert events[0].kind == "session_start"
        assert events[0].payload["model"] == "opencode"
        assert events[0].payload["tool_policy"] == "opencode:tool_catalog"
        assert events[0].payload["billing_model"] == "subscription"

    def test_run_turn_emits_text_events(self):
        """Assistant text messages from opencode serve map to acp_text events."""
        backend = OpencodeAcpBackend()
        opt = AcpBackendOptions(workspace_path="/tmp/ws", prompt="hello")
        session = backend.start_session(opt)
        fake = _FakeSubprocess(events=[
            {"type": "text", "text": "Hello, world!"},
            {"type": "result", "status": "success"},
        ])
        with self._mock_subprocess_exec(fake):
            _sess, events = _drive_session(session)

        kinds = [ev.kind for ev in events]
        assert "text" in kinds
        text_ev = next(ev for ev in events if ev.kind == "text")
        assert text_ev.payload["text"] == "Hello, world!"

    def test_run_turn_emits_tool_use_events(self):
        """opencode tool_use messages map to acp_tool_use events with tool name/input."""
        backend = OpencodeAcpBackend()
        opt = AcpBackendOptions(workspace_path="/tmp/ws", prompt="run a tool")
        session = backend.start_session(opt)
        fake = _FakeSubprocess(events=[
            {
                "type": "tool_use",
                "id": "call_abc123",
                "tool": "read_file",
                "input": {"path": "/tmp/foo.txt"},
            },
            {"type": "result", "status": "success"},
        ])
        with self._mock_subprocess_exec(fake):
            _sess, events = _drive_session(session)

        kinds = [ev.kind for ev in events]
        assert "tool_use" in kinds
        tool_ev = next(ev for ev in events if ev.kind == "tool_use")
        assert tool_ev.payload["tool"] == "read_file"
        assert tool_ev.payload["id"] == "call_abc123"
        assert tool_ev.payload["input"]["path"] == "/tmp/foo.txt"

    def test_run_turn_emits_tool_result_events(self):
        """tool_result messages map to acp_tool_result events."""
        backend = OpencodeAcpBackend()
        opt = AcpBackendOptions(workspace_path="/tmp/ws", prompt="run a tool")
        session = backend.start_session(opt)
        fake = _FakeSubprocess(events=[
            {
                "type": "tool_result",
                "tool_use_id": "call_abc123",
                "content": "file contents here",
                "is_error": False,
            },
            {"type": "result", "status": "success"},
        ])
        with self._mock_subprocess_exec(fake):
            _sess, events = _drive_session(session)

        kinds = [ev.kind for ev in events]
        assert "tool_result" in kinds
        result_ev = next(ev for ev in events if ev.kind == "tool_result")
        assert result_ev.payload["tool_use_id"] == "call_abc123"
        assert result_ev.payload["content"] == "file contents here"
        assert result_ev.payload["is_error"] is False

    def test_run_turn_emits_result_on_success(self):
        """Terminal result event has subtype=success and normalized usage dict."""
        backend = OpencodeAcpBackend()
        opt = AcpBackendOptions(workspace_path="/tmp/ws", prompt="hello")
        session = backend.start_session(opt)
        fake = _FakeSubprocess(events=[
            {"type": "result", "status": "success", "usage": {
                "input_tokens": 10, "output_tokens": 20, "total_tokens": 30,
            }},
        ])
        with self._mock_subprocess_exec(fake):
            _sess, events = _drive_session(session)

        kinds = [ev.kind for ev in events]
        assert "result" in kinds
        result_ev = next(ev for ev in events if ev.kind == "result")
        assert result_ev.payload["subtype"] == "success"
        assert result_ev.payload["is_error"] is False
        # usage dict is normalized
        usage = result_ev.payload.get("usage", {})
        assert usage["input_tokens"] == 10
        assert usage["output_tokens"] == 20
        assert usage["total_tokens"] == 30

    def test_run_turn_sets_errored_status_on_exception(self):
        """When the subprocess crashes, status becomes 'errored' and last_error is set."""
        backend = OpencodeAcpBackend()
        opt = AcpBackendOptions(workspace_path="/tmp/ws", prompt="hello")
        session = backend.start_session(opt)
        # FileNotFoundError from create_subprocess_exec → errored status.
        with patch(
            "asyncio.create_subprocess_exec",
            new=AsyncMock(side_effect=FileNotFoundError("opencode not found")),
        ):
            _sess, events = _drive_session(session)

        assert session.status == "errored"
        assert session.last_error is not None
        assert "opencode" in session.last_error.lower()
        kinds = [ev.kind for ev in events]
        assert "session_error" in kinds

    def test_run_turn_sets_errored_status_on_subprocess_failure(self):
        """Non-zero exit code from subprocess → errored status."""
        backend = OpencodeAcpBackend()
        opt = AcpBackendOptions(workspace_path="/tmp/ws", prompt="hello")
        session = backend.start_session(opt)
        fake = _FakeSubprocess(
            events=[{"type": "text", "text": "partial output"}],
            exit_code=1,
        )
        with self._mock_subprocess_exec(fake):
            _sess, events = _drive_session(session)

        assert session.status == "errored"
        assert session.last_error is not None

    def test_close_terminates_subprocess(self):
        """close() while run_turn() is active causes the next iteration to
        detect _stop_requested and exit with status='interrupted'.

        We also verify terminate() fires via aclose() which forces the
        generator's finally block to run through its cleanup path.
        """
        backend = OpencodeAcpBackend()
        opt = AcpBackendOptions(workspace_path="/tmp/ws", prompt="hello")
        session = backend.start_session(opt)

        fake = _FakeSubprocess(
            events=[
                {"type": "text", "text": "hello"},
                {"type": "result", "status": "success"},
            ],
        )
        patched = patch(
            "asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=fake),
        )

        async def _test():
            with patched:
                gen = session.run_turn()
                # First event: session_start.
                first = await gen.__anext__()
                assert first.kind == "session_start"
                # Second event: text event.
                second = await gen.__anext__()
                assert second.kind == "text"
                # Now close() while run_turn() is blocked on the next stdout read.
                await session.close()
                assert session._stop_requested is True
                # There is no further event because run_turn() sees
                # _stop_requested and exits the loop before the result msg.
                collected = []
                async for ev in gen:
                    collected.append(ev)
                return session, fake, collected

        sess, proc, events = asyncio.run(_test())

        # No terminal result event — interrupted before stdout could be re-read.
        kinds = [ev.kind for ev in events]
        assert "result" not in kinds
        # Status is interrupted from close().
        assert sess.status == "interrupted"
        # aclose() should be a no-op since gen already finished, but
        # verify terminate was at least called (via generator cleanup path
        # once events exhaust — the remaining result message triggers
        # the finally).
        assert proc.terminate_count >= 1

    def test_close_before_run_turn_marks_interrupted(self):
        """close() before run_turn sets status='interrupted' with no subprocess."""
        backend = OpencodeAcpBackend()
        opt = AcpBackendOptions(workspace_path="/tmp/ws", prompt="hello")
        session = backend.start_session(opt)

        async def _close_then_run():
            await session.close()
            # run_turn should return immediately when interrupted.
            collected = []
            async for ev in session.run_turn():
                collected.append(ev)
            return session, collected

        sess, events = asyncio.run(_close_then_run())
        assert sess.status == "interrupted"
        # No events because run_turn exited early.
        assert events == []

    def test_run_turn_captures_session_id_from_session_start(self):
        """session_id is captured from the opencode session_start message."""
        backend = OpencodeAcpBackend()
        opt = AcpBackendOptions(workspace_path="/tmp/ws", prompt="hello")
        session = backend.start_session(opt)
        fake = _FakeSubprocess(events=[
            {"type": "session_start", "session_id": "sess-opencode-42", "usage": {
                "input_tokens": 1, "output_tokens": 1, "total_tokens": 2,
            }},
            {"type": "result", "status": "success"},
        ])
        with self._mock_subprocess_exec(fake):
            _sess, events = _drive_session(session)

        assert session.session_id == "sess-opencode-42"

    def test_run_turn_absorbs_usage_from_session_start(self):
        """Usage data from session_start message updates counters."""
        backend = OpencodeAcpBackend()
        opt = AcpBackendOptions(workspace_path="/tmp/ws", prompt="hello")
        session = backend.start_session(opt)
        fake = _FakeSubprocess(events=[
            {"type": "session_start", "usage": {
                "input_tokens": 5, "output_tokens": 10, "total_tokens": 15,
            }},
            {"type": "result", "status": "success"},
        ])
        with self._mock_subprocess_exec(fake):
            _sess, events = _drive_session(session)

        assert session.input_tokens == 5
        assert session.output_tokens == 10
        assert session.total_tokens == 15

    def test_run_turn_increments_turn_count_on_tool_use(self):
        """Each tool_use message increments turn_count."""
        backend = OpencodeAcpBackend()
        opt = AcpBackendOptions(workspace_path="/tmp/ws", prompt="use tools")
        session = backend.start_session(opt)
        fake = _FakeSubprocess(events=[
            {"type": "tool_use", "id": "1", "tool": "read_file", "input": {}},
            {"type": "tool_use", "id": "2", "tool": "write_file", "input": {}},
            {"type": "result", "status": "success"},
        ])
        with self._mock_subprocess_exec(fake):
            _sess, events = _drive_session(session)

        assert session.turn_count == 2

    def test_run_turn_emit_agent_events(self):
        """AgentEvents flow through on_event callback for audit logging."""
        events_captured = []

        def on_event(ev):
            events_captured.append(ev)

        backend = OpencodeAcpBackend()
        opt = AcpBackendOptions(
            workspace_path="/tmp/ws",
            prompt="hello",
            on_event=on_event,
        )
        session = backend.start_session(opt)
        fake = _FakeSubprocess(events=[
            {"type": "session_start", "session_id": "sess-1"},
            {"type": "result", "status": "success"},
        ])
        with self._mock_subprocess_exec(fake):
            _sess, events = _drive_session(session)

        agent_event_names = [e.event for e in events_captured]
        assert "acp_session_start" in agent_event_names
        assert "acp_result" in agent_event_names


# ----------------------------------------------------------------------
# Counters
# ----------------------------------------------------------------------


class TestOpencodeCounters:
    def test_absorb_usage_from_dict(self):
        c = _OpencodeCounters()
        c.absorb_usage({"input_tokens": 11, "output_tokens": 22, "total_tokens": 33})
        assert c.input_tokens == 11
        assert c.output_tokens == 22
        assert c.total_tokens == 33

    def test_absorb_usage_derives_total(self):
        """When SDK reports input+output but not total, derive total."""
        c = _OpencodeCounters()
        c.absorb_usage({"input_tokens": 4, "output_tokens": 5})
        assert c.total_tokens == 9

    def test_absorb_usage_from_object(self):
        usage = types.SimpleNamespace(input_tokens=7, output_tokens=3, total_tokens=10)
        c = _OpencodeCounters()
        c.absorb_usage(usage)
        assert c.input_tokens == 7
        assert c.output_tokens == 3
        assert c.total_tokens == 10

    def test_absorb_usage_none_is_noop(self):
        c = _OpencodeCounters()
        c.absorb_usage(None)
        assert c.input_tokens == 0
        assert c.output_tokens == 0
        assert c.total_tokens == 0