---
id: OOMPAH-688
type: task
status: Backlog
priority: null
title: Make slow-tick telemetry tests deterministic under load
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-01T23:11:33.946132Z'
updated_at: '2026-08-01T23:11:33.946132Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Observed twice during operator recovery on 2026-08-01: tests/test_orchestrator_tick_telemetry.py::TestSlowTickSubstepLogging::test_no_slow_tick_warning_for_fast_ticks failed only in the parallel full branch gate, while the exact test and clean full reruns passed. The assertion uses a one-second timing boundary and can classify an otherwise fast synthetic tick as slow when the host is contended, producing false Needs CI Fix transitions for unrelated task heads (most recently OOMPAH-685 at 94d7ce2f7).\n\nImplementation scope:\n- Replace wall-clock/load-sensitive behavior in the slow-tick telemetry test with deterministic clock injection or an equivalent controlled elapsed-time seam.\n- Audit adjacent tick telemetry tests for the same real-time threshold pattern and convert them to deterministic time control without weakening production slow-tick logging.\n- Preserve coverage that genuinely fast ticks do not warn and slow ticks report the expected phase/substep breakdown.\n\nRelevant context: tests/test_orchestrator_tick_telemetry.py and the orchestrator tick timing/logging helpers.\n\nRequired tests:\n- Deterministically exercise elapsed time below, at, and above the configured slow-tick threshold.\n- Demonstrate repeated execution is stable under parallel pytest load.\n- Run the focused telemetry suite and make test.\n\nAcceptance criteria:\n- The test no longer depends on scheduler/host wall-clock timing.\n- Production thresholds and telemetry semantics remain unchanged.\n- Focused tests and the full Makefile gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

