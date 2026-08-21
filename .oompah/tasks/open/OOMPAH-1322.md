---
id: OOMPAH-1322
type: bug
status: Open
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
updated_at: '2026-08-21T05:08:09.926370Z'
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
  task_fingerprint: f4e1b4537a959ac44b8f294e9ddec79b99d08e821329d1d1a8f10dca46bb6ff7
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 24934f6e428b6b1f5868b967b89cd75eb95e0978fa7cad99025bc7cc6954965d:143345
  claim_owner: 7dbe71d1-9fc2-4b0c-bb54-3da0831c26d5
  claimed_at: '2026-08-21T05:07:58.433126+00:00'
  claim_expires_at: '2026-08-21T05:37:58.433126+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: c7074b86-776d-48ee-9b50-76b653bede1a
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

