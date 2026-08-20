---
id: OOMPAH-1197
type: bug
status: Open
priority: 2
title: '[backend:orchestrator] ACP worker failed issue_id=TRICKLE-119'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-12T23:56:36.517429Z'
updated_at: '2026-08-20T22:40:14.410495Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.lifecycle_revision: 1
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
  task_fingerprint: 0060d817b99465caeeff06056928426e2156f0a1f2325b9d668a6280b66afbc2
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 338ad294ce15fb3402c267dbe51423f04bb201d5ff7847546ebe45239ceb7701:56490
  claim_owner: b0161d82-55d7-4b08-9b68-ee54b4e13c9c
  claimed_at: '2026-08-20T22:40:11.832340+00:00'
  claim_expires_at: '2026-08-20T23:10:11.832340+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> ACP worker failed issue_id=TRICKLE-119

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> ACP worker failed issue_id=TRICKLE-119

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
- fingerprint: d274c7f10a0fe8d7
- dedup_fingerprint: d274c7f10a0fe8d7
- source_issue: TRICKLE-119

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 00:17
---
Duplicate task-specific occurrence of OOMPAH-1194. The canonical fix covers this failure: managed network Git used the stale local SSH origin instead of the project's configured HTTPS repo_url during Trickle workspace/epic refresh.
---
<!-- COMMENTS:END -->
