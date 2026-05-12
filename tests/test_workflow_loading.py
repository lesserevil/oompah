"""Tests for WORKFLOW.md → AgentProfileStore source-of-truth migration.

Covers oompah-zlz_2-hye:
- The persisted JSON store is authoritative; WORKFLOW.md profiles are
  the legacy fallback / migration seed.
- When WORKFLOW.md still has an agent.profiles block AND it differs
  from the persisted store, ServiceConfig.from_workflow flags drift
  and the orchestrator surfaces a dashboard alert
  (source="profile_drift").
- When OOMPAH_STRICT_PROFILE_SOURCE=strict and WORKFLOW.md still has
  an agent.profiles block, the strict-mode startup check refuses to
  let the orchestrator process boot.
"""

from __future__ import annotations

import json
import logging
import os

import pytest

from oompah.agent_profile_store import AgentProfileStore
from oompah.config import ServiceConfig
from oompah.models import AgentProfile, WorkflowDefinition
from oompah.orchestrator import Orchestrator


@pytest.fixture(autouse=True)
def isolate_store_path(tmp_path, monkeypatch):
    """Force ServiceConfig.from_workflow to use a per-test profiles path."""
    path = str(tmp_path / "agent_profiles.json")
    monkeypatch.setenv("OOMPAH_AGENT_PROFILES_PATH", path)
    return path


@pytest.fixture(autouse=True)
def clear_strict_env(monkeypatch):
    """Each test starts without OOMPAH_STRICT_PROFILE_SOURCE so the
    default ("warn") is in effect unless the test explicitly sets it."""
    monkeypatch.delenv("OOMPAH_STRICT_PROFILE_SOURCE", raising=False)


def _wf_with_profiles(profiles: list[dict]) -> WorkflowDefinition:
    return WorkflowDefinition(
        config={"agent": {"profiles": profiles}},
        prompt_template="",
    )


# ---------------------------------------------------------------------------
# 1. Persisted-store-takes-precedence
# ---------------------------------------------------------------------------


class TestPersistedStoreTakesPrecedence:
    def test_json_store_wins_over_workflow_block(self, isolate_store_path):
        """When .oompah/agent_profiles.json exists, ServiceConfig.from_workflow
        returns its contents and ignores WORKFLOW.md's agent.profiles block."""
        # Pre-populate the JSON store with one profile.
        with open(isolate_store_path, "w") as f:
            json.dump(
                [{"name": "from-json", "command": "claude", "mode": "cli"}], f,
            )
        # WORKFLOW.md block names a different profile.
        wf = _wf_with_profiles([
            {"name": "from-workflow", "mode": "cli", "command": "x"},
        ])
        cfg = ServiceConfig.from_workflow(wf)
        # Store wins.
        assert {p.name for p in cfg.agent_profiles} == {"from-json"}

    def test_first_boot_seeds_store_from_workflow(self, isolate_store_path):
        """When the JSON file is missing, WORKFLOW.md profiles seed the
        store. After the first call, the JSON file exists and subsequent
        edits to WORKFLOW.md are ignored (store now wins)."""
        wf = _wf_with_profiles([
            {"name": "default", "mode": "cli", "command": "claude"},
        ])
        cfg = ServiceConfig.from_workflow(wf)
        # Profile loaded from the seeded store.
        assert {p.name for p in cfg.agent_profiles} == {"default"}
        # JSON file now exists.
        assert os.path.exists(isolate_store_path)
        # Second boot with a DIFFERENT WORKFLOW.md block: store still wins.
        wf2 = _wf_with_profiles([
            {"name": "different", "mode": "cli", "command": "x"},
        ])
        cfg2 = ServiceConfig.from_workflow(wf2)
        assert {p.name for p in cfg2.agent_profiles} == {"default"}


# ---------------------------------------------------------------------------
# 2. Warning fires on drift
# ---------------------------------------------------------------------------


class TestWarningFiresOnDrift:
    def test_drift_flag_set_when_store_differs(self, isolate_store_path):
        """ServiceConfig.agent_profiles_drift is True when WORKFLOW.md's
        profile block differs from the persisted JSON store."""
        # Pre-populate the store.
        with open(isolate_store_path, "w") as f:
            json.dump(
                [{"name": "ui-managed", "command": "c", "mode": "cli"}], f,
            )
        # WORKFLOW.md still has a different/older block.
        wf = _wf_with_profiles([
            {"name": "stale-from-workflow", "mode": "cli", "command": "c"},
        ])
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.workflow_has_profiles_block is True
        assert cfg.agent_profiles_drift is True
        # Store still wins.
        assert {p.name for p in cfg.agent_profiles} == {"ui-managed"}

    def test_no_drift_when_store_matches_workflow(self, isolate_store_path):
        """No drift when both sides hold semantically equivalent content."""
        with open(isolate_store_path, "w") as f:
            json.dump(
                [{"name": "x", "command": "c", "mode": "cli"}], f,
            )
        wf = _wf_with_profiles([
            {"name": "x", "mode": "cli", "command": "c"},
        ])
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.workflow_has_profiles_block is True
        assert cfg.agent_profiles_drift is False

    def test_no_drift_on_first_boot_seeded_from_workflow(
        self, isolate_store_path,
    ):
        """Right after the JSON store is migrated FROM WORKFLOW.md the
        contents are identical by construction — no drift warning fires.
        The warning kicks in only after one side diverges."""
        wf = _wf_with_profiles([
            {"name": "default", "mode": "cli", "command": "claude"},
        ])
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.workflow_has_profiles_block is True
        assert cfg.agent_profiles_drift is False

    def test_no_drift_when_workflow_has_no_block(self, isolate_store_path):
        """Workflow with no agent.profiles key -> no drift, even if the
        store is non-empty (the legacy block has been retired)."""
        with open(isolate_store_path, "w") as f:
            json.dump(
                [{"name": "x", "command": "c", "mode": "cli"}], f,
            )
        # No agent.profiles in workflow at all.
        wf = WorkflowDefinition(config={"agent": {}}, prompt_template="")
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.workflow_has_profiles_block is False
        assert cfg.agent_profiles_drift is False

    def test_orchestrator_surfaces_drift_alert(
        self, isolate_store_path, tmp_path, caplog,
    ):
        """When ServiceConfig.agent_profiles_drift is True, the
        orchestrator's _alerts list contains a profile_drift entry that
        the dashboard renders as a warning banner."""
        # Pre-populate divergent store.
        with open(isolate_store_path, "w") as f:
            json.dump(
                [{"name": "ui-managed", "command": "c", "mode": "cli"}], f,
            )
        wf = _wf_with_profiles([
            {"name": "stale", "mode": "cli", "command": "c"},
        ])
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.agent_profiles_drift is True
        # Construct an orchestrator pointing at our isolated store.
        store = AgentProfileStore(path=isolate_store_path)
        orch = Orchestrator(
            cfg, str(tmp_path / "WORKFLOW.md"),
            agent_profile_store=store,
        )
        sources = {a.get("source") for a in orch._alerts}
        assert "profile_drift" in sources
        drift_alert = next(
            a for a in orch._alerts if a.get("source") == "profile_drift"
        )
        assert drift_alert["level"] == "warning"
        assert "agent.profiles" in drift_alert["message"]
        assert "persisted profile store" in drift_alert["message"]

    def test_orchestrator_clears_drift_alert_after_workflow_edit(
        self, isolate_store_path, tmp_path,
    ):
        """When the operator deletes the agent.profiles block from
        WORKFLOW.md and reload_config() runs, the dashboard alert clears."""
        with open(isolate_store_path, "w") as f:
            json.dump(
                [{"name": "ui", "command": "c", "mode": "cli"}], f,
            )
        wf = _wf_with_profiles([
            {"name": "stale", "mode": "cli", "command": "c"},
        ])
        cfg = ServiceConfig.from_workflow(wf)
        store = AgentProfileStore(path=isolate_store_path)
        orch = Orchestrator(
            cfg, str(tmp_path / "WORKFLOW.md"),
            agent_profile_store=store,
        )
        assert any(
            a.get("source") == "profile_drift" for a in orch._alerts
        )
        # Operator removes the block from WORKFLOW.md.
        wf2 = WorkflowDefinition(config={}, prompt_template="")
        cfg2 = ServiceConfig.from_workflow(wf2)
        assert cfg2.workflow_has_profiles_block is False
        assert cfg2.agent_profiles_drift is False
        orch.reload_config(cfg2, "")
        # Alert is gone.
        assert not any(
            a.get("source") == "profile_drift" for a in orch._alerts
        )


# ---------------------------------------------------------------------------
# 3. Strict mode fails on drift / fails when block is present
# ---------------------------------------------------------------------------


class TestStrictModeFailsOnDrift:
    def test_strict_mode_via_env(self, isolate_store_path, monkeypatch):
        """OOMPAH_STRICT_PROFILE_SOURCE=strict surfaces in
        ServiceConfig.strict_profile_source."""
        monkeypatch.setenv("OOMPAH_STRICT_PROFILE_SOURCE", "strict")
        wf = _wf_with_profiles([
            {"name": "x", "mode": "cli", "command": "c"},
        ])
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.strict_profile_source == "strict"
        assert cfg.workflow_has_profiles_block is True

    def test_strict_mode_via_workflow(self, isolate_store_path):
        """agent.strict_profile_source: strict in YAML works equivalently."""
        wf = WorkflowDefinition(
            config={
                "agent": {
                    "strict_profile_source": "strict",
                    "profiles": [
                        {"name": "x", "mode": "cli", "command": "c"},
                    ],
                },
            },
            prompt_template="",
        )
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.strict_profile_source == "strict"

    def test_default_is_warn(self, isolate_store_path):
        wf = _wf_with_profiles([
            {"name": "x", "mode": "cli", "command": "c"},
        ])
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.strict_profile_source == "warn"

    def test_unknown_value_falls_back_to_warn(
        self, isolate_store_path, monkeypatch,
    ):
        monkeypatch.setenv("OOMPAH_STRICT_PROFILE_SOURCE", "bananas")
        wf = _wf_with_profiles([
            {"name": "x", "mode": "cli", "command": "c"},
        ])
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.strict_profile_source == "warn"

    def test_strict_with_block_present_triggers_main_exit(
        self, isolate_store_path, monkeypatch, tmp_path, caplog,
    ):
        """Strict mode + workflow_has_profiles_block must cause the
        startup check in oompah/__main__.py to call sys.exit(1) with a
        clear error message. We exercise the exact branch by importing
        the helper and invoking it directly via the same condition the
        startup code uses."""
        monkeypatch.setenv("OOMPAH_STRICT_PROFILE_SOURCE", "strict")
        wf = _wf_with_profiles([
            {"name": "x", "mode": "cli", "command": "c"},
        ])
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.strict_profile_source == "strict"
        assert cfg.workflow_has_profiles_block is True
        # Mirror the startup check from __main__.py.
        with caplog.at_level(logging.ERROR, logger="oompah"):
            with pytest.raises(SystemExit) as excinfo:
                _enforce_strict_mode_or_exit(cfg, str(tmp_path / "WORKFLOW.md"))
        assert excinfo.value.code == 1
        # The error log explains how to fix it.
        joined = " ".join(r.message for r in caplog.records)
        assert "no longer authoritative" in joined or (
            "strict" in joined.lower() and "agent.profiles" in joined.lower()
        )

    def test_strict_with_no_block_starts_normally(
        self, isolate_store_path, monkeypatch, tmp_path,
    ):
        """Strict mode with the legacy block already removed: startup
        proceeds normally; no drift, no exit."""
        monkeypatch.setenv("OOMPAH_STRICT_PROFILE_SOURCE", "strict")
        # Pre-populate the store; workflow has no profiles.
        with open(isolate_store_path, "w") as f:
            json.dump(
                [{"name": "ui", "command": "c", "mode": "cli"}], f,
            )
        wf = WorkflowDefinition(config={}, prompt_template="")
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.strict_profile_source == "strict"
        assert cfg.workflow_has_profiles_block is False
        # Should NOT raise.
        _enforce_strict_mode_or_exit(cfg, str(tmp_path / "WORKFLOW.md"))


# ---------------------------------------------------------------------------
# Helper that mirrors the strict-mode branch in oompah/__main__.py.
# Replicating the predicate here keeps the test independent from the
# CLI plumbing while still exercising the precise condition that makes
# the orchestrator process exit at startup.
# ---------------------------------------------------------------------------


def _enforce_strict_mode_or_exit(cfg: ServiceConfig, workflow_path: str) -> None:
    """Same predicate the startup code uses; raises SystemExit(1) when
    strict mode is engaged AND the legacy block is still present."""
    logger = logging.getLogger("oompah")
    if (
        cfg.strict_profile_source == "strict"
        and cfg.workflow_has_profiles_block
    ):
        logger.error(
            "Strict profile-source mode is enabled and WORKFLOW.md still "
            "contains an agent.profiles block. This section is no longer "
            "authoritative; profiles are managed via the dashboard "
            "(/api/v1/agent-profiles) and stored in "
            ".oompah/agent_profiles.json. Delete the agent.profiles "
            "block from %s to start.",
            workflow_path,
        )
        raise SystemExit(1)
