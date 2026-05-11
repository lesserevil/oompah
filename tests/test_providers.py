"""Tests for oompah.providers."""

import json

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
# model_capabilities (oompah-zlz.2)
# ---------------------------------------------------------------------------

from oompah.models import ModelProvider


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
