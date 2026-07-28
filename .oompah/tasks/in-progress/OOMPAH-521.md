---
id: OOMPAH-521
type: epic
status: In Progress
priority: 0
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
- epic:rebasing
assignee: null
created_at: '2026-07-28T18:10:41.609070Z'
updated_at: '2026-07-28T21:21:07.028407Z'
work_branch: epic-OOMPAH-521
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/567
review_number: '567'
merged_at: null
oompah.review_url: https://github.com/lesserevil/oompah/pull/567
oompah.review_number: '567'
oompah.work_branch: epic-OOMPAH-521
oompah.target_branch: main
oompah.agent_run_id: 1fe4b652-59d2-4d23-bd3b-a78ad519389e
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

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 21:17
---
Branch quality gate passed for `4a15c3ecb298cf0e4812146b2bba3d45877c2527` using `make test` in 69.0s. Review creation may proceed.
---
author: oompah
created: 2026-07-28 21:17
---
YOLO: Merge conflict detected on MR #567. Rebase `epic-OOMPAH-521` onto main and resolve conflicts.
---
author: oompah
created: 2026-07-28 21:17
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-28 21:17
---
Focus: Merge Conflict Resolver
---
author: oompah
created: 2026-07-28 21:17
---
Understanding: Task is to rebase epic-OOMPAH-521 (10 commits, OOMPAH-522/523/524/525/526) onto origin/main. Merge base is at 0237f7730 (Merge pull request #564). Main is 4 commits ahead (OOMPAH-457, OOMPAH-527). Will fetch, rebase, resolve conflicts, then run focused auth tests.
---
<!-- COMMENTS:END -->
