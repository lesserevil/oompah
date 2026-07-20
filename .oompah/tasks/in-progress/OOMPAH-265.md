---
id: OOMPAH-265
type: bug
status: In Progress
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
updated_at: '2026-07-20T16:55:15.461968Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#451
  owner: lesserevil
  repo: oompah
  number: '451'
  url: https://github.com/lesserevil/oompah/issues/451
  requestor_login: NVShawn
  imported_comment_ids: []
  last_synced_status: Backlog
  last_synced_at: '2026-07-20T16:52:16.704135+00:00'
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
  last_validated_at: '2026-07-20T16:48:52.593601+00:00'
oompah.agent_run_id: c0fee581-ca37-4991-a643-2c0169652eb0
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

### Desired Behavior

The operation in `backend:server` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

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

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-20 16:55
---
Agent dispatched (profile: default)
---
<!-- COMMENTS:END -->
