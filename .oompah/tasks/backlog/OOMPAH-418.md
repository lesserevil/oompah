---
id: OOMPAH-418
type: epic
status: Backlog
priority: 1
title: Expose oompah's OpenAPI as a streamable MCP server
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-23T19:41:39.116461Z'
updated_at: '2026-07-23T19:41:39.116461Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Integrate the oapi2mcp OpenAPI-to-MCP gateway pattern into oompah so MCP clients can use oompah's FastAPI OpenAPI contract through a first-party streamable-HTTP MCP endpoint. Scope includes a maintainable gateway module, explicit route and authorization policy for potentially mutating management APIs, server lifecycle integration, dependency packaging, tests, and operator documentation. The endpoint must derive tools from oompah's own OpenAPI schema without requiring a separate oapi2mcp deployment. Acceptance: a configured oompah server exposes a documented MCP endpoint and discovery metadata; allowed MCP calls reach the intended oompah API operations; unsafe or unsupported operations are excluded or denied; make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

