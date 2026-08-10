"""Production-like state samples for the workflow rollout canary gate."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.workflow_rollout_check import evaluate_snapshot, main


ROOT = Path(__file__).resolve().parents[1]

_AUDIT_DEGRADATION_COUNTS = (
    "launch_failure_count",
    "transport_failure_count",
    "policy_incompatibility_count",
    "configuration_error_count",
    "finalization_failure_count",
    "stale_pending_count",
    "stale_in_validation_count",
    "retry_exhausted_count",
    "transport_retry_pending_count",
    "quarantined_count",
)


def terminal_audit_health(*, scan_complete: bool = True) -> dict:
    return {
        **{field: 0 for field in _AUDIT_DEGRADATION_COUNTS},
        "scan_complete": scan_complete,
        "scan_error_count": 0,
        "degraded": not scan_complete,
    }


def healthy_snapshot() -> dict:
    domains = ("implementation", "review", "integration", "epic")
    return {
        "alerts": [{"level": "info", "source": "normal:retry"}],
        "global_alerts": [],
        "health": {
            "status": "healthy",
            "terminal_audit": terminal_audit_health(),
            "validation_resources": {"status": "idle"},
            "workflow_jobs": {"quarantined": 0},
            "workflow_liveness": {
                "enabled": True,
                "status": "healthy",
                "degraded": False,
                "scan_complete": True,
            },
        },
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
            "leases": {
                "running": 1,
                "expired": 0,
                "quarantined": 0,
                "oldest_quarantined_age_seconds": None,
            },
            "states": {"running": 1, "queued": 2},
            "current_states": {"exhausted": 0},
        },
    }


def provisional_snapshot() -> dict:
    snapshot = healthy_snapshot()
    snapshot["health"]["status"] = "degraded"
    snapshot["health"]["terminal_audit"] = terminal_audit_health(scan_complete=False)
    snapshot["audits"] = {
        "candidate_scan_complete": False,
        "budget_deferred": True,
        "continuation_requested": True,
        "health_scan_error_count": 0,
    }
    snapshot["alerts"].append(
        {
            "source": "terminal_audit_health:scan",
            "level": "info",
            "action_required": False,
            "recovery_state": "automatic_recovery",
        }
    )
    return snapshot


def run_sequence(snapshots: list[dict], *, duration: int) -> int:
    clock = [0.0]

    def advance(seconds: float) -> None:
        clock[0] += seconds

    with (
        patch("scripts.workflow_rollout_check.load_client_environment"),
        patch(
            "scripts.workflow_rollout_check._read_snapshot",
            side_effect=snapshots,
        ),
        patch(
            "scripts.workflow_rollout_check.time.monotonic",
            side_effect=lambda: clock[0],
        ),
        patch(
            "scripts.workflow_rollout_check.time.sleep",
            side_effect=advance,
        ),
    ):
        return main(
            [
                "--duration-seconds",
                str(duration),
                "--sample-interval-seconds",
                "1",
            ]
        )


def test_production_like_soak_sample_passes_with_normal_active_work():
    result = evaluate_snapshot(healthy_snapshot())

    assert result.healthy
    assert result.failures == ()


def test_budgeted_audit_continuation_is_provisional_not_healthy():
    result = evaluate_snapshot(provisional_snapshot())

    assert not result.healthy
    assert result.provisional
    assert result.failures == ()


def test_canary_accepts_healthy_provisional_healthy_sequence():
    assert (
        run_sequence(
            [healthy_snapshot(), provisional_snapshot(), healthy_snapshot()],
            duration=2,
        )
        == 0
    )


def test_canary_accepts_provisional_then_complete_sequence():
    assert run_sequence([provisional_snapshot(), healthy_snapshot()], duration=1) == 0


def test_canary_rejects_window_with_only_provisional_samples(capsys):
    provisional = provisional_snapshot()

    assert run_sequence([provisional, provisional, provisional], duration=2) == 1
    assert "terminal-audit health did not complete" in capsys.readouterr().err


def test_once_rejects_provisional_sample(capsys):
    with (
        patch("scripts.workflow_rollout_check.load_client_environment"),
        patch(
            "scripts.workflow_rollout_check._read_snapshot",
            return_value=provisional_snapshot(),
        ),
    ):
        result = main(["--once"])

    assert result == 1
    assert "terminal-audit health did not complete" in capsys.readouterr().err


def test_canary_rejects_scan_error_instead_of_treating_it_as_provisional():
    snapshot = provisional_snapshot()
    snapshot["health"]["terminal_audit"]["scan_error_count"] = 1
    snapshot["audits"]["health_scan_error_count"] = 1

    result = evaluate_snapshot(snapshot)

    assert not result.healthy
    assert not result.provisional
    assert "service health is not healthy" in result.failures


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("budget_deferred", False),
        ("continuation_requested", False),
        ("candidate_scan_complete", True),
    ),
)
def test_canary_rejects_partial_scan_without_exact_continuation_telemetry(
    field: str,
    value: bool,
):
    snapshot = provisional_snapshot()
    snapshot["audits"][field] = value

    result = evaluate_snapshot(snapshot)

    assert not result.healthy
    assert not result.provisional
    assert "service health is not healthy" in result.failures


@pytest.mark.parametrize("counter", _AUDIT_DEGRADATION_COUNTS)
def test_canary_rejects_real_audit_failure_during_partial_scan(
    counter: str,
):
    snapshot = provisional_snapshot()
    snapshot["health"]["terminal_audit"][counter] = 1

    result = evaluate_snapshot(snapshot)

    assert not result.healthy
    assert not result.provisional
    assert "service health is not healthy" in result.failures


def test_canary_rejects_unrelated_degradation_during_partial_scan():
    snapshot = provisional_snapshot()
    snapshot["health"]["workflow_liveness"]["status"] = "degraded"
    snapshot["health"]["workflow_liveness"]["degraded"] = True

    result = evaluate_snapshot(snapshot)

    assert not result.healthy
    assert not result.provisional
    assert "service health is not healthy" in result.failures


def test_canary_stops_on_real_failure_after_provisional_sample():
    failed = provisional_snapshot()
    failed["health"]["terminal_audit"]["quarantined_count"] = 1

    assert run_sequence([provisional_snapshot(), failed], duration=2) == 1


def test_canary_rejects_healthy_status_without_complete_audit_coverage():
    snapshot = healthy_snapshot()
    snapshot["health"]["terminal_audit"]["scan_complete"] = False

    result = evaluate_snapshot(snapshot)

    assert not result.healthy
    assert not result.provisional
    assert "terminal-audit health coverage is not complete" in result.failures


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


def test_canary_rejects_quarantined_workflow_call():
    snapshot = healthy_snapshot()
    snapshot["workflow_jobs"]["leases"].update(
        {
            "quarantined": 1,
            "oldest_quarantined_age_seconds": 75.0,
        }
    )

    result = evaluate_snapshot(snapshot)

    assert not result.healthy
    assert "quarantined durable workflow calls remain" in result.failures


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
