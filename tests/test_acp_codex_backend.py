"""Tests for the Codex ACP backend (child B, oompah-zlz_2-yiuy).

Covers:

* :class:`CodexAcpBackend` registers as ``"codex"`` at package import.
* ``validate_provider`` enforces api_key for per-token tier and
  accepts a missing key for subscription tier; base_url is sanity-
  checked when overridden.
* Session lifecycle smoke test: instantiate the backend with a mock
  ``agents`` SDK module, run one turn, verify the expected
  :class:`BackendEvent` stream and terminal status.
* Tool bridging: oompah's MCP catalog round-trips through to the
  Codex / openai-agents ``function_tool`` format.
* The dual-backend state of the registry (claude + codex) doesn't
  regress the existing claude tests — verified by importing
  :class:`ClaudeAcpBackend` and re-running its validate_provider
  contract.
"""

from __future__ import annotations

import asyncio
import sys
import types
from unittest.mock import MagicMock

import pytest

from oompah.acp_backends import (
    BACKENDS,
    AcpBackendOptions,
    BackendEvent,
    get_backend,
    get_backend_or_raise,
)
from oompah.acp_backends.claude import ClaudeAcpBackend
from oompah.acp_backends.codex import (
    CodexAcpBackend,
    CodexAcpBackendSession,
    _CodexCounters,
)
from oompah.models import ModelProvider


# ----------------------------------------------------------------------
# Registration: codex shows up alongside claude after package import
# ----------------------------------------------------------------------


class TestCodexRegistration:
    def test_codex_in_registry(self):
        """Importing oompah.acp_backends (which the test harness does
        transitively) must populate BACKENDS['codex']."""
        assert "codex" in BACKENDS
        assert BACKENDS["codex"] is CodexAcpBackend

    def test_codex_name(self):
        assert CodexAcpBackend.name() == "codex"

    def test_codex_reachable_via_get_backend(self):
        assert get_backend("codex") is CodexAcpBackend
        assert get_backend_or_raise("codex") is CodexAcpBackend

    def test_claude_still_registered(self):
        """No shared-state regression: claude is still in the registry
        and resolves to ClaudeAcpBackend."""
        assert "claude" in BACKENDS
        assert BACKENDS["claude"] is ClaudeAcpBackend

    def test_registry_lists_both(self):
        """Both backends present so the /providers UI dropdown can
        offer the operator a real choice."""
        assert {"claude", "codex"}.issubset(set(BACKENDS.keys()))

    def test_acp_mode_provider_with_codex_validates_via_registry(self):
        """Provider record with mode=acp + backend='codex' passes the
        registry lookup check (validate_for_mode) — acceptance
        criterion in the bead description."""
        provider = ModelProvider(
            id="p", name="codex", base_url="", backend="codex",
            api_key="sk-codex-test",
        )
        # Backend resolves and registry-level validation is empty.
        assert provider.validate_for_mode("acp") == []


# ----------------------------------------------------------------------
# validate_provider: per-token vs subscription
# ----------------------------------------------------------------------


class TestCodexValidateProvider:
    def test_per_token_without_api_key_fails(self):
        """Per-token billing requires an api_key. Without one the
        validator emits a clear, actionable error.

        Explicit billing_model="per_token" here because main's default
        is "subscription" (the ag7h work pre-landed via 0hzh's PR #114).
        The test verifies the per-token rule fires when an operator
        has chosen per-token tier, not that per-token is implicit."""
        backend = CodexAcpBackend()
        provider = ModelProvider(
            id="p", name="codex", base_url="", api_key="",
            billing_model="per_token",
        )
        errors = backend.validate_provider(provider)
        assert len(errors) == 1
        # Error names the field AND suggests the subscription escape
        # hatch so the operator can self-serve.
        assert "api_key" in errors[0]
        assert "subscription" in errors[0].lower()

    def test_per_token_with_api_key_validates(self):
        backend = CodexAcpBackend()
        provider = ModelProvider(
            id="p", name="codex", base_url="", api_key="sk-codex-test",
        )
        assert backend.validate_provider(provider) == []

    def test_subscription_without_api_key_validates(self):
        """Subscription tier (Codex CLI OAuth flow) doesn't need an
        api_key on the provider — the validator must accept the
        record. Child C will land billing_model as a proper field;
        until then we set the attribute via setattr to simulate."""
        backend = CodexAcpBackend()
        provider = ModelProvider(
            id="p", name="codex", base_url="", api_key="",
        )
        # Simulate the field child C will add.
        provider.billing_model = "subscription"
        assert backend.validate_provider(provider) == []

    def test_subscription_case_insensitive(self):
        """Forgiving parsing — 'Subscription' / 'SUBSCRIPTION' work."""
        backend = CodexAcpBackend()
        provider = ModelProvider(
            id="p", name="codex", base_url="", api_key="",
        )
        provider.billing_model = "SUBSCRIPTION"
        assert backend.validate_provider(provider) == []

    def test_unknown_billing_model_defaults_to_per_token(self):
        """An unrecognized billing_model is treated as per-token
        (strict) — keeps validation conservative when the field is
        garbled."""
        backend = CodexAcpBackend()
        provider = ModelProvider(
            id="p", name="codex", base_url="", api_key="",
        )
        provider.billing_model = "freebie"  # not a real tier
        errors = backend.validate_provider(provider)
        assert any("api_key" in e for e in errors)

    def test_base_url_default_passes(self):
        """An empty base_url (operator wants the default Codex
        endpoint) is fine."""
        backend = CodexAcpBackend()
        provider = ModelProvider(
            id="p", name="codex", base_url="", api_key="sk-x",
        )
        assert backend.validate_provider(provider) == []

    def test_base_url_https_passes(self):
        backend = CodexAcpBackend()
        provider = ModelProvider(
            id="p", name="codex",
            base_url="https://api.openai.com/v1",
            api_key="sk-x",
        )
        assert backend.validate_provider(provider) == []

    def test_base_url_http_passes(self):
        """Operators sometimes proxy via a local http:// LB — must work."""
        backend = CodexAcpBackend()
        provider = ModelProvider(
            id="p", name="codex",
            base_url="http://localhost:8080",
            api_key="sk-x",
        )
        assert backend.validate_provider(provider) == []

    def test_base_url_invalid_scheme_fails(self):
        backend = CodexAcpBackend()
        provider = ModelProvider(
            id="p", name="codex",
            base_url="ftp://bogus",
            api_key="sk-x",
        )
        errors = backend.validate_provider(provider)
        assert any("base_url" in e for e in errors)


# ----------------------------------------------------------------------
# CodexAcpBackend.start_session returns a session-shaped handle
# ----------------------------------------------------------------------


class TestCodexStartSession:
    def test_start_session_returns_session(self):
        """start_session returns a session handle without invoking
        the SDK — the SDK only fires on the first run_turn call."""
        backend = CodexAcpBackend()
        opt = AcpBackendOptions(
            workspace_path="/tmp/ws",
            prompt="do the thing",
            model="gpt-5",
        )
        session = backend.start_session(opt)
        assert isinstance(session, CodexAcpBackendSession)
        # Pre-run sentinel — protocol consumers may not yet rely on
        # status before run_turn returns.
        assert session.status == "pending"

    def test_session_zero_counters_before_run(self):
        backend = CodexAcpBackend()
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
# Session lifecycle smoke test with a mock openai-agents SDK
# ----------------------------------------------------------------------


def _make_mock_sdk_module(
    *,
    stream_events_factory,
    usage=None,
    response_id=None,
):
    """Construct a fake ``agents`` SDK module that exposes the minimum
    surface the Codex backend uses:

    * ``Agent(name=..., instructions=..., tools=..., model=...)``
    * ``Runner.run_streamed(agent, input=...)`` → an object with an
      async ``stream_events()`` method and a ``usage`` attribute.
    * ``function_tool`` decorator (no-op for catalog round-trip
      tests).
    """
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
        # Mimic openai-agents: attach .name so the backend's catalog
        # listing in session_start can render it.
        fn.name = getattr(fn, "__name__", "tool")
        return fn

    sdk.Agent = _Agent
    sdk.Runner = _Runner
    sdk.function_tool = _function_tool
    return sdk


def _async_iter(items):
    """Build an async iterator from a list of items."""
    async def _gen():
        for it in items:
            yield it
    return _gen()


class _FakeStreamEvent:
    """Minimal stand-in for openai-agents' stream-event objects."""

    def __init__(self, type, **kwargs):
        self.type = type
        for k, v in kwargs.items():
            setattr(self, k, v)


class _FakeItem:
    def __init__(self, type, **kwargs):
        self.type = type
        for k, v in kwargs.items():
            setattr(self, k, v)


@pytest.fixture
def install_mock_sdk(monkeypatch):
    """Install a mock ``agents`` module on ``sys.modules`` for the
    duration of a single test. The Codex backend's lazy import picks
    it up via the standard ``import agents`` path."""

    installed_sdks: list[types.ModuleType] = []

    def _install(sdk: types.ModuleType) -> None:
        # Push the fake into sys.modules. _import_sdk() does
        # ``import agents`` which goes through sys.modules first.
        monkeypatch.setitem(sys.modules, "agents", sdk)
        installed_sdks.append(sdk)

    return _install


class TestCodexSessionLifecycle:
    """Smoke test: drive a CodexAcpBackendSession from start to
    terminal status through the public protocol. Mocks every SDK
    surface so the real openai-agents package never has to be
    installed."""

    def _drive_session(self, sdk_module, *, on_event=None, **opt_kwargs):
        async def runner():
            options = AcpBackendOptions(
                workspace_path="/tmp/ws",
                prompt=opt_kwargs.get("prompt", "do the thing"),
                model=opt_kwargs.get("model", "gpt-5"),
                env=opt_kwargs.get("env"),
                permission_mode=opt_kwargs.get("permission_mode", "default"),
                on_event=on_event,
            )
            # Patch the tool catalog builder so we don't load the SDK
            # at catalog-build time (the @function_tool decorator on
            # the fake sdk handles the round-trip).
            session = CodexAcpBackendSession(options)
            collected: list[BackendEvent] = []
            async for ev in session.run_turn():
                collected.append(ev)
                if len(collected) > 200:
                    break  # guard
            return session, collected

        return asyncio.run(runner())

    def test_succeeded_lifecycle(self, install_mock_sdk, monkeypatch):
        """Start → emit text → terminal result. Verify the event
        stream + terminal status + counters."""
        # Two stream items: one assistant text message, one synthetic
        # session-id capture via raw_response_event.
        items = [
            _FakeStreamEvent(
                "raw_response_event",
                data=types.SimpleNamespace(
                    delta="hello world", response_id="resp-123",
                ),
            ),
            _FakeStreamEvent(
                "run_item_stream_event",
                item=_FakeItem(
                    "message_output_item", text="completed the task",
                ),
            ),
        ]
        sdk = _make_mock_sdk_module(
            stream_events_factory=lambda: _async_iter(items),
            usage={"input_tokens": 42, "output_tokens": 17},
            response_id="resp-123",
        )
        install_mock_sdk(sdk)
        # Short-circuit the tool catalog builder to avoid importing
        # the real openai-agents at catalog-build time; the mocked
        # sdk's function_tool would already accept it but the
        # acp_tools.build_codex_tool_catalog calls api_agent's
        # _exec_* which we don't want firing for this smoke test.
        monkeypatch.setattr(
            CodexAcpBackendSession, "_build_tool_catalog",
            lambda self: [],
        )

        events_captured = []
        session, stream = self._drive_session(
            sdk, on_event=events_captured.append,
        )

        assert session.status == "succeeded"
        # session_id is captured from raw_response_event.data.response_id.
        assert session.session_id == "resp-123"
        # usage rolls up from the terminal RunResult.usage dict.
        assert session.input_tokens == 42
        assert session.output_tokens == 17
        assert session.total_tokens == 59
        # cost_usd is None for the default per_token billing model
        # when the SDK doesn't surface a dollar amount — child C will
        # compute it from tokens × model_costs.
        assert session.total_cost_usd is None

        # Expected backend event sequence: session_start → text → text → result.
        kinds = [ev.kind for ev in stream]
        assert kinds[0] == "session_start"
        assert kinds[-1] == "result"
        assert "text" in kinds

        # session_start carries the policy + catalog metadata for audit.
        start = stream[0]
        assert start.payload["model"] == "gpt-5"
        assert start.payload["tool_policy"] == "codex:bridged_catalog_only"
        assert start.payload["billing_model"] == "per_token"

        # AgentEvents flowed through on_event mirror the BackendEvents
        # (back-compat for the orchestrator's existing on_event audit
        # path — same shape it gets from the Claude backend).
        agent_event_kinds = [e.event for e in events_captured]
        assert "acp_session_start" in agent_event_kinds
        assert "acp_result" in agent_event_kinds

    def test_terminal_result_payload_has_normalized_cost_dict(
        self, install_mock_sdk, monkeypatch
    ):
        """The terminal acp_result event payload includes a
        normalized ``usage`` dict with input_tokens/output_tokens/
        total_tokens/cost_usd so child C can consume it uniformly
        regardless of which backend ran."""
        sdk = _make_mock_sdk_module(
            stream_events_factory=lambda: _async_iter([]),
            usage={"input_tokens": 10, "output_tokens": 20},
        )
        install_mock_sdk(sdk)
        monkeypatch.setattr(
            CodexAcpBackendSession, "_build_tool_catalog",
            lambda self: [],
        )
        _session, stream = self._drive_session(sdk)
        result = stream[-1]
        assert result.kind == "result"
        usage = result.payload["usage"]
        assert usage["input_tokens"] == 10
        assert usage["output_tokens"] == 20
        assert usage["total_tokens"] == 30
        # cost_usd key is present (None for per-token until child C
        # computes it from tokens × model_costs).
        assert "cost_usd" in usage
        assert usage["cost_usd"] is None

    def test_subscription_billing_cost_is_none(self, install_mock_sdk, monkeypatch):
        """When billing_model='subscription' (signaled via env),
        total_cost_usd is forced to None even if the SDK reports a
        dollar amount — there is no per-token bill in subscription
        tier."""
        sdk = _make_mock_sdk_module(
            stream_events_factory=lambda: _async_iter([]),
            usage={"input_tokens": 5, "output_tokens": 5},
        )
        # Inject a synthetic cost on the result handle to verify
        # the subscription path explicitly overrides it to None.
        original_run = sdk.Runner.run_streamed

        def _stamp_cost(agent, input=None):
            r = original_run(agent, input=input)
            r.total_cost_usd = 1.23  # would otherwise be surfaced
            return r

        sdk.Runner.run_streamed = staticmethod(_stamp_cost)
        install_mock_sdk(sdk)
        monkeypatch.setattr(
            CodexAcpBackendSession, "_build_tool_catalog",
            lambda self: [],
        )

        async def run():
            opt = AcpBackendOptions(
                workspace_path="/tmp/ws",
                prompt="x",
                env={"OOMPAH_CODEX_BILLING": "subscription"},
            )
            sess = CodexAcpBackendSession(opt)
            async for _ in sess.run_turn():
                pass
            return sess

        sess = asyncio.run(run())
        assert sess.status == "succeeded"
        assert sess.total_cost_usd is None

    def test_close_before_run_returns_interrupted(self, install_mock_sdk, monkeypatch):
        """A close() before run_turn marks status=interrupted and the
        stream yields nothing — orchestrator can short-circuit."""
        sdk = _make_mock_sdk_module(
            stream_events_factory=lambda: _async_iter([]),
            usage=None,
        )
        install_mock_sdk(sdk)
        monkeypatch.setattr(
            CodexAcpBackendSession, "_build_tool_catalog",
            lambda self: [],
        )

        async def run():
            opt = AcpBackendOptions(workspace_path="/tmp/ws", prompt="x")
            sess = CodexAcpBackendSession(opt)
            await sess.close()
            collected = []
            async for ev in sess.run_turn():
                collected.append(ev)
            return sess, collected

        sess, events = asyncio.run(run())
        assert sess.status == "interrupted"
        assert events == []

    def test_missing_sdk_returns_errored(self, monkeypatch):
        """When the openai-agents SDK isn't installed, run_turn sets
        status=errored with a clear last_error pointing at the
        missing dep — the orchestrator can surface this to the
        operator via the dashboard."""
        # Force a clean ImportError from _import_sdk by stripping any
        # cached mock module + blocking the real names.
        for name in ("agents", "openai_agents"):
            monkeypatch.delitem(sys.modules, name, raising=False)
        # Insert sentinels that raise on import attempt.
        import builtins
        real_import = builtins.__import__

        def _block_import(name, *args, **kwargs):
            if name in ("agents", "openai_agents"):
                raise ImportError(f"No module named '{name}'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _block_import)

        async def run():
            opt = AcpBackendOptions(workspace_path="/tmp/ws", prompt="x")
            sess = CodexAcpBackendSession(opt)
            collected = []
            async for ev in sess.run_turn():
                collected.append(ev)
            return sess

        sess = asyncio.run(run())
        assert sess.status == "errored"
        assert sess.last_error is not None
        assert "openai-agents" in sess.last_error

    def test_runtime_exception_during_stream_errors(self, install_mock_sdk, monkeypatch):
        """If the SDK's stream raises mid-flight, status=errored and a
        session_error event is emitted so the dashboard sees the
        failure."""

        async def _boom():
            raise RuntimeError("network blip")
            yield  # noqa — make this an async generator

        sdk = _make_mock_sdk_module(
            stream_events_factory=_boom,
            usage=None,
        )
        install_mock_sdk(sdk)
        monkeypatch.setattr(
            CodexAcpBackendSession, "_build_tool_catalog",
            lambda self: [],
        )
        _sess, stream = self._drive_session(sdk)
        kinds = [ev.kind for ev in stream]
        # session_start fires before the iteration; session_error
        # fires after the runtime exception is caught.
        assert "session_start" in kinds
        assert "session_error" in kinds
        # No "result" event — the run never terminated cleanly.
        assert "result" not in kinds


# ----------------------------------------------------------------------
# Tool bridging round-trip
# ----------------------------------------------------------------------


# TestCodexToolBridging calls build_tool_catalog() which requires
# claude_agent_sdk. Skip when it is not installed (base install without
# [claude] extra).
try:
    import claude_agent_sdk
except ImportError:
    pytest.skip("claude_agent_sdk not installed; install with uv pip install 'oompah[claude]'", allow_module_level=True)


# TestCodexToolBridging calls build_tool_catalog() which requires
# claude_agent_sdk. Skip when it is not installed (base install without
# [claude] extra).
try:
    import claude_agent_sdk
except ImportError:
    pytest.skip("claude_agent_sdk not installed; install with uv pip install 'oompah[claude]'", allow_module_level=True)


class TestCodexToolBridging:
    """A focus's MCP catalog round-trips through to Codex's tool
    format. We feed the SDK a no-op ``function_tool`` decorator and
    verify all six oompah tools come out the other side with their
    canonical names — the orchestrator's `_run_acp_worker` builds the
    catalog from oompah/acp_tools.py and this test pins that contract.
    """

    def test_codex_catalog_contains_oompah_tools(
        self, install_mock_sdk, tmp_path
    ):
        sdk = _make_mock_sdk_module(
            stream_events_factory=lambda: _async_iter([]),
            usage=None,
        )
        install_mock_sdk(sdk)

        from oompah.acp_tools import build_codex_tool_catalog

        cat = build_codex_tool_catalog(str(tmp_path))
        names = [getattr(t, "name", getattr(t, "__name__", str(t))) for t in cat]
        # The Q2 acceptance set — same six tools as the Claude
        # catalog, routed through the same _exec_* helpers so cd-guard
        # / BEADS_DIR routing apply identically.
        for expected in (
            "read_file", "write_file", "edit_file",
            "list_files", "search_files", "run_command",
        ):
            assert expected in names, f"missing {expected!r} in codex catalog"

    def test_codex_catalog_size_matches_claude(
        self, install_mock_sdk, tmp_path
    ):
        """Codex catalog has the same cardinality as Claude's — if
        someone adds a tool to one builder but forgets the other,
        this surfaces the drift."""
        sdk = _make_mock_sdk_module(
            stream_events_factory=lambda: _async_iter([]),
            usage=None,
        )
        install_mock_sdk(sdk)
        from oompah.acp_tools import build_codex_tool_catalog, build_tool_catalog

        claude_cat = build_tool_catalog(str(tmp_path))
        codex_cat = build_codex_tool_catalog(str(tmp_path))
        assert len(codex_cat) == len(claude_cat)

    def test_codex_catalog_missing_sdk_raises(self, monkeypatch, tmp_path):
        """When the openai-agents SDK isn't installed, the catalog
        builder raises ImportError with a clear install hint — NOT
        silently empty. Mismatched env vs operator expectation is an
        error worth surfacing immediately."""
        # Strip cached mock and block real imports.
        for name in ("agents", "openai_agents"):
            monkeypatch.delitem(sys.modules, name, raising=False)
        import builtins
        real_import = builtins.__import__

        def _block(name, *args, **kwargs):
            if name in ("agents", "openai_agents"):
                raise ImportError(f"No module named {name!r}")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _block)

        from oompah.acp_tools import build_codex_tool_catalog

        with pytest.raises(ImportError) as exc_info:
            build_codex_tool_catalog(str(tmp_path))
        assert "openai-agents" in str(exc_info.value)


# ----------------------------------------------------------------------
# Counters
# ----------------------------------------------------------------------


class TestCodexCounters:
    def test_absorb_usage_from_dict(self):
        c = _CodexCounters()
        c.absorb_usage({"input_tokens": 11, "output_tokens": 22, "total_tokens": 33})
        assert c.input_tokens == 11
        assert c.output_tokens == 22
        assert c.total_tokens == 33

    def test_absorb_usage_derives_total(self):
        """When the SDK reports input+output but not total, total is
        derived as input+output so callers can read a stable
        total_tokens."""
        c = _CodexCounters()
        c.absorb_usage({"input_tokens": 4, "output_tokens": 5})
        assert c.total_tokens == 9

    def test_absorb_usage_from_object(self):
        usage = types.SimpleNamespace(input_tokens=7, output_tokens=3, total_tokens=10)
        c = _CodexCounters()
        c.absorb_usage(usage)
        assert c.input_tokens == 7
        assert c.output_tokens == 3
        assert c.total_tokens == 10

    def test_absorb_usage_none_is_noop(self):
        c = _CodexCounters()
        c.absorb_usage(None)
        c.absorb_usage("not a usage object")
        assert c.input_tokens == 0


# ----------------------------------------------------------------------
# /providers UI: card badge + dropdown shows codex
# ----------------------------------------------------------------------


import os
import re


def _load_providers_html() -> str:
    path = os.path.join(
        os.path.dirname(__file__),
        os.pardir,
        "oompah",
        "templates",
        "providers.html",
    )
    with open(path, "r") as f:
        return f.read()


class TestProviderUiBackendBadge:
    """Acceptance criterion: provider list cards show the backend
    name as part of the existing mode badge style (``[ACP · claude]``
    / ``[ACP · codex]``)."""

    @pytest.fixture
    def html(self) -> str:
        return _load_providers_html()

    def test_card_renders_backend_badge_for_acp_providers(self, html: str):
        # The rendered card includes the backend name inside an
        # ACP-flavored badge when provider.backend is set. Look for
        # the literal template fragment that decides this.
        assert "p.backend" in html
        assert "ACP ·" in html or "ACP &middot;" in html
        # And the badge uses the mode-acp css class (already styled).
        assert re.search(
            r'class="provider-type mode-acp"[^>]*>ACP', html
        )

    def test_dropdown_static_fallback_lists_both(self, html: str):
        """The pre-rendered dropdown (static fallback, used while
        /api/v1/acp-backends is still loading) lists both ``claude``
        and ``codex`` so an operator opening the dialog before
        loadAcpBackends() resolves still sees the full choice.

        Regex tolerates additional <select> attributes (onchange,
        title, etc.) added by zvm0's UI cleanup so the test asserts
        the option list, not the exact element shape.
        """
        assert re.search(
            r'<select[^>]*id="prov-backend"[^>]*>[^<]*'
            r'<option value="claude">claude</option>[^<]*'
            r'<option value="codex">codex</option>',
            html, re.DOTALL,
        )


# ----------------------------------------------------------------------
# Cross-backend regression: the claude backend is unchanged
# ----------------------------------------------------------------------


class TestClaudeBackendNotRegressed:
    """The presence of the codex backend in the registry must not
    affect the claude backend's contract — acceptance criterion in
    the bead description."""

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

    def test_legacy_provider_default_backend_still_claude(self):
        """Provider records persisted before the backend field
        existed read back as backend=None, which defaults to claude
        at validate time — preserves back-compat through both A and
        B landing."""
        provider = ModelProvider(id="p1", name="x", base_url="", backend=None)
        assert provider.validate_for_mode("acp") == []
