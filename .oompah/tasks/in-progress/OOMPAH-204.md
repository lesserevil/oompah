---
id: OOMPAH-204
type: bug
status: In Progress
priority: 2
title: "[backend:server] Update issue API error: Cannot sync native tracker: git merge\
  \ --ff-only origin/main failed: hint: Diverging branches can't be fast-forwarded,\
  \ you need to either:\nhint:\nhint: \tgit m..."
parent: null
children: []
blocked_by: []
labels:
- external:github
assignee: null
created_at: '2026-07-13T20:02:50.911753Z'
updated_at: '2026-07-13T20:09:16.686689Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#415
  owner: lesserevil
  repo: oompah
  number: '415'
  url: https://github.com/lesserevil/oompah/issues/415
  requestor_login: lesserevil
  imported_comment_ids: []
  last_synced_status: In Progress
  last_synced_at: '2026-07-13T20:09:16.012723+00:00'
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
  last_validated_at: '2026-07-13T20:03:01.977732+00:00'
oompah.agent_run_id: 2d3ab2f7-41f9-4f68-9924-7c6720275aa0
---
## Summary

### Problem

Oompah detected a backend error from `backend:server`:

> Update issue API error: Cannot sync native tracker: git merge --ff-only origin/main failed: hint: Diverging branches can't be fast-forwarded, you need to either:
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

> Update issue API error: Cannot sync native tracker: git merge --ff-only origin/main failed: hint: Diverging branches can't be fast-forwarded, you need to either:
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
- fingerprint: f289e9452f5913f0
- dedup_fingerprint: f289e9452f5913f0
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue

- URL: https://github.com/lesserevil/oompah/issues/415
- Requestor: @lesserevil
- Reference: lesserevil/oompah#415

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 20:04
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-13 20:04
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 20:04
---
Understanding: This bug reports that the native tracker sync fails with a git fast-forward error when the local 'main' branch has diverged from origin. The error is caught by error_watcher and auto-filed. My role as Duplicate Investigator is to check whether this is a duplicate of a previously-handled issue before doing any implementation work. Starting search now.
---
author: oompah
created: 2026-07-13 20:05
---
Accepted as the durable native-tracker synchronization fix. Scope: serialize the entire prepare→write→commit→push transaction across processes, automatically rebase a local pending tracker commit when a concurrent remote tracker commit arrives, abort cleanly on genuine conflicts, and add regression tests for both recovery and conflict paths. This replaces the current ff-only failure for normal concurrent tracker writes.
---
<!-- COMMENTS:END -->
