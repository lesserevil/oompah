---
id: OOMPAH-1278
type: bug
status: In Progress
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1206 identifier=OOMPAH-1206 run_id=492b9a9720f6490dbdbde0e0652e76a2
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-20T22:48:41.811265Z'
updated_at: '2026-08-21T07:05:48.822001Z'
work_branch: OOMPAH-1278
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
  task_fingerprint: 554db1fbf5f28117d5dce92266d88b1d70fddc2894ccb1068c4a611fc42a2136
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-21T02:46:55.163850+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-1278 reports a distinct error pattern (\"Pre-provider\
    \ contributor evidence exceeded its bounded task-authority deadline\") not present\
    \ in the corpus. The closest reviewed tasks are OOMPAH-1015 (canonical backend\
    \ error incident, but for different error class) and OOMPAH-1000\u20131014 (orchestrator/terminal-audit\
    \ handling, but unrelated root causes). All 29 reviewed similarity candidates\
    \ address different failure modes (metadata validation, epic workflow, publication\
    \ authority) and no active task matches this contributor-evidence timeout.\nI'll\
    \ analyze whether OOMPAH-1278 is a duplicate of an existing task by examining\
    \ the error message and comparing it with the task corpus.\n\n**Analysis:**\n\n\
    The current task OOMPAH-1278 reports:\n- **Error**: \"Pre-provider contributor\
    \ evidence exceeded its bounded task-authority deadline\"\n- **Backend**: `backend:orchestrator`\n\
    - **Timeout**: 5.0 seconds\n- **Auto-filed by**: `error_watcher`\n- **Status**:\
    \ Open\n\nReviewing the supplied task corpus for active (non-terminal) tasks:\n\
    \nThe task corpus includes 29 similarity candidates, primarily focused on:\n1.\
    \ **Terminal audit enforcement errors** (OOMPAH-1015+): These report \"pre_recovery_finalization_metadata_malformed\"\
    \ errors\u2014a different error class entirely\n2. **Workflow/orchestrator systematic\
    \ repairs** (OOMPAH-1000\u20131014): These address epic handling, workflow admission,\
    \ terminal audit lifecycle, and publication\u2014but with different root causes\
    \ than contributor-evidence timeouts\n3. **Other infrastructure tasks**: No matches\
    \ for \"Pre-provider contributor evidence\" timeout failures\n\nAll reviewed tasks\
    \ with matching prefixes (terminal_audit_enforcement, backend:orchestrator) are\
    \ either:\n- **Merged/Done**: OOMPAH-1000\u20131014 (terminal audit handling,\
    \ workflow management)\n- **Archived**: OOMPAH-1016\u20131027 (startup-flood duplicates\
    \ of OOMPAH-1015, but for metadata_malformed errors)\n\n**Key Differences:**\n\
    - OOMPAH-1278 reports a unique timeout error in contributor evidence processing\
    \ with a 5.0-second deadline\n- The referenced OOMPAH-1206 in the error message\
    \ is embedded in the error text (not a parent task) and does not appear in the\
    \ provided corpus\n- No active task describes timeout failures in \"task-authority\"\
    \ processing for contributor evidence\n\n---\n\nFocus handoff: duplicate_detector\n\
    \nDuplicate preflight verdict: no_duplicate\n\nMatches: none\n\nEvidence: OOMPAH-1278\
    \ reports a distinct error pattern (\"Pre-provider contributor evidence exceeded\
    \ its bounded task-authority deadline\") not present in the corpus. The closest\
    \ reviewed tasks are"
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
  - run_id: 642d4b1003084628bc91263b5a53de8c--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1278
    source_sha: 2da1c8073e0617b21959af89a4443b9f50c9a1d7
    completed_at: '2026-08-21T02:46:55.187034+00:00'
  - run_id: 6233c678a6514078be3094b13b6acff7--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1278
    source_sha: 65e92b0fd75a91e4f845adea4765ae3e57670b6d
    completed_at: '2026-08-21T07:05:42.877190+00:00'
oompah.task_costs:
  total_input_tokens: 364
  total_output_tokens: 11399
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 364
      output_tokens: 11399
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2057
    cost_usd: 0.0
    recorded_at: '2026-08-21T02:46:55.161888+00:00'
  - profile: default
    model: haiku
    input_tokens: 354
    output_tokens: 9342
    cost_usd: 0.0
    recorded_at: '2026-08-21T07:05:42.862657+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1278
  base_branch: main
  base_sha: 859aa8a5a9fcf82063f312f6d16f8eb4ae288631
  head_sha: 65e92b0fd75a91e4f845adea4765ae3e57670b6d
  submitted_at: '2026-08-21T07:04:01.945647+00:00'
  updated_at: '2026-08-21T07:04:01.945647+00:00'
oompah.work_branch: OOMPAH-1278
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1206 identifier=OOMPAH-1206 run_id=492b9a9720f6490dbdbde0e0652e76a2 timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1206 identifier=OOMPAH-1206 run_id=492b9a9720f6490dbdbde0e0652e76a2 timeout_seconds=5.0

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
- fingerprint: 092b87d2970f486c
- dedup_fingerprint: 092b87d2970f486c

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 02:45
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 02:45
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 02:47
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.1K out [2.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 23s
- Log: OOMPAH-1278__20260821T024603Z.jsonl
---
author: oompah
created: 2026-08-21 06:48
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 06:49
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 06:50
---
**Understanding & Plan**

The issue reports a timeout error in backend:orchestrator when processing evidence with a 5-second deadline. The error 'Pre-provider contributor evidence exceeded its bounded task-authority deadline' is being auto-filed by error_watcher during normal operations.

**Approach:**
1. Locate the backend:orchestrator code and error_watcher implementation
2. Understand where this specific error is raised and why
3. Find the 5-second timeout configuration and assess if it's appropriate
4. Determine if the issue is: (a) timeout is too short, (b) operation needs optimization, (c) error needs graceful handling
5. Implement the fix and test to ensure error_watcher no longer triggers
6. Verify no regression in other error handling

**Searching for:** 'Pre-provider contributor evidence', task-authority, backend:orchestrator, error_watcher
---
author: oompah
created: 2026-08-21 06:55
---
**Discovery: Root Cause Found**

Located the error in `oompah/orchestrator.py` at line 58066-58083.

**Issue:** When persisting contributor evidence (metadata writes to tracker), if the operation exceeds the bounded task-authority deadline (5 seconds), a TimeoutError is caught and logged with `logger.error()`. This error log triggers error_watcher, which files it as a bug.

**Root Cause:** The timeout is being logged as an ERROR when it should be logged as a WARNING. The error is handled gracefully:
- The operation is retried on the next cycle
- An appropriate error message is returned
- No data is lost or corrupted

**Parallel Pattern:** The CancelledError path (line 58102) handles a similar scenario with `logger.warning()` instead of `logger.error()`, which is the correct approach.

**Fix:** Change `logger.error()` to `logger.warning()` on line 58066 so error_watcher is not triggered for this transient, handled condition.
---
author: oompah
created: 2026-08-21 07:01
---
**Implementation: Fixed Timeout Logging Level**

Changed line 58066 in `oompah/orchestrator.py` from `logger.error()` to `logger.warning()`.

**Rationale:** The contributor evidence persistence timeout is a transient, handled condition:
- The operation is retried on the next orchestration cycle
- An appropriate error message is returned to the caller
- No data is lost or corrupted
- The CancelledError path uses logger.warning() for a similar scenario

By logging as WARNING instead of ERROR, error_watcher will no longer be triggered for this normal operational condition, eliminating false-positive bug reports.

**Tests:** All 21 provider_retirement tests and 381 orchestrator_handler tests pass.
---
author: oompah
created: 2026-08-21 07:03
---
**Verification: Tests Passed**

✅ Provider Retirement Tests: 21/21 PASSED (17.01s)
✅ Orchestrator Handler Tests: 381/381 PASSED (4m 24s)

**Change Summary:**
- File: oompah/orchestrator.py, line 58066
- Changed: logger.error() → logger.warning()
- Reason: Pre-provider evidence timeout is a transient, handled condition
- Impact: error_watcher will no longer file false-positive bug reports

The fix is minimal, focused, and maintains full test coverage.
---
author: oompah
created: 2026-08-21 07:04
---
Changed pre-provider contributor evidence timeout logging from error to warning. This prevents error_watcher from filing false-positive bug reports for transient, handled timeout conditions. All tests pass.
---
author: oompah
created: 2026-08-21 07:05
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 89, Tool calls: 43
- Tokens: 354 in / 9.3K out [9.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 17m 5s
- Log: OOMPAH-1278__20260821T064955Z.jsonl
---
<!-- COMMENTS:END -->
