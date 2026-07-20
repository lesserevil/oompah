---
id: OOMPAH-265
type: bug
status: Proposed
priority: 2
title: "[backend:server] Create issue API error: git push origin HEAD:main failed:\
  \ remote: Bypassed rule violations for refs/heads/main:        \nremote: \nremote:\
  \ - 3 of 3 required status checks are expecte..."
parent: null
children: []
blocked_by: []
labels:
- external:github
assignee: null
created_at: '2026-07-20T16:48:39.964670Z'
updated_at: '2026-07-20T16:48:39.964670Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

### Problem
Oompah detected a backend error from `backend:server`:

> Create issue API error: git push origin HEAD:main failed: remote: Bypassed rule violations for refs/heads/main:        
remote: 
remote: - 3 of 3 required status checks are expected.        
remote: 
To https://github.com/lesserevil/oompah.git
 ! [remote rejected]   HEAD -> main (cannot lock ref 'refs/heads/main': is at 0a970ee6253d1705ec68ed6b2d8b67b34abc90f6 but expected 5ff1a2f5dc54b652b570b5ba9753f4b854334998)
error: failed to push some refs to 'https://github.com/lesserevil/oompah.git'

### Steps to Reproduce
1. Run oompah with `backend:server` active.
2. Let oompah execute the operation that involves `backend:server` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:server` and is recorded by oompah's `error_watcher`:

> Create issue API error: git push origin HEAD:main failed: remote: Bypassed rule violations for refs/heads/main:        
remote: 
remote: - 3 of 3 required status checks are expected.        
remote: 
To https://github.com/lesserevil/oompah.git
 ! [remote rejected]   HEAD -> main (cannot lock ref 'refs/heads/main': is at 0a970ee6253d1705ec68ed6b2d8b67b34abc90f6 but expected 5ff1a2f5dc54b652b570b5ba9753f4b854334998)
error: failed to push some refs to 'https://github.com/lesserevil/oompah.git'

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
- fingerprint: d5eadc888bec39d3
- dedup_fingerprint: d5eadc888bec39d3
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue
- URL: https://github.com/lesserevil/oompah/issues/451
- Requestor: @NVShawn
- Reference: lesserevil/oompah#451

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

