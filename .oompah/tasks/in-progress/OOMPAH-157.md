---
id: OOMPAH-157
type: bug
status: In Progress
priority: null
title: Add archive action to task detail UI
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-06-24T16:39:56.675340Z'
updated_at: '2026-06-24T16:43:31.352225Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 3e00f7c4-ad15-4abf-b206-3c8e0214312a
oompah.task_costs:
  total_input_tokens: 57
  total_output_tokens: 1792
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 57
      output_tokens: 1792
      cost_usd: 0.0
  runs:
  - profile: deep
    model: unknown
    input_tokens: 57
    output_tokens: 1792
    cost_usd: 0.0
    recorded_at: '2026-06-24T16:43:05.649419+00:00'
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
<!-- COMMENTS:END -->
