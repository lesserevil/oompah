---
id: OOMPAH-202
type: task
status: Backlog
priority: 1
title: Run end-to-end release delivery migration and regression coverage
parent: OOMPAH-192
children: []
blocked_by:
- OOMPAH-194
- OOMPAH-195
labels: []
assignee: null
created_at: '2026-07-13T19:33:31.162292Z'
updated_at: '2026-07-13T19:36:34.064697Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Plan reference: plans/release-delivery-commit-inventory.md section 7.

Create integration coverage that exercises the released feature across ledger migration, task/epic compatibility, direct commit selection, queue/executor behavior, PR evidence, and inventory rendering. This is the final verification task; do not add product behavior except narrowly scoped test-harness fixes.

Acceptance criteria
- A migrated existing task/epic delivery remains visible and has no duplicate PR after the new UI/API is used.
- A direct main commit can be selected for two release branches, creates two independent ledger deliveries, and does not create a task.
- A merged cherry-pick reports Delivered using source-to-result mapping; a shared-history delivery reports Delivered by ancestry.
- Blocked, retry, archived, unavailable-target, source-head-change, and concurrent/idempotent operator scenarios are covered.
- Full make test passes.

Tests
- Add end-to-end tests using temporary Git repositories and mocked SCM/PR operations for all acceptance scenarios above.
- Run make test and attach the exact result to the task handoff.

Dependencies
- OOMPAH-194, OOMPAH-195, OOMPAH-196, OOMPAH-198, OOMPAH-199, OOMPAH-200, and OOMPAH-201.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

