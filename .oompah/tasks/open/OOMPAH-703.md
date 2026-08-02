---
id: OOMPAH-703
type: bug
status: Open
priority: 1
title: Make backlog refresh invalidation tests wait for completion deterministically
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-02T20:59:10.197769Z'
updated_at: '2026-08-02T21:51:37.480275Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 7379f73edf0db9cd454f28a67b73307d7d36633b8a5f53b98c3407ab3f9291cf
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 4bdbe493-dd5e-403a-9471-86eeb1c5c0af
  claim_owner: 0b22eab2-a2d1-4082-a6c8-404ec37650a4
  claimed_at: '2026-08-02T21:51:30.242736+00:00'
  claim_expires_at: '2026-08-02T22:21:30.242736+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 2c1e8f7a-2093-4362-ae1e-96e3c19e48ca
---
## Summary

Triggered by: OOMPAH-700

CI for OOMPAH-700 exposed a pre-existing timing race in tests/test_release_delivery_refresh.py::TestBacklogRefreshManagerInvalidate::test_invalidate_causes_next_get_or_start_to_refresh on Python 3.11: the test sleeps for 50 ms after scheduling BacklogRefreshManager background work and sometimes observes one service call instead of two. Replace fixed-duration sleeps in this invalidate test and adjacent BacklogRefreshManager tests with deterministic synchronization on refresh completion. Prefer an existing status/result completion signal; if production code needs a narrowly scoped awaitable completion primitive, add it in oompah/release_delivery_refresh.py with unit coverage and without changing non-test refresh semantics. Add regression coverage that invalidation starts exactly one subsequent refresh, preserves stale-while-revalidate behavior, and is reliable under repeated Python 3.11 execution. Acceptance criteria: the formerly failing test no longer relies on wall-clock sleeps to infer completion; adjacent invalidation tests use deterministic synchronization where applicable; a repeated focused run passes; make test and make check-secrets pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-02 21:51
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-02 21:51
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
