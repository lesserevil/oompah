"""Tests for live agent-profile reload via Orchestrator.replace_agent_profiles
and AgentProfileStore->Orchestrator integration (oompah-zlz_2-mif).
"""

from __future__ import annotations

import asyncio
import logging

import pytest

from oompah.agent_profile_store import AgentProfileStore
from oompah.config import ServiceConfig
from oompah.models import AgentProfile
from oompah.orchestrator import Orchestrator


@pytest.fixture
def orch(tmp_path):
    cfg = ServiceConfig(workspace_root=str(tmp_path / "ws"))
    cfg.agent_profiles = [
        AgentProfile(name="default", command="claude", mode="cli"),
    ]
    state_path = str(tmp_path / "service_state.json")
    o = Orchestrator(cfg, str(tmp_path / "WORKFLOW.md"), state_path=state_path)
    return o


class TestReplaceAgentProfiles:
    def test_queue_then_apply(self, orch):
        new = [
            AgentProfile(name="default", command="claude", mode="cli"),
            AgentProfile(name="quick", command="claude", mode="cli"),
        ]
        orch.replace_agent_profiles(new)
        # Before apply, config still shows the old list
        assert [p.name for p in orch.config.agent_profiles] == ["default"]
        # _apply_pending_agent_profiles is what _tick() runs first
        applied = orch._apply_pending_agent_profiles()
        assert applied is True
        assert [p.name for p in orch.config.agent_profiles] == ["default", "quick"]

    def test_apply_is_idempotent(self, orch):
        # Without a queued swap, _apply does nothing and returns False.
        assert orch._apply_pending_agent_profiles() is False
        # After a swap is queued, it applies once and clears.
        orch.replace_agent_profiles([
            AgentProfile(name="x", command="c", mode="cli"),
        ])
        assert orch._apply_pending_agent_profiles() is True
        # Second call: nothing more to apply.
        assert orch._apply_pending_agent_profiles() is False

    def test_multiple_queues_collapse_to_last(self, orch):
        # If two reloads are queued before _tick runs, only the last one
        # is applied — that's what an operator submitting two PATCHes
        # back-to-back expects (no intermediate state surfaced).
        orch.replace_agent_profiles([AgentProfile(name="a", command="c", mode="cli")])
        orch.replace_agent_profiles([AgentProfile(name="b", command="c", mode="cli")])
        orch._apply_pending_agent_profiles()
        assert [p.name for p in orch.config.agent_profiles] == ["b"]

    def test_logs_on_queue(self, orch, caplog):
        with caplog.at_level(logging.INFO, logger="oompah.orchestrator"):
            orch.replace_agent_profiles(
                [AgentProfile(name="x", command="c", mode="cli")],
                source="api:test",
            )
        # The queue log shows up immediately
        assert any(
            "Agent profiles reload queued" in rec.message
            and "api:test" in rec.message
            for rec in caplog.records
        )

    def test_logs_on_apply(self, orch, caplog):
        orch.replace_agent_profiles(
            [AgentProfile(name="newprof", command="c", mode="cli")],
            source="api:create",
        )
        with caplog.at_level(logging.INFO, logger="oompah.orchestrator"):
            orch._apply_pending_agent_profiles()
        assert any(
            "Agent profiles reloaded" in rec.message
            and "newprof" in rec.message
            for rec in caplog.records
        )

    def test_caller_mutation_does_not_affect_queued_list(self, orch):
        # If the caller mutates the list after calling replace_agent_profiles,
        # the queued snapshot must NOT change — we defensive-copy.
        original = [AgentProfile(name="a", command="c", mode="cli")]
        orch.replace_agent_profiles(original)
        original.append(AgentProfile(name="b", command="c", mode="cli"))
        orch._apply_pending_agent_profiles()
        assert [p.name for p in orch.config.agent_profiles] == ["a"]

    def test_reload_config_clears_pending_swap(self, orch):
        # If a workflow file reload happens AFTER an API write queued a
        # swap, the workflow reload's profile list is authoritative — the
        # stale API queue must be discarded.
        orch.replace_agent_profiles([AgentProfile(name="api", command="c", mode="cli")])
        new_cfg = ServiceConfig()
        new_cfg.agent_profiles = [AgentProfile(name="from_workflow", command="c", mode="cli")]
        orch.reload_config(new_cfg, "")
        # The workflow's list is now active …
        assert [p.name for p in orch.config.agent_profiles] == ["from_workflow"]
        # … and the queued API swap was cleared, not applied.
        assert orch._apply_pending_agent_profiles() is False
        assert [p.name for p in orch.config.agent_profiles] == ["from_workflow"]

    def test_thread_safe_queue(self, orch):
        # Simulate HTTP threads racing with replace_agent_profiles.
        from concurrent.futures import ThreadPoolExecutor

        def push(i):
            orch.replace_agent_profiles([
                AgentProfile(name=f"p{i}", command="c", mode="cli"),
            ])

        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(push, range(50)))

        # Whatever races out, applying must produce a consistent single list
        # of length 1 (the last writer wins) — never a torn or empty queue.
        applied = orch._apply_pending_agent_profiles()
        assert applied is True
        assert len(orch.config.agent_profiles) == 1
        assert orch.config.agent_profiles[0].name.startswith("p")


class TestStoreOrchestratorIntegration:
    def test_store_callback_triggers_orch_reload(self, tmp_path):
        cfg = ServiceConfig(workspace_root=str(tmp_path / "ws"))
        cfg.agent_profiles = [AgentProfile(name="default", command="c", mode="cli")]
        orch = Orchestrator(
            cfg, str(tmp_path / "WORKFLOW.md"),
            state_path=str(tmp_path / "service_state.json"),
        )

        store = AgentProfileStore(path=str(tmp_path / "agent_profiles.json"))
        store.set_reload_callback(
            lambda profs, src: orch.replace_agent_profiles(profs, source=f"api:{src}"),
        )
        # Before the API write, only 'default' is configured
        assert [p.name for p in orch.config.agent_profiles] == ["default"]

        store.create({"name": "quick", "mode": "cli", "command": "claude"})
        # The callback queued the swap; tick simulation applies it.
        applied = orch._apply_pending_agent_profiles()
        assert applied is True
        names = [p.name for p in orch.config.agent_profiles]
        assert sorted(names) == ["quick"]  # JSON-store overrides config seed

    def test_callback_logs_with_api_source(self, tmp_path, caplog):
        cfg = ServiceConfig(workspace_root=str(tmp_path / "ws"))
        cfg.agent_profiles = []
        orch = Orchestrator(
            cfg, str(tmp_path / "WORKFLOW.md"),
            state_path=str(tmp_path / "service_state.json"),
        )
        store = AgentProfileStore(path=str(tmp_path / "agent_profiles.json"))
        store.set_reload_callback(
            lambda profs, src: orch.replace_agent_profiles(profs, source=f"api:{src}"),
        )
        with caplog.at_level(logging.INFO, logger="oompah.orchestrator"):
            store.create({"name": "quick", "mode": "cli", "command": "claude"})
        # Operator log shows the API path with its source ("api:create"),
        # distinguishing it from a workflow file reload.
        assert any(
            "Agent profiles reload queued" in rec.message
            and "api:create" in rec.message
            for rec in caplog.records
        )

    @pytest.mark.asyncio
    async def test_tick_applies_pending_at_quiescent_point(self, tmp_path):
        """End-to-end: a queued swap is applied when the dispatch loop ticks."""
        cfg = ServiceConfig(workspace_root=str(tmp_path / "ws"))
        cfg.agent_profiles = [AgentProfile(name="default", command="c", mode="cli")]
        orch = Orchestrator(
            cfg, str(tmp_path / "WORKFLOW.md"),
            state_path=str(tmp_path / "service_state.json"),
        )

        # Queue a swap before any tick runs
        orch.replace_agent_profiles([
            AgentProfile(name="default", command="c", mode="cli"),
            AgentProfile(name="quick", command="c", mode="cli"),
        ])
        # Stub out the heavy tick handlers so we exercise just the
        # _apply_pending_agent_profiles step.
        async def _no_op():
            return None
        async def _no_op2():
            return (0.0, 0.0, 0.0)
        async def _no_dolt_sync():
            return 0.0

        orch._handle_reconcile = _no_op
        orch._handle_review_check = _no_op
        orch._handle_dispatch_needed = _no_op
        orch._handle_yolo_review = _no_op2
        orch._handle_dolt_sync = _no_dolt_sync
        orch._handle_auto_update = _no_op
        orch._maybe_run_watchdog = lambda: None

        await orch._tick()
        names = sorted(p.name for p in orch.config.agent_profiles)
        assert names == ["default", "quick"]
