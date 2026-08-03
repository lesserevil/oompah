# Terminal-Transition Coordinator

**Status:** Implemented (OOMPAH-465 staging, OOMPAH-466 result routing)
**Epic:** OOMPAH-457  
**Prerequisites:** OOMPAH-461 (In Validation status), OOMPAH-462 (Terminal audits), OOMPAH-463 (Metadata persistence), OOMPAH-464 (Grandfather recovery)

## Overview

The `TerminalTransitionCoordinator` is a server-owned service that stagingizes and orchestrates terminal status transitions (Done, Merged, Archived) into durable audit chains. It prevents duplicate work, coalesces identical requests, and ensures atomicity: requests are persisted before the task is moved to "In Validation," guaranteeing recovery on restart.

### Design Principles

1. **Atomicity**: Request persisted → status moved to In Validation (not the reverse)
2. **Idempotence**: Repeated identical requests coalesce; changed fingerprints supersede pending work
3. **Auditability**: Every transition is recorded in a `TerminalAuditRecord` chain
4. **Determinism**: State transitions follow fixed rules: Done creates one audit; Merged reuses passed Done or queues Done→Merged; Archived defers to earlier pending targets
5. **Concurrency Safety**: Per-project locks prevent race conditions
6. **No Direct Status Writes**: The coordinator only *stages* requests; the auditor applies terminal statuses

## Definitions

### Terminal States

```python
class TargetState(Enum):
    DONE = "Done"
    MERGED = "Merged"
    ARCHIVED = "Archived"
```

### Request Lifecycle

```python
class RequestState(Enum):
    PENDING = "pending"            # Queued, not yet processed
    IN_PROGRESS = "in_progress"   # Auditor is working
    COMPLETED = "completed"        # Terminal status applied
    SUPERSEDED = "superseded"      # Replaced by newer request
    CANCELLED = "cancelled"        # Manually cancelled (future)
```

### Audit Chains

- **Done Chain**: `[Done(audit-1)]`
- **Merged Chain (with Done)**: `[Done(audit-1), Merged(audit-2)]`
- **Merged Chain (direct)**: `[Done(audit-1), Merged(audit-2)]` (the Done
  audit is queued unless a completed or already-active Done audit exists)
- **Archived Chain**: `[..., Archived(audit-N)]` (defers to earlier pending targets)

### Evidence Fingerprint

```python
class EvidenceFingerprint:
    digest: str  # SHA-256 of requirements, SHAs, review state, contributors, child audits
```

Fingerprints are deterministic and stable across identical inputs. A *changed fingerprint* signals new evidence and supersedes pending work of the same target.

## API: `request_transition`

```python
async def request_transition(
    current_issue: Issue,
    requested_target: TargetState,
    trigger_identity: ContributorIdentity,
    project_context: ProjectContext,
    evidence_fingerprint: EvidenceFingerprint,
) -> TransitionResult
```

### Parameters

- **`current_issue`**: The task/issue being transitioned
- **`requested_target`**: `Done`, `Merged`, or `Archived`
- **`trigger_identity`**: Who/what requested the transition (auditor, admin, etc.)
- **`project_context`**: Project/tracker metadata for tracker writes
- **`evidence_fingerprint`**: SHA-256 of requirements, source/target SHAs, review state, contributors, child audits

### Behavior

#### Step 1: Acquire Per-Project Lock

```python
async with _locks[project_context.project_id]:
    # Prevent concurrent requests for the same task
```

#### Step 2: Load Current State

```python
current_chain = load_audit_chain(
    project_id=project_context.project_id,
    task_id=current_issue.id,
)
```

#### Step 3: Coalesce or Supersede

1. **Coalesce identical requests**: If a pending audit for `requested_target` exists with *the same fingerprint*, return early without updating metadata or posting comments
2. **Supersede on changed fingerprint**: If a pending audit for `requested_target` exists with a *different fingerprint*, mark it `SUPERSEDED`, create a new audit with the new fingerprint, and re-enqueue

#### Step 4: Handle State Chains

Chain semantics are based on the `requested_target`:

##### Done

Creates one audit:

```python
audit = TerminalAuditRecord(
    audit_id=generate_id(),
    project_id=project_context.project_id,
    task_id=current_issue.id,
    target_state=TargetState.DONE,
    evidence_fingerprint=evidence_fingerprint,
    request_state=RequestState.PENDING,
    requested_by=trigger_identity,
    created_at=now(),
    previous_state=current_issue.status,
)
chain = [audit]
```

##### Merged

**Case 1: Current chain includes a COMPLETED Done audit**

Reuse it; create a Merged audit:

```python
done_audit = [a for a in current_chain if a.target == Done and a.request_state == COMPLETED][0]
merged_audit = TerminalAuditRecord(
    audit_id=generate_id(),
    target_state=TargetState.MERGED,
    evidence_fingerprint=evidence_fingerprint,
    parent_audit_id=done_audit.id,
)
chain = [done_audit, merged_audit]
```

**Case 2: No completed or active Done audit exists**

Queue Done first, then Merged:

```python
done_audit = TerminalAuditRecord(target_state=DONE, request_state=PENDING)
merged_audit = TerminalAuditRecord(target_state=MERGED, request_state=PENDING)
chain = [done_audit, merged_audit]
```

If a pending or in-progress Done audit already exists, it is reused for the
chain and only the Merged audit is appended. This prevents a repeated direct
Merged event from scheduling duplicate completion work.

##### Archived

**Safe-retirement semantics**: If any earlier (Done or Merged) audit is PENDING, defer the Archived audit to run *after* completion.

```python
if any(a.request_state == PENDING and a.target != ARCHIVED for a in current_chain):
    # Enqueue Archived to run after current audits complete
    audit = TerminalAuditRecord(
        target_state=ARCHIVED,
        request_state=PENDING,
        # Will be picked up by auditor after earlier targets complete
    )
else:
    # No pending non-Archived work; create Archived now
    audit = TerminalAuditRecord(target_state=ARCHIVED, request_state=PENDING)
chain = [audit]
```

#### Step 5: Atomically Persist Request

```python
save_audit_chain(
    project_id=project_context.project_id,
    task_id=current_issue.id,
    chain=chain,
)
```

This write is **durable** and occurs *before* step 6. On restart, the auditor recovers pending audits from storage.

#### Step 6: Move Task to "In Validation" Status

```python
if current_issue.status not in TERMINAL_STATUSES:
    await tracker.set_status(
        issue=current_issue,
        status=IN_VALIDATION,
        comment=queued_comment,
    )
```

**Important**: The status move happens *after* persistence, so if the process crashes, the persisted request survives.

#### Step 7: Post Concise Queued Comment (Once)

Check if a queued comment has already been posted for this task (to avoid duplicates on retries):

```python
if not has_queued_comment(project_id, task_id):
    tracker.post_comment(
        issue=current_issue,
        text=f"Queued for terminal transition: {requested_target}",
    )
    mark_queued_comment_posted(project_id, task_id)
```

### Return Value

```python
class TransitionResult:
    success: bool
    audit_id: str | None
    queued_targets: list[TargetState]  # [DONE], [DONE, MERGED], or [ARCHIVED]
    coalesced: bool  # True if request was deduplicated
    superseded_audit_id: str | None  # If a prior request was superseded
    reason: str | None  # Error details if success=False
```

## State Transitions

### Stale Request Rejection

A request is **stale** if:

- The requested `requested_target` already has a `COMPLETED` audit in the chain
- The `evidence_fingerprint` matches that completed audit

**Action**: Return `TransitionResult(success=False, reason="already completed")`

### Concurrent Request Handling

Two concurrent requests for the same task acquire the per-project lock serially. The second waits for the first to commit, then:

- **Same target, same fingerprint** → Coalesce (return success, no new audit)
- **Same target, different fingerprint** → Supersede (mark old SUPERSEDED, create new)
- **Different target** → Append to chain (if target-specific rules allow)

## Recovery and Restart Semantics

### Graceful Restart

1. On shutdown, in-flight audits remain `IN_PROGRESS` in storage
2. On startup, the auditor loads all `PENDING` and `IN_PROGRESS` audits
3. `IN_PROGRESS` audits are re-tried (idempotent auditor operations)
4. `PENDING` audits are worked through in order (target-dependent)

### Restart-Recovered Requests

Requests for tasks that were moved to `IN_VALIDATION` but the process crashed:

1. The audit chain is loaded from storage (persisted in step 5 of `request_transition`)
2. The auditor resumes from the last known state
3. No duplicate comments are posted (the queued-comment flag was set in step 7)
4. No duplicate audit records are created (requests are idempotent by fingerprint)

## Per-Project Locking

Each `project_id` has a dedicated async lock. Requests for the same task in different projects do not block each other; requests for different tasks in the same project may block briefly on the global orchestrator lock but not on this coordinator's per-project lock.

```python
_locks: dict[str, asyncio.Lock] = {}

async with _locks.setdefault(project_id, asyncio.Lock()):
    # Acquire exclusive access to this project's requests
```

## Comment Deduplication

Store a set of task IDs for which a queued comment has been posted:

```python
_queued_comments_posted: set[tuple[str, str]] = set()  # (project_id, task_id)

def mark_queued_comment_posted(project_id: str, task_id: str) -> None:
    _queued_comments_posted.add((project_id, task_id))

def has_queued_comment(project_id: str, task_id: str) -> bool:
    return (project_id, task_id) in _queued_comments_posted
```

**Persistence**: On shutdown, write `_queued_comments_posted` to metadata storage. On startup, reload it.

## Integration Points

### Server Bootstrap (`oompah/bootstrap.py`)

```python
async def setup_services(...) -> Services:
    # ...
    coordinator = TerminalTransitionCoordinator(
        project_store=project_store,
        tracker_store=tracker_store,  # or inline tracker ops
    )
    
    orchestrator = Orchestrator(
        ...,
        terminal_transition_coordinator=coordinator,
    )
    
    return Services(..., coordinator=coordinator, ...)
```

### Orchestrator Usage

```python
class Orchestrator:
    async def request_terminal_transition(
        self,
        task: Task,
        target: TargetState,
        trigger: ContributorIdentity,
    ) -> TransitionResult:
        return await self.terminal_transition_coordinator.request_transition(
            current_issue=task,
            requested_target=target,
            trigger_identity=trigger,
            project_context=self.project_context,
            evidence_fingerprint=...,  # Computed from task state
        )
```

### Auditor Interaction

The coordinator stages requests; the **auditor** (`oompah/auditor.py` or similar) consumes them:

1. Load all `PENDING` audits for the project
2. Execute the audit for each target state
3. Submit the verdict to `TerminalTransitionCoordinator.apply_audit_result(issue, result, project_id)` — the coordinator (not the auditor) marks the record `COMPLETED`, applies the tracker status, and posts the result comment
4. On a passing Done in a Done→Merged chain the coordinator keeps the task in `In Validation` and reports `advanced_target=Merged` so the auditor drives the next audit

## Result Application (OOMPAH-466)

`apply_audit_result` accepts an `AuditResult` submitted by an auditor and turns it into a durable tracker state change with no fail-open path.

### AuditResult inputs

- `audit_id`, `target_state`, `evidence_fingerprint` — CAS keys; must match the pending record exactly
- `verdict` — `PASS`, `FAIL`, `NEEDS_HUMAN`, or `ERROR`
- `failure_classification` — required for `FAIL` verdicts
- `message` — human-oriented explanation (assumed pre-redacted)
- `safe_evidence` — small map of scalar evidence keys the coordinator may echo in the result comment
- `auditor` — `ContributorIdentity` of the writer
- `attempt_id` — idempotency key; duplicate submissions are recognised and re-applied without side effects

### Compare-and-set

The coordinator rejects any result whose:

- `audit_id` is not present in the chain (`ResultRejection.AUDIT_NOT_FOUND`)
- `target_state` differs from the persisted record (`TARGET_MISMATCH`)
- `evidence_fingerprint` differs from the persisted record (`FINGERPRINT_MISMATCH`)
- Record is no longer `PENDING`/`IN_PROGRESS` (`STATE_MISMATCH`)
- Issue is not in `In Validation` on the tracker (`ISSUE_NOT_IN_VALIDATION`)

A rejected result leaves the record unchanged and never applies a tracker status.

### Verdict routing

| Verdict | Behaviour |
|---------|-----------|
| `PASS` | Mark record `COMPLETED`, record safe evidence in the attempt, apply the audited target's terminal status, advance to next chain item (or keep `In Validation` when a later target is pending). |
| `FAIL` (with classification) | Mark record `COMPLETED`, route to a repair state via the central classification map, post an explanation comment. |
| `NEEDS_HUMAN` | Compose an actionable comment (fallback text appended when the message is not actionable); refuse to apply the status if the tracker's `validate_needs_human_comment` still rejects it. |
| `ERROR` | Leave the record non-terminal; the task stays in `In Validation`. |

### Central failure-classification map

`classify_failure_to_status(classification, previous_state)` is the only place that maps `FailureClassification` values to statuses:

| Classification | Status |
|----------------|--------|
| `INCOMPLETE`, `MISSING_TESTS`, `UNPUSHED`, `MISSING_EVIDENCE` | `Open` |
| `CI_FAILURE` | `Needs CI Fix` |
| `CONFLICT`, `OUT_OF_DATE` | `Needs Rebase` |
| `HEALTHY_UNMERGED_REVIEW` | `In Review` |
| `AMBIGUOUS_REQUIREMENTS`, `EXTERNAL_CAPABILITY`, `NO_AUDITOR` | `Needs Human` |
| `UNSAFE_ARCHIVE` | Restore recorded `previous_state`; `Needs Human` when the pre-audit state is missing or terminal |
| `MALFORMED_RESULT`, `INFRASTRUCTURE_ERROR` | `None` — coordinator keeps the record non-terminal |

Unknown classifications raise `ValueError` — the switch fails closed for any new failure mode that has not been explicitly routed.

### Commit-Before-Comment Ordering

**Critical requirement (OOMPAH-734):** The durable verdict record **MUST be persisted and marked COMPLETED before any human-readable PASS/FAIL comment is posted** to the tracker.

#### Sequence for all verdicts:

1. **Atomically persist the record as COMPLETED** (update to storage):
   - Record `verdict` (PASS, FAIL, NEEDS_HUMAN, ERROR)
   - Record `failure_classification` (if applicable)
   - Record `safe_evidence` snapshot
   - Record `attempt_id` and timestamps
   - Mark `request_state` = `COMPLETED`
   - This write **survives provider timeout, policy denial, and process crash**

2. **Compute the human-readable message** (no side effects):
   - Classify the verdict and extract safe evidence
   - Compose the tracker comment text
   - Determine the target status (Done/Open/Needs CI Fix/etc.)

3. **Apply tracker state** (idempotent writes, safe to retry):
   - Update the task status (only if verdict is not ERROR)
   - Only after the status succeeds, post the human-readable result comment

#### Recovery path for an unapplied status intent:

If the auditor process crashes, times out, or receives a policy denial **after step 1 but before step 3**:

1. On restart, enforcement loads the `COMPLETED` record and its unapplied status intent.
2. Recovery revalidates project/task identity, target, lifecycle, and evidence fingerprint.
3. Recovery retries the exact status write and marks the intent applied after acceptance. It does not infer a verdict from comments or manufacture a comment during recovery.

#### Auditor turn-ceiling boundary:

When an auditor approaches or reaches its turn ceiling while deciding a PASS verdict:

1. The auditor **must reserve the finalization call as non-starvable**:
   - Final ordinary turn: complete the audit logic, gather evidence, decide PASS/FAIL
   - Finalization call (outside the ordinary turn budget): invoke `submit_audit_result` with the verdict
   - API sessions expose only `submit_audit_result` on the reserved finalization turn

2. The coordinator persists the verdict atomically in step 1 above, **independently of whether the auditor's session later completes normally or times out**

3. On service restart:
   - Load persisted completed verdicts and their unapplied status intents
   - Safely apply tracker state without reopening or redispatching the verdict

This ensures an auditor reaching its turn ceiling **cannot strand the task in In Validation** — the durable verdict is already committed and will be surfaced to the tracker on recovery.

### No fail-open paths

- `ERROR` verdicts and unparseable payloads never apply a status.
- `MALFORMED_RESULT` and `INFRASTRUCTURE_ERROR` classifications never apply a status.
- Retry ceilings never apply a status.
- `NEEDS_HUMAN` results whose comment is not actionable are rejected — the coordinator will not move the task to `Needs Human` without an actionable explanation.
- A tracker status failure leaves an observable unapplied intent and suppresses the result comment; a comment failure after the status succeeds does not roll back the durable audit record.
- **Commit-before-comment enforcement**: Verdict records are persisted COMPLETED before any tracker comment; provider/timeout/process-crash failures after persistence do not corrupt the durable verdict.

## Testing Strategy

### Test Structure

```
tests/
  test_terminal_transition_coordinator.py
    - TestRequestTransition
      - test_done_creates_one_audit()
      - test_merged_with_current_done_reuses_audit()
      - test_merged_without_done_queues_both()
      - test_archived_defers_to_pending()
      - test_duplicate_requests_coalesce()
      - test_changed_fingerprint_supersedes()
      - test_simultaneous_requests_serialize()
      - test_stale_requests_rejected()
      - test_queued_comment_posted_once()
      - test_restart_recovered_requests()
      - test_per_project_locking()
      - test_tracker_write_failure_ordering()
      - test_direct_merged_without_audit_evidence()
```

### Coverage Requirements

1. **Every target and chain**: Done (1 audit), Merged (reused + new), Archived (deferred)
2. **Direct Merged**: With/without current Done evidence
3. **Duplicate events**: Same fingerprint, same target
4. **Changed fingerprints**: Supersede pending work
5. **Simultaneous requests**: Two concurrent calls for the same task
6. **Superseded chains**: Verify old audit marked `SUPERSEDED`
7. **Tracker write failures**: Verify persistence occurs before status write
8. **Restart-recovered requests**: Reload from storage, no duplicate comments
9. **Comment deduplication**: Verify comment posted once across retries
10. **Per-project locking**: Requests from different projects proceed in parallel

## Acceptance Criteria

✓ No terminal status is written by staging (only by auditor after audit completion)  
✓ Every request has one durable chain (audit chain is persisted atomically)  
✓ Direct Merged cannot skip completion auditing (Done is created or reused)  
✓ Retries/events cannot create duplicate auditor work (idempotent by fingerprint + coalescing)  
✓ All tests pass; focused tests run before handoff; full gate (`make test`) passes on review branch  

## Data Schema

### TerminalAuditRecord (existing in `terminal_audit.py`)

```python
@dataclass
class TerminalAuditRecord:
    audit_id: str
    project_id: str
    task_id: str
    target_state: TargetState  # DONE, MERGED, ARCHIVED
    evidence_fingerprint: EvidenceFingerprint
    request_state: RequestState  # PENDING, IN_PROGRESS, COMPLETED, SUPERSEDED
    attempts: list[AuditAttempt]  # Auditor execution history
    requested_by: ContributorIdentity | None
    previous_state: str | None  # Status before In Validation
    created_at: str | None  # ISO 8601
    updated_at: str | None  # ISO 8601
```

### Audit Chain Storage

Stored as a JSON array under task metadata:

```json
{
  "project_id": "proj-xyz",
  "task_id": "OOMPAH-123",
  "terminal_audit_chain": [
    {
      "version": 1,
      "audit_id": "audit-1",
      "target_state": "Done",
      "request_state": "completed",
      ...
    },
    {
      "version": 1,
      "audit_id": "audit-2",
      "target_state": "Merged",
      "request_state": "pending",
      ...
    }
  ]
}
```

## Future Extensions

- **Manual cancellation**: Add `CANCELLED` request state for admin override
- **Audit replay**: Rerun a failed audit attempt without creating a new audit
- **Chain visualization**: API endpoint to inspect current audit chain for a task
- **Metrics**: Counter/gauge for pending/completed/failed audits by target state and project
