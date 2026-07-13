---
id: OOMPAH-169
type: task
status: In Progress
priority: 2
title: Remove epic-strategy controls and stale dashboard copy
parent: OOMPAH-166
children: []
blocked_by:
- OOMPAH-167
labels: []
assignee: null
created_at: '2026-07-13T02:23:10.333133Z'
updated_at: '2026-07-13T04:17:18.509240Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 8a048b33-4ece-4690-beec-cf797a9c870b
oompah.task_costs:
  total_input_tokens: 121075
  total_output_tokens: 1214
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 121075
      output_tokens: 1214
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 121075
    output_tokens: 1214
    cost_usd: 0.0
    recorded_at: '2026-07-13T03:15:02.145493+00:00'
---
## Summary

Remove the epic-strategy selector and any flat/stacked/shared choice from project create/edit UI, dashboard views, API forms, and client-side state. The UI must present shared behavior as the only workflow without a selectable strategy. Remove stale labels, help text, badges, and conditional rendering. Add dashboard/API contract tests that verify no strategy control is rendered or accepted and shared epic behavior remains visible.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 03:14
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-13 03:14
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 03:15
---
Agent completed successfully in 59s (122289 tokens)
---
author: oompah
created: 2026-07-13 03:15
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 2
- Tokens: 121.1K in / 1.2K out [122.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 59s
- Log: OOMPAH-169__20260713T031407Z.jsonl
---
author: oompah
created: 2026-07-13 03:15
---
Agent completed without closing this issue (59s (122289 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
<!-- COMMENTS:END -->
