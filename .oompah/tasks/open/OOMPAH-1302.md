---
id: OOMPAH-1302
type: bug
status: Open
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1249 identifier=OOMPAH-1249 run_id=40dc604639104a37ab8ec395fe3b26fa
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-21T00:14:43.227832Z'
updated_at: '2026-08-24T05:39:28.248280Z'
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
  task_fingerprint: 585225032887a77d8c4028b4377020b5da22197fc252361e392aaffb5fd0d860
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: a23f69a5393f7e636a31195a600dae363253fa5bf14bb72305c252570e09a2f9:165642
  claim_owner: 56032ce5-389f-4a89-8d1d-90008fb87378
  claimed_at: '2026-08-24T05:39:09.624583+00:00'
  claim_expires_at: '2026-08-24T06:09:09.624583+00:00'
  retry_count: 1
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 7f637a3e-c164-438e-883c-851e322559af
oompah.work_contributors:
  runs:
  - run_id: 6168bda38ef84d60a801eb80fcdd4ad6--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1302
    source_sha: null
    completed_at: ''
  - run_id: 6fa41a115c4141c1aacc14fbf731b063--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1302
    source_sha: null
    completed_at: ''
  - run_id: 855a919f0edd43578d6477264f8f9c80--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1302
    source_sha: null
    completed_at: ''
  - run_id: 9f27dd000ceb49508408f2cada9cf595--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1302
    source_sha: null
    completed_at: ''
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1249 identifier=OOMPAH-1249 run_id=40dc604639104a37ab8ec395fe3b26fa timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1249 identifier=OOMPAH-1249 run_id=40dc604639104a37ab8ec395fe3b26fa timeout_seconds=5.0

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
- fingerprint: 2a8a87ec7f95c97a
- dedup_fingerprint: 2a8a87ec7f95c97a

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 03:37
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 03:38
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 03:39
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 9s
- Log: OOMPAH-1302__20260821T033830Z.jsonl
---
author: oompah
created: 2026-08-21 07:58
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 07:59
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 08:00
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 12s
- Log: OOMPAH-1302__20260821T075941Z.jsonl
---
author: oompah
created: 2026-08-21 12:03
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 12:04
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 12:05
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 53s
- Log: OOMPAH-1302__20260821T120430Z.jsonl
---
author: oompah
created: 2026-08-21 12:05
---
Duplicate screening was inconclusive 3 times. Human action required: a project owner must review the authoritative task corpus and use the authenticated duplicate-screening owner-resolution action (POST /api/v1/issues/OOMPAH-1302/duplicate-screening/owner-resolution) with a conclusive verdict and reason. This records the owner decision, resets the retry budget, and returns no_duplicate tasks to Open (or routes a verified duplicate to Duplicate Candidate). A plain verdict comment is not authoritative.
---
author: oompah
created: 2026-08-23 22:56
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-23 22:57
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-23 22:57
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: interrupted, Duration: 51s
- Log: OOMPAH-1302__20260823T225736Z.jsonl
---
<!-- COMMENTS:END -->
