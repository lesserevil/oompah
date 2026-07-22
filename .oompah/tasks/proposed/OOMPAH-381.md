---
id: OOMPAH-381
type: bug
status: Proposed
priority: 2
title: '[backend:orchestrator] Dispatch loop stale: no tick completed in 1011s (threshold=900s).
  Alert armed, recovery queued.'
parent: null
children: []
blocked_by: []
labels:
- external:github
assignee: null
created_at: '2026-07-22T02:28:32.994193Z'
updated_at: '2026-07-22T02:28:32.994193Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Dispatch loop stale: no tick completed in 1011s (threshold=900s). Alert armed, recovery queued.

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah execute the operation that involves `backend:orchestrator` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Dispatch loop stale: no tick completed in 1011s (threshold=900s). Alert armed, recovery queued.

### Expected Behavior
The operation in `backend:orchestrator` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Acceptance Criteria
- The error from `backend:orchestrator` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: 037927480ab4b5f6
- dedup_fingerprint: 037927480ab4b5f6
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue
- URL: https://github.com/lesserevil/oompah/issues/512
- Requestor: @NVShawn
- Reference: lesserevil/oompah#512

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

