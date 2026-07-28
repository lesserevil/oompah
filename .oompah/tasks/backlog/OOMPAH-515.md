---
id: OOMPAH-515
type: bug
status: Backlog
priority: 2
title: '[backend:server] Add comment API error: Cannot sync state branch ''oompah/state/proj-14849f1b'':
  git fetch origin ''oompah/state/proj-14849f1b'' failed: fatal: unable to access
  ''https://github.com/less...'
parent: null
children: []
blocked_by: []
labels:
- external:github
assignee: null
created_at: '2026-07-28T15:29:11.690903Z'
updated_at: '2026-07-28T15:29:32.586826Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#561
  owner: lesserevil
  repo: oompah
  number: '561'
  url: https://github.com/lesserevil/oompah/issues/561
  requestor_login: NVShawn
  imported_comment_ids: []
  last_synced_status: Backlog
  last_synced_at: '2026-07-28T15:29:30.486137+00:00'
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
  last_validated_at: '2026-07-28T15:29:16.779090+00:00'
---
## Summary

### Problem

Oompah detected a backend error from `backend:server`:

> Add comment API error: Cannot sync state branch 'oompah/state/proj-14849f1b': git fetch origin 'oompah/state/proj-14849f1b' failed: fatal: unable to access 'https://github.com/lesserevil/oompah.git/': Could not resolve host: github.com. Remediation: verify network access and remote URL (git remote get-url origin).

### Desired Behavior

The operation in `backend:server` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Steps to Reproduce

1. Run oompah with `backend:server` active.
2. Let oompah execute the operation that involves `backend:server` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior

An error occurs in `backend:server` and is recorded by oompah's `error_watcher`:

> Add comment API error: Cannot sync state branch 'oompah/state/proj-14849f1b': git fetch origin 'oompah/state/proj-14849f1b' failed: fatal: unable to access 'https://github.com/lesserevil/oompah.git/': Could not resolve host: github.com. Remediation: verify network access and remote URL (git remote get-url origin).

### Acceptance Criteria

- The error from `backend:server` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: 46794e4200057267
- dedup_fingerprint: 46794e4200057267
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue

- URL: https://github.com/lesserevil/oompah/issues/561
- Requestor: @NVShawn
- Reference: lesserevil/oompah#561

## Notes


