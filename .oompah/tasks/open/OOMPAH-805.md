---
id: OOMPAH-805
type: bug
status: Open
priority: 1
title: Make residual event-loop and tick-metrics tests deterministic under full-gate
  load
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T20:18:59.284253Z'
updated_at: '2026-08-04T20:21:05.401614Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

The parallel home-backed make test gate intermittently fails tests/test_event_driven_loop.py::TestRunEventDrivenLoop::test_run_coalesces_burst_events_into_fewer_ticks and tests/test_long_tick_regression.py::TestOperatorDiagnostics::test_snapshot_tick_metrics_include_dispatch_timing, while both pass repeatedly in focused home-backed runs. The burst test stops after fixed sleeps instead of synchronizing on an observed event tick; under xdist load it may stop before the queued burst is processed. The tick-metrics test launches real background maintenance/executor work and can be delayed or leak archived-audit work across test completion despite mocking its foreground phases. This is a recurrence adjacent to OOMPAH-688, OOMPAH-709, and OOMPAH-715. Replace wall-clock sleeps with explicit asyncio events/phase synchronization, stub or drain every background maintenance future/thread-pool path in the diagnostic test, and assert no tracker or archived-audit side effects survive test completion. Required tests: repeat each exact test on OOMPAH_PYTEST_TEMP_ROOT, run both modules serially and with -n 4, then run make test. Acceptance: the tests prove the same coalescing and metric contracts without elapsed-time assumptions, leave no background work, and pass at least 20 repeated parallel full-gate stress runs without flake.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

