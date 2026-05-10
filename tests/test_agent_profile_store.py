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


# ---------------------------------------------------------------------------
# Source precedence + one-shot migration (oompah-zlz_2-2y7)
# ---------------------------------------------------------------------------

import logging
import os

from oompah.agent_profile_store import (
    DEFAULT_AGENT_PROFILES_PATH,
    SOURCE_JSON,
    SOURCE_WORKFLOW,
    _profiles_signature,
    reset_warning_state,
    resolve_agent_profiles,
    resolve_source,
)


@pytest.fixture(autouse=True)
def _isolated_env_for_resolve(monkeypatch):
    """Each resolve_* test starts with a clean OOMPAH_AGENT_PROFILES_SOURCE
    and a fresh once-per-process WARN cache. Scoped via autouse so it
    runs for every test in this module — main's CRUD tests don't touch
    the env var, so the cleanup is a no-op for them."""
    monkeypatch.delenv("OOMPAH_AGENT_PROFILES_SOURCE", raising=False)
    reset_warning_state()
    yield
    reset_warning_state()


def _make_resolve_profile(name: str, **overrides) -> AgentProfile:
    """Convenience builder for the source-precedence tests."""
    base = dict(
        name=name,
        command="claude --dangerously-skip-permissions",
        provider_id="prov-test",
        model_role="standard",
    )
    base.update(overrides)
    return AgentProfile(**base)


class TestResolveSource:
    def test_default_is_json(self):
        assert resolve_source() == SOURCE_JSON

    def test_explicit_workflow(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_AGENT_PROFILES_SOURCE", "workflow")
        assert resolve_source() == SOURCE_WORKFLOW

    def test_workflow_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_AGENT_PROFILES_SOURCE", "WORKFLOW")
        assert resolve_source() == SOURCE_WORKFLOW

    def test_typo_falls_back_to_json(self, monkeypatch):
        # A typo (e.g. workflwo) must NOT silently disable the JSON store.
        monkeypatch.setenv("OOMPAH_AGENT_PROFILES_SOURCE", "workflwo")
        assert resolve_source() == SOURCE_JSON

    def test_empty_falls_back_to_json(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_AGENT_PROFILES_SOURCE", "")
        assert resolve_source() == SOURCE_JSON


class TestResolveAgentProfiles:
    def test_one_shot_migration_writes_json(self, tmp_path, caplog):
        store_path = str(tmp_path / "agent_profiles.json")
        wf_profiles = [
            _make_resolve_profile("quick", model_role="fast"),
            _make_resolve_profile("standard", model_role="standard"),
        ]
        with caplog.at_level(logging.INFO):
            profiles, source, migrated = resolve_agent_profiles(
                wf_profiles, store_path=store_path,
            )
        assert source == SOURCE_JSON
        assert migrated is True
        assert [p.name for p in profiles] == ["quick", "standard"]
        # JSON file now exists
        assert os.path.exists(store_path)
        # Migration is logged at INFO with the count. The exact phrasing
        # of the log message lives in AgentProfileStore._load.
        msgs = [r.message for r in caplog.records]
        assert any(
            "Migrated" in m and "WORKFLOW.md" in m and "2" in m
            for m in msgs
        )

    def test_no_migration_when_workflow_empty(self, tmp_path):
        store_path = str(tmp_path / "agent_profiles.json")
        profiles, source, migrated = resolve_agent_profiles(
            [], store_path=store_path,
        )
        assert source == SOURCE_JSON
        assert migrated is False
        assert profiles == []
        # No JSON file created — the migration is keyed on YAML having profiles.
        assert not os.path.exists(store_path)

    def test_json_wins_after_first_migration(self, tmp_path, caplog):
        store_path = str(tmp_path / "agent_profiles.json")

        # First call migrates.
        wf_profiles = [_make_resolve_profile("quick")]
        resolve_agent_profiles(wf_profiles, store_path=store_path)

        # Operator manually edits the JSON store to add a profile.
        AgentProfileStore(path=store_path).replace_all([
            _make_resolve_profile("quick"),
            _make_resolve_profile("ui-only"),
        ])

        # Second call (e.g. workflow file change) returns the JSON contents,
        # NOT the WORKFLOW.md contents — and does not re-migrate.
        with caplog.at_level(logging.INFO):
            profiles, source, migrated = resolve_agent_profiles(
                wf_profiles, store_path=store_path,
            )
        assert source == SOURCE_JSON
        assert migrated is False
        names = {p.name for p in profiles}
        assert names == {"quick", "ui-only"}

    def test_warn_once_per_session_when_workflow_drifts(self, tmp_path, caplog):
        store_path = str(tmp_path / "agent_profiles.json")
        # Seed JSON
        AgentProfileStore(path=store_path).replace_all(
            [_make_resolve_profile("quick")]
        )

        # WORKFLOW.md still has profiles but they differ.
        drifted = [_make_resolve_profile("quick", model_role="fast")]
        with caplog.at_level(logging.WARNING):
            resolve_agent_profiles(drifted, store_path=store_path)
            resolve_agent_profiles(drifted, store_path=store_path)
            resolve_agent_profiles(drifted, store_path=store_path)

        warns = [
            r for r in caplog.records
            if r.levelno == logging.WARNING
            and "WORKFLOW.md agent.profiles[] differs" in r.message
        ]
        # Once-per-process: not once-per-call.
        assert len(warns) == 1

    def test_no_warn_when_workflow_matches_json(self, tmp_path, caplog):
        store_path = str(tmp_path / "agent_profiles.json")
        same = [_make_resolve_profile("quick")]
        AgentProfileStore(path=store_path).replace_all(same)

        with caplog.at_level(logging.WARNING):
            resolve_agent_profiles(same, store_path=store_path)
        assert not any(
            "WORKFLOW.md agent.profiles[] differs" in r.message
            for r in caplog.records
        )

    def test_no_warn_when_workflow_has_no_profiles(self, tmp_path, caplog):
        store_path = str(tmp_path / "agent_profiles.json")
        AgentProfileStore(path=store_path).replace_all(
            [_make_resolve_profile("quick")]
        )

        # Operator removed agent.profiles[] from WORKFLOW.md after migrating.
        # That's the *correct* steady state — no warn should fire.
        with caplog.at_level(logging.WARNING):
            resolve_agent_profiles([], store_path=store_path)
        assert not any(
            "WORKFLOW.md agent.profiles[] differs" in r.message
            for r in caplog.records
        )

    def test_workflow_source_skips_json(self, tmp_path, monkeypatch, caplog):
        monkeypatch.setenv("OOMPAH_AGENT_PROFILES_SOURCE", "workflow")
        store_path = str(tmp_path / "agent_profiles.json")
        # Pre-seed JSON store with values that should NOT win.
        AgentProfileStore(path=store_path).replace_all(
            [_make_resolve_profile("json-one")]
        )

        wf_profiles = [
            _make_resolve_profile("quick"),
            _make_resolve_profile("standard"),
        ]
        with caplog.at_level(logging.INFO):
            profiles, source, migrated = resolve_agent_profiles(
                wf_profiles, store_path=store_path,
            )
        assert source == SOURCE_WORKFLOW
        assert migrated is False
        assert [p.name for p in profiles] == ["quick", "standard"]
        # We did NOT log a migration.
        assert not any(
            "Migrated" in r.message for r in caplog.records
        )

    def test_signature_ignores_order(self):
        a = [_make_resolve_profile("a"), _make_resolve_profile("b")]
        b = [_make_resolve_profile("b"), _make_resolve_profile("a")]
        assert _profiles_signature(a) == _profiles_signature(b)

    def test_signature_detects_change(self):
        a = [_make_resolve_profile("a", model_role="fast")]
        b = [_make_resolve_profile("a", model_role="standard")]
        assert _profiles_signature(a) != _profiles_signature(b)


class TestServiceConfigIntegration:
    """Verify the migration runs through ServiceConfig.from_workflow."""

    def setup_method(self):
        for k in list(os.environ):
            if k.startswith("OOMPAH_"):
                os.environ.pop(k, None)
        reset_warning_state()

    def teardown_method(self):
        for k in list(os.environ):
            if k.startswith("OOMPAH_"):
                os.environ.pop(k, None)
        reset_warning_state()

    def test_first_boot_migrates(self, tmp_path):
        from oompah.config import ServiceConfig
        from oompah.models import WorkflowDefinition

        store_path = str(tmp_path / "agent_profiles.json")
        wf = WorkflowDefinition(
            config={
                "agent": {
                    "profiles": [
                        {"name": "quick", "model_role": "fast"},
                        {"name": "deep", "model_role": "big"},
                    ],
                },
            },
            prompt_template="t",
        )
        cfg = ServiceConfig.from_workflow(wf, agent_profiles_path=store_path)

        assert cfg.agent_profiles_source == "json"
        assert [p.name for p in cfg.agent_profiles] == ["quick", "deep"]
        assert os.path.exists(store_path)

    def test_second_boot_uses_json(self, tmp_path):
        from oompah.config import ServiceConfig
        from oompah.models import WorkflowDefinition

        store_path = str(tmp_path / "agent_profiles.json")
        # First boot: migrate.
        wf1 = WorkflowDefinition(
            config={"agent": {"profiles": [{"name": "quick"}]}},
            prompt_template="t",
        )
        ServiceConfig.from_workflow(wf1, agent_profiles_path=store_path)

        # Operator updates JSON via the dashboard / direct edit.
        AgentProfileStore(path=store_path).replace_all(
            [_make_resolve_profile("quick"), _make_resolve_profile("ui-added")]
        )

        # Operator also (separately) re-edits WORKFLOW.md.
        wf2 = WorkflowDefinition(
            config={"agent": {"profiles": [{"name": "quick", "mode": "acp"}]}},
            prompt_template="t",
        )
        cfg = ServiceConfig.from_workflow(wf2, agent_profiles_path=store_path)
        # JSON wins.
        names = {p.name for p in cfg.agent_profiles}
        assert names == {"quick", "ui-added"}

    def test_workflow_source_env(self, tmp_path, monkeypatch):
        from oompah.config import ServiceConfig
        from oompah.models import WorkflowDefinition

        monkeypatch.setenv("OOMPAH_AGENT_PROFILES_SOURCE", "workflow")
        store_path = str(tmp_path / "agent_profiles.json")
        # Pre-seed JSON that should be ignored.
        AgentProfileStore(path=store_path).replace_all(
            [_make_resolve_profile("from-json")]
        )

        wf = WorkflowDefinition(
            config={"agent": {"profiles": [{"name": "from-yaml"}]}},
            prompt_template="t",
        )
        cfg = ServiceConfig.from_workflow(wf, agent_profiles_path=store_path)
        assert cfg.agent_profiles_source == "workflow"
        assert [p.name for p in cfg.agent_profiles] == ["from-yaml"]

    def test_default_source_is_json(self, tmp_path):
        """When the env var is unset and there are no profiles anywhere,
        the resolved source is still 'json' (so the dashboard knows the
        UI is read/write)."""
        from oompah.config import ServiceConfig
        from oompah.models import WorkflowDefinition

        store_path = str(tmp_path / "agent_profiles.json")
        wf = WorkflowDefinition(config={}, prompt_template="t")
        cfg = ServiceConfig.from_workflow(wf, agent_profiles_path=store_path)
        assert cfg.agent_profiles_source == "json"
        assert cfg.agent_profiles == []
        # No spurious file created when there's nothing to migrate.
        assert not os.path.exists(store_path)
