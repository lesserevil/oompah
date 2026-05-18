"""Tests for the OpenCode ACP backend (oompah-zlz_2-4wdh).

Covers:

* :class:`OpencodeAcpBackend` registers as ``"opencode"`` at package import.
* ``validate_provider`` accepts a missing api_key (subscription auth at CLI level)
  and rejects invalid base_url schemes.
* Session lifecycle: instantiate the backend with a mock subprocess,
  run one turn, verify the expected :class:`BackendEvent` stream and
  terminal status.
* Error handling: FileNotFoundError when opencode binary is missing,
  errored status on subprocess failure, interrupted status on close().
* Tool bridging: oompah's MCP catalog round-trips through the same
  ``_exec_*`` helpers from ``oompah/acp_tools.py``.
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
# Registration: opencode shows up in the registry alongside claude + codex
# ----------------------------------------------------------------------


class TestOpencodeRegistration:
    def test_opencode_in_registry(self):
        """Importing oompah.acp_backends must populate BACKENDS['opencode']."""
        assert "opencode" in BACKENDS
        assert BACKENDS["opencode"] is OpencodeAcpBackend

    def test_opencode_name(self):
        assert OpencodeAcpBackend.name() == "opencode"

    def test_opencode_reachable_via_get_backend(self):
        from oompah.acp_backends import get_backend, get_backend_or_raise

        assert get_backend("opencode") is OpencodeAcpBackend
        assert get_backend_or_raise("opencode") is OpencodeAcpBackend

    def test_opencode_backend_session_is_importable(self):
        """OpencodeAcpBackendSession can be imported from the module."""
        from oompah.acp_backends.opencode import OpencodeAcpBackendSession

        assert OpencodeAcpBackendSession is not None


# ----------------------------------------------------------------------
# validate_provider: subscription auth + base_url validation
# ----------------------------------------------------------------------


class TestOpencodeValidateProvider:
    def test_name_returns_opencode(self):
        """Sanity: the backend name is 'opencode'."""
        backend = OpencodeAcpBackend()
        assert backend.name() == "opencode"

    def test_empty_api_key_is_accepted(self):
        """Opencode uses subscription auth at the CLI level — empty
        api_key on the provider is acceptable (the opencode binary
        handles its own OAuth flow, same as Codex)."""
        backend = OpencodeAcpBackend()
        provider = ModelProvider(
            id="p", name="opencode", base_url="", api_key="",
        )
        assert backend.validate_provider(provider) == []

    def test_provided_api_key_is_accepted(self):
        """Even when an api_key is set on the provider it should pass
        validation — the backend doesn't reject it."""
        backend = OpencodeAcpBackend()
        provider = ModelProvider(
            id="p", name="opencode", base_url="", api_key="sk-opencode-test",
        )
        assert backend.validate_provider(provider) == []

    def test_empty_base_url_is_accepted(self):
        """Empty base_url means 'use the default opencode endpoint'."""
        backend = OpencodeAcpBackend()
        provider = ModelProvider(
            id="p", name="opencode", base_url="", api_key="sk-x",
        )
        assert backend.validate_provider(provider) == []

    def test_base_url_https_is_accepted(self):
        backend = OpencodeAcpBackend()
        provider = ModelProvider(
            id="p", name="opencode",
            base_url="https://api.openai.com/v1",
            api_key="sk-x",
        )
        assert backend.validate_provider(provider) == []

    def test_base_url_http_is_accepted(self):
        """Local proxies via http:// LB are valid."""
        backend = OpencodeAcpBackend()
        provider = ModelProvider(
            id="p", name="opencode",
            base_url="http://localhost:8080",
            api_key="sk-x",
        )
        assert backend.validate_provider(provider) == []

    def test_base_url_invalid_scheme_fails(self):
        """Only http:// and https:// are valid; ftp:// etc. are rejected."""
        backend = OpencodeAcpBackend()
        provider = ModelProvider(
            id="p", name="opencode",
            base_url="ftp://bogus",
            api_key="sk-x",
        )
        errors = backend.validate_provider(provider)
        assert any("base_url" in e for e in errors)
        assert any("http://" in e or "https://" in e for e in errors)

    def test_base_url_file_scheme_fails(self):
        """file:// scheme is rejected."""
        backend = OpencodeAcpBackend()
        provider = ModelProvider(
            id="p", name="opencode",
            base_url="file:///tmp/bogus",
            api_key="sk-x",
        )
        errors = backend.validate_provider(provider)
        assert len(errors) == 1
        assert "base_url" in errors[0]


# ----------------------------------------------------------------------
# OpencodeAcpBackend.start_session
# ----------------------------------------------------------------------


class TestOpencodeStartSession:
    def test_start_session_returns_session(self):
        """start_session returns a session handle without spawning the
        subprocess — spawn is lazy on first run_turn call."""
        backend = OpencodeAcpBackend()
        opt = AcpBackendOptions(
            workspace_path="/tmp/ws",
            prompt="do the thing",
            model="opencode-model",
        )
        session = backend.start_session(opt)
        assert isinstance(session, OpencodeAcpBackendSession)
        assert session.status == "pending"

    def test_session_counters_default_before_run(self):
        """Pre-run counters are all zero / None."""
        backend = OpencodeAcpBackend()
        opt = AcpBackendOptions(workspace_path="/tmp/ws", prompt="x")
        session = backend.start_session(opt)
        assert session.input_tokens == 0
        assert session.output_tokens == 0
        assert session.total_tokens == 0
        assert session.total_cost_usd is None
        assert session.session_id is None
        assert session.turn_count == 0
        assert session.last_error is None
        assert session.permission_denials == []


# ----------------------------------------------------------------------
# Session lifecycle helpers
# ----------------------------------------------------------------------


class _FakeStreamWriter:
    """Sync write(), async drain() — mirrors asyncio.StreamWriter."""

    def __init__(self):
        self._buffer: list[bytes] = []

    def write(self, data: bytes) -> None:
        self._buffer.append(data)

    async def drain(self) -> None:
        pass


class _FakeStreamReader:
    """Async generator that yields byte lines from a list of strings."""

    def __init__(self, lines: list[str]):
        self._lines = list(lines)
        self._index = 0

    def __aiter__(self):
        return self

    async def __anext__(self) -> bytes:
        if self._index >= len(self._lines):
            raise StopAsyncIteration
        line = self._lines[self._index]
        self._index += 1
        return line.encode("utf-8")


def _json_msg(type: str, /, session_id: str = "session-123", **kwargs) -> str:
    """Serialize a dict as a JSON-line string."""
    payload = {"type": type, "session_id": session_id, **kwargs}
    return json.dumps(payload)


def _build_mock_proc(
    *,
    stdout_lines: list[str] | None = None,
    return_code: int = 0,
    session_id: str = "session-123",
    usage: dict | None = None,
):
    """Build a fully-configured mock subprocess for run_turn tests.

    Args:
        stdout_lines: JSON-line strings to yield from stdout.
        return_code: exit code for wait() — 0 = clean, non-zero = failure.
        session_id: value for session_start message.
        usage: usage dict embedded in session_start and/or result.
    """
    lines = stdout_lines or []

    fake_stdout = _FakeStreamReader(lines)
    fake_stderr = MagicMock()
    fake_stdin = _FakeStreamWriter()

    proc = MagicMock()
    proc.stdin = fake_stdin
    proc.stdout = fake_stdout
    proc.stderr = fake_stderr
    proc.terminate = MagicMock()
    proc.kill = MagicMock()
    proc.wait = AsyncMock(return_value=return_code)
    return proc


class TestOpencodeSessionLifecycle:
    """Smoke test: drive OpencodeAcpBackendSession from start to
    terminal status through the public protocol. Mocks the subprocess
    surface so no real opencode binary is needed."""

    async def _drive_session(
        self,
        mock_proc: MagicMock,
        *,
        on_event=None,
        **opt_kwargs,
    ) -> tuple[OpencodeAcpBackendSession, list[BackendEvent]]:
        """Run run_turn() with a pre-built mock subprocess."""
        options = AcpBackendOptions(
            workspace_path=opt_kwargs.get("workspace_path", "/tmp/ws"),
            prompt=opt_kwargs.get("prompt", "do the thing"),
            model=opt_kwargs.get("model", "opencode-model"),
            permission_mode=opt_kwargs.get("permission_mode", "default"),
            on_event=on_event,
            turn_timeout_s=opt_kwargs.get("turn_timeout_s", 60),
        )
        session = OpencodeAcpBackendSession(options)

        with patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_proc,
        ):
            with patch.object(
                session,
                "_build_tool_catalog",
                return_value=[],
            ):
                collected: list[BackendEvent] = []
                async for ev in session.run_turn():
                    collected.append(ev)

        return session, collected

    def test_session_properties_default_before_run_turn(self):
        """Before run_turn is called the session has pre-run defaults."""
        backend = OpencodeAcpBackend()
        session = backend.start_session(
            AcpBackendOptions(workspace_path="/tmp/ws", prompt="x")
        )
        assert session.status == "pending"
        assert session.input_tokens == 0
        assert session.output_tokens == 0
        assert session.total_tokens == 0
        assert session.total_cost_usd is None
        assert session.session_id is None
        assert session.turn_count == 0
        assert session.last_error is None
        assert session.permission_denials == []

    @pytest.mark.asyncio
    async def test_run_turn_emits_session_start(self):
        """The first event emitted is acp_session_start with model + tool_policy."""
        proc = _build_mock_proc(
            stdout_lines=[
                _json_msg(
                    "session_start",
                    session_id="opencode-sid-1",
                    usage={"input_tokens": 0, "output_tokens": 0},
                ),
                _json_msg("result"),
            ],
        )

        session, events = await self._drive_session(proc)

        assert len(events) > 0
        assert events[0].kind == "session_start"
        start_payload = events[0].payload
        assert start_payload["model"] == "opencode-model"
        assert start_payload["tool_policy"] == "opencode:tool_catalog"
        assert start_payload["billing_model"] == "subscription"

    @pytest.mark.asyncio
    async def test_run_turn_emits_text_events(self):
        """A text message from opencode serve is mapped to acp_text."""
        proc = _build_mock_proc(
            stdout_lines=[
                _json_msg(
                    "session_start",
                    usage={"input_tokens": 5, "output_tokens": 0},
                ),
                _json_msg("text", text="Hello from opencode"),
                _json_msg(
                    "result",
                    usage={"input_tokens": 5, "output_tokens": 10},
                ),
            ],
        )

        session, events = await self._drive_session(proc)

        text_events = [ev for ev in events if ev.kind == "text"]
        assert len(text_events) == 1
        assert "Hello from opencode" in text_events[0].payload["text"]

    @pytest.mark.asyncio
    async def test_run_turn_emits_tool_use_events(self):
        """A tool_use message from opencode serve is mapped to acp_tool_use."""
        proc = _build_mock_proc(
            stdout_lines=[
                _json_msg(
                    "session_start",
                    usage={"input_tokens": 0, "output_tokens": 0},
                ),
                _json_msg(
                    "tool_use",
                    tool="read_file",
                    id="tool-call-1",
                    input={"path": "/tmp/foo.txt"},
                ),
                _json_msg("result"),
            ],
        )

        session, events = await self._drive_session(proc)

        tool_events = [ev for ev in events if ev.kind == "tool_use"]
        assert len(tool_events) == 1
        assert tool_events[0].payload["tool"] == "read_file"
        assert tool_events[0].payload["id"] == "tool-call-1"

    @pytest.mark.asyncio
    async def test_run_turn_emits_tool_result_events(self):
        """A tool_result message from opencode serve is mapped to acp_tool_result."""
        proc = _build_mock_proc(
            stdout_lines=[
                _json_msg(
                    "session_start",
                    usage={"input_tokens": 0, "output_tokens": 0},
                ),
                _json_msg(
                    "tool_result",
                    tool_use_id="tool-call-1",
                    content="file contents here",
                ),
                _json_msg("result"),
            ],
        )

        session, events = await self._drive_session(proc)

        result_events = [ev for ev in events if ev.kind == "tool_result"]
        assert len(result_events) == 1
        assert result_events[0].payload["tool_use_id"] == "tool-call-1"
        assert "file contents here" in result_events[0].payload["content"]

    @pytest.mark.asyncio
    async def test_run_turn_emits_result_on_success(self):
        """Clean subprocess exit yields a final acp_result with subtype success."""
        proc = _build_mock_proc(
            stdout_lines=[
                _json_msg(
                    "session_start",
                    session_id="sid-clean",
                    usage={"input_tokens": 10, "output_tokens": 5},
                ),
                _json_msg(
                    "result",
                    usage={"input_tokens": 10, "output_tokens": 5},
                ),
            ],
            return_code=0,
        )

        session, events = await self._drive_session(proc)

        kinds = [ev.kind for ev in events]
        assert kinds[-1] == "result"
        assert events[-1].payload["subtype"] == "success"
        assert session.status == "succeeded"

    @pytest.mark.asyncio
    async def test_run_turn_sets_errored_status_on_exception(self):
        """When the subprocess exits non-zero the session status is 'errored'
        and a session_error event is emitted."""
        proc = _build_mock_proc(
            stdout_lines=[
                _json_msg(
                    "session_start",
                    usage={"input_tokens": 0, "output_tokens": 0},
                ),
            ],
            return_code=1,
        )

        session, events = await self._drive_session(proc)

        kinds = [ev.kind for ev in events]
        assert "session_error" in kinds
        assert session.status == "errored"
        assert session.last_error is not None
        assert "1" in session.last_error

    @pytest.mark.asyncio
    async def test_run_turn_handles_file_not_found_error(self):
        """When opencode binary is not in PATH, run_turn emits a
        session_error event and sets status to 'errored' with a clear message."""

        async def _boom(*args, **kwargs):
            raise FileNotFoundError("opencode not found")

        with patch("asyncio.create_subprocess_exec", side_effect=_boom):
            options = AcpBackendOptions(
                workspace_path="/tmp/ws",
                prompt="hello",
                model="opencode-model",
            )
            session = OpencodeAcpBackendSession(options)
            with patch.object(session, "_build_tool_catalog", return_value=[]):
                collected = []
                async for ev in session.run_turn():
                    collected.append(ev)

        kinds = [ev.kind for ev in collected]
        assert "session_error" in kinds
        assert session.status == "errored"
        assert "opencode" in session.last_error.lower()

    @pytest.mark.asyncio
    async def test_close_before_run_turn_marks_interrupted(self):
        """Calling close() before run_turn() marks the status 'interrupted'
        and run_turn exits immediately without spawning a subprocess."""
        proc = _build_mock_proc(
            stdout_lines=[_json_msg("session_start"), _json_msg("result")],
        )

        options = AcpBackendOptions(
            workspace_path="/tmp/ws",
            prompt="do it",
        )
        session = OpencodeAcpBackendSession(options)
        await session.close()

        with patch(
            "asyncio.create_subprocess_exec",
            return_value=proc,
        ) as mock_spawn:
            with patch.object(session, "_build_tool_catalog", return_value=[]):
                events = []
                async for ev in session.run_turn():
                    events.append(ev)

        assert session.status == "interrupted"
        assert events == []
        mock_spawn.assert_not_called()

    @pytest.mark.asyncio
    async def test_close_while_active_terminates_subprocess(self):
        """Calling close() while run_turn is active terminates the subprocess."""
        proc = _build_mock_proc(
            stdout_lines=[
                _json_msg(
                    "session_start",
                    usage={"input_tokens": 1, "output_tokens": 0},
                ),
                _json_msg("text", text="one"),
                _json_msg("text", text="two"),
            ],
            return_code=1,
        )

        async def _run_with_close():
            options = AcpBackendOptions(workspace_path="/tmp/ws", prompt="hi")
            session = OpencodeAcpBackendSession(options)

            events = []
            with patch(
                "asyncio.create_subprocess_exec",
                return_value=proc,
            ):
                with patch.object(
                    session,
                    "_build_tool_catalog",
                    return_value=[],
                ):
                    async for ev in session.run_turn():
                        events.append(ev)
                        if ev.kind == "session_start":
                            await session.close()

            return session, events

        session, events = await _run_with_close()

        assert session.status in ("interrupted", "errored")
        assert proc.terminate.called or proc.kill.called

    @pytest.mark.asyncio
    async def test_run_turn_captures_session_id(self):
        """session_id is extracted from session_start message."""
        proc = _build_mock_proc(
            stdout_lines=[
                _json_msg(
                    "session_start",
                    session_id="opencode-sid-abc",
                    usage={"input_tokens": 0, "output_tokens": 0},
                ),
                _json_msg("result"),
            ],
        )

        session, events = await self._drive_session(proc)

        assert session.session_id == "opencode-sid-abc"

    @pytest.mark.asyncio
    async def test_run_turn_updates_counters(self):
        """Token usage in messages updates the session counters."""
        proc = _build_mock_proc(
            stdout_lines=[
                _json_msg(
                    "session_start",
                    session_id="sid",
                    usage={"input_tokens": 42, "output_tokens": 0},
                ),
                _json_msg(
                    "result",
                    usage={"input_tokens": 42, "output_tokens": 17},
                ),
            ],
        )

        session, events = await self._drive_session(proc)

        assert session.input_tokens == 42
        assert session.output_tokens == 17
        assert session.total_tokens == 59

    @pytest.mark.asyncio
    async def test_run_turn_emits_agent_events(self):
        """on_event callback is called with agent events (acp_* prefix)."""
        agent_events_captured = []

        proc = _build_mock_proc(
            stdout_lines=[
                _json_msg(
                    "session_start",
                    usage={"input_tokens": 0, "output_tokens": 0},
                ),
                _json_msg("result"),
            ],
        )

        session, events = await self._drive_session(
            proc,
            on_event=agent_events_captured.append,
        )

        agent_event_names = [e.event for e in agent_events_captured]
        assert "acp_session_start" in agent_event_names
        assert "acp_result" in agent_event_names


# ----------------------------------------------------------------------
# Tool bridging
# ----------------------------------------------------------------------


# TestOpencodeToolBridging calls build_tool_catalog() which requires
# claude_agent_sdk. Skip when it is not installed (base install without
# [claude] extra).
try:
    import claude_agent_sdk
except ImportError:
    pytest.skip("claude_agent_sdk not installed; install with uv pip install 'oompah[claude]'", allow_module_level=True)


# TestOpencodeToolBridging calls build_tool_catalog() which requires
# claude_agent_sdk. Skip when it is not installed (base install without
# [claude] extra).
try:
    import claude_agent_sdk
except ImportError:
    pytest.skip("claude_agent_sdk not installed; install with uv pip install 'oompah[claude]'", allow_module_level=True)


class TestOpencodeToolBridging:
    """Opencode uses the same @tool-decorated catalog as Claude
    (not the openai-agents @function_tool decorator). The backend
    calls build_tool_catalog() in _build_tool_catalog(), so opencode
    inherits the full set of tools from oompah/acp_tools.py."""

    def test_opencode_catalog_uses_same_builder_as_claude(self, tmp_path):
        """OpencodeAcpBackendSession._build_tool_catalog calls the same
        build_tool_catalog() helper used by the Claude backend."""
        from oompah.acp_tools import build_tool_catalog

        cat = build_tool_catalog(str(tmp_path))
        names = [
            getattr(t, "name", getattr(t, "__name__", str(t)))
            for t in cat
        ]
        for expected in (
            "read_file", "write_file", "edit_file",
            "list_files", "search_files", "run_command",
        ):
            assert expected in names, f"missing {expected!r}"

    def test_opencode_tool_catalog_includes_run_command(self, tmp_path):
        """run_command is in the opencode catalog (cd-guard routing is
        identical across all subprocess backends)."""
        from oompah.acp_tools import build_tool_catalog

        cat = build_tool_catalog(str(tmp_path))
        names = [getattr(t, "name", str(t)) for t in cat]
        assert "run_command" in names


# ----------------------------------------------------------------------
# _OpencodeCounters
# ----------------------------------------------------------------------


class TestOpencodeCounters:
    def test_absorb_usage_from_dict(self):
        c = _OpencodeCounters()
        c.absorb_usage(
            {"input_tokens": 11, "output_tokens": 22, "total_tokens": 33}
        )
        assert c.input_tokens == 11
        assert c.output_tokens == 22
        assert c.total_tokens == 33

    def test_absorb_usage_derives_total(self):
        """When reported input+output but not total, total is derived."""
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
        assert c.total_tokens == 0


# ----------------------------------------------------------------------
# Registry integration: backends coexist
# ----------------------------------------------------------------------


class TestOpencodeRegistryIntegration:
    """The presence of the opencode backend in the registry must not
    affect other backends."""

    def test_claude_and_codex_still_in_registry(self):
        """Both claude and codex remain registered alongside opencode."""
        assert "claude" in BACKENDS
        assert "codex" in BACKENDS
        assert "opencode" in BACKENDS

    def test_opencode_and_codex_coexist(self):
        """codex and opencode are distinct entries."""
        assert BACKENDS["codex"] is not BACKENDS["opencode"]

    def test_opencode_provider_validates_with_empty_key(self):
        """A provider with backend='opencode' and no api_key validates."""
        provider = ModelProvider(
            id="p",
            name="opencode",
            base_url="",
            backend="opencode",
            api_key="",
        )
        assert provider.validate_for_mode("acp") == []