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
