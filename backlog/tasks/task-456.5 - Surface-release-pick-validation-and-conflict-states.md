---
id: TASK-456.5
title: Surface release-pick validation and conflict states
status: In Progress
assignee: []
created_date: 2026-06-08 17:29
updated_date: 2026-06-08 22:22
labels:
- task
dependencies:
- TASK-456.1
parent_task_id: TASK-456
priority: high
ordinal: 107000
oompah.task_costs:
  total_input_tokens: 784936
  total_output_tokens: 1516
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 784936
      output_tokens: 1516
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 784936
    output_tokens: 1516
    cost_usd: 0.0
    recorded_at: '2026-06-08T22:21:21.093588+00:00'
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Show branch validation errors, waiting-for-source-merge state, open PRs, merged picks, closed PRs, and cherry-pick conflicts clearly in the UI without requiring operators to inspect logs.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 1
author: oompah
created: 2026-06-08 21:24

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 2
author: oompah
created: 2026-06-08 21:24

Focus: Duplicate Investigator
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3
author: oompah
created: 2026-06-08 22:15

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 4
author: oompah
created: 2026-06-08 22:16

Focus: Frontend Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 5
author: oompah
created: 2026-06-08 22:21

Run #1 [attempt=1, profile=default, role=fast -> InferenceAPI/nvidia/nvidia/nemotron-3-ultra]
- Turns: 18, Tool calls: 17
- Tokens: 784.9K in / 1.5K out [786.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 5m 33s
- Log: TASK-456.5__20260608T221644Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 6
author: oompah
created: 2026-06-08 22:21

Agent completed successfully in 333s (786452 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 7
author: oompah
created: 2026-06-08 22:21

Agent completed without closing this issue (333s (786452 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 8
author: oompah
created: 2026-06-08 22:22

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
