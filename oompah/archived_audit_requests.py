"""Helper for requesting archived audits from maintenance paths."""

import logging
import uuid
from datetime import datetime, timezone

from oompah.models import Issue
from oompah.statuses import IN_VALIDATION
from oompah.terminal_audit import (
    ContributorIdentity,
    RequestState,
    TargetState,
    TerminalAuditRecord,
    compute_evidence_fingerprint,
)
from oompah.terminal_audit_metadata import TerminalAuditMetadata, TerminalAuditMetadataStore
from oompah.tracker import TrackerProtocol

logger = logging.getLogger(__name__)


def request_archived_audit(
    issue: Issue,
    tracker: TrackerProtocol,
    project_id: str,
    disposition_reason: str,
    project_store: object | None = None,
) -> bool:
    """Request an Archived audit for the given issue.
    
    Returns True if a new audit was queued, False if one is already pending
    or if the operation failed.
    
    Parameters
    ----------
    issue : Issue
        The issue to archive
    tracker : TrackerProtocol
        The tracker for the issue
    project_id : str
        The project ID
    disposition_reason : str
        Human-readable reason for archiving (e.g. "Aged Done/Merged auto-archive")
    project_store : object, optional
        The project store for writing locks. If None, uses a noop store.
        
    Returns
    -------
    bool
        True if audit was queued, False if already pending or failed
    """
    if project_store is None:
        # Create a noop project store for backward compatibility
        class _NoopProjectStore:
            def project_write_lock(self, _project_id: str):
                class _NoopLock:
                    def __enter__(self):
                        return self
                    def __exit__(self, *_args):
                        return None
                return _NoopLock()
        project_store = _NoopProjectStore()
    
    try:
        store = TerminalAuditMetadataStore(
            tracker, project_store, project_id
        )
        
        # Create evidence fingerprint from disposition reason
        evidence_fingerprint = compute_evidence_fingerprint(
            requirements_text=disposition_reason,
            project_id=project_id,
            task_id=issue.identifier,
        )
        
        # Read current metadata to check for pending audits
        try:
            doc = store.read(issue.identifier)
        except Exception:
            doc = TerminalAuditMetadata.empty()
        
        # Check for existing pending Archived audit with same fingerprint
        for record in doc.pending_chain:
            if (
                record.target_state == TargetState.ARCHIVED
                and record.request_state in (RequestState.PENDING, RequestState.IN_PROGRESS)
                and record.evidence_fingerprint == evidence_fingerprint
            ):
                logger.debug(
                    "Audit already pending for %s (audit_id=%s)",
                    issue.identifier,
                    record.audit_id,
                )
                return False  # Already queued with same disposition
        
        # Create new audit record
        now = datetime.now(timezone.utc).isoformat()
        audit_id = f"audit-{uuid.uuid4().hex[:12]}"
        
        record = TerminalAuditRecord(
            audit_id=audit_id,
            project_id=project_id,
            task_id=issue.identifier,
            target_state=TargetState.ARCHIVED,
            evidence_fingerprint=evidence_fingerprint,
            request_state=RequestState.PENDING,
            requested_by=ContributorIdentity(
                identity="oompah",
                source="maintenance",
            ),
            previous_state=issue.state or None,
            created_at=now,
        )
        
        # Upsert the audit record
        store.upsert_pending_audit(issue.identifier, record)
        
        # Move issue to In Validation status
        try:
            tracker.update_issue(issue.identifier, status=IN_VALIDATION)
        except Exception as exc:
            logger.warning(
                "Failed to update %s to In Validation after audit request: %s",
                issue.identifier,
                exc,
            )
            return False
        
        logger.info(
            "Queued Archived audit for %s (audit_id=%s, disposition=%s)",
            issue.identifier,
            audit_id,
            disposition_reason,
        )
        return True
        
    except Exception as exc:
        logger.exception(
            "Failed to request archived audit for %s: %s",
            issue.identifier,
            exc,
        )
        return False
