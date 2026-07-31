---
id: OOMPAH-670
type: task
status: In Progress
priority: null
title: Dashboard authenticated mutations must omit client-supplied actor identities
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T22:56:06.058439Z'
updated_at: '2026-07-31T23:03:10.880516Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: dee78a5f3d6e0185edec8c7096d78609e02af0974c9fa79e1bff6a11b9b7be26
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-31T23:02:39.111033+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\
    \nMatches: none\n\nEvidence: Reviewed active OOMPAH-281 (self-hosted CI runner)\
    \ and OOMPAH-282 (state-branch migration), both unrelated. Closest match is OOMPAH-13,\
    \ but it is Archived and implemented the inverse legacy behavior\u2014supplying\
    \ project actors to dashboard intake paths. OOMPAH-670 is a new authenticated-mode\
    \ correction: omit client actors while preserving unauthenticated compatibility."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 2dcbf35d-bd85-4dad-af1a-b78b09642038
oompah.task_costs:
  total_input_tokens: 217130
  total_output_tokens: 1406
  total_cost_usd: 0.0
  by_model:
    sonnet:
      input_tokens: 217130
      output_tokens: 1406
      cost_usd: 0.0
  runs:
  - profile: standard
    model: sonnet
    input_tokens: 217130
    output_tokens: 1406
    cost_usd: 0.0
    recorded_at: '2026-07-31T23:02:39.109732+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-670__20260731T230203Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-terra
    focus: duplicate_detector
    source_branch: OOMPAH-670
    source_sha: d96740a6ecdca353e40ef87e94a4ee91b8828df0
    completed_at: '2026-07-31T23:02:39.124795+00:00'
---
## Summary

Triggered by: OOMPAH-624 and the live Backlog → Open failure reproduced on 2026-07-31. With HTTP Basic authentication enabled, the dashboard's updateIssue() path derives projectStatusActorLogin(project) and injects actor_login into protected PATCH requests. The server now correctly binds authorization to the authenticated principal and rejects any differing client actor as actor_mismatch; in production the authenticated browser principal shedwards was rejected because the UI asserted lesserevil. The same stale client-actor pattern exists in dashboard intake detail/action paths. Update oompah/templates/dashboard.html so it consumes the state payload's http_auth.enabled signal and omits actor/actor_login from authenticated status and intake requests, letting the server derive the principal. Preserve the legacy actor path only for explicitly unauthenticated deployments. Ensure state refreshes and WebSocket updates keep the auth-mode flag current, and do not weaken server-side spoofing rejection. Add regression tests following existing dashboard and server actor-binding patterns for authenticated status moves, authenticated intake actions, differing project actor versus principal, unauthenticated compatibility, and auth-state refresh. Acceptance: an authorized authenticated operator can move Backlog tasks to Open and perform owner intake actions without actor_mismatch; the network payload contains no client actor when auth is enabled; unauthenticated deployments still send the configured actor; spoofed actors remain rejected server-side; focused tests and the complete Makefile gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 23:02
---
Duplicate screening dispatched (profile: standard, task remains Open)
---
author: oompah
created: 2026-07-31 23:02
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-31 23:02
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/gpt-5.6-terra]
- Turns: 1, Tool calls: 5
- Tokens: 217.1K in / 1.4K out [218.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 40s
- Log: OOMPAH-670__20260731T230203Z.jsonl
---
author: oompah
created: 2026-07-31 23:02
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-31 23:02
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-31 23:03
---
Understanding: With HTTP Basic authentication enabled, the dashboard incorrectly sends client-supplied actor_login in mutations (status updates, intake actions). The server correctly rejects mismatched actors as actor_mismatch. Solution: Update dashboard.html to detect http_auth.enabled from state and conditionally omit actor/actor_login fields in authenticated requests, while preserving the legacy actor path for unauthenticated deployments. Must maintain auth-state through refreshes and WebSocket updates. Planned approach: (1) Explore dashboard.html and related code, (2) Identify mutation request paths, (3) Detect http_auth.enabled in state, (4) Conditionally build payloads, (5) Add tests for both auth modes, (6) Verify no server-side spoofing weakening.
---
<!-- COMMENTS:END -->
