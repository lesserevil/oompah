---
id: OOMPAH-640
type: task
status: Backlog
priority: null
title: Complete combined stall-to-dispatch recovery regression coverage
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T05:59:47.260716Z'
updated_at: '2026-07-31T05:59:47.260716Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Follow-up to OOMPAH-417 after parent epic OOMPAH-414 merged. Implementation scope: add the missing integrated regression that exercises a stale dispatch loop recovery, orphaned In Progress tasks reset to Open, the REFRESH_REQUESTED wake, and dispatch of both recovered tasks on the next event-driven tick. Reuse the shipped OOMPAH-415 threshold behavior and OOMPAH-416 orphan-reset wake; do not rewrite those features. Relevant files: tests/test_dispatch_loop_heartbeat.py, tests/test_orphan_reset_dispatch_wake.py, or a focused new regression module, with only production changes if the combined test exposes a real bug. Required tests: prove recovery occurs before the legacy 15-minute threshold; prove one wake is posted after multiple resets; prove two recovered eligible tasks are dispatched without waiting for full sync; cover duplicate wake/tick idempotency. Acceptance: the combined July 23 failure path is deterministic and green, focused tests pass, terminal mutation scan passes, and make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

