---
id: OOMPAH-1290
type: bug
status: Open
priority: 2
title: '[backend:orchestrator] All dispatch candidates failed for issue TRICKLE-143:
  All 2 dispatch candidates unavailable: prov-52e94e83/gpt-5.6-luna: contributor_evidence_unavailable:
  Cannot durably reco...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-20T23:16:52.125972Z'
updated_at: '2026-08-21T11:37:49.130342Z'
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
  task_fingerprint: d5b4d5666dca4e859c3a7a3e9179186e880d98943992c361e0bfe7a826d610fc
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 4894c5c8165e06c25cde6690b3018ca4ba23d2b97adf025dfe242154238c601f:146509
  claim_owner: 94774825-4468-4d75-bdb4-5977b2bd9951
  claimed_at: '2026-08-21T11:37:36.262149+00:00'
  claim_expires_at: '2026-08-21T12:07:36.262149+00:00'
  retry_count: 2
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 87ac0720-621c-4605-98f6-3273be333bc8
oompah.work_contributors:
  runs:
  - run_id: 883d7c8a5dbb4140bb65fa6463ba9a7a--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1290
    source_sha: null
    completed_at: ''
  - run_id: 2f541eeeaf794b91abb98cb72267e784--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1290
    source_sha: null
    completed_at: ''
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> All dispatch candidates failed for issue TRICKLE-143: All 2 dispatch candidates unavailable: prov-52e94e83/gpt-5.6-luna: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before the bounded task-authority deadline. The pre-provider runtime was retired for retry; no provider or workspace was started.; prov-651d553c/haiku: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before the bounded task-authority deadline. The pre-provider runtime was retired for retry; no provider or workspace was started.

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> All dispatch candidates failed for issue TRICKLE-143: All 2 dispatch candidates unavailable: prov-52e94e83/gpt-5.6-luna: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before the bounded task-authority deadline. The pre-provider runtime was retired for retry; no provider or workspace was started.; prov-651d553c/haiku: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before the bounded task-authority deadline. The pre-provider runtime was retired for retry; no provider or workspace was started.

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
- fingerprint: 3e1944fd606f90af
- dedup_fingerprint: 3e1944fd606f90af

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 03:14
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 03:14
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 03:15
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 56s
- Log: OOMPAH-1290__20260821T031455Z.jsonl
---
author: oompah
created: 2026-08-21 07:27
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 07:27
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 07:28
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 23s
- Log: OOMPAH-1290__20260821T072805Z.jsonl
---
<!-- COMMENTS:END -->
