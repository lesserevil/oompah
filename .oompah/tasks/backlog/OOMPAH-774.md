---
id: OOMPAH-774
type: task
status: Backlog
priority: 1
title: Build replayable fixtures for historical stuck-task incidents
parent: OOMPAH-764
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T13:58:46.269128Z'
updated_at: '2026-08-04T13:58:46.269128Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Convert the systemic incident set OOMPAH-562, OOMPAH-731, OOMPAH-732, OOMPAH-739, OOMPAH-748, OOMPAH-749, and OOMPAH-751 into durable scenario fixtures with authoritative before/after facts and expected decisions. Capture mixed integration row ordering, self-invalidating epic maintenance, benign metadata authority churn, deleted source branches after merge, nested target cycles, audit-history starvation, and advisory peer-denial poisoning. Use native Markdown tracker and temporary Git where feasible; mocks may isolate unavailable forge transport but not replace lifecycle composition. Acceptance: every incident fails against the pre-fix model or asserts its historical failure condition, replays deterministically, and is reusable by transition, evaluator, job, liveness, and scale tests.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

