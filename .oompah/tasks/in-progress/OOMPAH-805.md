---
id: OOMPAH-805
type: bug
status: In Progress
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
updated_at: '2026-08-04T20:31:02.843464Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: cba73cec0fe5fb0fd392c73cb42cc753d54939c16fe1b15d074df4d3f718d04d
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-04T20:29:29.204697+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-805 describes test-specific determinism fixes\
    \ for two particular test cases (test_run_coalesces_burst_events_into_fewer_ticks\
    \ and test_snapshot_tick_metrics_include_dispatch_timing) under parallel xdist\
    \ load. The required changes are test-specific: replace wall-clock sleeps with\
    \ asyncio event synchronization, stub/drain background maintenance paths, and\
    \ assert no side effects persist. The corpus contains 31 tasks, with the closest\
    \ being OOMPAH-349 and OOMPAH-350 (both archived), which address production infrastructure\
    \ concerns (tracker timeouts and HTTP isolation) rather than test determinism.\
    \ No existing task covers making these specific tests deterministic under parallel\
    \ gate load. OOMPAH-805 is an original bug report with unique scope.\nLooking\
    \ at OOMPAH-805, I need to determine whether this task duplicates an existing\
    \ one. Let me analyze the issue systematically.\n\n## Issue Summary\n\n**OOMPAH-805**\
    \ describes:\n- Intermittent test failures in parallel `make test` runs for two\
    \ specific tests:\n  1. `test_event_driven_loop.py::TestRunEventDrivenLoop::test_run_coalesces_burst_events_into_fewer_ticks`\n\
    \  2. `test_long_tick_regression.py::TestOperatorDiagnostics::test_snapshot_tick_metrics_include_dispatch_timing`\n\
    - Root causes: wall-clock sleeps instead of event synchronization; background\
    \ maintenance work not cleaned up\n- Solution: Replace sleeps with asyncio events,\
    \ drain background work, assert no side effects survive test completion\n\n##\
    \ Corpus Analysis\n\nSearching the provided 31-task corpus for related work:\n\
    \n**Tasks with \"test\" in scope:**\n- OOMPAH-217, OOMPAH-236, OOMPAH-237, OOMPAH-239,\
    \ OOMPAH-242, OOMPAH-291, OOMPAH-31, OOMPAH-349, OOMPAH-350, OOMPAH-792\n\n**Closest\
    \ candidates examined:**\n\n1. **OOMPAH-349** (Archived): \"Make project tracker\
    \ refresh timeouts real\"\n   - Scope: Production code - timeouts for *tracker\
    \ operations* using asyncio.wait_for + executor\n   - NOT about tests; different\
    \ domain entirely (tracker reads vs. event loop tests)\n\n2. **OOMPAH-350** (Archived):\
    \ \"Isolate scheduler execution from the HTTP event loop\"\n   - Scope: Production\
    \ infrastructure - run orchestrator on dedicated thread to prevent HTTP blocking\n\
    \   - NOT about tests; addresses different architectural concern (threading isolation)\n\
    \n3. **OOMPAH-291** (Archived): \"Add prompt-injection regression suite\"\n  \
    \ - Scope: New test suite for security; not about fixing flaky existing tests\n\
    \n4. **OOMPAH-792** (Backlog): \"Run all historical systemic incidents as full-stack\
    \ scenarios\"\n   - Scope: Build new workflow scenario tests; not about making\
    \ specific existing tests deterministic\n\n**Explicitly searched for:**\n- \"\
    event-loop\", \"tick metrics\", \"deterministic\", \"burst events\", \"flak\"\
    , \"xdist\", \"sleep\", \"asyncio events\"\n- No existing"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 9e281e57-3322-435f-81ee-1d34e1d41854
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 2307
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 2307
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2307
    cost_usd: 0.0
    recorded_at: '2026-08-04T20:29:29.202263+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-805__20260804T202731Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-805
    source_sha: a681ec2fc005f339063b3b8e2a139b8ae0b3c379
    completed_at: '2026-08-04T20:29:29.223195+00:00'
---
## Summary

The parallel home-backed make test gate intermittently fails tests/test_event_driven_loop.py::TestRunEventDrivenLoop::test_run_coalesces_burst_events_into_fewer_ticks and tests/test_long_tick_regression.py::TestOperatorDiagnostics::test_snapshot_tick_metrics_include_dispatch_timing, while both pass repeatedly in focused home-backed runs. The burst test stops after fixed sleeps instead of synchronizing on an observed event tick; under xdist load it may stop before the queued burst is processed. The tick-metrics test launches real background maintenance/executor work and can be delayed or leak archived-audit work across test completion despite mocking its foreground phases. This is a recurrence adjacent to OOMPAH-688, OOMPAH-709, and OOMPAH-715. Replace wall-clock sleeps with explicit asyncio events/phase synchronization, stub or drain every background maintenance future/thread-pool path in the diagnostic test, and assert no tracker or archived-audit side effects survive test completion. Required tests: repeat each exact test on OOMPAH_PYTEST_TEMP_ROOT, run both modules serially and with -n 4, then run make test. Acceptance: the tests prove the same coalescing and metric contracts without elapsed-time assumptions, leave no background work, and pass at least 20 repeated parallel full-gate stress runs without flake.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 20:27
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-04 20:27
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-04 20:29
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.3K out [2.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 21s
- Log: OOMPAH-805__20260804T202731Z.jsonl
---
author: oompah
created: 2026-08-04 20:30
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-04 20:31
---
Focus: Oompah Tests Auth Specialist
---
<!-- COMMENTS:END -->
