"""Tests for revision-aware model-backed duplicate screening."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

from oompah.duplicate_screening import (
    DETECTOR_VERSION,
    METADATA_KEY,
    DuplicateScreeningRecord,
    ScreeningState,
    ScreeningVerdict,
    assess_screening,
    complete_claim_record,
    compute_task_fingerprint,
    load_record,
    new_claim_record,
    save_record,
)
from oompah.models import BlockerRef, Issue
from oompah.oompah_md_tracker import OompahMarkdownTracker
from oompah.statuses import DONE, OPEN


def _issue(**overrides) -> Issue:
    values = {
        "id": "TASK-1",
        "identifier": "TASK-1",
        "title": "Prevent duplicate work",
        "description": "Screen this task before implementation.",
        "state": OPEN,
        "issue_type": "feature",
        "project_id": "project-1",
        "parent_id": "EPIC-1",
        "labels": ["backend", "needs:feature"],
        "blocked_by": [BlockerRef(id="TASK-0", identifier="TASK-0")],
    }
    values.update(overrides)
    return Issue(**values)


def test_fingerprint_is_stable_for_normalization_and_dependency_order():
    left = _issue(
        title="  PREVENT   duplicate work ",
        description="Screen\nthis task before implementation.",
        labels=["needs:feature", "Backend"],
        blocked_by=[
            BlockerRef(id="TASK-2", identifier="TASK-2"),
            BlockerRef(id="TASK-0", identifier="TASK-0"),
        ],
    )
    right = _issue(
        title="prevent duplicate work",
        labels=["backend", "focus-complete:duplicate_detector"],
        blocked_by=[
            BlockerRef(id="TASK-0", identifier="TASK-0"),
            BlockerRef(id="TASK-2", identifier="TASK-2"),
        ],
    )

    assert compute_task_fingerprint(left) == compute_task_fingerprint(right)


def test_transient_oompah_labels_do_not_invalidate_fingerprint():
    original = _issue(labels=["backend"])
    updated = replace(
        original,
        labels=[
            "backend",
            "focus-complete:duplicate_detector",
            "needs:bugfix",
            "oompah:status:open",
            "duplicate-preflight:running",
            "merge-conflict",
        ],
    )

    assert compute_task_fingerprint(original) == compute_task_fingerprint(updated)


def test_each_material_field_invalidates_fingerprint():
    issue = _issue()
    original = compute_task_fingerprint(issue)
    changes = [
        replace(issue, title="A different title"),
        replace(issue, description="A different description"),
        replace(issue, project_id="project-2"),
        replace(issue, issue_type="bug"),
        replace(issue, parent_id="EPIC-2"),
        replace(issue, labels=[*issue.labels, "frontend"]),
        replace(
            issue,
            blocked_by=[BlockerRef(id="TASK-9", identifier="TASK-9")],
        ),
    ]

    assert all(compute_task_fingerprint(changed) != original for changed in changes)


def test_unchecked_legacy_malformed_and_future_records_fail_closed():
    issue = _issue()
    assert assess_screening(issue).state == ScreeningState.UNCHECKED

    issue.labels.append("focus-complete:duplicate_detector")
    legacy = assess_screening(issue)
    assert legacy.state == ScreeningState.STALE
    assert "legacy" in legacy.reason

    issue.labels = ["backend"]
    issue.duplicate_screening = {"schema_version": 1}
    assert assess_screening(issue).state == ScreeningState.STALE

    issue.duplicate_screening = {
        "schema_version": 999,
        "task_fingerprint": compute_task_fingerprint(issue),
        "detector_version": DETECTOR_VERSION,
    }
    assert assess_screening(issue).state == ScreeningState.STALE


def test_running_checked_stale_and_detector_version_states():
    now = datetime(2026, 7, 28, tzinfo=timezone.utc)
    issue = _issue()
    claim = new_claim_record(issue, owner="scheduler", now=now, ttl_seconds=60)
    issue.duplicate_screening = claim.to_dict()

    assert assess_screening(issue, now=now).state == ScreeningState.RUNNING
    assert (
        assess_screening(issue, now=now + timedelta(seconds=61)).state
        == ScreeningState.STALE
    )

    checked = complete_claim_record(
        claim,
        verdict=ScreeningVerdict.NO_DUPLICATE,
        now=now,
    )
    issue.duplicate_screening = checked.to_dict()
    assessment = assess_screening(issue, now=now)
    assert assessment.state == ScreeningState.CHECKED
    assert assessment.implementation_eligible is True

    issue.description = "Materially changed."
    assert assess_screening(issue, now=now).state == ScreeningState.STALE

    issue.description = "Screen this task before implementation."
    assert (
        assess_screening(issue, detector_version="duplicate-detector-v2", now=now).state
        == ScreeningState.STALE
    )


def test_record_round_trip_and_unknown_verdict_rejected():
    now = datetime(2026, 7, 28, tzinfo=timezone.utc)
    record = DuplicateScreeningRecord(
        task_fingerprint="abc123",
        detector_version=DETECTOR_VERSION,
        verdict=ScreeningVerdict.DUPLICATE_CANDIDATE,
        checked_at=now,
        matched_identifiers=("TASK-2",),
        evidence="Same root cause.",
    )

    assert DuplicateScreeningRecord.from_raw(record.to_dict()) == record
    malformed = record.to_dict()
    malformed["verdict"] = "made-up"
    assert DuplicateScreeningRecord.from_raw(malformed) is None


def test_native_tracker_metadata_round_trip_preserves_unrelated_fields(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    tracker = OompahMarkdownTracker(
        active_states=[OPEN],
        terminal_states=[DONE],
        cwd=str(root),
        default_branch="main",
        git_sync=False,
    )
    issue = tracker.create_issue(
        "Duplicate-screening metadata",
        description="Persist the qualification result.",
        initial_status=OPEN,
    )
    issue.project_id = "project-1"
    tracker.set_metadata_field(issue.identifier, "oompah.other", {"keep": True})
    record = new_claim_record(issue, owner="scheduler")

    save_record(tracker, issue, record)

    refreshed = tracker.fetch_issue_detail(issue.identifier)
    assert refreshed is not None
    refreshed.project_id = "project-1"
    loaded = load_record(tracker, refreshed)
    assert loaded == record
    assert refreshed.duplicate_screening == record.to_dict()
    metadata = tracker.get_metadata(issue.identifier)
    assert metadata[METADATA_KEY] == record.to_dict()
    assert metadata["oompah.other"] == {"keep": True}
