---
id: OOMPAH-812
type: task
status: In Progress
priority: null
title: Drain synthetic long-tick ordering fixtures under full-gate load
parent: OOMPAH-768
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T22:47:56.569040Z'
updated_at: '2026-08-04T22:48:21.494857Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live exact-head gate reproduction on OOMPAH-781 at 41f717cd46baf4e8ba455586b39ce9e67d25a471: make test passed 15,741 tests but failed tests/test_long_tick_regression.py::TestSyntheticSlowJobs::test_heal_repos_always_runs_after_dispatch_needed after 643s. The test asserts dispatch-before-maintenance ordering, but it constructs a real Orchestrator, schedules multiple fire-and-forget executor futures/stores in _tick(), awaits only _maintenance_future, and exits without draining/closing the other owned background work. The exact test passes focused and 100/100 direct same-process invocations, so this is a full-load lifecycle/timeout race adjacent to OOMPAH-805 rather than terminal-audit product behavior. Implementation scope: make this ordering fixture deterministic without weakening its structural assertion; stub irrelevant background lanes, synchronize on the actual maintenance action, and drain/close every orchestrator-owned future, pool, and durable store in finally. Give the test a lifecycle-sized timeout only if deterministic cleanup can legitimately exceed the global five-second unit budget under parallel load. Audit neighboring TestSyntheticSlowJobs fixtures for the same leak and repair only concrete cases. Required tests: the exact test repeated in one process, complete test_long_tick_regression module serially and with xdist, combined event-loop/long-tick/orchestrator fixture slice, terminal mutation scan, and the server exact full gate after landing. Acceptance: dispatch_needed always precedes heal_repos; no executor thread/future/store survives the test; the OOMPAH-781 combined gate can rerun without a load-only timeout.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

