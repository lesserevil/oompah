---
id: OOMPAH-521
type: epic
status: Backlog
priority: 1
title: Add optional htpasswd authentication to the Oompah service
parent: null
children:
- OOMPAH-522
- OOMPAH-523
- OOMPAH-524
- OOMPAH-525
- OOMPAH-526
blocked_by: []
labels:
- security
assignee: null
created_at: '2026-07-28T18:10:41.609070Z'
updated_at: '2026-07-28T18:13:23.438057Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

### Goal

Add optional HTTP Basic authentication backed by an Apache-style htpasswd file so operators can safely expose Oompah through HTTPS. Authentication is disabled for backward compatibility when no htpasswd file is present. When the file is present, every human-facing and programmatic service surface must require valid credentials except narrowly documented machine-to-machine ingress and health endpoints.

### Configuration contract

- By default, discover `.htpasswd` beside the `.env` file selected at server startup.
- Allow `OOMPAH_HTPASSWD_FILE` in `.env` to select an absolute or environment-relative secret mount path.
- If the default file is absent and no override is configured, authentication remains disabled with current behavior.
- If an override is configured but missing, or a discovered file is unreadable, malformed, or contains no usable accounts, fail startup closed with an actionable error.
- Credential file changes take effect after a graceful service restart; no live-reload requirement is included in this epic.

### Security boundary

Require HTTP Basic credentials for dashboard pages and assets, REST/OpenAPI endpoints, WebSocket connections, MCP discovery and transport, and other interactive service routes. Keep only a minimal liveness endpoint and the GitHub/GitLab webhook receiver POST routes unauthenticated. Webhooks must retain their existing signature or token verification. Never log Authorization values or plaintext passwords. Document that Basic authentication must be deployed behind HTTPS.

### Child work

Children must implement credential loading and verification, ASGI HTTP/WebSocket enforcement and health separation, MCP authentication behavior, first-party CLI and service-control client support, and operator documentation and security regression coverage.

### Dependencies

Credential loading is the foundation. Server enforcement depends on it. MCP and first-party client integration depend on server enforcement and may proceed in parallel. Documentation and final integration verification depend on all implementation children.

### Test requirements

Every child must add focused tests. The completed epic must pass make test and include end-to-end tests for auth disabled, valid credentials, invalid or absent credentials, malformed configuration, protected HTTP and WebSocket surfaces, protected MCP access, unauthenticated signed webhooks, and unauthenticated minimal health checks.

### Acceptance criteria

1. Starting Oompah with no discovered or configured htpasswd file preserves existing unauthenticated behavior.
2. Starting with a valid htpasswd file makes all in-scope HTTP, WebSocket, OpenAPI, and MCP surfaces require valid Basic credentials.
3. Invalid credentials return 401 with an appropriate WWW-Authenticate challenge and do not disclose why verification failed.
4. Missing or invalid explicitly configured credential files fail closed and explain remediation without exposing secrets.
5. GitHub and GitLab webhook delivery continues to work without Basic credentials and still requires the existing forge-specific authentication.
6. A minimal non-sensitive health endpoint remains suitable for process supervision without credentials.
7. Oompah CLIs and Makefile lifecycle operations can authenticate without putting passwords in URLs, logs, or command output.
8. Operator documentation covers setup, password creation and rotation, HTTPS, exclusions, client configuration, disablement, and recovery.
9. The full make test gate passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

