"""Tests for oompah.roles."""

import json
import logging
from datetime import datetime, timezone

import pytest

from oompah.models import AgentProfile, ModelProvider
from oompah.providers import ProviderStore
from oompah.roles import (
    Candidate,
    Role,
    RoleError,
    RoleStore,
    VALID_STRATEGIES,
    DEFAULT_STRATEGY,
)


# ---------------------------------------------------------------------------
# Candidate serialization
# ---------------------------------------------------------------------------


class TestCandidateSerialization:
    def test_to_dict(self):
        c = Candidate(provider_id="prov-1", model="gpt-4o")
        assert c.to_dict() == {"provider_id": "prov-1", "model": "gpt-4o"}

    def test_from_dict(self):
        c = Candidate.from_dict({"provider_id": "prov-1", "model": "gpt-4o"})
        assert c.provider_id == "prov-1"
        assert c.model == "gpt-4o"

    def test_from_dict_missing_fields(self):
        c = Candidate.from_dict({})
        assert c.provider_id == ""
        assert c.model == ""

    def test_equality(self):
        c1 = Candidate(provider_id="p1", model="m1")
        c2 = Candidate(provider_id="p1", model="m1")
        assert c1 == c2

    def test_inequality(self):
        c1 = Candidate(provider_id="p1", model="m1")
        c2 = Candidate(provider_id="p1", model="m2")
        assert c1 != c2

    def test_hashable(self):
        c1 = Candidate(provider_id="p1", model="m1")
        c2 = Candidate(provider_id="p1", model="m1")
        assert hash(c1) == hash(c2)
        assert len({c1, c2}) == 1


# ---------------------------------------------------------------------------
# Role.to_dict / from_dict round-trip (new schema)
# ---------------------------------------------------------------------------


class TestRoleSerialization:
    def test_round_trip_single_candidate(self):
        now = datetime.now(timezone.utc)
        candidates = [Candidate(provider_id="prov-1", model="gpt-4o")]
        r = Role(name="fast", strategy="priority", candidates=candidates, updated_at=now)
        d = r.to_dict()
        assert d == {
            "name": "fast",
            "strategy": "priority",
            "candidates": [{"provider_id": "prov-1", "model": "gpt-4o"}],
            "updated_at": now.isoformat(),
        }
        r2 = Role.from_dict(d)
        assert r2.name == r.name
        assert r2.strategy == r.strategy
        assert r2.candidates == r.candidates
        assert r2.updated_at == r.updated_at

    def test_round_trip_multi_candidate(self):
        now = datetime.now(timezone.utc)
        candidates = [
            Candidate(provider_id="prov-1", model="gpt-4o"),
            Candidate(provider_id="prov-2", model="claude-3"),
        ]
        r = Role(name="deep", strategy="round_robin", candidates=candidates, updated_at=now)
        d = r.to_dict()
        r2 = Role.from_dict(d)
        assert r2.name == "deep"
        assert r2.strategy == "round_robin"
        assert len(r2.candidates) == 2
        assert r2.candidates[0] == Candidate(provider_id="prov-1", model="gpt-4o")
        assert r2.candidates[1] == Candidate(provider_id="prov-2", model="claude-3")

    def test_to_dict_does_not_include_old_provider_id_model(self):
        """to_dict() writes new schema (strategy + candidates), not old flat fields."""
        now = datetime.now(timezone.utc)
        r = Role(
            name="fast",
            strategy="priority",
            candidates=[Candidate(provider_id="prov-1", model="gpt-4o")],
            updated_at=now,
        )
        d = r.to_dict()
        assert "candidates" in d
        assert "strategy" in d
        # Old flat fields should NOT appear at the top level in saved data.
        assert "provider_id" not in d
        assert "model" not in d

    def test_from_dict_missing_updated_at(self):
        r = Role.from_dict({
            "name": "x",
            "strategy": "priority",
            "candidates": [{"provider_id": "p", "model": "m"}],
        })
        assert r.name == "x"
        assert r.updated_at is not None  # defaults to now()

    def test_from_dict_bad_updated_at(self):
        r = Role.from_dict({
            "name": "x",
            "strategy": "priority",
            "candidates": [{"provider_id": "p", "model": "m"}],
            "updated_at": "garbage",
        })
        assert r.updated_at is not None  # defaults to now()

    def test_from_dict_datetime_object(self):
        now = datetime.now(timezone.utc)
        r = Role.from_dict({
            "name": "x",
            "strategy": "priority",
            "candidates": [{"provider_id": "p", "model": "m"}],
            "updated_at": now,
        })
        assert r.updated_at == now

    def test_from_dict_invalid_strategy_defaults_to_priority(self):
        """Unknown strategy in persisted data defaults to 'priority' for robustness."""
        r = Role.from_dict({
            "name": "x",
            "strategy": "unknown_strategy",
            "candidates": [{"provider_id": "p", "model": "m"}],
        })
        assert r.strategy == "priority"

    def test_from_dict_empty_candidates_list(self):
        """Empty candidates list in new format yields empty candidates (not an error at load)."""
        r = Role.from_dict({
            "name": "x",
            "strategy": "priority",
            "candidates": [],
        })
        assert r.candidates == []

    def test_from_dict_skips_non_dict_candidates(self):
        """Non-dict entries in candidates are skipped."""
        r = Role.from_dict({
            "name": "x",
            "strategy": "priority",
            "candidates": [{"provider_id": "p", "model": "m"}, "bad", 42],
        })
        assert len(r.candidates) == 1


# ---------------------------------------------------------------------------
# Backward compatibility: old single-candidate schema
# ---------------------------------------------------------------------------


class TestRoleBackwardCompatibility:
    def test_from_dict_old_format_becomes_priority_role(self):
        """Old provider_id/model at top level loads as a 1-candidate priority role."""
        r = Role.from_dict({
            "name": "fast",
            "provider_id": "prov-1",
            "model": "gpt-4o",
            "updated_at": "2025-01-01T00:00:00+00:00",
        })
        assert r.name == "fast"
        assert r.strategy == "priority"
        assert len(r.candidates) == 1
        assert r.candidates[0].provider_id == "prov-1"
        assert r.candidates[0].model == "gpt-4o"

    def test_from_dict_old_format_missing_updated_at(self):
        r = Role.from_dict({"name": "x", "provider_id": "p", "model": "m"})
        assert r.name == "x"
        assert r.updated_at is not None

    def test_from_dict_old_format_bad_updated_at(self):
        r = Role.from_dict({"name": "x", "provider_id": "p", "model": "m", "updated_at": "garbage"})
        assert r.updated_at is not None

    def test_from_dict_old_format_datetime_object(self):
        now = datetime.now(timezone.utc)
        r = Role.from_dict({"name": "x", "provider_id": "p", "model": "m", "updated_at": now})
        assert r.updated_at == now

    def test_provider_id_property_returns_first_candidate(self):
        """role.provider_id is a property delegating to candidates[0]."""
        r = Role(
            name="fast",
            strategy="priority",
            candidates=[
                Candidate(provider_id="prov-1", model="gpt-4o"),
                Candidate(provider_id="prov-2", model="claude-3"),
            ],
            updated_at=datetime.now(timezone.utc),
        )
        assert r.provider_id == "prov-1"

    def test_model_property_returns_first_candidate(self):
        """role.model is a property delegating to candidates[0]."""
        r = Role(
            name="fast",
            strategy="priority",
            candidates=[
                Candidate(provider_id="prov-1", model="gpt-4o"),
                Candidate(provider_id="prov-2", model="claude-3"),
            ],
            updated_at=datetime.now(timezone.utc),
        )
        assert r.model == "gpt-4o"

    def test_provider_id_property_empty_candidates(self):
        r = Role(name="x", strategy="priority", candidates=[], updated_at=datetime.now(timezone.utc))
        assert r.provider_id == ""

    def test_model_property_empty_candidates(self):
        r = Role(name="x", strategy="priority", candidates=[], updated_at=datetime.now(timezone.utc))
        assert r.model == ""

    def test_load_old_format_from_file(self, tmp_path):
        """Loading an old roles.json with provider_id/model at top level succeeds."""
        path = str(tmp_path / "roles.json")
        with open(path, "w") as f:
            json.dump([
                {
                    "name": "fast",
                    "provider_id": "prov-1",
                    "model": "gpt-4o",
                    "updated_at": "2025-01-01T00:00:00+00:00",
                }
            ], f)
        store = RoleStore(path=path)
        role = store.get("fast")
        assert role is not None
        assert role.strategy == "priority"
        assert len(role.candidates) == 1
        assert role.provider_id == "prov-1"  # compat property
        assert role.model == "gpt-4o"  # compat property

    def test_save_after_loading_old_format_writes_new_schema(self, tmp_path):
        """After loading old format and saving, the file contains the new schema."""
        path = str(tmp_path / "roles.json")
        with open(path, "w") as f:
            json.dump([
                {"name": "fast", "provider_id": "prov-1", "model": "gpt-4o"},
            ], f)
        store = RoleStore(path=path)
        # Trigger a save by setting any role.
        store.set("fast", "prov-1", "gpt-4o")
        with open(path) as f:
            data = json.load(f)
        assert isinstance(data, list)
        assert data[0]["strategy"] == "priority"
        assert "candidates" in data[0]
        assert data[0]["candidates"][0] == {"provider_id": "prov-1", "model": "gpt-4o"}
        # Old flat fields should NOT be in the saved file.
        assert "provider_id" not in data[0]
        assert "model" not in data[0]


# ---------------------------------------------------------------------------
# CRUD basics (without provider validation — provider_store=None)
# ---------------------------------------------------------------------------


class TestRoleStoreCRUD:
    def test_set_and_get(self, tmp_path):
        path = str(tmp_path / "roles.json")
        store = RoleStore(path=path)
        r = store.set("fast", "prov-1", "gpt-4o")
        assert r.name == "fast"
        assert r.strategy == "priority"
        assert len(r.candidates) == 1
        assert store.get("fast") is not None
        assert store.get("missing") is None

    def test_set_persists(self, tmp_path):
        path = str(tmp_path / "roles.json")
        store = RoleStore(path=path)
        store.set("fast", "prov-1", "gpt-4o")
        # Reopen
        store2 = RoleStore(path=path)
        assert store2.get("fast") is not None
        assert store2.get("fast").provider_id == "prov-1"

    def test_list_all(self, tmp_path):
        path = str(tmp_path / "roles.json")
        store = RoleStore(path=path)
        store.set("fast", "prov-1", "gpt-4o")
        store.set("deep", "prov-2", "claude-3")
        assert {r.name for r in store.list_all()} == {"fast", "deep"}

    def test_set_updates_existing(self, tmp_path):
        path = str(tmp_path / "roles.json")
        store = RoleStore(path=path)
        store.set("fast", "prov-1", "gpt-4o")
        updated = store.set("fast", "prov-2", "gpt-4")
        assert updated.provider_id == "prov-2"
        assert updated.model == "gpt-4"
        assert len(store.list_all()) == 1

    def test_delete(self, tmp_path):
        path = str(tmp_path / "roles.json")
        store = RoleStore(path=path)
        store.set("fast", "prov-1", "gpt-4o")
        assert store.delete("fast") is True
        assert store.get("fast") is None
        assert store.delete("fast") is False

    def test_is_empty(self, tmp_path):
        path = str(tmp_path / "roles.json")
        store = RoleStore(path=path)
        assert store.is_empty is True
        store.set("fast", "prov-1", "gpt-4o")
        assert store.is_empty is False


# ---------------------------------------------------------------------------
# set_candidates — multi-candidate API
# ---------------------------------------------------------------------------


class TestRoleStoreSetCandidates:
    def test_set_candidates_priority(self, tmp_path):
        path = str(tmp_path / "roles.json")
        store = RoleStore(path=path)
        candidates = [
            Candidate(provider_id="prov-1", model="gpt-4o"),
            Candidate(provider_id="prov-2", model="claude-3"),
        ]
        role = store.set_candidates("fast", "priority", candidates)
        assert role.name == "fast"
        assert role.strategy == "priority"
        assert len(role.candidates) == 2

    def test_set_candidates_round_robin(self, tmp_path):
        path = str(tmp_path / "roles.json")
        store = RoleStore(path=path)
        candidates = [
            Candidate(provider_id="prov-1", model="gpt-4o"),
            Candidate(provider_id="prov-2", model="claude-3"),
        ]
        role = store.set_candidates("fast", "round_robin", candidates)
        assert role.strategy == "round_robin"

    def test_set_candidates_persists(self, tmp_path):
        path = str(tmp_path / "roles.json")
        store = RoleStore(path=path)
        candidates = [
            Candidate(provider_id="prov-1", model="gpt-4o"),
            Candidate(provider_id="prov-2", model="claude-3"),
        ]
        store.set_candidates("fast", "round_robin", candidates)
        store2 = RoleStore(path=path)
        role = store2.get("fast")
        assert role is not None
        assert role.strategy == "round_robin"
        assert len(role.candidates) == 2

    def test_set_candidates_fires_reload_callback(self, tmp_path):
        path = str(tmp_path / "roles.json")
        calls = []
        store = RoleStore(path=path, reload_callback=lambda d, s: calls.append(s))
        store.set_candidates("fast", "priority", [Candidate("prov-1", "gpt-4o")])
        assert calls == ["set"]

    def test_set_candidates_empty_list_rejected(self, tmp_path):
        path = str(tmp_path / "roles.json")
        store = RoleStore(path=path)
        with pytest.raises(RoleError, match="non-empty"):
            store.set_candidates("fast", "priority", [])

    def test_set_candidates_invalid_strategy_rejected(self, tmp_path):
        path = str(tmp_path / "roles.json")
        store = RoleStore(path=path)
        with pytest.raises(RoleError, match="strategy"):
            store.set_candidates("fast", "bad_strategy", [Candidate("prov-1", "gpt-4o")])

    def test_set_candidates_duplicate_rejected(self, tmp_path):
        path = str(tmp_path / "roles.json")
        store = RoleStore(path=path)
        candidates = [
            Candidate(provider_id="prov-1", model="gpt-4o"),
            Candidate(provider_id="prov-1", model="gpt-4o"),  # duplicate
        ]
        with pytest.raises(RoleError, match="duplicate"):
            store.set_candidates("fast", "priority", candidates)

    def test_set_candidates_empty_name_rejected(self, tmp_path):
        path = str(tmp_path / "roles.json")
        store = RoleStore(path=path)
        with pytest.raises(RoleError, match="name"):
            store.set_candidates("", "priority", [Candidate("prov-1", "gpt-4o")])

    def test_set_candidates_with_provider_store_validates_each_candidate(self, tmp_path):
        """When provider_store is set, each candidate is validated."""
        path = str(tmp_path / "roles.json")
        prov_store = ProviderStore(path=str(tmp_path / "providers.json"))
        prov_store.create(name="test", base_url="http://x", models=["gpt-4", "gpt-4o"])
        store = RoleStore(path=path, provider_store=prov_store)
        prov = prov_store.get_default()
        candidates = [
            Candidate(provider_id=prov.id, model="gpt-4"),
            Candidate(provider_id=prov.id, model="gpt-4o"),
        ]
        role = store.set_candidates("fast", "priority", candidates)
        assert role.name == "fast"

    def test_set_candidates_with_provider_store_rejects_unknown_provider(self, tmp_path):
        """With provider_store, unknown provider_id in any candidate is rejected."""
        path = str(tmp_path / "roles.json")
        prov_store = ProviderStore(path=str(tmp_path / "providers.json"))
        store = RoleStore(path=path, provider_store=prov_store)
        with pytest.raises(RoleError, match="does not exist"):
            store.set_candidates(
                "fast",
                "priority",
                [Candidate(provider_id="nonexistent", model="gpt-4o")],
            )

    def test_set_candidates_with_provider_store_rejects_bad_model(self, tmp_path):
        """With provider_store, a model not in catalog is rejected."""
        path = str(tmp_path / "roles.json")
        prov_store = ProviderStore(path=str(tmp_path / "providers.json"))
        prov_store.create(name="test", base_url="http://x", models=["gpt-4"])
        store = RoleStore(path=path, provider_store=prov_store)
        prov = prov_store.get_default()
        with pytest.raises(RoleError, match="not in provider"):
            store.set_candidates(
                "fast",
                "priority",
                [Candidate(provider_id=prov.id, model="gpt-4o-mini")],
            )


# ---------------------------------------------------------------------------
# Snapshot / Restore
# ---------------------------------------------------------------------------


class TestRoleStoreSnapshotRestore:
    def test_snapshot_returns_copy(self, tmp_path):
        path = str(tmp_path / "roles.json")
        store = RoleStore(path=path)
        store.set("fast", "prov-1", "gpt-4o")
        snap = store.snapshot()
        # Mutating snapshot does not affect store
        del snap["fast"]
        assert store.get("fast") is not None

    def test_restore_replaces_store(self, tmp_path):
        path = str(tmp_path / "roles.json")
        store = RoleStore(path=path)
        store.set("fast", "prov-1", "gpt-4o")
        store.set("deep", "prov-2", "claude-3")
        snap = store.snapshot()
        # Change the store
        store.set("fast", "prov-1", "gpt-4")
        store.delete("deep")
        # Restore
        store.restore(snap)
        assert len(store.list_all()) == 2
        assert store.get("fast").model == "gpt-4o"
        assert store.get("deep") is not None

    def test_snapshot_empty_store(self, tmp_path):
        path = str(tmp_path / "roles.json")
        store = RoleStore(path=path)
        snap = store.snapshot()
        assert snap == {}
        store.restore(snap)
        assert store.list_all() == []

    def test_snapshot_preserves_strategy_and_candidates(self, tmp_path):
        """Snapshot deep-copies strategy and candidates."""
        path = str(tmp_path / "roles.json")
        store = RoleStore(path=path)
        candidates = [
            Candidate(provider_id="prov-1", model="gpt-4o"),
            Candidate(provider_id="prov-2", model="claude-3"),
        ]
        store.set_candidates("fast", "round_robin", candidates)
        snap = store.snapshot()
        role = snap["fast"]
        assert role.strategy == "round_robin"
        assert len(role.candidates) == 2
        # Mutate the snapshot's candidate list — store must be unaffected.
        role.candidates.clear()
        assert len(store.get("fast").candidates) == 2

    def test_restore_preserves_multi_candidate(self, tmp_path):
        """Restore keeps multi-candidate roles intact."""
        path = str(tmp_path / "roles.json")
        store = RoleStore(path=path)
        candidates = [
            Candidate(provider_id="prov-1", model="gpt-4o"),
            Candidate(provider_id="prov-2", model="claude-3"),
        ]
        store.set_candidates("fast", "round_robin", candidates)
        snap = store.snapshot()
        store.delete("fast")
        store.restore(snap)
        role = store.get("fast")
        assert role is not None
        assert role.strategy == "round_robin"
        assert len(role.candidates) == 2


# ---------------------------------------------------------------------------
# Validation (with provider_store)
# ---------------------------------------------------------------------------


class TestRoleStoreValidation:
    def test_validate_empty_name(self, tmp_path):
        path = str(tmp_path / "roles.json")
        store = RoleStore(path=path)
        with pytest.raises(RoleError, match="non-empty"):
            store.set("", "prov-1", "gpt-4o")

    def test_validate_empty_provider_id(self, tmp_path):
        path = str(tmp_path / "roles.json")
        store = RoleStore(path=path)
        with pytest.raises(RoleError, match="provider_id"):
            store.set("fast", "", "gpt-4o")

    def test_validate_empty_model(self, tmp_path):
        path = str(tmp_path / "roles.json")
        store = RoleStore(path=path)
        with pytest.raises(RoleError, match="model"):
            store.set("fast", "prov-1", "")

    def test_validate_provider_not_found(self, tmp_path):
        path = str(tmp_path / "roles.json")
        prov_store = ProviderStore(path=str(tmp_path / "providers.json"))
        store = RoleStore(path=path, provider_store=prov_store)
        with pytest.raises(RoleError, match="does not exist"):
            store.set("fast", "prov-nonexistent", "gpt-4o")

    def test_validate_model_not_in_catalog(self, tmp_path):
        path = str(tmp_path / "roles.json")
        prov_store = ProviderStore(path=str(tmp_path / "providers.json"))
        prov_store.create(name="test", base_url="http://x", models=["gpt-4", "gpt-4o"])
        store = RoleStore(path=path, provider_store=prov_store)
        # Get the provider ID
        prov = prov_store.get_default()
        with pytest.raises(RoleError, match="not in provider"):
            store.set("fast", prov.id, "gpt-4o-mini")

    def test_validate_model_in_catalog(self, tmp_path):
        path = str(tmp_path / "roles.json")
        prov_store = ProviderStore(path=str(tmp_path / "providers.json"))
        prov_store.create(name="test", base_url="http://x", models=["gpt-4", "gpt-4o"])
        store = RoleStore(path=path, provider_store=prov_store)
        prov = prov_store.get_default()
        r = store.set("fast", prov.id, "gpt-4")
        assert r.name == "fast"

    def test_validate_acp_provider_empty_catalog(self, tmp_path):
        """ACP-mode provider with empty catalog accepts any model."""
        path = str(tmp_path / "roles.json")
        prov_store = ProviderStore(path=str(tmp_path / "providers.json"))
        prov_store.create(name="acp-test", base_url="", mode="acp")
        store = RoleStore(path=path, provider_store=prov_store)
        prov = prov_store.get_default()
        r = store.set("fast", prov.id, "claude-3-5-sonnet")
        assert r.name == "fast"

    def test_validate_acp_provider_non_empty_catalog(self, tmp_path):
        """ACP-mode provider with non-empty catalog still validates model."""
        path = str(tmp_path / "roles.json")
        prov_store = ProviderStore(path=str(tmp_path / "providers.json"))
        prov_store.create(name="acp-test", base_url="", mode="acp", models=["claude-3"])
        store = RoleStore(path=path, provider_store=prov_store)
        prov = prov_store.get_default()
        with pytest.raises(RoleError, match="not in provider"):
            store.set("fast", prov.id, "gpt-4o")

    def test_validate_acp_provider_empty_catalog_empty_model_ok(self, tmp_path):
        """ACP-mode + empty catalog: empty model is accepted (SDK-managed)."""
        path = str(tmp_path / "roles.json")
        prov_store = ProviderStore(path=str(tmp_path / "providers.json"))
        prov_store.create(name="claude-sdk", base_url="", mode="acp")
        store = RoleStore(path=path, provider_store=prov_store)
        prov = prov_store.get_default()
        r = store.set("fast", prov.id, "")
        assert r.name == "fast"
        assert r.model == ""

    def test_validate_api_provider_empty_model_rejected(self, tmp_path):
        """Non-ACP provider still requires a non-empty model."""
        path = str(tmp_path / "roles.json")
        prov_store = ProviderStore(path=str(tmp_path / "providers.json"))
        prov_store.create(name="api-test", base_url="http://x", mode="api", models=["m1"])
        store = RoleStore(path=path, provider_store=prov_store)
        prov = prov_store.get_default()
        with pytest.raises(RoleError, match="model must be non-empty"):
            store.set("fast", prov.id, "")

    def test_valid_strategies(self):
        """VALID_STRATEGIES contains priority and round_robin."""
        assert "priority" in VALID_STRATEGIES
        assert "round_robin" in VALID_STRATEGIES

    def test_set_candidates_rejects_unknown_strategy(self, tmp_path):
        path = str(tmp_path / "roles.json")
        store = RoleStore(path=path)
        with pytest.raises(RoleError, match="strategy"):
            store.set_candidates("fast", "waterfall", [Candidate("p", "m")])

    def test_set_candidates_rejects_empty_candidates(self, tmp_path):
        path = str(tmp_path / "roles.json")
        store = RoleStore(path=path)
        with pytest.raises(RoleError, match="non-empty"):
            store.set_candidates("fast", "priority", [])

    def test_set_candidates_rejects_duplicate_pair(self, tmp_path):
        path = str(tmp_path / "roles.json")
        store = RoleStore(path=path)
        dup = Candidate(provider_id="prov-1", model="gpt-4o")
        with pytest.raises(RoleError, match="duplicate"):
            store.set_candidates("fast", "priority", [dup, dup])

    def test_set_candidates_allows_same_provider_different_models(self, tmp_path):
        """Same provider_id with different models is allowed."""
        path = str(tmp_path / "roles.json")
        store = RoleStore(path=path)
        candidates = [
            Candidate(provider_id="prov-1", model="gpt-4"),
            Candidate(provider_id="prov-1", model="gpt-4o"),
        ]
        role = store.set_candidates("fast", "priority", candidates)
        assert len(role.candidates) == 2


# ---------------------------------------------------------------------------
# Reload callback
# ---------------------------------------------------------------------------


class TestRoleStoreReloadCallback:
    def test_callback_fires_on_set(self, tmp_path):
        path = str(tmp_path / "roles.json")
        calls = []
        store = RoleStore(path=path, reload_callback=lambda d, s: calls.append(s))
        store.set("fast", "prov-1", "gpt-4o")
        assert calls == ["set"]

    def test_callback_fires_on_delete(self, tmp_path):
        path = str(tmp_path / "roles.json")
        calls = []
        store = RoleStore(path=path, reload_callback=lambda d, s: calls.append(s))
        store.set("fast", "prov-1", "gpt-4o")
        store.delete("fast")
        assert calls == ["set", "delete"]

    def test_callback_fires_on_restore(self, tmp_path):
        path = str(tmp_path / "roles.json")
        calls = []
        store = RoleStore(path=path, reload_callback=lambda d, s: calls.append(s))
        store.set("fast", "prov-1", "gpt-4o")
        snap = store.snapshot()
        store.restore(snap)
        assert calls == ["set", "restore"]

    def test_callback_exception_doesnt_break_write(self, tmp_path):
        path = str(tmp_path / "roles.json")
        def bad_callback(d, s):
            raise RuntimeError("boom")
        store = RoleStore(path=path, reload_callback=bad_callback)
        # Should not raise
        store.set("fast", "prov-1", "gpt-4o")
        assert store.get("fast") is not None

    def test_set_reload_callback(self, tmp_path):
        path = str(tmp_path / "roles.json")
        calls = []
        store = RoleStore(path=path)
        store.set_reload_callback(lambda d, s: calls.append(s))
        store.set("fast", "prov-1", "gpt-4o")
        assert calls == ["set"]
        store.set_reload_callback(None)
        store.set("deep", "prov-1", "gpt-4")
        assert calls == ["set"]  # no more calls


# ---------------------------------------------------------------------------
# File-format robustness
# ---------------------------------------------------------------------------


class TestRoleStoreFileFormat:
    def test_corrupt_json_yields_empty_store(self, tmp_path):
        path = str(tmp_path / "roles.json")
        with open(path, "w") as f:
            f.write("not valid json {")
        store = RoleStore(path=path)
        assert store.list_all() == []

    def test_non_list_top_level_yields_empty_store(self, tmp_path):
        path = str(tmp_path / "roles.json")
        with open(path, "w") as f:
            json.dump({"oops": "object"}, f)
        store = RoleStore(path=path)
        assert store.list_all() == []

    def test_non_dict_entries_skipped(self, tmp_path):
        path = str(tmp_path / "roles.json")
        with open(path, "w") as f:
            json.dump(["not", "a", "dict"], f)
        store = RoleStore(path=path)
        assert store.list_all() == []

    def test_duplicate_names_ignored(self, tmp_path):
        path = str(tmp_path / "roles.json")
        now = datetime.now(timezone.utc)
        with open(path, "w") as f:
            json.dump([
                {
                    "name": "fast",
                    "strategy": "priority",
                    "candidates": [{"provider_id": "p1", "model": "m1"}],
                    "updated_at": now.isoformat(),
                },
                {
                    "name": "fast",
                    "strategy": "round_robin",
                    "candidates": [{"provider_id": "p2", "model": "m2"}],
                    "updated_at": now.isoformat(),
                },
            ], f)
        store = RoleStore(path=path)
        assert len(store.list_all()) == 1
        assert store.get("fast").candidates[0].provider_id == "p1"  # first wins

    def test_new_schema_written_on_save(self, tmp_path):
        """Roles saved with set() use the new multi-candidate schema."""
        path = str(tmp_path / "roles.json")
        store = RoleStore(path=path)
        store.set("fast", "prov-1", "gpt-4o")
        with open(path) as f:
            data = json.load(f)
        entry = data[0]
        assert "strategy" in entry
        assert "candidates" in entry
        assert entry["strategy"] == "priority"
        assert entry["candidates"] == [{"provider_id": "prov-1", "model": "gpt-4o"}]


# ---------------------------------------------------------------------------
# Migration from AgentProfileStore
# ---------------------------------------------------------------------------


class TestMigrationFromAgentProfileStore:
    def test_migrate_profiles_with_provider_and_model(self, tmp_path, caplog):
        """Profiles with provider_id and model should be migrated to RoleStore."""
        from oompah.roles import migrate_agent_profiles_to_roles

        prov_store = ProviderStore(path=str(tmp_path / "providers.json"))
        prov_store.create(name="test", base_url="http://x", models=["gpt-4", "gpt-4o"])
        prov = prov_store.get_default()

        role_store = RoleStore(path=str(tmp_path / "roles.json"), provider_store=prov_store)

        profiles = [
            AgentProfile(
                name="fast",
                command="claude",
                provider_id=prov.id,
                model="gpt-4o",
                model_role="fast",
                mode="api",
            ),
            AgentProfile(
                name="deep",
                command="claude",
                provider_id=prov.id,
                model="gpt-4",
                model_role="deep",
                mode="api",
            ),
        ]

        with caplog.at_level(logging.INFO):
            migrated = migrate_agent_profiles_to_roles(role_store, profiles)

        assert migrated == 2
        assert role_store.get("fast") is not None
        assert role_store.get("fast").provider_id == prov.id
        assert role_store.get("fast").model == "gpt-4o"
        assert role_store.get("deep") is not None
        assert role_store.get("deep").model == "gpt-4"
        # Migrated roles are single-candidate priority roles.
        assert role_store.get("fast").strategy == "priority"
        assert len(role_store.get("fast").candidates) == 1
        assert any("Migrated" in r.message and "2" in r.message for r in caplog.records)

    def test_first_write_wins_for_duplicates(self, tmp_path, caplog):
        """When multiple profiles share the same model_role, first-write wins."""
        from oompah.roles import migrate_agent_profiles_to_roles

        prov_store = ProviderStore(path=str(tmp_path / "providers.json"))
        prov_store.create(name="test", base_url="http://x", models=["gpt-4", "gpt-4o"])
        prov = prov_store.get_default()

        role_store = RoleStore(path=str(tmp_path / "roles.json"), provider_store=prov_store)

        profiles = [
            AgentProfile(
                name="fast-a",
                command="claude",
                provider_id=prov.id,
                model="gpt-4o",
                model_role="fast",
                mode="api",
            ),
            AgentProfile(
                name="fast-b",
                command="claude",
                provider_id=prov.id,
                model="gpt-4",
                model_role="fast",  # same role
                mode="api",
            ),
        ]

        with caplog.at_level(logging.INFO):
            migrate_agent_profiles_to_roles(role_store, profiles)

        assert role_store.get("fast").model == "gpt-4o"  # first wins

    def test_profiles_without_provider_id_and_model_not_migrated(self, tmp_path):
        """Profiles without provider_id and model should not be migrated."""
        from oompah.roles import migrate_agent_profiles_to_roles

        prov_store = ProviderStore(path=str(tmp_path / "providers.json"))
        role_store = RoleStore(path=str(tmp_path / "roles.json"), provider_store=prov_store)

        profiles = [
            AgentProfile(
                name="cli-agent",
                command="claude",
                mode="cli",
            ),
        ]

        migrated = migrate_agent_profiles_to_roles(role_store, profiles)
        assert migrated == 0
        assert role_store.is_empty

    def test_profiles_without_model_role_not_migrated(self, tmp_path):
        """Profiles with provider_id and model but no model_role are skipped."""
        from oompah.roles import migrate_agent_profiles_to_roles

        prov_store = ProviderStore(path=str(tmp_path / "providers.json"))
        prov_store.create(name="test", base_url="http://x", models=["gpt-4"])
        prov = prov_store.get_default()

        role_store = RoleStore(path=str(tmp_path / "roles.json"), provider_store=prov_store)

        profiles = [
            AgentProfile(
                name="no-role",
                command="claude",
                provider_id=prov.id,
                model="gpt-4",
                mode="api",
            ),
        ]

        migrated = migrate_agent_profiles_to_roles(role_store, profiles)
        assert migrated == 0
        assert role_store.is_empty

    def test_existing_role_not_overwritten(self, tmp_path):
        """Existing roles in RoleStore should not be overwritten by migration."""
        from oompah.roles import migrate_agent_profiles_to_roles

        prov_store = ProviderStore(path=str(tmp_path / "providers.json"))
        prov_store.create(name="test", base_url="http://x", models=["gpt-4", "gpt-4o"])
        prov = prov_store.get_default()

        role_store = RoleStore(path=str(tmp_path / "roles.json"), provider_store=prov_store)
        # Pre-populate
        role_store.set("fast", prov.id, "gpt-4")

        profiles = [
            AgentProfile(
                name="fast",
                command="claude",
                provider_id=prov.id,
                model="gpt-4o",
                model_role="fast",
                mode="api",
            ),
        ]

        migrated = migrate_agent_profiles_to_roles(role_store, profiles)
        assert migrated == 0  # not migrated because slot already filled
        assert role_store.get("fast").model == "gpt-4"  # original preserved

    def test_migration_logs_each_profile(self, tmp_path, caplog):
        """Migration logs each profile that is migrated."""
        from oompah.roles import migrate_agent_profiles_to_roles

        prov_store = ProviderStore(path=str(tmp_path / "providers.json"))
        prov_store.create(name="test", base_url="http://x", models=["gpt-4"])
        prov = prov_store.get_default()

        role_store = RoleStore(path=str(tmp_path / "roles.json"), provider_store=prov_store)

        profiles = [
            AgentProfile(
                name="fast",
                command="claude",
                provider_id=prov.id,
                model="gpt-4",
                model_role="fast",
                mode="api",
            ),
        ]

        with caplog.at_level(logging.INFO):
            migrate_agent_profiles_to_roles(role_store, profiles)

        msgs = [r.message for r in caplog.records]
        assert any("migrate" in m.lower() or "Migrated" in m for m in msgs)

    def test_migration_persists_to_disk(self, tmp_path):
        """Migrated roles are persisted to disk."""
        from oompah.roles import migrate_agent_profiles_to_roles

        prov_store = ProviderStore(path=str(tmp_path / "providers.json"))
        prov_store.create(name="test", base_url="http://x", models=["gpt-4"])
        prov = prov_store.get_default()

        role_store = RoleStore(path=str(tmp_path / "roles.json"), provider_store=prov_store)

        profiles = [
            AgentProfile(
                name="fast",
                command="claude",
                provider_id=prov.id,
                model="gpt-4",
                model_role="fast",
                mode="api",
            ),
        ]

        migrate_agent_profiles_to_roles(role_store, profiles)

        # Reopen from disk
        role_store2 = RoleStore(path=str(tmp_path / "roles.json"))
        assert role_store2.get("fast") is not None
        assert role_store2.get("fast").model == "gpt-4"

    def test_migration_empty_profiles_noop(self, tmp_path):
        """Empty profile list should not create any roles."""
        from oompah.roles import migrate_agent_profiles_to_roles

        prov_store = ProviderStore(path=str(tmp_path / "providers.json"))
        role_store = RoleStore(path=str(tmp_path / "roles.json"), provider_store=prov_store)

        migrated = migrate_agent_profiles_to_roles(role_store, [])
        assert migrated == 0
        assert role_store.is_empty
