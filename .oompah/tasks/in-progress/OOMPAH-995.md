---
id: OOMPAH-995
type: bug
status: In Progress
priority: 1
title: Move gate and workflow publication I/O outside project locks
parent: OOMPAH-992
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T10:52:35.641259Z'
updated_at: '2026-08-10T10:53:06.610034Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Refactor quality-gate result and workflow publication so tracker reads, Git head/dependency checks, state-branch generation, and diff work occur outside project and delivery-authority locks. Use external preflight followed by a constant-time in-memory generation/CAS finalization that rejects superseded results while preserving terminal-first, result-first, head-change, and dependency-change behavior. Add barrier-based concurrency tests proving publication I/O is lock-free and unrelated task creation and health/control requests remain responsive.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

