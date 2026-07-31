---
id: OOMPAH-670
type: task
status: Open
priority: null
title: Dashboard authenticated mutations must omit client-supplied actor identities
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T22:56:06.058439Z'
updated_at: '2026-07-31T23:02:03.180043Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: dee78a5f3d6e0185edec8c7096d78609e02af0974c9fa79e1bff6a11b9b7be26
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 234f8b5e-382c-468b-898a-3d446079aace
  claim_owner: 83d630e6-ba64-48af-a521-3ffb6e2a4e3f
  claimed_at: '2026-07-31T23:01:56.617004+00:00'
  claim_expires_at: '2026-07-31T23:31:56.617004+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 62a1a832-53cd-494b-8216-babc953ed38e
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
<!-- COMMENTS:END -->
