---
id: OOMPAH-1315
type: bug
status: Archived
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1195 identifier=OOMPAH-1195 run_id=ab79167446334859bc98d8c203215877
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-21T00:41:47.946905Z'
updated_at: '2026-08-27T03:56:07.849243Z'
work_branch: OOMPAH-1315
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.lifecycle_revision: 3
oompah.last_batch:
  batch_id: batch-1c1d234dcdd64c5ba5a90080c24b1e3a
  actor: shedwards
  committed_at: '2026-08-21T00:45:50.707738Z'
  operation:
    kind: whole_column_move
    source_status: Backlog
    scope: flat_board
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: ba7797501107300ac3fa2190bad06d6c43c2d6e7092e3b0bb282d0e1866c4005
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-21T04:00:57.154466+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: The supplied task corpus contains no active duplicate\
    \ of OOMPAH-1315. While the corpus includes 29 peer candidates with similarity\
    \ overlap (particularly OOMPAH-1015 and related backend/error_watcher recovery\
    \ tasks), all of these are in terminal states (Merged, Done, or Archived). OOMPAH-1315's\
    \ specific error signature\u2014\"Pre-provider contributor evidence exceeded its\
    \ bounded task-authority deadline\"\u2014does not appear in any active or historical\
    \ task in the corpus. The most similar incident cluster (OOMPAH-1015 and 1016\u2013\
    1027) addresses a distinct error class from `backend:terminal_audit_enforcement`\
    \ and is marked resolved/archived. The corpus is authoritative and comprehensive;\
    \ no new-task duplicacy is detected.\nLooking at this duplicate screening task,\
    \ I need to analyze whether OOMPAH-1315 is a duplicate of an existing active issue\
    \ using only the supplied task corpus.\n\n## Analysis\n\n**Current Task:** OOMPAH-1315\n\
    - **Status:** Open\n- **Error:** \"Pre-provider contributor evidence exceeded\
    \ its bounded task-authority deadline\"\n- **Component:** backend:orchestrator\n\
    - **Source project:** proj-14849f1b\n\n**Corpus Review:**\n\nI've examined all\
    \ 29 included peer tasks in the provided corpus. All candidates fall into these\
    \ categories:\n\n1. **Terminal Tasks (Archived):** OOMPAH-1, OOMPAH-10, OOMPAH-164\n\
    2. **Terminal Tasks (Merged):** OOMPAH-1000, OOMPAH-1001, OOMPAH-1002, OOMPAH-1004,\
    \ OOMPAH-1005, OOMPAH-1006, OOMPAH-1008, OOMPAH-1010, OOMPAH-1011, OOMPAH-1012,\
    \ OOMPAH-1014, OOMPAH-1015\n3. **Terminal Tasks (Done):** OOMPAH-1003, OOMPAH-1007\n\
    4. **Terminal Tasks (Archived):** OOMPAH-1016 through OOMPAH-1027\n\n**Key Observations:**\n\
    \n- OOMPAH-1015 and its duplicates (OOMPAH-1016\u20131027) address a different\
    \ error from `backend:terminal_audit_enforcement` (\"pre_recovery_finalization_metadata_malformed\"\
    ), not the orchestrator timeout issue\n- All similar backend/error_watcher tasks\
    \ are in terminal states\n- No active (Open) task in the corpus matches the \"\
    Pre-provider contributor evidence exceeded its bounded task-authority deadline\"\
    \ error message\n- The corpus confirms 726 similarity candidates total, with 29\
    \ included; all in terminal or current states\n\n**Verdict:**\n\n---\n\nFocus\
    \ handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\nMatches:\
    \ none\n\nEvidence: The supplied task corpus contains no active duplicate of OOMPAH-1315.\
    \ While the corpus includes 29 peer candidates with similarity overlap (particularly\
    \ OOMPAH-1015 and related backend/error_watcher recovery tasks), all of these\
    \ are in terminal states (Merged, Done, or Archived). OOMPAH-1315's specific error\
    \ signature\u2014\"Pre-provider contributor evidence exceeded its bounded task-authority\
    \ deadline\"\u2014does not appear in any active or hist"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: null
oompah.work_contributors:
  runs:
  - run_id: dfc0f08cdf2542bb84bcf5a70fcbe89c--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1315
    source_sha: 2da1c8073e0617b21959af89a4443b9f50c9a1d7
    completed_at: '2026-08-21T04:00:57.160555+00:00'
  - run_id: 3a98a0024f4347bfa8ec762237f9d14c--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1315
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1620
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1620
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1620
    cost_usd: 0.0
    recorded_at: '2026-08-21T04:00:57.142062+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1315
  base_branch: main
  base_sha: 859aa8a5a9fcf82063f312f6d16f8eb4ae288631
  head_sha: 0b42e47165b77f737eff0db236eef8303e7cd00f
  submitted_at: '2026-08-21T08:25:36.685440+00:00'
  updated_at: '2026-08-21T08:25:36.685440+00:00'
oompah.work_branch: OOMPAH-1315
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-eac61e1fcd70
    project_id: proj-14849f1b
    task_id: OOMPAH-1315
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b7e0770b7810d029fecf8a25d1d12d8e4e65fd288725edd730734c7f1fb2760f
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Superseded during recovery cleanup. The underlying contributor-evidence/worker-dispatch
      incident is already fixed on main: persistence uses the 60-second configured
      bound, expected bounded retirement and pre-request worker failures are below
      error-intake severity, and provider-retirement behavior has regression coverage.
      This duplicate auto-filed task must not consume integration capacity or resurrect
      its stale branch.'
    created_at: '2026-08-27T03:55:45.831362+00:00'
    selected_ref: 0b42e47165b77f737eff0db236eef8303e7cd00f
    selected_sha: 0b42e47165b77f737eff0db236eef8303e7cd00f
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1315
    target_state: Archived
    evidence_fingerprint: b7e0770b7810d029fecf8a25d1d12d8e4e65fd288725edd730734c7f1fb2760f
    workflow_revision: null
    selected_ref: 0b42e47165b77f737eff0db236eef8303e7cd00f
    selected_sha: 0b42e47165b77f737eff0db236eef8303e7cd00f
    landing_revision: null
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-27T03:55:56.668456+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1195 identifier=OOMPAH-1195 run_id=ab79167446334859bc98d8c203215877 timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1195 identifier=OOMPAH-1195 run_id=ab79167446334859bc98d8c203215877 timeout_seconds=5.0

### Expected Behavior
The operation in `backend:orchestrator` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Acceptance Criteria
- The error from `backend:orchestrator` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: proj-14849f1b
- tracker: provenanceguardedtracker
- tracker_kind: provenanceguardedtracker
- fingerprint: d170ee1a02290d55
- dedup_fingerprint: d170ee1a02290d55

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 04:00
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 04:00
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 04:00
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.6K out [1.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 50s
- Log: OOMPAH-1315__20260821T040029Z.jsonl
---
author: oompah
created: 2026-08-21 08:11
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 08:14
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 08:16
---
**Understanding & Plan**

The error 'Pre-provider contributor evidence exceeded its bounded task-authority deadline' with a 5-second timeout suggests a timeout issue in the backend orchestrator when processing contributor evidence before provider operations.

**Investigation Plan:**
1. Search codebase for the error message to locate where it's generated
2. Understand the context: what is 'pre-provider contributor evidence' and 'task-authority deadline'
3. Identify the root cause: Is the 5s timeout too short? Is there a performance issue? Is this a known/acceptable failure?
4. Implement fix: either increase timeout, optimize performance, or add graceful error handling
5. Verify no regressions in error_watcher functionality

Starting exploration now.
---
author: oompah
created: 2026-08-21 08:21
---
**Discovery: Root Cause Identified**

Found the error in `oompah/orchestrator.py` line 58066-58083. The issue:

1. **Location**: Pre-provider contributor evidence persistence timeout (writing task metadata to tracker)
2. **Timeout**: Defaults to ~5 seconds (derived from control_timeout and termination_timeout)
3. **Configured default**: Can be set via `OOMPAH_CONTRIBUTOR_EVIDENCE_PERSIST_TIMEOUT_SECONDS` (defaults to 30.0 seconds)
4. **Current behavior**: Logs at ERROR level → error_watcher picks it up → auto-files a task
5. **Actual behavior**: This is a HANDLED graceful failure - the operation is retried (line 58084-58090)

**The Problem**: This timeout is expected/recoverable, but logging at ERROR level treats it as a critical unhandled error.

**The Fix**: Change log level from ERROR to WARNING since:
- The failure is caught and handled gracefully
- The operation is retried automatically
- This is an operational condition, not a critical failure
- Will prevent error_watcher from filing duplicate tasks
---
author: oompah
created: 2026-08-21 08:25
---
**Implementation Complete**

Changed the pre-provider contributor evidence timeout log from ERROR to WARNING level in `oompah/orchestrator.py` line 58066.

**What was changed:**
- `logger.error()` → `logger.warning()` when contributor evidence persistence times out
- Structured logging context preserved (still logs all diagnostic information via 'extra' dict)

**Why this fixes the issue:**
- This timeout is a handled, graceful failure (operation is retried automatically)
- ERROR-level logs trigger error_watcher task creation
- WARNING-level logs do not trigger error_watcher
- Real ERROR conditions continue to be tracked properly

**Verification:**
✓ test_provider_retirement.py: 21 tests passed
✓ test_error_watcher.py: 124 tests passed  
✓ test_error_watcher_orchestrator.py: 13 tests passed

All related test suites pass with the change. The fix is minimal and surgical - only the log level changes, all other behavior remains identical.
---
author: oompah
created: 2026-08-21 08:25
---
Fixed pre-provider contributor evidence timeout error reporting by downgrading log level from ERROR to WARNING. This timeout is a handled graceful failure that was incorrectly being reported as a critical error by error_watcher. The fix prevents duplicate task creation during normal operation while preserving diagnostic information and error tracking functionality.
---
author: oompah
created: 2026-08-27 03:55
---
Override by oompah-cli: terminal transition to Archived applied by project owner.

Reason: Superseded during recovery cleanup. The underlying contributor-evidence/worker-dispatch incident is already fixed on main: persistence uses the 60-second configured bound, expected bounded retirement and pre-request worker failures are below error-intake severity, and provider-retirement behavior has regression coverage. This duplicate auto-filed task must not consume integration capacity or resurrect its stale branch.
---
author: oompah
created: 2026-08-27 03:56
---
Superseded during recovery cleanup. The underlying contributor-evidence/worker-dispatch incident is already fixed on main: persistence uses the 60-second configured bound, expected bounded retirement and pre-request worker failures are below error-intake severity, and provider-retirement behavior has regression coverage. This duplicate auto-filed task must not consume integration capacity or resurrect its stale branch.
---
<!-- COMMENTS:END -->
