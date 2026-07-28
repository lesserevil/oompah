# Terminal-Transition Coordinator — API Reference

Quick reference for implementing the `TerminalTransitionCoordinator` class. Full design at `plans/terminal-transition-coordinator.md`.

## Class Definition

```python
# File: oompah/terminal_transition_coordinator.py

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Optional
import asyncio

from oompah.terminal_audit import (
    TargetState,
    RequestState,
    EvidenceFingerprint,
    ContributorIdentity,
    TerminalAuditRecord,
)
from oompah.terminal_audit_metadata import TerminalAuditMetadataStore, TerminalAuditMetadata
from oompah.statuses import IN_VALIDATION, TERMINAL_STATUSES


@dataclass
class TransitionResult:
    """Result of a request_transition call."""
    
    success: bool
    audit_id: Optional[str] = None
    queued_targets: list[TargetState] = field(default_factory=list)
    coalesced: bool = False
    superseded_audit_id: Optional[str] = None
    reason: Optional[str] = None


@dataclass
class ProjectContext:
    """Project/tracker metadata for a transition request."""
    
    project_id: str
    tracker_kind: str  # "github_issues", "gitlab_issues", "oompah_md", etc.
    tracker_owner: str
    tracker_repo: str


class TerminalTransitionCoordinator:
    """Stages and orchestrates terminal status transitions with audit chains.
    
    Ensures:
    - Atomicity: Request persisted before status move
    - Idempotence: Identical requests coalesce; changed fingerprints supersede
    - Auditability: Every transition recorded in a durable audit chain
    - Concurrency safety: Per-project locks prevent races
    """
    
    def __init__(
        self,
        project_store: "ProjectStore",
        tracker_interface: "TrackerInterface",
    ):
        """Initialize the coordinator.
        
        Args:
            project_store: ProjectStore for metadata persistence
            tracker_interface: Interface to read/write task statuses and comments
        """
        self.project_store = project_store
        self.tracker_interface = tracker_interface
        self._locks: dict[str, asyncio.Lock] = {}
        self._queued_comments_posted: set[tuple[str, str]] = set()
    
    async def request_transition(
        self,
        current_issue: "Issue",
        requested_target: TargetState,
        trigger_identity: ContributorIdentity,
        project_context: ProjectContext,
        evidence_fingerprint: EvidenceFingerprint,
    ) -> TransitionResult:
        """Request a terminal status transition for a task.
        
        Stages a transition request, persists the audit chain atomically,
        moves the task to "In Validation" status, and posts a notification.
        
        Args:
            current_issue:
                The task/issue being transitioned (has .id and .status).
            requested_target:
                Target state: TargetState.DONE, MERGED, or ARCHIVED.
            trigger_identity:
                ContributorIdentity of who/what triggered the request.
            project_context:
                ProjectContext with project_id and tracker metadata.
            evidence_fingerprint:
                EvidenceFingerprint (SHA-256) of requirements, SHAs,
                review state, contributors, and child audits.
        
        Returns:
            TransitionResult with success status and audit details.
        
        Raises:
            ValueError: If required parameters are invalid.
            RuntimeError: If persistence or tracker writes fail.
        """
        # Step 1: Acquire per-project lock
        lock = self._locks.setdefault(project_context.project_id, asyncio.Lock())
        async with lock:
            # Step 2: Load current audit chain
            current_chain = self._load_audit_chain(
                project_context.project_id,
                current_issue.id,
            )
            
            # Step 3: Coalesce or supersede
            coalesce_result = self._check_coalesce(
                current_chain,
                requested_target,
                evidence_fingerprint,
            )
            if coalesce_result is not None:
                return coalesce_result
            
            superseded = self._supersede_if_needed(
                current_chain,
                requested_target,
                evidence_fingerprint,
            )
            
            # Step 4: Build new audit chain
            new_chain = self._build_audit_chain(
                current_chain,
                current_issue,
                requested_target,
                trigger_identity,
                evidence_fingerprint,
                project_context,
            )
            
            # Step 5: Atomically persist
            self._save_audit_chain(
                project_context.project_id,
                current_issue.id,
                new_chain,
            )
            
            # Step 6: Move to In Validation (if not already terminal)
            if current_issue.status not in TERMINAL_STATUSES:
                await self.tracker_interface.set_status(
                    issue=current_issue,
                    status=IN_VALIDATION,
                    comment=f"Queued for terminal transition: {requested_target.value}",
                )
            
            # Step 7: Post notification (once)
            self._post_queued_comment_once(
                project_context.project_id,
                current_issue.id,
                requested_target,
            )
            
            return TransitionResult(
                success=True,
                audit_id=new_chain[0].id,
                queued_targets=[a.target for a in new_chain],
                coalesced=False,
                superseded_audit_id=superseded,
            )
    
    def _load_audit_chain(self, project_id: str, task_id: str) -> list[TerminalAuditRecord]:
        """Load the current audit chain from metadata storage."""
        # Retrieve task metadata, parse terminal_audit_chain JSON array
        # Return list of TerminalAuditRecord (may be empty for first request)
        pass
    
    def _check_coalesce(
        self,
        current_chain: list[TerminalAuditRecord],
        requested_target: TargetState,
        fingerprint: EvidenceFingerprint,
    ) -> TransitionResult | None:
        """Return early if an identical request is already pending.
        
        Returns:
            TransitionResult with coalesced=True if match found, else None.
        """
        for audit in current_chain:
            if (audit.target == requested_target 
                and audit.request_state == RequestState.PENDING
                and audit.fingerprint == fingerprint):
                return TransitionResult(
                    success=True,
                    audit_id=audit.id,
                    queued_targets=[requested_target],
                    coalesced=True,
                )
        return None
    
    def _supersede_if_needed(
        self,
        current_chain: list[TerminalAuditRecord],
        requested_target: TargetState,
        fingerprint: EvidenceFingerprint,
    ) -> str | None:
        """Mark pending audits with changed fingerprints as SUPERSEDED.
        
        Returns:
            audit_id of superseded audit, or None.
        """
        for audit in current_chain:
            if (audit.target == requested_target
                and audit.request_state == RequestState.PENDING
                and audit.fingerprint != fingerprint):
                audit.request_state = RequestState.SUPERSEDED
                self._save_audit_chain(...)  # Update storage
                return audit.id
        return None
    
    def _build_audit_chain(
        self,
        current_chain: list[TerminalAuditRecord],
        issue: "Issue",
        target: TargetState,
        trigger: ContributorIdentity,
        fingerprint: EvidenceFingerprint,
        project_context: ProjectContext,
    ) -> list[TerminalAuditRecord]:
        """Construct the new audit chain based on target state rules.
        
        - Done: Creates one audit
        - Merged: Reuses completed Done or queues Done then Merged
        - Archived: Defers to pending earlier targets
        """
        if target == TargetState.DONE:
            return self._chain_done(issue, trigger, fingerprint, project_context)
        elif target == TargetState.MERGED:
            return self._chain_merged(current_chain, issue, trigger, fingerprint, project_context)
        elif target == TargetState.ARCHIVED:
            return self._chain_archived(current_chain, issue, trigger, fingerprint, project_context)
    
    def _chain_done(
        self,
        issue: "Issue",
        trigger: ContributorIdentity,
        fingerprint: EvidenceFingerprint,
        project_context: ProjectContext,
    ) -> list[TerminalAuditRecord]:
        """Create a Done audit chain: [Done(pending)]."""
        audit = TerminalAuditRecord(
            audit_id=self._generate_audit_id(),
            project_id=project_context.project_id,
            task_id=issue.id,
            target_state=TargetState.DONE,
            evidence_fingerprint=fingerprint,
            request_state=RequestState.PENDING,
            requested_by=trigger,
            previous_state=issue.status,
            created_at=self._now_iso8601(),
        )
        return [audit]
    
    def _chain_merged(
        self,
        current_chain: list[TerminalAuditRecord],
        issue: "Issue",
        trigger: ContributorIdentity,
        fingerprint: EvidenceFingerprint,
        project_context: ProjectContext,
    ) -> list[TerminalAuditRecord]:
        """Create a Merged audit chain.
        
        If a completed Done audit exists, reuse it and create Merged.
        Otherwise, queue Done then Merged.
        """
        completed_done = None
        for audit in current_chain:
            if (audit.target == TargetState.DONE 
                and audit.request_state == RequestState.COMPLETED):
                completed_done = audit
                break
        
        chain = current_chain.copy() if current_chain else []
        
        if completed_done is None:
            # Case 1: No completed Done; queue both
            done_audit = TerminalAuditRecord(
                audit_id=self._generate_audit_id(),
                project_id=project_context.project_id,
                task_id=issue.id,
                target_state=TargetState.DONE,
                evidence_fingerprint=EvidenceFingerprint.from_evidence(
                    # Compute Done evidence fingerprint (may differ from Merged)
                    ...
                ),
                request_state=RequestState.PENDING,
                requested_by=trigger,
                previous_state=issue.status,
                created_at=self._now_iso8601(),
            )
            chain.append(done_audit)
        
        # Case 2: Create Merged audit (reuses Done if exists)
        merged_audit = TerminalAuditRecord(
            audit_id=self._generate_audit_id(),
            project_id=project_context.project_id,
            task_id=issue.id,
            target_state=TargetState.MERGED,
            evidence_fingerprint=fingerprint,
            request_state=RequestState.PENDING,
            requested_by=trigger,
            created_at=self._now_iso8601(),
        )
        chain.append(merged_audit)
        return chain
    
    def _chain_archived(
        self,
        current_chain: list[TerminalAuditRecord],
        issue: "Issue",
        trigger: ContributorIdentity,
        fingerprint: EvidenceFingerprint,
        project_context: ProjectContext,
    ) -> list[TerminalAuditRecord]:
        """Create an Archived audit chain.
        
        If any non-Archived audit is PENDING, defer Archived to run after.
        Otherwise, queue Archived immediately.
        """
        has_pending_non_archived = any(
            a.request_state == RequestState.PENDING 
            and a.target != TargetState.ARCHIVED
            for a in current_chain
        )
        
        chain = current_chain.copy() if current_chain else []
        
        audit = TerminalAuditRecord(
            audit_id=self._generate_audit_id(),
            project_id=project_context.project_id,
            task_id=issue.id,
            target_state=TargetState.ARCHIVED,
            evidence_fingerprint=fingerprint,
            request_state=RequestState.PENDING,
            requested_by=trigger,
            created_at=self._now_iso8601(),
        )
        chain.append(audit)
        return chain
    
    def _save_audit_chain(
        self,
        project_id: str,
        task_id: str,
        chain: list[TerminalAuditRecord],
    ) -> None:
        """Atomically persist audit chain to metadata storage via TerminalAuditMetadataStore.
        
        Uses the existing metadata store (oompah/terminal_audit_metadata.py) to:
        1. Read current metadata (acquiring per-project write lock)
        2. Update pending_chain with new/updated audits
        3. Atomically write back to tracker metadata
        4. Release write lock
        
        Must succeed before tracker status writes (Step 6).
        """
        store = TerminalAuditMetadataStore(
            tracker=self.tracker_interface,
            project_store=self.project_store,
            project_id=project_id,
        )
        
        def _update_chain(document: TerminalAuditMetadata) -> TerminalAuditMetadata:
            # Replace entire pending_chain with new chain
            return replace(document, pending_chain=chain)
        
        store.update(task_id, _update_chain)
    
    def _post_queued_comment_once(
        self,
        project_id: str,
        task_id: str,
        target: TargetState,
    ) -> None:
        """Post a queued notification comment (only once per task)."""
        key = (project_id, task_id)
        if key in self._queued_comments_posted:
            return  # Already posted
        
        # Post comment via tracker_interface
        # Mark as posted in set and persist to storage
        self._queued_comments_posted.add(key)
    
    def _generate_audit_id(self) -> str:
        """Generate a unique audit ID (e.g., UUID or timestamp-based)."""
        import uuid
        return f"audit-{uuid.uuid4().hex[:8]}"
    
    def _now_iso8601(self) -> str:
        """Return current time in ISO 8601 format."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()
    
    async def load_recovered_requests(self, project_id: str) -> list[TerminalAuditRecord]:
        """Load all PENDING and IN_PROGRESS audits for recovery on startup.
        
        Called by the auditor during bootstrap to resume after a restart.
        """
        # Scan all tasks in the project
        # For each task, load its audit chain
        # Yield all PENDING and IN_PROGRESS audits
        pass
```

## Integration: Server Bootstrap

Add to `oompah/bootstrap.py` → `setup_services`:

```python
# After creating orchestrator
coordinator = TerminalTransitionCoordinator(
    project_store=project_store,
    tracker_interface=tracker,  # or orchestrator's tracker access
)

orchestrator.terminal_transition_coordinator = coordinator

# Return in Services
return Services(
    ...,
    terminal_transition_coordinator=coordinator,
)
```

## Integration: Orchestrator Usage

Add method to `Orchestrator`:

```python
async def request_terminal_transition(
    self,
    task: Task,
    target: TargetState,
    trigger: ContributorIdentity,
) -> TransitionResult:
    """Request a terminal status transition."""
    
    fingerprint = EvidenceFingerprint.from_evidence(
        requirements_text=task.requirements or "",
        project_id=task.project_id,
        task_id=task.id,
        source_branch=task.branch or "",
        source_sha=task.commit_sha or "",
        target_branch=task.target_branch or "main",
        target_sha=task.target_sha or "",
        review_id=task.review_id or "",
        review_state=task.review_state or "",
        contributors=[ContributorIdentity(task.author)] if task.author else [],
    )
    
    return await self.terminal_transition_coordinator.request_transition(
        current_issue=task,
        requested_target=target,
        trigger_identity=trigger,
        project_context=ProjectContext(
            project_id=self.current_project_id,
            tracker_kind=self.tracker_kind,
            tracker_owner=self.tracker_owner,
            tracker_repo=self.tracker_repo,
        ),
        evidence_fingerprint=fingerprint,
    )
```

## Storage: Metadata Persistence

Audit chains are stored as JSON under task metadata:

```json
{
  "project_id": "proj-xyz",
  "task_id": "OOMPAH-123",
  "terminal_audit_chain": [
    {
      "version": 1,
      "audit_id": "audit-abc123",
      "project_id": "proj-xyz",
      "task_id": "OOMPAH-123",
      "target_state": "Done",
      "request_state": "pending",
      "evidence_fingerprint": {
        "version": 1,
        "algorithm": "sha256",
        "digest": "a1b2c3..."
      },
      "attempts": [],
      "requested_by": {
        "version": 1,
        "identity": "auditor-bot",
        "source": "oompah"
      },
      "previous_state": "In Progress",
      "created_at": "2026-07-28T19:00:00Z"
    }
  ],
  "queued_comments_posted": [
    ["proj-xyz", "OOMPAH-123"]
  ]
}
```

## Testing Checklist

Run focused tests before handoff:

```bash
make test -- tests/test_terminal_transition_coordinator.py -v
```

Test cases (from plans/terminal-transition-coordinator.md):

- [ ] `test_done_creates_one_audit()`
- [ ] `test_merged_with_current_done_reuses_audit()`
- [ ] `test_merged_without_done_queues_both()`
- [ ] `test_archived_defers_to_pending()`
- [ ] `test_duplicate_requests_coalesce()`
- [ ] `test_changed_fingerprint_supersedes()`
- [ ] `test_simultaneous_requests_serialize()`
- [ ] `test_stale_requests_rejected()`
- [ ] `test_queued_comment_posted_once()`
- [ ] `test_restart_recovered_requests()`
- [ ] `test_per_project_locking()`
- [ ] `test_tracker_write_failure_ordering()`
- [ ] `test_direct_merged_without_audit_evidence()`

## Error Handling

Common failures and recovery:

| Error | Handling |
|-------|----------|
| Fingerprint mismatch | Supersede pending with same target |
| No project context | Raise ValueError |
| Tracker write fails | Retry (audit chain already persisted) |
| Storage write fails | Raise RuntimeError; do not move to In Validation |
| Concurrent request | Acquire lock; serialize second request |

## Performance Considerations

- **Lock contention**: Per-project locks reduce cross-project blocking
- **Metadata reads**: Cache audit chains during request (single read per lock)
- **Fingerprint computation**: O(evidence fields); amortized across batches
- **Comment dedup**: O(1) set lookup; persisted for restart recovery
