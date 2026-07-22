---
id: OOMPAH-375
type: bug
status: Proposed
priority: 2
title: '[backend:orchestrator] Dispatch loop stale: no tick completed in 971s (threshold=900s).
  Alert armed, recovery queued.'
parent: null
children: []
blocked_by: []
labels:
- external:github
assignee: null
created_at: '2026-07-22T02:27:28.216091Z'
updated_at: '2026-07-22T02:27:29.017631Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#505
  owner: lesserevil
  repo: oompah
  number: '505'
  url: https://github.com/lesserevil/oompah/issues/505
  requestor_login: NVShawn
  imported_comment_ids: []
  last_synced_status: Proposed
  last_synced_at: '2026-07-22T02:27:28.342598+00:00'
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Dispatch loop stale: no tick completed in 971s (threshold=900s). Alert armed, recovery queued.

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah execute the operation that involves `backend:orchestrator` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Dispatch loop stale: no tick completed in 971s (threshold=900s). Alert armed, recovery queued.

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
- fingerprint: 8efe8a98da9aa250
- dedup_fingerprint: 8efe8a98da9aa250
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue
- URL: https://github.com/lesserevil/oompah/issues/505
- Requestor: @NVShawn
- Reference: lesserevil/oompah#505

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

