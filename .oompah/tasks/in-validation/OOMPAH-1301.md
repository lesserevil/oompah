---
id: OOMPAH-1301
type: bug
status: In Validation
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1219 identifier=OOMPAH-1219 run_id=7cd1a29615894245aa1d0e934206fd4f
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-21T00:14:39.219900Z'
updated_at: '2026-08-26T04:15:29.242820Z'
work_branch: OOMPAH-1301
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/923
review_number: '923'
review_head: 669845780ab945d5558aefebf1375fb86366dfc0
merged_at: null
oompah.lifecycle_revision: 7
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
  task_fingerprint: a155a29f81cf5ec93802ac14cee5e4bbde743f4b40f428488ed94e987c06d8c0
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-21T03:39:17.820089+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Reviewed 29 included candidates and found no active task\
    \ describing the same `backend:orchestrator` pre-provider contributor deadline-exceeded\
    \ error. The highest-scoring similar tasks (OOMPAH-1000\u20131027) address different\
    \ components (terminal-audit enforcement, workflow scheduling, epic handling)\
    \ or are already in terminal states (Merged/Done/Archived). OOMPAH-1301 remains\
    \ the sole active task for this specific orchestrator error signature.\n# Duplicate\
    \ Screening Analysis\n\nI'm reviewing the task corpus to determine whether OOMPAH-1301\
    \ is a duplicate of an existing task.\n\n## Current Task Summary\n\n**OOMPAH-1301**\
    \ is an auto-filed error report from `backend:orchestrator`:\n- Error: \"Pre-provider\
    \ contributor evidence exceeded its bounded task-authority deadline\"\n- Fingerprint:\
    \ 7e93697bb93af5b5\n- Source: error_watcher auto-filing\n- Status: Open\n\n##\
    \ Corpus Review\n\nThe provided corpus includes 29 similarity-candidate tasks.\
    \ I've examined each:\n\n**Terminal-state tasks (excluded from duplicate consideration):**\n\
    - OOMPAH-1 (Archived)\n- OOMPAH-10 (Archived)\n- OOMPAH-1000 through OOMPAH-1027\
    \ (Merged/Done) \u2014 These are workflow, terminal-audit, and epic-related fixes\n\
    - OOMPAH-164 (Archived)\n\n**Critical distinction:** Tasks OOMPAH-1015\u20131027\
    \ are about `backend:terminal_audit_enforcement` errors (specifically \"pre_recovery_finalization_metadata_malformed\"\
    ), NOT `backend:orchestrator` errors. They are also all in terminal states (Merged/Archived).\n\
    \n**Active tasks:** Only OOMPAH-1301 itself is Open.\n\n## Verdict\n\nNo active\
    \ (non-terminal) tasks in the corpus describe the same `backend:orchestrator`\
    \ deadline-exceeded error. The closest related tasks are all completed and address\
    \ different backend components (terminal-audit vs. orchestrator) or different\
    \ error types.\n\nThe corpus notes 697 of 726 similar candidates were omitted\
    \ due to byte/selection limits, so a true duplicate could theoretically exist\
    \ outside the provided sample. However, based on the authoritative corpus supplied,\
    \ I find no duplicate among the reviewed tasks.\n\n---\n\nFocus handoff: duplicate_detector\n\
    \nDuplicate preflight verdict: no_duplicate\n\nMatches: none\n\nEvidence: Reviewed\
    \ 29 included candidates and found no active task describing the same `backend:orchestrator`\
    \ pre-provider contributor deadline-exceeded error. The highest-scoring similar\
    \ tasks (OOMPAH-1000\u20131027) address different components (terminal-audit enforcement,\
    \ workflow scheduling, epic handling) o"
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
  - run_id: a36d2218292f4a86a8c8904155c383ee--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1301
    source_sha: 2da1c8073e0617b21959af89a4443b9f50c9a1d7
    completed_at: '2026-08-21T03:39:17.829404+00:00'
  - run_id: 380e68ea99ba42108e9b86ddcefc9dd1--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: general
    source_branch: OOMPAH-1301
    source_sha: null
    completed_at: ''
  - run_id: abc12d854fac44cda6eeb5ddefa52adf--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1301
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1559
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1559
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1559
    cost_usd: 0.0
    recorded_at: '2026-08-21T03:39:17.815063+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1301
  base_branch: main
  base_sha: a04ccf10a6e958aceb9c4fb41b04563f77c86917
  head_sha: 669845780ab945d5558aefebf1375fb86366dfc0
  submitted_at: '2026-08-21T16:31:10.855408+00:00'
  updated_at: '2026-08-26T00:05:42.326443+00:00'
oompah.work_branch: OOMPAH-1301
oompah.review_url: https://github.com/lesserevil/oompah/pull/923
oompah.review_number: '923'
oompah.target_branch: main
oompah.review_head: 669845780ab945d5558aefebf1375fb86366dfc0
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-c1c19820091a
    project_id: proj-14849f1b
    task_id: OOMPAH-1301
    digest: bd2a23f229516126f32f54257dfd3ccef80d86069ea4f29a96e9f64be35c4e25
  - version: 1
    audit_id: audit-57bb0ab6a861
    project_id: proj-14849f1b
    task_id: OOMPAH-1301
    digest: bd2a23f229516126f32f54257dfd3ccef80d86069ea4f29a96e9f64be35c4e25
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-c1c19820091a
    project_id: proj-14849f1b
    task_id: OOMPAH-1301
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: bd2a23f229516126f32f54257dfd3ccef80d86069ea4f29a96e9f64be35c4e25
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-26T04:15:22.468339+00:00'
    eligible_at: '2026-08-26T04:15:22.468339+00:00'
    selected_ref: 669845780ab945d5558aefebf1375fb86366dfc0
    selected_sha: 669845780ab945d5558aefebf1375fb86366dfc0
  - version: 1
    audit_id: audit-57bb0ab6a861
    project_id: proj-14849f1b
    task_id: OOMPAH-1301
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: bd2a23f229516126f32f54257dfd3ccef80d86069ea4f29a96e9f64be35c4e25
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-26T04:15:22.468339+00:00'
    prerequisite_audit_id: audit-c1c19820091a
    selected_ref: 669845780ab945d5558aefebf1375fb86366dfc0
    selected_sha: 669845780ab945d5558aefebf1375fb86366dfc0
  attempt_history: []
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1219 identifier=OOMPAH-1219 run_id=7cd1a29615894245aa1d0e934206fd4f timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1219 identifier=OOMPAH-1219 run_id=7cd1a29615894245aa1d0e934206fd4f timeout_seconds=5.0

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
- fingerprint: 7e93697bb93af5b5
- dedup_fingerprint: 7e93697bb93af5b5

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 03:37
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 03:37
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 03:39
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.6K out [1.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 49s
- Log: OOMPAH-1301__20260821T033830Z.jsonl
---
author: oompah
created: 2026-08-21 07:38
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 07:41
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 07:41
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: interrupted, Duration: 3m 17s
- Log: OOMPAH-1301__20260821T074122Z.jsonl
---
author: oompah
created: 2026-08-21 16:14
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 16:14
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 16:16
---
**Understanding & Plan**

The error 'Pre-provider contributor evidence exceeded its bounded task-authority deadline' indicates that an operation in the backend:orchestrator exceeded a 5-second timeout while processing task-authority evidence. 

**Approach:**
1. Locate the error message in the codebase
2. Identify where the timeout is enforced
3. Determine if the operation legitimately needs more time, or if there's inefficiency
4. Either increase the timeout appropriately, optimize the code, or add graceful error handling
5. Verify no regression in error_watcher reporting

Starting codebase exploration now.
---
author: oompah
created: 2026-08-21 16:21
---
**Discovery: Root Cause Identified**

Found the issue in oompah/orchestrator.py at line 58067 in the `_stage_work_contributor_launch()` function.

**Root Cause:**
- A TimeoutError occurs when persisting contributor evidence to the tracker takes longer than the configured timeout (5 seconds by default)
- The timeout handler logs this at ERROR level, which triggers error_watcher to auto-file a task
- However, the function returns a graceful error message and retries the operation, so this is expected behavior, not a bug

**The Problem:**
The `logger.error()` call at line 58066-58073 is logging at ERROR level, which error_watcher interprets as a critical failure and files automatically. However:
- The operation gracefully degrades with a clear error message
- The operation is retried (indicated by 'retired for retry' in the return message)  
- This is similar to other expected timeout scenarios in the codebase that log at WARNING instead

**Solution:**
Change the log level from ERROR to WARNING at line 58066, following the pattern used elsewhere in oompah for expected transient failures. This prevents error_watcher from auto-filing duplicate tasks while still logging the timeout for diagnostics.
---
author: oompah
created: 2026-08-21 16:29
---
**Implementation: Fixed Log Level**

Changed the timeout handler in `_stage_work_contributor_launch()` to log at WARNING level instead of ERROR level.

**Changes Made:**
- File: oompah/orchestrator.py, line 58066
- Changed: `logger.error()` → `logger.warning()`

**Rationale:**
- The contributor evidence timeout is a transient failure that is handled gracefully and retried
- Logging at ERROR triggers error_watcher to auto-file duplicate bug tasks on each occurrence
- This pattern follows the existing convention in oompah for expected transient failures (see test_timeout_logs_warning_not_error in test_orchestrator_handlers.py)

**Tests Added:**
- New test: `test_pre_provider_evidence_timeout_logs_warning_not_error` in tests/test_provider_retirement.py
- Verifies timeout is logged at WARNING, not ERROR
- Ensures error_watcher won't be triggered by this transient failure
- All 22 provider retirement tests pass
---
author: oompah
created: 2026-08-21 16:30
---
**Verification: Tests Pass, Code Committed**

All tests pass successfully:
- test_pre_provider_evidence_timeout_logs_warning_not_error: ✓ PASSED
- test_pre_provider_evidence_timeout_releases_task_authority: ✓ PASSED
- All 22 tests in test_provider_retirement.py: ✓ PASSED
- All 124 tests in test_error_watcher.py: ✓ PASSED
- Timeout logging pattern tests: ✓ PASSED

**Code Changes Committed:**
- Branch: OOMPAH-1301
- Commit: 669845780
- Files modified: oompah/orchestrator.py, tests/test_provider_retirement.py

**Result:**
The error 'Pre-provider contributor evidence exceeded its bounded task-authority deadline' will no longer trigger error_watcher task creation. It will be logged at WARNING level as a transient failure that is handled gracefully with automatic retry, preventing the duplicate task auto-filing issue.

Ready for integration.
---
author: oompah
created: 2026-08-21 16:31
---
Fixed contributor evidence timeout log level to prevent error_watcher task creation
---
author: oompah
created: 2026-08-25 22:41
---
Branch quality gate passed for `669845780ab945d5558aefebf1375fb86366dfc0` using `make test` in 192.8s. Review creation may proceed.
---
author: oompah
created: 2026-08-26 03:14
---
Branch quality gate passed for `669845780ab945d5558aefebf1375fb86366dfc0` using `make test` in 191.1s. Review creation may proceed.
---
author: oompah
created: 2026-08-26 04:15
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
<!-- COMMENTS:END -->
