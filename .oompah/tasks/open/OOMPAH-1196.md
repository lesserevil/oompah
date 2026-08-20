---
id: OOMPAH-1196
type: bug
status: Open
priority: 2
title: '[backend:orchestrator] ACP worker failed issue_id=TRICKLE-135'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-12T23:56:27.547026Z'
updated_at: '2026-08-20T22:37:58.161348Z'
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
  task_fingerprint: edc5b40bf21157962c4ba67005472a908500731b47d6391494553b14e8edc3b6
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 224067b6bdb33796c28829e33a8c6a2d18b83aa317c5e2aa8e23015f38f42d18:56489
  claim_owner: b0161d82-55d7-4b08-9b68-ee54b4e13c9c
  claimed_at: '2026-08-20T22:37:34.332959+00:00'
  claim_expires_at: '2026-08-20T23:07:34.332959+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 28111f5d-d8b2-4d16-838a-2efa2647cee4
oompah.work_contributors:
  runs:
  - run_id: 71b1976e1cee4120b339e39218832094--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1196
    source_sha: null
    completed_at: ''
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> ACP worker failed issue_id=TRICKLE-135

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> ACP worker failed issue_id=TRICKLE-135

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
- fingerprint: 1bc81be69915050f
- dedup_fingerprint: 1bc81be69915050f
- source_issue: TRICKLE-135

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 00:17
---
Duplicate task-specific occurrence of OOMPAH-1194. The canonical fix covers this failure: managed network Git used the stale local SSH origin instead of the project's configured HTTPS repo_url during Trickle workspace/epic refresh.
---
author: oompah
created: 2026-08-20 22:37
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-20 22:37
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
