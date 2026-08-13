---
id: OOMPAH-1236
type: task
status: Backlog
priority: null
title: Unify durable epic source authority with persisted nested branches
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T12:12:00.430229Z'
updated_at: '2026-08-13T12:12:14.234211Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: oompah
  operation_kind: api_task_create
  creation_marker: 456e97e8-3977-48c5-9043-da95629d9ced
  request_fingerprint: 24588412e8f783192162e56511e9c7c4eeb0377ce15c7f19468c4abb3905de0f
---
## Summary

Live scheduling bug exposed after OOMPAH-1235 created a current v2 epic-rebase job for TRICKLE-130. Nested dispatch correctly observes the persisted epic work branch TRICKLE-130 at 4493710 behind epic-TRICKLE-127, but EpicFactCollector hard-codes epic-TRICKLE-130 (already at the parent head). The durable decision therefore omits epic_rebase_repair and supersedes the helper job even though the dispatch topology remains stale. Implementation scope: establish one source-branch/head authority contract shared by EpicFactCollector, EpicWorkflowEventRouter, ProductionEpicWorkflowBackend, OrchestratorEpicWorkflowEffects, and nested-dispatch rebase request publication; preserve canonical epic-* fallback when no persisted branch exists; bind scheduling/revalidation/mutation to the exact live source head rather than a stale review head. Add regression tests with a nested epic whose persisted work_branch differs from epic-<id>, whose review_head differs from the live source ref, and whose immediate parent target has advanced. Acceptance: exactly one durable rebase helper is created for the persisted source and target, stale source/target changes fail closed, TRICKLE-138/139 topology repairs stop cycling after the helper publishes, focused epic/workflow suites and hosted CI pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 12:12
---
Claimed directly during live Trickle monitoring. OOMPAH-1235 successfully produced v2 job seq16476, but the job superseded because durable epic facts modeled source epic-TRICKLE-130 while nested dispatch and the tracker own persisted source TRICKLE-130. Fixing the branch/head authority split now; Oompah stays paused and only Trickle remains resumed.
---
<!-- COMMENTS:END -->
