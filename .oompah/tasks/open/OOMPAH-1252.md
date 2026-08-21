---
id: OOMPAH-1252
type: bug
status: Open
priority: 2
title: '[backend:server] Update issue API error: TaskTransitionNotApplied(''TRICKLE-142:
  In Progress was not applied (rejected: transition.project_owner_authority_required)'')'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T17:11:27.677981Z'
updated_at: '2026-08-21T05:30:58.287736Z'
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
  task_fingerprint: 6f73eb0dfbbe07cc353cc5bb0f0f6989ff930b3dc2445bd6575b166d631d24ef
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: e7cbe1e65a69111d9e1c705fb054a1d9e22ee3c0ac0ecc9f817b6ef8c5da4cbc:143735
  claim_owner: 7dbe71d1-9fc2-4b0c-bb54-3da0831c26d5
  claimed_at: '2026-08-21T05:29:48.215143+00:00'
  claim_expires_at: '2026-08-21T05:59:48.215143+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 94813b6e-e8b2-42d1-a506-ab9d1fd95cfe
oompah.work_contributors:
  runs:
  - run_id: 0172dc2af57c42a69a2746e651e135c9--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1252
    source_sha: null
    completed_at: ''
  - run_id: 79983a88fb7243dc8173ebcd21db7234--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1252
    source_sha: null
    completed_at: ''
  - run_id: be369fa1aef14aceba17df00ffa0af27--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1252
    source_sha: null
    completed_at: ''
  - run_id: 75a8e1bc0317449d9b63b1c119189837--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1252
    source_sha: null
    completed_at: ''
---
## Summary

### Problem
Oompah detected a backend error from `backend:server`:

> Update issue API error: TaskTransitionNotApplied('TRICKLE-142: In Progress was not applied (rejected: transition.project_owner_authority_required)')

### Steps to Reproduce
1. Run oompah with `backend:server` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:server` and is recorded by oompah's `error_watcher`:

> Update issue API error: TaskTransitionNotApplied('TRICKLE-142: In Progress was not applied (rejected: transition.project_owner_authority_required)')

### Expected Behavior
The operation in `backend:server` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Acceptance Criteria
- The error from `backend:server` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: proj-14849f1b
- tracker: provenanceguardedtracker
- tracker_kind: provenanceguardedtracker
- fingerprint: 9da02389c0ecf39f
- dedup_fingerprint: 9da02389c0ecf39f

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-20 23:07
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-20 23:08
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-20 23:08
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 2s
- Log: OOMPAH-1252__20260820T230808Z.jsonl
---
author: oompah
created: 2026-08-21 00:23
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 00:24
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 00:24
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: interrupted, Duration: 54s
- Log: OOMPAH-1252__20260821T002438Z.jsonl
---
author: oompah
created: 2026-08-21 01:59
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 02:00
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 02:01
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 29s
- Log: OOMPAH-1252__20260821T020057Z.jsonl
---
author: oompah
created: 2026-08-21 02:01
---
Duplicate screening was inconclusive 3 times. Human action required: a project owner must review the authoritative task corpus and use the authenticated duplicate-screening owner-resolution action (POST /api/v1/issues/OOMPAH-1252/duplicate-screening/owner-resolution) with a conclusive verdict and reason. This records the owner decision, resets the retry budget, and returns no_duplicate tasks to Open (or routes a verified duplicate to Duplicate Candidate). A plain verdict comment is not authoritative.
---
author: oompah
created: 2026-08-21 05:30
---
Duplicate screening dispatched (profile: default, task remains Open)
---
<!-- COMMENTS:END -->
