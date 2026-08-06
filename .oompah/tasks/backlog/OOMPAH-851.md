---
id: OOMPAH-851
type: bug
status: Backlog
priority: 1
title: Make every tick-test dispatch mock honor the timing mapping contract
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T04:40:40.631980Z'
updated_at: '2026-08-06T04:40:40.631980Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Regression evidence: OOMPAH-791 exact-head gate 0b5b039a failed tests/test_orchestrator_handlers.py::TestRunStep5cEpicMaintenance::test_tick_skips_new_epic_maintenance_when_previous_still_running after 16,192 passes. The test uses _handle_dispatch_needed = AsyncMock(), whose awaited value is another AsyncMock; when host load makes _tick exceed the slow-tick threshold, production correctly calls dispatch_timings.items() and the synthetic mock violates the Mapping contract. Static audit found six remaining bare assignments: tests/test_long_tick_regression.py:741, tests/test_dispatch_loop_heartbeat.py:615, and tests/test_orchestrator_handlers.py around 1385, 2612, 3167, and 3457, versus 21 faithful return_value={} mocks. Implementation scope: convert and audit every _tick unit-test mock so _handle_dispatch_needed returns a real timing Mapping; add a deterministic slow-path regression that forces elapsed time past the threshold and proves the target behavior remains valid; do not suppress production diagnostics or raise global timeouts. Relevant files: the three named test modules and shared orchestrator test helpers; production code only if a typed seam is required. Required tests: each converted test in forced fast and slow timing paths, affected modules serial and -n 4, static guard or helper coverage preventing new bare mocks, and make test. Acceptance criteria: no _tick test supplies a non-Mapping dispatch result; the observed maintenance-future test passes even when the slow path is deterministically forced; production timing telemetry remains unchanged; canonical full gate is stable under load.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

