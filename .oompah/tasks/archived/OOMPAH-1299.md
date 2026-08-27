---
id: OOMPAH-1299
type: bug
status: Archived
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1215 identifier=OOMPAH-1215 run_id=a131bc85b2904aa09baeeaec133cbabd
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-21T00:01:23.399466Z'
updated_at: '2026-08-27T03:51:51.717302Z'
work_branch: OOMPAH-1299
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.lifecycle_revision: 4
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
  task_fingerprint: fbfb65b3e47f4d3de0f07f04ee8fb9b5560ebd240d1ab59cabda6344404a151e
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-21T16:15:20.346772+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-1299 describes a unique error pattern from backend:orchestrator\
    \ involving a task-authority deadline timeout. No other active (non-terminal)\
    \ task in the project corpus describes this specific error. The closest related\
    \ tasks (OOMPAH-1015+) involve different backend components and error patterns,\
    \ and all are in terminal states (Merged/Archived).\nI'm now analyzing whether\
    \ OOMPAH-1299 is a duplicate of an existing active issue by examining the supplied\
    \ project task corpus.\n\n## Analysis\n\n**Current Task Summary:**\n- OOMPAH-1299\
    \ is an Open bug from the backend:orchestrator component\n- Error: \"Pre-provider\
    \ contributor evidence exceeded its bounded task-authority deadline\"\n- Specific\
    \ parameters: issue_id=OOMPAH-1215, timeout_seconds=5.0\n- Auto-filed by error_watcher\
    \ from proj-14849f1b\n\n**Corpus Review:**\n\nI've examined all 28 similarity\
    \ candidates in the provided corpus. The relevant findings:\n\n1. **Task Status\
    \ Filter:** Per instructions, I've excluded all terminal-state tasks (Done, Merged,\
    \ Archived). This eliminates OOMPAH-1000 through OOMPAH-1027, which are all in\
    \ terminal states.\n\n2. **Active Tasks:** The only Open task in the corpus is\
    \ OOMPAH-1299 itself.\n\n3. **Closest Similar Tasks:** \n   - OOMPAH-1015 and\
    \ OOMPAH-1016-1027 (all Merged/Archived) describe similar auto-filed error_watcher\
    \ issues, but they are:\n     - From a different backend component (terminal_audit_enforcement\
    \ vs. orchestrator)\n     - Describing a different error pattern (metadata_malformed\
    \ vs. task-authority deadline)\n     - All in terminal states\n\n4. **Error Pattern\
    \ Uniqueness:** The specific error \"Pre-provider contributor evidence exceeded\
    \ its bounded task-authority deadline\" with the 5-second timeout does not appear\
    \ in any other task in the corpus.\n\n---\n\nFocus handoff: duplicate_detector\n\
    \nDuplicate preflight verdict: no_duplicate\n\nMatches: none\n\nEvidence: OOMPAH-1299\
    \ describes a unique error pattern from backend:orchestrator involving a task-authority\
    \ deadline timeout. No other active (non-terminal) task in the project corpus\
    \ describes this specific error. The closest related tasks (OOMPAH-1015+) involve\
    \ different backend components and error patterns, and all are in terminal states\
    \ (Merged/Archived)."
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
  - run_id: a5126f34da0746d39ea7066fbaf780a4--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1299
    source_sha: null
    completed_at: ''
  - run_id: 650b23ac5ee34760a989810b9ed8558a--contributor-86e3ac8153e1
    provider_id: prov-6cf41c89
    provider_name: Opencode/Switchyard
    model_id: switchyard/auto
    focus: duplicate_detector
    source_branch: OOMPAH-1299
    source_sha: null
    completed_at: ''
  - run_id: c061115e38094eb487467aad0eaf19c7--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1299
    source_sha: c7b3911883a90c1b5805204a430926eb1c6f53b8
    completed_at: '2026-08-21T16:15:20.389494+00:00'
  - run_id: ad5bc63ed9ab4c63b01f36179e06ec41--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1299
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1327
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1327
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1327
    cost_usd: 0.0
    recorded_at: '2026-08-21T16:15:20.344940+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1299
  base_branch: main
  base_sha: 8c81b69c713e9bb6a1da8906b7e637f1ea6a1696
  head_sha: f14aee1e215de9f41740046a3057ffc50cc64c71
  submitted_at: '2026-08-23T23:56:19.200373+00:00'
  updated_at: '2026-08-23T23:56:19.200373+00:00'
oompah.work_branch: OOMPAH-1299
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-3965e55a215f
    project_id: proj-14849f1b
    task_id: OOMPAH-1299
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a7d69b4945765b3905ef79aac4e52f68e2e36df58390dcbd0aefe65377ff16e7
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
    created_at: '2026-08-27T03:51:46.967990+00:00'
    selected_ref: f14aee1e215de9f41740046a3057ffc50cc64c71
    selected_sha: f14aee1e215de9f41740046a3057ffc50cc64c71
    applied: false
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1215 identifier=OOMPAH-1215 run_id=a131bc85b2904aa09baeeaec133cbabd timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1215 identifier=OOMPAH-1215 run_id=a131bc85b2904aa09baeeaec133cbabd timeout_seconds=5.0

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
- fingerprint: e5636d61c424d7c5
- dedup_fingerprint: e5636d61c424d7c5

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 03:36
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 03:37
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 03:38
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 2m 43s
- Log: OOMPAH-1299__20260821T033822Z.jsonl
---
author: oompah
created: 2026-08-21 07:39
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 07:40
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 07:42
---
Run #1 [attempt=1, profile=default, role=fast -> Opencode/Switchyard/switchyard/auto]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 2m 53s
- Log: OOMPAH-1299__20260821T074203Z.jsonl
---
author: oompah
created: 2026-08-21 16:12
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 16:13
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 16:15
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.3K out [1.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 28s
- Log: OOMPAH-1299__20260821T161403Z.jsonl
---
author: oompah
created: 2026-08-23 23:40
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-23 23:40
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-23 23:41
---
## Understanding & Plan

**Issue Summary:** Backend orchestrator is timing out on 'pre-provider contributor evidence' operations with a 5-second deadline. The error is being auto-filed instead of being handled gracefully.

**Interpreted Problem:** Some operation that gathers contributor evidence before entering provider logic is exceeding a 5-second bounded task-authority deadline, likely in the orchestrator's provenanceguardedtracker integration.

**Investigation Plan:**
1. Search for 'pre-provider contributor evidence' in the codebase to locate the error source
2. Find the timeout configuration and understand why 5 seconds may be insufficient
3. Identify if this is a performance issue, a configuration issue, or missing error handling
4. Implement fix: either increase timeout, optimize performance, or add graceful degradation with clear messaging
5. Verify no regression in error_watcher behavior

**Next Step:** Exploring codebase for relevant code.
---
author: oompah
created: 2026-08-23 23:47
---
## Discovery

**Root Cause Found:** In `oompah/orchestrator.py` lines 58067-58083, the function `_stage_work_contributor_launch()` logs a warning when pre-provider contributor evidence persists longer than a timeout deadline:

\`\`\`
logger.warning(
    'Pre-provider contributor evidence exceeded its bounded '
    'task-authority deadline issue_id=%s identifier=%s '
    'run_id=%s timeout_seconds=%s',
    ...
)
\`\`\`

**Why This Happens:**
- The function persists contributor metadata (provider/model) asynchronously
- It waits for this persistence with a timeout (calculated as min(control_timeout, termination_timeout/2.0))
- When timeout occurs, this warning is logged with structured data
- The error_watcher system auto-files this as a task

**Current Timeout Logic:**
- Default control_timeout = 5.0 seconds
- Default worker_termination_timeout_ms = 10,000 (10 seconds)
- Calculated persistence_timeout = min(5.0, 5.0) = 5.0 seconds
- Can be configured via 'contributor_evidence_persist_timeout_seconds'

**Context:** This is a pre-provider synchronous tracker adapter write that can be slow for some tracker implementations. The issue is that this is logged as a warning that triggers error_watcher, but it's actually a handled graceful degradation - the function returns a clear error message and retries.

**Next Step:** Determine if this should be:
1. Handled silently (no warning log)
2. Logged at DEBUG level instead of WARNING
3. Timeout increased
4. Excluded from error_watcher tracking
---
author: oompah
created: 2026-08-23 23:52
---
## Implementation Plan

**Root Cause Analysis:**
The warning logged at line 58067 'Pre-provider contributor evidence exceeded its bounded task-authority deadline' is being picked up by error_watcher and auto-filed as a task, despite being logged at WARNING level. This appears to be via a project log file watcher or other mechanism.

**Key Insight:**
This is NOT actually an unhandled error - it's a handled graceful degradation. The function:
1. Times out waiting for synchronous tracker metadata writes
2. Returns a clear error message (causing the pre-provider runtime to retire for retry)
3. This is normal behavior when tracker operations are slow

**Solution:**
Change the log level from WARNING to DEBUG for both occurrence types:
1. 'Pre-provider contributor evidence exceeded its bounded task-authority deadline' (line 58067)
2. 'Cancelled pre-provider contributor evidence did not finish before task-authority release' (line 58103)

These are normal operational conditions (not errors), so DEBUG level is appropriate. They represent handled timeouts in the pre-provider lifecycle, not unexpected failures.

**Why This Is Safe:**
- The function still returns clear error messages
- The worker still exits gracefully  
- Retry logic is still triggered
- No change to error handling or flow
- Other error_watcher messages remain unchanged
---
author: oompah
created: 2026-08-23 23:55
---
## Implementation Complete

**Changes Made:**
Modified `oompah/orchestrator.py` to change log level from WARNING to DEBUG for pre-provider contributor evidence timeout scenarios:

1. Line 58067: Changed `logger.warning()` to `logger.debug()` for 'Pre-provider contributor evidence exceeded its bounded task-authority deadline' 
2. Line 58103: Changed `logger.warning()` to `logger.debug()` for 'Cancelled pre-provider contributor evidence did not finish before task-authority release'

**Why This Fixes the Issue:**
- These timeouts represent normal, handled operational conditions, not failures
- By logging at DEBUG level instead of WARNING, error_watcher will no longer pick them up and auto-file tasks
- The graceful error handling remains unchanged - worker exits cleanly with clear error messages
- Retry logic is unaffected

**Tests Run:**
✅ All 21 tests in test_provider_retirement.py pass
✅ All 124 tests in test_error_watcher.py pass
✅ Specifically verified:
  - test_pre_provider_evidence_timeout_releases_task_authority 
  - test_cancelled_pre_provider_evidence_releases_task_authority

**Result:** No unhandled errors will trigger error_watcher for normal pre-provider timeouts, resolving OOMPAH-1299.
---
author: oompah
created: 2026-08-23 23:56
---
Fixed pre-provider contributor evidence timeout handling to prevent error_watcher auto-filing by changing log level from WARNING to DEBUG. These are normal handled operational conditions, not unhandled errors.
---
author: oompah
created: 2026-08-23 23:56
---
## Completion Summary

**Issue:** Backend orchestrator was logging pre-provider contributor evidence timeouts at WARNING level, causing error_watcher to auto-file tasks inappropriately during normal operation.

**Root Cause:** Synchronous tracker metadata writes have bounded timeouts (5-10 seconds by default). When these timeouts occur, the system gracefully degrades and retries, but the WARNING-level logs were being picked up by error_watcher's monitoring mechanisms.

**Solution:** Changed log level from WARNING to DEBUG for two timeout scenarios in `_stage_work_contributor_launch()`:
- Line 58067: Pre-provider contributor evidence exceeded deadline
- Line 58103: Cancelled pre-provider contributor evidence timeout

**Result:** 
✅ Pre-provider evidence timeouts no longer trigger error_watcher tasks
✅ All error handling and retry logic unchanged
✅ All 145 related tests pass
✅ Code reviewed against existing patterns
✅ Task submitted for integration

**References:**
- Modified file: oompah/orchestrator.py
- Commit: f14aee1e2
- Branch: OOMPAH-1299
---
<!-- COMMENTS:END -->
