---
id: OOMPAH-732
type: task
status: Open
priority: null
title: Prevent standalone Ready delivery starvation after restart
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T17:50:33.429591Z'
updated_at: '2026-08-03T17:53:08.801088Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 1ead466f6b075a490ac65852a7c07a00a2fb85b329ff34b25e6401d64b7e3251
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 9ea6a089-2558-4a42-ad2d-3f278f14912a
  claim_owner: 8a58fb27-42d0-40cf-8dc2-70615b9783dc
  claimed_at: '2026-08-03T17:53:06.675850+00:00'
  claim_expires_at: '2026-08-03T18:23:06.675850+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
---
## Summary

Live regression of merged OOMPAH-598 observed after the 2026-08-03 service restart. Standalone tasks OOMPAH-724, OOMPAH-726, and OOMPAH-729 are Ready to Integrate with exact pushed branch/head metadata, no parent epic, no open review, no integration queue row, no active or recent quality gate, no running worker, and no standalone-delivery alert. OOMPAH-724 and OOMPAH-726 remained invisible for more than 40 minutes while shared-epic integration continued processing other projects. The project is healthy, unpaused, and has review capacity.\n\nImplementation scope:\n- Reproduce persisted standalone Ready records across startup and during a large shared-epic queue workload.\n- Ensure the standalone Ready reconciler runs on every bounded reconciliation interval independently of shared-epic claim success, cycle repair, project queue volume, and maintenance lane starvation.\n- Wake reconciliation immediately when a same-head accepted submission is restored or resubmitted.\n- Create exactly one gate/review delivery path, or emit one actionable standalone-delivery alert when delivery is impossible.\n- Reconcile records already in Ready at startup even when their submission predates the current service instance.\n- Preserve project review-capacity reservations, finish dependencies, exact-head gates, idempotent PR discovery, and no duplicate reviews.\n\nRelevant code: Orchestrator integration processing and standalone Ready reconciliation, tick-pool scheduling, startup recovery, state-change wakeups, integration metadata persistence, quality-gate scheduling, review cache/capacity, and standalone delivery alerts.\n\nRequired tests:\n- Restart with three persisted standalone Ready tasks and no PR/queue/gate; each obtains a bounded delivery path.\n- Keep a large shared-epic Ready queue and container-cycle repair active while proving standalone reconciliation is not starved.\n- Cover same-head resubmit wakeup, duplicate ticks, existing review, active/recent gate, unavailable SCM, review-capacity wait, gate failure/retry, and successful merge/audit.\n- Assert one review per available slot, no duplicate gate, no silent Ready row beyond the reconciliation interval, and actionable alert lifecycle.\n- Run focused standalone delivery, integration queue, maintenance scheduler, restart recovery, quality gate, review capacity, and state wakeup suites plus make test.\n\nAcceptance criteria:\n- A pushed standalone Ready task cannot remain without a gate, review, queue activity, or actionable alert beyond one bounded reconciliation interval.\n- OOMPAH-724, OOMPAH-726, and OOMPAH-729 converge through normal delivery after live rearming.\n- Busy shared-epic work cannot starve standalone delivery.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 17:52
---
Root evidence from the live log: capacity deferral was initially legitimate at 1/1, but after review capacity cleared every standalone sweep fetched each exact remote head and then logged Cancelled superseded standalone delivery ... delivery authority was revoked before review lookup for OOMPAH-724/726/729. This repeated at 17:40, 17:43, and 17:46 with no competing worker or tracker transition, no alert, and zero open Oompah reviews. The permanent fix must make evidence-revision/authority refresh stable across the remote-head and PR-lookup boundary, or atomically replace the authority without cancelling the same current generation. Add a concurrent tracker refresh/comment/update regression proving benign revision reads cannot revoke an otherwise identical exact-head delivery.
---
<!-- COMMENTS:END -->
