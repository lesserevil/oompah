---
id: OOMPAH-419
type: task
status: In Progress
priority: 1
title: Define the oompah OpenAPI-to-MCP exposure policy
parent: OOMPAH-418
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-23T19:41:54.055851Z'
updated_at: '2026-07-23T19:54:02.331715Z'
work_branch: epic-OOMPAH-418
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: cb22144c-aa8c-41ae-9cfc-f7f91faff654
oompah.work_branch: epic-OOMPAH-418
oompah.task_costs:
  total_input_tokens: 2370375
  total_output_tokens: 14743
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 2370375
      output_tokens: 14743
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 649389
    output_tokens: 5099
    cost_usd: 0.0
    recorded_at: '2026-07-23T19:48:20.296274+00:00'
  - profile: standard
    model: unknown
    input_tokens: 1720986
    output_tokens: 9644
    cost_usd: 0.0
    recorded_at: '2026-07-23T19:52:47.700260+00:00'
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
author: oompah
created: 2026-07-23 19:48
---
Agent completed without landing — no commits found on origin for branch `epic-OOMPAH-418`. Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-23 19:48
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-23 19:48
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-23 19:52
---
Focus handoff: duplicate_detector

1. Outcome: Duplicate screening found no duplicate for OOMPAH-419.
2. Evidence: A canonical-state search for OpenAPI, MCP, tool exposure, and service discovery found only parent epic OOMPAH-418 and siblings OOMPAH-420/OOMPAH-421. Full descriptions and comments confirm intentional decomposition: OOMPAH-419 owns exposure/authentication/fail-closed policy and focused policy tests; OOMPAH-420 owns the embedded gateway/lifecycle/discovery implementation and is blocked by OOMPAH-419; OOMPAH-421 owns end-to-end coverage and operator docs and is blocked by OOMPAH-420. Commands used: git grep against oompah/state/proj-14849f1b and git show of tasks 418-421. The code worktree remains clean.
3. Remaining work/risks: Implement the policy contract and allowed/denied unit coverage without absorbing OOMPAH-420 gateway construction or OOMPAH-421 end-to-end/docs scope. Keep protected operations fail-closed.
4. Recommended next focus: security.
---
author: oompah
created: 2026-07-23 19:52
---
Agent completed successfully in 243s (1730630 tokens)
---
author: oompah
created: 2026-07-23 19:52
---
Run #2 [attempt=2, profile=standard, role=standard -> Codex/default]
- Turns: 1, Tool calls: 21
- Tokens: 1.7M in / 9.6K out [1.7M total]
- Cost: $0.0000
- Exit: normal, Duration: 4m 3s
- Log: OOMPAH-419__20260723T194846Z.jsonl
---
author: oompah
created: 2026-07-23 19:52
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-23 19:52
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-23 19:52
---
Focus: Security Auditor
---
author: oompah
created: 2026-07-23 19:54
---
Security Auditor: Understanding + Plan

This task defines the OpenAPI-to-MCP exposure policy for OOMPAH-418 (expose oompah's FastAPI OpenAPI as an MCP server). My scope is OOMPAH-419 only — the policy module and its unit tests — not the gateway implementation (OOMPAH-420).

Attack vectors I'm evaluating:
1. Unsafe mutation exposure: POST/PUT/DELETE operations for admin, credential, webhook, restart APIs exposed as MCP tools without protection
2. Token/credential leakage: forwarding Authorization headers into server responses or logs
3. Prompt injection via MCP tool descriptions: attacker-controlled tool names or descriptions
4. Fail-open defaults: any unclassified route being treated as safe
5. Privilege escalation: an agent using MCP tools to reconfigure the server or trigger deploys

Plan:
- Audit oompah's server.py to categorize all /api/v1/* routes
- Implement oompah/mcp_exposure_policy.py with: allow-list (safe GETs), deny-list (mutating/admin/webhook/restart), fail-closed default
- Add tests in tests/test_mcp_exposure_policy.py covering: allowed ops return True, denied ops return False, unknown ops fail closed
---
<!-- COMMENTS:END -->
