---
id: OOMPAH-723
type: task
status: Backlog
priority: null
title: Isolate maintenance-lane nonblocking test from awaited tracker I/O
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T15:20:07.046080Z'
updated_at: '2026-08-03T15:20:07.046080Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by the exact-head OOMPAH-722 full gate on 2026-08-03: make test passed 15,119 tests but failed tests/test_orchestrator_handlers.py::TestMaintenanceLaneNonBlocking::test_tick_does_not_await_maintenance_heal. The test intends to prove _tick does not await _run_step5b_maintenance, but it leaves _recover_release_addendum_leases unstubbed even though the adjacent test documents that this awaited tracker scan can exceed the suite timeout under four-worker load. The result is a race/load-dependent failure unrelated to the branch under test.\n\nImplementation scope:\n- Reproduce the full-gate failure under parallel load.\n- Isolate test_tick_does_not_await_maintenance_heal from unrelated awaited tracker/filesystem work, using the same deterministic stub pattern as test_tick_starts_maintenance_future.\n- Preserve the structural invariant: _maintenance_future exists, remains pending when _tick returns, and finishes only after the explicit unblock.\n- Do not weaken the assertion into a broad wall-clock allowance.\n- Audit neighboring maintenance-lane tests for the same missing stub without broad unrelated rewrites.\n\nRequired tests:\n- Run the focused test repeatedly and the complete tests/test_orchestrator_handlers.py module serially and under the project parallel runner.\n- Run make test at the exact repair head.\n\nAcceptance criteria:\n- The test cannot fail because _recover_release_addendum_leases or other unrelated awaited I/O is slow.\n- A real regression where _tick awaits maintenance still fails deterministically.\n- No production behavior changes are required unless the focused reproduction proves _tick itself is incorrect.\n\nIn-flight workaround: OOMPAH-722's automatically dispatched CI Failure Fixer is applying the isolated repair on that task branch so its exact-head gate can continue; link the resulting commit here and retire this bug when the repair lands.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

