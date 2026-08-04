"""Tests for stable workflow reason codes and bounded liveness SLOs."""

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from oompah.workflow_contract import (
    CANONICAL_STATUSES,
    LIFECYCLE_FINAL_STATUSES,
    NEEDS_HUMAN,
    OPEN,
    READY_TO_INTEGRATE,
    STATUS_CONTRACTS,
)
from oompah.workflow_reasons import (
    LIVENESS_SLOS,
    REASON_DEFINITIONS,
    REASON_SCHEMA_VERSION,
    REASON_TAXONOMY_VERSION,
    AlertSeverity,
    ReasonClass,
    WorkflowReason,
    build_workflow_reason,
    validate_reason_taxonomy,
    validate_workflow_reason,
)

NOW = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)


def test_reason_serialization_is_stable_and_evidence_keys_are_sorted():
    reason = build_workflow_reason(
        "integration.queued",
        READY_TO_INTEGRATE,
        observed_at=NOW,
        evidence={
            "target_branch": "epic-OOMPAH-1",
            "job_id": "job-1",
            "head_sha": "abc1234",
        },
    )

    expected = {
        "schema_version": REASON_SCHEMA_VERSION,
        "taxonomy_version": REASON_TAXONOMY_VERSION,
        "code": "integration.queued",
        "status": READY_TO_INTEGRATE,
        "classification": "normal",
        "severity": "none",
        "subsystem": "integrator",
        "observed_at": "2026-08-04T12:00:00+00:00",
        "reassess_at": "2026-08-04T12:10:00+00:00",
        "evidence": {
            "head_sha": "abc1234",
            "job_id": "job-1",
            "target_branch": "epic-OOMPAH-1",
        },
        "operator_remedy": None,
        "unknown_code": False,
    }
    assert reason.to_dict() == expected
    assert json.dumps(reason.to_dict(), sort_keys=True) == json.dumps(
        WorkflowReason.from_dict(expected).to_dict(), sort_keys=True
    )


def test_unknown_future_reason_code_round_trips_without_losing_severity():
    payload = {
        "schema_version": 2,
        "taxonomy_version": "2.3",
        "code": "future_scheduler.partition_unavailable",
        "status": OPEN,
        "classification": "action_required",
        "severity": "warning",
        "subsystem": "future_scheduler",
        "observed_at": "2026-08-04T12:00:00Z",
        "reassess_at": "2026-08-04T12:01:00Z",
        "evidence": {"partition": "west"},
        "operator_remedy": "Restore the partition.",
    }

    reason = WorkflowReason.from_dict(payload)

    assert reason.unknown_code is True
    assert reason.schema_version == 2
    assert reason.taxonomy_version == "2.3"
    assert reason.classification == ReasonClass.ACTION_REQUIRED
    assert reason.severity == AlertSeverity.WARNING
    assert reason.subsystem == "future_scheduler"
    assert reason.evidence == {"partition": "west"}
    assert validate_workflow_reason(reason) == ()


def test_unknown_reason_without_explicit_presentation_defaults_to_information():
    reason = WorkflowReason.from_dict(
        {
            "code": "future.normal_condition",
            "status": OPEN,
            "observed_at": "2026-08-04T12:00:00Z",
            "reassess_at": "2026-08-04T12:01:00Z",
            "evidence": {},
        }
    )
    assert reason.classification == ReasonClass.INFORMATIONAL
    assert reason.severity == AlertSeverity.INFO


def test_normal_and_recovery_conditions_never_map_to_warnings():
    for definition in REASON_DEFINITIONS.values():
        if (
            definition.classification == ReasonClass.NORMAL
            or "recovery" in definition.code
        ):
            assert definition.severity not in {
                AlertSeverity.WARNING,
                AlertSeverity.CRITICAL,
            }


def test_action_required_reasons_have_a_visible_remedy_and_warning_severity():
    action_required = [
        definition
        for definition in REASON_DEFINITIONS.values()
        if definition.classification == ReasonClass.ACTION_REQUIRED
    ]
    assert action_required
    for definition in action_required:
        assert definition.severity == AlertSeverity.WARNING
        assert definition.operator_remedy


def test_builder_rejects_missing_evidence_and_wrong_status():
    with pytest.raises(ValueError, match="missing evidence"):
        build_workflow_reason(
            "integration.queued",
            READY_TO_INTEGRATE,
            observed_at=NOW,
            evidence={"job_id": "job-1"},
        )
    with pytest.raises(ValueError, match="does not apply"):
        build_workflow_reason(
            "integration.queued",
            OPEN,
            observed_at=NOW,
            evidence={
                "job_id": "job-1",
                "head_sha": "abc1234",
                "target_branch": "main",
            },
        )


def test_reassessment_deadline_is_positive_and_cannot_exceed_slo():
    maximum = LIVENESS_SLOS["dispatch_latency"].max_reassessment_seconds
    with pytest.raises(ValueError, match="between 1"):
        build_workflow_reason(
            "dispatch.eligible",
            OPEN,
            observed_at=NOW,
            evidence={"candidate_generation": "g1"},
            reassessment_seconds=0,
        )
    with pytest.raises(ValueError, match=str(maximum)):
        build_workflow_reason(
            "dispatch.eligible",
            OPEN,
            observed_at=NOW,
            evidence={"candidate_generation": "g1"},
            reassessment_seconds=maximum + 1,
        )


def test_instance_validator_detects_slo_breach_and_schema_mismatch():
    reason = build_workflow_reason(
        "dispatch.eligible",
        OPEN,
        observed_at=NOW,
        evidence={"candidate_generation": "g1"},
    )
    too_late = replace(
        reason,
        reassess_at=(NOW + timedelta(days=1)).isoformat(),
    )
    assert "reassessment exceeds SLO 'dispatch_latency'" in validate_workflow_reason(
        too_late
    )

    wrong_severity = replace(reason, severity=AlertSeverity.WARNING)
    assert "severity does not match reason definition" in validate_workflow_reason(
        wrong_severity
    )


def test_parser_rejects_unbounded_or_naive_deadlines():
    base = {
        "code": "future.normal_condition",
        "status": OPEN,
        "observed_at": "2026-08-04T12:00:00Z",
        "reassess_at": "2026-08-04T12:01:00Z",
        "evidence": {},
    }
    with pytest.raises(ValueError, match="later than"):
        WorkflowReason.from_dict({**base, "reassess_at": base["observed_at"]})
    with pytest.raises(ValueError, match="timezone"):
        WorkflowReason.from_dict({**base, "reassess_at": "2026-08-04T12:01:00"})

    with pytest.raises(ValueError, match="timezone"):
        build_workflow_reason(
            "dispatch.eligible",
            OPEN,
            observed_at=datetime(2026, 8, 4, 12, 0),
            evidence={"candidate_generation": "g1"},
        )


def test_every_nonfinal_status_has_reason_coverage_and_bounded_slo():
    nonfinal = set(CANONICAL_STATUSES) - set(LIFECYCLE_FINAL_STATUSES)
    covered = {
        status
        for definition in REASON_DEFINITIONS.values()
        if definition.code != "restart.reconciling"
        for status in definition.statuses
    }
    assert nonfinal <= covered
    for status in nonfinal:
        slo_key = STATUS_CONTRACTS[status].reassessment.slo_key
        assert slo_key in LIVENESS_SLOS
        assert LIVENESS_SLOS[slo_key].max_reassessment_seconds > 0


def test_operator_action_reason_has_required_evidence_and_remedy():
    reason = build_workflow_reason(
        "operator.action_required",
        NEEDS_HUMAN,
        observed_at=NOW,
        evidence={"action_code": "restore_transport", "action_detail": "auditor"},
    )
    assert reason.classification == ReasonClass.ACTION_REQUIRED
    assert reason.severity == AlertSeverity.WARNING
    assert reason.operator_remedy


def test_static_taxonomy_is_valid_and_read_only():
    assert validate_reason_taxonomy() == ()
    with pytest.raises(TypeError):
        REASON_DEFINITIONS["custom"] = REASON_DEFINITIONS[  # type: ignore[index]
            "dispatch.eligible"
        ]
    with pytest.raises(TypeError):
        LIVENESS_SLOS["custom"] = LIVENESS_SLOS[  # type: ignore[index]
            "dispatch_latency"
        ]
