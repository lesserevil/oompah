---
id: OOMPAH-78
type: task
status: Proposed
priority: null
title: '[backend:webhooks] WebhookForwarder: disabling webhook forwarding for project
  trickle: gh: Not Found (HTTP 404)'
parent: null
children: []
blocked_by: []
labels:
- external:github
assignee: null
created_at: '2026-06-24T15:45:11.715568Z'
updated_at: '2026-06-24T15:45:11.715568Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

## Problem
Oompah detected a backend error from `backend:webhooks`:

> WebhookForwarder: disabling webhook forwarding for project trickle: gh: Not Found (HTTP 404)

## Steps to Reproduce
1. Run oompah with `backend:webhooks` active.
2. Let oompah execute the operation that involves `backend:webhooks` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

## Actual Behavior
An error occurs in `backend:webhooks` and is recorded by oompah's `error_watcher`:

> WebhookForwarder: disabling webhook forwarding for project trickle: gh: Not Found (HTTP 404)

## Expected Behavior
The operation in `backend:webhooks` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

## Acceptance Criteria
- The error from `backend:webhooks` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: fab624f77cb2c7ae
- dedup_fingerprint: fab624f77cb2c7ae
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue
- URL: https://github.com/lesserevil/oompah/issues/364
- Requestor: @NVShawn
- Reference: lesserevil/oompah#364

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

