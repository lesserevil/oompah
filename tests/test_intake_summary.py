from __future__ import annotations

from oompah.intake_summary import build_intake_summary


def test_missing_fields_summary_requires_requestor_info():
    summary = build_intake_summary(
        {
            "missing_fields": ["acceptance_criteria", "repro_steps"],
            "scope": "small",
            "requestor_approved": False,
            "owner_override": False,
            "decomposition_status": "not_needed",
            "last_validator_result": "fail",
        },
        issue_state="Proposed",
    )

    assert summary is not None
    assert summary["state"] == "missing-info"
    assert summary["missing_fields"] == ["acceptance_criteria", "repro_steps"]
    assert summary["next_action"] == (
        "Requestor needs to add: acceptance_criteria, repro_steps."
    )


def test_awaiting_requestor_approval_summary():
    summary = build_intake_summary(
        {
            "missing_fields": [],
            "scope": "small",
            "requestor_approved": False,
            "owner_override": False,
            "decomposition_status": "not_needed",
            "last_validator_result": "pass",
        },
        issue_state="Proposed",
    )

    assert summary is not None
    assert summary["state"] == "awaiting-requestor-approval"
    assert summary["requestor_approval_state"] == "awaiting"
    assert summary["owner_override_state"] == "none"


def test_awaiting_owner_review_summary_for_unvalidated_proposal():
    summary = build_intake_summary(None, issue_state="Proposed")

    assert summary is not None
    assert summary["state"] == "awaiting-owner-review"
    assert summary["decomposition_state"] == "not_needed"
    assert summary["next_action"] == "Owner needs to run or review intake validation."


def test_ready_for_backlog_summary_with_owner_override():
    summary = build_intake_summary(
        {
            "missing_fields": [],
            "scope": "large",
            "requestor_approved": False,
            "owner_override": True,
            "owner_actor": "owner",
            "decomposition_status": "accepted",
            "last_validator_result": "pass",
        },
        issue_state="Proposed",
    )

    assert summary is not None
    assert summary["state"] == "ready-for-backlog"
    assert summary["ready_for_backlog"] is True
    assert summary["owner_override_state"] == "active"
    assert summary["owner_actor"] == "owner"


def test_non_proposed_issue_without_metadata_has_no_summary():
    assert build_intake_summary(None, issue_state="Backlog") is None
