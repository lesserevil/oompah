---
id: OOMPAH-1325
type: bug
status: Open
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1307 identifier=OOMPAH-1307 run_id=cf289f342ff8435d925bd789c13b1e6d
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-21T08:06:24.549306Z'
updated_at: '2026-08-24T07:35:50.217004Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.lifecycle_revision: 1
oompah.last_batch:
  batch_id: batch-406b98cf5aef4911b932a9c5924b23e6
  actor: shedwards
  committed_at: '2026-08-24T02:44:47.015459Z'
  operation:
    kind: whole_column_move
    source_status: Backlog
    scope: flat_board
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 7b6c82d765a10bddd8fcc4f872fec36ce04599ca941e22b853d2d19aeea3446e
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: ba2164e2689ef5467214ea24a5e059384c6ac8e61eeeda7f74750bf8dc967f1f:166228
  claim_owner: 11327615-6fad-46c0-ac4f-081c79ea0c4f
  claimed_at: '2026-08-24T07:35:31.803585+00:00'
  claim_expires_at: '2026-08-24T08:05:31.803585+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 8a6fafe4-9e52-4d0c-a09e-a2cf7e3ec52d
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1307 identifier=OOMPAH-1307 run_id=cf289f342ff8435d925bd789c13b1e6d timeout_seconds=30.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1307 identifier=OOMPAH-1307 run_id=cf289f342ff8435d925bd789c13b1e6d timeout_seconds=30.0

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
- fingerprint: 4f908520bbaded18
- dedup_fingerprint: 4f908520bbaded18

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-24 07:35
---
Duplicate screening dispatched (profile: default, task remains Open)
---
<!-- COMMENTS:END -->
