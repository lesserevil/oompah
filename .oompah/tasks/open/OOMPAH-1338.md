---
id: OOMPAH-1338
type: bug
status: Open
priority: 2
title: '[backend:server] Reviews API error: ProgrammingError(''Cannot operate on a
  closed database.'')'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-25T16:53:55.710371Z'
updated_at: '2026-08-25T20:22:53.890051Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.lifecycle_revision: 1
oompah.last_batch:
  batch_id: batch-6f0e83c8e44c413d864c213fbfd4e455
  actor: shedwards
  committed_at: '2026-08-25T17:51:56.061271Z'
  operation:
    kind: whole_column_move
    source_status: Backlog
    scope: flat_board
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 3b919e3a33c919aadfbcfc8cf23a19b5e4c1307b7458dd7e1b1e3924fa92f1de
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: b69f9168cb20548795d6dea40f7ebea5d17458d903d8262f668c9661ab9eccbb:168473
  claim_owner: a40199ea-9091-4b96-87de-6f33f559f142
  claimed_at: '2026-08-25T20:22:45.272175+00:00'
  claim_expires_at: '2026-08-25T20:52:45.272175+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 33d0193f-8900-40de-abaf-621a9ae6d93f
---
## Summary

### Problem
Oompah detected a backend error from `backend:server`:

> Reviews API error: ProgrammingError('Cannot operate on a closed database.')

### Steps to Reproduce
1. Run oompah with `backend:server` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:server` and is recorded by oompah's `error_watcher`:

> Reviews API error: ProgrammingError('Cannot operate on a closed database.')

### Expected Behavior
The operation in `backend:server` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Acceptance Criteria
- The error from `backend:server` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: proj-14849f1b
- tracker: provenanceguardedtracker
- tracker_kind: provenanceguardedtracker
- fingerprint: 1a18c13ca9f6f4ef
- dedup_fingerprint: 1a18c13ca9f6f4ef

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

