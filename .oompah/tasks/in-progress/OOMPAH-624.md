---
id: OOMPAH-624
type: bug
status: In Progress
priority: 1
title: Bind owner authorization to the authenticated server principal
parent: OOMPAH-619
children: []
blocked_by: []
start_blocked_by: []
labels:
- focus-complete:frontend
assignee: null
created_at: '2026-07-30T21:37:57.526368Z'
updated_at: '2026-07-30T21:41:33.187097Z'
work_branch: epic-OOMPAH-619--task-OOMPAH-624
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 008d12b488f0809330dcf4f75bc405d6d55a0607d8cbfcb384809cc5882d63f0
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-30T21:39:26.128500+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector  \nDuplicate preflight verdict: no_duplicate\
    \  \nMatches: none  \n\nEvidence: Reviewed active tasks OOMPAH-281 and OOMPAH-282;\
    \ neither concerns authorization identity binding. Archived OOMPAH-13 covers dashboard\
    \ actor fallback only and is terminal, so it cannot be a duplicate target."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 47663369-3e13-44da-8640-38c73995dbec
oompah.work_branch: epic-OOMPAH-619--task-OOMPAH-624
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-619--task-OOMPAH-624
  base_branch: epic-OOMPAH-619
  base_sha: c048ba706cbe9b1342b80a67576a49b82887e84a
  updated_at: '2026-07-30T21:41:29.105543+00:00'
oompah.task_costs:
  total_input_tokens: 177999
  total_output_tokens: 5508
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 177999
      output_tokens: 5508
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 177845
    output_tokens: 1184
    cost_usd: 0.0
    recorded_at: '2026-07-30T21:39:26.126861+00:00'
  - profile: default
    model: haiku
    input_tokens: 154
    output_tokens: 4324
    cost_usd: 0.0
    recorded_at: '2026-07-30T21:41:10.913452+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-624__20260730T213853Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: epic-OOMPAH-619--task-OOMPAH-624
    source_sha: c048ba706cbe9b1342b80a67576a49b82887e84a
    completed_at: '2026-07-30T21:39:26.134357+00:00'
  - run_id: OOMPAH-624__20260730T213945Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: frontend
    source_branch: epic-OOMPAH-619--task-OOMPAH-624
    source_sha: c048ba706cbe9b1342b80a67576a49b82887e84a
    completed_at: '2026-07-30T21:41:10.916822+00:00'
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

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 21:38
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 21:38
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-30 21:39
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 5
- Tokens: 177.8K in / 1.2K out [179.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 43s
- Log: OOMPAH-624__20260730T213853Z.jsonl
---
author: oompah
created: 2026-07-30 21:39
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-30 21:39
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-30 21:39
---
**Understanding**: This issue requires fixing the authentication/authorization boundary for task mutations. The server currently accepts client-supplied actor_login independently of HTTP authentication, allowing owner spoofing and forcing authenticated owners to use --actor. Core work involves: (1) exposing authenticated principal from auth middleware, (2) deriving authorization actor from trusted identity, (3) implementing username-to-actor mapping, (4) removing redundant --actor in CLIs, (5) comprehensive authorization tests. However, I notice this is categorized as 'Frontend Developer' role. This appears to be backend/security work affecting server auth middleware, API handlers, and CLI tools - not user-facing UI. I'm exploring the codebase to determine if there's a frontend component or if I should handoff to a backend/security specialist.
---
author: oompah
created: 2026-07-30 21:40
---
**Focus handoff: frontend** -- This is a backend/security issue that does not involve frontend UI work. After exploring the codebase, the required changes are:

**Changes needed:**
1. oompah/http_auth.py - Already has credential loading; needs to expose authenticated principal
2. oompah/server.py - FastAPI app needs middleware to expose authenticated principal to request handlers  
3. oompah/task_cli.py - Remove/deprecate redundant --actor flag when authenticated principal matches
4. oompah/admin_cli.py - Similar CLI changes
5. oompah/transition_gate.py - Use authenticated principal instead of actor_login for authorization
6. oompah/intake_actions.py - Same

**Frontend finding:**
- src/components/Dashboard.tsx is a stub ("useEffect cleanup" only)
- No UI components need changes for this security boundary fix
- Authorization is checked server-side, not displayed to user

**Recommended next focus:** backend/security specialist to implement authenticated principal exposure, username-to-actor mapping, and authorization refactoring. The orchestrator can dispatch immediately.
---
author: oompah
created: 2026-07-30 21:41
---
Agent completed successfully in 97s (4478 tokens)
---
author: oompah
created: 2026-07-30 21:41
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 41, Tool calls: 18
- Tokens: 154 in / 4.3K out [4.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 37s
- Log: OOMPAH-624__20260730T213945Z.jsonl
---
author: oompah
created: 2026-07-30 21:41
---
Focus handoff from `frontend` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-30 21:41
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-30 21:41
---
Focus: Security Auditor
---
<!-- COMMENTS:END -->
