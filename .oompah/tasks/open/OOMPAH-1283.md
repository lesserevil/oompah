---
id: OOMPAH-1283
type: bug
status: Open
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1216 identifier=OOMPAH-1216 run_id=7d692e02f8fb4053ad98f70b1a6f2764
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-20T22:56:45.420158Z'
updated_at: '2026-08-24T09:42:42.800046Z'
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
  task_fingerprint: ab1e7c9bf1e831b860540c1dc7f19ca2942170f3e27803b0351e35ab8de9ee55
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: b182f69c1d387d23fb421ad563030b3a2584b82e09acd6b573abc238aaa479f7:166649
  claim_owner: 37ccaa87-ad5a-4d18-9016-1bf917e62c3a
  claimed_at: '2026-08-24T09:41:48.721852+00:00'
  claim_expires_at: '2026-08-24T10:11:48.721852+00:00'
  retry_count: 2
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 3f32019d-daa5-47a8-add4-4816ba9cc798
oompah.work_contributors:
  runs:
  - run_id: 65d3ef7283c7451099c2949051272c23--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1283
    source_sha: null
    completed_at: ''
  - run_id: 90537535142741bb89869ab97b88fc9a--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1283
    source_sha: null
    completed_at: ''
  - run_id: 3cf4b19792994339a49b39f2260eb254--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1283
    source_sha: null
    completed_at: ''
  - run_id: 78e5f5c8a2544309bb3239924a87b99d--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1283
    source_sha: null
    completed_at: ''
  - run_id: b8d7877d947948a2a34a496f460e7fc9--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1283
    source_sha: 4988991309ba81b6b2cf06aa30528bf5f21b0a82
    completed_at: '2026-08-24T07:03:32.189464+00:00'
  - run_id: 6967529062b443448d882d5c46c16fc2--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1283
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1763
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1763
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1763
    cost_usd: 0.0
    recorded_at: '2026-08-24T07:03:32.157208+00:00'
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1216 identifier=OOMPAH-1216 run_id=7d692e02f8fb4053ad98f70b1a6f2764 timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1216 identifier=OOMPAH-1216 run_id=7d692e02f8fb4053ad98f70b1a6f2764 timeout_seconds=5.0

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
- fingerprint: 5eb144397d91aafa
- dedup_fingerprint: 5eb144397d91aafa

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 02:53
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 02:53
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 02:53
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 48s
- Log: OOMPAH-1283__20260821T025322Z.jsonl
---
author: oompah
created: 2026-08-21 07:00
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 07:00
---
Run #1 [attempt=1, profile=default, role=— -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 10s
---
author: oompah
created: 2026-08-21 11:28
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 11:29
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 11:30
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 49s
- Log: OOMPAH-1283__20260821T112929Z.jsonl
---
author: oompah
created: 2026-08-21 15:47
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 15:48
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 15:49
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 14s
- Log: OOMPAH-1283__20260821T154835Z.jsonl
---
author: oompah
created: 2026-08-21 15:49
---
Duplicate screening was inconclusive 3 times. Human action required: a project owner must review the authoritative task corpus and use the authenticated duplicate-screening owner-resolution action (POST /api/v1/issues/OOMPAH-1283/duplicate-screening/owner-resolution) with a conclusive verdict and reason. This records the owner decision, resets the retry budget, and returns no_duplicate tasks to Open (or routes a verified duplicate to Duplicate Candidate). A plain verdict comment is not authoritative.
---
author: oompah
created: 2026-08-23 23:29
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-23 23:30
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-23 23:31
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 2m 11s
- Log: OOMPAH-1283__20260823T233102Z.jsonl
---
author: oompah
created: 2026-08-24 07:00
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-24 07:01
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-24 07:03
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.8K out [1.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 40s
- Log: OOMPAH-1283__20260824T070154Z.jsonl
---
author: oompah
created: 2026-08-24 09:42
---
Duplicate screening dispatched (profile: default, task remains Open)
---
<!-- COMMENTS:END -->
