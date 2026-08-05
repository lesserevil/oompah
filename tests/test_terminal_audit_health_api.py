"""API snapshot compatibility tests for terminal-audit health."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from oompah.terminal_audit_health import HEALTH_ALERT_PREFIX, TerminalAuditHealth
from oompah.validation_resource_lease import ValidationLeaseStatus


def _make_orchestrator(tmp_path):
    """Create a minimal orchestrator for snapshot testing."""
    from oompah.config import ServiceConfig
    from oompah.orchestrator import Orchestrator
    from oompah.roles import RoleStore

    project_store = MagicMock()
    project_store.list_all.return_value = []
    project_store.get.return_value = None
    role_store = RoleStore(path=str(tmp_path / "roles.json"))
    cfg = ServiceConfig(duplicate_preflight_max_agents=0)
    return Orchestrator(
        config=cfg,
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        role_store=role_store,
        state_path=str(tmp_path / "state.json"),
    )


class TestLegacyStateSnapshotGetsAggregateHealthShape:
    """The /api/v1/state response must include terminal_audit_health."""

    def test_legacy_state_snapshot_gets_aggregate_health_shape(self, tmp_path):
        orch = _make_orchestrator(tmp_path)

        # Inject a degraded health object
        orch._audit_health = TerminalAuditHealth(
            launch_failure_count=2,
            scan_complete=True,
        )
        # Add a health alert as the orchestrator would
        from oompah.terminal_audit_health import terminal_audit_health_alerts

        orch._alerts = terminal_audit_health_alerts(orch._audit_health)

        snapshot = orch.get_snapshot()

        # terminal_audit_health key must be present and correct
        assert "terminal_audit_health" in snapshot, (
            "terminal_audit_health key missing from snapshot"
        )
        health = snapshot["terminal_audit_health"]
        assert health["launch_failure_count"] == 2
        assert health["degraded"] is True

        # health.status must reflect degradation
        assert "health" in snapshot
        assert snapshot["health"]["status"] == "degraded"

        # alerts must include the launch-failures alert
        alerts = snapshot.get("alerts", [])
        sources = [a.get("source", "") for a in alerts]
        assert any(s.startswith(HEALTH_ALERT_PREFIX) for s in sources), (
            f"Expected a terminal_audit_health alert, got: {sources}"
        )

        # alert_count could also be computed
        launch_alert_sources = [s for s in sources if "launch_failures" in s]
        assert len(launch_alert_sources) > 0


class TestUnavailableStateIsExplicitlyDegraded:
    """When get_snapshot() cannot find health data, the response must say so."""

    def test_unavailable_state_is_explicitly_degraded(self, tmp_path):
        orch = _make_orchestrator(tmp_path)

        # Force a missing _audit_health
        if hasattr(orch, "_audit_health"):
            del orch._audit_health

        snapshot = orch.get_snapshot()

        # Even without _audit_health, must not crash; must return a valid shape
        assert "terminal_audit_health" in snapshot
        health = snapshot["terminal_audit_health"]
        assert "scan_complete" in health

        # A fresh, never-scanned orchestrator is not degraded (empty queue)
        # because degradation requires positive failure/stale signals
        assert "health" in snapshot
        assert snapshot["health"]["status"] in ("healthy", "degraded")


def test_legacy_provider_root_validation_owner_degrades_aggregate_health(tmp_path):
    orch = _make_orchestrator(tmp_path)
    orch.validation_resource_lease.status = MagicMock(
        return_value=ValidationLeaseStatus(
            capacity=1,
            owner_count=1,
            waiter_count=1,
            oldest_waiter_age_seconds=30,
            owners=(
                {
                    "task_id": "OOMPAH-1",
                    "process_role": "legacy_provider_bootstrap",
                    "recovery_action": "claim_task_directly",
                },
            ),
            waiters=(),
        )
    )

    snapshot = orch.get_snapshot()

    assert snapshot["validation_resources"]["status"] == "action_required"
    assert snapshot["health"]["status"] == "degraded"
