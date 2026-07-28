---
id: OOMPAH-526
type: chore
status: In Progress
priority: 1
title: Document and validate secure htpasswd deployment and recovery
parent: OOMPAH-521
children: []
blocked_by:
- OOMPAH-522
- OOMPAH-523
- OOMPAH-524
- OOMPAH-525
labels: []
assignee: null
created_at: '2026-07-28T18:13:23.306052Z'
updated_at: '2026-07-28T20:10:05.747622Z'
work_branch: epic-OOMPAH-521
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: e2248382-f0d7-43f6-b30c-9a06d7e5c9c4
oompah.work_branch: epic-OOMPAH-521
---
## Summary

### Objective

Deliver operator-facing setup, rollout, verification, rotation, disablement, and recovery guidance for optional htpasswd authentication, then run cross-surface integration checks for the completed epic.

### Documentation scope

- Add a user-facing guide under `docs/`, linked from the operator runbook and relevant bootstrap/CLI documentation.
- Explain the distinction between `OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL` as the public Oompah URL, TLS termination, and htpasswd authentication.
- Provide copy-safe commands using the standard `htpasswd` utility to create a bcrypt credential file, add/update/remove users, set restrictive permissions, and install the file beside the selected `.env` or at `OOMPAH_HTPASSWD_FILE`.
- Explain that the server stores hashes while CLI clients need a separate plaintext credential source; document `OOMPAH_SERVER_USERNAME`, the preferred `OOMPAH_SERVER_PASSWORD_FILE`, and the limited environment-password alternative without encouraging secrets in URLs or command arguments.
- Document startup behavior for absent default files, explicit missing files, malformed/empty files, supported hash formats, restart-required rotation, and safe disablement.
- State prominently that HTTP Basic auth must be used behind HTTPS and that Oompah does not terminate TLS by itself. Include a reverse-proxy example without embedding real credentials.
- Enumerate the exact unauthenticated endpoints: minimal `GET /healthz` and the GitHub/GitLab webhook POST receivers. Explain that webhooks retain signature/token authentication and that hook status, dashboards, REST/OpenAPI, WebSocket, and MCP remain protected.
- Document browser behavior, curl/API examples using non-leaking credential mechanisms, MCP client configuration at a generic level, CLI setup, `make status`, graceful restart, 401 troubleshooting, file-permission failures, lockout recovery, and rollback.
- Ensure `.env.example`, CLI help, discovery metadata, and operator docs agree on names and precedence.

### Integration verification

Review the completed children as one security boundary. Confirm no route or mounted application omitted by unit-level tests, no documentation tells users to commit credential files, no client leaks credentials, and no webhook or lifecycle regression remains. Add contract tests for critical documentation/config examples where existing documentation-test patterns apply.

### Relevant files

A new `docs/authentication.md`, `docs/operator-runbook.md`, `docs/project-bootstrap.md`, `docs/cli-install.md`, `.env.example`, README/index links if present, CLI help text, MCP discovery documentation, and documentation contract tests.

### Dependencies

Depends on OOMPAH-522, OOMPAH-523, OOMPAH-524, and OOMPAH-525.

### Test requirements

Run focused tests from every implementation child, documentation contract tests, secret scanning through the Makefile target, and the complete `make test` gate. Manually smoke-test auth-off startup, auth-on browser/API access, MCP access, signed GitHub/GitLab webhook delivery without Basic credentials, CLI access, status, and graceful restart. Use generated disposable credentials only.

### Acceptance criteria

1. A new operator can enable authentication using only the documented steps and generated credentials.
2. The guide clearly requires HTTPS and correctly distinguishes the Oompah public URL from the GitLab forge URL.
3. Setup, rotation, adding/removing users, disablement, recovery from bad files or lockout, client use, MCP use, and webhook exclusions are documented accurately.
4. Credential files and plaintext passwords are neither committed nor shown in logs, URLs, process arguments, examples, or test fixtures.
5. Documentation, `.env.example`, CLI help, and runtime behavior use consistent setting names and precedence.
6. Cross-surface smoke tests pass in both disabled and enabled modes.
7. `make check-secrets` and the complete `make test` gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 20:10
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 20:10
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
