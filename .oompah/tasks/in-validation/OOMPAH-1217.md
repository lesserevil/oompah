---
id: OOMPAH-1217
type: bug
status: In Validation
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=TRICKLE-122 identifier=TRICKLE-122 run_id=55adaba352c743fc8a2cfc754517629a
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T04:00:53.373319Z'
updated_at: '2026-08-23T23:56:35.484831Z'
work_branch: OOMPAH-1217
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/897
review_number: '897'
review_head: 486e53196e7bb4c2ff4bdcd988be46ec8debba65
merged_at: null
oompah.lifecycle_revision: 7
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
  task_fingerprint: f5a55a6dfabcbe4e7399991f78d621dbb416372fb9da9c43f9d1486238f17aab
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-21T00:04:50.206002+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: The task corpus contains 29 similarity candidates, all\
    \ in terminal states (Done, Merged, or Archived). The structurally closest tasks\
    \ (OOMPAH-1015 through OOMPAH-1027) are auto-filed error_watcher incidents from\
    \ the same project/tracker but describe different backend components and error\
    \ types (terminal_audit_enforcement metadata_malformed vs. orchestrator task-authority\
    \ deadline). No active Open task matches OOMPAH-1217's specific backend:orchestrator\
    \ error. The closest reviewed historical task is OOMPAH-1015 (Merged), which addresses\
    \ a different component/error entirely.\n# Duplicate Investigation: OOMPAH-1217\n\
    \nI need to review the current task corpus and determine if OOMPAH-1217 matches\
    \ any active duplicate candidates.\n\n## Analysis\n\n**Current Task (OOMPAH-1217):**\n\
    - Status: **Open** \u2713 (active)\n- Error: `backend:orchestrator` - \"Pre-provider\
    \ contributor evidence exceeded its bounded task-authority deadline\"\n- Issue\
    \ ID: TRICKLE-122\n- Timeout: 5.0 seconds\n- Source: proj-14849f1b (provenanceguardedtracker)\n\
    - Fingerprint: 73d371097ee3d9c9\n\n**Reviewing the task corpus:**\n\nThe corpus\
    \ contains 29 similarity candidates, but examining their states:\n- **OOMPAH-1000\
    \ through OOMPAH-1014**: All are either **Merged** or **Done** (terminal states)\
    \ \u2717\n- **OOMPAH-1015 through OOMPAH-1027**: All are either **Merged** or\
    \ **Archived** (terminal states) \u2717\n- **OOMPAH-1, OOMPAH-10, OOMPAH-3**:\
    \ **Archived** (terminal states) \u2717\n- **OOMPAH-1217**: **Open** (the current\
    \ task)\n\n**Closest structural similarities:** \nOOMPAH-1015 and OOMPAH-1016-1027\
    \ share the same source project/tracker pattern and are error_watcher auto-filed\
    \ tasks, but they describe:\n- **Different backend component**: `backend:terminal_audit_enforcement`\
    \ (not orchestrator)\n- **Different error type**: \"pre_recovery_finalization_metadata_malformed\"\
    \ (not task-authority deadline)\n- **Terminal states**: All are already Merged/Archived\
    \ (historical context, not active duplicates)\n\nPer the instructions, I must\
    \ exclude every candidate in a terminal state. No active task in the corpus describes\
    \ the same backend:orchestrator task-authority deadline problem.\n\n---\n\nFocus\
    \ handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\n\
    Matches: none\n\nEvidence: The task corpus contains 29 similarity candidates,\
    \ all in terminal states (Done, Merged, or Archived). The structurally closest\
    \ tasks (OOMPAH-1015 through OOMPAH-1027) are auto-filed error_watcher incidents\
    \ from the same project/tracker but describe different backend components and\
    \ error types (terminal_audit_enforcement metadata_malformed vs. or"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 1
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: null
oompah.work_contributors:
  runs:
  - run_id: 0ca5465c97e848e5b86fd3697174cfed--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1217
    source_sha: null
    completed_at: ''
  - run_id: 0ca5465c97e848e5b86fd3697174cfed--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1217
    source_sha: null
    completed_at: ''
  - run_id: a63fbe8d72ac43eb8f697b131dc816d0--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1217
    source_sha: 02bd5960434a5c65dce259894737a55ab7a8ea96
    completed_at: '2026-08-21T00:04:50.209070+00:00'
  - run_id: b42bda3a342c481e948ec5e00223a47b--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1217
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 2010
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 2010
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2010
    cost_usd: 0.0
    recorded_at: '2026-08-21T00:04:50.204938+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1217
  base_branch: main
  base_sha: 859aa8a5a9fcf82063f312f6d16f8eb4ae288631
  head_sha: 486e53196e7bb4c2ff4bdcd988be46ec8debba65
  submitted_at: '2026-08-21T01:37:56.134651+00:00'
  updated_at: '2026-08-21T09:29:07.627173+00:00'
oompah.work_branch: OOMPAH-1217
oompah.review_url: https://github.com/lesserevil/oompah/pull/897
oompah.review_number: '897'
oompah.target_branch: main
oompah.review_head: 486e53196e7bb4c2ff4bdcd988be46ec8debba65
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-de399cf31768
    project_id: proj-14849f1b
    task_id: OOMPAH-1217
    digest: 35603ee8a46ec524aa496df57a6c6127b5531f39ab835e3fc39e1e2082bed033
  - version: 1
    audit_id: audit-b1b449c90517
    project_id: proj-14849f1b
    task_id: OOMPAH-1217
    digest: 35603ee8a46ec524aa496df57a6c6127b5531f39ab835e3fc39e1e2082bed033
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-de399cf31768
    project_id: proj-14849f1b
    task_id: OOMPAH-1217
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 35603ee8a46ec524aa496df57a6c6127b5531f39ab835e3fc39e1e2082bed033
    attempts:
    - version: 1
      attempt_id: attempt-070172778c4d
      target_state: Done
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 35603ee8a46ec524aa496df57a6c6127b5531f39ab835e3fc39e1e2082bed033
      created_at: '2026-08-23T23:56:33.962291+00:00'
      provider_id: prov-6cf41c89
      model: switchyard/auto
      started_at: '2026-08-23T23:56:33.962291+00:00'
      branch_key: OOMPAH-1217
      selected_ref: 486e53196e7bb4c2ff4bdcd988be46ec8debba65
      selected_sha: 486e53196e7bb4c2ff4bdcd988be46ec8debba65
    source_generation: 1
    requested_by:
      version: 1
      identity: oompah
      source: orchestrator
    previous_state: In Review
    created_at: '2026-08-23T23:41:38.984056+00:00'
    eligible_at: '2026-08-23T23:41:38.984056+00:00'
    selected_ref: 486e53196e7bb4c2ff4bdcd988be46ec8debba65
    selected_sha: 486e53196e7bb4c2ff4bdcd988be46ec8debba65
    workflow_revision: cbde4578c71296984a9f6b9e05b155e8360031432401e5fdd90bf1c4edacbf9b
    updated_at: '2026-08-23T23:56:33.962291+00:00'
  - version: 1
    audit_id: audit-b1b449c90517
    project_id: proj-14849f1b
    task_id: OOMPAH-1217
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 35603ee8a46ec524aa496df57a6c6127b5531f39ab835e3fc39e1e2082bed033
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: oompah
      source: orchestrator
    previous_state: In Review
    created_at: '2026-08-23T23:41:38.984056+00:00'
    prerequisite_audit_id: audit-de399cf31768
    selected_ref: 486e53196e7bb4c2ff4bdcd988be46ec8debba65
    selected_sha: 486e53196e7bb4c2ff4bdcd988be46ec8debba65
    workflow_revision: cbde4578c71296984a9f6b9e05b155e8360031432401e5fdd90bf1c4edacbf9b
  attempt_history:
  - version: 1
    attempt_id: attempt-070172778c4d
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 35603ee8a46ec524aa496df57a6c6127b5531f39ab835e3fc39e1e2082bed033
    created_at: '2026-08-23T23:56:33.962291+00:00'
    provider_id: prov-6cf41c89
    model: switchyard/auto
    started_at: '2026-08-23T23:56:33.962291+00:00'
    branch_key: OOMPAH-1217
    selected_ref: 486e53196e7bb4c2ff4bdcd988be46ec8debba65
    selected_sha: 486e53196e7bb4c2ff4bdcd988be46ec8debba65
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=TRICKLE-122 identifier=TRICKLE-122 run_id=55adaba352c743fc8a2cfc754517629a timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=TRICKLE-122 identifier=TRICKLE-122 run_id=55adaba352c743fc8a2cfc754517629a timeout_seconds=5.0

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
- fingerprint: 73d371097ee3d9c9
- dedup_fingerprint: 73d371097ee3d9c9

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-20 22:59
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-20 23:00
---
Run #1 [attempt=1, profile=default, role=— -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 37s
---
author: oompah
created: 2026-08-21 00:03
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 00:04
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 00:04
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.0K out [2.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 7s
- Log: OOMPAH-1217__20260821T000412Z.jsonl
---
author: oompah
created: 2026-08-21 01:19
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 01:19
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 01:28
---
## Understanding

The issue occurs in oompah's backend:orchestrator when persisting pre-provider contributor evidence times out. The error message 'Pre-provider contributor evidence exceeded its bounded task-authority deadline' is logged as ERROR level (line 58066 in orchestrator.py).

**Root Cause:**
ErrorWatcher has a logging handler that catches all ERROR+ level logs and automatically files them as tasks. When the contributor evidence persistence times out, the orchestrator logs an ERROR, which triggers error_watcher to file this task automatically.

**Why This is a Problem:**
This timeout is a handled graceful degradation case - the code recovers by retiring the pre-provider runtime for retry. It's not an unhandled error. The similar cancellation case (line 58102) uses logger.warning() instead of logger.error(), showing the pattern.

**Planned Fix:**
Change the logger.error() call on line 58066 of orchestrator.py to logger.warning() to prevent error_watcher from triggering while still logging the issue for operational visibility.
---
author: oompah
created: 2026-08-21 01:36
---
## Implementation

Changed `logger.error()` to `logger.warning()` on line 58066 of oompah/orchestrator.py for the pre-provider contributor evidence timeout case.

**Why This Works:**
- ErrorWatcher's logging handler only watches for ERROR+ level logs (logging.ERROR and above)
- By changing the log level to WARNING, the timeout message is still logged for operational visibility but no longer triggers error_watcher
- This aligns with the similar cancellation timeout case which already uses logger.warning() (line 58102)
- The timeout is a handled graceful degradation where the pre-provider runtime is retired for retry - it's not an unhandled error

**Tests Verified:**
- test_pre_provider_evidence_timeout_releases_task_authority: PASSED
- test_cancelled_pre_provider_evidence_releases_task_authority: PASSED (both variants)
- All 124 error_watcher tests: PASSED
---
author: oompah
created: 2026-08-21 01:37
---
## Verification

All relevant tests pass:
- test_pre_provider_evidence_timeout_releases_task_authority: ✓ PASSED
- test_cancelled_pre_provider_evidence_releases_task_authority (2 variants): ✓ PASSED
- All 124 error_watcher tests: ✓ PASSED

The fix is minimal (1-line change) and focused on the root cause. The timeout is now logged at WARNING level, preventing error_watcher from triggering while maintaining operational visibility.

Changes committed and pushed to branch OOMPAH-1217.
---
author: oompah
created: 2026-08-21 01:38
---
Fixed pre-provider evidence timeout logging to use WARNING instead of ERROR, preventing error_watcher from auto-filing this handled timeout scenario as a task.
---
author: oompah
created: 2026-08-21 04:55
---
Branch quality gate passed for `486e53196e7bb4c2ff4bdcd988be46ec8debba65` using `make test` in 188.0s. Review creation may proceed.
---
author: oompah
created: 2026-08-21 16:29
---
Branch quality gate passed for `486e53196e7bb4c2ff4bdcd988be46ec8debba65` using `make test` in 183.5s. Review creation may proceed.
---
author: oompah
created: 2026-08-23 23:41
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-23 23:51
---
Auditor dispatched (attempt #1, candidate: prov-6cf41c89/switchyard/auto)
---
author: oompah
created: 2026-08-23 23:51
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-23 23:52
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Opencode/Switchyard/switchyard/auto]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: interrupted, Duration: 26s
- Log: OOMPAH-1217__20260823T235155Z.jsonl
---
<!-- COMMENTS:END -->
