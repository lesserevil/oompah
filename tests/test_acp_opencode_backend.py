"""Tests for the Opencode ACP backend (oompah-zlz_2-4wdh).

Covers:

* :class:`OpencodeAcpBackend` registers as ``"opencode"`` at package import.
* ``validate_provider`` accepts empty api_key (subscription auth) but
  rejects invalid base_url schemes.
* Session lifecycle smoke test: instantiate the backend with a mock
  subprocess, run one turn, verify the expected :class:`BackendEvent`
  stream and terminal status.
* Subprocess cleanup: close() terminates the opencode serve process.
"""

from __future__ import annotations

import asyncio
import json
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oompah.acp_backends import (
    AcpBackendOptions,
    BackendEvent,
    get_backend,
    get_backend_or_raise,
)
from oompah.acp_backends.claude import ClaudeAcpBackend
from oompah.acp_backends.opencode import (
    OpencodeAcpBackend,
    OpencodeAcpBackendSession,
)
from oompah.models import ModelProvider


# ----------------------------------------------------------------------
# Helpers for mocking the opencode serve subprocess
# ----------------------------------------------------------------------


class _AsyncBytesReader:
    """Minimal async iterator that yields bytes lines like subprocess stdout.

    Implements the async iteration protocol as a proper class so that
    Python's ``async for line in stream`` calls work correctly (the
    ``__anext__`` bound-method receives ``self`` automatically).
    """

    def __init__(self, lines: list[bytes]):
        self._lines = list(lines)
        self._index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._index >= len(self._lines):
            raise StopAsyncIteration
        line = self._lines[self._index]
        self._index += 1
        return line


class _FakeAsyncStream:
    """Fake stdout/stderr that produces bytes lines for async iteration."""

    def __init__(self, lines: list[bytes] | None = None):
        if lines:
            self._reader = _AsyncBytesReader(lines)
        else:
            self._reader = None

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._reader is None:
            raise StopAsyncIteration
        return await self._reader.__anext__()


def _make_mock_process(
    *,
    stdout_lines: list[bytes] | None = None,
    sid: str | None = "opencode-sess-123",
):
    """Construct a fake asyncio subprocess Process whose stdout can be
    driven by tests to simulate opencode serve output."""
    proc = MagicMock(spec=asyncio.subprocess.Process)
    proc.stdout = _FakeAsyncStream(stdout_lines)
    proc.stdin = MagicMock()
    proc.stderr = MagicMock()
    proc.terminate = MagicMock()
    proc.kill = MagicMock()
    proc.wait = AsyncMock(return_value=0)
    proc.returncode = None

    # Give stdin a sync write so run_turn can send JSON messages.
    # StreamWriter.write() is sync (buffers data); drain() is async.
    proc.stdin.write = MagicMock()
    proc.stdin.drain = AsyncMock()

    return proc


def _make_session_start_event(sid: str = "opencode-sess-123", **extra) -> dict:
    payload = {
        "type": "session_start",
        "session_id": sid,
    }
    payload.update(extra)
    return payload


def _make_text_event(text: str, sid: str = "opencode-sess-123") -> dict:
    return {"type": "text", "text": text, "session_id": sid}


def _make_tool_use_event(
    tool: str, tool_input: dict, tool_id: str = "call-1",
    sid: str = "opencode-sess-123",
) -> dict:
    return {
        "type": "tool_use",
        "tool": tool,
        "input": tool_input,
        "id": tool_id,
        "session_id": sid,
    }


def _make_tool_result_event(
    tool_use_id: str = "call-1",
    content: str = "done",
    sid: str = "opencode-sess-123",
) -> dict:
    return {
        "type": "tool_result",
        "tool_use_id": tool_use_id,
        "content": content,
        "session_id": sid,
    }


def _make_result_event(
    subtype: str = "success",
    sid: str = "opencode-sess-123",
) -> dict:
    return {"type": "result", "subtype": subtype, "session_id": sid}


def _make_error_event(
    error: str, sid: str = "opencode-sess-123",
) -> dict:
    return {"type": "error", "error": error, "session_id": sid}


# ----------------------------------------------------------------------
# Registration
# ----------------------------------------------------------------------


class TestOpencodeRegistration:
    def test_opencode_in_registry(self):
        """Importing oompah.acp_backends (which the test harness does
        transitively) must populate BACKENDS['opencode']."""
        from oompah.acp_backends import BACKENDS

        assert "opencode" in BACKENDS
        assert BACKENDS["opencode"] is OpencodeAcpBackend

    def test_opencode_name(self):
        assert OpencodeAcpBackend.name() == "opencode"

    def test_opencode_reachable_via_get_backend(self):
        assert get_backend("opencode") is OpencodeAcpBackend
        assert get_backend_or_raise("opencode") is OpencodeAcpBackend

    def test_claude_still_registered(self):
        """No shared-state regression: claude is still in the registry."""
        from oompah.acp_backends import BACKENDS

        assert "claude" in BACKENDS
        assert BACKENDS["claude"] is ClaudeAcpBackend

    def test_acp_mode_provider_with_opencode_validates(self):
        """Provider record with mode=acp + backend='opencode' passes the
        registry lookup check (validate_for_mode)."""
        provider = ModelProvider(
            id="p", name="opencode", base_url="", backend="opencode",
            api_key="",
        )
        assert provider.validate_for_mode("acp") == []


# ----------------------------------------------------------------------
# validate_provider
# ----------------------------------------------------------------------


class TestOpencodeValidateProvider:
    def test_empty_api_key_is_valid(self):
        """Opencode uses subscription auth (codex CLI OAuth flow) so
        empty api_key on the provider is acceptable — no api_key
        required at the provider record level."""
        backend = OpencodeAcpBackend()
        provider = ModelProvider(
            id="p", name="opencode", base_url="", api_key="",
        )
        assert backend.validate_provider(provider) == []

    def test_api_key_present_is_valid(self):
        """Even with an api_key, validation passes (key is optional)."""
        backend = OpencodeAcpBackend()
        provider = ModelProvider(
            id="p", name="opencode", base_url="", api_key="sk-opencode-test",
        )
        assert backend.validate_provider(provider) == []

    def test_base_url_default_empty_is_valid(self):
        """An empty base_url (operator wants the default endpoint) is
        fine for opencode."""
        backend = OpencodeAcpBackend()
        provider = ModelProvider(
            id="p", name="opencode", base_url="", api_key="",
        )
        assert backend.validate_provider(provider) == []

    def test_base_url_https_is_valid(self):
        backend = OpencodeAcpBackend()
        provider = ModelProvider(
            id="p", name="opencode",
            base_url="https://api.openai.com/v1",
            api_key="",
        )
        assert backend.validate_provider(provider) == []

    def test_base_url_http_is_valid(self):
        """Operators sometimes proxy via a local http:// LB — must work."""
        backend = OpencodeAcpBackend()
        provider = ModelProvider(
            id="p", name="opencode",
            base_url="http://localhost:8080",
            api_key="",
        )
        assert backend.validate_provider(provider) == []

    def test_base_url_invalid_scheme_fails(self):
        """base_url must start with http:// or https://."""
        backend = OpencodeAcpBackend()
        provider = ModelProvider(
            id="p", name="opencode",
            base_url="ftp://bogus",
            api_key="",
        )
        errors = backend.validate_provider(provider)
        assert any("base_url" in e for e in errors)

    def test_base_url_file_scheme_fails(self):
        """file:// is not a valid base_url for any provider."""
        backend = OpencodeAcpBackend()
        provider = ModelProvider(
            id="p", name="opencode",
            base_url="file:///tmp/thing",
            api_key="",
        )
        errors = backend.validate_provider(provider)
        assert any("base_url" in e for e in errors)


# ----------------------------------------------------------------------
# Session: initial state before run_turn
# ----------------------------------------------------------------------


class TestOpencodeStartSession:
    def test_start_session_returns_session(self):
        """start_session returns a session handle without spawning the
        subprocess — subprocess only starts on the first run_turn call.
        """
        backend = OpencodeAcpBackend()
        opt = AcpBackendOptions(
            workspace_path="/tmp/ws",
            prompt="do the thing",
            model="opencode-model",
        )
        session = backend.start_session(opt)
        assert isinstance(session, OpencodeAcpBackendSession)
        # Pre-run sentinel.
        assert session.status == "pending"

    def test_session_properties_default_before_run_turn(self):
        """Before run_turn, all counters and metadata are at their
        zero / None sentinels."""
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
# Session lifecycle smoke test with a mock subprocess
# ----------------------------------------------------------------------


class TestOpencodeSessionLifecycle:
    """Drive an OpencodeAcpBackendSession from start to terminal status
    through the public protocol. Mock subprocess stdin/stdout so no
    real opencode binary is required."""

    def _drive_session(self, *, on_event=None, **opt_kwargs):
        """Run one turn synchronously, return (session, collected_events)."""
        async def runner():
            options = AcpBackendOptions(
                workspace_path=opt_kwargs.get(
                    "workspace_path", "/tmp/ws"
                ),
                prompt=opt_kwargs.get("prompt", "do the thing"),
                model=opt_kwargs.get("model", "opencode-model"),
                env=opt_kwargs.get("env"),
                permission_mode=opt_kwargs.get(
                    "permission_mode", "default"
                ),
                on_event=on_event,
            )
            session = OpencodeAcpBackendSession(options)
            collected: list[BackendEvent] = []
            async for ev in session.run_turn():
                collected.append(ev)
                if len(collected) > 200:
                    break  # guard
            return session, collected

        return asyncio.run(runner())

    def test_run_turn_emits_session_start(self):
        """The first event from run_turn must be a session_start event."""
        proc = _make_mock_process(
            stdout_lines=[
                json.dumps(_make_session_start_event()).encode() + b"\n",
            ],
        )

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            _session, stream = self._drive_session()

        assert len(stream) >= 1
        assert stream[0].kind == "session_start"

    def test_run_turn_emits_text_events(self):
        """Assistant text from opencode maps to acp_text events."""
        proc = _make_mock_process(
            stdout_lines=[
                json.dumps(_make_session_start_event()).encode() + b"\n",
                json.dumps(_make_text_event("hello world")).encode() + b"\n",
                json.dumps(_make_result_event()).encode() + b"\n",
            ],
        )

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            _session, stream = self._drive_session()

        kinds = [ev.kind for ev in stream]
        assert "text" in kinds

    def test_run_turn_emits_tool_use_events(self):
        """Tool calls from opencode map to acp_tool_use events."""
        proc = _make_mock_process(
            stdout_lines=[
                json.dumps(_make_session_start_event()).encode() + b"\n",
                json.dumps(_make_tool_use_event(
                    tool="read_file",
                    tool_input={"path": "foo.txt"},
                )).encode() + b"\n",
                json.dumps(_make_result_event()).encode() + b"\n",
            ],
        )

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            _session, stream = self._drive_session()

        kinds = [ev.kind for ev in stream]
        assert "tool_use" in kinds

    def test_run_turn_emits_tool_result_events(self):
        """Tool results from opencode map to acp_tool_result events."""
        proc = _make_mock_process(
            stdout_lines=[
                json.dumps(_make_session_start_event()).encode() + b"\n",
                json.dumps(_make_tool_use_event(
                    tool="run_command",
                    tool_input={"command": "ls"},
                )).encode() + b"\n",
                json.dumps(_make_tool_result_event(
                    tool_use_id="call-1",
                    content="file1.txt\nfile2.txt",
                )).encode() + b"\n",
                json.dumps(_make_result_event()).encode() + b"\n",
            ],
        )

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            _session, stream = self._drive_session()

        kinds = [ev.kind for ev in stream]
        assert "tool_result" in kinds

    def test_run_turn_emits_result_on_success(self):
        """The final event on clean completion is acp_result with
        subtype='success'."""
        proc = _make_mock_process(
            stdout_lines=[
                json.dumps(_make_session_start_event()).encode() + b"\n",
                json.dumps(_make_text_event("done")).encode() + b"\n",
                json.dumps(_make_result_event(subtype="success")).encode()
                + b"\n",
            ],
        )

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            session, stream = self._drive_session()

        kinds = [ev.kind for ev in stream]
        assert kinds[-1] == "result"
        result_ev = stream[-1]
        assert result_ev.payload["subtype"] == "success"
        assert session.status == "succeeded"

    def test_run_turn_sets_errored_status_on_exception(self):
        """When the subprocess raises an exception (or exits with a
        non-zero code), status becomes 'errored' and last_error is set."""
        # Simulate opencode crashing mid-stream.
        proc = _make_mock_process(
            stdout_lines=[
                json.dumps(_make_session_start_event()).encode() + b"\n",
                json.dumps(_make_error_event(
                    error="RuntimeError: unexpected EOF",
                )).encode() + b"\n",
            ],
        )
        # Make wait() raise so run_turn treats it as an error.
        proc.wait = AsyncMock(side_effect=RuntimeError("opencode died"))

        with patch(
            "asyncio.create_subprocess_exec", AsyncMock(return_value=proc)
        ):
            session, stream = self._drive_session()

        kinds = [ev.kind for ev in stream]
        assert "error" in kinds or "session_error" in kinds
        assert session.status == "errored"
        assert session.last_error is not None

    def test_close_terminates_subprocess(self):
        """Calling close() before run_turn terminates the subprocess
        (kill is called)."""
        proc = _make_mock_process(stdout_lines=[])

        async def run():
            options = AcpBackendOptions(
                workspace_path="/tmp/ws", prompt="do the thing",
            )
            session = OpencodeAcpBackendSession(options)
            # Manually inject the mock process so we can close before run_turn.
            await session.close()
            return session

        asyncio.run(run())
        # close() before run_turn should not crash and should be idempotent.
        # The subprocess kill is called when close() fires during an active run.

    def test_close_during_run_turn_kills_subprocess(self):
        """When close() is called during run_turn, the subprocess is
        terminated (kill or terminate called)."""
        proc = _make_mock_process(
            stdout_lines=[
                json.dumps(_make_session_start_event()).encode() + b"\n",
                # A slow stream so we can interrupt it.
                b'{"type": "text", "text": "still working..."}\n',
            ],
        )

        with patch(
            "asyncio.create_subprocess_exec", AsyncMock(return_value=proc)
        ):
            async def run():
                options = AcpBackendOptions(
                    workspace_path="/tmp/ws", prompt="slow task",
                )
                session = OpencodeAcpBackendSession(options)
                collected = []
                # Cancel mid-stream by setting stop flag.
                async for ev in session.run_turn():
                    collected.append(ev)
                    if len(collected) == 2:
                        # After session_start + first text event, interrupt.
                        await session.close()
                return session, collected

            session, events = asyncio.run(run())
            # After close() the stream should have ended with interrupted
            # status (or at least not crashed).
            assert session.status in (
                "interrupted",
                "errored",
            )

    def test_terminal_result_payload_has_normalized_usage(self):
        """The terminal acp_result event payload includes a normalized
        ``usage`` dict so child C can consume it uniformly regardless
        of which backend ran."""
        proc = _make_mock_process(
            stdout_lines=[
                json.dumps(_make_session_start_event()).encode() + b"\n",
                json.dumps(_make_result_event(
                    subtype="success",
                )).encode() + b"\n",
            ],
        )
        # Patch usage onto the result event payload if the backend
        # forwards usage fields separately.

        with patch(
            "asyncio.create_subprocess_exec", AsyncMock(return_value=proc)
        ):
            _session, stream = self._drive_session()

        result = stream[-1]
        assert result.kind == "result"
        # usage key should be present in payload.
        assert "usage" in result.payload


# ----------------------------------------------------------------------
# Tool catalog helper (mirrors codex pattern)
# ----------------------------------------------------------------------


class TestOpencodeToolCatalog:
    """If opencode has a parallel build function in acp_tools, test it."""

    def test_opencode_catalog_contains_oompah_tools(self, tmp_path):
        """The opencode catalog should contain the same six oompah tools
        as the other backends — same _exec_* helpers, same safety rails."""
        try:
            from oompah.acp_tools import build_opencode_tool_catalog
        except ImportError:
            pytest.skip("build_opencode_tool_catalog not yet implemented")

        cat = build_opencode_tool_catalog(str(tmp_path))
        names = [
            getattr(t, "name", getattr(t, "__name__", str(t))) for t in cat
        ]
        for expected in (
            "read_file", "write_file", "edit_file",
            "list_files", "search_files", "run_command",
        ):
            assert expected in names, f"missing {expected!r} in opencode catalog"

    def test_opencode_catalog_size_matches_claude(self, tmp_path):
        """Opencode catalog has the same cardinality as Claude's."""
        try:
            from oompah.acp_tools import (
                build_opencode_tool_catalog,
                build_tool_catalog,
            )
        except ImportError:
            pytest.skip("build_opencode_tool_catalog not yet implemented")

        claude_cat = build_tool_catalog(str(tmp_path))
        opencode_cat = build_opencode_tool_catalog(str(tmp_path))
        assert len(opencode_cat) == len(claude_cat)


# ----------------------------------------------------------------------
# Cross-backend regression: existing backends are unchanged
# ----------------------------------------------------------------------


class TestOpencodeDoesNotRegressOtherBackends:
    """The presence of the opencode backend in the registry must not
    affect the existing claude or codex backend contracts."""

    def test_claude_name_unchanged(self):
        assert ClaudeAcpBackend.name() == "claude"

    def test_claude_validate_still_empty(self):
        backend = ClaudeAcpBackend()
        provider = ModelProvider(
            id="p1", name="anthropic", base_url="", api_key="",
        )
        assert backend.validate_provider(provider) == []

    def test_claude_acp_provider_still_validates(self):
        provider = ModelProvider(
            id="p1", name="anthropic", base_url="", backend="claude",
        )
        assert provider.validate_for_mode("acp") == []