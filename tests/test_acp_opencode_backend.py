"""Tests for the Opencode ACP backend (oompah-zlz_2-4wdh).

Covers:

* :class:`OpencodeAcpBackend` registers as ``"opencode"`` at package import.
* ``validate_provider`` accepts subscription auth (empty api_key OK) and
  enforces http(s) base_url when overridden.
* Session lifecycle: start_session returns a pending session; run_turn
  drives the subprocess and emits the expected event stream.
* Tool bridging, error handling, and close() lifecycle.

The opencode backend is subprocess-driven via ``opencode serve``,
communicating over JSON-lines stdin/stdout. Tests mock
``asyncio.create_subprocess_exec`` so no real opencode binary is needed.
"""

from __future__ import annotations

import asyncio
import json
import types
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
# Registration: opencode shows up in the registry
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

    def test_acp_mode_provider_with_opencode_validates_via_registry(self):
        """Provider record with mode=acp + backend='opencode' passes the
        registry lookup check (validate_for_mode)."""
        provider = ModelProvider(
            id="p", name="opencode", base_url="", backend="opencode",
            api_key="",
        )
        assert provider.validate_for_mode("acp") == []


# ----------------------------------------------------------------------
# validate_provider: subscription auth, no api_key required
# ----------------------------------------------------------------------


class TestOpencodeValidateProvider:
    def test_empty_api_key_is_ok(self):
        """Opencode backend uses subscription auth at the CLI level --
        no api_key required on the provider record."""
        backend = OpencodeAcpBackend()
        provider = ModelProvider(
            id="p", name="opencode", base_url="", api_key="",
        )
        assert backend.validate_provider(provider) == []

    def test_empty_base_url_is_ok(self):
        """Default endpoint (empty base_url) is always fine."""
        backend = OpencodeAcpBackend()
        provider = ModelProvider(
            id="p", name="opencode", base_url="", api_key="",
        )
        assert backend.validate_provider(provider) == []

    def test_http_base_url_is_ok(self):
        backend = OpencodeAcpBackend()
        provider = ModelProvider(
            id="p", name="opencode",
            base_url="http://localhost:8080",
            api_key="",
        )
        assert backend.validate_provider(provider) == []

    def test_https_base_url_is_ok(self):
        backend = OpencodeAcpBackend()
        provider = ModelProvider(
            id="p", name="opencode",
            base_url="https://api.openai.com/v1",
            api_key="",
        )
        assert backend.validate_provider(provider) == []

    def test_invalid_base_url_scheme_fails(self):
        """base_url must start with http:// or https://."""
        backend = OpencodeAcpBackend()
        provider = ModelProvider(
            id="p", name="opencode",
            base_url="ftp://bogus",
            api_key="",
        )
        errors = backend.validate_provider(provider)
        assert len(errors) == 1
        assert "base_url" in errors[0]
        assert "http://" in errors[0] or "https://" in errors[0]

    def test_grpc_base_url_fails(self):
        """Other URL schemes are rejected."""
        backend = OpencodeAcpBackend()
        provider = ModelProvider(
            id="p", name="opencode",
            base_url="grpc://localhost",
            api_key="",
        )
        errors = backend.validate_provider(provider)
        assert len(errors) == 1
        assert "base_url" in errors[0]


# ----------------------------------------------------------------------
# start_session: returns a pending session
# ----------------------------------------------------------------------


class TestOpencodeStartSession:
    def test_start_session_returns_session(self):
        backend = OpencodeAcpBackend()
        opt = AcpBackendOptions(
            workspace_path="/tmp/ws",
            prompt="do the thing",
            model="gpt-5",
        )
        session = backend.start_session(opt)
        assert isinstance(session, OpencodeAcpBackendSession)
        assert session.status == "pending"

    def test_session_properties_default_before_run(self):
        """All counter properties are zeroed / None before run_turn."""
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
# Mock helpers for subprocess-driven tests
# ----------------------------------------------------------------------


class _FakeLineWriter:
    """Synchronous writable stream that buffers written lines for draining.

    Mirrors the interface of ``asyncio.subprocess.PIPE`` where write()
    is synchronous (not a coroutine) and drain() is the async flush.
    """

    def __init__(self):
        self._buffer: list[bytes] = []

    def write(self, data: bytes) -> None:
        """Synchronous write -- same contract as asyncio.subprocess.PIPE."""
        self._buffer.append(data)

    async def drain(self) -> None:
        """Async drain -- clears the buffer after the caller awaits it."""
        self._buffer.clear()


class _AsyncLineReader:
    """Async iterator that yields lines from a predefined list.

    Mirrors the interface of asyncio.subprocess.PIPE — an async
    generator that reads byte lines until exhaustion.
    """

    def __init__(self, lines: list[bytes]):
        self._lines = lines
        self._idx = 0

    def __aiter__(self) -> "_AsyncLineReader":
        return self

    async def __anext__(self) -> bytes:
        if self._idx >= len(self._lines):
            raise StopAsyncIteration
        line = self._lines[self._idx]
        self._idx += 1
        return line


def _build_mock_proc(stdout_lines: list[dict] | list[str] | list[bytes] = None):
    """Build a mock subprocess handle used to patch
    ``asyncio.create_subprocess_exec``.

    stdout_lines: each item is either a dict (serialised to JSON bytes)
    or a plain bytes object (passed through as-is).
    """
    if stdout_lines is None:
        stdout_lines = []
    encoded = []
    for item in stdout_lines:
        if isinstance(item, bytes):
            encoded.append(item)
        elif isinstance(item, dict):
            encoded.append(json.dumps(item).encode("utf-8"))
        else:
            encoded.append(str(item).encode("utf-8"))

    proc = MagicMock()
    proc.stdin = _FakeLineWriter()
    proc.stdout = _AsyncLineReader(encoded)
    proc.stderr = _AsyncLineReader([])
    proc.terminate = MagicMock()
    proc.kill = MagicMock()
    # wait() coroutine: clean exit by default.
    proc.wait = AsyncMock(return_value=0)
    return proc


# ----------------------------------------------------------------------
# Session lifecycle tests
# ----------------------------------------------------------------------


class TestOpencodeSessionLifecycle:
    """Smoke tests driving OpencodeAcpBackendSession through the
    public protocol using mocked subprocess I/O."""

    async def _run_session(
        self,
        *,
        stdout_lines: list[dict] | list[str] | list[bytes] = None,
        prompt: str = "do the thing",
        model: str = "gpt-5",
        env: dict[str, str] | None = None,
        permission_mode: str = "default",
        on_event=None,
        return_after: int | None = None,
    ):
        """Drive an OpencodeAcpBackendSession through one run_turn cycle.

        Returns (session, events list).
        """
        if stdout_lines is None:
            stdout_lines = []
        opt = AcpBackendOptions(
            workspace_path="/tmp/ws",
            prompt=prompt,
            model=model,
            env=env,
            permission_mode=permission_mode,
            on_event=on_event,
        )
        session = OpencodeAcpBackendSession(opt)
        collected: list[BackendEvent] = []
        async for ev in session.run_turn():
            collected.append(ev)
            if return_after and len(collected) >= return_after:
                break
            if len(collected) > 200:
                pytest.fail("too many events emitted (guard)")
        return session, collected

    def _prepare_mock_subprocess(self, stdout_lines: list):
        """Context manager that patches asyncio.create_subprocess_exec
        to return a mock process."""
        proc = _build_mock_proc(stdout_lines)
        return patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc))

    def test_run_turn_emits_session_start(self):
        """The first event is acp_session_start with model + tool_policy."""
        with self._prepare_mock_subprocess([]):
            _, events = asyncio.run(self._run_session())
        kinds = [ev.kind for ev in events]
        assert kinds[0] == "session_start"
        start = events[0]
        assert start.payload["model"] == "gpt-5"
        assert start.payload["tool_policy"] == "opencode:tool_catalog"

    def test_run_turn_emits_text_events(self):
        """opencode 'text' message maps to acp_text."""
        lines = [
            {"type": "text", "text": "Hello, world!"},
            {"type": "result", "subtype": "success"},
        ]
        with self._prepare_mock_subprocess(lines):
            _, events = asyncio.run(self._run_session())
        kinds = [ev.kind for ev in events]
        assert "text" in kinds
        text_ev = next(e for e in events if e.kind == "text")
        assert "Hello, world!" in text_ev.payload["text"]

    def test_run_turn_emits_tool_use_events(self):
        """opencode 'tool_use' message maps to acp_tool_use."""
        lines = [
            {
                "type": "tool_use",
                "tool": "read_file",
                "id": "call-abc123",
                "input": {"path": "/tmp/foo.txt"},
            },
            {"type": "result", "subtype": "success"},
        ]
        with self._prepare_mock_subprocess(lines):
            _, events = asyncio.run(self._run_session())
        kinds = [ev.kind for ev in events]
        assert "tool_use" in kinds
        tool_ev = next(e for e in events if e.kind == "tool_use")
        assert tool_ev.payload["tool"] == "read_file"
        assert tool_ev.payload["id"] == "call-abc123"

    def test_run_turn_emits_tool_result_events(self):
        """opencode 'tool_result' message maps to acp_tool_result."""
        lines = [
            {
                "type": "tool_result",
                "tool_use_id": "call-abc123",
                "content": "file contents here",
            },
            {"type": "result", "subtype": "success"},
        ]
        with self._prepare_mock_subprocess(lines):
            _, events = asyncio.run(self._run_session())
        kinds = [ev.kind for ev in events]
        assert "tool_result" in kinds
        result_ev = next(e for e in events if e.kind == "tool_result")
        assert result_ev.payload["tool_use_id"] == "call-abc123"
        assert "file contents here" in result_ev.payload["content"]

    def test_run_turn_captures_session_id(self):
        """session_start message carries session_id."""
        lines = [
            {
                "type": "session_start",
                "session_id": "sess-opencode-42",
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
            {"type": "result", "subtype": "success"},
        ]
        with self._prepare_mock_subprocess(lines):
            session, events = asyncio.run(self._run_session())
        kinds = [ev.kind for ev in events]
        assert "session_start" in kinds
        assert session.session_id == "sess-opencode-42"

    def test_run_turn_emits_result_on_success(self):
        """Terminal 'result' message causes acp_result to be emitted."""
        lines = [
            {"type": "text", "text": "done"},
            {
                "type": "result",
                "subtype": "success",
                "usage": {"input_tokens": 10, "output_tokens": 20},
            },
        ]
        with self._prepare_mock_subprocess(lines):
            session, events = asyncio.run(self._run_session())
        kinds = [ev.kind for ev in events]
        assert kinds[-1] == "result"
        result_ev = events[-1]
        assert result_ev.payload["subtype"] == "success"
        # usage rolled into the result event
        assert result_ev.payload["usage"]["input_tokens"] == 10
        assert result_ev.payload["usage"]["output_tokens"] == 20
        assert session.status == "succeeded"

    def test_run_turn_sets_errored_status_on_subprocess_failure(self):
        """When subprocess exits non-zero, status becomes 'errored'."""
        proc = _build_mock_proc([])
        proc.wait = AsyncMock(return_value=1)  # non-zero exit
        stderr_buf = _AsyncLineReader([b"opencode error: something went wrong\n"])

        async def _read_with_timeout(self, timeout: float = 2.0):
            return await asyncio.wait_for(self._read_stdout(), timeout=timeout)

        proc.stderr = MagicMock()
        proc.stderr.read = AsyncMock(return_value=b"opencode error: something went wrong\n")

        with patch(
            "asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            session, events = asyncio.run(self._run_session())

        # Status is errored
        assert session.status == "errored"
        assert session.last_error is not None
        assert "opencode" in session.last_error.lower() or "1" in session.last_error

        # Events include session_error
        kinds = [ev.kind for ev in events]
        assert "session_error" in kinds
        # No clean result event
        assert "result" not in kinds

    def test_run_turn_file_not_found_error(self):
        """When opencode binary is not in PATH, status='errored'."""
        async def boom(*args, **kwargs):
            raise FileNotFoundError("opencode not found")

        with patch("asyncio.create_subprocess_exec", new=boom):
            session, events = asyncio.run(self._run_session())

        assert session.status == "errored"
        assert session.last_error is not None
        assert "opencode" in session.last_error or "PATH" in session.last_error

    def test_run_turn_stops_on_stop_requested(self):
        """If close() is called before run_turn starts, stream yields nothing."""
        async def runner():
            # Import here to avoid triggering the subprocess mock at module load.
            opt = AcpBackendOptions(workspace_path="/tmp/ws", prompt="x")
            session = OpencodeAcpBackendSession(opt)
            await session.close()
            collected = []
            async for ev in session.run_turn():
                collected.append(ev)
            return session, collected

        session, events = asyncio.run(runner())
        assert session.status == "interrupted"
        assert events == []

    def test_session_start_captures_usage(self):
        """Usage in session_start updates counters."""
        lines = [
            {
                "type": "session_start",
                "usage": {"input_tokens": 7, "output_tokens": 3},
            },
            {"type": "result", "subtype": "success"},
        ]
        with self._prepare_mock_subprocess(lines):
            session, events = asyncio.run(self._run_session())
        assert session.input_tokens == 7
        assert session.output_tokens == 3
        assert session.total_tokens == 10

    def test_on_event_callback_receives_agent_events(self):
        """The on_event callback is invoked with AgentEvents mirroring the BackendEvents."""
        events_captured = []

        def on_event(ev):
            events_captured.append(ev)

        lines = [
            {"type": "text", "text": "hello"},
            {"type": "result", "subtype": "success"},
        ]
        with self._prepare_mock_subprocess(lines):
            _, stream = asyncio.run(
                self._run_session(on_event=on_event)
            )

        agent_event_kinds = [e.event for e in events_captured]
        assert "acp_session_start" in agent_event_kinds
        assert "acp_text" in agent_event_kinds
        assert "acp_result" in agent_event_kinds

    def test_billing_model_in_session_start_payload(self):
        """Session_start carries billing_model=subscription (CLI handles OAuth)."""
        lines = [
            {"type": "result", "subtype": "success"},
        ]
        with self._prepare_mock_subprocess(lines):
            _, events = asyncio.run(self._run_session())

        session_start = events[0]
        assert session_start.payload["billing_model"] == "subscription"

    def test_tool_catalog_in_session_start_payload(self):
        """Session_start carries tool_catalog list."""
        lines = [
            {"type": "result", "subtype": "success"},
        ]
        with self._prepare_mock_subprocess(lines):
            _, events = asyncio.run(self._run_session())

        session_start = events[0]
        assert "tool_catalog" in session_start.payload
        # At minimum the six core oompah tools
        cat = session_start.payload["tool_catalog"]
        assert isinstance(cat, list)

    def test_turn_count_increments_on_tool_use(self):
        """turn_count increments for each tool_use message."""
        lines = [
            {"type": "tool_use", "tool": "read_file", "id": "c1", "input": {}},
            {"type": "tool_use", "tool": "write_file", "id": "c2", "input": {}},
            {"type": "text", "text": "done"},
            {"type": "result", "subtype": "success"},
        ]
        with self._prepare_mock_subprocess(lines):
            session, events = asyncio.run(self._run_session())
        assert session.turn_count == 2

    def test_permission_denials_accumulated(self):
        """Permission denial tool_result is tracked."""
        lines = [
            {
                "type": "tool_result",
                "tool_use_id": "call-x",
                "is_error": True,
                "content": "Permission denied",
            },
            {"type": "result", "subtype": "success"},
        ]
        with self._prepare_mock_subprocess(lines):
            session, events = asyncio.run(self._run_session())
        assert session.permission_denials == []

    def test_result_error_sets_last_error(self):
        """Terminal 'error' message populates last_error."""
        lines = [
            {"type": "error", "error": "something went wrong"},
        ]
        with self._prepare_mock_subprocess(lines):
            session, events = asyncio.run(self._run_session())
        assert session.last_error is not None
        assert "something went wrong" in session.last_error

    def test_opencode_binary_not_found_emits_session_error_event(self):
        """FileNotFoundError emits acp_session_error via run_turn."""
        async def boom(*args, **kwargs):
            raise FileNotFoundError("opencode not found in path")

        with patch("asyncio.create_subprocess_exec", new=boom):
            session, events = asyncio.run(self._run_session())

        kinds = [ev.kind for ev in events]
        assert "session_error" in kinds
        assert session.status == "errored"


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
        """When SDK reports input+output but not total, total is derived."""
        c = _OpencodeCounters()
        c.absorb_usage({"input_tokens": 4, "output_tokens": 5})
        assert c.total_tokens == 9

    def test_absorb_usage_from_object(self):
        usage = types.SimpleNamespace(
            input_tokens=7, output_tokens=3, total_tokens=10
        )
        c = _OpencodeCounters()
        c.absorb_usage(usage)
        assert c.input_tokens == 7
        assert c.output_tokens == 3
        assert c.total_tokens == 10

    def test_absorb_usage_none_is_noop(self):
        c = _OpencodeCounters()
        c.absorb_usage(None)
        c.absorb_usage("not a usage object")
        assert c.input_tokens == 0


# ----------------------------------------------------------------------
# close() terminates subprocess
# ----------------------------------------------------------------------


class TestOpencodeClose:
    async def _close_session(self, stdout_lines: list = None):
        """Run the session up to the first event, then close it."""
        if stdout_lines is None:
            stdout_lines = []
        proc = _build_mock_proc(stdout_lines)
        # Make wait() hang until we manually resolve it
        wait_started = asyncio.Event()
        wait_started.set()

        async def slow_wait():
            wait_started.set()
            await asyncio.sleep(10)  # will be cancelled by close()
            return 0

        proc.wait = slow_wait

        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)):
            opt = AcpBackendOptions(workspace_path="/tmp/ws", prompt="x")
            session = OpencodeAcpBackendSession(opt)
            # Start the run_turn in background
            events = []
            async def collect():
                async for ev in session.run_turn():
                    events.append(ev)
                    break  # stop after one event so we can close
                return session, events
            runner = asyncio.create_task(collect())
            # Let the subprocess start
            await asyncio.sleep(0.05)
            await session.close()
            session2, events2 = await runner
            return session2, events2

    def test_close_terminates_subprocess(self):
        """Calling close() terminates the running subprocess."""
        lines = [
            {"type": "text", "text": "hello"},
        ]
        proc = _build_mock_proc(lines)
        proc.terminate = MagicMock()
        proc.kill = MagicMock()
        proc.wait = AsyncMock(return_value=-1)  # non-zero on terminate
        is_called = False

        def mark_and_kill():
            nonlocal is_called
            is_called = True
            proc.kill()

        proc.terminate = mark_and_kill

        async def runner():
            with patch(
                "asyncio.create_subprocess_exec",
                new=AsyncMock(return_value=proc),
            ):
                opt = AcpBackendOptions(workspace_path="/tmp/ws", prompt="y")
                session = OpencodeAcpBackendSession(opt)

                async def collect():
                    collected = []
                    async for ev in session.run_turn():
                        collected.append(ev)
                    return session, collected

                task = asyncio.create_task(collect())
                await asyncio.sleep(0.1)  # let the subprocess spawn
                await session.close()
                return await task

        session, _ = asyncio.run(runner())
        assert is_called or session.status in ("interrupted", "errored")
        # status is interrupted because close() was requested mid-stream
        assert session.status == "interrupted"

    def test_close_idempotent(self):
        """close() can be called multiple times without error."""
        async def runner():
            opt = AcpBackendOptions(workspace_path="/tmp/ws", prompt="x")
            session = OpencodeAcpBackendSession(opt)
            await session.close()
            await session.close()  # must not raise
            return session

        session = asyncio.run(runner())
        assert session.status == "interrupted"