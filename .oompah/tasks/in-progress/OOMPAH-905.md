---
id: OOMPAH-905
type: task
status: In Progress
priority: null
title: Age validation-resource waiters so strict priority cannot starve focused repair
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-07T19:44:43.282351Z'
updated_at: '2026-08-07T19:45:24.879942Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live direct-work reproduction on 2026-08-07 after OOMPAH-816/852 deployment: OOMPAH-859's canonical worker validation waiter remained queued for more than 19 minutes while exact-gate and auditor arrivals repeatedly overtook it; its 1800-second acquire timeout can expire even though the capacity-1 lane is making progress. OOMPAH-784/O795 worker waits show the same class. This violates OOMPAH-816's fairness/no-starvation acceptance and can deadlock focused repair behind a continuous stream of later high-priority work. Implementation scope: add bounded aging/fairness to ValidationResourceLease durable waiter selection while retaining exact-gate urgency and single-slot safety; guarantee a live low-priority waiter receives service within a documented bound under continuous higher-priority arrivals; preserve FIFO within effective priority, restart/PID pruning, cancellation, owner fencing, and truthful wait telemetry. Relevant files: oompah/validation_resource_lease.py, validation-resource projections/health, and tests for multiprocess ordering. Required tests: deterministic continuous exact/auditor arrivals cannot starve an older worker; urgent exact work still overtakes a fresh worker; aging persists across restart; cancelled/dead waiters do not inherit priority; capacity never exceeds one; existing O859/O784 ordering reproduction. Acceptance: no valid waiter reaches acquire timeout solely because later higher-priority work continues to arrive, and normal wait observability remains informational/self-clearing.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

