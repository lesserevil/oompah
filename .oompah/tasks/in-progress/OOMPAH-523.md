---
id: OOMPAH-523
type: feature
status: In Progress
priority: 1
title: Enforce Basic authentication across HTTP and WebSocket surfaces
parent: OOMPAH-521
children: []
blocked_by:
- OOMPAH-522
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-28T18:11:58.412853Z'
updated_at: '2026-07-28T18:43:52.037885Z'
work_branch: epic-OOMPAH-521
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 0f5b9f78-c77c-415e-b67f-a4a888d0615e
oompah.work_branch: epic-OOMPAH-521
---
## Summary

### Objective

Apply the htpasswd verifier from OOMPAH-522 at the ASGI boundary so an enabled deployment protects every interactive Oompah surface while preserving forge webhook delivery and process supervision.

### Implementation scope

- Add authentication enforcement that covers FastAPI routes, mounted static assets, mounted applications, and `/ws`. Do not rely on adding dependencies to individual routes because new routes must fail closed by default.
- When auth is disabled, preserve current behavior exactly.
- When auth is enabled, accept only a valid HTTP Basic Authorization header. Missing, malformed, unsupported-scheme, unknown-user, and wrong-password requests must be denied consistently.
- Return HTTP 401 with `WWW-Authenticate: Basic realm="oompah", charset="UTF-8"` for protected HTTP requests. Never echo credentials or distinguish unknown users from bad passwords.
- Authenticate WebSocket handshakes before `accept()`. Deny unauthenticated or invalid handshakes without adding the socket to `_ws_clients`; verify same-origin browser WebSockets work after browser Basic authentication.
- Protect dashboard HTML, static assets, favicon, REST APIs, OpenAPI schema, Swagger/ReDoc, GitLab hook status, MCP discovery, and the mounted MCP transport by default.
- Add a minimal unauthenticated `GET /healthz` endpoint for supervisors. It may return only health state and the service instance identifier needed to distinguish restarts; it must not expose projects, tasks, providers, budgets, alerts, or credentials.
- Exempt only `GET /healthz`, `POST /api/v1/webhooks/github`, and `POST /api/v1/webhooks/gitlab` from Basic authentication. Match exact methods and normalized paths so similarly prefixed routes cannot bypass auth. The GitLab hook status GET remains protected.
- Preserve existing GitHub signature and GitLab token validation on the exempt webhook POST routes. Basic auth must neither replace nor weaken forge-specific checks.
- Ensure request logging and exception paths redact Authorization values.

### Relevant files

`oompah/server.py`, the authentication module from OOMPAH-522, WebSocket handling near `/ws`, webhook endpoints, and focused server/WebSocket/webhook tests.

### Dependencies

Depends on OOMPAH-522.

### Test requirements

Add integration tests for disabled mode; valid credentials; missing, malformed, non-Basic, unknown-user, and wrong-password headers; the exact challenge header; dashboard/static/API/OpenAPI protection; WebSocket accepted and denied paths; protected GitLab status; public minimal health; and exact webhook exemptions. Re-run existing GitHub and GitLab webhook signature/token suites under enabled auth and prove adjacent methods and path-prefix variants do not bypass middleware.

### Acceptance criteria

1. Enabled authentication protects every HTTP and mounted route unless explicitly exempted above.
2. Invalid protected HTTP requests receive a uniform 401 Basic challenge with no credential disclosure.
3. Invalid WebSocket handshakes are rejected before connection registration; valid same-origin browser connections work.
4. `/healthz` remains unauthenticated and contains no operational data beyond minimal health and instance identity.
5. Webhook POST delivery works without Basic credentials but still fails when its existing signature or token is invalid.
6. No alternative method, trailing-path trick, encoded path, or similarly prefixed route bypasses authentication.
7. Disabled deployments retain current route behavior.
8. Focused tests pass through the project test tooling.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 18:42
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 18:42
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 18:43
---
**Duplicate Investigation Complete**

No duplicate found. OOMPAH-523 is a unique, new task.

**Investigation Summary:**
- Searched all .oompah/tasks states (open, merged, archived) — no authentication middleware tasks found
- Searched docs/ and plans/ — no related authentication design docs
- Searched git history — OOMPAH-522 (htpasswd verifier module) is merged and complete; no OOMPAH-523 commits exist
- Examined http_auth.py module (OOMPAH-522) and test_http_auth.py — both complete and ready to use
- Searched for related tasks with keywords: authentication, Basic auth, ASGI, middleware, WebSocket, healthz, webhook — found only OOMPAH-339 (GitLab status-label authorization, different feature)

**Key Finding:**
OOMPAH-522 dependency is satisfied (merged commit 98841ce7b). The htpasswd verifier module is implemented and tested. OOMPAH-523 is now ready for implementation — it needs to add ASGI middleware using the OOMPAH-522 verifier to protect HTTP and WebSocket surfaces.

**Recommended next focus:** feature (backend implementation of ASGI authentication middleware)
---
<!-- COMMENTS:END -->
