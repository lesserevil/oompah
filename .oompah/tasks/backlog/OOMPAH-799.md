---
id: OOMPAH-799
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
created_at: '2026-08-04T14:00:44.163423Z'
updated_at: '2026-08-04T14:00:44.163423Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Convert OOMPAH-562/731/732/739/748/749/751 into deterministic scenario fixtures covering mixed queue rows, self-invalidating epic maintenance, benign metadata authority churn, deleted branches, nested target cycles, audit-history starvation, and peer-denial poisoning. Use native Markdown tracker and temporary Git where feasible. Tests must assert historical failure conditions and reusable expected facts/decisions. Acceptance: every incident replays deterministically and is reusable by evaluator, job, liveness, and full-stack suites.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

