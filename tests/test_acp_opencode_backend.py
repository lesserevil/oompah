"""Tests for the OpenCode ACP backend (oompah-zlz_2-p1ti).

Covers:

* :class:`OpenCodeAcpBackend` registers as ``"opencode"`` at package import.
* ``validate_provider`` enforces api_key for per-token tier and
  accepts a missing key for subscription tier; base_url is sanity-
  checked when overridden.
* Session lifecycle smoke test: instantiate the backend with a mock
  ``opencode`` SDK module, run one turn, verify the expected
  :class:`BackendEvent` stream and terminal status.
* Tool bridging: oompah's tool catalog round-trips through to the
  OpenCode ``@tool`` format.
* The triple-backend state of the registry (claude + codex + opencode)
  doesn't regress the existing claude or codex tests.
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
import types
from typing import Any

import pytest

from oompah.acp_backends import (
    BACKENDS,
    AcpBackendOptions,
    BackendEvent,
    get_backend,
    get_backend_or_raise,
)
from oompah.acp_backends.claude import ClaudeAcpBackend
from oompah.acp_backends.codex import CodexAcpBackend
from oompah.acp_backends.opencode import (
    OpenCodeAcpBackend,
    OpenCodeAcpBackendSession,
    _OpenCodeCounters,
)
from oompah.models import ModelProvider


# ----------------------------------------------------------------------
# Registration: opencode shows up alongside claude + codex
# ----------------------------------------------------------------------


class TestOpenCodeRegistration:
    def test_opencode_in_registry(self):
        """Importing oompah.acp_backends (which the test harness does
        transitively) must populate BACKENDS['opencode']."""
        assert "opencode" in BACKENDS
        assert BACKENDS["opencode"] is OpenCodeAcpBackend

    def test_opencode_name(self):
        assert OpenCodeAcpBackend.name() == "opencode"

    def test_opencode_reachable_via_get_backend(self):
        assert get_backend("opencode") is OpenCodeAcpBackend
        assert get_backend_or_raise("opencode") is OpenCodeAcpBackend

    def test_claude_still_registered(self):
        """Triple-backend state must not regress claude."""
        assert "claude" in BACKENDS
        assert BACKENDS["claude"] is ClaudeAcpBackend

    def test_codex_still_registered(self):
        """Triple-backend state must not regress codex."""
        assert "codex" in BACKENDS
        assert BACKENDS["codex"] is CodexAcpBackend

    def test_registry_has_all_three(self):
        """All three backends present for the /providers UI dropdown."""
        assert {"claude", "codex", "opencode"}.issubset(set(BACKENDS.keys()))

    def test_acp_mode_provider_with_opencode_validates(self):
        """Provider record with mode='acp' + backend='opencode' passes
        registry-level validation — core acceptance criterion."""
        provider = ModelProvider(
            id="p", name="opencode", base_url="",
            backend="opencode", api_key="sk-opencode-test",
        )
        assert provider.validate_for_mode("acp") == []


# ----------------------------------------------------------------------
# validate_provider: per-token vs subscription
# ----------------------------------------------------------------------


class TestOpenCodeValidateProvider:
    def test_per_token_without_api_key_fails(self):
        """Per-token billing requires an api_key; without one the
        validator emits a clear actionable error."""
        backend = OpenCodeAcpBackend()
        provider = ModelProvider(
            id="p", name="opencode", base_url="",
            api_key="", billing_model="per_token",
        )
        errors = backend.validate_provider(provider)
        assert len(errors) == 1
        assert "api_key" in errors[0]
        assert "subscription" in errors[0].lower()

    def test_per_token_with_api_key_validates(self):
        backend = OpenCodeAcpBackend()
        provider = ModelProvider(
            id="p", name="opencode", base_url="",
            api_key="sk-opencode-test",
        )
        assert backend.validate_provider(provider) == []

    def test_subscription_without_api_key_validates(self):
        """Subscription tier doesn't need an api_key — validator must
        accept the record."""
        backend = OpenCodeAcpBackend()
        provider = ModelProvider(
            id="p", name="opencode", base_url="",
            api_key="",
        )
        provider.billing_model = "subscription"
        assert backend.validate_provider(provider) == []

    def test_subscription_case_insensitive(self):
        """Forgiving parsing — 'Subscription' / 'SUBSCRIPTION' work."""
        backend = OpenCodeAcpBackend()
        provider = ModelProvider(
            id="p", name="opencode", base_url="",
            api_key="",
        )
        provider.billing_model = "SUBSCRIPTION"
        assert backend.validate_provider(provider) == []

    def test_unknown_billing_model_defaults_to_per_token(self):
        """An unrecognized billing_model is treated as per-token —
        keeps validation conservative when the field is garbled."""
        backend = OpenCodeAcpBackend()
        provider = ModelProvider(
            id="p", name="opencode", base_url="",
            api_key="",
        )
        provider.billing_model = "freeform"
        errors = backend.validate_provider(provider)
        assert any("api_key" in e for e in errors)

    def test_base_url_default_passes(self):
        """Empty base_url (operator wants default OpenCode endpoint)
        is fine."""
        backend = OpenCodeAcpBackend()
        provider = ModelProvider(
            id="p", name="opencode", base_url="",
            api_key="sk-x",
        )
        assert backend.validate_provider(provider) == []

    def test_base_url_https_passes(self):
        backend = OpenCodeAcpBackend()
        provider = ModelProvider(
            id="p", name="opencode",
            base_url="https://api.openai.com/v1",
            api_key="sk-x",
        )
        assert backend.validate_provider(provider) == []

    def test_base_url_http_passes(self):
        """Local proxy via http:// passes (mirrors Codex behavior)."""
        backend = OpenCodeAcpBackend()
        provider = ModelProvider(
            id="p", name="opencode",
            base_url="http://localhost:8080",
            api_key="sk-x",
        )
        assert backend.validate_provider(provider) == []

    def test_base_url_invalid_scheme_fails(self):
        backend = OpenCodeAcpBackend()
        provider = ModelProvider(
            id="p", name="opencode",
            base_url="ftp://bogus",
            api_key="sk-x",
        )
        errors = backend.validate_provider(provider)
        assert any("base_url" in e for e in errors)


# ----------------------------------------------------------------------
# start_session returns a session-shaped handle
# ----------------------------------------------------------------------


class TestOpenCodeStartSession:
    def test_start_session_returns_session(self):
        """start_session returns a handle without invoking the SDK —
        SDK fires lazily on first run_turn call."""
        backend = OpenCodeAcpBackend()
        opt = AcpBackendOptions(
            workspace_path="/tmp/ws",
            prompt="do the thing",
            model="opencode",
        )
        session = backend.start_session(opt)
        assert isinstance(session, OpenCodeAcpBackendSession)
        assert session.status == "pending"

    def test_session_zero_counters_before_run(self):
        backend = OpenCodeAcpBackend()
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
# Mock SDK helper
# ----------------------------------------------------------------------


class _MockChat:
    """A minimal chat mock that stores stream items in ``_stream_items``
    passed in via the constructor and yields them as
    ``(event, data)`` tuples from ``stream(prompt)``."""

    def __init__(
        self,
        _stream_items: list[tuple[str, Any]],
        **kw: Any,
    ) -> None:
        self.kwargs = kw
        self._stream_items = _stream_items
        self.usage: Any = None
        self.response_id: Any = None

    async def stream(self, prompt: str):
        """Yield (event, data) tuples from _stream_items."""
        for ev, data in self._stream_items:
            yield (ev, data)


def _make_mock_opencode_module(
    *,
    stream_items: list[tuple[str, Any]] | None = None,
    usage: Any = None,
    response_id: Any = None,
):
    """Construct a fake ``opencode`` SDK module exposing:

    * ``Chat(model=..., tools=..., api_key=..., base_url=...)`` → a
      ``_MockChat`` instance that stores ``stream_items`` and yields
      them from its ``stream()`` async generator method.

    * ``@tool`` decorator (no-op for catalog round-trip tests — attaches
      a ``name`` attribute so the backend's catalog listing can render
      it).

    ``stream_items`` defaults to ``[]`` so callers that don't need a
    stream can still import the module without crashing. Tests that DO
    need streams pass explicit ``stream_items``.
    """
    if stream_items is None:
        stream_items = []

    sdk = types.ModuleType("opencode")

    def _make_chat(**kw: Any) -> _MockChat:
        return _MockChat(stream_items, **kw)

    def _tool(name: str, description: str, schema: Any):
        """No-op decorator that attaches metadata."""
        def decorator(fn):
            fn.name = name
            fn._description = description
            fn._schema = schema
            return fn
        return decorator

    sdk.Chat = _make_chat
    sdk.tool = _tool
    return sdk


@pytest.fixture
def install_mock_opencode(monkeypatch):
    """Install a fake ``opencode`` module on ``sys.modules`` for the
    duration of a single test so the real SDK never has to be present."""
    def _install(sdk: types.ModuleType) -> None:
        monkeypatch.setitem(sys.modules, "opencode", sdk)
    return _install


class TestOpenCodeSessionLifecycle:
    """Smoke test: drive an OpenCodeAcpBackendSession from construction
    to terminal status using only the public protocol. Mocks every SDK
    surface so the real opencode package is never needed."""

    async def _run(
        self, sdk_module, *, on_event=None, **opt_kwargs
    ):
        options = AcpBackendOptions(
            workspace_path="/tmp/ws",
            prompt=opt_kwargs.get("prompt", "do the thing"),
            model=opt_kwargs.get("model", "opencode"),
            env=opt_kwargs.get("env"),
            permission_mode=opt_kwargs.get("permission_mode", "default"),
            on_event=on_event,
        )
        session = OpenCodeAcpBackendSession(options)
        collected: list[BackendEvent] = []
        async for ev in session.run_turn():
            collected.append(ev)
            if len(collected) > 200:
                break
        return session, collected

    def test_succeeded_lifecycle(self, install_mock_opencode, monkeypatch):
        """Start → text → tool_use → tool_result → terminal result.
        Verify the full event stream + counters + status."""
        items = [
            ("session_id", "sess-opencode-1"),
            ("text", "hello"),
            ("tool_call", {
                "name": "read_file",
                "arguments": {"path": "foo.txt"},
                "id": "call-1",
            }),
            ("tool_result", {
                "tool_call_id": "call-1",
                "content": "file content",
                "is_error": False,
            }),
            ("usage", {"input_tokens": 10, "output_tokens": 20}),
        ]
        sdk = _make_mock_opencode_module(
            stream_items=items,
            usage={"input_tokens": 10, "output_tokens": 20},
            response_id="sess-opencode-1",
        )
        install_mock_opencode(sdk)
        # Short-circuit the tool catalog builder so acp_tools never
        # loads the real opencode SDK.
        monkeypatch.setattr(
            OpenCodeAcpBackendSession, "_build_tool_catalog",
            lambda self: [],
        )

        events_captured = []
        session, stream = asyncio.run(
            self._run(sdk, on_event=events_captured.append)
        )

        assert session.status == "succeeded"
        assert session.session_id == "sess-opencode-1"
        assert session.input_tokens == 10
        assert session.output_tokens == 20
        assert session.total_tokens == 30
        # cost_usd is None for per_token when SDK doesn't report it
        assert session.total_cost_usd is None

        kinds = [ev.kind for ev in stream]
        assert kinds[0] == "session_start"
        assert kinds[-1] == "result"
        assert "text" in kinds
        assert "tool_use" in kinds
        assert "tool_result" in kinds

        start = stream[0]
        assert start.payload["tool_policy"] == "opencode:bridged_catalog_only"
        assert start.payload["billing_model"] == "per_token"

        # AgentEvents flowed through on_event mirror BackendEvents.
        agent_event_kinds = [e.event for e in events_captured]
        assert "acp_session_start" in agent_event_kinds
        assert "acp_result" in agent_event_kinds

    def test_thinking_event_maps_to_acp_thinking(
        self, install_mock_opencode, monkeypatch
    ):
        """OpenCode 'thinking' stream events map to acp_thinking."""
        items = [
            ("thinking", "let me think about this carefully"),
            ("text", "done"),
        ]
        sdk = _make_mock_opencode_module(stream_items=items)
        install_mock_opencode(sdk)
        monkeypatch.setattr(
            OpenCodeAcpBackendSession, "_build_tool_catalog",
            lambda self: [],
        )
        _session, stream = asyncio.run(self._run(sdk))
        kinds = [ev.kind for ev in stream]
        assert "thinking" in kinds

    def test_close_before_run_returns_interrupted(
        self, install_mock_opencode, monkeypatch
    ):
        """A close() before run_turn marks status=interrupted and the
        stream yields nothing."""
        sdk = _make_mock_opencode_module(stream_items=[])
        install_mock_opencode(sdk)
        monkeypatch.setattr(
            OpenCodeAcpBackendSession, "_build_tool_catalog",
            lambda self: [],
        )

        async def run():
            opt = AcpBackendOptions(workspace_path="/tmp/ws", prompt="x")
            sess = OpenCodeAcpBackendSession(opt)
            await sess.close()
            collected = []
            async for ev in sess.run_turn():
                collected.append(ev)
            return sess, collected

        sess, events = asyncio.run(run())
        assert sess.status == "interrupted"
        assert events == []

    def test_missing_sdk_returns_errored(self, monkeypatch):
        """When the OpenCode SDK isn't installed, run_turn sets
        status=errored with a clear last_error + install hint."""
        for name in ("opencode",):
            monkeypatch.delitem(sys.modules, name, raising=False)
        import builtins
        real_import = builtins.__import__

        def _block(name, *args, **kwargs):
            if name == "opencode":
                raise ImportError(f"No module named '{name}'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _block)

        async def run():
            opt = AcpBackendOptions(workspace_path="/tmp/ws", prompt="x")
            sess = OpenCodeAcpBackendSession(opt)
            collected = []
            async for ev in sess.run_turn():
                collected.append(ev)
            return sess

        sess = asyncio.run(run())
        assert sess.status == "errored"
        assert sess.last_error is not None
        assert "opencode" in sess.last_error.lower()

    def test_runtime_exception_during_stream_errors(
        self, install_mock_opencode, monkeypatch
    ):
        """If the SDK's stream raises mid-flight, status=errored and a
        session_error event is emitted."""
        sdk = _make_mock_opencode_module(stream_items=[])
        # Patch Chat to yield something that raises.
        old_chat = sdk.Chat

        def _boom(**kw):
            chat = old_chat(**kw)
            orig = chat.stream

            async def _bad(prompt):
                yield ("text", "starting")
                raise RuntimeError("network blip")

            chat.stream = _bad
            return chat

        sdk.Chat = _boom
        install_mock_opencode(sdk)
        monkeypatch.setattr(
            OpenCodeAcpBackendSession, "_build_tool_catalog",
            lambda self: [],
        )
        _sess, stream = asyncio.run(self._run(sdk))
        kinds = [ev.kind for ev in stream]
        assert "session_start" in kinds
        assert "session_error" in kinds
        assert "result" not in kinds


# ----------------------------------------------------------------------
# Tool bridging round-trip
# ----------------------------------------------------------------------


class TestOpenCodeToolBridging:
    """A focus's tool catalog round-trips through the OpenCode SDK's
    ``@tool`` format. Mirrors the Codex tool bridging tests."""

    def test_opencode_catalog_contains_oompah_tools(
        self, install_mock_opencode, tmp_path
    ):
        sdk = _make_mock_opencode_module(stream_items=[])
        install_mock_opencode(sdk)

        from oompah.acp_tools import build_opencode_tool_catalog

        cat = build_opencode_tool_catalog(str(tmp_path))
        names = [
            getattr(t, "name", getattr(t, "__name__", str(t)))
            for t in cat
        ]
        for expected in (
            "read_file", "write_file", "edit_file",
            "list_files", "search_files", "run_command",
        ):
            assert expected in names, f"missing {expected!r}"

    def test_opencode_catalog_size_matches_claude(
        self, install_mock_opencode, tmp_path
    ):
        """OpenCode catalog has the same cardinality as Claude's."""
        sdk = _make_mock_opencode_module(stream_items=[])
        install_mock_opencode(sdk)
        from oompah.acp_tools import (
            build_opencode_tool_catalog,
            build_tool_catalog,
        )
        claude_cat = build_tool_catalog(str(tmp_path))
        opencode_cat = build_opencode_tool_catalog(str(tmp_path))
        assert len(opencode_cat) == len(claude_cat)

    def test_opencode_catalog_missing_sdk_raises(self, monkeypatch, tmp_path):
        """When the OpenCode SDK isn't installed, the catalog builder
        raises ImportError with a clear install hint."""
        for name in ("opencode",):
            monkeypatch.delitem(sys.modules, name, raising=False)
        import builtins
        real_import = builtins.__import__

        def _block(name, *args, **kwargs):
            if name == "opencode":
                raise ImportError(f"No module named {name!r}")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _block)

        from oompah.acp_tools import build_opencode_tool_catalog

        with pytest.raises(ImportError) as exc_info:
            build_opencode_tool_catalog(str(tmp_path))
        assert "opencode" in str(exc_info.value)


# ----------------------------------------------------------------------
# Counters
# ----------------------------------------------------------------------


class TestOpenCodeCounters:
    def test_absorb_usage_from_dict(self):
        c = _OpenCodeCounters()
        c.absorb_usage({"input_tokens": 11, "output_tokens": 22, "total_tokens": 33})
        assert c.input_tokens == 11
        assert c.output_tokens == 22
        assert c.total_tokens == 33

    def test_absorb_usage_derives_total(self):
        """When SDK reports only input+output, total is derived."""
        c = _OpenCodeCounters()
        c.absorb_usage({"input_tokens": 4, "output_tokens": 5})
        assert c.total_tokens == 9

    def test_absorb_usage_from_object(self):
        usage = types.SimpleNamespace(
            input_tokens=7, output_tokens=3, total_tokens=10,
        )
        c = _OpenCodeCounters()
        c.absorb_usage(usage)
        assert c.input_tokens == 7
        assert c.output_tokens == 3
        assert c.total_tokens == 10

    def test_absorb_usage_none_is_noop(self):
        c = _OpenCodeCounters()
        c.absorb_usage(None)
        assert c.input_tokens == 0


# ----------------------------------------------------------------------
# /providers UI: dropdown shows all three backends
# ----------------------------------------------------------------------


class TestProviderDropdownAllThree:
    """Acceptance criterion: the static-fallback dropdown in
    providers.html lists all three registered ACP backends so the
    operator sees the full choice before loadAcpBackends() resolves."""

    def test_dropdown_static_fallback_lists_all_three(self):
        html_path = os.path.join(
            os.path.dirname(__file__),
            os.pardir,
            "oompah",
            "templates",
            "providers.html",
        )
        with open(html_path) as fh:
            html = fh.read()
        assert re.search(
            r'<select[^>]*id="prov-backend"[^>]*>'
            r'[^<]*<option value="claude">claude</option>'
            r'[^<]*<option value="codex">codex</option>'
            r'[^<]*<option value="opencode">opencode</option>',
            html, re.DOTALL,
        ), "Static dropdown must list all three ACP backend options"


# ----------------------------------------------------------------------
# Cross-backend regression: existing backends are untouched
# ----------------------------------------------------------------------


class TestOtherBackendsNotRegressed:
    """The presence of the opencode backend must not affect claude or
    codex backends' contracts."""

    def test_claude_name_still_claude(self):
        assert ClaudeAcpBackend.name() == "claude"

    def test_claude_validate_still_empty(self):
        backend = ClaudeAcpBackend()
        provider = ModelProvider(
            id="p1", name="anthropic", base_url="", api_key="",
        )
        assert backend.validate_provider(provider) == []

    def test_codex_name_still_codex(self):
        assert CodexAcpBackend.name() == "codex"

    def test_legacy_provider_backend_defaults_to_claude(self):
        """Provider records persisted before the backend field existed
        read back as backend=None and default to claude."""
        provider = ModelProvider(
            id="p1", name="x", base_url="", backend=None,
        )
        assert provider.validate_for_mode("acp") == []