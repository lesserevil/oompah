---
id: OOMPAH-349
type: bug
status: In Progress
priority: 1
title: Make project tracker refresh timeouts real
parent: OOMPAH-348
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-22T00:56:34.088413Z'
updated_at: '2026-07-22T01:12:48.243897Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Problem: candidate and in-progress project refreshes call synchronous tracker methods inside an inner asyncio event loop. asyncio.wait_for cannot interrupt that blocking call, so the configured refresh timeout is ineffective; production candidate fetch blocked for 218 seconds.

Implement: execute each blocking tracker read in a worker executor, then apply asyncio timeout to the awaited future. Preserve per-project concurrency limits and stale-cache fallback. Cancellation/timeout must not leave unbounded queued work or leak executor tasks. Ensure candidate and in-progress refreshes share the safe helper.

Tests: simulate a blocking tracker read; assert the operation returns stale/empty data within configured timeout, records timeout metrics, and other projects still complete. Regression test that the old inner-loop blocking pattern cannot exceed the configured timeout.

Acceptance: a single hung tracker operation cannot stall the scheduler beyond project_refresh_timeout_ms plus small scheduling overhead; healthy projects remain dispatchable; make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 01:07
---
Implemented bounded candidate refreshes: blocking tracker reads enter the executor before the per-project deadline, stale data is used on timeout, and an in-flight hung read is reused rather than stacking workers. Regression coverage added; full suite is running.
---
<!-- COMMENTS:END -->
