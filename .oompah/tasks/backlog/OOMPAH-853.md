---
id: OOMPAH-853
type: task
status: Backlog
priority: null
title: Keep duplicate screening decisive when structural peers exceed the corpus budget
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T05:13:32.681862Z'
updated_at: '2026-08-06T05:13:32.681862Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live regression: OOMPAH-851 entered Needs Human on 2026-08-06 because duplicate screening declared required structural peers OOMPAH-848/OOMPAH-849/OOMPAH-850 could not fit the bounded corpus, despite OOMPAH-728's structural-peer retention work. A byte/task bound is an internal resource constraint and must not strand an actionable task for operator intervention. Implementation scope: make duplicate-corpus construction reserve deterministic space for every authoritative structural peer or compact peer records into sufficient identity/title/relationship/evidence summaries; distinguish an actual unreadable/corrupt tracker corpus from ordinary budget pressure; always produce a conclusive duplicate/unique verdict when tracker reads are healthy; preserve non-leakage, project scope, token bounds, and exact task/epic/depends-on relationships. Relevant code: duplicate preflight corpus selection/serialization, structural peer resolution, completion/owner-resolution flow, and duplicate-preflight health alerts. Required tests: reproduce OOMPAH-851 with three required peers exceeding both task and byte budgets; prove all peers remain represented and the investigator can return a durable verdict without Needs Human; cover one huge peer, many peers, multibyte text, missing/terminal/archived peers, restart/retry coalescing, and genuinely corrupt tracker reads remaining actionable. Acceptance criteria: healthy bounded corpus pressure never emits 'Required structural peers could not fit' or moves a task to Needs Human; the verdict remains scoped, deterministic, truncation-safe, and within configured limits; focused duplicate-preflight/corpus tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

