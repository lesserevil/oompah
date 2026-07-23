---
id: OOMPAH-420
type: feature
status: In Progress
priority: 1
title: Implement an embedded oompah OpenAPI MCP gateway
parent: OOMPAH-418
children: []
blocked_by:
- OOMPAH-419
labels:
- focus-complete:duplicate_detector
- needs:feature
assignee: null
created_at: '2026-07-23T19:41:55.025847Z'
updated_at: '2026-07-23T20:45:25.832747Z'
work_branch: epic-OOMPAH-418
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 7b2142a2-2cb1-4887-b7b8-8c7d742a0b4b
oompah.work_branch: epic-OOMPAH-418
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
<!-- COMMENTS:END -->
