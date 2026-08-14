---
id: OOMPAH-1263
type: bug
status: Open
priority: 1
title: Park external blockers and retire every stale durable lane
parent: OOMPAH-1231
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-1262
labels: []
assignee: null
created_at: '2026-08-14T02:39:37.692542Z'
updated_at: '2026-08-14T04:28:20.166435Z'
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
  creation_marker: oompah-1231-park-retirement-v1
  request_fingerprint: 98432ed9fc5b6f6b2f2c9c65ea49a82baf69aba3719cebb46325f1817bfe1024
oompah.start_blocked_by: *id001
oompah.lifecycle_revision: 1
---
## Summary

Consume exact structured prerequisite authority to publish a stable jobless work decision and an accepted managed zero-job authority cut. Atomically retire the outgoing owner/run and supersede or cancel every task-scoped durable lane that must not outlive the park, including current exhausted implementation or standalone delivery and overdue nested-dispatch topology repair. Project unresolved task dependencies as non-alerting Blocked decisions with named prerequisites; reserve Action Required warnings for genuine operator-only or unavailable-platform triggers. Preserve accepted-submission precedence and fail closed across crash/restart. Relevant areas: workflow decisions/controllers/scheduler store, implementation worker-exit adapter, authority revocation, nested topology recovery, liveness projection. Required regressions: TRICKLE-132 current exhausted standalone row retires, TRICKLE-139 retry-wait auxiliary row cannot run after park, repeated ticks/restart remain zero-job, current replacement authority wins races, and ordinary focus handoffs still progress. Acceptance: a parked task has no live owner, claimable/retryable/exhausted current job, false global warning, or restart redispatch.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-14 03:17
---
Live regression reproduced during the 948ef6f restart: TRICKLE-138 and TRICKLE-139 had current jobless Needs Human decisions, but unmanaged nested_dispatch_topology_repair rows survived and TRICKLE-138 advanced from attempt 3 to 5. Exact rows 18391/18392 were safely cancelled by generation CAS while Trickle was paused, then verified terminal with retry_at cleared. Scope must explicitly retire stale auxiliary/unmanaged lanes such as nested-dispatch-topology when current structured prerequisite or zero-job authority parks the task; authority_revocation currently covers implementation ownership only and is insufficient. Add restart/reclaim regressions for this exact shape.
---
author: oompah
created: 2026-08-14 03:55
---
Claimed for direct implementation in /home/shedwards/src/oompah-1263 on branch OOMPAH-1263, based on integrated prerequisite bf53cfb7a35c8c9773557712b55cbe09d5de6ef6 from epic-OOMPAH-1231. Oompah remains paused.
---
author: oompah
created: 2026-08-14 04:09
---
Implementation checkpoint: exact managed zero-job lane retirement and publication rollback/restart fencing are implemented; six focused store regressions pass. Decision classification now keeps dependency waits quiet, retains real operator/platform warnings, gives accepted submissions precedence, and schedules exact outgoing-source revocation before parking. Nested topology final-lease fencing and runtime race coverage are in progress in parallel.
---
author: oompah
created: 2026-08-14 04:26
---
Implemented stable structured prerequisite parking: exact blocked prerequisites now classify dependency waits as non-alerting Blocked and capability/operator failures as Action Required warnings; accepted submissions and current replacement generations retain precedence. Zero-job park cuts durably retire managed implementation work plus exact fact, imperative, and nested-repair event lanes while preserving the prerequisite-resolution lane. Added outgoing-run revocation and nested-repair mutation fencing, fail-closed publication rollback, restart/current-replacement behavior, and same-task tracker-drift retry protection. Focused consolidated verification: 789 passed across workflow runtime, store, scheduler/controller, decision, adapter, duplicate-preflight, implementation workflow, and nested topology suites. Branch remains local and unsubmitted for parent integration.
---
author: oompah
created: 2026-08-14 04:28
---
Frozen branch pushed at exact head 987c46cb8075073aac18a09c140eafe9526190fd in PR 880 targeting epic-OOMPAH-1231. Focused verification passes 789 tests and diff check is clean. Auto-merge is intentionally disabled until GitHub CI completes.
---
<!-- COMMENTS:END -->
