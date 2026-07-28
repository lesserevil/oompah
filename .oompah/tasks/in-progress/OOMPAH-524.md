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
- focus-complete:security
assignee: null
created_at: '2026-07-28T18:12:19.566427Z'
updated_at: '2026-07-28T19:17:31.202357Z'
work_branch: epic-OOMPAH-521
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: ffc358af-3f6e-4cda-a4cf-deb983c464b5
oompah.work_branch: epic-OOMPAH-521
oompah.task_costs:
  total_input_tokens: 1335101
  total_output_tokens: 18739
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 374387
      output_tokens: 9954
      cost_usd: 0.0
    sonnet:
      input_tokens: 960714
      output_tokens: 8785
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
  - profile: standard
    model: sonnet
    input_tokens: 960714
    output_tokens: 8785
    cost_usd: 0.0
    recorded_at: '2026-07-28T19:16:55.186716+00:00'
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
author: oompah
created: 2026-07-28 19:13
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-28 19:13
---
Focus: Security Auditor
---
author: oompah
created: 2026-07-28 19:13
---
Understanding: I am reviewing the MCP authentication integration as a security auditor. I will trace discovery, streamable HTTP, and in-process API dispatch; test credential and header handling; verify direct REST endpoints cannot be bypassed; and preserve MCP exposure and DNS-rebinding protections.
---
author: oompah
created: 2026-07-28 19:14
---
Discovery: MCP routes are covered by _BasicAuthMiddleware, which authenticates then strips Authorization. However build_mcp_gateway dispatches tools through a new ASGI HTTP client with no credentials, so protected REST tools will 401 under htpasswd. A fix needs a request-scoped server-private capability propagated only from a verified MCP request, not an inbound header/Host/path marker. Current discovery still always says authentication=none.
---
author: oompah
created: 2026-07-28 19:16
---
Verification: .venv/bin/pytest -q tests/test_mcp_gateway.py tests/test_server_auth.py passed (69 passed). An ad-hoc end-to-end call with enabled credentials successfully initialized MCP but the allowed api_state tool returned 401 from the internal ASGI request, confirming the identified propagation gap. uv run pytest was unavailable because its transient DBus scope could not be created; the project venv pytest completed normally.
---
author: oompah
created: 2026-07-28 19:16
---
Implementation: Security review completed; no code was changed in this focus. Required secure implementation decision: annotate only a successfully Basic-authenticated MCP ASGI scope with an in-memory sentinel, require that sentinel before a tool creates internal dispatch, and have a private ASGI wrapper attach a distinct internal-dispatch sentinel. The Basic middleware may trust only object-identity sentinels in ASGI scope—never Host, path, or any HTTP header—and must continue to redact Authorization.
---
author: oompah
created: 2026-07-28 19:16
---
Focus handoff: security\n\nOutcome: The security architecture is defined and the existing auth middleware/exposure policy are sound, but OOMPAH-524 still needs feature implementation.\n\nEvidence: Reviewed oompah/server.py (_BasicAuthMiddleware and mounted gateway), oompah/mcp_gateway.py (credential-free ASGI dispatch), oompah/mcp_exposure_policy.py, and focused gateway/auth tests. Valid authenticated MCP initialize works; an allowed tool returns 401 because the inner ASGI request lacks auth. Focused test command passed: .venv/bin/pytest -q tests/test_mcp_gateway.py tests/test_server_auth.py (69 passed).\n\nRemaining work/risk: Implement effective discovery authentication mode; preserve Basic auth for initialize/list/call/stream/session cleanup; add an unforgeable ASGI-scope sentinel capability to connect a verified MCP request to its private inner dispatch without forwarding Authorization; ensure direct REST and spoofed Host/path/headers stay 401; test enabled network mode, redaction, and denied tool absence. Do not use inbound internal marker headers.\n\nRecommended next focus: feature.
---
author: oompah
created: 2026-07-28 19:16
---
Agent completed successfully in 196s (969499 tokens)
---
author: oompah
created: 2026-07-28 19:16
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/gpt-5.6-terra]
- Turns: 1, Tool calls: 33
- Tokens: 960.7K in / 8.8K out [969.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 16s
- Log: OOMPAH-524__20260728T191342Z.jsonl
---
author: oompah
created: 2026-07-28 19:16
---
Focus handoff from `security` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-28 19:17
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-28 19:17
---
Focus: Refactoring Specialist
---
author: oompah
created: 2026-07-28 19:17
---
Understanding: As Refactoring Specialist, my role is to improve code quality without changing behavior. Previous agents confirmed this is distinct work (no duplicate) and defined the security architecture needed - but no feature code was written yet. I will first read the current codebase state to determine if there is any refactoring work to do on the existing code, run baseline tests, and if the feature implementation is still pending I will hand off to a feature agent with full context.
---
<!-- COMMENTS:END -->
