---
id: OOMPAH-348
type: epic
status: In Progress
priority: 1
title: Eliminate Oompah service wedge failure modes
parent: null
children:
- OOMPAH-349
- OOMPAH-350
- OOMPAH-351
- OOMPAH-352
blocked_by: []
labels:
- reliability
- service-wedge
assignee: null
created_at: '2026-07-22T00:56:17.834972Z'
updated_at: '2026-07-22T01:12:46.941701Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implement and verify the durable reliability fixes identified from production wedge incidents: enforce real tracker timeouts, separate scheduler work from HTTP serving, bound shutdown, and capture diagnostics for any future stall. Child tasks define the independently testable implementation units. Success means a slow or hung tracker/git operation cannot make the UI/API unresponsive or prevent a restart.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

