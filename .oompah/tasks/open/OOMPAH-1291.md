---
id: OOMPAH-1291
type: bug
status: Open
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1198 identifier=OOMPAH-1198 run_id=e0cde964aac043d8bb75d82717a085ba
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-20T23:34:19.692606Z'
updated_at: '2026-08-21T16:39:04.505144Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.lifecycle_revision: 1
oompah.last_batch:
  batch_id: batch-1c1d234dcdd64c5ba5a90080c24b1e3a
  actor: shedwards
  committed_at: '2026-08-21T00:45:50.707738Z'
  operation:
    kind: whole_column_move
    source_status: Backlog
    scope: flat_board
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: e17da9c2200f41f0d0f92ba6286096711fbb495363c52eadbee55eb77866b8e4
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 7bb3fd71f35dff7bea72cc7ad419ea024154c6688497dd3e6dad5c323da65ce4:147409
  claim_owner: 8b3bb5f8-8d0e-4cf3-9d62-5bd5932d676d
  claimed_at: '2026-08-21T16:38:07.964248+00:00'
  claim_expires_at: '2026-08-21T17:08:07.964248+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 5e3603f3-6899-4578-89a5-a2ac951dbba4
oompah.work_contributors:
  runs:
  - run_id: 45fd4c2be5ff4f97897a885afe7b3993--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1291
    source_sha: null
    completed_at: ''
  - run_id: 7ed7953cb52b4889a493480e70cd08c8--contributor-86e3ac8153e1
    provider_id: prov-6cf41c89
    provider_name: Opencode/Switchyard
    model_id: switchyard/auto
    focus: duplicate_detector
    source_branch: OOMPAH-1291
    source_sha: null
    completed_at: ''
  - run_id: 3c705f08248946b7bb6265aeab40b0da--contributor-86e3ac8153e1
    provider_id: prov-6cf41c89
    provider_name: Opencode/Switchyard
    model_id: switchyard/auto
    focus: duplicate_detector
    source_branch: OOMPAH-1291
    source_sha: null
    completed_at: ''
  - run_id: 11d2471744444954a77abba8188d3a2c--contributor-86e3ac8153e1
    provider_id: prov-6cf41c89
    provider_name: Opencode/Switchyard
    model_id: switchyard/auto
    focus: duplicate_detector
    source_branch: OOMPAH-1291
    source_sha: null
    completed_at: ''
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1198 identifier=OOMPAH-1198 run_id=e0cde964aac043d8bb75d82717a085ba timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1198 identifier=OOMPAH-1198 run_id=e0cde964aac043d8bb75d82717a085ba timeout_seconds=5.0

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
- fingerprint: 6cfdc883e5122e87
- dedup_fingerprint: 6cfdc883e5122e87

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 03:15
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 03:15
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 03:16
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 26s
- Log: OOMPAH-1291__20260821T031604Z.jsonl
---
author: oompah
created: 2026-08-21 07:27
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 07:28
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 07:28
---
Run #1 [attempt=1, profile=default, role=fast -> Opencode/Switchyard/switchyard/auto]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 46s
- Log: OOMPAH-1291__20260821T072833Z.jsonl
---
author: oompah
created: 2026-08-21 11:39
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 11:40
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 11:41
---
Run #1 [attempt=1, profile=default, role=fast -> Opencode/Switchyard/switchyard/auto]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 38s
- Log: OOMPAH-1291__20260821T114100Z.jsonl
---
author: oompah
created: 2026-08-21 11:41
---
Duplicate screening was inconclusive 3 times. Human action required: a project owner must review the authoritative task corpus and use the authenticated duplicate-screening owner-resolution action (POST /api/v1/issues/OOMPAH-1291/duplicate-screening/owner-resolution) with a conclusive verdict and reason. This records the owner decision, resets the retry budget, and returns no_duplicate tasks to Open (or routes a verified duplicate to Duplicate Candidate). A plain verdict comment is not authoritative.
---
author: oompah
created: 2026-08-21 16:38
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 16:39
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
