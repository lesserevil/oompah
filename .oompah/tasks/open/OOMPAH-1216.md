---
id: OOMPAH-1216
type: bug
status: Open
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=TRICKLE-136 identifier=TRICKLE-136 run_id=b556f246ba9f4b658b4f5218d3a5623b
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T04:00:51.761397Z'
updated_at: '2026-08-21T00:02:35.252413Z'
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
  task_fingerprint: 32253cf75d3113fe58d71baeb2d8b417a0284c71e8b5a36d257ad1be48ea106f
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 401212dc257ea401fdf002fb19b06e268036bc53cef84090a4035982afc65bba:142466
  claim_owner: b0161d82-55d7-4b08-9b68-ee54b4e13c9c
  claimed_at: '2026-08-21T00:02:18.195640+00:00'
  claim_expires_at: '2026-08-21T00:32:18.195640+00:00'
  retry_count: 1
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 30bc34d4-924b-4b7b-861d-f2f337c2809a
oompah.work_contributors:
  runs:
  - run_id: 7d692e02f8fb4053ad98f70b1a6f2764--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1216
    source_sha: null
    completed_at: ''
  - run_id: 7d692e02f8fb4053ad98f70b1a6f2764--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1216
    source_sha: null
    completed_at: ''
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=TRICKLE-136 identifier=TRICKLE-136 run_id=b556f246ba9f4b658b4f5218d3a5623b timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=TRICKLE-136 identifier=TRICKLE-136 run_id=b556f246ba9f4b658b4f5218d3a5623b timeout_seconds=5.0

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
- fingerprint: 2b11cbe8b5e4a6a0
- dedup_fingerprint: 2b11cbe8b5e4a6a0

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-20 22:56
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-20 22:57
---
Run #1 [attempt=1, profile=default, role=— -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 25s
---
author: oompah
created: 2026-08-21 00:02
---
Duplicate screening dispatched (profile: default, task remains Open)
---
<!-- COMMENTS:END -->
