---
id: OOMPAH-749
type: bug
status: Open
priority: 1
title: Bound historical audit replay so Ready integration claims cannot starve
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T00:41:30.892995Z'
updated_at: '2026-08-04T00:41:39.533568Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live reproduction on 2026-08-04: the integration ledger contains 37 Ready submissions across Oompah, Exocomp, and Nodevirt, with the oldest submitted 2026-08-01. Every row still has attempts=0, no lease owner, and no last error after repeated healthy ticks and a service restart. The integration driver scans and stages audits for the entire historical integrated set before it groups and claims live Ready rows, so growing history can indefinitely postpone forward work while the main orchestrator remains healthy. Implementation scope: make historical integrated-audit recovery incremental and bounded by a durable cursor or batch budget; claim or fairly interleave live Ready work before replaying unbounded history; preserve idempotent audit staging, lease recovery, per-epic serialization, dependencies, and cross-project fairness; expose progress and a degraded signal when Ready rows receive no claim within the expected interval. Relevant code includes _process_integration_queues, integrated terminal-audit staging, IntegrationQueue ledger scans, scheduling futures, and state metrics. Required tests: hundreds of historical integrated rows plus a live Ready row claimed within one driver interval; bounded replay across restarts; fair progress across projects and epic groups; dependency-blocked rows skipped without blocking eligible groups; no duplicate audits or lost lease recovery. Acceptance criteria: queue latency is bounded independently of historical ledger size, existing 37 Ready rows begin receiving leases naturally, and stalled claim progress becomes observable rather than silently healthy.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

