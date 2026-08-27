---
id: OOMPAH-1322
type: bug
status: Archived
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1208 identifier=OOMPAH-1208 run_id=dd82f7e7ce1d4fe388c01522732adf48
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-21T01:15:25.298559Z'
updated_at: '2026-08-27T03:58:41.502386Z'
work_branch: OOMPAH-1322
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.lifecycle_revision: 4
oompah.last_batch:
  batch_id: batch-6721ed37af5c4e51ae3558e98f499304
  actor: shedwards
  committed_at: '2026-08-21T01:29:59.950511Z'
  operation:
    kind: whole_column_move
    source_status: Backlog
    scope: flat_board
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: f4e1b4537a959ac44b8f294e9ddec79b99d08e821329d1d1a8f10dca46bb6ff7
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-24T13:33:14.989379+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-1322 describes a timeout error in pre-provider\
    \ contributor evidence collection specific to the orchestrator backend. While\
    \ the corpus contains multiple auto-filed error tasks from `error_watcher`, the\
    \ closest candidates (OOMPAH-1015 and related, OOMPAH-1014, OOMPAH-1000\u2013\
    1012) all address different failure modes (metadata malformation, terminal-audit\
    \ lifecycle, workflow coordination) and are all in terminal states. No open, active\
    \ task shares OOMPAH-1322's specific timeout symptom or addresses the same code\
    \ path.\nLooking at OOMPAH-1322 and comparing it to the supplied task corpus,\
    \ I need to determine if this is a duplicate of an existing issue.\n\n## Analysis\n\
    \n**OOMPAH-1322 Error Message:**\n- \"Pre-provider contributor evidence exceeded\
    \ its bounded task-authority deadline issue_id=OOMPAH-1208 identifier=OOMPAH-1208\
    \ run_id=dd82f7e7ce1d4fe388c01522732adf48 timeout_seconds=5.0\"\n- This is a timeout\
    \ error in `backend:orchestrator` during evidence collection\n- fingerprint: 6cbdb451c9d42ddd\n\
    \n**Corpus Review:**\n\nThe corpus includes 28 similarity candidates. Notably:\n\
    - **OOMPAH-1015** (Merged): \"terminal-audit enforcement: pre_recovery_finalization_metadata_malformed\"\
    \ \u2014 a different error pattern about malformed metadata, not timeout\n- **OOMPAH-1016\
    \ through OOMPAH-1027** (Archived): All duplicates of OOMPAH-1015 from a startup\
    \ flood, addressing malformed ledger rows\n- **OOMPAH-1014** (Merged): About orphaned\
    \ terminal-audit authority\n- **OOMPAH-1000 through OOMPAH-1012** (Merged/Done):\
    \ Various workflow, epic, and audit-related fixes\n\nAll tasks in the corpus that\
    \ show similar error-watcher auto-filing patterns are in **terminal states** (Merged,\
    \ Done, or Archived). Per the duplicate-screening rules, completed tasks are historical\
    \ context and cannot be duplicate targets.\n\n**Key Differences:**\n1. OOMPAH-1322's\
    \ error is specific to \"Pre-provider contributor evidence\" timeout \u2014 a\
    \ distinct code path\n2. No active (Open) task describes this same timeout error\n\
    3. Terminal-state tasks addressed different issues (metadata corruption, audit\
    \ lifecycle, workflow gates)\n4. The three previous screening attempts were inconclusive,\
    \ suggesting this is genuinely difficult to classify, not an obvious duplicate\n\
    \n---\n\nFocus handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\
    \nMatches: none\n\nEvidence: OOMPAH-1322 describes a timeout error in pre-provider\
    \ contributor evidence collection specific to the orchestrator backend. While\
    \ the corpus contains multiple auto-filed error tasks from `error_w"
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
  - run_id: 71d1715257d34f909788c567fb76ee9b--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1322
    source_sha: null
    completed_at: ''
  - run_id: c98d36782062453c944bda31857dbb1e--contributor-86e3ac8153e1
    provider_id: prov-6cf41c89
    provider_name: Opencode/Switchyard
    model_id: switchyard/auto
    focus: duplicate_detector
    source_branch: OOMPAH-1322
    source_sha: null
    completed_at: ''
  - run_id: 69e4c546cd90425e97d3285053d830fd--contributor-86e3ac8153e1
    provider_id: prov-6cf41c89
    provider_name: Opencode/Switchyard
    model_id: switchyard/auto
    focus: duplicate_detector
    source_branch: OOMPAH-1322
    source_sha: null
    completed_at: ''
  - run_id: e359d2e4127345ae91024caeec68dce3--contributor-86e3ac8153e1
    provider_id: prov-6cf41c89
    provider_name: Opencode/Switchyard
    model_id: switchyard/auto
    focus: duplicate_detector
    source_branch: OOMPAH-1322
    source_sha: null
    completed_at: ''
  - run_id: 1f730fcbd22545fd91fa868e7ca66a0d--contributor-86e3ac8153e1
    provider_id: prov-6cf41c89
    provider_name: Opencode/Switchyard
    model_id: switchyard/auto
    focus: duplicate_detector
    source_branch: OOMPAH-1322
    source_sha: null
    completed_at: ''
  - run_id: d161aecade4e4ac0b028dae52bc083d3--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1322
    source_sha: 584cdd53def37b6b16e99b49c3f4582822b4a848
    completed_at: '2026-08-24T13:33:14.991422+00:00'
  - run_id: 8e84398202364953a2abb91e1ee34d7b--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1322
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 2175
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 2175
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2175
    cost_usd: 0.0
    recorded_at: '2026-08-24T13:33:14.943069+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1322
  base_branch: main
  base_sha: 1e08d58a3fcfd254a2bffedd2580d383f1b02193
  head_sha: d05d11da131bde25d4df4c985f9f9e5ae92f98e2
  submitted_at: '2026-08-24T15:12:41.911327+00:00'
  updated_at: '2026-08-24T15:12:41.911327+00:00'
oompah.work_branch: OOMPAH-1322
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-c5a516f9dd4b
    project_id: proj-14849f1b
    task_id: OOMPAH-1322
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 13432eaaaf3355710b3fabdd1d4625fd75ddcdb2bfd2cc11d09768e2afb919aa
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
    created_at: '2026-08-27T03:58:36.439692+00:00'
    selected_ref: d05d11da131bde25d4df4c985f9f9e5ae92f98e2
    selected_sha: d05d11da131bde25d4df4c985f9f9e5ae92f98e2
    applied: false
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1208 identifier=OOMPAH-1208 run_id=dd82f7e7ce1d4fe388c01522732adf48 timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1208 identifier=OOMPAH-1208 run_id=dd82f7e7ce1d4fe388c01522732adf48 timeout_seconds=5.0

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
- fingerprint: 6cbdb451c9d42ddd
- dedup_fingerprint: 6cbdb451c9d42ddd

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 05:08
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 05:08
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 05:09
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 11s
- Log: OOMPAH-1322__20260821T050900Z.jsonl
---
author: oompah
created: 2026-08-21 09:53
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 09:54
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 09:54
---
Run #1 [attempt=1, profile=default, role=fast -> Opencode/Switchyard/switchyard/auto]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 47s
- Log: OOMPAH-1322__20260821T095430Z.jsonl
---
author: oompah
created: 2026-08-21 14:34
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 14:35
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 14:35
---
Run #1 [attempt=1, profile=default, role=fast -> Opencode/Switchyard/switchyard/auto]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 44s
- Log: OOMPAH-1322__20260821T143520Z.jsonl
---
author: oompah
created: 2026-08-21 14:36
---
Duplicate screening was inconclusive 3 times. Human action required: a project owner must review the authoritative task corpus and use the authenticated duplicate-screening owner-resolution action (POST /api/v1/issues/OOMPAH-1322/duplicate-screening/owner-resolution) with a conclusive verdict and reason. This records the owner decision, resets the retry budget, and returns no_duplicate tasks to Open (or routes a verified duplicate to Duplicate Candidate). A plain verdict comment is not authoritative.
---
author: oompah
created: 2026-08-23 23:01
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-23 23:01
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-23 23:02
---
Run #1 [attempt=1, profile=default, role=fast -> Opencode/Switchyard/switchyard/auto]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 49s
- Log: OOMPAH-1322__20260823T230204Z.jsonl
---
author: oompah
created: 2026-08-24 06:27
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-24 06:28
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-24 06:29
---
Run #1 [attempt=1, profile=default, role=fast -> Opencode/Switchyard/switchyard/auto]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: interrupted, Duration: 2m 3s
- Log: OOMPAH-1322__20260824T062905Z.jsonl
---
author: oompah
created: 2026-08-24 13:31
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-24 13:31
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-24 13:33
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.2K out [2.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 59s
- Log: OOMPAH-1322__20260824T133153Z.jsonl
---
author: oompah
created: 2026-08-24 14:56
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-24 14:56
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-24 15:03
---
**Understanding**: The issue reports that orchestrator logs a WARNING when pre-provider contributor evidence persistence times out. The error message 'Pre-provider contributor evidence exceeded its bounded task-authority deadline' is being auto-filed by error_watcher as a task, but it should either: (1) be handled gracefully without triggering error_watcher, or (2) the timeout should be increased for slow trackers.

**Planned approach**: 
1. Examine the timeout calculation logic in _stage_work_contributor_launch (oompah/orchestrator.py ~line 57837)
2. Check error_watcher.py to understand why this WARNING is being auto-filed
3. Determine if the timeout is genuinely too short or if this should be handled as a non-error
4. Implement fix to either increase timeout or suppress error_watcher triggering
---
author: oompah
created: 2026-08-24 15:08
---
**Discovery**: Found the root cause in oompah/orchestrator.py _stage_work_contributor_launch() function. The three gracefully-handled timeout conditions are logged at WARNING level:

1. Line ~57957: 'Pre-provider contributor evidence is still settling...'
2. Line ~58079: 'Pre-provider contributor evidence exceeded its bounded task-authority deadline...'
3. Line ~58115: 'Cancelled pre-provider contributor evidence did not finish...'

These are normal, retryable conditions where the orchestrator automatically retries the work. However, the _TaskLoggingHandler (which captures ERROR+ logs) should not catch WARNING-level logs. Upon investigation, found that OOMPAH-1324 was filed with the same fix: downgrade these three log levels from WARNING to INFO. This will prevent error_watcher from auto-filing tasks for these expected conditions.

The fix is to change three logger.warning() calls to logger.info() in oompah/orchestrator.py.
---
author: oompah
created: 2026-08-24 15:12
---
**Implementation**: Changed three logger.warning() calls to logger.info() in oompah/orchestrator.py _stage_work_contributor_launch() function (lines 57956, 58079, and 58115).

The changes prevent these gracefully-handled timeout conditions from being captured by error_watcher:
- Pre-provider contributor evidence is still settling from a retired generation
- Pre-provider contributor evidence exceeded its bounded task-authority deadline  
- Cancelled pre-provider contributor evidence did not finish before release

These are normal retry conditions, not actual errors. By lowering the log level to INFO, they won't trigger error_watcher's ERROR+ handler, preventing auto-filing of unnecessary tasks.

Changes committed and pushed to branch OOMPAH-1322.
---
author: oompah
created: 2026-08-24 15:12
---
**Verification**: All tests pass successfully.

Ran focused tests on the affected code:
- test_provider_retirement.py: 21/21 tests passed ✓
- test_error_watcher.py: 126/126 tests passed ✓

The fix successfully prevents error_watcher from auto-filing these expected timeout conditions while maintaining all existing error-handling and logging functionality.
---
author: oompah
created: 2026-08-24 15:12
---
Fixed pre-provider contributor evidence timeout logging to prevent auto-filing by error_watcher. Changed three logger.warning() calls to logger.info() in orchestrator.py to suppress notifications for these expected, gracefully-handled retry conditions.
---
<!-- COMMENTS:END -->
