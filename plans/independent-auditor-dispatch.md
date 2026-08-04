# Independent Auditor Dispatch Lane

**Status:** Implemented (OOMPAH-475)
**Epic:** OOMPAH-457
**Related:** OOMPAH-464 (Candidate Selector), OOMPAH-465 (Staging), OOMPAH-466 (Result Routing)

This document describes the implemented dispatch integration: durable
terminal-audit records, independent candidate policy, the reserved read-only
auditor contract, and the priority scheduler lane wired into the orchestrator.
The `OOMPAH_AUDIT_*` settings are available in `.env.example`.

## Overview

The independent auditor dispatch lane is a priority queue that reads persisted terminal-status audit requests, gathers target-specific evidence, selects an independent auditor candidate, and starts a reserved auditor focus with retry and recovery semantics.

This document complements the terminal-transition coordinator design (`plans/terminal-transition-coordinator.md`) by describing how audits move from the "pending" state (queued by the coordinator) through dispatched auditor sessions, candidate rotation on failure, rehydration on restart, and final routing to "Needs Human" when all independent candidates are exhausted.

### Design Principles

1. **Priority over ordinary work**: The audit lane runs before ordinary `Open` dispatch when a global slot is available. Within the lane, `OOMPAH_AUDIT_PRIORITY` orders requests that do not have an explicit task priority, so audits do not starve behind feature work.

2. **One auditor per epic branch**: Serialize auditor work on the same epic/task branch to prevent race conditions with branch writers (agents that claim the branch for implementation).

3. **Global concurrency limit**: Auditors consume from the normal `OOMPAH_MAX_CONCURRENT_AGENTS` limit and respect all provider health, budget, and rate-limit constraints.

4. **Candidate rotation on failure**: On transient provider/tool failures (rate limit, timeout, tool error), the system rotates to the next independent candidate with normal exponential backoff, up to `OOMPAH_AUDIT_MAX_ATTEMPTS`.

5. **Idempotent dispatch and recovery**: Attempt identity is persisted *before* auditor launch. On restart, pending/running audits are rehydrated with their exact attempt metadata, enabling idempotent retries without duplicate state changes.

6. **Abandoned session detection**: If an auditor session crashes or hangs, the attempt is marked abandoned; the next scheduler tick re-checks it and rotates candidates if the session's TTL has expired.

7. **Exhaustion handling**: When all independent candidates fail, the audit is marked with the existing `no_auditor` failure classification so the coordinator routes it to `Needs Human` with actionable configuration instructions.

## Architecture

### Audit Dispatch Flow

```mermaid
flowchart TD
    tick[Orchestrator scheduler tick]
    load[Load persisted tasks in In Validation]
    target[Extract the next pending target from terminal-audit metadata]
    lock{Epic/task branch claim available?}
    evidence[Collect target evidence and contributor provenance]
    candidate[Select the next independent auditor candidate]
    available{Candidate available?}
    human[Submit no_auditor failure; coordinator routes to Needs Human]
    preflight[Run provider, budget, and health preflight]
    persist[Persist attempt identity and candidate before launch]
    launch[Launch the reserved read-only auditor focus]
    result[Auditor submits submit_audit_result]
    apply[Coordinator validates the contract and applies the verdict]

    tick --> load --> target --> lock
    lock -- no; defer --> tick
    lock -- yes --> evidence --> candidate --> available
    available -- no --> human
    available -- yes --> preflight --> persist --> launch --> result --> apply
```

### Data Structures

#### Proposed dispatch attempt fields

The existing `AuditAttempt` is persisted inside each
`TerminalAuditRecord.attempts` list and in the bounded top-level
`attempt_history`. It already carries the stable `attempt_id`, target,
fingerprint, request state, verdict, classification, and timestamps. The
dispatch lane must extend that versioned record (or add a versioned adjacent
dispatch record) with its provider/model, launch timestamp, completion
timestamp, and rotation number. Do not invent a second top-level running-
attempt field: `oompah.terminal_audit` currently has only `pending_chain`,
`attempt_history`, and optional quarantine data.

```python
@dataclass
class AuditAttempt:
    attempt_id: str
    target_state: TargetState
    evidence_fingerprint: EvidenceFingerprint
    request_state: RequestState = RequestState.PENDING
    verdict: Verdict | None = None
    failure_classification: FailureClassification | None = None
    requested_by: ContributorIdentity | None = None
    created_at: str | None = None
    completed_at: str | None = None

# Dispatch-only fields to add through a versioned schema migration:
# provider_id, model, started_at, ended_at, candidate_rotation_count.
```

#### Audit Metadata (Task Storage)

Stored in task metadata under `oompah.terminal_audit`:

```json
{
  "version": 1,
  "pending_chain": [
    {
      "audit_id": "audit-1",
      "target_state": "Done",
      "request_state": "pending",
      "evidence_fingerprint": {
        "version": 1,
        "algorithm": "sha256",
        "digest": "<64 lowercase hex characters>"
      },
      "created_at": "2026-01-01T12:00:00Z",
      "previous_state": "Open",
      "attempts": []
    }
  ],
  "attempt_history": []
}
```

### Candidate Selection Policy

The independent auditor candidate selection process mirrors the seeded auditor role initialization (see `oompah/auditor_candidate_selector.py`) with the additional constraint that candidates must be independent of the task's contributors.

**Selection order:**

1. Load the auditor role from the project's role store (`.oompah/roles.json`).
2. Call `AuditorCandidateSelector.select_candidates(contributors=task_contributors, exclude=attempted_pairs)` to get eligible independent candidates in the configured role order.
3. Exclude provider/model pairs already attempted for this audit. If no candidate remains, use the selector's reason (for example, `all_are_contributors`) and mark the audit with `NO_AUDITOR` failure.
4. Apply provider health, budget, and rate-limit preflight checks.
5. Persist the attempt and launch.

**Independence policy:**

- A candidate (provider_id, model) is independent if:
  - Its provider_id is not in the set of contributor providers, OR
  - Its provider_id matches a contributor provider but its model is different from all models used by that provider's contributors
- Candidates from providers with unknown/SDK-managed model identities are treated as dependent if *any* contributor from that provider exists (fail-closed policy).

**Rotation on failure:**

When a candidate fails (provider error, timeout, auditor crash), the system:

1. Marks the attempt `ended_at` and records the failure reason (from provider logs or auditor exit code).
2. Increments `candidate_rotation_count`.
3. After the normal retry backoff, the next scheduler tick calls `select_candidates` again, excluding candidates already used by this audit.
4. If `select_candidates` returns no candidates, submit a `NO_AUDITOR` failure.

### Fingerprint-Based Duplicate-Dispatch Prevention

**Context (OOMPAH-734):** When an auditor completes with a PASS verdict and commits that result, the scheduler must not launch a second auditor for the same target and fingerprint. This is prevented through compare-and-set logic in the coordinator.

#### Duplicate-dispatch guard in scheduler:

Before dispatching a new audit attempt:

1. Load the pending audit record from task metadata
2. Check the audit chain for any **completed** record with:
   - Same `target_state` (Done, Merged, or Archived)
   - Same `evidence_fingerprint` (exact SHA-256 match)
   - `request_state = COMPLETED` (not PENDING or IN_PROGRESS)
3. If a completed match exists:
   - **Skip dispatch** — the audit has already been decided for this evidence
   - Log a deduplication event
   - Return to scheduler (do not launch a second auditor)
4. If no completed match exists, proceed to dispatch

#### Evidence fingerprint stability:

The fingerprint is a deterministic SHA-256 digest of:

- Task/issue requirements text
- Source and target git SHAs
- Review/merge state at the time of request
- Set of task contributors
- Child audit digests (for hierarchical tasks)

If evidence changes (new code commit, requirement update, reviewer addition), the fingerprint changes. A new fingerprint triggers a new audit, allowing re-evaluation with updated evidence. This is intentional and correct.

#### Idempotency guarantee:

The coordinator's compare-and-set check (`FINGERPRINT_MISMATCH` rejection) ensures:

- A completed audit with fingerprint F **cannot be overwritten** by a result with fingerprint F'
- A pending audit with fingerprint F **cannot be succeeded** by a result with fingerprint F'
- This preserves audit history: audit decisions are durable and cannot be retroactively changed

Combined with the dispatcher's duplicate-dispatch guard, this ensures:

- After a PASS verdict is committed for (target, fingerprint), no second auditor is launched for the same pair
- If evidence changes (new fingerprint), a new audit is independently launched
- No race between dispatcher and coordinator can create duplicate work

### Turn-Ceiling and Finalization Semantics

**Context (OOMPAH-734):** An auditor reaching its configured turn ceiling while deciding a verdict must not strand the task in In Validation. The finalization call (submitting the verdict via `submit_audit_result`) must be guaranteed to complete, independent of the auditor's turn budget.

#### Auditor Turn-Ceiling Boundary

An auditor session has a configured turn ceiling (e.g., 100 turns). The auditor lifecycle reserves the **finalization call as non-starvable**:

1. **Turns 1 to N-1 (ordinary work):** Auditor gathers evidence, runs checks, analyzes the work, and decides on a verdict. At turn N-1, the auditor has completed its logic and holds a decided verdict (PASS, FAIL, NEEDS_HUMAN, or ERROR).

2. **Turn N or finalization call (outside ordinary budget):** The auditor invokes `submit_audit_result` with its decided verdict. This call:
   - Does **not** consume the ordinary turn counter (allocated outside the turn budget)
   - Must complete within a fixed finalization timeout (e.g., 10 seconds)
   - Is **never skipped**, even if the auditor has only one turn remaining

3. **Coordinator persistence (atomic, turn-independent):** On receiving the result:
   - Coordinator persists the verdict record as COMPLETED (step 1 of commit-before-comment in terminal-transition-coordinator.md)
   - This write survives provider timeout, policy denial, or process crash
   - Even if the auditor's session crashes after this point, the durable verdict is committed

#### Recovery Path for Exit-Before-Finalization

If the auditor reaches its turn ceiling before calling `submit_audit_result` (rare, due to finalization reservation):

1. Auditor exits with an incomplete attempt record (no verdict persisted)
2. On the next scheduler tick, dispatcher detects the ended attempt after retry backoff
3. Dispatcher calls `select_candidates` to rotate to the next auditor candidate
4. New auditor is launched for the same audit, starting fresh with the same evidence

#### Recovery Path for Exit-After-Finalization-Call-but-Before-Coordinator-Persistence

This is mitigated by durable coordinator ordering:

1. If the coordinator receives the call, it persists the verdict atomically before applying tracker state or posting a comment.
2. Startup recovery revalidates and applies a persisted result intent; it does not derive or publish a verdict from comment text.
3. If the call exits before persistence, the auditor attempt stays fail-closed and is classified separately from provider transport and command-policy failures.

### Retry and Recovery Semantics

#### On Normal Exit (Auditor Completes)

1. Auditor calls `submit_audit_result` with verdict (PASS, FAIL, NEEDS_HUMAN).
2. TerminalTransitionCoordinator receives the result via `apply_audit_result(attempt_id=...)`.
3. Coordinator validates the attempt_id against the running attempt record.
4. Coordinator marks the audit COMPLETED and applies the verdict:
   - **PASS**: applies the terminal status (Done/Merged/Archived), keeps task in In Validation if later targets are pending
   - **FAIL**: routes to repair state based on failure_classification
   - **NEEDS_HUMAN**: routes the task to `Needs Human` with an actionable comment
5. The attempt record is updated with its verdict, classification, and
   completion timestamp; the coordinator posts the human-readable result
   message as the tracker comment. The auditor worker exits normally.

#### On Transient Failure (Provider/Tool Error)

1. Auditor tool raises exception (rate limit, timeout, connection error, etc.).
2. Orchestrator catches the exception, marks attempt `ended_at`, logs reason.
3. On the next scheduler tick, dispatcher detects the ended attempt after its persisted retry time.
4. Dispatcher checks if retry count < OOMPAH_AUDIT_MAX_ATTEMPTS.
5. Dispatcher calls `select_candidates` to rotate to the next candidate.
6. Dispatcher persists new attempt with incremented `candidate_rotation_count`.
7. Dispatcher launches new auditor session with the new candidate.

#### On Crash/Hang

1. Auditor session crashes (segfault, OOM, process killed, etc.).
2. Orchestrator detects worker exit; if auditor, marks attempt with crash reason.
3. On next scheduler tick, dispatcher rehydrates the task from metadata.
4. Dispatcher checks if running attempt is older than `OOMPAH_AUDIT_ATTEMPT_TTL` (default: 3600 seconds).
5. If TTL expired, dispatcher marks attempt abandoned and rotates candidates.
6. Otherwise, dispatcher assumes the auditor is still running and skips this task.

#### On Graceful Restart

1. Service receives shutdown signal; active workers are drained gracefully.
2. Orchestrator persists all in-flight dispatch state in the in-progress
   `AuditAttempt` record.
3. Service restarts and loads all persisted tasks.
4. Dispatcher scans all tasks in In Validation state.
5. For each task with an in-progress `AuditAttempt`:
   - If a live worker owns the attempt and it is recent, skip it.
   - If a live worker exceeds the TTL, terminate that auditor before reclaiming
     the attempt.
   - If no live worker owns it (including after restart), mark it abandoned and
     rotate without launching a duplicate attempt.

### Backoff and Rate Limiting

Retry backoff follows the normal dispatch retry backoff:

- Reuse the normal scheduler's exponential backoff. Its current initial delay
  is 10 seconds and its ceiling is `OOMPAH_MAX_RETRY_BACKOFF_MS` (default
  300000 ms).

Rate-limit responses (HTTP 429) persist the failure and use the same
exponential backoff as ordinary worker retries before rotating to a different
provider.

### Configuration Variables

New environment variables for independent auditor dispatch:

| Variable | Default | Description |
|----------|---------|-------------|
| `OOMPAH_AUDIT_MAX_ATTEMPTS` | 3 | Maximum number of auditor candidates to attempt per audit before routing to Needs Human |
| `OOMPAH_AUDIT_ATTEMPT_TTL` | 3600 | Seconds; a running attempt older than this is considered abandoned and eligible for retry |
| `OOMPAH_AUDIT_PRIORITY` | 100 | Relative dispatch priority for In Validation tasks (higher = sooner than Open) |
| `OOMPAH_AUDIT_LANE_SCAN_LIMIT` | 32 | Maximum In Validation tasks examined per scheduler tick |

### Concurrency and Serialization

#### Epic-Branch Claim

Auditor tasks and worker tasks contend for an exclusive claim on the
epic/task branch:

```python
_epic_branch_locks: dict[str, asyncio.Lock] = {}

async def claim_branch(epic_id: str, attempt_id: str) -> bool:
    async with _epic_branch_locks.setdefault(epic_id, asyncio.Lock()):
        # Atomically inspect and persist the durable claim for this session.
        # The in-process lock protects this transaction only.
```

- If an auditor holds the lock, incoming worker tasks are blocked and will be retried on the next scheduler tick.
- If a worker holds the lock, incoming audits are blocked and will be retried on the next scheduler tick.
- The in-process lock is held only for the claim transaction. The durable
  claim remains until the auditor or worker exits, so a branch writer cannot
  race an active auditor after launch.

#### Global Concurrency Limit

Auditor agents count against `OOMPAH_MAX_CONCURRENT_AGENTS`:

```python
active_auditors = count_agents(focus="auditor")
active_workers = count_agents(focus!="auditor")
total_active = active_auditors + active_workers
max_concurrent = OOMPAH_MAX_CONCURRENT_AGENTS

can_dispatch = total_active < max_concurrent
```

No special slots are reserved for auditors; they compete fairly with workers for capacity.

## Integration Points

### Orchestrator

The orchestrator's main dispatch loop is extended with an audit lane before the normal work dispatch:

```python
async def _handle_dispatch_needed_locked(self) -> dict[str, float]:
    # Audit dispatch lane (higher priority)
    audit_times = await self._dispatch_audit_lane()
    
    # Existing: Normal work dispatch
    work_times = await self._dispatch_work_lane()
    
    return {**audit_times, **work_times}
```

The audit lane runs the following sequence:

1. Load all tasks in "In Validation" state.
2. For each task, extract the first pending audit from metadata.
3. Attempt to dispatch the audit with `_dispatch_single_audit(task, audit)`.
4. Skip if the task/epic branch is locked by another worker.
5. Persist the attempt identity before launching the reserved worker.
6. Rotate candidates after normal backoff, or route exhaustion to Needs Human.
7. Return scheduling times for metrics and polling adjustment.

### Terminal Transition Coordinator

The coordinator's public `apply_audit_result` contract remains unchanged. The
dispatch lane provides the launch mechanism; the coordinator still validates
the result and applies the terminal status, while merging a result into its
pre-persisted attempt row when the attempt ID matches.

### Candidate Selector

The dispatch lane uses `AuditorCandidateSelector.select_candidates(contributors,
exclude=attempted_pairs)` to obtain the next independent candidate not already
recorded for the audit. The audit lane considers candidates in the saved role
order; it does not apply the role store's round-robin usage history. Selection
is deterministic given the same role, contributor set, and attempted pairs.

## Monitoring and Observability

### Metrics

The live `/api/v1/state` snapshot exposes the following under
`orchestrator_metrics.audits`:

- `dispatch_count` — audits dispatched
- `rotation_count` — audits dispatched after a candidate rotation
- `exhaustion_count` — audits routed to `Needs Human` after exhaustion
- `pending_count` — tasks in `In Validation` with a pending audit
- `in_progress_count` — running auditor agents
- `last_error` — most recent audit-lane error, if any

The same snapshot includes `audit_lane_ms` and related dispatch timings under
`orchestrator_metrics.last_dispatch`, plus `audit_id` and `audit_attempt_id`
in each running-worker row.

### Logging

Dispatch posts tracker comments with the attempt number and candidate. Service
logs contain the task identifier for dispatch failures; inspect both with the
project Make target:

```
make logs
```

### Errors and Alerts

**Actionable alerts:**
- "No independent auditor candidates available" — operator must add providers or adjust whitelist
- "Auditor dispatch queue backed up (>10 pending)" — consider increasing OOMPAH_MAX_CONCURRENT_AGENTS or reducing workload

## Testing Strategy

### Unit Tests

```python
class TestAuditDispatchLane:
    def test_pending_audit_extracted_from_metadata(self):
        # Verify audit metadata parsing
    
    def test_candidate_selector_called_with_contributors(self):
        # Verify independent selection policy
    
    def test_attempt_persisted_before_launch(self):
        # Verify idempotent dispatch recovery
    
    def test_rotation_on_provider_error(self):
        # Simulate 429, verify next candidate selected
    
    def test_exhaustion_routes_to_needs_human(self):
        # Verify no_auditor failure submission
    
    def test_epic_branch_lock_serialization(self):
        # Verify worker/auditor don't race on same branch
    
    def test_concurrent_audit_and_work_dispatch(self):
        # Verify both lanes work without interference
    
    def test_global_concurrency_limit_respected(self):
        # Verify auditors + workers don't exceed limit
```

### Integration Tests

```python
class TestAuditDispatchIntegration:
    def test_priority_over_ordinary_work(self):
        # Queue: 10x Open issues + 1 In Validation audit
        # Verify audit dispatched first
    
    def test_one_agent_per_epic_serialization(self):
        # Start writer on epic; queue audit
        # Verify audit waits for lock
    
    def test_successful_audit_result_flow(self):
        # Dispatch → auditor runs → submits PASS verdict
        # Verify terminal status applied
    
    def test_crash_and_restart_recovery(self):
        # Launch auditor; crash mid-session; restart orchestrator
        # Verify attempt rehydrated, rotation attempted
    
    def test_rate_limit_rotation(self):
        # Provider returns 429; verify candidate switch after normal backoff
    
    def test_timeout_rotation(self):
        # Auditor tool times out; verify rotation on next tick
    
    def test_max_attempts_exhaustion(self):
        # OOMPAH_AUDIT_MAX_ATTEMPTS=2; all fail → Needs Human
```

### Scheduler Focused Tests

```bash
.venv/bin/python -m pytest \
  tests/test_auditor_candidate_selector.py \
  tests/test_auditor_focus.py \
  tests/test_terminal_audit_metadata.py -q
make test
```

## Acceptance Criteria

✓ Every eligible persisted audit in In Validation is eventually dispatched once per attempt  
✓ Audits are retried safely with candidate rotation up to OOMPAH_AUDIT_MAX_ATTEMPTS  
✓ Exhausted audits (no candidates) are routed to Needs Human with actionable configuration instructions  
✓ Auditor work serializes with branch writers (no concurrent mutations)  
✓ Auditor work respects OOMPAH_MAX_CONCURRENT_AGENTS global limit  
✓ Pending/running attempts are rehydrated correctly on restart  
✓ Attempt identity (attempt_id) is persisted before launch for idempotent recovery  
✓ Abandoned auditor sessions (TTL expired) are detected and rotated on next tick  
✓ Changed fingerprint during run is handled safely (no duplicate completion work)  
✓ Stale results (completed audit with new evidence) are rejected by coordinator  
✓ All tests pass; focused scheduler tests run before handoff; full gate passes on review  

## Future Extensions

- **Audit priority levels** — prioritize Done before Merged before Archived
- **Partial evidence refresh** — re-run specific collectors when fingerprint changes
- **Auditor feedback loop** — store auditor performance by provider/model pair for candidate ranking
- **Predictive preflight** — probe provider health during the last work dispatch to warm up candidate list before audit lane
