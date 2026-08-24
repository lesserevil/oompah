---
id: OOMPAH-1326
type: bug
status: Open
priority: 2
title: '[backend:checkpoint_queue] Checkpoint flush FAILED (reason=debounce); push_failures=1'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-21T09:43:03.353905Z'
updated_at: '2026-08-24T07:38:07.674887Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.lifecycle_revision: 1
oompah.last_batch:
  batch_id: batch-406b98cf5aef4911b932a9c5924b23e6
  actor: shedwards
  committed_at: '2026-08-24T02:44:47.015459Z'
  operation:
    kind: whole_column_move
    source_status: Backlog
    scope: flat_board
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: e4576ce6189d04a26a3467a9f7d74a2b2ced0246c5aa75d275d841c72f16c43a
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 248f9b2ac5db257a6c84a532ad1530a711cc4f95181665b2a5d89de891e409c8:166229
  claim_owner: 11327615-6fad-46c0-ac4f-081c79ea0c4f
  claimed_at: '2026-08-24T07:36:46.543129+00:00'
  claim_expires_at: '2026-08-24T08:06:46.543129+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 9839fa75-b240-4763-b383-ab6242761fa5
oompah.work_contributors:
  runs:
  - run_id: bf3dc3334c60456c997a7ecf3d303c79--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1326
    source_sha: null
    completed_at: ''
---
## Summary

### Problem
Oompah detected a backend error (error class: `checkpoint_queue.flush_failed`) from `backend:checkpoint_queue`:

> Checkpoint flush FAILED (reason=debounce); push_failures=1

### Steps to Reproduce
1. Run oompah with `backend:checkpoint_queue` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:checkpoint_queue` and is recorded by oompah's `error_watcher`:

> Checkpoint flush FAILED (reason=debounce); push_failures=1

### Expected Behavior
The operation in `backend:checkpoint_queue` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Acceptance Criteria
- The error from `backend:checkpoint_queue` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: proj-14849f1b
- tracker: provenanceguardedtracker
- tracker_kind: provenanceguardedtracker
- fingerprint: 4e3f69c045df49d4
- dedup_fingerprint: 4e3f69c045df49d4
- error_class: checkpoint_queue.flush_failed
- incident_key: state_branch:oompah/state/proj-3e4e9214

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-24 07:37
---
Duplicate screening dispatched (profile: default, task remains Open)
---
<!-- COMMENTS:END -->
