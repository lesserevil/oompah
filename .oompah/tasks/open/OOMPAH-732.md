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
updated_at: '2026-08-03T17:50:50.626935Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live regression of merged OOMPAH-598 observed after the 2026-08-03 service restart. Standalone tasks OOMPAH-724, OOMPAH-726, and OOMPAH-729 are Ready to Integrate with exact pushed branch/head metadata, no parent epic, no open review, no integration queue row, no active or recent quality gate, no running worker, and no standalone-delivery alert. OOMPAH-724 and OOMPAH-726 remained invisible for more than 40 minutes while shared-epic integration continued processing other projects. The project is healthy, unpaused, and has review capacity.\n\nImplementation scope:\n- Reproduce persisted standalone Ready records across startup and during a large shared-epic queue workload.\n- Ensure the standalone Ready reconciler runs on every bounded reconciliation interval independently of shared-epic claim success, cycle repair, project queue volume, and maintenance lane starvation.\n- Wake reconciliation immediately when a same-head accepted submission is restored or resubmitted.\n- Create exactly one gate/review delivery path, or emit one actionable standalone-delivery alert when delivery is impossible.\n- Reconcile records already in Ready at startup even when their submission predates the current service instance.\n- Preserve project review-capacity reservations, finish dependencies, exact-head gates, idempotent PR discovery, and no duplicate reviews.\n\nRelevant code: Orchestrator integration processing and standalone Ready reconciliation, tick-pool scheduling, startup recovery, state-change wakeups, integration metadata persistence, quality-gate scheduling, review cache/capacity, and standalone delivery alerts.\n\nRequired tests:\n- Restart with three persisted standalone Ready tasks and no PR/queue/gate; each obtains a bounded delivery path.\n- Keep a large shared-epic Ready queue and container-cycle repair active while proving standalone reconciliation is not starved.\n- Cover same-head resubmit wakeup, duplicate ticks, existing review, active/recent gate, unavailable SCM, review-capacity wait, gate failure/retry, and successful merge/audit.\n- Assert one review per available slot, no duplicate gate, no silent Ready row beyond the reconciliation interval, and actionable alert lifecycle.\n- Run focused standalone delivery, integration queue, maintenance scheduler, restart recovery, quality gate, review capacity, and state wakeup suites plus make test.\n\nAcceptance criteria:\n- A pushed standalone Ready task cannot remain without a gate, review, queue activity, or actionable alert beyond one bounded reconciliation interval.\n- OOMPAH-724, OOMPAH-726, and OOMPAH-729 converge through normal delivery after live rearming.\n- Busy shared-epic work cannot starve standalone delivery.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

