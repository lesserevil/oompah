---
id: OOMPAH-1231
type: task
status: Open
priority: null
title: Park externally blocked implementations instead of hourly redispatch
parent: null
children:
- OOMPAH-1262
- OOMPAH-1263
- OOMPAH-1264
- OOMPAH-1265
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T10:05:01.537298Z'
updated_at: '2026-08-14T02:41:41.269288Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: 9223d5cd-d749-49ea-a7e0-726e1ad3b254
  request_fingerprint: 205b96c1d8811c203aa3609d81dd100bd7f854e623e5c3e9e43572037c3fb0d8
oompah.lifecycle_revision: 1
---
## Summary

Bug reproduced live on TRICKLE-123. A task whose own durable handoffs repeatedly state that remaining acceptance requires unavailable macOS hardware stays In Progress with implementation.active after the worker exits, has no live owner, and is redispatched hourly across exhausted foci. Several launches terminate with zero useful work, while the task never acquires an actionable operator-owned parked state. Earlier terminal provenance can also coexist with reopened implementation, making the lifecycle misleading. Implementation scope: teach the workflow implementation controller/worker-exit path to classify structured handoffs that identify a concrete external prerequisite unavailable to all configured profiles (hardware/platform credentials/operator evidence) and publish a stable action-required or blocked disposition rather than active ownership; stop successor implementation jobs until the prerequisite is explicitly resolved; preserve resumability and avoid treating ordinary agent uncertainty as an external blocker. Include exact current run/lease checks so a late handoff cannot park a newer generation. Add observability explaining the named prerequisite and recovery action. Required tests: TRICKLE-123-shaped repeated handoffs with no live worker park once and do not redispatch across ticks/restart; a capable configured profile remains schedulable; an explicit prerequisite-resolution action rearms exactly one generation; late/old worker output cannot park a replacement; normal focus handoffs still progress. Acceptance: tasks requiring unavailable external hardware do not consume agents indefinitely or claim implementation.active without an owner, operators see a truthful actionable prerequisite, and focused implementation/runtime/liveness plus complete Makefile gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-14 02:28
---
Claimed for direct systemic implementation after OOMPAH-1261 lands. Oompah remains paused; no scheduler dispatch is authorized. Parallel root-cause review is mapping external-prerequisite classification, truthful jobless parking, explicit recovery rearm, and stale durable-authority retirement against the live Trickle reproductions.
---
author: oompah
created: 2026-08-14 02:41
---
Decomposed direct implementation into OOMPAH-1262 typed prerequisite/profile authority, OOMPAH-1263 stable parking and durable-lane retirement, OOMPAH-1264 exact CAS resolution and one-generation continuation, and OOMPAH-1265 production-shaped restart/race/observability acceptance. 1263 and 1264 hard-start after 1262 and can proceed in parallel; 1265 hard-starts after both. All children are Open, but Oompah remains paused and they are reserved for direct implementation.
---
author: oompah
created: 2026-08-14 02:41
---
Decomposed direct implementation into OOMPAH-1262 typed prerequisite/profile authority, OOMPAH-1263 stable parking and durable-lane retirement, OOMPAH-1264 exact CAS resolution and one-generation continuation, and OOMPAH-1265 production-shaped restart/race/observability acceptance. OOMPAH-1263 and OOMPAH-1264 hard-start after OOMPAH-1262 and can proceed in parallel; OOMPAH-1265 hard-starts after both. All children are Open, but Oompah remains paused and they are reserved for direct implementation.
---
<!-- COMMENTS:END -->
