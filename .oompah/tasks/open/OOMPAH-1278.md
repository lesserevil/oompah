---
id: OOMPAH-1278
type: bug
status: Open
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
updated_at: '2026-08-21T02:47:00.234345Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.lifecycle_revision: 1
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
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 47558548befbea58ba9a3179c2c833dd79c92dd3be9d12876a1ffe5b7890530c:142907
  claim_owner: 884c7b0a-4fe0-4acd-9fe6-041416485094
  claimed_at: '2026-08-21T02:45:08.724345+00:00'
  claim_expires_at: '2026-08-21T03:15:08.724345+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: fb62f1ce-8ac7-4201-a75e-3c894aee54d6
oompah.work_contributors:
  runs:
  - run_id: 642d4b1003084628bc91263b5a53de8c--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1278
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 2057
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 2057
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2057
    cost_usd: 0.0
    recorded_at: '2026-08-21T02:46:55.161888+00:00'
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
<!-- COMMENTS:END -->
