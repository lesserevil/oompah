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
labels: []
assignee: null
created_at: '2026-07-23T19:41:55.025847Z'
updated_at: '2026-07-23T20:44:53.847743Z'
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
<!-- COMMENTS:END -->
