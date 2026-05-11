"""Tests for oompah.providers."""

import json

import pytest
from oompah.models import ModelProvider
from oompah.providers import ProviderStore


class TestProviderStore:
    def test_create_and_get(self, tmp_path):
        path = str(tmp_path / "providers.json")
        store = ProviderStore(path=path)
        prov = store.create(name="test", base_url="http://localhost:8000")
        assert prov.id.startswith("prov-")
        assert prov.name == "test"
        assert prov.base_url == "http://localhost:8000"

        fetched = store.get(prov.id)
        assert fetched is not None
        assert fetched.name == "test"

    def test_list_all(self, tmp_path):
        path = str(tmp_path / "providers.json")
        store = ProviderStore(path=path)
        store.create(name="a", base_url="http://a")
        store.create(name="b", base_url="http://b")
        assert len(store.list_all()) == 2

    def test_update(self, tmp_path):
        path = str(tmp_path / "providers.json")
        store = ProviderStore(path=path)
        prov = store.create(name="test", base_url="http://old")
        updated = store.update(prov.id, base_url="http://new")
        assert updated is not None
        assert updated.base_url == "http://new"

    def test_update_strips_trailing_slash(self, tmp_path):
        path = str(tmp_path / "providers.json")
        store = ProviderStore(path=path)
        prov = store.create(name="test", base_url="http://x")
        updated = store.update(prov.id, base_url="http://new/")
        assert updated.base_url == "http://new"

    def test_update_nonexistent(self, tmp_path):
        path = str(tmp_path / "providers.json")
        store = ProviderStore(path=path)
        assert store.update("nonexistent", name="x") is None

    def test_delete(self, tmp_path):
        path = str(tmp_path / "providers.json")
        store = ProviderStore(path=path)
        prov = store.create(name="test", base_url="http://x")
        assert store.delete(prov.id) is True
        assert store.get(prov.id) is None
        assert store.delete(prov.id) is False

    def test_persistence(self, tmp_path):
        path = str(tmp_path / "providers.json")
        store1 = ProviderStore(path=path)
        prov = store1.create(name="persist", base_url="http://x", api_key="sk-123")

        # Reload from disk
        store2 = ProviderStore(path=path)
        fetched = store2.get(prov.id)
        assert fetched is not None
        assert fetched.name == "persist"
        assert fetched.api_key == "sk-123"

    def test_empty_file(self, tmp_path):
        path = str(tmp_path / "providers.json")
        store = ProviderStore(path=path)
        assert store.list_all() == []

    def test_get_default_single_provider(self, tmp_path):
        path = str(tmp_path / "providers.json")
        store = ProviderStore(path=path)
        prov = store.create(name="only", base_url="http://x")
        assert store.get_default() is prov

    def test_get_default_no_providers(self, tmp_path):
        path = str(tmp_path / "providers.json")
        store = ProviderStore(path=path)
        assert store.get_default() is None

    def test_get_default_multiple_providers(self, tmp_path):
        path = str(tmp_path / "providers.json")
        store = ProviderStore(path=path)
        store.create(name="a", base_url="http://a")
        store.create(name="b", base_url="http://b")
        assert store.get_default() is None


# ---------------------------------------------------------------------------
# model_roles reconciliation (oompah-zlz_2-wvn5)
#
# Tests for ModelProvider._reconcile_model_roles():
#   1. model still valid → no-op, empty list returned.
#   2. model missing + default_model valid → repoint to default_model.
#   3. model missing + default_model invalid + models[0] valid → repoint to first available.
#   4. model missing + models empty → WARNING, role left alone, empty list returned.
# ---------------------------------------------------------------------------

class TestReconcileModelRoles:
    def test_no_op_when_model_still_valid(self):
        """Constants in the body are untouched when they reference an existing model."""
        p = ModelProvider(
            id="p", name="Test", base_url="http://x",
            models=["gpt-4", "gpt-4o-mini"],
            default_model="gpt-4",
            model_roles={"fast": "gpt-4o-mini", "deep": "gpt-4"},
        )
        changed = p._reconcile_model_roles()
        assert changed == []
        assert p.model_roles == {"fast": "gpt-4o-mini", "deep": "gpt-4"}

    def test_repoint_to_default_model_when_missing(self, caplog):
        """When a role points at a missing model and default_model is in models[],
        the role is repointed to default_model."""
        import logging
        caplog.set_level(logging.INFO, "oompah.models")
        p = ModelProvider(
            id="p", name="Test", base_url="http://x",
            models=["gpt-4", "gpt-4o-mini"],
            default_model="gpt-4",
            model_roles={"fast": "gpt-4o-mini", "deep": "old-model"},
        )
        changed = p._reconcile_model_roles()
        assert changed == ["deep"]
        assert p.model_roles["deep"] == "gpt-4"
        assert p.model_roles["fast"] == "gpt-4o-mini"  # untouched
        assert any("repointed" in record.message and "deep" in record.message
                   for record in caplog.records)

    def test_repoint_to_first_available_when_default_also_invalid(self, caplog):
        """When default_model is missing too, repoint to the first entry in models[]."""
        import logging
        caplog.set_level(logging.INFO, "oompah.models")
        p = ModelProvider(
            id="p", name="Test", base_url="http://x",
            models=["gpt-4", "gpt-4o-mini", "claude-3"],
            default_model="missing-model",
            model_roles={"fast": "not-real", "deep": "also-not-real"},
        )
        changed = p._reconcile_model_roles()
        assert set(changed) == {"fast", "deep"}
        assert p.model_roles["fast"] == "gpt-4"
        assert p.model_roles["deep"] == "gpt-4"
        assert all("repointed" in record.message for record in caplog.records)

    def test_no_repoint_warning_when_no_fallback_available(self, caplog):
        """When models[] is empty, roles pointing at missing models are left alone
        and a WARNING is emitted (ACP / SDK-managed scenario)."""
        import logging
        caplog.set_level(logging.WARNING, "oompah.models")
        p = ModelProvider(
            id="p", name="Test", base_url="http://x",
            models=[],
            model_roles={"fast": "old-model"},
        )
        changed = p._reconcile_model_roles()
        assert changed == []
        assert p.model_roles["fast"] == "old-model"  # left alone
        assert any("empty models" in record.message and "fast" in record.message
                   for record in caplog.records)

    def test_no_op_when_model_roles_empty(self):
        p = ModelProvider(id="p", name="Test", base_url="http://x",
                          models=["gpt-4"], model_roles={})
        changed = p._reconcile_model_roles()
        assert changed == []
        assert p.model_roles == {}

    def test_empty_models_list_is_early_return(self):
        """Empty models[] with existing roles => WARNING but no change."""
        p = ModelProvider(
            id="p", name="Test", base_url="http://x",
            models=[],
            default_model="gpt-4",
            model_roles={"fast": "old-model"},
        )
        changed = p._reconcile_model_roles()
        assert changed == []


# ---------------------------------------------------------------------------
# ProviderStore reconciliation wiring (oompah-zlz_2-wvn5)
#
# Tests that the store calls _reconcile_model_roles() at the right moments:
#   - update() when models changes.
#   - _load() defensively on startup.
# ---------------------------------------------------------------------------

class TestProviderStoreReconciliation:
    def test_update_with_models_reconciles(self, tmp_path):
        """PATCH with models= triggers _reconcile_model_roles()."""
        from oompah.models import ModelProvider

        store = ProviderStore(path=str(tmp_path / "providers.json"))
        # Directly build a provider with a stale role (store.create() doesn't
        # accept model_roles).
        provider = ModelProvider(
            id="prov-reconcile",
            name="Test",
            base_url="http://x",
            models=["gpt-4", "gpt-4o-mini"],
            default_model="gpt-4",
            model_roles={"fast": "missing-model"},
        )
        store._providers["prov-reconcile"] = provider
        store._save()

        # PATCH removes "gpt-4o-mini" from models[], so "fast" → orphan.
        updated = store.update("prov-reconcile", models=["gpt-4"])
        assert updated is not None
        assert updated.model_roles["fast"] == "gpt-4"

    def test_update_without_models_does_not_reconcile(self, tmp_path):
        """PATCH without models= in fields does NOT trigger reconciliation."""
        from oompah.models import ModelProvider

        store = ProviderStore(path=str(tmp_path / "providers2.json"))
        # Build provider with a valid role.
        provider = ModelProvider(
            id="prov-reconcile2",
            name="Test",
            base_url="http://x",
            models=["gpt-4"],
            model_roles={"fast": "gpt-4"},
        )
        store._providers["prov-reconcile2"] = provider
        store._save()

        # Update a field OTHER than models — reconciliation should NOT fire.
        updated = store.update("prov-reconcile2", name="Renamed")
        assert updated is not None
        assert updated.name == "Renamed"
        assert updated.model_roles["fast"] == "gpt-4"  # untouched

    def test_load_reconciles_stale_roles_on_startup(self, tmp_path, caplog):
        """ProviderStore._load() defensively reconciles every provider at startup."""
        path = tmp_path / "providers_drift.json"
        # Write a providers.json with a stale role pointer.
        with open(path, "w") as f:
            json.dump([{
                "id": "prov-drift",
                "name": "Drifty",
                "base_url": "http://x",
                "models": ["gpt-4", "gpt-4o-mini"],
                "default_model": "gpt-4",
                "model_roles": {"fast": "gpt-4", "deep": "deleted-model"},
            }], f)

        # Simulate a fresh load (what happens on oompah startup).
        store = ProviderStore(path=str(path))
        provider = store.get("prov-drift")
        assert provider is not None
        assert provider.model_roles["deep"] == "gpt-4"  # self-healed
        assert provider.model_roles["fast"] == "gpt-4"


# ---------------------------------------------------------------------------
# model_capabilities (oompah-zlz.2)
# ---------------------------------------------------------------------------

class TestModelCapabilities:
    def test_default_empty(self):
        p = ModelProvider(id="p", name="n", base_url="http://x")
        assert p.model_capabilities == {}

    def test_round_trip(self):
        p = ModelProvider(
            id="p", name="n", base_url="http://x",
            model_capabilities={"gpt-4o-mini": ["text", "image"],
                                "nemotron-omni": ["text", "image", "audio"]},
        )
        d = p.to_dict()
        assert d["model_capabilities"]["gpt-4o-mini"] == ["text", "image"]
        p2 = ModelProvider.from_dict(d)
        assert p2.model_capabilities == p.model_capabilities

    def test_omitted_when_empty(self):
        p = ModelProvider(id="p", name="n", base_url="http://x")
        assert "model_capabilities" not in p.to_dict()

    def test_from_dict_normalizes_values(self):
        # Ensures lists of non-strings are coerced to lists of strings.
        p = ModelProvider.from_dict({
            "id": "p", "name": "n", "base_url": "http://x",
            "model_capabilities": {"m": ["text", 123]},
        })
        assert p.model_capabilities == {"m": ["text", "123"]}


# ---------------------------------------------------------------------------
# ACP-mode provider records (oompah-zlz_2-keb)
#
# Cover the new ModelProvider.mode / acp_permission_mode /
# acp_subscription_only fields end-to-end:
#   - default values preserve the legacy "api" mode.
#   - to_dict / from_dict round-trip without dropping fields.
#   - ProviderStore.create() accepts the new params.
#   - ProviderStore.update() flips mode and persists.
#   - bad mode values are normalized to "api" (defensive).
# ---------------------------------------------------------------------------


class TestProviderAcpFields:
    def test_default_mode_is_api(self):
        p = ModelProvider(id="p", name="n", base_url="http://x")
        assert p.mode == "api"
        assert p.acp_permission_mode is None
        assert p.acp_subscription_only is False

    def test_to_dict_emits_mode_field(self):
        # mode is always emitted so the dashboard can rely on it.
        p = ModelProvider(id="p", name="n", base_url="http://x")
        d = p.to_dict()
        assert d["mode"] == "api"

    def test_to_dict_omits_acp_fields_in_api_mode(self):
        p = ModelProvider(id="p", name="n", base_url="http://x")
        d = p.to_dict()
        assert "acp_permission_mode" not in d
        assert "acp_subscription_only" not in d

    def test_acp_provider_round_trip(self):
        p = ModelProvider(
            id="p", name="acp-default",
            base_url="",
            api_key="",
            mode="acp",
            acp_permission_mode="acceptEdits",
            acp_subscription_only=True,
        )
        d = p.to_dict()
        assert d["mode"] == "acp"
        assert d["acp_permission_mode"] == "acceptEdits"
        assert d["acp_subscription_only"] is True
        p2 = ModelProvider.from_dict(d)
        assert p2.mode == "acp"
        assert p2.acp_permission_mode == "acceptEdits"
        assert p2.acp_subscription_only is True
        assert p2.base_url == ""
        assert p2.api_key == ""

    def test_from_dict_normalizes_bad_mode_to_api(self):
        # A typo or future-mode flag must not silently bypass the
        # budget gate by acting as ACP. Anything outside {"api","acp"}
        # falls back to "api".
        p = ModelProvider.from_dict({
            "id": "p", "name": "n", "base_url": "http://x",
            "mode": "WAT",
        })
        assert p.mode == "api"

    def test_from_dict_normalizes_mode_case(self):
        p = ModelProvider.from_dict({
            "id": "p", "name": "n", "base_url": "http://x",
            "mode": "ACP",
        })
        assert p.mode == "acp"

    def test_from_dict_treats_empty_permission_mode_as_none(self):
        p = ModelProvider.from_dict({
            "id": "p", "name": "n", "base_url": "http://x",
            "mode": "acp",
            "acp_permission_mode": "",
        })
        assert p.acp_permission_mode is None

    def test_store_create_acp_provider(self, tmp_path):
        path = str(tmp_path / "providers.json")
        store = ProviderStore(path=path)
        p = store.create(
            name="acp-default",
            base_url="",
            mode="acp",
            acp_permission_mode="default",
            acp_subscription_only=True,
        )
        assert p.mode == "acp"
        assert p.acp_permission_mode == "default"
        assert p.acp_subscription_only is True

        # Reload from disk and confirm the fields survived.
        store2 = ProviderStore(path=path)
        fetched = store2.get(p.id)
        assert fetched is not None
        assert fetched.mode == "acp"
        assert fetched.acp_permission_mode == "default"
        assert fetched.acp_subscription_only is True

    def test_store_create_default_is_api(self, tmp_path):
        path = str(tmp_path / "providers.json")
        store = ProviderStore(path=path)
        p = store.create(name="legacy", base_url="http://x")
        assert p.mode == "api"

    def test_store_update_flips_mode(self, tmp_path):
        path = str(tmp_path / "providers.json")
        store = ProviderStore(path=path)
        p = store.create(name="legacy", base_url="http://x", api_key="sk-1")
        updated = store.update(
            p.id,
            mode="acp",
            acp_permission_mode="bypassPermissions",
            acp_subscription_only=True,
        )
        assert updated is not None
        assert updated.mode == "acp"
        assert updated.acp_permission_mode == "bypassPermissions"
        assert updated.acp_subscription_only is True

    def test_store_update_normalizes_bad_mode(self, tmp_path):
        path = str(tmp_path / "providers.json")
        store = ProviderStore(path=path)
        p = store.create(name="legacy", base_url="http://x")
        updated = store.update(p.id, mode="garbage")
        assert updated is not None
        assert updated.mode == "api"


# ---------------------------------------------------------------------------
# /api/v1/providers ACP-aware validation (oompah-zlz_2-keb)
#
# Covers the ACP-aware validation rules in the create / update endpoints:
#   - api-mode requires base_url (legacy regression preserved).
#   - acp-mode does NOT require base_url or api_key.
#   - PATCH from acp -> api with no base_url is rejected.
# ---------------------------------------------------------------------------

import json
from unittest.mock import patch as _mock_patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def api_client(tmp_path):
    """Return a FastAPI TestClient bound to a temp ProviderStore.

    Patches the module-level _provider_store singleton so the create/
    update endpoints write into the tmp_path directory and the test
    is hermetic.
    """
    from oompah import server as _srv
    from oompah.providers import ProviderStore

    fresh = ProviderStore(path=str(tmp_path / "providers.json"))
    with _mock_patch.object(_srv, "_provider_store", fresh):
        yield TestClient(_srv.app)


class TestProviderApiValidation:
    def test_create_api_without_base_url_rejected(self, api_client):
        # Regression: api-mode (the default) still requires base_url.
        r = api_client.post(
            "/api/v1/providers",
            json={"name": "x"},
        )
        assert r.status_code == 400
        assert "base_url" in r.json()["error"]["message"]

    def test_create_api_explicit_mode_without_base_url_rejected(self, api_client):
        r = api_client.post(
            "/api/v1/providers",
            json={"name": "x", "mode": "api"},
        )
        assert r.status_code == 400

    def test_create_acp_without_base_url_succeeds(self, api_client):
        r = api_client.post(
            "/api/v1/providers",
            json={
                "name": "claude-sub",
                "mode": "acp",
                "acp_permission_mode": "default",
                "acp_subscription_only": True,
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["mode"] == "acp"
        assert body["acp_permission_mode"] == "default"
        assert body["acp_subscription_only"] is True

    def test_create_acp_without_api_key_succeeds(self, api_client):
        # api_key omitted entirely — the Claude Agent SDK manages auth.
        r = api_client.post(
            "/api/v1/providers",
            json={"name": "claude-sub", "mode": "acp"},
        )
        assert r.status_code == 201

    def test_create_without_name_rejected(self, api_client):
        r = api_client.post("/api/v1/providers", json={"mode": "acp"})
        assert r.status_code == 400

    def test_get_returns_mode_field(self, api_client):
        # Round-trip the new fields through GET /api/v1/providers.
        api_client.post(
            "/api/v1/providers",
            json={"name": "claude-sub", "mode": "acp",
                  "acp_permission_mode": "plan",
                  "acp_subscription_only": True},
        )
        r = api_client.get("/api/v1/providers")
        assert r.status_code == 200
        rows = r.json()
        assert any(p.get("mode") == "acp" for p in rows)
        # Make sure the new fields are present in the safe-dict response.
        acp_row = next(p for p in rows if p["mode"] == "acp")
        assert acp_row["acp_permission_mode"] == "plan"
        assert acp_row["acp_subscription_only"] is True

    def test_patch_flip_api_to_acp_succeeds(self, api_client):
        # Existing API provider can be flipped to ACP.
        r = api_client.post(
            "/api/v1/providers",
            json={"name": "legacy", "base_url": "http://x"},
        )
        pid = r.json()["id"]
        r2 = api_client.patch(
            f"/api/v1/providers/{pid}",
            json={"mode": "acp", "acp_permission_mode": "default",
                  "acp_subscription_only": True},
        )
        assert r2.status_code == 200, r2.text
        assert r2.json()["mode"] == "acp"

    def test_patch_flip_acp_to_api_without_base_url_rejected(self, api_client):
        # Flipping back to api with no stored base_url must be rejected
        # so we don't end up with a non-functional api provider.
        r = api_client.post(
            "/api/v1/providers",
            json={"name": "claude-sub", "mode": "acp"},
        )
        pid = r.json()["id"]
        r2 = api_client.patch(
            f"/api/v1/providers/{pid}",
            json={"mode": "api"},
        )
        assert r2.status_code == 400
        assert "base_url" in r2.json()["error"]["message"]

    def test_patch_flip_acp_to_api_with_base_url_succeeds(self, api_client):
        r = api_client.post(
            "/api/v1/providers",
            json={"name": "claude-sub", "mode": "acp"},
        )
        pid = r.json()["id"]
        r2 = api_client.patch(
            f"/api/v1/providers/{pid}",
            json={"mode": "api", "base_url": "http://y"},
        )
        assert r2.status_code == 200
        assert r2.json()["mode"] == "api"
        assert r2.json()["base_url"] == "http://y"

    def test_patch_update_acp_fields_only(self, api_client):
        r = api_client.post(
            "/api/v1/providers",
            json={"name": "claude-sub", "mode": "acp",
                  "acp_permission_mode": "default"},
        )
        pid = r.json()["id"]
        r2 = api_client.patch(
            f"/api/v1/providers/{pid}",
            json={"acp_permission_mode": "plan"},
        )
        assert r2.status_code == 200
        assert r2.json()["acp_permission_mode"] == "plan"
        assert r2.json()["mode"] == "acp"
