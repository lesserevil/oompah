---
id: OOMPAH-1203
type: bug
status: Open
priority: 2
title: '[backend:orchestrator] All dispatch candidates failed for issue TRICKLE-131:
  All 2 dispatch candidates unavailable: prov-52e94e83/gpt-5.6-luna: contributor_evidence_unavailable:
  Cannot durably reco...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T01:19:28.760792Z'
updated_at: '2026-08-20T23:42:22.146905Z'
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
  task_fingerprint: 1d105f98334cb4c98a6571e10a57c9173799ce23c81e31a71f9f79037cbdd6c6
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 9faae948b8e6ac3f6b8d754f9e03d6ec980fd1ad4d9cfc3418da4978136119f5:142369
  claim_owner: b0161d82-55d7-4b08-9b68-ee54b4e13c9c
  claimed_at: '2026-08-20T23:41:38.350286+00:00'
  claim_expires_at: '2026-08-21T00:11:38.350286+00:00'
  retry_count: 1
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: e5722ad5-457b-4d66-aa0f-839d7d6fec02
oompah.work_contributors:
  runs:
  - run_id: 1d9b48c4b46a452f93bc94e5caf3c72c--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1203
    source_sha: null
    completed_at: ''
  - run_id: 021fc41d268f4c13b989882da2ab1ca0--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1203
    source_sha: null
    completed_at: ''
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> All dispatch candidates failed for issue TRICKLE-131: All 2 dispatch candidates unavailable: prov-52e94e83/gpt-5.6-luna: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before launch (StateBranchFetchError). Restore tracker metadata writes and retry; no provider or workspace was started.; prov-651d553c/haiku: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before launch (StateBranchFetchError). Restore tracker metadata writes and retry; no provider or workspace was started.

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> All dispatch candidates failed for issue TRICKLE-131: All 2 dispatch candidates unavailable: prov-52e94e83/gpt-5.6-luna: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before launch (StateBranchFetchError). Restore tracker metadata writes and retry; no provider or workspace was started.; prov-651d553c/haiku: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before launch (StateBranchFetchError). Restore tracker metadata writes and retry; no provider or workspace was started.

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
- fingerprint: 7177dadeaf0eac51
- dedup_fingerprint: 7177dadeaf0eac51

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-20 22:46
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-20 22:46
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-20 22:47
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 49s
- Log: OOMPAH-1203__20260820T224650Z.jsonl
---
author: oompah
created: 2026-08-20 23:41
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-20 23:42
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
