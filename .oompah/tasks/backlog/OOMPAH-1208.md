---
id: OOMPAH-1208
type: bug
status: Backlog
priority: 2
title: '[backend:server] Update issue API error: TaskTransitionNotApplied(''OOMPAH-1207:
  In Progress was not applied (rejected: transition.project_owner_authority_required)'')'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T02:29:16.227300Z'
updated_at: '2026-08-13T22:41:56.984295Z'
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

> Update issue API error: TaskTransitionNotApplied('OOMPAH-1207: In Progress was not applied (rejected: transition.project_owner_authority_required)')

### Steps to Reproduce
1. Run oompah with `backend:server` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:server` and is recorded by oompah's `error_watcher`:

> Update issue API error: TaskTransitionNotApplied('OOMPAH-1207: In Progress was not applied (rejected: transition.project_owner_authority_required)')

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
- fingerprint: 2c611bab27fded44
- dedup_fingerprint: 2c611bab27fded44

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 16:49
---
Duplicate error_watcher occurrence suppressed; this task already tracks the same dedup fingerprint.

Source: `backend:server`

Message: Update issue API error: TaskTransitionNotApplied('OOMPAH-1251: In Progress was not applied (rejected: transition.project_owner_authority_required)')
---
author: oompah
created: 2026-08-13 22:41
---
Duplicate error_watcher occurrence suppressed; this task already tracks the same dedup fingerprint.

Source: `backend:server`

Message: Update issue API error: TaskTransitionNotApplied('OOMPAH-1258: In Progress was not applied (rejected: transition.project_owner_authority_required)')
---
<!-- COMMENTS:END -->
