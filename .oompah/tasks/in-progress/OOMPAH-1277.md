---
id: OOMPAH-1277
type: bug
status: In Progress
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1204 identifier=OOMPAH-1204 run_id=dd954c5651e849a6a9f6ef1d01e1d944
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-20T22:47:52.188773Z'
updated_at: '2026-08-24T07:16:29.857768Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.lifecycle_revision: 2
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
  task_fingerprint: ee16e84c6d41e2a66004044a815c8ffaf0b311c15e7fe14b6affd4936bd04f14
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-23T23:29:50.811307+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector

    Duplicate preflight verdict: no_duplicate

    Matches: none

    Evidence: OOMPAH-1277 shares topical similarity with completed backend and orchestrator
    tasks (OOMPAH-1000 through OOMPAH-1014), but all are in terminal states and address
    different subsystems (terminal audits, epic workflows, quality gates, ledger compatibility).
    The specific timeout error "Pre-provider contributor evidence exceeded its bounded
    task-authority deadline" does not match any active task. OOMPAH-1015 and related
    tasks address error_watcher auto-filing but for metadata malformation, not task-authority
    timeouts. This appears to be a distinct, previously-unhandled issue in the orchestrator''s
    task-authority enforcement.

    I am performing duplicate screening for OOMPAH-1277. Let me analyze the supplied
    project task corpus to determine if this issue matches any active duplicate.


    **OOMPAH-1277 Analysis:**

    - Title: Backend orchestrator error - "Pre-provider contributor evidence exceeded
    its bounded task-authority deadline"

    - Status: **Open** (active)

    - Type: bug

    - Error: Task-authority deadline timeout (5.0 seconds)

    - Fingerprint: b79233367fd31330

    - Auto-filed by error_watcher from proj-14849f1b


    **Corpus Review:**


    The corpus includes 28 similarity candidates. I''ve reviewed all of them:


    **Terminal-State Tasks (excluded per screening rules):**

    - OOMPAH-1000 through OOMPAH-1027 (Merged/Done): Various workflow, terminal audit,
    epic, and quality-gate fixes

    - OOMPAH-1015 (Merged): Similar error class - "terminal-audit enforcement: pre_recovery_finalization_metadata_malformed"
    but different backend and error type

    - OOMPAH-1016 through OOMPAH-1027 (Archived): Duplicate symptoms from startup
    flood, already consolidated

    - OOMPAH-10, OOMPAH-1, OOMPAH-270 (Archived): Historical completed work


    **Result:**


    All 28 similarity candidates are in terminal states (Done, Merged, or Archived).
    No active, non-terminal peer task matches OOMPAH-1277.


    ---


    Focus handoff: duplicate_detector


    Duplicate preflight verdict: no_duplicate


    Matches: none


    Evidence: OOMPAH-1277 shares topical similarity with completed backend and orchestrator
    tasks (OOMPAH-1000 through OOMPAH-1014), but all are in terminal states and address
    different subsystems (terminal audits, epic workflows, quality gates, ledger compatibility).
    The specific timeout error "Pre-provider contributor evidence exceeded its bounded
    task-authority deadline" does not match any active task. OOMPAH-1015 and related
    tasks address error_watcher auto-filing but for metadata malformation, not task-authority
    timeouts. This appears to be a distinct, previously-unhandled issue in the orchestrator''s
    task-authority enforcement.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 2
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: c8b83dd4-5e45-41e6-a87f-8767ca1a6387
oompah.work_contributors:
  runs:
  - run_id: 422c025706e544418acee6fcda3fd29a--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1277
    source_sha: null
    completed_at: ''
  - run_id: d242361bf0b745bd92c017c90d6d6f82--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1277
    source_sha: null
    completed_at: ''
  - run_id: a0e5ba934a6241609ba601e9993702a4--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1277
    source_sha: null
    completed_at: ''
  - run_id: 8688882a6aa14ab88954a6002d460485--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1277
    source_sha: 8c81b69c713e9bb6a1da8906b7e637f1ea6a1696
    completed_at: '2026-08-23T23:29:50.839063+00:00'
  - run_id: 195329f0644a498ba92b6993a96ee934--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1277
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 2185
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 2185
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2185
    cost_usd: 0.0
    recorded_at: '2026-08-23T23:29:50.810526+00:00'
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1204 identifier=OOMPAH-1204 run_id=dd954c5651e849a6a9f6ef1d01e1d944 timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1204 identifier=OOMPAH-1204 run_id=dd954c5651e849a6a9f6ef1d01e1d944 timeout_seconds=5.0

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
- fingerprint: b79233367fd31330
- dedup_fingerprint: b79233367fd31330

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 02:44
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 02:45
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 02:45
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: interrupted, Duration: 33s
- Log: OOMPAH-1277__20260821T024506Z.jsonl
---
author: oompah
created: 2026-08-21 06:17
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 06:17
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 11:03
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 11:04
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 11:05
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 2m 39s
- Log: OOMPAH-1277__20260821T110439Z.jsonl
---
author: oompah
created: 2026-08-23 23:27
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-23 23:28
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-23 23:29
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.2K out [2.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 12s
- Log: OOMPAH-1277__20260823T232820Z.jsonl
---
author: oompah
created: 2026-08-24 06:59
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-24 07:00
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-24 07:01
---
**Understanding & Plan:**

This is a backend:orchestrator timeout issue where a pre-provider contributor evidence operation exceeds its 5-second deadline. The error message indicates a task-authority deadline being exceeded, and this should either be fixed to complete in time or handled gracefully so error_watcher doesn't treat it as an unexpected failure.

**Approach:**
1. Locate backend:orchestrator code and understand the timeout mechanism
2. Find where 'Pre-provider contributor evidence' is being computed
3. Identify why it's timing out (5 seconds may be insufficient)
4. Either optimize the operation or increase the timeout/handle gracefully
5. Verify the fix with tests

Currently exploring the codebase.
---
author: oompah
created: 2026-08-24 07:10
---
**Discovery:**

Found the issue in oompah/orchestrator.py around line 58070. The contributor evidence persistence operation is timing out at 5.0 seconds instead of using the configured 60-second timeout.

**Root Cause:**
The timeout calculation flow is:
1. Lines 58005-58029: Calculate persistence_timeout based on control_lock_timeout (5.0s default)
2. Lines 58035-58043: If contributor_evidence_persist_timeout_seconds is configured, use it instead

The error shows timeout=5.0s, which is the fallback calculated value, not the configured 60-second value. This means getattr at line 58035 is returning None, so the configured timeout isn't being used.

The persistence operation is waiting too long and exceeding the 5-second deadline, causing a warning log that error_watcher is catching.

**Solution:**
Change the code to use the configured timeout value (60.0s) as the primary source instead of calculating a fallback first. This ensures slow tracker writes don't exceed an overly-tight deadline.
---
author: oompah
created: 2026-08-24 07:15
---
**Implementation:**

Fixed the issue in oompah/orchestrator.py at lines 58035-58043.

**The Problem:**
The code was calculating a tight 5-second timeout as a fallback, then only using the configured 60-second timeout if it was explicitly not None. This meant if getattr returned the default None, the 5-second timeout was used, causing persistence operations to fail.

**The Solution:**
Changed getattr to use 60.0 as the default instead of None, ensuring the configured timeout is always used. This gives slow tracker/state-branch writes sufficient time to complete without exceeding the deadline.

**Testing:**
- All 21 provider_retirement tests pass
- All 144 provider_retirement + epic_rebase_state tests pass
- Specific timeout test still validates the behavior
---
author: oompah
created: 2026-08-24 07:16
---
**Verification:**

All tests pass:
✓ test_pre_provider_evidence_timeout_releases_task_authority - validates timeout behavior
✓ 21/21 provider_retirement tests
✓ 144/144 provider_retirement + epic_rebase_state tests  
✓ 13/13 error_watcher_orchestrator tests

**Result:**
The contributor evidence persistence timeout now uses the configured 60-second default instead of a calculated 5-second fallback. This resolves the timeout errors that were being auto-filed as tasks by error_watcher during normal operations.

Changes committed and pushed to OOMPAH-1277 branch.
---
<!-- COMMENTS:END -->
