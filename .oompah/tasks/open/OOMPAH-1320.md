---
id: OOMPAH-1320
type: bug
status: Open
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1200 identifier=OOMPAH-1200 run_id=cdc92fe9ae4942f9aff1c4d8d5d14fe6
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-21T01:12:08.566823Z'
updated_at: '2026-08-21T05:04:58.404721Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.lifecycle_revision: 1
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
  task_fingerprint: 8f8a9e7ca03461ef8b7ad338935420f8209cba07dbf033be0e12f70f042ee33c
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: e0c4764a0767dc9d9a5dd2343602192aea4424f349e39d7b1e31b6ad01e70b2a:143343
  claim_owner: 7dbe71d1-9fc2-4b0c-bb54-3da0831c26d5
  claimed_at: '2026-08-21T05:04:46.550292+00:00'
  claim_expires_at: '2026-08-21T05:34:46.550292+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 97761749-5163-4ce5-ba3c-46dca3e36d45
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1200 identifier=OOMPAH-1200 run_id=cdc92fe9ae4942f9aff1c4d8d5d14fe6 timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1200 identifier=OOMPAH-1200 run_id=cdc92fe9ae4942f9aff1c4d8d5d14fe6 timeout_seconds=5.0

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
- fingerprint: d8afd06b57598237
- dedup_fingerprint: d8afd06b57598237

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

