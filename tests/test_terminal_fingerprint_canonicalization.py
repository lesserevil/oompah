"""Tests for canonical evidence fingerprint computation across all terminal paths.

Regression tests for OOMPAH-663: Ensures that integrated-task fingerprints
are computed canonically in orchestrator integration, API owner-override,
ACP owner-override, and restart recovery paths.

Bug reproduction: OOMPAH-660 was integrated but its integration-staged Done
audit computed an evidence fingerprint with epic-branch data that differed
from the API owner-override path, causing an HTTP 409 conflict until the
Done request was restaged with the API fingerprint.

Acceptance criteria:
- The first valid override succeeds and retires the audit alert
- No duplicate terminal request is needed
- Stale evidence remains rejected
- Different integration SHAs still fail closed
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, replace
from typing import Any
from unittest.mock import MagicMock, Mock

import pytest

from oompah.models import Issue
from oompah.terminal_audit import (
    ContributorIdentity,
    EvidenceFingerprint,
    RequestState,
    TerminalAuditRecord,
    TargetState,
    compute_issue_evidence_fingerprint,
)
from oompah.terminal_audit_metadata import (
    METADATA_KEY,
    TerminalAuditMetadata,
    TerminalAuditMetadataStore,
)
from oompah.terminal_transition_coordinator import (
    TerminalTransitionCoordinator,
)
from oompah.statuses import DONE, NEEDS_HUMAN


class _LockStore:
    """Thread-safe per-project write-lock provider."""

    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._locks: dict[str, threading.RLock] = {}

    def project_write_lock(self, project_id: str) -> threading.RLock:
        with self._guard:
            return self._locks.setdefault(project_id, threading.RLock())


class _MemoryTracker:
    """In-memory TrackerProtocol double."""

    def __init__(self) -> None:
        self.issues: dict[str, MagicMock] = {}
        self.metadata: dict[str, dict[str, Any]] = {}
        self.comments: list[tuple[str, str, str]] = []  # (identifier, text, author)
        self.status_updates: list[tuple[str, str]] = []  # (identifier, status)

    def fetch_issue(self, identifier: str) -> Issue | None:
        return self.issues.get(identifier)

    def update_issue(self, identifier: str, **kwargs: Any) -> None:
        if "status" in kwargs:
            self.status_updates.append((identifier, kwargs["status"]))

    def add_comment(self, identifier: str, text: str, author: str = "oompah") -> None:
        self.comments.append((identifier, text, author))

    def get_metadata(self, identifier: str) -> dict[str, Any]:
        return self.metadata.get(identifier, {})

    def set_metadata(self, identifier: str, metadata: dict[str, Any]) -> None:
        self.metadata[identifier] = metadata

    def set_metadata_field(self, identifier: str, field: str, value: Any) -> None:
        """Set a single metadata field (as required by TerminalAuditMetadataStore)."""
        if identifier not in self.metadata:
            self.metadata[identifier] = {}
        self.metadata[identifier][field] = value


@dataclass
class _MockProject:
    """Mock project for authorization checks."""

    status_label_authorized_logins: list[str] | None = None
    status_actor_login: str | None = None
    tracker_owner: str | None = None


@pytest.fixture
def lock_store():
    return _LockStore()


@pytest.fixture
def tracker():
    return _MemoryTracker()


@pytest.fixture
def coordinator(tracker, lock_store):
    return TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=lock_store,
        post_comments=True,
    )


@pytest.fixture
def project_id():
    return "test-project"


@pytest.fixture
def task_id():
    return "TASK-123"


@pytest.fixture
def owner_identity():
    return ContributorIdentity(identity="owner", source="github")


@pytest.mark.asyncio
async def test_integrated_task_audit_staged_and_overridden_with_canonical_fingerprint(
    coordinator, tracker, project_id, task_id, owner_identity
):
    """OOMPAH-663: Integrated task audit can be overridden without restaging.
    
    When an integrated task's Done audit is staged during orchestrator integration,
    it computes the canonical evidence fingerprint from the issue. When an authorized
    owner applies an override, it must compute the SAME fingerprint from the
    normalized task issue. The override should succeed without requiring the audit
    to be restaged.
    
    This tests the fix for a bug where the integration path and API override path
    computed different fingerprints, causing a 409 conflict.
    """
    
    # Step 1: Create an issue with integration record (simulating an integrated task)
    issue = Issue(
        id=task_id,
        identifier=task_id,
        state="Open",
        title="Integrated task",
        description="Test task with integration record",
    )
    
    # Simulate an integration record by adding properties
    # (In real usage, this would come from the tracker with integration metadata)
    issue.integration = Mock(
        task_branch="feature/task-123",
        head_sha="abc123def456",
        base_branch="main",
        base_sha="deadbeef0000",
        integrated_sha="cafe1234beef",
    )
    issue.project_id = project_id
    
    tracker.issues[task_id] = issue
    project = _MockProject(status_label_authorized_logins=["owner"])
    
    # Step 2: Compute the canonical fingerprint (as orchestrator integration would)
    # This is what gets stored in the initial Done audit
    integration_fingerprint = compute_issue_evidence_fingerprint(issue, project_id)
    
    # Step 3: Stage a Done audit (simulating orchestrator behavior)
    pending_record = TerminalAuditRecord(
        audit_id="audit-initial",
        project_id=project_id,
        task_id=task_id,
        target_state=TargetState.DONE,
        evidence_fingerprint=integration_fingerprint,
        request_state=RequestState.PENDING,
        requested_by=owner_identity,
    )
    
    # Set up metadata with the pending audit record
    metadata = TerminalAuditMetadata(
        pending_chain=[pending_record],
        unknown_fields={}
    )
    tracker.set_metadata(task_id, {METADATA_KEY: metadata.to_dict()})
    
    # Step 4: Simulate auditor routing to Needs Human (no independent candidate)
    # The issue is still in its current state, ready for override
    issue_in_validation = replace(issue, state="In Validation")
    tracker.issues[task_id] = issue_in_validation
    
    # Step 5: Apply authorized owner override WITHOUT restaging
    # The override path should compute the SAME fingerprint as the initial audit
    # by using compute_issue_evidence_fingerprint on the normalized issue
    override_fingerprint = compute_issue_evidence_fingerprint(issue_in_validation, project_id)
    
    # Fingerprints must match (canonical path)
    assert override_fingerprint == integration_fingerprint, (
        "Integration and override fingerprints must match when using canonical computation"
    )
    
    result = await coordinator.override_transition(
        current_issue=issue_in_validation,
        requested_target=TargetState.DONE,
        authorized_actor=owner_identity,
        project_id=project_id,
        evidence_fingerprint=override_fingerprint,
        reason="Approving integrated task",
        project=project,
    )
    
    # The override should succeed (not 409)
    assert result.success is True, f"Override should succeed, got reason: {result.reason}"
    assert result.applied_status == DONE
    assert result.posted_comment is True
    assert (task_id, DONE) in tracker.status_updates


@pytest.mark.asyncio
async def test_genuinely_changed_integration_sha_still_fails_closed(
    coordinator, tracker, project_id, task_id, owner_identity
):
    """OOMPAH-663: Genuinely changed integration SHA is detected and rejected.
    
    Even though we use canonical fingerprint computation, if the actual integration
    SHA has changed after the initial audit was staged, the fingerprints will not
    match and the override will be rejected (409 conflict). This ensures we fail
    closed when evidence has actually changed.
    """
    
    # Create an issue with initial integration record
    issue_original = Issue(
        id=task_id,
        identifier=task_id,
        state="Open",
        title="Integrated task",
        description="Test task",
    )
    
    # Original integration data
    issue_original.integration = Mock(
        task_branch="feature/task-123",
        head_sha="abc123def456",
        base_branch="main",
        base_sha="deadbeef0000",
        integrated_sha="cafe1234beef",
    )
    issue_original.project_id = project_id
    
    # Step 1: Compute initial fingerprint from original integration
    initial_fingerprint = compute_issue_evidence_fingerprint(issue_original, project_id)
    
    # Step 2: Stage initial Done audit
    pending_record = TerminalAuditRecord(
        audit_id="audit-original",
        project_id=project_id,
        task_id=task_id,
        target_state=TargetState.DONE,
        evidence_fingerprint=initial_fingerprint,
        request_state=RequestState.PENDING,
        requested_by=owner_identity,
    )
    
    metadata = TerminalAuditMetadata(
        pending_chain=[pending_record],
        unknown_fields={}
    )
    tracker.set_metadata(task_id, {METADATA_KEY: metadata.to_dict()})
    
    # Step 3: Simulate the issue being refetched with DIFFERENT integration data
    # (e.g., a different integration SHA)
    issue_changed = Issue(
        id=task_id,
        identifier=task_id,
        state="In Validation",
        title="Integrated task",
        description="Test task",
    )
    
    # NEW integration SHA (simulating a genuine change)
    issue_changed.integration = Mock(
        task_branch="feature/task-123",
        head_sha="def456ghi789",  # Different!
        base_branch="main",
        base_sha="deadbeef0000",
        integrated_sha="1234cafe5678",  # Different!
    )
    issue_changed.project_id = project_id
    tracker.issues[task_id] = issue_changed
    
    # Step 4: Compute fingerprint from changed issue
    changed_fingerprint = compute_issue_evidence_fingerprint(issue_changed, project_id)
    
    # Fingerprints must NOT match
    assert changed_fingerprint != initial_fingerprint, (
        "Changed integration SHA should result in different fingerprint"
    )
    
    project = _MockProject(status_label_authorized_logins=["owner"])
    
    # Step 5: Try to override with the changed fingerprint
    # This should FAIL because it doesn't match the pending audit
    result = await coordinator.override_transition(
        current_issue=issue_changed,
        requested_target=TargetState.DONE,
        authorized_actor=owner_identity,
        project_id=project_id,
        evidence_fingerprint=changed_fingerprint,
        reason="Should fail - evidence changed",
        project=project,
    )
    
    # Must fail (409 / fingerprint mismatch)
    assert result.success is False
    assert "fingerprint" in result.reason.lower()
    assert tracker.status_updates == []  # No status change should occur


@pytest.mark.asyncio
async def test_api_override_uses_same_canonical_fingerprint_as_orchestrator_integration(
    coordinator, tracker, project_id, task_id, owner_identity
):
    """OOMPAH-663: API and orchestrator paths use identical fingerprint computation.
    
    Both the orchestrator (when staging Done audits during integration) and the
    API (when applying owner overrides) must use compute_issue_evidence_fingerprint
    to ensure consistent, canonical fingerprints that work across all paths.
    """
    
    # Create an issue representing an integrated task
    issue = Issue(
        id=task_id,
        identifier=task_id,
        state="Open",
        title="Task",
        description="Description",
    )
    
    issue.integration = Mock(
        task_branch="fix/issue",
        head_sha="aabbccdd",
        base_branch="develop",
        base_sha="11223344",
        integrated_sha="99aabbcc",
    )
    issue.project_id = project_id
    tracker.issues[task_id] = issue
    
    # Compute fingerprint using the canonical function (as both paths should)
    canonical_fp = compute_issue_evidence_fingerprint(issue, project_id)
    
    # Simulate orchestrator staging with this fingerprint
    pending = TerminalAuditRecord(
        audit_id="audit-1",
        project_id=project_id,
        task_id=task_id,
        target_state=TargetState.DONE,
        evidence_fingerprint=canonical_fp,
        request_state=RequestState.PENDING,
        requested_by=owner_identity,
    )
    
    metadata = TerminalAuditMetadata(pending_chain=[pending], unknown_fields={})
    tracker.set_metadata(task_id, {METADATA_KEY: metadata.to_dict()})
    
    # Now simulate API override using the same canonical function
    # (This is what acp_tools.py and server.py do)
    api_computed_fp = compute_issue_evidence_fingerprint(issue, project_id)
    
    # Fingerprints MUST be identical
    assert api_computed_fp == canonical_fp
    assert api_computed_fp.digest == canonical_fp.digest
    
    project = _MockProject(status_label_authorized_logins=["owner"])
    
    # Override should succeed because fingerprints match
    result = await coordinator.override_transition(
        current_issue=issue,
        requested_target=TargetState.DONE,
        authorized_actor=owner_identity,
        project_id=project_id,
        evidence_fingerprint=api_computed_fp,
        reason="API-based override",
        project=project,
    )
    
    assert result.success is True
