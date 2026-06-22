---
id: OOMPAH-29
type: task
status: Backlog
priority: 1
title: Audit GitHub Issues intake reconciliation
parent: OOMPAH-27
children: []
blocked_by:
- OOMPAH-28
labels: []
assignee: null
created_at: '2026-06-22T01:16:57.697390Z'
updated_at: '2026-06-22T01:18:10.994938Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Plan: plans/oompah-1.0-release.md#managed-project-workflow-readiness

WHAT TO DO
Audit GitHub Issues intake reconciliation for open, closed, and reopened external issues.

EXPECTED BEHAVIOR
- Open external issue without an internal task creates an internal proposed task.
- Closed external issue archives a non-terminal internal task.
- Reopened external issue returns the internal task to proposed and runs the normal intake flow.

HOW TO VERIFY
Tests or documented manual checks cover all three cases.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

