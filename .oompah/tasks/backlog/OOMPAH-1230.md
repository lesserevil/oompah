---
id: OOMPAH-1230
type: bug
status: Backlog
priority: 2
title: '[backend:task_transition_service] Task transition mutation guard failed project=proj-3e4e9214
  task=TRICKLE-140 reason=implementation.validation_submission'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T09:58:05.284702Z'
updated_at: '2026-08-13T09:58:05.284702Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

### Problem
Oompah detected a backend error from `backend:task_transition_service`:

> Task transition mutation guard failed project=proj-3e4e9214 task=TRICKLE-140 reason=implementation.validation_submission

### Steps to Reproduce
1. Run oompah with `backend:task_transition_service` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:task_transition_service` and is recorded by oompah's `error_watcher`:

> Task transition mutation guard failed project=proj-3e4e9214 task=TRICKLE-140 reason=implementation.validation_submission

### Expected Behavior
The operation in `backend:task_transition_service` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Acceptance Criteria
- The error from `backend:task_transition_service` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: proj-14849f1b
- tracker: provenanceguardedtracker
- tracker_kind: provenanceguardedtracker
- fingerprint: 8da03cc9e21f888f
- dedup_fingerprint: 8da03cc9e21f888f

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

