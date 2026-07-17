---
id: OOMPAH-217
type: task
status: In Progress
priority: null
title: Handoff cleared duplicate investigations to normal-focus agents
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-17T03:17:53.831077Z'
updated_at: '2026-07-17T03:21:35.297188Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 19085470-fac0-47eb-8048-df00e0e407a2
oompah.task_costs:
  total_input_tokens: 30
  total_output_tokens: 698
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 30
      output_tokens: 698
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 30
    output_tokens: 698
    cost_usd: 0.0
    recorded_at: '2026-07-17T03:21:15.914147+00:00'
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
<!-- COMMENTS:END -->
