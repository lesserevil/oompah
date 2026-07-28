---
id: OOMPAH-525
type: feature
status: In Progress
priority: 1
title: Add Basic auth support to Oompah CLIs and lifecycle commands
parent: OOMPAH-521
children: []
blocked_by:
- OOMPAH-523
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-28T18:12:57.984075Z'
updated_at: '2026-07-28T19:37:50.081819Z'
work_branch: epic-OOMPAH-521
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: fb1d6b49-ab2b-4ff7-b304-f89ef517ac3b
oompah.work_branch: epic-OOMPAH-521
oompah.task_costs:
  total_input_tokens: 1933340
  total_output_tokens: 11195
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 1450196
      output_tokens: 8439
      cost_usd: 0.0
    sonnet:
      input_tokens: 483144
      output_tokens: 2756
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 1450196
    output_tokens: 8439
    cost_usd: 0.0
    recorded_at: '2026-07-28T19:33:09.124812+00:00'
  - profile: standard
    model: sonnet
    input_tokens: 483144
    output_tokens: 2756
    cost_usd: 0.0
    recorded_at: '2026-07-28T19:34:41.429724+00:00'
---
## Summary

### Objective

Keep first-party task, admin, and Makefile service-control workflows usable when server htpasswd authentication is enabled, with non-interactive credential handling that does not expose passwords in URLs, process arguments, logs, or command output.

### Implementation scope

- Add a shared client credential resolver used by `oompah task` and HTTP-backed `oompah admin` operations.
- Support `OOMPAH_SERVER_USERNAME` plus exactly one of `OOMPAH_SERVER_PASSWORD` or `OOMPAH_SERVER_PASSWORD_FILE`. Prefer the password-file form for unattended use. A password file contains only the client plaintext password, must be a regular readable file, and should trigger a warning or failure for unsafe permissions on POSIX systems according to documented behavior.
- Allow non-secret username and password-file CLI options if they fit existing parser conventions. Do not add a plaintext password command-line option.
- Send credentials using the HTTP client Basic-auth facility. Do not place userinfo in `OOMPAH_SERVER_URL`; reject or redact URLs containing credentials so error messages cannot leak them.
- Treat a 401 response as an authentication error with concise remediation distinct from connection failures. Never include response-reflected Authorization data or plaintext credentials.
- Update `make status`, `make restart`, and `make graceful` behavior for an authenticated server. The public `/healthz` probe may be used without credentials, but state and draining-restart API calls must authenticate. Pass credentials through a shared client helper or another mechanism that does not put the password in process arguments or printed recipes.
- Preserve safe restart semantics: missing or rejected credentials must stop before any interrupting fallback, and must never cause an automatic force restart.
- Keep client-only secrets out of server configuration passed to agent subprocesses. Documentation must distinguish server htpasswd hashes from client plaintext credentials.
- Preserve unauthenticated behavior when no client credentials are configured and the server has auth disabled.

### Relevant files

`oompah/task_cli.py`, `oompah/admin_cli.py`, a shared client auth helper if appropriate, `Makefile`, lifecycle tests such as `tests/test_makefile_restart_wait.py`, and CLI tests.

### Dependencies

Depends on OOMPAH-523. It may proceed in parallel with OOMPAH-524.

### Test requirements

Add tests for environment and password-file credential resolution, valid authenticated task/admin requests, missing username/password combinations, unreadable and unsafe password files, 401 remediation, URL credential redaction/rejection, and disabled-server compatibility. Extend Makefile recipe/integration tests to cover authenticated status and graceful restart, unauthenticated `/healthz`, no password in argv/output, rejected credentials causing no forced restart, and restart instance-ID verification.

### Acceptance criteria

1. Task and HTTP-backed admin CLI calls succeed against an authenticated server using supported client credential sources.
2. No supported path places a plaintext password in the server URL, process arguments, logs, errors, or normal output.
3. Missing, inconsistent, unreadable, or rejected credentials produce actionable errors without secret disclosure.
4. `make status`, `make restart`, and `make graceful` work with auth enabled and retain their drain and health guarantees.
5. Failed authentication never escalates to an interrupting restart.
6. Existing unauthenticated local workflows remain backward compatible.
7. Focused tests pass through the project test tooling.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 19:30
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 19:30
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 19:33
---
Agent completed successfully in 189s (1458635 tokens)
---
author: oompah
created: 2026-07-28 19:33
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 27
- Tokens: 1.5M in / 8.4K out [1.5M total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 9s
- Log: OOMPAH-525__20260728T193005Z.jsonl
---
author: oompah
created: 2026-07-28 19:33
---
Agent completed without closing this issue (189s (1458635 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-28 19:33
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-28 19:33
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 19:33
---
Understanding: I am performing the required duplicate review before any implementation. I will search existing auth/htpasswd-related tasks, read full candidate records, and either archive this task as a confirmed duplicate or hand it off with the closest evidence.
---
author: oompah
created: 2026-07-28 19:34
---
Discovery: Duplicate screening found no duplicate. Reviewed OOMPAH-522 (server htpasswd loading/verifier), OOMPAH-523 (ASGI HTTP/WebSocket enforcement and public /healthz), OOMPAH-524 (authenticated embedded MCP), and OOMPAH-526 (operator documentation/integration). Their scopes are prerequisites or follow-on documentation; none implements client credential resolution for task/admin CLIs or authenticated Makefile lifecycle APIs. Repository search across .oompah/tasks, docs, plans, README.md, and WORKFLOW.md found no separate task for this client/lifecycle scope.
---
author: oompah
created: 2026-07-28 19:34
---
Focus handoff: duplicate_detector\n\nOutcome: No duplicate confirmed; OOMPAH-525 is distinct client and lifecycle implementation work.\n\nEvidence: Searched .oompah/tasks, docs, plans, README.md, and WORKFLOW.md for htpasswd, Basic auth, client credentials, password files, authentication, and lifecycle commands. Read OOMPAH-522, OOMPAH-523, OOMPAH-524, and OOMPAH-526 in full. OOMPAH-522 owns server-side htpasswd loading/verification; 523 owns server route/WebSocket protection plus public /healthz; 524 owns MCP propagation; 526 is downstream docs/integration. None owns task_cli.py/admin_cli.py credential resolution or Makefile status/graceful/restart API authentication.\n\nRelevant implementation context: start with oompah/task_cli.py, oompah/admin_cli.py, Makefile, oompah/http_auth.py, oompah/server.py, and tests/test_makefile_restart_wait.py. Preserve the existing unauthenticated public /healthz probe; protected state and drain/restart APIs must use safe client-side Basic auth without secrets in URLs, argv, logs, or recipes.\n\nRemaining work/risk: implement and test credential source validation, password-file regular-file/permission checks, URL credential redaction/rejection, concise 401 remediation, safe no-force fallback on authentication failure, and backward compatibility.\n\nRecommended next focus: feature.
---
author: oompah
created: 2026-07-28 19:34
---
Agent completed successfully in 74s (485900 tokens)
---
author: oompah
created: 2026-07-28 19:34
---
Run #2 [attempt=2, profile=standard, role=standard -> Codex/gpt-5.6-terra]
- Turns: 1, Tool calls: 15
- Tokens: 483.1K in / 2.8K out [485.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 14s
- Log: OOMPAH-525__20260728T193329Z.jsonl
---
author: oompah
created: 2026-07-28 19:34
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-28 19:34
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-28 19:35
---
Focus: Security Auditor
---
author: oompah
created: 2026-07-28 19:35
---
Understanding: Security Auditor focus. I will audit the security design for OOMPAH-525 (Basic auth client support for task/admin CLIs and Makefile lifecycle commands), then implement the feature with security properties verified throughout. Attack vectors I will address: (1) credential leakage in URLs, process args, logs, errors; (2) password-file unsafe permissions (world-readable secrets); (3) 401 responses reflecting back auth data; (4) URL injection via OOMPAH_SERVER_URL with embedded userinfo; (5) forced restart escalation on auth failure; (6) timing side-channels in file permission checks; (7) symlink attacks on password files. I will implement: oompah/client_auth.py (shared resolver), task_cli.py/admin_cli.py integration, Makefile auth plumbing, and focused tests.
---
author: oompah
created: 2026-07-28 19:37
---
Discovery: Completed codebase analysis. Key findings:

1. Server-side auth (OOMPAH-522/523): FULLY IMPLEMENTED in oompah/http_auth.py (htpasswd loader/verifier) and oompah/server.py (_BasicAuthMiddleware). /healthz is public; /api/v1/state and other routes require auth.

2. Client-side auth: NOT YET IMPLEMENTED. task_cli.py uses httpx without auth; admin_cli.py uses urllib.request without auth.

3. Makefile: status/restart/graceful call curl for /api/v1/state and /api/v1/orchestrator/restart without auth. /healthz probe is already there but state calls lack auth.

4. Security attack vectors identified:
   - URL credential injection (OOMPAH_SERVER_URL with userinfo)
   - Password in curl argv (visible in /proc/*/cmdline)
   - Symlink attacks on password files
   - World-readable password files
   - 401 responses must not echo back credentials
   - Auth failure must not escalate to force-restart

Implementation plan:
- oompah/client_auth.py (new): shared resolver with URL sanitization, symlink rejection, permission warnings
- task_cli.py: add --username/--password-file, pass httpx BasicAuth, handle 401
- admin_cli.py: add auth via urllib.request, handle 401
- scripts/oompah_http.py (new): auth-aware helper for Makefile (avoids password in argv)
- Makefile: replace curl state/restart calls with scripts/oompah_http.py
- tests/test_client_auth.py (new): full credential resolver test suite
---
<!-- COMMENTS:END -->
