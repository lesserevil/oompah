---
id: OOMPAH-24
type: task
status: In Progress
priority: 1
title: Expand release smoke tests for project-bootstrap
parent: OOMPAH-22
children: []
blocked_by:
- OOMPAH-23
labels: []
assignee: null
created_at: '2026-06-22T01:16:43.935007Z'
updated_at: '2026-06-22T02:17:28.895480Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 62dc6f6b-a665-4242-b74f-06dbc446f922
oompah.task_costs:
  total_input_tokens: 4371367
  total_output_tokens: 21280
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 4371367
      output_tokens: 21280
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 4371367
    output_tokens: 21280
    cost_usd: 0.0
    recorded_at: '2026-06-22T02:17:21.529731+00:00'
---
## Summary

Plan: plans/oompah-1.0-release.md#cli-and-api-contract

WHAT TO DO
Expand packaging and release smoke tests to cover oompah project-bootstrap --help in addition to the existing root and task command smoke checks.

HOW TO VERIFY
The release packaging tests fail if project-bootstrap is missing from the installed lightweight CLI.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-22 02:04
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-06-22 02:04
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-22 02:17
---
Agent completed successfully in 750s (4392647 tokens)
---
author: oompah
created: 2026-06-22 02:17
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 66
- Tokens: 4.4M in / 21.3K out [4.4M total]
- Cost: $0.0000
- Exit: normal, Duration: 12m 30s
- Log: OOMPAH-24__20260622T020455Z.jsonl
---
author: oompah
created: 2026-06-22 02:17
---
Agent completed without closing this issue (750s (4392647 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
<!-- COMMENTS:END -->
