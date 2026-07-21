---
id: OOMPAH-316
type: bug
status: Proposed
priority: 2
title: '[backend:server] Fetch issues failed for project exocomp: State branch ''oompah/state/proj-c260b117''
  does not exist locally or at origin/''oompah/state/proj-c260b117''. Run the bootstrap
  or migration ...'
parent: null
children: []
blocked_by: []
labels:
- external:github
assignee: null
created_at: '2026-07-21T18:20:20.146747Z'
updated_at: '2026-07-21T18:20:21.577295Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#471
  owner: lesserevil
  repo: oompah
  number: '471'
  url: https://github.com/lesserevil/oompah/issues/471
  requestor_login: lesserevil
  imported_comment_ids: []
  last_synced_status: Proposed
  last_synced_at: '2026-07-21T18:20:20.318734+00:00'
---
## Summary

### Problem
Oompah detected a backend error from `backend:server`:

> Fetch issues failed for project exocomp: State branch 'oompah/state/proj-c260b117' does not exist locally or at origin/'oompah/state/proj-c260b117'. Run the bootstrap or migration flow to create it before enabling state_branch_enabled=True for this project. Normal tracker reads must not create remote branches.

### Steps to Reproduce
1. Run oompah with `backend:server` active.
2. Let oompah execute the operation that involves `backend:server` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:server` and is recorded by oompah's `error_watcher`:

> Fetch issues failed for project exocomp: State branch 'oompah/state/proj-c260b117' does not exist locally or at origin/'oompah/state/proj-c260b117'. Run the bootstrap or migration flow to create it before enabling state_branch_enabled=True for this project. Normal tracker reads must not create remote branches.

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
- fingerprint: 9a803f3b8b56abc0
- dedup_fingerprint: 9a803f3b8b56abc0
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue
- URL: https://github.com/lesserevil/oompah/issues/471
- Requestor: @lesserevil
- Reference: lesserevil/oompah#471

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

