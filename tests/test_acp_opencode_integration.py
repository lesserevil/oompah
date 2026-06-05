"""Integration tests for the Codex ACP backend (oompah-zlz_2-glhw).

These tests verify end-to-end session behavior with a mock openai-agents
SDK — covering the full lifecycle, event shapes, token counters,
billing, error handling, and clean subprocess termination. No real
openai-agents installation required; the SDK surface is mocked using
the same technique as the unit tests.

Mark: ``@pytest.mark.integration`` — run separately with:
    make test TEST=tests/test_acp_opencode_integration.py
"""

from __future__ import annotations

import asyncio
import sys
import types
from unittest.mock import MagicMock

import pytest

from oompah.acp_backends import AcpBackendOptions, BackendEvent
from oompah.acp_backends.codex import CodexAcpBackend, CodexAcpBackendSession
from oompah.agent import AgentEvent


# ----------------------------------------------------------------------
# Mock SDK helpers — shared across test classes
# ----------------------------------------------------------------------


def _make_mock_sdk_module(
    *,
    stream_events_factory,
    usage=None,
    response_id=None,
):
    """Build a fake ``agents`` module matching the openai-agents SDK
    surface that CodexAcpBackendSession consumes."""
    sdk = types.ModuleType("agents")

    class _Agent:
        def __init__(self, **kw):
            self.kwargs = kw

    class _StreamedResult:
        def __init__(self):
            self.usage = usage
            self.response_id = response_id
            self._iter = stream_events_factory()
            self.cancelled = False

        def stream_events(self):
            return self._iter

        def cancel(self):
            self.cancelled = True

    class _Runner:
        @staticmethod
        def run_streamed(agent, input=None):
            return _StreamedResult()

    def _function_tool(fn):
        fn.name = getattr(fn, "__name__", "tool")
        return fn

    sdk.Agent = _Agent
    sdk.Runner = _Runner
    sdk.function_tool = _function_tool
    return sdk


def _async_iter(items):
    """Wrap a synchronous list as an async generator."""
    async def _gen():
        for it in items:
            yield it
    return _gen()


class _FakeStreamEvent:
    """Minimal stand-in for a single openai-agents stream event."""

    def __init__(self, type, **kwargs):
        self.type = type
        for k, v in kwargs.items():
            setattr(self, k, v)


class _FakeItem:
    """Minimal stand-in for an SDK run-item object."""

    def __init__(self, type, **kwargs):
        self.type = type
        for k, v in kwargs.items():
            setattr(self, k, v)


class _FakeTextDelta:
    """Stand-in for openai-agents streaming text delta data."""

    def __init__(self, delta: str, response_id: str | None = None):
        self.delta = delta
        self.response_id = response_id
        self.id = response_id


@pytest.fixture
def install_mock_sdk(monkeypatch):
    """Install a mock ``agents`` module on sys.modules for a single test.
    The Codex backend's lazy import via _import_sdk() picks up the mock."""

    def _install(sdk: types.ModuleType) -> None:
        monkeypatch.setitem(sys.modules, "agents", sdk)

    return _install


@pytest.fixture
def null_tool_catalog(monkeypatch):
    """Replace _build_tool_catalog with a no-op that returns an empty list,
    avoiding real SDK imports / file-system side effects during the run."""
    monkeypatch.setattr(
        CodexAcpBackendSession, "_build_tool_catalog", lambda self: []
    )


# ----------------------------------------------------------------------
# Full session lifecycle: create → prompt → stream → close
# ----------------------------------------------------------------------


class TestCodexIntegrationSessionLifecycle:
    """Acceptance criterion: full round-trip works (create → prompt →
    stream → close). Verifies the event sequence, session_id capture,
    and terminal status."""

    @pytest.mark.asyncio
    async def test_create_prompt_stream_close_sequence(
        self, install_mock_sdk, null_tool_catalog
    ):
        """Session start → text chunks → tool call → tool result →
        thinking → terminal result → close() returns immediately."""
        events_received: list[BackendEvent] = []
        agent_events_received: list[AgentEvent] = []

        def _on_agent_event(ev: AgentEvent):
            agent_events_received.append(ev)

        stream_items = [
            # Session begins with a text delta.
            _FakeStreamEvent(
                "raw_response_event",
                data=_FakeTextDelta(delta="I'm looking at ", response_id="sess-abc"),
            ),
            _FakeStreamEvent(
                "raw_response_event",
                data=_FakeTextDelta(delta="the codebase now.", response_id="sess-abc"),
            ),
            # Tool call (standard Codex tool-calling pattern).
            _FakeStreamEvent(
                "run_item_stream_event",
                item=_FakeItem(
                    "tool_call_item",
                    tool_name="read_file",
                    arguments={"path": "README.md"},
                    call_id="call-001",
                ),
            ),
            # Tool result.
            _FakeStreamEvent(
                "run_item_stream_event",
                item=_FakeItem(
                    "tool_call_output_item",
                    call_id="call-001",
                    output="# oompah\n\nWelcome.\n",
                    is_error=False,
                ),
            ),
            # Reasoning / thinking.
            _FakeStreamEvent(
                "run_item_stream_event",
                item=_FakeItem(
                    "reasoning_item",
                    text="I read the README, here's what I think.",
                ),
            ),
            # Final assistant text.
            _FakeStreamEvent(
                "run_item_stream_event",
                item=_FakeItem(
                    "message_output_item",
                    text="The README shows this is oompah.",
                ),
            ),
        ]

        sdk = _make_mock_sdk_module(
            stream_events_factory=lambda: _async_iter(stream_items),
            usage={"input_tokens": 150, "output_tokens": 280, "total_tokens": 430},
            response_id="sess-abc",
        )
        install_mock_sdk(sdk)

        opt = AcpBackendOptions(
            workspace_path="/tmp/test-ws",
            prompt="Review the README.",
            model="gpt-5",
            permission_mode="default",
            on_event=_on_agent_event,
        )
        session = CodexAcpBackendSession(opt)
        collected: list[BackendEvent] = []

        async for ev in session.run_turn():
            collected.append(ev)
            events_received.append(ev)

        # --- Terminal assertions ---
        assert session.status == "succeeded"
        assert session.session_id == "sess-abc"
        assert session.turn_count == 1

        # --- Event sequence ---
        kinds = [ev.kind for ev in collected]
        assert kinds[0] == "session_start"
        assert "text" in kinds          # at least one text event
        assert "tool_use" in kinds      # tool call emitted
        assert "tool_result" in kinds   # tool result emitted
        assert "thinking" in kinds      # reasoning item emitted
        assert kinds[-1] == "result"

        # --- Tool call payload structure ---
        tool_use_ev = next(ev for ev in collected if ev.kind == "tool_use")
        assert tool_use_ev.payload["tool"] == "read_file"
        assert tool_use_ev.payload["input"] == {"path": "README.md"}
        assert tool_use_ev.payload["id"] == "call-001"

        # --- Tool result payload structure ---
        tool_res_ev = next(ev for ev in collected if ev.kind == "tool_result")
        assert tool_res_ev.payload["tool_use_id"] == "call-001"
        assert not tool_res_ev.payload["is_error"]
        assert "# oompah" in tool_res_ev.payload["content"]

        # --- Thinking payload ---
        thinking_ev = next(ev for ev in collected if ev.kind == "thinking")
        assert "README" in thinking_ev.payload["text"]

        # --- AgentEvents also fired through on_event ---
        agent_kinds = [e.event for e in agent_events_received]
        assert "acp_session_start" in agent_kinds
        assert "acp_tool_use" in agent_kinds
        assert "acp_result" in agent_kinds

        # --- close() is safe to call after stream exhausted ---
        await session.close()  # should not raise


# ----------------------------------------------------------------------
# Tool call structure validation
# ----------------------------------------------------------------------


class TestCodexIntegrationToolCalls:
    """Acceptance criterion: tool call events have correct structure —
    tool name (str), arguments (dict), call id (str)."""

    @pytest.mark.asyncio
    async def test_tool_call_payload_has_name_input_and_id(
        self, install_mock_sdk, null_tool_catalog
    ):
        """Baseline tool call: name is a string, input is a dict, id is present."""
        stream_items = [
            _FakeStreamEvent(
                "run_item_stream_event",
                item=_FakeItem(
                    "tool_call_item",
                    tool_name="search_files",
                    arguments={"pattern": "TODO", "path": "src"},
                    call_id="call-xyz-7",
                ),
            ),
        ]
        sdk = _make_mock_sdk_module(
            stream_events_factory=lambda: _async_iter(stream_items),
            usage={"input_tokens": 10, "output_tokens": 5},
            response_id="resp-1",
        )
        install_mock_sdk(sdk)

        opt = AcpBackendOptions(workspace_path="/tmp/ws", prompt="find todos")
        session = CodexAcpBackendSession(opt)
        collected = []
        async for ev in session.run_turn():
            collected.append(ev)

        tool_use = next(e for e in collected if e.kind == "tool_use")
        payload = tool_use.payload

        assert isinstance(payload["tool"], str)
        assert payload["tool"] == "search_files"
        assert isinstance(payload["input"], dict)
        assert payload["input"] == {"pattern": "TODO", "path": "src"}
        assert isinstance(payload["id"], str)
        assert payload["id"] == "call-xyz-7"

    @pytest.mark.asyncio
    async def test_multi_turn_tool_calls_increment_turn_count(
        self, install_mock_sdk, null_tool_catalog
    ):
        """Two sequential tool calls = two turns. turn_count tracks correctly."""
        stream_items = [
            _FakeStreamEvent(
                "run_item_stream_event",
                item=_FakeItem(
                    "tool_call_item",
                    tool_name="list_files",
                    arguments={"path": "."},
                    call_id="call-2",
                ),
            ),
            _FakeStreamEvent(
                "run_item_stream_event",
                item=_FakeItem(
                    "tool_call_output_item",
                    call_id="call-2",
                    output="a.py\nb.py\n",
                    is_error=False,
                ),
            ),
            _FakeStreamEvent(
                "run_item_stream_event",
                item=_FakeItem(
                    "tool_call_item",
                    tool_name="run_command",
                    arguments={"command": "git status"},
                    call_id="call-3",
                ),
            ),
        ]
        sdk = _make_mock_sdk_module(
            stream_events_factory=lambda: _async_iter(stream_items),
            usage={"input_tokens": 20, "output_tokens": 15},
            response_id="resp-multi",
        )
        install_mock_sdk(sdk)

        opt = AcpBackendOptions(workspace_path="/tmp/ws", prompt="list and run")
        session = CodexAcpBackendSession(opt)
        async for _ in session.run_turn():
            pass

        # Two distinct tool_use events → turn_count = 2.
        assert session.turn_count == 2

    @pytest.mark.asyncio
    async def test_tool_result_and_error_flag(
        self, install_mock_sdk, null_tool_catalog
    ):
        """tool_result payload has tool_use_id, is_error bool, and content."""
        stream_items = [
            _FakeStreamEvent(
                "run_item_stream_event",
                item=_FakeItem(
                    "tool_call_item",
                    tool_name="edit_file",
                    arguments={"path": "x.py", "old": "a", "new": "b"},
                    call_id="call-err-1",
                ),
            ),
            _FakeStreamEvent(
                "run_item_stream_event",
                item=_FakeItem(
                    "tool_call_output_item",
                    call_id="call-err-1",
                    output="File not found",
                    is_error=True,
                ),
            ),
        ]
        sdk = _make_mock_sdk_module(
            stream_events_factory=lambda: _async_iter(stream_items),
            usage={"input_tokens": 5, "output_tokens": 3},
            response_id="resp-err",
        )
        install_mock_sdk(sdk)

        opt = AcpBackendOptions(workspace_path="/tmp/ws", prompt="edit x")
        session = CodexAcpBackendSession(opt)
        collected = []
        async for ev in session.run_turn():
            collected.append(ev)

        tool_res = next(e for e in collected if e.kind == "tool_result")
        assert tool_res.payload["tool_use_id"] == "call-err-1"
        assert tool_res.payload["is_error"] is True
        assert "not found" in tool_res.payload["content"]


# ----------------------------------------------------------------------
# Token counters populated after run_turn
# ----------------------------------------------------------------------


class TestCodexIntegrationTokenCounters:
    """Acceptance criterion: token counters are accessible after the
    session completes. input_tokens, output_tokens, total_tokens all
    non-zero when the SDK reports usage."""

    @pytest.mark.asyncio
    async def test_counters_populated_after_run_turn(
        self, install_mock_sdk, null_tool_catalog
    ):
        """Counters reflect the final SDK usage report."""
        stream_items = [
            _FakeStreamEvent(
                "run_item_stream_event",
                item=_FakeItem("message_output_item", text="Done."),
            ),
        ]
        sdk = _make_mock_sdk_module(
            stream_events_factory=lambda: _async_iter(stream_items),
            usage={"input_tokens": 1000, "output_tokens": 500, "total_tokens": 1500},
            response_id="tok-test",
        )
        install_mock_sdk(sdk)

        opt = AcpBackendOptions(workspace_path="/tmp/ws", prompt="analyze")
        session = CodexAcpBackendSession(opt)
        async for _ in session.run_turn():
            pass

        assert session.input_tokens == 1000
        assert session.output_tokens == 500
        assert session.total_tokens == 1500

    @pytest.mark.asyncio
    async def test_counters_derivable_from_input_plus_output(
        self, install_mock_sdk, null_tool_catalog
    ):
        """When SDK only reports input + output (no total), total is derived."""
        stream_items = [
            _FakeStreamEvent(
                "run_item_stream_event",
                item=_FakeItem("message_output_item", text="ok"),
            ),
        ]
        sdk = _make_mock_sdk_module(
            stream_events_factory=lambda: _async_iter(stream_items),
            usage={"input_tokens": 7, "output_tokens": 3},  # no total_tokens
            response_id="tok-derive",
        )
        install_mock_sdk(sdk)

        opt = AcpBackendOptions(workspace_path="/tmp/ws", prompt="x")
        session = CodexAcpBackendSession(opt)
        async for _ in session.run_turn():
            pass

        assert session.input_tokens == 7
        assert session.output_tokens == 3
        assert session.total_tokens == 10

    @pytest.mark.asyncio
    async def test_usage_dict_in_terminal_result_event(
        self, install_mock_sdk, null_tool_catalog
    ):
        """The terminal acp_result event carries a usage dict with all four
        fields so the orchestrator / child C can read them uniformly."""
        stream_items = [
            _FakeStreamEvent(
                "run_item_stream_event",
                item=_FakeItem("message_output_item", text="done"),
            ),
        ]
        sdk = _make_mock_sdk_module(
            stream_events_factory=lambda: _async_iter(stream_items),
            usage={"input_tokens": 1, "output_tokens": 2},
            response_id="res-usage",
        )
        install_mock_sdk(sdk)

        opt = AcpBackendOptions(workspace_path="/tmp/ws", prompt="x")
        session = CodexAcpBackendSession(opt)
        collected = []
        async for ev in session.run_turn():
            collected.append(ev)

        result = next(e for e in collected if e.kind == "result")
        usage = result.payload["usage"]
        assert usage["input_tokens"] == 1
        assert usage["output_tokens"] == 2
        assert usage["total_tokens"] == 3
        assert "cost_usd" in usage


# ----------------------------------------------------------------------
# Billing model: subscription → total_cost_usd is None
# ----------------------------------------------------------------------


def _install_fake_codex_cli(monkeypatch, *, events):
    """Patch CodexAcpBackendSession._import_codex_cli with a fake
    (Codex, ThreadOptions, TurnOptions) triple that streams *events* —
    so the subscription/OAuth path runs without spawning the real codex
    binary."""
    async def _gen(items):
        for it in items:
            yield it

    class _Streamed:
        def __init__(self, evs):
            self.events = evs

    class _Thread:
        async def run_streamed(self, prompt, turn_options=None):
            return _Streamed(_gen(list(events)))

    class _Codex:
        def __init__(self, *a, **k):
            pass

        def start_thread(self, options=None):
            return _Thread()

    class _Opts:
        def __init__(self, **k):
            self.__dict__.update(k)

    monkeypatch.setattr(
        CodexAcpBackendSession,
        "_import_codex_cli",
        staticmethod(lambda: (_Codex, _Opts, _Opts)),
    )


class TestCodexIntegrationBillingSubscription:
    """Acceptance criterion: billing_model='subscription' routes to the
    Codex CLI (OAuth) path and reports total_cost_usd=None (no per-token
    bill in subscription tier)."""

    @pytest.mark.asyncio
    async def test_subscription_total_cost_usd_is_none(self, monkeypatch):
        """Subscription mode: no per-token bill, cost must be None."""
        _install_fake_codex_cli(
            monkeypatch,
            events=[
                types.SimpleNamespace(type="turn.started"),
                types.SimpleNamespace(
                    type="item.completed",
                    item=types.SimpleNamespace(type="agent_message", text="result"),
                ),
                types.SimpleNamespace(
                    type="turn.completed",
                    usage=types.SimpleNamespace(input_tokens=5, output_tokens=5),
                ),
            ],
        )

        opt = AcpBackendOptions(
            workspace_path="/tmp/ws",
            prompt="x",
            billing_model="subscription",
        )
        session = CodexAcpBackendSession(opt)
        async for _ in session.run_turn():
            pass

        assert session.status == "succeeded"
        assert session.total_cost_usd is None

    @pytest.mark.asyncio
    async def test_subscription_result_payload_has_none_cost(self, monkeypatch):
        """Terminal acp_result payload includes total_cost_usd=None."""
        _install_fake_codex_cli(
            monkeypatch,
            events=[
                types.SimpleNamespace(type="turn.started"),
                types.SimpleNamespace(
                    type="item.completed",
                    item=types.SimpleNamespace(type="agent_message", text="hi"),
                ),
                types.SimpleNamespace(
                    type="turn.completed",
                    usage=types.SimpleNamespace(input_tokens=2, output_tokens=1),
                ),
            ],
        )

        opt = AcpBackendOptions(
            workspace_path="/tmp/ws",
            prompt="x",
            billing_model="subscription",
        )
        session = CodexAcpBackendSession(opt)
        collected = []
        async for ev in session.run_turn():
            collected.append(ev)

        result = next(e for e in collected if e.kind == "result")
        assert result.payload["total_cost_usd"] is None
        assert result.payload["subtype"] == "success"


# ----------------------------------------------------------------------
# Error handling: invalid request returns errored status + event
# ----------------------------------------------------------------------


class TestCodexIntegrationErrorHandling:
    """Acceptance criterion: error cases produce correct status and
    events. Covers SDK import failure, stream exception, and missing
    required SDK attributes."""

    @pytest.mark.asyncio
    async def test_sdk_import_failure_yields_errored(
        self, monkeypatch, null_tool_catalog
    ):
        """When neither 'agents' nor 'openai_agents' resolves, status
        becomes 'errored' and last_error mentions the missing SDK.

        Note: no event is emitted for this pre-session failure — the
        session_start event is only yielded after the SDK loads
        successfully. The status + last_error path allows the
        orchestrator to detect this error through the session handle
        without relying on a specific event being present."""
        # Block all import paths.
        for name in ("agents", "openai_agents"):
            monkeypatch.delitem(sys.modules, name, raising=False)
        import builtins
        real_import = builtins.__import__

        def _block(name, *args, **kwargs):
            if name in ("agents", "openai_agents"):
                raise ImportError(f"No module named '{name}'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _block)

        opt = AcpBackendOptions(workspace_path="/tmp/ws", prompt="x")
        session = CodexAcpBackendSession(opt)
        collected = []
        async for ev in session.run_turn():
            collected.append(ev)

        # Status flips to 'errored' so orchestrator detects failure.
        assert session.status == "errored"
        assert "openai-agents" in (session.last_error or "")
        # No events — session_start only fires after successful SDK load.
        assert collected == []

    @pytest.mark.asyncio
    async def test_stream_runtime_exception_yields_errored(
        self, install_mock_sdk, null_tool_catalog
    ):
        """If the SDK stream raises mid-flight, the session transitions
        to errored and emits a session_error event."""

        async def _boom():
            raise RuntimeError("Simulated network blip")
            yield  # make this an async generator

        sdk = _make_mock_sdk_module(
            stream_events_factory=_boom,
            usage=None,
        )
        install_mock_sdk(sdk)

        opt = AcpBackendOptions(workspace_path="/tmp/ws", prompt="x")
        session = CodexAcpBackendSession(opt)
        collected = []
        async for ev in session.run_turn():
            collected.append(ev)

        assert session.status == "errored"
        kinds = [ev.kind for ev in collected]
        assert "session_start" in kinds              # session_start fires first
        assert "session_error" in kinds              # error captured
        assert "result" not in kinds                 # stream didn't drain

    @pytest.mark.asyncio
    async def test_missing_runner_run_streamed_yields_errored(
        self, install_mock_sdk, null_tool_catalog
    ):
        """When the SDK's Runner has neither run_streamed nor stream,
        the backend bails early with a clear error."""
        sdk = types.ModuleType("agents")

        class _BadRunner:
            pass  # neither run_streamed nor stream

        class _Agent:
            pass

        sdk.Agent = _Agent
        sdk.Runner = _BadRunner
        install_mock_sdk(sdk)

        opt = AcpBackendOptions(workspace_path="/tmp/ws", prompt="x")
        session = CodexAcpBackendSession(opt)
        async for _ in session.run_turn():
            pass

        assert session.status == "errored"
        assert session.last_error is not None


# ----------------------------------------------------------------------
# close() cleanly terminates subprocess / streamed result
# ----------------------------------------------------------------------


class TestCodexIntegrationClose:
    """Acceptance criterion: close() cleanly terminates the active
    session / streamed result. Idempotent (safe to call multiple
    times)."""

    @pytest.mark.asyncio
    async def test_close_before_run_turn_returns_interrupted(
        self, install_mock_sdk, null_tool_catalog
    ):
        """close() before run_turn → status=interrupted, no events."""
        sdk = _make_mock_sdk_module(
            stream_events_factory=lambda: _async_iter([]),
            usage=None,
        )
        install_mock_sdk(sdk)

        opt = AcpBackendOptions(workspace_path="/tmp/ws", prompt="x")
        session = CodexAcpBackendSession(opt)
        await session.close()

        collected = []
        async for ev in session.run_turn():
            collected.append(ev)

        assert session.status == "interrupted"
        assert collected == []

    @pytest.mark.asyncio
    async def test_close_during_run_turn_cancels_stream(
        self, install_mock_sdk, null_tool_catalog
    ):
        """close() mid-stream requests cancellation. The stream should
        break out and status reflect 'interrupted'."""
        mid_turn_cancelled = False

        async def _slow_stream():
            nonlocal mid_turn_cancelled
            yield _FakeStreamEvent(
                "raw_response_event",
                data=_FakeTextDelta(delta="chunk one"),
            )
            # Signal that we got here before cancel was processed.
            mid_turn_cancelled = True
            yield _FakeStreamEvent(
                "raw_response_event",
                data=_FakeTextDelta(delta="chunk two — should NOT see"),
            )

        sdk = _make_mock_sdk_module(
            stream_events_factory=_slow_stream,
            usage={"input_tokens": 1, "output_tokens": 1},
            response_id="close-mid",
        )
        install_mock_sdk(sdk)

        opt = AcpBackendOptions(workspace_path="/tmp/ws", prompt="x")
        session = CodexAcpBackendSession(opt)

        # Start iteration, let one event through, then close.
        async def _run_with_close():
            events = []
            async for ev in session.run_turn():
                events.append(ev)
                if len(events) == 1:
                    await session.close()
            return events

        events = await _run_with_close()
        # After cancel, stream should stop — we only got 1 event.
        assert len(events) == 1
        assert session.status == "interrupted"

    @pytest.mark.asyncio
    async def test_close_is_idempotent(self, install_mock_sdk, null_tool_catalog):
        """Calling close() multiple times does not raise."""
        sdk = _make_mock_sdk_module(
            stream_events_factory=lambda: _async_iter([
                _FakeStreamEvent(
                    "run_item_stream_event",
                    item=_FakeItem("message_output_item", text="done"),
                ),
            ]),
            usage={"input_tokens": 1, "output_tokens": 1},
            response_id="close-multi",
        )
        install_mock_sdk(sdk)

        opt = AcpBackendOptions(workspace_path="/tmp/ws", prompt="x")
        session = CodexAcpBackendSession(opt)
        async for _ in session.run_turn():
            pass

        # Multiple closes — should all be silent.
        await session.close()
        await session.close()
        await session.close()


# ----------------------------------------------------------------------
# Backend entrypoint, registry presence, and provider validation
# ----------------------------------------------------------------------


class TestCodexIntegrationBackendContract:
    """Integration sanity checks for the CodexAcpBackend class itself —
    registry presence, name, start_session, validate_provider."""

    def test_backend_name_is_codex(self):
        assert CodexAcpBackend.name() == "codex"

    def test_start_session_returns_session_handle(self):
        """start_session is a factory — no SDK invocation yet."""
        backend = CodexAcpBackend()
        opt = AcpBackendOptions(workspace_path="/tmp/ws", prompt="hi")
        session = backend.start_session(opt)
        assert isinstance(session, CodexAcpBackendSession)
        assert session.status == "pending"

    def test_per_token_validation_requires_api_key(self):
        """Per-token billing (default) requires api_key on the provider."""
        from oompah.models import ModelProvider

        backend = CodexAcpBackend()
        provider = ModelProvider(
            id="p1", name="codex", base_url="", api_key="",
            billing_model="per_token",
        )
        errors = backend.validate_provider(provider)
        assert len(errors) > 0
        assert any("api_key" in e for e in errors)

    def test_subscription_validation_skips_api_key(self):
        """Subscription tier does not require api_key."""
        from oompah.models import ModelProvider

        backend = CodexAcpBackend()
        provider = ModelProvider(
            id="p2", name="codex", base_url="", api_key="",
        )
        provider.billing_model = "subscription"
        assert backend.validate_provider(provider) == []

    def test_session_id_captured_from_raw_response_event(self):
        """session_id property is populated from the SDK's response_id."""
        stream_items = [
            _FakeStreamEvent(
                "raw_response_event",
                data=_FakeTextDelta(delta="hi", response_id="custom-sid"),
            ),
            _FakeStreamEvent(
                "run_item_stream_event",
                item=_FakeItem("message_output_item", text="done"),
            ),
        ]
        sdk = _make_mock_sdk_module(
            stream_events_factory=lambda: _async_iter(stream_items),
            usage={"input_tokens": 1, "output_tokens": 1},
            response_id="custom-sid",
        )
        # Monkeypatch install_mock_sdk inline since we're not in a test
        # fixture context here — use the monkeypatch from the parent class.
        import sys as _sys
        _sys.modules["agents"] = sdk

        opt = AcpBackendOptions(workspace_path="/tmp/ws", prompt="x")
        session = CodexAcpBackendSession(opt)
        # Patch tool catalog builder.
        session._build_tool_catalog = lambda: []

        async def _run():
            collected = []
            async for ev in session.run_turn():
                collected.append(ev)
            return collected

        result = asyncio.run(_run())
        assert session.session_id == "custom-sid"
        del _sys.modules["agents"]