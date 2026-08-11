---
id: OOMPAH-1129
type: bug
status: Backlog
priority: 2
title: Record authenticated actor provenance for orchestrator and project pause changes
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T22:38:43.861744Z'
updated_at: '2026-08-11T22:38:43.861744Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: incident-20260811-pause-resume-actor-provenance
  request_fingerprint: 738e1cd8e4736a45f2ce8c6021cab3e8725c1dbf66885804f3a29d6d88d46eed
---
## Summary

During the Trickle migration incident the server recorded an explicit orchestrator resume request at 2026-08-11T20:51:57Z, but neither logs nor retained state identify the authenticated principal or request source. Operators cannot determine who or what changed scheduling safety state.

Implementation scope:
- Add structured audit records for orchestrator and per-project pause/resume operations in oompah/server.py and the relevant persisted-state layer.
- Derive actor identity from the authenticated server principal or scoped capability; do not trust a caller-supplied actor field.
- Record timestamp, scope, previous/new state, request/correlation ID, and safe source metadata without storing credentials.
- Expose recent provenance through an operator API/UI surface and structured logs suitable for incident diagnosis.

Required tests:
- Exercise authenticated global and project pause/resume endpoints and verify complete provenance.
- Verify spoofed actor input cannot override the authenticated identity.
- Verify credentials and tokens never appear in audit records or logs.
- Verify provenance survives restart according to the documented retention policy.

Acceptance criteria:
- Every scheduling safety-state change can be attributed to an authenticated principal and request.
- Operators can distinguish API, UI, startup, and internal/system transitions.
- Existing pause/resume authorization and behavior remain unchanged.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

