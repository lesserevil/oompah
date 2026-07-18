---
id: OOMPAH-234
type: bug
status: In Progress
priority: 2
title: '[backend:webhooks] WebhookForwarder: disabling webhook forwarding for project
  trickle: configured repo_path is missing or not a directory'
parent: null
children: []
blocked_by: []
labels:
- external:github
assignee: null
created_at: '2026-07-18T12:01:21.441371Z'
updated_at: '2026-07-18T12:07:59.525438Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#440
  owner: lesserevil
  repo: oompah
  number: '440'
  url: https://github.com/lesserevil/oompah/issues/440
  requestor_login: lesserevil
  imported_comment_ids: []
  last_synced_status: Proposed
  last_synced_at: '2026-07-18T12:01:23.076436+00:00'
oompah.intake:
  missing_fields: []
  scope: small
  requestor_approved: false
  requestor_approved_at: null
  requestor_actor: null
  owner_override: false
  owner_override_at: null
  owner_actor: null
  decomposition_status: not_needed
  proposal_fingerprint: null
  last_validator_result: pass
  last_validated_at: '2026-07-18T12:01:46.647532+00:00'
oompah.agent_run_id: 507a0dc5-d4e3-48af-8704-6df8c56b3be2
---
## Summary

### Problem

Oompah detected a backend error from `backend:webhooks`:

> WebhookForwarder: disabling webhook forwarding for project trickle: configured repo_path is missing or not a directory

### Desired Behavior

The operation in `backend:webhooks` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Steps to Reproduce

1. Run oompah with `backend:webhooks` active.
2. Let oompah execute the operation that involves `backend:webhooks` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior

An error occurs in `backend:webhooks` and is recorded by oompah's `error_watcher`:

> WebhookForwarder: disabling webhook forwarding for project trickle: configured repo_path is missing or not a directory

### Acceptance Criteria

- The error from `backend:webhooks` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: 622aaaa5848fc5b4
- dedup_fingerprint: 622aaaa5848fc5b4
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue

- URL: https://github.com/lesserevil/oompah/issues/440
- Requestor: @lesserevil
- Reference: lesserevil/oompah#440

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-18 12:07
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-18 12:07
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
