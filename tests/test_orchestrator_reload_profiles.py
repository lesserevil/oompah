"""Tests for Orchestrator.reload_config refreshing the agent profile store.

Exercises the wiring added by oompah-zlz_2-xaj: a write through the
AgentProfileStore (e.g. from /api/v1/agent-profiles) becomes effective
on the next dispatch tick when reload_config() is invoked. Without that
hook, only WORKFLOW.md edits would take effect, defeating the point of
the JSON store.
"""

import os

import pytest

from oompah.agent_profile_store import AgentProfileStore
from oompah.config import ServiceConfig
from oompah.models import AgentProfile, WorkflowDefinition
from oompah.orchestrator import Orchestrator


@pytest.fixture
def orchestrator_with_store(tmp_path, monkeypatch):
    """Construct an Orchestrator wired to a tmp-path AgentProfileStore."""
    profiles_path = str(tmp_path / "agent_profiles.json")
    monkeypatch.setenv("OOMPAH_AGENT_PROFILES_PATH", profiles_path)
    workflow_path = str(tmp_path / "WORKFLOW.md")
    with open(workflow_path, "w") as f:
        f.write(
            "---\n"
            "agent:\n"
            "  profiles:\n"
            "    - name: default\n"
            "      mode: cli\n"
            "      command: claude\n"
            "---\nTemplate.\n"
        )
    wf = WorkflowDefinition(
        config={
            "agent": {
                "profiles": [
                    {"name": "default", "mode": "cli", "command": "claude"},
                ],
            },
        },
        prompt_template="Template.",
    )
    cfg = ServiceConfig.from_workflow(wf)
    store = AgentProfileStore(path=profiles_path)
    orch = Orchestrator(
        cfg, workflow_path,
        agent_profile_store=store,
    )
    return orch, store, cfg, wf, workflow_path


def test_reload_config_refreshes_profiles_from_store(
    orchestrator_with_store,
):
    orch, store, cfg, wf, _ = orchestrator_with_store
    # Baseline: only "default"
    assert {p.name for p in orch.config.agent_profiles} == {"default"}
    # Write new profile through store (simulates POST /api/v1/agent-profiles).
    store.create({"name": "new", "command": "c", "mode": "acp"})
    # Reload (simulates the API handler's reload hook).
    new_cfg = ServiceConfig.from_workflow(wf)
    orch.reload_config(new_cfg, "Template.")
    # Orchestrator now sees the new profile in config.agent_profiles.
    names = {p.name for p in orch.config.agent_profiles}
    assert names == {"default", "new"}


def test_reload_config_picks_up_external_store_edit(
    orchestrator_with_store,
):
    orch, store, cfg, wf, _ = orchestrator_with_store
    # External code (e.g. a test or admin tool) writes to the JSON
    # file directly, then triggers reload. The orchestrator's in-
    # memory store is refreshed via _load() so the change is visible.
    import json
    with open(store.path, "w") as f:
        json.dump(
            [
                {"name": "alpha", "command": "c", "mode": "cli"},
                {"name": "beta", "command": "c", "mode": "acp"},
            ],
            f,
        )
    new_cfg = ServiceConfig.from_workflow(wf)
    orch.reload_config(new_cfg, "Template.")
    names = {p.name for p in orch.config.agent_profiles}
    assert names == {"alpha", "beta"}
    # The orchestrator's store is also refreshed.
    assert {p.name for p in orch.agent_profile_store.list_all()} == {"alpha", "beta"}


def test_reload_config_with_empty_store_falls_back_to_workflow(
    orchestrator_with_store,
):
    orch, store, cfg, wf, _ = orchestrator_with_store
    # Wipe the store.
    for p in list(store.list_all()):
        store.delete(p.name)
    assert store.list_all() == []
    # Prepare a workflow with profiles.
    wf2 = WorkflowDefinition(
        config={
            "agent": {
                "profiles": [
                    {"name": "wf1", "mode": "cli", "command": "claude"},
                ],
            },
        },
        prompt_template="Template.",
    )
    new_cfg = ServiceConfig.from_workflow(wf2)
    orch.reload_config(new_cfg, "Template.")
    # Workflow profiles win when the store has been emptied AND the
    # workflow seeds the JSON file again on the next read.
    names = {p.name for p in orch.config.agent_profiles}
    assert names == {"wf1"}
