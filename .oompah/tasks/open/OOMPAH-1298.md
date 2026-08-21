---
id: OOMPAH-1298
type: bug
status: Open
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1214 identifier=OOMPAH-1214 run_id=b2123ad1829b44bd9421d35405167108
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-21T00:00:50.331057Z'
updated_at: '2026-08-21T16:45:19.339290Z'
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
  task_fingerprint: 8d64dafffd0de048cded37a525a921b46168b66509319ce7eb5849f65b2be722
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 0f3b9dbf872ce3ae46eea1ec9e7df5b08380b5197f8ff3b0734bda8419fee5e9:147415
  claim_owner: 8b3bb5f8-8d0e-4cf3-9d62-5bd5932d676d
  claimed_at: '2026-08-21T16:44:51.597654+00:00'
  claim_expires_at: '2026-08-21T17:14:51.597654+00:00'
  retry_count: 2
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 8fdce4bc-e8e7-4921-8f60-c619202500ee
oompah.work_contributors:
  runs:
  - run_id: 62dcd3d646a64cfeb06b2bbe7419e489--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1298
    source_sha: null
    completed_at: ''
  - run_id: a56a08ea2a5e4168bd23899d7f86376a--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1298
    source_sha: null
    completed_at: ''
  - run_id: 3bc5b95d02634ba1b474d9058df3f495--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1298
    source_sha: null
    completed_at: ''
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1214 identifier=OOMPAH-1214 run_id=b2123ad1829b44bd9421d35405167108 timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1214 identifier=OOMPAH-1214 run_id=b2123ad1829b44bd9421d35405167108 timeout_seconds=5.0

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
- fingerprint: a5c4a111e61cb5ed
- dedup_fingerprint: a5c4a111e61cb5ed

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 03:28
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 03:28
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 03:29
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 26s
- Log: OOMPAH-1298__20260821T032857Z.jsonl
---
author: oompah
created: 2026-08-21 07:37
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 07:39
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 07:40
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 3m 2s
- Log: OOMPAH-1298__20260821T073931Z.jsonl
---
author: oompah
created: 2026-08-21 11:50
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 11:50
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 16:45
---
Duplicate screening dispatched (profile: default, task remains Open)
---
<!-- COMMENTS:END -->
