"""Tests for the structured dashboard fact presentation boundary."""

from __future__ import annotations

from oompah.dashboard_alerts import normalize_alert, normalize_alerts
from oompah.orchestrator import Orchestrator


def test_normalize_alert_exposes_contract_and_redacts_detail() -> None:
    fact = normalize_alert(
        {
            "level": "warning",
            "source": "terminal_audit:project:task:audit",
            "message": "Audit is stale",
            "detail": "Authorization: Bearer top-secret-value",
            "action": "Requeue the audit",
            "attempts": 3,
        }
    )

    assert fact["action_required"] is True
    assert fact["severity"] == "warning"
    assert fact["stable_id"] == "terminal_audit:project:task:audit"
    assert fact["summary"] == "Audit is stale"
    assert fact["remediation"] == "Requeue the audit"
    assert fact["status"] == "active"
    assert fact["active"] is True
    assert fact["attempts"] == 3
    assert "top-secret-value" not in str(fact)
    assert "Authorization: Bearer" not in fact["detail"]


def test_normal_operating_recovery_is_status_not_actionable() -> None:
    fact = normalize_alert(
        {
            "level": "info",
            "source": "integration_retry:project:task",
            "recovery_state": "scheduled_retry",
            "action_required": False,
            "message": "Retry is scheduled",
            "next_retry_at": 123.0,
        }
    )

    assert fact["action_required"] is False
    assert fact["severity"] == "info"
    assert fact["recovery_state"] == "scheduled_retry"
    assert fact["status"] == "recovering"
    assert fact["active"] is True
    assert fact["next_retry_at"] == 123.0


def test_recovered_fact_is_not_active() -> None:
    fact = normalize_alert(
        {
            "level": "info",
            "source": "integration_retry:project:task",
            "recovery_state": "resolved",
            "action_required": False,
            "message": "Integration recovered",
        }
    )

    assert fact["status"] == "recovered"
    assert fact["lifecycle_state"] == "recovered"
    assert fact["recovered"] is True
    assert fact["active"] is False


def test_duplicate_source_prefers_highest_current_severity() -> None:
    facts = normalize_alerts(
        [
            {
                "level": "info",
                "source": "repo_hygiene_health",
                "action_required": False,
                "message": "Cleanup is scheduled",
                "inventory_count": 4,
            },
            {
                "level": "error",
                "source": "repo_hygiene_health",
                "action_required": True,
                "message": "Repository cleanup is blocked",
                "cleanup_error_count": 2,
            },
        ]
    )

    assert len(facts) == 1
    assert facts[0]["stable_id"] == "repo_hygiene_health"
    assert facts[0]["severity"] == "error"
    assert facts[0]["action_required"] is True
    assert facts[0]["cleanup_error_count"] == 2
    assert facts[0]["inventory_count"] == 4


def test_quality_gate_status_facts_are_actionable_only_when_failed() -> None:
    facts = Orchestrator._quality_gate_dashboard_alerts(
        {
            "active": [
                {
                    "project_id": "project",
                    "task_id": "TASK-1",
                    "head_sha": "abcdef1234567890",
                }
            ],
            "recent": [
                {
                    "project_id": "project",
                    "task_id": "TASK-2",
                    "head_sha": "1234567890abcdef",
                    "status": "timed_out",
                    "command": "make test",
                }
            ],
        }
    )

    assert facts[0]["action_required"] is False
    assert facts[0]["recovery_state"] == "running"
    assert facts[1]["action_required"] is True
    assert facts[1]["severity"] == "error"


def test_api_enrichment_normalizes_cached_alerts() -> None:
    from oompah.server import _enrich_state_snapshot

    enriched = _enrich_state_snapshot(
        {
            "alerts": [
                {
                    "level": "warning",
                    "source": "state_snapshot",
                    "message": "State snapshot is not available yet.",
                }
            ]
        }
    )

    alert = enriched["alerts"][0]
    assert alert["action_required"] is True
    assert alert["stable_id"] == "state_snapshot"
    assert alert["summary"] == "State snapshot is not available yet."
