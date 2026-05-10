"""Integration tests for ServiceConfig.from_workflow + AgentProfileStore.

Source-precedence rules under test (oompah-zlz_2-xaj):
- When .oompah/agent_profiles.json is missing AND WORKFLOW.md has profiles,
  the JSON file is created from WORKFLOW.md (migration on first boot).
- When the JSON file exists, it is the source of truth; WORKFLOW.md
  profiles are ignored.
- When neither has profiles, agent_profiles is an empty list.
"""

import json
import os

import pytest

from oompah.agent_profile_store import AgentProfileStore
from oompah.config import ServiceConfig
from oompah.models import WorkflowDefinition


@pytest.fixture(autouse=True)
def isolate_store_path(tmp_path, monkeypatch):
    """Force ServiceConfig.from_workflow to use a per-test profiles path."""
    path = str(tmp_path / "agent_profiles.json")
    monkeypatch.setenv("OOMPAH_AGENT_PROFILES_PATH", path)
    return path


class TestFromWorkflowMigration:
    def test_migration_first_boot(self, isolate_store_path):
        # JSON missing; WORKFLOW.md has profiles -> migrated.
        wf = WorkflowDefinition(
            config={
                "agent": {
                    "profiles": [
                        {"name": "default", "mode": "cli", "command": "claude"},
                        {"name": "big", "mode": "acp", "command": "claude"},
                    ],
                },
            },
            prompt_template="",
        )
        cfg = ServiceConfig.from_workflow(wf)
        assert {p.name for p in cfg.agent_profiles} == {"default", "big"}
        # JSON file now exists
        assert os.path.exists(isolate_store_path)
        with open(isolate_store_path) as f:
            data = json.load(f)
        assert {e["name"] for e in data} == {"default", "big"}

    def test_json_store_wins_over_workflow(self, isolate_store_path, tmp_path):
        # Pre-populate the JSON store with one profile.
        with open(isolate_store_path, "w") as f:
            json.dump(
                [{"name": "from-json", "command": "claude", "mode": "cli"}],
                f,
            )
        # WORKFLOW.md has different profiles -> ignored.
        wf = WorkflowDefinition(
            config={
                "agent": {
                    "profiles": [
                        {"name": "from-workflow", "mode": "cli", "command": "x"},
                    ],
                },
            },
            prompt_template="",
        )
        cfg = ServiceConfig.from_workflow(wf)
        names = {p.name for p in cfg.agent_profiles}
        assert names == {"from-json"}

    def test_no_profiles_anywhere(self, isolate_store_path):
        # Empty JSON store missing AND no workflow profiles -> empty.
        wf = WorkflowDefinition(config={}, prompt_template="")
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.agent_profiles == []

    def test_workflow_only_seed(self, isolate_store_path):
        # First boot. Seeds JSON, returns the same profile list.
        wf = WorkflowDefinition(
            config={
                "agent": {
                    "profiles": [
                        {"name": "x", "mode": "api", "provider_id": "p", "command": "c"},
                    ],
                },
            },
            prompt_template="",
        )
        cfg = ServiceConfig.from_workflow(wf)
        assert len(cfg.agent_profiles) == 1
        assert cfg.agent_profiles[0].name == "x"
        assert cfg.agent_profiles[0].mode == "api"
        assert cfg.agent_profiles[0].provider_id == "p"
        # Second call (file now exists) -> same answer.
        cfg2 = ServiceConfig.from_workflow(wf)
        assert {p.name for p in cfg2.agent_profiles} == {"x"}

    def test_mode_renormalized_on_load(self, isolate_store_path):
        # Pre-populate with a bogus mode -> from_workflow falls back to "auto".
        with open(isolate_store_path, "w") as f:
            json.dump(
                [{"name": "x", "command": "c", "mode": "bogus"}],
                f,
            )
        wf = WorkflowDefinition(config={}, prompt_template="")
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.agent_profiles[0].mode == "auto"


class TestStoreReloadAfterCRUD:
    """After a write through AgentProfileStore, a fresh ServiceConfig.from_workflow
    call must reflect the change without WORKFLOW.md being edited."""

    def test_store_create_visible_to_next_from_workflow(self, isolate_store_path):
        # First boot: WORKFLOW.md has one profile; file is created.
        wf = WorkflowDefinition(
            config={
                "agent": {
                    "profiles": [
                        {"name": "default", "mode": "cli", "command": "claude"},
                    ],
                },
            },
            prompt_template="",
        )
        ServiceConfig.from_workflow(wf)
        # Now write through the store (UI-driven create).
        store = AgentProfileStore(path=isolate_store_path)
        store.create({"name": "new", "command": "c", "mode": "acp"})
        # Re-read.
        cfg = ServiceConfig.from_workflow(wf)
        names = {p.name for p in cfg.agent_profiles}
        assert names == {"default", "new"}

    def test_store_delete_removes_from_config(self, isolate_store_path):
        wf = WorkflowDefinition(
            config={
                "agent": {
                    "profiles": [
                        {"name": "a", "mode": "cli", "command": "c"},
                        {"name": "b", "mode": "cli", "command": "c"},
                    ],
                },
            },
            prompt_template="",
        )
        ServiceConfig.from_workflow(wf)
        store = AgentProfileStore(path=isolate_store_path)
        store.delete("a")
        cfg = ServiceConfig.from_workflow(wf)
        assert {p.name for p in cfg.agent_profiles} == {"b"}
