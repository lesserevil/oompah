---
id: OOMPAH-523
type: feature
status: Open
priority: 1
title: Enforce Basic authentication across HTTP and WebSocket surfaces
parent: OOMPAH-521
children: []
blocked_by:
- OOMPAH-522
labels: []
assignee: null
created_at: '2026-07-28T18:11:58.412853Z'
updated_at: '2026-07-28T18:32:34.916720Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
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

