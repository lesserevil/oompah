---
id: OOMPAH-624
type: bug
status: Open
priority: 1
title: Bind owner authorization to the authenticated server principal
parent: OOMPAH-619
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T21:37:57.526368Z'
updated_at: '2026-07-30T21:38:29.865941Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Fix the authentication/authorization boundary for task and administrative mutations. The server currently accepts actor_login supplied by the client independently of the HTTP-authenticated principal, so an authenticated owner may still need --actor and an authenticated non-owner may be able to claim an owner identity.

Implementation scope:
- Expose the authenticated principal from the server authentication middleware to request handlers.
- Derive the effective authorization actor from that trusted principal for owner-gated task transitions, terminal overrides, intake actions, handoffs, and other mutations that currently consume caller-supplied actor_login.
- Define and implement the mapping between server authentication usernames and project actor logins when they differ; configuration must be explicit, validated, and documented.
- Make the task and admin CLIs omit redundant actor identity where the authenticated principal is sufficient. Deprecate, constrain, or reject --actor and actor_login when they conflict with the authenticated identity. Any supported impersonation must require explicit privileged authorization and produce an audit record.
- Preserve only intentionally unauthenticated/read-only compatibility; protected writes must fail closed when no trusted identity is available.
- Review relevant code in oompah/server authentication and API handlers, oompah/task_cli.py, oompah/admin_cli.py, oompah/transition_gate.py, and oompah/intake_actions.py.

Required tests:
- An authenticated project owner passes owner gates without --actor.
- An authenticated non-owner is denied owner-only operations.
- Supplying another users actor_login cannot spoof owner access.
- A conflicting actor value is rejected and does not mutate state.
- Explicit configured username-to-actor mapping works and invalid/ambiguous mappings fail closed.
- Task CLI, admin CLI, dashboard/API, audit-log, and unauthenticated regression coverage.

Acceptance criteria:
- Authorization decisions use a server-trusted authenticated identity, not an untrusted actor string from the request.
- The owner can perform owner-only operations after authenticating, with no second identity flag.
- Actor spoofing is covered by a regression test.
- Operator documentation explains identity mapping and any narrowly authorized impersonation flow.
- Focused tests and the complete Makefile gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

