# Terminal-Audit Enforcement: Periodic Reconciliation and Bypass Detection

**Status:** Implemented (OOMPAH-483)
**Prerequisite:** OOMPAH-465, OOMPAH-466 (Terminal Transition Coordinator staging)
**Related:** `plans/terminal-transition-coordinator.md`

## Overview

The **terminal-audit enforcement** system is a periodic reconciliation pass that runs at server startup and detects unaudited terminal-state writes. It prevents silent bypasses of the coordinator: a task that becomes terminal without going through `TerminalTransitionCoordinator.request_transition` is automatically queued for audit.

### Key Guarantees

1. **Missed Integrations Are Caught**: A task cannot silently become Done/Merged/Archived without an audit request
2. **Grandfather Baseline Prevents Noise**: Pre-existing terminal tasks are marked as "grandfathered" on first startup; only new or changed ones trigger audits
3. **Evidence Fingerprints Detect Changes**: If a task's evidence fingerprint changes (new code, new requirements, different contributors), it's re-audited even if the terminal state is unchanged
4. **Persistence Survives Restarts**: Baseline and pending audits are stored durably in `service_state.json`; restart recovery is idempotent

## Design Concepts

### Grandfather Baseline

On the first successful initialization, all existing terminal tasks (Done, Merged, Archived) are recorded as "grandfathered." This baseline includes:

- Project ID and task ID (scoped together)
- Terminal state (canonical form)
- Evidence fingerprint (SHA-256 of requirements, source/target SHAs, review state, contributors)

Later reconciliation passes compare current tasks against this baseline:

- **Match (same state + fingerprint)**: Task is still grandfathered; no action
- **Missing (was terminal, now non-terminal)**: Baseline entry is removed; task no longer requires audit
- **Changed (new fingerprint)**: Baseline is invalidated; task is queued for re-audit with new evidence
- **New Terminal (was non-terminal, now terminal)**: Queued for new audit

### Evidence Fingerprint

The fingerprint is a deterministic SHA-256 digest that captures the audit scope:

```python
fingerprint = SHA256(json.dumps({
    "format": "oompah-terminal-audit-evidence-v1",
    "requirements": normalized(requirements_text),
    "project_id": normalized(project_id),
    "task_id": normalized(task_id),
    "source_branch": normalized(source_branch),
    "source_sha": normalized(source_sha),
    "target_branch": normalized(target_branch),
    "target_sha": normalized(target_sha),
    "review_id": normalized(review_id),
    "review_state": normalized(review_state),
    "child_audit_digests": sorted(...),
    "contributors": sorted(...),
}))
```

The fingerprint is **stable**: identical inputs always produce the same digest. A changed fingerprint (e.g., new source SHA, added contributor) invalidates the baseline and triggers a re-audit.

**Non-evidence fields are excluded**: Credentials, diff text, auditor prose, and timestamps are not part of the fingerprint, so they do not cause spurious re-audits.

### Reconciliation Algorithm

**Input**: Current state of all tracked tasks + stored baseline + stored pending audits.

**Steps**:

1. **Load State**
   - Read `service_state.json` (or start empty on first run)
   - Parse grandfathered baseline, invalidated tuples, and pending audits
   - Recover `In Validation` metadata for pending audits already in flight

2. **Scan All Tasks**
   - Enumerate all issues in all configured projects
   - For each task, compute its current evidence fingerprint
   - Collect tuples: `(project_id, task_id, state, fingerprint)`

3. **Compare Against Baseline**
   - For each current task:
     - If **non-terminal**: Remove from baseline and invalidated sets (task is no longer terminal)
     - If **terminal and matches baseline**: Grandfathered; no action
     - If **terminal and does NOT match baseline** (new state or different fingerprint): Invalidate baseline entry; queue for audit

4. **Recover Pending Audits**
   - Scan all tasks in `In Validation` status
   - Load their `terminal_audit` metadata (request chain)
   - Extract `PENDING` and `IN_PROGRESS` audits and re-enqueue them
   - **Do not create new attempts** — copy attempt IDs from prior run to avoid duplication on restart

5. **Persist Updated State**
   - Write updated `grandfathered` baseline, `invalidated` tuples, and `pending_audits` to `service_state.json`
   - This persisted state survives a process restart

6. **Return Audit Queue**
   - Caller (typically Orchestrator) receives list of `PendingAudit` entries
   - Auditor consumes this queue asynchronously

### First Startup vs. Later Runs

#### First Startup (`baseline_initialized=False`)

- No prior baseline exists
- Scan all current terminal tasks
- If scan is **complete and successful**:
  - Mark all current terminal tasks as grandfathered
  - Set `baseline_initialized=True`
  - No audits are queued (we assume they're safe)
- If scan **fails or is incomplete**:
  - Queue all observed terminal tasks for audit (fail-closed)
  - Mark `baseline_initialized=False` and `quarantined=True`
  - Operator must review and fix the underlying issue before baseline is accepted

#### Later Runs (`baseline_initialized=True`)

- Normal reconciliation: compare current state against baseline
- Queue only changed or new-terminal tasks for audit
- Mark `quarantined=True` if any errors occur; stop accepting updates to baseline

### Pending Audit Queue

When a task is identified as needing audit, a `PendingAudit` entry is created:

```python
@dataclass
class PendingAudit:
    project_id: str           # "proj-xyz"
    task_id: str              # "OOMPAH-123"
    audit_id: str             # derived from (project, task, state, fingerprint)
    target_state: str         # "Done", "Merged", etc.
    evidence_fingerprint: EvidenceFingerprint
    attempt_ids: list[str]    # Auditor attempt IDs (copied on restart)
    source: str               # "enforcement" or "metadata"
    record: TerminalAuditRecord | None  # Full metadata record if in flight
```

**Key Properties**:

- **Audit ID is deterministic**: Same state + fingerprint always produce the same `audit_id`, so retries are idempotent
- **Attempt IDs are preserved**: On restart, prior auditor attempts are retained so we don't duplicate work
- **Deduplication**: If the same state + fingerprint is queued twice, the entries are merged (attempt IDs combined)

### Error Handling and Quarantine

Errors are logged and collected in `service_state.json` under an `errors` list. When critical errors occur, enforcement enters **quarantine mode**:

```python
self.state.quarantined = True
self.state.baseline_initialized = False
```

In quarantine:

- Baseline is **not updated** from current state
- All observed terminal tasks are queued as "invalidated" (not grandfathered)
- Operator must inspect logs and resolve the issue
- After fix, the service restarts and re-runs enforcement; baseline is accepted only when healthy

**Quarantine triggers**:

- Corrupt `service_state.json`
- Tracker enumeration fails (unable to fetch all issues)
- Metadata corruption for in-flight audits

## Implementation

### TerminalAuditEnforcement Class

Located in `oompah/terminal_audit_enforcement.py`.

#### Key Methods

```python
class TerminalAuditEnforcement:
    def initialize(
        self, scopes: Iterable[tuple[str, TrackerProtocol]]
    ) -> dict[str, Any]:
        """Initialize or reconcile enforcement baseline and pending audits.

        Args:
            scopes: List of (project_id, tracker) tuples.

        Returns:
            Dict with keys:
            - first_startup: bool (True if no prior baseline)
            - baseline_initialized: bool (baseline accepted and will be used for comparison)
            - quarantined: bool (True if errors prevent baseline update)
            - grandfathered: int (count of grandfathered baseline entries)
            - pending_audits: int (count of queued audits)
            - errors: list[str] (error codes encountered)
        """
        pass

    def recover_pending_audits(
        self, scopes: Iterable[tuple[str, TrackerProtocol]], *, persist: bool = True
    ) -> list[PendingAudit]:
        """Recover terminal-audit authority from durable task metadata.

        Replays incomplete result, override, and validation-departure
        transactions before projecting pending audits. Recovery may retire
        status-incompatible records or append a fresh generation when a task
        returns to In Validation with the same immutable evidence. Exact live
        authority resumes with its existing IDs; cancelled or departed
        generations and attempt IDs are never revived or reassigned.
        """
        pass

    def is_grandfathered(
        self,
        project_id: str,
        issue: Issue,
        fingerprint: EvidenceFingerprint | str | Mapping[str, Any] | None = None,
    ) -> bool:
        """Check if a task still matches its grandfathered baseline."""
        pass

    def mark_audit_passed(
        self,
        project_id: str,
        issue: Issue,
        fingerprint: EvidenceFingerprint | str | Mapping[str, Any],
    ) -> None:
        """Promote a freshly audited task into the grandfathered baseline.

        Called by the auditor after a passing audit; reestablishes the baseline
        for this task so later runs don't re-audit the same evidence.
        """
        pass
```

### Storage: service_state.json

Stored at the path configured in orchestrator initialization (default: `workspace/service_state.json`).

**Structure**:

```json
{
  "terminal_audit_enforcement": {
    "version": 1,
    "baseline_initialized": true,
    "grandfathered": [
      {
        "version": 1,
        "project_id": "proj-xyz",
        "task_id": "OOMPAH-123",
        "terminal_state": "Done",
        "evidence_fingerprint": {
          "version": 1,
          "algorithm": "sha256",
          "digest": "abc123..."
        }
      }
    ],
    "invalidated": [
      {
        "version": 1,
        "project_id": "proj-xyz",
        "task_id": "OOMPAH-124",
        "terminal_state": "Merged",
        "evidence_fingerprint": {
          "version": 1,
          "algorithm": "sha256",
          "digest": "def456..."
        }
      }
    ],
    "pending_audits": [
      {
        "version": 1,
        "project_id": "proj-xyz",
        "task_id": "OOMPAH-124",
        "audit_id": "terminal-audit-abc123",
        "target_state": "Merged",
        "evidence_fingerprint": {
          "version": 1,
          "algorithm": "sha256",
          "digest": "def456..."
        },
        "attempt_ids": ["attempt-1"],
        "source": "enforcement"
      }
    ],
    "quarantined": false,
    "errors": []
  },
  "paused": false,
  "future": { "keep": true }
}
```

## Integration: Server Startup

### Orchestrator Integration

In `Orchestrator._run_terminal_audit_enforcement()`:

```python
from oompah.terminal_audit_enforcement import TerminalAuditEnforcement

def _run_terminal_audit_enforcement(self) -> None:
    """Initialize terminal-audit enforcement baseline on startup."""

    enforcer = TerminalAuditEnforcement(
        state_path=self.state_path,
        terminal_states=self.configured_terminal_states,
        project_store=self.project_store,
    )

    scopes = self._terminal_audit_scopes()  # List of (project_id, tracker) tuples
    result = enforcer.initialize(scopes)

    logger.info("Terminal-audit enforcement initialized: %s", result)

    # Recover pending audits and queue them
    pending = enforcer.recover_pending_audits(scopes)
    self._maintenance_status["terminal_audit_enforcement"] = result

    # Auditor will consume pending queue
    self._pending_terminal_audits = pending
```

Call this before the auditor starts:

```python
async def _bootstrap(self) -> None:
    # ... other startup ...
    self._run_terminal_audit_enforcement()  # Before auditor starts
    await self._start_auditor()
```

### Result Handling

After an audit completes, notify enforcement so it updates the baseline:

```python
# In auditor or orchestrator after audit passes
enforcer.mark_audit_passed(
    project_id=audit.project_id,
    issue=task,
    fingerprint=audit.evidence_fingerprint,
)
# This promotes the task into the grandfathered baseline
```

## Testing Strategy

### Unit Tests

File: `tests/test_terminal_audit_enforcement.py`

Test structure:

```python
def test_first_startup_snapshots_existing_terminal_tasks(tmp_path):
    """First startup records grandfathered baseline; second run reuses it."""
    pass

def test_evidence_change_requires_one_fresh_audit(tmp_path):
    """Changed fingerprint invalidates baseline; queues new audit."""
    pass

def test_terminal_to_nonterminal_removes_from_baseline(tmp_path):
    """Task leaving terminal state is removed from baseline."""
    pass

def test_pending_validation_metadata_recovers_idempotently(tmp_path):
    """In Validation recovery does not duplicate attempts."""
    pass

def test_corrupt_service_state_fails_closed_and_quarantines(tmp_path):
    """Corrupt state file triggers quarantine; all terminal tasks queued."""
    pass

def test_malformed_metadata_is_quarantined_with_observable_error(tmp_path):
    """Bad In Validation metadata is logged and marked for operator review."""
    pass

def test_mark_audit_passed_reestablishes_grandfather_baseline(tmp_path):
    """After passing audit, task is promoted into grandfathered baseline."""
    pass

def test_overlapping_task_ids_are_scoped_by_project(tmp_path):
    """Same task ID in different projects are tracked separately."""
    pass
```

### Acceptance Criteria

- [x] First startup: existing terminal tasks are recorded as grandfathered
- [x] Later runs: only changed or new-terminal tasks are queued
- [x] Evidence fingerprint changes trigger re-audit
- [x] Restart recovery preserves attempt IDs (idempotent)
- [x] Corrupt state triggers quarantine and queues all tasks
- [x] Metadata corruption is logged and observable
- [x] All tests pass; focused tests run before handoff
- [x] Full gate (`make test`) passes on review branch

## Related Code Paths

### Tracker Adapters

Each tracker adapter must expose issue enumeration:

```python
class TrackerAdapter(TrackerProtocol):
    def fetch_all_issues_enriched(self) -> list[Issue]:
        """Return all issues with metadata and evidence fingerprint."""
        # GitHub, GitLab, Oompah MD implementations
```

**Fallback path** (for minimal adapters):

```python
def fetch_issues_by_states(self, states: Iterable[str]) -> list[Issue]:
    """Return issues in specified states (terminal + In Validation)."""
    # Used if fetch_all_issues_enriched is not available
```

### Evidence Fingerprint Computation

Located in `oompah/terminal_audit.py`:

```python
EvidenceFingerprint.from_evidence(
    requirements_text=issue.description,
    project_id=project_id,
    task_id=issue.identifier,
    source_branch=issue.branch,
    source_sha=issue.sha,
    target_branch="main",  # or configured default
    target_sha=issue.target_sha,
    review_id=issue.pr_number,
    review_state=issue.pr_state,
    contributors=[...],
    child_audit_digests=[...],
)
```

## Coordinator Interaction

Terminal-transition coordinator (`TerminalTransitionCoordinator`) is the **staging endpoint**. Enforcement is the **reconciliation pass**.

**Data flow**:

```
┌─ Orchestrator requests terminal transition
│  (e.g., after PR merge event)
│
├─ TerminalTransitionCoordinator.request_transition()
│  ├─ Persist audit chain to metadata
│  └─ Move task to In Validation
│
├─ Auditor consumes pending queue (from enforcement)
│  ├─ Fetch all PENDING/IN_PROGRESS audits
│  └─ Execute audit for each
│
└─ After audit passes: enforcer.mark_audit_passed()
   └─ Update grandfathered baseline
```

**Separate concern**:

- **Coordinator**: Stages requests (from direct API calls, webhook events, etc.)
- **Enforcement**: Detects unrequested terminal changes; catches bypasses
- **Auditor**: Executes audits and applies verdicts

## Future Extensions

1. **Direct tracker writes**: When enforcement detects a terminal change that did NOT come from the coordinator (e.g., manual label toggle in GitHub), it can emit a warning or automatically request auditing
2. **Metrics/observability**: Counters for grandfathered vs. invalidated tasks; histogram of evidence fingerprint changes per project
3. **Operator dashboard**: Visualization of baseline status, recent invalidations, and pending audit queue
4. **Policy override**: Allow project owners to explicitly exempt a task from enforcement (e.g., "bulk archive these closed tasks without audit")
