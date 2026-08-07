---
id: OOMPAH-875
type: task
status: Open
priority: null
title: Prevent slow scheduler lanes from starving Ready integration claims
parent: OOMPAH-768
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-07T08:44:33.807355Z'
updated_at: '2026-08-07T08:44:42.529458Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live cutover regression on 2026-08-07: OOMPAH-865 was durably Ready at 08:33:01 with an idle validation broker, but no integration claim began until 08:41:29. The first post-cutover scheduler tick took 366 seconds, including 320 seconds in dispatch and 175 seconds in terminal-audit scanning/launch. _process_integration_queues is only scheduled after reconcile, review, dispatch, YOLO, and watchdog, so eligible exact-head delivery is starved behind unrelated slow lanes despite available validation capacity.

Implementation scope:
- Give durable shared-epic integration reconciliation its own promptly woken lane or schedule it before unrelated unbounded dispatch/audit work.
- Preserve one active integration pass, exact-head CAS authority, dependency ordering, project isolation, and the single validation-resource lease.
- Make submit/refresh/cutover events wake the integration lane without duplicate claims.
- Publish bounded latency/progress telemetry and an actionable alert only when an eligible row exceeds the configured claim bound.
- Keep terminal-audit, normal dispatch, and maintenance work from monopolizing integration progress.

Relevant code: oompah/orchestrator.py _tick and _process_integration_queues, event/refresh coalescing, integration_queue.py claiming, and state telemetry.

Required tests:
- A synthetic multi-minute dispatch/audit lane cannot delay an eligible Ready integration claim beyond the configured bound.
- Restart/cutover with a pre-existing Ready row starts exactly one integration pass.
- Concurrent submit/refresh events coalesce and never double-claim.
- Dependency-blocked rows remain blocked while an independent eligible row claims.
- Validation broker capacity and exact authority generation remain unchanged.

Acceptance criteria: a Ready integration row with satisfied dependencies and available validation capacity is claimed within a bounded interval independent of dispatch/audit duration; state exposes the last integration run/claim latency; no duplicate gate or lost wakeup occurs; focused scheduler/integration/event-loop tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

