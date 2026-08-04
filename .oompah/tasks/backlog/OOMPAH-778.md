---
id: OOMPAH-778
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
created_at: '2026-08-04T13:58:53.917290Z'
updated_at: '2026-08-04T13:58:53.917290Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Inventory and migrate every orchestrator.py status mutation to TaskTransitionService, preserving each call site reason, authority, exact-head/generation fence, and recovery behavior. Cover dispatch, worker exit, retry, integration, review, epic rollup, duplicate screening, watchdog, CI/rebase repair, and direct maintenance. Refactor callers to consume TransitionOutcome rather than assuming tracker writes succeed. Required focused tests for each migrated family plus race/restart tests; no terminal safety bypass. Acceptance: orchestrator.py contains no direct task-status update_issue call, stale/rejected transitions cannot mutate newer work, and existing lifecycle tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

