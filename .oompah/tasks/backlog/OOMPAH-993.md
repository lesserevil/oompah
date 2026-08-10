---
id: OOMPAH-993
type: bug
status: Backlog
priority: 1
title: Make standalone delivery mutations lock-safe across thread offloads
parent: OOMPAH-992
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T10:52:26.512449Z'
updated_at: '2026-08-10T10:52:26.512449Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Replace the lock-spanning standalone-delivery mutation path with admitted, generation-bound operations so TaskTransitionService and tracker I/O never run while the project write lock or standalone delivery authority lock is held. Reproduce the quality-gate failure deadlock against ProvenanceGuardedTracker, preserve revocation and ABA/supersession semantics, and add focused tests proving the transition completes to Needs CI Fix and tracker callbacks execute without the project lock.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

