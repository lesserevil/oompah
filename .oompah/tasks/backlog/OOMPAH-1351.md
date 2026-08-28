---
id: OOMPAH-1351
type: bug
status: Backlog
priority: 2
title: '[backend:__main__] Workflow reload failed: WorkflowError(''Workflow file not
  found: /home/shedwards/src/oompah/WORKFLOW.md'')'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-28T01:26:34.676723Z'
updated_at: '2026-08-28T01:26:34.676723Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

### Problem
Oompah detected a backend error from `backend:__main__`:

> Workflow reload failed: WorkflowError('Workflow file not found: /home/shedwards/src/oompah/WORKFLOW.md')

### Steps to Reproduce
1. Run oompah with `backend:__main__` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:__main__` and is recorded by oompah's `error_watcher`:

> Workflow reload failed: WorkflowError('Workflow file not found: /home/shedwards/src/oompah/WORKFLOW.md')

### Expected Behavior
The operation in `backend:__main__` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Acceptance Criteria
- The error from `backend:__main__` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: proj-14849f1b
- tracker: provenanceguardedtracker
- tracker_kind: provenanceguardedtracker
- fingerprint: f35d40c256251584
- dedup_fingerprint: f35d40c256251584

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

