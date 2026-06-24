---
id: OOMPAH-157
type: bug
status: Open
priority: null
title: Add archive action to task detail UI
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-06-24T16:39:56.675340Z'
updated_at: '2026-06-24T16:47:37.060958Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: ccd8c5e5-1dc6-4d38-8c60-8f730385375f
oompah.task_costs:
  total_input_tokens: 144
  total_output_tokens: 4310
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 144
      output_tokens: 4310
      cost_usd: 0.0
  runs:
  - profile: deep
    model: unknown
    input_tokens: 57
    output_tokens: 1792
    cost_usd: 0.0
    recorded_at: '2026-06-24T16:43:05.649419+00:00'
  - profile: deep
    model: unknown
    input_tokens: 15
    output_tokens: 237
    cost_usd: 0.0
    recorded_at: '2026-06-24T16:44:00.896824+00:00'
  - profile: deep
    model: unknown
    input_tokens: 72
    output_tokens: 2281
    cost_usd: 0.0
    recorded_at: '2026-06-24T16:46:53.745285+00:00'
---
## Summary

Task details in the oompah UI expose actions such as Request Changes, Override Readiness, and Promote to Backlog, but there is no visible action to intentionally archive/cancel a task. Users need a Will not do / Cancel / Archive control from the detail view so stale Proposed tasks can be closed without using the CLI.\n\nAcceptance criteria:\n- Task detail UI exposes a clear archive/cancel action for non-terminal tasks.\n- The action updates the task status to Archived through the existing task status API.\n- The UI uses clear wording such as Archive or Will not do, with confirmation if appropriate.\n- Tests cover the button rendering and the status update request.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-24 16:40
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-06-24 16:40
---
Focus: Frontend Developer
---
author: oompah
created: 2026-06-24 16:41
---
Understanding: This task requires adding an Archive/Will not do action to the task detail UI. The UI currently has actions like Request Changes, Override Readiness, and Promote to Backlog, but lacks an archive/cancel option. Plan: (1) Find the task detail UI template/component, (2) Identify where other action buttons are rendered, (3) Add an Archive button that calls the existing task status API to set status to Archived, (4) Add confirmation dialog for safety, (5) Write tests covering button rendering and API call.
---
author: oompah
created: 2026-06-24 16:43
---
Run #1 [attempt=1, profile=deep, role=deep -> Claude/default]
- Turns: 0, Tool calls: 35
- Tokens: 57 in / 1.8K out [1.8K total]
- Cost: $0.0000
- Exit: terminated, Duration: 2m 21s
- Log: OOMPAH-157__20260624T164054Z.jsonl
---
author: oompah
created: 2026-06-24 16:43
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-06-24 16:43
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-24 16:43
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-06-24 16:43
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-24 16:44
---
Run #2 [attempt=2, profile=deep, role=deep -> Claude/default]
- Turns: 0, Tool calls: 15
- Tokens: 15 in / 237 out [252 total]
- Cost: $0.0000
- Exit: terminated, Duration: 32s
- Log: OOMPAH-157__20260624T164337Z.jsonl
---
author: oompah
created: 2026-06-24 16:44
---
Retrying (attempt #2, agent: deep)
---
author: oompah
created: 2026-06-24 16:44
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-24 16:44
---
Duplicate Investigation: Confirmed NOT a duplicate. Searched all tasks for 'archive action', 'cancel', 'task detail UI', and 'will not do'. No existing or previously-handled task covers adding an archive/cancel control to the task detail view. Proceeding with implementation. Plan: (1) find the task detail UI template/component, (2) identify where other action buttons are rendered, (3) add Archive/Will not do button calling the task status API to set Archived, (4) add confirmation for safety, (5) write tests for button rendering and API call.
---
author: oompah
created: 2026-06-24 16:46
---
Run #3 [attempt=3, profile=deep, role=deep -> Claude/default]
- Turns: 0, Tool calls: 68
- Tokens: 72 in / 2.3K out [2.4K total]
- Cost: $0.0000
- Exit: terminated, Duration: 2m 26s
- Log: OOMPAH-157__20260624T164432Z.jsonl
---
author: oompah
created: 2026-06-24 16:47
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-06-24 16:47
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
