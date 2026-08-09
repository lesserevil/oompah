---
id: OOMPAH-949
type: bug
status: Open
priority: 1
title: Make fresh-waiter priority regression independent of host scheduling
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T10:18:16.575025Z'
updated_at: '2026-08-09T10:22:00.276625Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-946

Full make test for OOMPAH-946 on 2026-08-09 reached 18,890 passing tests but intermittently failed tests/test_validation_resource_lease.py::test_cancelled_aged_waiter_does_not_transfer_protection: the fresh worker acquired before the fresh exact waiter. The test configures aging_seconds=0.01, so normal host scheduling can age the nominally fresh worker before the exact waiter is durably queued; 634-module coverage and 20 immediate isolated reruns passed. Determine whether the observed ordering is solely the real-clock fixture assumption or exposes a lease selection race. Make the regression deterministic with a controlled clock and explicit freshness boundary if production is correct, or repair the selection fence if exact work can lose while both waiters are provably fresh. Preserve bounded aging and no-starvation from OOMPAH-905, exact urgency for genuinely fresh waiters, FIFO within effective priority, cancellation cleanup, restart persistence, and capacity safety. Required tests: a cancelled aged waiter cannot transfer age; a fresh exact waiter overtakes a provably fresh worker; a genuinely aged worker still receives its fairness boost; repeated focused runs under artificial scheduling delay; complete make test. Acceptance: ordering assertions derive from explicit durable timestamps rather than sub-10ms scheduler timing and the full gate is stable under load.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

