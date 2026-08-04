---
id: OOMPAH-802
type: task
status: Backlog
priority: 1
title: Route orchestrator lifecycle writes through TaskTransitionService
parent: OOMPAH-769
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T14:00:59.248935Z'
updated_at: '2026-08-04T14:00:59.248935Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Migrate all orchestrator.py status writes across dispatch, worker exit, retry, integration, review, epic rollup, duplicate screening, watchdog, CI/rebase, and maintenance. Preserve reason, authority, exact-head generation, and recovery semantics. Add family-focused race/restart tests. Acceptance: orchestrator has no direct task-status update_issue calls and stale outcomes cannot mutate newer work.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

