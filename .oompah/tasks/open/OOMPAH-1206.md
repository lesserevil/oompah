---
id: OOMPAH-1206
type: bug
status: Open
priority: 2
title: '[backend:orchestrator] All dispatch candidates failed for issue TRICKLE-121:
  All 2 dispatch candidates unavailable: prov-651d553c/sonnet: contributor_evidence_unavailable:
  Cannot durably record exa...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T01:28:18.549010Z'
updated_at: '2026-08-20T23:54:06.207893Z'
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
  task_fingerprint: fbcb81c89765296d81d5cc7e201f22485ae76679ff7f54d22b4f93339f1b55b3
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: f206cc653fee5d2d49c4fde312891577627e499e547e82060c204292ee450047:142421
  claim_owner: b0161d82-55d7-4b08-9b68-ee54b4e13c9c
  claimed_at: '2026-08-20T23:53:41.178099+00:00'
  claim_expires_at: '2026-08-21T00:23:41.178099+00:00'
  retry_count: 1
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 076fdf0c-2c2e-4cc5-a9fd-2d5ac619064a
oompah.work_contributors:
  runs:
  - run_id: 492b9a9720f6490dbdbde0e0652e76a2--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1206
    source_sha: null
    completed_at: ''
  - run_id: 492b9a9720f6490dbdbde0e0652e76a2--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1206
    source_sha: null
    completed_at: ''
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> All dispatch candidates failed for issue TRICKLE-121: All 2 dispatch candidates unavailable: prov-651d553c/sonnet: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before the bounded task-authority deadline. The pre-provider runtime was retired for retry; no provider or workspace was started.; prov-52e94e83/gpt-5.6-terra: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before the bounded task-authority deadline. The pre-provider runtime was retired for retry; no provider or workspace was started.

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> All dispatch candidates failed for issue TRICKLE-121: All 2 dispatch candidates unavailable: prov-651d553c/sonnet: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before the bounded task-authority deadline. The pre-provider runtime was retired for retry; no provider or workspace was started.; prov-52e94e83/gpt-5.6-terra: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before the bounded task-authority deadline. The pre-provider runtime was retired for retry; no provider or workspace was started.

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
- fingerprint: eaf13222a2df2bf2
- dedup_fingerprint: eaf13222a2df2bf2

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-20 22:48
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-20 22:49
---
Run #1 [attempt=1, profile=default, role=— -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 0s
---
author: oompah
created: 2026-08-20 23:54
---
Duplicate screening dispatched (profile: default, task remains Open)
---
<!-- COMMENTS:END -->
