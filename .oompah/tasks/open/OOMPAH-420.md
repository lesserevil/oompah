---
id: OOMPAH-420
type: feature
status: Open
priority: 1
title: Implement an embedded oompah OpenAPI MCP gateway
parent: OOMPAH-418
children: []
blocked_by:
- OOMPAH-419
labels:
- focus-complete:duplicate_detector
- focus-complete:refactor
- needs:feature
assignee: null
created_at: '2026-07-23T19:41:55.025847Z'
updated_at: '2026-07-24T01:54:13.013584Z'
work_branch: epic-OOMPAH-418
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 17d31e67-4138-4baf-bee6-b4d4b02d8e79
oompah.work_branch: epic-OOMPAH-418
oompah.task_costs:
  total_input_tokens: 573371
  total_output_tokens: 4607
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 573371
      output_tokens: 4607
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 246322
    output_tokens: 2036
    cost_usd: 0.0
    recorded_at: '2026-07-23T20:45:28.875147+00:00'
  - profile: standard
    model: unknown
    input_tokens: 327049
    output_tokens: 2571
    cost_usd: 0.0
    recorded_at: '2026-07-23T20:46:57.790113+00:00'
---
## Summary

Adapt the oapi2mcp gateway approach into oompah as a first-party module. Build a FastMCP streamable-HTTP application from oompah's own FastAPI OpenAPI schema, route upstream tool calls safely to the local oompah API, mount it in the server lifecycle, and provide /.well-known MCP discovery metadata. Add required optional dependencies and ensure lifespan/client cleanup is correct. Acceptance: an MCP client can initialize and list the approved oompah OpenAPI tools via the documented endpoint; calls use the local service correctly; server startup remains healthy with the feature enabled.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-23 20:44
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-23 20:44
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-23 20:44
---
Understanding: Duplicate-screen OOMPAH-420 before implementation by searching task records and repository design docs for OpenAPI/FastMCP gateway work, then reading the closest candidates (especially OOMPAH-419 and OOMPAH-421) in full. This focus will only archive if the same implementation is already owned elsewhere; otherwise it will hand off for feature implementation.
---
author: oompah
created: 2026-07-23 20:45
---
Discovery: Duplicate screening found no duplicate. Repository search for oapi2mcp/OpenAPI MCP/FastMCP/streamable HTTP/discovery found plans/mcp-openapi-exposure-policy.md, which explicitly assigns gateway construction to OOMPAH-420. Full tracker review confirms OOMPAH-418 is the parent epic; OOMPAH-419 delivered only the fail-closed route exposure policy and focused tests; OOMPAH-421 owns downstream integration tests and operator docs. None owns OOMPAH-420's FastMCP app, local API forwarding, lifecycle/cleanup, dependency packaging, or discovery implementation.
---
author: oompah
created: 2026-07-23 20:45
---
Focus handoff: duplicate_detector

1. Outcome: No duplicate confirmed; OOMPAH-420 remains necessary and distinct.
2. Evidence: Searched .oompah/tasks, docs, plans, README.md, and WORKFLOW.md for oapi2mcp, OpenAPI MCP, MCP gateway, FastMCP, streamable HTTP, and discovery terms. Reviewed OOMPAH-418, OOMPAH-419, OOMPAH-420, and OOMPAH-421 in full with oompah task view. plans/mcp-openapi-exposure-policy.md identifies OOMPAH-419 as the implemented policy, OOMPAH-420 as gateway implementation, and OOMPAH-421 as integration tests/docs. The current worktree is clean.
3. Remaining work/risks: Implement the embedded gateway using oompah/mcp_exposure_policy.py; safely forward approved operations to the local API; mount streamable HTTP and discovery metadata with correct lifespan/client cleanup; add optional dependencies and code-level unit tests. Preserve scope for OOMPAH-421's end-to-end coverage/operator docs. Verify compatibility with the installed FastMCP API and server startup lifecycle.
4. Recommended next focus: feature.
---
author: oompah
created: 2026-07-23 20:45
---
Agent completed successfully in 69s (248358 tokens)
---
author: oompah
created: 2026-07-23 20:45
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 12
- Tokens: 246.3K in / 2.0K out [248.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 9s
- Log: OOMPAH-420__20260723T204424Z.jsonl
---
author: oompah
created: 2026-07-23 20:45
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-23 20:45
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-23 20:45
---
Focus: Refactoring Specialist
---
author: oompah
created: 2026-07-23 20:46
---
Agent completed successfully in 79s (329620 tokens)
---
author: oompah
created: 2026-07-23 20:47
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/default]
- Turns: 1, Tool calls: 6
- Tokens: 327.0K in / 2.6K out [329.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 19s
- Log: OOMPAH-420__20260723T204542Z.jsonl
---
author: oompah
created: 2026-07-24 01:51
---
Correction: this task was marked Merged incorrectly. The only commit on shared branch epic-OOMPAH-418 implements OOMPAH-419's exposure policy; source/history inspection confirms there is no FastMCP gateway module, no server mount for /api/mcp/v1, and no /.well-known/mcp route. Implement the first-party gateway now: build tools from /openapi.json filtered through mcp_exposure_policy, mount streamable HTTP at /api/mcp/v1, serve discovery metadata, add dependencies/lifecycle cleanup, and add tests proving initialize/list-tools, an allowed call, and protected-route exclusion. Do not mark complete until the live routes exist.
---
author: oompah
created: 2026-07-24 01:51
---
Reopened: false merge detected; gateway endpoint and discovery route are absent from source and live server.
---
author: oompah
created: 2026-07-24 01:53
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-24 01:53
---
Focus: Refactoring Specialist
---
author: oompah
created: 2026-07-24 01:53
---
Understanding: OOMPAH-420 requires new behavior (a FastMCP gateway module, live mounts, discovery metadata, dependencies, and tests), while this run is constrained to behavior-preserving refactoring only. I will verify the branch still lacks those artifacts and, if confirmed, record a refactor-focus handoff to needs:feature without making or committing feature changes.
---
author: oompah
created: 2026-07-24 01:53
---
Discovery: Verified a clean worktree and searched oompah/, tests/, pyproject.toml, plans/, docs/, README.md, and WORKFLOW.md. MCP endpoint/discovery references exist only in plans/mcp-openapi-exposure-policy.md, oompah/mcp_exposure_policy.py constants, and policy tests. There is no FastMCP import/application, /api/mcp/v1 server mount, /.well-known/mcp route implementation, forwarding client, gateway lifecycle, or gateway tests. This is feature implementation, not a behavior-preserving refactor.
---
author: oompah
created: 2026-07-24 01:54
---
Focus handoff: refactor

1. Outcome: No refactoring was appropriate or performed; the required gateway does not yet exist and every acceptance item requires new behavior.
2. Evidence: git status is clean. Repository search found only plans/mcp-openapi-exposure-policy.md, oompah/mcp_exposure_policy.py, and tests/test_mcp_exposure_policy.py; no FastMCP gateway, live endpoint/discovery mount, forwarding client, lifecycle integration, dependency addition, or gateway protocol tests exist.
3. Remaining work/risks: Implement the first-party FastMCP streamable-HTTP app from the filtered OpenAPI schema, safe local-ASGI forwarding, /api/mcp/v1 and /.well-known/mcp routes, lifespan/client cleanup, optional dependencies, and tests for initialize/list-tools, an allowed call, protected-route exclusion, and healthy startup. Preserve OOMPAH-421's downstream operator-doc/E2E scope.
4. Recommended next focus: feature.
---
<!-- COMMENTS:END -->
