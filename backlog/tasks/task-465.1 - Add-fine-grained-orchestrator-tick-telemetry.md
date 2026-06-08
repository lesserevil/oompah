---
id: TASK-465.1
title: Add fine-grained orchestrator tick telemetry
status: Done
assignee: []
created_date: 2026-06-08 18:47
updated_date: 2026-06-08 19:19
labels:
- task
- tick-latency
- dispatch-performance
dependencies: []
priority: 0
references:
- oompah/orchestrator.py
modified_files:
- oompah/orchestrator.py
- tests/test_orchestrator_handlers.py
parent_task_id: TASK-465
ordinal: 2
oompah.task_costs:
  total_input_tokens: 61
  total_output_tokens: 30561
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 61
      output_tokens: 30561
      cost_usd: 0.0
  runs:
  - profile: standard
    model: unknown
    input_tokens: 61
    output_tokens: 30561
    cost_usd: 0.0
    recorded_at: '2026-06-08T19:19:08.483928+00:00'
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Instrument _tick() and _handle_dispatch_needed() with substep timings so slow-tick logs and state snapshots show exactly where time is spent. Break dispatch timing into candidate fetch, blocker pre-resolution, duplicate detection, candidate selection, normal dispatch, epic planning, epic close/PR maintenance, staleness checks, rebase filing, orphan reset, watchdog, and repo self-heal. Keep log volume bounded and avoid exposing secrets in snapshots.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Slow-tick log output reports nested dispatch substep timings instead of one aggregate dispatch number.
- [ ] #2 State snapshots expose recent tick timing summaries suitable for the dashboard without secrets.
- [ ] #3 Tests cover timing collection and verify disabled or missing timings do not break existing snapshots.
<!-- AC:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 1
author: oompah
created: 2026-06-08 19:06

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 2
author: oompah
created: 2026-06-08 19:06

Focus: Test Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3
author: oompah
created: 2026-06-08 19:19

Agent completed successfully in 783s (30622 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 4
author: oompah
created: 2026-06-08 19:19

Run #1 [attempt=1, profile=standard, role=standard -> Claude/default]
- Turns: 104, Tool calls: 62
- Tokens: 61 in / 30.6K out [30.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 13m 3s
- Log: TASK-465.1__20260608T190627Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Instrumented _tick() and _handle_dispatch_needed() with fine-grained substep telemetry. _handle_dispatch_needed() now returns dict[str,float] with 10 substep timing keys. _tick() stores full breakdown in _last_tick_timings including watchdog_ms and heal_ms. Slow-tick log includes inline dispatch substep detail. get_snapshot() exposes tick_timings for dashboard (numeric only, no secrets). New test file tests/test_orchestrator_tick_telemetry.py with 34 tests covering all 3 acceptance criteria. All 178 tests pass.
<!-- SECTION:FINAL_SUMMARY:END -->
