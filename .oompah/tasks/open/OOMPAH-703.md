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
updated_at: '2026-08-02T21:53:41.869963Z'
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
  claim_id: 601acbeb-0cec-4b94-b478-33726134b71c
  claim_owner: 0b22eab2-a2d1-4082-a6c8-404ec37650a4
  claimed_at: '2026-08-02T21:53:32.579136+00:00'
  claim_expires_at: '2026-08-02T22:23:32.579136+00:00'
  retry_count: 1
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: dc4d31ea-156e-4dbf-97e0-e40f8b6a17d3
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1336
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1336
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1336
    cost_usd: 0.0
    recorded_at: '2026-08-02T21:52:08.225263+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-703__20260802T215147Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-703
    source_sha: 366129d0a5046c5ed7caed4acf26cd8cd2a3fbdd
    completed_at: '2026-08-02T21:52:11.278492+00:00'
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
author: oompah
created: 2026-08-02 21:52
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.3K out [1.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 33s
- Log: OOMPAH-703__20260802T215147Z.jsonl
---
author: oompah
created: 2026-08-02 21:53
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-02 21:53
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
