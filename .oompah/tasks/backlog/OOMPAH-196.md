---
id: OOMPAH-196
type: task
status: Backlog
priority: 1
title: Provide task and epic release-addendum compatibility over the ledger
parent: OOMPAH-192
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-13T19:32:14.875922Z'
updated_at: '2026-07-13T19:32:14.875922Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Plan reference: plans/release-delivery-commit-inventory.md sections 3.2 and 4.2.

Adapt existing task/epic release-addendum read, approval, retry, and archive paths to use the new project ledger while preserving the documented task-detail API request shapes during the compatibility window. Task and epic views query deliveries by source_identifier; task/epic approval resolves the existing immutable source-commit snapshot and creates ledger entries, never new task metadata addendums.

Acceptance criteria
- Existing task and epic detail screens show historical and new deliveries after migration.
- Approval from a Merged task/epic persists ledger deliveries and wakes the queue.
- Retry/archive only change the selected ledger delivery and enforce valid transitions.
- New approvals do not write oompah.release_addendums metadata or create child backport tasks.

Tests
- Server tests cover task and epic reads/approvals before and after migration, idempotent approval, invalid transitions, and source-commit resolution failures.
- Regression tests prove no legacy metadata entry or child task is created.

Dependencies
- OOMPAH-194 and OOMPAH-195.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

