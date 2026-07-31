"""Tests for :mod:`oompah.actor_mapping`."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from oompah.actor_mapping import ActorMap, ActorMapError, load_actor_map


class TestActorMapResolve:
    def test_identity_mapping_when_empty(self):
        """No entries → username IS the actor login (identity mapping)."""

        actor_map = ActorMap()
        assert actor_map.resolve("alice") == "alice"

    def test_case_folded_lookup_returns_configured_actor(self):
        """Lookup is case-insensitive; configured actor value is returned as-is."""

        actor_map = ActorMap(entries={"ci-bot": "Alice"})
        assert actor_map.resolve("CI-BOT") == "Alice"
        assert actor_map.resolve("ci-bot") == "Alice"

    def test_unmapped_user_uses_identity(self):
        """Unmapped user in non-strict mode falls back to identity mapping."""

        actor_map = ActorMap(entries={"ci-bot": "alice"})
        assert actor_map.resolve("carol") == "carol"

    def test_strict_mode_rejects_unmapped(self):
        """Strict mode returns None for unmapped users → caller must fail closed."""

        actor_map = ActorMap(entries={"ci-bot": "alice"}, strict=True)
        assert actor_map.resolve("carol") is None
        assert actor_map.resolve("ci-bot") == "alice"

    def test_blank_username_returns_none(self):
        actor_map = ActorMap(entries={"ci-bot": "alice"})
        assert actor_map.resolve("") is None


class TestLoadActorMapEnv:
    def test_no_config_returns_empty_identity_map(self):
        actor_map = load_actor_map(env_file_dir="/tmp", env={})
        assert actor_map.entries == {}
        assert actor_map.strict is False
        assert actor_map.resolve("anyone") == "anyone"

    def test_inline_env_map_parsed(self):
        env = {"OOMPAH_ACTOR_MAP": json.dumps({"ci-bot": "alice", "release-bot": "carol"})}
        actor_map = load_actor_map(env_file_dir="/tmp", env=env)
        assert actor_map.entries == {"ci-bot": "alice", "release-bot": "carol"}
        assert actor_map.resolve("ci-bot") == "alice"

    def test_strict_env_flag_recognized(self):
        env = {
            "OOMPAH_ACTOR_MAP": json.dumps({"ci-bot": "alice"}),
            "OOMPAH_ACTOR_MAP_STRICT": "true",
        }
        actor_map = load_actor_map(env_file_dir="/tmp", env=env)
        assert actor_map.strict is True
        assert actor_map.resolve("carol") is None

    def test_inline_and_file_are_mutually_exclusive(self, tmp_path):
        path = tmp_path / "actors.json"
        path.write_text(json.dumps({"ci-bot": "alice"}))
        env = {
            "OOMPAH_ACTOR_MAP": json.dumps({"ci-bot": "alice"}),
            "OOMPAH_ACTOR_MAP_FILE": str(path),
        }
        with pytest.raises(ActorMapError, match="exactly one"):
            load_actor_map(env_file_dir=str(tmp_path), env=env)

    def test_strict_without_config_fails_closed(self):
        env = {"OOMPAH_ACTOR_MAP_STRICT": "1"}
        with pytest.raises(ActorMapError, match="no mapping is configured"):
            load_actor_map(env_file_dir="/tmp", env=env)


class TestLoadActorMapFile:
    def test_absolute_file_path_loaded(self, tmp_path):
        path = tmp_path / "actors.json"
        path.write_text(json.dumps({"ci-bot": "alice"}))
        env = {"OOMPAH_ACTOR_MAP_FILE": str(path)}
        actor_map = load_actor_map(env_file_dir=str(tmp_path), env=env)
        assert actor_map.entries == {"ci-bot": "alice"}
        assert actor_map.source.startswith("OOMPAH_ACTOR_MAP_FILE")

    def test_relative_path_resolved_against_env_dir(self, tmp_path):
        (tmp_path / "actors.json").write_text(json.dumps({"ci-bot": "alice"}))
        env = {"OOMPAH_ACTOR_MAP_FILE": "actors.json"}
        actor_map = load_actor_map(env_file_dir=str(tmp_path), env=env)
        assert actor_map.entries == {"ci-bot": "alice"}

    def test_missing_file_fails_closed(self, tmp_path):
        env = {"OOMPAH_ACTOR_MAP_FILE": str(tmp_path / "missing.json")}
        with pytest.raises(ActorMapError, match="not found"):
            load_actor_map(env_file_dir=str(tmp_path), env=env)


class TestValidationFailsClosed:
    def test_invalid_json_rejected(self):
        env = {"OOMPAH_ACTOR_MAP": "{not json"}
        with pytest.raises(ActorMapError, match="not valid JSON"):
            load_actor_map(env_file_dir="/tmp", env=env)

    def test_non_object_json_rejected(self):
        env = {"OOMPAH_ACTOR_MAP": json.dumps(["alice", "carol"])}
        with pytest.raises(ActorMapError, match="expected a JSON object"):
            load_actor_map(env_file_dir="/tmp", env=env)

    def test_empty_key_rejected(self):
        env = {"OOMPAH_ACTOR_MAP": json.dumps({"": "alice"})}
        with pytest.raises(ActorMapError, match="non-empty"):
            load_actor_map(env_file_dir="/tmp", env=env)

    def test_empty_value_rejected(self):
        env = {"OOMPAH_ACTOR_MAP": json.dumps({"ci-bot": ""})}
        with pytest.raises(ActorMapError, match="non-empty"):
            load_actor_map(env_file_dir="/tmp", env=env)

    def test_ambiguous_mapping_rejected(self):
        env = {
            "OOMPAH_ACTOR_MAP": json.dumps(
                {"ci-bot": "alice", "release-bot": "Alice"}
            ),
        }
        with pytest.raises(ActorMapError, match="ambiguous"):
            load_actor_map(env_file_dir="/tmp", env=env)

    def test_duplicate_case_folded_key_rejected(self):
        # json.loads already dedupes exact-string keys; simulate a
        # normalization collision by using differently-cased keys.
        env = {
            "OOMPAH_ACTOR_MAP": json.dumps(
                {"ci-bot": "alice", "CI-BOT": "carol"}
            ),
        }
        with pytest.raises(ActorMapError, match="duplicate"):
            load_actor_map(env_file_dir="/tmp", env=env)
