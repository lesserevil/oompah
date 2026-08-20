---
id: OOMPAH-1208
type: bug
status: Open
priority: 2
title: '[backend:server] Update issue API error: TaskTransitionNotApplied(''OOMPAH-1207:
  In Progress was not applied (rejected: transition.project_owner_authority_required)'')'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T02:29:16.227300Z'
updated_at: '2026-08-20T22:49:13.513633Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.lifecycle_revision: 1
oompah.last_batch:
  batch_id: batch-41327bd44d2248989351b0a98c84746f
  actor: shedwards
  committed_at: '2026-08-18T16:18:18.970327Z'
  operation:
    kind: whole_column_move
    source_status: Backlog
    scope: flat_board
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 998ce95ba12f7e832767ff72b99ec94e78774b27f02a04aecaf3771fc670f260
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 04b178d0454167e7228077275f568e2bab399fcec7cbe1f0c2c62cbf1a8b78de:56498
  claim_owner: b0161d82-55d7-4b08-9b68-ee54b4e13c9c
  claimed_at: '2026-08-20T22:48:14.652845+00:00'
  claim_expires_at: '2026-08-20T23:18:14.652845+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 9396ee2f-9e23-436a-a9b2-a6bef7a86278
oompah.work_contributors:
  runs:
  - run_id: 12d48da69be547e6aea00cc996fbdf9c--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1208
    source_sha: null
    completed_at: ''
---
## Summary

### Problem
Oompah detected a backend error from `backend:server`:

> Update issue API error: TaskTransitionNotApplied('OOMPAH-1207: In Progress was not applied (rejected: transition.project_owner_authority_required)')

### Steps to Reproduce
1. Run oompah with `backend:server` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:server` and is recorded by oompah's `error_watcher`:

> Update issue API error: TaskTransitionNotApplied('OOMPAH-1207: In Progress was not applied (rejected: transition.project_owner_authority_required)')

### Expected Behavior
The operation in `backend:server` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Acceptance Criteria
- The error from `backend:server` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: proj-14849f1b
- tracker: provenanceguardedtracker
- tracker_kind: provenanceguardedtracker
- fingerprint: 2c611bab27fded44
- dedup_fingerprint: 2c611bab27fded44

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 16:49
---
Duplicate error_watcher occurrence suppressed; this task already tracks the same dedup fingerprint.

Source: `backend:server`

Message: Update issue API error: TaskTransitionNotApplied('OOMPAH-1251: In Progress was not applied (rejected: transition.project_owner_authority_required)')
---
author: oompah
created: 2026-08-13 22:41
---
Duplicate error_watcher occurrence suppressed; this task already tracks the same dedup fingerprint.

Source: `backend:server`

Message: Update issue API error: TaskTransitionNotApplied('OOMPAH-1258: In Progress was not applied (rejected: transition.project_owner_authority_required)')
---
author: oompah
created: 2026-08-20 22:48
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-20 22:49
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
