---
id: OOMPAH-853
type: task
status: Open
priority: null
title: Keep duplicate screening decisive when structural peers exceed the corpus budget
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T05:13:32.681862Z'
updated_at: '2026-08-06T05:14:11.608685Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-853
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 76de1f1705d2c49c194b4b015da286ed72a8022249d7dda6e00ae5520b1a3460
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 4d4f0130-2074-45d3-ab41-e81bb6c2d9ee
  claim_owner: 11468835-7c49-48df-a46d-b143af3a940a
  claimed_at: '2026-08-06T05:13:57.500730+00:00'
  claim_expires_at: '2026-08-06T05:43:57.500730+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 071bd140-fac0-49bb-93a8-f15254a6e28b
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-853
---
## Summary

Live regression: OOMPAH-851 entered Needs Human on 2026-08-06 because duplicate screening declared required structural peers OOMPAH-848/OOMPAH-849/OOMPAH-850 could not fit the bounded corpus, despite OOMPAH-728's structural-peer retention work. A byte/task bound is an internal resource constraint and must not strand an actionable task for operator intervention. Implementation scope: make duplicate-corpus construction reserve deterministic space for every authoritative structural peer or compact peer records into sufficient identity/title/relationship/evidence summaries; distinguish an actual unreadable/corrupt tracker corpus from ordinary budget pressure; always produce a conclusive duplicate/unique verdict when tracker reads are healthy; preserve non-leakage, project scope, token bounds, and exact task/epic/depends-on relationships. Relevant code: duplicate preflight corpus selection/serialization, structural peer resolution, completion/owner-resolution flow, and duplicate-preflight health alerts. Required tests: reproduce OOMPAH-851 with three required peers exceeding both task and byte budgets; prove all peers remain represented and the investigator can return a durable verdict without Needs Human; cover one huge peer, many peers, multibyte text, missing/terminal/archived peers, restart/retry coalescing, and genuinely corrupt tracker reads remaining actionable. Acceptance criteria: healthy bounded corpus pressure never emits 'Required structural peers could not fit' or moves a task to Needs Human; the verdict remains scoped, deterministic, truncation-safe, and within configured limits; focused duplicate-preflight/corpus tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 05:14
---
Duplicate screening dispatched (profile: default, task remains Open)
---
<!-- COMMENTS:END -->
