---
id: OOMPAH-378
type: bug
status: Backlog
priority: 2
title: '[backend:orchestrator] Dispatch loop stale: no tick completed in 989s (threshold=900s).
  Alert armed, recovery queued.'
parent: null
children: []
blocked_by: []
labels:
- external:github
assignee: null
created_at: '2026-07-22T02:28:03.535030Z'
updated_at: '2026-07-22T02:37:40.731218Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#508
  owner: lesserevil
  repo: oompah
  number: '508'
  url: https://github.com/lesserevil/oompah/issues/508
  requestor_login: NVShawn
  imported_comment_ids: []
  last_synced_status: Backlog
  last_synced_at: '2026-07-22T02:37:40.004798+00:00'
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
  last_validated_at: '2026-07-22T02:30:02.710508+00:00'
---
## Summary

### Problem

Oompah detected a backend error from `backend:orchestrator`:

> Dispatch loop stale: no tick completed in 989s (threshold=900s). Alert armed, recovery queued.

### Desired Behavior

The operation in `backend:orchestrator` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Steps to Reproduce

1. Run oompah with `backend:orchestrator` active.
2. Let oompah execute the operation that involves `backend:orchestrator` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior

An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Dispatch loop stale: no tick completed in 989s (threshold=900s). Alert armed, recovery queued.

### Acceptance Criteria

- The error from `backend:orchestrator` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: 4b503308bcafc2c8
- dedup_fingerprint: 4b503308bcafc2c8
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue

- URL: https://github.com/lesserevil/oompah/issues/508
- Requestor: @NVShawn
- Reference: lesserevil/oompah#508

## Notes


