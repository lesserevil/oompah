---
id: OOMPAH-268
type: bug
status: Proposed
priority: 2
title: '[backend:server] Add comment API error: git add .oompah/tasks failed: fatal:
  Unable to create ''/home/shedwards/.oompah/repos/oompah/.git/index.lock'': File
  exists.


  Another git process seems to be r...'
parent: null
children: []
blocked_by: []
labels:
- external:github
assignee: null
created_at: '2026-07-20T16:52:04.570031Z'
updated_at: '2026-07-20T16:52:04.570031Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

### Problem
Oompah detected a backend error from `backend:server`:

> Add comment API error: git add .oompah/tasks failed: fatal: Unable to create '/home/shedwards/.oompah/repos/oompah/.git/index.lock': File exists.

Another git process seems to be running in this repository, e.g.
an editor opened by 'git commit'. Please make sure all processes
are terminated then try again. If it still fails, a git process
may have crashed in this repository earlier:
remove the file manually to continue.

### Steps to Reproduce
1. Run oompah with `backend:server` active.
2. Let oompah execute the operation that involves `backend:server` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:server` and is recorded by oompah's `error_watcher`:

> Add comment API error: git add .oompah/tasks failed: fatal: Unable to create '/home/shedwards/.oompah/repos/oompah/.git/index.lock': File exists.

Another git process seems to be running in this repository, e.g.
an editor opened by 'git commit'. Please make sure all processes
are terminated then try again. If it still fails, a git process
may have crashed in this repository earlier:
remove the file manually to continue.

### Expected Behavior
The operation in `backend:server` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Acceptance Criteria
- The error from `backend:server` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: bed1bd7effec3bb8
- dedup_fingerprint: bed1bd7effec3bb8
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue
- URL: https://github.com/lesserevil/oompah/issues/454
- Requestor: @NVShawn
- Reference: lesserevil/oompah#454

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

