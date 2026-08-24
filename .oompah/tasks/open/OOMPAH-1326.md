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
updated_at: '2026-08-24T11:10:52.220423Z'
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
  claim_id: c69ecd462df35c95949ca1824450ead7895c26047c14f960dae80d1a729ebd14:166802
  claim_owner: bfade983-ab08-4226-b737-1b82ab83e6ed
  claimed_at: '2026-08-24T11:09:52.803874+00:00'
  claim_expires_at: '2026-08-24T11:39:52.803874+00:00'
  retry_count: 1
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: c66e1eb6-f1f0-400c-9d50-a39e87485b80
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
  - run_id: 0d7d9548b88847619e9f165317d9174c--contributor-4256b9f40773
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
author: oompah
created: 2026-08-24 07:38
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-24 07:38
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: interrupted, Duration: 1m 10s
- Log: OOMPAH-1326__20260824T073823Z.jsonl
---
author: oompah
created: 2026-08-24 11:10
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-24 11:10
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
