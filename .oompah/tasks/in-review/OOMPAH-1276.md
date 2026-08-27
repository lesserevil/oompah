---
id: OOMPAH-1276
type: bug
status: In Review
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1201 identifier=OOMPAH-1201 run_id=0d5bd79e400544d7974de22a21fbaf7b
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-20T22:45:59.311385Z'
updated_at: '2026-08-27T03:33:36.276564Z'
work_branch: OOMPAH-1276
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/939
review_number: '939'
review_head: e8c4d3ff807839faeab188a72ac5eedb8345cd35
merged_at: null
oompah.lifecycle_revision: 5
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
  task_fingerprint: 430399d3da61c9bc3e20c6bb6ce0d7d22c8322405a02fa5f44b8a0725c9f7ffb
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-21T11:26:17.886922+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Reviewed 28 similarity candidates; all are in terminal\
    \ states (Merged, Done, Archived). OOMPAH-1015 through OOMPAH-1027 describe different\
    \ backend errors (terminal-audit enforcement metadata issues) and are already\
    \ resolved. OOMPAH-1276's unique timeout error from backend:orchestrator has no\
    \ matching active task in the corpus. The issue remains genuinely Open and unresolved.\n\
    # Duplicate Screening for OOMPAH-1276\n\nI'm examining whether OOMPAH-1276 is\
    \ a duplicate of an existing task in the project corpus.\n\n## Analysis\n\n**Current\
    \ Task (OOMPAH-1276):**\n- Status: Open\n- Error: \"Pre-provider contributor evidence\
    \ exceeded its bounded task-authority deadline\" from backend:orchestrator\n-\
    \ Timeout: 5.0 seconds\n- Auto-filed by error_watcher\n- Fingerprint: 190362be30d13123\n\
    \n**Corpus Review:**\n\nI've examined all 28 similarity-candidate tasks provided\
    \ in the corpus. Key findings:\n\n1. **Terminal-state tasks (excluded):** All\
    \ reviewed candidates are in terminal states (Merged, Done, or Archived), which\
    \ per the screening protocol cannot be duplicate targets.\n\n2. **Error type mismatch:**\
    \ The similar-looking tasks in the corpus (OOMPAH-1015 through OOMPAH-1027) describe\
    \ different errors:\n   - OOMPAH-1015 through OOMPAH-1027: \"terminal-audit enforcement:\
    \ pre_recovery_finalization_metadata_malformed\" errors\n   - OOMPAH-1015 is explicitly\
    \ the canonical incident for a startup-flood batch (OOMPAH-1016-1070 are archived\
    \ duplicates of it)\n\n3. **Unique error signature:** The \"Pre-provider contributor\
    \ evidence exceeded its bounded task-authority deadline\" error has a unique fingerprint\
    \ (190362be30d13123) not matching any other task in the corpus.\n\n4. **No active\
    \ duplicate:** There are no Open or In Progress tasks in the corpus that describe\
    \ this same error.\n\n---\n\nFocus handoff: duplicate_detector\n\nDuplicate preflight\
    \ verdict: no_duplicate\n\nMatches: none\n\nEvidence: Reviewed 28 similarity candidates;\
    \ all are in terminal states (Merged, Done, Archived). OOMPAH-1015 through OOMPAH-1027\
    \ describe different backend errors (terminal-audit enforcement metadata issues)\
    \ and are already resolved. OOMPAH-1276's unique timeout error from backend:orchestrator\
    \ has no matching active task in the corpus. The issue remains genuinely Open\
    \ and unresolved."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 2
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: null
oompah.work_contributors:
  runs:
  - run_id: 27379a11d8d04e598d7b2f46dc8551e7--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1276
    source_sha: null
    completed_at: ''
  - run_id: f26e1a88ac60488e8e1a9cf83aae3404--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1276
    source_sha: null
    completed_at: ''
  - run_id: 94b8a06d42e0407e8c316b88f663a044--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1276
    source_sha: 859aa8a5a9fcf82063f312f6d16f8eb4ae288631
    completed_at: '2026-08-21T11:26:17.901891+00:00'
  - run_id: a4c843f70bd947f8a995d7f7ad7ef2d7--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1276
    source_sha: e8c4d3ff807839faeab188a72ac5eedb8345cd35
    completed_at: '2026-08-21T15:08:40.217881+00:00'
oompah.task_costs:
  total_input_tokens: 388
  total_output_tokens: 15084
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 388
      output_tokens: 15084
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1384
    cost_usd: 0.0
    recorded_at: '2026-08-21T11:26:17.883839+00:00'
  - profile: default
    model: haiku
    input_tokens: 378
    output_tokens: 13700
    cost_usd: 0.0
    recorded_at: '2026-08-21T15:08:40.210552+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1276
  base_branch: main
  base_sha: f1381bd482e212196531c958b2926839431ba9ae
  head_sha: e8c4d3ff807839faeab188a72ac5eedb8345cd35
  submitted_at: '2026-08-21T15:05:50.639378+00:00'
  updated_at: '2026-08-26T17:39:28.601924+00:00'
oompah.work_branch: OOMPAH-1276
oompah.review_url: https://github.com/lesserevil/oompah/pull/939
oompah.review_number: '939'
oompah.target_branch: main
oompah.review_head: e8c4d3ff807839faeab188a72ac5eedb8345cd35
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-48add4a8369c
    project_id: proj-14849f1b
    task_id: OOMPAH-1276
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c4b3371b8e38411eaa69b549b8f8ea3ee587623534943e0afd7dc08e51e290f8
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Superseded by fixes already merged to main: production now uses a 60-second
      contributor-evidence persistence timeout, logs the expected bounded timeout
      at DEBUG, and excludes expected pre-provider retirement from error intake. The
      stale branch conflicts with newer recovery work and must not be rebased or merged.'
    created_at: '2026-08-27T03:33:33.836631+00:00'
    selected_ref: e8c4d3ff807839faeab188a72ac5eedb8345cd35
    selected_sha: e8c4d3ff807839faeab188a72ac5eedb8345cd35
    applied: false
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1201 identifier=OOMPAH-1201 run_id=0d5bd79e400544d7974de22a21fbaf7b timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1201 identifier=OOMPAH-1201 run_id=0d5bd79e400544d7974de22a21fbaf7b timeout_seconds=5.0

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
- fingerprint: 190362be30d13123
- dedup_fingerprint: 190362be30d13123

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 02:38
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 02:39
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 02:39
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: interrupted, Duration: 45s
- Log: OOMPAH-1276__20260821T023929Z.jsonl
---
author: oompah
created: 2026-08-21 06:13
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 06:13
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 06:14
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 57s
- Log: OOMPAH-1276__20260821T061401Z.jsonl
---
author: oompah
created: 2026-08-21 11:24
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 11:24
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 11:26
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.4K out [1.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 38s
- Log: OOMPAH-1276__20260821T112524Z.jsonl
---
author: oompah
created: 2026-08-21 14:42
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 14:43
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 14:44
---
**Understanding & Plan:**

Issue: backend:orchestrator throws 'Pre-provider contributor evidence exceeded its bounded task-authority deadline' error with a 5.0s timeout when processing proj-14849f1b.

Interpretation: This appears to be a timeout error in the orchestrator when gathering contributor evidence before processing a provider. The 5-second deadline is being exceeded, and the error is not being handled gracefully (error_watcher detects it).

Planned approach:
1. Explore the codebase to find backend/orchestrator code
2. Locate the 'Pre-provider contributor evidence' logic
3. Find where the task-authority deadline is enforced (5.0s timeout)
4. Identify why it's timing out and implement a fix (either increase timeout, optimize code, or handle gracefully)
5. Verify fix with tests and manual testing

Starting investigation now.
---
author: oompah
created: 2026-08-21 14:49
---
**Discovery:**

Found the issue in oompah/orchestrator.py around line 58067 in the `_stage_work_contributor_launch()` function.

**Root Cause:**
When recording contributor evidence (provider/model identity) before dispatch, the code attempts to persist metadata to the tracker within a bounded timeout. The timeout defaults to 5.0 seconds (based on `terminal_control_lock_timeout_seconds` config).

When the tracker adapter is slow (particularly for `provenanceguardedtracker`), the metadata write exceeds this 5-second deadline, causing a `TimeoutError` that is logged as an ERROR via `logger.error()`. This error is then picked up by error_watcher and auto-filed.

**Key Code:**
- Line 58023-58040: Timeout calculation (defaults to 5.0 seconds)
- Line 58042-58046: Timeout enforcement with `asyncio.wait_for()`
- Line 58066-58090: Error logging and handling when timeout occurs

**Issue:** The timeout is too aggressive for slow trackers. The error is being treated as critical (ERROR level) when it should be handled as a transient retry-able failure.

**Proposed Fix:**
Increase the default timeout or make it more lenient for the contributor evidence persistence, since the comment in the code explicitly states: 'A dedicated deadline lets slow tracker/state-branch evidence writes finish instead of retiring with contributor_evidence_unavailable and starving implementation dispatch. When configured it is authoritative (production raises it well above the derived control floor).'

The configuration option `contributor_evidence_persist_timeout_seconds` already exists for this purpose but may not be set in the dev environment.
---
author: oompah
created: 2026-08-21 14:58
---
**Implementation:**

Fixed the contributor evidence timeout issue by making two key changes to oompah/orchestrator.py in the `_stage_work_contributor_launch()` function:

1. **Increased default timeout fallback** (line ~58045):
   - Added a fallback minimum of 10 seconds for the contributor evidence persistence timeout when no explicit configuration is set
   - The calculation was using min(5.0s control timeout, 5.0s termination timeout / 2) = 5.0s by default
   - Now uses max(calculated_value, 10.0s) as fallback, while still respecting explicit config values
   - This allows slow tracker implementations like provenanceguardedtracker to complete their metadata writes

2. **Changed error level to warning** (line ~58073):
   - Changed logger.error() to logger.warning() for the timeout condition
   - Updated message to indicate this is a retryable failure ('; retrying')
   - This prevents error_watcher from auto-filing transient timeout conditions as critical bugs
   - The retry mechanism already handles this gracefully

**Testing:**
- Verified all existing tests pass (21 tests in test_provider_retirement.py, 32 dispatch tests)
- The existing timeout test with explicit 0.1s config still works correctly
- Changes are backward compatible - explicit config values still override the fallback
---
author: oompah
created: 2026-08-21 15:04
---
**Verification:**

✅ All tests pass:
- 21 tests in test_provider_retirement.py (focused on contributor evidence timeout scenarios)
- 32 dispatch-related tests in test_orchestrator_handlers.py
- 79 total tests across test_provider_retirement.py and test_acp_agent.py

✅ Changes verified:
- Code increases the contributor evidence timeout from 5.0s to minimum 10.0s
- Explicit config values (like 60.0s default) are still respected
- Error logging changed from ERROR to WARNING for timeout conditions
- Backward compatibility maintained - all existing tests pass without modification

✅ Fix addresses the issue:
- Pre-provider contributor evidence timeout no longer triggers error_watcher
- Slow tracker implementations have sufficient time to complete metadata writes
- Transient timeout failures are properly classified as warnings, not errors
- Retry mechanism handles the timeout gracefully

Commit: OOMPAH-1276 e8c4d3ff8
Branch pushed and ready for review.
---
author: oompah
created: 2026-08-21 15:06
---
Fixed pre-provider contributor evidence timeout issue by increasing default timeout fallback to 10 seconds and changing error logging to warning level to prevent error_watcher triggering on transient failures.
---
author: oompah
created: 2026-08-21 15:08
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 108, Tool calls: 46
- Tokens: 378 in / 13.7K out [14.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 26m 16s
- Log: OOMPAH-1276__20260821T144324Z.jsonl
---
author: oompah
created: 2026-08-26 16:38
---
Branch quality gate passed for `e8c4d3ff807839faeab188a72ac5eedb8345cd35` using `make test` in 198.5s. Review creation may proceed.
---
author: oompah
created: 2026-08-26 18:31
---
Branch quality gate passed for `e8c4d3ff807839faeab188a72ac5eedb8345cd35` using `make test` in 186.0s. Review creation may proceed.
---
<!-- COMMENTS:END -->
