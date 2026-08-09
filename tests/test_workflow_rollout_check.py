"""Production-like state samples for the workflow rollout canary gate."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from scripts.workflow_rollout_check import evaluate_snapshot


ROOT = Path(__file__).resolve().parents[1]


def healthy_snapshot() -> dict:
    domains = ("implementation", "review", "integration", "epic")
    return {
        "alerts": [{"level": "info", "source": "normal:retry"}],
        "global_alerts": [],
        "health": {"status": "healthy"},
        "workflow_runtime": {
            "mode": "shadow",
            "started": True,
            "binding_topology_current": True,
            "domain_modes": {domain: "shadow" for domain in domains},
            "rollout": [
                {
                    "domain": domain,
                    "mode": "shadow",
                    "last_success_at": 20.0,
                    "last_failure_at": 10.0,
                }
                for domain in domains
            ],
            "rollout_gate": {
                "all_domains_ready": True,
                "min_shadow_sweeps": 3,
                "min_shadow_seconds": 300,
            },
        },
        "workflow_jobs": {
            "leases": {"running": 1, "expired": 0},
            "states": {"running": 1, "queued": 2},
            "current_states": {"exhausted": 0},
        },
    }


def test_production_like_soak_sample_passes_with_normal_active_work():
    result = evaluate_snapshot(healthy_snapshot())

    assert result.healthy
    assert result.failures == ()


def test_canary_rejects_actionable_alert_and_expired_lease():
    snapshot = healthy_snapshot()
    snapshot["global_alerts"] = [
        {"source": "operator:action_required:OOMPAH-1"}
    ]
    snapshot["workflow_jobs"]["leases"]["expired"] = 1

    result = evaluate_snapshot(snapshot)

    assert not result.healthy
    assert "1 operator-actionable alert(s) remain" in result.failures
    assert "expired durable workflow leases remain" in result.failures


def test_canary_ignores_historical_exhaustion_with_current_replacement():
    snapshot = healthy_snapshot()
    snapshot["workflow_jobs"]["states"]["exhausted"] = 1

    result = evaluate_snapshot(snapshot)

    assert result.healthy


def test_canary_rejects_current_exhaustion():
    snapshot = healthy_snapshot()
    snapshot["workflow_jobs"]["current_states"]["exhausted"] = 1

    result = evaluate_snapshot(snapshot)

    assert not result.healthy
    assert "exhausted durable workflow jobs remain" in result.failures


def test_canary_falls_back_to_raw_exhaustion_for_older_server():
    snapshot = healthy_snapshot()
    snapshot["workflow_jobs"].pop("current_states")
    snapshot["workflow_jobs"]["states"]["exhausted"] = 1

    result = evaluate_snapshot(snapshot)

    assert not result.healthy
    assert "exhausted durable workflow jobs remain" in result.failures


def test_canary_rejects_restart_staleness_and_latest_failed_shadow_sample():
    snapshot = deepcopy(healthy_snapshot())
    snapshot["workflow_runtime"]["binding_topology_current"] = False
    snapshot["workflow_runtime"]["rollout"][0]["last_failure_at"] = 30.0

    result = evaluate_snapshot(snapshot)

    assert not result.healthy
    assert "workflow project binding topology is stale" in result.failures
    assert "implementation: latest shadow sweep failed" in result.failures


def test_canary_rejects_domain_that_has_not_entered_shadow():
    snapshot = healthy_snapshot()
    snapshot["workflow_runtime"]["domain_modes"]["review"] = "off"

    result = evaluate_snapshot(snapshot)

    assert not result.healthy
    assert "one or more workflow domains remain off" in result.failures


def test_canary_rejects_incomplete_persisted_soak_gate():
    snapshot = healthy_snapshot()
    snapshot["workflow_runtime"]["rollout_gate"]["all_domains_ready"] = False

    result = evaluate_snapshot(snapshot)

    assert not result.healthy
    assert "persisted workflow rollout gate is not qualified" in result.failures


def test_shadow_canary_does_not_require_legacy_shadow_diagnostics():
    snapshot = healthy_snapshot()

    result = evaluate_snapshot(snapshot)

    assert result.healthy


def test_shadow_canary_ignores_stale_retired_legacy_shadow_diagnostics():
    snapshot = healthy_snapshot()
    snapshot["workflow_shadow"] = {
        "mode": "shadow",
        "last_evaluated_at": None,
        "divergence_count": 2,
    }

    result = evaluate_snapshot(snapshot)

    assert result.healthy


def test_enforce_canary_uses_persisted_gate_without_requiring_new_shadow_sample():
    snapshot = healthy_snapshot()
    snapshot["workflow_runtime"]["mode"] = "enforce"
    snapshot["workflow_runtime"]["domain_modes"] = {
        domain: "enforce"
        for domain in snapshot["workflow_runtime"]["domain_modes"]
    }
    result = evaluate_snapshot(snapshot)

    assert result.healthy


def test_supported_environment_and_operator_contracts_are_documented():
    env = (ROOT / ".env.example").read_text(encoding="utf-8")
    for domain in ("IMPLEMENTATION", "REVIEW", "INTEGRATION", "EPIC"):
        assert f"OOMPAH_WORKFLOW_{domain}_MODE=off" in env
    assert "# OOMPAH_WORKFLOW_ENGINE_MODE=" not in env
    assert "OOMPAH_WORKFLOW_ROLLOUT_MIN_SHADOW_SWEEPS=3" in env
    assert "OOMPAH_WORKFLOW_ROLLOUT_MIN_SHADOW_SECONDS=300" in env

    runbook = (ROOT / "docs" / "workflow-rollout.md").read_text(
        encoding="utf-8"
    )
    for phrase in (
        "Why a task is not progressing",
        "action_required: true",
        "Reassessment deadlines",
        "Upgrade, restart, and rollback",
        "make workflow-rollout-check",
        "```mermaid",
    ):
        assert phrase in runbook


def test_makefile_exposes_rollout_canary_target():
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "workflow-rollout-check: setup" in makefile
    assert "scripts/workflow_rollout_check.py" in makefile
