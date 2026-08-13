"""Tests for durable private-branch integration metadata."""

from types import SimpleNamespace
import hashlib

import pytest

from oompah.integration import (
    IntegrationRecord,
    REVIEW_GENERATION_REQUEUE_WAIT_REASON,
    accepted_submission_branch,
    assigned_work_branch,
    expected_submission_branch,
    direct_epic_maintenance_handoff_ready,
    is_direct_epic_maintenance_issue,
    parse_integration_record,
    requeue_standalone_review_generation,
    review_generation_requeue_marker,
    validate_submission_branch,
)


def _authoritative_noncanonical_helper(**overrides):
    generation = "f" * 64
    issue = {
        "id": "TRICKLE-141",
        "identifier": "TRICKLE-141",
        "title": "Rebase TRICKLE-130 onto epic-TRICKLE-127",
        "parent_id": "TRICKLE-130",
        "project_id": "proj-trickle",
        "work_branch": "TRICKLE-130",
        "target_branch": "epic-TRICKLE-127",
        "create_once": {
            "version": 1,
            "project_id": "proj-trickle",
            "operation_kind": "epic_rebase_helper",
            "creation_marker": "oompah-epic-rebase-reservation-v1:"
            + hashlib.sha256(
                f"proj-trickle\0TRICKLE-130\0{generation}".encode()
            ).hexdigest(),
        },
        "epic_rebase_target": {
            "version": 1,
            "epic_identifier": "TRICKLE-130",
            "epic_branch": "TRICKLE-130",
            "target_branch": "epic-TRICKLE-127",
            "resolution": "authoritative_parent",
        },
        "epic_rebase_authority": {
            "version": 1,
            "generation": generation,
            "task_id": "TRICKLE-141",
            "epic_identifier": "TRICKLE-130",
            "epic_branch": "TRICKLE-130",
            "epic_head": "a" * 40,
            "target_branch": "epic-TRICKLE-127",
            "target_head": "b" * 40,
        },
    }
    issue.update(overrides)
    return issue


def test_noncanonical_direct_maintenance_uses_explicit_scoped_authority():
    issue = _authoritative_noncanonical_helper()

    assert is_direct_epic_maintenance_issue(issue)
    assert direct_epic_maintenance_handoff_ready(
        issue,
        {
            "state": "integrated",
            "mode": "queue",
            "task_branch": "TRICKLE-130",
            "base_branch": "TRICKLE-130",
            "head_sha": "c" * 40,
            "integrated_sha": "c" * 40,
            "maintenance_publication_proven": True,
        },
    )


def test_native_noncanonical_helper_uses_creation_scope_when_model_is_unstamped():
    issue = _authoritative_noncanonical_helper(project_id=None)

    assert is_direct_epic_maintenance_issue(issue)


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("project_id", "proj-forged"),
        ("identifier", "TRICKLE-999"),
        ("parent_id", "TRICKLE-999"),
        ("work_branch", "forged-source"),
        ("target_branch", "forged-target"),
    ],
)
def test_explicit_direct_maintenance_rejects_conflicting_scope(field, replacement):
    issue = _authoritative_noncanonical_helper(**{field: replacement})

    assert not is_direct_epic_maintenance_issue(issue)


def test_incomplete_explicit_identity_disables_legacy_title_fallback():
    issue = _authoritative_noncanonical_helper(
        title="Rebase epic-TRICKLE-130 onto main",
        epic_rebase_authority=None,
    )

    assert not is_direct_epic_maintenance_issue(issue)


def test_integration_record_round_trips_all_supported_evidence():
    record = IntegrationRecord(
        state="ready",
        mode="standalone",
        post_landed_parent_id="ABC-1",
        task_branch="oompah/task/ABC-2",
        base_branch="epic-ABC-1",
        base_sha="a" * 40,
        head_sha="b" * 40,
        attempts=2,
        submitted_at="2026-07-29T12:00:00Z",
        updated_at="2026-07-29T12:01:00Z",
        dependency_heads={"ABC-1": "c" * 40},
        gate_outcome="cancelled_retryable",
        gate_cancellation={
            "cancelled_by": "operator:alice",
            "reason": "critical-path preemption",
        },
        wait_reason="nested_epic_base_stale",
        wait_generation="generation-1",
        required_base_missing=("epic-ABC-0", "ABC-1"),
    )

    assert IntegrationRecord.from_dict(record.to_dict()) == record


def test_review_generation_requeue_marker_requires_exact_complete_identity():
    valid = review_generation_requeue_marker("42", "a" * 40, "b" * 40)

    assert valid is not None
    assert valid.startswith("review:")
    assert review_generation_requeue_marker("", "a" * 40, "b" * 40) is None
    assert review_generation_requeue_marker("42", "short", "b" * 40) is None
    assert review_generation_requeue_marker("42", "a" * 41, "b" * 40) is None
    assert review_generation_requeue_marker("42", "a" * 40, None) is None


def test_requeue_standalone_review_generation_resets_stale_delivery_evidence():
    original = IntegrationRecord(
        state="integrated",
        mode="standalone",
        task_branch="TASK-1",
        base_branch="main",
        base_sha="a" * 40,
        head_sha="b" * 40,
        integrated_sha="b" * 40,
        attempts=3,
        last_error="stale failure",
        gate_outcome="passed",
        dependency_heads={"TASK-0": "c" * 40},
        required_base_missing=("TASK-0",),
    )

    replacement = requeue_standalone_review_generation(
        original,
        review_id="42",
        head_sha="d" * 40,
        base_sha="e" * 40,
        updated_at="2026-08-11T12:00:00+00:00",
    )

    assert replacement.state == "ready"
    assert replacement.head_sha == "d" * 40
    assert replacement.base_sha == "e" * 40
    assert replacement.integrated_sha is None
    assert replacement.attempts == 0
    assert replacement.last_error is None
    assert replacement.gate_outcome is None
    assert replacement.dependency_heads == {}
    assert replacement.required_base_missing == ()
    assert replacement.wait_reason == REVIEW_GENERATION_REQUEUE_WAIT_REASON
    assert replacement.wait_generation == review_generation_requeue_marker(
        "42",
        "d" * 40,
        "e" * 40,
    )


def test_requeue_standalone_review_generation_rejects_non_standalone_identity():
    with pytest.raises(ValueError, match="exact standalone review generation"):
        requeue_standalone_review_generation(
            IntegrationRecord(state="ready", mode="queue"),
            review_id="42",
            head_sha="a" * 40,
            base_sha="b" * 40,
            updated_at="2026-08-11T12:00:00+00:00",
        )


def test_integration_record_rejects_unknown_delivery_mode():
    with pytest.raises(ValueError, match="unsupported integration mode"):
        IntegrationRecord(state="ready", mode="caller-selected")


@pytest.mark.parametrize(
    "raw",
    [
        None,
        [],
        {},
        {"version": 999, "state": "ready"},
        {"version": 1, "state": "unknown"},
        {"version": 2, "state": "ready", "mode": "unknown"},
        {"version": 1, "state": "ready", "attempts": -1},
        {"version": "nope", "state": "ready"},
    ],
)
def test_parse_integration_record_rejects_malformed_or_unsupported_data(raw):
    assert parse_integration_record(raw) is None


def test_direct_maintenance_publication_proof_round_trips_only_when_true():
    proven = IntegrationRecord(
        state="integrated",
        task_branch="epic-parent",
        base_branch="epic-parent",
        head_sha="a" * 40,
        integrated_sha="a" * 40,
        maintenance_publication_proven=True,
    )

    assert IntegrationRecord.from_dict(proven.to_dict()) == proven
    assert proven.to_dict()["maintenance_publication_proven"] is True
    assert "maintenance_publication_proven" not in IntegrationRecord(
        state="ready"
    ).to_dict()


def test_direct_maintenance_publication_proof_rejects_truthy_non_boolean():
    record = IntegrationRecord.from_dict(
        {
            "state": "ready",
            "maintenance_publication_proven": "false",
        }
    )

    assert record.maintenance_publication_proven is False


def test_integration_record_ignores_unknown_future_keys():
    record = parse_integration_record(
        {
            "version": 1,
            "state": "queued",
            "task_branch": "task-1",
            "future_field": {"safe": True},
        }
    )

    assert record is not None
    assert record.state == "queued"
    assert "future_field" not in record.to_dict()


def test_expected_submission_branch_uses_persisted_work_branch():
    issue = SimpleNamespace(
        identifier="TASK-1",
        work_branch="epic-EPIC-1--task-TASK-1",
        branch_name="stale-branch",
    )

    assert expected_submission_branch(issue) == "epic-EPIC-1--task-TASK-1"


def test_submission_branch_validation_uses_native_task_branch_fallback():
    issue = SimpleNamespace(
        identifier="owner/repo#1234",
        work_branch=None,
        branch_name=None,
    )

    assert validate_submission_branch(issue, "owner_repo_1234") == "owner_repo_1234"
    with pytest.raises(ValueError, match="expected work branch"):
        validate_submission_branch(issue, "main")


def test_accepted_generation_branch_overrides_stale_tracker_projection():
    issue = SimpleNamespace(
        identifier="OOMPAH-814",
        work_branch="epic-OOMPAH-763--task-OOMPAH-814",
        branch_name="epic-OOMPAH-763--task-OOMPAH-814",
        integration=IntegrationRecord(
            state="blocked",
            task_branch="OOMPAH-814",
            head_sha="a" * 40,
        ),
    )

    assert accepted_submission_branch(issue) == "OOMPAH-814"
    assert assigned_work_branch(issue) == "OOMPAH-814"
    assert validate_submission_branch(issue, "OOMPAH-814") == "OOMPAH-814"
    with pytest.raises(ValueError, match="expected work branch"):
        validate_submission_branch(
            issue,
            "epic-OOMPAH-763--task-OOMPAH-814",
        )


def test_working_or_partial_record_cannot_claim_accepted_branch_authority():
    working = SimpleNamespace(
        identifier="TASK-1",
        work_branch="stale-projection",
        branch_name=None,
        integration=IntegrationRecord(
            state="working",
            task_branch="epic-EPIC-1--task-TASK-1",
        ),
    )
    partial = SimpleNamespace(
        identifier="TASK-2",
        work_branch="TASK-2",
        branch_name=None,
        integration=IntegrationRecord(
            state="blocked",
            task_branch="stale-branch",
        ),
    )

    assert accepted_submission_branch(working) is None
    assert assigned_work_branch(working) == "epic-EPIC-1--task-TASK-1"
    assert expected_submission_branch(working) == "epic-EPIC-1--task-TASK-1"
    assert accepted_submission_branch(partial) is None
    assert expected_submission_branch(partial) == "TASK-2"
