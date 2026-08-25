---
id: OOMPAH-1337
type: bug
status: Open
priority: 2
title: '[backend:orchestrator] Orchestrator shutdown attempt failed; retaining process
  and retrying'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-25T02:00:38.960190Z'
updated_at: '2026-08-25T20:22:56.931409Z'
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
  task_fingerprint: b0fea8ad252458e77fc29329780a841b70f885e885291d709f35db68e731a103
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 258280db133b35cd5a33f25f101577e80a7cd0e9d8edb216f14b8fe1e22097f0:168472
  claim_owner: a40199ea-9091-4b96-87de-6f33f559f142
  claimed_at: '2026-08-25T20:22:18.359510+00:00'
  claim_expires_at: '2026-08-25T20:52:18.359510+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: ed3a6a2b-bed9-4786-99a6-401ac5e55cb7
oompah.work_contributors:
  runs:
  - run_id: ad5ad528f8494b5497ad9ed59b4a313c--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1337
    source_sha: null
    completed_at: ''
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Orchestrator shutdown attempt failed; retaining process and retrying

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Orchestrator shutdown attempt failed; retaining process and retrying

### Expected Behavior
The operation in `backend:orchestrator` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Acceptance Criteria
- The error from `backend:orchestrator` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: proj-14849f1b
- tracker: provenanceguardedtracker
- tracker_kind: provenanceguardedtracker
- fingerprint: 9984037ce1db983d
- dedup_fingerprint: 9984037ce1db983d

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-25 20:22
---
Duplicate screening dispatched (profile: default, task remains Open)
---
<!-- COMMENTS:END -->
