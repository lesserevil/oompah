---
id: OOMPAH-191
type: bug
status: Proposed
priority: 2
title: "[backend:server] Create issue API error: Cannot sync native tracker: git merge\
  \ --ff-only origin/main failed: hint: Diverging branches can't be fast-forwarded,\
  \ you need to either:\nhint:\nhint: \tgit m..."
parent: null
children: []
blocked_by: []
labels:
- external:github
assignee: null
created_at: '2026-07-13T15:36:21.282670Z'
updated_at: '2026-07-13T15:36:50.700668Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#412
  owner: lesserevil
  repo: oompah
  number: '412'
  url: https://github.com/lesserevil/oompah/issues/412
  requestor_login: lesserevil
  imported_comment_ids: []
  last_synced_status: Proposed
  last_synced_at: '2026-07-13T15:36:23.025858+00:00'
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
  last_validated_at: '2026-07-13T15:36:50.038650+00:00'
---
## Summary

### Problem

Oompah detected a backend error from `backend:server`:

> Create issue API error: Cannot sync native tracker: git merge --ff-only origin/main failed: hint: Diverging branches can't be fast-forwarded, you need to either:
hint:
hint: 	git merge --no-ff
hint:
hint: or:
hint:
hint: 	git rebase
hint:
hint: Disable this message with "git config set advice.diverging false"
fatal: Not possible to fast-forward, aborting.. Remediation: the local 'main' branch has diverged from origin. Run: git fetch origin && git merge --ff-only origin/main

### Desired Behavior

The operation in `backend:server` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Steps to Reproduce

1. Run oompah with `backend:server` active.
2. Let oompah execute the operation that involves `backend:server` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior

An error occurs in `backend:server` and is recorded by oompah's `error_watcher`:

> Create issue API error: Cannot sync native tracker: git merge --ff-only origin/main failed: hint: Diverging branches can't be fast-forwarded, you need to either:
hint:
hint: 	git merge --no-ff
hint:
hint: or:
hint:
hint: 	git rebase
hint:
hint: Disable this message with "git config set advice.diverging false"
fatal: Not possible to fast-forward, aborting.. Remediation: the local 'main' branch has diverged from origin. Run: git fetch origin && git merge --ff-only origin/main

### Acceptance Criteria

- The error from `backend:server` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: da010b80848fc70a
- dedup_fingerprint: da010b80848fc70a
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue

- URL: https://github.com/lesserevil/oompah/issues/412
- Requestor: @lesserevil
- Reference: lesserevil/oompah#412

## Notes


