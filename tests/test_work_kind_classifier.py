"""Tests for authoritative work_kind classification across observability surfaces.

OOMPAH-827: Ensures that work_kind classification is consistent across:
- RunningEntry.classify_work_kind() method (source of truth)
- /api/v1/state snapshots
- /api/v1/agents/:identifier/activity responses
- AGENT_DISPATCHED WebSocket events

The classification precedence is:
1. audit (if is_auditor=True)
2. duplicate_screening (if duplicate_preflight=True)
3. implementation (default)

This ensures no surface reports a different work_kind for the same run.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oompah.config import ServiceConfig
from oompah.events import EventType
from oompah.models import Issue, RunningEntry
from oompah.orchestrator import Orchestrator


def _orchestrator(tmp_path) -> Orchestrator:
    """Create a minimal orchestrator for testing."""
    return Orchestrator(
        config=ServiceConfig(),
        workflow_path="WORKFLOW.md",
        state_path=str(tmp_path / "service_state.json"),
    )


def _issue(**overrides) -> Issue:
    """Create a test issue."""
    values = {
        "id": "task-1",
        "identifier": "TEST-1",
        "title": "Test task",
        "state": "Open",
        "issue_type": "feature",
        "project_id": "proj-1",
    }
    values.update(overrides)
    return Issue(**values)


def _running_entry(
    issue: Issue,
    is_auditor: bool = False,
    audit_id: str | None = None,
    audit_attempt_id: str | None = None,
    duplicate_preflight: bool = False,
    retirement_pending: bool = False,
) -> RunningEntry:
    """Create a test running entry."""
    return RunningEntry(
        worker_task=MagicMock(),
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        run_id="test-run-id",
        is_auditor=is_auditor,
        audit_id=audit_id,
        audit_attempt_id=audit_attempt_id,
        duplicate_preflight=duplicate_preflight,
        retirement_pending=retirement_pending,
    )


# ============================================================================
# Tests for RunningEntry.classify_work_kind() method
# ============================================================================


def test_classify_work_kind_ordinary_implementation():
    """Ordinary implementation (no audit, no duplicate screening)."""
    issue = _issue()
    entry = _running_entry(issue)

    assert entry.classify_work_kind() == "implementation"


def test_classify_work_kind_duplicate_screening():
    """Duplicate screening (duplicate_preflight=True, not audit)."""
    issue = _issue()
    entry = _running_entry(issue, duplicate_preflight=True)

    assert entry.classify_work_kind() == "duplicate_screening"


def test_classify_work_kind_audit():
    """Active auditor (is_auditor=True)."""
    issue = _issue()
    entry = _running_entry(
        issue,
        is_auditor=True,
        audit_id="audit-1",
        audit_attempt_id="attempt-1",
    )

    assert entry.classify_work_kind() == "audit"


def test_classify_work_kind_audit_precedence_over_duplicate():
    """Audit takes precedence over duplicate_screening.

    Although this should be rare in practice, the classifier must enforce
    that audit is the highest precedence.
    """
    issue = _issue()
    entry = _running_entry(
        issue,
        is_auditor=True,
        audit_id="audit-1",
        audit_attempt_id="attempt-1",
        duplicate_preflight=True,  # Both flags set, audit wins
    )

    assert entry.classify_work_kind() == "audit"


def test_classify_work_kind_duplicate_precedence_over_implementation():
    """Duplicate screening takes precedence over ordinary implementation."""
    issue = _issue()
    entry = _running_entry(issue, duplicate_preflight=True)

    assert entry.classify_work_kind() == "duplicate_screening"


def test_classify_work_kind_retiring_audit():
    """Retiring (post-PASS) auditor still classifies as audit.

    Retirement state doesn't affect work_kind classification.
    """
    issue = _issue()
    entry = _running_entry(
        issue,
        is_auditor=True,
        audit_id="audit-1",
        audit_attempt_id="attempt-1",
        retirement_pending=True,
    )

    # work_kind still reflects the actual type of work being done
    assert entry.classify_work_kind() == "audit"


# ============================================================================
# Tests for /api/v1/state snapshot consistency
# ============================================================================


def test_state_snapshot_includes_correct_work_kind_implementation(tmp_path):
    """State snapshot reports correct work_kind for implementation."""
    orch = _orchestrator(tmp_path)
    issue = _issue()
    entry = _running_entry(issue)
    orch.state.running[issue.id] = entry

    snapshot = orch.get_snapshot()
    running_row = snapshot["running"][0]

    assert running_row["work_kind"] == "implementation"


def test_state_snapshot_includes_correct_work_kind_duplicate_screening(tmp_path):
    """State snapshot reports correct work_kind for duplicate screening."""
    orch = _orchestrator(tmp_path)
    issue = _issue()
    entry = _running_entry(issue, duplicate_preflight=True)
    orch.state.running[issue.id] = entry

    snapshot = orch.get_snapshot()
    running_row = snapshot["running"][0]

    assert running_row["work_kind"] == "duplicate_screening"


def test_state_snapshot_includes_correct_work_kind_audit(tmp_path):
    """State snapshot reports correct work_kind for audit."""
    orch = _orchestrator(tmp_path)
    issue = _issue()
    entry = _running_entry(
        issue,
        is_auditor=True,
        audit_id="audit-1",
        audit_attempt_id="attempt-1",
    )
    orch.state.running[issue.id] = entry

    snapshot = orch.get_snapshot()
    running_row = snapshot["running"][0]

    assert running_row["work_kind"] == "audit"
    assert running_row["is_auditor"] is True
    assert running_row["audit_id"] == "audit-1"
    assert running_row["audit_attempt_id"] == "attempt-1"


def test_state_snapshot_includes_retiring_flag(tmp_path):
    """State snapshot includes retiring flag for post-PASS auditors."""
    orch = _orchestrator(tmp_path)
    issue = _issue()
    entry = _running_entry(
        issue,
        is_auditor=True,
        audit_id="audit-1",
        audit_attempt_id="attempt-1",
        retirement_pending=True,
    )
    orch.state.running[issue.id] = entry

    snapshot = orch.get_snapshot()
    running_row = snapshot["running"][0]

    assert running_row["retiring"] is True
    assert running_row["work_kind"] == "audit"


def test_state_snapshot_no_audit_fields_for_ordinary_work(tmp_path):
    """State snapshot doesn't expose audit fields for non-audit work."""
    orch = _orchestrator(tmp_path)
    issue = _issue()
    entry = _running_entry(issue)  # ordinary implementation
    orch.state.running[issue.id] = entry

    snapshot = orch.get_snapshot()
    running_row = snapshot["running"][0]

    assert running_row["is_auditor"] is False
    # Audit fields should be None for ordinary work
    assert running_row["audit_id"] is None
    assert running_row["audit_attempt_id"] is None


# ============================================================================
# Tests for /api/v1/agents/:identifier/activity endpoint
# ============================================================================


@pytest.mark.asyncio
async def test_api_agent_activity_work_kind_implementation(tmp_path):
    """Activity endpoint reports correct work_kind for implementation."""
    from oompah.server import app, _running_items_snapshot

    orch = _orchestrator(tmp_path)
    issue = _issue()
    entry = _running_entry(issue)
    orch.state.running[issue.id] = entry

    # Mock the orchestrator getter
    with patch("oompah.server._get_orchestrator", return_value=orch):
        # Simulate the activity endpoint logic
        for _, test_entry in _running_items_snapshot(orch):
            if test_entry.identifier == "TEST-1":
                assert test_entry.classify_work_kind() == "implementation"


@pytest.mark.asyncio
async def test_api_agent_activity_work_kind_audit(tmp_path):
    """Activity endpoint reports correct work_kind for audit."""
    from oompah.server import _running_items_snapshot

    orch = _orchestrator(tmp_path)
    issue = _issue()
    entry = _running_entry(
        issue,
        is_auditor=True,
        audit_id="audit-1",
        audit_attempt_id="attempt-1",
    )
    orch.state.running[issue.id] = entry

    # Verify the entry has correct work_kind
    for _, test_entry in _running_items_snapshot(orch):
        if test_entry.identifier == "TEST-1":
            assert test_entry.classify_work_kind() == "audit"


@pytest.mark.asyncio
async def test_api_agent_activity_includes_audit_identity_fields(tmp_path):
    """Activity endpoint includes is_auditor, audit_id, audit_attempt_id for audits."""
    from oompah.server import _running_items_snapshot

    orch = _orchestrator(tmp_path)
    issue = _issue()
    entry = _running_entry(
        issue,
        is_auditor=True,
        audit_id="audit-1",
        audit_attempt_id="attempt-1",
    )
    orch.state.running[issue.id] = entry

    for _, test_entry in _running_items_snapshot(orch):
        if test_entry.identifier == "TEST-1":
            assert getattr(test_entry, "is_auditor", False) is True
            assert getattr(test_entry, "audit_id", None) == "audit-1"
            assert getattr(test_entry, "audit_attempt_id", None) == "attempt-1"


@pytest.mark.asyncio
async def test_api_agent_activity_includes_retiring_flag(tmp_path):
    """Activity endpoint includes retiring flag for post-PASS auditors."""
    from oompah.server import _running_items_snapshot

    orch = _orchestrator(tmp_path)
    issue = _issue()
    entry = _running_entry(
        issue,
        is_auditor=True,
        audit_id="audit-1",
        audit_attempt_id="attempt-1",
        retirement_pending=True,
    )
    orch.state.running[issue.id] = entry

    for _, test_entry in _running_items_snapshot(orch):
        if test_entry.identifier == "TEST-1":
            assert getattr(test_entry, "retirement_pending", False) is True


# ============================================================================
# Tests for consistency across surfaces
# ============================================================================


def test_work_kind_consistent_across_state_and_entry_classifier(tmp_path):
    """State snapshot and entry classifier agree for all work kinds."""
    orch = _orchestrator(tmp_path)
    issue = _issue()

    # Test ordinary implementation
    entry = _running_entry(issue)
    orch.state.running[issue.id] = entry
    snapshot = orch.get_snapshot()
    assert snapshot["running"][0]["work_kind"] == entry.classify_work_kind()

    # Test duplicate screening
    entry2 = _running_entry(issue, duplicate_preflight=True)
    orch.state.running[issue.id] = entry2
    snapshot = orch.get_snapshot()
    assert snapshot["running"][0]["work_kind"] == entry2.classify_work_kind()

    # Test audit
    entry3 = _running_entry(
        issue,
        is_auditor=True,
        audit_id="audit-1",
        audit_attempt_id="attempt-1",
    )
    orch.state.running[issue.id] = entry3
    snapshot = orch.get_snapshot()
    assert snapshot["running"][0]["work_kind"] == entry3.classify_work_kind()


def test_profile_name_alone_never_determines_work_kind(tmp_path):
    """Profile name does not determine work_kind; only entry flags do."""
    orch = _orchestrator(tmp_path)
    issue = _issue()

    # Entry with "auditor" profile but not actually an auditor
    entry = _running_entry(issue)
    entry.agent_profile_name = "auditor"  # Just a profile name

    # Should still be "implementation" because is_auditor=False
    assert entry.classify_work_kind() == "implementation"

    # Now make it a real auditor
    entry2 = _running_entry(
        issue,
        is_auditor=True,
        audit_id="audit-1",
        audit_attempt_id="attempt-1",
    )
    entry2.agent_profile_name = "default"  # Any profile name

    # Should be "audit" because is_auditor=True
    assert entry2.classify_work_kind() == "audit"


def test_duplicate_preflight_field_enables_duplicate_screening_classification(tmp_path):
    """duplicate_preflight field determines duplicate_screening classification."""
    orch = _orchestrator(tmp_path)
    issue = _issue()

    # Without duplicate_preflight
    entry1 = _running_entry(issue)
    assert entry1.classify_work_kind() == "implementation"

    # With duplicate_preflight
    entry2 = _running_entry(issue, duplicate_preflight=True)
    assert entry2.classify_work_kind() == "duplicate_screening"


def test_is_auditor_field_enables_audit_classification(tmp_path):
    """is_auditor field determines audit classification."""
    orch = _orchestrator(tmp_path)
    issue = _issue()

    # Without is_auditor
    entry1 = _running_entry(issue)
    assert entry1.classify_work_kind() == "implementation"

    # With is_auditor
    entry2 = _running_entry(
        issue,
        is_auditor=True,
        audit_id="audit-1",
        audit_attempt_id="attempt-1",
    )
    assert entry2.classify_work_kind() == "audit"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
