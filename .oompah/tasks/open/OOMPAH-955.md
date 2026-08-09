---
id: OOMPAH-955
type: bug
status: Open
priority: 1
title: Prevent long durable effects from head-of-line blocking control jobs
parent: OOMPAH-940
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T11:49:56.915594Z'
updated_at: '2026-08-09T11:50:32.528361Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live production reproducer on 2026-08-09: workflow job OOMPAH-951 standalone_delivery held an accepted lease and renewed normally while waiting on the sole validation-resource slot owned by OOMPAH-939, but WorkflowRuntime._run_due awaited DurableWorkflowWorker.run_once inline. That one long effect prevented independent priority-0 authority revocation, priority-10 validation submission, controller observation, state publication, and tick completion for more than 900 seconds, arming the dispatch-loop-stale alert. Review capacity was available and the queued jobs were otherwise eligible. No active task covers this; OOMPAH-953 only removes network-backed hot polling. Scope: execute durable effects with bounded concurrency or lane isolation so long data-plane gates cannot head-of-line block control-plane jobs; reserve at least one control slot/lane; preserve database-enforced same-project/task serialization, fair project claiming, exact leases/heartbeats/checkpoints, effect idempotency, shutdown/drain semantics, and bounded resource use. Required tests: block standalone delivery on validation capacity, enqueue independent exact authority revocation and validation submission, and prove both complete plus state/controller generations advance within a deterministic bound; same-task effects remain serialized; configured concurrency and reserved control capacity are never exceeded; crash/restart/drain produce no duplicate effect or lost waiter; multi-project fairness remains. Acceptance: a waiting/running full gate cannot stale the dispatch loop or delay independent control work, live telemetry remains current, and focused/full gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

