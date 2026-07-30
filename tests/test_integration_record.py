"""Tests for durable private-branch integration metadata."""

from types import SimpleNamespace

import pytest

from oompah.integration import (
    IntegrationRecord,
    expected_submission_branch,
    parse_integration_record,
    validate_submission_branch,
)


def test_integration_record_round_trips_all_supported_evidence():
    record = IntegrationRecord(
        state="ready",
        task_branch="oompah/task/ABC-2",
        base_branch="epic-ABC-1",
        base_sha="a" * 40,
        head_sha="b" * 40,
        attempts=2,
        submitted_at="2026-07-29T12:00:00Z",
        updated_at="2026-07-29T12:01:00Z",
        dependency_heads={"ABC-1": "c" * 40},
    )

    assert IntegrationRecord.from_dict(record.to_dict()) == record


@pytest.mark.parametrize(
    "raw",
    [
        None,
        [],
        {},
        {"version": 999, "state": "ready"},
        {"version": 1, "state": "unknown"},
        {"version": 1, "state": "ready", "attempts": -1},
        {"version": "nope", "state": "ready"},
    ],
)
def test_parse_integration_record_rejects_malformed_or_unsupported_data(raw):
    assert parse_integration_record(raw) is None


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
