---
id: OOMPAH-420
type: feature
status: Backlog
priority: 1
title: Implement an embedded oompah OpenAPI MCP gateway
parent: OOMPAH-418
children: []
blocked_by:
- OOMPAH-419
labels: []
assignee: null
created_at: '2026-07-23T19:41:55.025847Z'
updated_at: '2026-07-23T19:42:04.678951Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Adapt the oapi2mcp gateway approach into oompah as a first-party module. Build a FastMCP streamable-HTTP application from oompah's own FastAPI OpenAPI schema, route upstream tool calls safely to the local oompah API, mount it in the server lifecycle, and provide /.well-known MCP discovery metadata. Add required optional dependencies and ensure lifespan/client cleanup is correct. Acceptance: an MCP client can initialize and list the approved oompah OpenAPI tools via the documented endpoint; calls use the local service correctly; server startup remains healthy with the feature enabled.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

