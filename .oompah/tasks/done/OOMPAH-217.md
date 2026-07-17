---
id: OOMPAH-217
type: task
status: Done
priority: null
title: Handoff cleared duplicate investigations to normal-focus agents
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-17T03:17:53.831077Z'
updated_at: '2026-07-17T03:24:36.279751Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 63d0c7b0-ce67-4448-b0fe-1ec4f8d8e4fe
oompah.task_costs:
  total_input_tokens: 77
  total_output_tokens: 1706
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 77
      output_tokens: 1706
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 30
    output_tokens: 698
    cost_usd: 0.0
    recorded_at: '2026-07-17T03:21:15.914147+00:00'
  - profile: standard
    model: unknown
    input_tokens: 9
    output_tokens: 3
    cost_usd: 0.0
    recorded_at: '2026-07-17T03:21:53.973718+00:00'
  - profile: standard
    model: unknown
    input_tokens: 38
    output_tokens: 1005
    cost_usd: 0.0
    recorded_at: '2026-07-17T03:23:28.078779+00:00'
---
## Summary

Implement a two-stage agent workflow for tasks flagged by duplicate detection.

The initial Duplicate Investigator run must only determine whether the task duplicates a closed task. If it archives the task, no further work runs. If it completes normally while the task remains active, Oompah must record that screening cleared, prevent the same duplicate flag from being re-applied, return the task to Open, and promptly dispatch a fresh agent session with normal focus.

Update Duplicate Investigator instructions so it does not implement the task after clearing duplicate screening. Add focused tests for: terminal duplicate has no handoff; active cleared task is marked screened and reopened; later focus selection is not duplicate_detector; duplicate detection skips screened tasks. Run make test.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-17 03:20
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-17 03:20
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-17 03:21
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 19
- Tokens: 30 in / 698 out [728 total]
- Cost: $0.0000
- Exit: terminated, Duration: 1m 10s
- Log: OOMPAH-217__20260717T032011Z.jsonl
---
author: oompah
created: 2026-07-17 03:21
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-17 03:21
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-17 03:21
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-17 03:21
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-17 03:21
---
Run #2 [attempt=2, profile=standard, role=standard -> Claude/default]
- Turns: 0, Tool calls: 2
- Tokens: 9 in / 3 out [12 total]
- Cost: $0.0000
- Exit: terminated, Duration: 18s
- Log: OOMPAH-217__20260717T032143Z.jsonl
---
author: oompah
created: 2026-07-17 03:22
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-17 03:22
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-17 03:22
---
Retrying (attempt #2, agent: standard)
---
author: oompah
created: 2026-07-17 03:22
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-17 03:23
---
Run #3 [attempt=3, profile=standard, role=standard -> Claude/default]
- Turns: 0, Tool calls: 43
- Tokens: 38 in / 1.0K out [1.0K total]
- Cost: $0.0000
- Exit: terminated, Duration: 1m 4s
- Log: OOMPAH-217__20260717T032235Z.jsonl
---
author: oompah
created: 2026-07-17 03:24
---
Implemented and pushed 2615bb98. Added generic focus-complete and needs handoffs, mandatory structured task handoff comments, re-triage into a fresh agent session, and duplicate-investigator integration. make test passed (9235 tests).
---
author: oompah
created: 2026-07-17 03:24
---
Understanding: This task requires a two-stage workflow for duplicate-detection. Currently, when a closed-issue match is found, oompah adds needs:duplicate_detector to the task and dispatches a Duplicate Investigator. But when the investigator clears the duplicate (doesnt archive), oompah falls through to the generic completed without closing path. Planned changes: 1) _on_worker_exit: when focus==duplicate_detector and task still active, add duplicate-screened label and reset to Open; 2) _apply_duplicate_detection: skip tasks with duplicate-screened; 3) Focus instructions: dont implement after clearing; 4) Tests: 4 focused tests.
---
author: oompah
created: 2026-07-17 03:24
---
Implemented focus handoff workflow in 2615bb98; full test suite passed.
---
<!-- COMMENTS:END -->
