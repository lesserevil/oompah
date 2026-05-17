"""Tests for the OpenCode ACP backend (oompah-zlz_2-4wdh).

Covers:

* :class:`OpencodeAcpBackend` registers as ``"opencode"`` at package import.
* ``validate_provider`` accepts subscription auth (empty api_key) and
  validates base_url scheme (http(s)://).
* Session lifecycle smoke test: instantiate the backend, run one turn,
  verify the expected :class:`BackendEvent` stream and terminal status.
* Subprocess management: close() terminates the opencode serve subprocess.

Tests use AsyncMock for subprocess mocking — no real opencode binary required.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from typing import AsyncIterator, Callable
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oompah.acp_backends import (
    BACKENDS,
    AcpBackendOptions,
    BackendEvent,
    get_backend,
    get_backend_or_raise,
)
from oompah.acp_backends.opencode import (
    OpencodeAcpBackend,
    OpencodeAcpBackendSession,
    _OpencodeCounters,
)
from oompah.models import ModelProvider


# ----------------------------------------------------------------------
# Registration
# ----------------------------------------------------------------------


class TestOpencodeRegistration:
    def test_opencode_in_registry(self):
        """Importing oompah.acp_backends must populate BACKENDS['opencode']."""
        assert "opencode" in BACKENDS
        assert BACKENDS["opencode"] is OpencodeAcpBackend

    def test_opencode_name(self):
        assert OpencodeAcpBackend.name() == "opencode"

    def test_opencode_reachable_via_get_backend(self):
        assert get_backend("opencode") is OpencodeAcpBackend
        assert get_backend_or_raise("opencode") is OpencodeAcpBackend


# ----------------------------------------------------------------------
# validate_provider: subscription auth + base_url scheme
# ----------------------------------------------------------------------


class TestOpencodeValidateProvider:
    def test_name_returns_opencode(self):
        """OpencodeAcpBackend.name() must return 'opencode'."""
        assert OpencodeAcpBackend.name() == "opencode"

    def test_validate_provider_accepts_valid_provider(self):
        """Opencode uses subscription auth — empty api_key is OK.

        The opencode CLI handles its own OAuth flow, same as Codex.
        A missing api_key must not produce a validation error."""
        backend = OpencodeAcpBackend()
        provider = ModelProvider(
            id="p", name="opencode", base_url="", api_key="",
        )
        # Simulate subscription billing (empty api_key is fine for opencode).
        provider.billing_model = "subscription"
        errors = backend.validate_provider(provider)
        assert errors == []

    def test_validate_provider_accepts_empty_base_url(self):
        """Empty base_url (operator wants the default endpoint) is fine."""
        backend = OpencodeAcpBackend()
        provider = ModelProvider(
            id="p", name="opencode", base_url="", api_key="",
        )
        assert backend.validate_provider(provider) == []

    def test_validate_provider_accepts_https_base_url(self):
        """HTTPS base_url is accepted."""
        backend = OpencodeAcpBackend()
        provider = ModelProvider(
            id="p", name="opencode",
            base_url="https://api.openai.com/v1",
            api_key="sk-x",
        )
        assert backend.validate_provider(provider) == []

    def test_validate_provider_accepts_http_base_url(self):
        """HTTP base_url (e.g., local proxy) is accepted."""
        backend = OpencodeAcpBackend()
        provider = ModelProvider(
            id="p", name="opencode",
            base_url="http://localhost:8080",
            api_key="sk-x",
        )
        assert backend.validate_provider(provider) == []

    def test_validate_provider_rejects_invalid_base_url(self):
        """base_url not starting with http:// or https:// returns an error."""
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


# ----------------------------------------------------------------------
# start_session
# ----------------------------------------------------------------------


class TestOpencodeStartSession:
    def test_start_session_returns_session(self):
        """start_session returns a session handle without invoking
        the subprocess — the subprocess only fires on the first
        run_turn call."""
        backend = OpencodeAcpBackend()
        opt = AcpBackendOptions(
            workspace_path="/tmp/ws",
            prompt="do the thing",
            model="opencode-model",
        )
        session = backend.start_session(opt)
        assert isinstance(session, OpencodeAcpBackendSession)
        assert session.status == "pending"


# ----------------------------------------------------------------------
# Session properties before run_turn
# ----------------------------------------------------------------------


class TestOpencodeSessionDefaults:
    def test_session_properties_default_before_run_turn(self):
        """Before run_turn, session has default sentinel values."""
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
# Mock helpers
# ----------------------------------------------------------------------


class _FakeStdin:
    """Minimal stand-in for asyncio.subprocess.PIPE stdin."""

    def __init__(self):
        self.buffer: list[bytes] = []
        self._closed = False

    def write(self, data: bytes) -> None:
        # asyncio.StreamWriter.write() is synchronous.
        self.buffer.append(data)

    async def drain(self) -> None:
        pass

    async def close(self) -> None:
        self._closed = True


class AsyncMockReadingStream:
    """Wraps a list of Python dicts as an async bytes iterator suitable
    for mocking subprocess.PIPE stdout."""

    def __init__(self, messages: list[dict]):
        self.messages = messages
        self._closed = False

    def __aiter__(self) -> AsyncIterator[bytes]:
        return self._async_gen()

    async def _async_gen(self) -> AsyncIterator[bytes]:
        for msg in self.messages:
            if self._closed:
                break
            await asyncio.sleep(0)  # yield control
            yield (json.dumps(msg) + "\n").encode("utf-8")

    async def read(self) -> bytes:
        return b""


# ----------------------------------------------------------------------
# Session lifecycle with mocked subprocess
# ----------------------------------------------------------------------


class TestOpencodeSessionLifecycle:
    """Smoke test: drive an OpencodeAcpBackendSession from start to
    terminal status through the public protocol.  Mocks the subprocess
    so the real opencode binary never has to be installed."""

    def _drive_session(
        self,
        *,
        stdout_messages: list[dict] | None = None,
        return_code: int = 0,
        on_event: Callable[[BackendEvent], None] | None = None,
        **opt_kwargs,
    ):
        """Run one turn with a mocked subprocess.

        Args:
            stdout_messages: JSON messages the fake stdout should emit.
            return_code: value returned by proc.wait().
            on_event: optional BackendEvent consumer (mirrors on_event path).
        """
        if stdout_messages is None:
            stdout_messages = []

        async def runner():
            options = AcpBackendOptions(
                workspace_path="/tmp/ws",
                prompt=opt_kwargs.get("prompt", "do the thing"),
                model=opt_kwargs.get("model", "opencode-model"),
                env=opt_kwargs.get("env"),
                permission_mode=opt_kwargs.get("permission_mode", "default"),
                on_event=on_event,
            )
            # Short-circuit the tool catalog builder so we don't load
            # the real MCP tools at catalog-build time.
            session = OpencodeAcpBackendSession(options)

            # Mock the subprocess via asyncio.create_subprocess_exec.
            fake_stdin = _FakeStdin()

            proc = MagicMock()
            proc.stdin = fake_stdin
            proc.stdout = AsyncMockReadingStream(stdout_messages)
            # stderr.read() is sync (returns bytes from a StreamReader) — use
            # MagicMock so we don't trigger "coroutine never awaited" warnings
            # when the mock's read() method is left unawaited by accident.
            proc.stderr = MagicMock()
            proc.terminate = MagicMock()
            proc.kill = MagicMock()
            proc.wait = AsyncMock(return_value=return_code)

            with patch(
                "asyncio.create_subprocess_exec",
                new=AsyncMock(return_value=proc),
            ):
                collected: list[BackendEvent] = []
                async for ev in session.run_turn():
                    collected.append(ev)
                    if len(collected) > 200:
                        break  # guard
                return session, collected, proc

        return asyncio.run(runner())

    def test_run_turn_emits_session_start(self):
        """The first event emitted is acp_session_start carrying model
        and tool_policy metadata."""
        session, stream, _ = self._drive_session(
            stdout_messages=[
                {"type": "session_start", "session_id": "sess-1"},
            ],
        )
        assert len(stream) >= 1
        assert stream[0].kind == "session_start"
        assert stream[0].payload["model"] == "opencode-model"
        assert stream[0].payload["tool_policy"] == "opencode:tool_catalog"

    def test_run_turn_emits_text_events(self):
        """Assistant text messages map to acp_text events."""
        session, stream, _ = self._drive_session(
            stdout_messages=[
                {"type": "text", "text": "hello world"},
            ],
        )
        kinds = [ev.kind for ev in stream]
        assert "text" in kinds
        text_events = [ev for ev in stream if ev.kind == "text"]
        assert len(text_events) == 1
        assert text_events[0].payload["text"] == "hello world"

    def test_run_turn_emits_tool_use_events(self):
        """Tool call requests map to acp_tool_use events."""
        session, stream, _ = self._drive_session(
            stdout_messages=[
                {"type": "tool_use", "id": "call-1", "tool": "read_file", "input": {"path": "/tmp/x"}},
            ],
        )
        kinds = [ev.kind for ev in stream]
        assert "tool_use" in kinds
        tool_events = [ev for ev in stream if ev.kind == "tool_use"]
        assert len(tool_events) == 1
        assert tool_events[0].payload["tool"] == "read_file"
        assert tool_events[0].payload["id"] == "call-1"

    def test_run_turn_emits_tool_result_events(self):
        """Tool results map to acp_tool_result events."""
        session, stream, _ = self._drive_session(
            stdout_messages=[
                {
                    "type": "tool_result",
                    "tool_use_id": "call-1",
                    "content": "file content here",
                    "is_error": False,
                },
            ],
        )
        kinds = [ev.kind for ev in stream]
        assert "tool_result" in kinds
        result_events = [ev for ev in stream if ev.kind == "tool_result"]
        assert len(result_events) == 1
        assert result_events[0].payload["tool_use_id"] == "call-1"
        assert "file content here" in result_events[0].payload["content"]

    def test_run_turn_emits_result_on_success(self):
        """When opencode serve exits 0, the final event is acp_result
        with subtype success."""
        session, stream, _ = self._drive_session(
            stdout_messages=[
                {
                    "type": "result",
                    "stop_reason": "end_turn",
                    "usage": {"input_tokens": 10, "output_tokens": 5},
                },
            ],
        )
        kinds = [ev.kind for ev in stream]
        assert kinds[-1] == "result"
        result_ev = stream[-1]
        assert result_ev.payload["subtype"] == "success"
        assert session.status == "succeeded"

    def test_run_turn_sets_errored_status_on_exception(self):
        """When the subprocess exits non-zero, status becomes 'errored'
        and last_error is set."""
        session, stream, _ = self._drive_session(
            stdout_messages=[
                {"type": "error", "error": "something went wrong"},
            ],
            return_code=1,
        )
        assert session.status == "errored"
        assert session.last_error is not None
        kinds = [ev.kind for ev in stream]
        assert "session_error" in kinds

    def test_run_turn_session_start_captures_session_id(self):
        """session_id from opencode session_start message is captured."""
        session, stream, _ = self._drive_session(
            stdout_messages=[
                {"type": "session_start", "session_id": "sess-abc123"},
            ],
        )
        assert session.session_id == "sess-abc123"

    def test_run_turn_absorbs_usage_from_session_start(self):
        """Usage data from session_start rolls up to session counters."""
        session, stream, _ = self._drive_session(
            stdout_messages=[
                {
                    "type": "session_start",
                    "session_id": "sess-1",
                    "usage": {"input_tokens": 100, "output_tokens": 50},
                },
            ],
        )
        assert session.input_tokens == 100
        assert session.output_tokens == 50
        assert session.total_tokens == 150


class TestOpencodeClose:
    """Tests for close() marking the session interrupted and killing subprocess."""

    def test_close_before_run_turn_marks_interrupted(self):
        """close() before run_turn marks the session 'interrupted' so
        run_turn exits immediately."""
        backend = OpencodeAcpBackend()
        opt = AcpBackendOptions(workspace_path="/tmp/ws", prompt="x")
        session = backend.start_session(opt)

        async def run():
            await session.close()
            return session

        session = asyncio.run(run())
        assert session.status == "interrupted"

    def test_close_terminates_subprocess(self):
        """close() while subprocess is active calls terminate() on the
        process handle."""
        backend = OpencodeAcpBackend()
        opt = AcpBackendOptions(workspace_path="/tmp/ws", prompt="x")
        session = backend.start_session(opt)

        # Mock the subprocess.
        fake_stdin = _FakeStdin()
        proc = MagicMock()
        proc.stdin = fake_stdin
        proc.stdout = AsyncMockReadingStream([
            {"type": "session_start", "session_id": "sess-1"},
            {"type": "text", "text": "hello"},
            {"type": "result", "stop_reason": "end_turn"},
        ])
        # stderr.read() returns bytes (sync), so use MagicMock.
        proc.stderr = MagicMock()
        proc.terminate = MagicMock()
        proc.kill = MagicMock()
        proc.wait = AsyncMock(return_value=0)

        async def run():
            with patch(
                "asyncio.create_subprocess_exec",
                new=AsyncMock(return_value=proc),
            ):
                # Start run_turn but close it immediately.
                async def run_and_close():
                    ev_queue = []
                    async for ev in session.run_turn():
                        ev_queue.append(ev)
                    return ev_queue

                task = asyncio.create_task(run_and_close())
                # Let run_turn start.
                await asyncio.sleep(0.05)
                await session.close()
                # Allow the task to finish.
                try:
                    await asyncio.wait_for(task, timeout=2.0)
                except Exception:
                    pass
                return proc

        proc = asyncio.run(run())
        # terminate was called.
        assert proc.terminate.called


# ----------------------------------------------------------------------
# _OpencodeCounters
# ----------------------------------------------------------------------


class TestOpencodeCounters:
    def test_absorb_usage_from_dict(self):
        c = _OpencodeCounters()
        c.absorb_usage({"input_tokens": 11, "output_tokens": 22})
        assert c.input_tokens == 11
        assert c.output_tokens == 22
        assert c.total_tokens == 33

    def test_absorb_usage_with_total(self):
        """When total_tokens is explicitly reported, use it."""
        c = _OpencodeCounters()
        c.absorb_usage({"input_tokens": 4, "output_tokens": 5, "total_tokens": 9})
        assert c.total_tokens == 9

    def test_absorb_usage_none_is_noop(self):
        """None usage is silently ignored."""
        c = _OpencodeCounters()
        c.absorb_usage(None)
        assert c.input_tokens == 0
        assert c.output_tokens == 0
        assert c.total_tokens == 0

    def test_absorb_usage_invalid_is_noop(self):
        """Non-dict usage is silently ignored."""
        c = _OpencodeCounters()
        c.absorb_usage("not a usage object")
        assert c.input_tokens == 0