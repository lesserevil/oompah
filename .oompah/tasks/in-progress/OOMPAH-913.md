---
id: OOMPAH-913
type: bug
status: In Progress
priority: 2
title: '[backend:server] Update issue API error: TaskTransitionNotApplied(''OOMPAH-912:
  Open was not applied (waiting: transition.recovery_required)'')'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-08T14:23:18.279242Z'
updated_at: '2026-08-08T15:38:28.092016Z'
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

> Update issue API error: TaskTransitionNotApplied('OOMPAH-912: Open was not applied (waiting: transition.recovery_required)')

### Steps to Reproduce
1. Run oompah with `backend:server` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:server` and is recorded by oompah's `error_watcher`:

> Update issue API error: TaskTransitionNotApplied('OOMPAH-912: Open was not applied (waiting: transition.recovery_required)')

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
- fingerprint: 57090f8aa43a1853
- dedup_fingerprint: 57090f8aa43a1853

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-08 14:37
---
Direct owner fix in progress on the systemic composition branch. This task is the error-watcher symptom of expected durable transition contention. The server now classifies transition.owner_active and transition.recovery_required as retryable HTTP 409 warnings instead of unexpected ERROR logs, so ordinary contention cannot auto-file another backend bug. Focused classification/API tests pass.
---
<!-- COMMENTS:END -->
