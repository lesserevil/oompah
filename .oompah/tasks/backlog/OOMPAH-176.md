---
id: OOMPAH-176
type: task
status: Backlog
priority: 1
title: Approve release addendums and snapshot main commits
parent: OOMPAH-172
children: []
blocked_by:
- OOMPAH-173
labels: []
assignee: null
created_at: '2026-07-13T02:35:47.109837Z'
updated_at: '2026-07-13T02:38:04.198233Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Read sections 4.1 and 6 of plans/release-branch-addendums.md. Implement POST /api/v1/issues/{identifier}/release-addendums. Require a task or epic that is Merged on the project default branch; accept only distinct, currently available supported release branches; resolve and persist the ordered full-SHA commit snapshot before creating each open addendum. Use a per-source lock and idempotency key so retries/concurrent requests create at most one active row per branch. Publish one release_addendum_ready event per newly created row after persistence; recover safely if event publication fails. Tests: two-target approval; duplicate request; concurrent approval; invalid/non-merged source; unavailable/default/unsupported target; unresolved commits; atomic all-or-nothing validation; and event failure recovery. Acceptance: approval immediately leaves durable open queue items attached to the source and creates no tracker child task.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

