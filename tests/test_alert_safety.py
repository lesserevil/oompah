"""Regression and security tests for dashboard alert projections."""

from __future__ import annotations

from pathlib import Path

from oompah.alert_safety import (
    ALERT_DIAGNOSTIC_MAX_LENGTH,
    ALERT_SUMMARY_MAX_LENGTH,
    ALERT_TITLE_MAX_LENGTH,
    TRUNCATION_MARKER,
)
from oompah.dashboard_alerts import normalize_alert, normalize_alerts


def test_exocomp_147_rebase_transcript_is_compact_but_available_on_demand() -> None:
    """The production rebase-conflict shape never reaches compact fields."""

    transcript = (
        Path(__file__).parent / "fixtures" / "exocomp_147_rebase_conflict.txt"
    ).read_text(encoding="utf-8")
    alert = normalize_alert(
        {
            "level": "warning",
            "source": "integration_retry:project:EXOCOMP-147",
            "message": transcript,
            "diagnostic": transcript,
        }
    )

    assert "\n" not in alert["title"]
    assert "\n" not in alert["summary"]
    assert "\n" not in alert["message"]
    assert len(alert["title"]) <= ALERT_TITLE_MAX_LENGTH
    assert len(alert["summary"]) <= ALERT_SUMMARY_MAX_LENGTH
    assert alert["diagnostic_available"] is True
    assert "CONFLICT" in alert["diagnostic"]
    assert "EXOCOMP-147" in alert["diagnostic"]


def test_alert_projection_redacts_credentials_and_bounds_html_control_input() -> None:
    alert = normalize_alert(
        {
            "source": "transport",
            "title": "<script>alert(1)</script>\x00 provider failure",
            "message": (
                "Authorization: Bearer bearer-secret\n"
                "token=plain-token\n<script>break layout</script>"
            ),
            "diagnostic": "Authorization: Bearer bearer-secret\npassword=plain-password",
        }
    )

    serialized = repr(alert)
    assert "bearer-secret" not in serialized
    assert "plain-token" not in serialized
    assert "plain-password" not in serialized
    assert "\x00" not in serialized
    # The API carries text, while the renderer's esc() is responsible for
    # HTML context encoding.  The compact fields are still bounded and safe
    # to pass through that renderer boundary.
    assert len(alert["title"]) <= ALERT_TITLE_MAX_LENGTH
    assert "<script>" in alert["title"]
    assert len(alert["diagnostic"]) <= ALERT_DIAGNOSTIC_MAX_LENGTH


def test_unicode_truncation_is_deterministic_and_keeps_accessible_marker() -> None:
    value = "前��" * 3000
    first = normalize_alert({"source": "audit", "message": value})
    second = normalize_alert({"source": "audit", "message": value})

    assert first == second
    assert len(first["summary"]) <= ALERT_SUMMARY_MAX_LENGTH
    assert first["summary"].endswith(TRUNCATION_MARKER)
    assert first["diagnostic"].endswith(TRUNCATION_MARKER)


def test_concise_alerts_keep_their_existing_explanation_and_remediation() -> None:
    alert = normalize_alert(
        {
            "source": "quality_gate:task-1",
            "title": "Quality gate failed",
            "message": "The configured quality gate failed.",
            "detail": "Run the gate locally to inspect the failing check.",
            "action": "Fix the check, push, and resubmit.",
        }
    )

    assert alert["title"] == "Quality gate failed"
    assert alert["message"] == "The configured quality gate failed."
    assert alert["detail"] == "Run the gate locally to inspect the failing check."
    assert alert["action"] == "Fix the check, push, and resubmit."
    assert "diagnostic" not in alert


def test_api_boundary_projects_legacy_and_non_mapping_alerts() -> None:
    alerts = normalize_alerts(
        [
            {"source": "legacy", "message": "line one\nline two"},
            "not an alert",
            {"source": "audit", "title": "Healthy", "message": "All clear"},
        ]
    )

    assert len(alerts) == 2
    assert all("\n" not in item["message"] for item in alerts)
    assert alerts[0]["diagnostic_available"] is True
    assert alerts[1]["message"] == "All clear"


def test_transcript_cannot_bypass_projection_through_summary_or_title() -> None:
    transcript = "provider response\nrequest failed\nretry exhausted"

    for field in ("summary", "title"):
        alert = normalize_alert(
            {
                "source": "transport:provider",
                field: transcript,
            }
        )

        assert "\n" not in alert["title"]
        assert "\n" not in alert["summary"]
        assert alert["diagnostic"] == transcript
        assert alert["diagnostic_available"] is True


def test_server_response_boundary_reprojects_cached_alerts() -> None:
    from oompah import server

    enriched = server._enrich_state_snapshot(
        {
            "alerts": [
                {
                    "source": "cached",
                    "message": "cached line one\ncached line two",
                }
            ]
        }
    )

    alert = enriched["alerts"][0]
    assert "\n" not in alert["message"]
    assert alert["diagnostic"] == "cached line one\ncached line two"


def test_stale_server_snapshot_withholds_pid_backed_gate_activity(
    monkeypatch,
) -> None:
    from oompah import server

    running_gate = {
        "pid": 1234,
        "status": "running",
        "project_id": "project-1",
        "task_id": "OOMPAH-1083",
        "head_sha": "a" * 40,
    }
    quality_gates = {"status": "running", "active": [running_gate], "recent": []}
    snapshot = {
        "state_snapshot_stale": True,
        "quality_gates": quality_gates,
        "health": {"quality_gates": quality_gates},
        "alerts": [
            {
                "source": f"quality_gate:project-1:OOMPAH-1083:{'a' * 40}",
                "severity": "info",
                "action_required": False,
                "recovery_state": "running",
                "active": True,
                "summary": "Branch quality gate is running for OOMPAH-1083",
            },
            {
                "source": f"quality_gate:project-1:OOMPAH-1082:{'b' * 40}",
                "severity": "warning",
                "action_required": True,
                "recovery_state": "failed",
                "active": True,
                "summary": "Branch quality gate failed for OOMPAH-1082",
            },
        ],
    }

    enriched = server._enrich_state_snapshot(snapshot)

    assert enriched["quality_gates"]["active"] == []
    assert enriched["quality_gates"]["status"] == "snapshot_stale"
    assert enriched["quality_gates"]["stale_active_count"] == 1
    assert enriched["quality_gates"]["active_snapshot_stale"] is True
    assert enriched["health"]["quality_gates"]["active"] == []
    assert enriched["health"]["quality_gates"]["status"] == "snapshot_stale"
    assert [alert["recovery_state"] for alert in enriched["alerts"]] == ["failed"]
    assert enriched["global_alerts"] == []
    # Enrichment is shared by REST/WebSocket but must not corrupt their shared
    # cached source or the revision/sequence cut that owns it.
    assert snapshot["quality_gates"]["active"] == [running_gate]
    assert snapshot["health"]["quality_gates"]["active"] == [running_gate]

    monkeypatch.setattr(
        server,
        "_read_state_snapshot_with_revision",
        lambda *, allow_stale: (snapshot, 73),
    )
    message = server._current_state_message()
    assert message["type"] == "state"
    assert message["state_revision"] == 73
    assert message["data"]["quality_gates"]["active"] == []


def test_stale_empty_gate_summary_cannot_remain_running() -> None:
    from oompah import server

    quality_gates = {"status": "running", "active": [], "recent": []}
    snapshot = {
        "quality_gates": quality_gates,
        "health": {"quality_gates": quality_gates, "other": {"status": "failed"}},
        "alerts": [],
    }

    enriched = server._enrich_state_snapshot(
        snapshot,
        snapshot_updated_at=100.0,
        now_monotonic=100.0 + server._STATE_SNAPSHOT_MAX_AGE_S + 1.0,
    )

    assert enriched["state_snapshot_stale"] is True
    assert enriched["quality_gates"] == {
        "status": "snapshot_stale",
        "active": [],
        "recent": [],
    }
    assert enriched["health"]["quality_gates"]["status"] == "snapshot_stale"
    assert enriched["health"]["other"] == {"status": "failed"}
    assert snapshot["quality_gates"]["status"] == "running"
    assert snapshot["health"]["quality_gates"]["status"] == "running"
