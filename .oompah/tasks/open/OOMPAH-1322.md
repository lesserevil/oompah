---
id: OOMPAH-1322
type: bug
status: Open
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1208 identifier=OOMPAH-1208 run_id=dd82f7e7ce1d4fe388c01522732adf48
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-21T01:15:25.298559Z'
updated_at: '2026-08-21T14:34:44.191114Z'
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
  task_fingerprint: f4e1b4537a959ac44b8f294e9ddec79b99d08e821329d1d1a8f10dca46bb6ff7
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 02d45c55de9d2271cde746ef17dfff16f062be883e4f483e928d7718adf0fbdb:147121
  claim_owner: f88f4310-5b61-4abc-a754-3264cc24a918
  claimed_at: '2026-08-21T14:34:22.981473+00:00'
  claim_expires_at: '2026-08-21T15:04:22.981473+00:00'
  retry_count: 2
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: f9d55560-62cc-4df9-8c31-2a3b97598df8
oompah.work_contributors:
  runs:
  - run_id: 71d1715257d34f909788c567fb76ee9b--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1322
    source_sha: null
    completed_at: ''
  - run_id: c98d36782062453c944bda31857dbb1e--contributor-86e3ac8153e1
    provider_id: prov-6cf41c89
    provider_name: Opencode/Switchyard
    model_id: switchyard/auto
    focus: duplicate_detector
    source_branch: OOMPAH-1322
    source_sha: null
    completed_at: ''
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1208 identifier=OOMPAH-1208 run_id=dd82f7e7ce1d4fe388c01522732adf48 timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1208 identifier=OOMPAH-1208 run_id=dd82f7e7ce1d4fe388c01522732adf48 timeout_seconds=5.0

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
- fingerprint: 6cbdb451c9d42ddd
- dedup_fingerprint: 6cbdb451c9d42ddd

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 05:08
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 05:08
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 05:09
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 11s
- Log: OOMPAH-1322__20260821T050900Z.jsonl
---
author: oompah
created: 2026-08-21 09:53
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 09:54
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 09:54
---
Run #1 [attempt=1, profile=default, role=fast -> Opencode/Switchyard/switchyard/auto]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 47s
- Log: OOMPAH-1322__20260821T095430Z.jsonl
---
author: oompah
created: 2026-08-21 14:34
---
Duplicate screening dispatched (profile: default, task remains Open)
---
<!-- COMMENTS:END -->
