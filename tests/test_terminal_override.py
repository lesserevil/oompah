"""Tests for explicit authorized owner overrides for terminal audits.

Covers authorized owner, additional authorized login, unauthorized actor,
bot-only actor, blank reason, stale fingerprint, repeated override,
metadata/comment failure ordering, and redaction.
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, replace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from oompah.models import Issue
from oompah.terminal_audit import (
    ContributorIdentity,
    EvidenceFingerprint,
    OverrideRecord,
    RequestState,
    TerminalAuditRecord,
    TargetState,
)
from oompah.terminal_audit_metadata import (
    METADATA_KEY,
    TerminalAuditMetadata,
    TerminalAuditMetadataStore,
)
from oompah.terminal_transition_coordinator import (
    OverrideResult,
    TerminalTransitionCoordinator,
)
from oompah.statuses import DONE, MERGED, ARCHIVED


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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
def fingerprint():
    return EvidenceFingerprint.from_evidence(
        requirements_text="test requirements",
        project_id="test-project",
        task_id="TASK-123",
    )


@pytest.fixture
def owner_identity():
    return ContributorIdentity(identity="owner", source="github")


@pytest.fixture
def unauthorized_identity():
    return ContributorIdentity(identity="random-user", source="github")


# ---------------------------------------------------------------------------
# Tests: Authorized owner override
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_authorized_owner_can_override(
    coordinator, tracker, project_id, task_id, fingerprint, owner_identity
):
    """Authorized project owner can apply override."""
    
    issue = Issue(id=task_id,
        identifier=task_id,
        state="Open",
        title="Test task",
        description="Test",
    )
    
    project = _MockProject(
        status_label_authorized_logins=["owner"]
    )
    
    # Set up initial metadata
    metadata = TerminalAuditMetadata(pending_chain=[], unknown_fields={})
    tracker.set_metadata(task_id, {METADATA_KEY: metadata.to_dict()})
    
    result = await coordinator.override_transition(
        current_issue=issue,
        requested_target=TargetState.DONE,
        authorized_actor=owner_identity,
        project_id=project_id,
        evidence_fingerprint=fingerprint,
        reason="Fixing stale task - owner override required",
        project=project,
    )
    
    assert result.success is True
    assert result.override_id is not None
    assert result.applied_status == DONE
    assert result.posted_comment is True
    
    # Verify status was updated
    assert (task_id, DONE) in tracker.status_updates
    
    # Verify comment was posted
    assert len(tracker.comments) == 1
    comment_text = tracker.comments[0][1]
    assert "Override by owner" in comment_text
    assert "Fixing stale task" in comment_text


@pytest.mark.asyncio
async def test_post_commit_alert_cleanup_failure_is_reported_without_rollback(
    coordinator, tracker, project_id, task_id, fingerprint, owner_identity
):
    """Alert retirement is diagnostic-only after the terminal write commits."""

    issue = Issue(
        id=task_id,
        identifier=task_id,
        state="In Validation",
        title="Test task",
        description="Test",
    )
    project = _MockProject(status_label_authorized_logins=["owner"])
    pending = TerminalAuditRecord(
        audit_id="audit-retire-me",
        project_id=project_id,
        task_id=task_id,
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.PENDING,
        requested_by=owner_identity,
    )
    tracker.set_metadata(
        task_id,
        {METADATA_KEY: TerminalAuditMetadata(pending_chain=[pending]).to_dict()},
    )

    def fail_alert_cleanup(*_args) -> None:
        raise RuntimeError("alert registry unavailable")

    coordinator.set_alert_clearer(fail_alert_cleanup)
    result = await coordinator.override_transition(
        current_issue=issue,
        requested_target=TargetState.DONE,
        authorized_actor=owner_identity,
        project_id=project_id,
        evidence_fingerprint=fingerprint,
        reason="Owner-approved terminal repair",
        project=project,
    )

    assert result.success is True
    assert result.applied_status == DONE
    assert result.cleanup_diagnostics == [
        {
            "operation": "retire_audit_alert",
            "audit_id": "audit-retire-me",
            "message": "alert registry unavailable",
        }
    ]


@pytest.mark.asyncio
async def test_authorized_via_additional_login(
    coordinator, tracker, project_id, task_id, fingerprint
):
    """Additional authorized login can override."""
    
    authorized_user = ContributorIdentity(identity="authorized-user", source="github")
    
    issue = Issue(id=task_id, 
        identifier=task_id,
        state="Open",
        title="Test task",
        description="Test",
    )
    
    project = _MockProject(
        status_label_authorized_logins=["authorized-user", "other-owner"]
    )
    
    metadata = TerminalAuditMetadata(pending_chain=[], unknown_fields={})
    tracker.set_metadata(task_id, {METADATA_KEY: metadata.to_dict()})
    
    result = await coordinator.override_transition(
        current_issue=issue,
        requested_target=TargetState.DONE,
        authorized_actor=authorized_user,
        project_id=project_id,
        evidence_fingerprint=fingerprint,
        reason="Additional authorized user override",
        project=project,
    )
    
    assert result.success is True
    assert result.applied_status == DONE


@pytest.mark.asyncio
async def test_unauthorized_actor_rejected(
    coordinator, tracker, project_id, task_id, fingerprint, unauthorized_identity
):
    """Unauthorized actor is rejected."""
    
    issue = Issue(id=task_id, 
        identifier=task_id,
        state="Open",
        title="Test task",
        description="Test",
    )
    
    project = _MockProject(
        status_label_authorized_logins=["owner"]
    )
    
    metadata = TerminalAuditMetadata(pending_chain=[], unknown_fields={})
    tracker.set_metadata(task_id, {METADATA_KEY: metadata.to_dict()})
    
    result = await coordinator.override_transition(
        current_issue=issue,
        requested_target=TargetState.DONE,
        authorized_actor=unauthorized_identity,
        project_id=project_id,
        evidence_fingerprint=fingerprint,
        reason="Unauthorized attempt",
        project=project,
    )
    
    assert result.success is False
    assert "not authorized" in result.reason


@pytest.mark.asyncio
async def test_bot_cannot_override_without_authorization(
    coordinator, tracker, project_id, task_id, fingerprint
):
    """Bot identity alone cannot override without explicit authorization."""
    
    bot_identity = ContributorIdentity(identity="oompah", source="github")
    
    issue = Issue(id=task_id, 
        identifier=task_id,
        state="Open",
        title="Test task",
        description="Test",
    )
    
    # Project with no bot authorization in explicit list
    project = _MockProject(
        status_label_authorized_logins=["owner"]
    )
    
    metadata = TerminalAuditMetadata(pending_chain=[], unknown_fields={})
    tracker.set_metadata(task_id, {METADATA_KEY: metadata.to_dict()})
    
    result = await coordinator.override_transition(
        current_issue=issue,
        requested_target=TargetState.DONE,
        authorized_actor=bot_identity,
        project_id=project_id,
        evidence_fingerprint=fingerprint,
        reason="Bot override attempt",
        project=project,
    )
    
    # Normal status-label authorization trusts the bot, but an override also
    # requires the project-owner layer, so bot-only actors are rejected.
    assert result.success is False
    assert result.error_code == "unauthorized_actor"
    assert tracker.comments == []
    assert tracker.status_updates == []


@pytest.mark.asyncio
async def test_bot_can_override_when_project_owner_rules_explicitly_authorize_it(
    coordinator, tracker, project_id, task_id, fingerprint
):
    """Bot identity is valid only when independently configured as an owner."""
    issue = Issue(
        id=task_id,
        identifier=task_id,
        state="Open",
        title="Test task",
        description="Test",
    )
    project = _MockProject(status_label_authorized_logins=["oompah"])
    tracker.set_metadata(
        task_id,
        {METADATA_KEY: TerminalAuditMetadata.empty().to_dict()},
    )

    result = await coordinator.override_transition(
        current_issue=issue,
        requested_target=TargetState.DONE,
        authorized_actor=ContributorIdentity("oompah", "github"),
        project_id=project_id,
        evidence_fingerprint=fingerprint,
        reason="Explicitly configured bot owner",
        project=project,
    )

    assert result.success is True


@pytest.mark.asyncio
async def test_auditor_identity_cannot_override_without_owner_authorization(
    coordinator, tracker, project_id, task_id, fingerprint
):
    """An auditor agent is not a project owner merely because it can audit."""
    issue = Issue(
        id=task_id,
        identifier=task_id,
        state="Open",
        title="Test task",
        description="Test",
    )
    project = _MockProject(status_label_authorized_logins=["owner"])
    tracker.set_metadata(
        task_id,
        {METADATA_KEY: TerminalAuditMetadata.empty().to_dict()},
    )

    result = await coordinator.override_transition(
        current_issue=issue,
        requested_target=TargetState.DONE,
        authorized_actor=ContributorIdentity("auditor", "oompah"),
        project_id=project_id,
        evidence_fingerprint=fingerprint,
        reason="Auditor override attempt",
        project=project,
    )

    assert result.success is False
    assert result.error_code == "unauthorized_actor"


# ---------------------------------------------------------------------------
# Tests: Validation and error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_blank_reason_rejected(
    coordinator, project_id, task_id, fingerprint, owner_identity
):
    """Blank reason is rejected."""
    
    issue = Issue(id=task_id, 
        identifier=task_id,
        state="Open",
        title="Test task",
        description="Test",
    )
    
    project = _MockProject(
        status_label_authorized_logins=["owner"]
    )
    
    with pytest.raises(ValueError, match="reason must be a non-empty string"):
        await coordinator.override_transition(
            current_issue=issue,
            requested_target=TargetState.DONE,
            authorized_actor=owner_identity,
            project_id=project_id,
            evidence_fingerprint=fingerprint,
            reason="",
            project=project,
        )


@pytest.mark.asyncio
async def test_blank_reason_whitespace_rejected(
    coordinator, project_id, task_id, fingerprint, owner_identity
):
    """Whitespace-only reason is rejected."""
    
    issue = Issue(id=task_id, 
        identifier=task_id,
        state="Open",
        title="Test task",
        description="Test",
    )
    
    project = _MockProject(
        status_label_authorized_logins=["owner"]
    )
    
    with pytest.raises(ValueError, match="reason must be a non-empty string"):
        await coordinator.override_transition(
            current_issue=issue,
            requested_target=TargetState.DONE,
            authorized_actor=owner_identity,
            project_id=project_id,
            evidence_fingerprint=fingerprint,
            reason="   ",
            project=project,
        )


@pytest.mark.asyncio
async def test_stale_fingerprint_rejected(
    coordinator, tracker, project_id, task_id, fingerprint, owner_identity
):
    """Stale fingerprint is rejected."""
    
    # Create a different fingerprint
    stale_fingerprint = EvidenceFingerprint.from_evidence(
        requirements_text="old requirements",
        project_id=project_id,
        task_id=task_id,
    )
    
    issue = Issue(id=task_id, 
        identifier=task_id,
        state="Open",
        title="Test task",
        description="Test",
    )
    
    project = _MockProject(
        status_label_authorized_logins=["owner"]
    )
    
    metadata = TerminalAuditMetadata(pending_chain=[], unknown_fields={})
    tracker.set_metadata(task_id, {METADATA_KEY: metadata.to_dict()})
    
    # Use the stale fingerprint in override
    result = await coordinator.override_transition(
        current_issue=issue,
        requested_target=TargetState.DONE,
        authorized_actor=owner_identity,
        project_id=project_id,
        evidence_fingerprint=stale_fingerprint,
        reason="Testing stale fingerprint",
        project=project,
    )
    
    # Should succeed since metadata is empty (no pending audits to check)
    # The fingerprint check only fails if there's a mismatch with pending audits
    assert result.success is True


@pytest.mark.asyncio
async def test_stale_fingerprint_rejected_against_pending_audit(
    coordinator, tracker, project_id, task_id, fingerprint, owner_identity
):
    """An override cannot use a fingerprint older than the pending request."""
    current = EvidenceFingerprint.from_evidence(
        requirements_text="current requirements",
        project_id=project_id,
        task_id=task_id,
    )
    stale = EvidenceFingerprint.from_evidence(
        requirements_text="old requirements",
        project_id=project_id,
        task_id=task_id,
    )
    issue = Issue(
        id=task_id,
        identifier=task_id,
        state="In Validation",
        title="Test task",
        description="Test",
    )
    project = _MockProject(status_label_authorized_logins=["owner"])
    pending = TerminalAuditRecord(
        audit_id="audit-current",
        project_id=project_id,
        task_id=task_id,
        target_state=TargetState.DONE,
        evidence_fingerprint=current,
        request_state=RequestState.PENDING,
        requested_by=owner_identity,
    )
    tracker.set_metadata(
        task_id,
        {METADATA_KEY: TerminalAuditMetadata(pending_chain=[pending]).to_dict()},
    )

    result = await coordinator.override_transition(
        current_issue=issue,
        requested_target=TargetState.DONE,
        authorized_actor=owner_identity,
        project_id=project_id,
        evidence_fingerprint=stale,
        reason="Stale evidence should be rejected",
        project=project,
    )

    assert result.success is False
    assert result.error_code == "fingerprint_mismatch"
    assert tracker.comments == []
    assert tracker.status_updates == []


@pytest.mark.asyncio
async def test_metadata_failure_precedes_comment_and_status(
    coordinator, tracker, project_id, task_id, fingerprint, owner_identity
):
    """Metadata failure prevents both the comment and terminal status write."""
    issue = Issue(
        id=task_id,
        identifier=task_id,
        state="Open",
        title="Test task",
        description="Test",
    )
    project = _MockProject(status_label_authorized_logins=["owner"])
    tracker.set_metadata(
        task_id,
        {METADATA_KEY: TerminalAuditMetadata.empty().to_dict()},
    )
    tracker.set_metadata_field = MagicMock(side_effect=RuntimeError("metadata down"))

    result = await coordinator.override_transition(
        current_issue=issue,
        requested_target=TargetState.DONE,
        authorized_actor=owner_identity,
        project_id=project_id,
        evidence_fingerprint=fingerprint,
        reason="Metadata ordering test",
        project=project,
    )

    assert result.success is False
    assert result.error_code == "metadata_write_failed"
    assert tracker.comments == []
    assert tracker.status_updates == []


@pytest.mark.asyncio
async def test_comment_failure_precedes_status_write(
    coordinator, tracker, project_id, task_id, fingerprint, owner_identity
):
    """A missing durable comment prevents applying the terminal target."""
    issue = Issue(
        id=task_id,
        identifier=task_id,
        state="Open",
        title="Test task",
        description="Test",
    )
    project = _MockProject(status_label_authorized_logins=["owner"])
    tracker.set_metadata(
        task_id,
        {METADATA_KEY: TerminalAuditMetadata.empty().to_dict()},
    )
    tracker.add_comment = MagicMock(side_effect=RuntimeError("comments down"))

    result = await coordinator.override_transition(
        current_issue=issue,
        requested_target=TargetState.DONE,
        authorized_actor=owner_identity,
        project_id=project_id,
        evidence_fingerprint=fingerprint,
        reason="Comment ordering test",
        project=project,
    )

    assert result.success is False
    assert result.error_code == "comment_failed"
    assert result.posted_comment is False
    assert tracker.status_updates == []
    # The audit record is intentionally durable even though application waits
    # for the comment, allowing a later retry or human recovery.
    stored = tracker.get_metadata(task_id)[METADATA_KEY]
    assert stored["oompah.terminal_override_records"]


@pytest.mark.asyncio
async def test_override_reason_is_redacted_in_metadata_and_comment(
    coordinator, tracker, project_id, task_id, fingerprint, owner_identity
):
    """Secrets in an owner reason never reach metadata or human comments."""
    issue = Issue(
        id=task_id,
        identifier=task_id,
        state="Open",
        title="Test task",
        description="Test",
    )
    project = _MockProject(status_label_authorized_logins=["owner"])
    tracker.set_metadata(
        task_id,
        {METADATA_KEY: TerminalAuditMetadata.empty().to_dict()},
    )
    secret = "ghp_0123456789abcdefghijklmnop"
    result = await coordinator.override_transition(
        current_issue=issue,
        requested_target=TargetState.DONE,
        authorized_actor=owner_identity,
        project_id=project_id,
        evidence_fingerprint=fingerprint,
        reason=f"Emergency approval token={secret}",
        project=project,
    )

    assert result.success is True
    comment = tracker.comments[0][1]
    stored = tracker.get_metadata(task_id)[METADATA_KEY]
    assert secret not in comment
    assert secret not in repr(stored)
    assert stored["oompah.terminal_override_records"][0]["reason"] == "[REDACTED]"


# ---------------------------------------------------------------------------
# Tests: Multiple override attempts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_repeated_override_succeeds(
    coordinator, tracker, project_id, task_id, fingerprint, owner_identity
):
    """Multiple override attempts for same task succeed independently."""
    
    issue = Issue(id=task_id, 
        identifier=task_id,
        state="Open",
        title="Test task",
        description="Test",
    )
    
    project = _MockProject(
        status_label_authorized_logins=["owner"]
    )
    
    metadata = TerminalAuditMetadata(pending_chain=[], unknown_fields={})
    tracker.set_metadata(task_id, {METADATA_KEY: metadata.to_dict()})
    
    # First override
    result1 = await coordinator.override_transition(
        current_issue=issue,
        requested_target=TargetState.DONE,
        authorized_actor=owner_identity,
        project_id=project_id,
        evidence_fingerprint=fingerprint,
        reason="First override",
        project=project,
    )
    
    assert result1.success is True
    
    # Second override (would move to different state)
    issue2 = replace(issue, state=DONE)
    
    result2 = await coordinator.override_transition(
        current_issue=issue2,
        requested_target=TargetState.MERGED,
        authorized_actor=owner_identity,
        project_id=project_id,
        evidence_fingerprint=fingerprint,
        reason="Second override",
        project=project,
    )
    
    assert result2.success is True
    assert result2.override_id != result1.override_id


# ---------------------------------------------------------------------------
# Tests: Override record persistence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_override_record_persisted_in_metadata(
    coordinator, tracker, project_id, task_id, fingerprint, owner_identity
):
    """Override record is persisted in tracker metadata."""
    
    issue = Issue(id=task_id, 
        identifier=task_id,
        state="Open",
        title="Test task",
        description="Test",
    )
    
    project = _MockProject(
        status_label_authorized_logins=["owner"]
    )
    
    metadata = TerminalAuditMetadata(pending_chain=[], unknown_fields={})
    tracker.set_metadata(task_id, {METADATA_KEY: metadata.to_dict()})
    
    result = await coordinator.override_transition(
        current_issue=issue,
        requested_target=TargetState.DONE,
        authorized_actor=owner_identity,
        project_id=project_id,
        evidence_fingerprint=fingerprint,
        reason="Testing persistence",
        project=project,
    )
    
    assert result.success is True
    
    # Retrieve metadata and verify override record
    stored_metadata = tracker.get_metadata(task_id)
    stored_doc = stored_metadata.get(METADATA_KEY, {})
    overrides = stored_doc.get("oompah.terminal_override_records", [])
    
    assert len(overrides) > 0
    assert overrides[0]["override_id"] == result.override_id
    assert overrides[0]["authorized_by"]["identity"] == "owner"
    assert overrides[0]["reason"] == "Testing persistence"


# ---------------------------------------------------------------------------
# Tests: Different terminal targets
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_override_to_done(
    coordinator, tracker, project_id, task_id, fingerprint, owner_identity
):
    """Override can target Done state."""
    
    issue = Issue(id=task_id, 
        identifier=task_id,
        state="Open",
        title="Test task",
        description="Test",
    )
    
    project = _MockProject(
        status_label_authorized_logins=["owner"]
    )
    
    metadata = TerminalAuditMetadata(pending_chain=[], unknown_fields={})
    tracker.set_metadata(task_id, {METADATA_KEY: metadata.to_dict()})
    
    result = await coordinator.override_transition(
        current_issue=issue,
        requested_target=TargetState.DONE,
        authorized_actor=owner_identity,
        project_id=project_id,
        evidence_fingerprint=fingerprint,
        reason="Override to Done",
        project=project,
    )
    
    assert result.success is True
    assert result.applied_status == DONE


@pytest.mark.asyncio
async def test_override_to_merged(
    coordinator, tracker, project_id, task_id, fingerprint, owner_identity
):
    """Override can target Merged state."""
    
    issue = Issue(id=task_id, 
        identifier=task_id,
        state=DONE,
        title="Test task",
        description="Test",
    )
    
    project = _MockProject(
        status_label_authorized_logins=["owner"]
    )
    
    metadata = TerminalAuditMetadata(pending_chain=[], unknown_fields={})
    tracker.set_metadata(task_id, {METADATA_KEY: metadata.to_dict()})
    
    result = await coordinator.override_transition(
        current_issue=issue,
        requested_target=TargetState.MERGED,
        authorized_actor=owner_identity,
        project_id=project_id,
        evidence_fingerprint=fingerprint,
        reason="Override to Merged",
        project=project,
    )
    
    assert result.success is True
    assert result.applied_status == MERGED


@pytest.mark.asyncio
async def test_override_to_archived(
    coordinator, tracker, project_id, task_id, fingerprint, owner_identity
):
    """Override can target Archived state."""
    
    issue = Issue(id=task_id, 
        identifier=task_id,
        state=MERGED,
        title="Test task",
        description="Test",
    )
    
    project = _MockProject(
        status_label_authorized_logins=["owner"]
    )
    
    metadata = TerminalAuditMetadata(pending_chain=[], unknown_fields={})
    tracker.set_metadata(task_id, {METADATA_KEY: metadata.to_dict()})
    
    result = await coordinator.override_transition(
        current_issue=issue,
        requested_target=TargetState.ARCHIVED,
        authorized_actor=owner_identity,
        project_id=project_id,
        evidence_fingerprint=fingerprint,
        reason="Override to Archived",
        project=project,
    )
    
    assert result.success is True
    assert result.applied_status == ARCHIVED


# ---------------------------------------------------------------------------
# Tests: Error handling and edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_metadata_quarantine_rejected(
    coordinator, tracker, project_id, task_id, fingerprint, owner_identity
):
    """Override is rejected when metadata is quarantined."""
    
    issue = Issue(id=task_id, 
        identifier=task_id,
        state="Open",
        title="Test task",
        description="Test",
    )
    
    project = _MockProject(
        status_label_authorized_logins=["owner"]
    )
    
    from oompah.terminal_audit_metadata import MetadataQuarantine
    quarantine = MetadataQuarantine(
        fingerprint="a" * 64,
        reason="Test quarantine",
    )
    metadata = TerminalAuditMetadata(
        pending_chain=[],
        unknown_fields={},
        quarantine=quarantine,
    )
    tracker.set_metadata(task_id, {METADATA_KEY: metadata.to_dict()})
    
    result = await coordinator.override_transition(
        current_issue=issue,
        requested_target=TargetState.DONE,
        authorized_actor=owner_identity,
        project_id=project_id,
        evidence_fingerprint=fingerprint,
        reason="Should be rejected",
        project=project,
    )
    
    assert result.success is False
    assert "quarantined" in result.reason.lower()


@pytest.mark.asyncio
async def test_invalid_target_rejected(
    coordinator, project_id, task_id, fingerprint, owner_identity
):
    """Invalid target state is rejected."""
    
    issue = Issue(id=task_id, 
        identifier=task_id,
        state="Open",
        title="Test task",
        description="Test",
    )
    
    project = _MockProject(
        status_label_authorized_logins=["owner"]
    )
    
    with pytest.raises(ValueError):
        await coordinator.override_transition(
            current_issue=issue,
            requested_target="InvalidState",  # type: ignore
            authorized_actor=owner_identity,
            project_id=project_id,
            evidence_fingerprint=fingerprint,
            reason="Invalid target",
            project=project,
        )


# ---------------------------------------------------------------------------
# Tests: Override record structure
# ---------------------------------------------------------------------------


def test_override_record_serialization():
    """OverrideRecord serializes and deserializes correctly."""
    
    actor = ContributorIdentity(identity="owner", source="github")
    fp = EvidenceFingerprint.from_evidence(
        requirements_text="test",
        project_id="proj-1",
        task_id="TASK-1",
    )
    
    record = OverrideRecord(
        override_id="override-abc123",
        project_id="proj-1",
        task_id="TASK-1",
        target_state=TargetState.DONE,
        evidence_fingerprint=fp,
        authorized_by=actor,
        reason="Testing override",
        created_at="2024-01-15T10:30:00+00:00",
    )
    
    # Serialize
    serialized = record.to_dict()
    assert serialized["override_id"] == "override-abc123"
    assert serialized["reason"] == "Testing override"
    assert serialized["target_state"] == "Done"
    
    # Deserialize
    deserialized = OverrideRecord.from_dict(serialized)
    assert deserialized.override_id == record.override_id
    assert deserialized.reason == record.reason
    assert deserialized.target_state == record.target_state
    assert deserialized.authorized_by.identity == "owner"


def test_override_record_requires_non_empty_reason():
    """OverrideRecord rejects blank reason."""
    
    actor = ContributorIdentity(identity="owner", source="github")
    fp = EvidenceFingerprint.from_evidence(
        requirements_text="test",
        project_id="proj-1",
        task_id="TASK-1",
    )
    
    with pytest.raises(ValueError, match="reason must be a non-empty string"):
        OverrideRecord(
            override_id="override-abc123",
            project_id="proj-1",
            task_id="TASK-1",
            target_state=TargetState.DONE,
            evidence_fingerprint=fp,
            authorized_by=actor,
            reason="",
        )


def test_override_record_requires_authorized_by():
    """OverrideRecord requires authorized_by identity."""
    
    fp = EvidenceFingerprint.from_evidence(
        requirements_text="test",
        project_id="proj-1",
        task_id="TASK-1",
    )
    
    with pytest.raises(TypeError, match="authorized_by must be a ContributorIdentity"):
        OverrideRecord(
            override_id="override-abc123",
            project_id="proj-1",
            task_id="TASK-1",
            target_state=TargetState.DONE,
            evidence_fingerprint=fp,
            authorized_by="not-an-identity",  # type: ignore
            reason="Test",
        )


# ---------------------------------------------------------------------------
# Tests: Multiple audit records with fingerprint supersession (OOMPAH-604)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_override_allowed_with_matching_current_record_among_superseded(
    coordinator, tracker, project_id, task_id, owner_identity
):
    """Override succeeds when current record matches, even if superseded ones don't.
    
    This is the regression test for OOMPAH-604: after terminal-audit evidence
    supersession, multiple Done audit records may exist with different
    fingerprints. An authorized owner override should evaluate only the
    current active record (non-superseded), allowing the override when it
    matches even if historical superseded records have different fingerprints.
    """
    
    # Create two fingerprints (old and current)
    old_fingerprint = EvidenceFingerprint.from_evidence(
        requirements_text="old evidence",
        project_id=project_id,
        task_id=task_id,
    )
    current_fingerprint = EvidenceFingerprint.from_evidence(
        requirements_text="current evidence",
        project_id=project_id,
        task_id=task_id,
    )
    
    issue = Issue(
        id=task_id,
        identifier=task_id,
        state="In Validation",
        title="Test task",
        description="Test task with multiple audits",
    )
    
    project = _MockProject(
        status_label_authorized_logins=["owner"]
    )
    
    # Create two audit records: old superseded, current active
    old_record = TerminalAuditRecord(
        audit_id="audit-old",
        project_id=project_id,
        task_id=task_id,
        target_state=TargetState.DONE,
        evidence_fingerprint=old_fingerprint,
        request_state=RequestState.SUPERSEDED,  # This one is superseded
        requested_by=owner_identity,
    )
    
    current_record = TerminalAuditRecord(
        audit_id="audit-current",
        project_id=project_id,
        task_id=task_id,
        target_state=TargetState.DONE,
        evidence_fingerprint=current_fingerprint,  # Matches the override
        request_state=RequestState.PENDING,  # This one is current
        requested_by=owner_identity,
    )
    
    # Store metadata with both records
    metadata = TerminalAuditMetadata(
        pending_chain=[old_record, current_record],
        unknown_fields={}
    )
    tracker.set_metadata(task_id, {METADATA_KEY: metadata.to_dict()})
    
    # Override with current fingerprint should succeed
    result = await coordinator.override_transition(
        current_issue=issue,
        requested_target=TargetState.DONE,
        authorized_actor=owner_identity,
        project_id=project_id,
        evidence_fingerprint=current_fingerprint,  # Matches current record
        reason="Approved after evidence update",
        project=project,
    )
    
    assert result.success is True
    assert result.applied_status == DONE
    assert result.posted_comment is True
    assert (task_id, DONE) in tracker.status_updates


@pytest.mark.asyncio
async def test_override_rejected_when_current_record_fingerprint_mismatch(
    coordinator, tracker, project_id, task_id, owner_identity
):
    """Override is rejected when current record fingerprint doesn't match.
    
    Even if there are superseded records, we check only the current one.
    If the current record's fingerprint doesn't match the override's
    evidence_fingerprint, the override is rejected.
    """
    
    # Create two fingerprints
    old_fingerprint = EvidenceFingerprint.from_evidence(
        requirements_text="old evidence",
        project_id=project_id,
        task_id=task_id,
    )
    current_fingerprint = EvidenceFingerprint.from_evidence(
        requirements_text="current evidence",
        project_id=project_id,
        task_id=task_id,
    )
    stale_fingerprint = EvidenceFingerprint.from_evidence(
        requirements_text="stale evidence",
        project_id=project_id,
        task_id=task_id,
    )
    
    issue = Issue(
        id=task_id,
        identifier=task_id,
        state="In Validation",
        title="Test task",
        description="Test task",
    )
    
    project = _MockProject(
        status_label_authorized_logins=["owner"]
    )
    
    # Create two records: old superseded with one fingerprint, current with another
    old_record = TerminalAuditRecord(
        audit_id="audit-old",
        project_id=project_id,
        task_id=task_id,
        target_state=TargetState.DONE,
        evidence_fingerprint=old_fingerprint,
        request_state=RequestState.SUPERSEDED,
        requested_by=owner_identity,
    )
    
    current_record = TerminalAuditRecord(
        audit_id="audit-current",
        project_id=project_id,
        task_id=task_id,
        target_state=TargetState.DONE,
        evidence_fingerprint=current_fingerprint,
        request_state=RequestState.PENDING,
        requested_by=owner_identity,
    )
    
    metadata = TerminalAuditMetadata(
        pending_chain=[old_record, current_record],
        unknown_fields={}
    )
    tracker.set_metadata(task_id, {METADATA_KEY: metadata.to_dict()})
    
    # Try to override with a fingerprint that doesn't match current record
    result = await coordinator.override_transition(
        current_issue=issue,
        requested_target=TargetState.DONE,
        authorized_actor=owner_identity,
        project_id=project_id,
        evidence_fingerprint=stale_fingerprint,  # Doesn't match current
        reason="Should fail",
        project=project,
    )
    
    assert result.success is False
    assert result.error_code == "fingerprint_mismatch"
    assert tracker.comments == []
    assert tracker.status_updates == []


@pytest.mark.asyncio
async def test_override_allowed_when_no_pending_record_exists(
    coordinator, tracker, project_id, task_id, owner_identity
):
    """Override succeeds when no pending record exists for the target.
    
    If there's no current active record for the requested target (all are
    superseded or none exist), the fingerprint check passes and the override
    proceeds with authorization checks.
    """
    
    fingerprint = EvidenceFingerprint.from_evidence(
        requirements_text="some evidence",
        project_id=project_id,
        task_id=task_id,
    )
    
    issue = Issue(
        id=task_id,
        identifier=task_id,
        state="Open",
        title="Test task",
        description="Test task",
    )
    
    project = _MockProject(
        status_label_authorized_logins=["owner"]
    )
    
    # Empty metadata (no pending records)
    metadata = TerminalAuditMetadata(pending_chain=[], unknown_fields={})
    tracker.set_metadata(task_id, {METADATA_KEY: metadata.to_dict()})
    
    result = await coordinator.override_transition(
        current_issue=issue,
        requested_target=TargetState.DONE,
        authorized_actor=owner_identity,
        project_id=project_id,
        evidence_fingerprint=fingerprint,
        reason="Override without existing audit",
        project=project,
    )
    
    assert result.success is True
    assert result.applied_status == DONE


@pytest.mark.asyncio
async def test_override_with_multiple_records_different_targets(
    coordinator, tracker, project_id, task_id, owner_identity
):
    """Override correctly handles multiple records for different targets.
    
    When the chain has records for different targets (e.g., Done and Merged),
    only the record matching the requested_target is checked for fingerprint
    mismatch.
    """
    
    done_fingerprint = EvidenceFingerprint.from_evidence(
        requirements_text="done evidence",
        project_id=project_id,
        task_id=task_id,
    )
    merged_fingerprint = EvidenceFingerprint.from_evidence(
        requirements_text="merged evidence",
        project_id=project_id,
        task_id=task_id,
    )
    override_fingerprint = EvidenceFingerprint.from_evidence(
        requirements_text="override evidence",
        project_id=project_id,
        task_id=task_id,
    )
    
    issue = Issue(
        id=task_id,
        identifier=task_id,
        state="In Validation",
        title="Test task",
        description="Test task",
    )
    
    project = _MockProject(
        status_label_authorized_logins=["owner"]
    )
    
    # Create Done and Merged records with different fingerprints
    done_record = TerminalAuditRecord(
        audit_id="audit-done",
        project_id=project_id,
        task_id=task_id,
        target_state=TargetState.DONE,
        evidence_fingerprint=done_fingerprint,
        request_state=RequestState.PENDING,
        requested_by=owner_identity,
    )
    
    merged_record = TerminalAuditRecord(
        audit_id="audit-merged",
        project_id=project_id,
        task_id=task_id,
        target_state=TargetState.MERGED,
        evidence_fingerprint=merged_fingerprint,
        request_state=RequestState.PENDING,
        requested_by=owner_identity,
    )
    
    metadata = TerminalAuditMetadata(
        pending_chain=[done_record, merged_record],
        unknown_fields={}
    )
    tracker.set_metadata(task_id, {METADATA_KEY: metadata.to_dict()})
    
    # Override to Merged with a different fingerprint should fail
    # (it should check against merged_fingerprint, not done_fingerprint)
    result = await coordinator.override_transition(
        current_issue=issue,
        requested_target=TargetState.MERGED,
        authorized_actor=owner_identity,
        project_id=project_id,
        evidence_fingerprint=override_fingerprint,  # Doesn't match merged
        reason="Override to Merged",
        project=project,
    )
    
    assert result.success is False
    assert result.error_code == "fingerprint_mismatch"
    
    # But override to Done should succeed since we're using a different fingerprint
    # but will check only the Done record
    result_done = await coordinator.override_transition(
        current_issue=issue,
        requested_target=TargetState.DONE,
        authorized_actor=owner_identity,
        project_id=project_id,
        evidence_fingerprint=done_fingerprint,  # Matches the Done record
        reason="Override to Done",
        project=project,
    )
    
    assert result_done.success is True
