"""Tests for oompah.agent_profile_store."""

import json

import pytest

from oompah.agent_profile_store import (
    AgentProfileError, AgentProfileStore, VALID_MODES,
)
from oompah.models import AgentProfile


# ---------------------------------------------------------------------------
# AgentProfile.to_dict / from_dict round-trip (foundation of the store)
# ---------------------------------------------------------------------------


class TestAgentProfileSerialization:
    def test_round_trip_minimal(self):
        p = AgentProfile(name="x", command="claude", mode="cli")
        d = p.to_dict()
        assert d == {"name": "x", "command": "claude", "mode": "cli"}
        p2 = AgentProfile.from_dict(d)
        assert p2 == p

    def test_round_trip_full(self):
        p = AgentProfile(
            name="big",
            command="claude --foo",
            provider_id="prov-1",
            model="gpt-4o",
            model_role="default",
            cost_per_1k_input=0.5,
            cost_per_1k_output=1.0,
            max_turns=42,
            keywords=["bug", "ui"],
            issue_types=["bug"],
            min_priority=0,
            max_priority=2,
            mode="api",
        )
        d = p.to_dict()
        p2 = AgentProfile.from_dict(d)
        assert p2 == p

    def test_to_dict_omits_default_optionals(self):
        p = AgentProfile(name="x", command="claude")
        d = p.to_dict()
        assert "provider_id" not in d
        assert "model" not in d
        assert "max_turns" not in d
        assert "keywords" not in d
        assert "issue_types" not in d
        assert "min_priority" not in d

    def test_from_dict_lenient(self):
        # Missing optional keys -> defaults; unknown keys -> ignored.
        p = AgentProfile.from_dict({"name": "x", "unknown": "ignored"})
        assert p.name == "x"
        # Default command from from_dict
        assert "claude" in p.command
        assert p.mode == "auto"

    def test_from_dict_max_turns_string(self):
        # Accept "42" or 42 from the wire.
        p = AgentProfile.from_dict({"name": "x", "max_turns": "42"})
        assert p.max_turns == 42
        # Bad value -> None (no crash).
        p = AgentProfile.from_dict({"name": "x", "max_turns": "garbage"})
        assert p.max_turns is None


# ---------------------------------------------------------------------------
# CRUD basics
# ---------------------------------------------------------------------------


class TestAgentProfileStoreCRUD:
    def test_create_and_get(self, tmp_path):
        path = str(tmp_path / "profiles.json")
        store = AgentProfileStore(path=path)
        p = store.create({"name": "fast", "command": "claude", "mode": "cli"})
        assert p.name == "fast"
        assert store.get("fast").name == "fast"
        assert store.get("missing") is None

    def test_create_persists(self, tmp_path):
        path = str(tmp_path / "profiles.json")
        store = AgentProfileStore(path=path)
        store.create({"name": "a", "command": "c", "mode": "cli"})
        # Reopen
        store2 = AgentProfileStore(path=path)
        assert store2.get("a").command == "c"

    def test_list_all(self, tmp_path):
        path = str(tmp_path / "profiles.json")
        store = AgentProfileStore(path=path)
        store.create({"name": "a", "command": "x", "mode": "cli"})
        store.create({"name": "b", "command": "y", "mode": "acp"})
        assert {p.name for p in store.list_all()} == {"a", "b"}

    def test_update_full(self, tmp_path):
        path = str(tmp_path / "profiles.json")
        store = AgentProfileStore(path=path)
        store.create({"name": "p1", "command": "c", "mode": "cli"})
        updated = store.update("p1", command="new-cmd", mode="acp")
        assert updated is not None
        assert updated.command == "new-cmd"
        assert updated.mode == "acp"

    def test_update_partial_keeps_other_fields(self, tmp_path):
        path = str(tmp_path / "profiles.json")
        store = AgentProfileStore(path=path)
        store.create({
            "name": "x", "command": "c", "mode": "api",
            "provider_id": "prov-1", "model": "gpt-4o", "max_turns": 100,
        })
        # Patch only model; other fields stay.
        updated = store.update("x", model="claude-sonnet")
        assert updated.model == "claude-sonnet"
        assert updated.provider_id == "prov-1"
        assert updated.max_turns == 100
        assert updated.mode == "api"

    def test_update_returns_none_when_missing(self, tmp_path):
        path = str(tmp_path / "profiles.json")
        store = AgentProfileStore(path=path)
        assert store.update("missing", command="x") is None

    def test_update_rename(self, tmp_path):
        path = str(tmp_path / "profiles.json")
        store = AgentProfileStore(path=path)
        store.create({"name": "old", "command": "c", "mode": "cli"})
        updated = store.update("old", name="new")
        assert updated.name == "new"
        assert store.get("old") is None
        assert store.get("new") is not None

    def test_delete(self, tmp_path):
        path = str(tmp_path / "profiles.json")
        store = AgentProfileStore(path=path)
        store.create({"name": "a", "command": "c", "mode": "cli"})
        assert store.delete("a") is True
        assert store.get("a") is None
        assert store.delete("a") is False

    def test_replace_all(self, tmp_path):
        path = str(tmp_path / "profiles.json")
        store = AgentProfileStore(path=path)
        store.create({"name": "a", "command": "c", "mode": "cli"})
        store.replace_all([
            AgentProfile(name="x", command="c", mode="cli"),
            AgentProfile(name="y", command="c", mode="acp"),
        ])
        names = {p.name for p in store.list_all()}
        assert names == {"x", "y"}


# ---------------------------------------------------------------------------
# Validation rules
# ---------------------------------------------------------------------------


class TestAgentProfileStoreValidation:
    def test_create_rejects_empty_name(self, tmp_path):
        store = AgentProfileStore(path=str(tmp_path / "p.json"))
        with pytest.raises(AgentProfileError, match="non-empty"):
            store.create({"name": "", "command": "c", "mode": "cli"})

    def test_create_rejects_duplicate_name(self, tmp_path):
        store = AgentProfileStore(path=str(tmp_path / "p.json"))
        store.create({"name": "x", "command": "c", "mode": "cli"})
        with pytest.raises(AgentProfileError, match="already exists"):
            store.create({"name": "x", "command": "c", "mode": "acp"})

    def test_create_rejects_bad_mode(self, tmp_path):
        store = AgentProfileStore(path=str(tmp_path / "p.json"))
        with pytest.raises(AgentProfileError, match="mode"):
            store.create({"name": "x", "command": "c", "mode": "weird"})

    def test_api_mode_requires_provider_id(self, tmp_path):
        store = AgentProfileStore(path=str(tmp_path / "p.json"))
        with pytest.raises(AgentProfileError, match="provider_id"):
            store.create({"name": "x", "command": "c", "mode": "api"})
        # With provider_id -> ok
        p = store.create({
            "name": "x", "command": "c", "mode": "api",
            "provider_id": "prov-1",
        })
        assert p.provider_id == "prov-1"

    def test_auto_mode_requires_provider_id(self, tmp_path):
        store = AgentProfileStore(path=str(tmp_path / "p.json"))
        with pytest.raises(AgentProfileError, match="provider_id"):
            store.create({"name": "x", "command": "c", "mode": "auto"})

    def test_acp_mode_does_not_require_provider_id(self, tmp_path):
        store = AgentProfileStore(path=str(tmp_path / "p.json"))
        p = store.create({"name": "x", "command": "c", "mode": "acp"})
        assert p.provider_id is None

    def test_cli_mode_does_not_require_provider_id(self, tmp_path):
        store = AgentProfileStore(path=str(tmp_path / "p.json"))
        p = store.create({"name": "x", "command": "c", "mode": "cli"})
        assert p.provider_id is None

    def test_update_rejects_rename_to_existing(self, tmp_path):
        store = AgentProfileStore(path=str(tmp_path / "p.json"))
        store.create({"name": "a", "command": "c", "mode": "cli"})
        store.create({"name": "b", "command": "c", "mode": "cli"})
        with pytest.raises(AgentProfileError, match="already exists"):
            store.update("a", name="b")

    def test_update_to_api_without_provider_id_fails(self, tmp_path):
        store = AgentProfileStore(path=str(tmp_path / "p.json"))
        store.create({"name": "x", "command": "c", "mode": "cli"})
        with pytest.raises(AgentProfileError, match="provider_id"):
            store.update("x", mode="api")

    def test_update_no_op_rename(self, tmp_path):
        # Renaming to the same value must be allowed.
        store = AgentProfileStore(path=str(tmp_path / "p.json"))
        store.create({"name": "x", "command": "c", "mode": "cli"})
        updated = store.update("x", name="x")
        assert updated.name == "x"


# ---------------------------------------------------------------------------
# Migration & source precedence
# ---------------------------------------------------------------------------


class TestAgentProfileStoreMigration:
    def test_seed_from_workflow_when_file_missing(self, tmp_path):
        path = str(tmp_path / "profiles.json")
        seed = [
            AgentProfile(name="default", command="claude", mode="cli"),
            AgentProfile(name="big", command="claude", mode="acp"),
        ]
        store = AgentProfileStore(path=path, seed_from=seed)
        names = {p.name for p in store.list_all()}
        assert names == {"default", "big"}
        assert store.migrated_from_workflow is True
        # File exists on disk now
        with open(path) as f:
            data = json.load(f)
        assert {e["name"] for e in data} == {"default", "big"}

    def test_no_migration_when_file_exists(self, tmp_path):
        path = str(tmp_path / "profiles.json")
        # Pre-populate the file with one profile
        with open(path, "w") as f:
            json.dump(
                [{"name": "from-disk", "command": "x", "mode": "cli"}], f,
            )
        # Open with a seed list (which would migrate if file were missing).
        # JSON file wins.
        seed = [AgentProfile(name="from-seed", command="y", mode="cli")]
        store = AgentProfileStore(path=path, seed_from=seed)
        assert {p.name for p in store.list_all()} == {"from-disk"}
        assert store.migrated_from_workflow is False
        assert store.loaded_from_disk is True

    def test_no_migration_when_seed_empty_and_file_missing(self, tmp_path):
        path = str(tmp_path / "profiles.json")
        store = AgentProfileStore(path=path, seed_from=[])
        assert store.list_all() == []
        assert store.migrated_from_workflow is False
        # File does not exist
        import os
        assert not os.path.exists(path)

    def test_seed_skips_duplicate_names(self, tmp_path):
        path = str(tmp_path / "profiles.json")
        seed = [
            AgentProfile(name="a", command="c", mode="cli"),
            AgentProfile(name="a", command="c2", mode="acp"),  # dupe -> ignored
        ]
        store = AgentProfileStore(path=path, seed_from=seed)
        assert len(store.list_all()) == 1


# ---------------------------------------------------------------------------
# File-format robustness
# ---------------------------------------------------------------------------


class TestAgentProfileStoreFileFormat:
    def test_corrupt_json_yields_empty_store(self, tmp_path):
        path = str(tmp_path / "profiles.json")
        with open(path, "w") as f:
            f.write("not valid json {")
        store = AgentProfileStore(path=path)
        assert store.list_all() == []

    def test_non_list_top_level_yields_empty_store(self, tmp_path):
        path = str(tmp_path / "profiles.json")
        with open(path, "w") as f:
            json.dump({"oops": "object"}, f)
        store = AgentProfileStore(path=path)
        assert store.list_all() == []

    def test_valid_modes_constant(self):
        assert VALID_MODES == ("auto", "api", "cli", "acp")
