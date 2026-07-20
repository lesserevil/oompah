---
id: OOMPAH-283
type: task
status: In Progress
priority: null
title: Expose active state-branch identity and checkpoint health in project APIs
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-20T22:54:50.695408Z'
updated_at: '2026-07-20T23:14:22.661253Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: ecd1a707-a567-4da8-865b-14fd53bb4e7e
oompah.task_costs:
  total_input_tokens: 85427
  total_output_tokens: 683
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 85427
      output_tokens: 683
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 85427
    output_tokens: 683
    cost_usd: 0.0
    recorded_at: '2026-07-20T23:09:41.004707+00:00'
---
## Summary

Problem: after a successful Stage B migration, GET /api/v1/projects reports state_branch: null and state_branch_shadow_write: null, while the state-branch status command correctly finds oompah/state/<project-id>. The status command also reports Last push: never immediately after bootstrap despite the branch being pushed.\n\nImplement the OOMPAH-253 API/health contract completely. For state-branch-enabled projects, return the computed branch name, a boolean shadow-write value, migration stage, and accurate last successful push/checkpoint information in project and state endpoints.\n\nTests: add API tests for a Stage B project asserting a non-null branch name and false shadow-write value; add health/status test asserting a pushed bootstrap commit is reflected as the last state commit/push.\n\nAcceptance criteria: dashboard and API consumers can identify the active state branch and its latest checkpoint without deriving branch names themselves; existing legacy projects retain null/disabled behavior.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-20 23:09
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-20 23:09
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-20 23:09
---
Agent completed successfully in 27s (86110 tokens)
---
author: oompah
created: 2026-07-20 23:09
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 85.4K in / 683 out [86.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 27s
- Log: OOMPAH-283__20260720T230915Z.jsonl
---
author: oompah
created: 2026-07-20 23:09
---
Agent completed without landing — no commits found on origin for branch `OOMPAH-283`. Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-20 23:10
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-20 23:10
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-20 23:14
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-20 23:14
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
