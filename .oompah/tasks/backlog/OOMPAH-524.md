---
id: OOMPAH-524
type: feature
status: Backlog
priority: 1
title: Integrate htpasswd authentication with the embedded MCP gateway
parent: OOMPAH-521
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T18:12:19.566427Z'
updated_at: '2026-07-28T18:12:19.566427Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

### Objective

Make Oompah MCP discovery and streamable-HTTP transport obey optional htpasswd authentication without breaking the gateway internal OpenAPI dispatch or introducing an externally spoofable bypass.

### Implementation scope

- Require valid Basic credentials on `/.well-known/mcp` and `/api/mcp/v1` whenever server authentication is enabled; preserve credential-free local behavior when disabled.
- Make the discovery document report the effective authentication mode rather than always advertising no authentication.
- Ensure supported MCP clients can supply ordinary HTTP Basic credentials during initialize, list-tools, tool calls, streaming, and session cleanup.
- The gateway currently invokes approved API operations through an in-process ASGI transport with no propagated client credentials. Adapt this flow so authenticated MCP calls can reach approved internal API operations without storing passwords in tool arguments, copying Authorization values into logs/results, or trusting a client-spoofable Host/header/path bypass.
- Preserve the existing fail-closed MCP exposure policy. Authentication must not make administrative, credential, webhook, release, or orchestrator operations available as tools.
- Keep DNS-rebinding protection behavior intact in local-only mode and ensure network-enabled MCP still requires Basic auth when the htpasswd feature is enabled.
- Ensure direct calls to the underlying REST endpoints remain protected even if they resemble gateway-internal traffic.

### Relevant files

`oompah/mcp_gateway.py`, `oompah/mcp_exposure_policy.py`, `oompah/server.py`, `tests/test_mcp_gateway.py`, and focused authentication tests from OOMPAH-523.

### Dependencies

Depends on OOMPAH-523.

### Test requirements

Extend the real streamable-HTTP MCP integration tests. Cover discovery in enabled and disabled modes; initialize/list/call with valid Basic auth; missing and invalid credentials; a successful protected API tool call through the gateway; streaming/session requests retaining authentication; direct REST calls remaining protected; network mode; and proof that disallowed operations remain absent. Include a regression test demonstrating that spoofing any internal marker from an external request cannot bypass authentication.

### Acceptance criteria

1. MCP discovery and transport return an authentication challenge when auth is enabled and credentials are absent or invalid.
2. Valid Basic credentials support a complete MCP initialize, list-tools, and tool-call flow.
3. The discovery document accurately states whether HTTP Basic auth is required.
4. Internal OpenAPI dispatch succeeds only within an authenticated MCP invocation and creates no externally reusable bypass.
5. Passwords and Authorization headers never appear in tool schemas, arguments, responses, logs, or exceptions.
6. Existing exposure-policy and DNS-rebinding guarantees remain intact.
7. Auth-disabled MCP behavior remains backward compatible.
8. Focused tests pass through the project test tooling.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

