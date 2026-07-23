---
id: OOMPAH-418
type: epic
status: In Review
priority: 1
title: Expose oompah's OpenAPI as a streamable MCP server
parent: null
children:
- OOMPAH-419
- OOMPAH-420
- OOMPAH-421
blocked_by: []
labels:
- epic:stale
assignee: null
created_at: '2026-07-23T19:41:39.116461Z'
updated_at: '2026-07-23T20:25:35.837442Z'
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

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-23 19:42
---
Created from the operator request to expose oompah's own FastAPI /openapi.json as a first-party streamable MCP server, using the oapi2mcp gateway pattern. Children are sequenced: exposure/security policy (OOMPAH-419), embedded gateway implementation (OOMPAH-420), then integration tests and operator docs (OOMPAH-421).
---
author: oompah
created: 2026-07-23 19:42
---
Epic activated; work begins with OOMPAH-419.
---
<!-- COMMENTS:END -->
