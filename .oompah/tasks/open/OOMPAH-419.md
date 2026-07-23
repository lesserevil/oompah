---
id: OOMPAH-419
type: task
status: Open
priority: 1
title: Define the oompah OpenAPI-to-MCP exposure policy
parent: OOMPAH-418
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-23T19:41:54.055851Z'
updated_at: '2026-07-23T20:14:28.374241Z'
work_branch: epic-OOMPAH-418
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: d40fe272-5311-43fd-a306-a040573e3734
oompah.work_branch: epic-OOMPAH-418
oompah.task_costs:
  total_input_tokens: 2370412
  total_output_tokens: 57073
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 2370412
      output_tokens: 57073
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
  - profile: standard
    model: unknown
    input_tokens: 37
    output_tokens: 42330
    cost_usd: 0.0
    recorded_at: '2026-07-23T20:12:00.005426+00:00'
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
author: oompah
created: 2026-07-23 19:56
---
Discovery: API route audit complete

Audited oompah/server.py for all @app.{method} routes. Categories identified:

SAFE_READ (35 GET routes): /api/v1/state, /api/v1/issues, issue detail/comments/attachments/picks, project read endpoints, agent-profiles, roles, foci, budget, reviews, providers read, console transcript, etc.

TASK_MUTATION (6 routes): POST/PATCH /api/v1/issues, POST labels/remove labels/dependencies/comments.

ADMIN_MUTATION (20+ routes): project create/update/delete/pause/resume, state-branch migrate/validate, bootstrap apply, template apply, agent-profile CRUD, role update, focus CRUD, console backend management, POST /refresh, POST /errors, review rebase/retry, attachments upload/delete, issue intake actions.

CREDENTIAL_BEARING (5 routes): POST/PATCH/DELETE /api/v1/providers, POST /providers/{id}/test, POST /providers/fetch-models, POST /providers/{id}/auto-populate-contexts.

ORCHESTRATOR_CONTROL (4 routes): POST /api/v1/orchestrator/pause, /resume, /restart, /dispatch/{id}.

WEBHOOK_INGESTION (2 routes): POST /api/v1/webhooks/github, /api/v1/webhooks/gitlab.

RELEASE_DELIVERY (9 routes): release-delivery trigger/retry/archive/refresh, release-addendums create/retry/archive, release-picks update/apply-all.

Policy: only SAFE_READ and TASK_MUTATION are exposed. All others are denied. UNKNOWN defaults to denied (fail-closed).

Security note: orchestrator/restart is the highest-risk route — any MCP exposure of this would allow an agent to restart the oompah service.
---
author: oompah
created: 2026-07-23 20:11
---
Implementation: oompah/mcp_exposure_policy.py

Added three files:

1. oompah/mcp_exposure_policy.py — The policy module:
   - RouteCategory enum (8 categories)
   - EXPOSED_CATEGORIES = {SAFE_READ, TASK_MUTATION} (only these two)
   - classify_route(method, path) -> RouteCategory using an ordered 80+ rule table
   - is_route_exposed(method, path) -> bool (fail-closed: UNKNOWN = False)
   - _is_valid_openapi_path() input validation (rejects %encoding, ?, #, whitespace)
   - Service-discovery constants: MCP_ENDPOINT_PATH=/api/mcp/v1, MCP_DISCOVERY_PATH=/.well-known/mcp
   - describe_policy() and iter_exposed_routes() utility functions

2. tests/test_mcp_exposure_policy.py — 292 unit tests covering all route categories, injection resistance, fail-closed behavior.

3. plans/mcp-openapi-exposure-policy.md — Gateway integration guide for OOMPAH-420.

Security decisions made:
- POST /api/v1/orchestrator/restart → ORCHESTRATOR_CONTROL (denied, explicitly tested)
- POST /api/v1/webhooks/{github,gitlab} → WEBHOOK_INGESTION (HMAC bypass prevention)
- POST/PATCH/DELETE /api/v1/providers → CREDENTIAL_BEARING (key management protection)
- No token forwarding (loopback-only, no Auth header propagation)
- Input validation rejects adversarial path strings before pattern matching
---
author: oompah
created: 2026-07-23 20:11
---
Verification: 292/292 tests pass

Full test suite: 12045 passed, 1 pre-existing failure (test_scm.py::TestFetchCiStatus::test_legacy_failure_short_circuits — confirmed pre-existing on clean checkout, unrelated to this change).

New tests: tests/test_mcp_exposure_policy.py — 292 cases covering:
- Route classification for all 8 categories
- Explicit allow list (SAFE_READ, TASK_MUTATION)
- Explicit deny list (ORCHESTRATOR_CONTROL, WEBHOOK_INGESTION, CREDENTIAL_BEARING, ADMIN_MUTATION, RELEASE_DELIVERY)
- Fail-closed for UNKNOWN routes
- Input validation (adversarial paths, URL encoding, query strings, fragments, whitespace)
- Method case-insensitivity
- describe_policy() JSON serialisability
- iter_exposed_routes() only yields exposed routes
- Injection resistance: orchestrator/restart cannot be smuggled via issue identifier pattern
---
author: oompah
created: 2026-07-23 20:11
---
Completion: OOMPAH-419 delivered

Deliverables:
- oompah/mcp_exposure_policy.py: policy module (RouteCategory enum, rule table, classify_route, is_route_exposed, input validation, service-discovery constants)
- tests/test_mcp_exposure_policy.py: 292 passing unit tests
- plans/mcp-openapi-exposure-policy.md: design doc + gateway integration guide for OOMPAH-420

Acceptance criteria met:
✅ Policy is represented in code (mcp_exposure_policy.py)
✅ Defaults fail-closed for protected APIs (UNKNOWN → denied)
✅ Tests cover allowed operations (SAFE_READ, TASK_MUTATION)
✅ Tests cover denied operations (all 6 other categories + injection resistance)
✅ orchestrator/restart, webhooks, provider credentials all explicitly denied
✅ Token propagation documented: loopback-only, no forwarding

Ready for OOMPAH-420 (gateway implementation) to unblock.
---
author: oompah
created: 2026-07-23 20:11
---
Implemented oompah/mcp_exposure_policy.py with RouteCategory enum, 80+ route rules, classify_route/is_route_exposed functions (fail-closed), input validation against adversarial paths, and 292 passing unit tests. All protected operations (orchestrator/restart, webhooks, provider credentials, admin mutations, release delivery) are denied. SAFE_READ and TASK_MUTATION are the only exposed categories. Plans doc added for OOMPAH-420 gateway implementer.
---
author: oompah
created: 2026-07-23 20:12
---
Agent completed successfully in 1144s (42367 tokens)
---
author: oompah
created: 2026-07-23 20:12
---
Run #1 [attempt=1, profile=standard, role=standard -> Claude/default]
- Turns: 71, Tool calls: 43
- Tokens: 37 in / 42.3K out [42.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 19m 4s
- Log: OOMPAH-419__20260723T195259Z.jsonl
---
author: oompah
created: 2026-07-23 20:12
---
Close refused by orchestrator: branch `epic-OOMPAH-418` has 1 commit not on `main` and no open PR targets `main` from this branch.

Diagnostic:
  Unmerged commits: 1
    913a2c6d3 OOMPAH-419: Define the oompah OpenAPI-to-MCP exposure policy
  Open PRs from this branch: 0
  Merged PRs from this branch: 0

Required: open a PR before closing.
  gh pr create --base main --head epic-OOMPAH-418 --title "OOMPAH-419: Define the oompah OpenAPI-to-MCP exposure policy" --body "..."

Task reopened. Re-dispatch on the next tick will see this comment in its prompt context.
---
author: oompah
created: 2026-07-23 20:12
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-23 20:12
---
Focus: Security Auditor
---
<!-- COMMENTS:END -->
