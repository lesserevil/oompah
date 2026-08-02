---
id: OOMPAH-703
type: bug
status: In Progress
priority: 1
title: Make backlog refresh invalidation tests wait for completion deterministically
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-02T20:59:10.197769Z'
updated_at: '2026-08-02T21:57:14.250795Z'
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
  verdict: no_duplicate
  checked_at: '2026-08-02T21:53:57.558386+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector  \nDuplicate preflight verdict: no_duplicate\
    \  \nMatches: none  \n\nEvidence: No active peer task covers deterministic synchronization\
    \ for `BacklogRefreshManager` invalidation tests. Closest reviewed tasks, OOMPAH-158\
    \ and OOMPAH-175, are terminal and address unrelated cache behavior."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 1
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: d3a84912-b6d8-4191-bfce-6cfbb56d0fad
oompah.task_costs:
  total_input_tokens: 50524
  total_output_tokens: 1662
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 50524
      output_tokens: 1662
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1336
    cost_usd: 0.0
    recorded_at: '2026-08-02T21:52:08.225263+00:00'
  - profile: default
    model: haiku
    input_tokens: 50514
    output_tokens: 326
    cost_usd: 0.0
    recorded_at: '2026-08-02T21:53:57.556844+00:00'
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
  - run_id: OOMPAH-703__20260802T215345Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-703
    source_sha: 366129d0a5046c5ed7caed4acf26cd8cd2a3fbdd
    completed_at: '2026-08-02T21:53:57.596053+00:00'
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
author: oompah
created: 2026-08-02 21:53
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 50.5K in / 326 out [50.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 18s
- Log: OOMPAH-703__20260802T215345Z.jsonl
---
author: oompah
created: 2026-08-02 21:54
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-02 21:54
---
Focus: Test Engineer
---
author: oompah
created: 2026-08-02 21:54
---
Understanding: I will inspect BacklogRefreshManager and its invalidation tests, replace wall-clock completion assumptions with deterministic synchronization, add regression coverage for one subsequent refresh and stale-while-revalidate behavior, then run focused checks and the required Makefile validation.
---
author: oompah
created: 2026-08-02 21:55
---
Discovery: refresh jobs already own an asyncio.Task, and _run records terminal complete/failed state before the task finishes; however, tests cannot await that task through the public API. I will add a narrowly scoped wait_for_completion(project_id, branch) method that shields the refresh task from caller cancellation and returns the terminal RefreshStatus, then use it in the invalidate tests. This preserves stale-while-revalidate and normal refresh behavior while making completion synchronization explicit.
---
author: oompah
created: 2026-08-02 21:57
---
Implementation: added BacklogRefreshManager.wait_for_completion(), which awaits the existing job task without cancelling refresh work and returns terminal complete/failed status (or None for an unknown key). Added success, failure, and no-job unit coverage. Reworked all applicable invalidate tests to await completion, strengthened stale-while-revalidate assertions to verify the old result is served then replaced, and kept the exact one-subsequent-call assertion.
---
<!-- COMMENTS:END -->
