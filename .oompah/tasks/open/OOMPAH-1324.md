---
id: OOMPAH-1324
type: bug
status: Open
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1214 identifier=OOMPAH-1214 run_id=2fa5716a82384dbe921b5bbdfa03ebca
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-21T01:22:19.264494Z'
updated_at: '2026-08-21T05:14:37.318738Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.lifecycle_revision: 1
oompah.last_batch:
  batch_id: batch-6721ed37af5c4e51ae3558e98f499304
  actor: shedwards
  committed_at: '2026-08-21T01:29:59.950511Z'
  operation:
    kind: whole_column_move
    source_status: Backlog
    scope: flat_board
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 3a8911b8fd0197150afbe13302c98fe04b84a220197c2742bd4733ae6429af23
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 38bf177aecd83da7a93860c427ba5aa6432ee07900fa97e95235833ecb45a27d:143347
  claim_owner: 7dbe71d1-9fc2-4b0c-bb54-3da0831c26d5
  claimed_at: '2026-08-21T05:14:08.751984+00:00'
  claim_expires_at: '2026-08-21T05:44:08.751984+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 2fd3741d-d85c-4d30-9674-66a5a7743ebd
oompah.work_contributors:
  runs:
  - run_id: 9d22ecdcb2224f1fb0ac3b62fdc7d6ed--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1324
    source_sha: null
    completed_at: ''
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1214 identifier=OOMPAH-1214 run_id=2fa5716a82384dbe921b5bbdfa03ebca timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1214 identifier=OOMPAH-1214 run_id=2fa5716a82384dbe921b5bbdfa03ebca timeout_seconds=5.0

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
- fingerprint: f87b492954951550
- dedup_fingerprint: f87b492954951550

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 05:14
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 05:14
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
