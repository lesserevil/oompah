---
id: OOMPAH-709
type: task
status: Backlog
priority: null
title: Make tick-delegation tests deterministic under parallel full-suite execution
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-02T23:17:45.073003Z'
updated_at: '2026-08-02T23:17:45.073003Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-702 and OOMPAH-707

Production evidence on 2026-08-02: the isolated branch gate for unchanged OOMPAH-702 head c3c4698482dd2f8260758a381c8329e30f5b5ed2 passed 15,010 tests but failed tests/test_orchestrator_handlers.py::TestTickDelegation::test_tick_handler_order. Minutes earlier, OOMPAH-707 full parallel verification passed 15,020 tests but failed the adjacent TestTickDelegation::test_tick_runs_watchdog; that exact test passed immediately in a serial rerun. OOMPAH-706 full parallel make test passed the same area, showing scheduler/inter-test timing rather than either candidate implementation determines the outcome.

Implementation scope:
- Reproduce both TickDelegation failures under repeated parallel execution and identify the shared state, background maintenance, or ordering assumption that leaks between tests.
- Replace wall-clock/thread scheduling assumptions with explicit barriers or fully isolated orchestrator state.
- Ensure each test waits for the exact delegated handler completion it asserts and tears down every background future/executor.
- Preserve production tick handler order and concurrency; do not serialize the live scheduler merely to satisfy tests.

Relevant code: tests/test_orchestrator_handlers.py TestTickDelegation, oompah/orchestrator.py tick delegation/maintenance scheduling, and shared fixtures or executor teardown used by the full xdist gate.

Required tests:
- Repeated parallel runs of test_tick_handler_order and test_tick_runs_watchdog cannot fail from another worker or pending maintenance callback.
- Delayed handler scheduling is synchronized without sleeps.
- Background handler exceptions remain observable.
- Focused orchestrator tests and make test/check-secrets pass.

Acceptance criteria:
- The OOMPAH-702 and OOMPAH-707 unrelated full-gate failures cannot recur from scheduling order.
- Tests assert explicit completion and leave no live background work.
- Production scheduler semantics remain unchanged.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

