---
id: OOMPAH-419
type: task
status: In Progress
priority: 1
title: Define the oompah OpenAPI-to-MCP exposure policy
parent: OOMPAH-418
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-23T19:41:54.055851Z'
updated_at: '2026-07-23T19:48:22.617253Z'
work_branch: epic-OOMPAH-418
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 88115688-15dc-4012-8654-b515794440d4
oompah.work_branch: epic-OOMPAH-418
oompah.task_costs:
  total_input_tokens: 649389
  total_output_tokens: 5099
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 649389
      output_tokens: 5099
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 649389
    output_tokens: 5099
    cost_usd: 0.0
    recorded_at: '2026-07-23T19:48:20.296274+00:00'
---
## Summary

Design and implement the explicit MCP tool-exposure policy for oompah's generated OpenAPI schema. Determine the mounted endpoint and service-discovery paths, authentication/token propagation behavior, and the allow-list or deny-list for mutating, administrative, credential-bearing, webhook, and restart APIs. Add focused tests proving the generated tool surface includes intended safe operations and excludes or rejects protected operations. Acceptance: the policy is represented in code/configuration, defaults fail closed for protected APIs, and tests cover both allowed and denied operations.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-23 19:46
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-23 19:46
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-23 19:48
---
Agent completed successfully in 134s (654488 tokens)
---
author: oompah
created: 2026-07-23 19:48
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 9
- Tokens: 649.4K in / 5.1K out [654.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 14s
- Log: OOMPAH-419__20260723T194610Z.jsonl
---
<!-- COMMENTS:END -->
