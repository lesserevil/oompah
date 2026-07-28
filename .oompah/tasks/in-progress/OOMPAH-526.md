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
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-28T18:13:23.306052Z'
updated_at: '2026-07-28T20:11:36.001790Z'
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
author: oompah
created: 2026-07-28 20:10
---
Understanding: I will screen the task ledger and project docs for overlapping htpasswd/authentication work, read plausible candidates fully, and either confirm a duplicate or hand off with evidence without modifying implementation files.
---
author: oompah
created: 2026-07-28 20:11
---
Discovery: Duplicate screening found no duplicate. Reviewed OOMPAH-521 and its complete children OOMPAH-522 (htpasswd loading), OOMPAH-523 (ASGI HTTP/WebSocket boundary), OOMPAH-524 (MCP), and OOMPAH-525 (CLI/lifecycle client auth) in full; each is a distinct prerequisite or sibling scope for this documentation/integration task. OOMPAH-6 is unrelated GitHub API intake authentication, and OOMPAH-339 is unrelated GitLab label authorization. Repository searches across .oompah/tasks, docs, plans, README.md, and WORKFLOW.md found no separate htpasswd deployment/recovery documentation task.
---
author: oompah
created: 2026-07-28 20:11
---
Focus handoff: duplicate_detector\n\nOutcome: No duplicate confirmed; OOMPAH-526 is the distinct documentation and cross-surface validation child of OOMPAH-521.\n\nEvidence and decisions: Reviewed OOMPAH-521 and children OOMPAH-522 through OOMPAH-525 in full via ; their scopes are server credential loading, ASGI enforcement, MCP propagation, and CLI/lifecycle client credentials, respectively. Reviewed OOMPAH-6 and OOMPAH-339 as closest historical auth/GitLab candidates; they cover GitHub API intake credentials and GitLab label governance, not htpasswd deployment. Searched , , , , and  with rg for htpasswd, Basic auth, server/client passwords, and authentication. No implementation files were changed. Existing relevant surfaces include , , , , , , , , and their focused tests.\n\nRemaining work and risks: add/finish operator authentication documentation and links, ensure setting names and precedence agree across docs/.env.example/CLI/discovery, add documentation contract coverage where appropriate, and run cross-surface auth-off/auth-on, webhook, MCP, CLI, lifecycle, secret-scan, and full-gate verification. Preserve the exact public endpoint boundary and never include real credentials in docs, logs, URLs, argv, or fixtures.\n\nRecommended next focus: docs, followed by integration/security verification.
---
<!-- COMMENTS:END -->
