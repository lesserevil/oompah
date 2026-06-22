---
id: OOMPAH-50
type: bug
status: Archived
priority: 2
title: '[backend:webhooks] WebhookForwarder: disabling webhook forwarding for project
  oompah: gh: Not Found (HTTP 404)'
parent: null
children: []
blocked_by: []
labels:
- external:github
assignee: null
created_at: '2026-06-22T13:53:15.245662Z'
updated_at: '2026-06-22T14:59:18.775794Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.intake:
  missing_fields:
  - acceptance_criteria
  - actual_behavior
  - expected_behavior
  - problem_statement
  - reproduction_steps
  scope: small
  requestor_approved: false
  requestor_approved_at: null
  requestor_actor: null
  owner_override: false
  owner_override_at: null
  owner_actor: null
  decomposition_status: not_needed
  proposal_fingerprint: null
  last_validator_result: fail
  last_validated_at: '2026-06-22T13:53:16.519647+00:00'
oompah.external.github:
  id: lesserevil/oompah#347
  owner: lesserevil
  repo: oompah
  number: '347'
  url: https://github.com/lesserevil/oompah/issues/347
  requestor_login: lesserevil
  imported_comment_ids: []
  last_synced_status: Archived
  last_synced_at: '2026-06-22T14:59:11.969444+00:00'
  last_github_state: closed
---
## Summary

## Problem
Oompah detected a backend error from `backend:webhooks`:

> WebhookForwarder: disabling webhook forwarding for project oompah: gh: Not Found (HTTP 404)

## Steps to Reproduce
1. Run oompah with `backend:webhooks` active.
2. Let oompah execute the operation that involves `backend:webhooks` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

## Actual Behavior
An error occurs in `backend:webhooks` and is recorded by oompah's `error_watcher`:

> WebhookForwarder: disabling webhook forwarding for project oompah: gh: Not Found (HTTP 404)

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
- URL: https://github.com/lesserevil/oompah/issues/347
- Requestor: @lesserevil
- Reference: lesserevil/oompah#347

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-22 14:50
---
Archived as a duplicate stale auto-filed webhook error. The same dedupe fingerprint also created OOMPAH-51, and the underlying webhook 404 has not recurred since the transient restart window.
---
<!-- COMMENTS:END -->
