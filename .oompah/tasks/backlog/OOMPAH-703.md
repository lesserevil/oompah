---
id: OOMPAH-703
type: bug
status: Backlog
priority: 1
title: Make backlog refresh invalidation tests wait for completion deterministically
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-02T20:59:10.197769Z'
updated_at: '2026-08-02T20:59:10.197769Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-700

CI for OOMPAH-700 exposed a pre-existing timing race in tests/test_release_delivery_refresh.py::TestBacklogRefreshManagerInvalidate::test_invalidate_causes_next_get_or_start_to_refresh on Python 3.11: the test sleeps for 50 ms after scheduling BacklogRefreshManager background work and sometimes observes one service call instead of two. Replace fixed-duration sleeps in this invalidate test and adjacent BacklogRefreshManager tests with deterministic synchronization on refresh completion. Prefer an existing status/result completion signal; if production code needs a narrowly scoped awaitable completion primitive, add it in oompah/release_delivery_refresh.py with unit coverage and without changing non-test refresh semantics. Add regression coverage that invalidation starts exactly one subsequent refresh, preserves stale-while-revalidate behavior, and is reliable under repeated Python 3.11 execution. Acceptance criteria: the formerly failing test no longer relies on wall-clock sleeps to infer completion; adjacent invalidation tests use deterministic synchronization where applicable; a repeated focused run passes; make test and make check-secrets pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

