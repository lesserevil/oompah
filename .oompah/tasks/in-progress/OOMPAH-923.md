---
id: OOMPAH-923
type: bug
status: In Progress
priority: 2
title: '[backend:server] Update issue API error: TaskTransitionNotApplied(''TRICKLE-126:
  In Progress was not applied (rejected: transition.generation_required)'')'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-08T16:51:21.989830Z'
updated_at: '2026-08-08T17:12:58.393487Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

### Problem
Oompah detected a backend error from `backend:server`:

> Update issue API error: TaskTransitionNotApplied('TRICKLE-126: In Progress was not applied (rejected: transition.generation_required)')

### Steps to Reproduce
1. Run oompah with `backend:server` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:server` and is recorded by oompah's `error_watcher`:

> Update issue API error: TaskTransitionNotApplied('TRICKLE-126: In Progress was not applied (rejected: transition.generation_required)')

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
- fingerprint: 47e4066f393770b2
- dedup_fingerprint: 47e4066f393770b2

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-08 17:11
---
Implemented the shared recurrence fix at 8a0b6948a1089b625d4ba416bde1bfed1da7a424. Structured durable-transition REJECTED outcomes now return HTTP 409 transition_rejected and log at INFO, so illegal-edge/generation-required client conflicts no longer create error-watcher tasks or health warnings. Focused regression suite: 25 passed; terminal mutation scan and secret scan passed. Exact full gate is next.
---
author: oompah
created: 2026-08-08 17:12
---
Correction to the prior progress comment: the amended commit's exact SHA is 8a0b6948ab0efb7a12f475b9f1cffc2d2a04a719. The short SHA remains 8a0b6948a; the earlier full SHA was copied from the pre-amend commit suffix and is not a Git object.
---
<!-- COMMENTS:END -->
