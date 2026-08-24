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
updated_at: '2026-08-24T13:29:43.512115Z'
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
  evidence: 'RuntimeError: Codex exec exited with code 1:'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 1
  retry_after: '2026-08-24T13:30:35.659219+00:00'
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: feff4bdd-2639-464b-a4c3-a3597677d2c2
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
  - run_id: 85fb643dbb2b48f885ddce7699210c0d--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1302
    source_sha: 4988991309ba81b6b2cf06aa30528bf5f21b0a82
    completed_at: '2026-08-24T05:41:23.287103+00:00'
  - run_id: 187c5d0e20224cedac3f6904293f8c4c--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1302
    source_sha: 4988991309ba81b6b2cf06aa30528bf5f21b0a82
    completed_at: '2026-08-24T09:07:33.701065+00:00'
  - run_id: 8a9becec592f4f20bee27b50807789ed--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1302
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 20
  total_output_tokens: 4337
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 20
      output_tokens: 4337
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1636
    cost_usd: 0.0
    recorded_at: '2026-08-24T05:41:23.260047+00:00'
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2701
    cost_usd: 0.0
    recorded_at: '2026-08-24T09:07:33.692453+00:00'
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
author: oompah
created: 2026-08-24 05:39
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-24 05:40
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-24 05:41
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.6K out [1.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 36s
- Log: OOMPAH-1302__20260824T054043Z.jsonl
---
author: oompah
created: 2026-08-24 09:05
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-24 09:06
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-24 09:07
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.7K out [2.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 4s
- Log: OOMPAH-1302__20260824T090646Z.jsonl
---
author: oompah
created: 2026-08-24 09:08
---
Duplicate screening was inconclusive 3 times. Human action required: a project owner must review the authoritative task corpus and use the authenticated duplicate-screening owner-resolution action (POST /api/v1/issues/OOMPAH-1302/duplicate-screening/owner-resolution) with a conclusive verdict and reason. This records the owner decision, resets the retry budget, and returns no_duplicate tasks to Open (or routes a verified duplicate to Duplicate Candidate). A plain verdict comment is not authoritative.
---
author: oompah
created: 2026-08-24 13:27
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-24 13:28
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-24 13:29
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 51s
- Log: OOMPAH-1302__20260824T132837Z.jsonl
---
<!-- COMMENTS:END -->
