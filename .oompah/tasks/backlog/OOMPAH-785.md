---
id: OOMPAH-785
type: task
status: Backlog
priority: 1
title: Replace process-local workflow scheduling primitives with durable job ownership
parent: OOMPAH-766
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T13:59:05.979634Z'
updated_at: '2026-08-04T13:59:05.979634Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Add the event-to-decision-to-job scheduling layer and migrate shared lifecycle ownership away from fire-and-forget futures, mutable cooldown maps, completed/reject sets, and timer-only retries as domain handlers become available. Events become wakeups; durable rows remain correctness authority. Preserve per-project/task serialization without a global bottleneck and expose queue/lease/retry health. Required tests: event coalescing/missed events, duplicate scheduling, concurrent ticks, process restart, bounded full-sync recovery, per-project fairness, and graceful drain. Acceptance: lifecycle progress never depends solely on an in-memory future/map/monotonic timestamp and a missed event cannot strand work.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

