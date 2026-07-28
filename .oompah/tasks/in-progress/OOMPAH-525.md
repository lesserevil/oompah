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
labels: []
assignee: null
created_at: '2026-07-28T18:12:57.984075Z'
updated_at: '2026-07-28T19:30:04.165984Z'
work_branch: epic-OOMPAH-521
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 796d5adf-5fc9-4e36-afaf-10aee3847d29
oompah.work_branch: epic-OOMPAH-521
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
<!-- COMMENTS:END -->
