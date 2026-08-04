---
id: OOMPAH-798
type: task
status: Backlog
priority: 1
title: Split the monolithic orchestrator into cohesive workflow modules
parent: OOMPAH-771
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-794
labels: []
assignee: null
created_at: '2026-08-04T13:59:30.266221Z'
updated_at: '2026-08-04T14:07:38.596906Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
---
## Summary

Refactor the remaining orchestrator after legacy deletion into explicit adapters/coordinators: event intake/fact refresh, decision scheduling, durable jobs, transitions, integration, audit, review, implementation ownership, epics, liveness, and housekeeping. Keep pure models/evaluators independent of I/O and enforce import boundaries. Preserve public API/orchestrator compatibility during extraction. Required tests: architectural dependency rules, no import cycles, focused module tests, startup/shutdown/reload, concurrency and full make test. Acceptance: orchestrator.py becomes a thin composition root; workflow modules have clear single ownership and substantially lower per-file branch complexity.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

