---
id: OOMPAH-1277
type: bug
status: Open
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
updated_at: '2026-08-21T02:45:13.605978Z'
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
  task_fingerprint: ee16e84c6d41e2a66004044a815c8ffaf0b311c15e7fe14b6affd4936bd04f14
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: e5cb1bf8dc908d1b0c75107a8d5db4b39038639a737124b4d1320cf851254737:142906
  claim_owner: 884c7b0a-4fe0-4acd-9fe6-041416485094
  claimed_at: '2026-08-21T02:44:27.165615+00:00'
  claim_expires_at: '2026-08-21T03:14:27.165615+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 8267d12b-d451-4268-b8f5-7aa631786fe4
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
<!-- COMMENTS:END -->
