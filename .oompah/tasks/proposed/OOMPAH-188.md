---
id: OOMPAH-188
type: task
status: Proposed
priority: null
title: '[backend:webhooks] WebhookForwarder: disabling webhook forwarding for project
  coroot: gh: Resource not accessible by personal access token (HTTP 403)'
parent: null
children: []
blocked_by: []
labels:
- external:github
assignee: null
created_at: '2026-07-13T14:19:41.967141Z'
updated_at: '2026-07-13T14:19:44.431129Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#409
  owner: lesserevil
  repo: oompah
  number: '409'
  url: https://github.com/lesserevil/oompah/issues/409
  requestor_login: NVShawn
  imported_comment_ids: []
  last_synced_status: Proposed
  last_synced_at: '2026-07-13T14:19:43.724087+00:00'
---
## Summary

### Problem
Oompah detected a backend error from `backend:webhooks`:

> WebhookForwarder: disabling webhook forwarding for project coroot: gh: Resource not accessible by personal access token (HTTP 403)

### Steps to Reproduce
1. Run oompah with `backend:webhooks` active.
2. Let oompah execute the operation that involves `backend:webhooks` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:webhooks` and is recorded by oompah's `error_watcher`:

> WebhookForwarder: disabling webhook forwarding for project coroot: gh: Resource not accessible by personal access token (HTTP 403)

### Expected Behavior
The operation in `backend:webhooks` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Acceptance Criteria
- The error from `backend:webhooks` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: 19757d16e7ee9e94
- dedup_fingerprint: 19757d16e7ee9e94
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue
- URL: https://github.com/lesserevil/oompah/issues/409
- Requestor: @NVShawn
- Reference: lesserevil/oompah#409

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

