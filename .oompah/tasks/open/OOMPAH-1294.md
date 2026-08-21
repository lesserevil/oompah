---
id: OOMPAH-1294
type: bug
status: Open
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1199 identifier=OOMPAH-1199 run_id=bea7300764c2440fb9a40ec351cdea22
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-20T23:53:32.349118Z'
updated_at: '2026-08-21T11:41:44.061714Z'
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
  task_fingerprint: 8da589b7377691fa54cc1cf0043a75bfd11d6c3c1f875d4d82f0eb75bb8f5219
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 88d08066c5acc1dafb8bf71027c22292cce1b74dd58c88d857dea23af494e48e:146586
  claim_owner: 94774825-4468-4d75-bdb4-5977b2bd9951
  claimed_at: '2026-08-21T11:40:48.432747+00:00'
  claim_expires_at: '2026-08-21T12:10:48.432747+00:00'
  retry_count: 2
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 8bbb97b2-826f-42c8-a6f0-3be16a6e5315
oompah.work_contributors:
  runs:
  - run_id: fe5f6b853aae415f8d9d3aa99f42732d--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1294
    source_sha: null
    completed_at: ''
  - run_id: 64060c1e6b564da6b9142d8ea126df97--contributor-86e3ac8153e1
    provider_id: prov-6cf41c89
    provider_name: Opencode/Switchyard
    model_id: switchyard/auto
    focus: duplicate_detector
    source_branch: OOMPAH-1294
    source_sha: null
    completed_at: ''
  - run_id: c1eb4993d55546538a167e9a78fc6ee7--contributor-86e3ac8153e1
    provider_id: prov-6cf41c89
    provider_name: Opencode/Switchyard
    model_id: switchyard/auto
    focus: duplicate_detector
    source_branch: OOMPAH-1294
    source_sha: null
    completed_at: ''
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1199 identifier=OOMPAH-1199 run_id=bea7300764c2440fb9a40ec351cdea22 timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1199 identifier=OOMPAH-1199 run_id=bea7300764c2440fb9a40ec351cdea22 timeout_seconds=5.0

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
- fingerprint: a3186e498005a50d
- dedup_fingerprint: a3186e498005a50d

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 03:23
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 03:23
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 03:24
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 55s
- Log: OOMPAH-1294__20260821T032348Z.jsonl
---
author: oompah
created: 2026-08-21 07:30
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 07:31
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 07:32
---
Run #1 [attempt=1, profile=default, role=fast -> Opencode/Switchyard/switchyard/auto]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 24s
- Log: OOMPAH-1294__20260821T073206Z.jsonl
---
author: oompah
created: 2026-08-21 11:41
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 11:41
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
