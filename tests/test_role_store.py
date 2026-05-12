"""Tests for oompah.roles."""

import json
import logging
from datetime import datetime, timezone

import pytest

from oompah.models import AgentProfile, ModelProvider
from oompah.providers import ProviderStore
from oompah.roles import Role, RoleError, RoleStore


# ---------------------------------------------------------------------------
# Role.to_dict / from_dict round-trip
# ---------------------------------------------------------------------------


class TestRoleSerialization:
    def test_round_trip_minimal(self):
        now = datetime.now(timezone.utc)
        r = Role(name="fast", provider_id="prov-1", model="gpt-4o", updated_at=now)
        d = r.to_dict()
        assert d == {
            "name": "fast",
            "provider_id": "prov-1",
            "model": "gpt-4o",
            "updated_at": now.isoformat(),
        }
        r2 = Role.from_dict(d)
        assert r2 == r

    def test_round_trip_full(self):
        now = datetime.now(timezone.utc)
        r = Role(name="deep", provider_id="prov-abc", model="claude-3", updated_at=now)
        d = r.to_dict()
        r2 = Role.from_dict(d)
        assert r2 == r

    def test_from_dict_missing_updated_at(self):
        r = Role.from_dict({"name": "x", "provider_id": "p", "model": "m"})
        assert r.name == "x"
        assert r.updated_at is not None  # defaults to now()

    def test_from_dict_bad_updated_at(self):
        r = Role.from_dict({"name": "x", "provider_id": "p", "model": "m", "updated_at": "garbage"})
        assert r.updated_at is not None  # defaults to now()

    def test_from_dict_datetime_object(self):
        now = datetime.now(timezone.utc)
        r = Role.from_dict({"name": "x", "provider_id": "p", "model": "m", "updated_at": now})
        assert r.updated_at == now


# ---------------------------------------------------------------------------
# CRUD basics (without provider validation — provider_store=None)
# ---------------------------------------------------------------------------


class TestRoleStoreCRUD:
    def test_set_and_get(self, tmp_path):
        path = str(tmp_path / "roles.json")
        store = RoleStore(path=path)
        r = store.set("fast", "prov-1", "gpt-4o")
        assert r.name == "fast"
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
                {"name": "fast", "provider_id": "p1", "model": "m1", "updated_at": now.isoformat()},
                {"name": "fast", "provider_id": "p2", "model": "m2", "updated_at": now.isoformat()},
            ], f)
        store = RoleStore(path=path)
        assert len(store.list_all()) == 1
        assert store.get("fast").provider_id == "p1"  # first wins


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