---
id: OOMPAH-1213
type: bug
status: Open
priority: 2
title: '[backend:orchestrator] Restart recovery persistence failed closed: restart
  recovery publication was not acknowledged'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T03:50:52.786229Z'
updated_at: '2026-08-20T22:54:06.117317Z'
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
  task_fingerprint: 9b03a38e9059580321d5ab6b8701606b8b24491d7c248cc2a9b6fad3b00488c2
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 7e626b2c5876af04b7d290e645ec2436341afc0de2f26215f3a903abfcebd81b:56501
  claim_owner: b0161d82-55d7-4b08-9b68-ee54b4e13c9c
  claimed_at: '2026-08-20T22:53:32.578601+00:00'
  claim_expires_at: '2026-08-20T23:23:32.578601+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 0d24f0f0-1902-4538-b2f6-8f4ca2dcaee3
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Restart recovery persistence failed closed: restart recovery publication was not acknowledged

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Restart recovery persistence failed closed: restart recovery publication was not acknowledged

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
- fingerprint: 399be2300fdef47a
- dedup_fingerprint: 399be2300fdef47a

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 04:28
---
Duplicate error_watcher occurrence suppressed; this task already tracks the same dedup fingerprint.

Source: `backend:orchestrator`

Message: Restart recovery persistence failed closed: restart recovery publication was not acknowledged
---
author: oompah
created: 2026-08-20 22:54
---
Duplicate screening dispatched (profile: default, task remains Open)
---
<!-- COMMENTS:END -->
