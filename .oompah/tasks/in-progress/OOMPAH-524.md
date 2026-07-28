---
id: OOMPAH-524
type: feature
status: In Progress
priority: 1
title: Integrate htpasswd authentication with the embedded MCP gateway
parent: OOMPAH-521
children: []
blocked_by:
- OOMPAH-523
labels:
- focus-complete:duplicate_detector
- needs:feature
assignee: null
created_at: '2026-07-28T18:12:19.566427Z'
updated_at: '2026-07-28T19:13:36.443451Z'
work_branch: epic-OOMPAH-521
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: ac4ed4d0-3f06-4bac-ac0a-8350db1499b1
oompah.work_branch: epic-OOMPAH-521
oompah.task_costs:
  total_input_tokens: 374387
  total_output_tokens: 9954
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 374387
      output_tokens: 9954
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 242
    output_tokens: 7327
    cost_usd: 0.0
    recorded_at: '2026-07-28T19:12:01.576965+00:00'
  - profile: default
    model: haiku
    input_tokens: 374145
    output_tokens: 2627
    cost_usd: 0.0
    recorded_at: '2026-07-28T19:13:25.968473+00:00'
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

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 19:09
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 19:09
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 19:11
---
Focus: Duplicate Investigator - Screening Complete

**Outcome:** No duplicate detected.

**Findings:**
- OOMPAH-523 (HTTP Basic auth for server) is COMPLETE: Two commits (cf4690852, e115fed59) implemented comprehensive authentication middleware protecting HTTP and WebSocket surfaces.
- OOMPAH-524 is a DISTINCT, DEPENDENT task requiring MCP gateway integration.
- Current state: MCP gateway code exists and is mounted, BUT:
  * MCP endpoints (/.well-known/mcp, /api/mcp/v1) are NOT protected by auth middleware
  * Discovery document still advertises 'authentication: none; local service access only'
  * Internal API dispatch path through MCP has not been adapted for authenticated requests

**Related code reviewed:**
- oompah/http_auth.py - HTTP Basic auth module (OOMPAH-523)
- oompah/mcp_gateway.py - MCP gateway implementation (mounted at /api/mcp/v1)
- oompah/mcp_exposure_policy.py - Fail-closed exposure policy
- tests/test_mcp_gateway.py - MCP integration tests (lack auth coverage)
- tests/test_server_auth.py - Server auth tests (do not cover MCP endpoints)

**Closest related tasks:**
- OOMPAH-523: HTTP Basic auth enforcement (COMPLETE)
- OOMPAH-419: MCP exposure policy definition (COMPLETE)
- Commit 3aa8dd5e1: MCP gateway mounting (COMPLETE)

This task requires implementation of auth integration with the mounted MCP gateway to fulfill the acceptance criteria.
---
author: oompah
created: 2026-07-28 19:12
---
Agent completed successfully in 127s (7569 tokens)
---
author: oompah
created: 2026-07-28 19:12
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 76, Tool calls: 42
- Tokens: 242 in / 7.3K out [7.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 7s
- Log: OOMPAH-524__20260728T190959Z.jsonl
---
author: oompah
created: 2026-07-28 19:12
---
Focus handoff required before leaving `duplicate_detector`. Add a comment headed `Focus handoff: duplicate_detector` with outcome, evidence, remaining work, and next focus.
---
author: oompah
created: 2026-07-28 19:12
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 19:12
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 19:13
---
Understanding: I am screening OOMPAH-524 for duplicates before any implementation. I will compare the MCP gateway/authentication scope against existing tracker tasks and repository design docs, then hand off with evidence if the work is distinct.
---
author: oompah
created: 2026-07-28 19:13
---
Focus handoff: duplicate_detector\n\nOutcome: No duplicate confirmed; OOMPAH-524 is distinct MCP authentication integration work.\n\nEvidence: Searched .oompah/tasks, docs, plans, README.md, and WORKFLOW.md for MCP, gateway, FastMCP, streamable HTTP, htpasswd, Basic authentication, and related credential terms. Read OOMPAH-419 in full (fail-closed MCP exposure policy), OOMPAH-420 in full (embedded gateway implementation), OOMPAH-522 in full (htpasswd verifier/config foundation), OOMPAH-523 in full (HTTP/WebSocket Basic-auth middleware), and OOMPAH-524 in full. The existing tasks are prerequisites/components, not duplicates: 419 owns exposure policy, 420 owns the gateway, 522 owns credential loading, and 523 owns outer HTTP enforcement. Current MCP discovery/transport and in-process API dispatch still require the integration described here. Relevant files are oompah/mcp_gateway.py, oompah/mcp_exposure_policy.py, oompah/server.py, tests/test_mcp_gateway.py, and tests/test_server_auth.py.\n\nRemaining work/risk: Implement and test auth-aware discovery and streamable HTTP, authenticated internal ASGI dispatch without an externally spoofable bypass, credential redaction, network/local-mode behavior, direct REST protection, and preservation of the fail-closed exposure policy.\n\nRecommended next focus: feature.:
---
author: oompah
created: 2026-07-28 19:13
---
Agent completed successfully in 72s (376772 tokens)
---
author: oompah
created: 2026-07-28 19:13
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 13
- Tokens: 374.1K in / 2.6K out [376.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 12s
- Log: OOMPAH-524__20260728T191216Z.jsonl
---
author: oompah
created: 2026-07-28 19:13
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
<!-- COMMENTS:END -->
