---
id: OOMPAH-267
type: bug
status: Proposed
priority: 2
title: "[backend:server] Add comment API error: git commit -m Comment on oompah task\
  \ OOMPAH-266\n\n\U0001F916 Generated with https://github.com/lesserevil/oompah\n\
  \nCo-authored-by: oompah <lesserevil@users.noreply.gith..."
parent: null
children: []
blocked_by: []
labels:
- external:github
assignee: null
created_at: '2026-07-20T16:51:11.086624Z'
updated_at: '2026-07-20T16:51:11.086624Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

### Problem
Oompah detected a backend error from `backend:server`:

> Add comment API error: git commit -m Comment on oompah task OOMPAH-266

🤖 Generated with https://github.com/lesserevil/oompah

Co-authored-by: oompah <lesserevil@users.noreply.github.com>
 failed: fatal: cannot lock ref 'HEAD': is at df6135ea58c6e6bdac8de56169bce64f2ca953c8 but expected 46558c30aa2ea303df139557c48067ceee30bc53

### Steps to Reproduce
1. Run oompah with `backend:server` active.
2. Let oompah execute the operation that involves `backend:server` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:server` and is recorded by oompah's `error_watcher`:

> Add comment API error: git commit -m Comment on oompah task OOMPAH-266

🤖 Generated with https://github.com/lesserevil/oompah

Co-authored-by: oompah <lesserevil@users.noreply.github.com>
 failed: fatal: cannot lock ref 'HEAD': is at df6135ea58c6e6bdac8de56169bce64f2ca953c8 but expected 46558c30aa2ea303df139557c48067ceee30bc53

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
- fingerprint: ec0c2cce6c7d7177
- dedup_fingerprint: ec0c2cce6c7d7177
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue
- URL: https://github.com/lesserevil/oompah/issues/453
- Requestor: @NVShawn
- Reference: lesserevil/oompah#453

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

