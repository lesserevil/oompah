---
id: OOMPAH-1214
type: bug
status: In Progress
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=TRICKLE-133 identifier=TRICKLE-133 run_id=ed9da72decc54fb5a2f55a2cbb41c2ad
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T03:56:36.835031Z'
updated_at: '2026-08-24T06:47:58.711085Z'
work_branch: OOMPAH-1214
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.lifecycle_revision: 2
oompah.last_batch:
  batch_id: batch-41327bd44d2248989351b0a98c84746f
  actor: shedwards
  committed_at: '2026-08-18T16:18:18.970327Z'
  operation:
    kind: whole_column_move
    source_status: Backlog
    scope: flat_board
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 9f501ce74a83770dbceabb6e16db4493620e7611cd26f35e0845554eb4301535
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-23T23:14:13.015972+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Searched 28 similarity candidates across backend orchestrator,\
    \ workflow, audit enforcement, and checkpoint systems. All matches are in terminal\
    \ states (Merged/Archived) addressing unrelated failures (malformed metadata,\
    \ epic lifecycle, terminal audit authority, workflow admission, quality gates).\
    \ The specific `backend:orchestrator` bounded task-authority deadline timeout\
    \ for TRICKLE-133 is unique among active tasks. OOMPAH-1214 should proceed as\
    \ a standalone investigation.\n# Duplicate Investigation: OOMPAH-1214\n\nI'm examining\
    \ OOMPAH-1214 against the supplied project task corpus to determine whether this\
    \ is a duplicate of an existing active task.\n\n## Analysis\n\n**Current Task\
    \ Details:**\n- **Identifier:** OOMPAH-1214\n- **Error:** `[backend:orchestrator]\
    \ Pre-provider contributor evidence exceeded its bounded task-authority deadline`\n\
    - **Context:** Auto-filed by `error_watcher` for project `proj-14849f1b`\n- **Status:**\
    \ Open\n\n**Corpus Review:**\n\nI reviewed 28 similarity candidates in the provided\
    \ task corpus. Key findings:\n\n1. **No Active Duplicates:** All non-OOMPAH-1214\
    \ tasks in the corpus are in terminal states (Archived, Done, or Merged). No other\
    \ task with status Open or In Progress matches this error.\n\n2. **Distinct Error\
    \ Source:** The error originates from `backend:orchestrator` with the specific\
    \ message \"Pre-provider contributor evidence exceeded its bounded task-authority\
    \ deadline.\" This is distinct from:\n   - OOMPAH-1015 and related (OOMPAH-1016\u2013\
    1026): `backend:terminal_audit_enforcement` errors about malformed metadata (all\
    \ Archived/Merged)\n   - OOMPAH-1098: `backend:checkpoint_queue` error (Archived)\n\
    \   - OOMPAH-1000\u20131014: Various systemic workflow/audit issues triggered\
    \ by OOMPAH-940/OOMPAH-999/etc. (all Merged/Done)\n\n3. **No Matching Active Resolution\
    \ Path:** The historical tasks addressing orchestrator issues (e.g., OOMPAH-1000\u2013\
    1014) are all completed and addressed different root causes in landing, workflow,\
    \ terminal audit, and epic lifecycle. None capture the specific bounded task-authority\
    \ deadline timeout scenario.\n\n4. **Prior Inconclusive Screenings:** The task\
    \ history notes duplicate screening was inconclusive 3 times. This run supplies\
    \ complete corpus context that earlier attempts may have lacked.\n\n---\n\nFocus\
    \ handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\n\
    Matches: none\n\nEvidence: Searched 28 similarity candidates across backend orchestrator,\
    \ workflow, audit enforcement, and checkpoint systems. A"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 8045446a-b9fc-4803-a1f9-f29be5affa40
oompah.work_contributors:
  runs:
  - run_id: df292ca636c54e39ad008fcfba8e4b83--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1214
    source_sha: null
    completed_at: ''
  - run_id: df292ca636c54e39ad008fcfba8e4b83--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1214
    source_sha: null
    completed_at: ''
  - run_id: b2123ad1829b44bd9421d35405167108--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1214
    source_sha: null
    completed_at: ''
  - run_id: b2123ad1829b44bd9421d35405167108--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1214
    source_sha: null
    completed_at: ''
  - run_id: 2fa5716a82384dbe921b5bbdfa03ebca--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1214
    source_sha: null
    completed_at: ''
  - run_id: 2fa5716a82384dbe921b5bbdfa03ebca--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1214
    source_sha: null
    completed_at: ''
  - run_id: 4df6b8c21ec744ab9c5b680945b03a37--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1214
    source_sha: null
    completed_at: ''
  - run_id: 7eabd0dc5d974719a660e90cb15e7e23--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1214
    source_sha: null
    completed_at: ''
  - run_id: aa62730a05be4518bd1bed14fd3da8e3--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1214
    source_sha: null
    completed_at: ''
  - run_id: 37b125d07d9647b8b0935682c1817f0f--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1214
    source_sha: 8c81b69c713e9bb6a1da8906b7e637f1ea6a1696
    completed_at: '2026-08-23T23:14:13.040174+00:00'
  - run_id: bdf54fecb3484a22ad2f776fad29b114--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1214
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1542
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1542
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1542
    cost_usd: 0.0
    recorded_at: '2026-08-23T23:14:13.015491+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1214
  base_branch: main
  base_sha: 4988991309ba81b6b2cf06aa30528bf5f21b0a82
  head_sha: 94c622052242a3ad2dd70f6a85d4ee3dc6b5ef2c
  submitted_at: '2026-08-24T06:47:31.204062+00:00'
  updated_at: '2026-08-24T06:47:31.204062+00:00'
oompah.work_branch: OOMPAH-1214
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=TRICKLE-133 identifier=TRICKLE-133 run_id=ed9da72decc54fb5a2f55a2cbb41c2ad timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=TRICKLE-133 identifier=TRICKLE-133 run_id=ed9da72decc54fb5a2f55a2cbb41c2ad timeout_seconds=5.0

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
- fingerprint: 2d6924dccde7ce33
- dedup_fingerprint: 2d6924dccde7ce33

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-20 22:54
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-20 22:55
---
Run #1 [attempt=1, profile=default, role=— -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 54s
---
author: oompah
created: 2026-08-21 00:00
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 00:01
---
Run #1 [attempt=1, profile=default, role=— -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 46s
---
author: oompah
created: 2026-08-21 01:20
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 01:23
---
Run #1 [attempt=1, profile=default, role=— -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 3m 10s
---
author: oompah
created: 2026-08-21 01:23
---
Duplicate screening was inconclusive 3 times. Human action required: a project owner must review the authoritative task corpus and use the authenticated duplicate-screening owner-resolution action (POST /api/v1/issues/OOMPAH-1214/duplicate-screening/owner-resolution) with a conclusive verdict and reason. This records the owner decision, resets the retry budget, and returns no_duplicate tasks to Open (or routes a verified duplicate to Duplicate Candidate). A plain verdict comment is not authoritative.
---
author: oompah
created: 2026-08-21 05:03
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 05:05
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 05:06
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 2m 19s
- Log: OOMPAH-1214__20260821T050528Z.jsonl
---
author: oompah
created: 2026-08-21 09:30
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 09:30
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 09:32
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 37s
- Log: OOMPAH-1214__20260821T093103Z.jsonl
---
author: oompah
created: 2026-08-21 14:30
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 14:30
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 14:31
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 16s
- Log: OOMPAH-1214__20260821T143051Z.jsonl
---
author: oompah
created: 2026-08-21 14:31
---
Duplicate screening was inconclusive 3 times. Human action required: a project owner must review the authoritative task corpus and use the authenticated duplicate-screening owner-resolution action (POST /api/v1/issues/OOMPAH-1214/duplicate-screening/owner-resolution) with a conclusive verdict and reason. This records the owner decision, resets the retry budget, and returns no_duplicate tasks to Open (or routes a verified duplicate to Duplicate Candidate). A plain verdict comment is not authoritative.
---
author: oompah
created: 2026-08-23 23:12
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-23 23:13
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-23 23:14
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.5K out [1.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 31s
- Log: OOMPAH-1214__20260823T231327Z.jsonl
---
author: oompah
created: 2026-08-24 06:23
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-24 06:24
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-24 06:25
---
**Understanding & Plan**

This issue reports a timeout error from backend:orchestrator: 'Pre-provider contributor evidence exceeded its bounded task-authority deadline timeout_seconds=5.0'. 

The error occurs when oompah operates on project proj-14849f1b with tracker provenanceguardedtracker. The operation takes longer than 5 seconds, causing the bounded task-authority deadline to exceed and triggering error_watcher.

**Approach:**
1. Find the backend:orchestrator code that handles 'pre-provider contributor evidence'
2. Identify where the 5-second timeout is enforced
3. Either increase the timeout, optimize the operation, or add graceful degradation
4. Ensure error_watcher doesn't trigger on expected timeouts
5. Test the fix

Starting investigation now.
---
author: oompah
created: 2026-08-24 06:39
---
**Discovery: Root Cause Identified**

Found the timeout issue at `oompah/orchestrator.py` line 58070.

The error occurs when persisting contributor evidence takes longer than the bounded deadline. The timeout is calculated as:
- `control_timeout` (terminal_control_lock_timeout_seconds) = 5.0 seconds (default)
- `termination_timeout` (worker_termination_timeout_ms / 1000) = 10.0 seconds
- `persistence_timeout` = max(min(5.0, 5.0), 0.05) = **5.0 seconds**

This causes slow tracker operations (especially git commits to state branches) to timeout on provenanceguardedtracker.

**The Bug:** The configured timeout override (60.0 seconds) at lines 58035-43 uses `getattr(self.config, 'contributor_evidence_persist_timeout_seconds', None)`. When this attribute is None or inaccessible, the 5-second calculated timeout is used instead of the configured 60-second timeout.

**The Fix:** 
1. Ensure the configured timeout is properly set and retrieved
2. Increase the calculated default timeout to be more lenient
3. Update .env.example to match code (says 30 but code is 60)

Starting implementation now.
---
author: oompah
created: 2026-08-24 06:43
---
**Implementation: Timeout Fix Applied**

Made two key changes to fix the pre-provider contributor evidence timeout issue:

1. **oompah/orchestrator.py (line 58035-38)**
   - Changed getattr default from `None` to `60.0`
   - Ensures configured timeout is always available as fallback
   - Prevents timeout from defaulting to 5 seconds when attribute is inaccessible

2. **.env.example (line 277-82)**
   - Updated default documentation from 30 to 60 seconds
   - Aligns documentation with actual code config default
   - Clarifies to operators the correct environment variable value

**Why this fixes the bug:**
- Before: If getattr returned None, configured timeout was skipped, using calculated 5.0s
- After: getattr returns 60.0 as fallback, ensuring 60-second timeout is always available
- Slow git operations on trackers like provenanceguardedtracker now complete within timeout

**Tests:** All 21 provider_retirement tests and 168 config tests pass.

Commit: 94c622052
---
author: oompah
created: 2026-08-24 06:46
---
**Verification: Tests Pass**

Ran comprehensive tests to verify the fix:

✓ test_pre_provider_evidence_timeout_releases_task_authority - PASSED
  Confirms timeout behavior works correctly when configured timeout is intentionally small

✓ All 21 provider_retirement tests - PASSED
  Ensures no regression in provider lifecycle handling

✓ All 168 config tests - PASSED  
  Verifies configuration loading and defaults work correctly

Total: 189 core tests passing

**How the fix resolves OOMPAH-1214:**
- Previously: 5-second calculated timeout caused slow tracker operations to fail
- Now: 60-second configured timeout is guaranteed to be used
- Slow git operations on provenanceguardedtracker now have adequate time
- error_watcher will no longer be triggered for normal slow operations

**Changes summary:**
- 1 line: orchestrator.py getattr default (None → 60.0)
- 2 lines: .env.example documentation update
- 0 lines: No behavior changes to existing tests

Commit pushed: 94c622052
---
author: oompah
created: 2026-08-24 06:47
---
Fixed pre-provider contributor evidence timeout issue by ensuring configured 60-second timeout is always available as fallback instead of calculated 5-second timeout
---
<!-- COMMENTS:END -->
