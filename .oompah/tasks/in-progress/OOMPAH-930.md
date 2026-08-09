---
id: OOMPAH-930
type: task
status: In Progress
priority: null
title: Isolate event-loop and close-race tests from live project reconciliation
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T03:11:25.306117Z'
updated_at: '2026-08-09T03:11:59.558129Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

The exact OOMPAH-929 gate reproducibly times out in tests/test_event_driven_loop.py and tests/test_dispatch_close_race.py because directly constructed Orchestrator fixtures retain unmocked startup/state-publication reconcilers that traverse the operator's live WORKFLOW.md projects and native task corpus. A serial reproduction shows TestRunEventDrivenLoop::test_run_calls_tick_on_startup blocked in _reconcile_owner_duplicate_resolution_boundaries reading real Exocomp/Oompah task Markdown until pytest's five-second timeout; close-race TestClient fixtures similarly expose live snapshot work through module-global server state. Implementation scope: make these unit fixtures explicitly isolate every unrelated startup reconciler, project binding, state publisher, and observer path while preserving the behavior each test claims to exercise; do not weaken production startup, lifecycle, transition, or cleanup behavior and do not merely extend timeouts. Relevant files: tests/test_event_driven_loop.py, tests/test_dispatch_close_race.py, shared test factories/fixtures if appropriate, and production only if an actual boundary defect is demonstrated. Required tests: both complete modules pass serially and in parallel with a large live task corpus present; focused failing cases repeat at least 20 times; fixture teardown leaves no event-loop tasks, threads, timers, or module-global orchestrator leakage; exact make test passes. Acceptance: these unit tests never read configured live project trackers or invoke unrelated Git/forge work, remain deterministic under parallel load, and retain assertions for shutdown/event coalescing and retry cancellation races.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

