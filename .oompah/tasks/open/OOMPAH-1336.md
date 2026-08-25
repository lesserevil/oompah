---
id: OOMPAH-1336
type: bug
status: Open
priority: 2
title: '[backend:__main__] Orchestrator thread crashed'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-25T02:00:36.934588Z'
updated_at: '2026-08-25T20:22:59.683636Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.lifecycle_revision: 1
oompah.last_batch:
  batch_id: batch-6f0e83c8e44c413d864c213fbfd4e455
  actor: shedwards
  committed_at: '2026-08-25T17:51:56.061271Z'
  operation:
    kind: whole_column_move
    source_status: Backlog
    scope: flat_board
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: d970c5a99d9e4a723dbeaa5a7bb673be75e9f5ba7fd3e567bdb79bfc2e2a52f8
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: ae17dee977531c2746553f640d44774812bc018554414597ed8c6a48cb7ad66c:168471
  claim_owner: a40199ea-9091-4b96-87de-6f33f559f142
  claimed_at: '2026-08-25T20:21:43.091154+00:00'
  claim_expires_at: '2026-08-25T20:51:43.091154+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: c0fa4f0d-6e00-4410-a62f-ecd099b2244e
oompah.work_contributors:
  runs:
  - run_id: 1e4dabd6f33e43c995b0862f2e1c217d--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1336
    source_sha: null
    completed_at: ''
---
## Summary

### Problem
Oompah detected a backend error from `backend:__main__`:

> Orchestrator thread crashed

### Steps to Reproduce
1. Run oompah with `backend:__main__` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:__main__` and is recorded by oompah's `error_watcher`:

> Orchestrator thread crashed

### Expected Behavior
The operation in `backend:__main__` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Acceptance Criteria
- The error from `backend:__main__` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: proj-14849f1b
- tracker: provenanceguardedtracker
- tracker_kind: provenanceguardedtracker
- fingerprint: 3eb8662f89d42022
- dedup_fingerprint: 3eb8662f89d42022

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-25 20:21
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-25 20:22
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
