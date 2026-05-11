"""Tests for the ACP backend abstraction + registry.

Child A of the multi-backend ACP epic (oompah-zlz_2-0hzh). Covers:

* :class:`ClaudeAcpBackend` registers as ``"claude"`` at import.
* A fake backend can be registered via :func:`register_backend` and
  looked up via the registry helpers.
* :class:`ModelProvider` ``validate_for_mode`` returns an error for an
  unknown backend when used in ``mode="acp"``.
* Non-acp modes ignore the ``backend`` field.
* :class:`ModelProvider.backend` round-trips through ``to_dict`` /
  ``from_dict`` (back-compat: missing field → ``None`` → ``"claude"``
  at validation time).
"""

from __future__ import annotations

import pytest

from oompah.acp_backends import (
    BACKENDS,
    AcpBackend,
    AcpBackendOptions,
    AcpBackendSession,
    BackendEvent,
    get_backend,
    get_backend_or_raise,
    register_backend,
    validate_provider_backend,
)
from oompah.acp_backends.claude import ClaudeAcpBackend
from oompah.models import ModelProvider


# ----------------------------------------------------------------------
# Registry
# ----------------------------------------------------------------------


class TestRegistry:
    def test_claude_registered_at_import(self):
        """The Claude backend is the back-compat default; importing the
        package alone must populate ``BACKENDS["claude"]`` so legacy
        providers (no backend field) can resolve a backend without any
        explicit registration step."""
        assert "claude" in BACKENDS
        assert BACKENDS["claude"] is ClaudeAcpBackend
        # Also reachable through the public lookup helpers.
        assert get_backend("claude") is ClaudeAcpBackend

    def test_get_backend_unknown_returns_none(self):
        assert get_backend("does-not-exist") is None
        assert get_backend(None) is None
        assert get_backend("") is None

    def test_get_backend_or_raise_unknown_raises(self):
        with pytest.raises(ValueError) as exc_info:
            get_backend_or_raise("nope")
        # The error message must list the registered backends so the
        # operator can fix their config without grepping source.
        assert "claude" in str(exc_info.value)
        assert "nope" in str(exc_info.value)

    def test_register_backend_round_trip(self):
        """register_backend installs a new backend; get_backend finds it."""

        class FakeBackend(AcpBackend):
            @classmethod
            def name(cls) -> str:
                return "fake"

            def start_session(self, options):
                raise NotImplementedError

            def validate_provider(self, provider):
                return []

        # Use a unique key to avoid colliding with the production
        # "claude" registration. Clean up at the end so we don't
        # pollute the registry for other tests.
        register_backend("fake", FakeBackend)
        try:
            assert get_backend("fake") is FakeBackend
            assert "fake" in BACKENDS
            # And the convenience raise-variant doesn't blow up.
            assert get_backend_or_raise("fake") is FakeBackend
        finally:
            BACKENDS.pop("fake", None)

    def test_register_backend_rejects_non_abc_subclass(self):
        class NotABackend:
            pass

        with pytest.raises(TypeError):
            register_backend("bogus", NotABackend)  # type: ignore[arg-type]

    def test_register_backend_rejects_empty_name(self):
        class FakeBackend(AcpBackend):
            @classmethod
            def name(cls) -> str:
                return "f"

            def start_session(self, options):
                raise NotImplementedError

            def validate_provider(self, provider):
                return []

        with pytest.raises(ValueError):
            register_backend("", FakeBackend)


# ----------------------------------------------------------------------
# ABC contract
# ----------------------------------------------------------------------


class TestAcpBackendABC:
    """AcpBackend enforces the four-method contract through
    abc.abstractmethod — instantiating a subclass that forgets one of
    them should fail."""

    def test_full_subclass_is_instantiable(self):
        class FullBackend(AcpBackend):
            @classmethod
            def name(cls):
                return "full"

            def start_session(self, options):
                raise NotImplementedError

            def validate_provider(self, provider):
                return []

        b = FullBackend()
        assert isinstance(b, AcpBackend)
        assert b.name() == "full"

    def test_missing_start_session_unimplementable(self):
        class PartialBackend(AcpBackend):
            @classmethod
            def name(cls):
                return "partial"

            def validate_provider(self, provider):
                return []

        with pytest.raises(TypeError):
            PartialBackend()  # type: ignore[abstract]

    def test_missing_validate_provider_unimplementable(self):
        class PartialBackend(AcpBackend):
            @classmethod
            def name(cls):
                return "partial"

            def start_session(self, options):
                raise NotImplementedError

        with pytest.raises(TypeError):
            PartialBackend()  # type: ignore[abstract]


# ----------------------------------------------------------------------
# Claude backend specifics
# ----------------------------------------------------------------------


class TestClaudeAcpBackend:
    def test_name_returns_claude(self):
        assert ClaudeAcpBackend.name() == "claude"

    def test_validate_provider_returns_empty(self):
        """The Claude SDK relies on subscription auth, no api_key
        required at the provider level."""
        backend = ClaudeAcpBackend()
        provider = ModelProvider(
            id="p1", name="anthropic", base_url="https://api.anthropic.com",
            api_key="",  # empty — should still validate
        )
        assert backend.validate_provider(provider) == []


# ----------------------------------------------------------------------
# ModelProvider validate_for_mode
# ----------------------------------------------------------------------


class TestValidateProviderBackend:
    def test_acp_mode_default_backend_validates(self):
        """When backend is None in acp mode, it defaults to 'claude' and
        validates because claude is registered."""
        provider = ModelProvider(
            id="p1", name="x", base_url="", backend=None,
        )
        assert validate_provider_backend(provider, "acp") == []
        # Same outcome via the convenience method on ModelProvider.
        assert provider.validate_for_mode("acp") == []

    def test_acp_mode_explicit_claude_validates(self):
        provider = ModelProvider(
            id="p1", name="x", base_url="", backend="claude",
        )
        assert provider.validate_for_mode("acp") == []

    def test_acp_mode_unknown_backend_fails(self):
        """An unregistered backend name surfaces a clear error so the
        operator can fix their provider config."""
        provider = ModelProvider(
            id="p1", name="x", base_url="", backend="bogus-backend",
        )
        errors = provider.validate_for_mode("acp")
        assert len(errors) == 1
        msg = errors[0]
        # Error message must name the offending backend AND list the
        # registered backends so the operator can self-serve a fix.
        assert "bogus-backend" in msg
        assert "claude" in msg

    def test_api_mode_ignores_backend(self):
        """mode != 'acp' ignores the backend field entirely — even an
        invalid value passes validation because backend is unused."""
        provider = ModelProvider(
            id="p1", name="x", base_url="", backend="anything-goes",
        )
        assert provider.validate_for_mode("api") == []
        assert provider.validate_for_mode("cli") == []
        assert provider.validate_for_mode("auto") == []

    def test_fake_backend_after_registration_validates(self):
        class FakeBackend(AcpBackend):
            @classmethod
            def name(cls):
                return "fake-validate"

            def start_session(self, options):
                raise NotImplementedError

            def validate_provider(self, provider):
                return []

        register_backend("fake-validate", FakeBackend)
        try:
            provider = ModelProvider(
                id="p1", name="x", base_url="", backend="fake-validate",
            )
            assert provider.validate_for_mode("acp") == []
        finally:
            BACKENDS.pop("fake-validate", None)


# ----------------------------------------------------------------------
# ModelProvider.backend round-trip
# ----------------------------------------------------------------------


class TestModelProviderBackendRoundTrip:
    def test_default_backend_is_none(self):
        """Fresh-constructed providers default to backend=None (the
        registry resolves None → 'claude' at validate time, preserving
        back-compat for legacy providers on disk)."""
        p = ModelProvider(id="p1", name="x", base_url="")
        assert p.backend is None

    def test_to_dict_omits_none_backend(self):
        """When backend is None we don't emit the key — keeps the
        on-disk JSON tidy and lets older oompah versions read newer
        files without choking on an unknown field."""
        p = ModelProvider(id="p1", name="x", base_url="")
        d = p.to_dict()
        assert "backend" not in d

    def test_to_dict_emits_set_backend(self):
        p = ModelProvider(
            id="p1", name="x", base_url="", backend="claude",
        )
        d = p.to_dict()
        assert d["backend"] == "claude"

    def test_from_dict_missing_backend(self):
        """Existing providers persisted before this field existed read
        back as backend=None — preserving back-compat."""
        p = ModelProvider.from_dict({
            "id": "p1", "name": "x", "base_url": "",
        })
        assert p.backend is None
        # And the default-to-claude resolution kicks in at validate time.
        assert p.validate_for_mode("acp") == []

    def test_from_dict_with_backend(self):
        p = ModelProvider.from_dict({
            "id": "p1", "name": "x", "base_url": "", "backend": "claude",
        })
        assert p.backend == "claude"

    def test_round_trip_preserves_backend(self):
        original = ModelProvider(
            id="p1", name="x", base_url="", backend="claude",
        )
        roundtrip = ModelProvider.from_dict(original.to_dict())
        assert roundtrip.backend == "claude"

    def test_from_dict_strips_whitespace(self):
        p = ModelProvider.from_dict({
            "id": "p1", "name": "x", "base_url": "", "backend": "  claude  ",
        })
        assert p.backend == "claude"

    def test_to_safe_dict_includes_backend(self):
        p = ModelProvider(
            id="p1", name="x", base_url="", backend="claude",
        )
        sd = p.to_safe_dict()
        assert sd["backend"] == "claude"

    def test_from_dict_empty_backend_is_none(self):
        # Some on-disk records have backend="" (empty string) from
        # accidental UI submissions — treat as None to keep the
        # default-to-claude resolution intact.
        p = ModelProvider.from_dict({
            "id": "p1", "name": "x", "base_url": "", "backend": "",
        })
        assert p.backend is None


# ----------------------------------------------------------------------
# AcpBackendOptions + BackendEvent
# ----------------------------------------------------------------------


class TestBackendEvent:
    def test_event_carries_kind_and_payload(self):
        ev = BackendEvent(
            kind="text",
            payload={"text": "hello"},
            timestamp=12345.0,
            usage={"input_tokens": 10},
        )
        assert ev.kind == "text"
        assert ev.payload == {"text": "hello"}
        assert ev.timestamp == 12345.0
        assert ev.usage == {"input_tokens": 10}

    def test_event_default_payload_and_usage(self):
        ev = BackendEvent(kind="result")
        assert ev.payload == {}
        assert ev.usage == {}


class TestAcpBackendOptions:
    def test_options_carry_permission_mode(self):
        """permission_mode lives on options (not inside the Claude
        backend) so future backends can read the same field."""
        opt = AcpBackendOptions(
            workspace_path="/tmp/ws",
            prompt="do the thing",
            permission_mode="default",
        )
        assert opt.permission_mode == "default"

    def test_options_defaults(self):
        opt = AcpBackendOptions(workspace_path="/x", prompt="y")
        assert opt.model is None
        assert opt.fallback_model is None
        assert opt.max_turns is None
        assert opt.env is None
        assert opt.tool_catalog is None
        assert opt.permission_mode == "default"
        assert opt.on_event is None


# ----------------------------------------------------------------------
# Provider dialog UI: Backend dropdown
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


class TestProviderBackendDropdownUI:
    """Verifies the provider dialog has a Backend dropdown wired up to
    the registry endpoint, defaulting to ``claude`` and read-only when
    only one backend is registered (today's state — Child B opens up
    the second backend)."""

    @pytest.fixture
    def html(self) -> str:
        return _load_providers_html()

    def test_backend_select_present(self, html: str):
        # The provider dialog has a labeled select element for the
        # ACP backend choice.
        assert 'id="prov-backend"' in html
        # And a human-readable label points at it.
        assert 'for="prov-backend"' in html

    def test_backend_default_option_claude(self, html: str):
        # The pre-rendered dropdown has a static "claude" option so
        # the dialog opens correctly even if loadAcpBackends() never
        # completes (e.g. server temporarily down).
        assert re.search(
            r'<select id="prov-backend">.*?<option value="claude">claude</option>',
            html, re.DOTALL,
        )

    def test_backend_loader_fetches_endpoint(self, html: str):
        # The JavaScript loader points at the new endpoint.
        assert "/api/v1/acp-backends" in html
        assert "loadAcpBackends" in html

    def test_backend_dropdown_renders_dynamically(self, html: str):
        # renderBackendOptions() populates the select from the
        # acpBackends array, and is called from openProviderDialog().
        assert "renderBackendOptions" in html
        # The function disables the select when there's only one
        # backend registered (today's state).
        assert "acpBackends.length <= 1" in html

    def test_submit_provider_sends_backend(self, html: str):
        # submitProvider() includes the backend in the request body.
        # We look for the literal field name + the source DOM element.
        assert "prov-backend" in html
        assert re.search(
            r"backend:\s*document\.getElementById\(['\"]prov-backend['\"]\)",
            html,
        )

    def test_dialog_hint_mentions_acp(self, html: str):
        # The hint text under the dropdown explains that the field is
        # only meaningful for ACP-mode profiles.
        # Using a flexible regex because surrounding markup may shift.
        assert re.search(
            r"mode=acp", html
        )


# ----------------------------------------------------------------------
# ProviderStore: create/update preserve the backend field
# ----------------------------------------------------------------------


class TestProviderStoreBackendField:
    """The ProviderStore must accept and persist the backend field
    through both ``create`` and ``update``."""

    def test_create_with_backend(self, tmp_path):
        from oompah.providers import ProviderStore

        store = ProviderStore(path=str(tmp_path / "providers.json"))
        provider = store.create(
            name="anthropic",
            base_url="https://api.anthropic.com",
            api_key="sk-...",
            backend="claude",
        )
        assert provider.backend == "claude"

        # Round-trip through disk via a fresh ProviderStore reading
        # the file back.
        store2 = ProviderStore(path=str(tmp_path / "providers.json"))
        loaded = store2.get(provider.id)
        assert loaded is not None
        assert loaded.backend == "claude"

    def test_create_without_backend_defaults_to_none(self, tmp_path):
        from oompah.providers import ProviderStore

        store = ProviderStore(path=str(tmp_path / "providers.json"))
        provider = store.create(
            name="openai",
            base_url="https://api.openai.com/v1",
        )
        assert provider.backend is None

    def test_update_sets_backend(self, tmp_path):
        from oompah.providers import ProviderStore

        store = ProviderStore(path=str(tmp_path / "providers.json"))
        provider = store.create(name="x", base_url="")
        updated = store.update(provider.id, backend="claude")
        assert updated is not None
        assert updated.backend == "claude"

        # Persists across reloads.
        store2 = ProviderStore(path=str(tmp_path / "providers.json"))
        loaded = store2.get(provider.id)
        assert loaded is not None
        assert loaded.backend == "claude"

    def test_update_clears_backend_with_none(self, tmp_path):
        from oompah.providers import ProviderStore

        store = ProviderStore(path=str(tmp_path / "providers.json"))
        provider = store.create(name="x", base_url="", backend="claude")
        updated = store.update(provider.id, backend=None)
        assert updated is not None
        assert updated.backend is None

    def test_legacy_provider_json_without_backend_loads(self, tmp_path):
        """Existing on-disk providers persisted before this field
        existed must still round-trip cleanly."""
        import json

        path = tmp_path / "providers.json"
        # Hand-crafted legacy record — no backend field at all.
        path.write_text(json.dumps([
            {
                "id": "prov-legacy",
                "name": "Legacy Anthropic",
                "base_url": "https://api.anthropic.com",
                "api_key": "sk-...",
                "models": ["claude-sonnet-4-6"],
                "default_model": "claude-sonnet-4-6",
                "provider_type": "anthropic",
            },
        ]))

        from oompah.providers import ProviderStore

        store = ProviderStore(path=str(path))
        loaded = store.get("prov-legacy")
        assert loaded is not None
        # Field defaults to None — the default-to-claude resolution
        # in validate_for_mode kicks in at dispatch time.
        assert loaded.backend is None
        # And validation passes for acp mode (defaulting to claude).
        assert loaded.validate_for_mode("acp") == []
